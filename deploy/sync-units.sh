#!/usr/bin/env bash
# auto-invest — systemd 유닛 동기화 (deploy-on-merge.yml 이 SSH 로 'sudo bash -s' 에 파이프).
#
# 목적: deploy/ 의 systemd 유닛(.service/.timer)을 서버 /etc/systemd/system 에 설치하고
# 타이머를 활성화한다. 또 polkit 규칙(deploy/50-auto-invest.rules)을 동기화한다. 스펙 006
# 배포 상태기계(`auto-invest deploy`)는 코드 git pull + 워커 재시작만 하고 '새 유닛/ polkit
# 규칙 설치'는 하지 않으므로, 그 빈틈을 이 스크립트가 채운다(cloud-init 은 서버 생성 때
# 한 번만 도므로 돌고 있는 서버엔 둘 다 유실될 수 있다).
#
# 안전:
#   - 워커(auto-invest.service)를 절대 재시작/시작하지 않는다 — 유닛 파일 설치 +
#     daemon-reload + 타이머 enable 만. 주문 라우팅과 무관하므로 장중에도 안전하다
#     (헌법 VIII.A '장중 배포 금지'는 워커 코드 교체/재시작에 대한 것이며, 유닛 정의
#     설치는 해당 없음). auto-invest-tune.timer 는 22:00 UTC 에만 발화하고, 튜너 자신의
#     market_hours_guard 가 장중 적용을 0건으로 막는다(이중 방어).
#   - 작업트리를 건드리지 않는다: `git show origin/main:<path>` 로 최신 내용만 읽어
#     설치하므로 배포 상태기계의 dirty-tree 검사와 충돌하지 않는다(git checkout/pull/reset 미사용).
#   - 멱등: install 덮어쓰기 + daemon-reload + enable --now 모두 반복 안전.

set -euo pipefail

REPO=/opt/auto-invest
REF=origin/main
UNITS=(
    auto-invest.service
    auto-invest-deploy.service
    auto-invest-deploy.timer
    auto-invest-tune.service
    auto-invest-tune.timer
)

echo "[sync-units] fetching ${REF} (read-only, no checkout)"
if ! sudo -u auto-invest git -C "$REPO" fetch origin main --quiet; then
    echo "[sync-units] WARN: git fetch failed — using whatever ${REF} the server already has" >&2
fi

installed=0
for u in "${UNITS[@]}"; do
    if sudo -u auto-invest git -C "$REPO" show "${REF}:deploy/${u}" > "/tmp/${u}.new" 2>/dev/null; then
        install -m 0644 "/tmp/${u}.new" "/etc/systemd/system/${u}"
        rm -f "/tmp/${u}.new"
        echo "[sync-units] installed ${u}"
        installed=$((installed + 1))
    else
        echo "[sync-units] skip (not in ${REF}): ${u}"
    fi
done

systemctl daemon-reload
echo "[sync-units] daemon-reload done (${installed} unit file(s) installed)"

# polkit 규칙 동기화: 비권한 `auto-invest` 사용자가 `auto-invest.service` 를 비대화식으로
# 관리(stop/start)하게 허용한다. 이게 없으면 배포 상태기계가 phase=stop_worker 에서
# "Interactive authentication required" 로 막혀 롤백한다. cloud-init(vultr-userdata.sh)은
# 서버 생성 때 한 번만 설치하므로, 규칙이 유실/미설치된 *돌고 있는* 서버를 매 배포마다
# 되살린다(systemd 유닛과 같은 빈틈 메우기). 멱등.
if sudo -u auto-invest git -C "$REPO" show "${REF}:deploy/50-auto-invest.rules" \
        > /tmp/50-auto-invest.rules.new 2>/dev/null; then
    install -d -m 0755 /etc/polkit-1/rules.d
    install -m 0644 /tmp/50-auto-invest.rules.new /etc/polkit-1/rules.d/50-auto-invest.rules
    rm -f /tmp/50-auto-invest.rules.new
    # 새 규칙을 실행 중인 polkitd 에 즉시 반영한다. 많은 배포판의 polkit.service 는
    # ExecReload 가 없어 `reload` 가 실패하므로(그러면 규칙이 안 올라가 stop_worker 가 계속
    # 막힌다 — 실제로 그랬다), cloud-init 과 동일하게 `reload` 실패 시 `restart` 로 떨어진다.
    # *polkit 만* 재시작한다 — 워커(auto-invest.service)는 절대 안 건드린다(polkit 재시작은
    # 잠깐 인가만 재질의시킬 뿐 워커 프로세스와 무관). 배포 상태기계가 곧바로 stop_worker 를
    # 호출하므로 즉시 반영이 중요하다.
    systemctl reload polkit 2>/dev/null || systemctl restart polkit 2>/dev/null || true
    echo "[sync-units] installed polkit rule 50-auto-invest.rules (+ reloaded/restarted polkit)"
else
    echo "[sync-units] skip (not in ${REF}): deploy/50-auto-invest.rules"
fi

# 타이머만 즉시 활성. 워커는 enable 만(운영자가 키 입력 후 start) — 절대 재시작하지 않음.
if [ -f /etc/systemd/system/auto-invest-deploy.timer ]; then
    systemctl enable --now auto-invest-deploy.timer
fi
if [ -f /etc/systemd/system/auto-invest-tune.timer ]; then
    systemctl enable --now auto-invest-tune.timer
fi
systemctl enable auto-invest.service || true

echo "[sync-units] timers:"
systemctl list-timers auto-invest-deploy.timer auto-invest-tune.timer --no-pager || true
echo "[sync-units] OK"

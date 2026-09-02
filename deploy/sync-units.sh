#!/usr/bin/env bash
# auto-invest — systemd 유닛 동기화 (forced-command gateway 의 'sync-units' 고정 명령).
#
# 목적: deploy/ 의 systemd 유닛(.service/.timer)을 서버 /etc/systemd/system 에 설치하고
# 타이머를 활성화한다. 또 sudoers 드롭인(deploy/auto-invest-deploy.sudoers)을 동기화한다
# (배포 상태기계가 워커를 `sudo -n systemctl` 로 제어하는 인가 경로). 스펙 006 배포 상태기계
# (`auto-invest deploy`)는 코드 git pull + 워커 재시작만 하고 '새 유닛/sudoers 설치'는 하지
# 않으므로, 그 빈틈을 이 스크립트가 채운다(cloud-init 은 서버 생성 때 한 번만 도므로 돌고
# 있는 서버엔 유실될 수 있다).
#
# 안전:
#   - 워커(auto-invest.service)를 절대 재시작/시작하지 않는다 — 유닛 파일 설치 +
#     daemon-reload + 타이머 enable 만. live-canary timer는 돈 경로이므로 설치 직후에도
#     exact deployed main·root systemd 신원·첫 진입 재검증·XNYS·공유 거래일 선점이 모두
#     통과해야만 주문할 수 있다. origin/main helper가 배포 HEAD보다 앞서면 배포 HEAD의 조상 관계와
#     고정 비실행 경로만 허용하는 운영 리비전 검사를 통과해야 한다. 실행 경로 변경은 실패 폐쇄한다.
#     auto-invest-tune.timer 는 22:00 UTC 에만 발화한다.
#   - 작업트리를 건드리지 않는다: `git show origin/main:<path>` 로 최신 내용만 읽어
#     설치하므로 배포 상태기계의 dirty-tree 검사와 충돌하지 않는다(git checkout/pull/reset 미사용).
#   - 멱등: install 덮어쓰기 + daemon-reload + enable --now 모두 반복 안전.

set -euo pipefail

REPO=/opt/auto-invest
REF=origin/main
TMP_ROOT=/run/auto-invest-deploy
UNITS=(
    auto-invest.service
    auto-invest-deploy.service
    auto-invest-deploy.timer
    auto-invest-tune.service
    auto-invest-tune.timer
    auto-invest-live-canary.service
    auto-invest-live-canary.timer
    auto-invest-telegram-alerts.service
)

if install -d -m 0700 -o root -g root "$TMP_ROOT" 2>/dev/null; then
    tmpdir="$(mktemp -d "${TMP_ROOT}/sync-units.XXXXXX")"
else
    tmpdir="$(mktemp -d)"
fi
trap 'rm -rf "$tmpdir"' EXIT

echo "[sync-units] fetching ${REF} (read-only, no checkout)"
if ! sudo -u auto-invest git -C "$REPO" fetch origin main --quiet; then
    echo "[sync-units] WARN: git fetch failed — using whatever ${REF} the server already has" >&2
fi

installed=0
for u in "${UNITS[@]}"; do
    unit_tmp="${tmpdir}/${u}.new"
    if sudo -u auto-invest git -C "$REPO" show "${REF}:deploy/${u}" > "$unit_tmp" 2>/dev/null; then
        install -m 0644 "$unit_tmp" "/etc/systemd/system/${u}"
        echo "[sync-units] installed ${u}"
        installed=$((installed + 1))
    else
        echo "[sync-units] skip (not in ${REF}): ${u}"
    fi
done

# Independent live-canary scheduler is a root-owned fixed helper. Installing it
# from origin/main does not authorize ahead-of-deploy runtime code: the helper
# and live order boundary both require deployed HEAD to be current main or its
# ancestor with only the frozen non-runtime path allowlist in between before the
# shared market-session claim can be consumed.
scheduler_tmp="${tmpdir}/live-canary-scheduled-on-instance.sh.new"
if sudo -u auto-invest git -C "$REPO" show \
        "${REF}:deploy/live-canary-scheduled-on-instance.sh" >"${scheduler_tmp}" 2>/dev/null; then
    install -m 0755 -o root -g root "${scheduler_tmp}" \
        /usr/local/sbin/auto-invest-live-canary-scheduler
    echo "[sync-units] installed root-owned live-canary scheduler helper"
else
    echo "[sync-units] skip (not in ${REF}): deploy/live-canary-scheduled-on-instance.sh"
fi

systemctl daemon-reload
echo "[sync-units] daemon-reload done (${installed} unit file(s) installed)"
if [ -f /etc/systemd/system/auto-invest-live-canary.service ] \
        && [ -f /etc/systemd/system/auto-invest-live-canary.timer ]; then
    systemd-analyze verify \
        /etc/systemd/system/auto-invest-live-canary.service \
        /etc/systemd/system/auto-invest-live-canary.timer
    echo "[sync-units] live-canary systemd units verified"
fi

# sudoers 동기화: 비권한 `auto-invest` 사용자가 워커 유닛만 비대화식 제어(stop/start)하게
# 허용한다 — 배포 상태기계가 `sudo -n systemctl …` 로 워커를 교체하는 결정론적 인가 경로
# (polkit 대체). **반드시 visudo 로 검증 후 설치** — 잘못된 /etc/sudoers.d 파일은 서버의 모든
# sudo(이 스크립트의 sudo 포함)를 깨뜨린다. 검증 실패 시 설치하지 않는다(안전). 멱등.
if sudo -u auto-invest git -C "$REPO" show "${REF}:deploy/auto-invest-deploy.sudoers" \
        > "${tmpdir}/ai-deploy.sudoers.new" 2>/dev/null; then
    if visudo -cf "${tmpdir}/ai-deploy.sudoers.new" >/dev/null 2>&1; then
        install -m 0440 -o root -g root "${tmpdir}/ai-deploy.sudoers.new" \
            /etc/sudoers.d/auto-invest-deploy
        echo "[sync-units] installed sudoers auto-invest-deploy (visudo-validated)"
    else
        echo "[sync-units] WARN: sudoers validation failed — NOT installing (sudo safety)" >&2
    fi
else
    echo "[sync-units] skip (not in ${REF}): deploy/auto-invest-deploy.sudoers"
fi

# (polkit 규칙은 제거됐다 — 워커 인가는 위 sudoers 가 결정론적으로 처리한다. polkit JS 규칙은
# 프로덕션 호스트에서 로드돼도 manage-units 를 인가하지 못했다. sudo 가 그 불확실성을 없앤다.)

# 타이머만 즉시 활성. 워커는 enable 만(운영자가 키 입력 후 start) — 절대 재시작하지 않음.
if [ -f /etc/systemd/system/auto-invest-deploy.timer ]; then
    systemctl enable --now auto-invest-deploy.timer
fi
if [ -f /etc/systemd/system/auto-invest-tune.timer ]; then
    systemctl enable --now auto-invest-tune.timer
fi
if [ -f /etc/systemd/system/auto-invest-live-canary.timer ]; then
    systemctl enable --now auto-invest-live-canary.timer
fi
systemctl enable auto-invest.service || true
# Telegram alerts are optional and require operator-provided TELEGRAM_* secrets.
# The unit is installed above but intentionally not enabled automatically.

echo "[sync-units] timers:"
systemctl list-timers auto-invest-deploy.timer auto-invest-tune.timer \
    auto-invest-live-canary.timer --no-pager || true
echo "[sync-units] OK"

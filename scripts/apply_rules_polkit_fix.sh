#!/usr/bin/env bash
# auto-invest — 기존 인스턴스의 두 가지 갭을 한 번에 메우는 스크립트.
#
# 이 스크립트가 메우는 갭 (둘 다 spec 006 / spec 010 통합에서 누락됐던 항목):
#
#   1. /opt/auto-invest/config/rules.toml 부재
#      → `auto-invest deploy --branch main`의 dry_run_check phase가
#        "rules file not found: config/rules.toml" 으로 실패.
#      → fix: tests/fixtures/rules/sample-canary.toml을 placeholder로
#        복사. spec 010의 `auto-invest design`이 OK 입력 시
#        config/rules_auto_<ts>.toml로 새로 작성하므로 이 placeholder는
#        첫 배포 통과용 임시 시드일 뿐.
#
#   2. /etc/polkit-1/rules.d/50-auto-invest.rules 부재
#      → deploy 중 rollback 또는 stop/start_worker phase에서
#        supervisor.start_worker()가 systemctl start auto-invest.service
#        를 호출 → polkit이 비밀번호 prompt → auto-invest 사용자는 패스워드
#        모름 → deploy 정체.
#      → fix: 매우 좁은 polkit rule 한 개 설치.
#        (manage-units + auto-invest 사용자 + auto-invest.service unit
#        조합만 무비밀 허용. 다른 모든 액션·사용자·unit은 기본 정책 유지.)
#
# 사용법 (인스턴스 콘솔에서 root로):
#
#   curl -sSL https://raw.githubusercontent.com/jinooaction/claude/main/scripts/apply_rules_polkit_fix.sh | sudo bash
#
# 또는 로컬에서:
#
#   sudo bash /opt/auto-invest/scripts/apply_rules_polkit_fix.sh
#
# 스크립트는 idempotent — 여러 번 실행해도 안전 (이미 적용된 경우 변경 없음).

set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/auto-invest}"

if [[ ! -d "${INSTALL_DIR}" ]]; then
    echo "ERROR: ${INSTALL_DIR} 디렉토리가 없습니다. cloud-init이 실행되지 않은 인스턴스입니다." >&2
    exit 2
fi

if [[ ! -f "${INSTALL_DIR}/tests/fixtures/rules/sample-canary.toml" ]]; then
    echo "ERROR: ${INSTALL_DIR}/tests/fixtures/rules/sample-canary.toml 이 없습니다." >&2
    echo "auto-invest deploy --branch main 으로 main 최신 코드를 먼저 받으세요." >&2
    exit 3
fi

echo "[1/2] /opt/auto-invest/config/rules.toml seed 확인"
install -d -m 0750 -o auto-invest -g auto-invest "${INSTALL_DIR}/config"
if [[ -f "${INSTALL_DIR}/config/rules.toml" ]]; then
    echo "    이미 존재 — 건너뜀 (덮어쓰지 않음)."
else
    install -m 0640 -o auto-invest -g auto-invest \
        "${INSTALL_DIR}/tests/fixtures/rules/sample-canary.toml" \
        "${INSTALL_DIR}/config/rules.toml"
    echo "    sample-canary fixture 로 seed 완료."
fi

echo "[2/2] /etc/polkit-1/rules.d/50-auto-invest.rules 설치"
install -d -m 0755 /etc/polkit-1/rules.d
cat > /etc/polkit-1/rules.d/50-auto-invest.rules <<'POLKIT_EOF'
polkit.addRule(function(action, subject) {
    if ((action.id == "org.freedesktop.systemd1.manage-units") &&
        subject.user == "auto-invest" &&
        action.lookup("unit") == "auto-invest.service") {
        return polkit.Result.YES;
    }
});
POLKIT_EOF
chmod 0644 /etc/polkit-1/rules.d/50-auto-invest.rules
systemctl reload polkit 2>/dev/null || systemctl restart polkit 2>/dev/null || true
echo "    polkit rule 설치 완료 + polkit reload."

echo
echo "============================================================"
echo "fix 적용 완료. 이제 다시 시도:"
echo
echo "  sudo -u auto-invest sh -c 'cd ${INSTALL_DIR} && \\"
echo "    /usr/local/bin/uv run --project ${INSTALL_DIR} auto-invest deploy --branch main' \\"
echo "    && sudo ${INSTALL_DIR}/scripts/set_secrets.sh"
echo
echo "그 후:"
echo
echo "  sudo -u auto-invest /usr/local/bin/uv run --project ${INSTALL_DIR} \\"
echo "    auto-invest design --intent \"자본 100달러, 미국 대형주 분산, 매주 월요일 적립, 위험 보통\""
echo "============================================================"

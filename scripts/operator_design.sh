#!/usr/bin/env bash
# auto-invest — 운영자 one-liner: design 명령 한 번에 실행.
#
# 운영자가 인스턴스 콘솔에서 단 한 줄로 design 시작:
#
#   sudo bash /opt/auto-invest/scripts/operator_design.sh "자본 100달러, 미국 대형주 분산, 매주 월요일 적립, 위험 보통"
#
# 또는 헬퍼를 받지 않은 인스턴스에서:
#
#   curl -sSL https://raw.githubusercontent.com/jinooaction/claude/main/scripts/operator_design.sh \
#     | sudo bash -s -- "자본 100달러, 미국 대형주 분산, 매주 월요일 적립, 위험 보통"
#
# 이 스크립트가 자동으로 처리하는 것:
#
#   1. main 최신 pull (auto-invest 사용자로) — detached HEAD 해결 포함.
#   2. apply_rules_polkit_fix.sh 멱등 호출 — config/rules.toml seed +
#      polkit rule 보장.
#   3. .env 검증 — KIS 키 빈 값이면 set_secrets.sh 호출, 이미 있으면 skip.
#   4. auto-invest design 호출 (모든 경로 명시 — cwd 의존성 없음).
#   5. design 실행 종료 후 상태 한 줄 요약 (라이브 worker 시작됐는지).
#
# 운영자가 한 번도 콘솔에서 여러 줄 입력할 필요 없도록 설계.
# 다만 design 의 OK prompt 는 보안상 그대로 유지 — 운영자가 룰 검토 후
# "OK" 한 번만 입력하면 라이브 시작 (구현부 보안 contract).

set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/auto-invest}"
ENV_PATH="${ENV_PATH:-${INSTALL_DIR}/.env}"
DB_PATH="${DB_PATH:-${INSTALL_DIR}/data/auto_invest.db}"
PRICES_PATH="${PRICES_PATH:-${INSTALL_DIR}/config/llm_prices.toml}"

INTENT="${1:-}"
if [[ -z "${INTENT}" ]]; then
    cat >&2 <<HELP
사용법:
    sudo bash $0 "<자연어 의도>"

예시:
    sudo bash $0 "자본 100달러, 미국 대형주 분산, 매주 월요일 적립, 위험 보통"

옵션 (환경변수):
    INSTALL_DIR    auto-invest 설치 디렉토리 (기본 /opt/auto-invest)
    ENV_PATH       .env 파일 경로 (기본 \${INSTALL_DIR}/.env)
    DB_PATH        SQLite DB 경로 (기본 \${INSTALL_DIR}/data/auto_invest.db)
    PRICES_PATH    Anthropic 가격표 (기본 \${INSTALL_DIR}/config/llm_prices.toml)

이 스크립트는 다음 5단계를 자동 처리:
    1. main 최신 pull
    2. polkit/rules.toml fix 멱등 적용
    3. KIS 키 있는지 확인, 없으면 set_secrets.sh prompt
    4. auto-invest design 호출
    5. 상태 요약 출력
HELP
    exit 2
fi

if [[ "$(id -u)" -ne 0 ]]; then
    echo "ERROR: 이 스크립트는 sudo 또는 root 로 실행하세요 (systemctl 호출 + auto-invest 사용자 전환 필요)." >&2
    exit 1
fi

if [[ ! -d "${INSTALL_DIR}" ]]; then
    echo "ERROR: ${INSTALL_DIR} 디렉토리가 없습니다. cloud-init 또는 repair_install.sh 먼저 실행하세요." >&2
    exit 2
fi

echo "============================================================"
echo "auto-invest design — 운영자 one-liner"
echo "  의도: ${INTENT}"
echo "  설치 디렉토리: ${INSTALL_DIR}"
echo "============================================================"

echo
echo "[1/5] main 최신 pull (auto-invest 사용자)"
# detached HEAD 환경 안전 처리 (fetch + checkout main + pull).
sudo -u auto-invest sh -c "
    cd '${INSTALL_DIR}' && \
    git fetch origin main && \
    git checkout main && \
    git pull origin main
" || {
    echo "WARNING: git pull 실패 — 기존 코드로 계속 진행." >&2
}

echo
echo "[2/5] polkit / config/rules.toml 멱등 fix"
if [[ -x "${INSTALL_DIR}/scripts/apply_rules_polkit_fix.sh" ]]; then
    bash "${INSTALL_DIR}/scripts/apply_rules_polkit_fix.sh"
else
    echo "  apply_rules_polkit_fix.sh 가 없음 — git pull 이 실패했거나 구버전. skip."
fi

echo
echo "[3/5] .env 의 KIS 키 검증"
need_set_secrets=0
if [[ ! -f "${ENV_PATH}" ]]; then
    echo "  ${ENV_PATH} 가 없음 — set_secrets.sh 가 필요합니다."
    need_set_secrets=1
else
    for key in KIS_APP_KEY KIS_APP_SECRET KIS_ACCOUNT_NO; do
        # .env 에서 KEY=value 행의 value 가 비어있으면 누락.
        value=$(grep -E "^${key}=" "${ENV_PATH}" 2>/dev/null | head -n1 | cut -d= -f2-)
        if [[ -z "${value}" ]]; then
            echo "  ${key} 가 비어있음 — set_secrets.sh 가 필요합니다."
            need_set_secrets=1
        fi
    done
fi

if [[ "${need_set_secrets}" -eq 1 ]]; then
    if [[ -x "${INSTALL_DIR}/scripts/set_secrets.sh" ]]; then
        echo "  set_secrets.sh 호출 — KIS 3개 + ANTHROPIC 키 prompt 가 차례로 뜹니다."
        bash "${INSTALL_DIR}/scripts/set_secrets.sh"
    else
        echo "ERROR: ${INSTALL_DIR}/scripts/set_secrets.sh 가 없습니다." >&2
        exit 3
    fi
else
    echo "  KIS 키 3개 모두 입력됨 — set_secrets.sh skip."
fi

# ANTHROPIC 키도 같이 검증 (design 에 필수).
anthropic_value=""
if [[ -f "${ENV_PATH}" ]]; then
    anthropic_value=$(grep -E "^ANTHROPIC_API_KEY=" "${ENV_PATH}" 2>/dev/null | head -n1 | cut -d= -f2-)
fi
if [[ -z "${anthropic_value}" ]]; then
    echo
    echo "WARNING: ANTHROPIC_API_KEY 가 ${ENV_PATH} 에 없거나 비어있습니다."
    echo "         design 명령은 Claude 호출이 필수입니다. set_secrets.sh 를 다시 실행하여"
    echo "         ANTHROPIC 키를 입력하세요 (KIS 키는 Enter 로 건너뛰면 기존 값 유지)."
    exit 4
fi

echo
echo "[4/5] auto-invest design 호출"
echo "  --env-file ${ENV_PATH}"
echo "  --db ${DB_PATH}"
echo "  --prices ${PRICES_PATH}"
echo
# 모든 경로를 명시적으로 줘서 cwd 의존성 회피. PR #26 받지 않은 인스턴스에서도 동작.
sudo -u auto-invest /usr/local/bin/uv run --project "${INSTALL_DIR}" \
    auto-invest design \
        --intent "${INTENT}" \
        --env-file "${ENV_PATH}" \
        --db "${DB_PATH}" \
        --prices "${PRICES_PATH}"
design_exit=$?

echo
echo "[5/5] 상태 요약"
if [[ ${design_exit} -eq 0 ]]; then
    echo "  design 명령 정상 종료."
    echo "  라이브 worker 상태 확인:"
    if sudo -u auto-invest /usr/local/bin/uv run --project "${INSTALL_DIR}" \
        auto-invest design --check --db "${DB_PATH}" 2>/dev/null; then
        echo
        echo "위 출력에 'live worker 시작 시각' 이 보이면 정상 동작 중입니다."
    else
        echo "  (--check 실패 — journalctl -u auto-invest.service -n 30 으로 확인하세요.)"
    fi
else
    echo "  design 명령 실패 (exit ${design_exit})."
    echo "  로그 확인:"
    echo "    journalctl -u auto-invest.service -n 50"
    echo "    sqlite3 ${DB_PATH} 'SELECT ts_utc, event_type, payload_json FROM audit_log WHERE event_type LIKE \"RULE_DESIGN_%\" ORDER BY seq DESC LIMIT 10'"
fi

echo "============================================================"
exit ${design_exit}

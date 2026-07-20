#!/usr/bin/env bash
# auto-invest — operator helper for proposal-only rule design.
#
# Console use:
#
#   bash /opt/auto-invest/scripts/operator_design.sh \
#     "자본 100달러, 미국 대형주 분산, 매주 월요일 적립, 위험 보통"
#
# GitHub Actions use:
#
#   INTENT_B64="$(printf '%s' "$INTENT" | base64 | tr -d '\n')" \
#     env INTENT_B64="$INTENT_B64" bash /opt/auto-invest/scripts/operator_design.sh
#
# The helper updates the repo, checks required local secrets, and runs
# `auto-invest design`. The command now creates an inert candidate and
# verification state only. It does not provide live activation authority.

set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/auto-invest}"
ENV_PATH="${ENV_PATH:-${INSTALL_DIR}/.env}"
DB_PATH="${DB_PATH:-${INSTALL_DIR}/data/auto_invest.db}"
PRICES_PATH="${PRICES_PATH:-${INSTALL_DIR}/config/llm_prices.toml}"

decode_intent_b64() {
    if [[ -z "${INTENT_B64:-}" ]]; then
        return 1
    fi
    if printf '%s' "${INTENT_B64}" | base64 --decode 2>/dev/null; then
        return 0
    fi
    printf '%s' "${INTENT_B64}" | base64 -d
}

INTENT="${1:-}"
if [[ -z "${INTENT}" && -n "${INTENT_B64:-}" ]]; then
    INTENT="$(decode_intent_b64)"
fi
if [[ -z "${INTENT}" && ! -t 0 ]]; then
    INTENT="$(cat)"
fi

if [[ -z "${INTENT}" ]]; then
    cat >&2 <<HELP
사용법:
    bash $0 "<자연어 의도>"

또는:
    printf '%s' "<자연어 의도>" | bash $0

옵션 (환경변수):
    INSTALL_DIR    auto-invest 설치 디렉토리 (기본 /opt/auto-invest)
    ENV_PATH       .env 파일 경로 (기본 \${INSTALL_DIR}/.env)
    DB_PATH        SQLite DB 경로 (기본 \${INSTALL_DIR}/data/auto_invest.db)
    PRICES_PATH    Anthropic 가격표 (기본 \${INSTALL_DIR}/config/llm_prices.toml)
    INTENT_B64     base64로 인코딩한 자연어 의도

이 스크립트는 후보 생성 전용입니다. 실거래 프로세스를 시작하지 않습니다.
HELP
    exit 2
fi

run_as_auto_invest() {
    if [[ "$(id -un)" == "auto-invest" ]]; then
        "$@"
    else
        sudo -n -u auto-invest "$@"
    fi
}

if [[ ! -d "${INSTALL_DIR}" ]]; then
    echo "ERROR: ${INSTALL_DIR} 디렉토리가 없습니다. cloud-init 또는 repair_install.sh 먼저 실행하세요." >&2
    exit 2
fi

echo "============================================================"
echo "auto-invest design — proposal-only helper"
echo "  의도 길이: ${#INTENT}자"
echo "  설치 디렉토리: ${INSTALL_DIR}"
echo "  권한: PROPOSAL_ONLY"
echo "============================================================"

echo
echo "[1/4] main 최신 pull (auto-invest 사용자)"
run_as_auto_invest sh -c "
    cd '${INSTALL_DIR}' && \
    git fetch origin main && \
    git checkout main && \
    git pull origin main
" || {
    echo "WARNING: git pull 실패 — 기존 코드로 계속 진행." >&2
}

echo
echo "[2/4] 권한 보정 자동 실행 없음"
echo "  proposal-only design은 root 보정 스크립트를 실행하지 않습니다."

echo
echo "[3/4] .env 의 읽기/설계용 키 검증"
need_set_secrets=0
if [[ ! -f "${ENV_PATH}" ]]; then
    echo "  ${ENV_PATH} 가 없음 — set_secrets.sh 가 필요합니다."
    need_set_secrets=1
else
    for key in KIS_APP_KEY KIS_APP_SECRET KIS_ACCOUNT_NO; do
        value=$(grep -E "^${key}=" "${ENV_PATH}" 2>/dev/null | head -n1 | cut -d= -f2-)
        if [[ -z "${value}" ]]; then
            echo "  ${key} 가 비어있음 — set_secrets.sh 가 필요합니다."
            need_set_secrets=1
        fi
    done
fi

if [[ "${need_set_secrets}" -eq 1 ]]; then
    echo "ERROR: 필요한 비밀값이 없습니다. 서버 콘솔에서 set_secrets.sh를 직접 실행한 뒤 다시 시도하세요." >&2
    exit 3
else
    echo "  KIS 키 3개 모두 입력됨 — set_secrets.sh skip."
fi

anthropic_value=""
if [[ -f "${ENV_PATH}" ]]; then
    anthropic_value=$(grep -E "^ANTHROPIC_API_KEY=" "${ENV_PATH}" 2>/dev/null | head -n1 | cut -d= -f2-)
fi
if [[ -z "${anthropic_value}" ]]; then
    echo
    echo "WARNING: ANTHROPIC_API_KEY 가 ${ENV_PATH} 에 없거나 비어있습니다."
    echo "         design 명령은 Claude 호출이 필수입니다. set_secrets.sh 를 다시 실행하세요."
    exit 4
fi

echo
echo "[4/4] auto-invest design 후보 생성"
echo "  --env-file ${ENV_PATH}"
echo "  --db ${DB_PATH}"
echo "  --prices ${PRICES_PATH}"
echo
run_as_auto_invest /usr/local/bin/uv run --project "${INSTALL_DIR}" \
    auto-invest design \
        --intent "${INTENT}" \
        --env-file "${ENV_PATH}" \
        --db "${DB_PATH}" \
        --prices "${PRICES_PATH}"
design_exit=$?

echo
if [[ ${design_exit} -eq 0 ]]; then
    echo "  design 명령 정상 종료."
    echo "  룰 후보와 검증 상태가 생성됐습니다. 실거래 프로세스는 시작하지 않았습니다."
else
    echo "  design 명령 실패 (exit ${design_exit})."
    echo "  로그 확인:"
    echo "    journalctl -u auto-invest.service -n 50"
    echo "    sqlite3 ${DB_PATH} 'SELECT ts_utc, event_type, payload_json FROM audit_log WHERE event_type LIKE \"RULE_DESIGN_%\" ORDER BY seq DESC LIMIT 10'"
fi

echo "============================================================"
exit "${design_exit}"

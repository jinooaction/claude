#!/usr/bin/env bash
# Fixed live-canary commands for the production instance.
#
# `order` is reachable only with a short-lived Ed25519 signature produced by the
# GitHub production environment. `fills` and `profit` cannot submit/cancel orders.

set -euo pipefail

REPO="${REPO:-/opt/auto-invest}"
APP_USER="${APP_USER:-auto-invest}"
PUBLIC_KEY="${PUBLIC_KEY:-/usr/local/share/auto-invest/live-order-signing-public.pem}"
NONCE_DIR="${NONCE_DIR:-/var/lib/auto-invest-live-order}"
NONCE_FILE="${NONCE_FILE:-${NONCE_DIR}/used-nonces}"
REPOSITORY="jinooaction/claude"
WORKFLOW="rebalance-live-canary.yml"
MAX_TTL_SEC=600

die() {
    echo "ERROR: $*" >&2
    exit 2
}

require_repo() {
    [[ -d "${REPO}/.git" ]] || die "missing repo: ${REPO}"
    cd "${REPO}"
}

run_cli() {
    sudo -u "${APP_USER}" -H /usr/local/bin/uv run auto-invest "$@"
}

git_as_app() {
    sudo -u "${APP_USER}" -H git -C "${REPO}" "$@"
}

validate_capital() {
    local capital="${1:-}"
    [[ "${capital}" =~ ^[0-9]+([.][0-9]+)?$ ]] || die "invalid capital"
    awk -v value="${capital}" 'BEGIN { exit !(value > 0) }' || die "capital must be positive"
}

sentinel_field() {
    local key="$1"
    awk -v key="${key}" '$1 == key ":" { print $2; exit }' automation/rebalance-live.request
}

validate_sentinel_authority() {
    local capital="$1"
    local armed sentinel_capital rung nav
    [[ -f automation/rebalance-live.request ]] || die "missing live arming sentinel"
    armed="$(sentinel_field armed)"
    sentinel_capital="$(sentinel_field capital_usd)"
    rung="$(sentinel_field ladder_rung)"
    nav="$(sentinel_field account_nav_usd)"

    [[ "${armed}" == "true" ]] || die "live sentinel is not armed"
    [[ "${sentinel_capital}" == "${capital}" ]] \
        || die "signed capital does not match sentinel"
    [[ "${rung}" =~ ^[0-9]+$ && "${rung}" -ge 1 ]] || die "invalid ladder rung"
    [[ "${nav}" =~ ^[0-9]+([.][0-9]+)?$ ]] || die "invalid account NAV"
    awk -v cap="${capital}" -v nav="${nav}" 'BEGIN { exit !(cap <= nav) }' \
        || die "capital exceeds sentinel account NAV"
}

is_deploy_ignored_path() {
    case "$1" in
        *.md|specs/*|.verify/*|.trigger/*) return 0 ;;
        *) return 1 ;;
    esac
}

validate_deployed_commit() {
    local signed_sha="$1"
    local deployed_sha path
    git_as_app fetch origin main --quiet \
        || die "failed to refresh signed main commit"
    git_as_app cat-file -e "${signed_sha}^{commit}" 2>/dev/null \
        || die "signed commit is not available on the server"
    deployed_sha="$(git_as_app rev-parse HEAD)"
    git_as_app merge-base --is-ancestor "${deployed_sha}" "${signed_sha}" \
        || die "deployed commit is not an ancestor of signed main"
    while IFS= read -r path; do
        [[ -z "${path}" ]] && continue
        is_deploy_ignored_path "${path}" \
            || die "server code differs from signed main: ${path}"
    done < <(git_as_app diff --name-only "${deployed_sha}" "${signed_sha}")
}

verify_signature() {
    local payload="$1"
    local signature_b64="$2"
    local tmpdir
    [[ -f "${PUBLIC_KEY}" ]] || die "missing live order public key"
    [[ "${signature_b64}" =~ ^[A-Za-z0-9+/]+={0,2}$ ]] || die "invalid signature encoding"
    tmpdir="$(mktemp -d)"
    trap 'rm -rf "${tmpdir}"' RETURN
    printf '%s' "${payload}" > "${tmpdir}/payload"
    printf '%s' "${signature_b64}" | base64 -d > "${tmpdir}/signature" 2>/dev/null \
        || die "invalid signature base64"
    openssl pkeyutl -verify -pubin -inkey "${PUBLIC_KEY}" \
        -sigfile "${tmpdir}/signature" -rawin -in "${tmpdir}/payload" >/dev/null 2>&1 \
        || die "live order signature verification failed"
    rm -rf "${tmpdir}"
    trap - RETURN
}

consume_nonce() {
    local nonce="$1"
    install -d -m 0700 "${NONCE_DIR}"
    touch "${NONCE_FILE}"
    chmod 0600 "${NONCE_FILE}"
    exec 9>>"${NONCE_FILE}"
    flock -x 9
    if grep -Fqx -- "${nonce}" "${NONCE_FILE}"; then
        die "live order nonce already used"
    fi
    printf '%s\n' "${nonce}" >&9
    flock -u 9
}

verify_order_request() {
    local run_id="$1" signed_sha="$2" capital="$3" expires="$4" nonce="$5" signature="$6"
    local now payload
    [[ "${run_id}" =~ ^[0-9]+$ ]] || die "invalid run id"
    [[ "${signed_sha}" =~ ^[0-9a-f]{40}$ ]] || die "invalid signed commit"
    validate_capital "${capital}"
    [[ "${expires}" =~ ^[0-9]+$ ]] || die "invalid expiry"
    [[ "${nonce}" =~ ^[0-9]+-[0-9]+$ ]] || die "invalid nonce"
    now="$(date +%s)"
    (( expires >= now )) || die "live order signature expired"
    (( expires - now <= MAX_TTL_SEC )) || die "live order expiry exceeds maximum TTL"

    payload="${REPOSITORY}|${WORKFLOW}|${run_id}|${signed_sha}|${capital}|${expires}|${nonce}"
    verify_signature "${payload}" "${signature}"
    require_repo
    validate_sentinel_authority "${capital}"
    validate_deployed_commit "${signed_sha}"
    consume_nonce "${nonce}"
    echo "LIVE_ORDER_AUTHORIZED run_id=${run_id} commit=${signed_sha} capital=${capital} nonce=${nonce}"
}

place_order() {
    local run_id="$1" signed_sha="$2" capital="$3" expires="$4" nonce="$5" signature="$6"
    verify_order_request "${run_id}" "${signed_sha}" "${capital}" "${expires}" "${nonce}" "${signature}"
    run_cli rebalance-once \
        --portfolio deploy/canary-live-portfolio.toml \
        --mode live \
        --confirm-live \
        --account-wide \
        --capital "${capital}" \
        --db data/auto_invest.db \
        --env-file .env \
        --json
}

sync_fills() {
    require_repo
    run_cli fills --sync --db data/auto_invest.db --env .env
}

measure_profit() {
    local capital="$1"
    validate_capital "${capital}"
    require_repo
    run_cli performance \
        --since 1970-01-01T00:00:00Z \
        --mode live \
        --capital "${capital}" \
        --db data/auto_invest.db \
        --env .env \
        --snapshot \
        --slippage \
        --format json
}

main() {
    local command="${1:-}"
    shift || true
    case "${command}" in
        order)
            [[ "$#" -eq 6 ]] || die "order requires run_id commit capital expiry nonce signature"
            place_order "$@"
            ;;
        verify-order)
            [[ "$#" -eq 6 ]] || die "verify-order requires run_id commit capital expiry nonce signature"
            verify_order_request "$@"
            ;;
        fills)
            [[ "$#" -eq 0 ]] || die "fills takes no args"
            sync_fills
            ;;
        profit)
            [[ "$#" -eq 1 ]] || die "profit requires capital"
            measure_profit "$1"
            ;;
        *)
            die "unknown live-canary command: ${command:-missing}"
            ;;
    esac
}

main "$@"

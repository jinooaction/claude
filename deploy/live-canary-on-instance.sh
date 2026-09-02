#!/usr/bin/env bash
# Fixed live-canary commands for the production instance.
#
# `order` is reachable only with a short-lived Ed25519 signature produced by the
# GitHub production environment. `systemd-order` is reachable only as a direct
# child of the fixed root-owned live-canary systemd unit. Both converge on the
# same market-session claim. `fills`, `profit`, and `scheduled-status` cannot
# submit/cancel orders.

set -euo pipefail

REPO="${REPO:-/opt/auto-invest}"
APP_USER="${APP_USER:-auto-invest}"
PUBLIC_KEY="${PUBLIC_KEY:-/usr/local/share/auto-invest/live-order-signing-public.pem}"
NONCE_DIR="${NONCE_DIR:-/var/lib/auto-invest-live-order}"
NONCE_FILE="${NONCE_FILE:-${NONCE_DIR}/used-nonces}"
SESSION_FILE="${SESSION_FILE:-${NONCE_DIR}/order-sessions.tsv}"
SCHEDULED_RUNS_DIR="${SCHEDULED_RUNS_DIR:-${NONCE_DIR}/scheduled-runs}"
SCHEDULED_LAST_RUN_FILE="${SCHEDULED_LAST_RUN_FILE:-${NONCE_DIR}/last-scheduled-run-id}"
DEPLOY_MAINTENANCE_INTERLOCK="${DEPLOY_MAINTENANCE_INTERLOCK:-/run/auto-invest-deploy/live-order-maintenance.lock}"
BROKER_WRITE_LOCK_PATH="${BROKER_WRITE_LOCK_PATH:-/run/auto-invest-deploy/broker-write.lock}"
UV_BIN="${UV_BIN:-/usr/local/bin/uv}"
REPOSITORY="jinooaction/claude"
WORKFLOW="rebalance-live-canary.yml"
MAX_TTL_SEC=600
DEPLOYED_CODE_COMMIT=""
MAIN_CODE_COMMIT=""

die() {
    echo "ERROR: $*" >&2
    exit 2
}

refuse_deploy_maintenance() {
    [[ ! -e "${DEPLOY_MAINTENANCE_INTERLOCK}" ]] \
        || die "live broker writes are halted for an owner emergency deploy"
}

acquire_broker_write_lock() {
    [[ -f "${BROKER_WRITE_LOCK_PATH}" && ! -L "${BROKER_WRITE_LOCK_PATH}" ]] \
        || die "missing or unsafe broker-write coordination lock"
    exec 7<>"${BROKER_WRITE_LOCK_PATH}"
    flock -n -s 7 || die "owner emergency deploy owns broker-write coordination lock"
    refuse_deploy_maintenance
}

require_repo() {
    [[ -d "${REPO}/.git" ]] || die "missing repo: ${REPO}"
    cd "${REPO}"
}

run_cli() {
    sudo -u "${APP_USER}" -H "${UV_BIN}" run auto-invest "$@"
}

market_session_key() {
    sudo -u "${APP_USER}" -H "${UV_BIN}" run \
        python -m auto_invest.execution.live_session
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
    local authority_mode="${2:-signed-history}"
    local deployed_sha main_sha path changed_paths
    case "${authority_mode}" in
        signed-history|current-main) ;;
        *) die "invalid operational revision authority mode" ;;
    esac
    git_as_app fetch origin main --quiet \
        || die "failed to refresh signed main commit"
    git_as_app cat-file -e "${signed_sha}^{commit}" 2>/dev/null \
        || die "signed commit is not available on the server"
    deployed_sha="$(git_as_app rev-parse HEAD)"
    main_sha="$(git_as_app rev-parse origin/main)"
    [[ "${deployed_sha}" =~ ^[0-9a-f]{40}$ && "${main_sha}" =~ ^[0-9a-f]{40}$ ]] \
        || die "invalid operational revision commit"
    if [[ "${authority_mode}" == "current-main" && "${signed_sha}" != "${main_sha}" ]]; then
        die "server timer requires current main authority"
    fi
    git_as_app merge-base --is-ancestor "${deployed_sha}" "${signed_sha}" \
        || die "deployed commit is not an ancestor of signed main"
    changed_paths="$(git_as_app diff --name-only "${deployed_sha}" "${signed_sha}")" \
        || die "failed to classify operational revision paths"
    while IFS= read -r path; do
        [[ -z "${path}" ]] && continue
        is_deploy_ignored_path "${path}" \
            || die "server code differs from signed main: ${path}"
    done <<< "${changed_paths}"
    DEPLOYED_CODE_COMMIT="${deployed_sha}"
    MAIN_CODE_COMMIT="${main_sha}"
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

claim_order_session() {
    local run_id="$1" signed_sha="$2" source="$3"
    local session_key session_exit claimed_at existing first_run_id first_source
    case "${source}" in
        github_schedule|server_timer) ;;
        *) die "invalid live order source" ;;
    esac
    set +e
    session_key="$(market_session_key)"
    session_exit=$?
    set -e
    if [[ "${session_exit}" != "0" ]]; then
        return "${session_exit}"
    fi
    [[ "${session_key}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] \
        || die "invalid XNYS session key"

    install -d -m 0700 "${NONCE_DIR}"
    touch "${SESSION_FILE}"
    chmod 0600 "${SESSION_FILE}"
    exec 8>>"${SESSION_FILE}"
    flock -x 8
    existing="$(awk -F '\t' -v key="${session_key}" '$1 == key { print; exit }' "${SESSION_FILE}")"
    if [[ -n "${existing}" ]]; then
        first_run_id="$(printf '%s\n' "${existing}" | awk -F '\t' '{ print $2 }')"
        first_source="$(printf '%s\n' "${existing}" | awk -F '\t' '{ print $5 }')"
        [[ -n "${first_source}" ]] || first_source="legacy"
        echo "LIVE_ORDER_SESSION_ALREADY_CLAIMED market_session=${session_key} first_run_id=${first_run_id} first_source=${first_source}"
        flock -u 8
        return 0
    fi

    claimed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf '%s\t%s\t%s\t%s\t%s\n' \
        "${session_key}" "${run_id}" "${signed_sha}" "${claimed_at}" "${source}" >&8
    flock -u 8
    echo "LIVE_ORDER_SESSION_CLAIMED market_session=${session_key} run_id=${run_id} source=${source} claimed_at=${claimed_at}"
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

validate_macro_evidence_revision() {
    local evidence="$1" signed_sha="$2" evidence_sha
    evidence_sha="$(jq -er '.code_commit | select(test("^[0-9a-f]{40}$"))' "${evidence}")" \
        || die "macro evidence code commit is missing or invalid"
    git_as_app cat-file -e "${evidence_sha}^{commit}" 2>/dev/null \
        || die "macro evidence commit is unavailable on the server"
    git_as_app merge-base --is-ancestor "${evidence_sha}" "${signed_sha}" \
        || die "macro evidence was not produced by signed main history"
}

require_systemd_invocation() {
    [[ "$(id -u)" -eq 0 ]] || die "server timer order requires root"
    [[ "${INVOCATION_ID:-}" =~ ^[0-9a-f]{32}$ ]] \
        || die "missing or invalid systemd invocation id"
    [[ "${PPID}" =~ ^[0-9]+$ ]] || die "invalid server timer parent"
    grep -Eq '/auto-invest-live-canary\.service$' "/proc/${PPID}/cgroup" \
        || die "server timer order must be a direct child of its fixed systemd unit"
}

verify_systemd_request() {
    local run_id="$1" signed_sha="$2" capital="$3"
    [[ "${run_id}" =~ ^[0-9]{14}$ ]] || die "invalid server timer run id"
    [[ "${signed_sha}" =~ ^[0-9a-f]{40}$ ]] || die "invalid current main commit"
    validate_capital "${capital}"
    require_systemd_invocation
    require_repo
    validate_sentinel_authority "${capital}"
    [[ ! -e automation/AUTOARM_DISABLED ]] || die "AUTOARM_DISABLED kill switch is active"
    [[ "$(sentinel_field ladder_rung)" == "1" ]] \
        || die "server timer order is limited to ladder rung 1"
    [[ "$(sentinel_field entry_route)" == "operational_canary" ]] \
        || die "server timer order requires operational_canary entry route"
    validate_deployed_commit "${signed_sha}" "current-main"
    echo "LIVE_ORDER_AUTHORIZED source=server_timer run_id=${run_id} commit=${signed_sha} deployed_commit=${DEPLOYED_CODE_COMMIT} operational_equivalent=true capital=${capital}"
}

place_order_authorized() {
    local source="$1" run_id="$2" signed_sha="$3" capital="$4"
    local claim_output claim_exit
    local -a cli_args
    refuse_deploy_maintenance
    acquire_broker_write_lock
    refuse_deploy_maintenance
    set +e
    claim_output="$(claim_order_session "${run_id}" "${signed_sha}" "${source}")"
    claim_exit=$?
    set -e
    if [[ -n "${claim_output}" ]]; then
        echo "${claim_output}"
    fi
    if [[ "${claim_exit}" != "0" ]]; then
        return "${claim_exit}"
    fi
    if [[ "${claim_output}" == LIVE_ORDER_SESSION_ALREADY_CLAIMED* ]]; then
        return 0
    fi

    cli_args=(
        rebalance-once
        --portfolio deploy/canary-live-portfolio.toml
        --mode live
        --confirm-live
        --account-wide
        --capital "${capital}"
        --db data/auto_invest.db
        --env-file .env
    )
    if grep -Fq '[portfolio.macro_policy]' deploy/canary-live-portfolio.toml; then
        local evidence="/tmp/auto-invest-macro-strategy-factory.json"
        git_as_app fetch origin automation/autonomous-strategy-factory-last-run --quiet \
            || die "failed to refresh macro strategy evidence"
        git_as_app show \
            origin/automation/autonomous-strategy-factory-last-run:macro_strategy_factory.json \
            > "${evidence}" \
            || die "missing macro strategy evidence"
        validate_macro_evidence_revision "${evidence}" "${signed_sha}"
        chmod 0644 "${evidence}"
        cli_args+=(--macro-evidence "${evidence}")
    fi
    cli_args+=(--json)
    run_cli "${cli_args[@]}"
}

place_order() {
    local run_id="$1" signed_sha="$2" capital="$3" expires="$4" nonce="$5" signature="$6"
    verify_order_request "${run_id}" "${signed_sha}" "${capital}" "${expires}" "${nonce}" "${signature}"
    place_order_authorized "github_schedule" "${run_id}" "${signed_sha}" "${capital}"
}

place_systemd_order() {
    local run_id="$1" signed_sha="$2" capital="$3"
    verify_systemd_request "${run_id}" "${signed_sha}" "${capital}"
    place_order_authorized "server_timer" "${run_id}" "${signed_sha}" "${capital}"
}

scheduled_status() {
    local run_id="${1:-}" summary
    if [[ -z "${run_id}" ]]; then
        [[ -f "${SCHEDULED_LAST_RUN_FILE}" && ! -L "${SCHEDULED_LAST_RUN_FILE}" ]] \
            || die "no server-scheduled live canary evidence"
        run_id="$(tr -d '\r\n' < "${SCHEDULED_LAST_RUN_FILE}")"
    fi
    [[ "${run_id}" =~ ^[0-9]{14}$ ]] || die "invalid scheduled run pointer"
    summary="${SCHEDULED_RUNS_DIR}/${run_id}/summary.json"
    [[ -f "${summary}" && ! -L "${summary}" ]] || die "missing scheduled run summary"
    jq -e \
        --arg run_id "${run_id}" \
        '.schema_version == "1.1" and .run_id == $run_id and .source == "server_timer" and
         (.code_commit | test("^[0-9a-f]{40}$")) and
         (.deployed_code_commit | test("^[0-9a-f]{40}$")) and
         .operational_equivalent == true' \
        "${summary}" >/dev/null || die "invalid scheduled run summary"
    cat "${summary}"
}

sync_fills() {
    local -a date_args=()
    if [[ "$#" -eq 2 ]]; then
        [[ "$1" =~ ^[0-9]{8}$ && "$2" =~ ^[0-9]{8}$ ]] \
            || die "fill recovery dates must use YYYYMMDD"
        date_args=(--order-start-date "$1" --order-end-date "$2")
    elif [[ "$#" -ne 0 ]]; then
        die "fills accepts zero args or start/end dates"
    fi
    require_repo
    run_cli fills --sync --db data/auto_invest.db --env .env "${date_args[@]}"
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
        --opening-positions deploy/live-opening-positions.toml \
        --portfolio deploy/canary-live-portfolio.toml \
        --strategy-scope \
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
        systemd-order)
            [[ "$#" -eq 3 ]] || die "systemd-order requires run_id commit capital"
            place_systemd_order "$@"
            ;;
        fills)
            [[ "$#" -eq 0 || "$#" -eq 2 ]] || die "fills accepts zero args or start/end dates"
            sync_fills "$@"
            ;;
        profit)
            [[ "$#" -eq 1 ]] || die "profit requires capital"
            measure_profit "$1"
            ;;
        scheduled-status)
            [[ "$#" -le 1 ]] || die "scheduled-status takes at most one run id"
            scheduled_status "${1:-}"
            ;;
        *)
            die "unknown live-canary command: ${command:-missing}"
            ;;
    esac
}

main "$@"

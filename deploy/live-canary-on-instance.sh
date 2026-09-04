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
RETRY_SESSION_FILE="${NONCE_DIR}/order-session-retries.tsv"
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
RETRY_MANIFEST_PATH="deploy/live-canary-retry-incident.json"
RETRY_EXISTING_RUN_ID=""

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

file_owned_by_root() {
    local owner
    owner="$(stat -c '%u' "$1" 2>/dev/null || stat -f '%u' "$1" 2>/dev/null)" \
        || return 1
    [[ "${owner}" == "0" ]]
}

file_mode() {
    stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1" 2>/dev/null
}

safe_root_evidence_file() {
    local path="$1" mode
    [[ -f "${path}" && ! -L "${path}" ]] || return 1
    file_owned_by_root "${path}" || return 1
    mode="$(file_mode "${path}")" || return 1
    [[ "${mode}" == "600" ]]
}

sha256_file() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{ print $1 }'
    else
        shasum -a 256 "$1" | awk '{ print $1 }'
    fi
}

fresh_kis_open_order_proof() {
    local deployed_sha="$1" smoke_output smoke_exit
    smoke_output="$(mktemp)" || return 1
    set +e
    /usr/local/sbin/auto-invest-kis-smoke "${deployed_sha}" \
        >"${smoke_output}" 2>&1
    smoke_exit=$?
    set -e
    if [[ "${smoke_exit}" -ne 0 ]] \
        || ! grep -Eq 'open_unfilled[=:][[:space:]]*0([^0-9]|$)' "${smoke_output}"; then
        rm -f "${smoke_output}"
        return 1
    fi
    rm -f "${smoke_output}"
}

existing_retry_run_id() {
    local session_key="$1" existing=""
    RETRY_EXISTING_RUN_ID=""
    [[ -e "${RETRY_SESSION_FILE}" ]] || return 1
    [[ -f "${RETRY_SESSION_FILE}" && ! -L "${RETRY_SESSION_FILE}" ]] || return 2
    file_owned_by_root "${RETRY_SESSION_FILE}" || return 2
    exec 5<"${RETRY_SESSION_FILE}" || return 2
    flock -s 5 || {
        exec 5<&-
        return 2
    }
    existing="$(awk -F '\t' -v key="${session_key}" '$1 == key { print; exit }' \
        "${RETRY_SESSION_FILE}")"
    flock -u 5
    exec 5<&-
    [[ -n "${existing}" ]] || return 1
    RETRY_EXISTING_RUN_ID="$(printf '%s\n' "${existing}" | awk -F '\t' '{ print $5 }')"
    [[ "${RETRY_EXISTING_RUN_ID}" =~ ^[0-9]{14}$ ]] || return 2
    return 0
}

claim_same_session_retry() {
    local session_key="$1" first_run_id="$2" first_source="$3" first_code_commit="$4"
    local retry_run_id="$5" deployed_sha="$6"
    local run_dir summary order_log reconciliation manifest_tmp manifest_sha claimed_at
    local retry_status existing

    [[ "${first_source}" == "server_timer" ]] || return 1
    [[ "${first_run_id}" =~ ^[0-9]{14}$ && "${retry_run_id}" =~ ^[0-9]{14}$ ]] \
        || return 1
    [[ "${first_code_commit}" =~ ^[0-9a-f]{40}$ \
        && "${deployed_sha}" =~ ^[0-9a-f]{40}$ ]] || return 1
    [[ "${retry_run_id}" != "${first_run_id}" ]] || return 1
    existing_retry_run_id "${session_key}"
    retry_status=$?
    [[ "${retry_status}" -eq 1 ]] || return 1

    run_dir="${SCHEDULED_RUNS_DIR}/${first_run_id}"
    summary="${run_dir}/summary.json"
    order_log="${run_dir}/order.log"
    reconciliation="${run_dir}/reconciliation.json"
    [[ -d "${SCHEDULED_RUNS_DIR}" && ! -L "${SCHEDULED_RUNS_DIR}" \
        && -d "${run_dir}" && ! -L "${run_dir}" ]] || return 1
    file_owned_by_root "${SCHEDULED_RUNS_DIR}" || return 1
    file_owned_by_root "${run_dir}" || return 1
    safe_root_evidence_file "${summary}" || return 1
    safe_root_evidence_file "${order_log}" || return 1
    safe_root_evidence_file "${reconciliation}" || return 1

    jq -e \
        --arg session "${session_key}" \
        --arg first_run_id "${first_run_id}" \
        --arg first_code "${first_code_commit}" '
        .schema_version == "1.1" and
        .run_id == $first_run_id and .source == "server_timer" and
        .market_session == $session and .code_commit == $first_code and
        .entry_state == "ENTRY_READY" and .entry_allowed == true and
        .claim_status == "claimed" and .order_exit == 0 and
        .orders_submitted == 0 and .fills_exit == 0 and
        .measurement_exit == 0 and .reconciliation_exit == 0 and
        .result == "completed" and
        ((.attempt_kind // "initial") == "initial") and
        ((.first_run_id // $first_run_id) == $first_run_id) and
        ((.retry_run_id // null) == null)
    ' "${summary}" >/dev/null || return 1
    jq -e '
        .status == "CLEAR" and .reconciliation_state == "OK" and
        .evidence_quality == "VALID" and
        .halt_present_before == false and .halt_present_after == false and
        .orders_submitted == 0
    ' "${reconciliation}" >/dev/null || return 1

    manifest_tmp="$(mktemp)" || return 1
    if ! git_as_app ls-tree "${deployed_sha}" -- "${RETRY_MANIFEST_PATH}" \
            | grep -Eq '^100644 blob [0-9a-f]{40}[[:space:]]+deploy/live-canary-retry-incident\.json$' \
        || ! git_as_app show "${deployed_sha}:${RETRY_MANIFEST_PATH}" >"${manifest_tmp}"; then
        rm -f "${manifest_tmp}"
        return 1
    fi
    if ! jq -e \
        --arg session "${session_key}" \
        --arg first_run_id "${first_run_id}" \
        --arg first_source "${first_source}" \
        --arg first_code "${first_code_commit}" '
        ((keys | sort) == ([
          "broker_rejection_signatures", "enabled", "first_code_commit",
          "first_run_id", "first_source", "incident_id", "market_session",
          "remediation_commit", "schema_version"
        ] | sort)) and
        .schema_version == "1.0" and .enabled == true and
        (.incident_id | type == "string" and test("^[a-z0-9][a-z0-9-]{0,79}$")) and
        .market_session == $session and .first_run_id == $first_run_id and
        .first_source == $first_source and .first_source == "server_timer" and
        .first_code_commit == $first_code and
        (.remediation_commit | test("^[0-9a-f]{40}$")) and
        (.broker_rejection_signatures | type == "array" and length > 0 and length <= 20) and
        ([.broker_rejection_signatures[] |
          ((keys | sort) == ([
            "exception_type", "http_status", "kis_msg_cd", "kis_rt_cd",
            "order_division", "order_exchange", "symbol", "tr_id"
          ] | sort)) and
          (.symbol | test("^[A-Z][A-Z0-9.-]{0,9}$")) and
          (.kis_rt_cd | type == "string" and test("^[0-9]{1,4}$")) and
          (.kis_msg_cd | type == "string" and test("^[A-Z0-9]{1,16}$")) and
          (.http_status | type == "number" and floor == . and . >= 100 and . <= 599) and
          (.exception_type | type == "string" and test("^[A-Za-z][A-Za-z0-9_]{0,63}$")) and
          (.tr_id | IN("TTTT1002U", "TTTT1006U")) and
          (.order_exchange | IN("NASD", "NYSE", "AMEX")) and
          (.order_division | IN("00", "01"))
        ] | all)
    ' "${manifest_tmp}" >/dev/null; then
        rm -f "${manifest_tmp}"
        return 1
    fi

    local remediation_commit
    remediation_commit="$(jq -r '.remediation_commit' "${manifest_tmp}")"
    if [[ "${deployed_sha}" == "${first_code_commit}" \
        || "${remediation_commit}" == "${first_code_commit}" ]] \
        || ! git_as_app merge-base --is-ancestor "${first_code_commit}" "${deployed_sha}" \
            >/dev/null 2>&1 \
        || ! git_as_app merge-base --is-ancestor "${remediation_commit}" "${deployed_sha}" \
            >/dev/null 2>&1; then
        rm -f "${manifest_tmp}"
        return 1
    fi

    if ! jq -R -s -e --slurpfile manifest "${manifest_tmp}" '
        (split("\n") | map(select(startswith("{")) | try fromjson catch empty) | last) as $order |
        ($manifest[0].broker_rejection_signatures | sort_by(.symbol)) as $expected |
        ($order.fundability.planned_orders // []) as $planned |
        ($order.results // []) as $results |
        ($planned | length) > 0 and ($planned | length) <= 20 and
        ($results | length) == ($planned | length) and
        ([ $planned[] |
          (.symbol | type == "string" and test("^[A-Z][A-Z0-9.-]{0,9}$")) and
          (.side == "BUY" or .side == "SELL") and
          (.qty | type == "number" and floor == . and . > 0)
        ] | all) and
        ([ $results[] |
          .state == "REJECTED_BY_BROKER" and
          (.requested_qty | type == "number" and floor == . and . > 0) and
          (.reason | type == "string")
        ] | all) and
        ([$planned[] | {symbol, side, requested_qty:.qty}] | sort_by(.symbol, .side)) ==
          ([$results[] | {symbol, side, requested_qty}] | sort_by(.symbol, .side)) and
        ([$results[] |
          (.reason | fromjson) as $reason |
          {symbol,
           kis_rt_cd:$reason.kis_rt_cd,
           kis_msg_cd:$reason.kis_msg_cd,
           http_status:$reason.http_status,
           exception_type:$reason.exception_type,
           tr_id:$reason.request_summary.tr_id,
           order_exchange:$reason.request_summary.body.OVRS_EXCG_CD,
           order_division:$reason.request_summary.body.ORD_DVSN}
        ] | sort_by(.symbol)) == $expected
    ' "${order_log}" >/dev/null; then
        rm -f "${manifest_tmp}"
        return 1
    fi

    if ! fresh_kis_open_order_proof "${deployed_sha}"; then
        rm -f "${manifest_tmp}"
        return 1
    fi
    manifest_sha="$(sha256_file "${manifest_tmp}")" || {
        rm -f "${manifest_tmp}"
        return 1
    }
    rm -f "${manifest_tmp}"
    [[ "${manifest_sha}" =~ ^[0-9a-f]{64}$ ]] || return 1

    touch "${RETRY_SESSION_FILE}" || return 1
    chmod 0600 "${RETRY_SESSION_FILE}" || return 1
    file_owned_by_root "${RETRY_SESSION_FILE}" || return 1
    exec 6>>"${RETRY_SESSION_FILE}" || return 1
    flock -x 6 || return 1
    existing="$(awk -F '\t' -v key="${session_key}" '$1 == key { print; exit }' \
        "${RETRY_SESSION_FILE}")"
    if [[ -n "${existing}" ]]; then
        RETRY_EXISTING_RUN_ID="$(printf '%s\n' "${existing}" | awk -F '\t' '{ print $5 }')"
        flock -u 6
        exec 6>&-
        return 1
    fi
    claimed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "${session_key}" "${first_run_id}" "${first_source}" "${first_code_commit}" \
        "${retry_run_id}" "${deployed_sha}" "${manifest_sha}" "${claimed_at}" >&6
    flock -u 6
    exec 6>&-
    echo "LIVE_ORDER_SESSION_RETRY_CLAIMED market_session=${session_key} first_run_id=${first_run_id} first_source=${first_source} retry_run_id=${retry_run_id} source=server_timer claimed_at=${claimed_at}"
    return 0
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
    local session_key session_exit claimed_at existing first_run_id first_source first_code_commit
    local deployed_sha retry_run_id_field retry_status
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
        first_code_commit="$(printf '%s\n' "${existing}" | awk -F '\t' '{ print $3 }')"
        first_source="$(printf '%s\n' "${existing}" | awk -F '\t' '{ print $5 }')"
        [[ -n "${first_source}" ]] || first_source="legacy"
        deployed_sha="${DEPLOYED_CODE_COMMIT:-${signed_sha}}"
        if [[ "${source}" == "server_timer" && "${first_source}" == "server_timer" ]] \
            && claim_same_session_retry \
                "${session_key}" "${first_run_id}" "${first_source}" \
                "${first_code_commit}" "${run_id}" "${deployed_sha}"; then
            flock -u 8
            return 0
        fi
        retry_run_id_field=""
        set +e
        existing_retry_run_id "${session_key}"
        retry_status=$?
        set -e
        if [[ "${retry_status}" -eq 0 ]]; then
            retry_run_id_field=" retry_run_id=${RETRY_EXISTING_RUN_ID}"
        fi
        echo "LIVE_ORDER_SESSION_ALREADY_CLAIMED market_session=${session_key} first_run_id=${first_run_id} first_source=${first_source}${retry_run_id_field}"
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
         .operational_equivalent == true and
         (if has("attempt_kind") then
            (.attempt_kind == "initial" or .attempt_kind == "same_session_retry") and
            (.first_run_id | test("^[0-9]{14}$")) and
            (.retry_run_id == null or (.retry_run_id | test("^[0-9]{14}$"))) and
            (if .attempt_kind == "initial" then
               .claim_status == "claimed" and .first_run_id == .run_id and .retry_run_id == null
             else
               .claim_status == "retry_claimed" and .retry_run_id == .run_id and
               .first_run_id != .run_id
             end)
          else true end)' \
        "${summary}" >/dev/null || die "invalid scheduled run summary"
    cat "${summary}"
}

scheduled_order_diagnostics() {
    local run_id="${1:-}" run_dir order_log payload diagnostics
    [[ -d "${SCHEDULED_RUNS_DIR}" && ! -L "${SCHEDULED_RUNS_DIR}" ]] \
        || die "missing scheduled evidence directory"
    if [[ -z "${run_id}" ]]; then
        [[ -f "${SCHEDULED_LAST_RUN_FILE}" && ! -L "${SCHEDULED_LAST_RUN_FILE}" ]] \
            || die "no server-scheduled live canary evidence"
        run_id="$(tr -d '\r\n' < "${SCHEDULED_LAST_RUN_FILE}")"
    fi
    [[ "${run_id}" =~ ^[0-9]{14}$ ]] || die "invalid scheduled run pointer"
    run_dir="${SCHEDULED_RUNS_DIR}/${run_id}"
    order_log="${run_dir}/order.log"
    [[ -d "${run_dir}" && ! -L "${run_dir}" ]] \
        || die "missing scheduled run evidence"
    [[ -f "${order_log}" && ! -L "${order_log}" ]] \
        || die "missing scheduled order evidence"

    payload="$(jq -R -s -c '
        split("\n")
        | map(select(startswith("{")) | try fromjson catch empty)
        | last // empty
    ' "${order_log}")" || die "failed to parse scheduled order evidence"
    [[ -n "${payload}" ]] || die "missing scheduled order result"

    printf '%s\n' "${payload}" | jq -e '
        (.results | type == "array" and length <= 20) and
        (.withheld_orders | type == "array" and length <= 20) and
        (.fundability | type == "object") and
        (.fundability.planned_orders | type == "array" and length <= 20) and
        ([.results[] |
          (.symbol | type == "string" and test("^[A-Z][A-Z0-9.-]{0,9}$")) and
          (.side == "BUY" or .side == "SELL") and
          (.requested_qty | type == "number" and floor == . and . >= 0 and . <= 1000000) and
          (.routed_qty | type == "number" and floor == . and . >= 0 and . <= 1000000) and
          (.state | IN(
            "SUBMITTED", "PARTIALLY_FILLED", "FILLED", "SUBMISSION_UNKNOWN",
            "REJECTED_BY_GATE", "REJECTED_BY_BROKER", "SKIPPED_PER_TRADE_CAP",
            "SKIPPED_BY_SIZING", "SKIPPED_BY_RANKING", "SKIPPED_BY_QUALITY",
            "SKIPPED_BY_COMPOSITE", "SKIPPED_BY_JUDGMENT", "ERROR"
          )) and
          (.gate == null or
            (.gate | type == "string" and test("^[a-z][a-z0-9_]{0,63}$"))) and
          ((keys | sort) == ([
            "gate", "limit_price_usd", "reason", "requested_qty", "routed_qty",
            "side", "state", "symbol"
          ] | sort))
        ] | all) and
        ([.withheld_orders[] |
          (.symbol | type == "string" and test("^[A-Z][A-Z0-9.-]{0,9}$")) and
          (.side == "BUY" or .side == "SELL") and
          (.requested_qty | type == "number" and floor == . and . >= 0 and . <= 1000000) and
          (.reason | type == "string") and
          ((keys | sort) == (["reason", "requested_qty", "side", "symbol"] | sort))
        ] | all)
    ' >/dev/null || die "invalid scheduled order result"

    diagnostics="$(printf '%s\n' "${payload}" | jq \
        --arg schema_version "1.2" \
        --arg source "server_timer_order_diagnostics" \
        --arg run_id "${run_id}" '
        def withheld_code:
          if . == "unmanaged_holding" then "unmanaged_holding"
          elif . == "insufficient_purchasable_cash" then "insufficient_cash"
          elif . == "cash_shortfall_sell_first" then "cash_shortfall_sell_first"
          elif . == "side_filtered_sell_only" then "side_filtered_sell_only"
          elif . == "side_filtered_buy_only" then "side_filtered_buy_only"
          else "other_withheld"
          end;
        def message_topics:
          if type != "string" or length == 0 then ["unavailable"]
          else
            [
              if test("\uacc4\uc88c|account"; "i") then "account" else empty end,
              if test("신청|미신청|등록|약정|서비스|service"; "i")
                then "service_registration" else empty end,
              if test("권한|허용|제한|거래불가|매매불가|주문불가|permission|not allowed|restricted"; "i")
                then "trading_permission" else empty end,
              if test("거래소|exchange"; "i") then "exchange" else empty end,
              if test("종목|symbol|ticker"; "i") then "symbol" else empty end,
              if test("거래시간|주문시간|장중|개장|폐장|market.*time|session"; "i")
                then "market_session" else empty end,
              if test("가격|호가|단가|틱|상한|하한|price"; "i") then "price" else empty end,
              if test("수량|quantity|qty"; "i") then "quantity" else empty end,
              if test("주문[ ]*가능[ ]*금액|예수금|증거금|부족|buying[ _-]*power|purchasable"; "i")
                then "buying_power" else empty end,
              if test("환전|외화|통화|currency"; "i") then "currency" else empty end,
              if test("주문구분|지정가|시장가|order[ _-]*type"; "i")
                then "order_type" else empty end
            ]
            | unique
            | if length == 0 then ["other"] else . end
          end;
        {schema_version:$schema_version,source:$source,run_id:$run_id,
         planned_order_count:(.fundability.planned_orders | length),
         result_count:(.results | length),
         withheld_order_count:(.withheld_orders | length),
         outcomes:[.results[] | {
           symbol,side,requested_qty,routed_qty,state,gate
         }],
         broker_rejections:[.results[]
           | select(.state == "REJECTED_BY_BROKER")
           | (.reason | try fromjson catch null) as $diagnostics
           | {
               symbol,
               kis_rt_cd:($diagnostics.kis_rt_cd // null),
               kis_msg_cd:($diagnostics.kis_msg_cd // null),
               http_status:($diagnostics.http_status // null),
               exception_type:($diagnostics.exception_type // null),
               tr_id:($diagnostics.request_summary.tr_id // null),
               order_exchange:($diagnostics.request_summary.body.OVRS_EXCG_CD // null),
               order_division:($diagnostics.request_summary.body.ORD_DVSN // null),
               message_topics:(($diagnostics.kis_msg1 // null) | message_topics)
             }],
         withheld_reason_codes:([.withheld_orders[].reason | withheld_code] | unique)}'
    )" || die "failed to sanitize scheduled order diagnostics"

    printf '%s\n' "${diagnostics}" | jq -e '
        .schema_version == "1.2" and
        .source == "server_timer_order_diagnostics" and
        (.broker_rejections | type == "array" and length <= 20) and
        ([.broker_rejections[] |
          (.symbol | type == "string" and test("^[A-Z][A-Z0-9.-]{0,9}$")) and
          (.kis_rt_cd == null or
            (.kis_rt_cd | type == "string" and test("^[0-9]{1,4}$"))) and
          (.kis_msg_cd == null or
            (.kis_msg_cd | type == "string" and test("^[A-Z0-9]{1,16}$"))) and
          (.http_status == null or
            (.http_status | type == "number" and floor == . and . >= 100 and . <= 599)) and
          (.exception_type == null or
            (.exception_type | type == "string" and test("^[A-Za-z][A-Za-z0-9_]{0,63}$"))) and
          (.tr_id == null or (.tr_id | IN("TTTT1002U", "TTTT1006U"))) and
          (.order_exchange == null or
            (.order_exchange | IN("NASD", "NYSE", "AMEX"))) and
          (.order_division == null or (.order_division | IN("00", "01"))) and
          (.message_topics | type == "array" and length >= 1 and length <= 12 and
            length == (unique | length) and
            all(.[]; IN(
              "account", "service_registration", "trading_permission", "exchange",
              "symbol", "market_session", "price", "quantity", "buying_power",
              "currency", "order_type", "other", "unavailable"
            ))) and
          ((keys | sort) == ([
            "exception_type", "http_status", "kis_msg_cd", "kis_rt_cd",
            "message_topics", "order_division", "order_exchange", "symbol", "tr_id"
          ] | sort))
        ] | all) and
        ([.outcomes[] | select(.state == "REJECTED_BY_BROKER")] | length) ==
          (.broker_rejections | length)
    ' >/dev/null || die "invalid sanitized broker rejection diagnostics"
    printf '%s\n' "${diagnostics}"
}

systemd_property() {
    local unit="$1" property="$2" value
    value="$(systemctl show "${unit}" --property="${property}" --value 2>/dev/null)" \
        || die "failed to read live-canary systemd state"
    [[ "${#value}" -le 160 && "${value}" != *$'\n'* && "${value}" != *$'\r'* ]] \
        || die "invalid live-canary systemd state"
    printf '%s\n' "${value}"
}

runtime_status() {
    local timer_load timer_active timer_last timer_next
    local service_load service_active service_result service_exit service_started service_finished
    local journal_events journal_exit journal_readable events_json

    timer_load="$(systemd_property auto-invest-live-canary.timer LoadState)"
    timer_active="$(systemd_property auto-invest-live-canary.timer ActiveState)"
    timer_last="$(systemd_property auto-invest-live-canary.timer LastTriggerUSec)"
    timer_next="$(systemd_property auto-invest-live-canary.timer NextElapseUSecRealtime)"
    service_load="$(systemd_property auto-invest-live-canary.service LoadState)"
    service_active="$(systemd_property auto-invest-live-canary.service ActiveState)"
    service_result="$(systemd_property auto-invest-live-canary.service Result)"
    service_exit="$(systemd_property auto-invest-live-canary.service ExecMainStatus)"
    service_started="$(systemd_property auto-invest-live-canary.service ExecMainStartTimestamp)"
    service_finished="$(systemd_property auto-invest-live-canary.service ExecMainExitTimestamp)"

    [[ "${timer_load}" =~ ^[a-z-]+$ && "${timer_active}" =~ ^[a-z-]+$ \
        && "${service_load}" =~ ^[a-z-]+$ && "${service_active}" =~ ^[a-z-]+$ \
        && "${service_result}" =~ ^[a-z-]+$ && "${service_exit}" =~ ^[0-9]+$ ]] \
        || die "invalid live-canary systemd status fields"

    set +e
    journal_events="$(journalctl -u auto-invest-live-canary.service --since '24 hours ago' \
        -n 400 --no-pager -o cat 2>/dev/null \
        | awk '
            /^LIVE_CANARY_SERVER_TIMER_DUPLICATE / {
                print "duplicate_scheduler"; next
            }
            /^LIVE_ORDER_SESSION_ALREADY_CLAIMED / {
                print "order_session_already_claimed"; next
            }
            /^ERROR: .*broker writes are halted for an owner emergency deploy$/ {
                print "deploy_maintenance_halt"; next
            }
            /^ERROR: .*systemd invocation/ ||
            /^ERROR: .*fixed systemd unit/ ||
            /^ERROR: .*direct child of its fixed systemd unit$/ {
                print "invalid_systemd_invocation"; next
            }
            /^ERROR: .*deployed commit/ ||
            /^ERROR: .*origin.main/ ||
            /^ERROR: .*operational revision/ ||
            /^ERROR: server code differs from/ ||
            /^ERROR: server timer requires current main authority$/ {
                print "operational_revision_mismatch"; next
            }
            /^ERROR: production worker is not active$/ {
                print "worker_inactive"; next
            }
            /^ERROR: .*deploy audit/ {
                print "deploy_audit_invalid"; next
            }
            /^ERROR: .*XNYS/ || /^ERROR: invalid XNYS session key$/ {
                print "market_session_invalid"; next
            }
            /^ERROR: .*sentinel/ || /^ERROR: AUTOARM_DISABLED kill switch is active$/ ||
            /^ERROR: server fallback is limited to ladder rung 1$/ ||
            /^ERROR: server fallback requires operational_canary entry route$/ {
                print "live_authority_invalid"; next
            }
            /^ERROR: .*live order session ledger$/ {
                print "order_session_ledger_invalid"; next
            }
            /^ERROR: duplicate scheduler run id$/ {
                print "duplicate_scheduler_run_id"; next
            }
            /^ERROR: server timer first-entry revalidation failed$/ {
                print "first_entry_revalidation_failed"; next
            }
            /^ERROR: .*scheduled evidence/ || /^ERROR: missing claimed market session$/ ||
            /^ERROR: failed to build scheduled summary$/ {
                print "scheduled_evidence_invalid"; next
            }
            /^ERROR:/ { print "unclassified_error" }
        ' \
        | tail -n 20)"
    journal_exit=$?
    set -e
    journal_readable=false
    if [[ "${journal_exit}" -eq 0 ]]; then
        journal_readable=true
    else
        journal_events=""
    fi
    events_json="$(printf '%s' "${journal_events}" \
        | jq -R -s 'if length == 0 then [] else split("\n") end')" \
        || die "failed to sanitize live-canary journal"

    jq -n \
        --arg schema_version "1.0" \
        --arg source "server_timer_runtime" \
        --arg observed_at_utc "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --arg timer_load_state "${timer_load}" \
        --arg timer_active_state "${timer_active}" \
        --arg timer_last_trigger_utc "${timer_last}" \
        --arg timer_next_elapse_utc "${timer_next}" \
        --arg service_load_state "${service_load}" \
        --arg service_active_state "${service_active}" \
        --arg service_result "${service_result}" \
        --argjson service_exec_main_status "${service_exit}" \
        --arg service_started_at_utc "${service_started}" \
        --arg service_finished_at_utc "${service_finished}" \
        --argjson journal_readable "${journal_readable}" \
        --argjson recent_events "${events_json}" \
        '{schema_version:$schema_version,source:$source,observed_at_utc:$observed_at_utc,
          timer:{load_state:$timer_load_state,active_state:$timer_active_state,
            last_trigger_utc:$timer_last_trigger_utc,next_elapse_utc:$timer_next_elapse_utc},
          service:{load_state:$service_load_state,active_state:$service_active_state,
            result:$service_result,exec_main_status:$service_exec_main_status,
            started_at_utc:$service_started_at_utc,finished_at_utc:$service_finished_at_utc},
          journal_readable:$journal_readable,recent_events:$recent_events}'
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
        scheduled-order-diagnostics)
            [[ "$#" -le 1 ]] \
                || die "scheduled-order-diagnostics takes at most one run id"
            scheduled_order_diagnostics "${1:-}"
            ;;
        runtime-status)
            [[ "$#" -eq 0 ]] || die "runtime-status takes no arguments"
            runtime_status
            ;;
        *)
            die "unknown live-canary command: ${command:-missing}"
            ;;
    esac
}

main "$@"

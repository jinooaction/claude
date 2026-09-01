#!/usr/bin/env bash
# Independent production live-canary wake-up path. GitHub schedule remains the
# primary source; this root-owned systemd path starts later and uses the same
# market-session claim so only one source can reach broker writes each session.

set -euo pipefail

PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
REPO="${REPO:-/opt/auto-invest}"
APP_USER="${APP_USER:-auto-invest}"
UV_BIN="${UV_BIN:-/usr/local/bin/uv}"
LIVE_HELPER="${LIVE_HELPER:-/usr/local/sbin/auto-invest-live-canary}"
OBSERVE_HELPER="${OBSERVE_HELPER:-/usr/local/sbin/auto-invest-observe}"
RECONCILIATION_HELPER="${RECONCILIATION_HELPER:-/usr/local/sbin/auto-invest-reconciliation-recovery}"
STATE_DIR="${STATE_DIR:-/var/lib/auto-invest-live-order}"
SCHEDULED_RUNS_DIR="${SCHEDULED_RUNS_DIR:-${STATE_DIR}/scheduled-runs}"
LAST_RUN_FILE="${LAST_RUN_FILE:-${STATE_DIR}/last-scheduled-run-id}"
SESSION_FILE="${SESSION_FILE:-${STATE_DIR}/order-sessions.tsv}"

die() {
    echo "ERROR: $*" >&2
    exit 2
}

require_root_systemd() {
    [[ "$(id -u)" -eq 0 ]] || die "live-canary fallback requires root"
    [[ "${INVOCATION_ID:-}" =~ ^[0-9a-f]{32}$ ]] \
        || die "live-canary fallback requires a systemd invocation id"
    grep -Eq '/auto-invest-live-canary\.service$' /proc/self/cgroup \
        || die "live-canary fallback must run in its fixed systemd unit"
}

git_as_app() {
    sudo -u "${APP_USER}" -H git -C "${REPO}" "$@"
}

run_as_app() {
    sudo -u "${APP_USER}" -H "${UV_BIN}" run "$@"
}

sentinel_field() {
    local key="$1"
    awk -v key="${key}" '$1 == key ":" { print $2; exit }' \
        "${REPO}/automation/rebalance-live.request"
}

validate_exact_main() {
    local deployed_sha main_sha
    [[ -d "${REPO}/.git" ]] || die "missing production repository"
    git_as_app fetch origin main --quiet || die "failed to refresh origin/main"
    deployed_sha="$(git_as_app rev-parse HEAD)" || die "missing deployed commit"
    main_sha="$(git_as_app rev-parse origin/main)" || die "missing origin/main"
    [[ "${deployed_sha}" =~ ^[0-9a-f]{40}$ && "${deployed_sha}" == "${main_sha}" ]] \
        || die "live-canary fallback requires exact deployed main"
    printf '%s\n' "${deployed_sha}"
}

validate_deploy_audit() {
    local sha="$1" completed
    systemctl is-active --quiet auto-invest.service \
        || die "production worker is not active"
    [[ -r "${REPO}/data/auto_invest.db" ]] || die "missing production audit database"
    completed="$(sqlite3 -readonly "${REPO}/data/auto_invest.db" \
        "SELECT COUNT(*) FROM audit_log
          WHERE event_type = 'DEPLOY_COMPLETED'
            AND json_extract(payload_json, '$.sha_after') = '${sha}'
            AND json_extract(payload_json, '$.phase') IN ('live', 'noop');")" \
        || die "failed to read deploy audit"
    [[ "${completed}" =~ ^[0-9]+$ && "${completed}" -ge 1 ]] \
        || die "exact main lacks a completed production deploy audit"
}

validate_market_session() {
    local session_key
    session_key="$(run_as_app python -m auto_invest.execution.live_session)" \
        || return $?
    [[ "${session_key}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] \
        || die "invalid XNYS session key"
    printf '%s\n' "${session_key}"
}

validate_sentinel() {
    local armed capital rung route
    [[ -f "${REPO}/automation/rebalance-live.request" ]] || die "missing live sentinel"
    [[ ! -e "${REPO}/automation/AUTOARM_DISABLED" ]] || die "AUTOARM_DISABLED kill switch is active"
    armed="$(sentinel_field armed)"
    capital="$(sentinel_field capital_usd)"
    rung="$(sentinel_field ladder_rung)"
    route="$(sentinel_field entry_route)"
    [[ "${armed}" == "true" ]] || die "live sentinel is not armed"
    [[ "${capital}" =~ ^[0-9]+([.][0-9]+)?$ ]] || die "invalid sentinel capital"
    [[ "${rung}" == "1" ]] || die "server fallback is limited to ladder rung 1"
    [[ "${route}" == "operational_canary" ]] \
        || die "server fallback requires operational_canary entry route"
    printf '%s\n' "${capital}"
}

existing_session_claim() {
    local session_key="$1" existing first_run_id first_source
    [[ -e "${SESSION_FILE}" ]] || return 1
    [[ -f "${SESSION_FILE}" && ! -L "${SESSION_FILE}" ]] \
        || die "unsafe live order session ledger"
    exec 9<"${SESSION_FILE}" || die "cannot open live order session ledger"
    flock -s 9 || die "cannot lock live order session ledger"
    existing="$(awk -F '\t' -v key="${session_key}" '$1 == key { print; exit }' \
        "${SESSION_FILE}")"
    flock -u 9
    exec 9<&-
    [[ -n "${existing}" ]] || return 1
    first_run_id="$(printf '%s\n' "${existing}" | awk -F '\t' '{ print $2 }')"
    first_source="$(printf '%s\n' "${existing}" | awk -F '\t' '{ print $5 }')"
    [[ -n "${first_source}" ]] || first_source="legacy"
    [[ "${first_run_id}" =~ ^[0-9]+$ ]] || die "invalid existing session run id"
    case "${first_source}" in
        github_schedule|server_timer|legacy) ;;
        *) die "invalid existing session source" ;;
    esac
    echo "LIVE_CANARY_SERVER_TIMER_DUPLICATE market_session=${session_key} first_run_id=${first_run_id} first_source=${first_source}"
    return 0
}

run_entry_revalidation() {
    local sha="$1" capital="$2" work_dir="$3"
    local profit_branch="automation/profit-evidence-engine-last-run"
    local factory_branch="automation/autonomous-strategy-factory-last-run"
    local now_epoch evidence_epoch factory_epoch evidence_age_hours factory_age_hours
    local backfill_exit canary_exit profit_exit parity_exit preview_exit probe_exit

    cd "${REPO}" || return 2
    git_as_app fetch --depth=1 origin \
        "+refs/heads/${profit_branch}:refs/remotes/origin/${profit_branch}" \
        "+refs/heads/${factory_branch}:refs/remotes/origin/${factory_branch}" \
        >"${work_dir}/evidence-fetch.log" 2>&1 || return 3
    git_as_app show "origin/${profit_branch}:profit_evidence.json" \
        >"${work_dir}/profit_evidence.json" || return 3
    git_as_app show "origin/${profit_branch}:operational_canary_evidence.json" \
        >"${work_dir}/operational_canary_evidence.json" || return 3
    git_as_app show "origin/${factory_branch}:capital_entry_evidence.json" \
        >"${work_dir}/capital_entry_evidence.json" || return 3
    chmod 0644 "${work_dir}"/*.json

    now_epoch="$(date +%s)"
    evidence_epoch="$(git_as_app show -s --format=%ct "origin/${profit_branch}")" || return 3
    factory_epoch="$(git_as_app show -s --format=%ct "origin/${factory_branch}")" || return 3
    evidence_age_hours="$(awk -v now="${now_epoch}" -v then="${evidence_epoch}" \
        'BEGIN { print (now - then) / 3600 }')"
    factory_age_hours="$(awk -v now="${now_epoch}" -v then="${factory_epoch}" \
        'BEGIN { print (now - then) / 3600 }')"

    set +e
    "${OBSERVE_HELPER}" live-canary-backfill \
        >"${work_dir}/backfill.log" 2>"${work_dir}/backfill.err"
    backfill_exit=$?
    "${OBSERVE_HELPER}" exploration-canary \
        >"${work_dir}/hardened_canary.json" 2>"${work_dir}/hardened_canary.err"
    canary_exit=$?
    "${LIVE_HELPER}" profit "${capital}" \
        >"${work_dir}/live_performance.json" 2>"${work_dir}/live_performance.err"
    profit_exit=$?
    "${OBSERVE_HELPER}" execution-proxy-parity \
        >"${work_dir}/execution_proxy_parity.json" 2>"${work_dir}/execution_proxy_parity.err"
    parity_exit=$?
    "${OBSERVE_HELPER}" live-canary-preview "${capital}" \
        >"${work_dir}/fundability_preview.json" 2>"${work_dir}/fundability_preview.err"
    preview_exit=$?
    set -e
    [[ "${backfill_exit}" -eq 0 && "${canary_exit}" -eq 0 && "${profit_exit}" -eq 0 \
        && "${parity_exit}" -eq 0 && "${preview_exit}" -eq 0 ]] || return 3
    chmod 0644 "${work_dir}"/*.json

    set +e
    run_as_app python scripts/live_entry_revalidation_probe.py \
        --profit-evidence-json "${work_dir}/profit_evidence.json" \
        --operational-evidence-json "${work_dir}/operational_canary_evidence.json" \
        --factory-evidence-json "${work_dir}/capital_entry_evidence.json" \
        --hardened-canary-json "${work_dir}/hardened_canary.json" \
        --live-performance-json "${work_dir}/live_performance.json" \
        --evidence-age-hours "${evidence_age_hours}" \
        --factory-evidence-age-hours "${factory_age_hours}" \
        --operational-evidence-age-hours "${evidence_age_hours}" \
        --expected-code-commit "${sha}" \
        --sentinel automation/rebalance-live.request \
        --live-portfolio deploy/canary-live-portfolio.toml \
        --validated-portfolio deploy/global-trend-fixed-portfolio.toml \
        --fundability-preview-json "${work_dir}/fundability_preview.json" \
        --execution-proxy-parity-json "${work_dir}/execution_proxy_parity.json" \
        --capital-usd "${capital}" \
        >"${work_dir}/entry_revalidation.json" 2>"${work_dir}/entry_revalidation.err"
    probe_exit=$?
    set -e
    [[ "${probe_exit}" -eq 0 ]] || return "${probe_exit}"
    jq -e '.allowed == true and .state == "ENTRY_READY"' \
        "${work_dir}/entry_revalidation.json" >/dev/null || return 3
    return 0
}

first_nonzero() {
    local status
    for status in "$@"; do
        if [[ "${status}" -ne 0 ]]; then
            printf '%s\n' "${status}"
            return
        fi
    done
    printf '0\n'
}

main() {
    local run_id started_at finished_at sha capital expected_session work_dir run_dir
    local order_exit fills_exit measure_exit profit_exit reconciliation_exit final_exit
    local market_session orders_submitted result summary_tmp pointer_tmp
    local prior_claim prior_claim_exit

    require_root_systemd
    sha="$(validate_exact_main)"
    validate_deploy_audit "${sha}"
    expected_session="$(validate_market_session)"
    capital="$(validate_sentinel)"
    set +e
    prior_claim="$(existing_session_claim "${expected_session}")"
    prior_claim_exit=$?
    set -e
    if [[ "${prior_claim_exit}" -eq 0 ]]; then
        echo "${prior_claim}"
        exit 0
    fi
    [[ "${prior_claim_exit}" -eq 1 ]] || die "failed to inspect live order session ledger"
    run_id="$(date -u +%Y%m%d%H%M%S)"
    started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    work_dir="/run/auto-invest-live-canary/${run_id}"
    install -d -m 0750 -o root -g "${APP_USER}" /run/auto-invest-live-canary
    [[ ! -e "${work_dir}" ]] || die "duplicate scheduler run id"
    install -d -m 0750 -o root -g "${APP_USER}" "${work_dir}"
    trap 'rm -rf "${work_dir}"' EXIT

    run_entry_revalidation "${sha}" "${capital}" "${work_dir}" \
        || die "server timer first-entry revalidation failed"

    set +e
    "${LIVE_HELPER}" systemd-order "${run_id}" "${sha}" "${capital}" \
        >"${work_dir}/order.log" 2>"${work_dir}/order.err"
    order_exit=$?
    set -e
    cat "${work_dir}/order.log"
    cat "${work_dir}/order.err" >&2
    if grep -q '^LIVE_ORDER_SESSION_ALREADY_CLAIMED ' "${work_dir}/order.log"; then
        echo "LIVE_CANARY_SERVER_TIMER_DUPLICATE run_id=${run_id}"
        exit 0
    fi
    grep -q '^LIVE_ORDER_SESSION_CLAIMED ' "${work_dir}/order.log" \
        || exit "${order_exit}"

    install -d -m 0700 -o root -g root "${STATE_DIR}" "${SCHEDULED_RUNS_DIR}"
    [[ ! -L "${STATE_DIR}" && ! -L "${SCHEDULED_RUNS_DIR}" ]] \
        || die "unsafe scheduled evidence directory"
    run_dir="${SCHEDULED_RUNS_DIR}/${run_id}"
    mkdir -m 0700 "${run_dir}" || die "scheduled evidence already exists"
    install -m 0600 -o root -g root "${work_dir}/entry_revalidation.json" \
        "${run_dir}/entry_revalidation.json"
    install -m 0600 -o root -g root "${work_dir}/order.log" "${run_dir}/order.log"
    install -m 0600 -o root -g root "${work_dir}/order.err" "${run_dir}/order.err"

    set +e
    fills_exit=0
    : >"${run_dir}/fills.log"
    for attempt in 1 2 3; do
        echo "--- fill sync attempt ${attempt}/3 ---" >>"${run_dir}/fills.log"
        "${LIVE_HELPER}" fills >>"${run_dir}/fills.log" 2>&1
        fills_exit=$?
        if [[ "${fills_exit}" -ne 0 || "${attempt}" -eq 3 ]]; then
            break
        fi
        sleep 20
    done
    "${OBSERVE_HELPER}" live-canary-measure "${capital}" \
        >"${run_dir}/measurement.log" 2>&1
    measure_exit=$?
    "${LIVE_HELPER}" profit "${capital}" \
        >"${run_dir}/profit.json" 2>"${run_dir}/profit.err"
    profit_exit=$?
    "${RECONCILIATION_HELPER}" \
        >"${run_dir}/reconciliation.json" 2>"${run_dir}/reconciliation.err"
    reconciliation_exit=$?
    set -e

    market_session="$(sed -n 's/^LIVE_ORDER_SESSION_CLAIMED market_session=\([^ ]*\).*/\1/p' \
        "${work_dir}/order.log" | head -1)"
    [[ "${market_session}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] \
        || die "missing claimed market session"
    [[ "${market_session}" == "${expected_session}" ]] \
        || die "XNYS session changed before the shared claim"
    orders_submitted="$(grep -Ec '"state"[[:space:]]*:[[:space:]]*"(SUBMITTED|PARTIALLY_FILLED|FILLED|SUBMISSION_UNKNOWN)"' \
        "${work_dir}/order.log" || true)"
    final_exit="$(first_nonzero "${order_exit}" "${fills_exit}" "${measure_exit}" \
        "${profit_exit}" "${reconciliation_exit}")"
    result="completed"
    [[ "${final_exit}" -eq 0 ]] || result="partial"
    finished_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    summary_tmp="${run_dir}/.summary.json.new"
    jq -n \
        --arg schema_version "1.0" \
        --arg run_id "${run_id}" \
        --arg source "server_timer" \
        --arg market_session "${market_session}" \
        --arg started_at_utc "${started_at}" \
        --arg finished_at_utc "${finished_at}" \
        --arg code_commit "${sha}" \
        --arg capital_usd "${capital}" \
        --arg entry_state "ENTRY_READY" \
        --arg claim_status "claimed" \
        --arg result "${result}" \
        --argjson entry_allowed true \
        --argjson order_exit "${order_exit}" \
        --argjson orders_submitted "${orders_submitted}" \
        --argjson fills_exit "${fills_exit}" \
        --argjson measurement_exit "$(first_nonzero "${measure_exit}" "${profit_exit}")" \
        --argjson reconciliation_exit "${reconciliation_exit}" \
        '{schema_version:$schema_version,run_id:$run_id,source:$source,
          market_session:$market_session,started_at_utc:$started_at_utc,
          finished_at_utc:$finished_at_utc,code_commit:$code_commit,
          capital_usd:$capital_usd,entry_state:$entry_state,
          entry_allowed:$entry_allowed,claim_status:$claim_status,
          order_exit:$order_exit,orders_submitted:$orders_submitted,
          fills_exit:$fills_exit,measurement_exit:$measurement_exit,
          reconciliation_exit:$reconciliation_exit,result:$result}' \
        >"${summary_tmp}" || die "failed to build scheduled summary"
    chmod 0600 "${summary_tmp}"
    mv "${summary_tmp}" "${run_dir}/summary.json"
    pointer_tmp="$(mktemp "${STATE_DIR}/.last-scheduled-run-id.XXXXXX")"
    printf '%s\n' "${run_id}" >"${pointer_tmp}"
    chmod 0600 "${pointer_tmp}"
    mv "${pointer_tmp}" "${LAST_RUN_FILE}"
    cat "${run_dir}/summary.json"
    exit "${final_exit}"
}

main "$@"

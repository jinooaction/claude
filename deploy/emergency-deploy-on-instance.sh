#!/usr/bin/env bash
# Root-owned, one-shot bridge for constitution VIII.A owner emergency deploys.
# It never submits/cancels orders and never changes live capital or strategy.

set -euo pipefail

readonly PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
readonly REPO=/opt/auto-invest
readonly APP_USER=auto-invest
readonly APP_GROUP=auto-invest
readonly KIS_SMOKE_HELPER=/usr/local/sbin/auto-invest-kis-smoke
readonly REQUEST_DIR=/run/auto-invest-deploy
readonly REQUEST_PATH=/run/auto-invest-deploy/emergency-request.json
readonly STATE_DIR=/var/lib/auto-invest-live-order
readonly INTERLOCK_PATH=/run/auto-invest-deploy/live-order-maintenance.lock
readonly BROKER_WRITE_LOCK_PATH=/run/auto-invest-deploy/broker-write.lock
readonly DB_PATH=/opt/auto-invest/data/auto_invest.db
readonly BOOTSTRAP_PARENT=/tmp/auto-invest-emergency-deploy
readonly MAX_TTL_SEC=900

die() {
    echo "ERROR: $*" >&2
    exit 2
}

require_root() {
    [[ "$(id -u)" -eq 0 ]] || die "run as root"
}

validate_args() {
    [[ "$#" -eq 6 ]] || die "expected target_sha workflow_run_id actor issued_at expires_at reason_sha256"
    [[ "$1" =~ ^[0-9a-f]{40}$ ]] || die "invalid target SHA"
    [[ "$2" =~ ^[1-9][0-9]*$ ]] || die "invalid workflow run id"
    [[ "$3" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,37}[A-Za-z0-9])?$ ]] \
        || die "invalid actor"
    [[ "$4" =~ ^[1-9][0-9]*$ ]] || die "invalid issued-at time"
    [[ "$5" =~ ^[1-9][0-9]*$ ]] || die "invalid expiry"
    [[ "$6" =~ ^[0-9a-f]{64}$ ]] || die "invalid reason digest"
}

terminal_event_for_request() {
    local request_id="$1" cid
    [[ -r "${DB_PATH}" ]] || return 1
    cid="$(sqlite3 -readonly "${DB_PATH}" \
        "SELECT correlation_id FROM audit_log
          WHERE event_type = 'DEPLOY_EMERGENCY_AUTHORIZED'
            AND json_extract(payload_json, '$.request_id') = '${request_id}'
          ORDER BY seq DESC LIMIT 1;")" || return 1
    [[ "${cid}" =~ ^[0-9a-f]{32}$ ]] || return 1
    sqlite3 -readonly "${DB_PATH}" \
        "SELECT event_type FROM audit_log
          WHERE correlation_id = '${cid}' AND event_type LIKE 'DEPLOY_%'
          ORDER BY seq DESC LIMIT 1;"
}

append_preauthorization() {
    local request_id="$1" target_sha="$2" workflow_run_id="$3" actor="$4"
    local issued_at="$5" expires_at="$6" reason_sha256="$7"
    local correlation_id audit_ts auth_payload existing

    [[ -f "${DB_PATH}" && ! -L "${DB_PATH}" ]] || die "missing or unsafe audit database"
    existing="$(sqlite3 -readonly "${DB_PATH}" \
        "SELECT count(*) FROM audit_log
          WHERE event_type = 'DEPLOY_EMERGENCY_AUTHORIZED'
            AND json_extract(payload_json, '$.request_id') = '${request_id}';")" \
        || die "failed to inspect emergency authorization ledger"
    [[ "${existing}" == "0" ]] || die "emergency request id was already authorized"

    correlation_id="$(printf '%s' \
        "${request_id}:${target_sha}:${issued_at}:${expires_at}" | sha256sum | cut -c1-32)"
    [[ "${correlation_id}" =~ ^[0-9a-f]{32}$ ]] || die "failed to derive correlation id"
    audit_ts="$(date -u +'%Y-%m-%dT%H:%M:%S.000Z')"
    auth_payload="$(jq -cn \
        --arg event_type "DEPLOY_EMERGENCY_AUTHORIZED" \
        --arg request_id "${request_id}" \
        --arg target_sha "${target_sha}" \
        --arg actor "${actor}" \
        --arg workflow_run_id "${workflow_run_id}" \
        --arg source "github-actions-workflow-dispatch" \
        --arg reason_sha256 "${reason_sha256}" \
        --argjson issued_at_epoch "${issued_at}" \
        --argjson expires_at_epoch "${expires_at}" \
        '{event_type:$event_type,request_id:$request_id,target_sha:$target_sha,
          actor:$actor,workflow_run_id:$workflow_run_id,source:$source,
          reason_sha256:$reason_sha256,issued_at_epoch:$issued_at_epoch,
          expires_at_epoch:$expires_at_epoch}')" \
        || die "failed to build emergency authorization audit"

    sqlite3 "${DB_PATH}" \
        "PRAGMA busy_timeout=30000;
         BEGIN IMMEDIATE;
         INSERT INTO audit_log
           (ts_utc,event_type,rule_id,symbol,payload_json,correlation_id)
         VALUES
           ('${audit_ts}','DEPLOY_EMERGENCY_AUTHORIZED',NULL,NULL,
            '${auth_payload}','${correlation_id}');
         COMMIT;" >/dev/null \
        || die "failed to append emergency authorization audit"
    printf '%s\n' "${correlation_id}"
}

validate_halted_interlock_for_recovery() {
    local prior_request_id prior_workflow_run_id prior_target_sha
    local expected_gid file_meta authorization_count correlation_id
    local started_count deploy_row_count

    [[ -f "${INTERLOCK_PATH}" && ! -L "${INTERLOCK_PATH}" ]] \
        || die "existing maintenance interlock is not a safe regular file"
    expected_gid="$(getent group "${APP_GROUP}" | cut -d: -f3)"
    [[ "${expected_gid}" =~ ^[0-9]+$ ]] || die "failed to resolve application group"
    file_meta="$(stat -c '%u:%g:%a' "${INTERLOCK_PATH}")" \
        || die "failed to inspect existing maintenance interlock"
    [[ "${file_meta}" == "0:${expected_gid}:640" ]] \
        || die "existing maintenance interlock ownership or mode is invalid"
    jq -e '
        type == "object" and
        keys == ["created_at_epoch","reason","request_id","state","target_sha","workflow_run_id"] and
        (.request_id | type == "string" and test("^github-run-[1-9][0-9]*$")) and
        (.target_sha | type == "string" and test("^[0-9a-f]{40}$")) and
        (.workflow_run_id | type == "string" and test("^[1-9][0-9]*$")) and
        (.created_at_epoch | type == "number" and . > 0 and floor == .) and
        .state == "HALTED" and
        .reason == "deploy terminal safety not proven"
    ' "${INTERLOCK_PATH}" >/dev/null \
        || die "existing maintenance interlock is not a recoverable HALTED record"

    prior_request_id="$(jq -r '.request_id' "${INTERLOCK_PATH}")"
    prior_workflow_run_id="$(jq -r '.workflow_run_id' "${INTERLOCK_PATH}")"
    prior_target_sha="$(jq -r '.target_sha' "${INTERLOCK_PATH}")"
    [[ "${prior_request_id}" == "github-run-${prior_workflow_run_id}" ]] \
        || die "existing maintenance interlock request identity is inconsistent"

    authorization_count="$(sqlite3 -readonly "${DB_PATH}" \
        "SELECT COUNT(*) FROM audit_log
          WHERE event_type = 'DEPLOY_EMERGENCY_AUTHORIZED'
            AND json_extract(payload_json, '$.request_id') = '${prior_request_id}'
            AND json_extract(payload_json, '$.target_sha') = '${prior_target_sha}'
            AND json_extract(payload_json, '$.workflow_run_id') = '${prior_workflow_run_id}'
            AND json_extract(payload_json, '$.actor') IN ('jinooaction','masonoh-kidsnote');")" \
        || die "failed to inspect prior emergency authorization"
    [[ "${authorization_count}" == "1" ]] \
        || die "prior emergency authorization is missing or ambiguous"
    correlation_id="$(sqlite3 -readonly "${DB_PATH}" \
        "SELECT correlation_id FROM audit_log
          WHERE event_type = 'DEPLOY_EMERGENCY_AUTHORIZED'
            AND json_extract(payload_json, '$.request_id') = '${prior_request_id}';")" \
        || die "failed to read prior emergency correlation"
    [[ "${correlation_id}" =~ ^[0-9a-f]{32}$ ]] \
        || die "prior emergency correlation is invalid or ambiguous"
    started_count="$(sqlite3 -readonly "${DB_PATH}" \
        "SELECT COUNT(*) FROM audit_log
          WHERE correlation_id = '${correlation_id}'
            AND event_type = 'DEPLOY_STARTED';")" \
        || die "failed to inspect prior deploy start"
    deploy_row_count="$(sqlite3 -readonly "${DB_PATH}" \
        "SELECT COUNT(*) FROM audit_log
          WHERE correlation_id = '${correlation_id}'
            AND event_type LIKE 'DEPLOY_%';")" \
        || die "failed to inspect prior deploy chain"
    [[ "${started_count}" == "0" && "${deploy_row_count}" == "1" ]] \
        || die "prior emergency reached or ambiguously crossed DEPLOY_STARTED"
    echo "RECOVERING_PRESTART_HALTED request_id=${prior_request_id} target=${prior_target_sha}"
}

validate_terminal_rollback_orphan() {
    local prior_request_id prior_workflow_run_id prior_target_sha prior_actor
    local expected_gid interlock_meta request_meta authorization_count correlation_id
    local started_count failed_count kernel_count rolled_back_count completed_count
    local unexpected_count terminal_event production_head rollback_sha_before

    [[ -f "${INTERLOCK_PATH}" && ! -L "${INTERLOCK_PATH}" ]] \
        || die "existing maintenance interlock is not a safe regular file"
    [[ -f "${REQUEST_PATH}" && ! -L "${REQUEST_PATH}" ]] \
        || die "existing emergency request is not a safe regular file"
    expected_gid="$(getent group "${APP_GROUP}" | cut -d: -f3)"
    [[ "${expected_gid}" =~ ^[0-9]+$ ]] || die "failed to resolve application group"
    interlock_meta="$(stat -c '%u:%g:%a' "${INTERLOCK_PATH}")" \
        || die "failed to inspect existing maintenance interlock"
    request_meta="$(stat -c '%u:%g:%a' "${REQUEST_PATH}")" \
        || die "failed to inspect existing emergency request"
    [[ "${interlock_meta}" == "0:${expected_gid}:640" \
        && "${request_meta}" == "0:${expected_gid}:640" ]] \
        || die "orphan recovery file ownership or mode is invalid"
    jq -e '
        type == "object" and
        keys == ["created_at_epoch","request_id","state","target_sha","workflow_run_id"] and
        (.request_id | type == "string" and test("^github-run-[1-9][0-9]*$")) and
        (.target_sha | type == "string" and test("^[0-9a-f]{40}$")) and
        (.workflow_run_id | type == "string" and test("^[1-9][0-9]*$")) and
        (.created_at_epoch | type == "number" and . > 0 and floor == .) and
        .state == "QUIESCED"
    ' "${INTERLOCK_PATH}" >/dev/null \
        || die "existing maintenance interlock is not a recoverable QUIESCED record"
    jq -e '
        type == "object" and
        keys == ["actor","expires_at_epoch","issued_at_epoch","reason_sha256","request_id","schema_version","source","target_sha","workflow_run_id"] and
        .schema_version == "1.0" and
        (.request_id | type == "string" and test("^github-run-[1-9][0-9]*$")) and
        (.target_sha | type == "string" and test("^[0-9a-f]{40}$")) and
        (.workflow_run_id | type == "string" and test("^[1-9][0-9]*$")) and
        (.actor == "jinooaction" or .actor == "masonoh-kidsnote") and
        .source == "github-actions-workflow-dispatch" and
        (.reason_sha256 | type == "string" and test("^[0-9a-f]{64}$")) and
        (.issued_at_epoch | type == "number" and . > 0 and floor == .) and
        (.expires_at_epoch | type == "number" and . > .issued_at_epoch and floor == .)
    ' "${REQUEST_PATH}" >/dev/null \
        || die "existing emergency request is not a recoverable closed record"

    prior_request_id="$(jq -r '.request_id' "${REQUEST_PATH}")"
    prior_workflow_run_id="$(jq -r '.workflow_run_id' "${REQUEST_PATH}")"
    prior_target_sha="$(jq -r '.target_sha' "${REQUEST_PATH}")"
    prior_actor="$(jq -r '.actor' "${REQUEST_PATH}")"
    [[ "$(jq -r '.request_id' "${INTERLOCK_PATH}")" == "${prior_request_id}" \
        && "$(jq -r '.workflow_run_id' "${INTERLOCK_PATH}")" == "${prior_workflow_run_id}" \
        && "$(jq -r '.target_sha' "${INTERLOCK_PATH}")" == "${prior_target_sha}" \
        && "${prior_request_id}" == "github-run-${prior_workflow_run_id}" ]] \
        || die "orphan recovery identities are inconsistent"

    authorization_count="$(sqlite3 -readonly "${DB_PATH}" \
        "SELECT COUNT(*) FROM audit_log
          WHERE event_type = 'DEPLOY_EMERGENCY_AUTHORIZED'
            AND json_extract(payload_json, '$.request_id') = '${prior_request_id}'
            AND json_extract(payload_json, '$.target_sha') = '${prior_target_sha}'
            AND json_extract(payload_json, '$.workflow_run_id') = '${prior_workflow_run_id}'
            AND json_extract(payload_json, '$.actor') = '${prior_actor}';")" \
        || die "failed to inspect orphan authorization"
    [[ "${authorization_count}" == "1" ]] \
        || die "orphan authorization is missing or ambiguous"
    correlation_id="$(sqlite3 -readonly "${DB_PATH}" \
        "SELECT correlation_id FROM audit_log
          WHERE event_type = 'DEPLOY_EMERGENCY_AUTHORIZED'
            AND json_extract(payload_json, '$.request_id') = '${prior_request_id}';")" \
        || die "failed to read orphan correlation"
    [[ "${correlation_id}" =~ ^[0-9a-f]{32}$ ]] \
        || die "orphan correlation is invalid or ambiguous"
    read -r started_count failed_count kernel_count rolled_back_count \
        completed_count unexpected_count <<<"$(sqlite3 -readonly -separator ' ' "${DB_PATH}" \
        "SELECT
            SUM(event_type = 'DEPLOY_STARTED'),
            SUM(event_type = 'DEPLOY_FAILED'),
            SUM(event_type = 'DEPLOY_KERNEL_TOUCHED'),
            SUM(event_type = 'DEPLOY_ROLLED_BACK'),
            SUM(event_type = 'DEPLOY_COMPLETED'),
            SUM(event_type NOT IN (
                'DEPLOY_EMERGENCY_AUTHORIZED','DEPLOY_STARTED',
                'DEPLOY_KERNEL_TOUCHED','DEPLOY_FAILED','DEPLOY_ROLLED_BACK'
            ))
          FROM audit_log WHERE correlation_id = '${correlation_id}';")" \
        || die "failed to inspect orphan deploy chain"
    [[ "${started_count}" == "1" && "${failed_count}" == "1" \
        && ( "${kernel_count}" == "0" || "${kernel_count}" == "1" ) \
        && "${rolled_back_count}" == "1" && "${completed_count}" == "0" \
        && "${unexpected_count}" == "0" ]] \
        || die "orphan deploy chain is incomplete or ambiguous"
    terminal_event="$(sqlite3 -readonly "${DB_PATH}" \
        "SELECT event_type FROM audit_log WHERE correlation_id = '${correlation_id}'
          AND event_type LIKE 'DEPLOY_%' ORDER BY seq DESC LIMIT 1;")" \
        || die "failed to read orphan terminal event"
    [[ "${terminal_event}" == "DEPLOY_ROLLED_BACK" ]] \
        || die "orphan deploy did not end in a verified rollback"
    rollback_sha_before="$(sqlite3 -readonly "${DB_PATH}" \
        "SELECT json_extract(payload_json, '$.sha_before') FROM audit_log
          WHERE correlation_id = '${correlation_id}'
            AND event_type = 'DEPLOY_ROLLED_BACK';")" \
        || die "failed to read rollback baseline"
    production_head="$(sudo -u "${APP_USER}" git -C "${REPO}" rev-parse HEAD)"
    [[ "${rollback_sha_before}" =~ ^[0-9a-f]{40}$ \
        && "${production_head}" == "${rollback_sha_before}" ]] \
        || die "production repo does not match the verified rollback baseline"
    echo "RECOVERING_TERMINAL_ROLLBACK request_id=${prior_request_id} target=${prior_target_sha}"
}

prepare_exact_target_runner() {
    local target_sha="$1" remote_url remote_head checkout_head

    remote_url="$(sudo -u "${APP_USER}" git -C "${REPO}" config --get remote.origin.url)" \
        || die "failed to resolve production remote"
    [[ -n "${remote_url}" ]] || die "production remote is empty"
    install -d -m 1777 -o root -g root "${BOOTSTRAP_PARENT}"
    bootstrap_repo="$(sudo -u "${APP_USER}" mktemp -d "${BOOTSTRAP_PARENT}/repo.XXXXXX")" \
        || die "failed to create emergency bootstrap checkout"
    [[ "${bootstrap_repo}" == "${BOOTSTRAP_PARENT}/repo."* ]] \
        || die "unsafe emergency bootstrap path"
    sudo -u "${APP_USER}" git clone --quiet --no-checkout \
        "${remote_url}" "${bootstrap_repo}" \
        || die "failed to clone exact emergency target"
    sudo -u "${APP_USER}" git -C "${bootstrap_repo}" fetch origin main --quiet \
        || die "failed to fetch exact emergency target"
    remote_head="$(sudo -u "${APP_USER}" git -C "${bootstrap_repo}" rev-parse origin/main)"
    [[ "${remote_head}" == "${target_sha}" ]] \
        || die "bootstrap origin/main changed from the authorized target"
    sudo -u "${APP_USER}" git -C "${bootstrap_repo}" checkout --quiet --detach \
        "${target_sha}" || die "failed to checkout exact emergency target"
    checkout_head="$(sudo -u "${APP_USER}" git -C "${bootstrap_repo}" rev-parse HEAD)"
    [[ "${checkout_head}" == "${target_sha}" ]] \
        || die "emergency bootstrap checkout is not the authorized target"
}

main() {
    require_root
    validate_args "$@"
    local target_sha="$1" workflow_run_id="$2" actor="$3"
    local issued_at="$4" expires_at="$5" reason_sha256="$6"
    local now main_sha request_id tmp="" smoke_tmp="" start_exit terminal_event
    local authorization_correlation_id="" safe_terminal=0 interlock_created=0
    local request_installed=0 bootstrap_repo="" auto_invest_home=""
    local timer_was_active=0

    now="$(date +%s)"
    (( issued_at <= now )) || die "emergency request issued in the future"
    (( expires_at >= now )) || die "emergency request expired"
    (( expires_at > issued_at )) || die "invalid emergency request lifetime"
    (( expires_at - issued_at <= MAX_TTL_SEC )) || die "emergency request exceeds maximum TTL"
    (( expires_at - now <= MAX_TTL_SEC )) || die "emergency request expiry is too far away"

    [[ -d "${REPO}/.git" ]] || die "missing repo"
    sudo -u "${APP_USER}" git -C "${REPO}" fetch origin main --quiet \
        || die "failed to refresh origin/main"
    main_sha="$(sudo -u "${APP_USER}" git -C "${REPO}" rev-parse origin/main)"
    [[ "${main_sha}" == "${target_sha}" ]] || die "target SHA is not exact current main"

    install -d -m 0700 -o root -g root "${STATE_DIR}"
    install -d -m 0750 -o root -g "${APP_GROUP}" "${REQUEST_DIR}"
    [[ ! -L "${STATE_DIR}" && ! -L "${REQUEST_DIR}" ]] || die "unsafe state directory"
    request_id="github-run-${workflow_run_id}"
    cleanup() {
        if [[ "${request_installed}" -eq 1 ]]; then
            rm -f "${REQUEST_PATH}"
        fi
        [[ -z "${tmp}" ]] || rm -f "${tmp}"
        [[ -z "${smoke_tmp}" ]] || rm -f "${smoke_tmp}"
        if [[ -n "${bootstrap_repo}" \
            && "${bootstrap_repo}" == "${BOOTSTRAP_PARENT}/repo."* ]]; then
            rm -rf -- "${bootstrap_repo}"
        fi
        if [[ "${interlock_created}" -eq 0 ]]; then
            return
        elif [[ "${safe_terminal}" -eq 1 ]]; then
            rm -f "${INTERLOCK_PATH}"
        else
            printf '{"request_id":"%s","target_sha":"%s","workflow_run_id":"%s","created_at_epoch":%s,"state":"HALTED","reason":"deploy terminal safety not proven"}\n' \
                "${request_id}" "${target_sha}" "${workflow_run_id}" "${now}" >"${INTERLOCK_PATH}"
            chmod 0640 "${INTERLOCK_PATH}"
            chown root:"${APP_GROUP}" "${INTERLOCK_PATH}"
            echo "DEPLOY_EMERGENCY_HALTED request_id=${request_id} target=${target_sha}" >&2
        fi
    }
    trap cleanup EXIT

    [[ -f "${DB_PATH}" && ! -L "${DB_PATH}" ]] \
        || die "missing or unsafe audit database"
    [[ -f "${BROKER_WRITE_LOCK_PATH}" && ! -L "${BROKER_WRITE_LOCK_PATH}" ]] \
        || die "missing or unsafe broker-write coordination lock"
    local recovered_terminal_rollback=0
    if [[ -e "${INTERLOCK_PATH}" ]]; then
        exec 9<>"${INTERLOCK_PATH}"
        flock -n -x 9 || die "existing maintenance interlock is still owned"
        if [[ -e "${REQUEST_PATH}" ]]; then
            validate_terminal_rollback_orphan
            recovered_terminal_rollback=1
        else
            validate_halted_interlock_for_recovery
        fi
    else
        [[ ! -e "${REQUEST_PATH}" ]] || die "orphan request exists without an interlock"
        install -m 0640 -o root -g "${APP_GROUP}" /dev/null "${INTERLOCK_PATH}"
        exec 9<>"${INTERLOCK_PATH}"
        flock -n -x 9 || die "another emergency deploy owns the maintenance interlock"
    fi
    interlock_created=1
    exec 8<>"${BROKER_WRITE_LOCK_PATH}"
    flock -w 30 -x 8 || die "live broker write did not quiesce within 30 seconds"
    if [[ "${recovered_terminal_rollback}" -eq 1 ]]; then
        rm -f "${REQUEST_PATH}"
    fi
    [[ ! -e "${REQUEST_PATH}" ]] || die "emergency request path is already occupied"

    printf '{"request_id":"%s","target_sha":"%s","workflow_run_id":"%s","created_at_epoch":%s,"state":"QUIESCED"}\n' \
        "${request_id}" "${target_sha}" "${workflow_run_id}" "${now}" >"${INTERLOCK_PATH}"

    tmp="$(mktemp "${REQUEST_DIR}/.emergency-request.XXXXXX")"
    smoke_tmp="$(mktemp "${REQUEST_DIR}/.kis-smoke.XXXXXX")"

    jq -n \
        --arg schema_version "1.0" \
        --arg request_id "${request_id}" \
        --arg target_sha "${target_sha}" \
        --arg actor "${actor}" \
        --arg workflow_run_id "${workflow_run_id}" \
        --arg source "github-actions-workflow-dispatch" \
        --arg reason_sha256 "${reason_sha256}" \
        --argjson issued_at_epoch "${issued_at}" \
        --argjson expires_at_epoch "${expires_at}" \
        '{schema_version:$schema_version,request_id:$request_id,target_sha:$target_sha,
          actor:$actor,workflow_run_id:$workflow_run_id,source:$source,
          reason_sha256:$reason_sha256,issued_at_epoch:$issued_at_epoch,
          expires_at_epoch:$expires_at_epoch}' >"${tmp}" \
        || die "failed to build emergency request"

    authorization_correlation_id="$(append_preauthorization \
        "${request_id}" "${target_sha}" "${workflow_run_id}" "${actor}" \
        "${issued_at}" "${expires_at}" "${reason_sha256}")"
    [[ "${authorization_correlation_id}" =~ ^[0-9a-f]{32}$ ]] \
        || die "emergency authorization audit was not proven"
    install -m 0640 -o root -g "${APP_GROUP}" "${tmp}" "${REQUEST_PATH}"
    request_installed=1
    rm -f "${tmp}"
    tmp=""

    if systemctl is-active --quiet auto-invest-live-canary.timer; then
        timer_was_active=1
    fi
    systemctl stop auto-invest-live-canary.timer \
        || die "failed to stop live canary timer"
    systemctl stop auto-invest-live-canary.service \
        || die "failed to quiesce live canary service"
    systemctl stop auto-invest.service \
        || die "failed to stop the previous live worker"
    if pgrep -u "${APP_USER}" -f 'auto-invest rebalance-once.*--mode live' >/dev/null \
        || pgrep -u "${APP_USER}" -f 'auto-invest run' >/dev/null; then
        die "a previous live process is still running"
    fi

    if ! "${KIS_SMOKE_HELPER}" "${target_sha}" >"${smoke_tmp}" 2>&1; then
        cat "${smoke_tmp}"
        die "KIS read-only smoke failed after broker writes were quiesced"
    fi
    cat "${smoke_tmp}"
    grep -Eq 'open_unfilled[=:][[:space:]]*0([^0-9]|$)' "${smoke_tmp}" \
        || die "KIS smoke did not prove open_unfilled=0"

    prepare_exact_target_runner "${target_sha}"
    auto_invest_home="$(getent passwd "${APP_USER}" | cut -d: -f6)"
    [[ -n "${auto_invest_home}" ]] || die "failed to resolve application home"
    set +e
    sudo -u "${APP_USER}" env \
        "PATH=${PATH}" \
        "HOME=${auto_invest_home}" \
        "UV_CACHE_DIR=${auto_invest_home}/.cache/uv" \
        /usr/local/bin/uv run --project "${bootstrap_repo}" auto-invest deploy \
        --branch main \
        --repo "${REPO}" \
        --db "${DB_PATH}" \
        --config "${REPO}/config/rules.toml" \
        --env-path "${REPO}/.env" \
        --supervisor systemd \
        --health-window-s 90
    start_exit=$?
    set -e
    terminal_event="$(terminal_event_for_request "${request_id}" || true)"
    case "${terminal_event}" in
        DEPLOY_COMPLETED|DEPLOY_ROLLED_BACK) safe_terminal=1 ;;
        *) safe_terminal=0 ;;
    esac
    if [[ "${safe_terminal}" -eq 1 && "${timer_was_active}" -eq 1 ]]; then
        if ! systemctl start auto-invest-live-canary.timer; then
            safe_terminal=0
            die "deploy recovered but the automatic live scheduler did not restart"
        fi
    fi
    if [[ "${start_exit}" -eq 0 && "${terminal_event}" == "DEPLOY_COMPLETED" ]]; then
        echo "DEPLOY_EMERGENCY_COMPLETED request_id=${request_id} target=${target_sha}"
        cleanup
        trap - EXIT
        return 0
    fi
    if [[ "${terminal_event}" == "DEPLOY_ROLLED_BACK" ]]; then
        echo "DEPLOY_EMERGENCY_ROLLED_BACK request_id=${request_id} target=${target_sha}" >&2
        cleanup
        trap - EXIT
        return 1
    fi
    die "emergency deploy failed without a proven healthy terminal state"
}

main "$@"

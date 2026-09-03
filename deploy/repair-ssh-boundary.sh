#!/usr/bin/env bash
# auto-invest server SSH boundary repair.
#
# Run this on the production host as root, after creating a fresh deploy key
# outside the host:
#
#   DEPLOY_PUBLIC_KEY="$(cat ~/.ssh/auto_invest_gh.pub)" \
#     sudo -E bash /opt/auto-invest/deploy/repair-ssh-boundary.sh
#
# If the host is still on an older deploy SHA and does not have this file yet,
# download it to a temporary file first, inspect it, then run that file. Avoid
# piping remote code directly into a root shell.
#
# The script is idempotent. It does not start the worker, change .env, arm live
# trading, or touch capital settings.

set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-gh-deploy}"
DEPLOY_HOME="${DEPLOY_HOME:-/var/lib/${DEPLOY_USER}}"
DEPLOY_PUBLIC_KEY="${DEPLOY_PUBLIC_KEY:-}"
REFRESH_HELPERS_ONLY="${REFRESH_HELPERS_ONLY:-0}"
REPO="${REPO:-/opt/auto-invest}"
REPO_REF="${REPO_REF:-origin/main}"
REPO_OWNER="${REPO_OWNER:-auto-invest}"
ROOT_AUTHORIZED_KEYS="${ROOT_AUTHORIZED_KEYS:-/root/.ssh/authorized_keys}"
LEGACY_ROOT_KEY_COMMENT="${LEGACY_ROOT_KEY_COMMENT:-github-actions@auto-invest}"
LEGACY_ROOT_KEY_PATH="${LEGACY_ROOT_KEY_PATH:-/root/.ssh/auto_invest_gh}"
GATEWAY_PATH="${GATEWAY_PATH:-/usr/local/sbin/auto-invest-deploy-gateway}"
SYNC_HELPER_PATH="${SYNC_HELPER_PATH:-/usr/local/sbin/auto-invest-sync-units}"
KIS_SMOKE_HELPER_PATH="${KIS_SMOKE_HELPER_PATH:-/usr/local/sbin/auto-invest-kis-smoke}"
OBSERVE_HELPER_PATH="${OBSERVE_HELPER_PATH:-/usr/local/sbin/auto-invest-observe}"
LIVE_CANARY_HELPER_PATH="${LIVE_CANARY_HELPER_PATH:-/usr/local/sbin/auto-invest-live-canary}"
RECONCILIATION_RECOVERY_HELPER_PATH="${RECONCILIATION_RECOVERY_HELPER_PATH:-/usr/local/sbin/auto-invest-reconciliation-recovery}"
DEPLOY_AUDIT_HELPER_PATH="${DEPLOY_AUDIT_HELPER_PATH:-/usr/local/sbin/auto-invest-deploy-audit}"
EMERGENCY_DEPLOY_HELPER_PATH="${EMERGENCY_DEPLOY_HELPER_PATH:-/usr/local/sbin/auto-invest-emergency-deploy}"
LIVE_ORDER_PUBLIC_KEY_PATH="${LIVE_ORDER_PUBLIC_KEY_PATH:-/usr/local/share/auto-invest/live-order-signing-public.pem}"
SUDOERS_PATH="${SUDOERS_PATH:-/etc/sudoers.d/auto-invest-gh-deploy}"
REPO_SYNC_UNITS="${REPO_SYNC_UNITS:-/opt/auto-invest/deploy/sync-units.sh}"
REPO_KIS_SMOKE_HELPER="${REPO_KIS_SMOKE_HELPER:-/opt/auto-invest/deploy/kis-smoke-on-instance.sh}"
REPO_OBSERVE_HELPER="${REPO_OBSERVE_HELPER:-/opt/auto-invest/deploy/observe-on-instance.sh}"
REPO_LIVE_CANARY_HELPER="${REPO_LIVE_CANARY_HELPER:-/opt/auto-invest/deploy/live-canary-on-instance.sh}"
REPO_RECONCILIATION_RECOVERY_HELPER="${REPO_RECONCILIATION_RECOVERY_HELPER:-/opt/auto-invest/deploy/reconciliation-recovery-on-instance.sh}"
REPO_DEPLOY_AUDIT_HELPER="${REPO_DEPLOY_AUDIT_HELPER:-/opt/auto-invest/deploy/deploy-audit-on-instance.sh}"
REPO_EMERGENCY_DEPLOY_HELPER="${REPO_EMERGENCY_DEPLOY_HELPER:-/opt/auto-invest/deploy/emergency-deploy-on-instance.sh}"
REPO_LIVE_ORDER_PUBLIC_KEY="${REPO_LIVE_ORDER_PUBLIC_KEY:-/opt/auto-invest/deploy/live-order-signing-public.pem}"
RUNTIME_BOUNDARY_DIR="${RUNTIME_BOUNDARY_DIR:-/run/auto-invest-deploy}"
BROKER_WRITE_LOCK_PATH="${BROKER_WRITE_LOCK_PATH:-${RUNTIME_BOUNDARY_DIR}/broker-write.lock}"
APP_GROUP="${APP_GROUP:-auto-invest}"

die() {
    echo "ERROR: $*" >&2
    exit 2
}

require_root() {
    if [[ "$(id -u)" -ne 0 ]]; then
        die "run as root"
    fi
}

validate_inputs() {
    [[ "${DEPLOY_USER}" =~ ^[a-z_][a-z0-9_-]*$ ]] || die "unsafe DEPLOY_USER"
    [[ -n "${DEPLOY_PUBLIC_KEY}" ]] || die "DEPLOY_PUBLIC_KEY is required"
    if grep -q "PRIVATE KEY" <<<"${DEPLOY_PUBLIC_KEY}"; then
        die "DEPLOY_PUBLIC_KEY contains private-key material"
    fi
    if ! grep -Eq '^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp(256|384|521)) [A-Za-z0-9+/=]+([[:space:]].*)?$' \
            <<<"${DEPLOY_PUBLIC_KEY}"; then
        die "DEPLOY_PUBLIC_KEY is not an OpenSSH public key"
    fi
}

install_repo_file() {
    local repo_path="$1"
    local fallback_path="$2"
    local destination="$3"
    local tmp_file
    tmp_file="$(mktemp)"

    if [[ -d "${REPO}/.git" ]] \
        && id "${REPO_OWNER}" >/dev/null 2>&1 \
        && sudo -u "${REPO_OWNER}" git -C "${REPO}" show "${REPO_REF}:${repo_path}" \
            > "${tmp_file}" 2>/dev/null; then
        install -m 0755 -o root -g root "${tmp_file}" "${destination}"
        rm -f "${tmp_file}"
        return
    fi

    rm -f "${tmp_file}"
    if [[ ! -f "${fallback_path}" ]]; then
        die "missing ${fallback_path}; deploy current main before running repair"
    fi
    install -m 0755 -o root -g root "${fallback_path}" "${destination}"
}

install_gateway() {
    cat > "${GATEWAY_PATH}.new" <<'EOF_GATEWAY'
#!/usr/bin/env bash
set -euo pipefail

cmd="${SSH_ORIGINAL_COMMAND:-status}"

case "${cmd}" in
    status)
        echo "AUTO_INVEST_GATEWAY_OK"
        echo "user=$(id -un)"
        echo "host=$(hostname)"
        echo "deploy_timer=$(systemctl is-active auto-invest-deploy.timer 2>/dev/null || true)"
        echo "live_canary_timer=$(systemctl is-active auto-invest-live-canary.timer 2>/dev/null || true)"
        echo "worker=$(systemctl is-active auto-invest.service 2>/dev/null || true)"
        ;;
    sync-units)
        exec sudo -n /usr/local/sbin/auto-invest-sync-units
        ;;
    kis-smoke)
        exec sudo -n /usr/local/sbin/auto-invest-kis-smoke
        ;;
    kis-smoke\ *)
        smoke_sha="${cmd#kis-smoke }"
        if [[ "${smoke_sha}" =~ ^[0-9a-f]{40}$ ]]; then
            exec sudo -n /usr/local/sbin/auto-invest-kis-smoke "${smoke_sha}"
        fi
        echo "refused command: ${cmd}" >&2
        exit 126
        ;;
    observe\ halt-status)
        exec sudo -n /usr/local/sbin/auto-invest-observe halt-status
        ;;
    observe\ signal-ic\ trend)
        exec sudo -n /usr/local/sbin/auto-invest-observe signal-ic trend
        ;;
    observe\ paper-track-run\ *)
        rest="${cmd#observe paper-track-run }"
        track="${rest%% *}"
        capital="${rest#* }"
        if [[ "${rest}" == "${track} ${capital}" \
            && "${track}" =~ ^(trend|notrend|rmbeta|multiasset|global|globalfixed|wide)$ \
            && "${capital}" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
            exec sudo -n /usr/local/sbin/auto-invest-observe paper-track-run "${track}" "${capital}"
        fi
        echo "refused command: ${cmd}" >&2
        exit 126
        ;;
    observe\ paper-track-verdict\ *)
        track="${cmd#observe paper-track-verdict }"
        if [[ "${track}" =~ ^(trend|notrend|rmbeta|multiasset|global|globalfixed|wide)$ ]]; then
            exec sudo -n /usr/local/sbin/auto-invest-observe paper-track-verdict "${track}"
        fi
        echo "refused command: ${cmd}" >&2
        exit 126
        ;;
    observe\ ladder-forward-verdict)
        exec sudo -n /usr/local/sbin/auto-invest-observe ladder-forward-verdict
        ;;
    observe\ ladder-anchored-verdict)
        exec sudo -n /usr/local/sbin/auto-invest-observe ladder-anchored-verdict
        ;;
    observe\ exploration-canary)
        exec sudo -n /usr/local/sbin/auto-invest-observe exploration-canary
        ;;
    observe\ account-nav)
        exec sudo -n /usr/local/sbin/auto-invest-observe account-nav
        ;;
    observe\ live-growth)
        exec sudo -n /usr/local/sbin/auto-invest-observe live-growth
        ;;
    observe\ live-growth\ *)
        since="${cmd#observe live-growth }"
        if [[ "${since}" =~ ^[0-9T:Z+_.-]+$ ]]; then
            exec sudo -n /usr/local/sbin/auto-invest-observe live-growth "${since}"
        fi
        echo "refused command: ${cmd}" >&2
        exit 126
        ;;
    observe\ live-canary-backfill)
        exec sudo -n /usr/local/sbin/auto-invest-observe live-canary-backfill
        ;;
    observe\ execution-proxy-parity)
        exec sudo -n /usr/local/sbin/auto-invest-observe execution-proxy-parity
        ;;
    observe\ live-canary-preview\ *)
        capital="${cmd#observe live-canary-preview }"
        if [[ "${capital}" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
            exec sudo -n /usr/local/sbin/auto-invest-observe live-canary-preview "${capital}"
        fi
        echo "refused command: ${cmd}" >&2
        exit 126
        ;;
    observe\ live-canary-measure\ *)
        capital="${cmd#observe live-canary-measure }"
        if [[ "${capital}" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
            exec sudo -n /usr/local/sbin/auto-invest-observe live-canary-measure "${capital}"
        fi
        echo "refused command: ${cmd}" >&2
        exit 126
        ;;
    observe\ promote-readiness)
        exec sudo -n /usr/local/sbin/auto-invest-observe promote-readiness
        ;;
    observe\ regime-stratify\ *)
        track="${cmd#observe regime-stratify }"
        if [[ "${track}" =~ ^(global|wide)$ ]]; then
            exec sudo -n /usr/local/sbin/auto-invest-observe regime-stratify "${track}"
        fi
        echo "refused command: ${cmd}" >&2
        exit 126
        ;;
    observe\ candidate-history\ *)
        dataset="${cmd#observe candidate-history }"
        if [[ "${dataset}" =~ ^(micro-gtaa|global-trend-wide|global-trend-fixed|multi-asset-trend)$ ]]; then
            exec sudo -n /usr/local/sbin/auto-invest-observe candidate-history "${dataset}"
        fi
        echo "refused command: ${cmd}" >&2
        exit 126
        ;;
    observe\ daily-ml-edge)
        exec sudo -n /usr/local/sbin/auto-invest-observe daily-ml-edge
        ;;
    live-canary-order\ *)
        read -r action run_id signed_sha capital expires nonce signature extra <<<"${cmd}"
        if [[ "${action:-}" == "live-canary-order" \
            && -z "${extra:-}" \
            && "${run_id:-}" =~ ^[0-9]+$ \
            && "${signed_sha:-}" =~ ^[0-9a-f]{40}$ \
            && "${capital:-}" =~ ^[0-9]+([.][0-9]+)?$ \
            && "${expires:-}" =~ ^[0-9]+$ \
            && "${nonce:-}" =~ ^[0-9]+-[0-9]+$ \
            && "${signature:-}" =~ ^[A-Za-z0-9+/]+={0,2}$ ]]; then
            exec sudo -n /usr/local/sbin/auto-invest-live-canary order \
                "${run_id}" "${signed_sha}" "${capital}" "${expires}" "${nonce}" "${signature}"
        fi
        echo "refused command: ${cmd}" >&2
        exit 126
        ;;
    live-canary-verify-order\ *)
        read -r action run_id signed_sha capital expires nonce signature extra <<<"${cmd}"
        if [[ "${action:-}" == "live-canary-verify-order" \
            && -z "${extra:-}" \
            && "${run_id:-}" =~ ^[0-9]+$ \
            && "${signed_sha:-}" =~ ^[0-9a-f]{40}$ \
            && "${capital:-}" =~ ^[0-9]+([.][0-9]+)?$ \
            && "${expires:-}" =~ ^[0-9]+$ \
            && "${nonce:-}" =~ ^[0-9]+-[0-9]+$ \
            && "${signature:-}" =~ ^[A-Za-z0-9+/]+={0,2}$ ]]; then
            exec sudo -n /usr/local/sbin/auto-invest-live-canary verify-order \
                "${run_id}" "${signed_sha}" "${capital}" "${expires}" "${nonce}" "${signature}"
        fi
        echo "refused command: ${cmd}" >&2
        exit 126
        ;;
    live-canary-fills)
        exec sudo -n /usr/local/sbin/auto-invest-live-canary fills
        ;;
    live-canary-scheduled-status)
        exec sudo -n /usr/local/sbin/auto-invest-live-canary scheduled-status
        ;;
    live-canary-scheduled-status\ *)
        scheduled_run_id="${cmd#live-canary-scheduled-status }"
        if [[ "${scheduled_run_id}" =~ ^[0-9]{14}$ ]]; then
            exec sudo -n /usr/local/sbin/auto-invest-live-canary scheduled-status \
                "${scheduled_run_id}"
        fi
        echo "refused command: ${cmd}" >&2
        exit 126
        ;;
    live-canary-runtime-status)
        exec sudo -n /usr/local/sbin/auto-invest-live-canary runtime-status
        ;;
    live-canary-fills\ *)
        read -r action start_date end_date extra <<<"${cmd}"
        if [[ "${action:-}" == "live-canary-fills" \
            && -z "${extra:-}" \
            && "${start_date:-}" =~ ^[0-9]{8}$ \
            && "${end_date:-}" =~ ^[0-9]{8}$ ]]; then
            exec sudo -n /usr/local/sbin/auto-invest-live-canary fills \
                "${start_date}" "${end_date}"
        fi
        echo "refused command: ${cmd}" >&2
        exit 126
        ;;
    live-canary-profit\ *)
        capital="${cmd#live-canary-profit }"
        if [[ "${capital}" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
            exec sudo -n /usr/local/sbin/auto-invest-live-canary profit "${capital}"
        fi
        echo "refused command: ${cmd}" >&2
        exit 126
        ;;
    reconciliation-halt-recovery)
        exec sudo -n /usr/local/sbin/auto-invest-reconciliation-recovery
        ;;
    emergency-deploy\ *)
        read -r action target_sha workflow_run_id actor issued_at expires_at reason_sha256 extra <<<"${cmd}"
        if [[ "${action:-}" == "emergency-deploy" \
            && -z "${extra:-}" \
            && "${target_sha:-}" =~ ^[0-9a-f]{40}$ \
            && "${workflow_run_id:-}" =~ ^[1-9][0-9]*$ \
            && "${actor:-}" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,37}[A-Za-z0-9])?$ \
            && "${issued_at:-}" =~ ^[1-9][0-9]*$ \
            && "${expires_at:-}" =~ ^[1-9][0-9]*$ \
            && "${reason_sha256:-}" =~ ^[0-9a-f]{64}$ ]]; then
            exec sudo -n /usr/local/sbin/auto-invest-emergency-deploy \
                "${target_sha}" "${workflow_run_id}" "${actor}" \
                "${issued_at}" "${expires_at}" "${reason_sha256}"
        fi
        echo "refused command: ${cmd}" >&2
        exit 126
        ;;
    start-deploy)
        exec sudo -n /usr/bin/systemctl start auto-invest-deploy.service
        ;;
    deploy-journal)
        exec sudo -n /usr/bin/journalctl -u auto-invest-deploy.service -n 120 --no-pager
        ;;
    deploy-audit)
        exec sudo -n /usr/local/sbin/auto-invest-deploy-audit
        ;;
    deploy-audit\ *)
        correlation_id="${cmd#deploy-audit }"
        if [[ "${correlation_id}" =~ ^[0-9a-fA-F]{8,64}$ ]]; then
            exec sudo -n /usr/local/sbin/auto-invest-deploy-audit "${correlation_id}"
        fi
        echo "refused command: ${cmd}" >&2
        exit 126
        ;;
    *)
        echo "refused command: ${cmd}" >&2
        exit 126
        ;;
esac
EOF_GATEWAY
    install -m 0755 -o root -g root "${GATEWAY_PATH}.new" "${GATEWAY_PATH}"
    rm -f "${GATEWAY_PATH}.new"
}

install_sync_helper() {
    install_repo_file "deploy/sync-units.sh" "${REPO_SYNC_UNITS}" "${SYNC_HELPER_PATH}"
}

install_kis_smoke_helper() {
    install_repo_file \
        "deploy/kis-smoke-on-instance.sh" \
        "${REPO_KIS_SMOKE_HELPER}" \
        "${KIS_SMOKE_HELPER_PATH}"
}

install_observe_helper() {
    install_repo_file \
        "deploy/observe-on-instance.sh" \
        "${REPO_OBSERVE_HELPER}" \
        "${OBSERVE_HELPER_PATH}"
}

install_live_canary_helper() {
    install_repo_file \
        "deploy/live-canary-on-instance.sh" \
        "${REPO_LIVE_CANARY_HELPER}" \
        "${LIVE_CANARY_HELPER_PATH}"
}

install_reconciliation_recovery_helper() {
    install_repo_file \
        "deploy/reconciliation-recovery-on-instance.sh" \
        "${REPO_RECONCILIATION_RECOVERY_HELPER}" \
        "${RECONCILIATION_RECOVERY_HELPER_PATH}"
}

install_deploy_audit_helper() {
    install_repo_file \
        "deploy/deploy-audit-on-instance.sh" \
        "${REPO_DEPLOY_AUDIT_HELPER}" \
        "${DEPLOY_AUDIT_HELPER_PATH}"
}

install_emergency_deploy_helper() {
    install_repo_file \
        "deploy/emergency-deploy-on-instance.sh" \
        "${REPO_EMERGENCY_DEPLOY_HELPER}" \
        "${EMERGENCY_DEPLOY_HELPER_PATH}"
}

install_runtime_boundaries() {
    install -d -m 0750 -o root -g "${APP_GROUP}" "${RUNTIME_BOUNDARY_DIR}"
    [[ ! -L "${RUNTIME_BOUNDARY_DIR}" ]] || die "unsafe runtime boundary directory"
    if [[ ! -e "${BROKER_WRITE_LOCK_PATH}" ]]; then
        install -m 0660 -o root -g "${APP_GROUP}" /dev/null "${BROKER_WRITE_LOCK_PATH}"
    fi
    [[ -f "${BROKER_WRITE_LOCK_PATH}" && ! -L "${BROKER_WRITE_LOCK_PATH}" ]] \
        || die "unsafe broker-write coordination lock"
    chown root:"${APP_GROUP}" "${BROKER_WRITE_LOCK_PATH}"
    chmod 0660 "${BROKER_WRITE_LOCK_PATH}"
}

install_live_order_public_key() {
    local tmp_file
    tmp_file="$(mktemp)"
    if [[ -d "${REPO}/.git" ]] \
        && id "${REPO_OWNER}" >/dev/null 2>&1 \
        && sudo -u "${REPO_OWNER}" git -C "${REPO}" show \
            "${REPO_REF}:deploy/live-order-signing-public.pem" > "${tmp_file}" 2>/dev/null; then
        :
    elif [[ -f "${REPO_LIVE_ORDER_PUBLIC_KEY}" ]]; then
        cp "${REPO_LIVE_ORDER_PUBLIC_KEY}" "${tmp_file}"
    else
        rm -f "${tmp_file}"
        die "missing live order signing public key"
    fi
    install -d -m 0755 -o root -g root "$(dirname "${LIVE_ORDER_PUBLIC_KEY_PATH}")"
    install -m 0644 -o root -g root "${tmp_file}" "${LIVE_ORDER_PUBLIC_KEY_PATH}"
    rm -f "${tmp_file}"
}

install_deploy_user() {
    if ! id "${DEPLOY_USER}" >/dev/null 2>&1; then
        useradd --system --create-home --home-dir "${DEPLOY_HOME}" --shell /bin/bash "${DEPLOY_USER}"
    fi
    install -d -m 0750 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" "${DEPLOY_HOME}"
    install -d -m 0700 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" "${DEPLOY_HOME}/.ssh"
}

install_authorized_key() {
    local auth_file="${DEPLOY_HOME}/.ssh/authorized_keys"
    local tmp_file
    tmp_file="$(mktemp)"
    if [[ -f "${auth_file}" ]]; then
        awk '
            $0 == "# auto-invest managed deploy key begin" {skip=1; next}
            $0 == "# auto-invest managed deploy key end" {skip=0; next}
            skip != 1 {print}
        ' "${auth_file}" > "${tmp_file}"
    fi
    {
        cat "${tmp_file}"
        echo "# auto-invest managed deploy key begin"
        printf 'restrict,no-pty,no-agent-forwarding,no-X11-forwarding,no-port-forwarding,command="%s" %s\n' \
            "${GATEWAY_PATH}" "${DEPLOY_PUBLIC_KEY}"
        echo "# auto-invest managed deploy key end"
    } > "${tmp_file}.new"
    install -m 0600 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" "${tmp_file}.new" "${auth_file}"
    rm -f "${tmp_file}" "${tmp_file}.new"
}

install_sudoers() {
    local tmp_file
    tmp_file="$(mktemp)"
    cat > "${tmp_file}" <<EOF_SUDOERS
# auto-invest deploy gateway: ${DEPLOY_USER} may run only fixed root-owned commands.
${DEPLOY_USER} ALL=(root) NOPASSWD: ${SYNC_HELPER_PATH}, ${KIS_SMOKE_HELPER_PATH}, ${OBSERVE_HELPER_PATH}, ${LIVE_CANARY_HELPER_PATH}, ${RECONCILIATION_RECOVERY_HELPER_PATH}, ${DEPLOY_AUDIT_HELPER_PATH}, ${EMERGENCY_DEPLOY_HELPER_PATH} *, /usr/bin/systemctl start auto-invest-deploy.service, /usr/bin/journalctl -u auto-invest-deploy.service -n 120 --no-pager
EOF_SUDOERS
    visudo -cf "${tmp_file}" >/dev/null
    install -m 0440 -o root -g root "${tmp_file}" "${SUDOERS_PATH}"
    rm -f "${tmp_file}"
}

retire_legacy_root_key() {
    local legacy_pub=""
    local changed=0
    local ts
    ts="$(date -u +%Y%m%dT%H%M%SZ)"
    install -d -m 0700 -o root -g root /root/.ssh
    touch "${ROOT_AUTHORIZED_KEYS}"
    chmod 0600 "${ROOT_AUTHORIZED_KEYS}"

    if [[ -f "${LEGACY_ROOT_KEY_PATH}.pub" ]]; then
        legacy_pub="$(cat "${LEGACY_ROOT_KEY_PATH}.pub")"
    fi

    local tmp_file
    tmp_file="$(mktemp)"
    awk -v legacy="${legacy_pub}" -v comment="${LEGACY_ROOT_KEY_COMMENT}" '
        legacy != "" && index($0, legacy) > 0 {changed=1; next}
        comment != "" && index($0, comment) > 0 {changed=1; next}
        {print}
        END { if (changed == 1) exit 7 }
    ' "${ROOT_AUTHORIZED_KEYS}" > "${tmp_file}" || {
        code=$?
        if [[ "${code}" -eq 7 ]]; then
            changed=1
        else
            rm -f "${tmp_file}"
            exit "${code}"
        fi
    }

    if [[ "${changed}" -eq 1 ]]; then
        cp -a "${ROOT_AUTHORIZED_KEYS}" "${ROOT_AUTHORIZED_KEYS}.pre-auto-invest-boundary-${ts}"
        install -m 0600 -o root -g root "${tmp_file}" "${ROOT_AUTHORIZED_KEYS}"
        echo "retired legacy root authorized_keys entry"
    else
        echo "no legacy root authorized_keys entry found"
    fi
    rm -f "${tmp_file}"

    if [[ -e "${LEGACY_ROOT_KEY_PATH}" || -e "${LEGACY_ROOT_KEY_PATH}.pub" ]]; then
        local retired_dir="/root/.ssh/retired-auto-invest-root-key-${ts}"
        install -d -m 0700 -o root -g root "${retired_dir}"
        [[ -e "${LEGACY_ROOT_KEY_PATH}" ]] && mv "${LEGACY_ROOT_KEY_PATH}" "${retired_dir}/"
        [[ -e "${LEGACY_ROOT_KEY_PATH}.pub" ]] && mv "${LEGACY_ROOT_KEY_PATH}.pub" "${retired_dir}/"
        chmod -R go-rwx "${retired_dir}"
        echo "moved legacy root key files to ${retired_dir}"
    fi
}

main() {
    require_root
    if [[ "${REFRESH_HELPERS_ONLY}" == "1" ]]; then
        install_gateway
        install_sync_helper
        install_kis_smoke_helper
        install_observe_helper
        install_live_canary_helper
        install_reconciliation_recovery_helper
        install_deploy_audit_helper
        install_emergency_deploy_helper
        install_runtime_boundaries
        install_live_order_public_key
        install_sudoers
        echo "AUTO_INVEST_SSH_BOUNDARY_HELPERS_REFRESHED"
        echo "deploy_user=${DEPLOY_USER}"
        echo "gateway=${GATEWAY_PATH}"
        echo "sync_helper=${SYNC_HELPER_PATH}"
        echo "kis_smoke_helper=${KIS_SMOKE_HELPER_PATH}"
        echo "observe_helper=${OBSERVE_HELPER_PATH}"
        echo "live_canary_helper=${LIVE_CANARY_HELPER_PATH}"
        echo "reconciliation_recovery_helper=${RECONCILIATION_RECOVERY_HELPER_PATH}"
        echo "deploy_audit_helper=${DEPLOY_AUDIT_HELPER_PATH}"
        echo "emergency_deploy_helper=${EMERGENCY_DEPLOY_HELPER_PATH}"
        echo "live_order_public_key=${LIVE_ORDER_PUBLIC_KEY_PATH}"
        exit 0
    fi
    validate_inputs
    install_gateway
    install_sync_helper
    install_kis_smoke_helper
    install_observe_helper
    install_live_canary_helper
    install_reconciliation_recovery_helper
    install_deploy_audit_helper
    install_emergency_deploy_helper
    install_runtime_boundaries
    install_live_order_public_key
    install_deploy_user
    install_authorized_key
    install_sudoers
    retire_legacy_root_key

    echo "AUTO_INVEST_SSH_BOUNDARY_REPAIRED"
    echo "deploy_user=${DEPLOY_USER}"
    echo "gateway=${GATEWAY_PATH}"
    echo "sync_helper=${SYNC_HELPER_PATH}"
    echo "kis_smoke_helper=${KIS_SMOKE_HELPER_PATH}"
    echo "observe_helper=${OBSERVE_HELPER_PATH}"
    echo "live_canary_helper=${LIVE_CANARY_HELPER_PATH}"
    echo "reconciliation_recovery_helper=${RECONCILIATION_RECOVERY_HELPER_PATH}"
    echo "deploy_audit_helper=${DEPLOY_AUDIT_HELPER_PATH}"
    echo "emergency_deploy_helper=${EMERGENCY_DEPLOY_HELPER_PATH}"
    echo "live_order_public_key=${LIVE_ORDER_PUBLIC_KEY_PATH}"
}

main "$@"

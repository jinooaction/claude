#!/usr/bin/env bash
# Refresh the root-owned SSH forced-command gateway and helper scripts from
# origin/main during deploy. This is intentionally narrower than the one-time
# repair script: it does not create users, install keys, retire root keys,
# start workers, arm live trading, or change capital.

set -euo pipefail

REPO="${REPO:-/opt/auto-invest}"
REF="${REF:-origin/main}"
REPO_OWNER="${REPO_OWNER:-auto-invest}"

die() {
    echo "ERROR: $*" >&2
    exit 2
}

require_root() {
    if [[ "$(id -u)" -ne 0 ]]; then
        die "run as root"
    fi
}

require_repo() {
    [[ -d "${REPO}/.git" ]] || die "missing repo: ${REPO}"
}

main() {
    require_root
    require_repo

    if ! sudo -u "${REPO_OWNER}" git -C "${REPO}" fetch origin main --quiet; then
        echo "WARN: git fetch failed; using existing ${REF}" >&2
    fi

    local tmpdir
    tmpdir="$(mktemp -d)"
    trap "rm -rf '${tmpdir}'" EXIT

    sudo -u "${REPO_OWNER}" git -C "${REPO}" show "${REF}:deploy/repair-ssh-boundary.sh" \
        > "${tmpdir}/repair-ssh-boundary.sh" \
        || die "missing deploy/repair-ssh-boundary.sh at ${REF}"
    chmod 0700 "${tmpdir}/repair-ssh-boundary.sh"

    REFRESH_HELPERS_ONLY=1 \
    REPO="${REPO}" \
    REPO_REF="${REF}" \
    REPO_OWNER="${REPO_OWNER}" \
        bash "${tmpdir}/repair-ssh-boundary.sh"
}

main "$@"

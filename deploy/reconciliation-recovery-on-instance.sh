#!/usr/bin/env bash
# Fixed production reconciliation recovery. It can clear only an eligible
# reconciliation-origin halt and can never submit orders.

set -euo pipefail

REPO="${REPO:-/opt/auto-invest}"
APP_USER="${APP_USER:-auto-invest}"

die() {
    echo "ERROR: $*" >&2
    exit 2
}

[[ -d "${REPO}/.git" ]] || die "missing repo: ${REPO}"
[[ ! -L "${REPO}/data/halt.flag" ]] || die "unsafe halt symlink"
cd "${REPO}"

exec sudo -u "${APP_USER}" -H /usr/local/bin/uv run auto-invest reconcile-recover \
    --confirm \
    --db data/auto_invest.db \
    --halt-path data/halt.flag \
    --env .env \
    --external-holdings deploy/external-holdings.toml \
    --opening-positions deploy/live-opening-positions.toml \
    --portfolio deploy/canary-live-portfolio.toml \
    --format json

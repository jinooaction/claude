#!/bin/bash
# auto-invest cloud-init repair script.
#
# Use when the Vultr cloud-init User-Data ran but failed partway through
# (most commonly: `git clone` into /opt/auto-invest failed because the
# directory already contained the data/ and logs/ subdirectories created
# by earlier steps -- git clone refuses non-empty targets).
#
# This script is idempotent: safe to re-run if a step fails.
#
# Usage on the instance console (as root):
#   curl -sSL https://raw.githubusercontent.com/jinooaction/claude/main/scripts/repair_install.sh | bash
#
# After this finishes successfully, the operator runs:
#   bash /opt/auto-invest/scripts/set_secrets.sh
# to enter KIS credentials and start the worker in dry-run mode.

set -euo pipefail

AUTO_INVEST_CAPITAL="${AUTO_INVEST_CAPITAL:-100}"
REPO_URL="https://github.com/jinooaction/claude.git"
INSTALL_DIR="/opt/auto-invest"

echo "[1/8] system user + base dirs (idempotent)"
if ! id auto-invest >/dev/null 2>&1; then
    useradd --system --create-home --home-dir /var/lib/auto-invest --shell /bin/bash auto-invest
fi

echo "[2/8] ensure uv is on the system PATH"
if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh
fi
ln -sf /usr/local/bin/uv /usr/bin/uv || true

echo "[3/8] reset ${INSTALL_DIR} to a clean clone of origin/main"
# Remove the partial install dir entirely so git clone can create it fresh.
# data/ and logs/ are recreated AFTER the clone, so the audit DB (if any
# old run wrote anything) is sacrificed -- acceptable on first install.
rm -rf "${INSTALL_DIR}"
git clone "${REPO_URL}" "${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}/data" "${INSTALL_DIR}/logs"
chown -R auto-invest:auto-invest "${INSTALL_DIR}"
chmod 0750 "${INSTALL_DIR}"

echo "[4/8] uv sync"
cd "${INSTALL_DIR}"
sudo -u auto-invest /usr/local/bin/uv sync --quiet

echo "[5/8] create .env with placeholder KIS keys (chmod 0600)"
umask 077
cat > "${INSTALL_DIR}/.env" <<EOF
# KIS credentials are written by:
#   bash ${INSTALL_DIR}/scripts/set_secrets.sh
KIS_APP_KEY=
KIS_APP_SECRET=
KIS_ACCOUNT_NO=
AUTO_INVEST_CAPITAL=${AUTO_INVEST_CAPITAL}
AUTO_INVEST_MODE=dry-run
EOF
chown auto-invest:auto-invest "${INSTALL_DIR}/.env"
chmod 0600 "${INSTALL_DIR}/.env"
umask 022

echo "[6/8] apply SQLite audit-log migrations"
sudo -u auto-invest /usr/local/bin/uv run auto-invest db migrate \
    --db "${INSTALL_DIR}/data/auto_invest.db"

echo "[7/8] install systemd units + timer"
install -m 0644 "${INSTALL_DIR}/deploy/auto-invest.service"        /etc/systemd/system/auto-invest.service
install -m 0644 "${INSTALL_DIR}/deploy/auto-invest-deploy.service" /etc/systemd/system/auto-invest-deploy.service
install -m 0644 "${INSTALL_DIR}/deploy/auto-invest-deploy.timer"   /etc/systemd/system/auto-invest-deploy.timer
systemctl daemon-reload
systemctl enable --now auto-invest-deploy.timer
systemctl enable auto-invest.service

echo "[8/8] done"
echo
echo "============================================================"
echo "auto-invest install repaired successfully."
echo
echo "Now run this to enter your KIS credentials and start the"
echo "worker in dry-run mode:"
echo
echo "    bash ${INSTALL_DIR}/scripts/set_secrets.sh"
echo
echo "============================================================"

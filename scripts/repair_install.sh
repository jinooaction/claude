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

echo "[3/9] reset ${INSTALL_DIR} to a clean clone of origin/main"
# Remove the partial install dir entirely so git clone can create it fresh.
# data/ and logs/ are recreated AFTER the clone, so the audit DB (if any
# old run wrote anything) is sacrificed -- acceptable on first install.
rm -rf "${INSTALL_DIR}"
git clone "${REPO_URL}" "${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}/data" "${INSTALL_DIR}/logs" "${INSTALL_DIR}/config"
# Seed config/rules.toml from the canary fixture so the first
# `auto-invest deploy` dry_run_check has a valid file to validate.
# spec 010's `auto-invest design` overwrites this on operator OK.
if [[ ! -f "${INSTALL_DIR}/config/rules.toml" ]]; then
    install -m 0640 \
        "${INSTALL_DIR}/tests/fixtures/rules/sample-canary.toml" \
        "${INSTALL_DIR}/config/rules.toml"
fi
chown -R auto-invest:auto-invest "${INSTALL_DIR}"
chmod 0750 "${INSTALL_DIR}"

echo "[4/9] uv sync"
cd "${INSTALL_DIR}"
sudo -u auto-invest /usr/local/bin/uv sync --quiet

echo "[5/9] create .env with placeholder KIS keys (chmod 0600)"
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

echo "[6/9] apply SQLite audit-log migrations"
sudo -u auto-invest /usr/local/bin/uv run auto-invest db migrate \
    --db "${INSTALL_DIR}/data/auto_invest.db"

echo "[7/9] install polkit rule (auto-invest user manages its own unit)"
# Without this, deploy's supervisor.start_worker() hits a polkit password
# prompt and the rollback path stalls. Scope is narrow: only the
# auto-invest user, only the auto-invest.service unit, only manage-units.
install -d -m 0755 /etc/polkit-1/rules.d
cat > /etc/polkit-1/rules.d/50-auto-invest.rules <<'POLKIT_EOF'
polkit.addRule(function(action, subject) {
    if ((action.id == "org.freedesktop.systemd1.manage-units") &&
        subject.user == "auto-invest" &&
        action.lookup("unit") == "auto-invest.service") {
        return polkit.Result.YES;
    }
});
POLKIT_EOF
chmod 0644 /etc/polkit-1/rules.d/50-auto-invest.rules
systemctl reload polkit 2>/dev/null || systemctl restart polkit 2>/dev/null || true

echo "[8/9] install systemd units + timer"
install -m 0644 "${INSTALL_DIR}/deploy/auto-invest.service"        /etc/systemd/system/auto-invest.service
install -m 0644 "${INSTALL_DIR}/deploy/auto-invest-deploy.service" /etc/systemd/system/auto-invest-deploy.service
install -m 0644 "${INSTALL_DIR}/deploy/auto-invest-deploy.timer"   /etc/systemd/system/auto-invest-deploy.timer
systemctl daemon-reload
systemctl enable --now auto-invest-deploy.timer
systemctl enable auto-invest.service

echo "[9/9] done"
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

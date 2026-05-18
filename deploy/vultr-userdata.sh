#!/bin/bash
# Vultr cloud-init User-Data for auto-invest. Runs once at instance first boot.
#
# Usage:
#   (A) Operator creates instance via Vultr console:
#       Paste this entire file into the "User Data" / "Cloud-Init" field.
#       Set AUTO_INVEST_CAPITAL below if you want a value other than 100 USD.
#       KIS credentials are NOT in this file -- operator runs the helper on the
#       instance console after boot:
#         bash /opt/auto-invest/scripts/set_secrets.sh
#
#   (B) GitHub Actions provisioning workflow:
#       Same. The workflow substitutes AUTO_INVEST_CAPITAL automatically.
#
# After one week of dry-run observation, flip to live trading with one line:
#   sed -i 's/^AUTO_INVEST_MODE=.*/AUTO_INVEST_MODE=live/' /opt/auto-invest/.env \
#   && systemctl restart auto-invest.service
#
# Safety:
#   - Runs once at boot under cloud-init as root.
#   - KIS keys stay as empty placeholders until set_secrets.sh writes them.
#     The worker is fail-safe in the placeholder state (refuses to start).
#   - Logs land in /var/log/auto-invest-cloud-init.log; no secret is echoed.
#
# IMPORTANT -- this file is ASCII-only on purpose. The Vultr new-experience
# Deploy UI has been observed to reject cloud-init payloads that contain
# non-ASCII characters (e.g. Korean comments) at form-submit time, with no
# visible error. Keep this file ASCII so the Deploy button works for any
# operator copy-pasting it from GitHub raw. Korean-facing documentation lives
# in docs/OPERATOR_VULTR_ONE_STEP_KR.md.

set -euo pipefail
exec > >(tee /var/log/auto-invest-cloud-init.log) 2>&1

# =====================================================================
# CONFIGURE_ME -- only this line. KIS keys go in via set_secrets.sh.
# =====================================================================
AUTO_INVEST_CAPITAL="100"
# =====================================================================

echo "[1/8] apt update + base tools"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq git curl nano build-essential ca-certificates sqlite3

echo "[2/8] timezone UTC"
timedatectl set-timezone UTC

echo "[3/8] auto-invest system user (no install dir yet -- git clone needs empty target)"
if ! id auto-invest >/dev/null 2>&1; then
    useradd --system --create-home --home-dir /var/lib/auto-invest --shell /bin/bash auto-invest
fi

echo "[4/8] install uv (system PATH)"
curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh
ln -sf /usr/local/bin/uv /usr/bin/uv

echo "[5/8] clone repo (target must be empty) + create data/logs after + uv sync"
# git clone refuses a non-empty target. Clone FIRST, then create data/logs.
rm -rf /opt/auto-invest
git clone https://github.com/jinooaction/claude.git /opt/auto-invest
install -d -m 0750 -o auto-invest -g auto-invest /opt/auto-invest/data
install -d -m 0750 -o auto-invest -g auto-invest /opt/auto-invest/logs
# uv cache lives here so the ProtectSystem=strict worker unit can write to it
# (default $HOME/.cache/uv = /var/lib/auto-invest/.cache/uv is read-only under
# the hardened service). Same path is pinned via UV_CACHE_DIR for every uv
# call below and in auto-invest.service.
install -d -m 0750 -o auto-invest -g auto-invest /opt/auto-invest/.cache/uv
chown -R auto-invest:auto-invest /opt/auto-invest
chmod 0750 /opt/auto-invest
cd /opt/auto-invest
sudo -u auto-invest UV_CACHE_DIR=/opt/auto-invest/.cache/uv /usr/local/bin/uv sync --quiet

echo "[6/8] create .env with placeholder KIS keys (chmod 0600, owned by auto-invest)"
umask 077
cat > /opt/auto-invest/.env <<EOF
# KIS credentials are written by:
#   bash /opt/auto-invest/scripts/set_secrets.sh
KIS_APP_KEY=
KIS_APP_SECRET=
KIS_ACCOUNT_NO=
AUTO_INVEST_CAPITAL=${AUTO_INVEST_CAPITAL}
AUTO_INVEST_MODE=dry-run
EOF
chown auto-invest:auto-invest /opt/auto-invest/.env
chmod 0600 /opt/auto-invest/.env
umask 022

echo "[7/8] apply SQLite audit-log migrations"
cd /opt/auto-invest
sudo -u auto-invest UV_CACHE_DIR=/opt/auto-invest/.cache/uv /usr/local/bin/uv run auto-invest db migrate --db /opt/auto-invest/data/auto_invest.db

echo "[8/8] install systemd units + timer (worker is fail-safe until KIS keys set)"
install -m 0644 /opt/auto-invest/deploy/auto-invest.service        /etc/systemd/system/auto-invest.service
install -m 0644 /opt/auto-invest/deploy/auto-invest-deploy.service /etc/systemd/system/auto-invest-deploy.service
install -m 0644 /opt/auto-invest/deploy/auto-invest-deploy.timer   /etc/systemd/system/auto-invest-deploy.timer
systemctl daemon-reload
# Deploy timer activates immediately (does not need KIS keys; just git pull).
systemctl enable --now auto-invest-deploy.timer
# Worker is enabled only -- operator starts it via set_secrets.sh which
# writes the KIS keys and then calls systemctl restart auto-invest.service.
systemctl enable auto-invest.service

echo
echo "============================================================"
echo "auto-invest instance setup complete."
echo
echo "Next: open the View Console, log in as root, and run:"
echo
echo "    bash /opt/auto-invest/scripts/set_secrets.sh"
echo
echo "It will prompt for the three KIS secrets (input hidden), write"
echo "them to /opt/auto-invest/.env (chmod 0600), and restart the"
echo "worker in dry-run mode."
echo
echo "One week later, flip to live trading with one line:"
echo "  sed -i 's/^AUTO_INVEST_MODE=.*/AUTO_INVEST_MODE=live/' /opt/auto-invest/.env \\"
echo "  && systemctl restart auto-invest.service"
echo "============================================================"

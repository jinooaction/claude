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

echo "[5/9] clone repo (target must be empty) + create data/logs after + uv sync"
# git clone refuses a non-empty target. Clone FIRST, then create data/logs.
rm -rf /opt/auto-invest
git clone https://github.com/jinooaction/claude.git /opt/auto-invest
install -d -m 0750 -o auto-invest -g auto-invest /opt/auto-invest/data
install -d -m 0750 -o auto-invest -g auto-invest /opt/auto-invest/logs
install -d -m 0750 -o auto-invest -g auto-invest /opt/auto-invest/config
# uv cache lives here so the ProtectSystem=strict worker unit can write to it
# (default $HOME/.cache/uv = /var/lib/auto-invest/.cache/uv is read-only under
# the hardened service). Same path is pinned via UV_CACHE_DIR for every uv
# call below and in auto-invest.service.
install -d -m 0750 -o auto-invest -g auto-invest /opt/auto-invest/.cache/uv
# Seed config/rules.toml from the canary fixture so the first
# `auto-invest deploy` dry_run_check has a valid file to validate.
# spec 010's `auto-invest design` writes a fresh rules_auto_<ts>.toml on
# operator OK; this seed only exists to unblock the first deploy.
install -m 0640 -o auto-invest -g auto-invest \
    /opt/auto-invest/tests/fixtures/rules/sample-canary.toml \
    /opt/auto-invest/config/rules.toml
chown -R auto-invest:auto-invest /opt/auto-invest
chmod 0750 /opt/auto-invest
cd /opt/auto-invest
sudo -u auto-invest UV_CACHE_DIR=/opt/auto-invest/.cache/uv /usr/local/bin/uv sync --quiet

echo "[6/9] create .env with placeholder KIS keys (chmod 0600, owned by auto-invest)"
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

echo "[7/9] apply SQLite audit-log migrations"
cd /opt/auto-invest
sudo -u auto-invest UV_CACHE_DIR=/opt/auto-invest/.cache/uv /usr/local/bin/uv run auto-invest db migrate --db /opt/auto-invest/data/auto_invest.db

echo "[8/9] install sudoers so auto-invest user can control the worker unit"
# 배포 상태기계(`auto-invest deploy`, auto-invest 사용자)의 supervisor.stop_worker()/
# start_worker() 가 워커 유닛을 `sudo -n systemctl …` 로 제어한다. polkit 은 프로덕션
# 호스트에서 규칙이 로드돼도 manage-units 를 인가하지 못해(Interactive authentication
# required) 버렸다 — sudo 가 결정론적 대체다.
# sudoers 드롭인: 배포 상태기계가 워커 유닛만 `sudo -n systemctl …` 로 제어하는 결정론적
# 인가 경로(polkit 대체). 반드시 visudo 검증 후 설치(잘못된 sudoers.d 는 모든 sudo 를 깨뜨림).
# sync-units.sh 도 매 배포 동기화하므로 돌고 있는 서버에서 유실돼도 되살아난다.
if visudo -cf /opt/auto-invest/deploy/auto-invest-deploy.sudoers >/dev/null 2>&1; then
    install -m 0440 -o root -g root /opt/auto-invest/deploy/auto-invest-deploy.sudoers /etc/sudoers.d/auto-invest-deploy
else
    echo "WARN: auto-invest-deploy.sudoers failed visudo — not installing" >&2
fi

echo "[9/9] install systemd units + timers (worker is fail-safe until KIS keys set)"
install -m 0644 /opt/auto-invest/deploy/auto-invest.service        /etc/systemd/system/auto-invest.service
install -m 0644 /opt/auto-invest/deploy/auto-invest-deploy.service /etc/systemd/system/auto-invest-deploy.service
install -m 0644 /opt/auto-invest/deploy/auto-invest-deploy.timer   /etc/systemd/system/auto-invest-deploy.timer
install -m 0644 /opt/auto-invest/deploy/auto-invest-tune.service   /etc/systemd/system/auto-invest-tune.service
install -m 0644 /opt/auto-invest/deploy/auto-invest-tune.timer     /etc/systemd/system/auto-invest-tune.timer
systemctl daemon-reload
# Deploy timer activates immediately (does not need KIS keys; just git pull).
systemctl enable --now auto-invest-deploy.timer
# Tuner timer activates immediately too: the tuner needs no KIS keys (pure
# deterministic, no LLM), and run-tune.sh is fail-safe until the worker has
# created the telemetry DB. Fires daily at 22:00 UTC, after US close.
systemctl enable --now auto-invest-tune.timer
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

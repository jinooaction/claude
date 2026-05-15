#!/usr/bin/env bash
# auto-invest — operator preflight script.
#
# Run this on the operator's host AFTER `git clone` + `uv sync` + filling
# in `.env`. The script:
#   1. Verifies the venv + CLI surface (`auto-invest --help`).
#   2. Verifies required secrets are present (`.env` parsed; never
#      logged or echoed in plaintext).
#   3. Runs the worker in dry-run against the supplied rules file —
#      this NEVER contacts KIS and is safe to run with real keys.
#   4. Runs `auto-invest deploy --dry-run --supervisor dryrun` against
#      a temp DB so the deploy pipeline is exercised end-to-end.
#   5. Prints the EXACT systemctl commands the operator needs to run
#      AS ROOT to enable the worker + deploy timer. It does NOT run
#      them itself — root operations require operator review.
#
# Exit code 0 on green; non-zero on any failure. Failure surfaces the
# specific phase so the operator can correct and re-run.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

echo "== auto-invest operator preflight =="
echo "repo: $repo_root"
echo

# ---- 1. CLI surface ---------------------------------------------------------
echo "[1/5] Verifying CLI surface..."
if ! uv run auto-invest --help >/dev/null 2>&1; then
    echo "  FAIL: 'uv run auto-invest --help' did not return 0."
    echo "  Hint: run 'uv sync' first, then re-run this script."
    exit 11
fi
echo "  OK"
echo

# ---- 2. Required secrets ----------------------------------------------------
echo "[2/5] Verifying required secrets (.env)..."
if [[ ! -f .env ]]; then
    echo "  FAIL: .env not found."
    echo "  Hint: cp .env.example .env  &&  edit .env to fill in KIS keys + AUTO_INVEST_CAPITAL"
    exit 12
fi
missing=()
for key in KIS_APP_KEY KIS_APP_SECRET KIS_ACCOUNT_NO AUTO_INVEST_CAPITAL; do
    # Match KEY=value where value is non-empty and not just whitespace.
    if ! grep -qE "^${key}=[^[:space:]]" .env; then
        missing+=("$key")
    fi
done
if [[ ${#missing[@]} -gt 0 ]]; then
    echo "  FAIL: missing or empty in .env: ${missing[*]}"
    echo "  Hint: edit .env and fill in real values for the listed keys."
    exit 13
fi
# Capital should look like a positive integer USD amount.
capital="$(grep -E '^AUTO_INVEST_CAPITAL=' .env | sed -E 's/^[^=]+=//; s/[\"'\'' ]//g')"
if ! [[ "$capital" =~ ^[0-9]+$ ]] || [[ "$capital" -lt 100 ]]; then
    echo "  FAIL: AUTO_INVEST_CAPITAL='$capital' is not a positive integer >= 100."
    exit 14
fi
echo "  OK (KIS_* present; AUTO_INVEST_CAPITAL=$capital)"

# Export .env so child processes (worker, deploy) inherit the secrets.
# `uv run` activates the venv but does NOT auto-load .env; in production
# systemd does this via EnvironmentFile=, so we mirror that here.
set -a
# shellcheck disable=SC1091
source .env
set +a
echo

# ---- 3. DB migrations -------------------------------------------------------
echo "[3/5] Applying SQLite migrations..."
mkdir -p data
if ! uv run auto-invest db migrate --db data/auto_invest.db >/tmp/auto-invest-migrate.log 2>&1; then
    echo "  FAIL: db migrate failed; see /tmp/auto-invest-migrate.log"
    exit 15
fi
echo "  OK ($(tail -1 /tmp/auto-invest-migrate.log))"
echo

# ---- 4. Worker dry-run ------------------------------------------------------
echo "[4/5] Running worker dry-run (no KIS calls)..."
rules_path="config/rules.toml"
if [[ ! -f "$rules_path" ]]; then
    rules_path="tests/fixtures/rules/sample-canary.toml"
    echo "  Note: config/rules.toml not found; falling back to $rules_path for the dry-run."
fi
if ! uv run auto-invest run --dry-run --config "$rules_path" --db data/auto_invest.db --capital "$capital" 2>&1 | tee /tmp/auto-invest-dryrun.log >/dev/null; then
    echo "  FAIL: worker dry-run failed; see /tmp/auto-invest-dryrun.log"
    cat /tmp/auto-invest-dryrun.log
    exit 16
fi
echo "  OK"
sed -n 's/^/    /p' /tmp/auto-invest-dryrun.log
echo

# ---- 5. Deploy dry-run (no-op against current HEAD) ------------------------
echo "[5/5] Running 'auto-invest deploy --dry-run'..."
if ! uv run auto-invest deploy --dry-run --supervisor dryrun --branch main --db data/auto_invest.db --repo . 2>&1 | tee /tmp/auto-invest-deploy.log >/dev/null; then
    echo "  FAIL: deploy dry-run failed; see /tmp/auto-invest-deploy.log"
    cat /tmp/auto-invest-deploy.log
    exit 17
fi
echo "  OK"
sed -n 's/^/    /p' /tmp/auto-invest-deploy.log
echo

# ---- Done -------------------------------------------------------------------
cat <<EOF
=========================================================
All preflight checks passed.

Next: install the systemd units AS ROOT. The exact commands are
listed below — review them, then run them yourself. This script
does NOT escalate to root.

  sudo install -m 0644 deploy/auto-invest.service        /etc/systemd/system/auto-invest.service
  sudo install -m 0644 deploy/auto-invest-deploy.service /etc/systemd/system/auto-invest-deploy.service
  sudo install -m 0644 deploy/auto-invest-deploy.timer   /etc/systemd/system/auto-invest-deploy.timer
  sudo systemctl daemon-reload
  sudo systemctl enable --now auto-invest.service
  sudo systemctl enable --now auto-invest-deploy.timer

Verify:

  sudo systemctl status auto-invest.service
  sudo systemctl list-timers auto-invest-deploy.timer
  sudo journalctl -u auto-invest.service -n 50

Cutover check (1 minute):
  Wait for the first WORKER_STARTED audit row, then query:
    sqlite3 data/auto_invest.db \\
      "SELECT ts_utc, event_type FROM audit_log
       WHERE ts_utc > datetime('now', '-5 minutes') ORDER BY seq DESC LIMIT 10;"

If anything looks off, refer to:
  - deploy/README.md          (operator install + troubleshooting)
  - specs/006-deploy-automation/quickstart.md
  - HANDOFF.md § '운영자 사용성 — 지금 바로 가능한 것'
=========================================================
EOF

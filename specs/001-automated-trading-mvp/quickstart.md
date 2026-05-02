# Quickstart: Automated US-Equity Trading MVP

This guide walks the operator from a fresh checkout to a worker running
in `--dry-run` mode against a single canary rule. It does not place any
real orders. Once you have completed it, the next step is to fill in
real KIS credentials and to drop `--dry-run`.

> **Constitution recap**: deny-by-default + position sizing caps are
> enforced before any order leaves the process. Until you have the
> values you want in `config/rules.toml`, keep `--dry-run` on.

## Prerequisites

- Python 3.11
- `uv` package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- A Korea Investment & Securities account with OpenAPI access enabled
  for **overseas equities**, plus an issued app key/secret.

## 1. Install dependencies

```bash
uv sync
```

This reads `pyproject.toml` and `uv.lock` and creates `.venv/`.

## 2. Configure secrets

```bash
cp .env.example .env
# then edit .env to fill in:
#   KIS_APP_KEY=...
#   KIS_APP_SECRET=...
#   KIS_ACCOUNT_NO=...
```

`.env` is gitignored. The worker refuses to start if any of these are
missing or empty.

## 3. Author your first rules file

Copy the sample and edit values:

```bash
mkdir -p config
cp tests/fixtures/rules/sample-canary.toml config/rules.toml
```

Open `config/rules.toml` and confirm:

- `[caps]` values are conservative for your account size.
- `[whitelist].symbols` lists only tickers you are comfortable trading.
- Each `[[rules]]` entry has `stage = "CANARY"` for first-time runs.

## 4. Initialize the database

```bash
uv run auto-invest db migrate
```

This creates `data/auto_invest.db` (gitignored) and applies any
pending schema migrations.

## 5. Dry-run the worker

```bash
uv run auto-invest run --dry-run
```

The worker:

- loads `.env` (and registers every value as a redactable secret),
- validates `config/rules.toml`,
- prints the resolved caps, whitelist, and parsed rules,
- contacts KIS exactly once to verify your account exists,
- exits `0`.

It does **not** place orders, does **not** subscribe to market data,
and does **not** start the asyncio loop. If any check fails, the
worker exits `2` with a precise message.

## 6. Inspect the audit log

```bash
sqlite3 data/auto_invest.db \
  'SELECT ts_utc, event_type, rule_id, symbol FROM audit_log ORDER BY seq DESC LIMIT 10;'
```

You should see at least `WORKER_STARTED`, `SECRETS_LOADED`, and
`WORKER_STOPPED` rows from the dry run.

## 7. (When you are ready) live run

```bash
uv run auto-invest run
```

In a separate terminal you can:

```bash
uv run auto-invest status                              # one-screen status
uv run auto-invest halt --reason "investigating"       # stop new orders
uv run auto-invest resume --confirm                    # allow new orders again
uv run auto-invest report                              # produce yesterday's report
```

## What this MVP does NOT do (yet)

- It does **not** call any LLM (per OD-2; v2 will introduce
  Claude-assisted judgment points).
- It does **not** hot-reload `config/rules.toml`; edits take effect
  after a restart (per OD-3).
- It does **not** push notifications; alerts live in the audit log
  and the daily report.
- It does **not** trade derivatives, options, futures, crypto, short,
  on margin, or domestic Korean equities (constitution v1.0.0).

## Where to look when something is unexpected

| Symptom | First place to check |
|---------|----------------------|
| Worker refuses to start with exit 2 | stderr message; `config/rules.toml` validation rules in `contracts/rules-config.md` |
| Order rejected unexpectedly | `audit_log` rows with `event_type='ORDER_REJECTED_BY_GATE'`; payload contains the gate name |
| Reconciliation reports a mismatch | `reconciliation_runs.mismatch_payload_json`; do not clear without writing a reason |
| KIS API calls failing in bursts | breaker may be open; check audit rows with `event_type='ERROR'` and the per-call-site state |

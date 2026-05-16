# auto-invest

Python-driven investment automation. The service runs as a long-lived
background worker that executes operator-declared trading rules on
US-listed equities via the Korea Investment & Securities (KIS) OpenAPI.

Built with Spec-Driven Development (SDD) using
[spec-kit](https://github.com/github/spec-kit). The non-negotiable
principles live in [`.specify/memory/constitution.md`](.specify/memory/constitution.md);
every feature begins as a spec under [`specs/`](specs/).

## What v1 does

- Loads operator-declared rules (time / price / indicator triggers) at
  startup and evaluates them during US regular trading hours.
- Routes every order through deny-by-default risk gates:
  whitelist · halt · per-trade cap · per-symbol cap · global cap.
- Persists every order, fill, error, and judgment to an append-only
  SQLite audit log (UPDATE/DELETE blocked by triggers).
- Reconciles internal state against the broker after each session and
  halts new orders on any mismatch.
- Emits a daily report (Markdown + JSON) summarising the session.

## What v1 does NOT do (yet)

- Does **not** call any LLM. Claude-assisted judgment is reserved for
  a later spec (see 004 stub).
- Does **not** hot-reload rules; edits take effect after a restart.
- Does **not** trade derivatives, options, futures, crypto, on margin,
  short, or domestic Korean equities.

## Operator quickstart

**GitHub Actions로 위임 (가장 자율 수행, 권장):** [`docs/OPERATOR_GITHUB_ACTIONS_KR.md`](docs/OPERATOR_GITHUB_ACTIONS_KR.md) — GitHub Secrets에 Vultr 토큰 한 번 박고 Actions 탭에서 "Run workflow" 한 번 클릭하면 인스턴스 자동 생성. KIS 키만 Vultr 콘솔에서 한 번 입력.

**Vultr 콘솔에서 직접 만들기:** [`docs/OPERATOR_VULTR_ONE_STEP_KR.md`](docs/OPERATOR_VULTR_ONE_STEP_KR.md) — GitHub Actions 안 쓰고 Vultr 콘솔에서 직접 인스턴스 만드는 경로. cloud-init User-Data에 자본금 한 줄만 박음.

**Vultr 단계별 (이전 가이드, 학습용):** [`docs/OPERATOR_START_NONDEV_KR.md`](docs/OPERATOR_START_NONDEV_KR.md) — 명령어를 한 줄씩 직접 쳐가며 학습하고 싶으신 분.

**개발자 (Linux + systemd 보유):** [`docs/OPERATOR_START.md`](docs/OPERATOR_START.md) — `git clone` → `.env` → `bash scripts/operator_install.sh`.

**자세한 영어 가이드:** [`specs/001-automated-trading-mvp/quickstart.md`](specs/001-automated-trading-mvp/quickstart.md).
TL;DR:

```bash
uv sync
cp .env.example .env             # edit .env to add your KIS credentials
uv run auto-invest db migrate
uv run auto-invest run --dry-run --config tests/fixtures/rules/sample-canary.toml
```

## CLI cheatsheet

```bash
auto-invest run --dry-run         # validate config, never contacts the broker
auto-invest run --capital 10000   # live run (US-session-aware)
auto-invest db migrate            # apply pending schema migrations
auto-invest halt --reason "..."   # block new orders (persists across restarts)
auto-invest resume --confirm      # clear the halt flag
auto-invest status                # one-screen JSON state summary
auto-invest report --date 2026-05-04   # emit yesterday's daily report
auto-invest efficiency --window 7d     # JSON snapshot of LLM token KPIs (spec 002)
auto-invest ingest-history --from-dir history/csv/          # spec 008 OHLCV ingest
auto-invest backtest --rules config/rules.toml \            # spec 008 backtest
    --from 2024-01-02 --to 2024-12-31
auto-invest backtest --rules config/rules.toml --synthetic-shock  # canonical shock days
auto-invest deploy --branch main          # spec 006 off-hours deploy automation
auto-invest deploy --dry-run              # validate without restarting the worker
auto-invest version
```

### Deploy automation (spec 006)

`auto-invest deploy` is the single-command, off-hours deploy runner.
It refuses to run during US regular hours (constitution VIII.A),
acquires a PID lock, fetches `origin/<branch>`, runs the kernel-touch
forensic check, applies migrations, restarts the worker, and waits
90 s for a healthy `WORKER_STARTED` audit row before declaring success.
On failure it rolls back to the previous sha. Every phase is recorded
in `audit_log` joined by a single `correlation_id`. Systemd unit +
timer templates ship under `deploy/`; install steps are in
[`specs/006-deploy-automation/quickstart.md`](specs/006-deploy-automation/quickstart.md)
and [`deploy/README.md`](deploy/README.md).

### Backtest engine (spec 008)

`auto-invest backtest` replays an operator-supplied ruleset against
historical OHLCV bars through the SAME `risk.gates` and
`strategy.triggers` code the live worker uses (Path B, see
[`specs/008-backtest-engine/research.md`](specs/008-backtest-engine/research.md#r-b13)).
It never connects to KIS or Anthropic. Run
[`specs/008-backtest-engine/quickstart.md`](specs/008-backtest-engine/quickstart.md)
for a 30-day fixture walkthrough; output lands under
`data/backtest/<run_id>/` with `backtest-run.json`, `metrics.csv`,
`summary.md`, and per-rule `orders.json` / `fills.json` /
`gate-rejections.json`.


Optional, for live KIS adapter validation (read-only, never places an
order):

```bash
uv run python scripts/live_smoke.py
```

## Development

```bash
uv sync                  # install dependencies
uv run pytest            # run tests
uv run ruff check .      # lint
uv run ruff format .     # format
```

Continuous integration runs the full test suite **without** ever
touching live broker endpoints; the live smoke test is gated by
`KIS_LIVE_TEST=1` and skipped otherwise.

## Active specs

- **001 — automated US-equity trading MVP** (shipped):
  [`specs/001-automated-trading-mvp/`](specs/001-automated-trading-mvp/).
  Read in this order: `spec.md` → `plan.md` → `research.md` →
  `data-model.md` → `contracts/` → `quickstart.md` → `tasks.md`.
- **002 — token telemetry & efficiency KPIs** (shipped on
  `claude/optimize-token-efficiency-uYiKk`):
  [`specs/002-token-telemetry/`](specs/002-token-telemetry/). Adds the
  `auto-invest efficiency` CLI plus a Token-Efficiency section in the
  daily report.
- **003 — Claude Code session cache** (shipped, operator-side
  validation pending): [`specs/003-session-cache/`](specs/003-session-cache/).
  Configures `.claude/settings.json` and a SessionStart hook that
  surfaces the long-lived constitution + active-spec context.
- **004 — LLM judgment points** (stub):
  [`specs/004-llm-judgment-points/`](specs/004-llm-judgment-points/).
- **005 — autonomous tuner** (stub):
  [`specs/005-autonomous-tuner/`](specs/005-autonomous-tuner/).

## Repository layout

```
src/auto_invest/
  config/          rules + caps + whitelist + loader
  broker/          KIS REST adapter + resilient HTTP client
  market_data/     PriceBar persistence + quality checks
  strategy/        triggers + indicators + canary auto-pause
  risk/            deny-by-default gates
  execution/       order router (gate chain + broker + audit)
  persistence/     SQLite + append-only audit log
  reconciliation/  end-of-session position diff
  reports/         daily report (Markdown + JSON)
  worker/          asyncio loop + halt flag + market calendar
  cli.py           operator commands (typer)
```

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
  a later spec.
- Does **not** hot-reload rules; edits take effect after a restart.
- Does **not** trade derivatives, options, futures, crypto, on margin,
  short, or domestic Korean equities.

## Operator quickstart

Walk through [`specs/001-automated-trading-mvp/quickstart.md`](specs/001-automated-trading-mvp/quickstart.md).
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
auto-invest version
```

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

## Active spec

Feature 001 — automated US-equity trading MVP — under
[`specs/001-automated-trading-mvp/`](specs/001-automated-trading-mvp/).
Read in this order: `spec.md` → `plan.md` → `research.md` →
`data-model.md` → `contracts/` → `quickstart.md` → `tasks.md`.

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

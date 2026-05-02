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
- Routes every order through deny-by-default risk gates (whitelist,
  per-trade / per-symbol / global exposure caps, halt flag, strategy
  stage uniqueness).
- Persists every order, fill, error, and judgment to an append-only
  SQLite audit log.
- Reconciles internal state against the broker after each session and
  halts new orders on any mismatch.
- Emits a daily report summarising the session.

## What v1 does NOT do (yet)

- Does **not** call any LLM. Claude-assisted judgment is reserved for a
  later spec.
- Does **not** hot-reload rules; edits take effect after a restart.
- Does **not** trade derivatives, options, futures, crypto, on margin,
  short, or domestic Korean equities.

## Operator quickstart

Start with [`specs/001-automated-trading-mvp/quickstart.md`](specs/001-automated-trading-mvp/quickstart.md).

## Development

```bash
uv sync                  # install dependencies
uv run pytest            # run tests
uv run ruff check .      # lint
uv run ruff format .     # format
```

## Active spec

Feature 001 — automated US-equity trading MVP — under
[`specs/001-automated-trading-mvp/`](specs/001-automated-trading-mvp/).
Read in this order: `spec.md` → `plan.md` → `research.md` →
`data-model.md` → `contracts/` → `quickstart.md` → `tasks.md`.

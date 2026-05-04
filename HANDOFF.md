# auto-invest — Next-Session Handoff

This file is the entry point for **the next Claude session** working on
this repository. It summarises what's done, where to read, and the
options the operator is considering for the next milestone.

## Status as of last commit on `main`

* **Spec 001 (automated US-equity trading MVP)** — fully implemented
  and validated end-to-end.
* **Test count**: 256 passing + 1 skipped (live KIS smoke is gated by
  `KIS_LIVE_TEST=1`).
* **Live broker validation**: operator (mason) ran
  `scripts/live_smoke.py` against their real KIS account on
  2026-05-04; returned a real-time AAPL quote (`$279.4475`). The
  KIS overseas-equity adapter is verified against production.
* **Constitution v1.0.0** — all eight principles satisfied for v1.

## Reading order for the next session

Read in this exact order before doing anything new:

1. `.specify/memory/constitution.md`
2. `specs/001-automated-trading-mvp/spec.md`
3. `specs/001-automated-trading-mvp/plan.md`
4. `specs/001-automated-trading-mvp/research.md`
5. `specs/001-automated-trading-mvp/data-model.md`
6. `specs/001-automated-trading-mvp/contracts/`
7. `specs/001-automated-trading-mvp/tasks.md` (every task box checked)
8. `README.md`
9. This file (`HANDOFF.md`)

## Open milestone options (operator chooses)

The operator (non-developer) needs to pick one of these directions.
Whichever they pick, start by writing a new spec under
`specs/002-<short-name>/spec.md` via the SDD workflow
(`/speckit-specify` → `/speckit-plan` → `/speckit-tasks` →
`/speckit-implement`).

### Option A — v2: Claude judgment integration

The original founding intent ("Python core, Claude only at judgment
points") was deliberately deferred in v1 (OD-2 in spec 001). Reviving
it means defining concrete judgment points and binding them to the
order pipeline.

Likely scope for v2:

- New principle in the constitution OR re-confirmation of principle
  III with concrete judgment-point definitions.
- New spec section for what triggers a Claude consult: "unusual size",
  "high-vol regime", "news event" — pick something concrete.
- A `judgment/` module that uses the `anthropic` SDK already in
  `pyproject.toml`. Tool use + structured output for yes/no decisions.
- Tests with a mocked Anthropic client (similar to how `respx` mocks
  KIS).
- Latency + cost budgets per judgment point.

### Option B — First canary live trade

The system is wired and verified, but has never placed a real order.
A single small canary trade is the next concrete proof.

Likely scope:

- Operator declares total capital and writes one rule with a real
  symbol (e.g. SPY) and a small qty.
- Run the worker live during US session.
- After the session: review audit log, run `auto-invest report`,
  verify reconciliation.
- Document the experience back into a "first run" appendix in
  quickstart.md.

This is mostly **operator action**, not new code. The next Claude
session might just answer questions and review the audit log.

### Option C — Operational hardening

Make the worker survive in real conditions: cloud deploy, push
notifications, monitoring dashboard, scheduled restart, backup of the
SQLite db.

Likely scope:

- New spec: "auto-invest hosting & alerting"
- systemd / launchd service definition (or Docker)
- Push notification channel (telegram bot, email, or apple push)
- Daily backup of `data/auto_invest.db` to cloud storage
- Health-check endpoint or heartbeat audit row

### Option D — Backtest engine (sibling spec)

Spec 001 explicitly listed "backtest engine" as out of scope (it
consumes results, doesn't produce them). v1 is fine without it, but
operator needs backtests before promoting any new strategy from
canary. So a backtest spec is a real follow-up.

Likely scope:

- Historical bar dataset (CSV ingest or vendor API).
- Replay loop that drives the existing `Worker.tick` against
  historical quotes instead of live.
- Backtest report (returns, Sharpe, drawdown, per-rule).
- Promotion gate that consumes a passing backtest as input to canary.

## How to start the next session

Have Claude (or the operator) say something like:

> Read HANDOFF.md, the constitution, and tasks.md. The operator has
> picked Option <A/B/C/D>. Start the SDD cycle for spec 002.

If the operator is undecided, the right move is to ask them which
one they value most — speed of feature delivery (B), system
intelligence (A), production reliability (C), or strategy validation
discipline (D).

## What NOT to do in the next session

- Do **not** modify any spec 001 file unless the operator explicitly
  asks for an amendment. v1 is shipped.
- Do **not** invent a feature without writing a spec first. SDD
  discipline is the project's working agreement.
- Do **not** push KIS credentials anywhere. They live only in the
  operator's local `.env`. Live testing is via the existing
  `scripts/live_smoke.py` runner; future live integration tests must
  follow the same gating pattern (`KIS_LIVE_TEST=1` env var).
- Do **not** push to `main` without operator permission. The
  branching convention going forward is one feature branch per spec
  (e.g. `claude/002-llm-judgment`), merged after operator review.

## Quick state summary table

| What | State |
|------|-------|
| Constitution | v1.0.0 ratified |
| Spec 001 | shipped to `main`, 256/256 tests, live broker verified |
| Operator local env | working `uv` venv, working `gh` auth, KIS keys in `.env` (operator's machine only) |
| Outstanding T062 | now done (live smoke run on operator's MacBook) |
| Pending operator decision | which of options A–D to start as spec 002 |

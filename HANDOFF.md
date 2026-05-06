# auto-invest — Next-Session Handoff

This file is the entry point for **the next Claude session** working on
this repository. It summarises what's done, where to read, and the
direction that has been chosen for the next milestones.

## North star (operator-set, 2026-05-06)

> **Goal**: build and operate a **world-class, self-improving automated
> investment service**. Investment scope is **not limited to US
> equities** — every domain that can be automated by a system is in
> scope (other equity markets, FX, crypto, derivatives where legal,
> rates, commodities, etc.).
>
> Until that goal is met, "v1 ships" is not the same as "we are done".
> v1 is a safe **execution shell**, not a strategy and not a research
> platform. The next specs exist to close that gap.

This north star is also captured in `CLAUDE.md` and is binding on every
future spec.

## Status as of last commit on `main`

* **Spec 001 (automated US-equity trading MVP)** — fully implemented
  and validated end-to-end as a *rule execution shell*.
* **Test count**: 256 passing + 1 skipped (live KIS smoke is gated by
  `KIS_LIVE_TEST=1`).
* **Live broker validation**: operator (mason) ran
  `scripts/live_smoke.py` against their real KIS account on
  2026-05-04; returned a real-time AAPL quote (`$279.4475`). The
  KIS overseas-equity adapter is verified against production.
* **Constitution v1.0.0** — all eight principles satisfied for v1.

### What v1 is and is NOT (read this before recommending next steps)

| Capability | State |
|---|---|
| Order plumbing through KIS, with risk gates and audit log | ✅ shipped |
| Reconciliation, halt/resume, daily report | ✅ shipped |
| Trigger families (time / price / EMA-cross / RSI-threshold) | ✅ shipped |
| **Portfolio construction algorithm** | ❌ none — operator hand-writes rules |
| **Alpha signal research / factor model** | ❌ none |
| **Backtest engine** | ❌ none — explicitly out of scope in spec 001 |
| **Multi-source market data (news, fundamentals, alt-data, macro)** | ❌ none — only KIS OHLCV |
| **Multi-asset support** (FX, crypto, derivatives, etc.) | ❌ none — US equities only |
| **LLM-assisted judgment points** | ❌ deferred (OD-2 in spec 001) |
| **Self-improving loop** (system tunes its own strategies) | ❌ none |

The honest framing: v1 will **execute any rule the operator writes
correctly and safely**, but it cannot tell the operator whether the
rule has any edge. That is the gap the next specs close.

## Reading order for the next session

Read in this exact order before doing anything new:

1. `.specify/memory/constitution.md`
2. `CLAUDE.md` (north star + active spec pointer)
3. `HANDOFF.md` (this file)
4. `specs/001-automated-trading-mvp/spec.md` (what v1 actually does)
5. `specs/001-automated-trading-mvp/research.md` (R-1 … R-12 decisions)
6. `specs/001-automated-trading-mvp/data-model.md`
7. `specs/001-automated-trading-mvp/contracts/`
8. `specs/002-data-and-backtest/spec.md` ← next active spec
9. `README.md`

## Roadmap (operator-approved, 2026-05-06)

The original A/B/C/D options in the previous handoff have been
**re-prioritised** because canary live trading (B) without a backtest
or measured strategy is just paying slippage to learn nothing. Goal of
"world-class" requires measurement before money.

```
spec 002  ─→  spec 003  ─→  spec 004  ─→  spec 005  ─→  spec 006
data +        strategy R&D    Claude         first         operational
backtest      (alpha,         judgment       canary live   hardening
              factors,        integration    trade
              portfolio
              construction)
```

| Spec | Was option | Now | Why this order |
|---|---|---|---|
| 002 — data infra + backtest engine | D | **first** | No "world-class" claim is testable without a backtest; constitution principle VI (`backtest → canary → full-live`) is currently not enforceable. |
| 003 — strategy R&D framework | (new) | second | Once 002 exists, hypotheses can be tested. This is where "alpha", factor research, and portfolio construction live. |
| 004 — Claude judgment integration | A | third | Worth investing in once judgment points are *measurable* via backtest harness (002) and a strategy framework (003). Adding LLM before that risks paying for noise. |
| 005 — first canary live trade | B | fourth | A canary that ships a strategy that already passed 002+003 is a real promotion, not a plumbing test. |
| 006 — operational hardening | C | fifth | Cloud deploy, alerts, backup, monitoring. Does not block earlier specs; can be lifted forward if reliability becomes a blocker. |

### Multi-asset expansion (constitution amendment)

The current constitution (v1.0.0) lists US equities as the *initial*
scope and explicitly rules out derivatives, leverage, short selling,
options, futures, crypto, and domestic Korean equities. The operator's
north star expands this. Plan:

- Spec 002 (data + backtest) is **designed asset-class agnostic from
  the start** — schemas, time handling, corporate-action plumbing, and
  the replay engine treat OHLCV-style and tick-style instruments
  uniformly. No constitution amendment needed for 002.
- Before any **trading** spec adds a non-US-equity asset class, a
  dedicated constitution amendment commit is required (per the
  `Governance` section). That amendment will be a MINOR version bump
  (principle expansion, not removal).

## How to start the next session

> Read `CLAUDE.md`, `HANDOFF.md`, and the active spec under
> `specs/002-data-and-backtest/`. The roadmap is locked in; the next
> step is `/speckit-plan` against spec 002 (or continue 002 spec
> refinement if there are still `[NEEDS CLARIFICATION]` markers).

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
  (e.g. `claude/002-data-and-backtest`), merged after operator review.
- Do **not** skip 002/003 to chase a canary live trade. The new order
  is **measurement before money**.

## Quick state summary table

| What | State |
|------|-------|
| Constitution | v1.0.0 ratified; multi-asset amendment pending (will land alongside the first non-US-equity trading spec) |
| Spec 001 | shipped to `main`, 256/256 tests, live broker verified |
| Spec 002 | drafted; needs `/speckit-plan` next |
| Operator local env | working `uv` venv, working `gh` auth, KIS keys in `.env` (operator's machine only) |
| Active branch | `claude/investment-automation-setup-8KPrZ` |
| North star | world-class, self-improving, multi-domain automated investment service |

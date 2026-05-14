"""Backtest judgment-point stub (T019).

Per research.md R-B9, every spec-004 judgment-point call during a backtest
short-circuits to a deterministic "safe default" branch and emits an
`LLM_CALL_STUBBED` audit row. No real Anthropic API call ever happens
inside `run_backtest()`.

Two-part contract:

  1. `JudgmentStub.decide(...)` — the substitute spec-004 clients call when
     `BACKTEST_MODE=1` is set. Always returns a rule-declared safe-default
     dict; never reaches a real LLM.
  2. `guard_no_real_llm(component)` — the future `AnthropicClient.__init__`
     (spec 004) MUST call this. If `BACKTEST_MODE=1` is in the environment,
     constructing a real LLM client raises `BacktestJudgmentLeakError` and
     the caller is responsible for translating that into a
     `BACKTEST_JUDGMENT_LEAK` ERROR audit row + exit code 79.

The two halves together close FR-B08: the stub provides the substitute,
the guard prevents the real one from being built behind the engine's back.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from auto_invest.persistence import audit
from auto_invest.persistence.audit import LlmCallStubbedPayload

BACKTEST_MODE_ENV = "BACKTEST_MODE"


class BacktestJudgmentLeakError(RuntimeError):
    """A real LLM client was constructed under BACKTEST_MODE=1."""


class BacktestSafeDefaultMissingError(KeyError):
    """The ruleset did not declare a safe-default branch for this decision class.

    Backtests refuse to fall back to "no-op" silently; a missing safe default
    is a configuration bug the operator must fix before re-running.
    """


def guard_no_real_llm(component: str) -> None:
    """Spec-004 LLM clients MUST call this in their constructor.

    Raises if `BACKTEST_MODE=1` is set in the environment. Defense-in-depth
    boundary so that no real Anthropic call can ever execute during a
    backtest run, even if a future code path forgets to swap to JudgmentStub.
    """
    if os.environ.get(BACKTEST_MODE_ENV) == "1":
        raise BacktestJudgmentLeakError(
            f"{component} attempted to construct a real LLM client while "
            f"{BACKTEST_MODE_ENV}=1; backtest must route judgment points "
            "through auto_invest.backtest.judgment_stub.JudgmentStub instead"
        )


def _canonical_input_sha256(inputs: Mapping[str, Any]) -> str:
    """Stable SHA-256 over canonical-JSON of `inputs` for FR-B15 byte-equality.

    `default=str` lets `Decimal`, `date`, `datetime` and `Path` serialise
    deterministically; `sort_keys=True` removes dict-iteration nondeterminism.
    """
    canonical = json.dumps(
        dict(inputs),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


@dataclass
class JudgmentStub:
    """Drop-in replacement for spec-004's future LLM judgment client.

    Constructed once per backtest run; passed by the engine in place of the
    real `AnthropicClient`. Every call records an `LLM_CALL_STUBBED` audit
    row with the canonical-JSON SHA-256 of `inputs`, then returns the
    rule-declared safe-default branch.

    `safe_defaults` must contain one entry per `decision_class` the ruleset
    can ask about; each entry is a dict with at least a `"branch"` key
    naming the branch (recorded in the audit row's `stubbed_branch` field)
    and any additional fields the rule expects in the return payload.
    """

    conn: sqlite3.Connection
    run_id: str
    safe_defaults: Mapping[str, dict[str, Any]] = field(default_factory=dict)

    def decide(self, *, decision_class: str, inputs: Mapping[str, Any]) -> dict[str, Any]:
        if decision_class not in self.safe_defaults:
            raise BacktestSafeDefaultMissingError(
                f"no safe-default branch declared for decision_class "
                f"{decision_class!r}; backtest cannot proceed without one"
            )
        default = self.safe_defaults[decision_class]
        if "branch" not in default:
            raise ValueError(
                f"safe_defaults[{decision_class!r}] must contain a 'branch' "
                "key naming the safe-default branch"
            )

        input_sha256 = _canonical_input_sha256(inputs)
        audit.append(
            self.conn,
            LlmCallStubbedPayload(
                run_id=self.run_id,
                decision_class=decision_class,
                input_sha256=input_sha256,
                stubbed_branch=str(default["branch"]),
            ),
            correlation_id=self.run_id,
        )
        return dict(default)


__all__ = [
    "BACKTEST_MODE_ENV",
    "BacktestJudgmentLeakError",
    "BacktestSafeDefaultMissingError",
    "JudgmentStub",
    "guard_no_real_llm",
]

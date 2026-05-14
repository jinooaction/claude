"""T020 — JudgmentStub emits LLM_CALL_STUBBED + leak-detection contract.

Verifies:
  - Each `decide(...)` writes exactly one LLM_CALL_STUBBED audit row.
  - `input_sha256` is the canonical-JSON SHA-256 of `inputs` and is stable
    across dict-iteration order (FR-B15 byte-equality precondition).
  - The returned dict equals the rule's safe-default branch.
  - Missing safe default raises BacktestSafeDefaultMissingError.
  - `guard_no_real_llm()` raises BacktestJudgmentLeakError under
    BACKTEST_MODE=1 and is silent otherwise.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from auto_invest.backtest.judgment_stub import (
    BACKTEST_MODE_ENV,
    BacktestJudgmentLeakError,
    BacktestSafeDefaultMissingError,
    JudgmentStub,
    guard_no_real_llm,
)
from auto_invest.persistence import audit, db


@pytest.fixture
def conn(tmp_path: Path):
    c = db.get_connection(tmp_path / "audit.db")
    db.migrate(c)
    yield c
    c.close()


@pytest.fixture
def stub(conn):
    return JudgmentStub(
        conn=conn,
        run_id="bt-run-abc123",
        safe_defaults={
            "should_promote": {"branch": "hold", "promote": False},
            "size_decision": {"branch": "default_size", "qty": 10},
        },
    )


# ---------- decide() emits LLM_CALL_STUBBED -------------------------------


def test_decide_emits_one_llm_call_stubbed(stub, conn) -> None:
    out = stub.decide(decision_class="should_promote", inputs={"sharpe": 0.5})

    rows = audit.read_all(conn)
    stubbed = [r for r in rows if r["event_type"] == "LLM_CALL_STUBBED"]
    assert len(stubbed) == 1
    payload = json.loads(stubbed[0]["payload_json"])
    assert payload["run_id"] == "bt-run-abc123"
    assert payload["decision_class"] == "should_promote"
    assert payload["stubbed_branch"] == "hold"
    # correlation_id aliased to run_id (R-B5)
    assert stubbed[0]["correlation_id"] == "bt-run-abc123"

    assert out == {"branch": "hold", "promote": False}


def test_decide_returns_copy_not_alias(stub) -> None:
    """Mutating the return dict MUST NOT poison the next call."""
    out = stub.decide(decision_class="should_promote", inputs={})
    out["branch"] = "PROMOTE_NOW"
    out2 = stub.decide(decision_class="should_promote", inputs={})
    assert out2["branch"] == "hold"


def test_input_sha256_is_canonical_json_hash(stub, conn) -> None:
    inputs = {"b": 2, "a": 1, "c": [3, 2, 1]}
    stub.decide(decision_class="should_promote", inputs=inputs)

    expected = hashlib.sha256(
        json.dumps(
            {"b": 2, "a": 1, "c": [3, 2, 1]},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()

    rows = audit.read_all(conn)
    payload = json.loads(rows[-1]["payload_json"])
    assert payload["input_sha256"] == expected


def test_input_sha256_stable_across_dict_insertion_order(stub, conn) -> None:
    """FR-B15 precondition: same logical inputs → same hash regardless of order."""
    stub.decide(decision_class="should_promote", inputs={"a": 1, "b": 2})
    stub.decide(decision_class="should_promote", inputs={"b": 2, "a": 1})

    rows = [
        json.loads(r["payload_json"])
        for r in audit.read_all(conn)
        if r["event_type"] == "LLM_CALL_STUBBED"
    ]
    assert len(rows) == 2
    assert rows[0]["input_sha256"] == rows[1]["input_sha256"]


def test_decide_records_each_call(stub, conn) -> None:
    stub.decide(decision_class="should_promote", inputs={"x": 1})
    stub.decide(decision_class="should_promote", inputs={"x": 2})
    stub.decide(decision_class="size_decision", inputs={"sym": "AAPL"})

    rows = [r for r in audit.read_all(conn) if r["event_type"] == "LLM_CALL_STUBBED"]
    assert len(rows) == 3


def test_missing_safe_default_raises(stub) -> None:
    with pytest.raises(BacktestSafeDefaultMissingError):
        stub.decide(decision_class="undeclared_class", inputs={})


def test_safe_default_without_branch_key_raises(conn) -> None:
    bad_stub = JudgmentStub(
        conn=conn,
        run_id="bt-run-xyz",
        safe_defaults={"x": {"foo": "bar"}},  # missing 'branch'
    )
    with pytest.raises(ValueError, match="must contain a 'branch' key"):
        bad_stub.decide(decision_class="x", inputs={})


# ---------- guard_no_real_llm: leak detection -----------------------------


def test_guard_silent_when_backtest_mode_unset(monkeypatch) -> None:
    monkeypatch.delenv(BACKTEST_MODE_ENV, raising=False)
    guard_no_real_llm("AnthropicClient")  # no raise


def test_guard_silent_when_backtest_mode_zero(monkeypatch) -> None:
    monkeypatch.setenv(BACKTEST_MODE_ENV, "0")
    guard_no_real_llm("AnthropicClient")  # no raise


def test_guard_raises_under_backtest_mode_one(monkeypatch) -> None:
    monkeypatch.setenv(BACKTEST_MODE_ENV, "1")
    with pytest.raises(BacktestJudgmentLeakError) as exc:
        guard_no_real_llm("AnthropicClient")
    assert "AnthropicClient" in str(exc.value)
    assert "BACKTEST_MODE=1" in str(exc.value)


def test_guard_called_by_simulated_anthropic_client(monkeypatch) -> None:
    """Spec-004 forward-compat handshake: a future AnthropicClient that
    invokes guard_no_real_llm in __init__ MUST fail-fast under
    BACKTEST_MODE=1, defending against any code path that forgot to
    swap to JudgmentStub."""

    class FakeAnthropicClient:
        def __init__(self) -> None:
            guard_no_real_llm(type(self).__name__)

    monkeypatch.setenv(BACKTEST_MODE_ENV, "1")
    with pytest.raises(BacktestJudgmentLeakError):
        FakeAnthropicClient()

    monkeypatch.setenv(BACKTEST_MODE_ENV, "0")
    FakeAnthropicClient()  # no raise


def test_env_var_state_does_not_leak_between_tests(monkeypatch) -> None:
    """Sanity: monkeypatch fixture rolls back env state."""
    assert os.environ.get(BACKTEST_MODE_ENV) != "1"

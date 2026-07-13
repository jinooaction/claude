from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from auto_invest.design.verifier import VerificationStageResult, verify_rules

_GOOD_TOML = """
[caps]
per_trade_pct = 5
per_symbol_pct = 20
global_exposure_pct = 80
canary_capital_pct = 5
canary_min_duration_days = 10
canary_acceptance_drawdown_pct = 3

[whitelist]
symbols = ["VOO", "QQQ"]
accounts = ["1234567801"]
order_types = ["MARKET", "LIMIT"]
sessions = ["REGULAR"]

[[rules]]
id = "rule_voo_buy"
symbol = "VOO"
stage = "CANARY"
priority = 10
enabled = true

[rules.trigger]
kind = "price"
direction = "<="
threshold = 999999
cooldown_seconds = 60

[rules.action]
side = "BUY"
order_type = "MARKET"
qty = 1
limit_price = "0"
"""


def _passing_stage(stage: str):
    def _validator(*, toml_text: str, candidate_fingerprint: str):  # noqa: ARG001
        return VerificationStageResult(
            stage=stage,
            status="PASS",
            reason_code="passed",
            reason_ko=f"{stage} 검증 통과",
            candidate_fingerprint=candidate_fingerprint,
            evidence_ref=f"{stage}-run-1",
            metrics={"observations": 1},
        )

    return _validator


def test_dynamic_evidence_missing_waits_fail_closed() -> None:
    result = verify_rules(_GOOD_TOML, kis_balance_usd=Decimal("102.45"))

    assert result.ok is False
    assert result.overall_status == "WAIT_DYNAMIC_VALIDATION"
    assert result.static_result.status == "PASS"
    assert result.backtest_result.status == "WAIT"
    assert result.paper_result.status == "WAIT"
    assert result.backtest_skipped is True
    assert result.paper_run_skipped is True
    assert result.candidate_fingerprint


def test_static_failure_blocks_before_dynamic_validation() -> None:
    result = verify_rules("[caps\nbroken", kis_balance_usd=Decimal("102.45"))

    assert result.ok is False
    assert result.overall_status == "BLOCKED"
    assert result.static_result.status == "FAIL"
    assert result.backtest_result.status == "WAIT"
    assert result.paper_result.status == "WAIT"
    assert "static" in result.blocking_reasons


def test_dynamic_validator_exception_blocks() -> None:
    def _boom(*, toml_text: str, candidate_fingerprint: str):  # noqa: ARG001
        raise RuntimeError("backtest unavailable")

    result = verify_rules(
        _GOOD_TOML,
        kis_balance_usd=Decimal("102.45"),
        backtest_validator=_boom,
        paper_validator=_passing_stage("paper"),
    )

    assert result.ok is False
    assert result.overall_status == "BLOCKED"
    assert result.backtest_result.status == "FAIL"
    assert "backtest_exception" in result.backtest_result.reason_code


def test_stubbed_or_malformed_dynamic_result_blocks() -> None:
    def _stub(*, toml_text: str, candidate_fingerprint: str):  # noqa: ARG001
        return None

    result = verify_rules(
        _GOOD_TOML,
        kis_balance_usd=Decimal("102.45"),
        backtest_validator=_stub,
        paper_validator=_passing_stage("paper"),
    )

    assert result.ok is False
    assert result.overall_status == "BLOCKED"
    assert result.backtest_result.status == "FAIL"
    assert result.backtest_result.reason_code == "backtest_malformed_result"


def test_fingerprint_mismatch_blocks() -> None:
    def _wrong_fingerprint(*, toml_text: str, candidate_fingerprint: str):  # noqa: ARG001
        return VerificationStageResult(
            stage="backtest",
            status="PASS",
            reason_code="passed",
            reason_ko="다른 후보 검증 결과",
            candidate_fingerprint="not-the-same-candidate",
            evidence_ref="bt-1",
            metrics={},
        )

    result = verify_rules(
        _GOOD_TOML,
        kis_balance_usd=Decimal("102.45"),
        backtest_validator=_wrong_fingerprint,
        paper_validator=_passing_stage("paper"),
    )

    assert result.ok is False
    assert result.overall_status == "BLOCKED"
    assert result.backtest_result.status == "FAIL"
    assert result.backtest_result.reason_code == "backtest_fingerprint_mismatch"


def test_stale_dynamic_evidence_blocks() -> None:
    def _stale(*, toml_text: str, candidate_fingerprint: str):  # noqa: ARG001
        return VerificationStageResult(
            stage="backtest",
            status="PASS",
            reason_code="passed",
            reason_ko="오래된 백테스트",
            candidate_fingerprint=candidate_fingerprint,
            evidence_ref="bt-old",
            fresh_until_utc="2026-01-01T00:00:00Z",
            metrics={},
        )

    result = verify_rules(
        _GOOD_TOML,
        kis_balance_usd=Decimal("102.45"),
        backtest_validator=_stale,
        paper_validator=_passing_stage("paper"),
        now_fn=lambda: datetime(2026, 7, 13, tzinfo=UTC),
    )

    assert result.ok is False
    assert result.overall_status == "BLOCKED"
    assert result.backtest_result.status == "FAIL"
    assert result.backtest_result.reason_code == "backtest_stale_evidence"


def test_all_actual_stage_evidence_passes() -> None:
    result = verify_rules(
        _GOOD_TOML,
        kis_balance_usd=Decimal("102.45"),
        backtest_validator=_passing_stage("backtest"),
        paper_validator=_passing_stage("paper"),
    )

    assert result.ok is True
    assert result.overall_status == "VERIFIED"
    assert result.backtest_skipped is False
    assert result.paper_run_skipped is False
    assert result.evidence_refs == ("backtest-run-1", "paper-run-1")

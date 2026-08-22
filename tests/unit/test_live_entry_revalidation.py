from auto_invest.portfolio.live_entry_revalidation import (
    ACTIVE_LIVE_TRACK,
    ENTRY_BLOCKED,
    ENTRY_READY,
    evaluate_live_entry,
)


def _profit(*, ready: bool = True, psr: float = 0.81) -> dict:
    return {
        "historical_verdict": "HOLDOUT_EDGE",
        "deployment_match": {
            "candidate_id": "globalfixed-ensemble-3-6-9-12",
            "historical_passed": True,
            "exploration_canary_ready": ready,
            "entry_policy": {"min_forward_obs": 40, "min_forward_psr": 0.8},
            "forward": {
                "n_obs": 47,
                "psr_vs_benchmark": psr,
                "beats_benchmark_calmar": True,
            },
        },
    }


def test_first_fill_requires_current_exploration_contract() -> None:
    result = evaluate_live_entry(
        _profit(), {"verdict": "PASS"}, {"fills_count": 0}, evidence_age_hours=2
    )
    assert result.allowed is True
    assert result.state == ENTRY_READY


def test_stale_entry_approval_fails_closed() -> None:
    result = evaluate_live_entry(
        _profit(ready=False, psr=0.60173),
        {"verdict": "PASS"},
        {"fills_count": 0},
        evidence_age_hours=2,
    )
    assert result.allowed is False
    assert result.state == ENTRY_BLOCKED
    assert "exploration_canary_ready" in result.reasons
    assert "forward_psr" in result.reasons


def test_missing_or_old_evidence_fails_closed_before_first_fill() -> None:
    missing = evaluate_live_entry(None, None, {"fills_count": 0}, evidence_age_hours=None)
    old = evaluate_live_entry(
        _profit(), {"verdict": "PASS"}, {"fills_count": 0}, evidence_age_hours=40
    )
    assert missing.allowed is False
    assert old.allowed is False
    assert "evidence_fresh" in old.reasons


def test_existing_fill_defers_to_live_risk_gates() -> None:
    result = evaluate_live_entry(None, None, {"fills_count": 1}, evidence_age_hours=None)
    assert result.allowed is True
    assert result.state == ACTIVE_LIVE_TRACK


def test_invalid_fill_count_never_opens_first_entry() -> None:
    result = evaluate_live_entry(_profit(), {"verdict": "PASS"}, {}, evidence_age_hours=1)
    assert result.allowed is False
    assert result.fills_count is None


def test_factory_winner_can_open_only_the_exact_10pct_strategy() -> None:
    fingerprint = "sha256:exact"
    factory = {
        "candidate_count": 64,
        "complete_trial_count": 64,
        "decision": {
            "verdict": "FACTORY_EDGE",
            "research_canary_eligible": True,
            "selected_candidate_id": "factory-winner",
            "selected_strategy_fingerprint": fingerprint,
        },
    }
    ready = evaluate_live_entry(
        None,
        {"verdict": "PASS"},
        {"fills_count": 0},
        evidence_age_hours=None,
        factory_evidence=factory,
        factory_evidence_age_hours=2,
        live_strategy_fingerprint=fingerprint,
    )
    mismatch = evaluate_live_entry(
        None,
        {"verdict": "PASS"},
        {"fills_count": 0},
        evidence_age_hours=None,
        factory_evidence=factory,
        factory_evidence_age_hours=2,
        live_strategy_fingerprint="sha256:other",
    )
    assert ready.allowed is True
    assert ready.evidence["entry_source"] == "strategy_factory"
    assert mismatch.allowed is False
    assert "factory_strategy_fingerprint" in mismatch.reasons


def test_incomplete_or_stale_factory_evidence_fails_closed() -> None:
    factory = {
        "candidate_count": 64,
        "complete_trial_count": 63,
        "decision": {
            "verdict": "FACTORY_EDGE",
            "research_canary_eligible": True,
            "selected_strategy_fingerprint": "sha256:exact",
        },
    }
    result = evaluate_live_entry(
        None,
        {"verdict": "PASS"},
        {"fills_count": 0},
        evidence_age_hours=None,
        factory_evidence=factory,
        factory_evidence_age_hours=40,
        live_strategy_fingerprint="sha256:exact",
    )
    assert result.allowed is False
    assert "factory_trials_complete" in result.reasons
    assert "factory_evidence_fresh" in result.reasons

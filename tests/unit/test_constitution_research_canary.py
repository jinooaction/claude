from decimal import Decimal
from pathlib import Path

from auto_invest.portfolio.capital_ladder import MAX_RUNG, RUNG_FRACTIONS

ROOT = Path(__file__).resolve().parents[2]


def test_constitution_requires_calibrated_family_entry_and_exact_fundability() -> None:
    text = (ROOT / ".specify" / "memory" / "constitution.md").read_text(encoding="utf-8")
    assert "**Version**: 15.0.0" in text
    assert "`gate_version=3.1` (`calibrated-family-entry-v3.1`)" in text
    assert "`gate_version=3.0`, legacy, and `gate_version=2.0` evidence are diagnostic-only" in text
    assert "`complete_family_trials`" in text
    assert "`prior_audit_complete`" in text
    assert "`global_audit_trials`" in text
    assert "`unique_audit_fingerprints`" in text
    assert "The consumer, not the producer, MUST independently recount" in text
    assert "holdout PSR MUST equal the selected raw trial row and be at least 0.95" in text
    assert "PBO MUST be at most 0.25" in text
    assert "DSR >= 0.95 and raw-candidate Bonferroni" in text
    assert "research_family_count × 0.01 <= 0.20" in text
    assert "100% positive-target quote coverage" in text
    assert "at least 66% funded among those whole-share-expressible targets" in text
    assert "A below-one-share target is excluded only from the funded-leg denominator" in text
    assert "L1 capital-weight error at most 25%" in text
    assert "maximum per-leg error at most 15%" in text
    assert "1 = 10% bounded canary (research-family or operational-verification entry)" in text
    assert "2 = 20% exploration canary" in text
    assert "3 = 25%" in text
    assert "4 = 50%" in text
    assert "5 = 100%" in text
    assert "Factory evidence alone can NEVER move capital above 10%" in text
    assert "typed `operational_canary_entry`" in text
    assert "`alpha_confirmed=false`, `max_rung=1`" in text
    assert "`promotion_above_rung1_allowed=false`" in text
    assert "Research diagnostics and capital-entry evidence MUST be separate" in text
    assert "MUST NEVER promote above rung 1" in text
    assert "drawdown ≥ budget/2 drops one rung" in text
    assert "drawdown ≥ budget disarms to rung 0" in text


def test_constitution_limits_live_wakeup_to_two_shared_claim_sources() -> None:
    text = (ROOT / ".specify" / "memory" / "constitution.md").read_text(encoding="utf-8")

    assert "restricted to exactly two automated sources" in text
    assert "rebalance-live-canary.yml" in text
    assert "auto-invest-live-canary.timer" in text
    assert "one root-owned market-session claim" in text
    assert "at most one broker-writing execution" in text
    assert "`workflow_dispatch`, `repository_dispatch`, arbitrary shell" in text


def test_ladder_fractions_match_constitution() -> None:
    assert {
        0: Decimal("0"),
        1: Decimal("0.10"),
        2: Decimal("0.20"),
        3: Decimal("0.25"),
        4: Decimal("0.50"),
        5: Decimal("1.00"),
    } == RUNG_FRACTIONS
    assert MAX_RUNG == 5

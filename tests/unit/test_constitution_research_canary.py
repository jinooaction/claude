from decimal import Decimal
from pathlib import Path

from auto_invest.portfolio.capital_ladder import MAX_RUNG, RUNG_FRACTIONS

ROOT = Path(__file__).resolve().parents[2]


def test_constitution_requires_v3_global_correction_and_exact_fundability() -> None:
    text = (ROOT / ".specify" / "memory" / "constitution.md").read_text(encoding="utf-8")
    assert "**Version**: 10.0.0" in text
    assert "`gate_version=3.0` (`family-complete-v3`)" in text
    assert "Legacy and `gate_version=2.0` evidence are diagnostic-only" in text
    assert "`complete_family_trials`" in text
    assert "`prior_audit_complete`" in text
    assert "`global_audit_trials`" in text
    assert "`unique_audit_fingerprints`" in text
    assert "The consumer, not the producer, MUST independently recount" in text
    assert "`min(1, (1 - PSR) × trials) <= 0.05`" in text
    assert "require DSR at least 0.95 and PBO at most 0.20" in text
    assert "100% positive-target quote coverage" in text
    assert "at least 66% funded positive target legs" in text
    assert "L1 capital-weight error at most 25%" in text
    assert "maximum per-leg error at most 15%" in text
    assert "1 = 10% research canary" in text
    assert "2 = 20% exploration canary" in text
    assert "3 = 25%" in text
    assert "4 = 50%" in text
    assert "5 = 100%" in text
    assert "Factory evidence alone can NEVER move capital above 10%" in text
    assert "drawdown ≥ budget/2 drops one rung" in text
    assert "drawdown ≥ budget disarms to rung 0" in text


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

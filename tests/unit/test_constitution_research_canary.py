from decimal import Decimal
from pathlib import Path

from auto_invest.portfolio.capital_ladder import MAX_RUNG, RUNG_FRACTIONS

ROOT = Path(__file__).resolve().parents[2]


def test_constitution_adds_10pct_without_weakening_higher_gates() -> None:
    text = (ROOT / ".specify" / "memory" / "constitution.md").read_text(encoding="utf-8")
    assert "**Version**: 9.0.0" in text
    assert "Legacy evidence without `gate_version=2.0` still requires exactly 64/64" in text
    assert "Current `gate_version=2.0` evidence requires at least 16" in text
    assert "`complete_family_trials`" in text
    assert "`prior_audit_complete`" in text
    assert "`global_audit_trials`" in text
    assert "`unique_audit_fingerprints`" in text
    assert "every blocking gate MUST pass" in text
    assert "variable family size does NOT lower any preregistered statistical" in text
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

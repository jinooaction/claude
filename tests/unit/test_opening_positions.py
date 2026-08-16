from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.performance.opening_positions import (
    OpeningPositionsError,
    load_opening_positions,
)

ROOT = Path(__file__).resolve().parents[2]


def test_deployed_live_opening_positions_match_verified_kis_snapshot() -> None:
    positions = load_opening_positions(ROOT / "deploy" / "live-opening-positions.toml")

    assert {(p.symbol, p.qty, p.avg_cost_usd) for p in positions} == {
        ("BHP", 1, Decimal("47.9700")),
        ("MRK", 3, Decimal("79.0900")),
        ("ORANY", 28, Decimal("11.1950")),
        ("RELX", 6, Decimal("54.1550")),
    }


def test_opening_positions_require_source_and_positive_cost(tmp_path: Path) -> None:
    path = tmp_path / "opening.toml"
    path.write_text(
        'observed_at_utc = "2026-06-12T08:54:00Z"\n'
        '[[positions]]\nsymbol = "BHP"\nqty = 1\navg_cost_usd = "0"\n',
        encoding="utf-8",
    )

    with pytest.raises(OpeningPositionsError):
        load_opening_positions(path)

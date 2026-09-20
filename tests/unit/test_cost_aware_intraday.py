from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from auto_invest.analytics.cost_aware_intraday import (
    candidate_registry,
    load_contract,
    select_development,
    validate_development,
)
from auto_invest.analytics.intraday_paper_challenger import IntradayDataset

CONTRACT = Path("specs/190-cost-aware-intraday/contracts/preregistration.json")
PRIOR = Path("specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json")


def _row(name: str, *, sharpe: float = 1, trades: int = 200) -> dict:
    metrics = {"net_return_pct": 1, "annualized_sharpe": sharpe,
               "max_drawdown_pct": 2, "turnover_usd": 100,
               "closed_trade_count": trades, "unclosed_quantity": 0}
    return {"candidate_id": name, "base": dict(metrics), "stress": dict(metrics)}


def test_frozen_contract_registry_and_tampering(tmp_path: Path) -> None:
    contract, prior = load_contract(CONTRACT, PRIOR)
    registry = candidate_registry(contract)
    assert len(registry) == len({row.strategy_fingerprint for row in registry}) == 6
    assert {(row.timeframe_minutes, row.parameters["breakout_buffer_bps"])
            for row in registry} == {(t, b) for t in (30, 60) for b in (62, 124, 186)}
    assert all(row.parameters["range_bars"] == 1 for row in registry)
    assert prior["cost_models"]["base"]["commission_bps_per_side"] == 25
    altered = tmp_path / "contract.json"
    altered.write_bytes(CONTRACT.read_bytes().replace(b"[62, 124, 186]", b"[1, 2, 3]"))
    with pytest.raises(ValueError, match="seal"):
        load_contract(altered, PRIOR)
    altered.write_bytes(PRIOR.read_bytes() + b" ")
    with pytest.raises(ValueError, match="prior contract"):
        load_contract(CONTRACT, altered)


@pytest.mark.parametrize("model,field,value", [
    ("base", "net_return_pct", 0), ("stress", "net_return_pct", -1),
    ("base", "closed_trade_count", 199), ("base", "unclosed_quantity", 1),
    ("stress", "unclosed_quantity", 1),
])
def test_selection_rejects_failed_development(model: str, field: str, value: int) -> None:
    row = _row("candidate")
    row[model][field] = value
    selected, reasons = select_development([row])
    assert selected is None
    assert reasons["candidate"]


def test_selection_rank_is_development_sharpe_then_drawdown_turnover_id() -> None:
    a, b = _row("a"), _row("b", sharpe=2)
    assert select_development([a, b])[0] == "b"
    b["base"]["annualized_sharpe"] = 1
    b["base"]["max_drawdown_pct"] = 1
    assert select_development([a, b])[0] == "b"
    a["base"]["max_drawdown_pct"] = 1
    b["base"]["turnover_usd"] = 99
    assert select_development([a, b])[0] == "b"
    a["base"]["turnover_usd"] = 99
    assert select_development([b, a])[0] == "a"
    for row in (a, b):
        row["confirmation"] = {"net_return_pct": 999 if row is b else -999}
    assert select_development([b, a])[0] == "a"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_metrics_are_not_selection_evidence(bad: float) -> None:
    row = _row("a")
    row["stress"]["net_return_pct"] = bad
    with pytest.raises(ValueError, match="non-finite"):
        select_development([row])


def test_development_rejects_synthetic_or_mismatched_fingerprint() -> None:
    contract, _ = load_contract(CONTRACT, PRIOR)
    fixture = IntradayDataset("fixture", "fixture", True, "sha256:other", {},
                              (date(2020, 3, 19),), ())
    with pytest.raises(ValueError, match="synthetic"):
        validate_development(fixture, contract)
    with pytest.raises(ValueError, match="interval"):
        validate_development(replace(fixture, synthetic=False), contract)

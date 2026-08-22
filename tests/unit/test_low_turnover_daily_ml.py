from __future__ import annotations

from auto_invest.analytics.daily_cross_asset_ml import (
    DailyMLConfig,
    Prediction,
    _ml_decisions,
)


def _group(index: int, *, preferred: str, advantage: float) -> list[Prediction]:
    from auto_invest.analytics.daily_cross_asset_ml import UNIVERSE

    return [
        Prediction(
            feature_index=index,
            date=f"2026-W{index:02d}",
            asset=symbol,
            realized_return=0.01 if symbol == preferred else 0.0,
            ridge_return=advantage if symbol == preferred else 0.0,
            boosting_return=advantage if symbol == preferred else 0.0,
            predicted_return=advantage if symbol == preferred else 0.0,
            uncertainty=0.0,
            trailing_volatility=0.1,
        )
        for symbol in UNIVERSE
    ]


def test_no_trade_threshold_and_minimum_hold_reduce_turnover() -> None:
    predictions = [
        *_group(1, preferred="SPY", advantage=0.10),
        *_group(2, preferred="QQQ", advantage=0.101),
        *_group(3, preferred="QQQ", advantage=0.102),
        *_group(4, preferred="QQQ", advantage=0.20),
    ]
    base = _ml_decisions(
        predictions,
        DailyMLConfig(minimum_hold_weeks=0, trade_threshold=0.0, estimated_trade_cost_bps=0),
    )
    low = _ml_decisions(
        predictions,
        DailyMLConfig(minimum_hold_weeks=3, trade_threshold=0.08, estimated_trade_cost_bps=25),
    )

    assert sum(row.turnover for row in low) <= sum(row.turnover for row in base)
    assert sum(row.suppressed_trades for row in low) > 0
    assert low[1].weights["SPY"] == low[0].weights["SPY"]

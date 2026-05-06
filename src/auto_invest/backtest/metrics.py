"""Backtest performance metrics (T026, FR-B-008).

All inputs are deterministic Decimal sequences so re-running with the
same equity curve produces byte-identical metric outputs.

Metrics computed:
  * total_return_pct
  * cagr_pct
  * volatility_pct (annualised stdev of log returns)
  * sharpe (rf=0)
  * sortino (downside-only stdev)
  * max_drawdown_pct
  * hit_rate
  * avg_win_loss_ratio
  * exposure_pct
  * turnover_pct (annualised notional turnover / starting capital)
  * gross_transaction_cost_usd
  * trade_count

The annualisation factor defaults to 252 (US-equity sessions). The
caller supplies `bars_per_year` so crypto (365) or 1m bars
(252 * 6.5 * 60) work correctly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Sequence

from auto_invest.backtest.portfolio import TradeRecord


@dataclass(frozen=True)
class BacktestMetrics:
    total_return_pct: Decimal
    cagr_pct: Decimal
    volatility_pct: Decimal
    sharpe: Decimal
    sortino: Decimal
    max_drawdown_pct: Decimal
    hit_rate: Decimal
    avg_win_loss_ratio: Decimal
    exposure_pct: Decimal
    turnover_pct: Decimal
    gross_transaction_cost_usd: Decimal
    trade_count: int

    def to_dict(self) -> dict[str, str | int]:
        return {
            "total_return_pct": str(self.total_return_pct),
            "cagr_pct": str(self.cagr_pct),
            "volatility_pct": str(self.volatility_pct),
            "sharpe": str(self.sharpe),
            "sortino": str(self.sortino),
            "max_drawdown_pct": str(self.max_drawdown_pct),
            "hit_rate": str(self.hit_rate),
            "avg_win_loss_ratio": str(self.avg_win_loss_ratio),
            "exposure_pct": str(self.exposure_pct),
            "turnover_pct": str(self.turnover_pct),
            "gross_transaction_cost_usd": str(self.gross_transaction_cost_usd),
            "trade_count": self.trade_count,
        }


def _q(value: Decimal, places: str = "0.0001") -> Decimal:
    """Quantise to a stable decimal precision so byte-equality holds."""
    if value.is_nan() or not value.is_finite():
        return Decimal("0")
    return value.quantize(Decimal(places))


def compute_metrics(
    *,
    equity_curve: Sequence[Decimal],
    starting_capital: Decimal,
    trades: Iterable[TradeRecord],
    notional_traded_usd: Decimal,
    gross_cost_usd: Decimal,
    days_invested: int,
    days_total: int,
    bars_per_year: int = 252,
) -> BacktestMetrics:
    if not equity_curve or starting_capital <= 0:
        return BacktestMetrics(
            total_return_pct=Decimal("0"),
            cagr_pct=Decimal("0"),
            volatility_pct=Decimal("0"),
            sharpe=Decimal("0"),
            sortino=Decimal("0"),
            max_drawdown_pct=Decimal("0"),
            hit_rate=Decimal("0"),
            avg_win_loss_ratio=Decimal("0"),
            exposure_pct=Decimal("0"),
            turnover_pct=Decimal("0"),
            gross_transaction_cost_usd=_q(gross_cost_usd, "0.01"),
            trade_count=0,
        )

    final = equity_curve[-1]
    total_return = (final - starting_capital) / starting_capital * Decimal(100)

    n = len(equity_curve)
    # Periodic returns (use simple % returns for stability).
    rets: list[Decimal] = []
    for prev, curr in zip(equity_curve, equity_curve[1:]):
        if prev <= 0:
            rets.append(Decimal("0"))
        else:
            rets.append((curr - prev) / prev)

    # Mean / std (sample) of periodic returns.
    if rets:
        mean = sum(rets, Decimal("0")) / Decimal(len(rets))
        var = sum(((r - mean) ** 2 for r in rets), Decimal("0")) / Decimal(max(1, len(rets) - 1))
        std = Decimal(math.sqrt(float(var))) if var > 0 else Decimal("0")
        downside = [r - mean for r in rets if r < mean]
        if downside:
            d_var = sum((d ** 2 for d in downside), Decimal("0")) / Decimal(len(downside))
            d_std = Decimal(math.sqrt(float(d_var)))
        else:
            d_std = Decimal("0")
    else:
        mean = std = d_std = Decimal("0")

    ann_factor = Decimal(math.sqrt(bars_per_year))
    sharpe = (mean / std * ann_factor) if std > 0 else Decimal("0")
    sortino = (mean / d_std * ann_factor) if d_std > 0 else Decimal("0")
    volatility_pct = std * ann_factor * Decimal(100)

    cagr_pct = Decimal("0")
    if days_total > 0 and final > 0:
        years = Decimal(days_total) / Decimal(365)
        if years > 0 and starting_capital > 0:
            ratio = float(final / starting_capital)
            if ratio > 0:
                cagr_pct = Decimal(ratio ** (1 / float(years)) - 1) * Decimal(100)

    # Max drawdown
    peak = equity_curve[0]
    max_dd = Decimal("0")
    for v in equity_curve:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd
    max_dd_pct = max_dd * Decimal(100)

    trades_list = list(trades)
    trade_count = len(trades_list)
    wins = [t.realised_pnl_usd for t in trades_list if t.realised_pnl_usd > 0]
    losses = [t.realised_pnl_usd for t in trades_list if t.realised_pnl_usd < 0]
    hit_rate = (Decimal(len(wins)) / Decimal(trade_count)) if trade_count > 0 else Decimal("0")
    avg_win = (sum(wins, Decimal("0")) / Decimal(len(wins))) if wins else Decimal("0")
    avg_loss = (sum(losses, Decimal("0")) / Decimal(len(losses))) if losses else Decimal("0")
    avg_win_loss_ratio = (avg_win / abs(avg_loss)) if avg_loss != 0 else Decimal("0")

    exposure_pct = (Decimal(days_invested) / Decimal(days_total) * Decimal(100)) if days_total > 0 else Decimal("0")
    years = Decimal(days_total) / Decimal(365) if days_total > 0 else Decimal(0)
    turnover_pct = (notional_traded_usd / starting_capital / years * Decimal(100)) if (years > 0 and starting_capital > 0) else Decimal("0")

    return BacktestMetrics(
        total_return_pct=_q(total_return),
        cagr_pct=_q(cagr_pct),
        volatility_pct=_q(volatility_pct),
        sharpe=_q(sharpe),
        sortino=_q(sortino),
        max_drawdown_pct=_q(max_dd_pct),
        hit_rate=_q(hit_rate),
        avg_win_loss_ratio=_q(avg_win_loss_ratio),
        exposure_pct=_q(exposure_pct),
        turnover_pct=_q(turnover_pct),
        gross_transaction_cost_usd=_q(gross_cost_usd, "0.01"),
        trade_count=trade_count,
    )

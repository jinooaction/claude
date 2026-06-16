"""스펙 055 ④ 게이트 — 포트폴리오 챔피언 하드닝 캐너리 단위 테스트.

검증: 정상 윈도우 낙폭이 밴드 안이면 PASS, 밴드 밖이면 FAIL(낙폭 지표); 데이터 결손이면
감사 무결성 FAIL; 합성 충격(과거 급락 윈도우)은 데이터 있으면 리플레이·없으면 graceful skip;
퍼즈 경로(K1 게이트 속성)는 전략 무관으로 0 반례 → PASS. all-or-nothing(하나라도 밖이면 FAIL).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.backtest.data_model import OHLCVBar
from auto_invest.backtest.data_source import trading_days_between
from auto_invest.canary.portfolio_harness import (
    DEFAULT_TIER,
    PortfolioCanaryInputs,
    run_portfolio_canary,
)
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType
from auto_invest.config.rules import PortfolioRebalanceConfig
from auto_invest.config.whitelist import Whitelist
from auto_invest.persistence import db

_REPO = Path(__file__).resolve().parents[2]
_BANDS = _REPO / "config" / "canary_bands_reassign.toml"


@dataclass
class _FakeDataSource:
    """coverage_holes 가 *실제 데이터 유무*로 결정 — 메인 윈도우는 덮이고 과거 충격은 빈다."""

    bars: dict[str, list[OHLCVBar]]

    @property
    def dataset_version(self) -> str:
        return "test"

    def list_symbols(self) -> list[str]:
        return sorted(self.bars)

    def session_dates(self, symbol: str) -> list[date]:
        return [b.session_date for b in self.bars.get(symbol, [])]

    def coverage_holes(self, symbols, date_start, date_end):  # noqa: ANN001
        out = []
        for s in symbols:
            has = any(
                date_start <= b.session_date <= date_end for b in self.bars.get(s, [])
            )
            if not has:
                out.append((s, date_start))
        return out

    def read_bars(self, symbol: str, date_start: date, date_end: date) -> list[OHLCVBar]:
        return [
            b for b in self.bars.get(symbol, []) if date_start <= b.session_date <= date_end
        ]


def _bars(symbol: str, days: list[date], price_of) -> list[OHLCVBar]:
    out = []
    for i, d in enumerate(days):
        c = Decimal(str(price_of(i)))
        out.append(
            OHLCVBar(
                symbol=symbol,
                session_date=d,
                open=c,
                high=(c * Decimal("1.01")).quantize(Decimal("0.0001")),
                low=(c * Decimal("0.99")).quantize(Decimal("0.0001")),
                close=c,
                volume=10_000_000,
                session_schedule_tag="regular",
            )
        )
    return out


def _caps() -> SizingCaps:
    return SizingCaps(
        per_trade_pct=Decimal("60"),
        per_symbol_pct=Decimal("65"),
        global_exposure_pct=Decimal("100"),
        canary_capital_pct=Decimal("1"),
        canary_min_duration_days=5,
        canary_acceptance_drawdown_pct=Decimal("80"),
    )


def _whitelist(symbols) -> Whitelist:
    return Whitelist(
        symbols=frozenset(symbols),
        accounts=frozenset({"BACKTEST"}),
        order_types=frozenset({OrderType.MARKET}),
    )


def _config(universe=("SPY", "IEF")) -> PortfolioRebalanceConfig:
    return PortfolioRebalanceConfig.model_validate(
        {
            "id": "canary-test",
            "universe": list(universe),
            "weights": {"momentum": "1.0"},
            "weight_scheme": "equal",
            "top_n": len(universe),
            "rebalance_mode": "hold_replace",
            "invested_fraction": "0.99",
            "rebalance_every_n_sessions": 5,
            "lookback_bars": 30,
            "momentum_period": 10,
        }
    )


@pytest.fixture
def conn(tmp_path: Path):
    c = db.get_connection(tmp_path / "audit.db")
    db.migrate(c)
    yield c
    c.close()


_DAYS = trading_days_between(date(2023, 1, 1), date(2023, 5, 1))[:60]


def _inputs(bars: dict, *, universe=("SPY", "IEF"), shocks_toml=None) -> PortfolioCanaryInputs:
    return PortfolioCanaryInputs(
        config=_config(universe),
        caps=_caps(),
        whitelist=_whitelist(universe),
        data_source=_FakeDataSource(bars=bars),
        date_start=_DAYS[0],
        date_end=_DAYS[-1],
        halt_path=Path("/nonexistent/HALT"),
        total_capital_usd=Decimal("100000"),
        shocks_toml=shocks_toml,
    )


def test_calm_window_passes(conn) -> None:
    # 완만히 상승 → 낙폭 ~0, 위반 0, 무결성 0 → PASS.
    bars = {
        "SPY": _bars("SPY", _DAYS, lambda i: 400 + i),
        "IEF": _bars("IEF", _DAYS, lambda i: 95 + i * Decimal("0.1")),
    }
    out = run_portfolio_canary(
        _inputs(bars), audit_conn=conn, bands_path=_BANDS, skip_fuzz=True, skip_shock=True
    )
    assert out.outcome == "passed"
    assert out.verdict == "PASS"
    assert out.candidate_drawdown_pct <= 10.0
    assert out.audit_integrity_count == 0
    assert out.failing_metrics == []


def test_crash_window_fails_on_drawdown(conn) -> None:
    # 상승 후 급락(−35%) → 낙폭 > 강등선(10%) → FAIL.
    def crash(i: int):
        return 400 + i * 2 if i < 30 else 460 - (i - 30) * 12

    bars = {
        "SPY": _bars("SPY", _DAYS, crash),
        "IEF": _bars("IEF", _DAYS, crash),
    }
    out = run_portfolio_canary(
        _inputs(bars), audit_conn=conn, bands_path=_BANDS, skip_fuzz=True, skip_shock=True
    )
    assert out.outcome == "failed"
    assert out.verdict == "FAIL"
    assert "pnl_drawdown_pct" in out.failing_metrics
    assert out.candidate_drawdown_pct > 10.0


def test_coverage_hole_fails_on_audit_integrity(conn) -> None:
    # 한 심볼의 바가 아예 없음 → 메인 윈도우 결손 → 감사 무결성 FAIL.
    bars = {
        "SPY": _bars("SPY", _DAYS, lambda i: 400 + i),
        "IEF": [],  # 데이터 결손
    }
    out = run_portfolio_canary(
        _inputs(bars), audit_conn=conn, bands_path=_BANDS, skip_fuzz=True, skip_shock=True
    )
    assert out.outcome == "failed"
    assert out.audit_integrity_count >= 1
    assert "audit_integrity_failures" in out.failing_metrics


def test_default_shocks_skipped_when_history_absent(conn) -> None:
    # 기본 합성 충격(2008·2020 등)은 테스트 데이터(2023)에 없음 → 전부 skip, 위반 0 → PASS.
    bars = {
        "SPY": _bars("SPY", _DAYS, lambda i: 400 + i),
        "IEF": _bars("IEF", _DAYS, lambda i: 95 + i * Decimal("0.1")),
    }
    out = run_portfolio_canary(
        _inputs(bars), audit_conn=conn, bands_path=_BANDS, skip_fuzz=True, skip_shock=False
    )
    assert out.outcome == "passed"
    assert out.shock_violations == 0
    # 과거 급락일(2008·2020 등 static)은 2023 테스트 데이터에 없어 스킵된다.
    assert out.skipped_shock_dates
    # 단, 동적 충격(분기 옵션만기)은 윈도우 안(2023-03)으로 해석돼 실제 리플레이될 수 있다 —
    # graceful skip 은 *데이터 없는* 과거 충격에만 적용된다는 핵심 동작을 확인.


def test_shock_runs_when_history_present(conn, tmp_path: Path) -> None:
    # 테스트 윈도우 안의 날짜를 충격일로 주면 충격 패스가 실제로 리플레이된다.
    shock_date = _DAYS[45]
    shocks_toml = tmp_path / "shocks.toml"
    shocks_toml.write_text(
        f'[[shocks]]\nname = "test-crash"\nsession_date = "{shock_date.isoformat()}"\n',
        encoding="utf-8",
    )
    bars = {
        "SPY": _bars("SPY", _DAYS, lambda i: 400 + i),
        "IEF": _bars("IEF", _DAYS, lambda i: 95 + i * Decimal("0.1")),
    }
    out = run_portfolio_canary(
        _inputs(bars, shocks_toml=shocks_toml),
        audit_conn=conn,
        bands_path=_BANDS,
        skip_fuzz=True,
        skip_shock=False,
    )
    assert shock_date in out.resolved_shock_dates
    assert out.skipped_shock_dates == []
    # 잘 사이징된 2자산 등가중은 충격 윈도우에서도 K1 위반 0 → PASS.
    assert out.outcome == "passed"
    assert out.shock_violations == 0


def test_fuzz_path_runs_clean(conn) -> None:
    # 퍼즈(K1 게이트 속성)는 전략 무관 — 게이트가 건전하므로 반례 0 → PASS. 작은 반복으로 빠르게.
    bars = {
        "SPY": _bars("SPY", _DAYS, lambda i: 400 + i),
        "IEF": _bars("IEF", _DAYS, lambda i: 95 + i * Decimal("0.1")),
    }
    out = run_portfolio_canary(
        _inputs(bars),
        audit_conn=conn,
        bands_path=_BANDS,
        skip_fuzz=False,
        hypothesis_iterations=25,
        hypothesis_seed=7,
        skip_shock=True,
    )
    assert out.fuzz_counterexamples == 0
    assert out.outcome == "passed"


def test_unknown_tier_rejected(conn) -> None:
    bars = {"SPY": _bars("SPY", _DAYS, lambda i: 400 + i), "IEF": _bars("IEF", _DAYS, lambda i: 95)}
    with pytest.raises(ValueError, match="tier"):
        run_portfolio_canary(
            _inputs(bars),
            audit_conn=conn,
            bands_path=_BANDS,
            tier="L9",
            skip_fuzz=True,
            skip_shock=True,
        )


def test_outcome_json_shape(conn) -> None:
    bars = {
        "SPY": _bars("SPY", _DAYS, lambda i: 400 + i),
        "IEF": _bars("IEF", _DAYS, lambda i: 95 + i * Decimal("0.1")),
    }
    out = run_portfolio_canary(
        _inputs(bars), audit_conn=conn, bands_path=_BANDS, skip_fuzz=True, skip_shock=True
    )
    j = out.to_json_dict()
    assert j["verdict"] == "PASS"
    assert j["tier"] == DEFAULT_TIER
    assert "candidate_drawdown_pct" in j
    assert "shock_violations" in j
    assert isinstance(j["failing_metrics"], list)

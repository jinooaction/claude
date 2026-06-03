"""Spec 035 — forward 엣지 판정 폐회로 통합 테스트.

생산자(`nav-snapshot --snapshot`)가 PORTFOLIO_NAV_SNAPSHOT 을 audit_log 에 쓰고,
소비자(`forward-verdict`)가 그 시계열 + price_bars 벤치마크를 읽어 판정을 내는
엔드투엔드 경로를 검증한다. 돈 0 이동(PAPER·측정 전용).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from typer.testing import CliRunner

from auto_invest.cli import app
from auto_invest.market_data.store import PriceBar, insert_bar
from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import (
    OrderPaperFilledPayload,
    PortfolioNavSnapshotPayload,
)

runner = CliRunner()


def _iso(d: date) -> str:
    return f"{d.isoformat()}T00:00:00.000Z"


def _compound(start: Decimal, mean: str, amp: str, n: int) -> list[Decimal]:
    """평균 mean·±amp 진동 수익률을 복리로 적용한 n점 곡선(결정론·분산>0)."""
    m, a = Decimal(mean), Decimal(amp)
    curve = [start]
    for i in range(n - 1):
        r = m + (a if i % 2 == 0 else -a)
        curve.append(curve[-1] * (Decimal("1") + r))
    return curve


def _seed_nav_series(
    conn, *, n: int, start: Decimal, mean: str = "0.0", amp: str = "0.005"
) -> None:
    """상승(또는 평평) NAV 스냅샷 n개(paper) — 진동 수익률 복리."""
    d0 = date(2026, 1, 1)
    curve = _compound(start, mean, amp, n)
    for i, nav in enumerate(curve):
        audit.append(
            conn,
            PortfolioNavSnapshotPayload(
                mode="paper",
                schema_version="1.0",
                source="ledger",
                computed_at_utc=_iso(d0 + timedelta(days=i)),
                cash_usd="0",
                total_market_value_usd=str(nav),
                total_nav_usd=str(nav),
                total_unrealized_pnl_usd="0",
                holdings_count=1,
            ),
        )


def _seed_bars(
    conn, *, symbol: str, n: int, start: Decimal, mean: str, amp: str
) -> None:
    d0 = date(2026, 1, 1)
    curve = _compound(start, mean, amp, n)
    for i, px in enumerate(curve):
        insert_bar(
            conn,
            PriceBar(
                symbol=symbol,
                timeframe="1d",
                bar_open_utc=_iso(d0 + timedelta(days=i)),
                open_usd=px,
                high_usd=px,
                low_usd=px,
                close_usd=px,
                volume=1000,
            ),
        )


def _write_portfolio(tmp_path: Path) -> Path:
    p = tmp_path / "port.toml"
    p.write_text(
        """
[caps]
per_trade_pct                  = 60.0
per_symbol_pct                 = 60.0
global_exposure_pct            = 100.0
canary_capital_pct             = 5.0
canary_min_duration_days       = 10
canary_acceptance_drawdown_pct = 30.0

[whitelist]
symbols     = ["AAA", "BBB"]
accounts    = ["BACKTEST"]
order_types = ["MARKET", "LIMIT"]
sessions    = ["REGULAR"]

[portfolio]
id            = "test"
universe      = ["AAA", "BBB"]
weights       = { momentum = "1.0" }
weight_scheme = "equal"
top_n         = 2
""",
        encoding="utf-8",
    )
    return p


def test_nav_snapshot_producer_writes_row(tmp_path: Path) -> None:
    """생산자: 페이퍼 체결로 보유가 있으면 nav-snapshot --snapshot 이 NAV 행을 쓴다."""
    db_path = tmp_path / "auto_invest.db"
    conn = db.get_connection(db_path)
    db.migrate(conn)
    audit.append(
        conn,
        OrderPaperFilledPayload(
            rule_id="r1",
            symbol="AAA",
            side="BUY",
            qty=10,
            simulated_fill_price_usd="100.00",
            quote_source="last",
            correlation_id="c1",
            paper_session_id=1,
        ),
    )
    conn.close()

    result = runner.invoke(
        app,
        [
            "nav-snapshot",
            "--mode", "paper",
            "--db", str(db_path),
            "--no-marks",
            "--snapshot",
            "--format", "json",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    out = json.loads(result.stdout)
    # 평균단가 $100 × 10주 = $1,000 (시세 없음 → 평균단가 보수 평가).
    assert Decimal(out["total_nav_usd"]) == Decimal("1000")

    # audit_log 에 PORTFOLIO_NAV_SNAPSHOT 이 실제로 1건 기록됐는지 확인.
    conn = db.get_connection(db_path)
    rows = conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE event_type='PORTFOLIO_NAV_SNAPSHOT'"
    ).fetchone()
    conn.close()
    assert rows["c"] == 1


def test_forward_verdict_insufficient_data(tmp_path: Path) -> None:
    """소비자: 스냅샷이 적으면 INSUFFICIENT_DATA(보수적)."""
    db_path = tmp_path / "auto_invest.db"
    conn = db.get_connection(db_path)
    db.migrate(conn)
    _seed_nav_series(conn, n=5, start=Decimal("10000"), mean="0.005", amp="0.001")
    conn.close()

    result = runner.invoke(
        app,
        ["forward-verdict", "--mode", "paper", "--db", str(db_path), "--format", "json"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    out = json.loads(result.stdout)
    assert out["verdict"] == "INSUFFICIENT_DATA"
    assert out["snapshot_count"] == 5


def test_forward_verdict_end_to_end_with_benchmark(tmp_path: Path) -> None:
    """소비자: NAV 시계열 + 벤치마크 가격 바를 읽어 판정 JSON 을 낸다."""
    db_path = tmp_path / "auto_invest.db"
    conn = db.get_connection(db_path)
    db.migrate(conn)
    # 전략 NAV: 25점, 강한 우상향·작은 잡음 → 높은(유한) 샤프.
    _seed_nav_series(conn, n=25, start=Decimal("10000"), mean="0.006", amp="0.001")
    # 벤치마크 바: 약한 상승·큰 잡음 → 낮은 샤프(전략이 위험조정으로 이긴다).
    _seed_bars(conn, symbol="AAA", n=25, start=Decimal("100"), mean="0.001", amp="0.004")
    _seed_bars(conn, symbol="BBB", n=25, start=Decimal("50"), mean="0.001", amp="0.004")
    conn.close()

    port = _write_portfolio(tmp_path)
    result = runner.invoke(
        app,
        [
            "forward-verdict",
            "--mode", "paper",
            "--db", str(db_path),
            "--portfolio", str(port),
            "--format", "json",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    out = json.loads(result.stdout)
    assert out["snapshot_count"] == 25
    assert out["has_benchmark"] is True
    assert out["universe"] == ["AAA", "BBB"]
    # n_obs = 24 ≥ min_obs 20 → 판정이 났다(데이터 부족 아님).
    assert out["n_obs"] == 24
    # 전략이 위험조정으로 벤치마크를 이기고 PSR 합격 → 엣지 확인.
    assert out["verdict"] == "EDGE_CONFIRMED"
    assert Decimal(out["excess_return_pct"]) > 0


def test_forward_verdict_text_smoke(tmp_path: Path) -> None:
    db_path = tmp_path / "auto_invest.db"
    conn = db.get_connection(db_path)
    db.migrate(conn)
    _seed_nav_series(conn, n=25, start=Decimal("10000"), mean="0.006", amp="0.001")
    conn.close()
    result = runner.invoke(
        app, ["forward-verdict", "--mode", "paper", "--db", str(db_path)]
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "forward 엣지 판정" in result.stdout


def test_forward_verdict_missing_db_is_error(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["forward-verdict", "--db", str(tmp_path / "nope.db")]
    )
    assert result.exit_code == 1

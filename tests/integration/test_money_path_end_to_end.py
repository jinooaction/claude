"""세계 최고 수준 4단계 계획 ② — 돈 경로 끝-끝 통합 테스트 (실제 운영 설정).

이번 주의 버그들(얕은 백필 → 빈 비중·거래 0건, NAV 자금 흐름 오염, 검증=배치 지문
드리프트)은 전부 단위가 아니라 **조합**에서 터졌다 — 워크플로 + 설정 + DB 상태가
만나는 지점. 이 테스트는 실제 운영 산출물(deploy/canary-live-portfolio.toml,
deploy/global-trend-portfolio.toml, automation/rebalance-live.request)로 전체
사슬을 한 번에 돌린다:

  이력 시드(깊은 백필 등가) → 점수·역변동성·추세 앙상블 신호 → 목표 비중 →
  실제 K1 게이트 주문 라우팅(페이퍼) → 체결 → NAV 스냅샷(자본 베이시스) →
  forward 판정 → 자본 사다리 결정 → 센티넬 자본 권위.

여기가 초록이면 "무장됐는데 거래 0건" / "자금 흐름이 수익률로 오인" / "검증 안 한
전략에 자본 배치" 클래스가 구조적으로 재발하지 못한다. 돈 0 이동(페이퍼 라우터·
임시 DB·실주문 코드 경로 미호출).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.broker.models import Quote
from auto_invest.cli import _load_execution_settings, _load_portfolio_for_backtest, app
from auto_invest.execution.order_router import OrderRouter
from auto_invest.execution.rebalancer import execute_rebalance
from auto_invest.market_data.store import PriceBar, get_bars, insert_bar
from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import PortfolioNavSnapshotPayload
from auto_invest.portfolio.autoarm import strategy_fingerprint
from auto_invest.portfolio.capital_ladder import (
    ACTION_PROMOTE,
    ACTION_WAIT_EDGE,
    decide_ladder,
    parse_ladder_fields,
    render_ladder_sentinel,
    rung_capital_usd,
)

runner = CliRunner()

_REPO = Path(__file__).resolve().parents[2]
_LIVE_TOML = _REPO / "deploy" / "canary-live-portfolio.toml"
_VALIDATED_TOML = _REPO / "deploy" / "global-trend-fixed-portfolio.toml"
_SENTINEL = _REPO / "automation" / "rebalance-live.request"

ACCOUNT = "E2E-ACCT"
ACCOUNT_NAV = Decimal("12000")  # 실계좌 NAV 가정 — 탐색 단 1 = 20% = $2,400.
RUNG1_CAPITAL = Decimal("2400")

_D0 = datetime(2023, 1, 3, tzinfo=UTC)
# 전략의 가장 긴 신호 창(추세 앙상블 252) + 모멘텀 여유 — 깊은 백필(--min-bars 1000)
# 이 보장하는 상태의 최소 등가. test_workflow_backfill_depth 가 워크플로 쪽을 고정.
_DEEP_BARS = 300
_SHALLOW_BARS = 100  # 2026-06-10 실측 사고 상태(기본 한 페이지).


def _seed_uptrend(conn, symbol: str, start: str, *, n: int, amp: str) -> None:
    """완만한 상승 + 진동(변동성 > 0) 일봉 n개 — 추세 앙상블 전 창 위."""
    price = Decimal(start)
    mean, a = Decimal("0.0008"), Decimal(amp)
    for i in range(n):
        r = mean + (a if i % 2 == 0 else -a)
        price = (price * (Decimal("1") + r)).quantize(Decimal("0.0001"))
        insert_bar(
            conn,
            PriceBar(
                symbol=symbol,
                timeframe="1d",
                bar_open_utc=(_D0 + timedelta(days=i)).strftime(
                    "%Y-%m-%dT00:00:00.000Z"
                ),
                open_usd=price,
                high_usd=(price * Decimal("1.005")).quantize(Decimal("0.0001")),
                low_usd=(price * Decimal("0.995")).quantize(Decimal("0.0001")),
                close_usd=price,
                volume=50_000_000,
            ),
        )


def _quote_provider(conn, universe):
    last = {
        s: get_bars(conn, symbol=s, timeframe="1d")[-1].close_usd for s in universe
    }

    async def provider(symbol: str) -> Quote:
        p = last[symbol]
        return Quote(
            symbol=symbol,
            last_price_usd=p,
            bid_usd=(p * Decimal("0.999")).quantize(Decimal("0.01")),
            ask_usd=(p * Decimal("1.001")).quantize(Decimal("0.01")),
            quoted_at_utc=datetime(2026, 6, 1, tzinfo=UTC),
        )

    return provider


def _execution_quote_provider(conn, symbol_map):
    last = {
        execution: get_bars(conn, symbol=signal, timeframe="1d")[-1].close_usd
        for signal, execution in symbol_map.items()
    }

    async def provider(symbol: str) -> Quote:
        p = last[symbol]
        return Quote(
            symbol=symbol,
            last_price_usd=p,
            bid_usd=(p * Decimal("0.999")).quantize(Decimal("0.01")),
            ask_usd=(p * Decimal("1.001")).quantize(Decimal("0.01")),
            quoted_at_utc=datetime(2026, 6, 1, tzinfo=UTC),
        )

    return provider


def _paper_router(conn, tmp_path: Path, whitelist, caps) -> OrderRouter:
    inner = httpx.AsyncClient(base_url="http://test")
    client = ResilientClient(
        inner,
        rate_limiter=AsyncTokenBucket(rate_per_sec=100.0, capacity=10.0),
        breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0),
        max_retries=1,
    )
    return OrderRouter(
        conn=conn,
        broker=client,
        access_token="tok",
        app_key="app",
        app_secret="sec",
        account_no=ACCOUNT,
        whitelist=whitelist,
        caps=caps,
        halt_path=tmp_path / "halt.flag",
        market="NASD",
        paper_mode=True,
        paper_session_id=1,
    )


def _load_live_config():
    caps, whitelist, cfg = _load_portfolio_for_backtest(
        _LIVE_TOML, env={"KIS_ACCOUNT_NO": ACCOUNT}
    )
    return caps, whitelist, cfg


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "e2e.db"
    c = db.get_connection(p)
    db.migrate(c)
    c.close()
    return p


def _seed_universe(db_path: Path, cfg, *, n: int) -> None:
    starts = {"SPY": ("400", "0.004"), "IEF": ("90", "0.0005"), "GLD": ("180", "0.005")}
    conn = db.get_connection(db_path)
    try:
        for sym in cfg.universe:
            start, amp = starts.get(sym, ("100", "0.003"))
            _seed_uptrend(conn, sym, start, n=n, amp=amp)
    finally:
        conn.close()


def _seed_nav_series(db_path: Path, *, n: int, basis: str) -> None:
    """페이퍼 NAV 스냅샷 n개(같은 자본 베이시스, ≥27일에 걸쳐) — 판정·성장 입력."""
    conn = db.get_connection(db_path)
    try:
        d0 = date(2026, 1, 1)
        nav = Decimal(basis)
        for i in range(n):
            r = Decimal("0.0006") + (Decimal("0.002") if i % 2 == 0 else Decimal("-0.002"))
            nav = (nav * (Decimal("1") + r)).quantize(Decimal("0.0001"))
            audit.append(
                conn,
                PortfolioNavSnapshotPayload(
                    mode="paper",
                    schema_version="1.0",
                    source="ledger",
                    computed_at_utc=f"{(d0 + timedelta(days=int(i * 1.4))).isoformat()}"
                    "T22:30:00.000Z",
                    cash_usd="0",
                    total_market_value_usd=str(nav),
                    total_nav_usd=str(nav),
                    total_unrealized_pnl_usd="0",
                    broker_reported_nav_usd=None,
                    holdings_count=3,
                    total_qty_drift=0,
                    total_value_drift_usd="0",
                    capital_basis_usd=basis,
                ),
            )
    finally:
        conn.close()


# ---------------------------------------------------------------- 끝-끝 사슬


@pytest.mark.asyncio
async def test_full_money_path_with_real_live_config(db_path: Path, tmp_path: Path):
    """실제 라이브 설정으로 신호→주문→체결→NAV→판정→사다리 전 사슬이 이어진다."""
    caps, whitelist, cfg = _load_live_config()
    execution_symbol_map, lot_rounding = _load_execution_settings(_LIVE_TOML)

    # 0. 검증=배치 정합 — 실제 두 운영 설정의 전략 지문이 동일해야 사다리가 가동된다.
    _, _, validated_cfg = _load_portfolio_for_backtest(
        _VALIDATED_TOML, env={"KIS_ACCOUNT_NO": ACCOUNT}
    )
    assert strategy_fingerprint(cfg) == strategy_fingerprint(validated_cfg), (
        "deploy/canary-live-portfolio.toml 과 deploy/global-trend-fixed-portfolio.toml 의"
        " 전략 지문이 다르다 — 검증하지 않은 전략이 라이브로 가는 드리프트."
    )

    # 1. 깊은 이력(백필 등가) → 신호 계산 가능.
    _seed_universe(db_path, cfg, n=_DEEP_BARS)

    # 2. 신호 → 비중 → 실제 K1 게이트 페이퍼 라우팅 → 체결.
    conn = db.get_connection(db_path)
    try:
        out = await execute_rebalance(
            config=cfg,
            router=_paper_router(conn, tmp_path, whitelist, caps),
            conn=conn,
            quote_provider=_execution_quote_provider(conn, execution_symbol_map),
            total_capital_usd=RUNG1_CAPITAL,
            caps=caps,
            account_holdings={},
            purchasable_cash_usd=ACCOUNT_NAV,
            execution_symbol_map=execution_symbol_map,
            lot_rounding=lot_rounding,
        )
    finally:
        conn.close()

    # 상승 추세 → 세 자산 전부 비중 > 0 (2026-06-10 "빈 비중" 클래스의 회귀 방패).
    assert set(out.signal_target_weights) == set(cfg.universe), (
        f"신호 비중이 유니버스를 다 덮지 못함: {out.signal_target_weights!r} — 이력/신호"
        " 경로가 끊겼다(얕은 백필 클래스)."
    )
    assert set(out.target_weights) == set(execution_symbol_map.values())
    assert all(Decimal(str(w)) > 0 for w in out.target_weights.values())
    fills = [r for r in out.results if r.state == "PAPER_FILLED"]
    assert len(fills) >= 2, f"체결이 너무 적음: {[(r.symbol, r.state) for r in out.results]}"
    bad = [
        r
        for r in out.results
        if r.state not in ("PAPER_FILLED", "SKIPPED_PER_TRADE_CAP", "SKIPPED_THRESHOLD")
        and r.reason is not None
    ]
    assert not bad, f"게이트 거부 발생: {[(r.symbol, r.state, r.reason) for r in bad]}"

    # 3. NAV 스냅샷(자본 베이시스) — 자금 흐름 불변: 매수 직후 NAV == 자본 (PR #243 클래스).
    res = runner.invoke(
        app,
        [
            "nav-snapshot",
            "--mode",
            "paper",
            "--db",
            str(db_path),
            "--no-marks",
            "--snapshot",
            "--capital",
            str(RUNG1_CAPITAL),
            "--format",
            "json",
        ],
    )
    assert res.exit_code == 0, res.output
    snap = json.loads(res.output.strip().splitlines()[-1])
    assert Decimal(snap["total_nav_usd"]) == RUNG1_CAPITAL, (
        f"매수 직후 NAV {snap['total_nav_usd']} ≠ 자본 {RUNG1_CAPITAL} — 자금 흐름이"
        " 수익률로 오인되는 측정 오염."
    )

    # 4. 판정 가능한 시계열(같은 베이시스, ≥27일·≥20관측) → forward-verdict 가 통계를 낸다.
    _seed_nav_series(db_path, n=25, basis=str(RUNG1_CAPITAL))
    res = runner.invoke(
        app,
        [
            "forward-verdict",
            "--mode",
            "paper",
            "--portfolio",
            str(_LIVE_TOML),
            "--db",
            str(db_path),
            "--format",
            "json",
        ],
    )
    assert res.exit_code == 0, res.output
    verdict = json.loads(res.output.strip().splitlines()[-1])
    assert verdict["verdict"] != "INSUFFICIENT_DATA", verdict
    assert verdict["n_obs"] >= 20

    # 5. 단 진입 후 실적(growth --since) — 사다리의 증거 산출기.
    res = runner.invoke(
        app,
        [
            "growth",
            "--mode",
            "paper",
            "--db",
            str(db_path),
            "--since",
            "2026-01-01",
            "--format",
            "json",
        ],
    )
    assert res.exit_code == 0, res.output
    growth = json.loads(res.output.strip().splitlines()[-1])
    assert growth["snapshot_count"] >= 20
    assert growth["max_drawdown_pct"] is not None

    # 6. 자본 사다리 — 실제 센티넬·실제 설정으로 결정이 난다.
    sentinel_text = _SENTINEL.read_text(encoding="utf-8")
    edge_verdict = {"verdict": "EDGE_CONFIRMED", "n_obs": verdict["n_obs"]}
    d = decide_ladder(
        sentinel_text=sentinel_text,
        forward_verdict=edge_verdict,
        live_growth=growth,
        account_nav_usd=ACCOUNT_NAV,
        live_config=cfg,
        validated_config=validated_cfg,
        kill_switch_present=False,
        today=date(2026, 6, 12),
    )
    if d.current_rung == 0:
        assert d.action == ACTION_PROMOTE and d.target_rung == 2
        assert d.target_capital_usd == rung_capital_usd(2, ACCOUNT_NAV)
        # 7. 게이트가 쓸 새 센티넬이 자본 권위 불변식을 만족한다.
        rung, _entered, nav = parse_ladder_fields(d.new_sentinel_text)
        assert rung == 2 and nav == ACCOUNT_NAV
        assert d.target_capital_usd == rung_capital_usd(rung, nav)
    else:
        # 사다리가 이미 가동된 상태의 저장소에서도 결정은 항상 난다(액션 라벨 유효).
        assert d.action

    # 8. 같은 입력 → 같은 결정 (결정론 — 캐너리 재현성 원칙).
    d2 = decide_ladder(
        sentinel_text=sentinel_text,
        forward_verdict=edge_verdict,
        live_growth=growth,
        account_nav_usd=ACCOUNT_NAV,
        live_config=cfg,
        validated_config=validated_cfg,
        kill_switch_present=False,
        today=date(2026, 6, 12),
    )
    assert d.to_json_dict() == d2.to_json_dict()


@pytest.mark.asyncio
async def test_shallow_history_yields_cash_not_trades(db_path: Path, tmp_path: Path):
    """얕은 이력(한 페이지 ≈100봉)이면 빈 비중 = 현금 — 2026-06-10 사고의 문서화.

    이 동작 자체는 fail-safe 로 옳다(모르면 현금). 위험은 *라이브 백필이 얕게 남는
    것*이고, 그쪽은 test_workflow_backfill_depth 가 워크플로 텍스트 불변식으로 막는다.
    둘이 합쳐 "무장됐는데 영원히 거래 0건" 클래스를 구조적으로 차단한다.
    """
    caps, whitelist, cfg = _load_live_config()
    _seed_universe(db_path, cfg, n=_SHALLOW_BARS)

    conn = db.get_connection(db_path)
    try:
        out = await execute_rebalance(
            config=cfg,
            router=_paper_router(conn, tmp_path, whitelist, caps),
            conn=conn,
            quote_provider=_quote_provider(conn, cfg.universe),
            total_capital_usd=RUNG1_CAPITAL,
            caps=caps,
            dry_run=True,
        )
    finally:
        conn.close()

    assert out.target_weights == {}, (
        "얕은 이력에서 비중이 나왔다 — on_insufficient=cash 보호가 풀렸거나 신호"
        f" 창 요구가 바뀌었다: {out.target_weights!r}"
    )


def test_committed_sentinel_blocks_unvalidated_strategy(db_path: Path):
    """검증 안 한 전략(지문 불일치)에는 어떤 단에서도 자본을 배치하지 않는다."""
    caps, whitelist, cfg = _load_live_config()
    _, _, validated_cfg = _load_portfolio_for_backtest(
        _VALIDATED_TOML, env={"KIS_ACCOUNT_NO": ACCOUNT}
    )
    mutated = cfg.model_copy(update={"top_n": 2})
    d = decide_ladder(
        sentinel_text=render_ladder_sentinel(
            rung=0,
            capital_usd=0,
            account_nav_usd=ACCOUNT_NAV,
            rung_entered=date(2026, 6, 12),
            run_seq=1,
            dd_budget_pct=Decimal("20"),
            evidence="test rung-0 baseline",
        ),
        forward_verdict={"verdict": "EDGE_CONFIRMED", "n_obs": 99},
        live_growth=None,
        account_nav_usd=ACCOUNT_NAV,
        live_config=mutated,
        validated_config=validated_cfg,
        kill_switch_present=False,
        today=date(2026, 6, 12),
    )
    assert d.action == "BLOCKED"
    assert not d.sentinel_changes


def test_ladder_waits_until_forward_edge_confirmed():
    """현재 저장소 상태 그대로면(미확정 판정) 사다리는 WAIT_EDGE — 돈 0 이동."""
    _, _, cfg = _load_live_config()
    _, _, validated_cfg = _load_portfolio_for_backtest(
        _VALIDATED_TOML, env={"KIS_ACCOUNT_NO": ACCOUNT}
    )
    sentinel_text = _SENTINEL.read_text(encoding="utf-8")
    rung, _, _ = parse_ladder_fields(sentinel_text)
    if rung not in (None, 0):
        pytest.skip("사다리가 이미 가동됨 — 이 가드는 가동 전 상태 전용.")
    d = decide_ladder(
        sentinel_text=sentinel_text,
        forward_verdict={"verdict": "INSUFFICIENT_DATA", "n_obs": 3},
        live_growth=None,
        account_nav_usd=ACCOUNT_NAV,
        live_config=cfg,
        validated_config=validated_cfg,
        kill_switch_present=False,
        today=date(2026, 6, 12),
    )
    assert d.action == ACTION_WAIT_EDGE
    assert not d.sentinel_changes


def test_money_path_report_surfaces_downside_with_real_config():
    """돈 경로 보고서(운영자 대시보드)가 실제 사다리 결정(실제 설정·NAV)으로 방어선
    예산·엣지 신뢰도를 끝단까지 표면화하는지 — 회귀 보호. 돈 0 이동(순수 판정·보고).

    실제 EDGE_CONFIRMED + 검증=배치 지문 정합이면 사다리는 단0→단2 PROMOTE 를 내고,
    보고서는 탐색 자본(NAV 20%)의 다운사이드를 달러로(강등 10% / 정지 20%) 보여야 한다.
    """
    from auto_invest.analytics.money_path import assess_money_path

    _, _, cfg = _load_live_config()
    _, _, validated_cfg = _load_portfolio_for_backtest(
        _VALIDATED_TOML, env={"KIS_ACCOUNT_NO": ACCOUNT}
    )
    d = decide_ladder(
        sentinel_text=render_ladder_sentinel(
            rung=0,
            capital_usd=0,
            account_nav_usd=ACCOUNT_NAV,
            rung_entered=date(2026, 6, 12),
            run_seq=1,
            dd_budget_pct=Decimal("20"),
            evidence="test rung-0 baseline",
        ),
        forward_verdict={"verdict": "EDGE_CONFIRMED", "n_obs": 25},
        live_growth=None,
        account_nav_usd=ACCOUNT_NAV,
        live_config=cfg,
        validated_config=validated_cfg,
        kill_switch_present=False,
        today=date(2026, 6, 12),
    )
    assert d.action == ACTION_PROMOTE  # 단0 → 단2 (지문 정합 + EDGE_CONFIRMED)

    report = assess_money_path(
        ladder=d.to_json_dict(),
        forward_verdict={
            "verdict": "EDGE_CONFIRMED",
            "n_obs": 25,
            "min_obs_required": 20,
            "psr_vs_benchmark": "0.97",
            "dsr_threshold": "0.95",
        },
        now=datetime(2026, 6, 12, 8, tzinfo=UTC),
    )
    # 방어선 예산: 탐색 자본 = NAV($12,000) 20% = $2,400, 강등 -$240 / 정지 -$480.
    # (PROMOTE → DEPLOYED 단계: 엣지 신뢰도는 EDGE_CONFIRMED 단계 전용 — 아래 별도 테스트.)
    assert report.safety is not None
    assert report.safety.capital_usd == int(RUNG1_CAPITAL)  # 2400
    assert report.safety.loss_at_demote_usd == 240
    assert report.safety.loss_at_halt_usd == 480
    assert "$2400" in report.as_text()  # 다운사이드가 달러로 끝단까지 표면화됨


def test_money_path_edge_confidence_stage_real_config():
    """판정만 EDGE_CONFIRMED 이고 사다리가 아직 단0 보류(WAIT_EDGE 동치)면 보고서는
    EDGE_CONFIRMED 단계 — 엣지 신뢰도(PSR) 게이트가 뜬다(돈 직전 강도 표시)."""
    from auto_invest.analytics.money_path import (
        GATE_PASS,
        STAGE_EDGE_CONFIRMED,
        assess_money_path,
    )

    # 사다리는 WAIT_EDGE(아직 단0 보류) 로 두고 판정만 EDGE_CONFIRMED → EDGE_CONFIRMED 단계.
    ladder = {
        "action": "WAIT_EDGE",
        "current_rung": 0,
        "target_rung": 0,
        "account_nav_usd": str(ACCOUNT_NAV),
        "target_capital_usd": None,
        "live_dd_pct": "0",
        "live_obs": None,
    }
    report = assess_money_path(
        ladder=ladder,
        forward_verdict={
            "verdict": "EDGE_CONFIRMED",
            "n_obs": 25,
            "min_obs_required": 20,
            "psr_vs_benchmark": "0.97",
            "dsr_threshold": "0.95",
        },
        now=datetime(2026, 6, 12, 8, tzinfo=UTC),
    )
    assert report.stage == STAGE_EDGE_CONFIRMED
    names = {g.name: g.status for g in report.gates}
    assert names["엣지 신뢰도(PSR)"] == GATE_PASS
    assert "신뢰도 PSR 0.97" in report.headline

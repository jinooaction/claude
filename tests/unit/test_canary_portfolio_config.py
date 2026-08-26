"""스펙 036 후속 — forward 페이퍼 트랙 설정(deploy/canary-portfolio.toml)이 추세 필터를
켠 채 유효하게 로드되는지 회귀 검증.

이 파일은 PAPER 전용(rebalance-paper-forward.yml 이 --mode paper 로만 사용; 라이브는
canary-live-rules.toml 별도). 운영 설정의 오타·스키마 깨짐을 CI 에서 잡는다.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from auto_invest.cli import (
    _load_account_rebalance_settings,
    _load_execution_settings,
    _load_portfolio_for_backtest,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CANARY = _REPO_ROOT / "deploy" / "canary-portfolio.toml"
_CANARY_NOTREND = _REPO_ROOT / "deploy" / "canary-portfolio-notrend.toml"
_CANARY_LIVE = _REPO_ROOT / "deploy" / "canary-live-portfolio.toml"
_MICRO_GTAA_LIVE = _REPO_ROOT / "deploy" / "micro-gtaa-live-portfolio.toml"
_RMBETA = _REPO_ROOT / "deploy" / "risk-managed-beta-portfolio.toml"
_MULTIASSET = _REPO_ROOT / "deploy" / "multi-asset-trend-portfolio.toml"


def test_canary_portfolio_parses_and_has_absolute_momentum_gate():
    caps, wl, cfg = _load_portfolio_for_backtest(_CANARY, env={"KIS_ACCOUNT_NO": "ACC-TEST"})
    # 스펙 041 — 절대 기대수익 게이트(듀얼 모멘텀): 상대 순위 1위라도 자기 후행수익이
    # 바닥(min_return) 미달이면 현금. "기대 안 되면 투자 안 함."
    assert cfg.trend_filter is not None
    assert cfg.trend_filter.method == "absolute_momentum"
    # 스펙 041 — 깊은 백필(--min-bars 300)로 6개월(120일) 절대 모멘텀 게이트가 활성.
    assert cfg.trend_filter.lookback <= 252
    assert cfg.trend_filter.on_insufficient in ("hold", "cash")
    assert cfg.trend_filter.min_return_pct >= 0  # 기대수익 바닥(0 = 양수 모멘텀 요구)
    # 유니버스 대폭 확대(스펙 041 — 좁은 3~28종목 → 넓은 횡단면).
    assert len(cfg.universe) >= 50
    # 구성 유니버스 ⊆ 화이트리스트(헌법 II — 거래 집합 못 넓힘).
    assert set(cfg.universe) <= set(wl.symbols)


def test_canary_portfolio_universe_all_whitelisted():
    _caps, wl, cfg = _load_portfolio_for_backtest(_CANARY, env={"KIS_ACCOUNT_NO": "ACC-TEST"})
    for sym in cfg.universe:
        assert sym in wl.symbols, f"{sym} not in whitelist"


def test_live_portfolio_config_ensemble_canary_invariants():
    """스펙 049 — 라이브 캐너리가 *검증된 글로벌 분산 추세 앙상블*인지 안전 불변식.

    옛 3종목 top_n=1(SPY·MSFT·AAPL)은 운영자가 "세계 최고 수준 아님"으로 거부(2026-06-04).
    재지정된 라이브 캐너리는 검증된 3자산 GTAA 앙상블이어야 한다:
    ① 유니버스 ⊆ 화이트리스트 = SPY·IEF·GLD(검증한 앙상블과 동일 집합). ② 고정등가중.
    ③ top_n=3(셋 다 보유). ④ 다중 속도 추세 앙상블 ON(드로다운 방어).
    ⑤ 저회전(hold_replace). 라이브 거래 집합 변경은 운영자 게이트(헌법 II) — 무장 전엔 돈 0.
    """
    _caps, wl, cfg = _load_portfolio_for_backtest(_CANARY_LIVE, env={"KIS_ACCOUNT_NO": "ACC-TEST"})
    assert set(cfg.universe) == {"SPY", "IEF", "GLD"}
    assert set(wl.symbols) == {"SCHX", "SPTI", "IAUM"}
    assert cfg.weight_scheme == "equal"
    assert cfg.top_n == 3
    assert cfg.rebalance_mode == "hold_replace"
    # 다중 속도 추세 앙상블(드로다운 방어) 필수.
    assert cfg.trend_filter is not None
    assert cfg.trend_filter.method == "sma"
    assert cfg.trend_filter.on_insufficient == "cash"
    assert cfg.trend_filter.ensemble_windows == (63, 126, 189, 252)

    account_enabled, liquidation, cash_buffer = _load_account_rebalance_settings(_CANARY_LIVE)
    symbol_map, lot_rounding = _load_execution_settings(_CANARY_LIVE)
    assert account_enabled is True
    assert liquidation == frozenset()
    assert str(cash_buffer) == "0.01"
    assert symbol_map == {"SPY": "SCHX", "IEF": "SPTI", "GLD": "IAUM"}
    assert lot_rounding == "nearest"
    assert set(symbol_map) == set(cfg.universe)
    assert set(symbol_map.values()) == set(wl.symbols)


def test_live_canary_strategy_matches_validated_ensemble():
    """스펙 049 — 검증=무장 정합성: 라이브 캐너리 설정의 전략 지문이 forward 페이퍼에서
    검증 중인 앙상블(global-trend-fixed-portfolio.toml)과 *정확히 일치*해야 한다.

    이게 깨지면 자동 무장 게이트가 BLOCKED 로 무장을 거부한다(검증 안 한 전략 무장 금지).
    한쪽 설정만 바꾸고 다른 쪽을 안 바꾸는 드리프트를 CI 에서 잡는다(돈을 잃지 않게).
    """
    from auto_invest.portfolio.autoarm import strategy_fingerprint

    _c1, _w1, live = _load_portfolio_for_backtest(_CANARY_LIVE, env={"KIS_ACCOUNT_NO": "ACC-TEST"})
    validated_path = _REPO_ROOT / "deploy" / "global-trend-fixed-portfolio.toml"
    _c2, _w2, validated = _load_portfolio_for_backtest(
        validated_path, env={"KIS_ACCOUNT_NO": "ACC-TEST"}
    )
    assert strategy_fingerprint(live) == strategy_fingerprint(validated)
    assert live.min_notional_usd == validated.min_notional_usd == 20


def test_micro_gtaa_live_canary_invariants():
    """스펙 058 — 빠른 실거래용 마이크로 GTAA 캐너리는 별도 소액 경로여야 한다.

    기존 자본 사다리 검증 집합(SPY·IEF·GLD)을 덮지 않고, $1,000 정수주에서 세 다리를
    표현하기 위해 SPYM·IEF·GLDM 만 허용한다. 기본 위험은 설정과 워크플로 센티넬의
    $1,000 상한으로 묶인다.
    """
    caps, wl, cfg = _load_portfolio_for_backtest(
        _MICRO_GTAA_LIVE, env={"KIS_ACCOUNT_NO": "ACC-TEST"}
    )
    raw = tomllib.loads(_MICRO_GTAA_LIVE.read_text(encoding="utf-8"))
    account_rebalance = raw.get("account_rebalance", {})
    liquidation_symbols = set(account_rebalance.get("liquidation_symbols", []))

    assert set(cfg.universe) == {"SPYM", "IEF", "GLDM"}
    assert liquidation_symbols == {"BHP", "MRK", "ORANY", "RELX"}
    assert set(wl.symbols) == set(cfg.universe) | liquidation_symbols
    assert set(cfg.universe) <= set(wl.symbols)
    assert set(cfg.universe).isdisjoint(liquidation_symbols)
    assert account_rebalance.get("enabled") is True
    assert account_rebalance.get("cash_buffer_pct") == "0.01"
    assert cfg.weight_scheme == "equal"
    assert cfg.top_n == 3
    assert cfg.rebalance_mode == "hold_replace"
    assert cfg.trend_filter is not None
    assert cfg.trend_filter.method == "sma"
    assert cfg.trend_filter.on_insufficient == "cash"
    assert cfg.trend_filter.ensemble_windows == (63, 126, 189, 252)
    assert caps.per_trade_pct <= caps.per_symbol_pct <= caps.global_exposure_pct
    assert caps.daily_loss_limit_pct == 3
    assert caps.max_total_drawdown_pct == 5


def test_notrend_control_config_is_identical_minus_trend_filter():
    """스펙 037 A/B 토너먼트 대조군: 추세 필터만 빠지고 나머지는 ON 과 동일해야 한다.

    유니버스·가중치·top_n·재조정 주기가 달라지면 A/B 가 추세 필터의 효과를 격리하지
    못한다(교란변수). 두 설정이 trend_filter 외 모든 운용 파라미터가 같음을 못박는다.
    """
    _c1, _w1, on = _load_portfolio_for_backtest(_CANARY, env={"KIS_ACCOUNT_NO": "ACC-TEST"})
    _c2, _w2, off = _load_portfolio_for_backtest(
        _CANARY_NOTREND, env={"KIS_ACCOUNT_NO": "ACC-TEST"}
    )
    # 대조군은 추세 필터가 없다.
    assert on.trend_filter is not None
    assert off.trend_filter is None
    # trend_filter 를 뺀 나머지 운용 파라미터는 전부 동일(교란변수 없음).
    assert off.universe == on.universe
    assert off.weights == on.weights
    assert off.weight_scheme == on.weight_scheme
    assert off.top_n == on.top_n
    assert off.rebalance_mode == on.rebalance_mode
    assert off.invested_fraction == on.invested_fraction
    assert off.rebalance_every_n_sessions == on.rebalance_every_n_sessions
    assert off.lookback_bars == on.lookback_bars
    assert off.momentum_period == on.momentum_period


def test_multi_asset_trend_config_is_uncorrelated_two_asset_trend():
    """스펙 043 — 멀티에셋 분산 추세추종 forward 설정(ARM D) 불변식.

    핵심: ARM C(risk-managed-beta, SPY·QQQ=둘 다 주식)와 달리 *비상관 자산*(주식 SPY +
    채권 IEF)을 합친다 — 그게 분산 이득의 근거. 각 자산을 자기 추세 게이트(sma 200)로 보유/
    현금. PAPER 전용이라 절대 위험 0(라이브는 별도 운영자 게이트, 헌법 X.4).
    """
    _caps, wl, cfg = _load_portfolio_for_backtest(_MULTIASSET, env={"KIS_ACCOUNT_NO": "ACC-TEST"})
    # 비상관 2자산: 주식(SPY) + 채권(IEF). 둘 다 보유(top_n=2, 선택 아님).
    assert set(cfg.universe) == {"SPY", "IEF"}
    assert cfg.top_n == 2
    # 유니버스 ⊆ 화이트리스트(헌법 II — 거래 집합 무확대).
    assert set(cfg.universe) <= set(wl.symbols)
    # 분산 추세의 핵심 = 각 자산 추세 게이트(스펙 042/043 검증 파라미터: sma 200≈10개월).
    assert cfg.trend_filter is not None
    assert cfg.trend_filter.method == "sma"
    assert cfg.trend_filter.lookback == 200
    assert cfg.trend_filter.on_insufficient == "cash"  # "확인 못 하면 투자 안 함"
    # 저회전(검증된 비용 강건성).
    assert cfg.rebalance_mode == "hold_replace"
    # ARM C(risk-managed-beta)와의 차이를 못박는다: 둘 다 주식이 아니라 채권이 들어가야 한다.
    _c2, _w2, rm = _load_portfolio_for_backtest(_RMBETA, env={"KIS_ACCOUNT_NO": "ACC-TEST"})
    assert "IEF" in cfg.universe and "IEF" not in rm.universe  # 채권 = 분산의 원천

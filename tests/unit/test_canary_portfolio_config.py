"""스펙 036 후속 — forward 페이퍼 트랙 설정(deploy/canary-portfolio.toml)이 추세 필터를
켠 채 유효하게 로드되는지 회귀 검증.

이 파일은 PAPER 전용(rebalance-paper-forward.yml 이 --mode paper 로만 사용; 라이브는
canary-live-rules.toml 별도). 운영 설정의 오타·스키마 깨짐을 CI 에서 잡는다.
"""

from __future__ import annotations

from pathlib import Path

from auto_invest.cli import _load_portfolio_for_backtest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CANARY = _REPO_ROOT / "deploy" / "canary-portfolio.toml"
_CANARY_NOTREND = _REPO_ROOT / "deploy" / "canary-portfolio-notrend.toml"
_CANARY_LIVE = _REPO_ROOT / "deploy" / "canary-live-portfolio.toml"


def test_canary_portfolio_parses_and_has_absolute_momentum_gate():
    caps, wl, cfg = _load_portfolio_for_backtest(
        _CANARY, env={"KIS_ACCOUNT_NO": "ACC-TEST"}
    )
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
    _caps, wl, cfg = _load_portfolio_for_backtest(
        _CANARY, env={"KIS_ACCOUNT_NO": "ACC-TEST"}
    )
    for sym in cfg.universe:
        assert sym in wl.symbols, f"{sym} not in whitelist"


def test_live_portfolio_config_500_canary_invariants():
    """스펙 039 — $500 라이브 캐너리 무장본의 안전 불변식.

    ① 유니버스 ⊆ 화이트리스트 = 기존 실거래 종목(SPY·MSFT·AAPL)만 — 라이브 거래 집합
    무확대(헌법 II). ② 추세 필터 ON(드로다운 방어). ③ top_n=1 — $500 는 1종목 1주만
    들어감(주당 $316~540). ④ 저회전(hold_replace). 캡은 자본($500)에 맞춰 크지만 절대
    위험은 자본이 천장(워크플로가 capital>$1,000 무장 거부로 footgun 차단).
    """
    _caps, wl, cfg = _load_portfolio_for_backtest(
        _CANARY_LIVE, env={"KIS_ACCOUNT_NO": "ACC-TEST"}
    )
    # 라이브 거래 집합 무확대: 기존 실거래 캐너리(SPY·MSFT·AAPL)와 동일.
    assert set(cfg.universe) == {"SPY", "MSFT", "AAPL"}
    assert set(wl.symbols) == {"SPY", "MSFT", "AAPL"}
    assert set(cfg.universe) <= set(wl.symbols)
    # 드로다운 방어 필수.
    assert cfg.trend_filter is not None
    assert cfg.trend_filter.method == "sma"
    # $500 현실: 1종목만.
    assert cfg.top_n == 1
    # 저회전.
    assert cfg.rebalance_mode == "hold_replace"


def test_notrend_control_config_is_identical_minus_trend_filter():
    """스펙 037 A/B 토너먼트 대조군: 추세 필터만 빠지고 나머지는 ON 과 동일해야 한다.

    유니버스·가중치·top_n·재조정 주기가 달라지면 A/B 가 추세 필터의 효과를 격리하지
    못한다(교란변수). 두 설정이 trend_filter 외 모든 운용 파라미터가 같음을 못박는다.
    """
    _c1, _w1, on = _load_portfolio_for_backtest(
        _CANARY, env={"KIS_ACCOUNT_NO": "ACC-TEST"}
    )
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

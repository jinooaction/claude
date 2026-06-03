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


def test_canary_portfolio_parses_and_has_trend_filter():
    caps, wl, cfg = _load_portfolio_for_backtest(
        _CANARY, env={"KIS_ACCOUNT_NO": "ACC-TEST"}
    )
    # 추세 필터가 켜져 있고(스펙 036), 인스턴스 ~100 일봉에서 활성인 lookback 이어야 한다.
    assert cfg.trend_filter is not None
    assert cfg.trend_filter.method == "sma"
    assert cfg.trend_filter.lookback <= 100  # 가용 일봉보다 작아야 '데이터 부족' 무효화 회피
    assert cfg.trend_filter.on_insufficient in ("hold", "cash")
    # 구성 유니버스 ⊆ 화이트리스트(헌법 II — 거래 집합 못 넓힘).
    assert set(cfg.universe) <= set(wl.symbols)


def test_canary_portfolio_universe_all_whitelisted():
    _caps, wl, cfg = _load_portfolio_for_backtest(
        _CANARY, env={"KIS_ACCOUNT_NO": "ACC-TEST"}
    )
    for sym in cfg.universe:
        assert sym in wl.symbols, f"{sym} not in whitelist"

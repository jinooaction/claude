"""백필 깊이 회귀 — 전략 신호가 요구하는 일봉 이력을 워크플로가 실제로 채우는가 (2026-06-11).

배경: rebalance-live-canary.yml 의 backfill-bars 가 --min-bars 없이(기본 한 페이지
≈100봉) 호출되어, 전략이 요구하는 이력(추세 앙상블 최대 252봉·역변동성 200봉·
모멘텀 120봉)에 못 미쳤다. 점수·추세가 전부 계산 불가 → on_insufficient=cash →
드라이런/실거래 모두 target_weights={} (실측: 2026-06-10 run 27296075204 —
IEF·GLD fetched=100, 미리보기 빈 비중). 자동 무장 게이트(스펙 049)가 무장해도
영원히 현금만 들고 거래 0건이 되는 끊긴 고리 — fail-safe 방향이지만 수익 0.

이 테스트는 forward/라이브 캐너리 워크플로의 모든 backfill-bars 호출이 해당
포트폴리오 설정의 가장 긴 신호 창보다 깊은 --min-bars 를 넘기는 불변식을 CI 에서
못박는다. 워크플로는 셸 변수로 호출을 조립하므로 YAML 파싱 대신 텍스트 불변식을
검사한다(test_workflow_nav_capital_basis.py 와 동일 접근).
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FORWARD = _REPO_ROOT / ".github" / "workflows" / "rebalance-paper-forward.yml"
_LIVE = _REPO_ROOT / ".github" / "workflows" / "rebalance-live-canary.yml"

_LIVE_PORTFOLIO = _REPO_ROOT / "deploy" / "canary-live-portfolio.toml"
# forward 워크플로의 다섯 트랙 설정(halt 격리·자본 베이시스 테스트와 동일 목록).
_FORWARD_PORTFOLIOS = [
    _REPO_ROOT / "deploy" / "canary-portfolio.toml",
    _REPO_ROOT / "deploy" / "canary-portfolio-notrend.toml",
    _REPO_ROOT / "deploy" / "risk-managed-beta-portfolio.toml",
    _REPO_ROOT / "deploy" / "multi-asset-trend-portfolio.toml",
    _REPO_ROOT / "deploy" / "global-trend-portfolio.toml",
    _REPO_ROOT / "deploy" / "global-trend-fixed-portfolio.toml",
    _REPO_ROOT / "deploy" / "global-trend-wide-portfolio.toml",
]


def _required_bars(portfolio_path: Path) -> int:
    """설정의 가장 긴 신호 창 + 1 (변동성·모멘텀은 n+1 종가 필요 — 보수 버퍼)."""
    cfg = tomllib.loads(portfolio_path.read_text(encoding="utf-8"))
    port = cfg.get("portfolio", {})
    trend = port.get("trend_filter", {})
    windows = [
        int(port.get("lookback_bars", 0)),
        int(port.get("momentum_period", 0)),
        int(trend.get("lookback", 0)),
        *[int(w) for w in trend.get("ensemble_windows", [])],
    ]
    return max(windows) + 1


def _backfill_calls(path: Path) -> list[str]:
    # 셸 연속 줄(역슬래시-개행)을 한 줄로 합쳐 호출 단위로 파싱한다 —
    # 라이브 워크플로는 --min-bars 가 다음 줄에 온다.
    joined = re.sub(r"\\\s*\n\s*", " ", path.read_text(encoding="utf-8"))
    return [
        ln for ln in joined.splitlines() if "backfill-bars" in ln and "uv run" in ln
    ]


def _min_bars(call: str) -> int:
    m = re.search(r"--min-bars\s+(\d+)", call)
    return int(m.group(1)) if m else 0


def test_live_canary_backfill_depth_covers_strategy_lookbacks():
    calls = _backfill_calls(_LIVE)
    assert len(calls) == 1, (
        f"라이브 캐너리 backfill-bars 호출이 {len(calls)}개 — 준비 스텝 구조가 바뀜."
    )
    need = _required_bars(_LIVE_PORTFOLIO)
    got = _min_bars(calls[0])
    assert got >= need, (
        f"라이브 캐너리 백필 깊이 --min-bars {got} < 전략 요구 {need}봉"
        f" ({_LIVE_PORTFOLIO.name} 의 가장 긴 신호 창 + 1). 얕은 이력이면 점수·추세"
        " 계산 불가 → on_insufficient=cash → 무장돼도 거래 0건(수익 0)."
    )


def test_forward_backfills_keep_deep_history():
    calls = _backfill_calls(_FORWARD)
    assert len(calls) == len(_FORWARD_PORTFOLIOS), (
        f"forward backfill-bars 호출이 {len(calls)}개 — 트랙 수"
        f"({len(_FORWARD_PORTFOLIOS)})와 다름. 트랙을 추가/삭제했다면 이 테스트의"
        " 설정 목록도 함께 갱신할 것."
    )
    # 다섯 트랙 중 가장 깊은 요구치 — 호출→설정 매핑이 위치 기반이라 보수적으로
    # 모든 호출이 최대 요구치를 넘는지 본다(현행 1000 은 전부 충족).
    need = max(_required_bars(p) for p in _FORWARD_PORTFOLIOS)
    for call in calls:
        got = _min_bars(call)
        assert got >= need, (
            f"forward 백필 깊이 --min-bars {got} < 전략 요구 {need}봉 — 검증 트랙의"
            f" 신호가 이력 부족으로 무력화된다: {call}"
        )

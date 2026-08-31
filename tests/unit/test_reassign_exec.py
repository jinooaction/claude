"""스펙 055 — 자율 전략 진화: 재지정 *실행* 단위 테스트.

핵심 불변식:
  - 전략 블록([portfolio] ~)은 챔피언에서 그대로 이식, 운영/거래집합([caps]·[whitelist])은
    라이브 원본 보존(헌법 X.5: WHICH not HOW MUCH).
  - 챔피언 유니버스 ⊄ 라이브 화이트리스트면 재지정 거부(헌법 II 거래 집합 확대 = 운영자 게이트).
  - 재지정 직후 자본 사다리 rung 0(무장 해제)로 리셋(⑤).
  - REASSIGN 이 아닌 결정은 실행 산출물을 만들지 않는다(라이브 무변경).
"""

from __future__ import annotations

import tomllib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.portfolio.auto_reassign import (
    ACTION_HOLD,
    ACTION_REASSIGN,
    ReassignDecision,
)
from auto_invest.portfolio.reassign_exec import (
    LIVE_CONFIG_PATH,
    TRACK_DEPLOY_CONFIGS,
    ReassignExecError,
    build_live_config_text,
    build_reassignment,
    deploy_config_path,
)

_NOW = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)

# 라이브 설정 축소본 — 운영 블록(caps 의 per_trade_pct, whitelist)에 *식별 가능한* 값을 둬
# 보존 여부를 검증한다(챔피언과 다른 값이어야 보존을 증명할 수 있다).
_LIVE = """# 라이브 머리말 — 옛 전략(역변동성) 설명. 재지정 후 stale.
# 라이브 안전장치 ①~⑥ (재지정 후에도 유효한 운영 주석).
[caps]
per_trade_pct       = 50.0
per_symbol_pct      = 60.0
global_exposure_pct = 100.0

[whitelist]
symbols     = ["SPY", "IEF", "GLD"]
accounts    = ["${KIS_ACCOUNT_NO}"]
order_types = ["LIMIT"]
sessions    = ["REGULAR"]

[portfolio]
id            = "global-trend"
universe      = ["SPY", "IEF", "GLD"]
weight_scheme = "inverse_vol"
top_n         = 3

[portfolio.trend_filter]
method = "sma"
"""

# 챔피언(등가중) 축소본 — caps/whitelist 는 *다른* 값(99.0)을 둬, 결과에 챔피언 caps 가 새지
# 않고 라이브 것이 보존됨을 검증한다. 전략 블록은 weight_scheme=equal + ensemble_windows.
_CHALLENGER_FIXED = """# 챔피언 머리말 — 등가중 설명.
[caps]
per_trade_pct       = 99.0
per_symbol_pct      = 99.0
global_exposure_pct = 100.0

[whitelist]
symbols     = ["SPY", "IEF", "GLD", "QQQ"]
accounts    = ["${KIS_ACCOUNT_NO}"]
order_types = ["LIMIT"]

[portfolio]
id            = "global-trend-fixed"
universe      = ["SPY", "IEF", "GLD"]
weight_scheme = "equal"
top_n         = 3

[portfolio.trend_filter]
method           = "sma"
ensemble_windows = [63, 126, 189, 252]
"""

# 거래 집합 밖 종목(QQQ)을 거래하는 챔피언 — 자율 재지정 거부 대상(헌법 II).
_CHALLENGER_WIDE = """[caps]
per_trade_pct = 50.0

[whitelist]
symbols = ["SPY", "QQQ", "EFA"]

[portfolio]
id            = "wide"
universe      = ["SPY", "QQQ", "EFA"]
weight_scheme = "inverse_vol"
top_n         = 3
"""


def _reassign_decision(
    *, challenger_key: str = "globalfixed", incumbent_key: str | None = "global"
) -> ReassignDecision:
    return ReassignDecision(
        action=ACTION_REASSIGN,
        incumbent_key=incumbent_key,
        challenger_key=challenger_key,
        canary_verdict="PASS",
        reason="테스트용 5중 게이트 통과",
        gate_challenger=True,
        gate_multiplicity=True,
        gate_canary=True,
    )


# ---- 전략 이식 + 운영 블록 보존 -------------------------------------------------


def test_strategy_swapped_ops_preserved() -> None:
    text = build_live_config_text(
        live_text=_LIVE,
        challenger_text=_CHALLENGER_FIXED,
        challenger_key="globalfixed",
        incumbent_key="global",
        now=_NOW,
    )
    data = tomllib.loads(text)
    # 전략 블록은 챔피언에서 이식 — 등가중 + 앙상블 창.
    assert data["portfolio"]["weight_scheme"] == "equal"
    assert data["portfolio"]["id"] == "global-trend-fixed"
    assert data["portfolio"]["trend_filter"]["ensemble_windows"] == [63, 126, 189, 252]
    # 운영 블록은 라이브 원본 보존 — 챔피언의 99.0 이 아니라 라이브의 50.0/60.0.
    assert data["caps"]["per_trade_pct"] == 50.0
    assert data["caps"]["per_symbol_pct"] == 60.0
    # 거래 집합(화이트리스트)도 라이브 원본 — 챔피언이 QQQ 를 화이트리스트에 둬도 안 샌다.
    assert data["whitelist"]["symbols"] == ["SPY", "IEF", "GLD"]
    assert "QQQ" not in data["whitelist"]["symbols"]
    assert data["whitelist"]["sessions"] == ["REGULAR"]  # 라이브 전용 키 보존


def test_provenance_banner_present() -> None:
    text = build_live_config_text(
        live_text=_LIVE,
        challenger_text=_CHALLENGER_FIXED,
        challenger_key="globalfixed",
        incumbent_key="global",
        now=_NOW,
    )
    assert "자율 전략 재지정" in text
    assert "globalfixed" in text and "global" in text
    assert TRACK_DEPLOY_CONFIGS["globalfixed"] in text  # 이식 출처 명시
    assert "2026-06-16" in text  # 재지정 날짜
    # 배너가 맨 위(첫 비어있지 않은 줄이 자동 생성 경고).
    assert text.lstrip().startswith("# ⚠ 자동 생성됨")


# ---- 헌법 II 거래 집합 가드 ------------------------------------------------------


def test_universe_outside_whitelist_blocked() -> None:
    # 챔피언이 QQQ·EFA 를 거래하나 라이브 화이트리스트는 SPY·IEF·GLD — 거래 집합 확대 거부.
    with pytest.raises(ReassignExecError, match="화이트리스트|매핑 키 불일치"):
        build_live_config_text(
            live_text=_LIVE,
            challenger_text=_CHALLENGER_WIDE,
            challenger_key="wide",
            incumbent_key="global",
            now=_NOW,
        )


def test_subset_universe_allowed() -> None:
    # 챔피언이 라이브 거래 집합의 *부분집합*(SPY·IEF)만 거래 — 허용(축소는 안전).
    challenger_subset = """[caps]
per_trade_pct = 50.0
[whitelist]
symbols = ["SPY"]
[portfolio]
id = "multiasset"
universe = ["SPY", "IEF"]
weight_scheme = "inverse_vol"
top_n = 2
"""
    text = build_live_config_text(
        live_text=_LIVE,
        challenger_text=challenger_subset,
        challenger_key="multiasset",
        incumbent_key="global",
        now=_NOW,
    )
    data = tomllib.loads(text)
    assert data["portfolio"]["universe"] == ["SPY", "IEF"]
    assert data["whitelist"]["symbols"] == ["SPY", "IEF", "GLD"]  # 라이브 보존


# ---- 경계/입력 방어 -------------------------------------------------------------


def test_missing_portfolio_section_refused() -> None:
    no_strategy = "[caps]\nper_trade_pct = 50.0\n[whitelist]\nsymbols = [\"SPY\"]\n"
    with pytest.raises(ReassignExecError, match="portfolio"):
        build_live_config_text(
            live_text=no_strategy,
            challenger_text=_CHALLENGER_FIXED,
            challenger_key="globalfixed",
            incumbent_key="global",
            now=_NOW,
        )


def test_caps_after_portfolio_refused() -> None:
    # 보존 대상([caps])이 전략 블록 뒤에 있으면 보존 경계가 불명 — 거부.
    misordered = """[portfolio]
id = "x"
universe = ["SPY"]
[caps]
per_trade_pct = 50.0
[whitelist]
symbols = ["SPY"]
"""
    with pytest.raises(ReassignExecError, match=r"\[caps\]"):
        build_live_config_text(
            live_text=misordered,
            challenger_text=_CHALLENGER_FIXED,
            challenger_key="globalfixed",
            incumbent_key="global",
            now=_NOW,
        )


def test_deploy_config_path_unknown_key_refused() -> None:
    with pytest.raises(ReassignExecError, match="레지스트리"):
        deploy_config_path("nonexistent-track")


# ---- build_reassignment (결정 → 두 산출물) --------------------------------------


def test_build_reassignment_produces_both_artifacts() -> None:
    out = build_reassignment(
        decision=_reassign_decision(),
        live_text=_LIVE,
        challenger_text=_CHALLENGER_FIXED,
        account_nav_usd=Decimal("1000"),
        run_seq=42,
        dd_budget_pct=Decimal("20"),
        rung_entered=date(2026, 6, 16),
        now=_NOW,
    )
    assert out.challenger_key == "globalfixed"
    assert out.incumbent_key == "global"
    assert out.live_config_path == LIVE_CONFIG_PATH
    assert out.live_whitelist_symbols == ("SPY", "IEF", "GLD")
    assert out.challenger_universe == ("SPY", "IEF", "GLD")
    # 산출물 1: 새 라이브 설정(등가중 전략 이식).
    assert tomllib.loads(out.new_live_config_text)["portfolio"]["weight_scheme"] == "equal"
    assert "단1=10% 검증" in out.new_live_config_text
    assert "단2=20% 탐색" in out.new_live_config_text
    # 산출물 2: rung 0 센티넬(무장 해제 + 자본 0).
    s = out.rung0_sentinel_text
    assert "armed: false" in s
    assert "capital_usd: 0" in s
    assert "ladder_rung: 0" in s


def test_build_reassignment_json_dict() -> None:
    out = build_reassignment(
        decision=_reassign_decision(),
        live_text=_LIVE,
        challenger_text=_CHALLENGER_FIXED,
        account_nav_usd=Decimal("1000"),
        run_seq=1,
        dd_budget_pct=Decimal("20"),
        rung_entered=date(2026, 6, 16),
        now=_NOW,
    )
    j = out.to_json_dict()
    assert j["challenger_key"] == "globalfixed"
    assert j["incumbent_key"] == "global"
    assert j["live_whitelist_symbols"] == ["SPY", "IEF", "GLD"]
    assert j["challenger_universe"] == ["SPY", "IEF", "GLD"]


def test_non_reassign_decision_refused() -> None:
    hold = ReassignDecision(
        action=ACTION_HOLD,
        incumbent_key="global",
        challenger_key=None,
        canary_verdict=None,
        reason="도전자 없음",
        gate_challenger=False,
        gate_multiplicity=False,
        gate_canary=False,
    )
    with pytest.raises(ReassignExecError, match="REASSIGN 이 아님"):
        build_reassignment(
            decision=hold,
            live_text=_LIVE,
            challenger_text=_CHALLENGER_FIXED,
            account_nav_usd=Decimal("1000"),
            run_seq=1,
            dd_budget_pct=Decimal("20"),
            rung_entered=date(2026, 6, 16),
            now=_NOW,
        )


def test_challenger_equals_incumbent_refused() -> None:
    dec = _reassign_decision(challenger_key="global", incumbent_key="global")
    with pytest.raises(ReassignExecError, match="같음"):
        build_reassignment(
            decision=dec,
            live_text=_LIVE,
            challenger_text=_CHALLENGER_FIXED,
            account_nav_usd=Decimal("1000"),
            run_seq=1,
            dd_budget_pct=Decimal("20"),
            rung_entered=date(2026, 6, 16),
            now=_NOW,
        )


def test_unknown_challenger_key_refused() -> None:
    dec = _reassign_decision(challenger_key="totally-unknown", incumbent_key="global")
    with pytest.raises(ReassignExecError, match="레지스트리"):
        build_reassignment(
            decision=dec,
            live_text=_LIVE,
            challenger_text=_CHALLENGER_FIXED,
            account_nav_usd=Decimal("1000"),
            run_seq=1,
            dd_budget_pct=Decimal("20"),
            rung_entered=date(2026, 6, 16),
            now=_NOW,
        )


# ---- 실제 deploy 파일 정합성(파일 드리프트 감지) --------------------------------


def test_real_global_to_globalfixed_reassignment() -> None:
    """실제 라이브 설정 + globalfixed 후보로 재지정 — 진짜 파일이 함수 가정과 맞는지 검증.

    이 테스트가 깨지면 deploy 파일 구조가 바뀐 것(섹션 순서·이름) — 실행 함수도 갱신해야 한다.
    """
    repo = Path(__file__).resolve().parents[2]
    live_text = (repo / LIVE_CONFIG_PATH).read_text(encoding="utf-8")
    challenger_text = (
        repo / TRACK_DEPLOY_CONFIGS["globalfixed"]
    ).read_text(encoding="utf-8")

    out = build_reassignment(
        decision=_reassign_decision(challenger_key="globalfixed", incumbent_key="global"),
        live_text=live_text,
        challenger_text=challenger_text,
        account_nav_usd=Decimal("1000"),
        run_seq=7,
        dd_budget_pct=Decimal("20"),
        rung_entered=date(2026, 6, 16),
        now=_NOW,
    )
    data = tomllib.loads(out.new_live_config_text)
    # 등가중 전략이 라이브로 이식됐다.
    assert data["portfolio"]["weight_scheme"] == "equal"
    assert data["portfolio"]["id"] == "global-trend-fixed"
    # 신호 집합은 SPY·IEF·GLD, 실제 거래 집합은 저가 1:1 대체 ETF로 보존됐다.
    assert data["portfolio"]["universe"] == ["SPY", "IEF", "GLD"]
    assert data["execution"]["symbol_map"] == {
        "SPY": "SCHX",
        "IEF": "SPTI",
        "GLD": "IAUM",
    }
    assert data["whitelist"]["symbols"] == ["SCHX", "SPTI", "IAUM"]
    assert data["caps"]["canary_acceptance_drawdown_pct"] == 3.0
    # 체결 매핑 값 ⊆ 화이트리스트(가드 통과).
    assert set(data["execution"]["symbol_map"].values()) <= set(
        out.live_whitelist_symbols
    )


def test_real_wide_reassignment_blocked() -> None:
    """실제 wide(11슬리브) 후보로의 재지정은 거래 집합 확대라 거부돼야 한다(헌법 II)."""
    repo = Path(__file__).resolve().parents[2]
    live_text = (repo / LIVE_CONFIG_PATH).read_text(encoding="utf-8")
    wide_text = (repo / TRACK_DEPLOY_CONFIGS["wide"]).read_text(encoding="utf-8")

    with pytest.raises(ReassignExecError, match="화이트리스트|매핑 키 불일치"):
        build_reassignment(
            decision=_reassign_decision(challenger_key="wide", incumbent_key="global"),
            live_text=live_text,
            challenger_text=wide_text,
            account_nav_usd=Decimal("1000"),
            run_seq=7,
            dd_budget_pct=Decimal("20"),
            rung_entered=date(2026, 6, 16),
            now=_NOW,
        )

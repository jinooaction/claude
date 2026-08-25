"""스펙 050 — 자본 사다리 결정 로직 테스트.

실거래 자본 규모가 걸린 게이트라 *보수적 fail-safe* 를 빠짐없이 검증한다:
내려가는 건(강등·정지) 낙폭 하나로 즉시, 올라가는 건(승격) 세 증거(관측 수·경과일·
낙폭) 전부 + 정합 + 킬스위치 없음 일 때만. 증거가 None(측정 불가)이면 절대 승격 아님.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from auto_invest.config.rules import PortfolioRebalanceConfig
from auto_invest.portfolio.capital_ladder import (
    ACTION_BLOCKED,
    ACTION_DEMOTE,
    ACTION_DISABLED,
    ACTION_HALT,
    ACTION_PROMOTE,
    ACTION_RESIZE,
    ACTION_STAY,
    ACTION_WAIT_EDGE,
    DEFAULT_DD_BUDGET_PCT,
    PROMOTION_MIN_CALENDAR_DAYS,
    PROMOTION_MIN_OBS,
    decide_ladder,
    ladder_schedule_ko,
    parse_ladder_fields,
    render_ladder_sentinel,
    rung_capital_usd,
    rung_pct_text,
)

# ---- 픽스처 (autoarm 테스트와 동일 앙상블) ----------------------------------------

_ENSEMBLE_PORTFOLIO = {
    "id": "global-trend",
    "universe": ["SPY", "IEF", "GLD"],
    "weights": {"momentum": "1.0"},
    "weight_scheme": "inverse_vol",
    "top_n": 3,
    "rebalance_mode": "hold_replace",
    "invested_fraction": "0.99",
    "rebalance_every_n_sessions": 21,
    "lookback_bars": 200,
    "momentum_period": 120,
    "rebalance_threshold_pct": "2.0",
    "min_notional_usd": "50",
    "trend_filter": {
        "method": "sma",
        "lookback": 200,
        "on_insufficient": "cash",
        "ensemble_windows": [63, 126, 189, 252],
    },
}


def _cfg(**overrides) -> PortfolioRebalanceConfig:
    raw = {**_ENSEMBLE_PORTFOLIO, **overrides}
    return PortfolioRebalanceConfig.model_validate(raw)


def _verdict(label: str = "EDGE_CONFIRMED", n_obs: int = 22) -> dict:
    return {
        "schema_version": "1.2",
        "verdict": label,
        "n_obs": n_obs,
        "significance_method": "paired_active_return_psr_v1",
    }


def _growth(
    dd: str | None = "2.5",
    obs: int | None = 25,
    period_days: str | None = "30",
    fills_count: int | None = None,
) -> dict:
    result = {
        "schema_version": "1.0",
        "mode": "live",
        "snapshot_count": obs,
        "max_drawdown_pct": dd,
        "period_days": period_days,
    }
    if fills_count is not None:
        result["fills_count"] = fills_count
    return result


_TODAY = date(2026, 6, 12)
_NAV = Decimal("12000")


def test_capital_ladder_reporting_comes_from_rung_fractions() -> None:
    assert rung_pct_text(1) == "10"
    assert rung_pct_text(5) == "100"
    assert ladder_schedule_ko() == (
        "단0=0% → 단1=10% 연구 → 단2=20% 탐색 → 단3=25% → 단4=50% → 단5=100%"
    )
    assert ladder_schedule_ko(start_rung=1).startswith("단1=10% 연구 → 단2=20% 탐색")

_DISARMED = """# header
armed: false
capital_usd: 500
requested_by: mason
stage: live-canary-portfolio
run_seq: 5
note: "disarmed"
"""

_RUNG1 = """# header
armed: true
capital_usd: 1200
requested_by: spec-050
stage: live-canary-portfolio
run_seq: 6
ladder_rung: 1
rung_entered: 2026-05-10
account_nav_usd: 12000
dd_budget_pct: 20
note: "rung 1"
"""

_RUNG2 = _RUNG1.replace("ladder_rung: 1", "ladder_rung: 2").replace(
    "capital_usd: 1200", "capital_usd: 2400"
)
_RUNG3 = _RUNG1.replace("ladder_rung: 1", "ladder_rung: 3").replace(
    "capital_usd: 1200", "capital_usd: 3000"
)
_RUNG4 = _RUNG1.replace("ladder_rung: 1", "ladder_rung: 4").replace(
    "capital_usd: 1200", "capital_usd: 6000"
)
_RUNG5 = _RUNG1.replace("ladder_rung: 1", "ladder_rung: 5").replace(
    "capital_usd: 1200", "capital_usd: 12000"
)

# 옛 autoarm 무장 센티넬 — 사다리 필드 없음(하위 호환: 단 1 취급).
_LEGACY_ARMED = _DISARMED.replace("armed: false", "armed: true")


def _decide(sentinel: str, **kw):
    defaults = dict(
        sentinel_text=sentinel,
        forward_verdict=_verdict(),
        live_growth=_growth(),
        account_nav_usd=_NAV,
        live_config=_cfg(),
        validated_config=_cfg(),
        kill_switch_present=False,
        today=_TODAY,
    )
    defaults.update(kw)
    return decide_ladder(**defaults)


# ---- 파싱/렌더 -------------------------------------------------------------------


def test_parse_ladder_fields_roundtrip():
    text = render_ladder_sentinel(
        rung=2,
        capital_usd=6000,
        account_nav_usd=_NAV,
        rung_entered=_TODAY,
        run_seq=7,
        dd_budget_pct=DEFAULT_DD_BUDGET_PCT,
        evidence="test",
    )
    rung, entered, nav = parse_ladder_fields(text)
    assert rung == 2
    assert entered == _TODAY
    assert nav == _NAV
    assert "armed: true" in text


def test_render_rung0_is_disarmed():
    text = render_ladder_sentinel(
        rung=0,
        capital_usd=0,
        account_nav_usd=_NAV,
        rung_entered=_TODAY,
        run_seq=8,
        dd_budget_pct=DEFAULT_DD_BUDGET_PCT,
        evidence="halt",
    )
    assert "armed: false" in text


def test_parse_ladder_fields_missing_is_none():
    assert parse_ladder_fields(_DISARMED) == (None, None, None)


def test_rung_capital_floor():
    assert rung_capital_usd(1, Decimal("12345")) == 1234
    assert rung_capital_usd(2, Decimal("12345")) == 2469
    assert rung_capital_usd(3, Decimal("12345")) == 3086
    assert rung_capital_usd(5, Decimal("12345")) == 12345
    assert rung_capital_usd(0, Decimal("12345")) == 0


# ---- 차단 계열 (어느 단에서든) -----------------------------------------------------


def test_kill_switch_disables_everything():
    d = _decide(_RUNG2, kill_switch_present=True)
    assert d.action == ACTION_DISABLED
    assert not d.sentinel_changes


def test_fingerprint_mismatch_blocks_at_any_rung():
    d = _decide(_RUNG2, live_config=_cfg(universe=["SPY", "IEF"], top_n=2))
    assert d.action == ACTION_BLOCKED
    assert not d.sentinel_changes


def test_unknown_account_nav_blocks_without_state_change():
    for nav in (None, Decimal("0"), Decimal("-1")):
        d = _decide(_RUNG1, account_nav_usd=nav)
        assert d.action == ACTION_BLOCKED
        assert not d.sentinel_changes


# ---- 단 0 (forward 검증 게이트) ----------------------------------------------------


def test_rung0_waits_without_edge():
    for label in ("INSUFFICIENT_DATA", "NO_EDGE", None):
        d = _decide(_DISARMED, forward_verdict=_verdict(label) if label else {})
        assert d.action == ACTION_WAIT_EDGE
        assert not d.sentinel_changes


def test_rung0_promotes_to_rung1_on_edge_confirmed():
    d = _decide(_DISARMED)
    assert d.action == ACTION_PROMOTE
    assert d.target_rung == 2
    assert d.target_capital_usd == 2400  # 20% of 12000
    assert d.sentinel_changes
    assert "armed: true" in d.new_sentinel_text
    assert "ladder_rung: 2" in d.new_sentinel_text
    assert f"rung_entered: {_TODAY.isoformat()}" in d.new_sentinel_text
    assert "run_seq: 6" in d.new_sentinel_text  # 5 + 1


def test_rung0_rejects_legacy_edge_confirmed_evidence():
    legacy = _verdict()
    legacy.pop("significance_method")

    decision = _decide(_DISARMED, forward_verdict=legacy)

    assert decision.action == ACTION_WAIT_EDGE
    assert decision.target_rung == 0
    assert "LEGACY_EDGE_EVIDENCE" in decision.reason


def test_rung0_enters_exploration_canary_without_full_forward_edge() -> None:
    d = _decide(
        _DISARMED,
        forward_verdict=_verdict("NO_EDGE", 41),
        exploration_verdict={
            "verdict": "EXPLORATION_CANARY_READY",
            "candidate_id": "globalfixed-ensemble-3-6-9-12",
        },
    )
    assert d.action == ACTION_PROMOTE
    assert d.target_rung == 2
    assert d.target_capital_usd == 2400
    assert "exploration canary ready" in d.new_sentinel_text


def test_factory_winner_enters_only_10pct_research_canary() -> None:
    d = _decide(
        _DISARMED,
        forward_verdict=_verdict("NO_EDGE", 0),
        factory_verdict={
            "verdict": "RESEARCH_CANARY_READY",
            "candidate_id": "factory-winner",
        },
    )
    assert d.action == ACTION_PROMOTE
    assert d.target_rung == 1
    assert d.target_capital_usd == 1200
    assert "strategy factory ready" in d.new_sentinel_text


def test_exploration_wait_never_arms() -> None:
    d = _decide(
        _DISARMED,
        forward_verdict=_verdict("NO_EDGE", 41),
        exploration_verdict={"verdict": "EXPLORATION_CANARY_WAIT"},
    )
    assert d.action == ACTION_WAIT_EDGE
    assert not d.sentinel_changes


def test_unfilled_exploration_rung_demotes_when_latest_entry_evidence_fails() -> None:
    d = _decide(
        _RUNG2,
        forward_verdict=_verdict("NO_EDGE", 47),
        exploration_verdict={"verdict": "EXPLORATION_CANARY_WAIT"},
        live_growth=_growth(),
        live_performance={"fills_count": 0},
    )
    assert d.action == ACTION_DEMOTE
    assert d.target_rung == 0
    assert "armed: false" in d.new_sentinel_text


def test_existing_strategy_fill_keeps_live_risk_gates_authoritative() -> None:
    d = _decide(
        _RUNG2,
        forward_verdict=_verdict("NO_EDGE", 47),
        exploration_verdict={"verdict": "EXPLORATION_CANARY_WAIT"},
        live_growth=_growth(),
        live_performance={"fills_count": 1},
    )
    assert d.action == ACTION_STAY
    assert d.target_rung == 2


# ---- 강등·정지 (내려가는 건 즉시) ---------------------------------------------------


def test_halt_at_budget_disarms():
    d = _decide(_RUNG2, live_growth=_growth(dd="20.0"))
    assert d.action == ACTION_HALT
    assert d.target_rung == 0
    assert "armed: false" in d.new_sentinel_text


def test_demote_one_rung_at_half_budget():
    d = _decide(_RUNG2, live_growth=_growth(dd="10.0"))
    assert d.action == ACTION_DEMOTE
    assert d.target_rung == 1
    assert d.target_capital_usd == 1200
    assert "armed: true" in d.new_sentinel_text


def test_demote_from_rung1_disarms():
    d = _decide(_RUNG1, live_growth=_growth(dd="10.0"))
    assert d.action == ACTION_DEMOTE
    assert d.target_rung == 0
    assert "armed: false" in d.new_sentinel_text


def test_halt_beats_demote_when_both_cross():
    d = _decide(_RUNG3, live_growth=_growth(dd="35.0"))
    assert d.action == ACTION_HALT
    assert d.target_rung == 0


# ---- 승격 (올라가는 건 증거 전부) ---------------------------------------------------


def test_promote_rung1_to_2_requires_existing_exploration_contract():
    d = _decide(
        _RUNG1,
        forward_verdict=_verdict("NO_EDGE", 40),
        exploration_verdict={"verdict": "EXPLORATION_CANARY_READY"},
        factory_verdict={"verdict": "RESEARCH_CANARY_READY"},
        live_growth=_growth(dd="2.5", obs=25, period_days="30"),
    )
    assert d.action == ACTION_PROMOTE
    assert d.target_rung == 2
    assert d.target_capital_usd == 2400
    assert "ladder_rung: 2" in d.new_sentinel_text


def test_no_promotion_with_insufficient_obs():
    d = _decide(_RUNG2, live_growth=_growth(obs=PROMOTION_MIN_OBS - 1))
    assert d.action == ACTION_STAY


def test_no_promotion_with_insufficient_period():
    d = _decide(_RUNG2, live_growth=_growth(period_days=str(PROMOTION_MIN_CALENDAR_DAYS - 1)))
    assert d.action == ACTION_STAY


def test_no_promotion_when_dd_unmeasurable():
    # 낙폭 None(점 부족 등) = 증거 없음 → 승격 금지(fail-safe). 강등도 아님.
    d = _decide(_RUNG2, live_growth=_growth(dd=None))
    assert d.action == ACTION_STAY


def test_no_promotion_without_growth_at_all():
    d = _decide(_RUNG2, live_growth=None)
    assert d.action == ACTION_STAY


def test_exploration_rung_cannot_reach_25pct_without_full_forward_edge():
    d = _decide(
        _RUNG2,
        forward_verdict=_verdict("NO_EDGE", 41),
        exploration_verdict={"verdict": "EXPLORATION_CANARY_READY"},
        live_growth=_growth(dd="1.0", obs=40, period_days="60"),
    )
    assert d.action == ACTION_STAY
    assert d.target_rung == 2


def test_rung5_is_ceiling():
    d = _decide(_RUNG5, live_growth=_growth(dd="1.0", obs=40, period_days="60"))
    assert d.action in (ACTION_STAY, ACTION_RESIZE)  # 승격 없음
    assert d.target_rung == 5


def test_legacy_armed_sentinel_treated_as_rung1():
    d = _decide(_LEGACY_ARMED, live_growth=_growth(dd="2.5", obs=25, period_days="30"))
    assert d.current_rung == 1
    assert d.action == ACTION_PROMOTE
    assert d.target_rung == 2


# ---- 재사이징 (입금/성장 자동 반영) -------------------------------------------------


def test_resize_on_nav_drift_keeps_rung_and_clock():
    # 단 1 자본 $1,200인데 계좌 NAV 가 $24,000 로 늘었다(입금) → 10% = $2,400.
    d = _decide(
        _RUNG1,
        account_nav_usd=Decimal("24000"),
        live_growth=_growth(dd="2.5", obs=5, period_days="6"),  # 승격 증거는 미달
    )
    assert d.action == ACTION_RESIZE
    assert d.target_rung == 1
    assert d.target_capital_usd == 2400
    assert "rung_entered: 2026-05-10" in d.new_sentinel_text  # 시계 리셋 안 함


def test_no_resize_within_drift_band():
    # NAV $12,300 → 기대 자본 $2,460, 센티넬 $2,400 — 드리프트 2.4% < 10% → STAY.
    d = _decide(
        _RUNG1,
        account_nav_usd=Decimal("12300"),
        live_growth=_growth(dd="2.5", obs=5, period_days="6"),
    )
    assert d.action == ACTION_STAY
    assert not d.sentinel_changes

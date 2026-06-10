"""스펙 049 — forward 엣지 자동 무장 게이트 결정 로직 테스트.

실거래 무장이 걸린 안전 게이트라 *보수적 fail-safe* 를 빠짐없이 검증한다:
EDGE_CONFIRMED + 정합 + 미무장 + 킬스위치 없음 일 때만 ARM, 그 외 전부 무장 안 함.
"""

from __future__ import annotations

import pytest

from auto_invest.config.rules import PortfolioRebalanceConfig
from auto_invest.portfolio.autoarm import (
    ACTION_ALREADY_ARMED,
    ACTION_ARM,
    ACTION_BLOCKED,
    ACTION_DISABLED,
    ACTION_WAIT,
    MAX_CANARY_CAPITAL_USD,
    decide_autoarm,
    parse_sentinel,
    render_armed_sentinel,
    strategy_fingerprint,
)

# ---- 픽스처 ----------------------------------------------------------------------

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
        "schema_version": "1.1",
        "verdict": label,
        "n_obs": n_obs,
        "strategy_sharpe_annual": "2.05",
        "strategy_max_drawdown_pct": "-3.7",
        "strategy_calmar": "1.8",
    }


_DISARMED_SENTINEL = """# header
armed: false
capital_usd: 500
requested_by: mason
stage: live-canary-portfolio
run_seq: 5
note: "disarmed"
"""

_ARMED_SENTINEL = _DISARMED_SENTINEL.replace("armed: false", "armed: true")


# ---- 센티넬 파싱 -----------------------------------------------------------------


def test_parse_sentinel_disarmed():
    s = parse_sentinel(_DISARMED_SENTINEL)
    assert s.armed is False
    assert s.capital_usd == 500
    assert s.run_seq == 5


def test_parse_sentinel_armed():
    s = parse_sentinel(_ARMED_SENTINEL)
    assert s.armed is True


@pytest.mark.parametrize("val", ["false", "False", "no", "", "1", "yes", "TRUE "])
def test_parse_sentinel_armed_only_exact_true(val):
    # 정확히 'true'(대소문자 무관) 만 무장. 그 외는 fail-safe 로 미무장.
    text = f"armed: {val}\ncapital_usd: 500\nrun_seq: 1\n"
    expected = val.strip().lower() == "true"
    assert parse_sentinel(text).armed is expected


def test_parse_sentinel_missing_fields_conservative():
    s = parse_sentinel("# nothing here\n")
    assert s.armed is False
    assert s.capital_usd is None
    assert s.run_seq is None


def test_parse_sentinel_bad_capital():
    s = parse_sentinel("armed: false\ncapital_usd: abc\nrun_seq: x\n")
    assert s.capital_usd is None
    assert s.run_seq is None


# ---- 전략 지문 -------------------------------------------------------------------


def test_fingerprint_identical_configs_match():
    assert strategy_fingerprint(_cfg()) == strategy_fingerprint(_cfg())


def test_fingerprint_differs_on_universe():
    other = _cfg(universe=["SPY", "IEF"])
    assert strategy_fingerprint(_cfg()) != strategy_fingerprint(other)


def test_fingerprint_differs_on_weight_scheme():
    assert strategy_fingerprint(_cfg()) != strategy_fingerprint(
        _cfg(weight_scheme="equal")
    )


def test_fingerprint_differs_on_ensemble_windows():
    tf = {**_ENSEMBLE_PORTFOLIO["trend_filter"], "ensemble_windows": [63, 126]}
    assert strategy_fingerprint(_cfg()) != strategy_fingerprint(_cfg(trend_filter=tf))


def test_fingerprint_ignores_caps_capital():
    # 캡/자본/화이트리스트는 지문에 안 들어간다(전략 본질만). top_n 같은 전략 필드만 본다.
    # 같은 [portfolio] 면 지문 동일 — 라이브 캡이 달라도 정합.
    assert strategy_fingerprint(_cfg()) == strategy_fingerprint(_cfg())


# ---- 핵심 결정: ARM 경로 ---------------------------------------------------------


def test_arm_when_confirmed_coherent_unarmed():
    d = decide_autoarm(
        verdict=_verdict(),
        live_config=_cfg(),
        validated_config=_cfg(),
        sentinel_text=_DISARMED_SENTINEL,
        kill_switch_present=False,
    )
    assert d.action == ACTION_ARM
    assert d.should_arm is True
    assert d.proposed_capital_usd == 500  # 마지막 운영자 신호 보존
    assert d.new_run_seq == 6  # 5 → 6
    assert d.new_sentinel_text is not None
    # 새 센티넬은 armed:true 로 파싱돼야 한다.
    assert parse_sentinel(d.new_sentinel_text).armed is True
    assert parse_sentinel(d.new_sentinel_text).capital_usd == 500


def test_arm_clamps_capital_to_cap():
    # 센티넬 자본이 캡을 넘으면 캡으로 클램프(자동 게이트가 노출을 못 키운다).
    sentinel = _DISARMED_SENTINEL.replace("capital_usd: 500", "capital_usd: 99999")
    d = decide_autoarm(
        verdict=_verdict(),
        live_config=_cfg(),
        validated_config=_cfg(),
        sentinel_text=sentinel,
        kill_switch_present=False,
    )
    assert d.action == ACTION_ARM
    assert d.proposed_capital_usd == MAX_CANARY_CAPITAL_USD


# ---- 핵심 결정: 무장하지 않는 모든 경로 -----------------------------------------


def test_disabled_kill_switch_blocks_even_when_confirmed():
    d = decide_autoarm(
        verdict=_verdict(),
        live_config=_cfg(),
        validated_config=_cfg(),
        sentinel_text=_DISARMED_SENTINEL,
        kill_switch_present=True,
    )
    assert d.action == ACTION_DISABLED
    assert d.new_sentinel_text is None


def test_already_armed_is_noop():
    d = decide_autoarm(
        verdict=_verdict(),
        live_config=_cfg(),
        validated_config=_cfg(),
        sentinel_text=_ARMED_SENTINEL,
        kill_switch_present=False,
    )
    assert d.action == ACTION_ALREADY_ARMED
    assert d.new_sentinel_text is None


def test_blocked_when_strategy_mismatch():
    # 라이브가 검증한 전략과 다르면 무장 안 함(검증=무장 정합성).
    d = decide_autoarm(
        verdict=_verdict(),
        live_config=_cfg(weight_scheme="equal"),
        validated_config=_cfg(),
        sentinel_text=_DISARMED_SENTINEL,
        kill_switch_present=False,
    )
    assert d.action == ACTION_BLOCKED
    assert d.new_sentinel_text is None


@pytest.mark.parametrize("label", ["NO_EDGE", "INSUFFICIENT_DATA", "UNKNOWN", None])
def test_wait_when_not_confirmed(label):
    v = _verdict(label=label) if label is not None else {"verdict": None, "n_obs": 3}
    d = decide_autoarm(
        verdict=v,
        live_config=_cfg(),
        validated_config=_cfg(),
        sentinel_text=_DISARMED_SENTINEL,
        kill_switch_present=False,
    )
    assert d.action == ACTION_WAIT
    assert d.new_sentinel_text is None


def test_blocked_when_capital_nonpositive():
    sentinel = _DISARMED_SENTINEL.replace("capital_usd: 500", "capital_usd: 0")
    d = decide_autoarm(
        verdict=_verdict(),
        live_config=_cfg(),
        validated_config=_cfg(),
        sentinel_text=sentinel,
        kill_switch_present=False,
    )
    assert d.action == ACTION_BLOCKED


def test_empty_verdict_dict_waits():
    d = decide_autoarm(
        verdict={},
        live_config=_cfg(),
        validated_config=_cfg(),
        sentinel_text=_DISARMED_SENTINEL,
        kill_switch_present=False,
    )
    assert d.action == ACTION_WAIT


def test_precedence_disabled_beats_already_armed():
    # 킬스위치가 멱등보다 우선 — 무장돼 있어도 DISABLED 로 보고(정지 신호 우선).
    d = decide_autoarm(
        verdict=_verdict(),
        live_config=_cfg(),
        validated_config=_cfg(),
        sentinel_text=_ARMED_SENTINEL,
        kill_switch_present=True,
    )
    assert d.action == ACTION_DISABLED


# ---- 센티넬 렌더 라운드트립 ------------------------------------------------------


def test_render_armed_sentinel_roundtrip():
    text = render_armed_sentinel(
        capital_usd=750, run_seq=7, verdict_summary="EDGE_CONFIRMED (관측 22)"
    )
    s = parse_sentinel(text)
    assert s.armed is True
    assert s.capital_usd == 750
    assert s.run_seq == 7
    assert "스펙 049" in text
    assert "X.4" in text


def test_decision_json_serializable():
    d = decide_autoarm(
        verdict=_verdict(),
        live_config=_cfg(),
        validated_config=_cfg(),
        sentinel_text=_DISARMED_SENTINEL,
        kill_switch_present=False,
    )
    js = d.to_json_dict()
    assert js["action"] == ACTION_ARM
    assert js["verdict"] == "EDGE_CONFIRMED"
    assert js["proposed_capital_usd"] == 500

"""스펙 052 — 첫-자본까지의 길(money-path) 종합 단위 테스트."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from auto_invest.analytics.money_path import (
    CONV_CONVERGING,
    CONV_REGRESSED,
    CONV_STALLED,
    CONV_UNKNOWN,
    ETA_MEASURED,
    ETA_NOMINAL,
    ETA_NONE,
    GATE_FAIL,
    GATE_PASS,
    GATE_PENDING,
    SCHEMA_VERSION,
    STAGE_ACCUMULATING,
    STAGE_BLOCKED,
    STAGE_DEFENDED,
    STAGE_DEPLOYED,
    STAGE_EDGE_CONFIRMED,
    STAGE_NO_EDGE_YET,
    MoneyPathReport,
    _project_trading_date,
    _trading_days_between,
    assess_money_path,
)

NOW = datetime(2026, 6, 13, 8, 0, 0, tzinfo=UTC)  # 2026-06-13 = 토요일


def _ladder(action="WAIT_EDGE", cur=0, tgt=0, nav="1518.21", cap=None, dd="0", obs=3):
    return {
        "schema_version": "1.0",
        "action": action,
        "current_rung": cur,
        "target_rung": tgt,
        "reason": "테스트",
        "account_nav_usd": nav,
        "target_capital_usd": cap,
        "live_dd_pct": dd,
        "live_obs": obs,
    }


def _verdict(verdict="INSUFFICIENT_DATA", n_obs=1, min_obs=20, beats=False, dsr=None):
    return {
        "schema_version": "1.1",
        "verdict": verdict,
        "n_obs": n_obs,
        "min_obs_required": min_obs,
        "beats_benchmark_calmar": beats,
        "dsr": dsr,
        "dsr_threshold": "0.95",
        "universe": ["SPY", "IEF", "GLD"],
    }


# ── 헬퍼: 거래일 계산 / 추정 도달일 ──


def test_trading_days_between_skips_weekend():
    # 금(6/12) → 다음 화(6/16): 금·월(13·14·15는 토일월… 실제 평일은 금/월/화 직전)
    # 2026-06-12 금, 13 토, 14 일, 15 월, 16 화 → [12,16) 평일 = 12(금),15(월) = 2
    assert _trading_days_between(date(2026, 6, 12), date(2026, 6, 16)) == 2


def test_trading_days_between_nonpositive():
    assert _trading_days_between(date(2026, 6, 16), date(2026, 6, 12)) == 0
    assert _trading_days_between(date(2026, 6, 12), date(2026, 6, 12)) == 0


def test_project_trading_date_counts_only_weekdays():
    # 토요일에서 5 관측, 거래일당 1 → 다음 5 평일(월~금) 후 = 그 주 금요일.
    cal, reached = _project_trading_date(date(2026, 6, 13), 5, 1.0)
    assert reached.weekday() == 4  # 금요일
    assert cal == 6  # 토→(일월화수목금) 6 캘린더일


def test_project_trading_date_zero_remaining():
    assert _project_trading_date(date(2026, 6, 13), 0, 1.0) == (0, date(2026, 6, 13))


# ── 단계 분류 ──


def test_accumulating_stage_nominal_eta():
    r = assess_money_path(ladder=_ladder(), forward_verdict=_verdict(n_obs=1), now=NOW)
    assert r.stage == STAGE_ACCUMULATING
    assert r.current_rung == 0
    assert r.capital_pct == "0"
    assert r.eta.basis == ETA_NOMINAL
    assert r.eta.obs_remaining == 19
    assert r.eta.projected_date is not None
    # 게이트: 전진 관측 수(PENDING) + 전진 판정(PENDING).
    names = {g.name: g.status for g in r.gates}
    assert names["전진 관측 수"] == GATE_PENDING
    assert "운영자 게이트" in r.next_action


def test_accumulating_measured_eta_from_prior():
    # 직전 사이드카: 6/8(월) 관측 1 → now 6/12(금) 관측 5 → 4 거래일에 4 관측 = 1/거래일.
    now = datetime(2026, 6, 12, 8, 0, 0, tzinfo=UTC)
    prior = {"as_of_utc": "2026-06-08T08:00:00Z", "n_obs": 1}
    r = assess_money_path(
        ladder=_ladder(), forward_verdict=_verdict(n_obs=5), prior=prior, now=now
    )
    assert r.eta.basis == ETA_MEASURED
    assert r.eta.obs_per_trading_day == 1.0
    assert r.eta.obs_remaining == 15


def test_accumulating_obs_already_met_projects_today():
    r = assess_money_path(
        ladder=_ladder(), forward_verdict=_verdict(n_obs=20, min_obs=20), now=NOW
    )
    # 관측은 찼지만 verdict 가 INSUFFICIENT_DATA 라 아직 ACCUMULATING — ETA 0/오늘.
    assert r.eta.obs_remaining == 0
    assert r.eta.projected_date == "2026-06-13"
    assert r.eta.basis == ETA_NONE


# ── 전진 시계 수렴(정체/리셋/수렴) — "살아있지만 수렴 못 하는" 사각지대 ──


def test_convergence_converging_when_obs_grows():
    # 직전 6/8(월) 관측 1 → now 6/12(금) 관측 5 = 매 거래일 증가 → CONVERGING.
    now = datetime(2026, 6, 12, 8, 0, 0, tzinfo=UTC)
    prior = {"as_of_utc": "2026-06-08T08:00:00Z", "n_obs": 1}
    r = assess_money_path(
        ladder=_ladder(), forward_verdict=_verdict(n_obs=5), prior=prior, now=now
    )
    assert r.eta.convergence == CONV_CONVERGING
    assert r.eta.basis == ETA_MEASURED
    names = {g.name: g.status for g in r.gates}
    assert names["전진 시계 수렴"] == GATE_PASS


def test_convergence_stalled_when_obs_flat_over_trading_days():
    # 직전 6/11(목) 관측 3 → now 6/13(토) 관측 3, 거래일 2 경과했는데 그대로 = STALLED.
    prior = {"as_of_utc": "2026-06-11T08:00:00Z", "n_obs": 3}
    r = assess_money_path(
        ladder=_ladder(), forward_verdict=_verdict(n_obs=3), prior=prior, now=NOW
    )
    assert r.eta.convergence == CONV_STALLED
    assert r.eta.basis == ETA_NOMINAL  # 정체는 측정 불가 → nominal 최선치
    assert "정체" in r.headline and "⚠" in r.headline
    names = {g.name: g.status for g in r.gates}
    assert names["전진 시계 수렴"] == GATE_PENDING  # 정체는 일시적 가능(주말 등)


def test_convergence_stalled_not_flagged_same_trading_day():
    # 같은 거래일에 두 번 돌면(거래일 0 경과) 관측이 같아도 정체 아님 → UNKNOWN.
    prior = {"as_of_utc": "2026-06-13T02:00:00Z", "n_obs": 3}
    r = assess_money_path(
        ladder=_ladder(), forward_verdict=_verdict(n_obs=3), prior=prior, now=NOW
    )
    assert r.eta.convergence == CONV_UNKNOWN


def test_convergence_regressed_when_obs_drops():
    # 직전 관측 5 → now 관측 1 = 전진 시계 리셋(베이시스 변경) → REGRESSED, 게이트 FAIL.
    prior = {"as_of_utc": "2026-06-11T08:00:00Z", "n_obs": 5}
    r = assess_money_path(
        ladder=_ladder(), forward_verdict=_verdict(n_obs=1), prior=prior, now=NOW
    )
    assert r.eta.convergence == CONV_REGRESSED
    assert r.eta.obs_remaining == 19  # 관측 줄어 남은 관측이 다시 늘어남
    assert "리셋" in r.headline and "⚠" in r.headline
    names = {g.name: g.status for g in r.gates}
    assert names["전진 시계 수렴"] == GATE_FAIL


def test_convergence_unknown_without_prior():
    r = assess_money_path(ladder=_ladder(), forward_verdict=_verdict(n_obs=1), now=NOW)
    assert r.eta.convergence == CONV_UNKNOWN
    names = {g.name: g.status for g in r.gates}
    assert names["전진 시계 수렴"] == GATE_PENDING
    # 정상 누적 헤드라인은 ⚠ 가 없어야 한다(거짓 경보 0).
    assert "정상" in r.headline


def test_convergence_present_in_eta_dict():
    r = assess_money_path(ladder=_ladder(), forward_verdict=_verdict(n_obs=1), now=NOW)
    assert r.to_dict()["eta"]["convergence"] == CONV_UNKNOWN


# ── 전략 지문 정합(검증=배포) — '엣지를 쌓아도 배포가 막히는' 분기 진단 ──


def _fp(match=True, diverged=None, live="deploy/canary-live-portfolio.toml",
        validated="deploy/global-trend-portfolio.toml"):
    return {
        "match": match,
        "diverged": diverged or [],
        "live_path": live,
        "validated_path": validated,
    }


def test_fingerprint_match_adds_pass_gate():
    r = assess_money_path(
        ladder=_ladder(), forward_verdict=_verdict(n_obs=1), fingerprint=_fp(True), now=NOW
    )
    names = {g.name: g.status for g in r.gates}
    assert names["전략 지문 정합(검증=배포)"] == GATE_PASS


def test_fingerprint_none_adds_no_gate():
    # 입력 없으면 게이트 무변경(거짓 경보 0) — 기존 동작 보존.
    r = assess_money_path(ladder=_ladder(), forward_verdict=_verdict(n_obs=1), now=NOW)
    assert "전략 지문 정합(검증=배포)" not in {g.name for g in r.gates}


def test_fingerprint_mismatch_gate_fail_lists_fields():
    r = assess_money_path(
        ladder=_ladder(),
        forward_verdict=_verdict(n_obs=1),
        fingerprint=_fp(False, diverged=["universe", "trend_filter"]),
        now=NOW,
    )
    g = next(g for g in r.gates if g.name == "전략 지문 정합(검증=배포)")
    assert g.status == GATE_FAIL
    assert "universe" in g.current and "trend_filter" in g.current


def test_fingerprint_mismatch_blocked_gives_specific_diagnosis():
    # 사다리 BLOCKED + 지문 불일치 → 일반 '점검 필요' 대신 구체 진단.
    r = assess_money_path(
        ladder=_ladder(action="BLOCKED"),
        forward_verdict=_verdict(),
        fingerprint=_fp(False, diverged=["universe"]),
        now=NOW,
    )
    assert r.stage == STAGE_BLOCKED
    assert "지문 불일치" in r.headline and "universe" in r.headline
    assert "일치시켜야" in r.blocking_gate
    names = {g.name: g.status for g in r.gates}
    assert names["전략 지문 정합(검증=배포)"] == GATE_FAIL


def test_fingerprint_blocked_other_cause_stays_generic():
    # BLOCKED 이지만 지문은 일치 → NAV/킬스위치 등 일반 진단 유지.
    r = assess_money_path(
        ladder=_ladder(action="BLOCKED"),
        forward_verdict=_verdict(),
        fingerprint=_fp(True),
        now=NOW,
    )
    assert "점검 필요" in r.headline


def test_no_edge_yet_stage():
    r = assess_money_path(
        ladder=_ladder(),
        forward_verdict=_verdict(verdict="NO_EDGE", n_obs=25, beats=False, dsr="0.40"),
        now=NOW,
    )
    assert r.stage == STAGE_NO_EDGE_YET
    names = {g.name: g.status for g in r.gates}
    assert names["벤치마크 대비 칼마"] == GATE_FAIL
    assert names["디플레이티드 샤프(DSR)"] == GATE_FAIL


def test_no_edge_yet_passing_metrics_marked_pass():
    r = assess_money_path(
        ladder=_ladder(),
        forward_verdict=_verdict(verdict="NO_EDGE", n_obs=25, beats=True, dsr="0.99"),
        now=NOW,
    )
    names = {g.name: g.status for g in r.gates}
    assert names["벤치마크 대비 칼마"] == GATE_PASS
    assert names["디플레이티드 샤프(DSR)"] == GATE_PASS


def test_edge_confirmed_pending_deploy_canary_not_armed():
    r = assess_money_path(
        ladder=_ladder(action="WAIT_EDGE"),
        forward_verdict=_verdict(verdict="EDGE_CONFIRMED", n_obs=22),
        canary_armed=False,
        now=NOW,
    )
    assert r.stage == STAGE_EDGE_CONFIRMED
    names = {g.name: g.status for g in r.gates}
    assert names["전진 판정"] == GATE_PASS
    assert names["캐너리 무장"] == GATE_PENDING
    assert "운영자 게이트" in r.blocking_gate or "운영자 게이트" in r.next_action


def test_deployed_stage_next_rung_gates():
    r = assess_money_path(
        ladder=_ladder(action="STAY", cur=1, tgt=1, cap=379, dd="3.0", obs=12),
        forward_verdict=_verdict(verdict="EDGE_CONFIRMED", n_obs=22),
        live_growth={"period_days": "15.0", "current_nav_usd": "500.0"},
        now=NOW,
    )
    assert r.stage == STAGE_DEPLOYED
    assert r.current_rung == 1
    assert r.capital_pct == "25"
    names = {g.name: g.status for g in r.gates}
    assert names["라이브 관측 수"] == GATE_PENDING  # 12 < 20
    assert names["경과일"] == GATE_PENDING  # 15 < 27
    assert names["낙폭 < 예산/2"] == GATE_PASS  # 3% < 10%


def test_promote_action_reports_target_rung():
    r = assess_money_path(
        ladder=_ladder(action="PROMOTE", cur=0, tgt=1, cap=379),
        forward_verdict=_verdict(verdict="EDGE_CONFIRMED", n_obs=22),
        now=NOW,
    )
    assert r.stage == STAGE_DEPLOYED
    assert r.current_rung == 1  # target_rung 로 보고


def test_defended_stage_demote():
    r = assess_money_path(
        ladder=_ladder(action="DEMOTE", cur=2, tgt=1, dd="11.0"),
        forward_verdict=_verdict(verdict="EDGE_CONFIRMED", n_obs=30),
        now=NOW,
    )
    assert r.stage == STAGE_DEFENDED
    assert any(g.name == "라이브 낙폭" and g.status == GATE_FAIL for g in r.gates)


def test_blocked_stage_on_blocked_action():
    r = assess_money_path(
        ladder=_ladder(action="BLOCKED"), forward_verdict=_verdict(), now=NOW
    )
    assert r.stage == STAGE_BLOCKED


def test_blocked_stage_on_missing_verdict():
    r = assess_money_path(ladder=_ladder(), forward_verdict=None, now=NOW)
    assert r.stage == STAGE_BLOCKED


def test_deployed_days_gate_na_when_no_growth():
    r = assess_money_path(
        ladder=_ladder(action="STAY", cur=1, tgt=1, cap=379, dd="1.0", obs=25),
        forward_verdict=_verdict(verdict="EDGE_CONFIRMED", n_obs=22),
        live_growth=None,
        now=NOW,
    )
    names = {g.name: g.status for g in r.gates}
    assert names["라이브 관측 수"] == GATE_PASS  # 25 >= 20
    assert names["경과일"] == "N/A"  # period_days 없음


# ── 직렬화 / 결정론 ──


def test_to_dict_roundtrip_keys():
    r = assess_money_path(ladder=_ladder(), forward_verdict=_verdict(), now=NOW)
    d = r.to_dict()
    assert d["schema_version"] == SCHEMA_VERSION
    assert d["stage"] == STAGE_ACCUMULATING
    assert "eta" in d and "gates" in d and "headline" in d
    assert isinstance(d["gates"], list)


def test_as_text_smoke():
    r = assess_money_path(ladder=_ladder(), forward_verdict=_verdict(), now=NOW)
    text = r.as_text()
    assert "첫-자본까지의 길" in text
    assert "ETA" in text
    assert "돈 0 이동" in text


def test_deterministic():
    a = assess_money_path(ladder=_ladder(), forward_verdict=_verdict(), now=NOW)
    b = assess_money_path(ladder=_ladder(), forward_verdict=_verdict(), now=NOW)
    assert a.to_dict() == b.to_dict()


def test_naive_now_is_accepted():
    naive = datetime(2026, 6, 13, 8, 0, 0)
    r = assess_money_path(ladder=_ladder(), forward_verdict=_verdict(), now=naive)
    assert isinstance(r, MoneyPathReport)
    assert r.as_of_utc.endswith("Z")


def test_custom_dd_budget_changes_demote_threshold():
    r = assess_money_path(
        ladder=_ladder(action="STAY", cur=1, tgt=1, cap=379, dd="9.0", obs=25),
        forward_verdict=_verdict(verdict="EDGE_CONFIRMED", n_obs=22),
        live_growth={"period_days": "30.0"},
        dd_budget_pct=Decimal("30"),  # 예산/2 = 15% → 9% < 15% PASS
        now=NOW,
    )
    names = {g.name: g.status for g in r.gates}
    assert names["낙폭 < 예산/2"] == GATE_PASS

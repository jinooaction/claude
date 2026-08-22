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
    LIVE_STATUS_ARMED,
    LIVE_STATUS_BLOCKED,
    LIVE_STATUS_PREVIEW,
    LIVE_STATUS_UNKNOWN,
    SAMPLE_CHURNING,
    SAMPLE_SETTLED,
    SAMPLE_STABLE,
    SAMPLE_UNKNOWN,
    SCHEMA_VERSION,
    STAGE_ACCUMULATING,
    STAGE_BLOCKED,
    STAGE_DEFENDED,
    STAGE_DEPLOYED,
    STAGE_EDGE_CONFIRMED,
    STAGE_NO_EDGE_YET,
    MoneyPathReport,
    _capital_pct,
    _project_trading_date,
    _trading_days_between,
    assess_live_money_state,
    assess_money_path,
)

NOW = datetime(2026, 6, 13, 8, 0, 0, tzinfo=UTC)  # 2026-06-13 = 토요일
MONDAY_BEFORE_MICRO_SCHEDULE = datetime(2026, 6, 22, 12, 55, 0, tzinfo=UTC)


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


def _verdict(
    verdict="INSUFFICIENT_DATA",
    n_obs=1,
    min_obs=20,
    beats=False,
    dsr=None,
    psr=None,
    legacy=None,
    snapshots=None,
):
    d = {
        "schema_version": "1.1",
        "verdict": verdict,
        "n_obs": n_obs,
        "min_obs_required": min_obs,
        "beats_benchmark_calmar": beats,
        "dsr": dsr,
        "psr_vs_benchmark": psr,
        "dsr_threshold": "0.95",
        "universe": ["SPY", "IEF", "GLD"],
    }
    # 자본 베이시스 정합 결과(cli.py forward-verdict 발행) — 표본 안정성 입력. 옛
    # 사이드카엔 없을 수 있어 기본 미포함(None) → 기존 동작/거짓 경보 0 보존.
    if legacy is not None:
        d["legacy_snapshots_excluded"] = legacy
    if snapshots is not None:
        d["snapshot_count"] = snapshots
    return d


def _micro_request(armed="true", capital="1000"):
    return {
        "armed": armed,
        "capital_usd": capital,
        "stage": "micro-gtaa-live-canary",
        "run_seq": "2",
        "warning_drawdown_pct": "3",
        "hard_stop_drawdown_pct": "5",
        "note": "운영자 2026-06-22 명시 승인",
    }


def _live_request(armed="true", capital="293", rung="1", nav="1466.83"):
    return {
        "armed": armed,
        "capital_usd": capital,
        "stage": "live-canary-portfolio",
        "ladder_rung": rung,
        "account_nav_usd": nav,
    }


def _halt_clear(now: datetime = NOW):
    return {
        "status": "CLEAR",
        "observed_at_utc": now.isoformat().replace("+00:00", "Z"),
        "halt_present_after": False,
        "reconciliation_state": "OK",
        "evidence_quality": "VALID",
        "halt_cleared": False,
        "orders_submitted": 0,
        "reasons": [],
    }


def _micro_last_run(preflight=None):
    return {
        "run_id": "27935469561",
        "timestamp_utc": "2026-06-22T07:04:12Z",
        "event": "workflow_dispatch",
        "live_step": "success",
        "preflight": preflight,
        "breaker": {"reason": "within loss limits", "tripped": False},
        "live_result": {
            "portfolio_id": "micro-gtaa",
            "mode": "live",
            "results": [
                {"symbol": "IEF", "state": "REJECTED_BY_BROKER"},
                {"symbol": "SPYM", "state": "REJECTED_BY_BROKER"},
            ],
        },
    }


def _micro_last_run_with_intent_loss():
    payload = _micro_last_run()
    payload["intent_gate"] = {
        "schema_version": 1,
        "ok": False,
        "reason": "latest_intent_loss",
        "blocking_reasons": ["latest_intent_loss"],
        "latest_signal": "INTENT_LOSS",
    }
    return payload


# ── 스펙 062: 실제 돈 최상위 상태(micro GTAA) ──


def test_live_money_state_micro_armed_surfaces_real_order_path():
    state = assess_live_money_state(
        micro_request=_micro_request(),
        micro_last_run=_micro_last_run(),
        halt_recovery=_halt_clear(MONDAY_BEFORE_MICRO_SCHEDULE),
        now=MONDAY_BEFORE_MICRO_SCHEDULE,
    )
    assert state.status == LIVE_STATUS_ARMED
    assert state.can_submit_real_orders is True
    assert state.capital_usd == 1000
    assert state.next_scheduled_live_utc == "2026-06-22T15:00:00Z"
    assert state.last_run is not None
    assert state.last_run.live_step == "success"
    assert state.last_run.accepted_or_filled_count == 0
    assert state.last_run.broker_rejected_count == 2
    assert state.last_run.preflight_reason == "preflight evidence absent"


def test_live_money_state_blocks_armed_path_without_recovery_evidence():
    state = assess_live_money_state(
        micro_request=_micro_request(),
        micro_last_run=_micro_last_run(),
        now=MONDAY_BEFORE_MICRO_SCHEDULE,
    )
    assert state.status == LIVE_STATUS_BLOCKED
    assert state.can_submit_real_orders is False
    assert state.next_scheduled_live_utc is None
    assert "evidence missing" in state.detail


def test_live_money_state_blocks_stale_or_present_halt_recovery():
    stale = _halt_clear(datetime(2026, 6, 20, 0, 0, tzinfo=UTC))
    present = _halt_clear(MONDAY_BEFORE_MICRO_SCHEDULE)
    present["status"] = "BLOCKED"
    present["halt_present_after"] = True

    stale_state = assess_live_money_state(
        micro_request=_micro_request(),
        halt_recovery=stale,
        now=MONDAY_BEFORE_MICRO_SCHEDULE,
    )
    present_state = assess_live_money_state(
        micro_request=_micro_request(),
        halt_recovery=present,
        now=MONDAY_BEFORE_MICRO_SCHEDULE,
    )

    assert stale_state.status == LIVE_STATUS_BLOCKED
    assert "stale" in stale_state.detail
    assert present_state.status == LIVE_STATUS_BLOCKED
    assert present_state.can_submit_real_orders is False


def test_live_money_state_micro_armed_intent_loss_blocks_orders():
    state = assess_live_money_state(
        micro_request=_micro_request(),
        micro_last_run=_micro_last_run_with_intent_loss(),
        halt_recovery=_halt_clear(MONDAY_BEFORE_MICRO_SCHEDULE),
        now=MONDAY_BEFORE_MICRO_SCHEDULE,
    )

    assert state.status == LIVE_STATUS_BLOCKED
    assert state.can_submit_real_orders is False
    assert state.next_scheduled_live_utc is None
    assert "latest_intent_loss" in state.detail
    assert state.last_run is not None
    assert state.last_run.intent_gate_ok is False
    assert state.last_run.intent_gate_reason == "latest_intent_loss"


def test_money_path_report_surfaces_intent_gate_reason():
    report = assess_money_path(
        ladder=_ladder(),
        forward_verdict=_verdict(n_obs=1),
        micro_request=_micro_request(),
        micro_last_run=_micro_last_run_with_intent_loss(),
        now=MONDAY_BEFORE_MICRO_SCHEDULE,
    )

    text = report.as_text()

    assert "마지막 전략 의도 게이트" in text
    assert "ok=False, reason=latest_intent_loss" in text


def test_live_money_state_micro_disarmed_is_preview_only():
    state = assess_live_money_state(
        micro_request=_micro_request(armed="false"),
        micro_last_run=None,
        halt_recovery=_halt_clear(MONDAY_BEFORE_MICRO_SCHEDULE),
        now=MONDAY_BEFORE_MICRO_SCHEDULE,
    )
    assert state.status == LIVE_STATUS_PREVIEW
    assert state.can_submit_real_orders is False
    assert state.next_scheduled_live_utc is None


def test_live_money_state_micro_invalid_capital_blocks_orders():
    state = assess_live_money_state(
        micro_request=_micro_request(capital="1001"),
        micro_last_run=None,
        now=MONDAY_BEFORE_MICRO_SCHEDULE,
    )
    assert state.status == LIVE_STATUS_BLOCKED
    assert state.can_submit_real_orders is False


def test_live_money_state_missing_sentinel_is_unknown():
    state = assess_live_money_state(
        micro_request=None,
        micro_last_run=None,
        halt_recovery=_halt_clear(MONDAY_BEFORE_MICRO_SCHEDULE),
        now=MONDAY_BEFORE_MICRO_SCHEDULE,
    )
    assert state.status == LIVE_STATUS_UNKNOWN
    assert state.can_submit_real_orders is False


def test_money_path_report_puts_live_money_state_before_ladder_stage():
    r = assess_money_path(
        ladder=_ladder(),
        forward_verdict=_verdict(n_obs=1),
        micro_request=_micro_request(),
        micro_last_run=_micro_last_run(),
        halt_recovery=_halt_clear(MONDAY_BEFORE_MICRO_SCHEDULE),
        now=MONDAY_BEFORE_MICRO_SCHEDULE,
    )
    d = r.to_dict()
    assert d["live_money_state"]["status"] == LIVE_STATUS_ARMED
    assert d["live_money_state"]["can_submit_real_orders"] is True
    text = r.as_text()
    assert "실제 돈 최상위 상태" in text
    assert "실제 돈 경로 무장" in text
    assert "preflight 통과 후 실주문 가능" in text
    assert "브로커 접수·체결 0건" in text
    assert text.index("실제 돈 최상위 상태") < text.index("## 기존 자본 사다리 상태")


def test_live_money_state_prefers_armed_capital_ladder_over_disarmed_micro():
    state = assess_live_money_state(
        live_request=_live_request(),
        live_last_run=None,
        canary_armed=True,
        micro_request=_micro_request(armed="false"),
        micro_last_run=None,
        halt_recovery=_halt_clear(NOW),
        now=NOW,
    )

    assert state.status == LIVE_STATUS_ARMED
    assert state.can_submit_real_orders is True
    assert state.path == "capital-ladder-live-canary"
    assert state.capital_usd == 293
    assert state.max_capital_usd == 293
    assert state.next_scheduled_live_utc == "2026-06-15T15:00:00Z"
    assert "production environment machine authorization" in state.required_gates
    assert "production environment approval" not in state.required_gates


def test_live_money_state_blocks_capital_ladder_sidecar_mismatch():
    state = assess_live_money_state(
        live_request=_live_request(),
        live_last_run=None,
        canary_armed=False,
        micro_request=_micro_request(armed="false"),
        micro_last_run=None,
        now=NOW,
    )

    assert state.status == LIVE_STATUS_BLOCKED
    assert state.can_submit_real_orders is False
    assert state.path == "capital-ladder-live-canary"
    assert "불일치" in state.detail


def test_live_money_state_blocks_when_capital_ladder_sidecar_is_missing():
    state = assess_live_money_state(
        live_request=_live_request(),
        live_last_run=None,
        canary_armed=None,
        micro_request=_micro_request(armed="false"),
        micro_last_run=None,
        now=NOW,
    )

    assert state.status == LIVE_STATUS_BLOCKED
    assert state.can_submit_real_orders is False
    assert "결측 차단" in state.detail


def test_live_money_state_keeps_armed_micro_when_standard_is_inactive():
    state = assess_live_money_state(
        live_request=_live_request(armed="false", capital="0", rung="0"),
        live_last_run=None,
        canary_armed=False,
        micro_request=_micro_request(),
        micro_last_run=_micro_last_run(),
        halt_recovery=_halt_clear(MONDAY_BEFORE_MICRO_SCHEDULE),
        now=MONDAY_BEFORE_MICRO_SCHEDULE,
    )

    assert state.status == LIVE_STATUS_ARMED
    assert state.path == "micro-gtaa-live-canary"


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
    # 헌법 X.4 v5.0.0: 무장은 자율(상시 위임), 운영자 전용은 입금·킬스위치뿐.
    assert "자율 무장" in r.next_action
    assert "운영자 전용" in r.next_action


def test_accumulating_measured_eta_from_prior():
    # 직전 사이드카: 6/8(월) 관측 1 → now 6/12(금) 관측 5 → 4 거래일에 4 관측 = 1/거래일.
    now = datetime(2026, 6, 12, 8, 0, 0, tzinfo=UTC)
    prior = {"as_of_utc": "2026-06-08T08:00:00Z", "n_obs": 1}
    r = assess_money_path(ladder=_ladder(), forward_verdict=_verdict(n_obs=5), prior=prior, now=now)
    assert r.eta.basis == ETA_MEASURED
    assert r.eta.obs_per_trading_day == 1.0
    assert r.eta.obs_remaining == 15


def test_accumulating_obs_already_met_projects_today():
    r = assess_money_path(ladder=_ladder(), forward_verdict=_verdict(n_obs=20, min_obs=20), now=NOW)
    # 관측은 찼지만 verdict 가 INSUFFICIENT_DATA 라 아직 ACCUMULATING — ETA 0/오늘.
    assert r.eta.obs_remaining == 0
    assert r.eta.projected_date == "2026-06-13"
    assert r.eta.basis == ETA_NONE


# ── 전진 시계 수렴(정체/리셋/수렴) — "살아있지만 수렴 못 하는" 사각지대 ──


def test_convergence_converging_when_obs_grows():
    # 직전 6/8(월) 관측 1 → now 6/12(금) 관측 5 = 매 거래일 증가 → CONVERGING.
    now = datetime(2026, 6, 12, 8, 0, 0, tzinfo=UTC)
    prior = {"as_of_utc": "2026-06-08T08:00:00Z", "n_obs": 1}
    r = assess_money_path(ladder=_ladder(), forward_verdict=_verdict(n_obs=5), prior=prior, now=now)
    assert r.eta.convergence == CONV_CONVERGING
    assert r.eta.basis == ETA_MEASURED
    names = {g.name: g.status for g in r.gates}
    assert names["전진 시계 수렴"] == GATE_PASS


def test_convergence_stalled_when_obs_flat_over_trading_days():
    # 직전 6/11(목) 관측 3 → now 6/13(토) 관측 3, 거래일 2 경과했는데 그대로 = STALLED.
    prior = {"as_of_utc": "2026-06-11T08:00:00Z", "n_obs": 3}
    r = assess_money_path(ladder=_ladder(), forward_verdict=_verdict(n_obs=3), prior=prior, now=NOW)
    assert r.eta.convergence == CONV_STALLED
    assert r.eta.basis == ETA_NOMINAL  # 정체는 측정 불가 → nominal 최선치
    assert "정체" in r.headline and "⚠" in r.headline
    names = {g.name: g.status for g in r.gates}
    assert names["전진 시계 수렴"] == GATE_PENDING  # 정체는 일시적 가능(주말 등)


def test_convergence_stalled_not_flagged_same_trading_day():
    # 같은 거래일에 두 번 돌면(거래일 0 경과) 관측이 같아도 정체 아님 → UNKNOWN.
    prior = {"as_of_utc": "2026-06-13T02:00:00Z", "n_obs": 3}
    r = assess_money_path(ladder=_ladder(), forward_verdict=_verdict(n_obs=3), prior=prior, now=NOW)
    assert r.eta.convergence == CONV_UNKNOWN


def test_convergence_regressed_when_obs_drops():
    # 직전 관측 5 → now 관측 1 = 전진 시계 리셋(베이시스 변경) → REGRESSED, 게이트 FAIL.
    prior = {"as_of_utc": "2026-06-11T08:00:00Z", "n_obs": 5}
    r = assess_money_path(ladder=_ladder(), forward_verdict=_verdict(n_obs=1), prior=prior, now=NOW)
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


# ── 전진 표본 안정성(자본 베이시스 흔들림) — 수렴과 직교한 '왜 안 쌓이나'의 원인 ──


def test_sample_stable_when_no_legacy_excluded():
    # 제외 0 → 모든 스냅샷 같은 베이시스 → STABLE, 게이트 PASS.
    r = assess_money_path(
        ladder=_ladder(),
        forward_verdict=_verdict(n_obs=3, legacy=0, snapshots=4),
        now=NOW,
    )
    assert r.eta.sample_stability == SAMPLE_STABLE
    names = {g.name: g.status for g in r.gates}
    assert names["전진 표본 안정성(베이시스)"] == GATE_PASS


def test_sample_settled_when_legacy_flat_vs_prior():
    # 직전 제외 4 == 이번 제외 4, 관측 증가 → 과거 1회 정리(SETTLED), 게이트 PASS.
    prior = {"as_of_utc": "2026-06-11T08:00:00Z", "n_obs": 1, "legacy_excluded": 4}
    r = assess_money_path(
        ladder=_ladder(),
        forward_verdict=_verdict(n_obs=2, legacy=4, snapshots=3),
        prior=prior,
        now=NOW,
    )
    assert r.eta.sample_stability == SAMPLE_SETTLED
    names = {g.name: g.status for g in r.gates}
    assert names["전진 표본 안정성(베이시스)"] == GATE_PASS


def test_sample_settled_without_prior_is_conservative():
    # 제외 4 이지만 직전 비교 불가 → 보수적 SETTLED(거짓 흔들림 경보 0), 게이트 PASS.
    r = assess_money_path(
        ladder=_ladder(),
        forward_verdict=_verdict(n_obs=1, legacy=4, snapshots=2),
        now=NOW,
    )
    assert r.eta.sample_stability == SAMPLE_SETTLED
    names = {g.name: g.status for g in r.gates}
    assert names["전진 표본 안정성(베이시스)"] == GATE_PASS
    assert "정상" in r.headline  # 정상 누적 헤드라인(흔들림 경보 아님)


def test_sample_churning_masquerading_as_stalled():
    # 핵심 빈칸: 관측은 그대로(STALLED 로 보임)인데 제외가 직전보다 늘어남 → 진짜 원인은
    # 베이시스 흔들림. headline 이 '표본 흔들림' 을 짚고, 표본 게이트 FAIL.
    prior = {"as_of_utc": "2026-06-11T08:00:00Z", "n_obs": 1, "legacy_excluded": 2}
    r = assess_money_path(
        ladder=_ladder(),
        forward_verdict=_verdict(n_obs=1, legacy=4, snapshots=2),
        prior=prior,
        now=NOW,
    )
    assert r.eta.sample_stability == SAMPLE_CHURNING
    assert r.eta.convergence == CONV_STALLED  # 관측만 보면 정체
    assert "흔들림" in r.headline and "측정 기준 고정" in r.headline
    names = {g.name: g.status for g in r.gates}
    assert names["전진 표본 안정성(베이시스)"] == GATE_FAIL
    assert names["전진 시계 수렴"] == GATE_PENDING  # 수렴은 여전히 정체로 본다(직교)


def test_sample_churning_with_regressed_obs_names_count():
    # 관측도 줄고(REGRESSED) 제외도 늘어남(CHURNING) — 리셋 headline 에 제외 개수 명시.
    prior = {"as_of_utc": "2026-06-11T08:00:00Z", "n_obs": 5, "legacy_excluded": 1}
    r = assess_money_path(
        ladder=_ladder(),
        forward_verdict=_verdict(n_obs=1, legacy=4, snapshots=2),
        prior=prior,
        now=NOW,
    )
    assert r.eta.convergence == CONV_REGRESSED
    assert r.eta.sample_stability == SAMPLE_CHURNING
    assert "리셋" in r.headline and "4개 스냅샷 제외" in r.headline
    names = {g.name: g.status for g in r.gates}
    assert names["전진 표본 안정성(베이시스)"] == GATE_FAIL


def test_sample_no_gate_without_legacy_info():
    # legacy 정보 없는 옛 사이드카 → 표본 게이트 미추가(기존 동작/거짓 경보 0).
    r = assess_money_path(ladder=_ladder(), forward_verdict=_verdict(n_obs=1), now=NOW)
    assert "전진 표본 안정성(베이시스)" not in {g.name for g in r.gates}
    assert r.eta.sample_stability == SAMPLE_UNKNOWN


def test_sample_fields_present_in_eta_dict():
    r = assess_money_path(
        ladder=_ladder(),
        forward_verdict=_verdict(n_obs=1, legacy=4, snapshots=2),
        now=NOW,
    )
    d = r.to_dict()["eta"]
    assert d["sample_stability"] == SAMPLE_SETTLED
    assert d["legacy_excluded"] == 4
    assert d["snapshot_count"] == 2


# ── 전략 지문 정합(검증=배포) — '엣지를 쌓아도 배포가 막히는' 분기 진단 ──


def _fp(
    match=True,
    diverged=None,
    live="deploy/canary-live-portfolio.toml",
    validated="deploy/global-trend-portfolio.toml",
):
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
    # 헌법 X.4 v5.0.0: 무장 자체가 자율 — '운영자 게이트' 가 아니라 입금·킬스위치만 운영자 몫.
    assert "자율 무장" in r.blocking_gate or "자율 무장" in r.next_action
    assert "운영자 전용" in r.next_action


def test_edge_confirmed_shows_psr_confidence():
    # 실제 돈 직전 — 엣지 신뢰도(PSR)를 게이트·헤드라인에 수치로 보인다.
    r = assess_money_path(
        ladder=_ladder(action="WAIT_EDGE"),
        forward_verdict=_verdict(verdict="EDGE_CONFIRMED", n_obs=22, psr="0.97"),
        canary_armed=False,
        now=NOW,
    )
    assert r.stage == STAGE_EDGE_CONFIRMED
    names = {g.name: g.status for g in r.gates}
    assert names["엣지 신뢰도(PSR)"] == GATE_PASS  # 0.97 ≥ 0.95
    assert "신뢰도 PSR 0.97" in r.headline


def test_edge_confirmed_no_psr_no_confidence_gate():
    # PSR 없으면 신뢰도 게이트·헤드라인 표식 없음(거짓 표시 0, 하위호환).
    r = assess_money_path(
        ladder=_ladder(action="WAIT_EDGE"),
        forward_verdict=_verdict(verdict="EDGE_CONFIRMED", n_obs=22),
        now=NOW,
    )
    names = {g.name for g in r.gates}
    assert "엣지 신뢰도(PSR)" not in names
    assert "신뢰도 PSR" not in r.headline


def test_no_edge_yet_shows_psr_when_present():
    r = assess_money_path(
        ladder=_ladder(),
        forward_verdict=_verdict(verdict="NO_EDGE", n_obs=25, beats=False, dsr="0.40", psr="0.50"),
        now=NOW,
    )
    names = {g.name: g.status for g in r.gates}
    assert names["엣지 신뢰도(PSR)"] == GATE_FAIL  # 0.50 < 0.95
    assert names["디플레이티드 샤프(DSR)"] == GATE_FAIL


def test_deployed_stage_next_rung_gates():
    r = assess_money_path(
        ladder=_ladder(action="STAY", cur=1, tgt=1, cap=303, dd="3.0", obs=12),
        forward_verdict=_verdict(verdict="EDGE_CONFIRMED", n_obs=22),
        live_growth={"period_days": "15.0", "current_nav_usd": "500.0"},
        now=NOW,
    )
    assert r.stage == STAGE_DEPLOYED
    assert r.current_rung == 1
    assert r.capital_pct == "10"
    names = {g.name: g.status for g in r.gates}
    assert names["라이브 관측 수"] == GATE_PENDING  # 12 < 20
    assert names["경과일"] == GATE_PENDING  # 15 < 27
    assert names["낙폭 < 예산/2"] == GATE_PASS  # 3% < 10%


def test_promote_action_reports_target_rung():
    r = assess_money_path(
        ladder=_ladder(action="PROMOTE", cur=0, tgt=1, cap=303),
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
    r = assess_money_path(ladder=_ladder(action="BLOCKED"), forward_verdict=_verdict(), now=NOW)
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


# ── 자본 방어선 예산 (다운사이드 한계 — 내려가는 길) ──


def test_safety_budget_prospective_at_rung0():
    # 단0(자본 0%) — 첫 자본이 들어가면 어떤 다운사이드인지 미리(돈 움직이기 전).
    r = assess_money_path(ladder=_ladder(), forward_verdict=_verdict(), now=NOW)
    s = r.safety
    assert s is not None
    assert s.prospective is True
    assert s.reference_rung == 1  # 첫 자본 단
    assert s.capital_usd == 151  # floor(1518.21 * 0.10)
    assert s.demote_dd_pct == "10"  # 예산 20% / 2
    assert s.halt_dd_pct == "20"
    assert s.loss_at_demote_usd == 16  # ceil(151 * 0.10)
    assert s.loss_at_halt_usd == 31  # ceil(151 * 0.20)
    assert s.current_dd_pct is None  # 아직 배치 안 됨 → 현재 낙폭 없음
    assert s.margin_to_demote_pct is None


def test_safety_budget_prospective_at_edge_confirmed():
    # 엣지 확정(첫 자본 임박)에도 예상 예산이 보인다.
    r = assess_money_path(
        ladder=_ladder(action="WAIT_EDGE"),
        forward_verdict=_verdict(verdict="EDGE_CONFIRMED", n_obs=22),
        now=NOW,
    )
    assert r.stage == STAGE_EDGE_CONFIRMED
    assert r.safety is not None
    assert r.safety.prospective is True
    assert r.safety.reference_rung == 1


def test_safety_budget_deployed_shows_margins():
    # 배치 중 — 방어선까지 남은 여유(%포인트)를 연속 값으로 표면화.
    r = assess_money_path(
        ladder=_ladder(action="STAY", cur=1, tgt=1, cap=379, dd="3.0", obs=12),
        forward_verdict=_verdict(verdict="EDGE_CONFIRMED", n_obs=22),
        live_growth={"period_days": "15.0"},
        now=NOW,
    )
    s = r.safety
    assert s is not None
    assert s.prospective is False
    assert s.reference_rung == 1
    assert s.capital_usd == 379  # 결정 JSON 의 배치 자본 사용
    assert s.current_dd_pct == "3.0"
    assert s.margin_to_demote_pct == "7.0"  # 10 - 3.0
    assert s.margin_to_halt_pct == "17.0"  # 20 - 3.0
    assert s.loss_at_demote_usd == 38


def test_safety_budget_defended_negative_margin():
    # 방어 발동(낙폭 초과) — 강등까지 여유가 음수로 드러난다.
    r = assess_money_path(
        ladder=_ladder(action="DEMOTE", cur=2, tgt=1, dd="11.0"),
        forward_verdict=_verdict(verdict="EDGE_CONFIRMED", n_obs=30),
        now=NOW,
    )
    assert r.stage == STAGE_DEFENDED
    s = r.safety
    assert s is not None
    assert s.reference_rung == 2  # 초과한 그 단 기준
    assert s.capital_usd == 303  # floor(1518.21 * 0.20)
    assert s.current_dd_pct == "11.0"
    assert Decimal(s.margin_to_demote_pct) < 0  # 10 - 11.0 = -1.0


def test_safety_budget_none_when_blocked():
    r = assess_money_path(ladder=_ladder(action="BLOCKED"), forward_verdict=_verdict(), now=NOW)
    assert r.safety is None
    assert r.to_dict()["safety_budget"] is None


def test_safety_budget_na_when_nav_unknown():
    # NAV 측정 불가면 달러는 None 이지만 % 임계는 여전히 의미 있다.
    r = assess_money_path(ladder=_ladder(nav=""), forward_verdict=_verdict(), now=NOW)
    s = r.safety
    assert s is not None
    assert s.capital_usd is None
    assert s.loss_at_demote_usd is None
    assert s.demote_dd_pct == "10"


def test_safety_budget_deployed_dd_missing_flags_feed():
    # 배치됐는데 라이브 낙폭이 없으면 방어선 입력 결손을 경고(자동 강등 지연 위험).
    r = assess_money_path(
        ladder=_ladder(action="STAY", cur=1, tgt=1, cap=379, dd=None, obs=25),
        forward_verdict=_verdict(verdict="EDGE_CONFIRMED", n_obs=22),
        live_growth={"period_days": "30.0"},
        now=NOW,
    )
    s = r.safety
    assert s is not None
    assert s.capital_usd == 379
    assert s.current_dd_pct is None
    assert s.margin_to_demote_pct is None
    assert "측정 불가" in r.as_text()


def test_safety_budget_custom_budget_scales_thresholds():
    r = assess_money_path(
        ladder=_ladder(action="STAY", cur=1, tgt=1, cap=379, dd="9.0", obs=25),
        forward_verdict=_verdict(verdict="EDGE_CONFIRMED", n_obs=22),
        live_growth={"period_days": "30.0"},
        dd_budget_pct=Decimal("30"),
        now=NOW,
    )
    s = r.safety
    assert s is not None
    assert s.demote_dd_pct == "15"  # 30 / 2
    assert s.halt_dd_pct == "30"
    assert s.margin_to_demote_pct == "6.0"  # 15 - 9.0


def test_safety_budget_in_to_dict():
    r = assess_money_path(ladder=_ladder(), forward_verdict=_verdict(), now=NOW)
    sb = r.to_dict()["safety_budget"]
    assert sb["reference_rung"] == 1
    assert sb["prospective"] is True
    assert sb["loss_at_demote_usd"] == 16
    assert sb["demote_dd_pct"] == "10"


def test_as_text_includes_safety_section():
    r = assess_money_path(ladder=_ladder(), forward_verdict=_verdict(), now=NOW)
    text = r.as_text()
    assert "자본 방어선 예산" in text
    assert "첫 자본" in text


# ── 배치 비율 표기 (과학적 표기 회귀) ──


def test_capital_pct_no_scientific_notation():
    # Decimal.normalize() 회귀: 단4=50%·단5=100% 가 '5E+1'/'1E+2' 로 깨지면 안 됨.
    assert _capital_pct(0) == "0"
    assert _capital_pct(1) == "10"
    assert _capital_pct(2) == "20"
    assert _capital_pct(3) == "25"
    assert _capital_pct(4) == "50"
    assert _capital_pct(5) == "100"


def test_capital_pct_in_report_at_rung4():
    # 실제 돈이 NAV 50%(단4)로 커진 보고서에 '5E+1%' 가 새어나오면 안 됨.
    r = assess_money_path(
        ladder=_ladder(action="STAY", cur=4, tgt=4, cap=759, dd="2.0", obs=25),
        forward_verdict=_verdict(verdict="EDGE_CONFIRMED", n_obs=30),
        live_growth={"period_days": "30.0"},
        now=NOW,
    )
    assert r.capital_pct == "50"
    assert "5E+1" not in r.as_text()
    assert "1E+2" not in r.as_text()

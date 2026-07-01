"""스펙 051 — 자율 파이프라인 생존 감시 단위 테스트."""

from __future__ import annotations

from datetime import UTC, datetime

from auto_invest.analytics.pipeline_liveness import (
    CRITICAL,
    DEGRADED,
    HEALTHY,
    LATE,
    MISSING,
    OK,
    PENDING,
    SCHEMA_VERSION,
    STALE,
    SidecarSpec,
    assess_liveness,
    default_specs,
    parse_timestamp_utc,
)

NOW = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)


def _md(ts: str) -> str:
    """LAST_RUN.md 의 timestamp_utc 표 행을 흉내."""
    return f"# 어떤 사이드카\n\n| 항목 | 값 |\n|---|---|\n| timestamp_utc | {ts} |\n"


def _spec(key: str, *, max_age: float = 24.0, critical: bool = True) -> SidecarSpec:
    return SidecarSpec(
        key=key,
        branch=f"automation/{key}-last-run",
        filename="LAST_RUN.md",
        max_age_hours=max_age,
        critical=critical,
        description=f"{key} 설명",
    )


# ── 타임스탬프 파싱 ──


def test_parse_timestamp_from_markdown_table():
    assert parse_timestamp_utc(_md("2026-06-13T06:59:34Z")) == "2026-06-13T06:59:34Z"


def test_parse_timestamp_from_json_with_fraction():
    text = '{"timestamp_utc": "2026-06-13T01:53:50.182Z", "x": 1}'
    assert parse_timestamp_utc(text) == "2026-06-13T01:53:50.182Z"


def test_parse_timestamp_none_when_absent_or_empty():
    assert parse_timestamp_utc("표에 시각이 없는 본문") is None
    assert parse_timestamp_utc("") is None
    assert parse_timestamp_utc(None) is None


# ── 등급 분류(나이 기준) ──


def test_fresh_sidecar_is_ok():
    # 12h 전 = 한계 24h 안 → OK.
    obs = {"a": _md("2026-06-13T00:00:00Z")}
    rep = assess_liveness([_spec("a", max_age=24.0)], obs, NOW)
    assert rep.checks[0].status == OK
    assert rep.overall == HEALTHY
    assert rep.exit_code == 0


def test_late_sidecar_between_one_and_two_cadences():
    # 30h 전 = 24h~48h 사이 → LATE.
    obs = {"a": _md("2026-06-12T06:00:00Z")}
    rep = assess_liveness([_spec("a", max_age=24.0)], obs, NOW)
    assert rep.checks[0].status == LATE


def test_stale_sidecar_beyond_two_cadences():
    # 60h 전 = 48h(2*24) 초과 → STALE.
    obs = {"a": _md("2026-06-11T00:00:00Z")}
    rep = assess_liveness([_spec("a", max_age=24.0)], obs, NOW)
    assert rep.checks[0].status == STALE


def test_missing_sidecar():
    rep = assess_liveness([_spec("a")], {"a": None}, NOW)
    assert rep.checks[0].status == MISSING
    assert rep.checks[0].age_hours is None
    assert rep.checks[0].timestamp_utc is None


# ── 종합 판정 + 종료 코드 ──


def test_critical_stale_sidecar_makes_overall_critical():
    obs = {"a": _md("2026-06-11T00:00:00Z")}  # 60h → STALE
    rep = assess_liveness([_spec("a", max_age=24.0, critical=True)], obs, NOW)
    assert rep.overall == CRITICAL
    assert rep.exit_code == 1
    assert [c.key for c in rep.stale_critical] == ["a"]


def test_critical_missing_sidecar_makes_overall_critical():
    rep = assess_liveness([_spec("a", critical=True)], {"a": None}, NOW)
    assert rep.overall == CRITICAL
    assert rep.exit_code == 1


def test_informational_stale_is_only_degraded():
    obs = {"a": _md("2026-06-11T00:00:00Z")}  # 60h → STALE
    rep = assess_liveness([_spec("a", max_age=24.0, critical=False)], obs, NOW)
    assert rep.checks[0].status == STALE
    assert rep.overall == DEGRADED
    assert rep.exit_code == 0  # 연구 트랙 정지는 빨강(실패)으로 만들지 않는다


def test_informational_late_does_not_escalate():
    obs = {"a": _md("2026-06-12T06:00:00Z")}  # 30h → LATE
    rep = assess_liveness([_spec("a", max_age=24.0, critical=False)], obs, NOW)
    assert rep.checks[0].status == LATE
    assert rep.overall == HEALTHY  # 연구 트랙의 가벼운 지연은 무시


def test_critical_late_is_degraded_not_critical():
    obs = {"a": _md("2026-06-12T06:00:00Z")}  # 30h → LATE
    rep = assess_liveness([_spec("a", max_age=24.0, critical=True)], obs, NOW)
    assert rep.checks[0].status == LATE
    assert rep.overall == DEGRADED
    assert rep.exit_code == 0


def test_overall_is_worst_across_checks():
    obs = {
        "fresh": _md("2026-06-13T06:00:00Z"),  # OK
        "info_stale": _md("2026-06-11T00:00:00Z"),  # 연구 STALE → DEGRADED
        "crit_stale": _md("2026-06-10T00:00:00Z"),  # 핵심 STALE → CRITICAL
    }
    specs = [
        _spec("fresh", max_age=24.0, critical=True),
        _spec("info_stale", max_age=24.0, critical=False),
        _spec("crit_stale", max_age=24.0, critical=True),
    ]
    rep = assess_liveness(specs, obs, NOW)
    assert rep.overall == CRITICAL


def test_all_fresh_is_healthy():
    obs = {
        "a": _md("2026-06-13T06:00:00Z"),
        "b": _md("2026-06-13T00:00:00Z"),
    }
    specs = [_spec("a"), _spec("b", critical=False)]
    rep = assess_liveness(specs, obs, NOW)
    assert rep.overall == HEALTHY
    assert rep.exit_code == 0


# ── 직렬화 ──


def test_as_dict_shape():
    obs = {"a": _md("2026-06-13T06:00:00Z")}
    rep = assess_liveness([_spec("a")], obs, NOW)
    d = rep.as_dict()
    assert d["schema_version"] == SCHEMA_VERSION
    assert d["overall"] == HEALTHY
    assert d["checks"][0]["key"] == "a"
    assert d["checks"][0]["age_hours"] == 6.0


def test_as_text_flags_critical_and_safety_note():
    obs = {"a": _md("2026-06-10T00:00:00Z")}  # 핵심 STALE
    rep = assess_liveness([_spec("a", max_age=24.0, critical=True)], obs, NOW)
    txt = rep.as_text()
    assert "CRITICAL" in txt
    assert "핵심 사이드카 정지" in txt
    assert "운영자 게이트" in txt  # 안전 문구


def test_as_text_healthy_message():
    obs = {"a": _md("2026-06-13T06:00:00Z")}
    rep = assess_liveness([_spec("a")], obs, NOW)
    assert "정상 가동" in rep.as_text()


# ── 기본 레지스트리 ──


def test_default_specs_registry_sane():
    specs = default_specs()
    keys = {s.key for s in specs}
    # 자율 머니루프의 직접 경로는 반드시 핵심으로 등록돼 있어야 한다.
    assert {"rebalance-paper-forward", "edge-autoarm", "kis-smoke"} <= keys
    by_key = {s.key: s for s in specs}
    assert by_key["rebalance-paper-forward"].critical is True
    assert by_key["edge-autoarm"].critical is True
    # 연구/보고 트랙은 비핵심(저하로만).
    assert by_key["regime-stratify"].critical is False
    assert by_key["collect-public-data"].critical is False
    # 스펙 052 — 첫-자본까지의 길 보고자도 감시 대상(감시자가 보고자를 감시, 비핵심).
    assert by_key["money-path"].critical is False
    # 스펙 067 — 영구 자율 성장 루프도 감시 대상. 실패는 가시성 저하이지 돈 이동 아님.
    assert "autonomous-evolution" in keys
    assert by_key["autonomous-evolution"].critical is False
    assert by_key["autonomous-evolution"].branch == "automation/autonomous-evolution-last-run"
    # 스펙 068 — 후보를 검증 단계로 분류하는 승격 루프. 직접 돈 이동은 없으므로 비핵심.
    assert "autonomous-promotion" in keys
    assert by_key["autonomous-promotion"].critical is False
    assert by_key["autonomous-promotion"].branch == "automation/autonomous-promotion-last-run"
    # 스펙 070 — BACKTEST_REQUIRED 후보를 검증 패키지와 enriched backlog로 변환하는
    # 공장도 promotion scan 앞단에서 침묵 정지가 드러나야 한다. 돈 이동은 없으므로 비핵심.
    assert "candidate-implementation-factory" in keys
    assert by_key["candidate-implementation-factory"].critical is False
    assert (
        by_key["candidate-implementation-factory"].branch
        == "automation/candidate-implementation-factory-last-run"
    )
    # 스펙 071 — 후보 패키지를 실제 result evidence 로 바꾸는 루프도 감시 대상.
    # 실패해도 돈 경로는 fail-closed 라 비핵심이지만, 침묵 정지는 드러나야 한다.
    assert "candidate-result-executor" in keys
    assert by_key["candidate-result-executor"].critical is False
    assert (
        by_key["candidate-result-executor"].branch
        == "automation/candidate-implementation-results"
    )
    # 스펙 079 — 완료 후보 소비 장부. 정지하면 같은 완료 후보를 반복 선택할 수 있으나
    # 돈 이동 경로는 아니므로 비핵심 감시로 드러낸다.
    assert "released-work" in keys
    assert by_key["released-work"].critical is False
    assert by_key["released-work"].branch == "automation/released-work-last-run"
    # 스펙 069 — 승격 실행 루프와 promotion 전용 검증 채널도 감시 대상.
    # 돈 이동은 기존 게이트만 담당하므로 비핵심이지만, 침묵 정지는 드러나야 한다.
    assert "autonomous-promotion-actions" in keys
    assert by_key["autonomous-promotion-actions"].critical is False
    assert (
        by_key["autonomous-promotion-actions"].branch
        == "automation/autonomous-promotion-actions-last-run"
    )
    assert "promotion-forward" in keys
    assert by_key["promotion-forward"].critical is False
    assert by_key["promotion-forward"].branch == "automation/promotion-forward-last-run"
    assert by_key["promotion-forward"].max_age_hours >= 72.0
    assert "promotion-canary" in keys
    assert by_key["promotion-canary"].critical is False
    assert by_key["promotion-canary"].branch == "automation/promotion-canary-last-run"
    assert by_key["promotion-canary"].max_age_hours >= 72.0
    # 스펙 055 — 자율 전략 재지정 폐회로(평일 스케줄)도 감시 대상이어야 한다.
    # 정지 시 검증된 incumbent 가 그대로 라이브로 남는 fail-safe 라 비핵심(저하만,
    # 빨강 아님) — 단 가장 최신 자율 루프의 침묵 정지는 반드시 드러나야 한다.
    assert "reassign" in keys
    assert by_key["reassign"].critical is False
    assert by_key["reassign"].branch == "automation/reassign-last-run"
    assert by_key["reassign"].max_age_hours >= 72.0  # 주말 갭(Sat→Tue 72h) 견딤
    # 첫 cron(2026-06-17) 전엔 사이드카 없음이 정상(PENDING) — 거짓 DEGRADED 방지.
    assert by_key["reassign"].first_expected_utc is not None
    # 모든 명세는 양수 한계와 automation 브랜치를 가진다.
    for s in specs:
        assert s.max_age_hours > 0
        assert s.branch.startswith("automation/")


def test_reassign_loop_pending_before_first_run_is_not_alarm():
    """스펙 055 재지정 루프는 첫 cron(2026-06-17T00:20Z) 전까지 사이드카가 없는 게
    정상이다. 감시자는 이를 PENDING(첫 실행 대기)으로 보고 거짓 DEGRADED 를 내지
    않아야 한다 — '아직 안 태어난' 루프와 '죽은' 루프를 구분하는 거짓경보 방지 가드."""
    specs = default_specs()
    # NOW(2026-06-13)는 reassign 첫 실행 예정(2026-06-17T00:20Z) 전.
    fresh = _md("2026-06-13T11:00:00Z")  # 1h 전 — 모든 한계 안
    obs: dict[str, str | None] = {s.key: fresh for s in specs}
    obs["reassign"] = None  # 첫 실행 전 — 아직 안 태어남(정상)
    rep = assess_liveness(specs, obs, NOW)
    by_key = {c.key: c for c in rep.checks}
    assert by_key["reassign"].status == PENDING
    assert rep.overall == HEALTHY  # 첫 실행 전은 거짓경보 아님 — 종합 정상
    assert rep.exit_code == 0


def test_reassign_loop_silent_stall_after_first_run_is_degraded_not_red():
    """재지정 루프가 첫 실행 예정 시각 + 한계(80h)를 지나도 사이드카가 없으면(첫 실행
    실패 또는 이후 침묵 정지) 감시자가 MISSING 으로 *드러내되* 거짓 빨강(CRITICAL)은
    내지 않아야 한다 — 정지 시 검증된 incumbent 가 라이브로 남는 fail-safe 이므로."""
    specs = default_specs()
    # reassign 첫 실행 예정(2026-06-17T00:20Z) + 한계 80h(=2026-06-20T08:20Z) 후.
    now_after = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)
    fresh = _md("2026-06-21T11:00:00Z")  # 1h 전 — 모든 한계 안
    obs: dict[str, str | None] = {s.key: fresh for s in specs}
    obs["reassign"] = None  # 첫 실행 예정+한계 지났는데도 미발행 — 침묵 정지
    rep = assess_liveness(specs, obs, now_after)
    by_key = {c.key: c for c in rep.checks}
    assert by_key["reassign"].status == MISSING
    assert rep.overall == DEGRADED  # 빨강(CRITICAL) 아님 — 핵심 루프는 전부 신선
    assert rep.exit_code == 0  # 워크플로를 빨갛게 실패시키지 않는다(거짓경보 방지)
    assert rep.overall != HEALTHY  # 그래도 정지가 *드러난다*


# ── 신규 루프 PENDING/MISSING 구분(first_expected_utc) ──


def test_pending_before_first_expected_is_healthy_contribution():
    """first_expected_utc 가 미래면 사이드카 없음은 PENDING(정상) — 경보 기여 안 함."""
    spec = SidecarSpec(
        key="newloop",
        branch="automation/newloop-last-run",
        filename="LAST_RUN.md",
        max_age_hours=80.0,
        critical=False,
        description="갓 등록된 루프",
        first_expected_utc="2026-06-20T00:00:00Z",  # NOW(6/13) 보다 미래
    )
    rep = assess_liveness([spec], {"newloop": None}, NOW)
    assert rep.checks[0].status == PENDING
    assert rep.checks[0].age_hours is None
    assert rep.overall == HEALTHY
    assert rep.exit_code == 0


def test_missing_after_first_expected_plus_limit_is_flagged():
    """first_expected_utc + max_age 를 지나도 사이드카 없으면 MISSING(첫 실행 실패 의심)."""
    spec = SidecarSpec(
        key="newloop",
        branch="automation/newloop-last-run",
        filename="LAST_RUN.md",
        max_age_hours=24.0,
        critical=False,
        description="갓 등록된 루프",
        first_expected_utc="2026-06-10T00:00:00Z",  # NOW(6/13 12:00)와 ≈84h 차 > 24h
    )
    rep = assess_liveness([spec], {"newloop": None}, NOW)
    assert rep.checks[0].status == MISSING
    assert "첫 실행 실패 의심" in rep.checks[0].detail


def test_critical_new_loop_missing_after_first_expected_is_critical():
    """핵심 신규 루프가 첫 실행 예정+한계 후에도 없으면 MISSING→CRITICAL(빨강)."""
    spec = SidecarSpec(
        key="newloop",
        branch="automation/newloop-last-run",
        filename="LAST_RUN.md",
        max_age_hours=24.0,
        critical=True,
        description="갓 등록된 핵심 루프",
        first_expected_utc="2026-06-10T00:00:00Z",
    )
    rep = assess_liveness([spec], {"newloop": None}, NOW)
    assert rep.checks[0].status == MISSING
    assert rep.overall == CRITICAL
    assert rep.exit_code == 1


def test_established_loop_missing_is_immediately_flagged():
    """first_expected_utc=None(확립된 루프)면 사이드카 없음은 즉시 MISSING(기존 동작 회귀)."""
    spec = SidecarSpec(
        key="oldloop",
        branch="automation/oldloop-last-run",
        filename="LAST_RUN.md",
        max_age_hours=24.0,
        critical=False,
        description="확립된 루프",
    )
    rep = assess_liveness([spec], {"oldloop": None}, NOW)
    assert rep.checks[0].status == MISSING
    assert "미발행 또는 비정상" in rep.checks[0].detail

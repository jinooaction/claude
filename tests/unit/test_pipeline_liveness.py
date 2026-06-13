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
    # 모든 명세는 양수 한계와 automation 브랜치를 가진다.
    for s in specs:
        assert s.max_age_hours > 0
        assert s.branch.startswith("automation/")

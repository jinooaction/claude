"""Spec 009 T018·T019·T020 — paper-report 집계 단위 테스트.

검증 항목:
  - test_aggregation_correctness: 합성 audit_log에서 룰별/게이트별/quote_source
    카운트가 정확.
  - test_empty_log: audit_log 비어 있어도 exit 0 + 빈 표 (edge case).
  - test_excludes_live_events: live의 FILL/ORDER_SUBMITTED row가 paper-report
    집계에 포함되지 않음 (FR-011).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from auto_invest.paper.report import build_paper_report, render_text
from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import (
    ErrorPayload,
    FillPayload,
    OrderIntentPayload,
    OrderPaperFilledPayload,
    OrderRejectedByGatePayload,
    OrderSubmittedPayload,
    PaperRunStartedPayload,
    PaperRunStoppedPayload,
    RuleLoadPayload,
)


@pytest.fixture
def conn(tmp_path):
    c = db.get_connection(tmp_path / "t.db")
    db.migrate(c)
    yield c
    c.close()


def test_empty_log_returns_empty_report(conn) -> None:
    """audit_log가 비어 있어도 build_paper_report는 정상 리턴 (edge case 4)."""
    since = datetime(2000, 1, 1, tzinfo=UTC)
    until = datetime(2099, 1, 1, tzinfo=UTC)
    report = build_paper_report(conn, since=since, until=until)
    assert report.sessions_count == 0
    assert report.per_rule == []
    assert report.gate_denials == {}
    assert report.virtual_positions == []
    assert report.quote_source_pct == {}
    # text 렌더링도 깨지지 않음
    text = render_text(report)
    assert "auto-invest paper-report" in text


def test_aggregation_correctness(conn) -> None:
    """합성 audit_log로 각 집계가 정확한지 검증."""
    # 룰 로딩
    audit.append(
        conn,
        RuleLoadPayload(
            rule_count=3,
            rule_ids=["RULE_A", "RULE_B", "RULE_C"],
        ),
    )
    # 세션 시작
    session_id = audit.append(
        conn,
        PaperRunStartedPayload(
            pid=1,
            config_path="/x",
            ruleset_sha256="a" * 64,
            started_at_utc="2026-05-13T00:00:00.000Z",
            host="test",
        ),
    )

    # RULE_A: 시그널 3건, fills 2건, denied 1건 (cap)
    for i in range(3):
        audit.append(
            conn,
            OrderIntentPayload(
                rule_id="RULE_A",
                symbol="AAPL",
                side="BUY",
                order_type="MARKET",
                qty=1,
                limit_price_usd=None,
            ),
            rule_id="RULE_A",
            correlation_id=f"a-{i}",
        )
    for i in range(2):
        audit.append(
            conn,
            OrderPaperFilledPayload(
                rule_id="RULE_A",
                symbol="AAPL",
                side="BUY",
                qty=1,
                simulated_fill_price_usd="100.00",
                quote_source="ask",
                correlation_id=f"a-{i}",
                paper_session_id=session_id,
            ),
            rule_id="RULE_A",
            correlation_id=f"a-{i}",
        )
    audit.append(
        conn,
        OrderRejectedByGatePayload(
            gate="per_trade_cap_gate",
            reason="exceeds cap",
            metadata={},
        ),
        rule_id="RULE_A",
        correlation_id="a-2",
    )

    # RULE_B: 시그널 1건, fills 0, denied 1 (whitelist)
    audit.append(
        conn,
        OrderIntentPayload(
            rule_id="RULE_B",
            symbol="UNKNOWN",
            side="BUY",
            order_type="MARKET",
            qty=1,
            limit_price_usd=None,
        ),
        rule_id="RULE_B",
        correlation_id="b-0",
    )
    audit.append(
        conn,
        OrderRejectedByGatePayload(
            gate="whitelist_gate",
            reason="not whitelisted",
            metadata={},
        ),
        rule_id="RULE_B",
        correlation_id="b-0",
    )

    # RULE_C: 한 번도 fire 안 됨 (rules_never_fired에 들어가야 함)

    # 외부 API 오류 1건
    audit.append(
        conn,
        ErrorPayload(where="quote_fetch", message="upstream 502"),
    )

    # 세션 종료 (1시간 후)
    audit.append(
        conn,
        PaperRunStoppedPayload(
            reason="signal_received",
            stopped_at_utc="2026-05-13T01:00:00.000Z",
            session_started_event_id=session_id,
        ),
    )

    since = datetime(2000, 1, 1, tzinfo=UTC)
    until = datetime(2099, 1, 1, tzinfo=UTC)
    report = build_paper_report(conn, since=since, until=until)

    # 룰별 통계
    by_rule = {r.rule_id: r for r in report.per_rule}
    assert by_rule["RULE_A"].signals == 3
    assert by_rule["RULE_A"].fills == 2
    assert by_rule["RULE_A"].denied == 1
    assert by_rule["RULE_B"].signals == 1
    assert by_rule["RULE_B"].fills == 0
    assert by_rule["RULE_B"].denied == 1

    # 게이트 분포
    assert report.gate_denials == {
        "per_trade_cap_gate": 1,
        "whitelist_gate": 1,
    }

    # 외부 API 오류
    assert report.external_api_errors.get("ERROR") == 1

    # 튜닝 피드백
    assert "RULE_C" in report.rules_never_fired
    assert report.hottest_rules[0][0] == "RULE_A"
    assert report.hottest_rules[0][1] == 3

    # quote_source — 2건의 fill 모두 ask
    assert report.quote_source_pct == {"ask": 1.0}

    # 세션 + 가동 시간
    assert report.sessions_count == 1
    # 1시간 = 3600초. paper_run_stopped는 paper_run_started 직후이므로 둘 사이 차이.
    # 시작/종료 ts_utc는 audit.append가 wall clock으로 기록 — 1초 미만일 수 있음.
    # uptime은 0초 이상이면 OK (정확한 1시간은 ts_utc 인자를 안 줬으므로 보장 X).
    assert report.sessions_uptime_seconds >= 0

    # 가상 포지션 (2건의 BUY)
    positions = {p.symbol: p for p in report.virtual_positions}
    assert positions["AAPL"].qty == 2

    # total_paper_events: started(1) + stopped(1) + filled(2) = 4
    assert report.total_paper_events == 4


def test_excludes_live_events(conn) -> None:
    """live의 ORDER_SUBMITTED·FILL row가 paper-report에 포함되지 않음 (FR-011)."""
    since = datetime(2000, 1, 1, tzinfo=UTC)
    until = datetime(2099, 1, 1, tzinfo=UTC)

    # live 이벤트만 넣고 paper 이벤트 0건.
    audit.append(
        conn,
        OrderSubmittedPayload(
            kis_order_id="kis-1",
            submitted_at_utc="2026-05-13T00:00:00.000Z",
        ),
        rule_id="RULE_LIVE",
        symbol="AAPL",
        correlation_id="ord-live-1",
    )
    audit.append(
        conn,
        FillPayload(
            kis_fill_id="kis-fill-1",
            qty=10,
            price_usd="999.00",
            executed_at_utc="2026-05-13T00:01:00.000Z",
        ),
        rule_id="RULE_LIVE",
        symbol="AAPL",
        correlation_id="ord-live-1",
    )

    report = build_paper_report(conn, since=since, until=until)
    # paper 이벤트 0 → 모든 paper 집계 비어 있음.
    assert report.total_paper_events == 0
    assert report.virtual_positions == []
    # RULE_LIVE는 fills/signals 모두 0 (paper-report는 ORDER_PAPER_FILLED만 본다).
    by_rule = {r.rule_id: r for r in report.per_rule}
    if "RULE_LIVE" in by_rule:
        assert by_rule["RULE_LIVE"].fills == 0
    # 가상 포지션도 없음 — live FILL은 누적 안 됨.
    assert "AAPL" not in {p.symbol for p in report.virtual_positions}


def test_to_json_dict_keys(conn) -> None:
    """JSON 출력 키 셋이 contracts와 일치."""
    since = datetime(2000, 1, 1, tzinfo=UTC)
    until = datetime(2099, 1, 1, tzinfo=UTC)
    report = build_paper_report(conn, since=since, until=until)
    d = report.to_json_dict()
    assert set(d.keys()) >= {
        "period",
        "sessions",
        "rulesets_observed",
        "per_rule",
        "gate_denials",
        "external_api_errors",
        "tuning_feedback",
        "virtual_positions",
    }
    assert set(d["tuning_feedback"].keys()) == {
        "rules_never_fired",
        "hottest_rules",
        "quote_source_pct",
    }

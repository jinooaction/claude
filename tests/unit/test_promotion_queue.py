"""캐너리 합격 후보 운영자 승격 큐 단위 테스트.

순수 함수(assess_promotion_queue)의 집계·최신 판정 우선·정렬·카운트와, 감사 로그를
읽어 종합하는 편의 함수(build_promotion_queue)를 실제 SQLite 로 검증한다.
"""

from __future__ import annotations

from datetime import UTC, datetime

from auto_invest.analytics.promotion_queue import (
    EVENT_CANDIDATE,
    EVENT_VALIDATED,
    OUTCOME_ERROR,
    OUTCOME_FAILED,
    OUTCOME_PASSED,
    OUTCOME_SKIPPED,
    PromotionQueueReport,
    assess_promotion_queue,
    build_promotion_queue,
    load_canary_events,
)

NOW = datetime(2026, 6, 18, 8, 0, 0, tzinfo=UTC)


def _candidate(
    cid="cand-1",
    session="2026-06-18",
    rule="latency_degradation",
    tier="L2",
    target="config/judgment_tunables.toml",
    key="daily_summary.max_tokens",
    old="700",
    new="560",
    rec_tier="L2",
    window=7,
):
    return {
        "event_type": EVENT_CANDIDATE,
        "session_date": session,
        "candidate_id": cid,
        "detection_rule": rule,
        "authority_tier": tier,
        "target_path": target,
        "config_key": key,
        "old_value": old,
        "new_value": new,
        "recommended_tier": rec_tier,
        "recommended_window_days": window,
    }


def _validation(
    cid="cand-1",
    session="2026-06-18",
    outcome=OUTCOME_PASSED,
    run_id="canary-123",
    failing=None,
    skip=None,
):
    return {
        "event_type": EVENT_VALIDATED,
        "session_date": session,
        "candidate_id": cid,
        "outcome": outcome,
        "canary_run_id": run_id,
        "candidate_rev": "abc123",
        "baseline_rev": "def456",
        "failing_metrics": failing or [],
        "skip_reason": skip,
        "promoted": False,
    }


def test_empty_inputs_give_empty_queue():
    rep = assess_promotion_queue(candidates=[], validations=[], now=NOW)
    assert isinstance(rep, PromotionQueueReport)
    assert rep.queue == []
    assert rep.passed_pending == 0
    assert rep.failed == rep.skipped == rep.errored == 0
    assert "후보 자체가 없음" in rep.headline


def test_single_passed_enters_queue_with_change_detail():
    rep = assess_promotion_queue(
        candidates=[_candidate()],
        validations=[_validation()],
        now=NOW,
    )
    assert rep.passed_pending == 1
    (item,) = rep.queue
    assert item.candidate_id == "cand-1"
    assert item.authority_tier == "L2"
    assert item.config_key == "daily_summary.max_tokens"
    assert item.old_value == "700"
    assert item.new_value == "560"
    assert item.recommended_window_days == 7
    assert item.canary_run_id == "canary-123"
    assert item.validated_session_date == "2026-06-18"


def test_revalidation_latest_outcome_wins():
    # 같은 후보가 합격(이른 세션) 후 재검증에서 불합격(늦은 세션) → 최신(불합격)이 이긴다.
    rep = assess_promotion_queue(
        candidates=[_candidate()],
        validations=[
            _validation(session="2026-06-10", outcome=OUTCOME_PASSED),
            _validation(session="2026-06-18", outcome=OUTCOME_FAILED, failing=["calmar"]),
        ],
        now=NOW,
    )
    assert rep.passed_pending == 0
    assert rep.failed == 1
    assert rep.queue == []


def test_mixed_outcomes_are_counted_separately():
    rep = assess_promotion_queue(
        candidates=[
            _candidate(cid="p1"),
            _candidate(cid="f1"),
            _candidate(cid="s1"),
            _candidate(cid="e1"),
        ],
        validations=[
            _validation(cid="p1", outcome=OUTCOME_PASSED),
            _validation(cid="f1", outcome=OUTCOME_FAILED),
            _validation(cid="s1", outcome=OUTCOME_SKIPPED, skip="no_replay_data"),
            _validation(cid="e1", outcome=OUTCOME_ERROR),
        ],
        now=NOW,
    )
    assert rep.passed_pending == 1
    assert rep.failed == 1
    assert rep.skipped == 1
    assert rep.errored == 1
    assert [i.candidate_id for i in rep.queue] == ["p1"]


def test_promoted_ids_excluded_from_queue():
    rep = assess_promotion_queue(
        candidates=[_candidate(cid="p1"), _candidate(cid="p2")],
        validations=[
            _validation(cid="p1", outcome=OUTCOME_PASSED),
            _validation(cid="p2", outcome=OUTCOME_PASSED),
        ],
        promoted_ids={"p1"},
        now=NOW,
    )
    # p1 은 이미 승격됨 → 대기 아님. p2 만 큐에.
    assert [i.candidate_id for i in rep.queue] == ["p2"]
    assert rep.passed_pending == 1


def test_queue_sorted_deterministically():
    # 검증일 → 후보 id 순. 입력 순서가 달라도 같은 정렬을 낸다(재현성).
    val_a = _validation(cid="b", session="2026-06-10", outcome=OUTCOME_PASSED)
    val_b = _validation(cid="a", session="2026-06-18", outcome=OUTCOME_PASSED)
    cands = [_candidate(cid="a"), _candidate(cid="b")]
    rep1 = assess_promotion_queue(candidates=cands, validations=[val_a, val_b], now=NOW)
    rep2 = assess_promotion_queue(candidates=cands, validations=[val_b, val_a], now=NOW)
    order1 = [i.candidate_id for i in rep1.queue]
    assert order1 == ["b", "a"]  # 2026-06-10(b) 먼저, 그 다음 2026-06-18(a)
    assert order1 == [i.candidate_id for i in rep2.queue]
    assert rep1.to_dict() == rep2.to_dict()


def test_passed_without_candidate_detail_is_robust():
    # VALIDATED 는 있는데 CANDIDATE 상세가 없는 비정상 케이스 — 보수적으로 표시하되 큐에 남긴다.
    rep = assess_promotion_queue(
        candidates=[],
        validations=[_validation(cid="orphan", outcome=OUTCOME_PASSED)],
        now=NOW,
    )
    assert rep.passed_pending == 1
    (item,) = rep.queue
    assert item.candidate_id == "orphan"
    assert item.old_value == "(상세 불명)"


def test_to_dict_and_text_carry_safety_note():
    rep = assess_promotion_queue(
        candidates=[_candidate()], validations=[_validation()], now=NOW
    )
    d = rep.to_dict()
    assert d["counts"]["passed_pending"] == 1
    assert d["queue"][0]["promotion"] == "operator-gated (spec 006); NOT auto-promoted"
    text = rep.as_text()
    assert "IX.B-2" in text  # 자동 승격 0 불변 명시
    assert "700 → 560" in text  # 변경 내용 표면화
    assert "승격 대기" in text


# ── build_promotion_queue: 실제 감사 로그를 읽어 종합 ──


def _seed_db(tmp_path):
    from auto_invest.persistence import db
    from auto_invest.persistence.audit import (
        AutoTunedCanaryCandidatePayload,
        AutoTunedCanaryValidatedPayload,
        append,
    )

    conn = db.get_connection(tmp_path / "t.db")
    db.migrate(conn)
    append(
        conn,
        AutoTunedCanaryCandidatePayload(
            session_date="2026-06-18",
            candidate_id="cand-1",
            detection_rule="latency_degradation",
            authority_tier="L2",
            target_path="config/judgment_tunables.toml",
            config_key="daily_summary.max_tokens",
            old_value="700",
            new_value="560",
            recommended_tier="L2",
            recommended_window_days=7,
        ),
    )
    append(
        conn,
        AutoTunedCanaryValidatedPayload(
            session_date="2026-06-18",
            candidate_id="cand-1",
            outcome=OUTCOME_PASSED,
            canary_run_id="canary-xyz",
        ),
    )
    conn.commit()
    return conn


def test_build_promotion_queue_reads_audit_log(tmp_path):
    conn = _seed_db(tmp_path)
    try:
        candidates, validations = load_canary_events(conn)
        assert len(candidates) == 1
        assert len(validations) == 1
        rep = build_promotion_queue(conn, now=NOW)
    finally:
        conn.close()
    assert rep.passed_pending == 1
    (item,) = rep.queue
    assert item.candidate_id == "cand-1"
    assert item.new_value == "560"
    assert item.canary_run_id == "canary-xyz"

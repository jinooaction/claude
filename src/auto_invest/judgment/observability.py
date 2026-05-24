"""판단 지점 관측 집계 (US4 / FR-040).

audit_log 에서 판단 지점별 호출 수·자문 적용 수·폴백 수·폴백률을 윈도 단위로
집계한다. efficiency 명령이 token_usage 기반 비용/지연 분해(per_decision_class)에
더해 이 판단-특화 신호를 함께 노출한다.
"""

from __future__ import annotations

import json
import sqlite3

from auto_invest.judgment import registry

_JUDGMENT_EVENTS = ("LLM_CALL", "JUDGMENT_ADVISORY_APPLIED", "JUDGMENT_FALLBACK")


def judgment_efficiency(
    conn: sqlite3.Connection,
    *,
    window_start_utc: str,
    window_end_utc: str,
) -> dict[str, dict[str, object]]:
    """판단 지점 decision_class 별 {llm_calls, advisories_applied, fallbacks,
    fallback_rate} 를 반환. fallback_rate 는 (적용+폴백) 중 폴백 비율(없으면 None).
    """
    classes = set(registry.decision_classes())
    stats: dict[str, dict[str, int]] = {
        c: {"llm_calls": 0, "advisories_applied": 0, "fallbacks": 0} for c in classes
    }

    rows = conn.execute(
        """
        SELECT event_type, payload_json
        FROM audit_log
        WHERE ts_utc >= ? AND ts_utc < ? AND event_type IN (?, ?, ?)
        """,
        (window_start_utc, window_end_utc, *_JUDGMENT_EVENTS),
    ).fetchall()

    for row in rows:
        try:
            payload = json.loads(row["payload_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        dc = payload.get("decision_class")
        if dc not in stats:
            continue
        et = row["event_type"]
        if et == "LLM_CALL":
            stats[dc]["llm_calls"] += 1
        elif et == "JUDGMENT_ADVISORY_APPLIED":
            stats[dc]["advisories_applied"] += 1
        elif et == "JUDGMENT_FALLBACK":
            stats[dc]["fallbacks"] += 1

    out: dict[str, dict[str, object]] = {}
    for dc, s in stats.items():
        decided = s["advisories_applied"] + s["fallbacks"]
        rate = round(s["fallbacks"] / decided, 4) if decided > 0 else None
        out[dc] = {**s, "fallback_rate": rate}
    return out

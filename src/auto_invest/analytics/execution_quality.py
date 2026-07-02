"""스펙 083 — 주문 거부·체결 품질 실행 품질 패키지.

이미 발행된 sidecar만 읽어 거부 주문 손익, 브로커 거부 코드, KIS smoke 상태를
하나의 읽기 전용 보고로 묶는다. 브로커 API, 주문, 자본, live 설정은 사용하지 않는다.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "1.0"

PARSE_OK = "ok"
PARSE_PRESENT = "present"
PARSE_MISSING = "missing"
PARSE_MALFORMED = "malformed"

OVERALL_OBSERVE = "OBSERVE"
OVERALL_STRATEGY_REVIEW = "STRATEGY_REVIEW"
OVERALL_EXECUTION_REVIEW = "EXECUTION_REVIEW"
OVERALL_MISSING_EVIDENCE = "MISSING_EVIDENCE"

SOURCE_REFS: dict[str, str] = {
    "opportunity-monitor": "automation/rebalance-micro-gtaa-last-run:opportunity_monitor.json",
    "opportunity-history": "automation/rebalance-micro-gtaa-last-run:opportunity_history.json",
    "rebalance-micro-gtaa": "automation/rebalance-micro-gtaa-last-run:LAST_RUN.md",
    "kis-smoke": "automation/kis-smoke-last-run:LAST_RUN.md",
}

SAFETY_INVARIANTS: tuple[str, ...] = (
    "no broker API call",
    "no orders",
    "no capital allocation",
    "no live strategy change",
    "no whitelist/caps change",
    "no secret read/write",
    "no external paid service",
    "execution-quality evidence package only",
)

_TS_RE = re.compile(
    r"timestamp_utc[^0-9]*?(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)"
)


@dataclass(frozen=True)
class EvidenceSurface:
    """입력 sidecar 한 개의 존재·파싱 상태."""

    key: str
    source_ref: str
    present: bool
    parse_status: str
    summary_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "source_ref": self.source_ref,
            "present": self.present,
            "parse_status": self.parse_status,
            "summary_ko": self.summary_ko,
        }


@dataclass(frozen=True)
class ExecutionQualityReport:
    """실행 품질 패키지 최종 보고."""

    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    opportunity_monitor: Mapping[str, Any]
    broker_rejections: Mapping[str, Any]
    broker_smoke: Mapping[str, Any]
    live_gate: Mapping[str, Any]
    evidence_surfaces: tuple[EvidenceSurface, ...]
    safety_invariants: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "commit": self.commit,
            "timestamp_utc": self.timestamp_utc,
            "overall_status": self.overall_status,
            "opportunity_monitor": dict(self.opportunity_monitor),
            "broker_rejections": dict(self.broker_rejections),
            "broker_smoke": dict(self.broker_smoke),
            "live_gate": dict(self.live_gate),
            "evidence_surfaces": [surface.to_dict() for surface in self.evidence_surfaces],
            "safety_invariants": list(self.safety_invariants),
        }

    def as_markdown(self) -> str:
        monitor = self.opportunity_monitor
        rejections = self.broker_rejections
        smoke = self.broker_smoke
        lines = [
            f"# 실행 품질 패키지 (as of {self.timestamp_utc})",
            "",
            "읽기 전용 보고입니다. 이미 발행된 sidecar만 읽어 실행 품질 증거를 묶습니다.",
            "주문, 자본, whitelist, caps, live 전략은 변경하지 않았습니다.",
            "",
            "## 종합 판정",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| overall_status | {self.overall_status} |",
            f"| monitor_verdict | {_table(monitor.get('verdict'))} |",
            f"| latest_signal | {_table(monitor.get('latest_signal'))} |",
            f"| cumulative_pnl_usd | {_table(monitor.get('cumulative_pnl_usd'))} |",
            f"| next_action_ko | {_table(monitor.get('next_action_ko'))} |",
            "",
            "## 브로커 거부 관측",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| rejected_orders | {rejections.get('rejected_orders')} |",
            f"| parsed_broker_errors | {rejections.get('parsed_broker_errors')} |",
            f"| unparsed_reasons | {rejections.get('unparsed_reasons')} |",
            f"| broker_error_observation_rate | "
            f"{_table(rejections.get('broker_error_observation_rate'))} |",
            f"| kis_msg_codes | {_table(rejections.get('kis_msg_codes'))} |",
            "",
            "## KIS smoke",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| present | {smoke.get('present')} |",
            f"| smoke_state | {_table(smoke.get('smoke_state'))} |",
            f"| smoke_exit | {_table(smoke.get('smoke_exit'))} |",
            f"| tests_total | {_table(smoke.get('tests_total'))} |",
            f"| tests_failed | {_table(smoke.get('tests_failed'))} |",
            f"| smoke_error_rate | {_table(smoke.get('smoke_error_rate'))} |",
            "",
            "## 입력 증거",
            "",
            "| 증거 | 존재 | 파싱 | 요약 |",
            "|------|:----:|------|------|",
        ]
        for surface in self.evidence_surfaces:
            present = "yes" if surface.present else "no"
            lines.append(
                f"| {surface.key} | {present} | {surface.parse_status} | "
                f"{_table(surface.summary_ko)} |"
            )
        lines += ["", "## 안전 경계", ""]
        for invariant in self.safety_invariants:
            lines.append(f"- {invariant}")
        lines += ["", "## 결정 JSON", "", "```json"]
        lines.append(json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        lines.append("```")
        return "\n".join(lines)


def build_execution_quality(
    evidence_texts: Mapping[str, str | None],
    *,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> ExecutionQualityReport:
    """이미 수집된 sidecar 원문으로 실행 품질 보고를 만든다."""

    now = _as_utc(now)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    monitor_doc = _json_dict(evidence_texts.get("opportunity-monitor"))
    history_doc = _json_dict(evidence_texts.get("opportunity-history"))
    live_gate = _live_gate_summary(evidence_texts.get("rebalance-micro-gtaa"))
    smoke = _broker_smoke_summary(evidence_texts.get("kis-smoke"))
    monitor = _opportunity_monitor_summary(monitor_doc)
    rejections = _broker_rejection_summary(history_doc)
    surfaces = (
        _surface(
            "opportunity-monitor",
            evidence_texts.get("opportunity-monitor"),
            monitor_doc,
            _monitor_surface_summary(monitor_doc),
            expect_json=True,
        ),
        _surface(
            "opportunity-history",
            evidence_texts.get("opportunity-history"),
            history_doc,
            _history_surface_summary(history_doc),
            expect_json=True,
        ),
        _surface(
            "rebalance-micro-gtaa",
            evidence_texts.get("rebalance-micro-gtaa"),
            live_gate if live_gate.get("present") else None,
            _live_gate_surface_summary(live_gate),
            expect_json=False,
        ),
        _surface(
            "kis-smoke",
            evidence_texts.get("kis-smoke"),
            smoke if smoke.get("present") else None,
            _smoke_surface_summary(smoke),
            expect_json=False,
        ),
    )
    return ExecutionQualityReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=timestamp,
        overall_status=_overall_status(monitor_doc),
        opportunity_monitor=monitor,
        broker_rejections=rejections,
        broker_smoke=smoke,
        live_gate=live_gate,
        evidence_surfaces=surfaces,
        safety_invariants=SAFETY_INVARIANTS,
    )


def _as_utc(now: datetime) -> datetime:
    return now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)


def _json_dict(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _surface(
    key: str,
    raw: str | None,
    parsed: Any,
    summary_ko: str,
    *,
    expect_json: bool,
) -> EvidenceSurface:
    if raw is None:
        return EvidenceSurface(key, SOURCE_REFS[key], False, PARSE_MISSING, "sidecar 없음")
    if expect_json and parsed is None:
        return EvidenceSurface(key, SOURCE_REFS[key], True, PARSE_MALFORMED, "JSON 파싱 실패")
    return EvidenceSurface(
        key=key,
        source_ref=SOURCE_REFS[key],
        present=True,
        parse_status=PARSE_OK if parsed is not None else PARSE_PRESENT,
        summary_ko=summary_ko,
    )


def _opportunity_monitor_summary(doc: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(doc, Mapping):
        return {
            "verdict": "UNKNOWN",
            "latest_signal": "UNKNOWN",
            "cumulative_pnl_usd": None,
            "valued_records": 0,
            "rejected_orders": 0,
            "valued_orders": 0,
            "latest_run_id": None,
            "next_action_ko": "opportunity_monitor.json 증거를 먼저 복구합니다.",
        }
    counts = doc.get("counts") if isinstance(doc.get("counts"), Mapping) else {}
    cumulative = doc.get("cumulative") if isinstance(doc.get("cumulative"), Mapping) else {}
    latest = doc.get("latest") if isinstance(doc.get("latest"), Mapping) else {}
    return {
        "verdict": _clean(doc.get("verdict"), "UNKNOWN"),
        "latest_signal": _clean(doc.get("latest_signal"), "UNKNOWN"),
        "cumulative_pnl_usd": _none_if_blank(
            cumulative.get("total_intended_order_mark_pnl_usd")
        ),
        "valued_records": _int(counts.get("valued_records"), 0),
        "rejected_orders": _int(counts.get("rejected_orders"), 0),
        "valued_orders": _int(counts.get("valued_orders"), 0),
        "latest_run_id": _none_if_blank(latest.get("run_id")),
        "next_action_ko": _clean(doc.get("next_action_ko"), ""),
    }


def _broker_rejection_summary(doc: Mapping[str, Any] | None) -> dict[str, Any]:
    rows = _history_rejected_rows(doc)
    codes: Counter[str] = Counter()
    exceptions: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    parsed_errors = 0
    unparsed = 0
    for row in rows:
        reason = row.get("reason")
        parsed = _json_dict(str(reason)) if reason is not None else None
        if parsed is None:
            unparsed += 1
            continue
        code = _clean(
            parsed.get("kis_msg_cd")
            or _mapping_value(parsed.get("response_json"), "msg_cd")
            or parsed.get("msg_cd")
        )
        exception = _clean(parsed.get("exception_type"))
        http_status = _clean(parsed.get("http_status"))
        if code:
            codes[code] += 1
        if exception:
            exceptions[exception] += 1
        if http_status:
            statuses[http_status] += 1
        if code or exception or http_status:
            parsed_errors += 1
        else:
            unparsed += 1
    rejected_orders = len(rows)
    return {
        "rejected_orders": rejected_orders,
        "parsed_broker_errors": parsed_errors,
        "unparsed_reasons": unparsed,
        "broker_error_observation_rate": _rate(parsed_errors, rejected_orders),
        "kis_msg_codes": dict(sorted(codes.items())),
        "exception_types": dict(sorted(exceptions.items())),
        "http_statuses": dict(sorted(statuses.items())),
    }


def _history_rejected_rows(doc: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(doc, Mapping):
        return []
    records = doc.get("records")
    if not isinstance(records, list):
        return []
    rows: list[Mapping[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        report = record.get("opportunity_report")
        if not isinstance(report, Mapping):
            continue
        raw_rows = report.get("rows")
        if not isinstance(raw_rows, list):
            continue
        for row in raw_rows:
            if not isinstance(row, Mapping):
                continue
            state = _clean(row.get("state")).upper()
            if "REJECTED" in state or row.get("reason"):
                rows.append(row)
    return rows


def _broker_smoke_summary(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {
            "present": False,
            "timestamp_utc": None,
            "smoke_state": "unknown",
            "smoke_exit": None,
            "tests_total": None,
            "tests_failed": None,
            "smoke_error_rate": None,
            "key_valid": None,
        }
    smoke_state = _table_field(raw, "smoke_state") or "unknown"
    smoke_exit = _int_or_none(_table_field(raw, "smoke_exit"))
    key_valid = _bool_or_none(_table_field(raw, "key_valid"))
    tests_total, tests_failed = _pytest_counts(raw, smoke_exit)
    return {
        "present": True,
        "timestamp_utc": parse_timestamp_utc(raw),
        "smoke_state": smoke_state,
        "smoke_exit": smoke_exit,
        "tests_total": tests_total,
        "tests_failed": tests_failed,
        "smoke_error_rate": (
            _rate(tests_failed, tests_total)
            if tests_failed is not None and tests_total is not None
            else None
        ),
        "key_valid": key_valid,
    }


def _live_gate_summary(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {"present": False, "ok": None, "reason": None}
    parsed = _json_after_header(raw, "라이브 전 전략 의도 게이트")
    if not isinstance(parsed, Mapping):
        return {"present": True, "ok": None, "reason": None}
    return {
        "present": True,
        "ok": parsed.get("ok") if isinstance(parsed.get("ok"), bool) else None,
        "reason": _none_if_blank(parsed.get("reason")),
        "verdict": _none_if_blank(parsed.get("verdict")),
        "latest_signal": _none_if_blank(parsed.get("latest_signal")),
        "cumulative_pnl_usd": _none_if_blank(parsed.get("cumulative_pnl_usd")),
    }


def _overall_status(monitor_doc: Mapping[str, Any] | None) -> str:
    if not isinstance(monitor_doc, Mapping):
        return OVERALL_MISSING_EVIDENCE
    verdict = _clean(monitor_doc.get("verdict")).upper()
    if verdict == OVERALL_STRATEGY_REVIEW:
        return OVERALL_STRATEGY_REVIEW
    if verdict == OVERALL_EXECUTION_REVIEW:
        return OVERALL_EXECUTION_REVIEW
    return OVERALL_OBSERVE


def _json_after_header(text: str, header: str) -> dict[str, Any] | None:
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if header in line:
            start = i
            break
    if start is None:
        return None
    in_block = False
    buf: list[str] = []
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if not in_block:
            if stripped.startswith("```"):
                in_block = True
            continue
        if stripped.startswith("```"):
            break
        buf.append(line)
    return _json_dict("\n".join(buf)) if buf else None


def parse_timestamp_utc(text: str | None) -> str | None:
    if not text:
        return None
    match = _TS_RE.search(text)
    return match.group(1) if match else None


def _table_field(text: str, field: str) -> str | None:
    pattern = re.compile(rf"\|\s*{re.escape(field)}\s*\|\s*([^|]+?)\s*\|")
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def _pytest_counts(text: str, smoke_exit: int | None) -> tuple[int | None, int | None]:
    collected = re.search(r"collected\s+(\d+)\s+items?", text)
    total = int(collected.group(1)) if collected else None
    passed = _sum_count(text, "passed")
    failed = _sum_count(text, "failed") + _sum_count(text, "error") + _sum_count(text, "errors")
    if total is None and passed + failed > 0:
        total = passed + failed
    if total is None:
        return None, None
    if failed == 0 and smoke_exit == 0:
        return total, 0
    return total, failed


def _sum_count(text: str, word: str) -> int:
    return sum(int(match.group(1)) for match in re.finditer(rf"\b(\d+)\s+{word}\b", text))


def _monitor_surface_summary(doc: Mapping[str, Any] | None) -> str:
    if not isinstance(doc, Mapping):
        return "monitor JSON 없음 또는 손상"
    return (
        f"verdict={_clean(doc.get('verdict'), 'UNKNOWN')}, "
        f"signal={_clean(doc.get('latest_signal'), 'UNKNOWN')}"
    )


def _history_surface_summary(doc: Mapping[str, Any] | None) -> str:
    if not isinstance(doc, Mapping):
        return "history JSON 없음 또는 손상"
    records = doc.get("records")
    count = len(records) if isinstance(records, list) else 0
    return f"records={count}, rejected_rows={len(_history_rejected_rows(doc))}"


def _live_gate_surface_summary(live_gate: Mapping[str, Any]) -> str:
    if not live_gate.get("present"):
        return "micro GTAA LAST_RUN 없음"
    return f"reason={_clean(live_gate.get('reason'), 'unknown')}"


def _smoke_surface_summary(smoke: Mapping[str, Any]) -> str:
    if not smoke.get("present"):
        return "KIS smoke sidecar 없음"
    return (
        f"state={_clean(smoke.get('smoke_state'), 'unknown')}, "
        f"exit={_clean(smoke.get('smoke_exit'), 'unknown')}"
    )


def _mapping_value(value: Any, key: str) -> Any | None:
    return value.get(key) if isinstance(value, Mapping) else None


def _clean(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _none_if_blank(value: object) -> str | None:
    text = _clean(value)
    return text or None


def _int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _int_or_none(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: object) -> bool | None:
    text = _clean(value).lower()
    if text == "true":
        return True
    if text == "false":
        return False
    return None


def _rate(numerator: int, denominator: int) -> str | None:
    if denominator <= 0:
        return None
    return f"{numerator / denominator:.4f}"


def _table(value: object) -> str:
    if isinstance(value, Mapping):
        text = json.dumps(dict(value), ensure_ascii=False, sort_keys=True)
    else:
        text = "" if value is None else str(value)
    return text.replace("|", "/").replace("\n", " ")


__all__ = [
    "OVERALL_EXECUTION_REVIEW",
    "OVERALL_MISSING_EVIDENCE",
    "OVERALL_OBSERVE",
    "OVERALL_STRATEGY_REVIEW",
    "PARSE_MALFORMED",
    "PARSE_MISSING",
    "PARSE_OK",
    "PARSE_PRESENT",
    "SCHEMA_VERSION",
    "ExecutionQualityReport",
    "EvidenceSurface",
    "build_execution_quality",
    "parse_timestamp_utc",
]

"""스펙 133 — 광역 no-edge 데이터 결측 원인 감사 계약.

선택된 자율 후보 `candidate-broad-no-edge-data-gap-audit`를 공개 데이터
결측과 레짐 조인 품질 관점의 기계 판독 보고서로 고정한다.

안전 경계: 읽기 전용·순수·결정론. 브로커 API, 주문, 자본 배분, live 전략,
whitelist/caps, 비밀값, 헌법/커널, 외부 유료 서비스는 건드리지 않는다.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

SCHEMA_VERSION = "1.0"
AUDIT_ID = "broad-no-edge-data-gap-audit"
COMPLETED_CANDIDATE_ID = "candidate-broad-no-edge-data-gap-audit"
NEXT_CANDIDATE_ID = "wait-for-fresh-evidence"

CONTRACT_READY = "CONTRACT_READY"
OBSERVATION_WAIT = "OBSERVATION_WAIT"
BLOCKED = "BLOCKED"

PARSE_OK = "ok"
PARSE_MISSING = "missing"
PARSE_MALFORMED = "malformed"

GATE_PASS = "PASS"
GATE_WAIT = "WAIT"
GATE_FAIL = "FAIL"

DATA_READY = "DATA_READY"
GAP_DETECTED = "GAP_DETECTED"

IMPACT_LOW = "LOW"
IMPACT_MEDIUM = "MEDIUM"
IMPACT_HIGH = "HIGH"
IMPACT_UNKNOWN = "UNKNOWN"

CANONICAL_LABELS: tuple[str, ...] = ("RISK_ON", "CAUTION", "RISK_OFF")
TIMELINE_COLUMNS: tuple[str, ...] = ("spread", "vix", "inflation_yoy", "sahm_pp")
MIN_TIMELINE_ROWS = 20
MIN_STRATIFIED_OBS = 20

SAFETY_BOUNDARY: tuple[str, ...] = (
    "no broker API call",
    "no orders",
    "no capital allocation",
    "no live strategy change",
    "no whitelist/caps change",
    "no secret read/write",
    "no external paid service",
    "no constitution/kernel change",
    "no fresh external collection",
    "data-gap audit contract only",
)

CONSUMED_SIDECARS: tuple[tuple[str, str, str], ...] = (
    ("public-data-last-run", "automation/public-data", "LAST_RUN.md"),
    ("public-data-summary", "automation/public-data", "summary.json"),
    ("public-data-regime", "automation/public-data", "regime.json"),
    ("public-data-regime-timeline", "automation/public-data", "regime_timeline.csv"),
    ("regime-stratify", "automation/regime-stratify-last-run", "LAST_RUN.md"),
    ("rebalance-paper-forward", "automation/rebalance-paper-forward-last-run", "LAST_RUN.md"),
    ("money-path", "automation/money-path-last-run", "LAST_RUN.md"),
    ("edge-autoarm", "automation/edge-autoarm-last-run", "LAST_RUN.md"),
    ("released-work", "automation/released-work-last-run", "released_work.json"),
    ("pipeline-liveness", "automation/pipeline-liveness-last-run", "LAST_RUN.md"),
)


@dataclass(frozen=True)
class EvidenceSurface:
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
class PublicDataItemGap:
    kind: str
    item_id: str
    ok: bool
    rows: int | None
    first_date: str | None
    last_date: str | None
    missing: int | None
    published: str | None
    issues: tuple[str, ...]
    gap_status: str
    gap_causes: tuple[str, ...]
    no_edge_impact: str
    reason_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "item_id": self.item_id,
            "ok": self.ok,
            "rows": self.rows,
            "first_date": self.first_date,
            "last_date": self.last_date,
            "missing": self.missing,
            "published": self.published,
            "issues": list(self.issues),
            "gap_status": self.gap_status,
            "gap_causes": list(self.gap_causes),
            "no_edge_impact": self.no_edge_impact,
            "reason_ko": self.reason_ko,
        }


@dataclass(frozen=True)
class CrossCheckGap:
    pair: str
    kind: str | None
    status: str
    overlap: int | None
    detail: str
    gap_cause: str
    no_edge_impact: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair": self.pair,
            "kind": self.kind,
            "status": self.status,
            "overlap": self.overlap,
            "detail": self.detail,
            "gap_cause": self.gap_cause,
            "no_edge_impact": self.no_edge_impact,
        }


@dataclass(frozen=True)
class RegimeIndicatorGap:
    indicator: str
    status: str
    state: str | None
    reason: str | None
    source: str | None
    gap_cause: str
    no_edge_impact: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "indicator": self.indicator,
            "status": self.status,
            "state": self.state,
            "reason": self.reason,
            "source": self.source,
            "gap_cause": self.gap_cause,
            "no_edge_impact": self.no_edge_impact,
        }


@dataclass(frozen=True)
class MoneyState:
    status: str | None
    can_submit_real_orders: bool | None
    stage: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "can_submit_real_orders": self.can_submit_real_orders,
            "stage": self.stage,
        }


@dataclass(frozen=True)
class EdgeAutoarmState:
    action: str | None
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ForwardTrackSnapshot:
    key: str
    label_ko: str
    verdict: str | None
    n_obs: int | None
    rank: int | None
    is_incumbent: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label_ko": self.label_ko,
            "verdict": self.verdict,
            "n_obs": self.n_obs,
            "rank": self.rank,
            "is_incumbent": self.is_incumbent,
        }


@dataclass(frozen=True)
class CausalFinding:
    finding_id: str
    impact: str
    summary_ko: str
    evidence_keys: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "impact": self.impact,
            "summary_ko": self.summary_ko,
            "evidence_keys": list(self.evidence_keys),
        }


@dataclass(frozen=True)
class ValidationGate:
    gate_id: str
    status: str
    summary_ko: str
    required_evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "status": self.status,
            "summary_ko": self.summary_ko,
            "required_evidence": list(self.required_evidence),
        }


@dataclass(frozen=True)
class BroadNoEdgeDataGapAuditReport:
    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    audit_id: str
    completed_candidate_id: str
    next_candidate_id: str
    overall_status: str
    headline_ko: str
    required_inputs: tuple[str, ...]
    evidence_surfaces: tuple[EvidenceSurface, ...]
    public_data_gaps: tuple[PublicDataItemGap, ...]
    cross_check_gaps: tuple[CrossCheckGap, ...]
    regime_indicator_gaps: tuple[RegimeIndicatorGap, ...]
    timeline_gap_summary: dict[str, Any]
    stratified_join_summary: dict[str, Any]
    forward_no_edge_summary: dict[str, Any]
    causal_findings: tuple[CausalFinding, ...]
    validation_gates: tuple[ValidationGate, ...]
    money_state: MoneyState
    edge_autoarm_state: EdgeAutoarmState
    released_work_summary: dict[str, Any]
    liveness_summary: dict[str, Any]
    safety_boundary: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "commit": self.commit,
            "timestamp_utc": self.timestamp_utc,
            "audit_id": self.audit_id,
            "completed_candidate_id": self.completed_candidate_id,
            "next_candidate_id": self.next_candidate_id,
            "overall_status": self.overall_status,
            "headline_ko": self.headline_ko,
            "required_inputs": list(self.required_inputs),
            "evidence_surfaces": [surface.to_dict() for surface in self.evidence_surfaces],
            "public_data_gaps": [gap.to_dict() for gap in self.public_data_gaps],
            "cross_check_gaps": [gap.to_dict() for gap in self.cross_check_gaps],
            "regime_indicator_gaps": [gap.to_dict() for gap in self.regime_indicator_gaps],
            "timeline_gap_summary": self.timeline_gap_summary,
            "stratified_join_summary": self.stratified_join_summary,
            "forward_no_edge_summary": self.forward_no_edge_summary,
            "causal_findings": [finding.to_dict() for finding in self.causal_findings],
            "validation_gates": [gate.to_dict() for gate in self.validation_gates],
            "money_state": self.money_state.to_dict(),
            "edge_autoarm_state": self.edge_autoarm_state.to_dict(),
            "released_work_summary": self.released_work_summary,
            "liveness_summary": self.liveness_summary,
            "safety_boundary": list(self.safety_boundary),
        }

    def as_markdown(self) -> str:
        lines = [
            f"# 데이터 결측 원인 감사 no-live 계약 (as of {self.timestamp_utc})",
            "",
            self.headline_ko,
            "",
            "## 요약",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| audit_id | `{self.audit_id}` |",
            f"| completed_candidate_id | `{self.completed_candidate_id}` |",
            f"| next_candidate_id | `{self.next_candidate_id}` |",
            f"| overall_status | `{self.overall_status}` |",
            f"| public_data_gap_count | {self._gap_count()} |",
            f"| regime_indicator_gap_count | {self._indicator_gap_count()} |",
            f"| timeline_rows | {self.timeline_gap_summary.get('row_count')} |",
            f"| no_edge_tracks | {self.forward_no_edge_summary.get('no_edge_count')} |",
            f"| money_state | `{self.money_state.status or 'unknown'}` |",
            f"| edge_autoarm | `{self.edge_autoarm_state.action or 'unknown'}` |",
            "",
            "## 공개 데이터 결측",
            "",
            "| 항목 | 상태 | 원인 | 영향 | 설명 |",
            "|------|------|------|------|------|",
        ]
        for gap in self.public_data_gaps:
            lines.append(
                f"| `{_table(gap.kind)}:{_table(gap.item_id)}` | `{gap.gap_status}` | "
                f"{_table(', '.join(gap.gap_causes) or '-')} | "
                f"`{gap.no_edge_impact}` | {_table(gap.reason_ko)} |"
            )
        lines += [
            "",
            "## 레짐 지표 결측",
            "",
            "| 지표 | 상태 | 원인 | 영향 | 출처 |",
            "|------|------|------|------|------|",
        ]
        for gap in self.regime_indicator_gaps:
            lines.append(
                f"| `{_table(gap.indicator)}` | `{_table(gap.status)}` | "
                f"`{gap.gap_cause}` | `{gap.no_edge_impact}` | "
                f"{_table(gap.source or '-')} |"
            )
        date_range = (
            f"{self.timeline_gap_summary.get('first_date')}.."
            f"{self.timeline_gap_summary.get('last_date')}"
        )
        canonical_missing = (
            ", ".join(self.timeline_gap_summary.get("canonical_labels_missing", []))
            or "-"
        )
        lines += [
            "",
            "## 타임라인 결측",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| row_count | {self.timeline_gap_summary.get('row_count')} |",
            f"| date_range | {date_range} |",
            f"| canonical_labels_missing | {_table(canonical_missing)} |",
            f"| missing_columns | {_table(_missing_columns_text(self.timeline_gap_summary))} |",
            "",
            "## 인과 판단",
            "",
            "| 판단 | 영향 | 설명 |",
            "|------|------|------|",
        ]
        for finding in self.causal_findings:
            lines.append(
                f"| `{_table(finding.finding_id)}` | `{finding.impact}` | "
                f"{_table(finding.summary_ko)} |"
            )
        lines += [
            "",
            "## 검증 게이트",
            "",
            "| 게이트 | 상태 | 설명 |",
            "|--------|------|------|",
        ]
        for gate in self.validation_gates:
            lines.append(
                f"| `{_table(gate.gate_id)}` | `{gate.status}` | {_table(gate.summary_ko)} |"
            )
        lines += ["", "## 안전 경계", ""]
        for invariant in self.safety_boundary:
            lines.append(f"- {invariant}")
        lines += ["", "## 결정 JSON", "", "```json"]
        lines.append(json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        lines.append("```")
        return "\n".join(lines)

    def _gap_count(self) -> int:
        return sum(gap.gap_status == GAP_DETECTED for gap in self.public_data_gaps)

    def _indicator_gap_count(self) -> int:
        return sum(gap.gap_cause != "READY" for gap in self.regime_indicator_gaps)


def build_broad_no_edge_data_gap_audit(
    evidence_texts: Mapping[str, str | None],
    *,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> BroadNoEdgeDataGapAuditReport:
    """sidecar 증거를 읽어 데이터 결측 원인 no-live 계약을 만든다."""

    now = _as_utc(now)
    timestamp = now.isoformat().replace("+00:00", "Z")
    parsed = {
        key: _parse_for_key(key, evidence_texts.get(key))
        for key, _ref, _filename in CONSUMED_SIDECARS
    }
    surfaces = tuple(
        _surface_for(key, ref, filename, evidence_texts.get(key), parsed[key])
        for key, ref, filename in CONSUMED_SIDECARS
    )
    required_inputs = tuple(f"{ref}:{filename}" for _, ref, filename in CONSUMED_SIDECARS)

    public_gaps = _public_data_gaps(parsed["public-data-summary"])
    cross_gaps = _cross_check_gaps(parsed["public-data-summary"])
    indicator_gaps = _regime_indicator_gaps(parsed["public-data-regime"])
    timeline_summary = _timeline_gap_summary(parsed["public-data-regime-timeline"])
    stratified_summary = _stratified_join_summary(
        parsed["regime-stratify"],
        timeline_labels=timeline_summary.get("label_counts", {}),
    )
    forward_summary = _forward_no_edge_summary(parsed["rebalance-paper-forward"])
    money_state = _money_state(parsed["money-path"])
    edge_state = _edge_autoarm_state(parsed["edge-autoarm"])
    released_summary = _released_work_summary(parsed["released-work"])
    liveness_summary = _liveness_summary(parsed["pipeline-liveness"])
    findings = _causal_findings(
        public_gaps=public_gaps,
        cross_gaps=cross_gaps,
        indicator_gaps=indicator_gaps,
        timeline_summary=timeline_summary,
        stratified_summary=stratified_summary,
        forward_summary=forward_summary,
    )
    gates = _validation_gates(
        evidence_surfaces=surfaces,
        public_gaps=public_gaps,
        indicator_gaps=indicator_gaps,
        timeline_summary=timeline_summary,
        stratified_summary=stratified_summary,
        forward_summary=forward_summary,
        money_state=money_state,
        edge_state=edge_state,
        released_summary=released_summary,
        liveness_summary=liveness_summary,
    )
    overall = _overall_status(gates)

    return BroadNoEdgeDataGapAuditReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=timestamp,
        audit_id=AUDIT_ID,
        completed_candidate_id=COMPLETED_CANDIDATE_ID,
        next_candidate_id=NEXT_CANDIDATE_ID,
        overall_status=overall,
        headline_ko=_headline(overall, findings),
        required_inputs=required_inputs,
        evidence_surfaces=surfaces,
        public_data_gaps=public_gaps,
        cross_check_gaps=cross_gaps,
        regime_indicator_gaps=indicator_gaps,
        timeline_gap_summary=timeline_summary,
        stratified_join_summary=stratified_summary,
        forward_no_edge_summary=forward_summary,
        causal_findings=findings,
        validation_gates=gates,
        money_state=money_state,
        edge_autoarm_state=edge_state,
        released_work_summary=released_summary,
        liveness_summary=liveness_summary,
        safety_boundary=SAFETY_BOUNDARY,
    )


def _parse_for_key(key: str, raw: str | None) -> Any:
    if raw is None:
        return None
    if key == "public-data-regime-timeline":
        return _parse_csv_rows(raw)
    if key == "regime-stratify":
        return _parse_regime_stratify_sections(raw)
    if key in {
        "public-data-last-run",
        "rebalance-paper-forward",
        "money-path",
        "edge-autoarm",
        "pipeline-liveness",
    }:
        return _parse_markdown_or_json(raw)
    return _parse_json(raw)


def _surface_for(
    key: str,
    ref: str,
    filename: str,
    raw: str | None,
    parsed: Any,
) -> EvidenceSurface:
    source_ref = f"{ref}:{filename}"
    if raw is None:
        return EvidenceSurface(
            key=key,
            source_ref=source_ref,
            present=False,
            parse_status=PARSE_MISSING,
            summary_ko="sidecar 파일 없음",
        )
    if parsed is None or (key == "regime-stratify" and not parsed):
        return EvidenceSurface(
            key=key,
            source_ref=source_ref,
            present=True,
            parse_status=PARSE_MALFORMED,
            summary_ko="원문은 있으나 구조화 파싱 실패",
        )
    return EvidenceSurface(
        key=key,
        source_ref=source_ref,
        present=True,
        parse_status=PARSE_OK,
        summary_ko=_summary_for(key, parsed),
    )


def _public_data_gaps(parsed: Any) -> tuple[PublicDataItemGap, ...]:
    if not isinstance(parsed, dict):
        return ()
    rows = []
    for item in _items(parsed, "items"):
        kind = str(item.get("kind") or "")
        item_id = str(item.get("id") or item.get("key") or "")
        ok = bool(item.get("ok"))
        missing = _int_or_none(item.get("missing"))
        published = _str_or_none(item.get("published"))
        issues = tuple(str(issue) for issue in item.get("issues", []) if issue)
        causes = _item_gap_causes(ok=ok, missing=missing, published=published, issues=issues)
        gap_status = GAP_DETECTED if _item_gap_is_detected(causes) else DATA_READY
        impact = _item_gap_impact(kind, item_id, causes, gap_status)
        rows.append(
            PublicDataItemGap(
                kind=kind,
                item_id=item_id,
                ok=ok,
                rows=_int_or_none(item.get("rows")),
                first_date=_str_or_none(item.get("first_date")),
                last_date=_str_or_none(item.get("last_date")),
                missing=missing,
                published=published,
                issues=issues,
                gap_status=gap_status,
                gap_causes=causes,
                no_edge_impact=impact,
                reason_ko=_item_gap_reason(kind, item_id, causes, impact),
            )
        )
    return tuple(rows)


def _cross_check_gaps(parsed: Any) -> tuple[CrossCheckGap, ...]:
    if not isinstance(parsed, dict):
        return ()
    rows = []
    for index, check in enumerate(_items(parsed, "cross_checks")):
        status = str(check.get("status") or "").upper()
        pair = str(check.get("pair") or check.get("name") or f"cross-check-{index}")
        overlap = _int_or_none(check.get("overlap") or check.get("overlap_days"))
        detail = str(check.get("detail") or "")
        if status == GATE_PASS:
            cause = "PASS"
            impact = IMPACT_LOW
        elif status == "SKIPPED":
            cause = "SKIPPED_MISSING_INPUT"
            impact = IMPACT_MEDIUM
        elif status == GATE_FAIL:
            cause = "FAILED_CROSS_CHECK"
            impact = IMPACT_HIGH
        else:
            cause = "INSUFFICIENT_OVERLAP" if not overlap else "UNKNOWN_CROSS_CHECK_STATUS"
            impact = IMPACT_UNKNOWN
        rows.append(
            CrossCheckGap(
                pair=pair,
                kind=_str_or_none(check.get("kind")),
                status=status or "UNKNOWN",
                overlap=overlap,
                detail=detail,
                gap_cause=cause,
                no_edge_impact=impact,
            )
        )
    return tuple(rows)


def _regime_indicator_gaps(parsed: Any) -> tuple[RegimeIndicatorGap, ...]:
    if not isinstance(parsed, dict):
        return ()
    rows = []
    for item in _items(parsed, "indicators"):
        indicator = str(item.get("key") or item.get("name") or "")
        status = str(item.get("status") or "UNKNOWN").upper()
        if status in {"OK", GATE_PASS}:
            cause = "READY"
            impact = IMPACT_LOW
        elif indicator == "inflation":
            cause = "INDICATOR_UNAVAILABLE"
            impact = IMPACT_MEDIUM
        else:
            cause = "INDICATOR_UNAVAILABLE"
            impact = IMPACT_HIGH
        rows.append(
            RegimeIndicatorGap(
                indicator=indicator,
                status=status,
                state=_str_or_none(item.get("state")),
                reason=_str_or_none(item.get("reason")),
                source=_str_or_none(item.get("source")),
                gap_cause=cause,
                no_edge_impact=impact,
            )
        )
    return tuple(rows)


def _timeline_gap_summary(rows: Any) -> dict[str, Any]:
    if not isinstance(rows, list):
        return _empty_timeline_summary(parseable=False)
    if not rows:
        return _empty_timeline_summary(parseable=True)

    labels: Counter[str] = Counter()
    dates: list[str] = []
    missing_label_rows: list[int] = []
    invalid_date_rows: list[int] = []
    duplicate_dates: list[str] = []
    out_of_order_dates: list[str] = []
    seen_dates: set[str] = set()
    previous_date: str | None = None
    missing_columns: Counter[str] = Counter()
    available_distribution: Counter[str] = Counter()
    available_values: list[int] = []

    for index, row in enumerate(rows, start=2):
        raw_date = str(row.get("date") or "").strip()
        raw_label = str(row.get("label") or "").strip()
        if raw_label:
            labels[raw_label] += 1
        else:
            missing_label_rows.append(index)

        if not raw_date:
            invalid_date_rows.append(index)
        else:
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                invalid_date_rows.append(index)
            if raw_date in seen_dates:
                duplicate_dates.append(raw_date)
            seen_dates.add(raw_date)
            if previous_date is not None and raw_date < previous_date:
                out_of_order_dates.append(raw_date)
            previous_date = raw_date
            dates.append(raw_date)

        for column in TIMELINE_COLUMNS:
            if not str(row.get(column) or "").strip():
                missing_columns[column] += 1
        available = _int_or_none(row.get("available"))
        if available is not None:
            available_values.append(available)
            available_distribution[str(available)] += 1

    total = len(rows)
    missing_pcts = {
        column: round((missing_columns[column] / total) * 100, 2) if total else 0.0
        for column in TIMELINE_COLUMNS
    }
    return {
        "parseable": True,
        "row_count": total,
        "first_date": dates[0] if dates else None,
        "last_date": dates[-1] if dates else None,
        "label_counts": dict(sorted(labels.items())),
        "canonical_labels_present": [
            label for label in CANONICAL_LABELS if labels.get(label, 0) > 0
        ],
        "canonical_labels_missing": [
            label for label in CANONICAL_LABELS if labels.get(label, 0) <= 0
        ],
        "missing_label_rows": missing_label_rows,
        "duplicate_dates": duplicate_dates,
        "invalid_date_rows": invalid_date_rows,
        "out_of_order_dates": out_of_order_dates,
        "missing_column_counts": {
            column: int(missing_columns[column]) for column in TIMELINE_COLUMNS
        },
        "missing_column_pcts": missing_pcts,
        "min_available": min(available_values) if available_values else None,
        "max_available": max(available_values) if available_values else None,
        "available_distribution": dict(sorted(available_distribution.items())),
    }


def _empty_timeline_summary(*, parseable: bool) -> dict[str, Any]:
    return {
        "parseable": parseable,
        "row_count": 0,
        "first_date": None,
        "last_date": None,
        "label_counts": {},
        "canonical_labels_present": [],
        "canonical_labels_missing": list(CANONICAL_LABELS),
        "missing_label_rows": [],
        "duplicate_dates": [],
        "invalid_date_rows": [],
        "out_of_order_dates": [],
        "missing_column_counts": {column: 0 for column in TIMELINE_COLUMNS},
        "missing_column_pcts": {column: 0.0 for column in TIMELINE_COLUMNS},
        "min_available": None,
        "max_available": None,
        "available_distribution": {},
    }


def _stratified_join_summary(
    sections: Any, *, timeline_labels: Mapping[str, int]
) -> dict[str, Any]:
    if not isinstance(sections, list) or not sections:
        return {
            "parseable": False,
            "section_count": 0,
            "sections": [],
            "sparse_labels": [],
            "non_forward_sections": [],
            "count_mismatches": [],
            "unknown_labels": [],
        }

    label_set = set(timeline_labels)
    summaries = [_stratified_section_summary(section, label_set) for section in sections]
    sparse = [
        f"{summary['section_name']}:{label}"
        for summary in summaries
        for label in summary["sparse_labels"]
    ]
    non_forward = [
        summary["section_name"] for summary in summaries if not summary["forward_join"]
    ]
    mismatches = [
        summary["section_name"] for summary in summaries if not summary["count_matches_total"]
    ]
    unknown = [
        f"{summary['section_name']}:{label}"
        for summary in summaries
        for label in summary["unknown_labels"]
    ]
    return {
        "parseable": True,
        "section_count": len(summaries),
        "sections": summaries,
        "sparse_labels": sparse,
        "non_forward_sections": non_forward,
        "count_mismatches": mismatches,
        "unknown_labels": unknown,
    }


def _stratified_section_summary(section: Mapping[str, Any], label_set: set[str]) -> dict[str, Any]:
    payload = section.get("payload") if isinstance(section.get("payload"), dict) else {}
    label_counts = {
        str(label): _int_or_none(values.get("n_days")) or 0
        for label, values in (payload.get("by_label") or {}).items()
        if isinstance(values, dict)
    }
    total_return_days = _int_or_none(payload.get("total_return_days")) or 0
    count_sum = sum(label_counts.values())
    join_rule = str(payload.get("join_rule") or "")
    return {
        "section_name": str(section.get("section_name") or "unknown"),
        "total_return_days": total_return_days,
        "join_rule": join_rule,
        "forward_join": _is_forward_join_rule(join_rule),
        "label_counts": dict(sorted(label_counts.items())),
        "count_sum": count_sum,
        "count_matches_total": total_return_days > 0 and count_sum == total_return_days,
        "sparse_labels": [
            label
            for label, n_days in sorted(label_counts.items())
            if 0 < n_days < MIN_STRATIFIED_OBS
        ],
        "unknown_labels": [
            label
            for label in sorted(label_counts)
            if label_set and label not in label_set and label not in CANONICAL_LABELS
        ],
    }


def _forward_no_edge_summary(parsed: Any) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        return {"parseable": False, "track_count": 0, "no_edge_count": 0, "rows": []}
    rows = [
        ForwardTrackSnapshot(
            key=str(row.get("key") or ""),
            label_ko=str(row.get("label") or row.get("label_ko") or row.get("key") or ""),
            verdict=_str_or_none(row.get("verdict")),
            n_obs=_int_or_none(row.get("n_obs")),
            rank=_int_or_none(row.get("rank")),
            is_incumbent=bool(row.get("is_incumbent")),
        )
        for row in _items(parsed, "rows")
    ]
    return {
        "parseable": True,
        "track_count": len(rows),
        "no_edge_count": sum(row.verdict == "NO_EDGE" for row in rows),
        "rows": [row.to_dict() for row in rows],
    }


def _money_state(parsed: Any) -> MoneyState:
    payload = parsed if isinstance(parsed, dict) else {}
    live_raw = payload.get("live_money_state")
    live = live_raw if isinstance(live_raw, dict) else {}
    can_submit = live.get("can_submit_real_orders")
    return MoneyState(
        status=_str_or_none(live.get("status") or payload.get("overall_status")),
        can_submit_real_orders=can_submit if isinstance(can_submit, bool) else None,
        stage=_str_or_none(payload.get("stage")),
    )


def _edge_autoarm_state(parsed: Any) -> EdgeAutoarmState:
    payload = parsed if isinstance(parsed, dict) else {}
    return EdgeAutoarmState(
        action=_str_or_none(payload.get("action")),
        reason=_str_or_none(payload.get("reason")),
    )


def _released_work_summary(parsed: Any) -> dict[str, Any]:
    released = {
        str(item.get("candidate_id") or "")
        for item in _items(parsed, "released_work")
        if str(item.get("status") or "").lower()
        in {"released", "release", "completed", "complete", "done", "shipped"}
    }
    return {
        "parseable": isinstance(parsed, dict),
        "completed_candidate_id": COMPLETED_CANDIDATE_ID,
        "completed_candidate_released": COMPLETED_CANDIDATE_ID in released,
        "released_count": len(released),
    }


def _liveness_summary(parsed: Any) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        return {"parseable": False, "overall": None, "non_ok_checks": []}
    tracked = {}
    for item in _items(parsed, "checks"):
        key = str(item.get("key") or item.get("name") or "")
        if key in {"collect-public-data", "regime-stratify", "rebalance-paper-forward"}:
            tracked[key] = str(item.get("status") or "")
    return {
        "parseable": True,
        "overall": parsed.get("overall") or parsed.get("overall_status"),
        "tracked_checks": tracked,
        "non_ok_checks": [key for key, status in tracked.items() if status != "OK"],
    }


def _causal_findings(
    *,
    public_gaps: tuple[PublicDataItemGap, ...],
    cross_gaps: tuple[CrossCheckGap, ...],
    indicator_gaps: tuple[RegimeIndicatorGap, ...],
    timeline_summary: Mapping[str, Any],
    stratified_summary: Mapping[str, Any],
    forward_summary: Mapping[str, Any],
) -> tuple[CausalFinding, ...]:
    detected_gaps = [gap for gap in public_gaps if gap.gap_status == GAP_DETECTED]
    skipped_checks = [gap for gap in cross_gaps if gap.gap_cause != "PASS"]
    indicator_gap_names = [gap.indicator for gap in indicator_gaps if gap.gap_cause != "READY"]
    missing_labels = list(timeline_summary.get("canonical_labels_missing") or [])
    inflation_missing_pct = _float_or_none(
        (timeline_summary.get("missing_column_pcts") or {}).get("inflation_yoy")
    )
    sparse_labels = list(stratified_summary.get("sparse_labels") or [])
    no_edge_count = int(forward_summary.get("no_edge_count") or 0)

    return (
        CausalFinding(
            finding_id="public_data_publication_gap",
            impact=_max_impact([gap.no_edge_impact for gap in detected_gaps], default=IMPACT_LOW),
            summary_ko=(
                f"공개 데이터 결측 {len(detected_gaps)}개와 교차검증 제한 "
                f"{len(skipped_checks)}개를 분리했습니다."
                if detected_gaps or skipped_checks
                else "공개 데이터 발행 결측은 없습니다."
            ),
            evidence_keys=("public-data-summary", "public-data-last-run"),
        ),
        CausalFinding(
            finding_id="regime_indicator_gap",
            impact=(
                _max_impact(
                    [gap.no_edge_impact for gap in indicator_gaps if gap.gap_cause != "READY"],
                    default=IMPACT_LOW,
                )
            ),
            summary_ko=(
                f"레짐 지표 결측은 {', '.join(indicator_gap_names)}입니다."
                if indicator_gap_names
                else "레짐 지표가 모두 준비됐습니다."
            ),
            evidence_keys=("public-data-regime",),
        ),
        CausalFinding(
            finding_id="timeline_label_coverage",
            impact=IMPACT_HIGH if missing_labels else IMPACT_LOW,
            summary_ko=(
                f"타임라인 canonical label 누락: {', '.join(missing_labels)}."
                if missing_labels
                else "타임라인에 RISK_ON, CAUTION, RISK_OFF 라벨이 모두 있습니다."
            ),
            evidence_keys=("public-data-regime-timeline",),
        ),
        CausalFinding(
            finding_id="timeline_column_missingness",
            impact=(
                IMPACT_MEDIUM
                if inflation_missing_pct is not None and inflation_missing_pct >= 90.0
                else IMPACT_LOW
            ),
            summary_ko=(
                f"inflation_yoy 결측률은 {inflation_missing_pct:.1f}%입니다."
                if inflation_missing_pct is not None
                else "timeline column 결측률을 계산하지 못했습니다."
            ),
            evidence_keys=("public-data-regime-timeline",),
        ),
        CausalFinding(
            finding_id="stratified_join_coverage",
            impact=IMPACT_MEDIUM if sparse_labels else IMPACT_LOW,
            summary_ko=(
                f"stratified sparse label: {', '.join(sparse_labels)}."
                if sparse_labels
                else "regime-stratify 조인과 label 관측이 충분합니다."
            ),
            evidence_keys=("regime-stratify",),
        ),
        CausalFinding(
            finding_id="no_edge_verdict_context",
            impact=IMPACT_LOW if no_edge_count else IMPACT_UNKNOWN,
            summary_ko=(
                f"forward paper NO_EDGE 행 {no_edge_count}개가 있어 데이터 "
                "결측과 전략 판정을 분리할 수 있습니다."
                if no_edge_count
                else "forward paper NO_EDGE 행을 확인하지 못했습니다."
            ),
            evidence_keys=("rebalance-paper-forward",),
        ),
    )


def _validation_gates(
    *,
    evidence_surfaces: tuple[EvidenceSurface, ...],
    public_gaps: tuple[PublicDataItemGap, ...],
    indicator_gaps: tuple[RegimeIndicatorGap, ...],
    timeline_summary: Mapping[str, Any],
    stratified_summary: Mapping[str, Any],
    forward_summary: Mapping[str, Any],
    money_state: MoneyState,
    edge_state: EdgeAutoarmState,
    released_summary: Mapping[str, Any],
    liveness_summary: Mapping[str, Any],
) -> tuple[ValidationGate, ...]:
    required_inputs = tuple(f"{ref}:{filename}" for _, ref, filename in CONSUMED_SIDECARS)
    bad_inputs = [
        surface
        for surface in evidence_surfaces
        if surface.parse_status in {PARSE_MISSING, PARSE_MALFORMED}
    ]
    input_gate = ValidationGate(
        gate_id="input-evidence",
        status=GATE_FAIL if bad_inputs else GATE_PASS,
        summary_ko=(
            "필수 sidecar 일부를 읽지 못했습니다."
            if bad_inputs
            else "필수 sidecar 10개를 읽었습니다."
        ),
        required_evidence=required_inputs,
    )
    data_gap_gate = ValidationGate(
        gate_id="public-data-gap-classification",
        status=GATE_PASS if public_gaps else GATE_FAIL,
        summary_ko=(
            f"공개 데이터 항목 {len(public_gaps)}개를 결측 원인별로 분류했습니다."
            if public_gaps
            else "공개 데이터 항목을 분류하지 못했습니다."
        ),
        required_evidence=("automation/public-data:summary.json",),
    )
    regime_gate = ValidationGate(
        gate_id="regime-indicator-coverage",
        status=GATE_PASS if indicator_gaps else GATE_FAIL,
        summary_ko=(
            f"레짐 지표 {len(indicator_gaps)}개를 읽었습니다."
            if indicator_gaps
            else "레짐 지표를 읽지 못했습니다."
        ),
        required_evidence=("automation/public-data:regime.json",),
    )
    timeline_gate = _timeline_gate(timeline_summary)
    stratified_gate = _stratified_gate(stratified_summary)
    forward_gate = ValidationGate(
        gate_id="forward-no-edge-context",
        status=(
            GATE_PASS
            if forward_summary.get("parseable") and int(forward_summary.get("no_edge_count") or 0)
            else GATE_WAIT
        ),
        summary_ko=(
            f"forward NO_EDGE 행 {forward_summary.get('no_edge_count')}개를 읽었습니다."
            if forward_summary.get("parseable")
            else "forward paper 리더보드를 읽지 못했습니다."
        ),
        required_evidence=("automation/rebalance-paper-forward-last-run:LAST_RUN.md",),
    )
    money_aligned = _money_no_live_aligned(money_state, edge_state)
    money_gate = ValidationGate(
        gate_id="money-gate-alignment",
        status=GATE_PASS if money_aligned else GATE_WAIT,
        summary_ko=(
            "돈 경로가 PREVIEW_ONLY/NO_EDGE_YET 및 WAIT_EDGE와 맞습니다."
            if money_aligned
            else "돈 경로나 edge-autoarm가 no-live 대기와 맞지 않습니다."
        ),
        required_evidence=(
            "automation/money-path-last-run:LAST_RUN.md",
            "automation/edge-autoarm-last-run:LAST_RUN.md",
        ),
    )
    liveness_gate = ValidationGate(
        gate_id="pipeline-liveness",
        status=GATE_WAIT if liveness_summary.get("non_ok_checks") else GATE_PASS,
        summary_ko=(
            f"데이터 관련 sidecar 생존성 대기: {liveness_summary.get('non_ok_checks')}"
            if liveness_summary.get("non_ok_checks")
            else "데이터 관련 sidecar 생존성이 OK입니다."
        ),
        required_evidence=("automation/pipeline-liveness-last-run:LAST_RUN.md",),
    )
    release_gate = ValidationGate(
        gate_id="released-work-closure",
        status=(
            GATE_PASS
            if released_summary.get("completed_candidate_released")
            else GATE_WAIT
        ),
        summary_ko=(
            "released-work가 이번 data-gap 후보를 완료 후보로 읽었습니다."
            if released_summary.get("completed_candidate_released")
            else "released-work에는 아직 이번 data-gap 후보가 없습니다."
        ),
        required_evidence=("automation/released-work-last-run:released_work.json",),
    )
    return (
        input_gate,
        data_gap_gate,
        regime_gate,
        timeline_gate,
        stratified_gate,
        forward_gate,
        money_gate,
        liveness_gate,
        release_gate,
    )


def _timeline_gate(summary: Mapping[str, Any]) -> ValidationGate:
    if not summary.get("parseable"):
        return ValidationGate(
            gate_id="timeline-label-coverage",
            status=GATE_FAIL,
            summary_ko="regime_timeline.csv를 파싱할 수 없습니다.",
            required_evidence=("automation/public-data:regime_timeline.csv",),
        )
    problems = []
    for field, label in (
        ("invalid_date_rows", "날짜 파싱 실패"),
        ("duplicate_dates", "중복 날짜"),
        ("out_of_order_dates", "날짜 역순"),
        ("missing_label_rows", "빈 label"),
    ):
        if summary.get(field):
            problems.append(f"{label} {len(summary[field])}건")
    if problems:
        return ValidationGate(
            gate_id="timeline-label-coverage",
            status=GATE_FAIL,
            summary_ko=", ".join(problems),
            required_evidence=("automation/public-data:regime_timeline.csv",),
        )
    if int(summary.get("row_count") or 0) < MIN_TIMELINE_ROWS:
        return ValidationGate(
            gate_id="timeline-label-coverage",
            status=GATE_WAIT,
            summary_ko=f"timeline 행 수가 부족합니다: {summary.get('row_count')}",
            required_evidence=("automation/public-data:regime_timeline.csv",),
        )
    missing = list(summary.get("canonical_labels_missing") or [])
    if missing:
        return ValidationGate(
            gate_id="timeline-label-coverage",
            status=GATE_WAIT,
            summary_ko=f"canonical label 관측 대기: {', '.join(missing)}",
            required_evidence=("automation/public-data:regime_timeline.csv",),
        )
    return ValidationGate(
        gate_id="timeline-label-coverage",
        status=GATE_PASS,
        summary_ko=(
            f"timeline {summary.get('row_count')}행과 canonical label 3개를 확인했습니다."
        ),
        required_evidence=("automation/public-data:regime_timeline.csv",),
    )


def _stratified_gate(summary: Mapping[str, Any]) -> ValidationGate:
    if not summary.get("parseable"):
        return ValidationGate(
            gate_id="stratified-join-coverage",
            status=GATE_FAIL,
            summary_ko="regime-stratify stratified JSON을 파싱할 수 없습니다.",
            required_evidence=("automation/regime-stratify-last-run:LAST_RUN.md",),
        )
    hard = list(summary.get("non_forward_sections") or []) + list(
        summary.get("count_mismatches") or []
    )
    if hard:
        return ValidationGate(
            gate_id="stratified-join-coverage",
            status=GATE_FAIL,
            summary_ko=f"stratified join 구조 문제가 있습니다: {hard[:3]}",
            required_evidence=("automation/regime-stratify-last-run:LAST_RUN.md",),
        )
    return ValidationGate(
        gate_id="stratified-join-coverage",
        status=GATE_PASS,
        summary_ko=(
            f"stratified section {summary.get('section_count')}개를 읽었습니다. "
            f"sparse label={len(summary.get('sparse_labels') or [])}개."
        ),
        required_evidence=("automation/regime-stratify-last-run:LAST_RUN.md",),
    )


def _overall_status(gates: tuple[ValidationGate, ...]) -> str:
    statuses = {gate.status for gate in gates}
    if GATE_FAIL in statuses:
        return BLOCKED
    if GATE_WAIT in statuses:
        return OBSERVATION_WAIT
    return CONTRACT_READY


def _headline(overall: str, findings: tuple[CausalFinding, ...]) -> str:
    high = [finding for finding in findings if finding.impact == IMPACT_HIGH]
    medium = [finding for finding in findings if finding.impact == IMPACT_MEDIUM]
    if overall == BLOCKED:
        return "필수 증거가 깨져 데이터 결측 원인 감사를 완료할 수 없습니다."
    if high:
        return (
            "데이터 결측이 NO_EDGE 해석을 크게 흔들 수 있어 관측 대기로 남깁니다."
        )
    if medium:
        return (
            "CPI/inflation 결측은 확인됐지만, 레짐 라벨과 forward NO_EDGE 증거는 "
            "분리해서 읽을 수 있습니다."
        )
    return "공개 데이터 결측이 NO_EDGE 판정의 주된 원인으로 보이지 않습니다."


def _item_gap_causes(
    *,
    ok: bool,
    missing: int | None,
    published: str | None,
    issues: tuple[str, ...],
) -> tuple[str, ...]:
    causes: list[str] = []
    if not ok:
        causes.append("item_not_ok")
    if not published:
        causes.append("not_published")
    if missing and missing > 0:
        causes.append("missing_observations")
    if any("신선도" in issue or "stale" in issue.lower() for issue in issues):
        causes.append("stale_observation")
    return tuple(dict.fromkeys(causes))


def _item_gap_is_detected(causes: tuple[str, ...]) -> bool:
    material = set(causes) - {"missing_observations"}
    return bool(material)


def _item_gap_impact(
    kind: str,
    item_id: str,
    causes: tuple[str, ...],
    gap_status: str,
) -> str:
    if not causes or gap_status == DATA_READY:
        return IMPACT_LOW
    if kind in {"treasury", "cboe"} or item_id in {"UST10Y2Y", "VIX"}:
        return IMPACT_HIGH
    if kind in {"bls", "dbnomics"} or item_id in {"CUUR0000SA0", "LNS14000000"}:
        return IMPACT_MEDIUM
    return IMPACT_MEDIUM


def _item_gap_reason(
    kind: str,
    item_id: str,
    causes: tuple[str, ...],
    impact: str,
) -> str:
    if not causes:
        return "발행과 기본 관측이 준비됐습니다."
    cause_text = ", ".join(causes)
    return f"{kind}:{item_id} 결측 원인 {cause_text}; NO_EDGE 영향도 {impact}."


def _money_no_live_aligned(money_state: MoneyState, edge_state: EdgeAutoarmState) -> bool:
    return (
        money_state.status in {"PREVIEW_ONLY", "NO_LIVE", None}
        and money_state.stage in {"NO_EDGE_YET", "ACCUMULATING_EDGE", None}
        and money_state.can_submit_real_orders is not True
        and edge_state.action in {"WAIT_EDGE", "NO_EDGE", "WAIT", None}
    )


def _summary_for(key: str, parsed: Any) -> str:
    if key == "public-data-regime-timeline" and isinstance(parsed, list):
        return f"timeline_rows={len(parsed)}"
    if key == "regime-stratify" and isinstance(parsed, list):
        return f"stratified_sections={len(parsed)}"
    if not isinstance(parsed, dict):
        return "구조화 입력 존재"
    if key in {"public-data-summary", "public-data-last-run"}:
        return (
            f"overall_ok={parsed.get('overall_ok')}, "
            f"published={parsed.get('published')}/{parsed.get('total_items')}"
        )
    if key == "public-data-regime":
        indicators = _items(parsed, "indicators")
        overall = parsed.get("overall") if isinstance(parsed.get("overall"), dict) else {}
        return (
            f"label={overall.get('label') or parsed.get('overall_label')}, "
            f"indicators={len(indicators)}"
        )
    if key == "rebalance-paper-forward":
        return f"forward_rows={len(_items(parsed, 'rows'))}"
    if key == "released-work":
        return f"released_count={len(_items(parsed, 'released_work'))}"
    if key == "pipeline-liveness":
        return f"overall={parsed.get('overall') or parsed.get('overall_status')}"
    if key == "money-path":
        live_raw = parsed.get("live_money_state")
        live = live_raw if isinstance(live_raw, dict) else {}
        return f"status={live.get('status') or parsed.get('overall_status')}"
    if key == "edge-autoarm":
        return f"action={parsed.get('action')}"
    return "구조화 JSON 존재"


def _parse_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _parse_markdown_or_json(raw: str) -> Any:
    direct = _parse_json(raw.strip())
    if isinstance(direct, dict):
        return direct
    for candidate in _iter_json_dicts(raw):
        return candidate
    return None


def _parse_csv_rows(raw: str) -> list[dict[str, str]] | None:
    try:
        rows = list(csv.DictReader(io.StringIO(raw)))
    except csv.Error:
        return None
    return rows if rows and "date" in rows[0] and "label" in rows[0] else None


def _parse_regime_stratify_sections(raw: str) -> list[dict[str, Any]] | None:
    sections: list[dict[str, Any]] = []
    current_heading = "unknown"
    lines = raw.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## "):
            current_heading = _clean_heading(stripped)
        if "--- stratified json ---" not in stripped:
            continue
        payload = _first_json_dict("\n".join(lines[index + 1 :]))
        if isinstance(payload, dict) and isinstance(payload.get("by_label"), dict):
            sections.append({"section_name": current_heading, "payload": payload})
    if sections:
        return sections
    parsed = _parse_json(raw.strip())
    if isinstance(parsed, dict) and isinstance(parsed.get("by_label"), dict):
        return [{"section_name": "regime-window", "payload": parsed}]
    return None


def _first_json_dict(text: str) -> dict[str, Any] | None:
    for candidate in _iter_json_dicts(text):
        return candidate
    return None


def _iter_json_dicts(text: str) -> tuple[dict[str, Any], ...]:
    decoder = json.JSONDecoder()
    objects: list[dict[str, Any]] = []
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            parsed, _end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            objects.append(parsed)
    return tuple(objects)


def _items(parsed: Any, key: str) -> list[dict[str, Any]]:
    if not isinstance(parsed, dict):
        return []
    raw = parsed.get(key)
    if isinstance(raw, dict):
        if all(isinstance(value, dict) for value in raw.values()):
            return [
                {"key": str(item_key), **value}
                for item_key, value in raw.items()
                if isinstance(value, dict)
            ]
        return [raw]
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _is_forward_join_rule(join_rule: str) -> bool:
    return "d+1" in join_rule or "전망" in join_rule or "미래 누출 차단" in join_rule


def _clean_heading(line: str) -> str:
    heading = line.lstrip("#").strip()
    if "(" in heading:
        heading = heading.split("(", 1)[0].strip()
    if "—" in heading:
        heading = heading.split("—", 1)[0].strip()
    return heading or "regime-window"


def _missing_columns_text(summary: Mapping[str, Any]) -> str:
    pcts = summary.get("missing_column_pcts") if isinstance(summary, Mapping) else {}
    if not isinstance(pcts, Mapping):
        return "-"
    return ", ".join(f"{key}={value}%" for key, value in pcts.items())


def _max_impact(values: list[str], *, default: str) -> str:
    if not values:
        return default
    rank = {IMPACT_LOW: 0, IMPACT_MEDIUM: 1, IMPACT_HIGH: 2, IMPACT_UNKNOWN: 3}
    return max(values, key=lambda value: rank.get(value, -1))


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _str_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _table(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _as_utc(now: datetime) -> datetime:
    return now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)

"""스펙 132 — 광역 no-edge 레짐·비용 견고성 no-live 실험 계약.

선택된 자율 후보 `candidate-broad-no-edge-regime-cost-robustness-experiment`를
레짐 구간과 비용 민감도 관점의 기계 판독 보고서로 고정한다.

안전 경계: 읽기 전용·순수·결정론. 브로커 API, 주문, 자본 배분, live 전략,
whitelist/caps, 비밀값, 헌법/커널, 외부 유료 서비스는 건드리지 않는다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "1.0"
EXPERIMENT_ID = "broad-no-edge-regime-cost-robustness"
COMPLETED_CANDIDATE_ID = "candidate-broad-no-edge-regime-cost-robustness-experiment"
NEXT_CANDIDATE_ID = "candidate-broad-no-edge-data-gap-audit"

CONTRACT_READY = "CONTRACT_READY"
OBSERVATION_WAIT = "OBSERVATION_WAIT"
BLOCKED = "BLOCKED"

PARSE_OK = "ok"
PARSE_MISSING = "missing"
PARSE_MALFORMED = "malformed"

GATE_PASS = "PASS"
GATE_WAIT = "WAIT"
GATE_FAIL = "FAIL"

ASSESS_PASS = "PASS"
ASSESS_WAIT = "WAIT"
ASSESS_STRESS = "STRESS"

PROPOSED = "PROPOSED"
WAIT = "WAIT"
EXCLUDED = "EXCLUDED"

MIN_REGIME_OBS = 20
SHARPE_STRESS_THRESHOLD = 1.0
MAX_DRAWDOWN_STRESS_THRESHOLD = 7.0
COST_STRESS_BPS: tuple[int, ...] = (10, 25, 50)

SAFETY_BOUNDARY: tuple[str, ...] = (
    "no broker API call",
    "no orders",
    "no capital allocation",
    "no live strategy change",
    "no whitelist/caps change",
    "no secret read/write",
    "no external paid service",
    "no constitution/kernel change",
    "experiment contract only",
)

CONSUMED_SIDECARS: tuple[tuple[str, str, str], ...] = (
    ("regime-stratify", "automation/regime-stratify-last-run", "LAST_RUN.md"),
    ("execution-quality", "automation/execution-quality-last-run", "LAST_RUN.md"),
    ("money-path", "automation/money-path-last-run", "LAST_RUN.md"),
    ("edge-autoarm", "automation/edge-autoarm-last-run", "LAST_RUN.md"),
    ("rebalance-paper-forward", "automation/rebalance-paper-forward-last-run", "LAST_RUN.md"),
    ("released-work", "automation/released-work-last-run", "released_work.json"),
    ("evolution-ledger", "automation/autonomous-evolution-last-run", "learning_ledger.json"),
    ("pipeline-liveness", "automation/pipeline-liveness-last-run", "LAST_RUN.md"),
)


@dataclass(frozen=True)
class EvidenceSurface:
    key: str
    source_ref: str
    parse_status: str
    summary_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "source_ref": self.source_ref,
            "parse_status": self.parse_status,
            "summary_ko": self.summary_ko,
        }


@dataclass(frozen=True)
class RegimeLabelAssessment:
    label: str
    n_days: int | None
    total_return_pct: float | None
    sharpe: float | None
    max_drawdown_pct: float | None
    assessment: str
    reason_ko: str

    @classmethod
    def from_payload(cls, label: str, payload: dict[str, Any]) -> RegimeLabelAssessment:
        n_days = _int_or_none(payload.get("n_days"))
        total_return = _float_or_none(payload.get("total_return_pct"))
        sharpe = _float_or_none(payload.get("sharpe") or payload.get("sharpe_ratio"))
        max_drawdown = _float_or_none(payload.get("max_drawdown_pct"))
        assessment, reason = _assess_regime_label(
            n_days=n_days,
            total_return_pct=total_return,
            sharpe=sharpe,
            max_drawdown_pct=max_drawdown,
        )
        return cls(
            label=str(label),
            n_days=n_days,
            total_return_pct=total_return,
            sharpe=sharpe,
            max_drawdown_pct=max_drawdown,
            assessment=assessment,
            reason_ko=reason,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "n_days": self.n_days,
            "total_return_pct": self.total_return_pct,
            "sharpe": self.sharpe,
            "max_drawdown_pct": self.max_drawdown_pct,
            "assessment": self.assessment,
            "reason_ko": self.reason_ko,
        }


@dataclass(frozen=True)
class RegimeWindow:
    track_label: str
    join_rule: str | None
    total_return_days: int | None
    labels: tuple[RegimeLabelAssessment, ...]
    all_n_days: int | None
    all_total_return_pct: float | None
    all_sharpe: float | None
    all_max_drawdown_pct: float | None

    @classmethod
    def from_payload(cls, track_label: str, payload: dict[str, Any]) -> RegimeWindow:
        by_label = payload.get("by_label")
        by_label = by_label if isinstance(by_label, dict) else {}
        labels = tuple(
            RegimeLabelAssessment.from_payload(label, values)
            for label, values in sorted(by_label.items())
            if isinstance(values, dict)
        )
        all_payload = payload.get("all")
        all_payload = all_payload if isinstance(all_payload, dict) else {}
        join_rule = payload.get("join_rule")
        return cls(
            track_label=track_label,
            join_rule=join_rule if isinstance(join_rule, str) else None,
            total_return_days=_int_or_none(payload.get("total_return_days")),
            labels=labels,
            all_n_days=_int_or_none(all_payload.get("n_days")),
            all_total_return_pct=_float_or_none(all_payload.get("total_return_pct")),
            all_sharpe=_float_or_none(
                all_payload.get("sharpe") or all_payload.get("sharpe_ratio")
            ),
            all_max_drawdown_pct=_float_or_none(all_payload.get("max_drawdown_pct")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_label": self.track_label,
            "join_rule": self.join_rule,
            "total_return_days": self.total_return_days,
            "labels": [label.to_dict() for label in self.labels],
            "all": {
                "n_days": self.all_n_days,
                "total_return_pct": self.all_total_return_pct,
                "sharpe": self.all_sharpe,
                "max_drawdown_pct": self.all_max_drawdown_pct,
            },
        }


@dataclass(frozen=True)
class ExecutionCostSnapshot:
    overall_status: str | None
    monitor_verdict: str | None
    latest_signal: str | None
    cumulative_pnl_usd: float | None
    rejected_orders: int | None
    parsed_broker_errors: int | None
    broker_error_observation_rate: float | None
    kis_msg_codes: dict[str, int]
    smoke_state: str | None
    smoke_error_rate: float | None
    live_gate_ok: bool | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> ExecutionCostSnapshot:
        payload = payload if isinstance(payload, dict) else {}
        monitor = payload.get("opportunity_monitor")
        monitor = monitor if isinstance(monitor, dict) else {}
        broker = payload.get("broker_rejections")
        broker = broker if isinstance(broker, dict) else {}
        smoke = payload.get("broker_smoke")
        smoke = smoke if isinstance(smoke, dict) else {}
        live_gate = payload.get("live_gate")
        live_gate = live_gate if isinstance(live_gate, dict) else {}
        codes = broker.get("kis_msg_codes")
        codes = codes if isinstance(codes, dict) else {}
        live_ok = live_gate.get("ok")
        return cls(
            overall_status=_str_or_none(payload.get("overall_status")),
            monitor_verdict=_str_or_none(monitor.get("verdict")),
            latest_signal=_str_or_none(monitor.get("latest_signal")),
            cumulative_pnl_usd=_float_or_none(monitor.get("cumulative_pnl_usd")),
            rejected_orders=_int_or_none(broker.get("rejected_orders")),
            parsed_broker_errors=_int_or_none(broker.get("parsed_broker_errors")),
            broker_error_observation_rate=_float_or_none(
                broker.get("broker_error_observation_rate")
            ),
            kis_msg_codes={
                str(key): int(value)
                for key, value in sorted(codes.items())
                if _int_or_none(value) is not None
            },
            smoke_state=_str_or_none(smoke.get("smoke_state")),
            smoke_error_rate=_float_or_none(smoke.get("smoke_error_rate")),
            live_gate_ok=live_ok if isinstance(live_ok, bool) else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "monitor_verdict": self.monitor_verdict,
            "latest_signal": self.latest_signal,
            "cumulative_pnl_usd": self.cumulative_pnl_usd,
            "rejected_orders": self.rejected_orders,
            "parsed_broker_errors": self.parsed_broker_errors,
            "broker_error_observation_rate": self.broker_error_observation_rate,
            "kis_msg_codes": self.kis_msg_codes,
            "smoke_state": self.smoke_state,
            "smoke_error_rate": self.smoke_error_rate,
            "live_gate_ok": self.live_gate_ok,
        }


@dataclass(frozen=True)
class MoneyState:
    status: str | None
    can_submit_real_orders: bool | None
    stage: str | None
    detail_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "can_submit_real_orders": self.can_submit_real_orders,
            "stage": self.stage,
            "detail_ko": self.detail_ko,
        }


@dataclass(frozen=True)
class EdgeAutoarmState:
    action: str | None
    reason: str | None
    current_rung: int | None
    next_rung: int | None
    detail_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "current_rung": self.current_rung,
            "next_rung": self.next_rung,
            "detail_ko": self.detail_ko,
        }


@dataclass(frozen=True)
class ForwardTrackSnapshot:
    key: str
    label_ko: str
    verdict: str | None
    n_obs: int | None
    rank: int | None
    is_incumbent: bool

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ForwardTrackSnapshot:
        key = str(row.get("key") or "")
        return cls(
            key=key,
            label_ko=str(row.get("label") or row.get("label_ko") or key),
            verdict=_str_or_none(row.get("verdict")),
            n_obs=_int_or_none(row.get("n_obs")),
            rank=_int_or_none(row.get("rank")),
            is_incumbent=bool(row.get("is_incumbent")),
        )

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
class CostStressRow:
    stress_bps: int
    status: str
    affected_tracks: tuple[str, ...]
    execution_observation_ko: str
    reason_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "stress_bps": self.stress_bps,
            "status": self.status,
            "affected_tracks": list(self.affected_tracks),
            "execution_observation_ko": self.execution_observation_ko,
            "reason_ko": self.reason_ko,
        }


@dataclass(frozen=True)
class ExclusionCriterion:
    candidate_key: str
    status: str
    reason_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_key": self.candidate_key,
            "status": self.status,
            "reason_ko": self.reason_ko,
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
class BroadNoEdgeRegimeCostRobustnessReport:
    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    experiment_id: str
    completed_candidate_id: str
    next_candidate_id: str
    overall_status: str
    headline_ko: str
    required_inputs: tuple[str, ...]
    evidence_surfaces: tuple[EvidenceSurface, ...]
    regime_windows: tuple[RegimeWindow, ...]
    regime_metrics: dict[str, Any]
    execution_cost_snapshot: ExecutionCostSnapshot
    money_state: MoneyState
    edge_autoarm_state: EdgeAutoarmState
    forward_track_snapshots: tuple[ForwardTrackSnapshot, ...]
    cost_stress_rows: tuple[CostStressRow, ...]
    exclusion_criteria: tuple[ExclusionCriterion, ...]
    validation_gates: tuple[ValidationGate, ...]
    learning_summary: dict[str, Any]
    released_work_summary: dict[str, Any]
    safety_boundary: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "commit": self.commit,
            "timestamp_utc": self.timestamp_utc,
            "experiment_id": self.experiment_id,
            "completed_candidate_id": self.completed_candidate_id,
            "next_candidate_id": self.next_candidate_id,
            "overall_status": self.overall_status,
            "headline_ko": self.headline_ko,
            "required_inputs": list(self.required_inputs),
            "evidence_surfaces": [surface.to_dict() for surface in self.evidence_surfaces],
            "regime_windows": [window.to_dict() for window in self.regime_windows],
            "regime_metrics": self.regime_metrics,
            "execution_cost_snapshot": self.execution_cost_snapshot.to_dict(),
            "money_state": self.money_state.to_dict(),
            "edge_autoarm_state": self.edge_autoarm_state.to_dict(),
            "forward_track_snapshots": [
                snapshot.to_dict() for snapshot in self.forward_track_snapshots
            ],
            "cost_stress_rows": [row.to_dict() for row in self.cost_stress_rows],
            "exclusion_criteria": [criterion.to_dict() for criterion in self.exclusion_criteria],
            "validation_gates": [gate.to_dict() for gate in self.validation_gates],
            "learning_summary": self.learning_summary,
            "released_work_summary": self.released_work_summary,
            "safety_boundary": list(self.safety_boundary),
        }

    def as_markdown(self) -> str:
        lines = [
            f"# 레짐·비용 견고성 no-live 실험 계약 (as of {self.timestamp_utc})",
            "",
            self.headline_ko,
            "",
            "## 요약",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| experiment_id | `{self.experiment_id}` |",
            f"| completed_candidate_id | `{self.completed_candidate_id}` |",
            f"| next_candidate_id | `{self.next_candidate_id}` |",
            f"| overall_status | `{self.overall_status}` |",
            f"| regime_window_count | {self.regime_metrics.get('window_count')} |",
            f"| stress_label_count | {self.regime_metrics.get('stress_label_count')} |",
            f"| wait_label_count | {self.regime_metrics.get('wait_label_count')} |",
            (
                "| cost_stress_bps | "
                f"{', '.join(str(row.stress_bps) for row in self.cost_stress_rows)} |"
            ),
            f"| money_state | `{self.money_state.status or 'unknown'}` |",
            f"| edge_autoarm | `{self.edge_autoarm_state.action or 'unknown'}` |",
            "",
            "## 레짐 창",
            "",
            "| 트랙 | 레짐 | 관측 | 수익률% | 샤프 | 낙폭% | 판정 |",
            "|------|------|-----:|--------:|------:|------:|------|",
        ]
        for window in self.regime_windows:
            for label in window.labels:
                lines.append(
                    f"| {_table(window.track_label)} | `{_table(label.label)}` | "
                    f"{_table(label.n_days)} | {_table(label.total_return_pct)} | "
                    f"{_table(label.sharpe)} | {_table(label.max_drawdown_pct)} | "
                    f"`{label.assessment}` |"
                )
        lines += [
            "",
            "## 비용 민감도 행",
            "",
            "| 비용(bp) | 상태 | 적용 트랙 | 이유 |",
            "|---------:|------|-----------|------|",
        ]
        for row in self.cost_stress_rows:
            lines.append(
                f"| {row.stress_bps} | `{row.status}` | "
                f"{_table(', '.join(row.affected_tracks))} | {_table(row.reason_ko)} |"
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
        lines += ["", "## 제외 기준", ""]
        for criterion in self.exclusion_criteria:
            lines.append(f"- `{criterion.candidate_key}`: {criterion.reason_ko}")
        lines += ["", "## 안전 경계", ""]
        for invariant in self.safety_boundary:
            lines.append(f"- {invariant}")
        lines += ["", "## 결정 JSON", "", "```json"]
        lines.append(json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        lines.append("```")
        return "\n".join(lines)


def build_broad_no_edge_regime_cost_robustness(
    evidence_texts: dict[str, str | None],
    *,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> BroadNoEdgeRegimeCostRobustnessReport:
    """sidecar 증거를 읽어 레짐·비용 견고성 no-live 계약을 만든다."""

    now = _as_utc(now)
    timestamp = now.isoformat().replace("+00:00", "Z")

    regime_windows, regime_status, regime_summary = _parse_regime_windows(
        evidence_texts.get("regime-stratify")
    )
    execution_payload, execution_status, execution_summary = _parse_execution_quality(
        evidence_texts.get("execution-quality")
    )
    money_payload, money_status, money_summary = _parse_markdown_or_json(
        evidence_texts.get("money-path")
    )
    edge_payload, edge_status, edge_summary = _parse_markdown_or_json(
        evidence_texts.get("edge-autoarm")
    )
    forward_board, forward_status, forward_summary = _parse_forward_board(
        evidence_texts.get("rebalance-paper-forward")
    )
    released_payload, released_status, released_summary = _parse_json_document(
        evidence_texts.get("released-work")
    )
    ledger_payload, ledger_status, ledger_summary = _parse_json_document(
        evidence_texts.get("evolution-ledger")
    )
    pipeline_payload, pipeline_status, pipeline_summary = _parse_markdown_or_json(
        evidence_texts.get("pipeline-liveness")
    )

    surface_status = {
        "regime-stratify": (regime_status, regime_summary),
        "execution-quality": (execution_status, execution_summary),
        "money-path": (money_status, money_summary),
        "edge-autoarm": (edge_status, edge_summary),
        "rebalance-paper-forward": (forward_status, forward_summary),
        "released-work": (released_status, released_summary),
        "evolution-ledger": (ledger_status, ledger_summary),
        "pipeline-liveness": (pipeline_status, pipeline_summary),
    }
    evidence_surfaces = tuple(
        EvidenceSurface(
            key=key,
            source_ref=f"{ref}:{filename}",
            parse_status=surface_status[key][0],
            summary_ko=surface_status[key][1],
        )
        for key, ref, filename in CONSUMED_SIDECARS
    )

    required_inputs = tuple(f"{ref}:{filename}" for _, ref, filename in CONSUMED_SIDECARS)
    execution_snapshot = ExecutionCostSnapshot.from_payload(execution_payload)
    money_state = _money_state(money_payload)
    edge_state = _edge_autoarm_state(edge_payload)
    forward_snapshots = _forward_snapshots(forward_board)
    regime_metrics = _regime_metrics(regime_windows)
    cost_rows = _cost_stress_rows(
        regime_windows=regime_windows,
        forward_snapshots=forward_snapshots,
        execution_snapshot=execution_snapshot,
        money_state=money_state,
        edge_state=edge_state,
    )
    exclusions = _exclusion_criteria()
    learning_summary = _learning_summary(ledger_payload)
    released_summary_dict = _released_work_summary(released_payload)
    validation_gates = _validation_gates(
        evidence_surfaces=evidence_surfaces,
        regime_windows=regime_windows,
        regime_metrics=regime_metrics,
        execution_snapshot=execution_snapshot,
        money_state=money_state,
        edge_state=edge_state,
        forward_snapshots=forward_snapshots,
        cost_rows=cost_rows,
        learning_summary=learning_summary,
        released_summary=released_summary_dict,
        pipeline_payload=pipeline_payload,
    )
    overall = _overall_status(validation_gates)
    headline = _headline(overall, regime_metrics, cost_rows)

    return BroadNoEdgeRegimeCostRobustnessReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=timestamp,
        experiment_id=EXPERIMENT_ID,
        completed_candidate_id=COMPLETED_CANDIDATE_ID,
        next_candidate_id=NEXT_CANDIDATE_ID,
        overall_status=overall,
        headline_ko=headline,
        required_inputs=required_inputs,
        evidence_surfaces=evidence_surfaces,
        regime_windows=regime_windows,
        regime_metrics=regime_metrics,
        execution_cost_snapshot=execution_snapshot,
        money_state=money_state,
        edge_autoarm_state=edge_state,
        forward_track_snapshots=forward_snapshots,
        cost_stress_rows=cost_rows,
        exclusion_criteria=exclusions,
        validation_gates=validation_gates,
        learning_summary=learning_summary,
        released_work_summary=released_summary_dict,
        safety_boundary=SAFETY_BOUNDARY,
    )


def _parse_regime_windows(text: str | None) -> tuple[tuple[RegimeWindow, ...], str, str]:
    if text is None:
        return (), PARSE_MISSING, "regime-stratify sidecar가 없습니다."
    direct = _loads_dict(text)
    if _looks_like_regime_window(direct):
        return (
            (RegimeWindow.from_payload(_track_label_from_payload(direct), direct),),
            PARSE_OK,
            "regime-stratify JSON 입력을 읽었습니다.",
        )

    windows: list[RegimeWindow] = []
    current_heading = "unknown"
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## "):
            current_heading = _clean_heading(stripped)
        if "--- stratified json ---" not in stripped:
            continue
        candidate = _first_json_dict("\n".join(lines[index + 1 :]))
        if _looks_like_regime_window(candidate):
            windows.append(RegimeWindow.from_payload(current_heading, candidate))

    if not windows:
        fenced = _extract_json_after_header(text, "결정 JSON")
        if _looks_like_regime_window(fenced):
            windows.append(RegimeWindow.from_payload(_track_label_from_payload(fenced), fenced))

    if not windows:
        for candidate in _iter_json_dicts(text):
            if _looks_like_regime_window(candidate):
                windows.append(
                    RegimeWindow.from_payload(
                        _track_label_from_payload(candidate),
                        candidate,
                    )
                )

    if not windows:
        return (), PARSE_MALFORMED, "regime-stratify stratified JSON 블록을 읽지 못했습니다."
    return (
        tuple(windows),
        PARSE_OK,
        f"regime-stratify stratified JSON {len(windows)}개를 읽었습니다.",
    )


def _parse_execution_quality(text: str | None) -> tuple[dict[str, Any] | None, str, str]:
    payload, status, summary = _parse_markdown_or_json(text)
    if status != PARSE_OK or not isinstance(payload, dict):
        return payload, status, summary
    has_cost = isinstance(payload.get("broker_rejections"), dict)
    has_smoke = isinstance(payload.get("broker_smoke"), dict)
    has_monitor = isinstance(payload.get("opportunity_monitor"), dict)
    if has_cost and has_smoke and has_monitor:
        return payload, PARSE_OK, "execution-quality 결정 JSON을 읽었습니다."
    return None, PARSE_MALFORMED, "execution-quality 비용·스모크·모니터 증거가 부족합니다."


def _parse_forward_board(text: str | None) -> tuple[dict[str, Any] | None, str, str]:
    if text is None:
        return None, PARSE_MISSING, "forward sidecar가 없습니다."
    board = _extract_json_after_header(text, "리더보드 결정 JSON")
    if isinstance(board, dict) and isinstance(board.get("rows"), list):
        return board, PARSE_OK, "forward 리더보드 결정 JSON을 읽었습니다."
    direct = _loads_dict(text)
    if isinstance(direct, dict) and isinstance(direct.get("rows"), list):
        return direct, PARSE_OK, "forward JSON 입력을 읽었습니다."
    return None, PARSE_MALFORMED, "forward 리더보드를 읽지 못했습니다."


def _parse_markdown_or_json(text: str | None) -> tuple[dict[str, Any] | None, str, str]:
    if text is None:
        return None, PARSE_MISSING, "입력이 없습니다."
    direct = _loads_dict(text)
    if direct is not None:
        return direct, PARSE_OK, "JSON 입력을 읽었습니다."
    fenced = _extract_json_after_header(text, "결정 JSON")
    if isinstance(fenced, dict):
        return fenced, PARSE_OK, "Markdown 결정 JSON을 읽었습니다."
    return None, PARSE_MALFORMED, "결정 JSON을 읽지 못했습니다."


def _parse_json_document(text: str | None) -> tuple[dict[str, Any] | None, str, str]:
    if text is None:
        return None, PARSE_MISSING, "입력이 없습니다."
    parsed = _loads_dict(text)
    if parsed is None:
        return None, PARSE_MALFORMED, "JSON 문서를 읽지 못했습니다."
    return parsed, PARSE_OK, "JSON 문서를 읽었습니다."


def _extract_json_after_header(text: str | None, header: str) -> dict[str, Any] | None:
    if not text:
        return None
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if header in line:
            start = index
            break
    if start is None:
        return None
    in_block = False
    buf: list[str] = []
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if not in_block:
            if stripped.startswith("```json") or stripped.startswith("```"):
                in_block = True
            continue
        if stripped.startswith("```"):
            break
        buf.append(line)
    if not buf:
        return None
    return _loads_dict("\n".join(buf))


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


def _loads_dict(text: str | None) -> dict[str, Any] | None:
    if text is None:
        return None
    try:
        parsed = json.loads(text.strip())
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _looks_like_regime_window(payload: object) -> bool:
    return isinstance(payload, dict) and isinstance(payload.get("by_label"), dict)


def _track_label_from_payload(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return "regime-window"
    for key in ("track_label", "portfolio_id", "track", "key"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return "regime-window"


def _clean_heading(line: str) -> str:
    heading = line.lstrip("#").strip()
    if "(" in heading:
        heading = heading.split("(", 1)[0].strip()
    if "—" in heading:
        heading = heading.split("—", 1)[0].strip()
    return heading or "regime-window"


def _assess_regime_label(
    *,
    n_days: int | None,
    total_return_pct: float | None,
    sharpe: float | None,
    max_drawdown_pct: float | None,
) -> tuple[str, str]:
    if n_days is None or n_days < MIN_REGIME_OBS:
        return ASSESS_WAIT, f"관측 {n_days or 0}개로 최소 {MIN_REGIME_OBS}개보다 적습니다."
    if total_return_pct is not None and total_return_pct < 0:
        return ASSESS_STRESS, "해당 레짐의 누적 수익률이 음수입니다."
    if sharpe is not None and sharpe < SHARPE_STRESS_THRESHOLD:
        return (
            ASSESS_STRESS,
            f"샤프 {sharpe:.2f}가 기준 {SHARPE_STRESS_THRESHOLD:.2f}보다 낮습니다.",
        )
    if max_drawdown_pct is not None and max_drawdown_pct >= MAX_DRAWDOWN_STRESS_THRESHOLD:
        return (
            ASSESS_STRESS,
            (
                f"최대 낙폭 {max_drawdown_pct:.2f}%가 기준 "
                f"{MAX_DRAWDOWN_STRESS_THRESHOLD:.2f}% 이상입니다."
            ),
        )
    return ASSESS_PASS, "관측 수, 샤프, 낙폭 기준을 통과했습니다."


def _money_state(payload: dict[str, Any] | None) -> MoneyState:
    live = payload.get("live_money_state") if isinstance(payload, dict) else None
    live = live if isinstance(live, dict) else {}
    status = _str_or_none(live.get("status") or payload.get("status") if payload else None)
    can_submit = live.get("can_submit_real_orders")
    stage = _str_or_none(payload.get("stage") if isinstance(payload, dict) else None)
    detail = live.get("detail") or (
        payload.get("blocking_gate") if isinstance(payload, dict) else ""
    )
    return MoneyState(
        status=status,
        can_submit_real_orders=can_submit if isinstance(can_submit, bool) else None,
        stage=stage,
        detail_ko=str(detail or ""),
    )


def _edge_autoarm_state(payload: dict[str, Any] | None) -> EdgeAutoarmState:
    if not isinstance(payload, dict):
        return EdgeAutoarmState(
            action=None,
            reason=None,
            current_rung=None,
            next_rung=None,
            detail_ko="edge-autoarm 결정 JSON을 읽지 못했습니다.",
        )
    action = _str_or_none(payload.get("action"))
    reason = _str_or_none(payload.get("reason"))
    current_rung = _int_or_none(payload.get("current_rung") or payload.get("rung"))
    next_rung = _int_or_none(payload.get("next_rung"))
    return EdgeAutoarmState(
        action=action,
        reason=reason,
        current_rung=current_rung,
        next_rung=next_rung,
        detail_ko=(
            "엣지 자동 무장은 대기 상태입니다."
            if action in {"WAIT_EDGE", "NO_EDGE", "WAIT", None}
            else "edge-autoarm가 무장 또는 승격 상태라 no-live 계약은 대기해야 합니다."
        ),
    )


def _forward_snapshots(board: dict[str, Any] | None) -> tuple[ForwardTrackSnapshot, ...]:
    rows = board.get("rows") if isinstance(board, dict) else None
    rows = rows if isinstance(rows, list) else []
    return tuple(ForwardTrackSnapshot.from_row(row) for row in rows if isinstance(row, dict))


def _regime_metrics(windows: tuple[RegimeWindow, ...]) -> dict[str, Any]:
    labels = [label for window in windows for label in window.labels]
    pass_count = len([label for label in labels if label.assessment == ASSESS_PASS])
    wait_count = len([label for label in labels if label.assessment == ASSESS_WAIT])
    stress_count = len([label for label in labels if label.assessment == ASSESS_STRESS])
    return {
        "window_count": len(windows),
        "label_count": len(labels),
        "pass_label_count": pass_count,
        "wait_label_count": wait_count,
        "stress_label_count": stress_count,
        "min_regime_obs": MIN_REGIME_OBS,
        "sharpe_stress_threshold": SHARPE_STRESS_THRESHOLD,
        "max_drawdown_stress_threshold": MAX_DRAWDOWN_STRESS_THRESHOLD,
        "track_labels": [window.track_label for window in windows],
        "stress_labels": [
            f"{window.track_label}:{label.label}"
            for window in windows
            for label in window.labels
            if label.assessment == ASSESS_STRESS
        ],
        "wait_labels": [
            f"{window.track_label}:{label.label}"
            for window in windows
            for label in window.labels
            if label.assessment == ASSESS_WAIT
        ],
    }


def _cost_stress_rows(
    *,
    regime_windows: tuple[RegimeWindow, ...],
    forward_snapshots: tuple[ForwardTrackSnapshot, ...],
    execution_snapshot: ExecutionCostSnapshot,
    money_state: MoneyState,
    edge_state: EdgeAutoarmState,
) -> tuple[CostStressRow, ...]:
    affected_tracks = tuple(
        sorted(
            {
                *(window.track_label for window in regime_windows if window.track_label),
                *(snapshot.key for snapshot in forward_snapshots if snapshot.key),
            }
        )
    )
    ready = _execution_cost_observable(execution_snapshot) and _money_no_live_aligned(
        money_state, edge_state
    )
    rows = []
    for bps in COST_STRESS_BPS:
        rows.append(
            CostStressRow(
                stress_bps=bps,
                status=PROPOSED if ready else WAIT,
                affected_tracks=affected_tracks,
                execution_observation_ko=(
                    f"브로커 거부 {execution_snapshot.rejected_orders}건, "
                    f"KIS smoke={execution_snapshot.smoke_state or 'unknown'}."
                ),
                reason_ko=(
                    f"{bps}bp 비용 충격을 레짐별 paper 성과에 덧씌워 봅니다. "
                    "실주문 허가가 아니라 no-live 민감도 설계입니다."
                    if ready
                    else f"{bps}bp 비용 충격 행은 증거 또는 no-live 정렬을 더 기다립니다."
                ),
            )
        )
    return tuple(rows)


def _exclusion_criteria() -> tuple[ExclusionCriterion, ...]:
    return (
        ExclusionCriterion(
            candidate_key="live_rearm_or_order_submission",
            status=EXCLUDED,
            reason_ko="PREVIEW_ONLY와 WAIT_EDGE를 보존해야 하므로 실주문·재무장은 제외합니다.",
        ),
        ExclusionCriterion(
            candidate_key="single_regime_overfit",
            status=EXCLUDED,
            reason_ko="관측이 적은 RISK_OFF 같은 구간 하나에 맞춘 과적합 변경은 제외합니다.",
        ),
        ExclusionCriterion(
            candidate_key="same_signal_retest_without_cost_stress",
            status=EXCLUDED,
            reason_ko="같은 NO_EDGE 신호를 비용 민감도 없이 반복 측정하는 후보는 제외합니다.",
        ),
    )


def _validation_gates(
    *,
    evidence_surfaces: tuple[EvidenceSurface, ...],
    regime_windows: tuple[RegimeWindow, ...],
    regime_metrics: dict[str, Any],
    execution_snapshot: ExecutionCostSnapshot,
    money_state: MoneyState,
    edge_state: EdgeAutoarmState,
    forward_snapshots: tuple[ForwardTrackSnapshot, ...],
    cost_rows: tuple[CostStressRow, ...],
    learning_summary: dict[str, Any],
    released_summary: dict[str, Any],
    pipeline_payload: dict[str, Any] | None,
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
            else "필수 sidecar 8개를 읽었습니다."
        ),
        required_evidence=required_inputs,
    )

    pipeline_overall = _pipeline_overall(pipeline_payload)
    pipeline_gate = ValidationGate(
        gate_id="pipeline-liveness",
        status=GATE_FAIL if pipeline_overall in {"CRITICAL", "FAIL", "FAILED"} else GATE_PASS,
        summary_ko=(
            "파이프라인 생존 상태가 critical/fail입니다."
            if pipeline_overall in {"CRITICAL", "FAIL", "FAILED"}
            else "파이프라인 생존 상태가 OK입니다."
        ),
        required_evidence=("automation/pipeline-liveness-last-run:LAST_RUN.md",),
    )

    no_live_gate = ValidationGate(
        gate_id="no-live-safety",
        status=GATE_PASS,
        summary_ko=(
            "보고서는 읽기 전용입니다. "
            f"money_state={money_state.status or 'unknown'}, "
            f"edge_autoarm={edge_state.action or 'unknown'}."
        ),
        required_evidence=(
            "automation/money-path-last-run:LAST_RUN.md",
            "automation/edge-autoarm-last-run:LAST_RUN.md",
        ),
    )

    money_aligned = _money_no_live_aligned(money_state, edge_state)
    money_gate = ValidationGate(
        gate_id="money-gate-alignment",
        status=GATE_PASS if money_aligned else GATE_WAIT,
        summary_ko=(
            "현재 돈 경로는 실주문이 아니라 엣지 대기 상태와 맞습니다."
            if money_aligned
            else "돈 경로 또는 edge-autoarm 상태가 no-live 대기와 맞지 않습니다."
        ),
        required_evidence=(
            "automation/money-path-last-run:LAST_RUN.md",
            "automation/edge-autoarm-last-run:LAST_RUN.md",
        ),
    )

    usable_labels = [
        label
        for window in regime_windows
        for label in window.labels
        if label.assessment in {ASSESS_PASS, ASSESS_STRESS}
    ]
    regime_gate = ValidationGate(
        gate_id="regime-window-coverage",
        status=GATE_PASS if regime_windows and usable_labels else GATE_WAIT,
        summary_ko=(
            (
                f"레짐 창 {len(regime_windows)}개와 판독 가능한 레짐 라벨 "
                f"{len(usable_labels)}개를 읽었습니다."
            )
            if regime_windows and usable_labels
            else "레짐 창은 있으나 최소 관측을 넘은 라벨이 아직 없습니다."
        ),
        required_evidence=("automation/regime-stratify-last-run:LAST_RUN.md",),
    )

    execution_gate = ValidationGate(
        gate_id="execution-cost-observability",
        status=GATE_PASS if _execution_cost_observable(execution_snapshot) else GATE_WAIT,
        summary_ko=(
            "브로커 거부, 파싱된 오류, KIS smoke 증거를 비용 민감도 입력으로 읽었습니다."
            if _execution_cost_observable(execution_snapshot)
            else "실행 품질 비용 증거 일부가 부족합니다."
        ),
        required_evidence=("automation/execution-quality-last-run:LAST_RUN.md",),
    )

    stress_gate = ValidationGate(
        gate_id="cost-stress-coverage",
        status=(
            GATE_PASS
            if tuple(row.stress_bps for row in cost_rows) == COST_STRESS_BPS
            else GATE_WAIT
        ),
        summary_ko="10/25/50bp 비용 민감도 행을 생성했습니다.",
        required_evidence=(
            "automation/execution-quality-last-run:LAST_RUN.md",
            "automation/rebalance-paper-forward-last-run:LAST_RUN.md",
        ),
    )

    forward_gate = ValidationGate(
        gate_id="forward-track-context",
        status=GATE_PASS if forward_snapshots else GATE_WAIT,
        summary_ko=(
            f"forward 트랙 {len(forward_snapshots)}개를 비용 적용 대상 문맥으로 읽었습니다."
            if forward_snapshots
            else "forward 트랙 문맥이 부족합니다."
        ),
        required_evidence=("automation/rebalance-paper-forward-last-run:LAST_RUN.md",),
    )

    learning_gate = ValidationGate(
        gate_id="learning-ledger-duplication",
        status=GATE_FAIL if learning_summary.get("current_candidate_suppressed") else GATE_PASS,
        summary_ko=(
            "학습 장부가 현재 후보를 억제했습니다."
            if learning_summary.get("current_candidate_suppressed")
            else "학습 장부에서 현재 후보 억제 신호가 없습니다."
        ),
        required_evidence=("automation/autonomous-evolution-last-run:learning_ledger.json",),
    )

    release_gate = ValidationGate(
        gate_id="released-work-closure",
        status=GATE_PASS if released_summary.get("has_completed_candidate") else GATE_WAIT,
        summary_ko=(
            "현재 checkout/released-work가 완료 후보 마커를 포함합니다."
            if released_summary.get("has_completed_candidate")
            else "released-work가 아직 완료 후보 마커를 보지 못했습니다."
        ),
        required_evidence=(
            "specs/132-broad-no-edge-regime-cost-robustness/contracts/"
            "broad-no-edge-regime-cost-robustness.md",
        ),
    )

    return (
        input_gate,
        pipeline_gate,
        no_live_gate,
        money_gate,
        regime_gate,
        execution_gate,
        stress_gate,
        forward_gate,
        learning_gate,
        release_gate,
    )


def _overall_status(gates: tuple[ValidationGate, ...]) -> str:
    hard_fail_gate_ids = {
        "input-evidence",
        "pipeline-liveness",
        "learning-ledger-duplication",
    }
    if any(gate.status == GATE_FAIL and gate.gate_id in hard_fail_gate_ids for gate in gates):
        return BLOCKED
    if any(gate.status == GATE_WAIT for gate in gates):
        return OBSERVATION_WAIT
    return CONTRACT_READY


def _headline(
    overall: str,
    metrics: dict[str, Any],
    cost_rows: tuple[CostStressRow, ...],
) -> str:
    if overall == BLOCKED:
        return "레짐·비용 견고성 계약을 만들 핵심 증거가 부족하거나 파이프라인이 막혔습니다."
    if overall == OBSERVATION_WAIT:
        return (
            "레짐·비용 견고성 no-live 계약은 생성됐지만 일부 관측 또는 출시 증거가 더 필요합니다. "
            f"현재 레짐 창은 {metrics.get('window_count')}개입니다."
        )
    return (
        "레짐·비용 견고성 no-live 계약이 준비됐습니다. "
        f"{len(cost_rows)}개 비용 민감도 행과 레짐별 취약 구간을 보고합니다."
    )


def _learning_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    entries = payload.get("entries") if isinstance(payload, dict) else None
    entries = entries if isinstance(entries, list) else []
    matching = [
        entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("candidate_id") == COMPLETED_CANDIDATE_ID
    ]
    latest_decision = (
        matching[-1].get("decision")
        if matching and isinstance(matching[-1].get("decision"), str)
        else None
    )
    suppressed = latest_decision is not None and latest_decision.lower() in {
        "suppressed",
        "rejected",
        "discarded",
        "reject",
        "discard",
        "unsafe",
    }
    return {
        "entry_count": len(entries),
        "has_current_candidate_memory": bool(matching),
        "latest_decision": latest_decision,
        "current_candidate_suppressed": suppressed,
    }


def _released_work_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    released = payload.get("released_work") if isinstance(payload, dict) else None
    released = released if isinstance(released, list) else []
    candidate_ids = [
        str(entry.get("candidate_id"))
        for entry in released
        if isinstance(entry, dict) and entry.get("candidate_id")
    ]
    return {
        "released_count": len(candidate_ids),
        "has_completed_candidate": COMPLETED_CANDIDATE_ID in candidate_ids,
    }


def _pipeline_overall(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    raw = payload.get("overall") or payload.get("overall_status") or payload.get("status")
    return str(raw).upper() if raw is not None else None


def _money_no_live_aligned(money_state: MoneyState, edge_state: EdgeAutoarmState) -> bool:
    money_safe = (
        money_state.status in {"PREVIEW_ONLY", "NO_EDGE_YET", "WAIT_EDGE"}
        or money_state.stage == "NO_EDGE_YET"
        or money_state.can_submit_real_orders is False
    )
    edge_waiting = edge_state.action in {"WAIT_EDGE", "NO_EDGE", "WAIT", None}
    return money_safe and edge_waiting


def _execution_cost_observable(snapshot: ExecutionCostSnapshot) -> bool:
    return (
        snapshot.rejected_orders is not None
        and snapshot.parsed_broker_errors is not None
        and snapshot.broker_error_observation_rate is not None
        and snapshot.smoke_state is not None
        and snapshot.smoke_error_rate is not None
        and snapshot.live_gate_ok is not None
    )


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _float_or_none(value: object) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _table(value: object) -> str:
    if value is None:
        return "-"
    return str(value).replace("|", "\\|").replace("\n", " ")


__all__ = [
    "BLOCKED",
    "CONTRACT_READY",
    "OBSERVATION_WAIT",
    "build_broad_no_edge_regime_cost_robustness",
]

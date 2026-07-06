"""스펙 097 — 비용 차감 엣지 no-live 실험 계약.

선택된 자율 후보 `candidate-cost-adjusted-edge-experiment`를 사람이 sidecar를
다시 조립하지 않아도 되는 기계 판독 보고서로 고정한다.

안전 경계: 읽기 전용·순수·결정론. 브로커 API, 주문, 자본 배분, live 전략,
whitelist/caps, 비밀값, 헌법/커널, 외부 유료 서비스는 건드리지 않는다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from auto_invest.analytics.forward_tournament import OBS_HEALTH_BLOCKED, UNKNOWN

SCHEMA_VERSION = "1.0"
EXPERIMENT_ID = "cost-adjusted-edge-experiment"
COMPLETED_CANDIDATE_ID = "candidate-cost-adjusted-edge-experiment"

CONTRACT_READY = "CONTRACT_READY"
OBSERVATION_WAIT = "OBSERVATION_WAIT"
BLOCKED = "BLOCKED"

PARSE_OK = "ok"
PARSE_MISSING = "missing"
PARSE_MALFORMED = "malformed"

GATE_PASS = "PASS"
GATE_WAIT = "WAIT"
GATE_FAIL = "FAIL"

PROVISIONAL = "PROVISIONAL"
WAIT = "WAIT"

STRESS_BPS: tuple[int, ...] = (10, 25, 50)

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
    ("rebalance-paper-forward", "automation/rebalance-paper-forward-last-run", "LAST_RUN.md"),
    ("execution-quality", "automation/execution-quality-last-run", "LAST_RUN.md"),
    ("money-path", "automation/money-path-last-run", "LAST_RUN.md"),
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
class ForwardCostTrack:
    key: str
    label_ko: str
    is_incumbent: bool
    verdict: str | None
    comparability: str
    n_obs: int | None
    min_obs: int | None
    rank: int | None
    total_return_pct: float | None
    max_drawdown_pct: float | None
    universe: tuple[str, ...]

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ForwardCostTrack:
        return cls(
            key=str(row.get("key") or ""),
            label_ko=str(row.get("label") or row.get("label_ko") or row.get("key") or ""),
            is_incumbent=bool(row.get("is_incumbent")),
            verdict=row.get("verdict") if isinstance(row.get("verdict"), str) else None,
            comparability=str(row.get("comparability") or UNKNOWN),
            n_obs=_int_or_none(row.get("n_obs")),
            min_obs=_int_or_none(row.get("min_obs") or row.get("min_obs_required")),
            rank=_int_or_none(row.get("rank")),
            total_return_pct=_float_or_none(row.get("total_return_pct")),
            max_drawdown_pct=_float_or_none(row.get("max_drawdown_pct")),
            universe=_string_tuple(row.get("universe")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label_ko": self.label_ko,
            "is_incumbent": self.is_incumbent,
            "verdict": self.verdict,
            "comparability": self.comparability,
            "n_obs": self.n_obs,
            "min_obs": self.min_obs,
            "rank": self.rank,
            "total_return_pct": self.total_return_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "universe": list(self.universe),
        }


@dataclass(frozen=True)
class CostAdjustedCandidate:
    track_key: str
    label_ko: str
    is_incumbent: bool
    base_total_return_pct: float
    stress_bps: int
    stress_cost_pct: float
    cost_adjusted_return_pct: float
    status: str
    reason_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_key": self.track_key,
            "label_ko": self.label_ko,
            "is_incumbent": self.is_incumbent,
            "base_total_return_pct": self.base_total_return_pct,
            "stress_bps": self.stress_bps,
            "stress_cost_pct": self.stress_cost_pct,
            "cost_adjusted_return_pct": self.cost_adjusted_return_pct,
            "status": self.status,
            "reason_ko": self.reason_ko,
        }


@dataclass(frozen=True)
class ExecutionCostSnapshot:
    overall_status: str | None
    monitor_verdict: str | None
    latest_signal: str | None
    cumulative_pnl_usd: float | None
    rejected_orders: int
    parsed_broker_errors: int
    broker_error_observation_rate: float | None
    kis_msg_codes: dict[str, int]
    smoke_state: str | None
    smoke_error_rate: float | None
    cost_basis_complete: bool
    detail_ko: str

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
            "cost_basis_complete": self.cost_basis_complete,
            "detail_ko": self.detail_ko,
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
class CostAdjustedEdgeExperimentReport:
    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    experiment_id: str
    completed_candidate_id: str
    overall_status: str
    headline_ko: str
    required_inputs: tuple[str, ...]
    evidence_surfaces: tuple[EvidenceSurface, ...]
    forward_tracks: tuple[ForwardCostTrack, ...]
    execution_cost: ExecutionCostSnapshot
    cost_adjusted_candidates: tuple[CostAdjustedCandidate, ...]
    cost_metrics: dict[str, Any]
    money_state: MoneyState
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
            "overall_status": self.overall_status,
            "headline_ko": self.headline_ko,
            "required_inputs": list(self.required_inputs),
            "evidence_surfaces": [surface.to_dict() for surface in self.evidence_surfaces],
            "forward_tracks": [track.to_dict() for track in self.forward_tracks],
            "execution_cost": self.execution_cost.to_dict(),
            "cost_adjusted_candidates": [
                candidate.to_dict() for candidate in self.cost_adjusted_candidates
            ],
            "cost_metrics": self.cost_metrics,
            "money_state": self.money_state.to_dict(),
            "validation_gates": [gate.to_dict() for gate in self.validation_gates],
            "learning_summary": self.learning_summary,
            "released_work_summary": self.released_work_summary,
            "safety_boundary": list(self.safety_boundary),
        }

    def as_markdown(self) -> str:
        lines = [
            f"# 비용 차감 no-live 엣지 실험 계약 (as of {self.timestamp_utc})",
            "",
            self.headline_ko,
            "",
            "## 요약",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| experiment_id | `{self.experiment_id}` |",
            f"| completed_candidate_id | `{self.completed_candidate_id}` |",
            f"| overall_status | `{self.overall_status}` |",
            f"| cost_basis_complete | {self.execution_cost.cost_basis_complete} |",
            f"| money_state | `{self.money_state.status or 'unknown'}` |",
            "",
            "## 비용 스트레스 후보",
            "",
            "| 트랙 | incumbent | base_return_pct | stress_bps | adjusted_return_pct | 상태 |",
            "|------|-----------|----------------:|-----------:|--------------------:|------|",
        ]
        for candidate in self.cost_adjusted_candidates:
            lines.append(
                f"| `{_table(candidate.track_key)}` | "
                f"{'yes' if candidate.is_incumbent else 'no'} | "
                f"{candidate.base_total_return_pct:.2f} | {candidate.stress_bps} | "
                f"{candidate.cost_adjusted_return_pct:.2f} | `{candidate.status}` |"
            )
        lines += [
            "",
            "## 실행 비용 근거",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| monitor_verdict | `{_table(self.execution_cost.monitor_verdict)}` |",
            f"| latest_signal | `{_table(self.execution_cost.latest_signal)}` |",
            f"| cumulative_pnl_usd | {_table(self.execution_cost.cumulative_pnl_usd)} |",
            f"| rejected_orders | {self.execution_cost.rejected_orders} |",
            f"| parsed_broker_errors | {self.execution_cost.parsed_broker_errors} |",
            f"| smoke_state | `{_table(self.execution_cost.smoke_state)}` |",
            "",
            "## 검증 게이트",
            "",
            "| 게이트 | 상태 | 설명 |",
            "|--------|------|------|",
        ]
        for gate in self.validation_gates:
            lines.append(
                f"| `{_table(gate.gate_id)}` | `{gate.status}` | "
                f"{_table(gate.summary_ko)} |"
            )
        lines += ["", "## 안전 경계", ""]
        for invariant in self.safety_boundary:
            lines.append(f"- {invariant}")
        lines += ["", "## 결정 JSON", "", "```json"]
        lines.append(json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        lines.append("```")
        return "\n".join(lines)


def build_cost_adjusted_edge_experiment(
    evidence_texts: dict[str, str | None],
    *,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> CostAdjustedEdgeExperimentReport:
    now = _as_utc(now)
    timestamp = now.isoformat().replace("+00:00", "Z")

    forward_board, forward_status, forward_summary = _parse_forward_board(
        evidence_texts.get("rebalance-paper-forward")
    )
    execution_payload, execution_status, execution_summary = _parse_markdown_or_json(
        evidence_texts.get("execution-quality")
    )
    money_payload, money_status, money_summary = _parse_markdown_or_json(
        evidence_texts.get("money-path")
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
        "rebalance-paper-forward": (forward_status, forward_summary),
        "execution-quality": (execution_status, execution_summary),
        "money-path": (money_status, money_summary),
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

    board = forward_board or {}
    tracks = tuple(
        ForwardCostTrack.from_row(row)
        for row in board.get("rows", [])
        if isinstance(row, dict)
    )
    required_inputs = tuple(f"{ref}:{filename}" for _, ref, filename in CONSUMED_SIDECARS)
    execution_cost = _execution_cost_snapshot(execution_payload)
    cost_candidates = _cost_adjusted_candidates(tracks)
    money_state = _money_state(money_payload)
    learning_summary = _learning_summary(ledger_payload)
    released_summary_dict = _released_work_summary(released_payload)
    metrics = _cost_metrics(board=board, tracks=tracks, candidates=cost_candidates)
    validation_gates = _validation_gates(
        evidence_surfaces=evidence_surfaces,
        board=board,
        candidates=cost_candidates,
        metrics=metrics,
        execution_cost=execution_cost,
        money_state=money_state,
        learning_summary=learning_summary,
        released_summary=released_summary_dict,
        pipeline_payload=pipeline_payload,
    )
    overall = _overall_status(validation_gates)
    headline = _headline(overall, metrics, execution_cost)

    return CostAdjustedEdgeExperimentReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=timestamp,
        experiment_id=EXPERIMENT_ID,
        completed_candidate_id=COMPLETED_CANDIDATE_ID,
        overall_status=overall,
        headline_ko=headline,
        required_inputs=required_inputs,
        evidence_surfaces=evidence_surfaces,
        forward_tracks=tracks,
        execution_cost=execution_cost,
        cost_adjusted_candidates=cost_candidates,
        cost_metrics=metrics,
        money_state=money_state,
        validation_gates=validation_gates,
        learning_summary=learning_summary,
        released_work_summary=released_summary_dict,
        safety_boundary=SAFETY_BOUNDARY,
    )


def _parse_forward_board(text: str | None) -> tuple[dict[str, Any] | None, str, str]:
    if text is None:
        return None, PARSE_MISSING, "forward sidecar가 없습니다."
    board = _extract_json_after_header(text, "리더보드 결정 JSON")
    if isinstance(board, dict) and isinstance(board.get("rows"), list):
        return board, PARSE_OK, "forward 리더보드 결정 JSON을 읽었습니다."
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
            if stripped.startswith("```json") or stripped.startswith("```"):
                in_block = True
            continue
        if stripped.startswith("```"):
            break
        buf.append(line)
    if not buf:
        return None
    return _loads_dict("\n".join(buf))


def _loads_dict(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text.strip())
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _execution_cost_snapshot(payload: dict[str, Any] | None) -> ExecutionCostSnapshot:
    if not isinstance(payload, dict):
        return ExecutionCostSnapshot(
            overall_status=None,
            monitor_verdict=None,
            latest_signal=None,
            cumulative_pnl_usd=None,
            rejected_orders=0,
            parsed_broker_errors=0,
            broker_error_observation_rate=None,
            kis_msg_codes={},
            smoke_state=None,
            smoke_error_rate=None,
            cost_basis_complete=False,
            detail_ko="execution-quality 결정 JSON을 읽지 못했습니다.",
        )
    monitor = payload.get("opportunity_monitor")
    monitor = monitor if isinstance(monitor, dict) else {}
    rejections = payload.get("broker_rejections")
    rejections = rejections if isinstance(rejections, dict) else {}
    smoke = payload.get("broker_smoke")
    smoke = smoke if isinstance(smoke, dict) else {}
    cost_basis = payload.get("execution_cost_basis")
    cost_basis = cost_basis if isinstance(cost_basis, dict) else {}
    accepted_or_filled = _int_or_none(cost_basis.get("accepted_or_filled_orders")) or 0
    turnover_observed = cost_basis.get("turnover_observed") is True
    basis_complete = cost_basis.get("basis_complete") is True or (
        turnover_observed and accepted_or_filled > 0
    )
    codes = rejections.get("kis_msg_codes")
    codes_dict = {
        str(key): int(value)
        for key, value in codes.items()
        if isinstance(codes, dict) and _int_or_none(value) is not None
    } if isinstance(codes, dict) else {}
    detail = (
        "accepted/fill 또는 turnover 근거가 있어 비용 기준을 사용할 수 있습니다."
        if basis_complete
        else "실제 체결 비용·회전율 근거가 아직 부족합니다."
    )
    return ExecutionCostSnapshot(
        overall_status=_str_or_none(payload.get("overall_status")),
        monitor_verdict=_str_or_none(monitor.get("verdict")),
        latest_signal=_str_or_none(monitor.get("latest_signal")),
        cumulative_pnl_usd=_float_or_none(monitor.get("cumulative_pnl_usd")),
        rejected_orders=_int_or_none(rejections.get("rejected_orders")) or 0,
        parsed_broker_errors=_int_or_none(rejections.get("parsed_broker_errors")) or 0,
        broker_error_observation_rate=_float_or_none(
            rejections.get("broker_error_observation_rate")
        ),
        kis_msg_codes=codes_dict,
        smoke_state=_str_or_none(smoke.get("smoke_state")),
        smoke_error_rate=_float_or_none(smoke.get("smoke_error_rate")),
        cost_basis_complete=basis_complete,
        detail_ko=detail,
    )


def _cost_adjusted_candidates(
    tracks: tuple[ForwardCostTrack, ...],
) -> tuple[CostAdjustedCandidate, ...]:
    candidates: list[CostAdjustedCandidate] = []
    for track in tracks:
        if track.total_return_pct is None:
            continue
        for stress_bps in STRESS_BPS:
            stress_pct = round(stress_bps / 100.0, 6)
            adjusted = round(track.total_return_pct - stress_pct, 6)
            candidates.append(
                CostAdjustedCandidate(
                    track_key=track.key,
                    label_ko=track.label_ko,
                    is_incumbent=track.is_incumbent,
                    base_total_return_pct=round(track.total_return_pct, 6),
                    stress_bps=stress_bps,
                    stress_cost_pct=stress_pct,
                    cost_adjusted_return_pct=adjusted,
                    status=PROVISIONAL,
                    reason_ko=(
                        "forward 총수익률에서 보수적 비용 스트레스를 차감한 "
                        "no-live 후보 값입니다."
                    ),
                )
            )
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                candidate.stress_bps,
                -candidate.cost_adjusted_return_pct,
                candidate.track_key,
            ),
        )
    )


def _money_state(payload: dict[str, Any] | None) -> MoneyState:
    live = payload.get("live_money_state") if isinstance(payload, dict) else None
    live = live if isinstance(live, dict) else {}
    status = live.get("status") if isinstance(live.get("status"), str) else None
    can_submit = live.get("can_submit_real_orders")
    can_submit_bool = can_submit if isinstance(can_submit, bool) else None
    stage = payload.get("stage") if isinstance(payload, dict) else None
    detail = live.get("detail") or payload.get("blocking_gate") if isinstance(payload, dict) else ""
    return MoneyState(
        status=status,
        can_submit_real_orders=can_submit_bool,
        stage=stage if isinstance(stage, str) else None,
        detail_ko=str(detail or ""),
    )


def _learning_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    entries = payload.get("entries") if isinstance(payload, dict) else None
    entries = entries if isinstance(entries, list) else []
    matching = [
        entry
        for entry in entries
        if isinstance(entry, dict)
        and entry.get("candidate_id") == COMPLETED_CANDIDATE_ID
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


def _cost_metrics(
    *,
    board: dict[str, Any],
    tracks: tuple[ForwardCostTrack, ...],
    candidates: tuple[CostAdjustedCandidate, ...],
) -> dict[str, Any]:
    observed = [track.n_obs for track in tracks if track.n_obs is not None]
    targets = [track.min_obs for track in tracks if track.min_obs is not None]
    max_n_obs = max(observed) if observed else None
    target = max(targets) if targets else None
    remaining = (
        max(target - max_n_obs, 0)
        if target is not None and max_n_obs is not None
        else None
    )
    stressed_50 = [candidate for candidate in candidates if candidate.stress_bps == 50]
    best_50 = max(
        stressed_50,
        key=lambda candidate: candidate.cost_adjusted_return_pct,
        default=None,
    )
    return {
        "track_count": len(tracks),
        "candidate_count": len(candidates),
        "stress_bps": list(STRESS_BPS),
        "forward_comparable_count": _int_or_none(board.get("comparable_count")),
        "max_n_obs": max_n_obs,
        "target_min_obs": target,
        "remaining_observations": remaining,
        "best_50bps_track_key": best_50.track_key if best_50 else None,
        "best_50bps_adjusted_return_pct": (
            best_50.cost_adjusted_return_pct if best_50 else None
        ),
    }


def _validation_gates(
    *,
    evidence_surfaces: tuple[EvidenceSurface, ...],
    board: dict[str, Any],
    candidates: tuple[CostAdjustedCandidate, ...],
    metrics: dict[str, Any],
    execution_cost: ExecutionCostSnapshot,
    money_state: MoneyState,
    learning_summary: dict[str, Any],
    released_summary: dict[str, Any],
    pipeline_payload: dict[str, Any] | None,
) -> tuple[ValidationGate, ...]:
    required_inputs = tuple(f"{ref}:{filename}" for _, ref, filename in CONSUMED_SIDECARS)
    bad_surfaces = [
        surface
        for surface in evidence_surfaces
        if surface.parse_status in {PARSE_MISSING, PARSE_MALFORMED}
    ]
    input_gate = ValidationGate(
        gate_id="input-evidence",
        status=GATE_FAIL if bad_surfaces else GATE_PASS,
        summary_ko=(
            "필수 sidecar 일부를 읽지 못했습니다."
            if bad_surfaces
            else "필수 sidecar 6개를 읽었습니다."
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
            "보고서는 읽기 전용이며 실주문 가능 상태를 요구하지 않습니다. "
            f"현재 money_state={money_state.status or 'unknown'}."
        ),
        required_evidence=("automation/money-path-last-run:LAST_RUN.md",),
    )

    comparable = metrics.get("forward_comparable_count")
    observation_health = board.get("observation_health")
    observation_gate = ValidationGate(
        gate_id="forward-observation-readiness",
        status=(
            GATE_FAIL
            if observation_health == OBS_HEALTH_BLOCKED
            else GATE_PASS
            if isinstance(comparable, int) and comparable > 0
            else GATE_WAIT
        ),
        summary_ko=(
            "forward 관측 품질이 blocked입니다."
            if observation_health == OBS_HEALTH_BLOCKED
            else "비교 가능한 forward track이 있습니다."
            if isinstance(comparable, int) and comparable > 0
            else "forward 관측이 아직 비교 가능 기준에 도달하지 않았습니다."
        ),
        required_evidence=("automation/rebalance-paper-forward-last-run:LAST_RUN.md",),
    )

    execution_gate = ValidationGate(
        gate_id="execution-quality-evidence",
        status=GATE_PASS if execution_cost.overall_status is not None else GATE_FAIL,
        summary_ko=(
            "execution-quality 결정 JSON을 읽었습니다."
            if execution_cost.overall_status is not None
            else "execution-quality 결정 JSON을 읽지 못했습니다."
        ),
        required_evidence=("automation/execution-quality-last-run:LAST_RUN.md",),
    )

    stress_gate = ValidationGate(
        gate_id="cost-stress-candidates",
        status=GATE_PASS if candidates else GATE_FAIL,
        summary_ko=(
            f"비용 스트레스 후보 {len(candidates)}개를 계산했습니다."
            if candidates
            else "비용 스트레스를 계산할 forward 수익률이 없습니다."
        ),
        required_evidence=("automation/rebalance-paper-forward-last-run:LAST_RUN.md",),
    )

    basis_gate = ValidationGate(
        gate_id="cost-basis-completeness",
        status=GATE_PASS if execution_cost.cost_basis_complete else GATE_WAIT,
        summary_ko=execution_cost.detail_ko,
        required_evidence=("automation/execution-quality-last-run:LAST_RUN.md",),
    )

    learning_gate = ValidationGate(
        gate_id="learning-ledger-duplication",
        status=(
            GATE_FAIL
            if learning_summary.get("current_candidate_suppressed")
            else GATE_PASS
        ),
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
            "specs/097-cost-adjusted-edge-experiment/contracts/"
            "cost-adjusted-edge-experiment.md",
        ),
    )

    return (
        input_gate,
        pipeline_gate,
        no_live_gate,
        observation_gate,
        execution_gate,
        stress_gate,
        basis_gate,
        learning_gate,
        release_gate,
    )


def _overall_status(gates: tuple[ValidationGate, ...]) -> str:
    hard_fail_gate_ids = {
        "input-evidence",
        "pipeline-liveness",
        "execution-quality-evidence",
        "cost-stress-candidates",
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
    execution_cost: ExecutionCostSnapshot,
) -> str:
    if overall == BLOCKED:
        return "비용 차감 실험 계약을 만들 핵심 증거가 부족하거나 파이프라인이 막혔습니다."
    remaining = metrics.get("remaining_observations")
    best = metrics.get("best_50bps_track_key")
    best_return = metrics.get("best_50bps_adjusted_return_pct")
    if overall == OBSERVATION_WAIT:
        return (
            "비용 차감 no-live 계약은 생성됐지만 "
            f"forward 비교 가능 판정까지 관측 {remaining}개가 더 필요하고, "
            "실제 체결 비용·회전율 기준은 아직 대기 상태입니다."
        )
    return (
        "비용 차감 no-live 계약이 준비됐고, "
        f"50bps 스트레스 기준 최상위 후보는 {best}({best_return}%)입니다. "
        f"execution latest_signal={execution_cost.latest_signal or 'unknown'}."
    )


def _pipeline_overall(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    raw = payload.get("overall") or payload.get("overall_status") or payload.get("status")
    return str(raw).upper() if raw is not None else None


def _as_utc(now: datetime) -> datetime:
    return now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)


def _int_or_none(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _float_or_none(value: object) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = value.strip().rstrip("%")
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if item is not None)


def _table(value: object) -> str:
    if value is None:
        return "-"
    return str(value).replace("|", "\\|").replace("\n", " ")


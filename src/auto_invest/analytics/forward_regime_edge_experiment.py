"""스펙 095 — forward 레짐 엣지 no-live 실험 계약.

선택된 자율 후보 `candidate-forward-regime-edge-experiment`를 사람이 다시
sidecar를 조립하지 않아도 되는 기계 판독 보고서로 고정한다.

안전 경계: 읽기 전용·순수·결정론. 브로커 API, 주문, 자본 배분, live 전략,
whitelist/caps, 비밀값, 헌법/커널, 외부 유료 서비스는 건드리지 않는다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from auto_invest.analytics.forward_tournament import (
    OBS_HEALTH_BLOCKED,
    PREMATURE,
    UNKNOWN,
    build_track_result,
    rank_tournament,
)

SCHEMA_VERSION = "1.0"
EXPERIMENT_ID = "forward-regime-edge-experiment"
COMPLETED_CANDIDATE_ID = "candidate-forward-regime-edge-experiment"

CONTRACT_READY = "CONTRACT_READY"
OBSERVATION_WAIT = "OBSERVATION_WAIT"
BLOCKED = "BLOCKED"

PARSE_OK = "ok"
PARSE_PRESENT = "present"
PARSE_MISSING = "missing"
PARSE_MALFORMED = "malformed"

GATE_PASS = "PASS"
GATE_WAIT = "WAIT"
GATE_FAIL = "FAIL"

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
    ("money-path", "automation/money-path-last-run", "LAST_RUN.md"),
    ("released-work", "automation/released-work-last-run", "released_work.json"),
    ("evolution-ledger", "automation/autonomous-evolution-last-run", "learning_ledger.json"),
    ("pipeline-liveness", "automation/pipeline-liveness-last-run", "LAST_RUN.md"),
)

TRACKS: tuple[tuple[str, str, str, bool], ...] = (
    ("trend", "추세 필터 ON (드로다운 방어)", "추세 필터 ON", False),
    ("notrend", "추세 필터 OFF (대조군)", "추세 필터 OFF", False),
    ("rmbeta", "위험관리 베타 (스펙 042)", "위험관리 베타", False),
    ("multiasset", "멀티에셋 분산 추세 (스펙 043)", "멀티에셋 분산 추세", False),
    ("global", "글로벌 분산 추세 (라이브 검증, SPY·IEF·GLD)", "글로벌 분산 추세", True),
    ("globalfixed", "글로벌 3자산 추세 고정등가중", "글로벌 3자산 추세 고정", False),
    ("wide", "글로벌 분산 추세 확대 (11 슬리브)", "글로벌 분산 추세 확대", False),
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
class ForwardTrackSnapshot:
    key: str
    label_ko: str
    is_incumbent: bool
    verdict: str | None
    comparability: str
    n_obs: int | None
    min_obs: int | None
    rank: int | None
    calmar: str | None
    sharpe: str | None
    max_drawdown_pct: str | None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ForwardTrackSnapshot:
        return cls(
            key=str(row.get("key") or ""),
            label_ko=str(row.get("label") or row.get("label_ko") or ""),
            is_incumbent=bool(row.get("is_incumbent")),
            verdict=row.get("verdict") if isinstance(row.get("verdict"), str) else None,
            comparability=str(row.get("comparability") or UNKNOWN),
            n_obs=_int_or_none(row.get("n_obs")),
            min_obs=_int_or_none(row.get("min_obs") or row.get("min_obs_required")),
            rank=_int_or_none(row.get("rank")),
            calmar=_str_or_none(row.get("calmar")),
            sharpe=_str_or_none(row.get("sharpe")),
            max_drawdown_pct=_str_or_none(row.get("max_drawdown_pct")),
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
            "calmar": self.calmar,
            "sharpe": self.sharpe,
            "max_drawdown_pct": self.max_drawdown_pct,
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
class RegimeContext:
    verdict: str | None
    corr_current: float | None
    corr_recent_5y_avg: float | None
    today_signal: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "corr_current": self.corr_current,
            "corr_recent_5y_avg": self.corr_recent_5y_avg,
            "today_signal": self.today_signal,
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
class NextObservationGate:
    max_n_obs: int | None
    target_min_obs: int | None
    remaining_observations: int | None
    waiting_tracks: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_n_obs": self.max_n_obs,
            "target_min_obs": self.target_min_obs,
            "remaining_observations": self.remaining_observations,
            "waiting_tracks": list(self.waiting_tracks),
        }


@dataclass(frozen=True)
class ForwardRegimeEdgeExperimentReport:
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
    forward_tracks: tuple[ForwardTrackSnapshot, ...]
    forward_leaderboard: dict[str, Any]
    money_state: MoneyState
    regime_context: RegimeContext
    validation_gates: tuple[ValidationGate, ...]
    next_observation_gate: NextObservationGate
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
            "forward_leaderboard": self.forward_leaderboard,
            "money_state": self.money_state.to_dict(),
            "regime_context": self.regime_context.to_dict(),
            "validation_gates": [gate.to_dict() for gate in self.validation_gates],
            "next_observation_gate": self.next_observation_gate.to_dict(),
            "learning_summary": self.learning_summary,
            "released_work_summary": self.released_work_summary,
            "safety_boundary": list(self.safety_boundary),
        }

    def as_markdown(self) -> str:
        lines = [
            f"# forward 레짐 엣지 no-live 실험 계약 (as of {self.timestamp_utc})",
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
            f"| money_state | `{self.money_state.status or 'unknown'}` |",
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
        lines += [
            "",
            "## forward 트랙",
            "",
            "| 순위 | 트랙 | 판정 | 관측 | 비교 | 낙폭% |",
            "|-----:|------|------|------|------|------:|",
        ]
        for track in self.forward_tracks:
            obs = (
                f"{track.n_obs}/{track.min_obs}"
                if track.n_obs is not None and track.min_obs is not None
                else "?"
            )
            lines.append(
                f"| {track.rank or '-'} | {_table(track.label_ko)} | "
                f"`{track.verdict or 'UNKNOWN'}` | {obs} | "
                f"`{track.comparability}` | {track.max_drawdown_pct or '-'} |"
            )
        lines += [
            "",
            "## 다음 관측 게이트",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| max_n_obs | {self.next_observation_gate.max_n_obs} |",
            f"| target_min_obs | {self.next_observation_gate.target_min_obs} |",
            f"| remaining_observations | {self.next_observation_gate.remaining_observations} |",
            "| waiting_tracks | "
            f"{_table(', '.join(self.next_observation_gate.waiting_tracks) or '-')} |",
            "",
            "## 안전 경계",
            "",
        ]
        for invariant in self.safety_boundary:
            lines.append(f"- {invariant}")
        lines += ["", "## 결정 JSON", "", "```json"]
        lines.append(json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        lines.append("```")
        return "\n".join(lines)


def build_forward_regime_edge_experiment(
    evidence_texts: dict[str, str | None],
    *,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> ForwardRegimeEdgeExperimentReport:
    now = _as_utc(now)
    timestamp = now.isoformat().replace("+00:00", "Z")

    forward_board, forward_status, forward_summary = _parse_forward_board(
        evidence_texts.get("rebalance-paper-forward"),
        now=now,
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
        ForwardTrackSnapshot.from_row(row)
        for row in board.get("rows", [])
        if isinstance(row, dict)
    )
    money_state = _money_state(money_payload)
    regime_context = _regime_context(evidence_texts.get("rebalance-paper-forward"))
    learning_summary = _learning_summary(ledger_payload)
    released_summary_dict = _released_work_summary(released_payload)
    next_observation_gate = _next_observation_gate(tracks)
    validation_gates = _validation_gates(
        evidence_surfaces=evidence_surfaces,
        board=board,
        tracks=tracks,
        money_state=money_state,
        regime_context=regime_context,
        released_summary=released_summary_dict,
        pipeline_payload=pipeline_payload,
    )
    overall = _overall_status(validation_gates)
    headline = _headline(overall, next_observation_gate)

    return ForwardRegimeEdgeExperimentReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=timestamp,
        experiment_id=EXPERIMENT_ID,
        completed_candidate_id=COMPLETED_CANDIDATE_ID,
        overall_status=overall,
        headline_ko=headline,
        required_inputs=tuple(f"{ref}:{filename}" for _, ref, filename in CONSUMED_SIDECARS),
        evidence_surfaces=evidence_surfaces,
        forward_tracks=tracks,
        forward_leaderboard=_leaderboard_summary(board),
        money_state=money_state,
        regime_context=regime_context,
        validation_gates=validation_gates,
        next_observation_gate=next_observation_gate,
        learning_summary=learning_summary,
        released_work_summary=released_summary_dict,
        safety_boundary=SAFETY_BOUNDARY,
    )


def _parse_forward_board(
    text: str | None,
    *,
    now: datetime,
) -> tuple[dict[str, Any] | None, str, str]:
    if text is None:
        return None, PARSE_MISSING, "forward sidecar가 없습니다."
    board = _extract_json_after_header(text, "리더보드 결정 JSON")
    if isinstance(board, dict) and isinstance(board.get("rows"), list):
        return board, PARSE_OK, "forward 리더보드 결정 JSON을 읽었습니다."

    tracks = []
    for key, label, header, incumbent in TRACKS:
        verdict = _extract_json_after_header(text, header)
        tracks.append(
            build_track_result(
                key=key,
                label=label,
                is_incumbent=incumbent,
                verdict_json=verdict if isinstance(verdict, dict) else None,
            )
        )
    ranked = rank_tournament(tracks, as_of_utc=now.isoformat()).to_json_dict()
    if ranked.get("known_count", 0) > 0:
        return ranked, PARSE_OK, "forward 트랙 판정 블록을 읽어 리더보드를 재구성했습니다."
    return None, PARSE_MALFORMED, "forward 리더보드나 트랙 판정 JSON을 읽지 못했습니다."


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
            if stripped.startswith("```json"):
                in_block = True
            continue
        if stripped.startswith("```"):
            break
        buf.append(line)
    if not buf:
        return None
    return _loads_dict("\n".join(buf))


def _extract_json_line_after(text: str | None, marker: str) -> dict[str, Any] | None:
    if not text:
        return None
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if marker in line:
            start = i
            break
    if start is None:
        return None
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return _loads_dict(stripped)
    return None


def _loads_dict(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text.strip())
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


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


def _regime_context(forward_text: str | None) -> RegimeContext:
    monitor = _extract_json_line_after(forward_text, "낙폭 예산 20%")
    regime = monitor.get("regime") if isinstance(monitor, dict) else None
    regime = regime if isinstance(regime, dict) else {}
    return RegimeContext(
        verdict=regime.get("verdict") if isinstance(regime.get("verdict"), str) else None,
        corr_current=_float_or_none(regime.get("corr_current")),
        corr_recent_5y_avg=_float_or_none(regime.get("corr_recent_5y_avg")),
        today_signal=(
            monitor.get("today_signal")
            if isinstance(monitor, dict) and isinstance(monitor.get("today_signal"), dict)
            else {}
        ),
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
    return {
        "entry_count": len(entries),
        "has_current_candidate_memory": bool(matching),
        "latest_decision": (
            matching[-1].get("decision")
            if matching and isinstance(matching[-1].get("decision"), str)
            else None
        ),
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


def _next_observation_gate(
    tracks: tuple[ForwardTrackSnapshot, ...],
) -> NextObservationGate:
    observed = [track.n_obs for track in tracks if track.n_obs is not None]
    targets = [track.min_obs for track in tracks if track.min_obs is not None]
    max_n_obs = max(observed) if observed else None
    target = max(targets) if targets else None
    remaining = (
        max(target - max_n_obs, 0)
        if target is not None and max_n_obs is not None
        else None
    )
    waiting = tuple(
        track.key
        for track in tracks
        if track.comparability in {PREMATURE, UNKNOWN}
        or (
            track.n_obs is not None
            and track.min_obs is not None
            and track.n_obs < track.min_obs
        )
    )
    return NextObservationGate(
        max_n_obs=max_n_obs,
        target_min_obs=target,
        remaining_observations=remaining,
        waiting_tracks=waiting,
    )


def _validation_gates(
    *,
    evidence_surfaces: tuple[EvidenceSurface, ...],
    board: dict[str, Any],
    tracks: tuple[ForwardTrackSnapshot, ...],
    money_state: MoneyState,
    regime_context: RegimeContext,
    released_summary: dict[str, Any],
    pipeline_payload: dict[str, Any] | None,
) -> tuple[ValidationGate, ...]:
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
            else "필수 sidecar 5개를 읽었습니다."
        ),
        required_evidence=tuple(surface.source_ref for surface in evidence_surfaces),
    )

    pipeline_overall = (
        pipeline_payload.get("overall") if isinstance(pipeline_payload, dict) else None
    )
    if pipeline_overall == "CRITICAL":
        pipeline_status = GATE_FAIL
        pipeline_summary = "핵심 파이프라인 생존 감시가 CRITICAL입니다."
    elif pipeline_overall == "DEGRADED":
        pipeline_status = GATE_WAIT
        pipeline_summary = "파이프라인 일부가 지연 상태입니다."
    elif pipeline_overall == "OK":
        pipeline_status = GATE_PASS
        pipeline_summary = "파이프라인 생존 상태가 OK입니다."
    else:
        pipeline_status = GATE_FAIL
        pipeline_summary = "파이프라인 생존 상태를 읽지 못했습니다."

    if money_state.can_submit_real_orders is True:
        no_live_status = GATE_WAIT
        no_live_summary = "돈 경로가 실주문 가능 상태라 no-live 안전 검토가 필요합니다."
    elif money_state.status is None:
        no_live_status = GATE_FAIL
        no_live_summary = "돈 경로 상태를 읽지 못했습니다."
    else:
        no_live_status = GATE_PASS
        no_live_summary = "보고서는 읽기 전용이며 실주문 가능 상태를 요구하지 않습니다."

    incumbent = next((track for track in tracks if track.is_incumbent), None)
    if not tracks or board.get("observation_health") == OBS_HEALTH_BLOCKED:
        forward_status = GATE_FAIL
        forward_summary = "forward 판정 또는 라이브 검증 트랙을 읽지 못했습니다."
    elif incumbent is None or incumbent.comparability == UNKNOWN:
        forward_status = GATE_FAIL
        forward_summary = "incumbent forward 트랙이 비교 불가입니다."
    elif any(track.comparability in {PREMATURE, UNKNOWN} for track in tracks):
        forward_status = GATE_WAIT
        forward_summary = "forward 관측이 아직 비교 가능 기준에 도달하지 않았습니다."
    else:
        forward_status = GATE_PASS
        forward_summary = "incumbent와 후보 트랙이 비교 가능한 관측 수에 도달했습니다."

    regime_gate = ValidationGate(
        gate_id="regime-brittleness",
        status=GATE_PASS if regime_context.verdict else GATE_WAIT,
        summary_ko=(
            f"현재 regime context={regime_context.verdict}를 보고합니다."
            if regime_context.verdict
            else "regime context가 없어 후속 실험에서 별도 확인이 필요합니다."
        ),
        required_evidence=("automation/rebalance-paper-forward-last-run:LAST_RUN.md",),
    )
    closure_gate = ValidationGate(
        gate_id="released-work-closure",
        status=(
            GATE_PASS
            if released_summary["has_completed_candidate"]
            else GATE_WAIT
        ),
        summary_ko=(
            "현재 checkout/released-work가 완료 후보 마커를 포함합니다."
            if released_summary["has_completed_candidate"]
            else "released-work가 아직 이 후보 완료 마커를 보지 못했습니다."
        ),
        required_evidence=("specs/095-forward-regime-edge-experiment/contracts/forward-regime-edge-experiment.md",),
    )

    return (
        input_gate,
        ValidationGate(
            gate_id="pipeline-liveness",
            status=pipeline_status,
            summary_ko=pipeline_summary,
            required_evidence=("automation/pipeline-liveness-last-run:LAST_RUN.md",),
        ),
        ValidationGate(
            gate_id="no-live-safety",
            status=no_live_status,
            summary_ko=no_live_summary,
            required_evidence=("automation/money-path-last-run:LAST_RUN.md",),
        ),
        ValidationGate(
            gate_id="forward-comparability",
            status=forward_status,
            summary_ko=forward_summary,
            required_evidence=("automation/rebalance-paper-forward-last-run:LAST_RUN.md",),
        ),
        regime_gate,
        closure_gate,
    )


def _overall_status(gates: tuple[ValidationGate, ...]) -> str:
    if any(gate.status == GATE_FAIL for gate in gates):
        return BLOCKED
    if any(gate.status == GATE_WAIT for gate in gates):
        return OBSERVATION_WAIT
    return CONTRACT_READY


def _headline(status: str, gate: NextObservationGate) -> str:
    if status == BLOCKED:
        return "핵심 입력이나 파이프라인 상태가 막혀 no-live 실험 계약을 자동 평가할 수 없습니다."
    if status == OBSERVATION_WAIT:
        remaining = gate.remaining_observations
        if remaining is None:
            return "no-live 실험 계약은 생성됐지만 forward 관측 상태 확인이 더 필요합니다."
        return (
            "no-live 실험 계약은 생성됐고, "
            f"비교 가능 판정까지 관측 {remaining}개가 더 필요합니다."
        )
    return "no-live 실험 계약과 검증 기준이 준비됐습니다."


def _leaderboard_summary(board: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "as_of_utc",
        "champion_key",
        "incumbent_key",
        "challenger_key",
        "comparable_count",
        "track_count",
        "known_count",
        "unknown_count",
        "max_n_obs",
        "min_n_obs",
        "observation_health",
        "observation_note",
        "headline",
    )
    return {key: board.get(key) for key in keys}


def _as_utc(now: datetime) -> datetime:
    return now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _table(value: object) -> str:
    return str(value if value is not None else "").replace("|", "/").replace("\n", " ")


__all__ = [
    "BLOCKED",
    "COMPLETED_CANDIDATE_ID",
    "CONSUMED_SIDECARS",
    "CONTRACT_READY",
    "EXPERIMENT_ID",
    "ForwardRegimeEdgeExperimentReport",
    "OBSERVATION_WAIT",
    "SAFETY_BOUNDARY",
    "build_forward_regime_edge_experiment",
]

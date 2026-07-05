"""스펙 096 — 신호 다변화 엣지 no-live 실험 계약.

선택된 자율 후보 `candidate-signal-diversification-edge-experiment`를 사람이
sidecar를 다시 조립하지 않아도 되는 기계 판독 보고서로 고정한다.

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
    UNKNOWN,
    build_track_result,
    rank_tournament,
)

SCHEMA_VERSION = "1.0"
EXPERIMENT_ID = "signal-diversification-edge-experiment"
COMPLETED_CANDIDATE_ID = "candidate-signal-diversification-edge-experiment"

CONTRACT_READY = "CONTRACT_READY"
OBSERVATION_WAIT = "OBSERVATION_WAIT"
BLOCKED = "BLOCKED"

PARSE_OK = "ok"
PARSE_MISSING = "missing"
PARSE_MALFORMED = "malformed"

GATE_PASS = "PASS"
GATE_WAIT = "WAIT"
GATE_FAIL = "FAIL"

PROPOSED = "PROPOSED"
WAIT = "WAIT"

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

TRACK_FAMILIES: dict[str, tuple[str, str]] = {
    "trend": ("broad_equity_timing", "광범위 주식 추세 타이밍"),
    "notrend": ("broad_equity_timing", "광범위 주식 추세 타이밍"),
    "rmbeta": ("risk_managed_beta", "위험관리 베타"),
    "multiasset": ("multi_asset_allocation", "멀티에셋 배분"),
    "global": ("global_diversification", "글로벌 3자산 분산"),
    "globalfixed": ("fixed_weight_allocation", "고정비중 배분"),
    "wide": ("wide_universe_allocation", "확대 유니버스 배분"),
}

FAMILY_TITLES: dict[str, str] = {
    "broad_equity_timing": "광범위 주식 신호 후보",
    "risk_managed_beta": "위험관리 베타 신호 후보",
    "multi_asset_allocation": "멀티에셋 배분 신호 후보",
    "fixed_weight_allocation": "고정비중 배분 신호 후보",
    "wide_universe_allocation": "확대 유니버스 신호 후보",
}


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
    family_key: str
    family_label_ko: str
    is_incumbent: bool
    verdict: str | None
    comparability: str
    n_obs: int | None
    min_obs: int | None
    rank: int | None
    max_drawdown_pct: str | None
    universe: tuple[str, ...]

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ForwardTrackSnapshot:
        key = str(row.get("key") or "")
        family_key, family_label = _family_for_track(key)
        return cls(
            key=key,
            label_ko=str(row.get("label") or row.get("label_ko") or key),
            family_key=family_key,
            family_label_ko=family_label,
            is_incumbent=bool(row.get("is_incumbent")),
            verdict=row.get("verdict") if isinstance(row.get("verdict"), str) else None,
            comparability=str(row.get("comparability") or UNKNOWN),
            n_obs=_int_or_none(row.get("n_obs")),
            min_obs=_int_or_none(row.get("min_obs") or row.get("min_obs_required")),
            rank=_int_or_none(row.get("rank")),
            max_drawdown_pct=_str_or_none(row.get("max_drawdown_pct")),
            universe=_string_tuple(row.get("universe")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label_ko": self.label_ko,
            "family_key": self.family_key,
            "family_label_ko": self.family_label_ko,
            "is_incumbent": self.is_incumbent,
            "verdict": self.verdict,
            "comparability": self.comparability,
            "n_obs": self.n_obs,
            "min_obs": self.min_obs,
            "rank": self.rank,
            "max_drawdown_pct": self.max_drawdown_pct,
            "universe": list(self.universe),
        }


@dataclass(frozen=True)
class SignalFamilySnapshot:
    family_key: str
    label_ko: str
    track_keys: tuple[str, ...]
    track_count: int
    incumbent_present: bool
    max_n_obs: int | None
    verdicts: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "family_key": self.family_key,
            "label_ko": self.label_ko,
            "track_keys": list(self.track_keys),
            "track_count": self.track_count,
            "incumbent_present": self.incumbent_present,
            "max_n_obs": self.max_n_obs,
            "verdicts": list(self.verdicts),
        }


@dataclass(frozen=True)
class SignalCandidate:
    candidate_key: str
    family_key: str
    title_ko: str
    reason_ko: str
    required_inputs: tuple[str, ...]
    overlap_with_incumbent: float | None
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_key": self.candidate_key,
            "family_key": self.family_key,
            "title_ko": self.title_ko,
            "reason_ko": self.reason_ko,
            "required_inputs": list(self.required_inputs),
            "overlap_with_incumbent": self.overlap_with_incumbent,
            "status": self.status,
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
class SignalDiversificationEdgeExperimentReport:
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
    signal_families: tuple[SignalFamilySnapshot, ...]
    proposed_signal_candidates: tuple[SignalCandidate, ...]
    diversification_metrics: dict[str, Any]
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
            "signal_families": [family.to_dict() for family in self.signal_families],
            "proposed_signal_candidates": [
                candidate.to_dict() for candidate in self.proposed_signal_candidates
            ],
            "diversification_metrics": self.diversification_metrics,
            "money_state": self.money_state.to_dict(),
            "validation_gates": [gate.to_dict() for gate in self.validation_gates],
            "learning_summary": self.learning_summary,
            "released_work_summary": self.released_work_summary,
            "safety_boundary": list(self.safety_boundary),
        }

    def as_markdown(self) -> str:
        lines = [
            f"# 신호 다변화 no-live 엣지 실험 계약 (as of {self.timestamp_utc})",
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
            f"| family_count | {self.diversification_metrics.get('family_count')} |",
            f"| money_state | `{self.money_state.status or 'unknown'}` |",
            "",
            "## 신호군",
            "",
            "| 신호군 | 트랙 | incumbent | 최대 관측 | 판정 |",
            "|--------|------|-----------|----------:|------|",
        ]
        for family in self.signal_families:
            lines.append(
                f"| {_table(family.label_ko)} | {_table(', '.join(family.track_keys))} | "
                f"{'yes' if family.incumbent_present else 'no'} | "
                f"{family.max_n_obs if family.max_n_obs is not None else '-'} | "
                f"{_table(', '.join(family.verdicts) or '-')} |"
            )
        lines += [
            "",
            "## 제안 신호 후보",
            "",
            "| 후보 | 신호군 | incumbent 겹침 | 상태 | 이유 |",
            "|------|--------|----------------:|------|------|",
        ]
        for candidate in self.proposed_signal_candidates:
            overlap = (
                f"{candidate.overlap_with_incumbent:.3f}"
                if candidate.overlap_with_incumbent is not None
                else "unknown"
            )
            lines.append(
                f"| `{candidate.candidate_key}` | `{candidate.family_key}` | "
                f"{overlap} | `{candidate.status}` | {_table(candidate.reason_ko)} |"
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


def build_signal_diversification_edge_experiment(
    evidence_texts: dict[str, str | None],
    *,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> SignalDiversificationEdgeExperimentReport:
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
    signal_families = _signal_families(tracks)
    required_inputs = tuple(f"{ref}:{filename}" for _, ref, filename in CONSUMED_SIDECARS)
    candidates = _proposed_signal_candidates(tracks, required_inputs=required_inputs)
    money_state = _money_state(money_payload)
    learning_summary = _learning_summary(ledger_payload)
    released_summary_dict = _released_work_summary(released_payload)
    metrics = _diversification_metrics(
        board=board,
        tracks=tracks,
        signal_families=signal_families,
        candidates=candidates,
    )
    validation_gates = _validation_gates(
        evidence_surfaces=evidence_surfaces,
        board=board,
        tracks=tracks,
        signal_families=signal_families,
        candidates=candidates,
        metrics=metrics,
        money_state=money_state,
        learning_summary=learning_summary,
        released_summary=released_summary_dict,
        pipeline_payload=pipeline_payload,
    )
    overall = _overall_status(validation_gates)
    headline = _headline(overall, metrics, candidates)

    return SignalDiversificationEdgeExperimentReport(
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
        signal_families=signal_families,
        proposed_signal_candidates=candidates,
        diversification_metrics=metrics,
        money_state=money_state,
        validation_gates=validation_gates,
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


def _signal_families(
    tracks: tuple[ForwardTrackSnapshot, ...],
) -> tuple[SignalFamilySnapshot, ...]:
    grouped: dict[str, list[ForwardTrackSnapshot]] = {}
    for track in tracks:
        grouped.setdefault(track.family_key, []).append(track)
    families = []
    for family_key, family_tracks in grouped.items():
        label = family_tracks[0].family_label_ko if family_tracks else family_key
        obs = [track.n_obs for track in family_tracks if track.n_obs is not None]
        verdicts = sorted(
            {
                track.verdict
                for track in family_tracks
                if isinstance(track.verdict, str) and track.verdict
            }
        )
        families.append(
            SignalFamilySnapshot(
                family_key=family_key,
                label_ko=label,
                track_keys=tuple(track.key for track in family_tracks),
                track_count=len(family_tracks),
                incumbent_present=any(track.is_incumbent for track in family_tracks),
                max_n_obs=max(obs) if obs else None,
                verdicts=tuple(verdicts),
            )
        )
    return tuple(sorted(families, key=lambda family: (-family.track_count, family.family_key)))


def _proposed_signal_candidates(
    tracks: tuple[ForwardTrackSnapshot, ...],
    *,
    required_inputs: tuple[str, ...],
) -> tuple[SignalCandidate, ...]:
    incumbent = next((track for track in tracks if track.is_incumbent), None)
    incumbent_universe = set(incumbent.universe) if incumbent else set()
    by_family: dict[str, list[ForwardTrackSnapshot]] = {}
    for track in tracks:
        if track.is_incumbent:
            continue
        if track.family_key == "unknown":
            continue
        by_family.setdefault(track.family_key, []).append(track)

    candidates = []
    for family_key, family_tracks in by_family.items():
        overlap_values = [
            _jaccard(track.universe, tuple(incumbent_universe))
            for track in family_tracks
            if track.universe and incumbent_universe
        ]
        overlap = min(overlap_values) if overlap_values else None
        title = FAMILY_TITLES.get(family_key, f"{family_tracks[0].family_label_ko} 후보")
        status = PROPOSED if overlap is not None and overlap <= 0.5 else WAIT
        candidates.append(
            SignalCandidate(
                candidate_key=family_key,
                family_key=family_key,
                title_ko=title,
                reason_ko=_candidate_reason(family_key, overlap),
                required_inputs=required_inputs,
                overlap_with_incumbent=overlap,
                status=status,
            )
        )
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                1 if candidate.overlap_with_incumbent is None else candidate.overlap_with_incumbent,
                candidate.candidate_key,
            ),
        )
    )


def _diversification_metrics(
    *,
    board: dict[str, Any],
    tracks: tuple[ForwardTrackSnapshot, ...],
    signal_families: tuple[SignalFamilySnapshot, ...],
    candidates: tuple[SignalCandidate, ...],
) -> dict[str, Any]:
    total_tracks = len(tracks)
    largest = signal_families[0] if signal_families else None
    observed = [track.n_obs for track in tracks if track.n_obs is not None]
    targets = [track.min_obs for track in tracks if track.min_obs is not None]
    max_n_obs = max(observed) if observed else None
    target = max(targets) if targets else None
    remaining = (
        max(target - max_n_obs, 0)
        if target is not None and max_n_obs is not None
        else None
    )
    incumbent = next((track for track in tracks if track.is_incumbent), None)
    lowest = next(
        (candidate for candidate in candidates if candidate.overlap_with_incumbent is not None),
        None,
    )
    return {
        "track_count": total_tracks,
        "family_count": len(signal_families),
        "largest_family_key": largest.family_key if largest else None,
        "largest_family_share": (
            round(largest.track_count / total_tracks, 6)
            if largest and total_tracks
            else None
        ),
        "incumbent_family_key": incumbent.family_key if incumbent else None,
        "lowest_overlap_candidate_key": lowest.candidate_key if lowest else None,
        "lowest_overlap_with_incumbent": (
            lowest.overlap_with_incumbent if lowest else None
        ),
        "forward_comparable_count": _int_or_none(board.get("comparable_count")),
        "max_n_obs": max_n_obs,
        "target_min_obs": target,
        "remaining_observations": remaining,
    }


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


def _validation_gates(
    *,
    evidence_surfaces: tuple[EvidenceSurface, ...],
    board: dict[str, Any],
    tracks: tuple[ForwardTrackSnapshot, ...],
    signal_families: tuple[SignalFamilySnapshot, ...],
    candidates: tuple[SignalCandidate, ...],
    metrics: dict[str, Any],
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
            else "필수 sidecar 5개를 읽었습니다."
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

    family_count = metrics.get("family_count")
    signal_gate = ValidationGate(
        gate_id="signal-diversity",
        status=GATE_PASS if isinstance(family_count, int) and family_count >= 3 else GATE_WAIT,
        summary_ko=(
            f"forward 후보가 {family_count}개 신호군으로 분리됩니다."
            if isinstance(family_count, int) and family_count >= 3
            else "신호군 분리 근거가 아직 부족합니다."
        ),
        required_evidence=("automation/rebalance-paper-forward-last-run:LAST_RUN.md",),
    )

    low_overlap = [
        candidate
        for candidate in candidates
        if candidate.overlap_with_incumbent is not None
        and candidate.overlap_with_incumbent <= 0.5
    ]
    incumbent_gate = ValidationGate(
        gate_id="incumbent-overlap",
        status=GATE_PASS if low_overlap else GATE_WAIT,
        summary_ko=(
            f"incumbent와 낮게 겹치는 후보 {len(low_overlap)}개가 있습니다."
            if low_overlap
            else "incumbent와 낮게 겹치는 후보를 아직 계산하지 못했습니다."
        ),
        required_evidence=("automation/rebalance-paper-forward-last-run:LAST_RUN.md",),
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
            "specs/096-signal-diversification-edge-experiment/contracts/"
            "signal-diversification-edge-experiment.md",
        ),
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

    return (
        input_gate,
        pipeline_gate,
        no_live_gate,
        observation_gate,
        signal_gate,
        incumbent_gate,
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
    if any(
        gate.gate_id == "forward-observation-readiness" and gate.status == GATE_WAIT
        for gate in gates
    ):
        return OBSERVATION_WAIT
    if any(gate.status == GATE_WAIT for gate in gates):
        return OBSERVATION_WAIT
    return CONTRACT_READY


def _headline(
    overall: str,
    metrics: dict[str, Any],
    candidates: tuple[SignalCandidate, ...],
) -> str:
    if overall == BLOCKED:
        return "신호 다변화 실험 계약을 만들 핵심 증거가 부족하거나 파이프라인이 막혔습니다."
    family_count = metrics.get("family_count")
    remaining = metrics.get("remaining_observations")
    proposed_count = len([candidate for candidate in candidates if candidate.status == PROPOSED])
    if overall == OBSERVATION_WAIT:
        return (
            "신호 다변화 no-live 계약은 생성됐고, "
            f"{family_count}개 신호군과 낮은 겹침 후보 {proposed_count}개를 분리했습니다. "
            f"forward 비교 가능 판정까지 관측 {remaining}개가 더 필요합니다."
        )
    return (
        "신호 다변화 no-live 계약이 준비됐고, "
        f"{family_count}개 신호군과 낮은 겹침 후보 {proposed_count}개를 보고합니다."
    )


def _pipeline_overall(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    raw = payload.get("overall") or payload.get("overall_status") or payload.get("status")
    return str(raw).upper() if raw is not None else None


def _family_for_track(key: str) -> tuple[str, str]:
    return TRACK_FAMILIES.get(key, ("unknown", "알 수 없는 신호군"))


def _candidate_reason(family_key: str, overlap: float | None) -> str:
    overlap_text = "unknown" if overlap is None else f"{overlap:.3f}"
    reasons = {
        "broad_equity_timing": (
            "현재 incumbent ETF 조합과 다른 개별 주식 폭의 추세 신호라 "
            f"겹침({overlap_text})이 낮은 별도 no-live 후보가 될 수 있습니다."
        ),
        "risk_managed_beta": (
            "주식 베타 방어 신호는 글로벌 3자산 incumbent와 다른 위험 노출을 "
            f"검증하므로 겹침({overlap_text})이 낮습니다."
        ),
        "multi_asset_allocation": (
            "주식·채권 2자산 배분은 금 포함 incumbent와 일부만 겹치므로 "
            f"겹침({overlap_text})을 별도 관찰할 가치가 있습니다."
        ),
        "fixed_weight_allocation": (
            "같은 3자산이라도 가중 방식만 달라 위험 배분 효과를 분리해 볼 수 있습니다."
        ),
        "wide_universe_allocation": (
            "11개 슬리브 확대 유니버스는 incumbent보다 자산 폭이 넓어 "
            f"겹침({overlap_text})이 낮은 신호 후보입니다."
        ),
    }
    return reasons.get(family_key, f"incumbent와 겹침({overlap_text})을 별도 확인합니다.")


def _jaccard(left: tuple[str, ...], right: tuple[str, ...]) -> float | None:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return None
    union = left_set | right_set
    if not union:
        return None
    return round(len(left_set & right_set) / len(union), 6)


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if item is not None)


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _str_or_none(value: Any) -> str | None:
    return str(value) if value is not None else None


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")

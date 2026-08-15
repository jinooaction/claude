"""스펙 136 — 광역 no-edge 꼬리위험 방어·볼록성 no-live 계약.

선택된 자율 후보 `candidate-broad-no-edge-tail-risk-convexity-experiment`를
큰 하락장 방어, 볼록성 proxy, 비용 부담 관점의 기계 판독 보고서로 고정한다.

안전 경계: 읽기 전용·순수·결정론. 브로커 API, 주문, 자본 배분, live 전략,
whitelist/caps, 비밀값, 헌법/커널, 외부 유료 서비스는 건드리지 않는다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "1.0"
CONTRACT_ID = "broad-no-edge-tail-risk-convexity"
COMPLETED_CANDIDATE_ID = "candidate-broad-no-edge-tail-risk-convexity-experiment"
NEXT_CANDIDATE_ID = "candidate-broad-no-edge-vol-target-drawdown-experiment"

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

MIN_FORWARD_TRACKS = 3
MIN_TAIL_REGIME_DAYS = 20
TAIL_WORST_DAY_PCT = -1.5

SAFETY_BOUNDARY: tuple[str, ...] = (
    "no broker API call",
    "no orders",
    "no capital allocation",
    "no live strategy change",
    "no whitelist/caps change",
    "no secret read/write",
    "no external paid service",
    "no constitution/kernel change",
    "tail-risk convexity contract only",
)

CONSUMED_SIDECARS: tuple[tuple[str, str, str], ...] = (
    ("rebalance-paper-forward", "automation/rebalance-paper-forward-last-run", "LAST_RUN.md"),
    ("regime-stratify", "automation/regime-stratify-last-run", "LAST_RUN.md"),
    ("execution-quality", "automation/execution-quality-last-run", "LAST_RUN.md"),
    ("money-path", "automation/money-path-last-run", "LAST_RUN.md"),
    ("edge-autoarm", "automation/edge-autoarm-last-run", "LAST_RUN.md"),
    ("released-work", "automation/released-work-last-run", "released_work.json"),
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
class ForwardTrack:
    key: str
    label_ko: str
    verdict: str | None
    rank: int | None
    n_obs: int | None
    psr_vs_benchmark: float | None
    calmar: float | None
    max_drawdown_pct: float | None
    universe_size: int | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ForwardTrack:
        label = payload.get("label") or payload.get("label_ko") or payload.get("key") or ""
        universe = payload.get("universe")
        return cls(
            key=str(payload.get("key") or ""),
            label_ko=str(label),
            verdict=_str_or_none(payload.get("verdict")),
            rank=_int_or_none(payload.get("rank")),
            n_obs=_int_or_none(payload.get("n_obs")),
            psr_vs_benchmark=_float_or_none(payload.get("psr_vs_benchmark")),
            calmar=_float_or_none(payload.get("calmar") or payload.get("strategy_calmar")),
            max_drawdown_pct=_float_or_none(
                payload.get("max_drawdown_pct") or payload.get("strategy_max_drawdown_pct")
            ),
            universe_size=_int_or_none(payload.get("universe_size"))
            or (len(universe) if isinstance(universe, list) else None),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label_ko": self.label_ko,
            "verdict": self.verdict,
            "rank": self.rank,
            "n_obs": self.n_obs,
            "psr_vs_benchmark": self.psr_vs_benchmark,
            "calmar": self.calmar,
            "max_drawdown_pct": self.max_drawdown_pct,
            "universe_size": self.universe_size,
        }


@dataclass(frozen=True)
class RegimeTailProfile:
    section_count: int
    total_return_days: int
    tail_labels: tuple[str, ...]
    worst_day_pct: float | None
    max_drawdown_pct: float | None
    summary_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_count": self.section_count,
            "total_return_days": self.total_return_days,
            "tail_labels": list(self.tail_labels),
            "worst_day_pct": self.worst_day_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "summary_ko": self.summary_ko,
        }


@dataclass(frozen=True)
class ExecutionCostProfile:
    present: bool
    overall_status: str | None
    latest_signal: str | None
    cumulative_pnl_usd: float | None
    rejected_orders: int
    smoke_state: str | None
    summary_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "present": self.present,
            "overall_status": self.overall_status,
            "latest_signal": self.latest_signal,
            "cumulative_pnl_usd": self.cumulative_pnl_usd,
            "rejected_orders": self.rejected_orders,
            "smoke_state": self.smoke_state,
            "summary_ko": self.summary_ko,
        }


@dataclass(frozen=True)
class ConvexityLane:
    lane_id: str
    status: str
    candidate_rule_ko: str
    required_inputs: tuple[str, ...]
    wait_reason_ko: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "lane_id": self.lane_id,
            "status": self.status,
            "candidate_rule_ko": self.candidate_rule_ko,
            "required_inputs": list(self.required_inputs),
            "wait_reason_ko": self.wait_reason_ko,
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
        return {"action": self.action, "reason": self.reason}


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
class BroadNoEdgeTailRiskConvexityReport:
    schema_version: str
    contract_id: str
    run_id: str
    commit: str
    generated_at_utc: str
    completed_candidate_id: str
    next_candidate_id: str
    overall_status: str
    headline_ko: str
    evidence_surfaces: tuple[EvidenceSurface, ...]
    forward_tracks: tuple[ForwardTrack, ...]
    regime_tail_profile: RegimeTailProfile
    execution_cost_profile: ExecutionCostProfile
    convexity_lanes: tuple[ConvexityLane, ...]
    money_state: MoneyState
    edge_autoarm_state: EdgeAutoarmState
    validation_gates: tuple[ValidationGate, ...]
    safety_boundary: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "contract_id": self.contract_id,
            "run_id": self.run_id,
            "commit": self.commit,
            "generated_at_utc": self.generated_at_utc,
            "completed_candidate_id": self.completed_candidate_id,
            "next_candidate_id": self.next_candidate_id,
            "overall_status": self.overall_status,
            "headline_ko": self.headline_ko,
            "evidence_surfaces": [surface.to_dict() for surface in self.evidence_surfaces],
            "forward_tracks": [track.to_dict() for track in self.forward_tracks],
            "regime_tail_profile": self.regime_tail_profile.to_dict(),
            "execution_cost_profile": self.execution_cost_profile.to_dict(),
            "convexity_lanes": [lane.to_dict() for lane in self.convexity_lanes],
            "money_state": self.money_state.to_dict(),
            "edge_autoarm_state": self.edge_autoarm_state.to_dict(),
            "validation_gates": [gate.to_dict() for gate in self.validation_gates],
            "safety_boundary": list(self.safety_boundary),
        }

    def as_markdown(self) -> str:
        lines = [
            "# 꼬리위험 방어·볼록성 no-live 실험 계약",
            "",
            f"- overall_status: `{self.overall_status}`",
            f"- completed_candidate_id: `{self.completed_candidate_id}`",
            f"- next_candidate_id: `{self.next_candidate_id}`",
            f"- headline: {self.headline_ko}",
            "",
            "## 볼록성 후보 축",
            "",
            "| lane | status | rule |",
            "|------|--------|------|",
        ]
        for lane in self.convexity_lanes:
            lines.append(
                f"| {lane.lane_id} | {lane.status} | "
                f"{lane.candidate_rule_ko.replace('|', '/')} |"
            )
        lines.extend(
            [
                "",
                "## 꼬리위험 증거",
                "",
                f"- {self.regime_tail_profile.summary_ko}",
                f"- {self.execution_cost_profile.summary_ko}",
                "",
                "## 검증 게이트",
                "",
                "| gate | status | summary |",
                "|------|--------|---------|",
            ]
        )
        for gate in self.validation_gates:
            lines.append(
                f"| {gate.gate_id} | {gate.status} | "
                f"{gate.summary_ko.replace('|', '/')} |"
            )
        lines.extend(["", "## 안전 경계", "", "- " + "\n- ".join(self.safety_boundary)])
        return "\n".join(lines)


def build_broad_no_edge_tail_risk_convexity(
    evidence_texts: dict[str, str | None],
    *,
    now: datetime | None = None,
    run_id: str = "local",
    commit: str = "unknown",
) -> BroadNoEdgeTailRiskConvexityReport:
    now = now or datetime.now(tz=UTC)
    parsed = {key: _parse_for_key(key, evidence_texts.get(key)) for key, _, _ in CONSUMED_SIDECARS}
    surfaces = tuple(
        _surface_for(key, ref, filename, evidence_texts.get(key), parsed[key])
        for key, ref, filename in CONSUMED_SIDECARS
    )
    tracks = _forward_tracks(parsed["rebalance-paper-forward"])
    regime = _regime_tail_profile(parsed["regime-stratify"])
    execution = _execution_cost_profile(parsed["execution-quality"])
    money = _money_state(parsed["money-path"])
    edge = _edge_autoarm_state(parsed["edge-autoarm"])
    lanes = _convexity_lanes(tracks, regime, execution)
    released_summary = _released_work_summary(parsed["released-work"])
    liveness_summary = _liveness_summary(parsed["pipeline-liveness"])
    gates = _validation_gates(
        evidence_surfaces=surfaces,
        tracks=tracks,
        regime=regime,
        execution=execution,
        lanes=lanes,
        money_state=money,
        edge_state=edge,
        released_summary=released_summary,
        liveness_summary=liveness_summary,
    )
    overall = _overall_status(gates)
    return BroadNoEdgeTailRiskConvexityReport(
        schema_version=SCHEMA_VERSION,
        contract_id=CONTRACT_ID,
        run_id=run_id,
        commit=commit,
        generated_at_utc=now.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        completed_candidate_id=COMPLETED_CANDIDATE_ID,
        next_candidate_id=NEXT_CANDIDATE_ID,
        overall_status=overall,
        headline_ko=_headline(overall, lanes, regime),
        evidence_surfaces=surfaces,
        forward_tracks=tracks,
        regime_tail_profile=regime,
        execution_cost_profile=execution,
        convexity_lanes=lanes,
        money_state=money,
        edge_autoarm_state=edge,
        validation_gates=gates,
        safety_boundary=SAFETY_BOUNDARY,
    )


def _parse_for_key(key: str, raw: str | None) -> Any:
    if raw is None:
        return None
    if key == "regime-stratify":
        return _parse_regime_sections(raw)
    return _parse_markdown_or_json(raw)


def _surface_for(
    key: str,
    ref: str,
    filename: str,
    raw: str | None,
    parsed: Any,
) -> EvidenceSurface:
    source_ref = f"{ref}:{filename}"
    if raw is None:
        return EvidenceSurface(key, source_ref, PARSE_MISSING, "sidecar 파일 없음")
    if parsed is None or (key == "regime-stratify" and not parsed):
        return EvidenceSurface(key, source_ref, PARSE_MALFORMED, "구조화 파싱 실패")
    return EvidenceSurface(key, source_ref, PARSE_OK, _summary_for(key, parsed))


def _forward_tracks(parsed: Any) -> tuple[ForwardTrack, ...]:
    if not isinstance(parsed, dict):
        return ()
    return tuple(
        sorted(
            (
                ForwardTrack.from_payload(row)
                for row in _items(parsed, "rows")
                if isinstance(row, dict)
            ),
            key=lambda row: (row.rank is None, row.rank or 9999, row.key),
        )
    )


def _regime_tail_profile(parsed: Any) -> RegimeTailProfile:
    sections = parsed if isinstance(parsed, list) else []
    total_days = 0
    tail_labels: set[str] = set()
    worst_values: list[float] = []
    drawdown_values: list[float] = []
    for section in sections:
        total_days = max(total_days, _int_or_none(section.get("total_return_days")) or 0)
        by_label = section.get("by_label") if isinstance(section, dict) else {}
        if not isinstance(by_label, dict):
            continue
        for label, stats in by_label.items():
            if not isinstance(stats, dict):
                continue
            days = _int_or_none(stats.get("n_days")) or 0
            worst = _float_or_none(stats.get("worst_day_pct"))
            drawdown = _float_or_none(stats.get("max_drawdown_pct"))
            if worst is not None:
                worst_values.append(worst)
            if drawdown is not None:
                drawdown_values.append(drawdown)
            has_tail_loss = worst is not None and worst <= TAIL_WORST_DAY_PCT
            has_tail_drawdown = drawdown is not None and drawdown >= 5
            has_risk_off_observation = label == "RISK_OFF" and days > 0
            if (days >= MIN_TAIL_REGIME_DAYS or label == "RISK_OFF") and (
                has_tail_loss or has_tail_drawdown or has_risk_off_observation
            ):
                tail_labels.add(str(label))
    worst_day = min(worst_values) if worst_values else None
    max_drawdown = max(drawdown_values) if drawdown_values else None
    return RegimeTailProfile(
        section_count=len(sections),
        total_return_days=total_days,
        tail_labels=tuple(sorted(tail_labels)),
        worst_day_pct=worst_day,
        max_drawdown_pct=max_drawdown,
        summary_ko=(
            f"레짐 section {len(sections)}개, 꼬리위험 라벨 {len(tail_labels)}개, "
            f"최악 일손익 {worst_day}%를 확인했습니다."
            if sections
            else "regime-stratify 구조화 증거를 읽지 못했습니다."
        ),
    )


def _execution_cost_profile(parsed: Any) -> ExecutionCostProfile:
    if not isinstance(parsed, dict):
        return ExecutionCostProfile(False, None, None, None, 0, None, "실행 품질 증거 없음")
    broker = (
        parsed.get("broker_rejections")
        if isinstance(parsed.get("broker_rejections"), dict)
        else {}
    )
    smoke = parsed.get("broker_smoke") if isinstance(parsed.get("broker_smoke"), dict) else {}
    latest_signal = _str_or_none(parsed.get("latest_signal") or _lookup(parsed, "latest_signal"))
    rejected = _int_or_none(broker.get("rejected_orders")) or 0
    cumulative = _float_or_none(
        parsed.get("cumulative_pnl_usd") or _lookup(parsed, "cumulative_pnl_usd")
    )
    smoke_state = _str_or_none(smoke.get("smoke_state"))
    return ExecutionCostProfile(
        present=True,
        overall_status=_str_or_none(parsed.get("overall_status")),
        latest_signal=latest_signal,
        cumulative_pnl_usd=cumulative,
        rejected_orders=rejected,
        smoke_state=smoke_state,
        summary_ko=(
            f"execution-quality={parsed.get('overall_status')}, signal={latest_signal}, "
            f"거부 {rejected}건, smoke={smoke_state}"
        ),
    )


def _convexity_lanes(
    tracks: tuple[ForwardTrack, ...],
    regime: RegimeTailProfile,
    execution: ExecutionCostProfile,
) -> tuple[ConvexityLane, ...]:
    no_edge_count = sum(track.verdict == "NO_EDGE" for track in tracks)
    has_drawdown_evidence = any(
        (track.max_drawdown_pct or 0) >= 10 for track in tracks
    ) or regime.max_drawdown_pct is not None
    return (
        _lane(
            lane_id="risk_off_convexity_proxy",
            available="RISK_OFF" in regime.tail_labels,
            rule=(
                "RISK_OFF 구간에서 풋 proxy, 장기채/금 convexity proxy, "
                "현금 대기를 별도 후보로 비교한다."
            ),
            inputs=("regime-stratify", "rebalance-paper-forward"),
        ),
        _lane(
            lane_id="caution_drawdown_overlay",
            available=any(label in regime.tail_labels for label in ("CAUTION", "RISK_ON")),
            rule=(
                "CAUTION/RISK_ON 안의 큰 일손실을 기준으로 손실 제한 "
                "오버레이를 no-live로 검증한다."
            ),
            inputs=("regime-stratify",),
        ),
        _lane(
            lane_id="shock_day_loss_cap",
            available=has_drawdown_evidence,
            rule=(
                "forward 후보의 낙폭과 레짐별 최악 일손익을 이용해 "
                "단순 수익률보다 하방 제한을 우선 평가한다."
            ),
            inputs=("rebalance-paper-forward", "regime-stratify"),
        ),
        _lane(
            lane_id="cost_drag_exclusion",
            available=execution.present,
            rule="볼록성 proxy가 보호비용과 체결 거부 비용을 넘지 못하면 live 후보에서 제외한다.",
            inputs=("execution-quality", "rebalance-paper-forward"),
        ),
        _lane(
            lane_id="broad_no_edge_tail_context",
            available=len(tracks) >= MIN_FORWARD_TRACKS and no_edge_count == len(tracks),
            rule=(
                "기존 broad no-edge 상태에서는 평균 수익률 후보보다 "
                "꼬리위험 방어 후보를 우선 분리한다."
            ),
            inputs=("rebalance-paper-forward", "money-path", "edge-autoarm"),
        ),
    )


def _lane(
    *,
    lane_id: str,
    available: bool,
    rule: str,
    inputs: tuple[str, ...],
) -> ConvexityLane:
    return ConvexityLane(
        lane_id=lane_id,
        status=PROPOSED if available else WAIT,
        candidate_rule_ko=rule,
        required_inputs=inputs,
        wait_reason_ko=None if available else "필수 꼬리위험·비용 증거가 아직 부족합니다.",
    )


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
        "completed_candidate_released": COMPLETED_CANDIDATE_ID in released,
        "released_count": len(released),
    }


def _liveness_summary(parsed: Any) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        return {"parseable": False, "overall": None, "non_ok_checks": []}
    checks = []
    for item in _items(parsed, "checks"):
        key = str(item.get("key") or item.get("name") or "")
        status = str(item.get("status") or "")
        watched = {"rebalance-paper-forward", "regime-stratify", "execution-quality"}
        if key in watched and status != "OK":
            checks.append(key)
    return {
        "parseable": True,
        "overall": parsed.get("overall") or parsed.get("overall_status"),
        "non_ok_checks": checks,
    }


def _validation_gates(
    *,
    evidence_surfaces: tuple[EvidenceSurface, ...],
    tracks: tuple[ForwardTrack, ...],
    regime: RegimeTailProfile,
    execution: ExecutionCostProfile,
    lanes: tuple[ConvexityLane, ...],
    money_state: MoneyState,
    edge_state: EdgeAutoarmState,
    released_summary: dict[str, Any],
    liveness_summary: dict[str, Any],
) -> tuple[ValidationGate, ...]:
    required_inputs = tuple(f"{ref}:{filename}" for _, ref, filename in CONSUMED_SIDECARS)
    bad_inputs = [
        surface
        for surface in evidence_surfaces
        if surface.parse_status in {PARSE_MISSING, PARSE_MALFORMED}
    ]
    no_edge_count = sum(track.verdict == "NO_EDGE" for track in tracks)
    proposed_count = sum(lane.status == PROPOSED for lane in lanes)
    money_aligned = _money_no_live_aligned(money_state, edge_state)
    return (
        ValidationGate(
            "input-evidence",
            GATE_FAIL if bad_inputs else GATE_PASS,
            (
                "필수 sidecar 일부를 읽지 못했습니다."
                if bad_inputs
                else "필수 sidecar 7개를 읽었습니다."
            ),
            required_inputs,
        ),
        ValidationGate(
            "forward-no-edge-context",
            (
                GATE_PASS
                if len(tracks) >= MIN_FORWARD_TRACKS and no_edge_count == len(tracks)
                else GATE_WAIT
            ),
            f"forward track {len(tracks)}개 중 NO_EDGE {no_edge_count}개를 읽었습니다.",
            ("automation/rebalance-paper-forward-last-run:LAST_RUN.md",),
        ),
        ValidationGate(
            "tail-regime-coverage",
            GATE_PASS if regime.tail_labels else GATE_WAIT,
            f"꼬리위험 라벨 {len(regime.tail_labels)}개를 확인했습니다.",
            ("automation/regime-stratify-last-run:LAST_RUN.md",),
        ),
        ValidationGate(
            "convexity-lane-coverage",
            GATE_PASS if proposed_count >= 4 else GATE_WAIT,
            f"볼록성 후보 축 {proposed_count}/{len(lanes)}개를 제안했습니다.",
            (
                "automation/rebalance-paper-forward-last-run:LAST_RUN.md",
                "automation/regime-stratify-last-run:LAST_RUN.md",
                "automation/execution-quality-last-run:LAST_RUN.md",
            ),
        ),
        ValidationGate(
            "execution-cost-awareness",
            GATE_PASS if execution.present else GATE_WAIT,
            execution.summary_ko,
            ("automation/execution-quality-last-run:LAST_RUN.md",),
        ),
        ValidationGate(
            "money-gate-alignment",
            GATE_PASS if money_aligned else GATE_WAIT,
            "돈 경로가 PREVIEW_ONLY/NO_EDGE_YET 및 WAIT_EDGE와 맞습니다."
            if money_aligned
            else "돈 경로나 edge-autoarm가 no-live 대기와 맞지 않습니다.",
            (
                "automation/money-path-last-run:LAST_RUN.md",
                "automation/edge-autoarm-last-run:LAST_RUN.md",
            ),
        ),
        ValidationGate(
            "pipeline-liveness",
            GATE_WAIT if liveness_summary.get("non_ok_checks") else GATE_PASS,
            f"관련 sidecar 생존성 대기: {liveness_summary.get('non_ok_checks')}"
            if liveness_summary.get("non_ok_checks")
            else "관련 sidecar 생존성이 OK입니다.",
            ("automation/pipeline-liveness-last-run:LAST_RUN.md",),
        ),
        ValidationGate(
            "released-work-closure",
            GATE_PASS if released_summary.get("completed_candidate_released") else GATE_WAIT,
            "released-work가 이번 꼬리위험 후보를 완료 후보로 읽었습니다."
            if released_summary.get("completed_candidate_released")
            else "released-work에는 아직 이번 꼬리위험 후보가 없습니다.",
            ("automation/released-work-last-run:released_work.json",),
        ),
    )


def _overall_status(gates: tuple[ValidationGate, ...]) -> str:
    statuses = {gate.status for gate in gates}
    if GATE_FAIL in statuses:
        return BLOCKED
    if GATE_WAIT in statuses:
        return OBSERVATION_WAIT
    return CONTRACT_READY


def _headline(
    overall: str,
    lanes: tuple[ConvexityLane, ...],
    regime: RegimeTailProfile,
) -> str:
    if overall == BLOCKED:
        return "필수 증거가 깨져 꼬리위험 방어 후보 계약을 완료할 수 없습니다."
    proposed = sum(lane.status == PROPOSED for lane in lanes)
    return (
        f"레짐별 꼬리위험 라벨 {len(regime.tail_labels)}개와 "
        f"볼록성 후보 축 {proposed}개를 no-live로 엽니다."
    )


def _money_no_live_aligned(money_state: MoneyState, edge_state: EdgeAutoarmState) -> bool:
    return (
        money_state.status in {"PREVIEW_ONLY", "NO_LIVE", None}
        and money_state.stage in {"NO_EDGE_YET", "ACCUMULATING_EDGE", None}
        and money_state.can_submit_real_orders is not True
        and edge_state.action in {"WAIT_EDGE", "NO_EDGE", "WAIT", None}
    )


def _summary_for(key: str, parsed: Any) -> str:
    if key == "regime-stratify" and isinstance(parsed, list):
        return f"stratified_sections={len(parsed)}"
    if not isinstance(parsed, dict):
        return "구조화 입력 존재"
    if key == "rebalance-paper-forward":
        return f"forward_rows={len(_items(parsed, 'rows'))}"
    if key == "execution-quality":
        return f"overall={parsed.get('overall_status')}, signal={parsed.get('latest_signal')}"
    if key == "released-work":
        return f"released_count={len(_items(parsed, 'released_work'))}"
    if key == "pipeline-liveness":
        return f"overall={parsed.get('overall') or parsed.get('overall_status')}"
    if key == "money-path":
        live = (
            parsed.get("live_money_state")
            if isinstance(parsed.get("live_money_state"), dict)
            else {}
        )
        return f"status={live.get('status') or parsed.get('overall_status')}"
    if key == "edge-autoarm":
        return f"action={parsed.get('action')}"
    return "구조화 JSON 존재"


def _parse_markdown_or_json(raw: str) -> Any:
    direct = _parse_json(raw.strip())
    if isinstance(direct, dict):
        return direct
    for candidate in _iter_json_dicts(raw):
        if isinstance(candidate, dict) and (
            "rows" in candidate
            or "live_money_state" in candidate
            or "checks" in candidate
            or "released_work" in candidate
            or "action" in candidate
            or "overall_status" in candidate
        ):
            return candidate
    return None


def _parse_regime_sections(raw: str) -> list[dict[str, Any]] | None:
    sections = [
        candidate
        for candidate in _iter_json_dicts(raw)
        if isinstance(candidate, dict) and "by_label" in candidate
    ]
    return sections or None


def _parse_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _iter_json_dicts(text: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    objects: list[dict[str, Any]] = []
    index = 0
    while True:
        index = text.find("{", index)
        if index < 0:
            return objects
        try:
            parsed, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            index += 1
            continue
        if isinstance(parsed, dict):
            objects.append(parsed)
        index += max(end, 1)


def _items(payload: Any, key: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(payload, dict):
        return ()
    raw = payload.get(key)
    if isinstance(raw, dict):
        iterable = raw.values()
    elif isinstance(raw, list):
        iterable = raw
    else:
        return ()
    return tuple(item for item in iterable if isinstance(item, dict))


def _lookup(payload: Any, key: str) -> Any:
    if not isinstance(payload, dict):
        return None
    if key in payload:
        return payload[key]
    for value in payload.values():
        found = _lookup(value, key)
        if found is not None:
            return found
    return None


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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


__all__ = [
    "BLOCKED",
    "COMPLETED_CANDIDATE_ID",
    "CONSUMED_SIDECARS",
    "CONTRACT_READY",
    "NEXT_CANDIDATE_ID",
    "OBSERVATION_WAIT",
    "build_broad_no_edge_tail_risk_convexity",
]

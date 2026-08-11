"""스펙 125 — 광역 자산군 방어 회전 no-live 실험 계약.

선택된 자율 후보 `candidate-broad-no-edge-asset-universe-rotation-experiment`를
사람이 sidecar를 다시 조립하지 않아도 되는 기계 판독 보고서로 고정한다.

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
EXPERIMENT_ID = "broad-no-edge-asset-universe-rotation"
COMPLETED_CANDIDATE_ID = "candidate-broad-no-edge-asset-universe-rotation-experiment"
NEXT_CANDIDATE_ID = "candidate-broad-no-edge-multi-horizon-signal-experiment"

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
EXCLUDED = "EXCLUDED"

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
    ("edge-autoarm", "automation/edge-autoarm-last-run", "LAST_RUN.md"),
    ("public-data", "automation/public-data", "LAST_RUN.md"),
    ("released-work", "automation/released-work-last-run", "released_work.json"),
    ("evolution-ledger", "automation/autonomous-evolution-last-run", "learning_ledger.json"),
    ("pipeline-liveness", "automation/pipeline-liveness-last-run", "LAST_RUN.md"),
)

SYMBOL_BUCKETS: dict[str, str] = {
    "SPY": "equity",
    "QQQ": "equity",
    "EFA": "equity",
    "EEM": "equity",
    "IEF": "duration_bond",
    "TLT": "duration_bond",
    "SHY": "cash_proxy",
    "BIL": "cash_proxy",
    "SGOV": "cash_proxy",
    "TBIL": "cash_proxy",
    "LQD": "credit",
    "TIP": "inflation_linked_bond",
    "GLD": "commodity",
    "DBC": "commodity",
    "VNQ": "real_estate",
    "UUP": "currency",
}

PUBLIC_RATES = {"UST2Y", "UST10Y", "UST10Y2Y", "DGS2", "DGS10"}
PUBLIC_VOL = {"VIX"}


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
class ForwardUniverseSnapshot:
    key: str
    label_ko: str
    is_incumbent: bool
    verdict: str | None
    comparability: str
    n_obs: int | None
    min_obs: int | None
    rank: int | None
    universe: tuple[str, ...]
    asset_buckets: tuple[str, ...]

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ForwardUniverseSnapshot:
        universe = _string_tuple(row.get("universe"))
        return cls(
            key=str(row.get("key") or ""),
            label_ko=str(row.get("label") or row.get("label_ko") or row.get("key") or ""),
            is_incumbent=bool(row.get("is_incumbent")),
            verdict=row.get("verdict") if isinstance(row.get("verdict"), str) else None,
            comparability=str(row.get("comparability") or UNKNOWN),
            n_obs=_int_or_none(row.get("n_obs")),
            min_obs=_int_or_none(row.get("min_obs") or row.get("min_obs_required")),
            rank=_int_or_none(row.get("rank")),
            universe=universe,
            asset_buckets=_asset_buckets(universe),
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
            "universe": list(self.universe),
            "asset_buckets": list(self.asset_buckets),
        }


@dataclass(frozen=True)
class DefensiveRotationCandidate:
    candidate_key: str
    title_ko: str
    symbols: tuple[str, ...]
    asset_bucket: str
    status: str
    reason_ko: str
    separation_from_failed_wide_ko: str
    required_inputs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_key": self.candidate_key,
            "title_ko": self.title_ko,
            "symbols": list(self.symbols),
            "asset_bucket": self.asset_bucket,
            "status": self.status,
            "reason_ko": self.reason_ko,
            "separation_from_failed_wide_ko": self.separation_from_failed_wide_ko,
            "required_inputs": list(self.required_inputs),
        }


@dataclass(frozen=True)
class ExclusionCriterion:
    candidate_key: str
    status: str
    covered_by_track: str | None
    reason_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_key": self.candidate_key,
            "status": self.status,
            "covered_by_track": self.covered_by_track,
            "reason_ko": self.reason_ko,
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
class PublicDataSupport:
    overall_ok: bool | None
    published: int | None
    macro_core_available: bool
    available_items: tuple[str, ...]
    warning_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_ok": self.overall_ok,
            "published": self.published,
            "macro_core_available": self.macro_core_available,
            "available_items": list(self.available_items),
            "warning_ko": self.warning_ko,
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
class BroadNoEdgeAssetUniverseRotationReport:
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
    forward_universe_snapshots: tuple[ForwardUniverseSnapshot, ...]
    asset_universe_metrics: dict[str, Any]
    proposed_rotation_candidates: tuple[DefensiveRotationCandidate, ...]
    exclusion_criteria: tuple[ExclusionCriterion, ...]
    money_state: MoneyState
    edge_autoarm_state: EdgeAutoarmState
    public_data_support: PublicDataSupport
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
            "forward_universe_snapshots": [
                snapshot.to_dict() for snapshot in self.forward_universe_snapshots
            ],
            "asset_universe_metrics": self.asset_universe_metrics,
            "proposed_rotation_candidates": [
                candidate.to_dict() for candidate in self.proposed_rotation_candidates
            ],
            "exclusion_criteria": [criterion.to_dict() for criterion in self.exclusion_criteria],
            "money_state": self.money_state.to_dict(),
            "edge_autoarm_state": self.edge_autoarm_state.to_dict(),
            "public_data_support": self.public_data_support.to_dict(),
            "validation_gates": [gate.to_dict() for gate in self.validation_gates],
            "learning_summary": self.learning_summary,
            "released_work_summary": self.released_work_summary,
            "safety_boundary": list(self.safety_boundary),
        }

    def as_markdown(self) -> str:
        lines = [
            f"# 자산군 방어 회전 no-live 실험 계약 (as of {self.timestamp_utc})",
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
            f"| tested_bucket_count | {self.asset_universe_metrics.get('tested_bucket_count')} |",
            f"| proposed_count | {self.asset_universe_metrics.get('proposed_count')} |",
            f"| money_state | `{self.money_state.status or 'unknown'}` |",
            f"| edge_autoarm | `{self.edge_autoarm_state.action or 'unknown'}` |",
            "",
            "## 제안 후보",
            "",
            "| 후보 | 자산군 | 심볼 | 상태 | 이유 |",
            "|------|--------|------|------|------|",
        ]
        for candidate in self.proposed_rotation_candidates:
            lines.append(
                f"| `{_table(candidate.candidate_key)}` | "
                f"{_table(candidate.asset_bucket)} | "
                f"{_table(', '.join(candidate.symbols))} | "
                f"`{candidate.status}` | {_table(candidate.reason_ko)} |"
            )
        lines += [
            "",
            "## 제외 기준",
            "",
            "| 후보 | 상태 | 이미 덮은 트랙 | 이유 |",
            "|------|------|---------------|------|",
        ]
        for criterion in self.exclusion_criteria:
            lines.append(
                f"| `{_table(criterion.candidate_key)}` | `{criterion.status}` | "
                f"{_table(criterion.covered_by_track or '-')} | {_table(criterion.reason_ko)} |"
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


def build_broad_no_edge_asset_universe_rotation(
    evidence_texts: dict[str, str | None],
    *,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> BroadNoEdgeAssetUniverseRotationReport:
    """sidecar 증거를 읽어 광역 자산군 방어 회전 no-live 계약을 만든다."""

    now = _as_utc(now)
    timestamp = now.isoformat().replace("+00:00", "Z")

    forward_board, forward_status, forward_summary = _parse_forward_board(
        evidence_texts.get("rebalance-paper-forward")
    )
    money_payload, money_status, money_summary = _parse_markdown_or_json(
        evidence_texts.get("money-path")
    )
    edge_payload, edge_status, edge_summary = _parse_markdown_or_json(
        evidence_texts.get("edge-autoarm")
    )
    public_payload, public_status, public_summary = _parse_public_data(
        evidence_texts.get("public-data")
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
        "edge-autoarm": (edge_status, edge_summary),
        "public-data": (public_status, public_summary),
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
    snapshots = tuple(
        ForwardUniverseSnapshot.from_row(row)
        for row in board.get("rows", [])
        if isinstance(row, dict)
    )
    required_inputs = tuple(f"{ref}:{filename}" for _, ref, filename in CONSUMED_SIDECARS)
    money_state = _money_state(money_payload)
    edge_state = _edge_autoarm_state(edge_payload)
    public_support = _public_data_support(public_payload)
    learning_summary = _learning_summary(ledger_payload)
    released_summary_dict = _released_work_summary(released_payload)
    proposed = _rotation_candidates(
        snapshots,
        public_support=public_support,
        required_inputs=required_inputs,
    )
    exclusions = _exclusion_criteria(snapshots)
    metrics = _asset_universe_metrics(
        board=board,
        snapshots=snapshots,
        candidates=proposed,
        exclusions=exclusions,
        public_support=public_support,
    )
    validation_gates = _validation_gates(
        evidence_surfaces=evidence_surfaces,
        board=board,
        snapshots=snapshots,
        metrics=metrics,
        candidates=proposed,
        money_state=money_state,
        edge_state=edge_state,
        public_support=public_support,
        learning_summary=learning_summary,
        released_summary=released_summary_dict,
        pipeline_payload=pipeline_payload,
    )
    overall = _overall_status(validation_gates)
    headline = _headline(overall, metrics, proposed)

    return BroadNoEdgeAssetUniverseRotationReport(
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
        forward_universe_snapshots=snapshots,
        asset_universe_metrics=metrics,
        proposed_rotation_candidates=proposed,
        exclusion_criteria=exclusions,
        money_state=money_state,
        edge_autoarm_state=edge_state,
        public_data_support=public_support,
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


def _parse_public_data(text: str | None) -> tuple[dict[str, Any] | None, str, str]:
    if text is None:
        return None, PARSE_MISSING, "public-data sidecar가 없습니다."
    direct = _loads_dict(text)
    if direct is not None:
        return direct, PARSE_OK, "public-data JSON 입력을 읽었습니다."
    summary = _extract_json_after_header(text, "summary.json")
    if isinstance(summary, dict):
        return summary, PARSE_OK, "public-data summary.json을 읽었습니다."
    decision = _extract_json_after_header(text, "결정 JSON")
    if isinstance(decision, dict):
        return decision, PARSE_OK, "public-data 결정 JSON을 읽었습니다."
    return None, PARSE_MALFORMED, "public-data JSON 블록을 읽지 못했습니다."


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


def _edge_autoarm_state(payload: dict[str, Any] | None) -> EdgeAutoarmState:
    if not isinstance(payload, dict):
        return EdgeAutoarmState(
            action=None,
            reason=None,
            current_rung=None,
            next_rung=None,
            detail_ko="edge-autoarm 결정 JSON을 읽지 못했습니다.",
        )
    action = payload.get("action") if isinstance(payload.get("action"), str) else None
    reason = payload.get("reason") if isinstance(payload.get("reason"), str) else None
    current_rung = _int_or_none(payload.get("current_rung") or payload.get("rung"))
    next_rung = _int_or_none(payload.get("next_rung"))
    detail = (
        "엣지 자동 무장은 대기 상태입니다."
        if action in {"WAIT_EDGE", "NO_EDGE", "WAIT"}
        else "edge-autoarm 상태를 보고에 반영했습니다."
    )
    return EdgeAutoarmState(
        action=action,
        reason=reason,
        current_rung=current_rung,
        next_rung=next_rung,
        detail_ko=detail,
    )


def _public_data_support(payload: dict[str, Any] | None) -> PublicDataSupport:
    if not isinstance(payload, dict):
        return PublicDataSupport(
            overall_ok=None,
            published=None,
            macro_core_available=False,
            available_items=(),
            warning_ko="public-data summary.json을 읽지 못했습니다.",
        )
    items = payload.get("items")
    items = items if isinstance(items, list) else []
    available = tuple(sorted(_public_item_ids(items)))
    has_rates = bool(set(available) & PUBLIC_RATES)
    has_vol = bool(set(available) & PUBLIC_VOL)
    macro_core_available = has_rates and has_vol
    overall_ok = payload.get("overall_ok")
    overall_ok_bool = overall_ok if isinstance(overall_ok, bool) else None
    published = _int_or_none(payload.get("published"))
    warning = (
        "일부 공개 데이터 경고가 있어도 금리와 VIX 핵심 입력은 있습니다."
        if macro_core_available and overall_ok_bool is False
        else "방어 회전에 필요한 금리와 VIX 핵심 입력을 사용할 수 있습니다."
        if macro_core_available
        else "금리 또는 VIX 핵심 입력이 부족합니다."
    )
    return PublicDataSupport(
        overall_ok=overall_ok_bool,
        published=published,
        macro_core_available=macro_core_available,
        available_items=available,
        warning_ko=warning,
    )


def _public_item_ids(items: list[object]) -> tuple[str, ...]:
    ids: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("ok") is False:
            continue
        raw_id = item.get("id") or item.get("symbol") or item.get("name")
        if raw_id is not None:
            ids.append(str(raw_id))
    return tuple(ids)


def _rotation_candidates(
    snapshots: tuple[ForwardUniverseSnapshot, ...],
    *,
    public_support: PublicDataSupport,
    required_inputs: tuple[str, ...],
) -> tuple[DefensiveRotationCandidate, ...]:
    tested_symbols = {symbol for snapshot in snapshots for symbol in snapshot.universe}
    templates = (
        (
            "cash_treasury_defense_rotation",
            "현금성 단기국채 방어 회전",
            ("BIL", "SHY", "SGOV"),
            "cash_proxy",
            True,
            "첫 자본 투입 전에 손실 폭을 낮추는 현금성 방어 후보입니다.",
            "기존 wide는 위험자산까지 넓힌 정적 확대였고, 이 후보는 cash-like 방어만 봅니다.",
        ),
        (
            "duration_barbell_defense_rotation",
            "단기·중기·장기 국채 바벨 방어 회전",
            ("SHY", "IEF", "TLT"),
            "duration_bond",
            True,
            "채권 만기 구간을 나눠 금리 충격 방어가 실제로 남는지 확인합니다.",
            "기존 wide의 채권 포함과 달리, 주식·원자재를 섞지 않은 만기 회전입니다.",
        ),
        (
            "inflation_shock_defense_rotation",
            "인플레이션 충격 방어 회전",
            ("GLD", "DBC", "TIP"),
            "commodity",
            public_support.macro_core_available,
            "금리와 VIX 입력을 붙여 물가 충격 방어가 독립 엣지인지 봅니다.",
            "기존 wide가 이미 GLD·DBC를 포함했으므로, 정적 편입이 아닌 regime-gated 후보입니다.",
        ),
        (
            "currency_shock_defense_rotation",
            "달러 충격 방어 회전",
            ("UUP", "GLD", "BIL"),
            "currency",
            public_support.macro_core_available,
            "달러 강세·위험회피 구간에서 현금성 방어와 금 노출을 분리합니다.",
            "기존 wide의 UUP 단순 편입과 달리, 달러 충격 방어 역할만 검증합니다.",
        ),
    )

    candidates = []
    for key, title, symbols, bucket, ready, reason, separation in templates:
        has_new_symbols = bool(set(symbols) - tested_symbols)
        status = PROPOSED if ready and has_new_symbols else WAIT
        if key == "duration_barbell_defense_rotation" and ready:
            status = PROPOSED
        candidates.append(
            DefensiveRotationCandidate(
                candidate_key=key,
                title_ko=title,
                symbols=symbols,
                asset_bucket=bucket,
                status=status,
                reason_ko=reason if status == PROPOSED else f"{reason} 추가 입력을 기다립니다.",
                separation_from_failed_wide_ko=separation,
                required_inputs=required_inputs,
            )
        )
    return tuple(candidates)


def _exclusion_criteria(
    snapshots: tuple[ForwardUniverseSnapshot, ...],
) -> tuple[ExclusionCriterion, ...]:
    wide = next((snapshot for snapshot in snapshots if snapshot.key == "wide"), None)
    return (
        ExclusionCriterion(
            candidate_key="repeat_wide_universe_static",
            status=EXCLUDED,
            covered_by_track=wide.key if wide else None,
            reason_ko=(
                "SPY·QQQ·EFA·EEM·IEF·TLT·LQD·GLD·DBC·VNQ·UUP 정적 확대는 "
                "이미 wide 트랙에서 NO_EDGE였으므로 반복하지 않습니다."
            ),
        ),
        ExclusionCriterion(
            candidate_key="live_rearm_or_order_submission",
            status=EXCLUDED,
            covered_by_track=None,
            reason_ko=(
                "money-path는 PREVIEW_ONLY이고 edge-autoarm은 WAIT_EDGE입니다. "
                "이 작업은 실주문이나 자본 배분을 열지 않습니다."
            ),
        ),
    )


def _asset_universe_metrics(
    *,
    board: dict[str, Any],
    snapshots: tuple[ForwardUniverseSnapshot, ...],
    candidates: tuple[DefensiveRotationCandidate, ...],
    exclusions: tuple[ExclusionCriterion, ...],
    public_support: PublicDataSupport,
) -> dict[str, Any]:
    tested_buckets = sorted({bucket for snapshot in snapshots for bucket in snapshot.asset_buckets})
    incumbent = next((snapshot for snapshot in snapshots if snapshot.is_incumbent), None)
    incumbent_buckets = sorted(incumbent.asset_buckets) if incumbent else []
    wide = next((snapshot for snapshot in snapshots if snapshot.key == "wide"), None)
    proposed_count = len([candidate for candidate in candidates if candidate.status == PROPOSED])
    return {
        "track_count": len(snapshots),
        "forward_track_count": _int_or_none(board.get("track_count")),
        "forward_comparable_count": _int_or_none(board.get("comparable_count")),
        "tested_bucket_count": len(tested_buckets),
        "tested_buckets": tested_buckets,
        "incumbent_buckets": incumbent_buckets,
        "wide_track_status": {
            "key": wide.key,
            "verdict": wide.verdict,
            "bucket_count": len(wide.asset_buckets),
            "buckets": list(wide.asset_buckets),
        }
        if wide
        else None,
        "proposed_count": proposed_count,
        "excluded_count": len(exclusions),
        "macro_core_available": public_support.macro_core_available,
    }


def _validation_gates(
    *,
    evidence_surfaces: tuple[EvidenceSurface, ...],
    board: dict[str, Any],
    snapshots: tuple[ForwardUniverseSnapshot, ...],
    metrics: dict[str, Any],
    candidates: tuple[DefensiveRotationCandidate, ...],
    money_state: MoneyState,
    edge_state: EdgeAutoarmState,
    public_support: PublicDataSupport,
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
            else "필수 sidecar 7개를 읽었습니다."
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

    money_safe = (
        money_state.status in {"PREVIEW_ONLY", "NO_EDGE_YET", "WAIT_EDGE"}
        or money_state.can_submit_real_orders is False
    )
    edge_waiting = edge_state.action in {"WAIT_EDGE", "NO_EDGE", "WAIT", None}
    money_gate = ValidationGate(
        gate_id="money-gate-alignment",
        status=GATE_PASS if money_safe and edge_waiting else GATE_WAIT,
        summary_ko=(
            "현재 돈 경로는 실주문이 아니라 엣지 대기 상태와 맞습니다."
            if money_safe and edge_waiting
            else "돈 경로와 edge-autoarm 상태가 no-live 대기와 완전히 맞지 않습니다."
        ),
        required_evidence=(
            "automation/money-path-last-run:LAST_RUN.md",
            "automation/edge-autoarm-last-run:LAST_RUN.md",
        ),
    )

    observation_health = board.get("observation_health")
    comparable = metrics.get("forward_comparable_count")
    coverage_gate = ValidationGate(
        gate_id="forward-universe-coverage",
        status=(
            GATE_FAIL
            if observation_health == OBS_HEALTH_BLOCKED
            else GATE_PASS
            if snapshots and isinstance(comparable, int) and comparable > 0
            else GATE_WAIT
        ),
        summary_ko=(
            "forward 관측 품질이 blocked입니다."
            if observation_health == OBS_HEALTH_BLOCKED
            else f"forward 유니버스 {len(snapshots)}개를 자산군으로 분해했습니다."
            if snapshots
            else "forward 유니버스 스냅샷이 없습니다."
        ),
        required_evidence=("automation/rebalance-paper-forward-last-run:LAST_RUN.md",),
    )

    public_gate = ValidationGate(
        gate_id="public-data-support",
        status=GATE_PASS if public_support.macro_core_available else GATE_WAIT,
        summary_ko=public_support.warning_ko,
        required_evidence=("automation/public-data:LAST_RUN.md",),
    )

    proposed_count = len([candidate for candidate in candidates if candidate.status == PROPOSED])
    candidate_gate = ValidationGate(
        gate_id="candidate-separation",
        status=GATE_PASS if proposed_count else GATE_WAIT,
        summary_ko=(
            f"failed wide 반복을 제외하고 방어 회전 후보 {proposed_count}개를 분리했습니다."
            if proposed_count
            else "failed wide와 충분히 다른 방어 회전 후보가 아직 없습니다."
        ),
        required_evidence=(
            "automation/rebalance-paper-forward-last-run:LAST_RUN.md",
            "automation/public-data:LAST_RUN.md",
        ),
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
            "specs/125-broad-no-edge-asset-universe/contracts/"
            "broad-no-edge-asset-universe.md",
        ),
    )

    return (
        input_gate,
        pipeline_gate,
        no_live_gate,
        money_gate,
        coverage_gate,
        public_gate,
        candidate_gate,
        learning_gate,
        release_gate,
    )


def _overall_status(gates: tuple[ValidationGate, ...]) -> str:
    hard_fail_gate_ids = {
        "input-evidence",
        "pipeline-liveness",
        "forward-universe-coverage",
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
    candidates: tuple[DefensiveRotationCandidate, ...],
) -> str:
    if overall == BLOCKED:
        return "자산군 방어 회전 실험 계약을 만들 핵심 증거가 부족하거나 파이프라인이 막혔습니다."
    proposed_count = len([candidate for candidate in candidates if candidate.status == PROPOSED])
    tested_count = metrics.get("tested_bucket_count")
    if overall == OBSERVATION_WAIT:
        return (
            "자산군 방어 회전 no-live 계약은 생성됐지만 일부 보조 증거가 더 필요합니다. "
            f"현재 확인한 자산군은 {tested_count}개이고 제안 후보는 {proposed_count}개입니다."
        )
    return (
        "자산군 방어 회전 no-live 계약이 준비됐습니다. "
        f"이미 실패한 wide 반복을 제외하고 방어 후보 {proposed_count}개를 보고합니다."
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


def _asset_buckets(symbols: tuple[str, ...]) -> tuple[str, ...]:
    buckets = sorted({_symbol_bucket(symbol) for symbol in symbols})
    return tuple(bucket for bucket in buckets if bucket)


def _symbol_bucket(symbol: str) -> str:
    normalized = symbol.upper()
    if normalized in SYMBOL_BUCKETS:
        return SYMBOL_BUCKETS[normalized]
    return "equity" if normalized.isalpha() else "unknown"


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


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


__all__ = [
    "BLOCKED",
    "CONTRACT_READY",
    "OBSERVATION_WAIT",
    "build_broad_no_edge_asset_universe_rotation",
]

"""스펙 135 — 광역 no-edge 자산 간 상대가치 no-live 계약.

선택된 자율 후보
`candidate-broad-no-edge-cross-asset-relative-value-experiment`를 주식·채권·
원자재·현금성 자산 간 상대가치 관점의 기계 판독 보고서로 고정한다.

안전 경계: 읽기 전용·순수·결정론. 브로커 API, 주문, 자본 배분, live 전략,
whitelist/caps, 비밀값, 헌법/커널, 외부 유료 서비스는 건드리지 않는다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "1.0"
CONTRACT_ID = "broad-no-edge-cross-asset-relative-value"
COMPLETED_CANDIDATE_ID = (
    "candidate-broad-no-edge-cross-asset-relative-value-experiment"
)
NEXT_CANDIDATE_ID = "candidate-broad-no-edge-tail-risk-convexity-experiment"

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

MIN_FORWARD_TRACKS = 3
MIN_PUBLIC_DATA_ITEMS = 8

SAFETY_BOUNDARY: tuple[str, ...] = (
    "no broker API call",
    "no orders",
    "no capital allocation",
    "no live strategy change",
    "no whitelist/caps change",
    "no secret read/write",
    "no external paid service",
    "no constitution/kernel change",
    "relative-value contract only",
)

CONSUMED_SIDECARS: tuple[tuple[str, str, str], ...] = (
    ("rebalance-paper-forward", "automation/rebalance-paper-forward-last-run", "LAST_RUN.md"),
    ("public-data-summary", "automation/public-data", "summary.json"),
    ("regime-stratify", "automation/regime-stratify-last-run", "LAST_RUN.md"),
    ("money-path", "automation/money-path-last-run", "LAST_RUN.md"),
    ("edge-autoarm", "automation/edge-autoarm-last-run", "LAST_RUN.md"),
    ("released-work", "automation/released-work-last-run", "released_work.json"),
    ("pipeline-liveness", "automation/pipeline-liveness-last-run", "LAST_RUN.md"),
)

ASSET_CLASS_BY_SYMBOL: dict[str, str] = {
    "SPY": "equity",
    "QQQ": "equity",
    "EFA": "equity",
    "EEM": "equity",
    "IWM": "equity",
    "IEF": "duration",
    "TLT": "duration",
    "SHY": "cash_proxy",
    "BIL": "cash_proxy",
    "SGOV": "cash_proxy",
    "LQD": "credit",
    "HYG": "credit",
    "GLD": "commodity",
    "SLV": "commodity",
    "DBC": "commodity",
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
class ForwardTrack:
    key: str
    label_ko: str
    verdict: str | None
    rank: int | None
    n_obs: int | None
    psr_vs_benchmark: float | None
    sharpe: float | None
    calmar: float | None
    universe: tuple[str, ...]
    asset_classes: tuple[str, ...]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ForwardTrack:
        universe = tuple(str(symbol).upper() for symbol in payload.get("universe", []) if symbol)
        classes = tuple(
            sorted(
                {
                    ASSET_CLASS_BY_SYMBOL[symbol]
                    for symbol in universe
                    if symbol in ASSET_CLASS_BY_SYMBOL
                }
            )
        )
        label = payload.get("label") or payload.get("label_ko") or payload.get("key") or ""
        return cls(
            key=str(payload.get("key") or ""),
            label_ko=str(label),
            verdict=_str_or_none(payload.get("verdict")),
            rank=_int_or_none(payload.get("rank")),
            n_obs=_int_or_none(payload.get("n_obs")),
            psr_vs_benchmark=_float_or_none(payload.get("psr_vs_benchmark")),
            sharpe=_float_or_none(payload.get("sharpe") or payload.get("strategy_sharpe_annual")),
            calmar=_float_or_none(payload.get("calmar")),
            universe=universe,
            asset_classes=classes,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label_ko": self.label_ko,
            "verdict": self.verdict,
            "rank": self.rank,
            "n_obs": self.n_obs,
            "psr_vs_benchmark": self.psr_vs_benchmark,
            "sharpe": self.sharpe,
            "calmar": self.calmar,
            "universe": list(self.universe),
            "asset_classes": list(self.asset_classes),
        }


@dataclass(frozen=True)
class RelativeValueLane:
    lane_id: str
    asset_pair: str
    status: str
    candidate_rule_ko: str
    required_inputs: tuple[str, ...]
    exclusion_reason_ko: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "lane_id": self.lane_id,
            "asset_pair": self.asset_pair,
            "status": self.status,
            "candidate_rule_ko": self.candidate_rule_ko,
            "required_inputs": list(self.required_inputs),
            "exclusion_reason_ko": self.exclusion_reason_ko,
        }


@dataclass(frozen=True)
class CashProxySnapshot:
    available: bool
    evidence_items: tuple[str, ...]
    summary_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "evidence_items": list(self.evidence_items),
            "summary_ko": self.summary_ko,
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
class BroadNoEdgeCrossAssetRelativeValueReport:
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
    relative_value_lanes: tuple[RelativeValueLane, ...]
    cash_proxy_snapshot: CashProxySnapshot
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
            "relative_value_lanes": [lane.to_dict() for lane in self.relative_value_lanes],
            "cash_proxy_snapshot": self.cash_proxy_snapshot.to_dict(),
            "money_state": self.money_state.to_dict(),
            "edge_autoarm_state": self.edge_autoarm_state.to_dict(),
            "validation_gates": [gate.to_dict() for gate in self.validation_gates],
            "safety_boundary": list(self.safety_boundary),
        }

    def as_markdown(self) -> str:
        lines = [
            "# 자산 간 상대가치 no-live 실험 계약",
            "",
            f"- overall_status: `{self.overall_status}`",
            f"- completed_candidate_id: `{self.completed_candidate_id}`",
            f"- next_candidate_id: `{self.next_candidate_id}`",
            f"- headline: {self.headline_ko}",
            "",
            "## 상대가치 후보 축",
            "",
            "| lane | pair | status | rule |",
            "|------|------|--------|------|",
        ]
        for lane in self.relative_value_lanes:
            lines.append(
                "| "
                + " | ".join(
                    [
                        lane.lane_id,
                        lane.asset_pair,
                        lane.status,
                        lane.candidate_rule_ko.replace("|", "/"),
                    ]
                )
                + " |"
            )
        lines.extend(
            [
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
        lines.extend(
            [
                "",
                "## 안전 경계",
                "",
                "- " + "\n- ".join(self.safety_boundary),
            ]
        )
        return "\n".join(lines)


def build_broad_no_edge_cross_asset_relative_value(
    evidence_texts: dict[str, str | None],
    *,
    now: datetime | None = None,
    run_id: str = "local",
    commit: str = "unknown",
) -> BroadNoEdgeCrossAssetRelativeValueReport:
    now = now or datetime.now(tz=UTC)
    parsed = {key: _parse_for_key(key, evidence_texts.get(key)) for key, _, _ in CONSUMED_SIDECARS}
    surfaces = tuple(
        _surface_for(key, ref, filename, evidence_texts.get(key), parsed[key])
        for key, ref, filename in CONSUMED_SIDECARS
    )
    tracks = _forward_tracks(parsed["rebalance-paper-forward"])
    cash = _cash_proxy_snapshot(parsed["public-data-summary"])
    money = _money_state(parsed["money-path"])
    edge = _edge_autoarm_state(parsed["edge-autoarm"])
    lanes = _relative_value_lanes(tracks, cash)
    released_summary = _released_work_summary(parsed["released-work"])
    liveness_summary = _liveness_summary(parsed["pipeline-liveness"])
    gates = _validation_gates(
        evidence_surfaces=surfaces,
        tracks=tracks,
        lanes=lanes,
        cash=cash,
        money_state=money,
        edge_state=edge,
        released_summary=released_summary,
        liveness_summary=liveness_summary,
    )
    overall = _overall_status(gates)
    return BroadNoEdgeCrossAssetRelativeValueReport(
        schema_version=SCHEMA_VERSION,
        contract_id=CONTRACT_ID,
        run_id=run_id,
        commit=commit,
        generated_at_utc=now.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        completed_candidate_id=COMPLETED_CANDIDATE_ID,
        next_candidate_id=NEXT_CANDIDATE_ID,
        overall_status=overall,
        headline_ko=_headline(overall, lanes, tracks),
        evidence_surfaces=surfaces,
        forward_tracks=tracks,
        relative_value_lanes=lanes,
        cash_proxy_snapshot=cash,
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
    if key == "public-data-summary":
        return _parse_json(raw)
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


def _cash_proxy_snapshot(parsed: Any) -> CashProxySnapshot:
    if not isinstance(parsed, dict):
        return CashProxySnapshot(False, (), "public-data summary를 읽지 못했습니다.")
    items = [
        f"{item.get('kind')}:{item.get('id')}"
        for item in _items(parsed, "items")
        if item.get("ok") and str(item.get("id") or "") in {"UST2Y", "UST10Y", "DGS2", "DGS10"}
    ]
    available = len(items) >= 2
    return CashProxySnapshot(
        available=available,
        evidence_items=tuple(items),
        summary_ko=(
            f"현금성 대체 수익률 proxy 입력 {len(items)}개를 확인했습니다."
            if available
            else "현금성 대체 수익률 proxy 입력이 부족합니다."
        ),
    )


def _relative_value_lanes(
    tracks: tuple[ForwardTrack, ...],
    cash: CashProxySnapshot,
) -> tuple[RelativeValueLane, ...]:
    classes = {asset_class for track in tracks for asset_class in track.asset_classes}
    no_edge_count = sum(track.verdict == "NO_EDGE" for track in tracks)
    rows = [
        _lane(
            lane_id="equity_duration_spread",
            pair="equity/duration",
            available={"equity", "duration"}.issubset(classes),
            rule="주식과 중기채 상대 강도 spread를 absolute momentum 후보와 별도로 검증한다.",
            inputs=("rebalance-paper-forward", "public-data-summary"),
        ),
        _lane(
            lane_id="duration_gold_spread",
            pair="duration/commodity",
            available={"duration", "commodity"}.issubset(classes),
            rule="채권 듀레이션과 금 가격 방어력을 레짐별 상대가치 후보로 분리한다.",
            inputs=("rebalance-paper-forward", "regime-stratify"),
        ),
        _lane(
            lane_id="cash_proxy_hurdle",
            pair="risk_asset/cash_proxy",
            available=cash.available,
            rule="위험자산 후보가 현금성 proxy 수익률을 넘지 못하면 no-live 제외한다.",
            inputs=("public-data-summary", "money-path"),
        ),
        _lane(
            lane_id="broad_no_edge_exclusion",
            pair="all_tracks/benchmark",
            available=len(tracks) >= MIN_FORWARD_TRACKS and no_edge_count == len(tracks),
            rule="기존 7개 forward 트랙이 모두 NO_EDGE이면 같은 절대 모멘텀 변형은 제외한다.",
            inputs=("rebalance-paper-forward",),
        ),
    ]
    return tuple(rows)


def _lane(
    *,
    lane_id: str,
    pair: str,
    available: bool,
    rule: str,
    inputs: tuple[str, ...],
) -> RelativeValueLane:
    return RelativeValueLane(
        lane_id=lane_id,
        asset_pair=pair,
        status=PROPOSED if available else WAIT,
        candidate_rule_ko=rule,
        required_inputs=inputs,
        exclusion_reason_ko=None if available else "필수 자산군 또는 proxy 입력이 아직 부족합니다.",
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
        if (
            key in {"rebalance-paper-forward", "collect-public-data", "regime-stratify"}
            and status != "OK"
        ):
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
    lanes: tuple[RelativeValueLane, ...],
    cash: CashProxySnapshot,
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
    proposed_count = sum(lane.status == PROPOSED for lane in lanes)
    no_edge_count = sum(track.verdict == "NO_EDGE" for track in tracks)
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
            "relative-value-lane-coverage",
            GATE_PASS if proposed_count >= 3 else GATE_WAIT,
            f"상대가치 후보 축 {proposed_count}/{len(lanes)}개를 제안했습니다.",
            (
                "automation/rebalance-paper-forward-last-run:LAST_RUN.md",
                "automation/public-data:summary.json",
            ),
        ),
        ValidationGate(
            "cash-proxy-availability",
            GATE_PASS if cash.available else GATE_WAIT,
            cash.summary_ko,
            ("automation/public-data:summary.json",),
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
            "released-work가 이번 상대가치 후보를 완료 후보로 읽었습니다."
            if released_summary.get("completed_candidate_released")
            else "released-work에는 아직 이번 상대가치 후보가 없습니다.",
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
    lanes: tuple[RelativeValueLane, ...],
    tracks: tuple[ForwardTrack, ...],
) -> str:
    if overall == BLOCKED:
        return "필수 증거가 깨져 상대가치 후보 계약을 완료할 수 없습니다."
    proposed = sum(lane.status == PROPOSED for lane in lanes)
    no_edge = sum(track.verdict == "NO_EDGE" for track in tracks)
    return (
        f"기존 forward 트랙 {len(tracks)}개 중 {no_edge}개가 NO_EDGE라 "
        f"절대 모멘텀 반복 대신 상대가치 후보 축 {proposed}개를 no-live로 엽니다."
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
    if key == "public-data-summary":
        return (
            f"overall_ok={parsed.get('overall_ok')}, "
            f"published={parsed.get('published')}/{parsed.get('total_items')}"
        )
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
        if isinstance(candidate, dict) and (
            "rows" in candidate
            or "live_money_state" in candidate
            or "checks" in candidate
            or "released_work" in candidate
            or "action" in candidate
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
    "build_broad_no_edge_cross_asset_relative_value",
]

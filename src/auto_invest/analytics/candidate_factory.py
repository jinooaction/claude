"""스펙 070 — 후보 구현 공장.

자율 성장 후보를 실행 가능한 검증 패키지로 바꾸고, 기계 판독 결과가 있을 때만
promotion_evidence를 보강한다. 이 모듈은 브로커 API, 주문, 자본, whitelist, caps,
live 전략 설정을 건드리지 않는다.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auto_invest.analytics.evolution_loop import mask_sensitive_values

SCHEMA_VERSION = "1.0"

OVERALL_OK = "ok"
OVERALL_DEGRADED = "degraded"

STATUS_READY = "ready"
STATUS_PENDING = "pending"
STATUS_BLOCKED = "blocked"
STATUS_EVIDENCE_PASSED = "evidence_passed"

EVIDENCE_PASS = "pass"
EVIDENCE_FAIL = "fail"
EVIDENCE_PENDING = "pending"
EVIDENCE_MISSING = "missing"

KIND_STRATEGY_BACKTEST = "strategy_backtest"
KIND_PORTFOLIO_BACKTEST = "portfolio_backtest"
KIND_GATE_ALIGNMENT = "gate_alignment"
KIND_OPS_LIVENESS = "ops_liveness"
KIND_REVIEW_LEDGER = "review_ledger"
KIND_ANALYTICS_VALIDATION = "analytics_validation"
KIND_EXECUTION_QUALITY = "execution_quality"
KIND_DATA_QUALITY = "data_quality"
KIND_DATA_COLLECTION = "data_collection"

_EVIDENCE_KEYS: tuple[str, ...] = (
    "historical_backtest",
    "recent_oos",
    "walk_forward",
)

_STRATEGY_KINDS = {KIND_STRATEGY_BACKTEST, KIND_PORTFOLIO_BACKTEST}

_HARD_OPERATOR_SURFACES = {
    "orders",
    "whitelist",
    "caps",
    "secrets",
    "deploy",
    "kernel",
    "paid_service",
}


@dataclass(frozen=True)
class ImplementationPackage:
    package_id: str
    candidate_id: str
    title_ko: str
    domain_key: str
    source_stage: str
    package_kind: str
    status: str
    required_inputs: tuple[str, ...]
    commands: tuple[str, ...]
    produces_evidence: tuple[str, ...]
    promotion_patch: Mapping[str, Any]
    block_reason_ko: str | None
    safety_note_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "candidate_id": self.candidate_id,
            "title_ko": self.title_ko,
            "domain_key": self.domain_key,
            "source_stage": self.source_stage,
            "package_kind": self.package_kind,
            "status": self.status,
            "required_inputs": list(self.required_inputs),
            "commands": list(self.commands),
            "produces_evidence": list(self.produces_evidence),
            "promotion_patch": dict(self.promotion_patch),
            "block_reason_ko": self.block_reason_ko,
            "safety_note_ko": self.safety_note_ko,
        }


@dataclass(frozen=True)
class EvidenceResult:
    candidate_id: str
    historical_backtest: str
    recent_oos: str
    walk_forward: str
    source_ref: str | None
    forward_track: Mapping[str, Any] | None
    canary_track: Mapping[str, Any] | None
    raw: Mapping[str, Any]

    @property
    def all_strategy_evidence_passed(self) -> bool:
        return all(
            getattr(self, key) == EVIDENCE_PASS
            for key in _EVIDENCE_KEYS
        )

    @property
    def any_strategy_evidence_failed(self) -> bool:
        return any(
            getattr(self, key) == EVIDENCE_FAIL
            for key in _EVIDENCE_KEYS
        )


@dataclass(frozen=True)
class CandidateFactoryRun:
    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    packages: tuple[ImplementationPackage, ...]
    missing_inputs: tuple[str, ...]
    enriched_candidate_backlog: Mapping[str, Any]

    @property
    def counts(self) -> dict[str, int]:
        counts = {
            STATUS_READY: 0,
            STATUS_PENDING: 0,
            STATUS_BLOCKED: 0,
            STATUS_EVIDENCE_PASSED: 0,
        }
        for package in self.packages:
            counts[package.status] = counts.get(package.status, 0) + 1
        return counts

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "commit": self.commit,
            "timestamp_utc": self.timestamp_utc,
            "overall_status": self.overall_status,
            "counts": self.counts,
            "missing_inputs": list(self.missing_inputs),
            "packages": [package.to_dict() for package in self.packages],
            "enriched_candidate_backlog": dict(self.enriched_candidate_backlog),
        }

    def package_plan_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "packages": [package.to_dict() for package in self.packages],
        }

    def as_markdown(self) -> str:
        lines = [
            "# 후보 구현 공장 최신 실행",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| schema_version | {self.schema_version} |",
            f"| run_id | {self.run_id} |",
            f"| commit | {self.commit} |",
            f"| timestamp_utc | {self.timestamp_utc} |",
            f"| overall_status | {self.overall_status} |",
            "",
            "## 한 줄 결론",
            "",
            "`BACKTEST_REQUIRED` 후보를 그냥 대기시키지 않고 후보별 검증 패키지와 "
            "`promotion_evidence` 보강 경로로 변환했다. 결과 증거가 없는 후보는 "
            "통과로 위조하지 않고 실행 대기 상태로 남겼다.",
            "",
            "## 집계",
            "",
        ]
        for key, value in self.counts.items():
            lines.append(f"- `{key}`: {value}")
        if self.missing_inputs:
            lines += ["", "## 누락 입력", ""]
            for item in self.missing_inputs:
                lines.append(f"- `{item}`")
        lines += ["", "## 후보별 패키지", ""]
        if not self.packages:
            lines.append("- 후보 없음")
        for package in self.packages:
            lines.append(
                f"- `{package.status}` {package.package_kind}: "
                f"{package.title_ko} (`{package.candidate_id}`)"
            )
            if package.block_reason_ko:
                lines.append(f"  - 차단/대기: {package.block_reason_ko}")
            if package.commands:
                lines.append(f"  - 첫 명령: `{package.commands[0]}`")
        lines += [
            "",
            "## 안전 문구",
            "",
            "이 실행은 검증 패키지와 후보 JSON만 만든다. 주문, 자본 사다리, "
            "live 전략 설정, whitelist, caps, 실거래 sentinel, 브로커 API를 변경하지 않는다.",
        ]
        return mask_sensitive_values("\n".join(lines))


def build_candidate_factory_run(
    *,
    candidate_backlog: Mapping[str, Any] | None,
    promotion_summary: Mapping[str, Any] | None = None,
    result_evidence: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    commit: str = "unknown",
    run_id: str = "local",
) -> CandidateFactoryRun:
    now = _ensure_utc(now or datetime.now(UTC))
    candidates = _candidate_rows(candidate_backlog, promotion_summary)
    stage_by_id = _stage_by_candidate_id(promotion_summary)
    results = parse_result_evidence(result_evidence)
    packages = tuple(
        _build_package(candidate, stage_by_id.get(_candidate_id(candidate), "unknown"), results)
        for candidate in candidates
    )
    missing_inputs: list[str] = []
    if not _mapping_has_list(candidate_backlog, "candidates") and not candidates:
        missing_inputs.append("candidate_backlog.candidates")
    enriched = enrich_candidate_backlog(candidate_backlog, packages)
    overall = (
        OVERALL_DEGRADED
        if missing_inputs or any(package.status == STATUS_BLOCKED for package in packages)
        else OVERALL_OK
    )
    return CandidateFactoryRun(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=_iso(now),
        overall_status=overall,
        packages=packages,
        missing_inputs=tuple(missing_inputs),
        enriched_candidate_backlog=enriched,
    )


def parse_result_evidence(doc: Mapping[str, Any] | None) -> dict[str, EvidenceResult]:
    if not isinstance(doc, Mapping):
        return {}
    raw_results: Sequence[Any]
    if isinstance(doc.get("results"), list):
        raw_results = doc["results"]  # type: ignore[index]
    elif isinstance(doc.get("candidates"), list):
        raw_results = doc["candidates"]  # type: ignore[index]
    else:
        raw_results = [
            {"candidate_id": key, **value}
            for key, value in doc.items()
            if isinstance(value, Mapping)
        ]
    results: dict[str, EvidenceResult] = {}
    for raw in raw_results:
        if not isinstance(raw, Mapping):
            continue
        candidate_id = str(raw.get("candidate_id") or "").strip()
        if not candidate_id:
            continue
        forward_track = raw.get("forward_track")
        canary_track = raw.get("canary_track")
        results[candidate_id] = EvidenceResult(
            candidate_id=candidate_id,
            historical_backtest=_status_value(raw.get("historical_backtest")),
            recent_oos=_status_value(raw.get("recent_oos")),
            walk_forward=_status_value(raw.get("walk_forward")),
            source_ref=str(raw.get("source_ref") or "") or None,
            forward_track=forward_track if isinstance(forward_track, Mapping) else None,
            canary_track=canary_track if isinstance(canary_track, Mapping) else None,
            raw=raw,
        )
    return results


def enrich_candidate_backlog(
    candidate_backlog: Mapping[str, Any] | None,
    packages: Sequence[ImplementationPackage],
) -> dict[str, Any]:
    package_by_id = {package.candidate_id: package for package in packages}
    base: dict[str, Any] = dict(candidate_backlog or {})
    raw_candidates = base.get("candidates")
    if not isinstance(raw_candidates, list):
        raw_candidates = []
    enriched_candidates: list[dict[str, Any]] = []
    for item in raw_candidates:
        if not isinstance(item, Mapping):
            continue
        row = dict(item)
        candidate_id = _candidate_id(row)
        package = package_by_id.get(candidate_id)
        if package is not None:
            existing = row.get("promotion_evidence")
            promotion_evidence = dict(existing if isinstance(existing, Mapping) else {})
            promotion_evidence.update(package.promotion_patch)
            row["promotion_evidence"] = promotion_evidence
        enriched_candidates.append(row)
    base["schema_version"] = str(base.get("schema_version") or SCHEMA_VERSION)
    base["candidates"] = enriched_candidates
    base["candidate_factory"] = {
        "schema_version": SCHEMA_VERSION,
        "package_count": len(packages),
        "packages": [
            {
                "candidate_id": package.candidate_id,
                "package_id": package.package_id,
                "package_kind": package.package_kind,
                "status": package.status,
            }
            for package in packages
        ],
    }
    return base


def write_candidate_factory_artifacts(
    run: CandidateFactoryRun,
    *,
    summary_out: Path | None = None,
    json_out: Path | None = None,
    enriched_backlog_out: Path | None = None,
    package_plan_out: Path | None = None,
) -> None:
    if summary_out is not None:
        summary_out.parent.mkdir(parents=True, exist_ok=True)
        summary_out.write_text(run.as_markdown() + "\n", encoding="utf-8")
    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(
            json.dumps(run.as_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if enriched_backlog_out is not None:
        enriched_backlog_out.parent.mkdir(parents=True, exist_ok=True)
        enriched_backlog_out.write_text(
            json.dumps(run.enriched_candidate_backlog, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if package_plan_out is not None:
        package_plan_out.parent.mkdir(parents=True, exist_ok=True)
        package_plan_out.write_text(
            json.dumps(run.package_plan_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _build_package(
    candidate: Mapping[str, Any],
    source_stage: str,
    results: Mapping[str, EvidenceResult],
) -> ImplementationPackage:
    candidate_id = _candidate_id(candidate)
    title = str(candidate.get("title_ko") or candidate_id)
    domain = str(candidate.get("domain_key") or "unknown")
    kind = _package_kind(candidate)
    package_id = stable_id("pkg", candidate_id, kind)
    safety_impacts = {str(item) for item in candidate.get("safety_impact") or ()}
    result = results.get(candidate_id)
    hard_surfaces = sorted(safety_impacts & _HARD_OPERATOR_SURFACES)
    if hard_surfaces:
        status = STATUS_BLOCKED
        block = (
            f"안전 경계({', '.join(hard_surfaces)})를 건드리는 후보라 "
            "자동 검증 패키지에서 제외한다."
        )
    elif result is not None and result.any_strategy_evidence_failed:
        status = STATUS_BLOCKED
        block = "기계 판독 검증 결과에 실패가 있어 승격 증거로 병합하지 않는다."
    elif kind in _STRATEGY_KINDS and result is not None and result.all_strategy_evidence_passed:
        status = STATUS_EVIDENCE_PASSED
        block = None
    elif result is not None:
        status = STATUS_PENDING
        block = "검증 결과가 아직 세 필수 증거를 모두 통과하지 못했다."
    else:
        status = STATUS_READY
        block = "실행 패키지는 준비됐지만 아직 기계 판독 검증 결과가 없다."
    commands = _commands_for(kind, candidate_id)
    patch = _promotion_patch(
        package_id=package_id,
        kind=kind,
        status=status,
        block_reason_ko=block,
        result=result,
    )
    return ImplementationPackage(
        package_id=package_id,
        candidate_id=candidate_id,
        title_ko=title,
        domain_key=domain,
        source_stage=source_stage,
        package_kind=kind,
        status=status,
        required_inputs=_required_inputs_for(kind),
        commands=commands,
        produces_evidence=_produces_evidence_for(kind),
        promotion_patch=patch,
        block_reason_ko=block,
        safety_note_ko=(
            "읽기 전용 또는 backtest/paper 검증 계획만 생성한다. 주문, 자본, live 설정, "
            "whitelist, caps, sentinel은 변경하지 않는다."
        ),
    )


def _promotion_patch(
    *,
    package_id: str,
    kind: str,
    status: str,
    block_reason_ko: str | None,
    result: EvidenceResult | None,
) -> dict[str, Any]:
    patch: dict[str, Any] = {
        "factory_package_id": package_id,
        "factory_kind": kind,
        "factory_status": status,
        "factory_source": "candidate-implementation-factory",
    }
    if block_reason_ko:
        patch["factory_block_reason_ko"] = block_reason_ko
    if status == STATUS_BLOCKED:
        return patch
    if kind not in _STRATEGY_KINDS:
        if result is not None and not result.any_strategy_evidence_failed:
            validation = result.raw.get("factory_validation")
            if _status_value(validation) == EVIDENCE_PASS:
                patch["factory_validation"] = EVIDENCE_PASS
                patch["factory_validation_source"] = result.source_ref
        return patch
    if result is None:
        for key in _EVIDENCE_KEYS:
            patch[key] = EVIDENCE_PENDING
            patch[f"{key}_source"] = f"candidate-factory:{package_id}"
        return patch
    for key in _EVIDENCE_KEYS:
        value = getattr(result, key)
        patch[key] = value
        patch[f"{key}_source"] = result.source_ref or f"candidate-factory:{package_id}"
    if result.forward_track is not None:
        patch["forward_track"] = dict(result.forward_track)
    if result.canary_track is not None:
        patch["canary_track"] = dict(result.canary_track)
    return patch


def _candidate_rows(
    candidate_backlog: Mapping[str, Any] | None,
    promotion_summary: Mapping[str, Any] | None,
) -> tuple[Mapping[str, Any], ...]:
    if _mapping_has_list(candidate_backlog, "candidates"):
        return tuple(
            item
            for item in candidate_backlog["candidates"]  # type: ignore[index]
            if isinstance(item, Mapping) and _candidate_id(item)
        )
    if not _mapping_has_list(promotion_summary, "assessments"):
        return ()
    rows: list[Mapping[str, Any]] = []
    for assessment in promotion_summary["assessments"]:  # type: ignore[index]
        if not isinstance(assessment, Mapping):
            continue
        candidate = assessment.get("candidate")
        if isinstance(candidate, Mapping) and _candidate_id(candidate):
            rows.append(candidate)
    return tuple(rows)


def _stage_by_candidate_id(promotion_summary: Mapping[str, Any] | None) -> dict[str, str]:
    if not _mapping_has_list(promotion_summary, "assessments"):
        return {}
    stages: dict[str, str] = {}
    for assessment in promotion_summary["assessments"]:  # type: ignore[index]
        if not isinstance(assessment, Mapping):
            continue
        candidate = assessment.get("candidate")
        candidate_id = _candidate_id(candidate if isinstance(candidate, Mapping) else assessment)
        if candidate_id:
            stages[candidate_id] = str(assessment.get("stage") or "unknown")
    return stages


def _package_kind(candidate: Mapping[str, Any]) -> str:
    domain = str(candidate.get("domain_key") or "").strip()
    by_domain = {
        "strategy_design": KIND_STRATEGY_BACKTEST,
        "portfolio_design": KIND_PORTFOLIO_BACKTEST,
        "live_readiness": KIND_GATE_ALIGNMENT,
        "agent_ops": KIND_OPS_LIVENESS,
        "review": KIND_REVIEW_LEDGER,
        "analysis": KIND_ANALYTICS_VALIDATION,
        "execution_quality": KIND_EXECUTION_QUALITY,
        "data_quality": KIND_DATA_QUALITY,
        "data_collection": KIND_DATA_COLLECTION,
    }
    if domain in by_domain:
        return by_domain[domain]
    if str(candidate.get("breakthrough_type") or "") == "profit_power":
        return KIND_STRATEGY_BACKTEST
    return KIND_ANALYTICS_VALIDATION


def _commands_for(kind: str, candidate_id: str) -> tuple[str, ...]:
    slug = _safe_slug(candidate_id)
    if kind == KIND_STRATEGY_BACKTEST:
        return (
            "uv run auto-invest portfolio-walk-forward --portfolio "
            "deploy/micro-gtaa-live-portfolio.toml --trailing-years 5 "
            f"--db data/candidate-factory/{slug}.db "
            f"--halt-path data/candidate-factory/{slug}.halt.flag --json",
            "uv run python scripts/deep_walk_forward_probe.py --segment-months 60",
        )
    if kind == KIND_PORTFOLIO_BACKTEST:
        return (
            "uv run auto-invest portfolio-walk-forward --portfolio "
            "deploy/global-trend-wide-portfolio.toml --trailing-years 5 "
            f"--db data/candidate-factory/{slug}-wide.db "
            f"--halt-path data/candidate-factory/{slug}.halt.flag --json",
            "uv run auto-invest portfolio-walk-forward --portfolio "
            "deploy/multi-asset-trend-portfolio.toml --trailing-years 5 "
            f"--db data/candidate-factory/{slug}-multi.db "
            f"--halt-path data/candidate-factory/{slug}.halt.flag --json",
        )
    if kind == KIND_GATE_ALIGNMENT:
        return ("uv run python scripts/money_path_probe.py --manifest",)
    if kind == KIND_OPS_LIVENESS:
        return ("uv run python scripts/pipeline_liveness_probe.py --json",)
    if kind == KIND_REVIEW_LEDGER:
        return (
            "uv run python scripts/evolution_loop_probe.py "
            "--evidence-dir /tmp/evidence --json",
        )
    if kind == KIND_EXECUTION_QUALITY:
        return ("uv run python scripts/money_path_probe.py --manifest",)
    if kind == KIND_DATA_COLLECTION:
        return ("uv run auto-invest collect-public-data --json",)
    if kind == KIND_DATA_QUALITY:
        return ("uv run auto-invest bars-status --symbols SPY,TLT,GLD,DBC --json",)
    return ("uv run auto-invest macro-regime --format json",)


def _required_inputs_for(kind: str) -> tuple[str, ...]:
    if kind in _STRATEGY_KINDS:
        return ("data/history dataset", "portfolio TOML", "candidate result evidence")
    if kind == KIND_DATA_COLLECTION:
        return ("deploy/public-data.toml", "network access to public data sources")
    if kind == KIND_DATA_QUALITY:
        return ("price_bars database or exported historical CSVs",)
    if kind == KIND_OPS_LIVENESS:
        return ("automation sidecar LAST_RUN.md files",)
    if kind == KIND_GATE_ALIGNMENT:
        return ("money-path and promotion sidecars",)
    return ("current automation sidecars",)


def _produces_evidence_for(kind: str) -> tuple[str, ...]:
    if kind in _STRATEGY_KINDS:
        return _EVIDENCE_KEYS + ("forward_track",)
    return ("factory_validation",)


def _status_value(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {EVIDENCE_PASS, "ok", "passed", "edge_confirmed", "true"}:
        return EVIDENCE_PASS
    if text in {EVIDENCE_FAIL, "failed", "no_edge", "false"}:
        return EVIDENCE_FAIL
    if text in {EVIDENCE_PENDING, "running", "queued"}:
        return EVIDENCE_PENDING
    return EVIDENCE_MISSING


def _mapping_has_list(doc: Mapping[str, Any] | None, key: str) -> bool:
    return isinstance(doc, Mapping) and isinstance(doc.get(key), list)


def _candidate_id(candidate: Mapping[str, Any] | object) -> str:
    if not isinstance(candidate, Mapping):
        return ""
    return str(candidate.get("candidate_id") or "").strip()


def _safe_slug(value: str) -> str:
    out = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    out = "-".join(part for part in out.split("-") if part)
    return out[:64] or "candidate"


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso(value: datetime) -> str:
    return _ensure_utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def stable_id(prefix: str, *parts: object) -> str:
    text = "\n".join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]}"


__all__ = [
    "EVIDENCE_FAIL",
    "EVIDENCE_MISSING",
    "EVIDENCE_PASS",
    "EVIDENCE_PENDING",
    "KIND_ANALYTICS_VALIDATION",
    "KIND_DATA_COLLECTION",
    "KIND_DATA_QUALITY",
    "KIND_EXECUTION_QUALITY",
    "KIND_GATE_ALIGNMENT",
    "KIND_OPS_LIVENESS",
    "KIND_PORTFOLIO_BACKTEST",
    "KIND_REVIEW_LEDGER",
    "KIND_STRATEGY_BACKTEST",
    "OVERALL_DEGRADED",
    "OVERALL_OK",
    "SCHEMA_VERSION",
    "STATUS_BLOCKED",
    "STATUS_EVIDENCE_PASSED",
    "STATUS_PENDING",
    "STATUS_READY",
    "CandidateFactoryRun",
    "EvidenceResult",
    "ImplementationPackage",
    "build_candidate_factory_run",
    "enrich_candidate_backlog",
    "parse_result_evidence",
    "stable_id",
    "write_candidate_factory_artifacts",
]

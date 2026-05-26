"""권한 등급 분류 (스펙 005, FR-A05·A06·A09, data-model.md §4).

후보 변경의 대상 파일이 Kernel(`kernel.toml`)에 닿는지 기존
`deploy/kernel_guard`로 판정한다. 닿으면 1차 분류와 무관하게 **L4로 강제**
한다(방어 심층화). `kernel.toml`·헌법 자체(K-meta)는 튜너가 절대 자동 적용
대상으로 삼지 않는다.

이 모듈은 순수 함수다 — 같은 입력(후보 + 매니페스트)이면 같은 등급
(SC-A01 결정성). LLM 미호출.
"""

from __future__ import annotations

from pathlib import Path

from auto_invest.deploy.kernel_guard import (
    KernelManifest,
    kernel_diff_check,
    load_kernel_manifest,
)
from auto_invest.tuner.models import CandidateChange, Classification

# K-meta 경로(forensic 콜아웃용 추가 표식). kernel_guard.match 가 이미 K_meta
# 그룹으로 잡지만, 튜너가 K-meta 를 "절대 수정하지 않는다"(FR-A06)는 사실을
# 분류 사유에 명시하기 위해 별도로 인식한다.
_KMETA_PATHS = (
    ".specify/memory/kernel.toml",
    ".specify/memory/constitution.md",
)


def _non_kernel_tier(candidate: CandidateChange) -> tuple[str, str]:
    """Kernel 비교집합 후보의 1차 등급 + 사유.

    권한 등급 모델(spec.md)에 따라 대상 파일·변경 종류로 결정한다.
    """
    if candidate.proposed.kind == "threshold_tighten":
        return "L1", "non-kernel KPI threshold knob → L1 (low-risk, reversible)"
    # 판단 지점 max_tokens 튜닝(LLM 비용/품질 영향, 헌법 III·VI) → 캐너리 검증 필수.
    if candidate.proposed.kind == "max_tokens_reduce":
        return "L2", "judgment max_tokens knob (LLM cost/quality) → L2 (canary)"
    # proposal_only / 미래 변경: 대상 파일 패턴으로 캐너리 등급 판정.
    for p in candidate.proposed.target_paths:
        if "/judgment/" in p or "judgment_tunables" in p or "prompt" in p.lower():
            return "L2", "prompt/judgment-parameter surface → L2 (canary)"
        if p.startswith("specs/") or "migrations/" in p:
            return "L3", "new scaffolding/schema → L3 (canary, extended window)"
    # 적용 노브가 없는 드리프트 감지(cost/cache/latency): 의도 등급은 L1
    # (스텁의 'detection rules, all L1')이나 v1에 적용 경로가 없다 → runner 가
    # no_apply_path 로 스킵한다.
    return "L1", "non-kernel drift proposal → L1 intent (no v1 apply path)"


def classify(
    candidate: CandidateChange,
    manifest: KernelManifest,
) -> Classification:
    """후보를 L1/L2/L3/L4 로 분류한다. Kernel 교집합이면 무조건 L4."""
    target_paths = candidate.proposed.target_paths
    report = kernel_diff_check(list(target_paths), manifest)
    if not report.is_clean:
        groups = report.touched_groups
        is_kmeta = any(p in _KMETA_PATHS for p in target_paths) or "K_meta" in groups
        if is_kmeta:
            reason = (
                "K-meta touch (kernel manifest/constitution) → forced L4; "
                "튜너는 K-meta 를 절대 자동 수정하지 않음 (FR-A06)"
            )
        else:
            reason = f"kernel touch (groups: {', '.join(groups)}) → forced L4 (FR-A05)"
        return Classification(
            candidate=candidate,
            tier="L4",
            kernel_groups=groups,
            reason=reason,
        )

    tier, reason = _non_kernel_tier(candidate)
    return Classification(
        candidate=candidate,
        tier=tier,  # type: ignore[arg-type]
        kernel_groups=(),
        reason=reason,
    )


def classify_all(
    candidates: list[CandidateChange],
    *,
    kernel_path: Path | None = None,
    manifest: KernelManifest | None = None,
) -> list[Classification]:
    """후보 리스트를 한 번에 분류한다(매니페스트 1회 로드)."""
    if manifest is None:
        manifest = load_kernel_manifest(kernel_path)
    return [classify(c, manifest) for c in candidates]


__all__ = ["classify", "classify_all"]

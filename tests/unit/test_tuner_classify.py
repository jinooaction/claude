"""스펙 005 — 권한 등급 분류 (SC-A02, SC-A09)."""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_invest.deploy.kernel_guard import load_kernel_manifest
from auto_invest.tuner.classify import classify
from auto_invest.tuner.models import CandidateChange, ProposedChange

KERNEL_PATH = Path(".specify/memory/kernel.toml")


def _candidate(target_paths: tuple[str, ...], kind: str = "proposal_only") -> CandidateChange:
    return CandidateChange(
        candidate_id="t:test",
        detection_rule="test",
        kpi_name="latency_p95_ms",
        observed_value="1500",
        observed_tier="B",
        window="30d",
        proposed=ProposedChange(kind=kind, target_paths=target_paths),  # type: ignore[arg-type]
        rationale="r",
        measurement_sample=30,
    )


@pytest.fixture
def manifest():
    return load_kernel_manifest(KERNEL_PATH)


# (kernel file, expected group) — K1~K6 + K_meta 전수.
_KERNEL_CASES = [
    ("src/auto_invest/risk/gates.py", "K1_position_sizing"),
    ("src/auto_invest/config/whitelist.py", "K2_whitelist"),
    ("src/auto_invest/telemetry/meter.py", "K3_judgment_points"),
    ("src/auto_invest/persistence/audit.py", "K4_append_only_audit"),
    ("src/auto_invest/logging_config.py", "K5_secret_isolation"),
    ("src/auto_invest/worker/schedule.py", "K6_market_hours_guard"),
    (".specify/memory/kernel.toml", "K_meta"),
    (".specify/memory/constitution.md", "K_meta"),
]


@pytest.mark.parametrize("path,group", _KERNEL_CASES)
def test_kernel_touch_forces_l4(manifest, path: str, group: str) -> None:
    """대상 파일이 Kernel 에 닿으면 무조건 L4 (SC-A02)."""
    cls = classify(_candidate((path,)), manifest)
    assert cls.tier == "L4"
    assert group in cls.kernel_groups


def test_kmeta_paths_get_kmeta_reason(manifest) -> None:
    """kernel.toml·헌법은 L4 + 'K-meta 미수정' 사유 (SC-A09)."""
    for p in (".specify/memory/kernel.toml", ".specify/memory/constitution.md"):
        cls = classify(_candidate((p,)), manifest)
        assert cls.tier == "L4"
        assert "K-meta" in cls.reason


def test_kernel_plus_nonkernel_still_l4(manifest) -> None:
    """Kernel + 비커널을 함께 건드려도 L4 강등."""
    cls = classify(
        _candidate(("config/llm_kpi_thresholds.toml", "src/auto_invest/risk/gates.py")),
        manifest,
    )
    assert cls.tier == "L4"
    assert "K1_position_sizing" in cls.kernel_groups


def test_threshold_knob_is_l1(manifest) -> None:
    """비커널 KPI 임계값 노브는 L1."""
    cls = classify(
        _candidate(("config/llm_kpi_thresholds.toml",), kind="threshold_tighten"),
        manifest,
    )
    assert cls.tier == "L1"
    assert cls.kernel_groups == ()


def test_judgment_surface_is_l2(manifest) -> None:
    cls = classify(_candidate(("src/auto_invest/judgment/points/volatility.py",)), manifest)
    assert cls.tier == "L2"


def test_new_spec_scaffolding_is_l3(manifest) -> None:
    cls = classify(_candidate(("specs/099-future/spec.md",)), manifest)
    assert cls.tier == "L3"


def test_classification_deterministic(manifest) -> None:
    """같은 입력 → 같은 등급 (SC-A01)."""
    cand = _candidate(("config/llm_kpi_thresholds.toml",), kind="threshold_tighten")
    assert classify(cand, manifest) == classify(cand, manifest)

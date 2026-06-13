"""스펙 051 — 파이프라인 생존 감시 프로브 통합 테스트.

워크플로가 만드는 사이드카 디렉터리(<key>.md)를 흉내 내, 프로브가 디렉터리를 읽어
판정·출력하고 --strict 종료 코드를 올바로 내는지 검증한다. scripts/ 는 패키지가
아니므로 파일 경로로 직접 로드한다(실제 진입점 검증).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from auto_invest.analytics.pipeline_liveness import default_specs

_PROBE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "pipeline_liveness_probe.py"
_spec = importlib.util.spec_from_file_location("pipeline_liveness_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def _write_sidecar(d: Path, key: str, ts: str) -> None:
    (d / f"{key}.md").write_text(f"| timestamp_utc | {ts} |\n", encoding="utf-8")


def test_probe_all_fresh_json(tmp_path, capsys):
    # 모든 사이드카를 기준 시각 직전으로 채운다 → 종합 OK.
    for spec in default_specs():
        _write_sidecar(tmp_path, spec.key, "2026-06-13T11:00:00Z")
    rc = probe_main(
        ["--sidecar-dir", str(tmp_path), "--json", "--now", "2026-06-13T12:00:00Z"]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["overall"] == "OK"
    assert {c["key"] for c in out["checks"]} == {s.key for s in default_specs()}


def test_probe_missing_critical_strict_exits_nonzero(tmp_path, capsys):
    # 핵심(rebalance-paper-forward) 사이드카만 빼고 나머지는 신선하게.
    for spec in default_specs():
        if spec.key == "rebalance-paper-forward":
            continue
        _write_sidecar(tmp_path, spec.key, "2026-06-13T11:00:00Z")
    rc = probe_main(
        [
            "--sidecar-dir",
            str(tmp_path),
            "--json",
            "--strict",
            "--now",
            "2026-06-13T12:00:00Z",
        ]
    )
    assert rc == 1  # 핵심 사이드카 MISSING → strict 비정상 종료
    out = json.loads(capsys.readouterr().out)
    assert out["overall"] == "CRITICAL"
    missing = [c for c in out["checks"] if c["key"] == "rebalance-paper-forward"]
    assert missing and missing[0]["status"] == "MISSING"


def test_probe_without_strict_always_exits_zero(tmp_path, capsys):
    # strict 가 없으면 CRITICAL 이어도 종료 코드 0(워크플로가 발행 후 별도로 실패시킴).
    # 디렉터리를 비워 전부 MISSING → 종합 CRITICAL.
    rc = probe_main(
        ["--sidecar-dir", str(tmp_path), "--json", "--now", "2026-06-13T12:00:00Z"]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["overall"] == "CRITICAL"


def test_probe_text_output_renders(tmp_path, capsys):
    for spec in default_specs():
        _write_sidecar(tmp_path, spec.key, "2026-06-13T11:00:00Z")
    rc = probe_main(["--sidecar-dir", str(tmp_path), "--now", "2026-06-13T12:00:00Z"])
    assert rc == 0
    text = capsys.readouterr().out
    assert "파이프라인 생존 감시" in text
    assert "종합 판정" in text

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_mobile_status_generator_renders_html(tmp_path: Path) -> None:
    sidecars = tmp_path / "sidecars"
    sidecars.mkdir()
    (sidecars / "kis-smoke.md").write_text(
        "| 항목 | 값 |\n|------|-----|\n| timestamp_utc | 2026-06-18T07:00:00Z |\n",
        encoding="utf-8",
    )
    output = tmp_path / "status.html"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/generate_mobile_status.py",
            "--sidecar-dir",
            str(sidecars),
            "--output",
            str(output),
            "--repository",
            "jinooaction/claude",
            "--commit",
            "abcdef123456",
            "--now",
            "2026-06-18T08:00:00Z",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    html = output.read_text(encoding="utf-8")
    assert "Wrote" in result.stdout
    assert "<html lang=\"ko\">" in html
    assert "auto-invest 상태판" in html
    assert "KIS 연결" in html
    assert "abcdef1" in html
    assert "status-data" in html


def test_mobile_status_manifest_lists_sidecars() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/generate_mobile_status.py",
            "--sidecar-dir",
            "/tmp/unused",
            "--manifest",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "kis-smoke\tautomation/kis-smoke-last-run\tLAST_RUN.md" in result.stdout

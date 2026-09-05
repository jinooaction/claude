"""늦은 예약 이벤트와 최신 증거를 섞어 자본 변경을 제안하지 않는다."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check_autoarm_main.sh"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture
def repository(tmp_path: Path) -> tuple[Path, Path, str]:
    remote = tmp_path / "remote"
    remote.mkdir()
    git(remote, "init", "-q", "-b", "main")
    git(remote, "config", "user.name", "test")
    git(remote, "config", "user.email", "test@example.invalid")
    git(remote, "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-qm", "base")
    base = git(remote, "rev-parse", "HEAD")
    local = tmp_path / "local"
    subprocess.run(["git", "clone", "-q", str(remote), str(local)], check=True)
    return remote, local, base


def run_guard(local: Path, base: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT)], cwd=local, env={**os.environ, "GITHUB_SHA": base},
        check=False, capture_output=True, text=True,
    )


def test_current_main_passes_without_modifying_checkout(repository) -> None:
    _, local, base = repository
    before = git(local, "status", "--porcelain")
    assert run_guard(local, base).returncode == 0
    assert git(local, "status", "--porcelain") == before
    assert git(local, "rev-parse", "HEAD") == base


def test_main_moves_while_event_waits_or_tests_run(repository) -> None:
    remote, local, base = repository
    assert run_guard(local, base).returncode == 0
    git(remote, "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-qm", "new main")
    result = run_guard(local, base)
    assert result.returncode == 75
    assert "no longer current main" in result.stderr
    assert git(local, "rev-parse", "HEAD") == base
    assert git(local, "status", "--porcelain") == ""


@pytest.mark.parametrize("expected", ["", "main", "a" * 39, "A" * 40])
def test_invalid_event_is_blocked(repository, expected: str) -> None:
    _, local, _ = repository
    assert run_guard(local, expected).returncode == 75


@pytest.mark.parametrize("failure", ["missing_main", "unreachable"])
def test_remote_uncertainty_is_blocked(repository, failure: str) -> None:
    remote, local, base = repository
    if failure == "missing_main":
        git(remote, "branch", "-m", "not-main")
    else:
        git(local, "remote", "set-url", "origin", str(remote / "not-a-repository"))
    assert run_guard(local, base).returncode == 75


def test_workflow_rechecks_before_evidence_decision_and_external_writes() -> None:
    workflow = (ROOT / ".github/workflows/forward-edge-autoarm.yml").read_text()
    assert workflow.index("Verify current main before reading evidence") < workflow.index(
        "Read exact deployed-strategy profit evidence",
    )
    assert (
        'bash scripts/check_autoarm_main.sh\n          uv run auto-invest ladder-decide'
    ) in workflow
    assert workflow.count('bash scripts/check_autoarm_main.sh\n          git push -u origin') == 2
    assert 'bash scripts/check_autoarm_main.sh\n          if gh pr merge' in workflow

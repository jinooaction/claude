"""Spec 176: production runtime revision equivalence stays fail-closed."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GATEWAY = ROOT / "deploy" / "live-canary-on-instance.sh"
SCHEDULER = ROOT / "deploy" / "live-canary-scheduled-on-instance.sh"


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args), cwd=cwd, text=True, capture_output=True, check=True
    )


@pytest.fixture
def revision_repo(tmp_path: Path) -> tuple[Path, dict[str, str], str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run("git", "init", "-q", "-b", "main", cwd=repo)
    _run("git", "config", "user.name", "test", cwd=repo)
    _run("git", "config", "user.email", "test@example.com", cwd=repo)
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _run("git", "add", ".", cwd=repo)
    _run("git", "commit", "-qm", "base", cwd=repo)
    base = _run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()
    _run("git", "remote", "add", "origin", str(repo), cwd=repo)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    sudo = fake_bin / "sudo"
    sudo.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ \"${1:-}\" == \"-u\" ]]; then shift 2; fi\n"
        "if [[ \"${1:-}\" == \"-H\" ]]; then shift; fi\n"
        "exec \"$@\"\n",
        encoding="utf-8",
    )
    sudo.chmod(0o755)
    env = os.environ.copy()
    env.update({"REPO": str(repo), "PATH": f"{fake_bin}:{env['PATH']}"})
    return repo, env, base


def _commit_main_path(repo: Path, path: str) -> str:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"changed {path}\n", encoding="utf-8")
    _run("git", "add", path, cwd=repo)
    _run("git", "commit", "-qm", f"change {path}", cwd=repo)
    return _run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()


def _source_call(
    script: Path,
    command: str,
    *,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    source = script.read_text(encoding="utf-8").rsplit('\nmain "$@"', 1)[0]
    return subprocess.run(
        ["bash"],
        input=(
            f"{source}\n"
            'git_as_app() { git -C "${REPO}" "$@"; }\n'
            f"{command}\n"
        ),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def _prepare_descendant(repo: Path, base: str, path: str) -> str:
    main_sha = _commit_main_path(repo, path)
    _run("git", "checkout", "-q", "--detach", base, cwd=repo)
    return main_sha


@pytest.mark.parametrize(
    "path",
    ["HANDOFF.md", "specs/176-note.json", ".verify/pass", ".trigger/pass"],
)
def test_deploy_excluded_descendant_is_operationally_equivalent_in_both_boundaries(
    revision_repo: tuple[Path, dict[str, str], str], path: str
) -> None:
    repo, env, base = revision_repo
    main_sha = _prepare_descendant(repo, base, path)

    gateway = _source_call(
        GATEWAY,
        f"validate_deployed_commit {main_sha} current-main; "
        "printf '%s\\t%s\\n' \"${DEPLOYED_CODE_COMMIT}\" \"${MAIN_CODE_COMMIT}\"",
        env=env,
    )
    scheduler = _source_call(
        SCHEDULER,
        "validate_operational_revision; "
        "printf '%s\\t%s\\n' \"${DEPLOYED_CODE_COMMIT}\" \"${MAIN_CODE_COMMIT}\"",
        env=env,
    )

    expected = f"{base}\t{main_sha}\n"
    assert gateway.returncode == 0, gateway.stderr
    assert gateway.stdout == expected
    assert scheduler.returncode == 0, scheduler.stderr
    assert scheduler.stdout == expected


@pytest.mark.parametrize(
    "path",
    [
        "src/runtime.py",
        "deploy/runtime.toml",
        ".github/workflows/runtime.yml",
        "automation/rebalance-live.request",
        "config.toml",
    ],
)
def test_runtime_or_unclassified_descendant_fails_closed_in_both_boundaries(
    revision_repo: tuple[Path, dict[str, str], str], path: str
) -> None:
    repo, env, base = revision_repo
    main_sha = _prepare_descendant(repo, base, path)

    gateway = _source_call(
        GATEWAY, f"validate_deployed_commit {main_sha} current-main", env=env
    )
    scheduler = _source_call(
        SCHEDULER, "validate_operational_revision", env=env
    )

    assert gateway.returncode == 2
    assert path in gateway.stderr
    assert scheduler.returncode == 2
    assert path in scheduler.stderr


def test_diverged_deployed_history_fails_closed_in_both_boundaries(
    revision_repo: tuple[Path, dict[str, str], str]
) -> None:
    repo, env, base = revision_repo
    main_sha = _commit_main_path(repo, "HANDOFF.md")
    _run("git", "checkout", "-q", "--detach", base, cwd=repo)
    _commit_main_path(repo, "server-only.txt")

    gateway = _source_call(
        GATEWAY, f"validate_deployed_commit {main_sha} current-main", env=env
    )
    scheduler = _source_call(
        SCHEDULER, "validate_operational_revision", env=env
    )

    assert gateway.returncode == 2
    assert "not an ancestor" in gateway.stderr
    assert scheduler.returncode == 2
    assert "not an ancestor" in scheduler.stderr


def test_systemd_boundary_rejects_a_stale_authority_commit_even_when_runtime_matches(
    revision_repo: tuple[Path, dict[str, str], str]
) -> None:
    repo, env, base = revision_repo
    _prepare_descendant(repo, base, "HANDOFF.md")

    gateway = _source_call(
        GATEWAY, f"validate_deployed_commit {base} current-main", env=env
    )

    assert gateway.returncode == 2
    assert "current main authority" in gateway.stderr


def test_scheduler_summary_distinguishes_main_authority_from_deployed_runtime() -> None:
    scheduler = SCHEDULER.read_text(encoding="utf-8")
    gateway = GATEWAY.read_text(encoding="utf-8")

    assert '--arg schema_version "1.1"' in scheduler
    assert '--arg deployed_code_commit "${deployed_sha}"' in scheduler
    assert '--argjson operational_equivalent true' in scheduler
    assert "deployed_code_commit:$deployed_code_commit" in scheduler
    assert "operational_equivalent:$operational_equivalent" in scheduler
    assert 'validate_deploy_audit "${deployed_sha}"' in scheduler
    assert 'run_entry_revalidation "${main_sha}"' in scheduler
    assert 'systemd-order "${run_id}" "${main_sha}"' in scheduler
    assert 'validate_deployed_commit "${signed_sha}" "current-main"' in gateway
    assert '"${deployed_sha}" == "${signed_sha}"' not in gateway
    assert '"${main_sha}" == "${signed_sha}"' not in gateway

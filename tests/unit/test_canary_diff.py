"""Spec 007 T011 — diff helper + baseline resolution + kernel intersection.

Covers R-C1 (baseline-rev chain through audit log), R-C7 (working-tree
ignored), R-C8 (kernel-touch payload), and the SHA-40 contract.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from auto_invest.canary.diff import (
    FALLBACK_BASELINE,
    GitRevResolutionError,
    diff_paths,
    intersect_kernel,
    resolve_baseline,
    resolve_rev,
)
from auto_invest.deploy.kernel_guard import KernelGroup, KernelManifest
from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import CanaryPassedPayload


# ---------------------------------------------------------- fixtures: tiny git repo


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a tiny throwaway repo with three commits on `main`.

    Layout:
      - commit A: README.md, src/auto_invest/risk/gates.py
      - commit B: edits README.md only
      - commit C: edits src/auto_invest/risk/gates.py (kernel-touch)
    """

    def run(*args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            env={
                "HOME": str(tmp_path),
                "GIT_AUTHOR_NAME": "spec007",
                "GIT_AUTHOR_EMAIL": "spec007@example.com",
                "GIT_COMMITTER_NAME": "spec007",
                "GIT_COMMITTER_EMAIL": "spec007@example.com",
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_CONFIG_SYSTEM": "/dev/null",
            },
        )

    run("init", "--initial-branch=main", "--quiet")
    (tmp_path / "README.md").write_text("hello\n")
    (tmp_path / "src" / "auto_invest" / "risk").mkdir(parents=True)
    (tmp_path / "src" / "auto_invest" / "risk" / "gates.py").write_text(
        "def per_trade_cap_gate(): pass\n"
    )
    run("add", ".")
    run("commit", "-m", "A: initial")

    (tmp_path / "README.md").write_text("hello world\n")
    run("add", "README.md")
    run("commit", "-m", "B: README edit")

    (tmp_path / "src" / "auto_invest" / "risk" / "gates.py").write_text(
        "def per_trade_cap_gate(): return 'changed'\n"
    )
    run("add", "src/auto_invest/risk/gates.py")
    run("commit", "-m", "C: gates touch")

    return tmp_path


def _sha(repo: Path, ref: str) -> str:
    out = subprocess.run(
        ["git", "rev-parse", ref],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


# ---------------------------------------------------------- resolve_rev


def test_resolve_rev_returns_sha40_for_head(git_repo: Path) -> None:
    sha = resolve_rev("HEAD", cwd=git_repo)
    assert len(sha) == 40
    assert all(c in "0123456789abcdef" for c in sha)
    assert sha == _sha(git_repo, "HEAD")


def test_resolve_rev_accepts_short_sha(git_repo: Path) -> None:
    full = _sha(git_repo, "HEAD")
    short = full[:7]
    assert resolve_rev(short, cwd=git_repo) == full


def test_resolve_rev_rejects_unknown_ref(git_repo: Path) -> None:
    with pytest.raises(GitRevResolutionError):
        resolve_rev("origin/does-not-exist", cwd=git_repo)


# ---------------------------------------------------------- diff_paths (R-C7)


def test_diff_paths_between_two_commits(git_repo: Path) -> None:
    a = _sha(git_repo, "HEAD~2")
    c = _sha(git_repo, "HEAD")
    paths = diff_paths(baseline_sha=a, candidate_sha=c, cwd=git_repo)
    assert paths == sorted(
        ["README.md", "src/auto_invest/risk/gates.py"]
    )


def test_diff_paths_identical_revs_returns_empty(git_repo: Path) -> None:
    head = _sha(git_repo, "HEAD")
    assert diff_paths(baseline_sha=head, candidate_sha=head, cwd=git_repo) == []


def test_diff_paths_ignores_working_tree(git_repo: Path, monkeypatch) -> None:
    """R-C7 — the canary tests committed revs, NOT local edits."""
    b = _sha(git_repo, "HEAD~1")
    c = _sha(git_repo, "HEAD")
    # Make working-tree dirty with an unrelated path.
    (git_repo / "wt_only.py").write_text("unrelated\n")
    paths = diff_paths(baseline_sha=b, candidate_sha=c, cwd=git_repo)
    assert "wt_only.py" not in paths


# ---------------------------------------------------------- resolve_baseline (R-C1)


def test_resolve_baseline_falls_back_to_main_when_no_prior_pass(
    tmp_path: Path, git_repo: Path
) -> None:
    conn = db.get_connection(tmp_path / "audit.sqlite")
    db.migrate(conn)
    head = _sha(git_repo, "HEAD")
    # Configure a fake "origin/main" branch pointing at HEAD~1.
    main_sha = _sha(git_repo, "HEAD~1")
    subprocess.run(
        ["git", "update-ref", f"refs/remotes/{FALLBACK_BASELINE}", main_sha],
        cwd=git_repo,
        check=True,
    )
    try:
        resolved = resolve_baseline(audit_conn=conn, candidate_rev=head, cwd=git_repo)
        assert resolved == main_sha
    finally:
        conn.close()


def test_resolve_baseline_picks_latest_canary_passed(
    tmp_path: Path, git_repo: Path
) -> None:
    """R-C1 — chain through the most recent CANARY_PASSED row."""
    conn = db.get_connection(tmp_path / "audit.sqlite")
    db.migrate(conn)
    older_sha = "0" * 40
    newer_sha = "1" * 40
    candidate_sha = "2" * 40
    audit.append(
        conn,
        CanaryPassedPayload(
            canary_run_id="r0",
            candidate_rev=older_sha,
            baseline_rev="x" * 40,
            tier="L2",
            finished_at="2026-04-01T00:00:00.000Z",
            artefact_path="data/canary/r0/canary-run.json",
        ),
        correlation_id="r0",
    )
    audit.append(
        conn,
        CanaryPassedPayload(
            canary_run_id="r1",
            candidate_rev=newer_sha,
            baseline_rev=older_sha,
            tier="L2",
            finished_at="2026-04-02T00:00:00.000Z",
            artefact_path="data/canary/r1/canary-run.json",
        ),
        correlation_id="r1",
    )
    conn.commit()
    resolved = resolve_baseline(
        audit_conn=conn, candidate_rev=candidate_sha, cwd=git_repo
    )
    assert resolved == newer_sha
    conn.close()


def test_resolve_baseline_skips_self_match(
    tmp_path: Path, git_repo: Path
) -> None:
    """Don't compare the candidate to itself — fall through to the next row or fallback."""
    conn = db.get_connection(tmp_path / "audit.sqlite")
    db.migrate(conn)
    candidate_sha = "a" * 40
    audit.append(
        conn,
        CanaryPassedPayload(
            canary_run_id="r0",
            candidate_rev=candidate_sha,
            baseline_rev="b" * 40,
            tier="L2",
            finished_at="2026-04-01T00:00:00.000Z",
            artefact_path="data/canary/r0/canary-run.json",
        ),
        correlation_id="r0",
    )
    conn.commit()

    main_sha = _sha(git_repo, "HEAD~1")
    subprocess.run(
        ["git", "update-ref", f"refs/remotes/{FALLBACK_BASELINE}", main_sha],
        cwd=git_repo,
        check=True,
    )
    resolved = resolve_baseline(
        audit_conn=conn, candidate_rev=candidate_sha, cwd=git_repo
    )
    assert resolved == main_sha
    conn.close()


# ---------------------------------------------------------- intersect_kernel (R-C8)


def _manifest_for_test() -> KernelManifest:
    """Synthetic manifest with one entry per group label used in tests."""
    return KernelManifest(
        groups={
            "K1_position_sizing": KernelGroup(
                description="caps",
                files=("src/auto_invest/risk/gates.py",),
            ),
            "K4_append_only_audit": KernelGroup(
                description="audit",
                files=("src/auto_invest/persistence/audit.py",),
            ),
            "K_meta": KernelGroup(
                description="meta",
                files=(".specify/memory/constitution.md", ".specify/memory/kernel.toml"),
            ),
        },
        source_path=".specify/memory/kernel.toml",
    )


def test_intersect_kernel_empty_when_no_touched_paths() -> None:
    assert intersect_kernel([], manifest=_manifest_for_test()) == []


def test_intersect_kernel_groups_paths_by_group_label() -> None:
    touched = [
        "README.md",
        "src/auto_invest/risk/gates.py",
        "src/auto_invest/persistence/audit.py",
        "src/auto_invest/something/non_kernel.py",
    ]
    result = intersect_kernel(touched, manifest=_manifest_for_test())
    groups = {kt.group: list(kt.files) for kt in result}
    assert groups == {
        "K1": ["src/auto_invest/risk/gates.py"],
        "K4": ["src/auto_invest/persistence/audit.py"],
    }


def test_intersect_kernel_sorts_by_kernel_rank() -> None:
    # Touch K_meta + K1 + K4; expect K1, K4, K_meta in that order.
    touched = [
        ".specify/memory/kernel.toml",
        "src/auto_invest/persistence/audit.py",
        "src/auto_invest/risk/gates.py",
    ]
    result = intersect_kernel(touched, manifest=_manifest_for_test())
    assert [kt.group for kt in result] == ["K1", "K4", "K_meta"]


def test_intersect_kernel_files_sorted_lexicographically() -> None:
    touched = [
        ".specify/memory/kernel.toml",
        ".specify/memory/constitution.md",
    ]
    result = intersect_kernel(touched, manifest=_manifest_for_test())
    assert len(result) == 1
    assert result[0].group == "K_meta"
    assert result[0].files == [
        ".specify/memory/constitution.md",
        ".specify/memory/kernel.toml",
    ]

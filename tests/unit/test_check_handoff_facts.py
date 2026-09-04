from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


def _load_checker():
    path = Path(__file__).resolve().parents[2] / "scripts" / "check_handoff_facts.py"
    spec = importlib.util.spec_from_file_location("check_handoff_facts", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _handoff(tmp_path: Path, main_row: str) -> Path:
    path = tmp_path / "HANDOFF.md"
    path.write_text(
        f"""
# Handoff

| 항목 | 상태 |
|------|------|
| 마지막 main 커밋 | {main_row} |
| main 테스트 | `uv run pytest -q` -> 2205 passed, 4 skipped |
| main 린트 | `uv run ruff check src tests` -> All checks passed |
| 열린 PR | 없음 |
""",
        encoding="utf-8",
    )
    return path


def test_handoff_fact_check_passes_when_summary_matches(tmp_path, monkeypatch):
    checker = _load_checker()
    monkeypatch.setattr(
        checker,
        "_git",
        lambda _repo, *_args: "fe2af54 Merge pull request #369 from branch",
    )
    handoff = _handoff(tmp_path, "`fe2af54` - Merge pull request #369")

    report = checker.evaluate(
        tmp_path,
        handoff_path=handoff,
        expect_pytest="2205 passed, 4 skipped",
        expect_ruff="All checks passed",
        expect_open_pr="없음",
    )

    assert report.status == "OK"
    assert all(fact.status == "PASS" for fact in report.facts)


def test_handoff_fact_check_fails_stale_main_commit(tmp_path, monkeypatch):
    checker = _load_checker()
    monkeypatch.setattr(
        checker,
        "_git",
        lambda _repo, *_args: "fe2af54 Merge pull request #369 from branch",
    )
    handoff = _handoff(tmp_path, "`cbc2cd4` - Merge pull request #368")

    report = checker.evaluate(tmp_path, handoff_path=handoff)

    assert report.status == "DEGRADED"
    main_fact = next(fact for fact in report.facts if fact.id == "main_commit")
    assert main_fact.status == "FAIL"


def test_handoff_fact_check_accepts_previous_baseline_for_handoff_only_merge(
    tmp_path, monkeypatch
):
    checker = _load_checker()

    def fake_git(_repo, *args):
        if args == ("log", "-1", "--pretty=%h %s", "origin/main"):
            return "eb32b8d Merge pull request #371 from handoff"
        if args == ("rev-list", "--parents", "-n", "1", "origin/main"):
            return "eb32b8d75986295 ecc93f2112bea88 ceb5749f00d"
        if args == ("diff", "--name-only", "ecc93f2112bea88", "eb32b8d75986295"):
            return "\n".join(
                [
                    "HANDOFF.md",
                    "HANDOFF-052-AGENT-QUALITY-REDTEAM.md",
                    "specs/057-agent-quality-redteam/tasks.md",
                ]
            )
        if args == ("log", "-1", "--pretty=%h %s", "ecc93f2112bea88"):
            return "ecc93f2 Merge pull request #370 from feature"
        return ""

    monkeypatch.setattr(checker, "_git", fake_git)
    handoff = _handoff(tmp_path, "`ecc93f2` - Merge pull request #370")

    report = checker.evaluate(tmp_path, handoff_path=handoff)

    assert report.status == "OK"
    main_fact = next(fact for fact in report.facts if fact.id == "main_commit")
    assert main_fact.status == "PASS"
    assert "previous main before handoff-only merge" in main_fact.message


def test_handoff_fact_check_fails_missing_expected_validation(tmp_path, monkeypatch):
    checker = _load_checker()
    monkeypatch.setattr(
        checker,
        "_git",
        lambda _repo, *_args: "fe2af54 Merge pull request #369 from branch",
    )
    handoff = _handoff(tmp_path, "`fe2af54` - Merge pull request #369")

    report = checker.evaluate(
        tmp_path,
        handoff_path=handoff,
        expect_pytest="9999 passed",
    )

    assert report.status == "DEGRADED"
    pytest_fact = next(fact for fact in report.facts if fact.id == "main_pytest")
    assert pytest_fact.status == "FAIL"


def test_real_shallow_clone_needs_history_for_handoff_only_parent(tmp_path):
    checker = _load_checker()
    upstream = tmp_path / "upstream"
    upstream.mkdir()

    def git(repo: Path, *args: str) -> str:
        return subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
             "-c", "commit.gpgsign=false", "-C", str(repo), *args],
            check=True, capture_output=True, text=True, timeout=15,
        ).stdout.strip()

    git(upstream, "init", "-q", "-b", "main")
    (upstream / "runtime.py").write_text("pass\n", encoding="utf-8")
    git(upstream, "add", "runtime.py")
    git(upstream, "commit", "-qm", "runtime baseline")
    baseline = git(upstream, "rev-parse", "--short", "HEAD")
    git(upstream, "switch", "-qc", "handoff")
    _handoff(upstream, f"`{baseline}` runtime baseline")
    git(upstream, "add", "HANDOFF.md")
    git(upstream, "commit", "-qm", "record runtime baseline")
    git(upstream, "switch", "-q", "main")
    git(upstream, "merge", "--no-ff", "-m", "handoff merge", "handoff")

    clone = tmp_path / "shallow"
    git(tmp_path, "clone", "-q", "--depth", "1", upstream.as_uri(), str(clone))
    assert git(clone, "rev-parse", "--is-shallow-repository") == "true"
    assert checker.evaluate(clone).status == "DEGRADED"
    git(clone, "fetch", "-q", "--unshallow", "origin")
    assert git(clone, "rev-parse", "--is-shallow-repository") == "false"
    assert checker.evaluate(clone).status == "OK"

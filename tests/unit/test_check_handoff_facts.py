from __future__ import annotations

import importlib.util
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

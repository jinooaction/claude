"""스펙 079 — 완료 후보 소비 장부 단위 테스트."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.released_work import (
    ENTRY_STATUS_RELEASED,
    STATUS_EMPTY,
    STATUS_OK,
    scan_released_work,
)

NOW = datetime(2026, 7, 2, 9, 5, 0, tzinfo=UTC)


def _write_complete_spec(
    root: Path,
    spec_name: str,
    *,
    candidate_id: str,
    checked: bool = True,
    field: str = "selected_work_candidate",
) -> None:
    spec_dir = root / "specs" / spec_name
    contracts_dir = spec_dir / "contracts"
    contracts_dir.mkdir(parents=True)
    mark = "x" if checked else " "
    (spec_dir / "tasks.md").write_text(
        f"# Tasks\n\n- [{mark}] T001 구현 완료\n",
        encoding="utf-8",
    )
    (contracts_dir / "completion.md").write_text(
        "{\n"
        f'  "{field}": "{candidate_id}",\n'
        '  "status": "released"\n'
        "}\n",
        encoding="utf-8",
    )


def test_scan_released_work_reads_only_completed_specs_with_explicit_fields(tmp_path):
    _write_complete_spec(
        tmp_path,
        "078-money-gate-alignment-loop",
        candidate_id="candidate-fd04772a23c5",
    )
    _write_complete_spec(
        tmp_path,
        "079-incomplete-candidate",
        candidate_id="candidate-should-not-release",
        checked=False,
    )

    report = scan_released_work(tmp_path, now=NOW, run_id="123", commit="abc123")

    assert report.overall_status == STATUS_OK
    assert report.run_id == "123"
    assert report.commit == "abc123"
    assert [entry.candidate_id for entry in report.released_work] == [
        "candidate-fd04772a23c5"
    ]
    entry = report.released_work[0]
    assert entry.status == ENTRY_STATUS_RELEASED
    assert entry.spec_id == "078-money-gate-alignment-loop"
    assert entry.source_field == "selected_work_candidate"
    assert report.skipped_specs == (
        {
            "spec_id": "079-incomplete-candidate",
            "reason_ko": "체크박스 작업이 없거나 완료되지 않았습니다.",
        },
    )


def test_scan_released_work_does_not_parse_plain_candidate_mentions(tmp_path):
    spec_dir = tmp_path / "specs" / "080-plain-mention"
    spec_dir.mkdir(parents=True)
    (spec_dir / "tasks.md").write_text("- [x] 완료\n", encoding="utf-8")
    (spec_dir / "spec.md").write_text(
        "candidate-fd04772a23c5 후보를 논의했지만 완료 필드는 없습니다.\n",
        encoding="utf-8",
    )

    report = scan_released_work(tmp_path, now=NOW)

    assert report.overall_status == STATUS_EMPTY
    assert report.released_work == ()


def test_scan_released_work_supports_completion_field_aliases(tmp_path):
    _write_complete_spec(
        tmp_path,
        "081-completed-alias",
        candidate_id="candidate-alias",
        field="completed_candidate_id",
    )

    report = scan_released_work(tmp_path, now=NOW)

    assert report.overall_status == STATUS_OK
    assert report.released_work[0].candidate_id == "candidate-alias"
    assert report.released_work[0].source_field == "completed_candidate_id"

"""스펙 079 — 완료 후보 소비 장부.

완료된 Speckit 작업 산출물에서 명시적 후보 ID만 읽어, 자율 작업 실행 루프가 같은
후보를 다시 선택하지 않도록 하는 읽기 전용 장부를 만든다.

안전 경계: 브로커, 주문, 자본 배분, live 설정, whitelist/caps, 비밀값, 외부 유료
서비스를 건드리지 않는다. 이 모듈은 저장소 문서만 읽고 완료 후보 목록만 발행한다.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"

STATUS_OK = "OK"
STATUS_EMPTY = "EMPTY"
ENTRY_STATUS_RELEASED = "released"

SAFETY_INVARIANTS: tuple[str, ...] = (
    "no broker API call",
    "no orders",
    "no capital allocation",
    "no live strategy change",
    "no whitelist/caps change",
    "no secret read/write",
    "no external paid service",
    "released-work ledger only",
)

_SPEC_DIR_RE = re.compile(r"^\d{3}-.+")
_CHECKBOX_RE = re.compile(r"(?m)^\s*-\s*\[([ xX])\]\s+")
_UNFINISHED_CHECKBOX_RE = re.compile(r"(?m)^\s*-\s*\[\s\]\s+")
_CANDIDATE_FIELD_RE = re.compile(
    r"(?P<field>selected_work_candidate|released_candidate_id|completed_candidate_id)"
    r"[^A-Za-z0-9_-]+"
    r"(?P<candidate>candidate-[A-Za-z0-9_-]+)"
)
_TEXT_SUFFIXES = {".json", ".md", ".toml", ".txt", ".yaml", ".yml"}


@dataclass(frozen=True)
class ReleasedWorkEntry:
    """이미 완료되어 다시 선택하면 안 되는 작업 후보."""

    entry_id: str
    candidate_id: str
    status: str
    spec_id: str
    source_file: str
    source_field: str
    reason_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "candidate_id": self.candidate_id,
            "status": self.status,
            "spec_id": self.spec_id,
            "source_file": self.source_file,
            "source_field": self.source_field,
            "reason_ko": self.reason_ko,
        }


@dataclass(frozen=True)
class ReleasedWorkReport:
    """완료 후보 장부 보고."""

    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    released_work: tuple[ReleasedWorkEntry, ...]
    scanned_specs: tuple[str, ...]
    skipped_specs: tuple[dict[str, str], ...]
    safety_invariants: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "commit": self.commit,
            "timestamp_utc": self.timestamp_utc,
            "overall_status": self.overall_status,
            "released_work": [entry.to_dict() for entry in self.released_work],
            "scanned_specs": list(self.scanned_specs),
            "skipped_specs": list(self.skipped_specs),
            "safety_invariants": list(self.safety_invariants),
        }

    def as_markdown(self) -> str:
        lines = [
            f"# 완료 후보 소비 장부 (as of {self.timestamp_utc})",
            "",
            (
                "읽기 전용 보고입니다. 완료된 작업 후보를 다음 자율 작업 선택에서 "
                "제외하기 위한 장부입니다."
            ),
            "주문, 자본 배분, live 설정 변경, 코드 자동 수정, PR 자동 생성은 하지 않습니다.",
            "",
            "## 종합 판정",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| overall_status | {self.overall_status} |",
            f"| released_count | {len(self.released_work)} |",
            f"| scanned_specs | {len(self.scanned_specs)} |",
        ]

        lines += ["", "## 완료 후보", ""]
        if self.released_work:
            lines += [
                "| 후보 | 상태 | 스펙 | 근거 파일 | 근거 필드 |",
                "|------|------|------|-----------|-----------|",
            ]
            for entry in self.released_work:
                lines.append(
                    f"| {_table(entry.candidate_id)} | {entry.status} | "
                    f"{_table(entry.spec_id)} | {_table(entry.source_file)} | "
                    f"{_table(entry.source_field)} |"
                )
        else:
            lines.append("- 완료 처리할 후보가 없습니다.")

        if self.skipped_specs:
            lines += ["", "## 제외한 스펙", ""]
            lines += ["| 스펙 | 이유 |", "|------|------|"]
            for skipped in self.skipped_specs:
                lines.append(
                    f"| {_table(skipped.get('spec_id', '-'))} | "
                    f"{_table(skipped.get('reason_ko', '-'))} |"
                )

        lines += ["", "## 안전 경계", ""]
        for invariant in self.safety_invariants:
            lines.append(f"- {invariant}")
        lines += ["", "## 결정 JSON", "", "```json"]
        lines.append(json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        lines.append("```")
        return "\n".join(lines)


def scan_released_work(
    repo_root: Path,
    *,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> ReleasedWorkReport:
    """저장소의 완료 스펙에서 명시적 완료 후보 ID를 수집한다."""

    root = repo_root.resolve()
    specs_root = root / "specs"
    timestamp = _as_utc(now).isoformat().replace("+00:00", "Z")
    if not specs_root.exists():
        return ReleasedWorkReport(
            schema_version=SCHEMA_VERSION,
            run_id=run_id,
            commit=commit,
            timestamp_utc=timestamp,
            overall_status=STATUS_EMPTY,
            released_work=(),
            scanned_specs=(),
            skipped_specs=(
                {"spec_id": "specs", "reason_ko": "specs 디렉터리가 없습니다."},
            ),
            safety_invariants=SAFETY_INVARIANTS,
        )

    entries_by_key: dict[tuple[str, str], ReleasedWorkEntry] = {}
    scanned_specs: list[str] = []
    skipped_specs: list[dict[str, str]] = []

    for spec_dir in _iter_spec_dirs(specs_root):
        tasks_path = spec_dir / "tasks.md"
        try:
            tasks_text = tasks_path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            skipped_specs.append(
                {"spec_id": spec_dir.name, "reason_ko": "tasks.md를 읽을 수 없습니다."}
            )
            continue

        if not _tasks_complete(tasks_text):
            skipped_specs.append(
                {
                    "spec_id": spec_dir.name,
                    "reason_ko": "체크박스 작업이 없거나 완료되지 않았습니다.",
                }
            )
            continue

        scanned_specs.append(spec_dir.name)
        for source_file in _iter_candidate_source_files(spec_dir):
            try:
                text = source_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            except OSError:
                continue
            for field, candidate_id in _candidate_refs(text):
                rel_path = source_file.relative_to(root).as_posix()
                key = (candidate_id, spec_dir.name)
                if key in entries_by_key:
                    continue
                entries_by_key[key] = _entry(
                    candidate_id=candidate_id,
                    spec_id=spec_dir.name,
                    source_file=rel_path,
                    source_field=field,
                )

    released = tuple(
        sorted(entries_by_key.values(), key=lambda entry: (entry.candidate_id, entry.spec_id))
    )
    return ReleasedWorkReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=timestamp,
        overall_status=STATUS_OK if released else STATUS_EMPTY,
        released_work=released,
        scanned_specs=tuple(sorted(scanned_specs)),
        skipped_specs=tuple(skipped_specs),
        safety_invariants=SAFETY_INVARIANTS,
    )


def _as_utc(now: datetime) -> datetime:
    return now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)


def _table(value: object) -> str:
    return str(value if value is not None else "").replace("|", "/").replace("\n", " ")


def _iter_spec_dirs(specs_root: Path) -> Iterable[Path]:
    return sorted(
        path for path in specs_root.iterdir() if path.is_dir() and _SPEC_DIR_RE.match(path.name)
    )


def _tasks_complete(tasks_text: str) -> bool:
    return bool(_CHECKBOX_RE.search(tasks_text)) and not _UNFINISHED_CHECKBOX_RE.search(
        tasks_text
    )


def _iter_candidate_source_files(spec_dir: Path) -> Iterable[Path]:
    preferred = [
        spec_dir / "spec.md",
        spec_dir / "plan.md",
        spec_dir / "data-model.md",
        spec_dir / "quickstart.md",
    ]
    yielded: set[Path] = set()
    for path in preferred:
        if path.exists() and path.is_file():
            yielded.add(path)
            yield path
    contracts_dir = spec_dir / "contracts"
    if contracts_dir.exists():
        for path in sorted(contracts_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in _TEXT_SUFFIXES and path not in yielded:
                yielded.add(path)
                yield path


def _candidate_refs(text: str) -> Iterable[tuple[str, str]]:
    for match in _CANDIDATE_FIELD_RE.finditer(text):
        yield match.group("field"), match.group("candidate")


def _entry(
    *,
    candidate_id: str,
    spec_id: str,
    source_file: str,
    source_field: str,
) -> ReleasedWorkEntry:
    digest = hashlib.sha256(
        "|".join([candidate_id, spec_id, source_file, source_field]).encode("utf-8")
    ).hexdigest()[:12]
    return ReleasedWorkEntry(
        entry_id=f"released-{digest}",
        candidate_id=candidate_id,
        status=ENTRY_STATUS_RELEASED,
        spec_id=spec_id,
        source_file=source_file,
        source_field=source_field,
        reason_ko="완료된 Speckit 작업 산출물에서 명시적으로 완료 후보로 기록되었습니다.",
    )


__all__ = [
    "ENTRY_STATUS_RELEASED",
    "ReleasedWorkEntry",
    "ReleasedWorkReport",
    "SAFETY_INVARIANTS",
    "SCHEMA_VERSION",
    "STATUS_EMPTY",
    "STATUS_OK",
    "scan_released_work",
]

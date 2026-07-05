"""스펙 096 — 신호 다변화 엣지 no-live 실험 계약 probe.

워크플로 또는 로컬 검증이 sidecar 브랜치들을 `<key>.md` 파일로 모아두면,
순수 코어(`analytics.signal_diversification_edge_experiment`)로 실험 계약을 발행한다.

읽기 전용 — 주문 0건, 돈 0 이동, live 전략 변경 0건.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.released_work import scan_released_work
from auto_invest.analytics.signal_diversification_edge_experiment import (
    CONSUMED_SIDECARS,
    build_signal_diversification_edge_experiment,
)


def _parse_now(raw: str | None) -> datetime:
    if raw is None:
        return datetime.now(tz=UTC)
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _read_evidence(
    sidecar_dir: Path,
    *,
    repo_root: Path | None,
    now: datetime,
    run_id: str,
    commit: str,
) -> dict[str, str | None]:
    evidence: dict[str, str | None] = {}
    for key, _ref, _filename in CONSUMED_SIDECARS:
        path = sidecar_dir / f"{key}.md"
        try:
            evidence[key] = path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            evidence[key] = None
    if repo_root is not None:
        report = scan_released_work(repo_root, now=now, run_id=run_id, commit=commit)
        evidence["released-work"] = json.dumps(
            report.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
        )
    return evidence


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Signal diversification edge no-live experiment contract probe"
    )
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="Print consumed sidecars as key<TAB>branch<TAB>filename and exit.",
    )
    parser.add_argument(
        "--sidecar-dir",
        "--evidence-dir",
        dest="sidecar_dir",
        type=Path,
        default=Path("."),
        help="Directory containing <key>.md sidecar snapshots.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    parser.add_argument("--json-out", type=Path, help="Write JSON report to this path.")
    parser.add_argument("--summary-out", type=Path, help="Write Markdown report to this path.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        help="Repository root to scan for completed specs, overriding released-work sidecar.",
    )
    parser.add_argument("--now", help="Override current UTC time for deterministic tests.")
    parser.add_argument("--run-id", default="local", help="Workflow run id.")
    parser.add_argument("--commit", default="unknown", help="Source commit hash.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.manifest:
        for key, ref, filename in CONSUMED_SIDECARS:
            print(f"{key}\t{ref}\t{filename}")
        return 0

    now = _parse_now(args.now)
    report = build_signal_diversification_edge_experiment(
        _read_evidence(
            args.sidecar_dir,
            repo_root=args.repo_root,
            now=now,
            run_id=args.run_id,
            commit=args.commit,
        ),
        now=now,
        run_id=args.run_id,
        commit=args.commit,
    )
    json_text = json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
    markdown_text = report.as_markdown()

    if args.json_out:
        args.json_out.write_text(json_text + "\n", encoding="utf-8")
    if args.summary_out:
        args.summary_out.write_text(markdown_text + "\n", encoding="utf-8")

    print(json_text if args.json else markdown_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""스펙 051 — 자율 파이프라인 생존 감시 드라이버.

워크플로(`.github/workflows/pipeline-liveness.yml`)가 각 핵심 사이드카를
`git show origin/<branch>:<file> > <dir>/<key>.md` 로 내려받은 디렉터리를 읽어,
순수 코어(`analytics.pipeline_liveness`)로 생존을 판정하고 text/json 으로 찍는다.

읽기 전용 — 주문 0건, 돈 0 이동. 사용:
  uv run python scripts/pipeline_liveness_probe.py --sidecar-dir /tmp/sidecars [--json]
  # --strict : 종합 CRITICAL 이면 비정상 종료(로컬/수동 확인용; 워크플로는 발행 후 별도로 실패시킴)
  # --now ISO: 기준 시각 고정(테스트/재현용)
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.pipeline_liveness import (
    SidecarSpec,
    assess_liveness,
    default_specs,
)


def _read_observations(sidecar_dir: Path, specs: list[SidecarSpec]) -> dict[str, str | None]:
    """디렉터리에서 spec.key 별 `<key>.md` 원문을 읽는다(없으면 None)."""
    obs: dict[str, str | None] = {}
    for spec in specs:
        path = sidecar_dir / f"{spec.key}.md"
        try:
            obs[spec.key] = path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            obs[spec.key] = None
    return obs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--sidecar-dir",
        default=None,
        help="git show 로 내려받은 사이드카 원문(<key>.md)이 든 디렉터리.",
    )
    ap.add_argument("--json", action="store_true", help="JSON 출력(기본은 text).")
    ap.add_argument("--now", default=None, help="기준 시각 ISO-8601(테스트/재현용).")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="종합 CRITICAL 이면 비정상 종료(워크플로는 발행 후 별도로 실패시킴).",
    )
    ap.add_argument(
        "--manifest",
        action="store_true",
        help="레지스트리를 'key<TAB>branch<TAB>filename' 으로 출력하고 종료"
        "(워크플로가 사이드카를 git show 로 모을 때 단일 출처로 씀).",
    )
    args = ap.parse_args(argv)

    if args.manifest:
        for spec in default_specs():
            print(f"{spec.key}\t{spec.branch}\t{spec.filename}")
        return 0

    if not args.sidecar_dir:
        ap.error("--sidecar-dir 가 필요합니다(--manifest 가 아니면).")

    now = (
        datetime.fromisoformat(args.now.replace("Z", "+00:00"))
        if args.now
        else datetime.now(UTC)
    )

    specs = default_specs()
    obs = _read_observations(Path(args.sidecar_dir), specs)
    report = assess_liveness(specs, obs, now)

    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False))
    else:
        print(report.as_text())

    return report.exit_code if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())

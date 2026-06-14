"""스펙 053 — forward 토너먼트 리더보드 드라이버.

`rebalance-paper-forward.yml` A/B 토너먼트가 트랙마다 낸 스펙 035 forward-verdict JSON 을
모아, 순수 코어(`analytics.forward_tournament`)로 정직성 게이트 순위를 매겨 text/json 으로
찍는다. 읽기 전용 — 주문 0건, 돈 0 이동, 새 측정 0(발행된 판정 숫자 비교만).

두 입력 모드:
  --verdict-dir DIR   : 워크플로 모드 — DIR/verdict_<key>.json 6개를 읽는다(러너 /tmp).
  --from-sidecar FILE : 컨테이너 검증 모드 — 발행된 LAST_RUN.md 를 트랙 헤더별로 파싱
                        (git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md).

사용:
  uv run python scripts/forward_tournament_probe.py --verdict-dir /tmp [--json]
  uv run python scripts/forward_tournament_probe.py --from-sidecar /tmp/forward.md
  uv run python scripts/forward_tournament_probe.py --manifest   # 트랙 레지스트리 출력
  # --now ISO : 기준 시각 고정(테스트/재현용)
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.forward_tournament import (
    build_track_result,
    rank_tournament,
)

# 트랙 레지스트리(단일 출처) — rebalance-paper-forward.yml 의 6개 A/B 트랙과 일치.
#   key            : 워크플로의 /tmp/verdict_<key>.json 파일명 + 결정 JSON 키.
#   label          : 사람이 읽는 트랙 이름.
#   header_substr  : 발행된 사이드카에서 그 트랙 판정 블록을 찾는 헤더 부분 문자열(유일).
#   is_incumbent   : 라이브 검증 트랙(글로벌 추세 SPY·IEF·GLD)인가 — autoarm/사다리가
#                    global-trend-portfolio.toml 로 검증·배치하는 바로 그 트랙.
TRACKS: list[tuple[str, str, str, bool]] = [
    ("trend", "추세 필터 ON (드로다운 방어)", "추세 필터 ON", False),
    ("notrend", "추세 필터 OFF (대조군)", "추세 필터 OFF", False),
    ("rmbeta", "위험관리 베타 (스펙 042)", "위험관리 베타", False),
    ("multiasset", "멀티에셋 분산 추세 (스펙 043)", "멀티에셋 분산 추세", False),
    ("global", "글로벌 분산 추세 (라이브 검증, SPY·IEF·GLD)", "글로벌 분산 추세 (주식", True),
    ("wide", "글로벌 분산 추세 확대 (11 슬리브)", "글로벌 분산 추세 확대", False),
]


def _load_verdict_file(verdict_dir: Path, key: str) -> dict | None:
    """DIR/verdict_<key>.json 을 읽어 dict 로(없거나 깨졌으면 None)."""
    path = verdict_dir / f"verdict_{key}.json"
    try:
        raw = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def extract_json_after_header(text: str | None, header: str) -> dict | None:
    """마크다운에서 `header` 부분 문자열을 포함한 첫 줄 다음의 첫 ```json 펜스 블록을 파싱.

    money_path_probe.extract_json_after_header 와 동일 동작(헤더별 트랙 판정 추출).
    """
    if not text:
        return None
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if header in line:
            start = i
            break
    if start is None:
        return None
    in_block = False
    buf: list[str] = []
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if not in_block:
            if stripped.startswith("```"):
                in_block = True
            continue
        if stripped.startswith("```"):
            break
        buf.append(line)
    if not buf:
        return None
    try:
        obj = json.loads("\n".join(buf))
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def collect_verdicts(
    *,
    verdict_dir: Path | None,
    sidecar_text: str | None,
) -> dict[str, dict | None]:
    """트랙별 판정 JSON 을 모은다 — verdict_dir 우선, 없으면 사이드카 파싱."""
    out: dict[str, dict | None] = {}
    for key, _label, header, _inc in TRACKS:
        if verdict_dir is not None:
            out[key] = _load_verdict_file(verdict_dir, key)
        else:
            out[key] = extract_json_after_header(sidecar_text, header)
    return out


def build_leaderboard(
    *,
    verdict_dir: Path | None = None,
    sidecar_text: str | None = None,
    now: datetime,
):
    verdicts = collect_verdicts(verdict_dir=verdict_dir, sidecar_text=sidecar_text)
    tracks = [
        build_track_result(
            key=key,
            label=label,
            is_incumbent=inc,
            verdict_json=verdicts.get(key),
        )
        for key, label, _header, inc in TRACKS
    ]
    return rank_tournament(tracks, as_of_utc=now.isoformat())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--verdict-dir",
        default=None,
        help="워크플로 모드 — DIR/verdict_<key>.json 6개를 읽는다(러너 /tmp).",
    )
    ap.add_argument(
        "--from-sidecar",
        default=None,
        help="컨테이너 모드 — 발행된 forward 사이드카 LAST_RUN.md 파일을 헤더별 파싱.",
    )
    ap.add_argument("--json", action="store_true", help="JSON 출력(기본은 text).")
    ap.add_argument("--now", default=None, help="기준 시각 ISO-8601(테스트/재현용).")
    ap.add_argument(
        "--manifest",
        action="store_true",
        help="트랙 레지스트리를 'key<TAB>label<TAB>incumbent' 로 출력하고 종료.",
    )
    args = ap.parse_args(argv)

    if args.manifest:
        for key, label, _header, inc in TRACKS:
            print(f"{key}\t{label}\t{inc}")
        return 0

    if not args.verdict_dir and not args.from_sidecar:
        ap.error("--verdict-dir 또는 --from-sidecar 가 필요합니다(--manifest 가 아니면).")

    now = (
        datetime.fromisoformat(args.now.replace("Z", "+00:00"))
        if args.now
        else datetime.now(UTC)
    )

    sidecar_text = None
    verdict_dir = None
    if args.verdict_dir:
        verdict_dir = Path(args.verdict_dir)
    elif args.from_sidecar:
        try:
            sidecar_text = Path(args.from_sidecar).read_text(encoding="utf-8")
        except (FileNotFoundError, OSError) as exc:
            ap.error(f"--from-sidecar 읽기 실패: {exc}")

    board = build_leaderboard(
        verdict_dir=verdict_dir, sidecar_text=sidecar_text, now=now
    )

    if args.json:
        print(json.dumps(board.to_json_dict(), ensure_ascii=False))
    else:
        print(board.as_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

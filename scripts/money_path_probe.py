"""스펙 052 — 첫-자본까지의 길(money-path) 종합 드라이버.

워크플로(`.github/workflows/money-path.yml`)가 관련 사이드카를
`git show origin/<branch>:LAST_RUN.md > <dir>/<key>.md` 로 내려받은 디렉터리를 읽어,
라벨된 JSON 블록을 뽑아 순수 코어(`analytics.money_path`)로 종합하고 text/json 으로 찍는다.

읽기 전용 — 주문 0건, 돈 0 이동. 사용:
  uv run python scripts/money_path_probe.py --sidecar-dir /tmp/sidecars [--json]
  # --now ISO : 기준 시각 고정(테스트/재현용)
  # --manifest: 소비할 사이드카 레지스트리를 'key<TAB>branch<TAB>filename' 으로 출력
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.money_path import assess_money_path

# 이 프로브가 소비하는 사이드카(워크플로가 git show 로 모은다).
# (key, branch, filename) — pipeline_liveness 의 --manifest 와 같은 형식.
CONSUMED_SIDECARS: list[tuple[str, str, str]] = [
    ("edge-autoarm", "automation/edge-autoarm-last-run", "LAST_RUN.md"),
    ("rebalance-live-canary", "automation/rebalance-live-canary-last-run", "LAST_RUN.md"),
    ("promote-readiness", "automation/promote-readiness-last-run", "LAST_RUN.md"),
    # 자기 직전 사이드카 — ETA 실측 누적 속도용(첫 실행엔 없음 → nominal 로 폴백).
    ("money-path", "automation/money-path-last-run", "LAST_RUN.md"),
]

_ARMED_RE = re.compile(r"armed\s*\(무장 여부\)\s*\|\s*(true|false)", re.IGNORECASE)


def _read(sidecar_dir: Path, key: str) -> str | None:
    try:
        return (sidecar_dir / f"{key}.md").read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None


def extract_json_after_header(text: str | None, header: str) -> dict | None:
    """마크다운에서 `header` 줄 다음에 오는 첫 ```json 펜스 블록을 파싱.

    header 는 '## 결정 JSON' 처럼 줄 시작 토큰의 일부(부분 일치). 없으면 None.
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
    # header 이후 첫 ```json … ``` 블록.
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


def parse_canary_armed(text: str | None) -> bool | None:
    """라이브 캐너리 사이드카에서 `armed (무장 여부)` 표 행을 읽는다(없으면 None)."""
    if not text:
        return None
    m = _ARMED_RE.search(text)
    if not m:
        return None
    return m.group(1).lower() == "true"


def parse_prior(text: str | None) -> dict | None:
    """직전 money-path 사이드카에서 ETA 실측용 {as_of_utc, n_obs} 를 읽는다."""
    if not text:
        return None
    decision = extract_json_after_header(text, "결정 JSON") or extract_json_after_header(
        text, "money-path"
    )
    # 직전 보고의 결정 JSON 안에 eta.obs_remaining + 게이트 현재값이 있지만, ETA 실측에
    # 필요한 건 (그때의 as_of_utc, 그때의 n_obs). n_obs 는 결정 JSON 의 게이트에서 못
    # 꺼내므로, 직전 보고가 별도로 박아 둔 prior 힌트(as_of_utc + forward_n_obs)를 쓴다.
    if not decision:
        return None
    n_obs = decision.get("forward_n_obs")
    as_of = decision.get("as_of_utc")
    if n_obs is None or as_of is None:
        return None
    return {"as_of_utc": as_of, "n_obs": n_obs}


def build_report(sidecar_dir: Path, now: datetime):
    edge = _read(sidecar_dir, "edge-autoarm")
    canary = _read(sidecar_dir, "rebalance-live-canary")
    promote = _read(sidecar_dir, "promote-readiness")
    prior_raw = _read(sidecar_dir, "money-path")

    ladder = extract_json_after_header(edge, "결정 JSON")
    forward_verdict = extract_json_after_header(edge, "forward 판정 JSON")
    live_growth = extract_json_after_header(edge, "라이브 실적 JSON")
    promote_ready = extract_json_after_header(
        promote, "promote-check"
    ) or extract_json_after_header(promote, "JSON")
    canary_armed = parse_canary_armed(canary)
    prior = parse_prior(prior_raw)

    report = assess_money_path(
        ladder=ladder,
        forward_verdict=forward_verdict,
        live_growth=live_growth,
        canary_armed=canary_armed,
        promote_ready=promote_ready,
        prior=prior,
        now=now,
    )
    # 다음 실행의 ETA 실측을 위해, 이번 forward n_obs 를 결정 JSON 에 prior 힌트로 싣는다.
    forward_n_obs = (forward_verdict or {}).get("n_obs")
    return report, forward_n_obs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--sidecar-dir", default=None, help="git show 로 모은 사이드카(<key>.md) 디렉터리."
    )
    ap.add_argument("--json", action="store_true", help="JSON 출력(기본은 text).")
    ap.add_argument("--now", default=None, help="기준 시각 ISO-8601(테스트/재현용).")
    ap.add_argument(
        "--manifest",
        action="store_true",
        help="소비할 사이드카 레지스트리를 'key<TAB>branch<TAB>filename' 으로 출력하고 종료.",
    )
    args = ap.parse_args(argv)

    if args.manifest:
        for key, branch, filename in CONSUMED_SIDECARS:
            print(f"{key}\t{branch}\t{filename}")
        return 0

    if not args.sidecar_dir:
        ap.error("--sidecar-dir 가 필요합니다(--manifest 가 아니면).")

    now = (
        datetime.fromisoformat(args.now.replace("Z", "+00:00"))
        if args.now
        else datetime.now(UTC)
    )

    report, forward_n_obs = build_report(Path(args.sidecar_dir), now)

    if args.json:
        out = report.to_dict()
        # 다음 실행 ETA 실측용 prior 힌트(이 보고의 forward 관측 수 + 시각).
        out["forward_n_obs"] = forward_n_obs
        out["as_of_utc"] = report.as_of_utc
        print(json.dumps(out, ensure_ascii=False))
    else:
        print(report.as_text())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

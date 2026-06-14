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

# 전략 지문 비교 대상(스펙 050/049) — forward-edge-autoarm.yml 의 autoarm-decide 가
# 비교하는 바로 그 두 설정(--live-portfolio / --validated-portfolio 기본값과 동일).
# 사다리 게이트와 같은 두 파일을 읽어야 비교가 정확하다.
DEFAULT_LIVE_PORTFOLIO = "deploy/canary-live-portfolio.toml"
DEFAULT_VALIDATED_PORTFOLIO = "deploy/global-trend-portfolio.toml"

# strategy_fingerprint(autoarm) 튜플 위치 ↔ 사람이 읽는 항목 이름(같은 순서 유지 필수).
_FP_FIELDS = (
    "universe",
    "weight_scheme",
    "rebalance_mode",
    "top_n",
    "top_pct",
    "lookback_bars",
    "momentum_period",
    "weights",
    "trend_filter",
)

_ARMED_RE = re.compile(r"armed\s*\(무장 여부\)\s*\|\s*(true|false)", re.IGNORECASE)


def _load_portfolio_cfg(path: Path):
    """TOML 의 `[portfolio]` 테이블을 PortfolioRebalanceConfig 로 — 지문 계산용(읽기 전용).

    지문은 caps/whitelist/env 와 무관하므로 `[portfolio]` 만 검증한다(cli 의
    _load_portfolio_for_backtest 와 지문 관련 동작 동일).
    """
    import tomllib

    from auto_invest.config.rules import PortfolioRebalanceConfig

    raw = tomllib.loads(path.read_bytes().decode("utf-8"))
    if "portfolio" not in raw:
        raise ValueError(f"{path}: [portfolio] 섹션 없음")
    return PortfolioRebalanceConfig.model_validate(raw["portfolio"])


def compute_fingerprint_status(live_path: Path, validated_path: Path) -> dict:
    """라이브 배포 설정 vs 전진 검증 설정의 전략 지문 정합(사다리 게이트와 동일 비교).

    반환 {'match': bool|None, 'diverged': [field...], 'live_path', 'validated_path'}.
    둘 중 하나라도 못 읽으면 match=None(N/A — 거짓 경보 안 냄).
    """
    from pydantic import ValidationError

    from auto_invest.portfolio.autoarm import strategy_fingerprint

    out = {
        "match": None,
        "diverged": [],
        "live_path": str(live_path),
        "validated_path": str(validated_path),
    }
    try:
        live_fp = strategy_fingerprint(_load_portfolio_cfg(live_path))
        val_fp = strategy_fingerprint(_load_portfolio_cfg(validated_path))
    except (OSError, ValueError, ValidationError) as exc:
        out["error"] = str(exc)
        return out
    # match 는 튜플 전체 비교(정확). diverged 항목 이름은 보조 표시 — 길이 불일치가
    # 프로브를 죽이지 않게 strict=False(미래 지문 변경에도 안전).
    out["match"] = live_fp == val_fp
    out["diverged"] = [
        name
        for name, lv, vv in zip(_FP_FIELDS, live_fp, val_fp, strict=False)
        if lv != vv
    ]
    return out


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


def build_report(
    sidecar_dir: Path,
    now: datetime,
    live_portfolio: Path | None = None,
    validated_portfolio: Path | None = None,
):
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

    fingerprint = None
    if live_portfolio is not None and validated_portfolio is not None:
        fingerprint = compute_fingerprint_status(live_portfolio, validated_portfolio)

    report = assess_money_path(
        ladder=ladder,
        forward_verdict=forward_verdict,
        live_growth=live_growth,
        canary_armed=canary_armed,
        promote_ready=promote_ready,
        prior=prior,
        fingerprint=fingerprint,
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
        "--live-portfolio",
        default=DEFAULT_LIVE_PORTFOLIO,
        help="라이브 캐너리가 실제 거래할 설정(전략 지문 비교 대상). 사다리 게이트와 동일.",
    )
    ap.add_argument(
        "--validated-portfolio",
        default=DEFAULT_VALIDATED_PORTFOLIO,
        help="전진 페이퍼에서 검증한 설정(전략 지문 비교 대상). 사다리 게이트와 동일.",
    )
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

    live_pf = Path(args.live_portfolio) if args.live_portfolio else None
    val_pf = Path(args.validated_portfolio) if args.validated_portfolio else None
    report, forward_n_obs = build_report(
        Path(args.sidecar_dir), now, live_portfolio=live_pf, validated_portfolio=val_pf
    )

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

"""NAV 스냅샷의 자본 베이시스 회귀 (2026-06-11).

배경: 페이퍼 트랙의 nav-snapshot 이 --capital 없이 호출되면 장부 현금이 0 으로
찍혀 NAV = 포지션 평가액만 남는다. 그러면 매수/매도(자금 흐름)가 NAV 점프로
나타나 forward 수익률·샤프·낙폭이 전부 오염되고, 자동 무장 게이트(스펙 049)가
쓰레기 통계로 EDGE 를 판정한다 (실측: 추세 ON 트랙 '총수익 463%' = 흐름 오염).

이 테스트는 forward/라이브 캐너리 워크플로의 모든 nav-snapshot 호출이 자본
베이시스를 넘기는 불변식을 CI 에서 못박는다. 워크플로는 셸 변수로 호출을
조립하므로 YAML 파싱 대신 텍스트 불변식을 검사한다.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FORWARD = _REPO_ROOT / ".github" / "workflows" / "rebalance-paper-forward.yml"
_LIVE = _REPO_ROOT / ".github" / "workflows" / "rebalance-live-canary.yml"
_OBSERVE_HELPER = _REPO_ROOT / "deploy" / "observe-on-instance.sh"

# forward 워크플로의 페이퍼 트랙 수(6 트랙 + globalfixed 재지정 후보 = 7).
_FORWARD_TRACKS = 7


def _calls(path: Path) -> list[str]:
    joined = re.sub(r"\\\s*\n\s*", " ", path.read_text(encoding="utf-8"))
    return [
        ln
        for ln in joined.splitlines()
        if "nav-snapshot" in ln and "uv run" in ln
    ]


def test_forward_paper_nav_snapshots_pass_capital():
    workflow = _FORWARD.read_text(encoding="utf-8")
    for track in (
        "trend",
        "notrend",
        "rmbeta",
        "multiasset",
        "global",
        "globalfixed",
        "wide",
    ):
        assert f"observe paper-track-run {track} " in workflow

    helper = re.sub(
        r"\\\s*\n\s*",
        " ",
        _OBSERVE_HELPER.read_text(encoding="utf-8"),
    )
    assert "nav-snapshot" in helper
    assert '--capital "${capital}"' in helper, (
        "nav-snapshot 이 --capital 없이 호출됨 — 장부 현금 0 회귀로 자금 흐름이"
        " 수익률로 오인된다(판정 오염)."
    )


def test_live_canary_nav_snapshot_passes_capital():
    calls = _calls(_LIVE)
    assert len(calls) == 1, (
        f"라이브 캐너리 nav-snapshot 호출이 {len(calls)}개 — 측정 스텝 구조가 바뀜."
    )
    assert "--capital ${CAP}" in calls[0], (
        "라이브 측정 nav-snapshot 이 --capital 없이 호출됨 — 페이퍼 forward 와 측정"
        f" 기준이 어긋난다: {calls[0]}"
    )

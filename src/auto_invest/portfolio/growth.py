"""Spec 029 슬라이스 3 — 포트폴리오 순자산(NAV) 성장 추적 (순수·결정론·읽기 전용).

성과 엔진(스펙 011)의 자산곡선은 실현손익만 누적한다(과거 시세 없이 미실현 시점 평가
불가). 슬라이스 1이 PORTFOLIO_NAV_SNAPSHOT 감사 이벤트로 미실현 포함 순자산을 시점별로
남기기 시작했으므로, 이 모듈은 그 시계열을 이어 붙여 실현+미실현을 합친 진짜 시가평가
(mark-to-market) 자산곡선과 성장 지표를 계산한다.

설계 원칙 (스펙 011/029 슬라이스 1과 동일):
  - 순수 함수. audit_log 를 SELECT 만 한다(읽기 전용). DB 에 어떤 row 도 안 쓴다.
  - 자산곡선 지표는 스펙 008 backtest/metrics.py 를 재사용 — 백테스트·라이브가 한 잣대
    (헌법 X.2). total_return_pct·max_drawdown_pct 를 그대로 호출한다.
  - 스냅샷 2개 미만이면 추세 None(측정 불가). 순자산에 0 이하가 섞이면 낙폭/CAGR 은
    None 으로 강등(곡선이 양수일 때만 계산).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from auto_invest.backtest.metrics import max_drawdown_pct, total_return_pct


@dataclass(frozen=True)
class NavPoint:
    """자산곡선의 한 점 — 한 NAV 스냅샷의 (시각, 순자산).

    `capital_basis_usd` 는 스냅샷이 찍힐 때 쓴 측정 기준 자본(현금 = 자본 + 순현금
    흐름). None 이면 현금 미포함 레거시 측정 — 기준이 다른 점을 한 곡선에 섞으면
    자금 흐름이 수익률로 오인되므로, 판정은 `consistent_basis_suffix` 로 거른다.
    """

    at_utc: str
    nav_usd: Decimal
    capital_basis_usd: str | None = None
    measurement_contract_id: str | None = None


@dataclass(frozen=True)
class GrowthReport:
    """미실현 포함 시가평가 자산곡선의 성장 지표."""

    mode: str  # "paper" | "live"
    snapshot_count: int
    first_at_utc: str | None
    last_at_utc: str | None
    starting_nav_usd: Decimal | None
    current_nav_usd: Decimal | None
    absolute_change_usd: Decimal | None
    total_return_pct: Decimal | None
    max_drawdown_pct: Decimal | None
    period_days: Decimal | None
    cagr_pct: Decimal | None  # 연환산 복리 수익률

    SCHEMA_VERSION = "1.0"

    def to_json_dict(self) -> dict:
        def _s(v: Decimal | None) -> str | None:
            return None if v is None else str(v)

        return {
            "schema_version": self.SCHEMA_VERSION,
            "mode": self.mode,
            "snapshot_count": self.snapshot_count,
            "first_at_utc": self.first_at_utc,
            "last_at_utc": self.last_at_utc,
            "starting_nav_usd": _s(self.starting_nav_usd),
            "current_nav_usd": _s(self.current_nav_usd),
            "absolute_change_usd": _s(self.absolute_change_usd),
            "total_return_pct": _s(self.total_return_pct),
            "max_drawdown_pct": _s(self.max_drawdown_pct),
            "period_days": _s(self.period_days),
            "cagr_pct": _s(self.cagr_pct),
        }


def _parse_iso(ts: str) -> datetime:
    """audit_log.ts_utc(밀리초 Z) → datetime. Z 를 +00:00 으로 바꿔 파싱."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def read_nav_points(
    conn: sqlite3.Connection,
    *,
    mode: str,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[NavPoint]:
    """PORTFOLIO_NAV_SNAPSHOT 행을 모드별·기간별로 읽어 시간순 점열로 (FR-14).

    읽기 전용(SELECT만). 스냅샷 payload 의 total_nav_usd(미실현 포함 순자산)와
    computed_at_utc(평가 시각)를 점으로 쓴다. 같은 모드의 스냅샷만 모은다.
    """
    if mode not in ("paper", "live"):
        raise ValueError(f"mode must be 'paper' or 'live', got {mode!r}")
    rows = conn.execute(
        "SELECT ts_utc, payload_json FROM audit_log "
        "WHERE event_type = 'PORTFOLIO_NAV_SNAPSHOT' ORDER BY seq"
    ).fetchall()
    points: list[NavPoint] = []
    for row in rows:
        p = json.loads(row["payload_json"])
        if p.get("mode") != mode:
            continue
        at = p.get("computed_at_utc") or row["ts_utc"]
        if since is not None and _parse_iso(at) < since:
            continue
        if until is not None and _parse_iso(at) >= until:
            continue
        points.append(
            NavPoint(
                at_utc=at,
                nav_usd=Decimal(str(p["total_nav_usd"])),
                capital_basis_usd=p.get("capital_basis_usd"),
                measurement_contract_id=p.get("measurement_contract_id"),
            )
        )
    return points


def latest_measurement_contract_suffix(points: list[NavPoint]) -> list[NavPoint]:
    """Return only the latest contiguous performance-definition contract."""
    if not points or points[-1].measurement_contract_id is None:
        return points
    contract_id = points[-1].measurement_contract_id
    start = len(points)
    for index in range(len(points) - 1, -1, -1):
        if points[index].measurement_contract_id != contract_id:
            break
        start = index
    return points[start:]


def consistent_basis_suffix(points: list[NavPoint]) -> list[NavPoint]:
    """측정 기준(자본 베이시스)이 같은 최신 연속 구간(꼬리)만 남긴다.

    NAV 측정 기준이 바뀌면(현금 미포함 레거시 → 자본 베이시스 포함, 또는 자본 변경)
    곡선에 손익이 아닌 가짜 점프(자금 흐름)가 생겨 수익률·샤프·낙폭이 전부 오염된다.
    forward 판정은 가장 최근 기준으로 찍힌 연속 구간만 봐야 한다.

    규칙 (결정론):
      - 마지막 점에 베이시스가 없으면(레거시 페이퍼 / 브로커 NAV 라이브) 전체를 그대로
        반환 — 과거 동작 보존(라이브 트랙은 브로커 현금이 이미 포함돼 오염이 없다).
      - 있으면 같은 베이시스가 연속되는 최장 꼬리만 반환. 그 앞의 레거시/다른 자본
        구간은 제외된다(append-only 감사 행 자체는 그대로 — 읽기 필터일 뿐).
    """
    if not points or points[-1].capital_basis_usd is None:
        return points
    basis = points[-1].capital_basis_usd
    start = len(points)
    for i in range(len(points) - 1, -1, -1):
        if points[i].capital_basis_usd != basis:
            break
        start = i
    return points[start:]


def stitch_basis_segments(points: list[NavPoint]) -> list[NavPoint]:
    """자본 베이시스 경계(자금 흐름)를 건너뛰고 같은 전략의 일별 수익률을 사슬로 이어
    연속 합성 자산곡선을 만든다 — 시간가중수익률(TWR, GIPS 표준)의 결정론 구현.

    `consistent_basis_suffix` 는 베이시스가 바뀌면 그 앞을 통째로 버려(최신 구간만) 같은
    전략인데도 forward 관측이 리셋된다. 그러나 수익률은 자본 규모와 무관하다(1% 는 $500
    이든 $5,000 이든 1%) — 구간 *내부* 수익률만 사슬로 이으면 자금 흐름은 빠지고 전략의
    전체 track record 가 보존된다. 깨끗한 1일 수익률(같은 베이시스 + 양수 NAV)만 복리하고,
    베이시스 경계의 단일 전이(자금 흐름으로 오염)만 버린다.

    한 forward 트랙의 스냅샷은 전략이 고정(그 트랙 설정)이므로, 베이시스 변경은 자본 조정
    이지 전략 변경이 아니다 → 구간을 가로질러 수익률을 잇는 것이 정당하다(전문 성과측정의
    표준). 마지막 점의 베이시스가 None(레거시/라이브 브로커 NAV)이면 오염이 없으므로 원본을
    그대로 반환(과거 동작·라이브 트랙 보존). 깨끗한 수익률이 하나도 없으면 마지막 점 1개만.

    반환: 합성 NAV 점열 — 날짜는 보존된 실제 점의 날짜, nav 는 첫 유효 점에서 출발해 구간
    내부 수익률만 복리한 연속값. suffix 와 달리 같은 전략의 자본 변경이 시계를 리셋하지 않는다.
    """
    if not points or points[-1].capital_basis_usd is None:
        return points
    out: list[NavPoint] = []
    synth: Decimal | None = None
    for i in range(1, len(points)):
        prev, cur = points[i - 1], points[i]
        # 깨끗한 1일 수익률: 같은 *알려진* 베이시스 + 양수 NAV. None(레거시 현금 미포함
        # 포지션-only)은 측정 정의가 달라 그들끼리도 잇지 않는다(자기들 수익률도 왜곡).
        # 베이시스가 바뀌거나(자금 흐름 경계) 비양수 NAV 면 그 전이를 폐기한다.
        if (
            prev.capital_basis_usd is None
            or cur.capital_basis_usd != prev.capital_basis_usd
            or prev.nav_usd <= 0
            or cur.nav_usd <= 0
        ):
            continue
        if synth is None:
            synth = prev.nav_usd
            out.append(
                NavPoint(
                    at_utc=prev.at_utc,
                    nav_usd=synth,
                    capital_basis_usd=prev.capital_basis_usd,
                    measurement_contract_id=prev.measurement_contract_id,
                )
            )
        synth = synth * (cur.nav_usd / prev.nav_usd)
        out.append(
            NavPoint(
                at_utc=cur.at_utc,
                nav_usd=synth,
                capital_basis_usd=cur.capital_basis_usd,
                measurement_contract_id=cur.measurement_contract_id,
            )
        )
    return out if out else [points[-1]]


def compute_growth(points: list[NavPoint], *, mode: str) -> GrowthReport:
    """점열에서 시가평가 자산곡선 성장 지표를 결정론적으로 계산한다 (FR-15, FR-16).

    스냅샷 2개 미만이면 추세 None(측정 불가). 총수익률·최대낙폭은 스펙 008 metrics
    함수를 재사용한다(단일 잣대). 곡선에 0 이하가 섞이면 낙폭/CAGR 은 None(metrics 가
    양수 곡선만 받는 계약과 동일). CAGR 은 기간 ≥ 1일일 때만, 시작·현재가 양수일 때만.
    """
    n = len(points)
    if n == 0:
        return GrowthReport(
            mode=mode, snapshot_count=0, first_at_utc=None, last_at_utc=None,
            starting_nav_usd=None, current_nav_usd=None, absolute_change_usd=None,
            total_return_pct=None, max_drawdown_pct=None, period_days=None,
            cagr_pct=None,
        )

    start = points[0].nav_usd
    end = points[-1].nav_usd
    if n < 2:
        # 점 1개 — 현재 순자산은 알지만 추세는 측정 불가.
        return GrowthReport(
            mode=mode, snapshot_count=1, first_at_utc=points[0].at_utc,
            last_at_utc=points[-1].at_utc, starting_nav_usd=start,
            current_nav_usd=end, absolute_change_usd=Decimal("0"),
            total_return_pct=None, max_drawdown_pct=None, period_days=None,
            cagr_pct=None,
        )

    curve = [pt.nav_usd for pt in points]
    all_positive = all(v > 0 for v in curve)

    tot_return = total_return_pct(curve) if start > 0 else None
    drawdown = max_drawdown_pct(curve) if all_positive else None

    # 기간(일수) — 첫→마지막 평가 시각 차이.
    delta = _parse_iso(points[-1].at_utc) - _parse_iso(points[0].at_utc)
    period_days = Decimal(str(delta.total_seconds() / 86400.0))

    cagr: Decimal | None = None
    if all_positive and period_days > 0 and start > 0:
        years = float(period_days) / 365.0
        if years > 0:
            ratio = float(end) / float(start)
            cagr_val = (ratio ** (1.0 / years) - 1.0) * 100.0
            cagr = Decimal(str(round(cagr_val, 6)))

    return GrowthReport(
        mode=mode,
        snapshot_count=n,
        first_at_utc=points[0].at_utc,
        last_at_utc=points[-1].at_utc,
        starting_nav_usd=start,
        current_nav_usd=end,
        absolute_change_usd=end - start,
        total_return_pct=tot_return,
        max_drawdown_pct=drawdown,
        period_days=period_days,
        cagr_pct=cagr,
    )


def _money(v: Decimal | None) -> str:
    return "N/A" if v is None else f"${v:,.2f}"


def _pct(v: Decimal | None) -> str:
    return "N/A" if v is None else f"{v:+.2f}%"


def render_text(report: GrowthReport) -> str:
    """사람용 표. CLI text 모드 출력."""
    lines: list[str] = []
    lines.append("=" * 56)
    lines.append(f"포트폴리오 순자산 성장 추세 (모드: {report.mode})")
    lines.append("=" * 56)
    if report.snapshot_count == 0:
        lines.append("(NAV 스냅샷 없음 — `auto-invest portfolio --snapshot` 으로 기록하세요)")
        return "\n".join(lines)
    lines.append(f"스냅샷 수   : {report.snapshot_count}")
    lines.append(f"기간        : {report.first_at_utc} → {report.last_at_utc}")
    if report.period_days is not None:
        lines.append(f"            ({report.period_days.quantize(Decimal('0.1'))}일)")
    lines.append(f"시작 순자산 : {_money(report.starting_nav_usd)}")
    lines.append(f"현재 순자산 : {_money(report.current_nav_usd)}")
    lines.append(f"증감        : {_money(report.absolute_change_usd)}")
    lines.append(f"총수익률    : {_pct(report.total_return_pct)}")
    lines.append(f"최대낙폭    : {_pct(report.max_drawdown_pct)}")
    lines.append(f"연환산(CAGR): {_pct(report.cagr_pct)}")
    if report.snapshot_count < 2:
        lines.append("")
        lines.append("(스냅샷 2개 미만 — 추세 측정 불가)")
    return "\n".join(lines)

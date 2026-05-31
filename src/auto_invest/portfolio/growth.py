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
    """자산곡선의 한 점 — 한 NAV 스냅샷의 (시각, 순자산)."""

    at_utc: str
    nav_usd: Decimal


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
        points.append(NavPoint(at_utc=at, nav_usd=Decimal(str(p["total_nav_usd"]))))
    return points


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

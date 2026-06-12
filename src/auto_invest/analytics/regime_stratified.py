"""레짐별 성과 층화 분석 (연구 전용 — 거시 레짐 타임라인의 소비자).

공개 데이터 채널이 발행한 거시 레짐 타임라인(regime_timeline.csv)과 임의의
NAV/수익률 시계열(백테스트 산출물·forward NAV 스냅숏 등)을 결합해 "이 전략은
어떤 거시 레짐에서 벌고 어디서 잃는가"를 잰다.

전망적 결합(look-ahead 차단이 본질):
  * 타임라인의 d일 라벨은 d일 장 마감 시점 정보다(일간 지표는 그날 종가,
    월간 지표는 발표 지연 반영). 그 라벨에 d일 수익률을 붙이면 "마감을 보고
    마감 전에 포지션을 잡은" 미래 누출이 된다.
  * 그래서 여기서는 d일 라벨에 **d+1 거래일 수익률**을 붙인다 — "어제 마감
    레짐이 X였을 때 오늘 하루 성과". 백테스트가 신호를 다음 날 적용하는
    관행과 같은 규율이다.

라이브 매매 신호 아님 — strategy/·broker/ 와 양방향 무접촉(불변식 테스트).
모든 계산은 결정론적 Decimal.
"""

from __future__ import annotations

import bisect
import csv
import io
from decimal import Decimal
from typing import Any

ANNUALIZATION_DAYS = 252
MIN_OBS_FOR_RATIOS = 20  # 이보다 적으면 샤프/연환산은 통계적으로 무의미 → 생략


def load_timeline_csv(text: str) -> dict[str, str]:
    """regime_timeline.csv → {날짜: 라벨}."""
    stripped = text.strip()
    if not stripped:
        raise ValueError("타임라인 CSV 가 비어 있음")
    reader = csv.DictReader(io.StringIO(stripped))
    fields = reader.fieldnames or []
    if "date" not in fields or "label" not in fields:
        raise ValueError(f"타임라인 헤더에 date/label 없음: {reader.fieldnames!r}")
    return {row["date"]: row["label"] for row in reader if row.get("date")}


def load_value_series_csv(text: str) -> list[tuple[str, Decimal]]:
    """date,value CSV(NAV 또는 일일 수익률) — 결측 행은 건너뜀, 날짜 오름차순."""
    stripped = text.strip()
    if not stripped:
        raise ValueError("시계열 CSV 가 비어 있음")
    reader = csv.reader(io.StringIO(stripped))
    header = next(reader)
    if [h.strip().lower() for h in header[:2]] != ["date", "value"]:
        raise ValueError(f"시계열 CSV 헤더가 예상과 다름: {header!r}")
    out = []
    for row in reader:
        if not row or not row[0].strip() or len(row) < 2 or not row[1].strip():
            continue
        out.append((row[0].strip(), Decimal(row[1].strip())))
    out.sort(key=lambda p: p[0])
    return out


def nav_to_returns(nav: list[tuple[str, Decimal]]) -> list[tuple[str, Decimal]]:
    """NAV 시계열 → 단순 일일 수익률(소수, 0.01 = 1%). 0/음수 NAV 는 건너뜀."""
    out = []
    for (_, prev), (d, cur) in zip(nav, nav[1:], strict=False):
        if prev > 0 and cur > 0:
            out.append((d, cur / prev - 1))
    return out


def _bucket_stats(returns: list[Decimal]) -> dict[str, Any]:
    n = len(returns)
    stats: dict[str, Any] = {"n_days": n}
    if n == 0:
        return stats
    equity = Decimal("1")
    peak = Decimal("1")
    max_dd = Decimal("0")
    for r in returns:
        equity *= 1 + r
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)
    total = equity - 1
    mean = sum(returns) / n
    stats.update(
        total_return_pct=f"{total * 100:.2f}",
        mean_daily_pct=f"{mean * 100:.4f}",
        worst_day_pct=f"{min(returns) * 100:.2f}",
        best_day_pct=f"{max(returns) * 100:.2f}",
        max_drawdown_pct=f"{max_dd * 100:.2f}",
    )
    if n >= MIN_OBS_FOR_RATIOS and equity > 0:
        var = sum((r - mean) ** 2 for r in returns) / (n - 1)
        std = var.sqrt()
        ann_factor = Decimal(ANNUALIZATION_DAYS)
        stats["ann_vol_pct"] = f"{std * ann_factor.sqrt() * 100:.2f}"
        stats["ann_return_pct"] = (
            f"{((equity.ln() * ann_factor / n).exp() - 1) * 100:.2f}"
        )
        if std > 0:
            stats["sharpe"] = f"{mean / std * ann_factor.sqrt():.2f}"
    else:
        stats["note"] = f"관측 {n}개 < {MIN_OBS_FOR_RATIOS}개 — 연환산/샤프 생략"
    return stats


def stratify_returns(
    returns: list[tuple[str, Decimal]], timeline: dict[str, str]
) -> dict[str, Any]:
    """d일 라벨 ↔ d+1 거래일 수익률 전망적 결합 → 라벨별 성과.

    수익률 날짜 d 에 붙는 라벨은 "타임라인에서 d *직전* 거래일의 라벨"이다.
    타임라인에 직전 거래일이 없는 수익률은 UNLABELED 로 정직하게 분리한다
    (조용히 버리면 표본 편향이 보이지 않는다).
    """
    tl_dates = sorted(timeline)
    buckets: dict[str, list[Decimal]] = {}
    for d, r in returns:
        idx = bisect.bisect_left(tl_dates, d)
        label = timeline[tl_dates[idx - 1]] if idx > 0 else "UNLABELED"
        buckets.setdefault(label, []).append(r)

    by_label = {
        label: _bucket_stats(rs)
        for label, rs in sorted(buckets.items(), key=lambda kv: kv[0])
    }
    all_returns = [r for _, r in returns]
    return {
        "schema_version": "1.0",
        "join_rule": "d일 라벨 ↔ d+1 거래일 수익률 (전망적 — 미래 누출 차단)",
        "total_return_days": len(all_returns),
        "by_label": by_label,
        "all": _bucket_stats(all_returns),
        "note": "연구 전용 — 라이브 매매 신호 아님",
    }

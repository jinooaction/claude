"""정보계수(IC) — 합성 점수의 예측 성공률 측정 (스펙 041). 비커널 진단.

운영자 지적: "기대 수익율이나 예측 성공률 기준으로 판단해야 하는 거 아니야?" 합성 점수로
순위를 매겨 사는데, 그 점수가 *실제로* 미래 수익을 예측하는지는 따로 검증해야 한다. 그게
정보계수(Information Coefficient, IC)다 — 매 시점 횡단면에서 (점수 순위) vs (다음 기간 실현
수익률 순위)의 스피어만 순위상관. 여러 시점 평균이 양수이고 통계적으로 유의하면 신호에
예측력이 있는 것이고, 0 근처면 "그 점수로 줄 세워 사는 건 동전 던지기"라는 뜻이다.

이 모듈은 주문을 내지 않는다(읽기 전용). `strategy.factors.composite_scores` 를 *그대로*
재사용해, 과거 각 시점에서 그 시점까지의 바로 점수를 다시 계산하고 그 뒤 forward_horizon
거래일의 실현 수익률과 순위상관을 잰다. 미래 데이터 누출 없음(t 시점 점수는 t까지의 바만 사용).
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from decimal import Decimal

from auto_invest.market_data.store import PriceBar
from auto_invest.strategy.factors import composite_scores

_NEG_INF = Decimal("-Infinity")


@dataclass(frozen=True)
class ICResult:
    """IC 측정 결과 — 신호의 예측 성공률 요약."""

    mean_ic: float
    ic_std: float
    t_stat: float
    hit_rate: float  # IC_t > 0 인 시점 비율(방향 적중률)
    n_dates: int  # 유효 측정 시점 수
    avg_symbols: float  # 시점당 평균 횡단면 종목 수
    forward_horizon: int
    verdict: str

    def as_dict(self) -> dict:
        return {
            "mean_ic": round(self.mean_ic, 4),
            "ic_std": round(self.ic_std, 4),
            "t_stat": round(self.t_stat, 3),
            "hit_rate": round(self.hit_rate, 3),
            "n_dates": self.n_dates,
            "avg_symbols": round(self.avg_symbols, 1),
            "forward_horizon": self.forward_horizon,
            "verdict": self.verdict,
        }


def _ranks(values: list[float]) -> list[float]:
    """평균 순위(동률은 평균). 스피어만용."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0  # 1-기반 평균 순위
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:  # 분산 0 → 상관 정의 불가
        return None
    return sxy / math.sqrt(sxx * syy)


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """스피어만 순위상관(−1..1). 3개 미만이거나 한쪽 분산 0이면 None."""
    if len(xs) != len(ys):
        raise ValueError("length mismatch")
    if len(xs) < 3:
        return None
    return _pearson(_ranks(xs), _ranks(ys))


def _classify(mean_ic: float, t_stat: float, n_dates: int) -> str:
    if n_dates < 4:
        return "insufficient (측정 시점 부족 — 바를 더 쌓아야 판정 가능)"
    if mean_ic > 0 and t_stat >= 2.0:
        return "예측력 있음 (평균 IC 양수 + 통계적 유의 t≥2)"
    if mean_ic > 0:
        return "약한 양의 예측력 (IC 양수지만 유의성 약함 — 표본 더 필요)"
    return "예측력 없음 (IC≤0 — 이 점수로 줄 세워 사는 건 엣지 아님)"


def cross_sectional_ic(
    symbol_bars: dict[str, list[PriceBar]],
    *,
    weights: dict[str, Decimal],
    lookback_bars: int = 60,
    momentum_period: int = 20,
    momentum_gap_lag: int = 21,
    forward_horizon: int = 21,
    step: int | None = None,
    min_symbols: int = 5,
) -> ICResult:
    """합성 점수의 횡단면 IC를 과거 바로 측정한다(미래 누출 없음).

    매 평가 시점 t에서: (1) t까지의 바로 ``composite_scores`` 재계산, (2) 각 종목의 t→t+
    forward_horizon 거래일 실현 수익률 계산, (3) 둘의 스피어만 순위상관 IC_t. 여러 t의 평균/
    표준편차/ t-통계량/ 방향 적중률을 집계한다.

    Args:
        symbol_bars: 종목→오름차순 바 리스트.
        weights: 팩터 가중치(``composite_scores`` 와 동일).
        lookback_bars, momentum_period: 점수 계산 파라미터(전략과 동일하게).
        momentum_gap_lag: ``momentum_gap`` 팩터에서 최근 끝에서 건너뛸 바 수
            (12-1 의 "1"; ~21 ≈ 한 달). 다른 팩터는 무시.
        forward_horizon: 실현 수익률을 재는 앞쪽 거래일 수(21 ≈ 한 달).
        step: 평가 시점 간격. None 이면 forward_horizon(겹치지 않는 창 → 시점 간 독립성↑,
            t-통계량 과대평가 방지).
        min_symbols: 한 시점에서 IC를 재려면 필요한 최소 횡단면 종목 수.
    """
    if forward_horizon < 1:
        raise ValueError("forward_horizon must be >= 1")
    stride = step if step is not None else forward_horizon
    if stride < 1:
        raise ValueError("step must be >= 1")

    # 종목별 (날짜 리스트, 종가 리스트). 날짜 = bar_open_utc 문자열(정렬 가능).
    dates: dict[str, list[str]] = {}
    closes: dict[str, list[float]] = {}
    for sym, bars in symbol_bars.items():
        if not bars:
            continue
        dates[sym] = [b.bar_open_utc for b in bars]
        closes[sym] = [float(b.close_usd) for b in bars]

    timeline = sorted({d for ds in dates.values() for d in ds})
    if not timeline:
        return ICResult(0.0, 0.0, 0.0, 0.0, 0, 0.0, forward_horizon, _classify(0.0, 0.0, 0))

    ics: list[float] = []
    sym_counts: list[int] = []
    for ti in range(0, len(timeline), stride):
        t = timeline[ti]
        slice_bars: dict[str, list[PriceBar]] = {}
        fwd: dict[str, float] = {}
        for sym, ds in dates.items():
            k = bisect.bisect_right(ds, t)  # t 이하 바 개수
            if k < 1:
                continue
            slice_bars[sym] = symbol_bars[sym][:k]
            cur_idx = k - 1
            fut_idx = cur_idx + forward_horizon
            if fut_idx < len(closes[sym]) and closes[sym][cur_idx] > 0:
                fwd[sym] = closes[sym][fut_idx] / closes[sym][cur_idx] - 1.0
        if len(slice_bars) < min_symbols:
            continue
        scored = composite_scores(
            slice_bars,
            weights=weights,
            lookback_bars=lookback_bars,
            momentum_period=momentum_period,
            momentum_gap_lag=momentum_gap_lag,
        )
        score_map = {s: float(v) for s, v in scored if v != _NEG_INF}
        common = [s for s in score_map if s in fwd]
        if len(common) < min_symbols:
            continue
        ic = spearman([score_map[s] for s in common], [fwd[s] for s in common])
        if ic is not None:
            ics.append(ic)
            sym_counts.append(len(common))

    n = len(ics)
    if n == 0:
        return ICResult(0.0, 0.0, 0.0, 0.0, 0, 0.0, forward_horizon, _classify(0.0, 0.0, 0))
    mean_ic = sum(ics) / n
    if n > 1:
        var = sum((x - mean_ic) ** 2 for x in ics) / (n - 1)
        std = math.sqrt(var)
        if std > 0:
            t_stat = mean_ic / (std / math.sqrt(n))
        elif mean_ic != 0:
            # 분산 0 = 모든 시점 IC 동일 = 완벽히 일관된 신호 → 가장 강함(0이 아님).
            t_stat = math.copysign(99.0, mean_ic)
        else:
            t_stat = 0.0
        t_stat = max(-99.0, min(99.0, t_stat))  # JSON 유효 + 표시용 캡
    else:
        std = 0.0
        t_stat = 0.0
    hit_rate = sum(1 for x in ics if x > 0) / n
    avg_symbols = sum(sym_counts) / n
    return ICResult(
        mean_ic=mean_ic,
        ic_std=std,
        t_stat=t_stat,
        hit_rate=hit_rate,
        n_dates=n,
        avg_symbols=avg_symbols,
        forward_horizon=forward_horizon,
        verdict=_classify(mean_ic, t_stat, n),
    )


__all__ = ["ICResult", "cross_sectional_ic", "spearman"]

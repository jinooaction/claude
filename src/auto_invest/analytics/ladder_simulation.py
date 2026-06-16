"""스펙 050×044 — 자본 사다리 순 복리 시뮬레이션: raw 복리가 아니라 *배포된 시스템*의 돈.

왜 이게 "진짜 돈"의 정답인가(비직관적이지만 결정적):
  자본 사다리(헌법 X.4, 스펙 050)는 단 진입 후 *전략 자체의* 낙폭이 예산/2(기본 10%)에
  닿으면 즉시 한 단 **강등**(배포 자본 절반/4분의1로 컷), 예산(20%)에 닿으면 **정지**(단 0)
  한다. 강등은 배포 비율과 무관하게 전략의 낙폭으로 발동한다. 따라서:
  - 낙폭 큰 전략(예: 고정가중 ≈9.6%)은 10% 강등선을 자주 건드려 *손실 구간마다 배포
    자본이 깎이고* 다시 기어올라야 한다 → 단 3(NAV 100%)에 오래 못 머문다.
  - 낙폭 작은 전략(예: 역변동성 ≈5.5%)은 강등선 한참 아래라 단을 유지하며 단 3 까지 올라
    *온전히 복리*된다.
  그래서 "고정 자본 복리"는 raw CAGR 이 아니라 **사다리 강등/승격을 반영한 순 NAV 복리**로
  재야 한다. raw CAGR 이 높아도 낙폭이 커서 자꾸 강등되면 순 복리는 더 낮을 수 있다.

이 모듈은 순수·결정론·비커널이다. 주문 0·돈 0 이동(연구/측정 전용). 사다리 상수는 스펙 050
단일 출처(`capital_ladder`)에서 재사용한다(여기서 새 임계를 정의하지 않는다 — K1/X.4 보존).

정직한 한계:
  - **월간 해상도**: 낙폭을 월말 기준으로 재 일중/일별 낙폭을 과소평가한다(실제 강등은 더
    잦다). 두 전략에 같은 한계라 *상대* 비교는 공정하나 절대 강등 빈도는 보수적.
  - **단 0→1 재진입**: 실제론 forward EDGE_CONFIRMED 재검증이 필요(시간 소요). 여기선
    `promotion_min_months`(기본 1) 후 재진입으로 단순화(두 전략 동일 적용 → 상대 비교 공정).
  - **미배포분 수익 0**: 배포 안 된 NAV 는 현금(수익 0)으로 본다(보수적, rf 미반영).
"""

from __future__ import annotations

from dataclasses import dataclass

from auto_invest.portfolio.capital_ladder import (
    DEFAULT_DD_BUDGET_PCT,
    MAX_RUNG,
    RUNG_FRACTIONS,
)

MONTHS_PER_YEAR = 12

# 스펙 050 단 비율(Decimal)을 시뮬레이션용 float 로 — 임계는 재정의하지 않고 재사용만.
_RUNG_FRAC_F: dict[int, float] = {k: float(v) for k, v in RUNG_FRACTIONS.items()}
_DEFAULT_BUDGET_F = float(DEFAULT_DD_BUDGET_PCT)


@dataclass(frozen=True)
class LadderGrowthResult:
    """한 전략을 자본 사다리에 통과시킨 순 NAV 복리 + 사다리 동역학."""

    final_nav_multiple: float  # 시작 1.0 대비 최종 NAV 배수
    cagr_pct: float  # 사다리 순 NAV 연복리
    n_months: int
    demotions: int  # 강등 횟수(낙폭 ≥ 예산/2)
    halts: int  # 정지 횟수(낙폭 ≥ 예산)
    promotions: int  # 승격 횟수
    avg_rung: float  # 평균 체류 단(높을수록 배포 유지 잘함)
    rung_months: dict[int, int]  # 단별 체류 개월
    unconstrained_nav_multiple: float  # 항상 단 3(100% 배포) = raw 전략 복리 기준
    unconstrained_cagr_pct: float

    def as_dict(self) -> dict:
        return {
            "final_nav_multiple": round(self.final_nav_multiple, 4),
            "cagr_pct": round(self.cagr_pct, 2),
            "n_months": self.n_months,
            "demotions": self.demotions,
            "halts": self.halts,
            "promotions": self.promotions,
            "avg_rung": round(self.avg_rung, 3),
            "rung_months": dict(self.rung_months),
            "unconstrained_nav_multiple": round(self.unconstrained_nav_multiple, 4),
            "unconstrained_cagr_pct": round(self.unconstrained_cagr_pct, 2),
        }


def simulate_ladder_growth(
    monthly_returns: list[float],
    *,
    dd_budget_pct: float = _DEFAULT_BUDGET_F,
    promotion_min_months: int = 1,
    start_rung: int = 1,
) -> LadderGrowthResult:
    """전략의 월수익 스트림을 자본 사다리에 통과시켜 순 NAV 복리를 시뮬레이션한다.

    낙폭은 *단 진입 후* 전략 누적곡선의 고점 대비 하락(스펙 050 의 live_dd 정의)으로 재고,
    단이 바뀌면(승격·강등·정지) 시계를 리셋한다. 강등 ≥ 예산/2, 정지 ≥ 예산. 승격은 현 단에서
    `promotion_min_months` 이상 체류 + 낙폭 < 예산/2 + 단 < 최대일 때. 미배포분(단 비율의 나머지)
    은 현금(수익 0). `unconstrained_*` 는 같은 스트림을 항상 100% 배포(사다리 없음)했을 때 =
    raw 전략 복리(사다리의 보호/드래그를 견주는 기준).
    """
    demote_dd = dd_budget_pct / 2.0
    halt_dd = dd_budget_pct
    rung = max(0, min(MAX_RUNG, start_rung))

    nav = 1.0
    uncon = 1.0
    sub = 1.0  # 단 진입 후 전략 누적곡선
    peak = 1.0
    months_at = 0
    demotions = halts = promotions = 0
    rung_months: dict[int, int] = {r: 0 for r in range(MAX_RUNG + 1)}

    for r in monthly_returns:
        frac = _RUNG_FRAC_F[rung]
        nav *= 1.0 + frac * r
        uncon *= 1.0 + r
        rung_months[rung] += 1
        months_at += 1

        if rung >= 1:
            sub *= 1.0 + r
            if sub > peak:
                peak = sub
            dd = (peak - sub) / peak * 100.0 if peak > 0 else 0.0
        else:
            dd = 0.0  # 단 0 = 미배포 → 라이브 낙폭 없음

        new_rung = rung
        if rung >= 1 and dd >= halt_dd:
            new_rung = 0
            halts += 1
        elif rung >= 1 and dd >= demote_dd:
            new_rung = rung - 1
            demotions += 1
        elif rung < MAX_RUNG and months_at >= promotion_min_months and dd < demote_dd:
            new_rung = rung + 1
            promotions += 1  # 단 0→1 재진입도 승격으로 센다(검증 통과 가정)

        if new_rung != rung:
            rung = new_rung
            sub = 1.0
            peak = 1.0
            months_at = 0

    n = len(monthly_returns)
    years = n / MONTHS_PER_YEAR if n else 0.0
    cagr = (nav ** (1.0 / years) - 1.0) * 100.0 if nav > 0 and years > 0 else -100.0
    uncon_cagr = (
        (uncon ** (1.0 / years) - 1.0) * 100.0 if uncon > 0 and years > 0 else -100.0
    )
    avg_rung = (
        sum(k * v for k, v in rung_months.items()) / n if n else 0.0
    )
    return LadderGrowthResult(
        final_nav_multiple=nav,
        cagr_pct=cagr,
        n_months=n,
        demotions=demotions,
        halts=halts,
        promotions=promotions,
        avg_rung=avg_rung,
        rung_months=rung_months,
        unconstrained_nav_multiple=uncon,
        unconstrained_cagr_pct=uncon_cagr,
    )


__all__ = [
    "LadderGrowthResult",
    "simulate_ladder_growth",
]

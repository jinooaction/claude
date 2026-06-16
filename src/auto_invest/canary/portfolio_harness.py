"""스펙 055 — 자율 전략 재지정 ④ 게이트: 포트폴리오 챔피언 하드닝 캐너리.

스펙 007 하드닝 캐너리는 *룰 기반*(TradingRule) 변경을 검증한다(replay_window·shock·
RunOptions 가 모두 rules). 그러나 재지정 챔피언은 *포트폴리오 리밸런스 설정*(deploy/*.toml 의
`[portfolio]`)이다. 이 모듈은 검증된 포트폴리오 백테스트 엔진(`backtest.portfolio_replay`)으로
챔피언 전략을 과거 윈도우 + 실제 과거 급락 윈도우(합성 충격) + K1 게이트 퍼즈로 돌려, 스펙 007
과 *같은 5지표 평가*(`canary.metrics.evaluate_metrics`)로 PASS/FAIL 을 낸다 — 재지정 결정의
④ 게이트(`auto_reassign.decide_reassignment` 의 `canary_verdict`).

스펙 007 코어 재사용(전략 무관이라 그대로):
  - `evaluate_metrics` 5지표(낙폭·K1 위반·감사 무결성·지연·LLM비용) — 절대 임계.
  - `load_bands` 밴드 로더(위반=0·무결성=0 고정 강제).
  - `run_fuzz_pass` K1 게이트 속성 퍼즈(risk/gates.py 불변식 — 전략 무관).
  - `resolve_synthetic_shock_dates` / `shock_window` — 합성 충격은 가격 주입이 아니라 *실제
    과거 급락일 윈도우*(2008·2020 등)를 리플레이하는 것이라, 포트폴리오 엔진에 그대로 적용된다.

포트폴리오 전용으로 새로 만드는 것:
  - 정상 윈도우 + 충격 윈도우를 `replay_portfolio` 로 구동(룰의 `run_backtest` 대신).
  - 낙폭 = `PortfolioReplayResult.max_drawdown_pct`, K1 위반 = 충격 윈도우의 `gate_rejections`
    수(룰 캐너리와 동일 의미: 충격 하 게이트 거부 총합), 감사 무결성 = 윈도우 데이터 결손 수.

밴드: 재지정 캐너리는 *룰 변경*용 `canary_bands.toml`(낙폭 2~3%, 너무 타이트)이 아니라
전략에 맞는 별도 밴드(`config/canary_bands_reassign.toml`, 낙폭 = 자본 사다리 강등선 10%)를
쓴다. 도착 즉시 강등될 챔피언(최근 윈도우 낙폭 > 강등선)은 재지정 전에 거른다.

안전: 이 캐너리가 PASS 를 줘도 재지정은 자본 사다리를 rung 0(무장 해제)으로 리셋한다 — 실제
자본은 새 전략이 forward 재검증(스펙 050 사다리)을 다시 통과해야 들어간다. 캐너리는 *재지정
전 사전 선별*이고, 실제 돈 게이트는 하류의 자본 사다리다(심층 방어). 주문 0건·돈 0 이동(백테스트).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from auto_invest.backtest.broker_mock import BacktestBroker
from auto_invest.backtest.clock import ReplayClock
from auto_invest.backtest.data_source import HistoricalDataSource
from auto_invest.backtest.portfolio_replay import replay_portfolio
from auto_invest.backtest.replay import DEFAULT_TOTAL_CAPITAL_USD
from auto_invest.backtest.synthetic_shocks import (
    SyntheticShockConfigError,
    resolve_synthetic_shock_dates,
    shock_window,
)
from auto_invest.canary.bands import load_bands
from auto_invest.canary.fuzz import DEFAULT_ITERATIONS as DEFAULT_FUZZ_ITERATIONS
from auto_invest.canary.fuzz import run_fuzz_pass
from auto_invest.canary.metrics import evaluate_metrics
from auto_invest.config.caps import SizingCaps
from auto_invest.config.rules import PortfolioRebalanceConfig
from auto_invest.config.whitelist import Whitelist

# 재지정 캐너리 전용 밴드(낙폭 = 자본 사다리 강등선). 룰 변경용 canary_bands.toml 과 별개.
DEFAULT_REASSIGN_BANDS_PATH = Path("config/canary_bands_reassign.toml")

# 재지정 챔피언 검증 tier — 가장 엄격한 윈도우(L3, ≥45 거래일). 밴드 로더가 허용하는 tier.
DEFAULT_TIER = "L3"


@dataclass(frozen=True)
class PortfolioCanaryInputs:
    """포트폴리오 챔피언 캐너리 입력 — 검증할 전략 설정 + 데이터 + 윈도우."""

    config: PortfolioRebalanceConfig
    caps: SizingCaps
    whitelist: Whitelist
    data_source: HistoricalDataSource
    date_start: date  # 최근 윈도우 시작(낙폭 측정 구간 — ≥ tier.trading_days 권장)
    date_end: date  # 최근 윈도우 끝(≈ 오늘)
    halt_path: Path
    total_capital_usd: Decimal = DEFAULT_TOTAL_CAPITAL_USD
    shocks_toml: Path | None = None  # 없으면 스펙 008 기본 경로
    today: date | None = None  # 합성 충격 날짜 해석 기준(없으면 date_end)


@dataclass(frozen=True)
class PortfolioCanaryOutcome:
    """포트폴리오 캐너리 결과 — 재지정 ④ 게이트의 PASS/FAIL + 포렌식 지표."""

    outcome: Literal["passed", "failed"]
    failing_metrics: list[str]
    tier: str
    candidate_drawdown_pct: float
    shock_violations: int
    audit_integrity_count: int
    fuzz_counterexamples: int
    window_gate_rejections: int  # 정상 윈도우 게이트 거부(참고 — 위반으로 안 셈, 룰 캐너리와 동일)
    resolved_shock_dates: list[date]
    skipped_shock_dates: list[date]

    SCHEMA_VERSION = "1.0"

    @property
    def passed(self) -> bool:
        return self.outcome == "passed"

    @property
    def verdict(self) -> str:
        """auto_reassign.decide_reassignment 의 canary_verdict 입력(PASS/FAIL)."""
        return "PASS" if self.passed else "FAIL"

    def to_json_dict(self) -> dict:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "outcome": self.outcome,
            "verdict": self.verdict,
            "tier": self.tier,
            "failing_metrics": list(self.failing_metrics),
            "candidate_drawdown_pct": self.candidate_drawdown_pct,
            "shock_violations": self.shock_violations,
            "audit_integrity_count": self.audit_integrity_count,
            "fuzz_counterexamples": self.fuzz_counterexamples,
            "window_gate_rejections": self.window_gate_rejections,
            "resolved_shock_dates": [d.isoformat() for d in self.resolved_shock_dates],
            "skipped_shock_dates": [d.isoformat() for d in self.skipped_shock_dates],
        }


def _replay(
    inputs: PortfolioCanaryInputs,
    *,
    start: date,
    end: date,
    conn: sqlite3.Connection,
):
    """검증된 포트폴리오 백테스트 엔진으로 [start, end] 윈도우를 리플레이."""
    broker = BacktestBroker()
    clock = ReplayClock(datetime.combine(start, datetime.min.time(), UTC))
    return replay_portfolio(
        config=inputs.config,
        data_source=inputs.data_source,
        date_start=start,
        date_end=end,
        caps=inputs.caps,
        whitelist=inputs.whitelist,
        halt_path=inputs.halt_path,
        conn=conn,
        clock=clock,
        broker=broker,
        run_id=f"canary-port-{inputs.config.id}",
        total_capital_usd=inputs.total_capital_usd,
    )


def run_portfolio_canary(
    inputs: PortfolioCanaryInputs,
    *,
    audit_conn: sqlite3.Connection,
    tier: str = DEFAULT_TIER,
    bands_path: Path = DEFAULT_REASSIGN_BANDS_PATH,
    hypothesis_iterations: int = DEFAULT_FUZZ_ITERATIONS,
    hypothesis_seed: int | None = None,
    skip_fuzz: bool = False,
    skip_shock: bool = False,
) -> PortfolioCanaryOutcome:
    """포트폴리오 챔피언을 하드닝 캐너리로 검증 → PASS/FAIL(스펙 007 5지표 재사용).

    1. 정상 윈도우 리플레이 → 낙폭 + 데이터 결손 수(감사 무결성).
    2. 합성 충격 패스 — 실제 과거 급락 윈도우마다 리플레이, K1 게이트 거부 합산(데이터 없는
       충격일은 graceful skip).
    3. K1 게이트 속성 퍼즈(risk/gates.py 불변식 — 전략 무관).
    4. `evaluate_metrics` 로 5지표 절대 임계 평가(하나라도 밖이면 FAIL, all-or-nothing).
    """
    bands_map = load_bands(bands_path)
    if tier not in bands_map:
        raise ValueError(
            f"tier {tier!r} 가 {bands_path} 에 없음 — 사용 가능: {sorted(bands_map)}"
        )
    tier_bands = bands_map[tier]
    universe = list(inputs.config.universe)

    # 1. 정상 윈도우 — 낙폭 + 데이터 무결성(결손 = 데이터 품질 이슈).
    holes = inputs.data_source.coverage_holes(
        universe, inputs.date_start, inputs.date_end
    )
    audit_integrity_count = len(holes)
    window = _replay(inputs, start=inputs.date_start, end=inputs.date_end, conn=audit_conn)
    candidate_drawdown_pct = float(window.max_drawdown_pct)
    window_gate_rejections = len(window.gate_rejections)

    # 2. 합성 충격 — 실제 과거 급락 윈도우 리플레이, K1 게이트 거부 합산.
    shock_violations = 0
    resolved_shock_dates: list[date] = []
    skipped_shock_dates: list[date] = []
    if not skip_shock:
        try:
            shock_days = resolve_synthetic_shock_dates(
                today=inputs.today or inputs.date_end,
                path=inputs.shocks_toml,
            )
        except SyntheticShockConfigError:
            shock_days = []
        for s in shock_days:
            ws, we = shock_window(s, lookback_bars=30)
            if inputs.data_source.coverage_holes(universe, ws, we):
                skipped_shock_dates.append(s.session_date)
                continue
            sub = _replay(inputs, start=ws, end=we, conn=audit_conn)
            shock_violations += len(sub.gate_rejections)
            resolved_shock_dates.append(s.session_date)

    # 3. K1 게이트 속성 퍼즈(전략 무관 — 스펙 007 그대로).
    fuzz_counterexamples = 0
    if not skip_fuzz:
        seed = hypothesis_seed if hypothesis_seed is not None else 0
        fuzz_result = run_fuzz_pass(
            iterations=hypothesis_iterations, database_seed=seed
        )
        fuzz_counterexamples = len(fuzz_result.counterexamples)

    # 4. 5지표 절대 임계 평가(스펙 007 평가기 재사용).
    metrics = evaluate_metrics(
        candidate_drawdown_pct=candidate_drawdown_pct,
        audit_integrity_count=audit_integrity_count,
        shock_risk_gate_violations=shock_violations,
        fuzz_counterexample_count=fuzz_counterexamples,
        bands=tier_bands,
    )
    failing = metrics.failing_metric_ids()
    outcome: Literal["passed", "failed"] = "passed" if not failing else "failed"

    return PortfolioCanaryOutcome(
        outcome=outcome,
        failing_metrics=failing,
        tier=tier,
        candidate_drawdown_pct=candidate_drawdown_pct,
        shock_violations=shock_violations,
        audit_integrity_count=audit_integrity_count,
        fuzz_counterexamples=fuzz_counterexamples,
        window_gate_rejections=window_gate_rejections,
        resolved_shock_dates=resolved_shock_dates,
        skipped_shock_dates=skipped_shock_dates,
    )


__all__ = [
    "DEFAULT_REASSIGN_BANDS_PATH",
    "DEFAULT_TIER",
    "PortfolioCanaryInputs",
    "PortfolioCanaryOutcome",
    "run_portfolio_canary",
]

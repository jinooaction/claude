"""스펙 052 — 첫-자본까지의 길(money-path) 준비도 종합 + 첫-자본 추정 시점(ETA).

운영자 상시 지시(2026-06-13): "세계 최고 수준으로 진짜 돈을 벌어보자 + 사람 개입 없는
완벽한 자동 시스템 + 세계 최고 수준의 안정성." 이 모듈은 그 첫 문장("진짜 돈은 언제,
무엇을 통과해야 시작되나")을 한눈에 읽히게 만든다.

배경(왜 필요한가):
  자율 시스템이 "진짜 돈"으로 가는 길은 여러 사이드카에 흩어져 있다:
    · 전진 페이퍼(rebalance-paper-forward) — 전진 엣지 관측을 매 거래일 1개씩 쌓는다.
    · 자본 사다리 게이트(edge-autoarm) — 전진 엣지가 EDGE_CONFIRMED 가 되면 단0→단1
      (실계좌 NAV 의 0%→25%)로 자본을 올린다(헌법 X.4 v5.0.0 사다리).
    · 라이브 캐너리(rebalance-live-canary) — 무장 시 실제로 주문을 낸다.
    · 승격 준비(promote-readiness) — 헌법 VI 풀라이브 트랙레코드 게이트.
  "지금 진짜 돈이 어디까지 왔나, 다음 한 발을 막는 게 정확히 무엇인가, 언제 첫
  자본이 들어가나"에 답하려면 이 사이드카들을 사람이 일일이 받아 머릿속에서
  짜맞춰야 했다 — 이 프로젝트가 반복적으로 물렸던 "상태 혼동"의 한 형태다.

이 모듈이 하는 일(읽기 전용 소비자 계층):
  이미 발행된 결정 JSON 들(자본 사다리 결정·전진 판정·라이브 실적·캐너리 무장·승격
  준비)을 받아, "첫-자본까지의 길"을 단일 단계(stage)로 종합하고, 지금 한 발을 막는
  게이트(blocking gate)를 한 문장으로 지목하며, 누적 속도로 첫-자본 추정 시점(ETA)을
  낸다. **새 측정·재계산을 하지 않는다** — 사이드카가 발행한 숫자를 합칠 뿐이다.
  또한 "내려가는 길"(자본 방어선)도 표면화한다 — 배치된(또는 첫 자본 배치 예정) 자본의
  강등/정지 임계까지 남은 여유와 그때의 달러 손실을, 돈이 움직이기 전에도 한눈에 보인다.

안전 경계(중요):
  순수·결정론·비커널·읽기 전용. 주문 0건, 돈 0 이동. 이건 *보고/가시성*이지 거래나
  자본 변경이 아니다. 실제 자본 배치는 자본 사다리 게이트(edge-autoarm.yml)가, 실주문은
  라이브 캐너리 스케줄이 한다 — 무장·자본 사이징은 헌법 X.4 상시 위임에 따라 자율이고,
  운영자 전용은 입금(은행 이체=NAV 상한)·킬스위치·낙폭 예산뿐이다. 이 모듈은 그
  결정들을 *읽어 설명할* 뿐 어떤 것도 일으키지 않는다. 또한 누적이 조용히 멈추면(전진
  엣지 동결) ETA 가 무한대로 벌어져 드러나므로, 스펙 051 생존 감시와 결을 같이한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, InvalidOperation

from auto_invest.portfolio.capital_ladder import (
    DEFAULT_DD_BUDGET_PCT,
    MAX_RUNG,
    PROMOTION_MIN_CALENDAR_DAYS,
    PROMOTION_MIN_OBS,
    RUNG_FRACTIONS,
)

SCHEMA_VERSION = "1.1"

# 자본 사다리 결정 라벨(capital_ladder 와 동일 — 재사용보다 명시로 결합도 낮춤).
ACTION_PROMOTE = "PROMOTE"
ACTION_STAY = "STAY"
ACTION_DEMOTE = "DEMOTE"
ACTION_HALT = "HALT"
ACTION_RESIZE = "RESIZE"
ACTION_WAIT_EDGE = "WAIT_EDGE"
ACTION_BLOCKED = "BLOCKED"
ACTION_DISABLED = "DISABLED"

# 전진 판정 라벨(autoarm 과 동일).
EDGE_CONFIRMED = "EDGE_CONFIRMED"
NO_EDGE = "NO_EDGE"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

# ── 첫-자본까지의 길 단계(stage) ──
# 자율 머니루프가 "진짜 돈"으로 가는 경로상의 한 칸. 위에서 아래로 진행한다.
STAGE_BLOCKED = "BLOCKED"  # 게이트 입력 불능/정합성 차단/킬스위치 — 길을 읽을 수 없음
STAGE_ACCUMULATING = "ACCUMULATING_EDGE"  # 단0 · 관측 < 최소 — 더 쌓이는 중(정상, 시간 게이트)
STAGE_NO_EDGE_YET = "NO_EDGE_YET"  # 단0 · 관측 충분하나 엣지가 기준 미달(아직 엣지 없음)
STAGE_EDGE_CONFIRMED = "EDGE_CONFIRMED_PENDING_DEPLOY"  # 엣지 확정 — 첫 자본 배치 임박
STAGE_DEPLOYED = "DEPLOYED"  # 단≥1 · 자본 배치됨 — 다음 단 게이트 추적
STAGE_DEFENDED = "DEFENDED"  # 강등/정지(낙폭) — 자본 회수됨

# 게이트 한 조건의 상태.
GATE_PASS = "PASS"
GATE_PENDING = "PENDING"
GATE_FAIL = "FAIL"
GATE_NA = "N/A"

# ETA 추정 근거.
ETA_MEASURED = "measured"  # 직전 사이드카 대비 실측 누적 속도
ETA_NOMINAL = "nominal"  # 전진 스케줄 가정(거래일당 ~1 관측)
ETA_NONE = "n/a"  # 추정 불가/불필요

# 실제 돈 최상위 상태. 기존 money-path 는 자본 사다리의 첫 자본 ETA 를 잘 보여줬지만,
# 스펙 058 이후 별도 운영자 승인형 micro GTAA live 경로가 생겼다. 이 상태는 첫-자본
# 사다리보다 먼저 보여야 한다.
LIVE_STATUS_ARMED = "REAL_ORDER_PATH_ARMED"
LIVE_STATUS_PREVIEW = "PREVIEW_ONLY"
LIVE_STATUS_BLOCKED = "BLOCKED"
LIVE_STATUS_UNKNOWN = "UNKNOWN"
MICRO_GTAA_PATH = "micro-gtaa-live-canary"
MICRO_MAX_CAPITAL_USD = 1000
MICRO_SCHEDULE_HOUR_UTC = 15
MICRO_REQUIRED_GATES = (
    "strategy intent gate clear",
    "non-push workflow event",
    "US regular session",
    "KIS purchasable cash >= planned buys + 1% buffer",
    "micro circuit breaker clear",
    "K1 caps and K2 whitelist",
)
_BROKER_ACCEPTED_STATES = {
    "ACCEPTED",
    "SUBMITTED",
    "OPEN",
    "PARTIALLY_FILLED",
    "FILLED",
}

# 전진 시계 수렴 상태 — "살아있지만 수렴 못 하는" 정체/리셋을 드러낸다.
# 생존 감시(스펙 051)는 워크플로가 *멈췄나*(사이드카 나이)만 잡는다. 워크플로가
# *돌면서도* 전진 관측이 안 늘면(시장 휴장·중복 스냅샷) 또는 줄면(자본 베이시스
# 변경으로 consistent_basis_suffix 가 과거 점을 떨굼), 사이드카는 신선하니 생존
# 감시는 🟢 OK 로 본다 — 이 사각지대를 직전 money-path 사이드카 대비 관측 증감으로 잡는다.
CONV_CONVERGING = "converging"  # 직전 대비 관측 증가 — 정상 누적
CONV_STALLED = "stalled"  # 거래일 지났는데 관측 그대로 — 전진 시계 정체
CONV_REGRESSED = "regressed"  # 관측이 줄어듦 — 전진 시계 리셋(베이시스 변경 추정), 누적 재시작
CONV_UNKNOWN = "unknown"  # 직전 사이드카 없음/같은 거래일 — 아직 측정 불가

# 전진 표본 안정성 — 자본 베이시스 churn 진단. 수렴(관측 시계)과 *직교*하는 별개 차원.
# 출처: forward 판정의 legacy_snapshots_excluded(자본 베이시스가 바뀌어
# consistent_basis_suffix 가 떨군 과거 스냅샷 수, cli.py 가 발행). 매 거래일 새 스냅샷이
# 쌓여도 매번 같은 수가 베이시스 변경으로 제외되면 유효 관측은 정체/감소해 첫 자본이 영영
# 안 들어간다 — 생존 감시(스펙 051: 워크플로 정지)도, 수렴 감시(스펙 052: 관측 증감)도
# "정체(stalled)"로만 보고 그 *원인*(베이시스 churn)을 못 짚는 사각지대다. 직전 사이드카의
# 제외 개수와 비교해 '과거 1회 정리'와 '지금도 흔들리는 중'을 가른다.
SAMPLE_STABLE = "stable"  # 제외 0 — 모든 스냅샷 같은 베이시스(완전 안정)
SAMPLE_SETTLED = "settled"  # 제외 > 0 이나 직전 대비 안 늘어남 — 과거 1회 정리, 새 churn 없음
SAMPLE_CHURNING = "churning"  # 제외가 직전보다 늘어남 — 베이시스가 또 바뀜(누적 잠식 진행 중)
SAMPLE_UNKNOWN = "unknown"  # legacy 정보 없음 — 측정 불가(기존 사이드카/거짓 경보 0)

# 전진 페이퍼 스케줄(rebalance-paper-forward.yml: 평일 22:30 UTC) — 거래일당 ~1 관측.
NOMINAL_OBS_PER_TRADING_DAY = 1.0


def _dec(value: object) -> Decimal | None:
    """문자열/숫자를 Decimal 로 보수적으로 변환(불능이면 None)."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


@dataclass(frozen=True)
class GateCondition:
    """다음 한 발을 막는(또는 통과시키는) 단일 조건."""

    name: str
    status: str  # PASS | PENDING | FAIL | N/A
    current: str  # 사람이 읽는 현재값
    required: str  # 사람이 읽는 합격 기준
    detail: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "current": self.current,
            "required": self.required,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class EtaProjection:
    """첫-자본(또는 다음 단)까지의 추정 시점."""

    basis: str  # measured | nominal | n/a
    obs_remaining: int | None
    obs_per_trading_day: float | None
    trading_days_remaining: int | None
    projected_date: str | None  # ISO date (YYYY-MM-DD)
    assumption: str
    convergence: str = CONV_UNKNOWN  # converging | stalled | regressed | unknown
    sample_stability: str = SAMPLE_UNKNOWN  # stable | settled | churning | unknown
    legacy_excluded: int | None = None  # 이번 판정에서 베이시스 변경으로 제외된 스냅샷 수
    snapshot_count: int | None = None  # 베이시스 일치 유효 스냅샷 수(관측 = 이 값 − 1)

    def to_dict(self) -> dict:
        return {
            "basis": self.basis,
            "obs_remaining": self.obs_remaining,
            "obs_per_trading_day": (
                round(self.obs_per_trading_day, 3)
                if self.obs_per_trading_day is not None
                else None
            ),
            "trading_days_remaining": self.trading_days_remaining,
            "projected_date": self.projected_date,
            "assumption": self.assumption,
            "convergence": self.convergence,
            "sample_stability": self.sample_stability,
            "legacy_excluded": self.legacy_excluded,
            "snapshot_count": self.snapshot_count,
        }


@dataclass(frozen=True)
class SafetyBudget:
    """자본 방어선 예산 — 배치된(또는 배치 예정) 자본의 다운사이드 한계와 여유.

    money-path 가 "올라가는 길"(엣지 누적→첫 자본→다음 단 승격)은 촘촘히 계측하지만,
    "내려가는 방어선"(낙폭에 따른 강등/정지)은 DEPLOYED 단계의 *이진* 게이트(예산/2 미만?)
    뿐이라 방어선에 *얼마나 가까운지*가 안 보였다. 이 구조체는 그 방어선을 연속 값으로
    표면화한다:
      · 강등 임계(예산/2)·정지 임계(예산)까지 남은 %포인트(margin)와 그때의 달러 손실,
      · 단0(미배치)에서도 "첫 자본이 들어가면 다운사이드 예산이 달러로 얼마인가"(prospective).
    낙폭은 배치 NAV 대비 peak-to-trough 이므로 달러 손실은 배치 자본 기준 *근사*(올림 —
    위험을 과소평가하지 않는다)다. 읽기 전용·결정론 — 강제하지 않고 보이게만 한다(실제
    강등/정지는 자본 사다리가 한다).
    """

    reference_rung: int  # 기준 단(배치 중이면 현재/목표 단, 미배치면 첫 자본 단=1)
    capital_usd: int | None  # 기준 단의 배치(예정) 자본
    demote_dd_pct: str  # 강등 임계 낙폭(예산/2)
    halt_dd_pct: str  # 정지 임계 낙폭(예산)
    loss_at_demote_usd: int | None  # 강등 발동 시점 누적 손실(근사, 배치 자본 기준)
    loss_at_halt_usd: int | None  # 정지 발동 시점 누적 손실(근사)
    current_dd_pct: str | None  # 현재 라이브 낙폭(배치 후에만; 미배치면 None)
    margin_to_demote_pct: str | None  # 강등까지 남은 %포인트(음수=이미 초과)
    margin_to_halt_pct: str | None  # 정지까지 남은 %포인트(음수=이미 초과)
    prospective: bool  # True=아직 미배치(첫 자본 예상 예산), False=배치 중 실측

    def to_dict(self) -> dict:
        return {
            "reference_rung": self.reference_rung,
            "capital_usd": self.capital_usd,
            "demote_dd_pct": self.demote_dd_pct,
            "halt_dd_pct": self.halt_dd_pct,
            "loss_at_demote_usd": self.loss_at_demote_usd,
            "loss_at_halt_usd": self.loss_at_halt_usd,
            "current_dd_pct": self.current_dd_pct,
            "margin_to_demote_pct": self.margin_to_demote_pct,
            "margin_to_halt_pct": self.margin_to_halt_pct,
            "prospective": self.prospective,
        }


@dataclass(frozen=True)
class MicroGtaaRunEvidence:
    """micro GTAA 마지막 실행 증거 — job success 와 브로커 접수/체결을 분리한다."""

    run_id: str | None
    timestamp_utc: str | None
    event: str | None
    live_step: str | None
    intent_gate_ok: bool | None
    intent_gate_reason: str | None
    preflight_ok: bool | None
    preflight_reason: str
    breaker_reason: str | None
    order_states: list[str]
    accepted_or_filled_count: int
    broker_rejected_count: int

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "timestamp_utc": self.timestamp_utc,
            "event": self.event,
            "live_step": self.live_step,
            "intent_gate_ok": self.intent_gate_ok,
            "intent_gate_reason": self.intent_gate_reason,
            "preflight_ok": self.preflight_ok,
            "preflight_reason": self.preflight_reason,
            "breaker_reason": self.breaker_reason,
            "order_states": list(self.order_states),
            "accepted_or_filled_count": self.accepted_or_filled_count,
            "broker_rejected_count": self.broker_rejected_count,
        }


@dataclass(frozen=True)
class LiveMoneyState:
    """현재 실제 돈 경로 최상위 상태.

    can_submit_real_orders=True 는 "비-push 실행이 preflight 와 안전 게이트를 통과하면
    실주문 단계에 도달할 수 있음"이다. 주문 접수/체결 보장은 아니다.
    """

    status: str
    can_submit_real_orders: bool
    path: str
    capital_usd: int | None
    max_capital_usd: int
    next_scheduled_live_utc: str | None
    required_gates: tuple[str, ...]
    detail: str
    last_run: MicroGtaaRunEvidence | None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "can_submit_real_orders": self.can_submit_real_orders,
            "path": self.path,
            "capital_usd": self.capital_usd,
            "max_capital_usd": self.max_capital_usd,
            "next_scheduled_live_utc": self.next_scheduled_live_utc,
            "required_gates": list(self.required_gates),
            "detail": self.detail,
            "last_run": None if self.last_run is None else self.last_run.to_dict(),
        }


@dataclass(frozen=True)
class MoneyPathReport:
    """첫-자본까지의 길 종합 보고 — 읽기 전용 결정 표면."""

    schema_version: str
    as_of_utc: str
    stage: str
    headline: str  # 한 문장 요약(운영자가 먼저 읽는 줄)
    blocking_gate: str  # 지금 한 발을 막는 것(없으면 설명)
    current_rung: int
    capital_pct: str  # 현재 단의 배치 비율(%)
    account_nav_usd: str | None
    deployed_capital_usd: int | None
    canary_armed: bool | None
    live_money_state: LiveMoneyState
    gates: list[GateCondition]
    eta: EtaProjection
    safety: SafetyBudget | None  # 자본 방어선 예산(내려가는 길) — BLOCKED 면 None
    next_action: str  # 시스템이 자율로 할 다음 일 + 운영자 게이트가 무엇인지

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "as_of_utc": self.as_of_utc,
            "stage": self.stage,
            "headline": self.headline,
            "blocking_gate": self.blocking_gate,
            "current_rung": self.current_rung,
            "capital_pct": self.capital_pct,
            "account_nav_usd": self.account_nav_usd,
            "deployed_capital_usd": self.deployed_capital_usd,
            "canary_armed": self.canary_armed,
            "live_money_state": self.live_money_state.to_dict(),
            "gates": [g.to_dict() for g in self.gates],
            "eta": self.eta.to_dict(),
            "safety_budget": None if self.safety is None else self.safety.to_dict(),
            "next_action": self.next_action,
        }

    def as_text(self) -> str:
        cap = self.deployed_capital_usd if self.deployed_capital_usd is not None else 0
        stage_icon = {
            STAGE_BLOCKED: "🛑",
            STAGE_ACCUMULATING: "⏳",
            STAGE_NO_EDGE_YET: "➖",
            STAGE_EDGE_CONFIRMED: "🟢",
            STAGE_DEPLOYED: "💰",
            STAGE_DEFENDED: "🛡",
        }.get(self.stage, "•")
        gate_icon = {GATE_PASS: "✅", GATE_PENDING: "⏳", GATE_FAIL: "❌", GATE_NA: "—"}
        lines = [
            f"# 돈 경로 상태 / 첫-자본까지의 길 (as of {self.as_of_utc}) — 읽기 전용, 돈 0 이동",
            "",
            "## 실제 돈 최상위 상태",
            "",
            *self._live_money_lines(),
            "",
            "## 기존 자본 사다리 상태",
            "",
            f"단계: {stage_icon} **{self.stage}**",
            "",
            f"> {self.headline}",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| 현재 단(rung) | {self.current_rung} / {MAX_RUNG} |",
            f"| 배치 비율 | {self.capital_pct}% |",
            f"| 실계좌 NAV | {self.account_nav_usd or '(측정 불가)'} |",
            f"| 배치 자본(USD) | {cap} |",
            f"| 캐너리 무장 | {self._armed_text()} |",
            f"| 지금 막는 것 | {self.blocking_gate} |",
            "",
            "## 게이트 (다음 한 발의 합격 조건)",
            "",
            "| 조건 | 상태 | 현재 | 기준 |",
            "|------|:----:|------|------|",
        ]
        for g in self.gates:
            lines.append(
                f"| {g.name} | {gate_icon.get(g.status, '?')} {g.status} | "
                f"{g.current} | {g.required} |"
            )
        lines += ["", "## 첫-자본 추정 시점(ETA)", ""]
        if self.eta.basis == ETA_NONE:
            lines.append(f"- {self.eta.assumption}")
        else:
            conv_label = {
                CONV_CONVERGING: "🟢 수렴 중(직전 사이드카 대비 관측 증가)",
                CONV_STALLED: "🟡 정체(거래일 지났는데 관측 그대로) — 아래 날짜 신뢰 낮음",
                CONV_REGRESSED: "🔴 리셋(관측 줄어듦, 자본 베이시스 변경 추정) — 누적 재시작",
                CONV_UNKNOWN: "⚪ 측정 전(직전 사이드카 없음 또는 같은 거래일)",
            }.get(self.eta.convergence, self.eta.convergence)
            lines.append(f"- 전진 시계 수렴: {conv_label}")
            if (
                self.eta.legacy_excluded is not None
                and self.eta.sample_stability != SAMPLE_UNKNOWN
            ):
                sample_label = {
                    SAMPLE_STABLE: "🟢 안정(모든 스냅샷 같은 자본 베이시스)",
                    SAMPLE_SETTLED: (
                        f"🟡 정리됨(과거 {self.eta.legacy_excluded}개 베이시스 제외, "
                        f"유효 {self.eta.snapshot_count}, 추가 없음)"
                    ),
                    SAMPLE_CHURNING: (
                        f"🔴 흔들림({self.eta.legacy_excluded}개 제외 직전↑, 유효 "
                        f"{self.eta.snapshot_count}) — 새 스냅샷이 계속 떨궈짐"
                    ),
                }.get(self.eta.sample_stability, self.eta.sample_stability)
                lines.append(f"- 전진 표본 안정성: {sample_label}")
            lines += [
                f"- 남은 관측: **{self.eta.obs_remaining}** 개 "
                f"(속도 ~{self.eta.obs_per_trading_day} 관측/거래일, 근거={self.eta.basis})",
                f"- 추정: 약 **{self.eta.trading_days_remaining} 거래일** 후 "
                f"→ **{self.eta.projected_date}** 경",
                f"- 가정: {self.eta.assumption}",
            ]
        lines += self._safety_lines()
        lines += [
            "",
            "## 다음 행동",
            "",
            f"- {self.next_action}",
            "",
            "⚠ 이건 종합 보고다(읽기 전용). 거래·자본 변경 없음 — 실제 배치는 자본 사다리 "
            "게이트가 자율로 한다(헌법 X.4 상시 위임). 운영자 전용은 입금·킬스위치·낙폭 예산뿐.",
        ]
        return "\n".join(lines)

    def _live_money_lines(self) -> list[str]:
        state = self.live_money_state
        status_label = {
            LIVE_STATUS_ARMED: (
                "🟠 실제 돈 경로 무장 — preflight 통과 후 실주문 가능"
            ),
            LIVE_STATUS_PREVIEW: "⚪ 미리보기 전용 — 실주문 불가",
            LIVE_STATUS_BLOCKED: "🛑 차단 — 실주문 불가",
            LIVE_STATUS_UNKNOWN: "❓ 불명 — 단정 금지",
        }.get(state.status, state.status)
        submit = (
            "예(비-push 실행 + preflight 통과 필요)"
            if state.can_submit_real_orders
            else "아니오"
        )
        cap = "(불명)" if state.capital_usd is None else f"${state.capital_usd}"
        next_run = state.next_scheduled_live_utc or "(없음)"
        lines = [
            f"> {status_label}",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| 경로 | {state.path} |",
            f"| 상태 | {state.status} |",
            f"| 실주문 단계 도달 가능 | {submit} |",
            f"| 선언 자본 / 한도 | {cap} / ${state.max_capital_usd} |",
            f"| 다음 예약 live 후보 | {next_run} |",
            f"| 남은 필수 게이트 | {', '.join(state.required_gates)} |",
            f"| 판정 근거 | {state.detail} |",
        ]
        if state.last_run is None:
            lines.append("| 마지막 micro GTAA 실행 | (sidecar 없음) |")
            return lines

        run = state.last_run
        live_step = run.live_step or "(불명)"
        states = ", ".join(run.order_states) if run.order_states else "(주문 결과 없음)"
        fill_text = (
            f"브로커 접수·체결 {run.accepted_or_filled_count}건, "
            f"브로커 거부 {run.broker_rejected_count}건"
        )
        lines += [
            "| 마지막 run | "
            f"{run.run_id or '(불명)'} / {run.timestamp_utc or '(시각 불명)'} / "
            f"event={run.event or '(불명)'} |",
            f"| 마지막 LIVE 스텝 | {live_step} |",
            "| 마지막 전략 의도 게이트 | "
            f"ok={run.intent_gate_ok}, reason={run.intent_gate_reason or '(불명)'} |",
            f"| 마지막 preflight | ok={run.preflight_ok}, reason={run.preflight_reason} |",
            f"| 마지막 손실 브레이커 | {run.breaker_reason or '(불명)'} |",
            f"| 마지막 주문 상태 | {states} |",
            f"| 마지막 접수·체결 판단 | {fill_text} |",
        ]
        return lines

    def _armed_text(self) -> str:
        if self.canary_armed is None:
            return "(불명)"
        return "예(armed)" if self.canary_armed else "아니오(드라이런)"

    def _safety_lines(self) -> list[str]:
        """자본 방어선 예산 섹션(as_text 보조) — '내려가는 길'을 사람이 읽게."""
        s = self.safety
        if s is None:
            return []
        cap = "(측정 불가)" if s.capital_usd is None else f"${s.capital_usd}"
        ld = "(측정 불가)" if s.loss_at_demote_usd is None else f"-${s.loss_at_demote_usd}"
        lh = "(측정 불가)" if s.loss_at_halt_usd is None else f"-${s.loss_at_halt_usd}"
        out = ["", "## 자본 방어선 예산 (다운사이드 한계 — 내려가는 길)", ""]
        if s.prospective:
            out += [
                f"- 첫 자본은 단{s.reference_rung}(NAV 의 {_capital_pct(s.reference_rung)}%) "
                f"≈ **{cap}** 로 들어간다.",
                f"- 자동 강등(→단0, 무장 해제): 낙폭 ≥ **{s.demote_dd_pct}%** → 약 {ld} 손실.",
                f"- 절대 정지: 낙폭 ≥ **{s.halt_dd_pct}%** → 약 {lh} 손실.",
                f"- 즉 첫 자본의 다운사이드는 약 {ld}(강등) 안에서 시스템이 스스로 자본을 "
                "회수한다 — 사람 개입 없이 작동하는 방어선.",
            ]
            return out
        cur = "(측정 불가)" if s.current_dd_pct is None else f"{s.current_dd_pct}%"
        out.append(f"- 배치 자본: 단{s.reference_rung} ≈ **{cap}**, 현재 낙폭 **{cur}**.")
        if s.current_dd_pct is None:
            out += [
                "- ⚠ 현재 낙폭 측정 불가 — 방어선까지의 여유를 계산할 수 없다. 라이브 실적 "
                "피드(live_growth)가 비면 자동 강등/정지가 늦어질 수 있으니 점검 필요.",
                f"- 강등 임계 {s.demote_dd_pct}% ≈ {ld}, 정지 임계 {s.halt_dd_pct}% ≈ {lh}.",
            ]
            return out
        md = s.margin_to_demote_pct
        mh = s.margin_to_halt_pct
        breached = md is not None and Decimal(md) <= 0
        if breached:
            out.append(
                f"- ⚠ 방어선 초과 — 낙폭이 강등 임계 {s.demote_dd_pct}% 를 넘었다"
                f"(여유 {md}%포인트). 자본 사다리가 자본을 회수한다."
            )
        else:
            out.append(
                f"- 강등까지 여유: **{md}%포인트** (강등 임계 {s.demote_dd_pct}% ≈ {ld})."
            )
        out.append(f"- 정지까지 여유: **{mh}%포인트** (정지 임계 {s.halt_dd_pct}% ≈ {lh}).")
        return out


def _trading_days_between(d0: date, d1: date) -> int:
    """[d0, d1) 사이 평일(월~금) 수. d1<=d0 이면 0."""
    if d1 <= d0:
        return 0
    days = 0
    cur = d0
    while cur < d1:
        if cur.weekday() < 5:  # 0=월 … 4=금
            days += 1
        cur += timedelta(days=1)
    return days


def _project_trading_date(
    start: date, obs_remaining: float, obs_per_trading_day: float
) -> tuple[int, date]:
    """start 부터 평일마다 obs_per_trading_day 씩 쌓아 obs_remaining 도달일을 추정.

    반환: (걸린 캘린더일 수, 추정 도달일). obs_remaining<=0 이면 (0, start).
    """
    if obs_remaining <= 0 or obs_per_trading_day <= 0:
        return 0, start
    accrued = 0.0
    cur = start
    calendar_days = 0
    # 안전 상한: 5년(누적 속도가 비정상적으로 느려도 무한 루프 방지).
    for _ in range(366 * 5):
        cur += timedelta(days=1)
        calendar_days += 1
        if cur.weekday() < 5:
            accrued += obs_per_trading_day
        if accrued >= obs_remaining:
            return calendar_days, cur
    return calendar_days, cur


def _sample_stability(legacy_excluded: int | None, prior_legacy: int | None) -> str:
    """자본 베이시스 churn 등급 — 직전 사이드카의 제외 개수와 비교(수렴과 직교).

    legacy_excluded 가 직전보다 *늘어났으면* 이번에도 베이시스가 또 바뀌어 새 스냅샷이
    제외된 것(CHURNING). 0 이면 모든 스냅샷 같은 베이시스(STABLE). 0 보다 크지만 직전
    대비 안 늘었으면 과거 1회 정리이고 지금은 안정(SETTLED). 직전 비교 불가 시에도
    보수적으로 SETTLED(거짓 churn 경보 0).
    """
    if legacy_excluded is None:
        return SAMPLE_UNKNOWN
    if legacy_excluded == 0:
        return SAMPLE_STABLE
    if prior_legacy is not None and legacy_excluded > prior_legacy:
        return SAMPLE_CHURNING
    return SAMPLE_SETTLED


def _accumulation_eta(
    *,
    n_obs: int | None,
    min_obs: int | None,
    as_of: datetime,
    prior_n_obs: int | None,
    prior_ts: str | None,
    legacy_excluded: int | None = None,
    snapshot_count: int | None = None,
    prior_legacy: int | None = None,
) -> EtaProjection:
    """전진 관측 누적 속도로 최소 관측 수 도달 시점을 추정.

    measured: 직전 사이드카(prior_n_obs, prior_ts) 대비 실측 속도(거래일당 관측).
    nominal: 직전이 없거나 속도가 비양수면 전진 스케줄 가정(거래일당 ~1 관측).

    legacy_excluded/snapshot_count(forward 판정의 자본 베이시스 정합 결과)와
    prior_legacy(직전 사이드카의 제외 개수)로 표본 안정성(베이시스 churn)을 함께 진단해
    수렴 위에 덧입힌다 — 정체/리셋의 *원인*이 베이시스 churn 인지 짚기 위함.
    """
    sample = _sample_stability(legacy_excluded, prior_legacy)
    if n_obs is None or min_obs is None:
        return EtaProjection(
            basis=ETA_NONE,
            obs_remaining=None,
            obs_per_trading_day=None,
            trading_days_remaining=None,
            projected_date=None,
            assumption="전진 판정 JSON 에 관측 수가 없어 추정 불가.",
            sample_stability=sample,
            legacy_excluded=legacy_excluded,
            snapshot_count=snapshot_count,
        )
    obs_remaining = max(0, min_obs - n_obs)
    if obs_remaining == 0:
        return EtaProjection(
            basis=ETA_NONE,
            obs_remaining=0,
            obs_per_trading_day=None,
            trading_days_remaining=0,
            projected_date=as_of.date().isoformat(),
            assumption="최소 관측 수 이미 충족 — 판정 단계로 진행.",
            sample_stability=sample,
            legacy_excluded=legacy_excluded,
            snapshot_count=snapshot_count,
        )

    as_of_date = as_of.date()
    rate = NOMINAL_OBS_PER_TRADING_DAY
    basis = ETA_NOMINAL
    convergence = CONV_UNKNOWN
    assumption = "전진 페이퍼는 평일 22:30 UTC 1회 → 거래일당 ~1 관측 가정(실측 누적 전 기본값)."

    prior_dt = _parse_iso(prior_ts)
    if prior_dt is not None and prior_n_obs is not None:
        td = _trading_days_between(prior_dt.date(), as_of_date)
        if n_obs < prior_n_obs:
            # 관측이 줄었다 = 전진 시계 리셋(consistent_basis_suffix 가 자본 베이시스
            # 변경으로 과거 스냅샷을 떨굼). 누적이 처음부터 다시 시작 → ETA 가 뒤로 밀린다.
            # 거래일 경과와 무관하게 항상 드러낸다(관측은 절대 줄면 안 되는 값).
            convergence = CONV_REGRESSED
            assumption = (
                f"⚠ 전진 관측이 직전({prior_dt.date().isoformat()}) {prior_n_obs}개에서 "
                f"{n_obs}개로 줄었다 — 전진 시계 리셋(자본 베이시스 변경 추정). 누적이 처음부터 "
                "다시 시작돼 첫-자본 ETA 가 뒤로 밀렸다. 전략 지문이 자주 바뀌면 영영 최소 "
                "관측을 못 채운다(전략 변경은 전진 토너먼트에 *추가* 검증으로 — 갈아엎지 말 것)."
            )
        elif n_obs > prior_n_obs and td > 0:
            measured = (n_obs - prior_n_obs) / td
            if measured > 0:
                rate = measured
                basis = ETA_MEASURED
                convergence = CONV_CONVERGING
                assumption = (
                    f"직전 사이드카({prior_dt.date().isoformat()}, 관측 {prior_n_obs}) "
                    f"대비 실측 누적 속도 {measured:.2f} 관측/거래일."
                )
        elif n_obs == prior_n_obs and td > 0:
            # 거래일이 지났는데 관측이 그대로 = 전진 시계 정체(시장 휴장·중복 스냅샷·전진
            # 페이퍼 정지 가능). nominal 날짜는 누적이 *재개된다는 가정*의 낙관 최선치일 뿐.
            convergence = CONV_STALLED
            assumption = (
                f"⚠ 직전 사이드카({prior_dt.date().isoformat()}, 관측 {prior_n_obs}) 대비 "
                f"거래일 {td}일 지났는데 관측이 그대로({n_obs}) — 전진 시계 정체(시장 휴장·중복 "
                "스냅샷·전진 페이퍼 정지 가능). 아래 날짜는 누적이 재개된다는 가정의 최선치다."
            )

    # 표본 안정성(베이시스 churn)을 수렴 위에 덧입힌다 — 정체/리셋의 *원인*을 짚는다.
    # CHURNING 이면 (관측이 정체로 보여도) 진짜 원인은 베이시스가 또 바뀌어 새 스냅샷이
    # 제외되는 것 — 자본/측정 기준을 고정하지 않으면 누적이 영영 진척되지 않는다.
    if sample == SAMPLE_CHURNING:
        assumption += (
            f" ⚠ 또한 이번 판정은 유효 스냅샷 {snapshot_count}개뿐이고 "
            f"{legacy_excluded}개가 자본 베이시스 변경으로 제외됐다(직전보다 늘어남) — "
            "베이시스가 또 바뀌는 중이라 새 스냅샷이 계속 떨궈진다. 측정 기준을 고정해야 "
            "관측이 진척된다."
        )
    elif sample == SAMPLE_SETTLED and legacy_excluded:
        assumption += (
            f" (참고: 과거 {legacy_excluded}개 스냅샷이 베이시스 변경으로 제외됐으나 직전 "
            "대비 추가 제외 없음 — 현재 베이시스는 안정.)"
        )

    calendar_days, projected = _project_trading_date(as_of_date, obs_remaining, rate)
    return EtaProjection(
        basis=basis,
        obs_remaining=obs_remaining,
        obs_per_trading_day=rate,
        trading_days_remaining=_trading_days_between(as_of_date, projected),
        projected_date=projected.isoformat(),
        assumption=assumption,
        convergence=convergence,
        sample_stability=sample,
        legacy_excluded=legacy_excluded,
        snapshot_count=snapshot_count,
    )


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    return None


def _next_micro_schedule(now: datetime) -> str:
    """다음 평일 15:00 UTC micro GTAA 예약 live 후보 시각."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    now = now.astimezone(UTC)
    candidate = now.replace(
        hour=MICRO_SCHEDULE_HOUR_UTC, minute=0, second=0, microsecond=0
    )
    if now.weekday() >= 5 or now >= candidate:
        candidate = candidate + timedelta(days=1)
        while candidate.weekday() >= 5:
            candidate = candidate + timedelta(days=1)
    return candidate.strftime("%Y-%m-%dT%H:%M:%SZ")


def _micro_run_evidence(data: dict | None) -> MicroGtaaRunEvidence | None:
    if not data:
        return None

    live_result = data.get("live_result")
    results = live_result.get("results", []) if isinstance(live_result, dict) else []
    order_states = [
        str(row.get("state"))
        for row in results
        if isinstance(row, dict) and row.get("state") is not None
    ]
    accepted = sum(1 for state in order_states if state in _BROKER_ACCEPTED_STATES)
    rejected = sum(1 for state in order_states if state == "REJECTED_BY_BROKER")

    preflight = data.get("preflight")
    if isinstance(preflight, dict):
        preflight_ok = preflight.get("ok") if isinstance(preflight.get("ok"), bool) else None
        preflight_reason = str(preflight.get("reason") or "preflight reason absent")
    else:
        preflight_ok = None
        preflight_reason = "preflight evidence absent"

    intent_gate = data.get("intent_gate")
    if isinstance(intent_gate, dict):
        intent_gate_ok = (
            intent_gate.get("ok") if isinstance(intent_gate.get("ok"), bool) else None
        )
        intent_gate_reason = str(intent_gate.get("reason") or "intent gate reason absent")
    else:
        intent_gate_ok = None
        intent_gate_reason = None

    breaker = data.get("breaker")
    breaker_reason = (
        str(breaker.get("reason")) if isinstance(breaker, dict) and breaker.get("reason") else None
    )

    return MicroGtaaRunEvidence(
        run_id=None if data.get("run_id") is None else str(data.get("run_id")),
        timestamp_utc=(
            None if data.get("timestamp_utc") is None else str(data.get("timestamp_utc"))
        ),
        event=None if data.get("event") is None else str(data.get("event")),
        live_step=None if data.get("live_step") is None else str(data.get("live_step")),
        intent_gate_ok=intent_gate_ok,
        intent_gate_reason=intent_gate_reason,
        preflight_ok=preflight_ok,
        preflight_reason=preflight_reason,
        breaker_reason=breaker_reason,
        order_states=order_states,
        accepted_or_filled_count=accepted,
        broker_rejected_count=rejected,
    )


def assess_live_money_state(
    *,
    micro_request: dict | None,
    micro_last_run: dict | None = None,
    now: datetime,
) -> LiveMoneyState:
    """micro GTAA 실거래 경로 최상위 상태를 분류(읽기 전용·결정론)."""
    last_run = _micro_run_evidence(micro_last_run)
    base = {
        "path": MICRO_GTAA_PATH,
        "max_capital_usd": MICRO_MAX_CAPITAL_USD,
        "required_gates": MICRO_REQUIRED_GATES,
        "last_run": last_run,
    }
    if not micro_request:
        return LiveMoneyState(
            status=LIVE_STATUS_UNKNOWN,
            can_submit_real_orders=False,
            capital_usd=None,
            next_scheduled_live_utc=None,
            detail="micro GTAA 센티넬을 읽지 못함 — 실제 돈 상태 단정 금지.",
            **base,
        )

    armed = _bool(micro_request.get("armed"))
    capital = _int(micro_request.get("capital_usd"))
    if armed is None:
        return LiveMoneyState(
            status=LIVE_STATUS_UNKNOWN,
            can_submit_real_orders=False,
            capital_usd=capital,
            next_scheduled_live_utc=None,
            detail=f"armed 값 파싱 불가: {micro_request.get('armed')!r}",
            **base,
        )
    if capital is None or capital < 1 or capital > MICRO_MAX_CAPITAL_USD:
        return LiveMoneyState(
            status=LIVE_STATUS_BLOCKED,
            can_submit_real_orders=False,
            capital_usd=capital,
            next_scheduled_live_utc=None,
            detail=(
                f"capital_usd={micro_request.get('capital_usd')!r} 이 micro 한도 "
                f"1..{MICRO_MAX_CAPITAL_USD} 밖이거나 파싱 불가."
            ),
            **base,
        )
    if not armed:
        return LiveMoneyState(
            status=LIVE_STATUS_PREVIEW,
            can_submit_real_orders=False,
            capital_usd=capital,
            next_scheduled_live_utc=None,
            detail="armed:false — push/스케줄 모두 미리보기만, 실주문 0건.",
            **base,
        )
    if last_run and last_run.intent_gate_ok is False:
        return LiveMoneyState(
            status=LIVE_STATUS_BLOCKED,
            can_submit_real_orders=False,
            capital_usd=capital,
            next_scheduled_live_utc=None,
            detail=(
                "armed:true 이지만 최신 전략 의도 게이트가 실주문을 차단함: "
                f"{last_run.intent_gate_reason or 'reason absent'}."
            ),
            **base,
        )

    return LiveMoneyState(
        status=LIVE_STATUS_ARMED,
        can_submit_real_orders=True,
        capital_usd=capital,
        next_scheduled_live_utc=_next_micro_schedule(now),
        detail=(
            "센티넬 armed:true + 유효 자본. 다음 비-push 실행은 정규장·현금 preflight, "
            "손실 브레이커, K1 캡, K2 화이트리스트를 통과하면 실주문 단계에 도달한다."
        ),
        **base,
    )


def _pct_str(value: Decimal) -> str:
    """Decimal 퍼센트를 과학적 표기 없이 사람이 읽는 문자열로.

    Decimal.normalize() 는 50.00→'5E+1', 100.00→'1E+2' 처럼 지수 형태를 낼 수 있어
    운영자 보고서(단2=50%·단3=100%)에 깨져 보였다. 고정소수점(format f)으로 펼친 뒤
    의미 없는 0 만 떼어 '50'·'100'·'12.5' 처럼 항상 정상 표기한다.
    """
    s = format(value, "f")  # 고정소수점 — 지수 표기 절대 안 나옴
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def _capital_pct(rung: int) -> str:
    frac = RUNG_FRACTIONS.get(rung)
    if frac is None:
        return "?"
    return _pct_str(frac * 100)


def _safety_budget(
    *,
    reference_rung: int,
    account_nav: Decimal | None,
    deployed_capital: int | None,
    current_dd_pct: Decimal | None,
    dd_budget_pct: Decimal,
    prospective: bool,
) -> SafetyBudget:
    """기준 단의 배치(예정) 자본에 대한 방어선 예산을 계산(순수·결정론).

    강등 임계 = 예산/2, 정지 임계 = 예산. 낙폭은 배치 NAV 대비라 강등/정지 발동 시점의
    달러 손실 ≈ 임계% × 배치 자본(올림 — 위험을 과소평가하지 않는다). 배치 자본은 (배치
    중이면) deployed_capital, 아니면 단 비율 × 실계좌 NAV(자본 사다리와 같은 내림). NAV 도
    자본도 모르면 달러는 None(임계 % 만 의미 있음). current_dd_pct 가 있으면(배치 후) 임계
    까지 남은 %포인트(여유)를 낸다 — 음수면 이미 방어선 초과.
    """
    demote = dd_budget_pct / 2
    halt = dd_budget_pct
    frac = RUNG_FRACTIONS.get(reference_rung)

    capital: int | None
    if deployed_capital is not None and deployed_capital > 0:
        capital = deployed_capital
    elif account_nav is not None and account_nav > 0 and frac is not None:
        capital = int((account_nav * frac).to_integral_value(rounding=ROUND_FLOOR))
    else:
        capital = None

    if capital is None or capital <= 0:
        loss_demote = loss_halt = None
    else:
        cap_d = Decimal(capital)
        loss_demote = int(
            (cap_d * demote / 100).to_integral_value(rounding=ROUND_CEILING)
        )
        loss_halt = int((cap_d * halt / 100).to_integral_value(rounding=ROUND_CEILING))

    if current_dd_pct is None:
        margin_demote = margin_halt = None
    else:
        margin_demote = str(demote - current_dd_pct)
        margin_halt = str(halt - current_dd_pct)

    return SafetyBudget(
        reference_rung=reference_rung,
        capital_usd=capital,
        demote_dd_pct=str(demote),
        halt_dd_pct=str(halt),
        loss_at_demote_usd=loss_demote,
        loss_at_halt_usd=loss_halt,
        current_dd_pct=None if current_dd_pct is None else str(current_dd_pct),
        margin_to_demote_pct=margin_demote,
        margin_to_halt_pct=margin_halt,
        prospective=prospective,
    )


def _confidence_gates(
    psr: Decimal | None,
    dsr: Decimal | None,
    dsr_threshold: Decimal | None,
) -> list[GateCondition]:
    """엣지 신뢰도 게이트(PSR·DSR) — 값이 있을 때만(거짓 표시 0).

    이진 EDGE_CONFIRMED 만으로는 "겨우 넘었나(0.951) 강하게 넘었나(0.99)"를 알 수 없다.
    실제 돈이 들어가기 직전, 엣지가 *얼마나* 강한지를 확률로 보인다:
      · PSR = 참 샤프가 벤치마크보다 클 확률(스큐·첨도 보정).
      · DSR = 여러 설정을 시도한 다중검정까지 보정한 PSR(과적합 처벌, num_trials>1 일 때만).
    """
    gates: list[GateCondition] = []
    if psr is not None and dsr_threshold is not None:
        gates.append(
            GateCondition(
                "엣지 신뢰도(PSR)",
                GATE_PASS if psr >= dsr_threshold else GATE_FAIL,
                f"{psr}",
                f"≥ {dsr_threshold}",
                "참 샤프가 벤치마크보다 클 확률(스큐·첨도 보정). 높을수록 우연이 아닐 확신이 큼.",
            )
        )
    if dsr is not None and dsr_threshold is not None:
        gates.append(
            GateCondition(
                "디플레이티드 샤프(DSR)",
                GATE_PASS if dsr >= dsr_threshold else GATE_FAIL,
                f"{dsr}",
                f"≥ {dsr_threshold}",
                "여러 설정을 시도한 다중검정 보정 후에도 샤프가 0보다 유의해야 한다(과적합 배제).",
            )
        )
    return gates


def assess_money_path(
    *,
    ladder: dict | None,
    forward_verdict: dict | None,
    live_growth: dict | None = None,
    canary_armed: bool | None = None,
    promote_ready: dict | None = None,
    prior: dict | None = None,
    fingerprint: dict | None = None,
    micro_request: dict | None = None,
    micro_last_run: dict | None = None,
    dd_budget_pct: Decimal = DEFAULT_DD_BUDGET_PCT,
    now: datetime,
) -> MoneyPathReport:
    """발행된 사이드카 결정들로 첫-자본까지의 길을 종합(순수·결정론·읽기 전용).

    ladder: 자본 사다리 결정 JSON(edge-autoarm '결정 JSON').
    forward_verdict: 전진 판정 JSON(edge-autoarm 'forward 판정 JSON').
    live_growth: 라이브 실적 JSON(현재 단 진입 이후, 선택).
    canary_armed: 라이브 캐너리 무장 여부(rebalance-live-canary 사이드카, 선택).
    promote_ready: 승격 준비 JSON(헌법 VI 게이트, 선택).
    prior: 직전 money-path 사이드카에서 읽은 {'as_of_utc','n_obs'}(ETA 실측용, 선택).
    fingerprint: 검증 forward 설정 vs 라이브 배포 설정의 전략 지문 정합
        {'match': bool|None, 'diverged': [field...], 'live_path', 'validated_path'}(선택).
        자본 사다리가 지문 불일치면 어떤 단에서도 자본을 배치하지 않으므로(BLOCKED),
        이 입력으로 '엣지를 쌓아도 배포가 막히는' 분기를 미리 진단한다.
    micro_request/micro_last_run: 스펙 058 micro GTAA 별도 실거래 캐너리의 현재 센티넬과
        마지막 실행 증거. 기존 자본 사다리와 별개 실제 돈 경로라 최상위 상태로 표면화한다.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    as_of = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    live_money_state = assess_live_money_state(
        micro_request=micro_request,
        micro_last_run=micro_last_run,
        now=now,
    )

    ladder = ladder or {}
    forward_verdict = forward_verdict or {}

    action = ladder.get("action")
    current_rung = _int(ladder.get("current_rung")) or 0
    target_rung = _int(ladder.get("target_rung"))
    account_nav = _dec(ladder.get("account_nav_usd"))
    deployed_capital = _int(ladder.get("target_capital_usd"))
    live_dd = _dec(ladder.get("live_dd_pct"))
    live_obs = _int(ladder.get("live_obs"))

    verdict = forward_verdict.get("verdict")
    n_obs = _int(forward_verdict.get("n_obs"))
    min_obs = _int(forward_verdict.get("min_obs_required")) or PROMOTION_MIN_OBS
    beats_calmar = bool(forward_verdict.get("beats_benchmark_calmar"))
    dsr = _dec(forward_verdict.get("dsr"))
    dsr_threshold = _dec(forward_verdict.get("dsr_threshold"))
    psr = _dec(forward_verdict.get("psr_vs_benchmark"))  # 참 샤프>벤치마크 확률(신뢰도)
    # 자본 베이시스 정합 결과(cli.py forward-verdict 가 발행): 유효 스냅샷 수와 베이시스
    # 변경으로 제외된 스냅샷 수. 표본 안정성(churn) 진단 입력.
    legacy_excluded = _int(forward_verdict.get("legacy_snapshots_excluded"))
    snapshot_count = _int(forward_verdict.get("snapshot_count"))

    prior_n_obs = _int((prior or {}).get("n_obs"))
    prior_ts = (prior or {}).get("as_of_utc")
    prior_legacy = _int((prior or {}).get("legacy_excluded"))

    # 전략 지문 정합(검증 forward 설정 == 라이브 배포 설정). match: True/False/None(측정 불가).
    fp = fingerprint or {}
    fp_match = fp.get("match")  # True | False | None
    fp_diverged = [str(x) for x in (fp.get("diverged") or [])]
    fp_live = fp.get("live_path") or "라이브 배포 설정"
    fp_validated = fp.get("validated_path") or "검증 forward 설정"

    # 배치 자본(USD): 결정 JSON 에 있으면 그걸, 없으면 단 비율 × NAV.
    if deployed_capital is None and account_nav is not None:
        frac = RUNG_FRACTIONS.get(current_rung, Decimal("0"))
        deployed_capital = int(account_nav * frac)

    # ── 단계 분류 ──
    demote_threshold = dd_budget_pct / 2
    if action in (ACTION_BLOCKED, ACTION_DISABLED) or not verdict:
        stage = STAGE_BLOCKED
    elif action in (ACTION_DEMOTE, ACTION_HALT):
        stage = STAGE_DEFENDED
    elif action == ACTION_PROMOTE or current_rung >= 1 or (target_rung or 0) >= 1:
        stage = STAGE_DEPLOYED
    elif verdict == EDGE_CONFIRMED:
        stage = STAGE_EDGE_CONFIRMED
    elif verdict == NO_EDGE:
        stage = STAGE_NO_EDGE_YET
    else:  # INSUFFICIENT_DATA 또는 기타
        stage = STAGE_ACCUMULATING

    # PROMOTE 면 보고 기준 단은 target.
    report_rung = target_rung if (action == ACTION_PROMOTE and target_rung) else current_rung

    # ── 자본 방어선 예산('내려가는 길'을 연속 값으로) ──
    # 미배치(단0)면 첫 자본 단(1) 기준 예상 예산, 배치 중이면 현재/목표 단 실측, 방어
    # 중이면 초과한 그 단 기준. BLOCKED(길을 못 읽음)면 방어선도 None(거짓 숫자 0).
    safety: SafetyBudget | None
    if stage == STAGE_BLOCKED:
        safety = None
    elif current_rung < 1:  # 단0 — 첫 자본이 들어가면 어떤 다운사이드 예산인지 미리.
        safety = _safety_budget(
            reference_rung=1,
            account_nav=account_nav,
            deployed_capital=None,
            current_dd_pct=None,
            dd_budget_pct=dd_budget_pct,
            prospective=True,
        )
    elif stage == STAGE_DEFENDED:  # 방어 발동 — 초과한 '그 단'(current_rung) 기준으로 본다.
        safety = _safety_budget(
            reference_rung=current_rung,
            account_nav=account_nav,
            deployed_capital=None,
            current_dd_pct=live_dd,
            dd_budget_pct=dd_budget_pct,
            prospective=False,
        )
    else:  # DEPLOYED — 배치 중 실측(목표 단 자본·현재 낙폭).
        safety = _safety_budget(
            reference_rung=report_rung,
            account_nav=account_nav,
            deployed_capital=deployed_capital,
            current_dd_pct=live_dd,
            dd_budget_pct=dd_budget_pct,
            prospective=False,
        )

    gates: list[GateCondition] = []
    eta = EtaProjection(ETA_NONE, None, None, None, None, "해당 없음.")

    if stage == STAGE_BLOCKED:
        if fp_match is False:
            # 차단 원인을 지문 불일치로 특정 — 운영자가 정확히 무엇을 고칠지 안다.
            diff_txt = ", ".join(fp_diverged) or "항목 불명"
            headline = (
                f"🛑 자본 사다리 차단 — 배포 전략이 전진 검증 전략과 다르다(지문 불일치: "
                f"{diff_txt}). 엣지를 아무리 쌓아도 자본이 들어가지 않는다."
            )
            blocking = (
                f"전략 지문 불일치({diff_txt}) — 라이브 배포({fp_live})와 "
                f"전진 검증({fp_validated})의 해당 항목을 일치시켜야 사다리가 자본을 배치한다. "
                "검증하지 않은 전략엔 어떤 단에서도 배치 안 함(헌법 안전 자세)."
            )
        else:
            headline = "🛑 자본 사다리 게이트가 차단/정지 상태 — 길을 읽을 수 없다(점검 필요)."
            blocking = (
                f"자본 사다리 결정={action!r}"
                + (f", 전진 판정={verdict!r}" if verdict else " (전진 판정 JSON 없음)")
                + " — 정합성 불일치·NAV 조회 불능·킬스위치 가능."
            )
        gates.append(
            GateCondition(
                "자본 사다리 게이트",
                GATE_FAIL,
                f"action={action}",
                "WAIT_EDGE/STAY/PROMOTE 등 정상 결정",
                "BLOCKED/DISABLED 는 안전 자세(상태 무변경). 사유는 edge-autoarm 사이드카 확인.",
            )
        )
        next_action = (
            "자율 시스템은 안전 자세로 멈춰 있다(돈 0 이동). edge-autoarm 사이드카의 사유를 "
            "보고 정합성/계좌 NAV/킬스위치를 점검하라."
        )
    elif stage == STAGE_ACCUMULATING:
        eta = _accumulation_eta(
            n_obs=n_obs,
            min_obs=min_obs,
            as_of=now,
            prior_n_obs=prior_n_obs,
            prior_ts=prior_ts,
            legacy_excluded=legacy_excluded,
            snapshot_count=snapshot_count,
            prior_legacy=prior_legacy,
        )
        churning = eta.sample_stability == SAMPLE_CHURNING
        if eta.convergence == CONV_REGRESSED:
            headline = (
                "⚠ 단0(자본 0%) — 전진 시계 리셋(관측 줄어듦, 자본 베이시스 변경"
                + (f": {eta.legacy_excluded}개 스냅샷 제외" if churning else " 추정")
                + f"). 누적 재시작 — 첫-자본 ETA 가 뒤로 밀림({n_obs}/{min_obs} 관측)."
            )
        elif churning:
            # 관측이 정체로 보여도 진짜 원인은 자본 베이시스가 자꾸 바뀌는 것 — 새 스냅샷이
            # 계속 제외돼 유효 표본이 안 늘어난다. 생존·수렴 감시가 못 짚는 사각지대의 핵심.
            headline = (
                f"⚠ 단0(자본 0%) — 전진 표본 흔들림: 유효 스냅샷 {eta.snapshot_count}개뿐"
                f"({eta.legacy_excluded}개 베이시스 변경 제외, 직전보다 늘어남). 새 스냅샷이 "
                f"계속 떨궈져 관측이 안 쌓인다({n_obs}/{min_obs}) — 측정 기준 고정 필요."
            )
        elif eta.convergence == CONV_STALLED:
            headline = (
                f"⚠ 단0(자본 0%) — 전진 엣지 누적 정체({n_obs}/{min_obs} 관측, 직전 대비 "
                "안 늘어남). 지속되면 첫-자본 ETA 가 뒤로 밀린다(전진 페이퍼 점검)."
            )
        else:
            headline = (
                f"⏳ 단0(자본 0%) — 전진 엣지 누적 중({n_obs}/{min_obs} 관측). "
                f"추정 첫-자본 ≈ {eta.projected_date or '미정'}. 정상(시간 게이트)."
            )
        blocking = f"전진 관측 부족: {n_obs}/{min_obs} (통계적 유의까지 더 쌓여야 함)."
        gates.append(
            GateCondition(
                "전진 관측 수",
                GATE_PENDING,
                f"{n_obs}",
                f"≥ {min_obs}",
                "전진 페이퍼가 매 거래일 1개씩 쌓는다. 정체/리셋이면 '전진 시계 수렴'이 잡는다.",
            )
        )
        conv_status = {
            CONV_CONVERGING: GATE_PASS,
            CONV_UNKNOWN: GATE_PENDING,
            CONV_STALLED: GATE_PENDING,
            CONV_REGRESSED: GATE_FAIL,
        }.get(eta.convergence, GATE_PENDING)
        gates.append(
            GateCondition(
                "전진 시계 수렴",
                conv_status,
                eta.convergence,
                "converging(매 거래일 +1)",
                "직전 money-path 사이드카 대비 관측 증감. 정체(stalled)/리셋(regressed)이면 "
                "살아있어도 수렴 못 하는 것 — 생존 감시(스펙 051)가 못 잡는 사각지대를 메운다.",
            )
        )
        # 전진 표본 안정성(자본 베이시스 churn) — 수렴과 직교. legacy 정보가 있을 때만
        # 추가(없으면 게이트 무변경, 거짓 경보 0 + 기존 사이드카 호환).
        if legacy_excluded is not None:
            sample_status = {
                SAMPLE_STABLE: GATE_PASS,
                SAMPLE_SETTLED: GATE_PASS,
                SAMPLE_CHURNING: GATE_FAIL,
            }.get(eta.sample_stability, GATE_PENDING)
            if eta.sample_stability == SAMPLE_STABLE:
                sample_current = "안정(제외 0)"
            elif eta.sample_stability == SAMPLE_CHURNING:
                sample_current = (
                    f"흔들림: {eta.legacy_excluded}개 제외(직전↑), 유효 {eta.snapshot_count}"
                )
            else:  # SETTLED
                sample_current = (
                    f"정리됨: {eta.legacy_excluded}개 제외(추가 없음), 유효 "
                    f"{eta.snapshot_count}"
                )
            gates.append(
                GateCondition(
                    "전진 표본 안정성(베이시스)",
                    sample_status,
                    sample_current,
                    "같은 자본 베이시스로 연속 누적(제외 증가 없음)",
                    "forward 판정의 legacy_snapshots_excluded(자본 베이시스가 바뀌어 떨궈진 "
                    "과거 스냅샷). 직전보다 늘면 베이시스가 또 바뀌어 새 스냅샷이 제외되는 중 — "
                    "관측이 안 쌓이는 진짜 원인(수렴 감시가 '정체'로만 보는 사각지대).",
                )
            )
        gates.append(
            GateCondition(
                "전진 판정",
                GATE_PENDING,
                f"{verdict}",
                f"{EDGE_CONFIRMED}",
                "관측 충족 후 엣지(벤치마크 대비 칼마·디플레이티드 샤프)를 평가한다.",
            )
        )
        next_action = (
            "자율 시스템은 매 거래일 전진 관측을 쌓는다. 최소 관측 도달 후 엣지가 "
            f"{EDGE_CONFIRMED} 되면 자본 사다리가 단0→단1(NAV 25%)을 자율 무장한다"
            "(헌법 X.4 상시 위임). 운영자 전용은 입금(NAV 상한)·킬스위치뿐."
        )
    elif stage == STAGE_NO_EDGE_YET:
        headline = (
            f"➖ 단0 — 관측({n_obs})은 충분하나 엣지가 기준 미달({verdict}). "
            "아직 배치할 검증된 엣지가 없다(정상 — 과적합 방어)."
        )
        blocking = "엣지 미확정: 전진 성과가 벤치마크/유의 기준을 넘지 못함."
        gates.append(
            GateCondition(
                "벤치마크 대비 칼마",
                GATE_PASS if beats_calmar else GATE_FAIL,
                "넘음" if beats_calmar else "못 넘음",
                "전략 칼마 > 벤치마크 칼마",
                "자본 방어(낙폭 대비 수익)가 벤치마크보다 나아야 한다.",
            )
        )
        gates.extend(_confidence_gates(psr, dsr, dsr_threshold))
        next_action = (
            "자율 시스템은 계속 전진 관측을 쌓으며 엣지를 재평가한다. 전략 자체를 갈아엎으면 "
            "지문이 바뀌어 누적이 리셋되므로, 후보 전략은 전진 토너먼트에 *추가*로 검증한다."
        )
    elif stage == STAGE_EDGE_CONFIRMED:
        conf = f", 신뢰도 PSR {psr}" if psr is not None else ""
        headline = (
            f"🟢 전진 엣지 확정(EDGE_CONFIRMED{conf}) — 첫 자본(단0→단1, NAV 25%) 배치 임박."
        )
        blocking = (
            "막는 것 없음 — 자본 사다리가 다음 게이트 실행에서 단1을 자율 무장한다"
            "(헌법 X.4 상시 위임). 운영자 전용은 입금(NAV 상한)·킬스위치뿐."
        )
        gates.append(
            GateCondition(
                "전진 판정", GATE_PASS, f"{verdict}", f"{EDGE_CONFIRMED}", "엣지 확정."
            )
        )
        # 실제 돈이 들어가기 직전 — 엣지가 *얼마나* 강한지 신뢰도(PSR/DSR)로 보인다.
        gates.extend(_confidence_gates(psr, dsr, dsr_threshold))
        gates.append(
            GateCondition(
                "캐너리 무장",
                GATE_PASS if canary_armed else GATE_PENDING,
                "예" if canary_armed else "아니오(드라이런)",
                "무장(실주문)",
                "자본 사다리가 EDGE_CONFIRMED+지문 정합 시 자율 무장(센티넬 PR 자동 머지, "
                "헌법 X.4). 운영자가 직접 켜지 않는다 — 입금·킬스위치만 운영자 몫.",
            )
        )
        next_action = (
            "자본 사다리가 단1(NAV 25%)을 자율 무장한다(센티넬 PR 자동 머지). 실제 실주문은 "
            "시장시간 스케줄에서 시작된다(헌법 X.4 상시 위임). 운영자 전용은 입금(NAV 상한)·"
            "킬스위치뿐."
        )
    elif stage == STAGE_DEPLOYED:
        days_in_rung = _dec((live_growth or {}).get("period_days"))
        obs_ok = live_obs is not None and live_obs >= PROMOTION_MIN_OBS
        days_ok = days_in_rung is not None and days_in_rung >= PROMOTION_MIN_CALENDAR_DAYS
        dd_ok = live_dd is not None and live_dd < demote_threshold
        headline = (
            f"💰 자본 배치됨 — 단{report_rung}(NAV {_capital_pct(report_rung)}%, "
            f"${deployed_capital or 0}). 다음 단 게이트 추적 중."
        )
        if report_rung >= MAX_RUNG:
            blocking = "최상단(단3, NAV 100%) — 더 올릴 단 없음. 낙폭 예산만 방어."
        else:
            blocking = "다음 단 승격: 라이브 관측 ≥20 + 경과 ≥27일 + 낙폭 < 예산/2 (셋 다)."
        gates.append(
            GateCondition(
                "라이브 관측 수",
                GATE_PASS if obs_ok else GATE_PENDING,
                f"{live_obs if live_obs is not None else '?'}",
                f"≥ {PROMOTION_MIN_OBS}",
                "현재 단 진입 이후 라이브 NAV 관측.",
            )
        )
        gates.append(
            GateCondition(
                "경과일",
                GATE_PASS
                if days_ok
                else (GATE_NA if days_in_rung is None else GATE_PENDING),
                f"{days_in_rung}" if days_in_rung is not None else "측정 불가",
                f"≥ {PROMOTION_MIN_CALENDAR_DAYS}일",
                "현재 단 진입 후 경과 캘린더일(라이브 실적 JSON 의 period_days).",
            )
        )
        gates.append(
            GateCondition(
                "낙폭 < 예산/2",
                GATE_PASS if dd_ok else (GATE_FAIL if live_dd is not None else GATE_NA),
                f"{live_dd}%" if live_dd is not None else "측정 불가",
                f"< {demote_threshold}%",
                f"낙폭 ≥ 예산/2({demote_threshold}%) 강등, ≥ 예산({dd_budget_pct}%) 정지.",
            )
        )
        next_action = (
            "자율 시스템은 라이브 실적을 쌓으며 세 증거(관측·경과일·낙폭)가 모두 차면 다음 "
            "단을 자동 승격한다. 낙폭이 예산/2 를 넘으면 증거 없이 즉시 강등."
        )
    else:  # STAGE_DEFENDED
        headline = (
            f"🛡 자본 방어 발동({action}) — 낙폭으로 자본 회수. 단{current_rung}→{target_rung}."
        )
        blocking = (
            "방어 중 — 낙폭이 예산 한계를 넘어 자동 강등/정지. 재진입은 전진 재검증부터."
        )
        gates.append(
            GateCondition(
                "라이브 낙폭",
                GATE_FAIL,
                f"{live_dd}%" if live_dd is not None else "측정 불가",
                f"< 예산/2({demote_threshold}%) 유지",
                f"강등 임계 {demote_threshold}% / 정지 임계 {dd_budget_pct}%(운영자 소유 예산).",
            )
        )
        next_action = (
            "자율 시스템이 자본을 한 단(또는 무장 해제)으로 즉시 회수했다(증거 불필요한 하향). "
            "재배치는 전진 엣지 재검증 → 사다리 재승격 경로로만."
        )

    # 전략 지문 게이트 — 입력이 있을 때만 추가(없으면 게이트 무변경, 거짓 경보 0).
    # 사다리(capital_ladder.decide_ladder)가 매 단에서 검사하는 바로 그 정합을, 운영자가
    # '엣지를 쌓아도 배포가 막히는지'를 미리 볼 수 있게 표면화한다(자본 임박 전 진단).
    if fp_match is not None:
        if fp_match:
            fp_status, fp_current = GATE_PASS, "일치"
        else:
            fp_status = GATE_FAIL
            fp_current = "불일치: " + (", ".join(fp_diverged) or "항목 불명")
        gates.append(
            GateCondition(
                "전략 지문 정합(검증=배포)",
                fp_status,
                fp_current,
                "라이브 배포 설정 == 전진 검증 설정",
                "지문(유니버스·가중·추세 게이트 등, 캡/자본 제외)이 다르면 자본 사다리가 "
                "어떤 단에서도 자본을 배치하지 않는다(BLOCKED). 두 TOML 을 일치시켜야 "
                "첫 자본이 들어간다.",
            )
        )

    return MoneyPathReport(
        schema_version=SCHEMA_VERSION,
        as_of_utc=as_of,
        stage=stage,
        headline=headline,
        blocking_gate=blocking,
        current_rung=report_rung,
        capital_pct=_capital_pct(report_rung),
        account_nav_usd=None if account_nav is None else str(account_nav),
        deployed_capital_usd=deployed_capital,
        canary_armed=canary_armed,
        live_money_state=live_money_state,
        gates=gates,
        eta=eta,
        safety=safety,
        next_action=next_action,
    )


__all__ = [
    "CONV_CONVERGING",
    "CONV_REGRESSED",
    "CONV_STALLED",
    "CONV_UNKNOWN",
    "SAMPLE_CHURNING",
    "SAMPLE_SETTLED",
    "SAMPLE_STABLE",
    "SAMPLE_UNKNOWN",
    "ETA_MEASURED",
    "ETA_NOMINAL",
    "ETA_NONE",
    "GATE_FAIL",
    "GATE_NA",
    "GATE_PASS",
    "GATE_PENDING",
    "SCHEMA_VERSION",
    "LIVE_STATUS_ARMED",
    "LIVE_STATUS_BLOCKED",
    "LIVE_STATUS_PREVIEW",
    "LIVE_STATUS_UNKNOWN",
    "STAGE_ACCUMULATING",
    "STAGE_BLOCKED",
    "STAGE_DEFENDED",
    "STAGE_DEPLOYED",
    "STAGE_EDGE_CONFIRMED",
    "STAGE_NO_EDGE_YET",
    "EtaProjection",
    "GateCondition",
    "LiveMoneyState",
    "MicroGtaaRunEvidence",
    "MoneyPathReport",
    "SafetyBudget",
    "assess_live_money_state",
    "assess_money_path",
]

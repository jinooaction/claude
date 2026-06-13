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

안전 경계(중요):
  순수·결정론·비커널·읽기 전용. 주문 0건, 돈 0 이동. 이건 *보고/가시성*이지 거래나
  자본 변경이 아니다. 실제 자본 배치는 자본 사다리 게이트(edge-autoarm.yml)가, 실주문은
  라이브 캐너리 스케줄이, 라이브 전환은 운영자 게이트(헌법 X.4)가 한다. 이 모듈은 그
  결정들을 *읽어 설명할* 뿐 어떤 것도 일으키지 않는다. 또한 누적이 조용히 멈추면(전진
  엣지 동결) ETA 가 무한대로 벌어져 드러나므로, 스펙 051 생존 감시와 결을 같이한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from auto_invest.portfolio.capital_ladder import (
    DEFAULT_DD_BUDGET_PCT,
    MAX_RUNG,
    PROMOTION_MIN_CALENDAR_DAYS,
    PROMOTION_MIN_OBS,
    RUNG_FRACTIONS,
)

SCHEMA_VERSION = "1.0"

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
    gates: list[GateCondition]
    eta: EtaProjection
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
            "gates": [g.to_dict() for g in self.gates],
            "eta": self.eta.to_dict(),
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
            f"# 첫-자본까지의 길 (as of {self.as_of_utc}) — 읽기 전용, 돈 0 이동",
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
            lines += [
                f"- 남은 관측: **{self.eta.obs_remaining}** 개 "
                f"(속도 ~{self.eta.obs_per_trading_day} 관측/거래일, 근거={self.eta.basis})",
                f"- 추정: 약 **{self.eta.trading_days_remaining} 거래일** 후 "
                f"→ **{self.eta.projected_date}** 경",
                f"- 가정: {self.eta.assumption}",
            ]
        lines += [
            "",
            "## 다음 행동",
            "",
            f"- {self.next_action}",
            "",
            "⚠ 이건 종합 보고다(읽기 전용). 거래·자본 변경 없음 — 실제 배치는 자본 사다리 "
            "게이트가, 라이브 전환은 운영자 게이트(헌법 X.4)가 한다.",
        ]
        return "\n".join(lines)

    def _armed_text(self) -> str:
        if self.canary_armed is None:
            return "(불명)"
        return "예(armed)" if self.canary_armed else "아니오(드라이런)"


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


def _accumulation_eta(
    *,
    n_obs: int | None,
    min_obs: int | None,
    as_of: datetime,
    prior_n_obs: int | None,
    prior_ts: str | None,
) -> EtaProjection:
    """전진 관측 누적 속도로 최소 관측 수 도달 시점을 추정.

    measured: 직전 사이드카(prior_n_obs, prior_ts) 대비 실측 속도(거래일당 관측).
    nominal: 직전이 없거나 속도가 비양수면 전진 스케줄 가정(거래일당 ~1 관측).
    """
    if n_obs is None or min_obs is None:
        return EtaProjection(
            basis=ETA_NONE,
            obs_remaining=None,
            obs_per_trading_day=None,
            trading_days_remaining=None,
            projected_date=None,
            assumption="전진 판정 JSON 에 관측 수가 없어 추정 불가.",
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
        )

    as_of_date = as_of.date()
    rate = NOMINAL_OBS_PER_TRADING_DAY
    basis = ETA_NOMINAL
    assumption = "전진 페이퍼는 평일 22:30 UTC 1회 → 거래일당 ~1 관측 가정(실측 누적 전 기본값)."

    prior_dt = _parse_iso(prior_ts)
    if prior_dt is not None and prior_n_obs is not None and n_obs > prior_n_obs:
        td = _trading_days_between(prior_dt.date(), as_of_date)
        if td > 0:
            measured = (n_obs - prior_n_obs) / td
            if measured > 0:
                rate = measured
                basis = ETA_MEASURED
                assumption = (
                    f"직전 사이드카({prior_dt.date().isoformat()}, 관측 {prior_n_obs}) "
                    f"대비 실측 누적 속도 {measured:.2f} 관측/거래일."
                )

    calendar_days, projected = _project_trading_date(as_of_date, obs_remaining, rate)
    return EtaProjection(
        basis=basis,
        obs_remaining=obs_remaining,
        obs_per_trading_day=rate,
        trading_days_remaining=_trading_days_between(as_of_date, projected),
        projected_date=projected.isoformat(),
        assumption=assumption,
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


def _capital_pct(rung: int) -> str:
    frac = RUNG_FRACTIONS.get(rung)
    if frac is None:
        return "?"
    return str((frac * 100).normalize())


def assess_money_path(
    *,
    ladder: dict | None,
    forward_verdict: dict | None,
    live_growth: dict | None = None,
    canary_armed: bool | None = None,
    promote_ready: dict | None = None,
    prior: dict | None = None,
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
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    as_of = now.strftime("%Y-%m-%dT%H:%M:%SZ")

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

    prior_n_obs = _int((prior or {}).get("n_obs"))
    prior_ts = (prior or {}).get("as_of_utc")

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

    gates: list[GateCondition] = []
    eta = EtaProjection(ETA_NONE, None, None, None, None, "해당 없음.")

    if stage == STAGE_BLOCKED:
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
        )
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
                "전진 페이퍼가 매 거래일 1개씩 쌓는다. 동결되면 ETA 가 무한대로 벌어진다.",
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
            f"{EDGE_CONFIRMED} 되면 자본 사다리가 단0→단1(NAV 25%)을 자동 제안한다. "
            "라이브 실주문 전환만 운영자 게이트(헌법 X.4)."
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
        if dsr is not None and dsr_threshold is not None:
            gates.append(
                GateCondition(
                    "디플레이티드 샤프(DSR)",
                    GATE_PASS if dsr >= dsr_threshold else GATE_FAIL,
                    f"{dsr}",
                    f"≥ {dsr_threshold}",
                    "다중검정 보정 후에도 샤프가 0보다 유의해야 한다(우연 배제).",
                )
            )
        next_action = (
            "자율 시스템은 계속 전진 관측을 쌓으며 엣지를 재평가한다. 전략 자체를 갈아엎으면 "
            "지문이 바뀌어 누적이 리셋되므로, 후보 전략은 전진 토너먼트에 *추가*로 검증한다."
        )
    elif stage == STAGE_EDGE_CONFIRMED:
        headline = (
            "🟢 전진 엣지 확정(EDGE_CONFIRMED) — 첫 자본(단0→단1, NAV 25%) 배치 임박."
        )
        blocking = (
            "막는 것 없음 — 자본 사다리가 다음 게이트 실행에서 단1을 자동 제안한다. "
            "실주문 전환(캐너리 무장)만 운영자 게이트."
        )
        gates.append(
            GateCondition(
                "전진 판정", GATE_PASS, f"{verdict}", f"{EDGE_CONFIRMED}", "엣지 확정."
            )
        )
        gates.append(
            GateCondition(
                "캐너리 무장",
                GATE_PASS if canary_armed else GATE_PENDING,
                "예" if canary_armed else "아니오(드라이런)",
                "무장(실주문)",
                "무장은 돈 움직이는 운영자 게이트(automation/rebalance-live.request).",
            )
        )
        next_action = (
            "자본 사다리가 단1(NAV 25%)을 제안한다(센티넬 PR). 실제 실주문은 라이브 캐너리 "
            "무장 + 시장시간 스케줄에서 시작된다 — 무장은 운영자 게이트."
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
        gates=gates,
        eta=eta,
        next_action=next_action,
    )


__all__ = [
    "ETA_MEASURED",
    "ETA_NOMINAL",
    "ETA_NONE",
    "GATE_FAIL",
    "GATE_NA",
    "GATE_PASS",
    "GATE_PENDING",
    "SCHEMA_VERSION",
    "STAGE_ACCUMULATING",
    "STAGE_BLOCKED",
    "STAGE_DEFENDED",
    "STAGE_DEPLOYED",
    "STAGE_EDGE_CONFIRMED",
    "STAGE_NO_EDGE_YET",
    "EtaProjection",
    "GateCondition",
    "MoneyPathReport",
    "assess_money_path",
]

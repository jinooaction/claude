"""스펙 050 — 자본 사다리 (evidence-gated capital ladder, 순수·결정론·읽기 전용 판정).

운영자 위임(2026-06-11): "1·2·3 모두 세계 최고 수준이 목표. 3번(자본·수단)도 자동과
자율에 맡길 것. 기준은 계좌 잔고와 포트폴리오." — 자본 배치 규모 결정을 운영자 단건
승인에서 **증거 게이트 공식**으로 위임한다(헌법 X.4 v5.0.0 개정). 운영자가 정하는 것은
낙폭 예산(기본 20%) 하나이고, 시스템은 그 예산 아래에서 실계좌 순자산(NAV)의 단계적
배치(사다리)를 자율 운영한다.

사다리 구조 (LP/GP 모형 — 내려가는 건 즉시, 올라가는 건 증거 필요):

  단(rung)  배치 비율(실계좌 NAV 대비)   진입 조건
  0         0%   (무장 해제)            — (강등/정지의 종착점)
  1         20%  (탐색 캐너리)          정확 배포전략 홀드아웃 + forward floor + hardening
  2         25%                         EDGE_CONFIRMED + 단 1 live 증거
  3         50%                         단 2에서 같은 live 증거 재충족
  4         100%                        단 3에서 같은 live 증거 재충족

  강등: 단 진입 후 라이브 낙폭 ≥ 예산/2 (기본 10%) → 한 단 아래로(단 1이면 0 = 무장 해제).
  정지: 단 진입 후 라이브 낙폭 ≥ 예산   (기본 20%) → 단 0 + 무장 해제.
  재사이징: 단 유지 중 실계좌 NAV 가 ±10% 이상 변하면(입금/성장) 자본만 재계산(RESIZE)
            — 운영자 입금이 다음 게이트 실행에서 자동 반영된다.

이 모듈은 **결정만** 한다 — 주문 0건, 돈 0 이동, 네트워크 0. 결정의 실행(센티넬 PR)은
게이트 워크플로(forward-edge-autoarm.yml)가, 실주문은 rebalance-live-canary.yml 의
시장시간 스케줄이 한다. 빠른 방어선은 여전히 스펙 014 서킷 브레이커(장중, 워커 레벨) —
사다리는 그 위의 *느린 거버너*다(일 1회, 자본 규모).

안전 원칙 (autoarm 과 동일한 fail-safe 자세):
  1. 파싱 실패·모호·증거 부족 = 현상 유지(STAY)/차단(BLOCKED), **절대 승격 아님**.
  2. 검증=배치 정합: 라이브 설정의 전략 지문이 검증 앙상블과 다르면 어떤 단에서도 BLOCKED.
  3. 강등·정지는 증거 없이도(낙폭 하나로) 즉시, 승격은 세 증거(관측 수·경과일·낙폭) 전부.
  4. 킬스위치(automation/AUTOARM_DISABLED)는 사다리 전체를 멈춘다.
  5. 낙폭 예산 자체는 운영자 소유 — 코드 기본값(20%)을 바꾸는 것은 운영자 결정.

헌법 X.4(v5.0.0): 자본 사다리는 운영자의 상시 위임에 따른 자율 운영이다. 비위임 불변
(I 캡 체계·II 화이트리스트·IV 감사·V 시크릿·VI 단계 승격 구조·VIII.A 장중 배포 금지·
스펙 014 서킷 브레이커)은 그대로다. 입금(은행 이체)은 물리적으로 운영자만 가능하다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, Decimal

from auto_invest.config.rules import PortfolioRebalanceConfig
from auto_invest.portfolio.autoarm import (
    EDGE_CONFIRMED,
    parse_sentinel,
    strategy_fingerprint,
)

# ---- 사다리 상수 (스펙 050 — 바꾸려면 스펙/헌법 개정 절차) ----
RUNG_FRACTIONS: dict[int, Decimal] = {
    0: Decimal("0"),
    1: Decimal("0.20"),
    2: Decimal("0.25"),
    3: Decimal("0.50"),
    4: Decimal("1.00"),
}
MAX_RUNG = 4

# 운영자 낙폭 예산(2026-06-11 위임 계약, 기본 20%). 강등은 예산/2, 정지는 예산.
DEFAULT_DD_BUDGET_PCT = Decimal("20")

# 승격 증거: 현재 단에서 라이브 NAV 관측 ≥ 20 개 + ≥ 27 캘린더일(≈ 20 거래일) 경과.
PROMOTION_MIN_OBS = 20
PROMOTION_MIN_CALENDAR_DAYS = 27

# 단 유지 중 실계좌 NAV 가 이 비율 이상 변하면 자본 재계산(입금/성장 자동 반영).
RESIZE_DRIFT_PCT = Decimal("10")

# ---- 결정 라벨 ----
ACTION_PROMOTE = "PROMOTE"  # 한 단 위로 (증거 충족)
ACTION_STAY = "STAY"  # 현상 유지 (증거 부족 또는 이상 없음)
ACTION_DEMOTE = "DEMOTE"  # 한 단 아래로 (낙폭 ≥ 예산/2)
ACTION_HALT = "HALT"  # 단 0 + 무장 해제 (낙폭 ≥ 예산)
ACTION_RESIZE = "RESIZE"  # 단 유지, 자본만 재계산 (계좌 NAV 드리프트)
ACTION_WAIT_EDGE = "WAIT_EDGE"  # 단 0, forward 미확정 → 보류 (autoarm WAIT 동치)
ACTION_BLOCKED = "BLOCKED"  # 정합성/입력 불능 → 아무것도 안 함
ACTION_DISABLED = "DISABLED"  # 킬스위치


@dataclass(frozen=True)
class LadderDecision:
    """자본 사다리의 한 줄 결정 — 헌법 X.4 v5.0.0 포렌식 증거."""

    action: str
    current_rung: int
    target_rung: int
    reason: str
    account_nav_usd: Decimal | None
    target_capital_usd: int | None  # 센티넬에 쓸 자본 (rung 0 이면 None)
    live_dd_pct: Decimal | None  # 단 진입 후 라이브 낙폭 (증거)
    live_obs: int | None  # 단 진입 후 라이브 관측 수 (증거)
    new_sentinel_text: str | None  # 센티넬 변경이 필요할 때만 채워짐

    SCHEMA_VERSION = "1.0"

    @property
    def sentinel_changes(self) -> bool:
        return self.new_sentinel_text is not None

    def to_json_dict(self) -> dict:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "action": self.action,
            "current_rung": self.current_rung,
            "target_rung": self.target_rung,
            "reason": self.reason,
            "account_nav_usd": (
                None if self.account_nav_usd is None else str(self.account_nav_usd)
            ),
            "target_capital_usd": self.target_capital_usd,
            "live_dd_pct": None if self.live_dd_pct is None else str(self.live_dd_pct),
            "live_obs": self.live_obs,
        }


# ---- 센티넬 사다리 필드 (autoarm 의 armed/capital/run_seq 에 추가) ----
_RUNG_RE = re.compile(r"^ladder_rung:\s*(\S+)\s*$", re.MULTILINE)
_RUNG_ENTERED_RE = re.compile(r"^rung_entered:\s*(\S+)\s*$", re.MULTILINE)
_ACCOUNT_NAV_RE = re.compile(r"^account_nav_usd:\s*(\S+)\s*$", re.MULTILINE)


def parse_ladder_fields(text: str) -> tuple[int | None, date | None, Decimal | None]:
    """센티넬에서 (ladder_rung, rung_entered, account_nav_usd) 를 보수적으로 읽는다.

    파싱 못 한 값은 None — 호출자가 fail-safe 기본값을 정한다(armed:true 인데 rung 이
    없으면 단 1 로 취급: 옛 autoarm 무장 센티넬과의 하위 호환).
    """
    rung: int | None = None
    m = _RUNG_RE.search(text)
    if m:
        try:
            rung = int(m.group(1))
        except (ValueError, TypeError):
            rung = None
    entered: date | None = None
    m = _RUNG_ENTERED_RE.search(text)
    if m:
        try:
            entered = date.fromisoformat(m.group(1))
        except (ValueError, TypeError):
            entered = None
    nav: Decimal | None = None
    m = _ACCOUNT_NAV_RE.search(text)
    if m:
        try:
            nav = Decimal(m.group(1))
        except ArithmeticError:
            nav = None
    return rung, entered, nav


def rung_capital_usd(rung: int, account_nav_usd: Decimal) -> int:
    """단 비율 × 실계좌 NAV → 정수 USD (내림 — 보수적)."""
    frac = RUNG_FRACTIONS[rung]
    return int((account_nav_usd * frac).to_integral_value(rounding=ROUND_FLOOR))


def render_ladder_sentinel(
    *,
    rung: int,
    capital_usd: int,
    account_nav_usd: Decimal,
    rung_entered: date,
    run_seq: int,
    dd_budget_pct: Decimal,
    evidence: str,
) -> str:
    """사다리 상태를 담은 무장 센티넬 본문 (rung ≥ 1 = armed:true, rung 0 = armed:false).

    rebalance-live-canary.yml 이 파싱하는 라인(`armed:`, `capital_usd:`,
    `account_nav_usd:`)을 유지하고, 사다리 필드(`ladder_rung:`, `rung_entered:`)와
    포렌식 헤더(위임 근거·증거·정지 수단)를 단다. 머지 커밋이 X.4 v5.0.0 기록이다.
    """
    armed = rung >= 1
    return (
        "# 라이브 캐너리 포트폴리오 무장 센티넬 (스펙 040; 스펙 050 자본 사다리가 갱신).\n"
        "#\n"
        "# 이 파일이 main 에 머지되면 rebalance-live-canary.yml 워크플로가 발화한다.\n"
        "#   - armed: false → 드라이런 미리보기만(실주문 0건).\n"
        "#   - armed: true  → 실주문(시장시간 스케줄에서만). 실제 돈 이동.\n"
        "#\n"
        "# 🪜 이 상태는 스펙 050 자본 사다리(증거 게이트 공식)가 결정했다 — 운영자 위임\n"
        '#   (2026-06-11): "자본·수단도 자동과 자율에 맡긴다. 기준은 계좌 잔고와 포트폴리오."\n'
        "#   헌법 X.4 v7.0.0. 사다리: 단0=0% → 단1=20% 탐색 → 단2=25% → "
        "단3=50% → 단4=100% (실계좌 NAV 대비).\n"
        "#   승격 = 관측 ≥20 + ≥27일 + 낙폭 < 예산/2. 강등 = 낙폭 ≥ 예산/2(즉시).\n"
        "#   정지 = 낙폭 ≥ 예산(즉시, 무장 해제). 재사이징 = 계좌 NAV ±10% 드리프트.\n"
        "#\n"
        f"# 증거: {evidence}\n"
        "#\n"
        "# 즉시 정지: automation/AUTOARM_DISABLED 파일을 main 에 두면 사다리가 멈춘다.\n"
        "# 낙폭 예산은 운영자 소유 — 변경은 운영자 결정.\n"
        "\n"
        f"armed: {'true' if armed else 'false'}\n"
        f"capital_usd: {capital_usd}\n"
        "requested_by: spec-050-capital-ladder (operator delegation 2026-06-11)\n"
        "stage: live-canary-portfolio\n"
        f"run_seq: {run_seq}\n"
        f"ladder_rung: {rung}\n"
        f"rung_entered: {rung_entered.isoformat()}\n"
        f"account_nav_usd: {account_nav_usd}\n"
        f"dd_budget_pct: {dd_budget_pct}\n"
        f'note: "🪜 자본 사다리 단 {rung} ({RUNG_FRACTIONS[rung] * 100}% of NAV '
        f'${account_nav_usd}). {evidence}"\n'
    )


# ---- 핵심 결정 -------------------------------------------------------------------


def _growth_field_decimal(growth: dict | None, key: str) -> Decimal | None:
    if not isinstance(growth, dict):
        return None
    v = growth.get(key)
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except ArithmeticError:
        return None


def decide_ladder(
    *,
    sentinel_text: str,
    forward_verdict: dict,
    live_growth: dict | None,
    account_nav_usd: Decimal | None,
    live_config: PortfolioRebalanceConfig,
    validated_config: PortfolioRebalanceConfig,
    kill_switch_present: bool,
    today: date,
    exploration_verdict: dict | None = None,
    live_performance: dict | None = None,
    dd_budget_pct: Decimal = DEFAULT_DD_BUDGET_PCT,
) -> LadderDecision:
    """자본 사다리 결정 — 순수·결정론·보수적 fail-safe.

    순서(가장 강한 차단부터):
      1. 킬스위치 → DISABLED.
      2. 전략 지문 불일치 → BLOCKED (어떤 단에서도 검증 안 한 전략에 자본 배치 금지).
      3. 계좌 NAV 불능(None/≤0) → BLOCKED (사이징 불가 — 모르면 아무것도 안 바꾼다).
      4. 단 0: forward EDGE_CONFIRMED 또는 엄격한 탐색 캐너리 증거면 단 1 로 PROMOTE.
      5. 단 ≥1: 낙폭 ≥ 예산 → HALT / 낙폭 ≥ 예산/2 → DEMOTE /
         증거(관측·경과일·낙폭) 충족 + 단 < 4 → PROMOTE / NAV 드리프트 → RESIZE / STAY.
    """
    cur_sent = parse_sentinel(sentinel_text)
    rung_raw, entered, recorded_nav = parse_ladder_fields(sentinel_text)
    # 하위 호환: 옛 autoarm 센티넬(armed:true, rung 없음)은 단 1 로 취급.
    rung = rung_raw if rung_raw is not None else (1 if cur_sent.armed else 0)
    rung = max(0, min(MAX_RUNG, rung))
    run_seq = cur_sent.run_seq or 0

    dd = _growth_field_decimal(live_growth, "max_drawdown_pct")
    obs_raw = live_growth.get("snapshot_count") if isinstance(live_growth, dict) else None
    try:
        obs = int(obs_raw) if obs_raw is not None else None
    except (ValueError, TypeError):
        obs = None
    period_days = _growth_field_decimal(live_growth, "period_days")

    def _d(
        action: str,
        target: int,
        reason: str,
        *,
        capital: int | None = None,
        sentinel: str | None = None,
    ) -> LadderDecision:
        return LadderDecision(
            action=action,
            current_rung=rung,
            target_rung=target,
            reason=reason,
            account_nav_usd=account_nav_usd,
            target_capital_usd=capital,
            live_dd_pct=dd,
            live_obs=obs,
            new_sentinel_text=sentinel,
        )

    # 1. 킬스위치.
    if kill_switch_present:
        return _d(
            ACTION_DISABLED, rung,
            "automation/AUTOARM_DISABLED 존재 — 자본 사다리 정지(운영자 킬스위치).",
        )

    # 2. 검증=배치 정합 (모든 단에 적용).
    if strategy_fingerprint(live_config) != strategy_fingerprint(validated_config):
        return _d(
            ACTION_BLOCKED, rung,
            "정합성 불일치 — 라이브 설정의 전략 지문이 검증 앙상블과 다르다. "
            "검증하지 않은 전략에는 어떤 단에서도 자본을 배치하지 않는다.",
        )

    # 3. 계좌 NAV 불능 — 사이징 불가면 상태를 바꾸지 않는다(승격도 강등도 아님).
    if account_nav_usd is None or account_nav_usd <= 0:
        return _d(
            ACTION_BLOCKED, rung,
            f"실계좌 NAV={account_nav_usd!r} — 사이징 불가. 모르면 아무것도 바꾸지 않는다.",
        )

    def _changed(action: str, target: int, reason: str, evidence: str) -> LadderDecision:
        capital = rung_capital_usd(target, account_nav_usd)
        sentinel = render_ladder_sentinel(
            rung=target,
            capital_usd=capital,
            account_nav_usd=account_nav_usd,
            rung_entered=today,
            run_seq=run_seq + 1,
            dd_budget_pct=dd_budget_pct,
            evidence=evidence,
        )
        return _d(action, target, reason, capital=capital, sentinel=sentinel)

    # 4. 단 0 — 완전 forward 또는 제한된 탐색 캐너리만 첫 진입을 허용한다.
    if rung == 0:
        v_label = (
            forward_verdict.get("verdict") if isinstance(forward_verdict, dict) else None
        )
        exploration_ready = (
            isinstance(exploration_verdict, dict)
            and exploration_verdict.get("verdict") == "EXPLORATION_CANARY_READY"
        )
        if v_label != EDGE_CONFIRMED and not exploration_ready:
            exploration_label = (
                exploration_verdict.get("verdict")
                if isinstance(exploration_verdict, dict)
                else None
            )
            return _d(
                ACTION_WAIT_EDGE, 0,
                f"단 0 + forward 판정={v_label!r}, 탐색 캐너리="
                f"{exploration_label!r}"
                " — 진입 증거 미충족. 배치 보류.",
            )
        n_obs = forward_verdict.get("n_obs")
        if exploration_ready and v_label != EDGE_CONFIRMED:
            candidate = exploration_verdict.get("candidate_id", "unknown")
            return _changed(
                ACTION_PROMOTE, 1,
                f"정확 배포전략 {candidate}의 홀드아웃·forward floor·하드닝·지문 정합 "
                "충족 → 탐색 캐너리 단 1 (NAV의 20%) 진입.",
                f"exploration canary ready({candidate}), 전략 지문 정합. 단 0→1.",
            )
        return _changed(
            ACTION_PROMOTE, 1,
            f"forward EDGE_CONFIRMED(관측 {n_obs}) + 정합 → 탐색 캐너리 단 1 "
            "(NAV 의 20%) 진입.",
            f"forward EDGE_CONFIRMED(관측 {n_obs}), 전략 지문 정합. 단 0→1.",
        )

    # 5. 첫 체결 전 탐색 승인이 최신 증거에서 사라졌으면 오래된 무장을 회수한다.
    # 이미 체결된 전략은 위험 축소 거래를 막지 않고 아래 라이브 손실 게이트로 넘긴다.
    v_label = (
        forward_verdict.get("verdict") if isinstance(forward_verdict, dict) else None
    )
    exploration_ready = (
        isinstance(exploration_verdict, dict)
        and exploration_verdict.get("verdict") == "EXPLORATION_CANARY_READY"
    )
    fill_source = live_performance if isinstance(live_performance, dict) else live_growth
    live_fills = fill_source.get("fills_count") if isinstance(fill_source, dict) else None
    if (
        rung == 1
        and live_fills == 0
        and v_label != EDGE_CONFIRMED
        and not exploration_ready
    ):
        return _changed(
            ACTION_DEMOTE,
            0,
            "단 1 첫 전략 체결 전 최신 탐색 자격 미달 -> 단 0(무장 해제).",
            "첫 전략 체결 0건 + 최신 탐색 자격 미달. 단 1->0, 재진입은 최신 forward 재검증부터.",
        )

    # 6. 단 ≥ 1 — 라이브 실적이 유일한 잣대 (내려가는 건 즉시, 올라가는 건 증거).
    halt_dd = dd_budget_pct
    demote_dd = dd_budget_pct / 2

    if dd is not None and dd >= halt_dd:
        return _changed(
            ACTION_HALT, 0,
            f"단 {rung} 라이브 낙폭 {dd}% ≥ 예산 {halt_dd}% → 정지(단 0, 무장 해제).",
            f"낙폭 {dd}% ≥ 예산 {halt_dd}%. 단 {rung}→0 정지. 재진입은 forward 재검증부터.",
        )
    if dd is not None and dd >= demote_dd:
        target = rung - 1
        if target == 0:
            return _changed(
                ACTION_DEMOTE, 0,
                f"단 {rung} 라이브 낙폭 {dd}% ≥ 예산/2 {demote_dd}% → 단 0(무장 해제).",
                f"낙폭 {dd}% ≥ 예산/2 {demote_dd}%. 단 {rung}→0. 재진입은 forward 재검증부터.",
            )
        return _changed(
            ACTION_DEMOTE, target,
            f"단 {rung} 라이브 낙폭 {dd}% ≥ 예산/2 {demote_dd}% → 단 {target} 강등.",
            f"낙폭 {dd}% ≥ 예산/2 {demote_dd}%. 단 {rung}→{target} 강등(시계 리셋).",
        )

    # 승격 — 세 증거 전부 + 천장 미만. 증거가 None(측정 불가)이면 절대 승격 아님.
    forward_confirmed = (
        isinstance(forward_verdict, dict)
        and forward_verdict.get("verdict") == EDGE_CONFIRMED
    )
    if (
        rung < MAX_RUNG
        and (rung != 1 or forward_confirmed)
        and obs is not None
        and obs >= PROMOTION_MIN_OBS
        and period_days is not None
        and period_days >= PROMOTION_MIN_CALENDAR_DAYS
        and dd is not None
        and dd < demote_dd
    ):
        target = rung + 1
        return _changed(
            ACTION_PROMOTE, target,
            f"단 {rung} 증거 충족(관측 {obs} ≥ {PROMOTION_MIN_OBS}, 경과 {period_days}일 ≥ "
            f"{PROMOTION_MIN_CALENDAR_DAYS}, 낙폭 {dd}% < {demote_dd}%) → 단 {target} 승격.",
            f"관측 {obs}, 경과 {period_days}일, 낙폭 {dd}% < {demote_dd}%. 단 {rung}→{target}.",
        )

    # 재사이징 — 단 유지 중 실계좌 NAV 드리프트(입금/성장/하락) ±10% 이상이면 자본 재계산.
    expected = rung_capital_usd(rung, account_nav_usd)
    current_cap = cur_sent.capital_usd
    if current_cap is not None and expected > 0:
        drift_pct = abs(Decimal(current_cap) - Decimal(expected)) / Decimal(expected) * 100
        if drift_pct >= RESIZE_DRIFT_PCT:
            keep_entered = entered if entered is not None else today
            capital = expected
            sentinel = render_ladder_sentinel(
                rung=rung,
                capital_usd=capital,
                account_nav_usd=account_nav_usd,
                rung_entered=keep_entered,  # 재사이징은 시계를 리셋하지 않는다.
                run_seq=run_seq + 1,
                dd_budget_pct=dd_budget_pct,
                evidence=(
                    f"계좌 NAV 드리프트 재사이징: 센티넬 ${current_cap} → ${capital} "
                    f"(단 {rung} 비율 유지, NAV ${account_nav_usd})."
                ),
            )
            return _d(
                ACTION_RESIZE, rung,
                f"단 {rung} 유지, 자본 ${current_cap} → ${capital} 재계산"
                f"(계좌 NAV ${account_nav_usd} 드리프트 {drift_pct.quantize(Decimal('0.1'))}%"
                f" ≥ {RESIZE_DRIFT_PCT}%).",
                capital=capital,
                sentinel=sentinel,
            )

    return _d(
        ACTION_STAY, rung,
        f"단 {rung} 유지 — 승격 증거 미충족(관측 {obs}/{PROMOTION_MIN_OBS}, "
        f"경과 {period_days}일/{PROMOTION_MIN_CALENDAR_DAYS}, 낙폭 {dd}%, "
        f"forward_confirmed={forward_confirmed}), 강등 사유 없음.",
    )

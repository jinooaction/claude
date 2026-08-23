"""스펙 049 — forward 엣지 자동 무장 게이트 결정 로직 (순수·결정론·읽기 전용 판정).

운영자 지시(2026-06-10): **"forward 검증 후 자동 무장."** 이는 무장 해제 노트
(2026-06-04)의 계획 — *"넓은 forward 페이퍼로 검증 후 재무장"* — 을 자동화한 것이다.
옛 3종목 top_n=1(SPY·MSFT·AAPL)은 "세계 최고 수준 아님"으로 운영자가 거부했고, 그 후속이
검증된 글로벌 분산 추세추세 앙상블(SPY·IEF·GLD, 역변동성, 다중 속도 앙상블, 스펙 047/048)이다.

이 모듈은 **결정만** 한다 — 주문 0건, 돈 0 이동, 네트워크 0. 무장(armed:true)이라는
*제안*만 내고, 실제 라이브 전환은 별도 채널(rebalance-live-canary.yml)이 한다.

입력:
  - forward-verdict JSON: ARM E(검증된 앙상블 페이퍼 트랙, global-trend-portfolio.toml,
    data/forward_global.db)의 스펙 035 엣지 판정.
  - 라이브 캐너리가 *실제로 거래할* 설정(canary-live-portfolio.toml)의 전략 블록.
  - 검증에 쓴 설정(global-trend-portfolio.toml)의 전략 블록.
  - 현재 무장 센티넬(automation/rebalance-live.request) 본문.
  - 킬스위치 존재 여부(automation/AUTOARM_DISABLED).

출력: `AutoArmDecision` — ARM / WAIT / BLOCKED / ALREADY_ARMED / DISABLED + 사유 +
(ARM 일 때만) 새 센티넬 본문.

안전 원칙 — *돈을 잃지 않게 보수적으로*:
  1. **fail-safe**: 파싱 실패·모호·예외 = WAIT/BLOCKED, **절대 ARM 아님**. "모르면 무장 안 함".
  2. **검증=무장 정합성**: 라이브 캐너리 설정의 전략 지문이 검증한 앙상블과 다르면 BLOCKED —
     *검증하지 않은 전략은 무장하지 않는다*(paper 에서 앙상블을 검증하고 라이브에서 다른 전략을
     무장하는 실수 차단).
  3. **EDGE_CONFIRMED 만 ARM**: NO_EDGE/INSUFFICIENT_DATA = WAIT(더 쌓여야 함, 정상).
  4. **자본 상한**: 제안 자본은 워크플로 footgun 캡($1,000) 이하로 클램프. 마지막 운영자
     신호(센티넬 capital_usd)를 초과하지 않는다 — 자동 게이트가 실거래 노출을 키우지 못한다.
  5. **멱등**: 이미 armed:true 면 ALREADY_ARMED(no-op) — 매일 돌아도 중복 무장 안 함.
  6. **킬스위치**: AUTOARM_DISABLED 파일이 있으면 DISABLED(no-op) — 운영자 즉시 정지 수단.

헌법 X.4(v4.0.0): 라이브 전환은 운영자 결정이다. 이 게이트는 운영자의 **명시 지시**("forward
검증 후 자동 무장")에 따른 *라이브 캐너리* 무장 준비이며 풀라이브가 아니다(헌법 VI 2단계).
무장 머지 자체는 미리보기만(rebalance-live-canary.yml 은 push 가 아니라 *시장시간 스케줄*에서만
실주문) — 운영자가 사이드카/PR 로 첫 실주문 전에 검토·disarm 할 시간이 있다.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from auto_invest.config.rules import PortfolioRebalanceConfig

# ---- 결정 라벨 (이 다섯 값만 난다) ----
ACTION_ARM = "ARM"  # EDGE_CONFIRMED + 정합 + 미무장 → 무장 제안
ACTION_WAIT = "WAIT"  # 아직 엣지 미확정(관측 부족/우위 없음) → 보류
ACTION_BLOCKED = "BLOCKED"  # 정합성 불일치·자본 위반 등 안전 차단 → 무장 안 함
ACTION_ALREADY_ARMED = "ALREADY_ARMED"  # 이미 armed:true → no-op(멱등)
ACTION_DISABLED = "DISABLED"  # 킬스위치 → no-op

# 검증된 forward 판정에서 ARM 을 허용하는 유일한 라벨.
EDGE_CONFIRMED = "EDGE_CONFIRMED"

# 자본 안전 상한 — rebalance-live-canary.yml 의 footgun 캡과 동일($1,000).
# 자동 게이트는 이 이상으로 실거래 노출을 키울 수 없다.
MAX_CANARY_CAPITAL_USD = 1000


@dataclass(frozen=True)
class AutoArmDecision:
    """자동 무장 게이트의 한 줄 결정 — 운영자 X.4 검토 증거."""

    action: str  # ARM | WAIT | BLOCKED | ALREADY_ARMED | DISABLED
    reason: str
    verdict: str | None  # EDGE_CONFIRMED | NO_EDGE | INSUFFICIENT_DATA | None
    n_obs: int | None
    proposed_capital_usd: int | None  # ARM 일 때만 의미
    new_run_seq: int | None  # ARM 일 때만 의미
    new_sentinel_text: str | None  # ARM 일 때만 채워짐

    SCHEMA_VERSION = "1.0"

    @property
    def should_arm(self) -> bool:
        return self.action == ACTION_ARM

    def to_json_dict(self) -> dict:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "action": self.action,
            "reason": self.reason,
            "verdict": self.verdict,
            "n_obs": self.n_obs,
            "proposed_capital_usd": self.proposed_capital_usd,
            "new_run_seq": self.new_run_seq,
        }


# ---- 전략 지문 (검증=무장 정합성의 핵심) -----------------------------------------
# 두 포트폴리오 설정이 "같은 전략"인지 비교하는 안전 관련 필드들. 라이브 캐너리가
# 거래할 전략 지문이 검증한 앙상블의 지문과 다르면 무장하지 않는다(BLOCKED).
# 자본·캡·화이트리스트는 *라이브 사이징* 이라 의도적으로 제외한다 — 전략 본질만 비교.


def _trend_fingerprint(tf) -> tuple:
    if tf is None:
        return ("none",)
    return (
        "trend",
        tf.method,
        tf.lookback,
        tf.on_insufficient,
        str(tf.min_return_pct),
        tuple(tf.ensemble_windows) if tf.ensemble_windows is not None else None,
    )


def strategy_fingerprint(cfg: PortfolioRebalanceConfig) -> tuple:
    """포트폴리오 설정의 *전략 본질* 지문 — 검증=무장 정합성 비교용.

    유니버스·가중 방식·선택 폭·재조정 동작·추세 게이트(앙상블 창 포함)를 포착한다.
    캡/자본/화이트리스트(라이브 사이징)는 제외 — 그건 전략이 아니라 *운용 규모*다.
    """
    base = (
        tuple(cfg.universe),
        cfg.weight_scheme,
        cfg.rebalance_mode,
        cfg.rebalance_every_n_sessions,
        cfg.top_n,
        cfg.top_pct,
        cfg.lookback_bars,
        cfg.momentum_period,
        tuple(sorted((k, str(v)) for k, v in cfg.weights.items())),
        _trend_fingerprint(cfg.trend_filter),
        (
            "none"
            if cfg.macro_policy is None
            else json.dumps(
                cfg.macro_policy.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            )
        ),
    )
    if cfg.treasury_carry_policy is not None:
        return base + (
            json.dumps(
                cfg.treasury_carry_policy.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    if cfg.credit_spread_policy is not None:
        return base + (
            "credit_spread",
            json.dumps(
                cfg.credit_spread_policy.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    return base


def strategy_fingerprint_digest(cfg: PortfolioRebalanceConfig) -> str:
    """Stable serializable digest of the exact live strategy fingerprint."""
    encoded = json.dumps(strategy_fingerprint(cfg), sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


# ---- 센티넬 파싱/렌더 -------------------------------------------------------------

_ARMED_RE = re.compile(r"^armed:\s*(\S+)\s*$", re.MULTILINE)
_CAPITAL_RE = re.compile(r"^capital_usd:\s*(\S+)\s*$", re.MULTILINE)
_RUNSEQ_RE = re.compile(r"^run_seq:\s*(\S+)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class SentinelState:
    armed: bool
    capital_usd: int | None
    run_seq: int | None


def parse_sentinel(text: str) -> SentinelState:
    """무장 센티넬 본문에서 armed/capital_usd/run_seq 를 보수적으로 읽는다.

    파싱 못 한 값은 None(자본)·False(armed)·None(run_seq)로 둔다. armed 는 정확히
    'true' 일 때만 True — 그 외 모든 값(false/오타/누락)은 미무장으로 취급(fail-safe).
    """
    am = _ARMED_RE.search(text)
    armed = bool(am) and am.group(1).strip().lower() == "true"
    cap: int | None = None
    cm = _CAPITAL_RE.search(text)
    if cm:
        try:
            cap = int(float(cm.group(1)))
        except (ValueError, TypeError):
            cap = None
    seq: int | None = None
    sm = _RUNSEQ_RE.search(text)
    if sm:
        try:
            seq = int(sm.group(1))
        except (ValueError, TypeError):
            seq = None
    return SentinelState(armed=armed, capital_usd=cap, run_seq=seq)


def render_armed_sentinel(
    *,
    capital_usd: int,
    run_seq: int,
    verdict_summary: str,
) -> str:
    """armed:true 무장 센티넬 본문을 렌더한다(자동 게이트가 main 에 머지).

    rebalance-live-canary.yml 이 파싱하는 라인(`armed:`, `capital_usd:`)을 그대로 유지하고,
    포렌식 기록용 헤더(운영자 지시·X.4 권한·검증 증거)를 단다. 머지 커밋이 X.4 기록이다.
    """
    return (
        "# 라이브 캐너리 포트폴리오 무장 센티넬 (스펙 040; 스펙 049 자동 무장 게이트가 갱신).\n"
        "#\n"
        "# 이 파일이 main 에 머지되면 rebalance-live-canary.yml 워크플로가 발화한다.\n"
        "#   - armed: false → 드라이런 미리보기만(실주문 0건).\n"
        "#   - armed: true  → 실주문(rebalance-once --mode live --confirm-live). 실제 돈 이동.\n"
        "#\n"
        "# 🤖 이 무장은 스펙 049 forward 엣지 자동 무장 게이트가 제안했다 — 운영자 지시\n"
        '#   "forward 검증 후 자동 무장"(2026-06-10)의 자동화. 무장 해제 노트(2026-06-04)의\n'
        '#   계획 "넓은 forward 페이퍼로 검증 후 재무장" 을 검증된 앙상블(SPY·IEF·GLD, 역변동성,\n'
        "#   다중 속도 앙상블)로 실현한다. 라이브 캐너리 설정이 *검증한 바로 그 앙상블*과\n"
        "#   전략 지문이 일치함을 게이트가 확인했다(검증=무장 정합성).\n"
        "#\n"
        "# 검증 증거(ARM E forward 페이퍼, 스펙 035 판정):\n"
        f"#   {verdict_summary}\n"
        "#\n"
        "# ⚠ 정직: 무장 머지 자체는 *미리보기만* — 첫 실주문은 다음 미국 정규장 스케줄에서만\n"
        "#   나간다(rebalance-live-canary.yml 은 push 가 아니라 schedule 에서만 실주문). 운영자가\n"
        "#   사이드카/PR 로 검토하고 첫 실주문 전에 disarm 할 시간이 있다. 자본은 소액 캡 이하.\n"
        "#\n"
        "# 헌법 X.4: 라이브 전환은 운영자 결정. 소액 캐너리 무장 전용, 풀라이브 아님.\n"
        "# 즉시 정지: automation/AUTOARM_DISABLED 파일을 만들면 게이트가 무장을 멈춘다.\n"
        "\n"
        "armed: true\n"
        f"capital_usd: {capital_usd}\n"
        "requested_by: spec-049-edge-autoarm-gate (per operator instruction 2026-06-10)\n"
        "stage: live-canary-portfolio\n"
        f"run_seq: {run_seq}\n"
        f'note: "🟢 자동 무장(스펙 049) — 검증된 글로벌 분산 추세 앙상블이 forward 페이퍼에서 '
        f"EDGE_CONFIRMED. {verdict_summary} 운영자 지시 'forward 검증 후 자동 무장'(2026-06-10) "
        f"+ 헌법 X.4. 자본 ${capital_usd}(소액 캐너리, 캡 ${MAX_CANARY_CAPITAL_USD} 이하). 첫 "
        f'실주문은 다음 미국 정규장. 검토 후 disarm 가능."\n'
    )


# ---- 핵심 결정 -------------------------------------------------------------------


def decide_autoarm(
    *,
    verdict: dict,
    live_config: PortfolioRebalanceConfig,
    validated_config: PortfolioRebalanceConfig,
    sentinel_text: str,
    kill_switch_present: bool,
    max_capital_usd: int = MAX_CANARY_CAPITAL_USD,
) -> AutoArmDecision:
    """자동 무장 결정 — 순수·결정론·보수적 fail-safe.

    순서(가장 강한 차단부터):
      1. 킬스위치 → DISABLED.
      2. 이미 무장 → ALREADY_ARMED(멱등).
      3. 검증=무장 정합성 불일치 → BLOCKED(검증 안 한 전략 무장 금지).
      4. 판정이 EDGE_CONFIRMED 아님 → WAIT(정상, 더 쌓여야 함).
      5. 자본 결정 불가/위반 → BLOCKED.
      6. 위 전부 통과 → ARM(새 센티넬 본문 포함).
    """
    cur = parse_sentinel(sentinel_text)

    # 판정에서 안전하게 라벨/관측수 추출(없거나 깨졌으면 보수적으로 None).
    v_label = verdict.get("verdict") if isinstance(verdict, dict) else None
    n_obs_raw = verdict.get("n_obs") if isinstance(verdict, dict) else None
    try:
        n_obs = int(n_obs_raw) if n_obs_raw is not None else None
    except (ValueError, TypeError):
        n_obs = None

    def _d(action: str, reason: str) -> AutoArmDecision:
        return AutoArmDecision(
            action=action,
            reason=reason,
            verdict=v_label,
            n_obs=n_obs,
            proposed_capital_usd=None,
            new_run_seq=None,
            new_sentinel_text=None,
        )

    # 1. 킬스위치.
    if kill_switch_present:
        return _d(
            ACTION_DISABLED,
            "automation/AUTOARM_DISABLED 존재 — 자동 무장 게이트 정지(운영자 킬스위치).",
        )

    # 2. 멱등 — 이미 무장.
    if cur.armed:
        return _d(
            ACTION_ALREADY_ARMED,
            "센티넬이 이미 armed:true — 중복 무장 안 함(멱등 no-op).",
        )

    # 3. 검증=무장 정합성.
    live_fp = strategy_fingerprint(live_config)
    val_fp = strategy_fingerprint(validated_config)
    if live_fp != val_fp:
        return _d(
            ACTION_BLOCKED,
            "정합성 불일치 — 라이브 캐너리 설정의 전략 지문이 검증한 앙상블과 다르다. "
            "검증하지 않은 전략은 무장하지 않는다(canary-live-portfolio.toml 의 [portfolio] "
            "전략 블록을 검증된 global-trend-portfolio.toml 과 일치시켜야 무장 가능). "
            f"live={live_fp!r} vs validated={val_fp!r}",
        )

    # 4. 판정.
    if v_label != EDGE_CONFIRMED:
        return _d(
            ACTION_WAIT,
            f"판정={v_label!r}(관측 {n_obs}) — EDGE_CONFIRMED 아님. 무장 보류(정상, 더 쌓여야 함).",
        )

    # 5. 자본 — 마지막 운영자 신호(센티넬 capital_usd)를 캡 이하로 클램프.
    base_cap = cur.capital_usd if cur.capital_usd is not None else max_capital_usd
    if base_cap <= 0:
        return _d(
            ACTION_BLOCKED,
            f"센티넬 capital_usd={cur.capital_usd!r} 가 비양수 — 자본 결정 불가. 무장 차단.",
        )
    capital = min(base_cap, max_capital_usd)

    # 6. ARM.
    new_seq = (cur.run_seq or 0) + 1
    sharpe = verdict.get("strategy_sharpe_annual") if isinstance(verdict, dict) else None
    dd = verdict.get("strategy_max_drawdown_pct") if isinstance(verdict, dict) else None
    calmar = verdict.get("strategy_calmar") if isinstance(verdict, dict) else None
    summary = f"EDGE_CONFIRMED (관측 {n_obs}, 전략 샤프 {sharpe}, 최대낙폭 {dd}%, 칼마 {calmar})"
    sentinel = render_armed_sentinel(capital_usd=capital, run_seq=new_seq, verdict_summary=summary)
    return AutoArmDecision(
        action=ACTION_ARM,
        reason=(
            f"EDGE_CONFIRMED (관측 {n_obs} ≥ 최소) + 검증=무장 정합 + 미무장 → 자동 무장 제안. "
            f"자본 ${capital}(캡 ${max_capital_usd} 이하), run_seq {cur.run_seq}→{new_seq}."
        ),
        verdict=v_label,
        n_obs=n_obs,
        proposed_capital_usd=capital,
        new_run_seq=new_seq,
        new_sentinel_text=sentinel,
    )

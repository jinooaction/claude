"""스펙 053 — forward 토너먼트 리더보드 (순수·결정론·읽기 전용 종합).

이 프로젝트가 반복적으로 물린 안티패턴은 "사이드카(또는 JSON 블록) 여러 개를 사람이
머릿속에서 짜맞춰야 한다"는 것이다. 스펙 051(생존 감시)·052(첫-자본까지의 길)가 각각
"파이프라인이 살아있나"·"검증된 한 트랙의 자본까지 길"을 한 곳에 모았듯, 이 모듈은
**"7개 forward 페이퍼 트랙 중 누가 이기고 있나"를 한 곳에 모은다.**

배경: `rebalance-paper-forward.yml` A/B 토너먼트는 후보 전략 여러 개(추세 ON/OFF·
위험관리 베타·멀티에셋 추세·글로벌 추세·확대 유니버스)를 각자 전용 DB 로 격리해 병렬
페이퍼 트레이딩하고, 트랙마다 스펙 035 forward-verdict(EDGE_CONFIRMED/NO_EDGE/
INSUFFICIENT_DATA)를 낸다. 그런데 사이드카는 판정 JSON 6덩이를 *날 것 그대로* 박아넣고
"비교해보면..."이라는 산문만 달 뿐, **계산된 순위가 없다.** 라이브 검증 트랙(글로벌 추세
SPY·IEF·GLD)이 아직도 최강인지, 어떤 도전자가 EDGE_CONFIRMED 를 벌어 재지정 후보가
됐는지(검증=배치 정합, 헌법 X.4 v5.0.0 사다리)를 알려면 사람이 6덩이를 눈으로 비교해야
했다.

이 모듈은 그 7개 판정을 받아 **정직성 게이트로 순위를 매긴다**:

  - 비교 가능(COMPARABLE) = 관측 ≥ 최소(스펙 035 기본 20). 엣지를 판정할 만큼 쌓임.
  - 잠정(PREMATURE)      = INSUFFICIENT_DATA(관측 < 최소). 지표는 아직 노이즈 → 순위는
                           매기되 *챔피언으로 선언하지 않는다*(거짓 자신만만 금지).
  - 불명(UNKNOWN)        = 판정 JSON 을 못 읽음.

  챔피언 = 비교 가능한 EDGE_CONFIRMED 중 품질 1위(칼마→샤프→초과수익→낙폭 순).
           하나도 EDGE_CONFIRMED 가 아니면 **챔피언 없음**(정직: 아직 아무도 엣지 확정 못 함).
  도전자 경보 = 비-incumbent 트랙이 챔피언이고, incumbent(라이브 검증 트랙)도 비교 가능해
               *사과 대 사과* 비교가 성립할 때만 — 검증 트랙은 자동으로 안 바뀐다(운영자
               게이트 X.4). 관측 부족한 트랙으로는 절대 도전자 경보를 내지 않는다(거짓 경보 0).

안전 경계: 읽기 전용·순수·결정론. 주문 0건·돈 0 이동·새 측정 0(발행된 판정 숫자 비교만).
라이브 전략 변경은 여전히 운영자 게이트(헌법 X.4) — 이 모듈은 그 결정을 *읽어 설명할* 뿐
아무것도 일으키지 않는다. 라이브를 *건드리지 않으므로* 전진 시계가 리셋되지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

# 판정 라벨 — edge_verdict.py 와 동일(이 세 값만 비교 대상).
EDGE_CONFIRMED = "EDGE_CONFIRMED"
NO_EDGE = "NO_EDGE"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

# 비교 가능성 등급.
COMPARABLE = "COMPARABLE"  # 관측 ≥ 최소 — 엣지 판정 가능(순위·챔피언 대상)
PREMATURE = "PREMATURE"  # 관측 < 최소 — 지표 노이즈, 순위는 매기되 챔피언 아님
UNKNOWN = "UNKNOWN"  # 판정 JSON 못 읽음

SCHEMA_VERSION = "1.0"

# 후보 관측 품질. 토너먼트 자체의 생존은 사이드카 timestamp 로 보지만, "살아있는데
# 일부 후보 판정을 못 읽거나 한 후보만 뒤처지는" 문제는 별도 품질 상태로 드러낸다.
OBS_HEALTH_OK = "OK"
OBS_HEALTH_DEGRADED = "DEGRADED"
OBS_HEALTH_BLOCKED = "BLOCKED"

# 스펙 035 기본 최소 관측(판정 JSON 에 min_obs_required 가 없을 때 폴백).
DEFAULT_MIN_OBS = 20

# 유의 기준(판정 JSON 에 dsr_threshold 가 없을 때 폴백, 스펙 035 와 동일 0.95).
DEFAULT_DSR_THRESHOLD = Decimal("0.95")


def _dec(value: object) -> Decimal | None:
    """문자열/숫자를 Decimal 로 — 실패하면 None(보수적)."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError, TypeError):
        return None


def _int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


@dataclass(frozen=True)
class TrackResult:
    """한 forward 트랙의 판정 + 비교 가능성 + (순위 매긴 뒤) 등수."""

    key: str
    label: str
    is_incumbent: bool  # 라이브 검증 트랙(글로벌 추세)인가
    verdict: str | None  # EDGE_CONFIRMED | NO_EDGE | INSUFFICIENT_DATA | None
    n_obs: int | None
    min_obs: int | None
    sharpe: Decimal | None  # strategy_sharpe_annual
    total_return_pct: Decimal | None
    max_drawdown_pct: Decimal | None
    calmar: Decimal | None
    excess_return_pct: Decimal | None
    dsr: Decimal | None
    universe: tuple[str, ...]
    comparability: str  # COMPARABLE | PREMATURE | UNKNOWN
    rank: int | None = None  # 1-기반 등수(정렬 후 채워짐)
    psr_vs_benchmark: Decimal | None = None  # 참 샤프>벤치마크 확률(PSR) — 교차-트랙 보정용
    dsr_threshold: Decimal | None = None  # 유의 기준(기본 0.95) — 보정 기준 계산용

    def with_rank(self, rank: int) -> TrackResult:
        return replace(self, rank=rank)

    def to_json_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "is_incumbent": self.is_incumbent,
            "verdict": self.verdict,
            "n_obs": self.n_obs,
            "min_obs": self.min_obs,
            "comparability": self.comparability,
            "rank": self.rank,
            "calmar": None if self.calmar is None else str(self.calmar),
            "sharpe": None if self.sharpe is None else str(self.sharpe),
            "total_return_pct": (
                None if self.total_return_pct is None else str(self.total_return_pct)
            ),
            "max_drawdown_pct": (
                None if self.max_drawdown_pct is None else str(self.max_drawdown_pct)
            ),
            "excess_return_pct": (
                None if self.excess_return_pct is None else str(self.excess_return_pct)
            ),
            "dsr": None if self.dsr is None else str(self.dsr),
            "psr_vs_benchmark": (
                None if self.psr_vs_benchmark is None else str(self.psr_vs_benchmark)
            ),
            "dsr_threshold": (
                None if self.dsr_threshold is None else str(self.dsr_threshold)
            ),
            "universe_size": len(self.universe),
            "universe": list(self.universe[:8]),
        }


def build_track_result(
    *,
    key: str,
    label: str,
    is_incumbent: bool,
    verdict_json: dict | None,
    min_obs_default: int = DEFAULT_MIN_OBS,
) -> TrackResult:
    """판정 JSON(스펙 035 forward-verdict)을 TrackResult 로 — 보수적 파싱.

    판정이 없거나(None) verdict 라벨이 없으면 comparability=UNKNOWN.
    INSUFFICIENT_DATA 또는 관측 < 최소면 PREMATURE, 그 외(관측 ≥ 최소)면 COMPARABLE.
    """
    if not isinstance(verdict_json, dict):
        return TrackResult(
            key=key, label=label, is_incumbent=is_incumbent, verdict=None,
            n_obs=None, min_obs=None, sharpe=None, total_return_pct=None,
            max_drawdown_pct=None, calmar=None, excess_return_pct=None, dsr=None,
            universe=(), comparability=UNKNOWN,
        )
    verdict = verdict_json.get("verdict")
    n_obs = _int(verdict_json.get("n_obs"))
    min_obs = _int(verdict_json.get("min_obs_required")) or min_obs_default
    universe_raw = verdict_json.get("universe")
    universe = (
        tuple(str(s) for s in universe_raw) if isinstance(universe_raw, list) else ()
    )

    if verdict not in (EDGE_CONFIRMED, NO_EDGE, INSUFFICIENT_DATA):
        comparability = UNKNOWN
    elif verdict == INSUFFICIENT_DATA or n_obs is None or n_obs < min_obs:
        # INSUFFICIENT_DATA(또는 관측 부족) = 지표가 통계적으로 무의미 → 잠정.
        comparability = PREMATURE
    else:
        comparability = COMPARABLE

    return TrackResult(
        key=key,
        label=label,
        is_incumbent=is_incumbent,
        verdict=verdict if isinstance(verdict, str) else None,
        n_obs=n_obs,
        min_obs=min_obs,
        sharpe=_dec(verdict_json.get("strategy_sharpe_annual")),
        total_return_pct=_dec(verdict_json.get("strategy_total_return_pct")),
        max_drawdown_pct=_dec(verdict_json.get("strategy_max_drawdown_pct")),
        calmar=_dec(verdict_json.get("strategy_calmar")),
        excess_return_pct=_dec(verdict_json.get("excess_return_pct")),
        dsr=_dec(verdict_json.get("dsr")),
        psr_vs_benchmark=_dec(verdict_json.get("psr_vs_benchmark")),
        dsr_threshold=_dec(verdict_json.get("dsr_threshold")),
        universe=universe,
        comparability=comparability,
    )


# ---- 순위 정렬 키 ------------------------------------------------------------------
# 티어(가장 강한 우선): 0 = 비교 가능 EDGE_CONFIRMED, 1 = 비교 가능 NO_EDGE,
#                       2 = 잠정(PREMATURE), 3 = 불명(UNKNOWN).
# 티어 0/1 안에서는 품질(칼마→샤프→초과수익→낙폭). 티어 2 안에서는 관측 수(많을수록
# 비교 가능에 가까움 — 지표가 아니라 진척으로 정렬, 노이즈로 챔피언 흉내 안 냄).
_TIER_CONFIRMED = 0
_TIER_NO_EDGE = 1
_TIER_PREMATURE = 2
_TIER_UNKNOWN = 3


def _tier(t: TrackResult) -> int:
    if t.comparability == COMPARABLE:
        return _TIER_CONFIRMED if t.verdict == EDGE_CONFIRMED else _TIER_NO_EDGE
    if t.comparability == PREMATURE:
        return _TIER_PREMATURE
    return _TIER_UNKNOWN


def _hi(value: Decimal | None) -> tuple[int, Decimal]:
    """높을수록 좋은 지표의 오름차순 정렬 키(값 있는 게 먼저, 큰 값이 먼저). None 은 뒤로."""
    return (0, -value) if value is not None else (1, Decimal(0))


def _lo(value: Decimal | None) -> tuple[int, Decimal]:
    """낮을수록 좋은 지표(낙폭)의 오름차순 정렬 키. None 은 뒤로."""
    return (0, value) if value is not None else (1, Decimal(0))


def _neutral() -> tuple[int, Decimal]:
    return (0, Decimal(0))


def _sort_key(idx: int, t: TrackResult) -> tuple:
    """결정론적 정렬 키. 티어가 1순위라 티어가 다르면 지표 칸은 비교에 닿지 않는다."""
    tier = _tier(t)
    if tier in (_TIER_CONFIRMED, _TIER_NO_EDGE):
        return (
            tier,
            _hi(t.calmar),
            _hi(t.sharpe),
            _hi(t.excess_return_pct),
            _lo(t.max_drawdown_pct),
            idx,
        )
    if tier == _TIER_PREMATURE:
        # 관측 많을수록(비교 가능에 가까울수록) 앞. 지표는 노이즈라 보지 않는다.
        nobs = Decimal(t.n_obs) if t.n_obs is not None else None
        return (tier, _hi(nobs), _neutral(), _neutral(), _neutral(), idx)
    return (tier, _neutral(), _neutral(), _neutral(), _neutral(), idx)


@dataclass(frozen=True)
class TournamentLeaderboard:
    """forward 토너먼트의 종합 순위 — 헌법 X.4 v5.0.0 재지정 후보 포렌식 증거."""

    schema_version: str
    as_of_utc: str | None
    rows: list[TrackResult]  # 순위순(rank 채워짐)
    champion_key: str | None  # 비교 가능 EDGE_CONFIRMED 1위(없으면 None)
    incumbent_key: str | None  # 라이브 검증 트랙
    challenger_key: str | None  # incumbent 를 앞선 비교 가능 EDGE_CONFIRMED 도전자(없으면 None)
    headline: str
    note: str = ""
    # 교차-트랙 다중비교(본페로니) 보정 — 6트랙 동시 검정에서 '운 좋은 우승' 처벌.
    comparable_count: int = 0  # 비교 가능 트랙 수 K(챔피언을 뽑은 가족 크기)
    adjusted_dsr_threshold: Decimal | None = None  # 1 − (1−기준)/K (없으면 평가 불가)
    champion_multiplicity_robust: bool | None = None  # 챔피언 유의확률 ≥ 보정 기준?(None=미평가)
    # 후보 관측 품질 — 재지정 루프가 "도전자 없음"과 "후보 판정을 못 읽음"을 구분하게 한다.
    track_count: int = 0
    known_count: int = 0
    unknown_count: int = 0
    max_n_obs: int | None = None
    min_n_obs: int | None = None
    lagging_keys: tuple[str, ...] = ()
    observation_health: str = OBS_HEALTH_OK
    observation_note: str = ""

    def to_json_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "as_of_utc": self.as_of_utc,
            "champion_key": self.champion_key,
            "incumbent_key": self.incumbent_key,
            "challenger_key": self.challenger_key,
            "comparable_count": self.comparable_count,
            "adjusted_dsr_threshold": (
                None
                if self.adjusted_dsr_threshold is None
                else str(self.adjusted_dsr_threshold)
            ),
            "champion_multiplicity_robust": self.champion_multiplicity_robust,
            "track_count": self.track_count,
            "known_count": self.known_count,
            "unknown_count": self.unknown_count,
            "max_n_obs": self.max_n_obs,
            "min_n_obs": self.min_n_obs,
            "lagging_keys": list(self.lagging_keys),
            "observation_health": self.observation_health,
            "observation_note": self.observation_note,
            "headline": self.headline,
            "note": self.note,
            "rows": [r.to_json_dict() for r in self.rows],
        }

    def as_text(self) -> str:
        """사이드카(LAST_RUN.md)에 박을 마크다운 — 사람이 한눈에 순위를 본다."""
        status_icon = {
            COMPARABLE: "✅",
            PREMATURE: "⏳",
            UNKNOWN: "❓",
        }
        verdict_icon = {
            EDGE_CONFIRMED: "🟢",
            NO_EDGE: "➖",
            INSUFFICIENT_DATA: "⏳",
        }
        lines: list[str] = []
        lines.append("# 🏆 forward 토너먼트 리더보드 — 읽기 전용, 돈 0 이동")
        lines.append("")
        lines.append(f"> {self.headline}")
        if self.note:
            lines.append(">")
            lines.append(f"> {self.note}")
        lines.append("")
        lines.append("| # | 트랙 | 판정 | 관측 | 칼마 | 샤프 | 초과수익% | 낙폭% | 상태 |")
        lines.append("|--:|------|:----:|-----:|-----:|-----:|----------:|------:|:----:|")
        for r in self.rows:
            v = verdict_icon.get(r.verdict or "", "—")
            vlabel = r.verdict or "판정 없음"
            mark = " 👑" if r.key == self.champion_key else ""
            mark += " 🏠" if r.is_incumbent else ""
            mark += " 🚀" if r.key == self.challenger_key else ""
            obs = (
                f"{r.n_obs}/{r.min_obs}"
                if r.n_obs is not None and r.min_obs is not None
                else "?"
            )
            calmar = _fmt(r.calmar)
            sharpe = _fmt(r.sharpe)
            excess = _fmt(r.excess_return_pct)
            dd = _fmt(r.max_drawdown_pct)
            st = status_icon.get(r.comparability, "—")
            lines.append(
                f"| {r.rank or '—'} | {r.label}{mark} | {v} {vlabel} | {obs} | "
                f"{calmar} | {sharpe} | {excess} | {dd} | {st} |"
            )
        lines.append("")
        lines.append(
            "🏠 라이브 검증 트랙 · 👑 챔피언(비교 가능 EDGE_CONFIRMED 1위) · 🚀 도전자"
            "(검증 트랙을 앞섬). 잠정(⏳)은 관측이 더 쌓여야 비교 가능 — 지표는 잠정치."
        )
        health_icon = {
            OBS_HEALTH_OK: "✅",
            OBS_HEALTH_DEGRADED: "⚠",
            OBS_HEALTH_BLOCKED: "🛑",
        }.get(self.observation_health, "•")
        lines += [
            "",
            "## 후보 관측 품질",
            "",
            f"{health_icon} **{self.observation_health}** — {self.observation_note}",
            "",
            "| 전체 | 판정 읽힘 | 판정 없음 | 최소 관측 | 최대 관측 | 뒤처진 트랙 |",
            "|-----:|----------:|----------:|----------:|----------:|-------------|",
            f"| {self.track_count} | {self.known_count} | {self.unknown_count} | "
            f"{self.min_n_obs if self.min_n_obs is not None else '—'} | "
            f"{self.max_n_obs if self.max_n_obs is not None else '—'} | "
            f"{', '.join(self.lagging_keys) if self.lagging_keys else '—'} |",
        ]
        if self.champion_key is not None:
            bar = _fmt_p(self.adjusted_dsr_threshold)
            if self.champion_multiplicity_robust is True:
                mtag = (
                    f"✅ 챔피언이 {self.comparable_count}개 트랙 동시 검정 보정 통과"
                    f"(보정 기준 {bar})."
                )
            elif self.champion_multiplicity_robust is False:
                mtag = (
                    f"⚠ 챔피언이 {self.comparable_count}개 트랙 동시 검정 보정 미통과"
                    f"(보정 기준 {bar}) — 여러 트랙 동시 운영에서 온 우연 우승 가능, 재지정 신중."
                )
            else:
                mtag = "교차-트랙 다중비교 보정 미평가(유의확률 PSR/DSR 없음)."
            lines.append("")
            lines.append(f"🔬 교차-트랙 다중비교(본페로니): {mtag}")
        lines.append("")
        lines.append(
            "⚠ 이건 종합 보고다(읽기 전용). 라이브 전략은 자동으로 안 바뀐다 — 재지정은 "
            "운영자 게이트(헌법 X.4). 검증=배치 정합이라 도전자가 라이브가 되려면 라이브 "
            "설정 지문을 그 트랙으로 맞추는 운영자/세션 결정이 필요하다."
        )
        return "\n".join(lines)


def _fmt(value: Decimal | None) -> str:
    if value is None:
        return "—"
    # 소수 둘째 자리까지(노이즈 자릿수 줄임), 정수면 정수로.
    q = value.quantize(Decimal("0.01"))
    return str(q)


def _fmt_p(value: Decimal | None) -> str:
    """확률(PSR/DSR/보정 기준)을 소수 넷째 자리까지 — 0.95 vs 0.9917 을 가른다."""
    if value is None:
        return "—"
    return str(value.quantize(Decimal("0.0001")))


def _sig_prob(t: TrackResult | None) -> Decimal | None:
    """트랙의 유의확률 — PSR 와 (있으면) DSR 중 가장 보수적인(낮은) 값.

    EDGE_CONFIRMED 는 PSR ≥ 기준(+num_trials>1 이면 DSR ≥ 기준)을 모두 통과한 것이므로,
    둘 중 낮은 쪽이 그 트랙 '엣지가 진짜일' 신뢰의 하한이다. 둘 다 없으면 None(미평가).
    """
    if t is None:
        return None
    probs = [p for p in (t.psr_vs_benchmark, t.dsr) if p is not None]
    return min(probs) if probs else None


def _multiplicity(
    champion: TrackResult | None, comparable_count: int
) -> tuple[Decimal | None, bool | None]:
    """교차-트랙 본페로니 보정 — K개 비교 가능 트랙 중 챔피언을 뽑은 선택 다중성을 처벌.

    가족 신뢰도(트랙 기준, 기본 0.95)를 K 트랙에 유지하려면 챔피언 유의확률이
    1 − (1−기준)/K 이상이어야 한다(=가족 단위 거짓 양성 α 를 K 로 나눔). K≤1 이면 보정
    없음(단독 선택). 챔피언/유의확률/기준이 없으면 (기준, None) 또는 (None, None) — 미평가.

    반환: (보정 기준, robust?). robust=None 은 '유의확률이 없어 평가 불가'(보수적).
    """
    if champion is None:
        return None, None
    base = champion.dsr_threshold or DEFAULT_DSR_THRESHOLD
    k = max(1, comparable_count)
    adjusted = (Decimal(1) - (Decimal(1) - base) / k).quantize(Decimal("0.000001"))
    sig = _sig_prob(champion)
    if sig is None:
        return adjusted, None
    return adjusted, sig >= adjusted


def _mult_clause(
    robust: bool | None,
    sig_prob: Decimal | None,
    adjusted: Decimal | None,
    comparable_count: int,
) -> str:
    """다중비교 보정 결과를 사람이 읽는 한 구절로(헤드라인/노트에 덧붙임)."""
    if robust is None:
        return (
            "교차-트랙 다중비교 보정 미평가(유의확률 PSR/DSR 없음 — 보수적으로 신뢰 보류)."
        )
    bar = _fmt_p(adjusted)
    sp = _fmt_p(sig_prob)
    if robust:
        return (
            f"{comparable_count}개 비교 가능 트랙 동시 검정 보정 통과"
            f"(유의확률 {sp} ≥ 보정 기준 {bar})."
        )
    return (
        f"⚠ {comparable_count}개 트랙 동시 검정 보정 미통과(유의확률 {sp} < 보정 기준 "
        f"{bar}) — 여러 트랙을 동시에 돌린 데서 온 우연 우승 가능."
    )


def _observation_quality(
    ranked: list[TrackResult],
    incumbent: TrackResult | None,
) -> tuple[int, int, int, int | None, int | None, tuple[str, ...], str, str]:
    """후보군 관측 품질을 요약한다.

    생존 감시는 "워크플로가 돌았나"만 본다. 여기서는 "후보 판정이 모두 읽혔나",
    "한 후보가 관측 누적에서 크게 뒤처졌나", "incumbent 판정을 잃어 사과 대 사과 비교가
    불가능한가"를 드러낸다. 이 값은 거래를 일으키지 않고, 재지정 판단의 입력 품질을
    설명하는 포렌식 표면이다.
    """
    track_count = len(ranked)
    known = [t for t in ranked if t.comparability != UNKNOWN]
    unknown = [t for t in ranked if t.comparability == UNKNOWN]
    n_obs_values = [t.n_obs for t in known if t.n_obs is not None]
    max_obs = max(n_obs_values) if n_obs_values else None
    min_obs = min(n_obs_values) if n_obs_values else None
    lagging: tuple[str, ...] = ()
    if max_obs is not None:
        # 하루 정도 차이는 워크플로 타이밍/신규 트랙에서 정상일 수 있다. 2관측 이상
        # 뒤처지면 재지정 후보군의 비교 품질 저하로 표면화한다.
        lagging = tuple(
            t.key
            for t in known
            if t.n_obs is not None and max_obs - t.n_obs >= 2
        )

    if not known:
        return (
            track_count,
            0,
            len(unknown),
            max_obs,
            min_obs,
            lagging,
            OBS_HEALTH_BLOCKED,
            "어떤 후보 판정도 읽히지 않음 — 토너먼트 입력 품질 차단.",
        )
    if incumbent is None or incumbent.comparability == UNKNOWN:
        return (
            track_count,
            len(known),
            len(unknown),
            max_obs,
            min_obs,
            lagging,
            OBS_HEALTH_BLOCKED,
            "라이브 검증 트랙 판정을 읽지 못함 — 사과 대 사과 비교 불가.",
        )
    if unknown or lagging:
        parts: list[str] = []
        if unknown:
            parts.append(
                "판정 없음: " + ", ".join(t.key for t in unknown)
            )
        if lagging:
            parts.append("관측 뒤처짐: " + ", ".join(lagging))
        return (
            track_count,
            len(known),
            len(unknown),
            max_obs,
            min_obs,
            lagging,
            OBS_HEALTH_DEGRADED,
            "; ".join(parts) + " — 재지정 후보군 관측 품질 저하.",
        )
    return (
        track_count,
        len(known),
        0,
        max_obs,
        min_obs,
        lagging,
        OBS_HEALTH_OK,
        "모든 후보 판정이 읽혔고 관측 누적이 같은 속도로 진행 중.",
    )


def rank_tournament(
    tracks: list[TrackResult],
    *,
    as_of_utc: str | None = None,
) -> TournamentLeaderboard:
    """TrackResult 목록을 정직성 게이트로 순위 매겨 TournamentLeaderboard 반환(순수).

    챔피언은 비교 가능한 EDGE_CONFIRMED 1위에게만. 도전자 경보는 그 챔피언이 비-incumbent
    이고 incumbent 도 비교 가능할 때만(사과 대 사과). 둘 중 하나라도 관측 부족이면 경보 0.
    """
    ordered = sorted(enumerate(tracks), key=lambda it: _sort_key(it[0], it[1]))
    ranked = [t.with_rank(i + 1) for i, (_, t) in enumerate(ordered)]

    incumbent = next((t for t in ranked if t.is_incumbent), None)
    incumbent_key = incumbent.key if incumbent else None

    # 챔피언 = 비교 가능 EDGE_CONFIRMED 중 1위(정렬상 티어 0 의 맨 앞).
    champion = next(
        (
            t
            for t in ranked
            if t.comparability == COMPARABLE and t.verdict == EDGE_CONFIRMED
        ),
        None,
    )
    champion_key = champion.key if champion else None

    # 도전자 = 챔피언이 incumbent 가 아니고, incumbent 도 비교 가능(사과 대 사과)할 때만.
    challenger_key = None
    if (
        champion is not None
        and not champion.is_incumbent
        and incumbent is not None
        and incumbent.comparability == COMPARABLE
    ):
        challenger_key = champion.key

    # 교차-트랙 다중비교(본페로니) 보정 — K=비교 가능 트랙 중 챔피언을 뽑은 선택 다중성.
    comparable_count = sum(1 for t in ranked if t.comparability == COMPARABLE)
    adjusted_threshold, champion_robust = _multiplicity(champion, comparable_count)
    (
        track_count,
        known_count,
        unknown_count,
        max_n_obs,
        min_n_obs,
        lagging_keys,
        observation_health,
        observation_note,
    ) = _observation_quality(ranked, incumbent)

    headline, note = _summarize(
        ranked,
        champion,
        incumbent,
        challenger_key,
        robust=champion_robust,
        adjusted=adjusted_threshold,
        comparable_count=comparable_count,
        sig_prob=_sig_prob(champion),
    )
    return TournamentLeaderboard(
        schema_version=SCHEMA_VERSION,
        as_of_utc=as_of_utc,
        rows=ranked,
        champion_key=champion_key,
        incumbent_key=incumbent_key,
        challenger_key=challenger_key,
        headline=headline,
        note=note,
        comparable_count=comparable_count,
        adjusted_dsr_threshold=adjusted_threshold,
        champion_multiplicity_robust=champion_robust,
        track_count=track_count,
        known_count=known_count,
        unknown_count=unknown_count,
        max_n_obs=max_n_obs,
        min_n_obs=min_n_obs,
        lagging_keys=lagging_keys,
        observation_health=observation_health,
        observation_note=observation_note,
    )


def _summarize(
    ranked: list[TrackResult],
    champion: TrackResult | None,
    incumbent: TrackResult | None,
    challenger_key: str | None,
    *,
    robust: bool | None = None,
    adjusted: Decimal | None = None,
    comparable_count: int = 0,
    sig_prob: Decimal | None = None,
) -> tuple[str, str]:
    """헤드라인 + 보조 노트(정직 — 관측 부족이면 챔피언 선언 안 함).

    robust/adjusted/comparable_count/sig_prob 는 교차-트랙 다중비교 보정 결과 — 챔피언/
    도전자 헤드라인에 '운 좋은 우승'인지 정직하게 덧입힌다(재지정은 여전히 운영자 게이트).
    """
    parseable = [t for t in ranked if t.comparability != UNKNOWN]
    if not parseable:
        return ("🛑 토너먼트 판정 불가 — 어떤 트랙 판정도 읽을 수 없음.", "")

    comparable = [t for t in ranked if t.comparability == COMPARABLE]
    if not comparable:
        # 현재 상태: 전부 관측 누적 중. 최다 관측 트랙을 진척 표시로만.
        lead = max(
            (t for t in ranked if t.n_obs is not None),
            key=lambda t: t.n_obs,
            default=None,
        )
        tail = (
            f" 최다 관측: {lead.label}({lead.n_obs}/{lead.min_obs})."
            if lead is not None
            else ""
        )
        return (
            f"⏳ 아직 비교 불가 — 비교 가능 트랙 0개(모두 관측 부족, 누적 중).{tail}",
            "관측이 최소(스펙 035 기본 20)를 넘는 트랙이 나오면 그때 챔피언을 가린다. "
            "지표는 그전까지 잠정치(통계적으로 노이즈) — 챔피언 선언 안 함(거짓 자신만만 금지).",
        )

    if champion is None:
        # 비교 가능 트랙은 있으나 EDGE_CONFIRMED 가 없다 = 아직 아무도 엣지 확정 못 함.
        return (
            "➖ 엣지 확정 트랙 없음 — 비교 가능 트랙 모두 NO_EDGE(우위가 우연과 구별 안 됨). "
            "더 나은 후보 탐색 계속.",
            "비교 가능하지만 단순 보유를 과적합 보정 후 못 이긴 상태. 라이브 변경 사유 없음.",
        )

    champ_label = champion.label
    clause = _mult_clause(robust, sig_prob, adjusted, comparable_count)
    if challenger_key is not None:
        # 도전자가 라이브 검증 트랙을 앞섬(둘 다 비교 가능).
        if robust is False:
            # 운 좋은 우승 가능 — 도전자 경보를 정직하게 강등(재지정 보류).
            head = (
                f"⚠ 도전자 '{champ_label}'가 라이브 검증 트랙을 앞서나 교차-트랙 다중비교 "
                "보정 미통과 — 재지정 보류(운영자 게이트 X.4)."
            )
        else:
            head = (
                f"🚀 도전자 '{champ_label}'가 라이브 검증 트랙을 앞선다 — 둘 다 엣지 확정, "
                "재지정 후보. 단 자동 전환 아님(운영자 게이트 X.4)."
            )
        return (
            head,
            "라이브가 되려면 검증=배치 정합상 라이브 설정 지문을 이 트랙으로 맞춰야 한다"
            f"(운영자/세션 결정). 그 전까지 라이브는 현 검증 트랙 유지 — 전진 시계 보존. {clause}",
        )
    if champion.is_incumbent:
        robust_tag = ""
        if robust is True:
            robust_tag = " 교차-트랙 다중비교 보정도 통과."
        elif robust is False:
            robust_tag = " 단, 교차-트랙 다중비교 보정은 미통과(아래 노트)."
        return (
            f"🏆 라이브 검증 트랙 '{champ_label}'이 선두 — 도전자 없음, 현 전략 유지.{robust_tag}",
            "검증 트랙이 토너먼트 챔피언(엣지 확정 1위)이다. 재지정 불필요 — 현 전략으로 "
            f"자본 사다리 진행. {clause}",
        )
    # 챔피언이 비-incumbent 인데 incumbent 가 아직 비교 불가(관측 부족) → 직접 비교 전.
    inc_note = ""
    if incumbent is not None:
        inc_note = (
            f" 라이브 검증 트랙('{incumbent.label}')은 아직 관측 부족"
            f"({incumbent.n_obs}/{incumbent.min_obs}) — 직접 비교는 그 트랙도 관측 채운 뒤."
        )
    return (
        f"🟢 '{champ_label}'가 먼저 엣지 확정(EDGE_CONFIRMED) — 비교 가능 1위.{inc_note}",
        "도전자가 먼저 확정했으나 검증 트랙이 비교 가능해질 때까지 사과 대 사과 비교는 보류"
        f"(거짓 경보 0). 라이브 변경은 운영자 게이트(헌법 X.4). {clause}",
    )


__all__ = [
    "COMPARABLE",
    "DEFAULT_DSR_THRESHOLD",
    "DEFAULT_MIN_OBS",
    "EDGE_CONFIRMED",
    "INSUFFICIENT_DATA",
    "NO_EDGE",
    "OBS_HEALTH_BLOCKED",
    "OBS_HEALTH_DEGRADED",
    "OBS_HEALTH_OK",
    "PREMATURE",
    "SCHEMA_VERSION",
    "UNKNOWN",
    "TournamentLeaderboard",
    "TrackResult",
    "build_track_result",
    "rank_tournament",
]

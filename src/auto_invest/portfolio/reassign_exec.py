"""스펙 055 — 자율 전략 진화: 재지정 *실행* (순수 함수, 산출물 계산만).

`auto_reassign.decide_reassignment` 이 5중 게이트를 전부 통과해 REASSIGN 을 내면, 이 모듈이
그 결정을 *실행 가능한 산출물 두 개*로 바꾼다 — 전부 순수 함수다(파일 I/O·네트워크·주문 0).
디스크 쓰기와 PR 발행은 워크플로가, 실주문은 시장시간 스케줄이 한다(결정/실행 분리).

두 산출물:

  1. **새 라이브 설정 toml 내용** — 챔피언(challenger) 트랙의 *전략 블록*([portfolio] ~ 이후
     모든 섹션)을 현 라이브 설정에 그대로 이식한다. 라이브 *운영/거래집합 블록*([caps]·
     [whitelist])은 라이브 원본을 **보존**한다. 즉 재지정은 "무엇을(전략·가중·신호)"만 바꾸고
     "얼마나(자본·캡)"·"어디서(거래 집합)"는 안 바꾼다(헌법 X.5: WHICH not HOW MUCH).
     전략 블록은 *텍스트로 그대로 복사*한다 — 값 재직렬화(예: "0.99" 문자열 ↔ float, 인라인
     테이블 재배열)로 인한 미세 변형 위험 0. 이식 출처 파일은 이미 검증·테스트된 deploy 설정.

  2. **rung 0 자본 사다리 센티넬** — `capital_ladder.render_ladder_sentinel(rung=0)`. 새 전략은
     아직 *라이브로* 검증 안 됐으므로 자본을 0%(무장 해제)로 리셋한다 → forward 재검증부터
     10% 연구·20% 탐색·25%·50%·100% 로 자율 재승격(스펙 050 사다리). 검증 안 한 전략에
     자본이 즉시 실리는 것을 막는 ⑤번 안전장치다.

안전 경계(헌법 II 비협상 — 자율 재지정으로 절대 못 넘김):
  challenger 의 거래 유니버스가 라이브 화이트리스트의 *부분집합이 아니면* 재지정을 거부한다
  (ReassignExecError). 라이브 거래 집합 확대(새 종목 편입)는 운영자 게이트지 자율 재지정의
  범위가 아니다. 그래서 자율 재지정은 *이미 라이브로 승인된 거래 집합 안에서* 전략(가중·신호)
  만 바꾼다 — 예: global(역변동성) → globalfixed(등가중)는 SPY·IEF·GLD 안이라 허용,
  wide(11슬리브, QQQ·EFA·… 포함)는 거래 집합 밖이라 거부.

비위임 불변(헌법 I 캡·II 화이트리스트·IV 감사·VI 단계 승격·VIII.A 장중 배포 금지·스펙 014
서킷 브레이커)은 그대로다. 이 모듈은 라이브 *설정 파일 내용*을 계산할 뿐 — 머지·무장·실주문은
여전히 각자의 게이트(PR 머지·사다리 센티넬·시장시간 스케줄)를 통과해야 한다.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from auto_invest.portfolio.auto_reassign import ACTION_REASSIGN, ReassignDecision
from auto_invest.portfolio.capital_ladder import ladder_schedule_ko, render_ladder_sentinel

# 트랙 key → forward-paper deploy 설정 파일 경로(단일 출처).
#   rebalance-paper-forward.yml 의 각 ARM `cfg=` 와 일치해야 한다. challenger_key/incumbent_key
#   는 analytics.forward_tournament 가 TrackResult.key 로 설정하고, 그 값은
#   scripts/forward_tournament_probe.py TRACKS 의 key 와 같다(예: "global", "globalfixed").
TRACK_DEPLOY_CONFIGS: dict[str, str] = {
    "trend": "deploy/canary-portfolio.toml",
    "notrend": "deploy/canary-portfolio-notrend.toml",
    "rmbeta": "deploy/risk-managed-beta-portfolio.toml",
    "multiasset": "deploy/multi-asset-trend-portfolio.toml",
    "global": "deploy/global-trend-portfolio.toml",  # incumbent (라이브 검증 트랙)
    "globalfixed": "deploy/global-trend-fixed-portfolio.toml",
    "wide": "deploy/global-trend-wide-portfolio.toml",
}

# 자동 재지정이 교체하는 라이브 설정 파일 — rebalance-live-canary.yml 이 --portfolio 로 읽는다.
LIVE_CONFIG_PATH = "deploy/canary-live-portfolio.toml"

# 챔피언에서 가져오지 *않고* 라이브 원본에서 보존하는 운영/안전 경계 섹션.
#   caps      : 자본 규모·캡("얼마나" — X.4 자본 사다리 소관, 재지정이 안 건드림).
#   whitelist : 라이브 거래 집합("어디서" — 헌법 II 비협상, 확대는 운영자 게이트).
PRESERVE_FROM_LIVE = ("caps", "whitelist")

# 전략 블록의 시작 헤더. 이 헤더(컬럼 0)부터 EOF 까지가 "전략"이고 챔피언에서 이식한다.
# 그 앞(머리말 + [caps] + [whitelist])은 라이브 운영/안전 경계라 보존한다.
_STRATEGY_HEADER_PREFIX = "[portfolio"


class ReassignExecError(ValueError):
    """재지정 실행 거부 — 안전 경계 위반(거래 집합 확대 등) 또는 실행 불가 결정.

    보수적 fail-safe: 경계가 불명하거나 의심스러우면 산출물을 만들지 않고 raise 한다.
    재지정 실행을 *안 하는* 쪽이 항상 안전(현 전략·자본 유지).
    """


@dataclass(frozen=True)
class ReassignmentExecution:
    """REASSIGN 결정의 실행 산출물 — 순수 계산(파일 I/O·주문 0). 포렌식 증거."""

    challenger_key: str
    incumbent_key: str | None
    live_config_path: str  # 교체 대상 라이브 설정 파일(LIVE_CONFIG_PATH)
    new_live_config_text: str  # 챔피언 전략 + 라이브 운영설정 보존
    rung0_sentinel_text: str  # 자본 사다리 rung 0 리셋 센티넬
    live_whitelist_symbols: tuple[str, ...]  # 보존된 라이브 거래 집합
    challenger_universe: tuple[str, ...]  # 챔피언 전략이 거래하는 종목(⊆ 화이트리스트)

    SCHEMA_VERSION = "1.0"

    def to_json_dict(self) -> dict:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "challenger_key": self.challenger_key,
            "incumbent_key": self.incumbent_key,
            "live_config_path": self.live_config_path,
            "live_whitelist_symbols": list(self.live_whitelist_symbols),
            "challenger_universe": list(self.challenger_universe),
        }


def deploy_config_path(track_key: str) -> str:
    """트랙 key → forward-paper deploy 설정 파일 경로(없으면 거부)."""
    try:
        return TRACK_DEPLOY_CONFIGS[track_key]
    except KeyError:
        raise ReassignExecError(
            f"트랙 key '{track_key}' 가 deploy 레지스트리에 없음 — 매핑 불명, 재지정 거부."
        ) from None


def _header_offset(text: str, header: str) -> int | None:
    """컬럼 0 에서 `header` 로 시작하는 첫 줄의 문자 오프셋(없으면 None)."""
    offset = 0
    for line in text.splitlines(keepends=True):
        if line.startswith(header):
            return offset
        offset += len(line)
    return None


def _strategy_offset(text: str, *, label: str) -> int:
    """`[portfolio` 헤더(전략 블록 시작)의 문자 오프셋. 없으면 거부."""
    off = _header_offset(text, _STRATEGY_HEADER_PREFIX)
    if off is None:
        raise ReassignExecError(
            f"{label}: '[portfolio]' 섹션을 찾지 못함 — 전략 블록 경계 불명, 재지정 거부."
        )
    return off


def build_live_config_text(
    *,
    live_text: str,
    challenger_text: str,
    challenger_key: str,
    incumbent_key: str | None,
    now: datetime,
) -> str:
    """라이브 설정 + 챔피언 설정 → 새 라이브 설정 내용(순수 텍스트 스플라이스).

    라이브의 머리말 + [caps] + [whitelist] 를 보존하고, 전략 블록([portfolio] ~)을 챔피언의
    것으로 교체한다. 맨 위에 자율 재지정 출처 배너를 단다. 결과를 파싱해 챔피언 유니버스가
    라이브 화이트리스트의 부분집합인지 검증(헌법 II) — 아니면 ReassignExecError.
    """
    live_strat = _strategy_offset(live_text, label=f"라이브 설정({LIVE_CONFIG_PATH})")
    # 보존 대상([caps]·[whitelist])은 전략 블록 *앞*에 있어야 한다(보존 경계가 명확하도록).
    for section in PRESERVE_FROM_LIVE:
        off = _header_offset(live_text, f"[{section}]")
        if off is None or off >= live_strat:
            raise ReassignExecError(
                f"라이브 설정에 [{section}] 가 [portfolio] 앞에 없음 — 보존 경계 불명, 재지정 거부."
            )
    live_head = live_text[:live_strat]  # 머리말 + [caps] + [whitelist] (주석 포함)

    chal_label = f"챔피언 설정({TRACK_DEPLOY_CONFIGS.get(challenger_key, challenger_key)})"
    chal_strat = _strategy_offset(challenger_text, label=chal_label)
    challenger_strategy = challenger_text[chal_strat:]  # [portfolio] ~ 이후 전체(전략 섹션들)

    banner = _provenance_banner(challenger_key, incumbent_key, now)
    head = live_head if live_head.endswith("\n") else live_head + "\n"
    body = challenger_strategy if challenger_strategy.endswith("\n") else challenger_strategy + "\n"
    new_text = f"{banner}{head}\n{body}"

    _assert_universe_within_whitelist(new_text, challenger_key)
    return new_text


def _provenance_banner(
    challenger_key: str, incumbent_key: str | None, now: datetime
) -> str:
    """재지정 출처/안전 경계를 설명하는 자동 생성 머리말 배너."""
    chal_path = TRACK_DEPLOY_CONFIGS.get(challenger_key, f"deploy/<{challenger_key}>.toml")
    inc = incumbent_key or "(불명)"
    ts = now.date().isoformat() if isinstance(now, datetime) else str(now)
    return (
        "# ⚠ 자동 생성됨 — 자율 전략 재지정(스펙 055, 헌법 X.5). 직접 편집하지 말 것.\n"
        f"#   재지정({ts}): 라이브 전략을 '{inc}' → '{challenger_key}' 로 교체.\n"
        f"#   전략 블록([portfolio] 이후)은 {chal_path} 에서 그대로 이식했다(텍스트 복사).\n"
        f"#   라이브 운영/거래집합([caps]·[whitelist])은 {LIVE_CONFIG_PATH} 원본을 보존한다 —\n"
        "#   재지정은 '무엇을(전략)'만 바꾸고 '얼마나(자본·캡)'·'어디서(거래 집합)'는 안 바꾼다\n"
        "#   (헌법 X.5: WHICH not HOW MUCH). 챔피언 유니버스가 라이브 화이트리스트 밖이면\n"
        "#   자율 재지정은 거부된다(거래 집합 확대 = 운영자 게이트, 헌법 II).\n"
        "#   ⓘ 아래 원본 머리말 주석 일부는 옛 전략 설명이라 stale 할 수 있다 — 권위는\n"
        f"#     [portfolio] 블록과 이식 출처 {chal_path} 의 주석이다.\n"
        "#     5중 게이트 통과 기록은 이 변경을 만든 PR 본문에 있다.\n"
        "#   교체 직후 자본 사다리는 rung 0(0%, 무장 해제)로 리셋된다 — 새 전략은 forward\n"
        f"#   재검증부터 {ladder_schedule_ko(start_rung=1)} 순서로 자율 재승격(스펙 050).\n"
        "#   검증 안 한 전략에 자본이 즉시 실리는 것을 막는다.\n"
        "\n"
    )


def _assert_universe_within_whitelist(text: str, challenger_key: str) -> None:
    """Validate signal universe, optional execution map, and live whitelist."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ReassignExecError(f"재지정 결과가 유효한 TOML 이 아님: {e}") from e
    symbols = set(data.get("whitelist", {}).get("symbols", []))
    universe = list(data.get("portfolio", {}).get("universe", []))
    if not symbols:
        raise ReassignExecError(
            "재지정 결과 [whitelist].symbols 가 비어 있음 — 라이브 거래 집합 불명, 거부."
        )
    if not universe:
        raise ReassignExecError(
            "재지정 결과 [portfolio].universe 가 비어 있음 — 챔피언 전략 유니버스 불명, 거부."
        )
    raw_map = data.get("execution", {}).get("symbol_map", {})
    if raw_map:
        symbol_map = {str(k).upper(): str(v).upper() for k, v in raw_map.items()}
        if set(symbol_map) != set(universe):
            raise ReassignExecError(
                f"챔피언 '{challenger_key}' 신호 유니버스와 execution 매핑 키 불일치 — "
                "검증 신호를 체결 종목으로 완전히 옮길 수 없어 재지정 거부."
            )
        if len(set(symbol_map.values())) != len(symbol_map):
            raise ReassignExecError("execution 매핑 값 중복 — 1:1 체결 경계 불명, 재지정 거부.")
        execution_universe = list(symbol_map.values())
    else:
        execution_universe = universe
    outside = [s for s in execution_universe if s not in symbols]
    if outside:
        raise ReassignExecError(
            f"챔피언 '{challenger_key}' 체결 유니버스 {outside} 가 라이브 화이트리스트 "
            f"{sorted(symbols)} 밖 — 라이브 거래 집합 확대는 운영자 게이트(헌법 II). "
            "자율 재지정 거부."
        )


def build_rung0_sentinel(
    *,
    account_nav_usd: Decimal,
    run_seq: int,
    dd_budget_pct: Decimal,
    rung_entered: date,
    challenger_key: str,
    incumbent_key: str | None,
) -> str:
    """재지정 직후 자본 사다리를 rung 0(0%, 무장 해제)로 리셋하는 센티넬 본문(⑤)."""
    evidence = (
        f"자율 전략 재지정(스펙 055): 라이브 '{incumbent_key or '?'}' → '{challenger_key}'. "
        "5중 게이트 전부 통과 → 자본 사다리 rung 0 리셋(새 전략을 forward 재검증부터 자율 재승격)."
    )
    return render_ladder_sentinel(
        rung=0,
        capital_usd=0,  # rung 0 = 0% of NAV (무장 해제)
        account_nav_usd=account_nav_usd,
        rung_entered=rung_entered,
        run_seq=run_seq,
        dd_budget_pct=dd_budget_pct,
        evidence=evidence,
    )


def build_reassignment(
    *,
    decision: ReassignDecision,
    live_text: str,
    challenger_text: str,
    account_nav_usd: Decimal,
    run_seq: int,
    dd_budget_pct: Decimal,
    rung_entered: date,
    now: datetime,
) -> ReassignmentExecution:
    """REASSIGN 결정 → 실행 산출물(새 라이브 설정 + rung 0 센티넬). 순수.

    decision.action 이 REASSIGN 이 아니면 거부(다른 결정은 라이브 무변경). challenger_key 가
    deploy 레지스트리에 없거나 incumbent 와 같으면 거부(모순). 거래 집합 확대(헌법 II)는
    build_live_config_text 안에서 거부된다.
    """
    if decision.action != ACTION_REASSIGN:
        raise ReassignExecError(
            f"실행 불가: 결정이 REASSIGN 이 아님(action={decision.action!r}). 라이브 무변경."
        )
    challenger_key = decision.challenger_key
    if not challenger_key:
        raise ReassignExecError("REASSIGN 인데 challenger_key 가 없음 — 모순, 거부.")
    if challenger_key not in TRACK_DEPLOY_CONFIGS:
        raise ReassignExecError(
            f"challenger_key '{challenger_key}' 가 deploy 레지스트리에 없음 — 매핑 불명, 거부."
        )
    if challenger_key == decision.incumbent_key:
        raise ReassignExecError(
            f"challenger 와 incumbent 가 같음('{challenger_key}') — 재지정 의미 없음, 거부."
        )

    new_text = build_live_config_text(
        live_text=live_text,
        challenger_text=challenger_text,
        challenger_key=challenger_key,
        incumbent_key=decision.incumbent_key,
        now=now,
    )
    # build_live_config_text 가 이미 검증·파싱했다. 메타데이터 추출용 재파싱(저렴).
    data = tomllib.loads(new_text)
    symbols = tuple(data["whitelist"]["symbols"])
    universe = tuple(data["portfolio"]["universe"])

    sentinel = build_rung0_sentinel(
        account_nav_usd=account_nav_usd,
        run_seq=run_seq,
        dd_budget_pct=dd_budget_pct,
        rung_entered=rung_entered,
        challenger_key=challenger_key,
        incumbent_key=decision.incumbent_key,
    )
    return ReassignmentExecution(
        challenger_key=challenger_key,
        incumbent_key=decision.incumbent_key,
        live_config_path=LIVE_CONFIG_PATH,
        new_live_config_text=new_text,
        rung0_sentinel_text=sentinel,
        live_whitelist_symbols=symbols,
        challenger_universe=universe,
    )


__all__ = [
    "LIVE_CONFIG_PATH",
    "PRESERVE_FROM_LIVE",
    "TRACK_DEPLOY_CONFIGS",
    "ReassignExecError",
    "ReassignmentExecution",
    "build_live_config_text",
    "build_reassignment",
    "build_rung0_sentinel",
    "deploy_config_path",
]

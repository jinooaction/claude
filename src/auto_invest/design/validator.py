"""Spec 010 T012 — 생성된 룰 TOML 정적 검증.

Claude 응답을 TOML로 파싱한 뒤 spec 001의 pydantic 모델로 1차 검증, 추가로
contracts/claude-prompt.md "안전 추가 검증" 검사:

1. caps 값 양수 + 헌법 권장치 이내.
2. 모든 rule.symbol이 whitelist.symbols에 포함.
3. order_type이 whitelist.order_types에 포함.
4. KIS 잔고 최소 한도($10) 충족.
5. 종목이 미국 6자 미만 휴리스틱.

운영자 "의도 자본 $100" 정책은 제거됨 — 자본은 항상 KIS 잔고를 그대로
사용한다. 잔고 자체가 최소 한도($10) 미만일 때만 거부.

실패 시 한글 사유 + RULE_DESIGN_REJECTED 호출자가 결정.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from pydantic import ValidationError

from auto_invest.config.caps import SizingCaps
from auto_invest.config.rules import TradingRule
from auto_invest.config.whitelist import Whitelist

_RejectReason = Literal[
    "parse_error",
    "whitelist_violation",
    "cap_violation",
    "insufficient_balance",
]


@dataclass(frozen=True)
class ValidationResult:
    """`validate_generated_rules`의 리턴값.

    - ok=True: 검증 통과. 호출자가 paper-run 진입.
    - ok=False: 거부. reason + detail이 audit 페이로드와 한글 보고에 사용.
    """

    ok: bool
    reason: _RejectReason | None = None
    detail: str = ""


_MIN_BALANCE_USD = Decimal("10")
_MAX_PER_TRADE_PCT = Decimal("10")  # 헌법 권장 5%, 안전 마진 10% 상한
_MAX_PER_SYMBOL_PCT = Decimal("40")  # 헌법 권장 20%, 안전 마진 40% 상한
_MAX_GLOBAL_EXPOSURE_PCT = Decimal("100")


def validate_generated_rules(
    toml_text: str,
    *,
    kis_balance_usd: Decimal,
) -> ValidationResult:
    """생성된 룰 TOML을 정적 검증.

    파싱 실패·whitelist 위반·cap 위반·잔고 부족 중 하나라도 걸리면 ok=False.
    """
    # 1. 잔고 최소 한도 — TOML 파싱 전 사전 검증.
    if kis_balance_usd < _MIN_BALANCE_USD:
        return ValidationResult(
            ok=False,
            reason="insufficient_balance",
            detail=(
                f"KIS 잔고 ${kis_balance_usd}이 최소 한도 ${_MIN_BALANCE_USD} 미만입니다. "
                "입금 후 다시 시도해주세요."
            ),
        )

    # 2. TOML 파싱.
    try:
        parsed = tomllib.loads(toml_text)
    except tomllib.TOMLDecodeError as exc:
        return ValidationResult(
            ok=False,
            reason="parse_error",
            detail=f"Claude가 생성한 TOML 파싱 실패: {exc}",
        )

    # 3. caps section.
    try:
        caps = SizingCaps.model_validate(parsed.get("caps", {}))
    except ValidationError as exc:
        return ValidationResult(
            ok=False,
            reason="cap_violation",
            detail=f"[caps] 섹션 유효성 실패: {exc}",
        )

    if caps.per_trade_pct > _MAX_PER_TRADE_PCT:
        return ValidationResult(
            ok=False,
            reason="cap_violation",
            detail=(
                f"per_trade_pct {caps.per_trade_pct}이 안전 상한 {_MAX_PER_TRADE_PCT} 초과."
            ),
        )
    if caps.per_symbol_pct > _MAX_PER_SYMBOL_PCT:
        return ValidationResult(
            ok=False,
            reason="cap_violation",
            detail=(
                f"per_symbol_pct {caps.per_symbol_pct}이 안전 상한 "
                f"{_MAX_PER_SYMBOL_PCT} 초과."
            ),
        )
    if caps.global_exposure_pct > _MAX_GLOBAL_EXPOSURE_PCT:
        return ValidationResult(
            ok=False,
            reason="cap_violation",
            detail=(
                f"global_exposure_pct {caps.global_exposure_pct}이 100 초과."
            ),
        )

    # 4. whitelist section.
    try:
        whitelist = Whitelist.model_validate(parsed.get("whitelist", {}))
    except ValidationError as exc:
        return ValidationResult(
            ok=False,
            reason="whitelist_violation",
            detail=f"[whitelist] 섹션 유효성 실패: {exc}",
        )

    # 5. rules — 각 항목 검증 + symbol/order_type whitelist 매핑 + 미국 6자 휴리스틱.
    for i, rule_data in enumerate(parsed.get("rules", [])):
        try:
            rule = TradingRule.model_validate(rule_data)
        except ValidationError as exc:
            return ValidationResult(
                ok=False,
                reason="parse_error",
                detail=f"[[rules]] 항목 {i} 유효성 실패: {exc}",
            )

        if rule.symbol not in whitelist.symbols:
            return ValidationResult(
                ok=False,
                reason="whitelist_violation",
                detail=(
                    f"룰 {rule.id!r}의 종목 {rule.symbol!r}가 whitelist에 없습니다."
                ),
            )

        if rule.action.order_type not in whitelist.order_types:
            return ValidationResult(
                ok=False,
                reason="whitelist_violation",
                detail=(
                    f"룰 {rule.id!r}의 order_type "
                    f"{rule.action.order_type.value!r}가 whitelist에 없습니다."
                ),
            )

        if len(rule.symbol) > 5 or not rule.symbol.isalpha():
            return ValidationResult(
                ok=False,
                reason="whitelist_violation",
                detail=(
                    f"종목 {rule.symbol!r}이 미국 주식·ETF 형식이 아닙니다 "
                    "(5자 이하 영문)."
                ),
            )

    # 6. whitelist의 모든 종목도 미국 6자 미만 휴리스틱.
    for sym in whitelist.symbols:
        if len(sym) > 5 or not sym.isalpha():
            return ValidationResult(
                ok=False,
                reason="whitelist_violation",
                detail=(
                    f"whitelist 종목 {sym!r}이 미국 주식·ETF 형식이 아닙니다."
                ),
            )

    return ValidationResult(ok=True)

"""Spec 010 T011 — Claude system+user prompt 조립.

contracts/claude-prompt.md 명세 그대로. 시스템 prompt에 헌법 I·II·III·VI
안전 제약 + TOML 출력 형식을 박아두고, user prompt에 운영자 의도 + KIS 계좌
상태 + (재시도 시) 직전 실패 사유를 넣는다.

Claude 응답은 INTERPRETATION JSON 주석 + TOML 본문 형태. `parse_claude_response`
가 둘을 분리해 반환.
"""
# ruff: noqa: E501 — system prompt 한글 문장은 의미 단위로 한 줄 유지.

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal

SYSTEM_PROMPT = """\
당신은 운영자(mason)의 자동 투자 시스템 룰 설계자입니다. 운영자가 자연어 한 줄로 의도를 적어주면, 당신은 다음 안전 제약을 모두 만족하는 룰 TOML 1개를 응답합니다.

# 안전 제약 (헌법 v3.0.0 I·II·III·VI)

1. **자기자본 비율 제한 (헌법 I)**: 모든 룰은 cap 게이트를 통과해야 합니다.
   - 단일 주문 비중(per_trade_pct): 5% 이하 권장.
   - 단일 종목 비중(per_symbol_pct): 20% 이하 권장.
   - 전체 자본 노출(global_exposure_pct): 80% 이하 권장.

2. **종목 화이트리스트 (헌법 II)**: 룰에 사용된 모든 종목은 `[whitelist].symbols`에 명시되어야 합니다. 미국 상장 주식·ETF만. 옵션·채권·해외 시장 금지.

3. **LLM 판단점 제한 (헌법 III)**: 생성된 룰 자체는 매 tick에서 LLM 호출을 하지 않습니다. 룰은 결정적 트리거(가격·지표·시간)만 사용합니다.

4. **단계적 확장 (헌법 VI)**: 새 룰은 모두 `stage = "CANARY"`로 시작.

# 출력 형식

응답은 다음 형태로 작성하세요. 코드 펜스 사용 금지, 본문 외 설명 금지.

# INTERPRETATION: {"max_drawdown_pct": <N>, "per_symbol_pct": <N>, "universe": [...], "schedule": "..."}

[caps]
per_trade_pct = <number>
per_symbol_pct = <number>
global_exposure_pct = <number>
canary_capital_pct = <number>
canary_min_duration_days = <int>
canary_acceptance_drawdown_pct = <number>

[whitelist]
symbols = ["..."]
accounts = ["..."]
order_types = ["MARKET", "LIMIT"]
sessions = ["REGULAR"]

[[rules]]
id = "rule_<descriptive>"
symbol = "..."
stage = "CANARY"
priority = <int>
enabled = true

[rules.trigger]
kind = "price"
direction = "<="
threshold = <number>
cooldown_seconds = <int>

[rules.action]
side = "BUY"
order_type = "MARKET"
qty = <int>
limit_price = "0"

# 모호한 의도의 기본값

- "위험 보통" → max_drawdown 5%, per_symbol_pct 20%.
- "위험 낮음" → max_drawdown 3%, per_symbol_pct 10%.
- "위험 높음" → max_drawdown 10%, per_symbol_pct 30%.
- "미국 대형주 분산" → VOO, QQQ, SPY 중 1~3종.
- 적립 주기 미명시 → 매주 월요일.

# 자본 한도

자본은 KIS 잔고(예수금)를 그대로 사용합니다. 운영자가 자연어로 "100달러 적립" 같이 적어도 그 숫자는 의도를 짐작하는 단서이지 자본 상한이 아닙니다. 보유 종목 정보가 함께 주어지면 그것을 활용해 룰을 구성하세요 (예: 이미 보유한 종목을 우선 매수 대상에 포함, 평단보다 낮은 트리거를 추가 매수 조건으로 사용).

잔고 < $10이면 다음 한 줄만 응답:

ERROR: 잔고 부족 (현재 잔고 $X)
"""


def build_system_prompt() -> str:
    """Claude system prompt — 정적이며 호출마다 동일."""
    return SYSTEM_PROMPT


def build_user_prompt(
    *,
    intent: str,
    kis_balance_usd: Decimal,
    kis_holdings: list[dict],
    retry_context: dict | None = None,
) -> str:
    """Claude user prompt — 호출마다 변동.

    `retry_context`가 주어지면 직전 실패 사유 + 직전 TOML을 포함해 Claude가
    동일 실수를 피할 수 있게 한다 (R-D10).
    """
    holdings_lines = (
        "\n".join(
            f"  - {h['symbol']}: {h.get('qty', 0)}주 (평단 ${h.get('avg_cost_usd', '?')})"
            for h in kis_holdings
        )
        or "  - (보유 종목 없음)"
    )
    retry_block = ""
    if retry_context:
        retry_block = (
            "\n# 직전 시도 정보\n\n"
            f"직전 시도가 다음 사유로 실패했습니다:\n"
            f"- 사유: {retry_context['reason']}\n"
            f"- 상세: {retry_context['detail']}\n\n"
            "직전 생성한 TOML:\n"
            f"{retry_context.get('previous_toml', '(없음)')}\n\n"
            "같은 의도로 다시 룰을 설계해주세요. 위 사유를 피해야 합니다.\n"
        )
    return (
        f"# 운영자 의도\n\n{intent}\n\n"
        "# KIS 계좌 상태\n\n"
        f"- 예수금: {kis_balance_usd} USD\n"
        "- 보유 종목:\n"
        f"{holdings_lines}\n"
        f"{retry_block}"
    )


@dataclass(frozen=True)
class ParsedClaudeResponse:
    """`parse_claude_response`의 결과.

    `error`가 None이 아니면 Claude가 "ERROR: ..." 로 응답한 경우.
    """

    error: str | None
    interpretation: dict
    rules_toml: str


_INTERPRETATION_RE = re.compile(r"^#\s*INTERPRETATION:\s*(\{.*?\})\s*$", re.MULTILINE)


def parse_claude_response(text: str) -> ParsedClaudeResponse:
    """Claude 응답 텍스트를 INTERPRETATION 주석 + TOML 본문으로 분리.

    - 응답 첫 줄이 `ERROR:`로 시작 → `error` 필드에 메시지 담음.
    - 그 외에는 INTERPRETATION 라인 1개와 그 이후의 TOML 본문을 추출.
    """
    stripped = text.lstrip()
    if stripped.startswith("ERROR:"):
        first_line = stripped.split("\n", 1)[0]
        return ParsedClaudeResponse(
            error=first_line[len("ERROR:") :].strip(),
            interpretation={},
            rules_toml="",
        )

    interp_match = _INTERPRETATION_RE.search(text)
    interpretation: dict = {}
    if interp_match:
        try:
            interpretation = json.loads(interp_match.group(1))
        except json.JSONDecodeError:
            interpretation = {}

    # INTERPRETATION 주석을 제외한 나머지 — 본문이 TOML.
    rules_toml = (
        text[: interp_match.start()] + text[interp_match.end() :]
        if interp_match
        else text
    )
    return ParsedClaudeResponse(
        error=None,
        interpretation=interpretation,
        rules_toml=rules_toml.strip(),
    )

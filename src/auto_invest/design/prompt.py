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

# INTERPRETATION: {"max_drawdown_pct": <N>, "per_symbol_pct": <N>, "universe": [...], "schedule": "...", "holdings_applied": ["averaging_down:VOO", "concentration_cap_skipped:AAPL"]}

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

# 트리거 종류 (`kind`는 반드시 아래 셋 중 하나입니다. `schedule` 등 다른 값은 절대 쓰지 마세요.)

- **시간 트리거 `kind = "time"` (적립·정기 매수용)**
  - `at_time`: "HH:MM" 24시간 형식만 (예 "09:35"). 요일이나 날짜를 이 필드에 넣지 마세요.
  - `weekdays`: 요일 배열. `[0]`=월요일 (0=월 1=화 2=수 3=목 4=금 5=토 6=일). 여러 요일은 `[0, 2, 4]`. 필드를 생략하면 매일 발동.
  - `cooldown_seconds`: 같은 룰의 재발동 최소 간격(초). 매주 1회면 604800, 매일 1회면 86400.
- **가격 트리거 `kind = "price"`**: `direction`("<=" 또는 ">="), `threshold`(양수), `cooldown_seconds`.
- **지표 트리거 `kind = "indicator"`**: `indicator`, `params`, `timeframe`("1d"·"1h"·"5m" 등), `cooldown_seconds`.

적립(정기 매수)은 반드시 시간 트리거(`kind = "time"`)로 만드세요. 요일은 `at_time`이 아니라 `weekdays`로 표현합니다. 적립용 시간 트리거 예시 ("매주 월요일 09:35 매수"):

[rules.trigger]
kind = "time"
at_time = "09:35"
weekdays = [0]
cooldown_seconds = 604800

[rules.action]
side = "BUY"
order_type = "MARKET"
qty = <분할 매수 수량>
limit_price = "0"

# 모호한 의도의 기본값

- "위험 보통" → max_drawdown 5%, per_symbol_pct 20%.
- "위험 낮음" → max_drawdown 3%, per_symbol_pct 10%.
- "위험 높음" → max_drawdown 10%, per_symbol_pct 30%.
- "미국 대형주 분산" → VOO, QQQ, SPY 중 1~3종.
- 적립 주기 미명시 → 매주 월요일 (`kind = "time"`, `weekdays = [0]`, `cooldown_seconds = 604800`).

# 자본 한도

자본은 KIS 잔고(예수금)를 그대로 사용합니다. 운영자가 자연어로 "100달러 적립" 같이 적어도 그 숫자는 의도를 짐작하는 단서이지 자본 상한이 아닙니다.

잔고 < $10이면 다음 한 줄만 응답:

ERROR: 잔고 부족 (현재 잔고 $X)

# 보유 종목 활용 패턴

보유 종목 정보(symbol·qty·평단 USD)가 함께 주어지면 다음 세 패턴 중 운영자 의도와 정렬되는 것을 적용하세요. 적용한 패턴은 INTERPRETATION JSON의 `holdings_applied` 키에 배열로 기록하세요 (적용 안 한 경우 빈 배열 `[]`).

1. **추가 매수 (averaging-down) — 기본 적용**. 보유 종목 X의 평단이 $A일 때, 다음 룰을 추가하세요:
   - trigger: `kind = "price"`, `direction = "<="`, `threshold = A * 0.95` (기본 5% 하락폭)
   - action: `side = "BUY"`, `order_type = "MARKET"`, `qty = <분할 매수 수량>`
   - id: `rule_avgdown_<symbol>`
   - `holdings_applied`에 `"averaging_down:<SYMBOL>"` 기록.
   - 운영자 의도에 "물타기 금지", "추가 매수 안 함", "no averaging down" 같은 단서가 명시되면 생략.

2. **익절 (take-profit) — 의도에 명시될 때만**. 의도에 "익절", "수익 실현", "차익 실현", "profit taking" 같은 표현이 있을 때만 적용:
   - trigger: `kind = "price"`, `direction = ">="`, `threshold = A * (1 + 익절폭)` (의도에 익절폭 없으면 기본 10%)
   - action: `side = "SELL"`, `order_type = "MARKET"`, `qty = <보유 수량의 일부>`
   - id: `rule_takeprofit_<symbol>`
   - `holdings_applied`에 `"take_profit:<SYMBOL>"` 기록.

3. **분산 안전장치 (concentration cap) — 항상 검사**. 보유 종목의 비중(= qty * 평단 / KIS 예수금)이 `per_symbol_pct`를 이미 초과한 경우, 그 종목에 대한 새 BUY 룰을 생성하지 마세요 (위 1번 averaging-down도 생략).
   - `holdings_applied`에 `"concentration_cap_skipped:<SYMBOL>"` 기록.

세 패턴 모두 화이트리스트(`[whitelist].symbols`)에 종목이 포함돼야 작동하므로, 보유 종목은 빠짐없이 화이트리스트에 추가하세요.
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

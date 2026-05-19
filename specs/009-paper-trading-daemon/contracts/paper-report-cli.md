# Contract: `auto-invest paper-report`

**Spec**: 009 · **Phase**: 1 · **Date**: 2026-05-19

paper-run의 audit_log를 집계해 룰 튜닝용 리포트를 출력하는 CLI. read-only.

---

## Usage

```
auto-invest paper-report \
    --since ISO8601 \
    [--until ISO8601] \
    [--db PATH] \
    [--format {text,json}]
```

**옵션**:
- `--since` (필수): 집계 시작 시각 (UTC, ISO8601). 예 `2026-05-12T00:00:00Z`.
- `--until` (선택): 집계 종료 시각. 미지정 시 현재 시각.
- `--db` (선택): SQLite 경로. 기본 `data/auto_invest.db`.
- `--format` (선택): `text` (기본) 또는 `json`. text는 사람용, json은 외부 도구·후속 자동 튜너 입력용.

---

## Behavior

1. SQLite read-only 모드로 연결 (`PRAGMA query_only = ON`).
2. since~until 범위 안의 paper 모드 이벤트만 6개 SELECT로 집계 (research.md R-P5).
3. `virtual_positions.recompute_virtual_positions(...)` 호출로 가상 포지션 derived.
4. 표 또는 JSON 형식으로 stdout에 출력.
5. exit 0.

audit_log가 비어 있어도 빈 리포트를 출력하고 exit 0 (edge case).

---

## 출력 — text format

```
auto-invest paper-report
========================
Period:        2026-05-12T00:00:00Z ~ 2026-05-19T00:00:00Z (7d)
Sessions:      3 (total uptime 47h 12m)
Ruleset SHA:   abc123... (3 distinct rulesets observed)

Per-rule statistics
-------------------
rule_id          signals  fills   denied   v.PnL (USD)
RULE_A_BUY_AAPL       42      5       37        +12.34
RULE_B_SELL_TSLA      18      4       14         -3.21
RULE_C_BUY_VOO         0      0        0         +0.00     ← never fired
...

Gate denials (top 5)
--------------------
gate                   count
per_trade_cap            87
whitelist                23
halt                      6
per_symbol_cap            5
global_exposure           2

External API errors
-------------------
order_rejected_by_broker   3
error (other)              1

Tuning feedback
---------------
Rules that never fired:    RULE_C_BUY_VOO, RULE_D_SELL_QQQ
Hottest rules (signals):   RULE_A_BUY_AAPL (42), RULE_B_SELL_TSLA (18)
quote_source fallback:     ask 87%, bid 11%, last 2% (낮을수록 좋음)

Virtual positions snapshot
--------------------------
symbol   qty    avg_cost   realized_pnl
AAPL      4     $148.20         $0.00
TSLA     -1     $230.50         -$3.21
```

`v.PnL`은 매수 평균단가와 (보유 중인 경우) 현재 시뮬 fill 가격의 차이 + 실현 손익을 합친 값. 미실현 손익은 paper-report 시점의 가상 포지션과 최근 fill 가격으로 추정.

---

## 출력 — json format

```json
{
  "period": {"since_utc": "...", "until_utc": "..."},
  "sessions": {"count": 3, "uptime_seconds": 169920},
  "rulesets_observed": ["abc123...", "..."],
  "per_rule": [
    {"rule_id": "RULE_A_BUY_AAPL", "signals": 42, "fills": 5, "denied": 37, "virtual_pnl_usd": "12.34"},
    ...
  ],
  "gate_denials": {"per_trade_cap": 87, "whitelist": 23, ...},
  "external_api_errors": {"order_rejected_by_broker": 3, "error": 1},
  "tuning_feedback": {
    "rules_never_fired": ["RULE_C_BUY_VOO", "RULE_D_SELL_QQQ"],
    "hottest_rules": [{"rule_id": "RULE_A_BUY_AAPL", "signals": 42}, ...],
    "quote_source_pct": {"ask": 0.87, "bid": 0.11, "last": 0.02}
  },
  "virtual_positions": [
    {"symbol": "AAPL", "qty": 4, "avg_cost_usd": "148.20", "realized_pnl_usd": "0.00"},
    ...
  ]
}
```

---

## Exit Codes

| Code | 의미 |
|------|------|
| 0 | 정상 출력 (빈 리포트 포함) |
| 1 | DB 오류 또는 예외 |
| 2 | 인자 오류 (잘못된 ISO8601, --since 누락) |

---

## 성능 계약

- audit_log 10만 row 기준 200ms 이내 (SC-003). 통합 테스트에서 합성 데이터로 검증.

## 안전 계약

- read-only (`PRAGMA query_only=ON`). live row·paper row 어느 것도 수정 안 함 (SC-006).
- live 모드 이벤트(`worker_started`, `fill`, `order_submitted` 등)는 집계에서 제외. paper 모드 이벤트만 본다 (FR-011).

---

## 테스트 가능한 invariants

| Invariant | 검증 방법 |
|-----------|----------|
| 빈 audit_log에서도 exit 0 + 빈 표 출력 | `tests/test_paper_report.py::test_empty_log` |
| live 이벤트는 집계에서 제외 | live `fill` row를 미리 INSERT 후 paper-report 실행, 결과에 미포함 확인 |
| 200ms 성능 예산 | 합성 10만 row 생성 후 `time.perf_counter()` 측정 |
| 가상 포지션 매수 평균단가 정확 | 합성 BUY 시퀀스 후 derived 결과의 avg_cost를 수동 계산값과 비교 |
| json 출력이 contracts 스키마와 일치 | json.loads 후 키·타입 검증 |

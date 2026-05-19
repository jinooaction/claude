# Contract: Rule-Design Audit Event Payloads

**Spec**: 010 · **Phase**: 1 · **Date**: 2026-05-19

K4 (`src/auto_invest/persistence/audit.py`)에 추가되는 4개 새 페이로드. 기존 28종(spec 009 머지 후 baseline)은 무수정.

본 변경은 **K4 추가 변경(additive)** — constitution v3.0.0 IX.D 자율 머지 채널.

---

## 1. `RuleDesignRequestedPayload`

design 명령 시작 시 1번 (mutex check + KIS 잔고 조회 후, Claude 호출 직전).

| 필드 | 타입 | 필수 | 의미 |
|------|------|------|------|
| `intent` | str | yes | 운영자 자연어 의도 (한 줄) |
| `requested_at_utc` | str (ISO8601) | yes | 호출 시각 |
| `kis_balance_usd` | str (Decimal) | yes | KIS 예수금 |
| `kis_holdings` | list[dict] | yes | `[{"symbol": "VOO", "qty": 0.2, "avg_cost_usd": "450.00"}, ...]` |
| `host` | str | yes | gethostname() |

### Audit 이벤트 타입

- `event_type` = `"RULE_DESIGN_REQUESTED"`

### Validation

- pydantic V2 BaseModel + `extra="forbid"` + `frozen=True`.
- `kis_balance_usd`는 Decimal 변환 가능 + 양수.

---

## 2. `RuleDesignCompletedPayload`

Claude 호출 + 정적 검증 + paper-run 1일분 통과 시 1번.

| 필드 | 타입 | 필수 | 의미 |
|------|------|------|------|
| `intent` | str | yes | 원본 의도 (글자 그대로) |
| `interpretation` | dict | yes | Claude의 정량 해석 (`max_drawdown_pct`, `per_symbol_pct`, `universe`, ...) |
| `generated_rules_toml` | str | yes | 생성된 TOML 전체 텍스트 |
| `model_id` | str | yes | Claude 모델 ID (예: `claude-opus-4-7`) |
| `tokens_input` | int | yes | 입력 토큰 |
| `tokens_output` | int | yes | 출력 토큰 |
| `cost_usd` | str (Decimal) | yes | 호출 비용 |
| `retry_index` | int | yes | 시도 번호 (1~3) |
| `paper_run_session_id` | int \| None | no | 검증에 사용된 paper-run row seq |

### Audit 이벤트 타입

- `event_type` = `"RULE_DESIGN_COMPLETED"`

### Validation

- `retry_index` 1 ≤ x ≤ 3.
- `cost_usd` ≤ 1.0 (SC-002).
- `generated_rules_toml`은 빈 문자열 아님.

---

## 3. `RuleDesignRejectedPayload`

모든 거부 사유.

| 필드 | 타입 | 필수 | 의미 |
|------|------|------|------|
| `reason` | Literal | yes | 11종 거부 사유 (data-model.md 참조) |
| `detail` | str | yes | 한글 메시지 |
| `retry_index` | int \| None | no | 재시도 번호 (None = 시도 전 거부) |
| `conflicting_event_id` | int \| None | no | mutex_conflict 시 |

### Audit 이벤트 타입

- `event_type` = `"RULE_DESIGN_REJECTED"`

### `reason` enum

```
parse_error · whitelist_violation · cap_violation · backtest_fail ·
paper_run_fail · operator_declined · max_retries · mutex_conflict ·
insufficient_balance · kis_token_failed · claude_api_error
```

---

## 4. `RuleDesignDeployedPayload`

운영자 OK 후 새 라이브 worker 시작 시 1번.

| 필드 | 타입 | 필수 | 의미 |
|------|------|------|------|
| `design_session_id` | int | yes | 대응 REQUESTED row seq |
| `live_session_id` | int | yes | 새 라이브 worker의 WORKER_STARTED row seq |
| `deployed_at_utc` | str (ISO8601) | yes | 라이브 시작 시각 |
| `total_capital_usd` | str (Decimal) | yes | 자본 |

### Audit 이벤트 타입

- `event_type` = `"RULE_DESIGN_DEPLOYED"`

---

## 통합 계약

- Append-only (constitution IV).
- `audit.append(conn, payload)` 시그니처 변경 없음.
- `AnyPayload` Union에 4종 추가.
- spec 009와 동일한 K4 additive 패턴.
- migration SQL 파일 0개 추가.

## 테스트 가능한 invariants

| Invariant | 검증 방법 |
|-----------|----------|
| 4개 페이로드 pydantic validation | `tests/unit/test_design_audit_payloads.py` |
| event_type 문자열 일관 | 동 테스트 |
| `cost_usd ≤ 1.0` 강제 | 동 테스트 |
| 기존 28종 페이로드 무수정 | `test_k4_touch_is_purely_additive` 확장 |
| audit.append 통합 동작 | 동 테스트 |

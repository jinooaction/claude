# Data Model: 자동 룰 설계자 (spec 010)

**Phase**: 1 · **Date**: 2026-05-19

본 스펙은 신규 SQLite 테이블·migration 0개. 모든 design 상태는 audit_log의 신규 이벤트 4종으로 표현된다.

---

## 엔티티 개요

```
+------------------------------+   1..N    +------------------------------+
| RuleDesignSession            |-produces->| AuditEvent (rule_design)     |
| (RULE_DESIGN_REQUESTED ~     |           | • RuleDesignRequested        |
|  COMPLETED/REJECTED/DEPLOYED |           | • RuleDesignCompleted        |
|  로 경계 표시)                |           | • RuleDesignRejected         |
+------------------------------+           | • RuleDesignDeployed         |
              |                            +------------------------------+
              | references                            |
              v                                       | feeds into
+------------------------------+                      |
| GeneratedRule (TOML)         |<---------------------+
| (Claude 응답 텍스트)          |
+------------------------------+
              |
              | feeds
              v
+------------------------------+
| Verification (paper-run)     |
| (spec 009 paper-run 결과)     |
+------------------------------+
              |
              | passes
              v
+------------------------------+
| LiveSession                  |
| (RULE_DESIGN_DEPLOYED 후      |
|  실제 worker session 시작)    |
+------------------------------+
```

---

## 엔티티 정의

### RuleDesignSession

design 명령의 1회 실행. audit_log 안에서 `RULE_DESIGN_REQUESTED`로 시작, `RULE_DESIGN_COMPLETED`(또는 `_REJECTED`)로 종결.

| 필드 | 출처 | 의미 |
|------|------|------|
| `session_id` | RULE_DESIGN_REQUESTED audit_log row seq | 한 design 호출 식별 |
| `intent_text` | RuleDesignRequestedPayload.intent | 운영자 원본 자연어 의도 |
| `requested_at_utc` | audit_log.ts_utc | 호출 시각 |
| `state` | (derived) | requested · in_progress · completed · rejected · deployed |
| `retry_count` | (derived) | 같은 session에서 시도된 횟수 (1~3) |

---

### AuditEvent — 4종 신규 페이로드

#### `RuleDesignRequestedPayload`

design 명령 시작 시 1회.

| 필드 | 타입 | 의미 |
|------|------|------|
| `intent` | str | 운영자가 입력한 자연어 의도 (한 줄) |
| `requested_at_utc` | str (ISO8601) | 시각 |
| `kis_balance_usd` | str (Decimal) | KIS 잔고 (예수금) — Claude prompt에 사용 |
| `kis_holdings` | list[dict] | 보유 종목 [{symbol, qty, avg_cost_usd}] |
| `host` | str | 호스트명 |

#### `RuleDesignCompletedPayload`

Claude 호출 + 정적 검증 + paper-run 1일분 모두 통과 시 1회.

| 필드 | 타입 | 의미 |
|------|------|------|
| `intent` | str | 원본 의도 (글자 그대로) |
| `interpretation` | dict | Claude가 해석한 정량 매개변수 (예: `{"max_drawdown_pct": 5, "per_symbol_pct": 20, "universe": [...]}`) |
| `generated_rules_toml` | str | 생성된 TOML 전체 텍스트 |
| `model_id` | str | 사용된 Claude 모델 ID |
| `tokens_input` | int | 입력 토큰 수 |
| `tokens_output` | int | 출력 토큰 수 |
| `cost_usd` | str (Decimal) | 호출 비용 |
| `retry_index` | int | 몇 번째 시도에서 성공했는지 (1~3) |
| `paper_run_session_id` | int \| None | paper-run 검증 시작 row seq (FR-014 상태 복구용) |

#### `RuleDesignRejectedPayload`

자동 재설계 1회 실패 또는 운영자 거부 또는 mutex 충돌 등 모든 거부 사유.

| 필드 | 타입 | 의미 |
|------|------|------|
| `reason` | str (enum) | `parse_error` · `whitelist_violation` · `cap_violation` · `backtest_fail` · `paper_run_fail` · `operator_declined` · `max_retries` · `mutex_conflict` · `insufficient_balance` · `kis_token_failed` · `claude_api_error` |
| `detail` | str | 한글 메시지 |
| `retry_index` | int \| None | 재시도 시도 번호 (None이면 mutex_conflict 등 시도 전 거부) |
| `conflicting_event_id` | int \| None | mutex_conflict 시 충돌 row id |

#### `RuleDesignDeployedPayload`

운영자 OK 후 라이브 worker 시작 시 1회.

| 필드 | 타입 | 의미 |
|------|------|------|
| `design_session_id` | int | 대응 RULE_DESIGN_REQUESTED 이벤트의 seq |
| `live_session_id` | int | 새 라이브 worker의 WORKER_STARTED 이벤트 seq |
| `deployed_at_utc` | str (ISO8601) | 라이브 시작 시각 |
| `total_capital_usd` | str (Decimal) | 라이브로 굴리는 자본 |

---

### GeneratedRule (derived view)

별도 저장소 없음. `RuleDesignCompletedPayload.generated_rules_toml`에서 직접 파싱해 spec 001의 `LoadedConfig`로 변환 가능.

---

### Verification (paper-run 1일분)

spec 009의 paper-run 데몬을 background subprocess로 띄워 진행. design 명령은 audit_log에서 paper 이벤트(`ORDER_PAPER_FILLED`, `PAPER_RUN_STOPPED`)를 polling으로 확인.

---

### LiveSession

design이 OK 받고 시작한 라이브 worker. spec 001의 일반 `auto-invest run`과 동일 — 단 audit_log에 `RULE_DESIGN_DEPLOYED`가 그 worker session과 짝맞춰 있어야 한다.

---

## State Transitions

```
[design 명령 시작]
       |
       v
[mutex check] -- conflict --> [REJECTED(mutex_conflict)] -- exit 70
       |
       | clear
       v
[KIS 잔고 조회] -- fail --> [REJECTED(kis_token_failed/insufficient_balance)] -- exit 1
       |
       | OK
       v
[REQUESTED audit 기록]
       |
       v
[Claude 호출] (시도 1)
       |
       +-- parse_error --+
       +-- validator 실패 --+
       +-- backtest 실패 --+--> [재시도? Yes if retry < 3]
       +-- paper-run 1일분 실패 --+
       |
       | 통과
       v
[COMPLETED audit 기록]
       |
       v
[운영자 OK prompt (60s timeout)]
       |
       +-- 거부/타임아웃 --> [REJECTED(operator_declined)]
       |
       | OK
       v
[새 라이브 worker 시작]
       |
       v
[DEPLOYED audit 기록]
       |
       v
[design 명령 종료, 라이브 worker 실행 중]
```

재시도가 3회 모두 실패하면 → `REJECTED(max_retries)` 후 exit 1.

---

## 외부 시스템 의존

| 컴포넌트 | 본 스펙에서 변경? | 비고 |
|---------|----------------|------|
| KIS REST API (잔고·보유 조회) | 변경 없음 | spec 001 모듈 재사용 |
| KIS REST API (주문) | **호출 안 함** | paper-run 단계에서 spec 009 단일 차단 지점 통과 |
| Claude API | **신규 호출** | constitution III 새 judgment point `rule_design` |
| SQLite (audit_log) | 스키마 변경 없음 | 페이로드 JSON에 새 type 4개 |
| spec 002 telemetry (token_usage) | 변경 없음 | claude_client.py가 spec 002 meter 사용 |
| spec 008 backtest | **stub 가드** | import 가능하면 사용, 아니면 건너뜀 |
| spec 009 paper-run | 변경 없음 | subprocess로 실행 |

---

## 마이그레이션 영향

- audit_log 테이블 스키마 무변경.
- 신규 테이블·인덱스·컬럼 0개.
- migration SQL 파일 0개.

**결론**: K3 + K4 두 파일만 변경. 둘 다 additive.

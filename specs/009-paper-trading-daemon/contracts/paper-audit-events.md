# Contract: Paper Audit Event Payloads

**Spec**: 009 · **Phase**: 1 · **Date**: 2026-05-19

K4 (`src/auto_invest/persistence/audit.py`)에 추가되는 4개 새 페이로드 클래스의 계약. 기존 24종 페이로드는 무수정.

이 변경은 **K4 추가 변경(additive)**이며 constitution v3.0.0 IX.D 자율 머지 채널에 해당한다. PR 본문에 해당 commit hash가 명시되어야 한다.

---

## 1. `PaperRunStartedPayload`

paper-run 데몬 시작 시 정확히 1번 기록.

### 필드

| 필드 | 타입 | 필수 | 의미 |
|------|------|------|------|
| `pid` | int | yes | os.getpid() |
| `config_path` | str | yes | 룰셋 TOML 파일 절대 경로 |
| `ruleset_sha256` | str (64 hex char) | yes | 룰셋 파일 바이트 SHA-256 |
| `started_at_utc` | str (ISO8601 with Z) | yes | "YYYY-MM-DDTHH:MM:SS.sssZ" |
| `host` | str | yes | socket.gethostname() |

### Audit 이벤트 타입 상수

- `event_type` = `"paper_run_started"` (모든 페이로드의 event_type은 클래스명 snake_case)

### 검증

- pydantic V2 BaseModel 사용 (기존 audit.py 패턴).
- `pid > 0`, `ruleset_sha256`은 정확히 64자 16진 문자.

---

## 2. `PaperRunStoppedPayload`

paper-run 데몬 종료 시 1번 기록. 비정상 종료 시 best-effort.

### 필드

| 필드 | 타입 | 필수 | 의미 |
|------|------|------|------|
| `reason` | Literal["normal_shutdown", "signal_received", "mutex_conflict", "crash"] | yes | 종료 사유 |
| `stopped_at_utc` | str (ISO8601 with Z) | yes | 종료 시각 |
| `session_started_event_id` | int | yes | 대응 PaperRunStarted 이벤트의 audit_log row id |

### Audit 이벤트 타입 상수

- `event_type` = `"paper_run_stopped"`

---

## 3. `OrderPaperFilledPayload`

게이트 통과 후 paper 분기에서 시뮬 체결 시 매번 기록.

### 필드

| 필드 | 타입 | 필수 | 의미 |
|------|------|------|------|
| `rule_id` | str | yes | 트리거 룰 ID |
| `symbol` | str | yes | 종목 (whitelist 통과한 값) |
| `side` | Literal["BUY", "SELL"] | yes | 매매 방향 |
| `qty` | int | yes | 룰이 요청한 수량 (정수, > 0) |
| `simulated_fill_price_usd` | str (Decimal as string) | yes | 시뮬 체결 가격 |
| `quote_source` | Literal["ask", "bid", "last"] | yes | FR-007 폴백 어떤 단계 |
| `correlation_id` | str | yes | OrderIntentPayload와 짝맞춤 (`"ord-..."`) |
| `paper_session_id` | int | yes | 어느 PaperRunSession의 audit_log row id |

### Audit 이벤트 타입 상수

- `event_type` = `"order_paper_filled"`

### 검증

- `qty > 0`
- `simulated_fill_price_usd`는 Decimal 변환 가능해야 함, 양수
- `correlation_id`는 OrderIntent의 그것과 정확히 일치

### Audit row 추가 컬럼

audit_log 테이블의 기존 컬럼 `rule_id`, `symbol`, `correlation_id`도 함께 채운다 (live의 OrderSubmittedPayload 패턴과 동일).

---

## 4. `PaperRunRejectedPayload`

mutex 거부 또는 시뮬 체결 거부 (quote 결측 등) 시 기록.

### 필드

| 필드 | 타입 | 필수 | 의미 |
|------|------|------|------|
| `attempted_mode` | Literal["paper", "live"] | yes | 어느 모드 시작이 거부됐는지 |
| `reason` | Literal["mutex_conflict", "no_quote_field", "other"] | yes | 거부 사유 |
| `conflicting_event_id` | int \| None | no | (mutex_conflict 시) 충돌 worker_started/paper_run_started 이벤트 id |
| `conflicting_session_started_at` | str \| None | no | (mutex_conflict 시) 충돌 세션 시작 시각 |
| `detail` | str | yes | 사람 읽을 메시지 (예: "live worker started at ... is still running") |

### Audit 이벤트 타입 상수

- `event_type` = `"paper_run_rejected"`

---

## 통합 계약 (모든 4종 공통)

### Append-only 원칙

- 어떤 paper 페이로드도 UPDATE·DELETE 안 함 (constitution IV).
- 기록 실패 시 (DB busy 등) 재시도 또는 stderr 경고 — 본 스펙은 단일 connection 가정으로 재시도 비범위.

### 기존 호환성

- `audit.append(conn, payload)`의 기존 시그니처 변경 없음.
- `audit.append`가 받는 `AuditPayload` Union에 4종 추가. spec 008의 같은 패턴과 일치.

### Forensic grep 지원

- 운영자가 `git log --grep="K4 touch"` 또는 commit message에 K4 paths를 명시하는 관행 유지.
- PR 본문에 명시: "K4 touch in audit.py (additive): commit <SHA>"

### Migration 영향

- SQL migration 파일 0개 추가. audit_log 테이블 스키마 무변경.
- payload JSON에 새 event_type 4종만 추가됨 — 기존 row 무영향.

---

## 테스트 가능한 invariants

| Invariant | 검증 방법 |
|-----------|----------|
| 4개 페이로드 모두 pydantic validation 통과 | `tests/test_paper_audit_payloads.py` — 각 페이로드 fixture로 BaseModel.model_validate 검증 |
| event_type 문자열이 클래스 → snake_case 일관 | 동 테스트 — `payload.__class__.__name__` 변환과 expected 비교 |
| OrderPaperFilledPayload는 OrderIntentPayload와 correlation_id 짝맞춤 | `tests/test_paper_integration.py` — paper-run 1 tick 후 audit_log SELECT |
| 기존 24종 페이로드는 무수정 | `tests/test_paper_audit_payloads.py::test_existing_payloads_unchanged` — 클래스 dict 키 set 비교 (baseline 캡처) |
| `audit_log` 테이블 스키마 무변경 | spec 008 migration 이후 schema dump를 baseline으로 저장, paper 코드 import 후 schema dump 비교 |

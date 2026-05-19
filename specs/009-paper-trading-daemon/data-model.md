# Data Model: Paper-Trading Daemon (spec 009)

**Phase**: 1 (Design)
**Date**: 2026-05-19

이 문서는 spec 009가 추가하는 엔티티·이벤트 페이로드·derived view를 정의한다. SQLite 스키마(테이블·컬럼) 변경은 0건이다 — 모든 paper 모드 데이터는 기존 `audit_log` 테이블의 새 이벤트 타입으로 표현된다.

---

## 엔티티 개요

```
+--------------------------+    1..N    +-----------------------+
| PaperRunSession          |--produces->| AuditEvent (paper)    |
| (audit_log 이벤트들로     |            | • PaperRunStarted     |
|  경계 표시되는 논리 단위)  |            | • PaperRunStopped     |
+--------------------------+            | • OrderPaperFilled    |
            |                           | • PaperRunRejected    |
            | derives                   +-----------------------+
            v                                       |
+--------------------------+                       | reduces
| VirtualPosition          |<----------------------+
| (ORDER_PAPER_FILLED      |
|  이벤트 누적의 derived)   |
+--------------------------+
            |
            | aggregated by
            v
+--------------------------+
| PaperReport              |
| (paper-report CLI 출력)   |
+--------------------------+
```

---

## 엔티티 정의

### PaperRunSession

paper-run 데몬의 1회 실행 단위. audit_log 안에서 `PaperRunStarted` ~ `PaperRunStopped` 사이로 식별. 별도 테이블 없음.

| 필드 | 출처 | 의미 |
|------|------|------|
| `session_id` | PaperRunStartedPayload의 audit_log row id (정수) | 한 paper-run 인스턴스 식별자 |
| `started_at_utc` | audit_log.created_at | 시작 시각 |
| `stopped_at_utc` | 대응 PaperRunStopped event의 created_at | 종료 시각 (없으면 null = 현재 실행 중) |
| `ruleset_sha256` | PaperRunStartedPayload.ruleset_sha256 | 그 세션에 적재된 룰셋 해시 |
| `stop_reason` | PaperRunStoppedPayload.reason | normal_shutdown · signal_received · mutex_conflict · crash |

**Validation rules**:
- 같은 host에 `PaperRunStarted` 이벤트가 stop 짝 없이 2건 존재할 수 없다 (FR-015). mutex 가드가 이를 검증.
- `ruleset_sha256`은 spec 008과 같은 계산법(rules.toml 파일 바이트의 SHA-256) 사용.

---

### AuditEvent (paper-mode 페이로드 4종)

spec 008까지 24종이었던 `AuditPayload` 유니온에 4종 추가. 기존 24종은 본 스펙에서 무수정 (research.md R-P11).

#### `PaperRunStartedPayload`

paper-run 데몬 시작 시 기록. `record_start()`에서 paper_mode=True면 `WorkerStartedPayload` 대신 이 페이로드 사용.

| 필드 | 타입 | 의미 |
|------|------|------|
| `pid` | int | 데몬 프로세스 ID |
| `config_path` | str | 룰셋 파일 경로 |
| `ruleset_sha256` | str (64자) | 룰셋 파일 바이트 SHA-256 |
| `started_at_utc` | str (ISO8601) | 시작 시각 (페이로드 명시; audit_log.created_at과 중복 OK) |
| `host` | str | gethostname() — 후속 systemd 통합에서 유용 |

#### `PaperRunStoppedPayload`

paper-run 데몬 종료 시 기록. `record_stop()`에서 paper_mode=True면 `WorkerStoppedPayload` 대신 사용.

| 필드 | 타입 | 의미 |
|------|------|------|
| `reason` | str (enum) | `normal_shutdown` · `signal_received` · `mutex_conflict` · `crash` |
| `stopped_at_utc` | str (ISO8601) | 종료 시각 |
| `session_started_event_id` | int | 대응 PaperRunStarted 이벤트의 audit_log row id |

#### `OrderPaperFilledPayload`

paper 모드에서 게이트 통과 + 시뮬 체결 시 기록. live 모드의 `OrderSubmittedPayload` + `FillPayload` 쌍을 대체.

| 필드 | 타입 | 의미 |
|------|------|------|
| `rule_id` | str | 트리거된 룰 ID |
| `symbol` | str | 종목 |
| `side` | str (enum) | `BUY` · `SELL` |
| `qty` | int | 주문 수량 (룰이 요청한 그대로) |
| `simulated_fill_price_usd` | str (Decimal) | 시뮬 체결 가격 |
| `quote_source` | str (enum) | `ask` · `bid` · `last` (FR-007의 어떤 폴백을 썼는지) |
| `correlation_id` | str | OrderIntent와 매칭되는 ID |
| `paper_session_id` | int | 어느 PaperRunSession에 속하는지 |

**Invariant**: paper_session_id로 묶었을 때 `(rule_id, symbol, side, qty)`의 누적 합이 R-P3의 VirtualPosition을 재구성.

#### `PaperRunRejectedPayload`

paper-run 시작이 mutex로 거부됐을 때, 또는 paper-run 도중 quote 결측으로 시뮬 체결 거부됐을 때 기록.

| 필드 | 타입 | 의미 |
|------|------|------|
| `attempted_mode` | str (enum) | `paper` · `live` (어느 모드 시작이 거부됐는지) |
| `reason` | str (enum) | `mutex_conflict` · `no_quote_field` · `other` |
| `conflicting_event_id` | int | (mutex_conflict 시) 충돌한 worker_started/paper_run_started 이벤트 id |
| `conflicting_session_started_at` | str (ISO8601) | (mutex_conflict 시) 충돌 세션 시작 시각 |
| `detail` | str | 사람이 읽을 메시지 |

---

### VirtualPosition (derived, 테이블 아님)

`paper/virtual_positions.py`가 `OrderPaperFilledPayload` 이벤트를 누적해 계산. 메모리·캐시 없음 — 호출마다 audit_log 재집계.

함수 시그니처 (의사 정의):
```
def recompute_virtual_positions(
    conn: sqlite3.Connection,
    *,
    paper_session_id: int | None = None,  # None이면 모든 세션 합산
    since: datetime | None = None,
    until: datetime | None = None,
) -> dict[str, VirtualPositionRow]:
    """
    리턴: { symbol: VirtualPositionRow }
    """
```

`VirtualPositionRow`:

| 필드 | 의미 |
|------|------|
| `symbol` | 종목 |
| `qty` | 누적 수량 (BUY +, SELL -) |
| `avg_cost_usd` | 매수 평균단가 (SELL이 발생해도 평균단가는 유지 — 가중평균) |
| `realized_pnl_usd` | 실현 손익 (SELL 발생 시 (sell_price - avg_cost) × sold_qty 누적) |
| `last_event_at` | 가장 최근 이벤트의 created_at |

**계산 규칙**:
- BUY: `new_avg = (old_avg × old_qty + buy_price × buy_qty) / (old_qty + buy_qty)`, qty += buy_qty
- SELL: `realized_pnl += (sell_price - avg_cost) × sell_qty`, qty -= sell_qty (음수 허용 안 함 — 음수면 paper-report가 경고)
- 음수 qty 발생: PaperRunRejectedPayload는 기록되지 않음 (시뮬은 실패 안 함), 단 paper-report 출력에 anomaly 표시

---

### PaperReport (derived, 출력만 존재)

paper-report CLI의 출력. 별도 저장소 없음. 6개 SQL 집계의 합성 결과.

| 섹션 | 내용 |
|------|------|
| 메타 | 기간 (since~until), 포함 세션 수, paper-run 총 가동 시간 |
| 룰별 통계 | rule_id × (signal_count, paper_fill_count, deny_count, virtual_pnl_usd) |
| 게이트 분포 | gate_name × deny_count |
| 외부 API 오류 | error_type × count |
| 튜닝 피드백 | 한 번도 trigger 안 된 룰, trigger 빈도 상위 5개, quote_source 폴백 비율 |

출력 형식은 contracts/paper-report-cli.md에서 정의.

---

## 데이터 흐름

```
1. paper-run 데몬 시작
   → mutex 체크 (audit_log SELECT)
   → 충돌? → PaperRunRejected 기록 → exit 70
   → 정상? → PaperRunStarted 기록 → Worker 루프 시작

2. tick 1회
   → KIS quote 조회 (live와 동일 코드)
   → 룰 평가 (live와 동일 코드)
   → 시그널 발생 시 OrderRouter.submit_order 호출 (live와 동일 코드)
       → 게이트 체인 (live와 동일 호출)
       → broker 호출 직전 분기:
           - paper 모드: OrderPaperFilled 기록 (FillPayload·OrderSubmittedPayload 발생 안 함)
           - live 모드: place_order(broker, ...) (기존 코드 그대로)
   → tick 종료 → sleep tick_interval

3. SIGTERM 수신
   → 다음 tick 완료 → PaperRunStopped(reason=signal_received) 기록 → exit 0

4. paper-report --since X --until Y 실행
   → mutex 영향 없음 (read-only)
   → audit_log SELECT 6회 + virtual_positions.recompute 1회
   → 표 형식 출력 → exit 0
```

---

## 외부 시스템 의존 (변경 없음 확인)

| 컴포넌트 | 본 스펙에서 변경? | 비고 |
|---------|----------------|------|
| KIS REST API (quote) | 변경 없음 | paper도 동일 호출 |
| KIS REST API (order) | **호출 안 함** | 단일 차단 지점 (research.md R-P1) |
| SQLite (audit_log 테이블) | 스키마 변경 없음 | payload JSON에 새 type만 추가 |
| SQLite (positions 테이블) | **무수정** | SC-006 |
| SQLite (orders, fills 등) | **무수정** | live row 보호 |
| ResilientClient (broker wrapper) | 변경 없음 | paper에서도 quote 호출에 사용 |
| OrderRouter | 1줄 분기 추가 | research.md R-P1 |
| Worker | paper_mode flag + record_start/stop 분기 | research.md R-P7 |

---

## State Transitions

### PaperRunSession 상태

```
[start command]
     |
     v
[mutex check]
     | conflict
     +----------> [REJECTED] (PaperRunRejected → exit 70)
     | clear
     v
[STARTED] (PaperRunStarted)
     |
     | SIGTERM/SIGINT
     v
[STOPPING] (다음 tick 완료 대기)
     |
     v
[STOPPED] (PaperRunStopped(reason=signal_received))

또는:
[STARTED]
     | unhandled exception
     v
[CRASHED] (try/finally에서 PaperRunStopped(reason=crash))
```

---

## 마이그레이션 영향

| 항목 | 본 스펙에서 신규 마이그레이션? |
|------|---------------------------|
| audit_log 테이블 스키마 | 없음 — JSON payload에 type만 추가 |
| 신규 테이블 | 없음 |
| 신규 인덱스 | 없음 — 기존 `idx_audit_event_type_created_at` 활용 |
| 신규 컬럼 | 없음 |

**결론**: SQL 마이그레이션 파일 0개 추가. K4 파일 중 변경되는 것은 `persistence/audit.py` 1개 (페이로드 클래스 4개 추가).

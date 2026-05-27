# Tasks: Live Fill Ingestion (라이브 체결 동기화) — spec 015

**브랜치**: `claude/fervent-hamilton-oISbf`  **스펙 디렉터리**: `015-live-fill-ingestion`

Kernel 터치 0건 목표. 손댄 파일 전부 비커널(`broker/overseas.py`,
`broker/models.py`, 새 `execution/fill_sync.py`, `worker/loop.py`, `cli.py`,
`reports/health.py`, `tests/`). 기존 `FILL`/`CANCEL` 감사 이벤트 재사용 — `audit.py`
(K4) 미터치. `orders.state` 자유 TEXT — 마이그레이션(K4) 미터치.

## Phase 1 — 브로커 체결 조회 (P1)

- [x] **T001** `broker/models.py`에 `BrokerExecution` 모델 추가(kis_order_id·symbol·
      filled_qty·avg_fill_price_usd·unfilled_qty?·side?·terminal?).
- [x] **T002** `broker/overseas.py`에 `get_order_executions`(KIS `inquire-ccnl`,
      읽기 전용 GET) 추가. 후보 필드명 폴백 패턴(기존 `_row_eval_amount_usd` 스타일).
- [x] **T003** [P] `tests/unit/test_overseas_executions.py` — 응답 파싱(전량·부분·
      필드명 변형·빈 응답) 단위 테스트.

## Phase 2 — 순수 체결 동기화 계획 로직 (P1)

- [x] **T004** 새 `execution/fill_sync.py`: `plan_fill_ingestion(open_orders,
      executions, recorded_qty_by_corr)` 순수 함수 — delta>0인 주문에 대한
      `PlannedFill` + 상태 전이(`FILLED`/`PARTIALLY_FILLED`/`EXPIRED`) 계획 반환.
      음수 delta·종료 신호·미체결 처리 포함.
- [x] **T005** [P] `tests/unit/test_fill_sync_plan.py` — 순수 함수 테스트:
      전량/부분/다단계/멱등(이미 기록분 제외)/음수 delta 무시/종료→EXPIRED/
      종료 신호 없으면 무전이.

## Phase 3 — 동기화 오케스트레이터 + 영속 (P1)

- [x] **T006** `fill_sync.py`에 `sync_fills(conn, broker, ...)` async 오케스트레이터:
      열린 주문 로드 → 브로커 체결 조회 → `plan_fill_ingestion` → 각 계획 적용
      (`FILL` 감사 append + `fills` INSERT OR IGNORE + `positions.update_from_fill` +
      상태 전이). 0건이면 브로커 미호출. 예외 격리(ERROR 감사, 계속). 적용 요약 반환.
- [x] **T007** [P] `tests/integration/test_fill_sync.py` — 인메모리 DB + 가짜 브로커로
      전량/부분/다단계/멱등/오류격리/열린주문0 통합 테스트. correlation_id·symbol·
      rule_id이 `_read_live_fills` 조인과 호환되는지 검증.

## Phase 4 — 워커 연결 (P1)

- [x] **T008** `worker/loop.py`: `_sync_open_order_fills(now)` + cadence
      (`_FILL_SYNC_GAP_SECONDS`, 기본 5초). `tick()`에서 브레이커 점검 이후, 룰
      평가 전에 **라이브 모드 전용**으로 호출. 열린 주문 0건이면 즉시 반환.
- [x] **T009** [P] `tests/integration/test_worker_fill_sync.py` — 라이브 워커가
      틱에서 체결을 당겨 보유/상태/성과에 반영하는지 + paper 모드는 호출 안 하는지.

## Phase 5 — 브레이커 라이브 활성 검증 (P1)

- [x] **T010** [P] `test_worker_fill_sync.py::test_fill_sync_activates_live_breaker`
      — 라이브 매수→매도 손실 체결을 동기화로 기록 → 스펙 011 성과가 손실 반영 →
      스펙 014 브레이커 트립(US3·SC-003).

## Phase 6 — CLI + 헬스 + 종료 상태 (P2/P3)

- [x] **T011** `cli.py`에 `auto-invest fills [--sync]` 추가(--sync=1회 동기화+건수,
      무인자=읽기전용 요약). 종료 코드 규약(0/1/2).
- [x] **T012** [P] `tests/integration/test_cli_fills.py` — 읽기 전용 요약·--sync
      --env 누락 오용(2)·DB 없음(1).
- [x] **T013** (P2) 종료(EXPIRED) 경로 마무리 — `sync_fills`가 `CANCEL` 감사 +
      `EXPIRED` 전이를 실제 적용. `test_fill_sync.py`에 EXPIRED 케이스 포함.
- [ ] **T014** [P] (선택·보류) `reports/health.py` "열린 주문 수 / 마지막 체결 동기화"
      정보 블록 — 범위를 좁게 유지하기 위해 후속으로 미룸(헬스는 이미 읽기 전용 출시됨).

## Phase 7 — 마무리

- [x] **T015** 전체 `uv run pytest` 1024 통과·4 스킵 + `uv run ruff check src tests`
      깨끗 확인. Kernel 터치 0건 확인.
- [x] **T016** PR 본문에 Kernel 터치 0건 명시 + 자동 머지 절차.
- [ ] **T017** `/handoff`로 HANDOFF 갱신(스펙 015 출시 반영) — 머지 후 수행.

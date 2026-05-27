# Tasks: Live Loss Circuit Breaker (스펙 014)

**Input**: `specs/014-loss-circuit-breaker/spec.md`
**Branch**: `claude/adoring-edison-AIkbz`

안전 불변: 브레이커는 **정지만** 한다(노출 증가/주문/청산 0건). 한도는 K1
(`config/caps.py`)에 둬 튜너가 자동 완화 불가. 손익은 스펙 011 엔진 한 잣대 재사용.

## Phase 1 — 설정 한도 (K1 추가-전용)

- [x] **T001** `config/caps.py`(K1)에 옵션 필드 추가: `circuit_breaker_enabled:
  bool = True`, `daily_loss_limit_pct: Decimal = 10`, `max_total_drawdown_pct:
  Decimal = 20`. 각 비율 `(0,100]` 검증. 기존 6필드 설정과 하위 호환(추가-전용).
- [x] **T002** 단위 테스트: 기본값 적용, 명시 오버라이드, 범위 위반 거부, 기존
  6필드-only 설정이 그대로 검증되는지(하위 호환).

## Phase 2 — 순수 평가기 (비커널 신규)

- [x] **T003** `risk/circuit_breaker.py`(신규, 비커널) — `BreakerLimits`,
  `BreakerDecision`, 순수 `evaluate(...)`. 일일 손실·전체 낙폭 두 한도를 결정론적
  평가. 외부 호출·DB 쓰기 0.
- [x] **T004** `evaluate_from_audit(conn, *, mode, starting_capital, caps, now,
  marks)` — 스펙 011 엔진(`read_fills`/`realized_trades`/`compute_performance`)로
  오늘 실현 손익·현재 자산 계산 후 `evaluate` 호출. read-only.
- [x] **T005** 단위 테스트: 일일 한도 트립/미트립, 낙폭 한도 트립/미트립, 둘 다,
  비활성, 거래 0건, 시세 결측(보수), 시작 자본 0, 경계값, 결정론(같은 입력=같은 결과).

## Phase 3 — 감사 이벤트 (K4 추가-전용)

- [x] **T006** `persistence/audit.py`(K4)에 `CIRCUIT_BREAKER_TRIPPED` 이벤트 타입 +
  `CircuitBreakerTrippedPayload` 추가. `EventType` Literal·`AnyPayload` 유니온에
  추가. 추가-전용(기존 이벤트 미수정).
- [x] **T007** 단위 테스트: 페이로드 직렬화/round-trip, append 후 read.

## Phase 4 — 워커 강제 (비커널)

- [x] **T008** `worker/loop.py` — `_check_circuit_breaker(now) -> BreakerDecision`
  (보유 종목 최근 바 종가로 marks 조립 → `evaluate_from_audit`). `tick()`에서
  halt·세션 점검 이후 호출, 트립 시 `set_halt` + `CIRCUIT_BREAKER_TRIPPED` append +
  `skipped_reason="circuit_breaker_tripped"`. halt 선점이므로 멱등.
- [x] **T009** 통합 테스트: 손실 시나리오 → 트립 → halt 세워짐 + 감사 row 1건;
  무손실 → 정상; 비활성 → 평가 스킵; 이미 halt → 중복 0건; paper/live 모드.

## Phase 5 — 관측 (P3, 비커널 읽기 전용)

- [x] **T010** `reports/health.py`에 브레이커 점검 추가(읽기 전용) — halt가 브레이커
  트립으로 걸렸는지 + 현재 평가 표시. `health` 종합 판정에 반영.
- [x] **T011** 단위 테스트: health에 브레이커 점검이 나타나는지, 읽기 전용 유지.

## Phase 6 — 마무리

- [x] **T012** 전체 `uv run pytest` + `uv run ruff check src tests` green.
- [x] **T013** HANDOFF 갱신(`/handoff`)은 머지 후 후속.

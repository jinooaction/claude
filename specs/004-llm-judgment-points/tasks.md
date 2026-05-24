---
description: "Task list — LLM Judgment Points (spec 004)"
---

# Tasks: LLM Judgment Points (LLM 판단 지점)

**Input**: `specs/004-llm-judgment-points/` (plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md)
**Tests**: 포함 — 헌법 개발 워크플로우는 "판단 지점 계약·리스크·주문 검증 모듈은 머지 전 자동 테스트 통과 필수"를 요구한다.
**Branch**: `claude/beautiful-mayer-nDR3x`

## 안전 불변량 (모든 작업이 지켜야 함)

- 자문은 `execution/order_router.py`(비커널)에서만 소비, **주문을 줄이거나 건너뛰기만**(노출 증가 불가). `risk/gates.py`(K1) 미수정.
- 모든 판단 지점에 결정론적 폴백(LLM 실패해도 거래 안 막힘).
- 같은 자문 → 같은 게이트 결정(결정성).
- 매 호출 token_usage 1행 + LLM_CALL 1행, 같은 correlation_id. 프롬프트/응답 본문·비밀 미기록.
- 유일한 Kernel 터치: `persistence/audit.py`(K4) 추가-전용 이벤트 2종. PR 본문에 커밋 해시 명시.

---

## Phase 1: Setup (공유 인프라)

- [x] T001 `src/auto_invest/judgment/__init__.py` + `src/auto_invest/judgment/points/__init__.py` 생성 (새 비커널 패키지 골격, plan 구조대로).
- [x] T002 [P] `config/llm_prices.toml` 확인 — 판단 지점 기본 모델(`claude-haiku-4-5-20251001` 저비용, `daily_summary`는 `claude-sonnet-4-6`)이 가격표에 있는지 확인(이미 존재 → 변경 없으면 no-op, 누락 시에만 추가).

**Checkpoint**: 패키지 골격 준비.

---

## Phase 2: Foundational (모든 User Story의 차단 선행 — 반드시 먼저)

**⚠️ 이 단계 완료 전 어떤 User Story도 시작 불가.**

### Tests (먼저 작성, 구현 전 실패 확인)

- [x] T003 [P] `tests/unit/test_judgment_schemas.py` — 세 출력 스키마(Volatility/News/DailySummary)의 enum·범위(0..1)·길이(≤500) 검증과 위반 거부 테스트.
- [x] T004 [P] `tests/unit/test_judgment_audit_payloads.py` — `JUDGMENT_ADVISORY_APPLIED`·`JUDGMENT_FALLBACK` 페이로드가 append되고 기존 이벤트 타입을 깨지 않는지(추가-전용) 테스트.
- [x] T005 [P] `tests/unit/test_judgment_client.py` — 견고한 Anthropic 클라이언트: 정상 호출 시 token_usage+LLM_CALL 기록, 예외/타임아웃/서킷오픈 시 폴백 신호 반환(거래 막지 않음) 테스트(mock `_AnthropicProtocol`).
- [x] T006 [P] `tests/unit/test_judgment_budget.py` — 롤링 비용이 예산 초과 시 해당 판단 지점이 폴백 전환되는지 테스트.
- [x] T007 [P] `tests/unit/test_judgment_registry.py` — 레지스트리가 세 판단 지점의 헌법 III 계약(트리거·입력·스키마·지연 예산·비용 예산·폴백)을 조회 가능하게 선언하는지 테스트.

### Implementation

- [x] T008 [P] `src/auto_invest/judgment/schemas.py` — pydantic 출력 모델 `VolatilityAdvisory`/`NewsAdvisory`/`DailySummaryAdvisory` + `parse_and_validate(decision_class, raw_text)` (검증 실패 시 명시적 예외). (T003 통과시킴)
- [x] T009 `src/auto_invest/persistence/audit.py` — **K4 추가-전용**: `JudgmentAdvisoryAppliedPayload`(decision_class·advisory 요약·applied_decision·canary_cohort)·`JudgmentFallbackPayload`(decision_class·reason) 추가, `EventType` Literal + `AnyPayload` union에 등록. 기존 타입·행 미변경, 마이그레이션 불필요. (T004 통과시킴)
- [x] T010 `src/auto_invest/judgment/client.py` — 견고한 Anthropic 호출 래퍼: `broker/client.py`의 `AsyncTokenBucket`+`CircuitBreaker`+재시도 재사용, `design/claude_client.py`의 `TokenMeter` 감싸기 패턴 미러. 실패/타임아웃/서킷오픈을 폴백 신호로 변환. 프롬프트/응답 본문 미기록. (T005 통과시킴)
- [x] T011 [P] `src/auto_invest/judgment/budget.py` — 판단 지점별 롤링 비용 추적 + 예산 초과 시 `disabled` 전환(메모리 상태, token_usage 조회 기반). (T006 통과시킴)
- [x] T012 `src/auto_invest/judgment/registry.py` — `JudgmentPoint` 계약 dataclass + 세 판단 지점 등록(decision_class·트리거·입력 계약·output_schema·latency_budget_ms·cost_budget_usd·model·max_tokens·affects_capital·fallback). 조회 API. (T007 통과시킴)

**Checkpoint**: 프레임워크(스키마·감사·클라이언트·예산·레지스트리) 준비 — User Story 착수 가능.

---

## Phase 3: User Story 1 — volatility_assessment (P1) 🎯 MVP

**Goal**: 변동성 급등 시 Claude가 hold/size_down/halt를 자문하고, order_router가 결정론적으로 소비(주문 축소/건너뛰기)하되 K1 캡은 그대로 바인딩.

**Independent Test**: 합성 요약 통계 + mock 자문으로 (1) 자문이 order_router에서 소비되어 qty 축소/건너뛰기, (2) 같은 자문 → 같은 결정(결정성), (3) LLM 실패 시 v1 동작 폴백, (4) token_usage+LLM_CALL 짝 기록.

### Tests

- [ ] T013 [P] [US1] `tests/integration/test_judgment_volatility_gate.py` — 자문 소비(축소/건너뛰기)·결정성·자문은 노출 증가 불가·K1 게이트 여전히 바인딩 테스트.
- [ ] T014 [P] [US1] `tests/integration/test_judgment_fallback_chaos.py` — LLM이 항상 실패하는 mock에서 주문 경로가 v1과 동일하게 동작(0건 막힘)하고 `JUDGMENT_FALLBACK` 기록 (SC-001).
- [ ] T015 [P] [US1] `tests/integration/test_judgment_audit_telemetry.py` — 매 호출 token_usage 1행 + LLM_CALL 1행 같은 correlation_id, 본문·비밀 미기록 (SC-003).

### Implementation

- [ ] T016 [US1] `src/auto_invest/judgment/points/volatility.py` — `volatility_assessment` 프롬프트 빌더(요약 통계 입력, 원시 바 금지) + `VolatilityAdvisory` 파싱 + 결정론적 폴백 정의.
- [ ] T017 [US1] `src/auto_invest/config/rules.py` (비커널) — 룰/액션에 판단 지점 소비 규칙 선언 필드 추가(`halt_min_confidence` 기본 0.7·`size_down_factor` 기본 0.5). 기존 룰 하위호환(필드 없으면 판단 지점 비활성).
- [ ] T018 [US1] `src/auto_invest/execution/order_router.py` (비커널) — 게이트 체인 진입 **전** 자문 소비: `halt`+고신뢰 → 주문 미제출(기록), `size_down` → qty 축소. 그 뒤 기존 게이트 체인 변형 없이 실행. `JUDGMENT_ADVISORY_APPLIED` 기록(correlation_id·canary_cohort). (T013 통과시킴)
- [ ] T019 [US1] 캐너리 코호트 연동 — `strategy/canary.py`/`canary/` 인프라로 5% 코호트 거래에만 자문 반영, 코호트 밖 v1 동작, `canary_cohort` 표식. (T013·SC-005 통과시킴)
- [ ] T020 [US1] 거래 루프 트리거 연결 — 변동성 트리거 발화 시(쿨다운 존중) 판단 지점 호출. 기존 `strategy/triggers.py`/지표 인프라 재사용(`worker/loop.py` 또는 `run` 경로 비커널 통합). (T014 통과시킴)

**Checkpoint**: US1 단독 동작·테스트 가능 — MVP. **여기서 테스트+린트 green이면 커밋·푸시.**

---

## Phase 4: User Story 2 — daily_summary (P2)

**Goal**: 장 마감 후 Claude가 운영 요약·경보를 작성, 일일 리포트에 섹션 추가. 주문 경로 무접촉(순수 자문).

**Independent Test**: 합성 audit 카운터 + mock으로 `report --date`에 요약 섹션이 붙고, LLM 실패 시 결정론적 카운터만 표시·정상 종료.

### Tests

- [ ] T021 [P] [US2] `tests/integration/test_judgment_daily_summary.py` — 리포트 요약 섹션 + 폴백(요약 생성 불가, 나머지 정상) 테스트.

### Implementation

- [ ] T022 [US2] `src/auto_invest/judgment/points/daily_summary.py` — 그날 audit 집계 카운터 입력 → `DailySummaryAdvisory` 파싱 + 폴백 정의.
- [ ] T023 [US2] `src/auto_invest/cli.py` `report` 명령(비커널) — 판단 요약 섹션 추가(FR-022). LLM 실패 시 결정론적 카운터만. (T021 통과시킴)

**Checkpoint**: US1+US2 독립 동작. green이면 커밋·푸시.

---

## Phase 5: User Story 3 — news_screen (P3)

**Goal**: 장 시작 전 주입된 헤드라인에 대한 Claude 스탠스(bull/bear/neutral)를 게이트가 결정론적으로 소비(bear+고신뢰 → 당일 신규 매수 보류). 공급원 없으면 비활성.

**Independent Test**: 합성 헤드라인 주입 + mock으로 스탠스 소비(결정성), 공급원 부재 시 깨끗한 neutral 폴백.

### Tests

- [ ] T024 [P] [US3] `tests/integration/test_judgment_news_screen.py` — 스탠스 소비·결정성·공급원 부재 비활성·LLM 실패 neutral 폴백 테스트.

### Implementation

- [ ] T025 [US3] `src/auto_invest/judgment/points/news_screen.py` — 헤드라인+종목 입력 → `NewsAdvisory` 파싱 + neutral 폴백 정의. 헤드라인 공급원 주입 인터페이스(없으면 비활성).
- [ ] T026 [US3] `src/auto_invest/config/rules.py` + `execution/order_router.py`(비커널) — `block_buy_stance="bear"`·`block_min_confidence`(0.8) 소비 규칙으로 당일 신규 매수 보류 결정론적 적용. (T024 통과시킴)

**Checkpoint**: 세 판단 지점 독립 동작. green이면 커밋·푸시.

---

## Phase 6: User Story 4 — 관측성·예산 강제 (P2)

**Goal**: 운영자가 판단 지점별 비용·지연·호출 수·폴백률 조회, 예산 초과 시 폴백 전환.

**Independent Test**: 합성 호출 기록으로 `efficiency`가 decision_class별 분해 출력, 예산 초과 시 폴백 전환 + 감사.

### Tests

- [ ] T027 [P] [US4] `tests/integration/test_judgment_efficiency_budget.py` — efficiency 분해(폴백률 포함) + 예산 초과 폴백 전환 + 합산 보존(SC-006) 테스트.

### Implementation

- [ ] T028 [US4] `src/auto_invest/cli.py` `efficiency`(비커널) — 기존 `per_decision_class` 출력에 판단 지점 폴백 발생률·예산 대비 사용률 추가(FR-040). 판단 지점 decision_class 식별.
- [ ] T029 [US4] order_router/거래 루프에 예산 가드 연결 — `judgment/budget.py`가 예산 초과 보고 시 그 판단 지점을 폴백 전환, `JUDGMENT_FALLBACK(reason="budget_exceeded")` 기록(FR-041). (T027 통과시킴)

**Checkpoint**: 전체 기능 동작. green이면 커밋·푸시.

---

## Phase 7: Polish & 검증

- [ ] T030 [P] `uv run pytest` 전체 통과(skip 허용, fail 없음) + `uv run ruff check src tests` 깨끗 확인.
- [ ] T031 quickstart.md 8개 시나리오 수동/자동 검증(특히 SC-001 폴백, SC-002 결정성, SC-007 K1 불변).
- [ ] T032 PR 본문에 K4 터치 커밋 해시(T009) 명시 + 헌법 IX.A 포렌식 콜아웃. 자동 머지 조건(CLAUDE.md 규칙 3) 점검.

---

## Dependencies & Execution Order

- **Phase 1 (Setup)** → **Phase 2 (Foundational, 차단)** → **Phase 3+ (User Stories)**.
- Foundational(T003~T012)이 모든 US를 차단. T008(schemas)·T009(audit)·T010(client)·T011(budget)·T012(registry)는 US 구현의 선행.
- **US1(P3, MVP)**: Foundational 후 착수. 독립 테스트 가능.
- **US2/US3/US4**: Foundational 후 착수. order_router 자문 소비는 US1이 먼저 깔고 US3가 확장(T018 → T026 순서 권장, 같은 파일).
- **Phase 7**: 모든 원하는 US 완료 후.

### 같은 파일 주의 (순차)

- `execution/order_router.py`: T018(US1) → T026(US3) → T029(US4). 병렬 금지.
- `config/rules.py`: T017(US1) → T026(US3). 순차.
- `persistence/audit.py`: T009만(단일).
- `cli.py`: T023(report) ‖ T028(efficiency) 서로 다른 함수라 병렬 가능하나 같은 파일이므로 순차 권장.

### Parallel Opportunities

- Foundational 테스트 T003~T007 전부 [P] 병렬.
- 구현 중 T008(schemas)·T011(budget)은 [P] 병렬(서로 다른 파일). T009·T010·T012는 의존/단일.
- US1 테스트 T013~T015 [P] 병렬.

---

## Implementation Strategy

### MVP First (US1만)

1. Phase 1 Setup → 2. Phase 2 Foundational(차단) → 3. Phase 3 US1 → **STOP & VALIDATE**(SC-001/002/003/005/007) → green이면 커밋·푸시.

### Incremental Delivery

Foundational → US1(MVP) → US2 → US3 → US4 → Polish. 각 US 완료 시 테스트+린트 green → 커밋·푸시(CLAUDE.md 자율 진행 정책). 전체 완료 시 자동 머지 조건 점검.

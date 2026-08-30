# Tasks: PEAD와 21가족 프로그램 관문

**Input**: `/specs/175-pead-program-gate/`의 spec, plan, research, data model, contracts
**Tests**: 각 사용자 이야기의 테스트를 먼저 작성해 실패를 확인한 뒤 구현한다.

## Phase 1: Setup and Preregistration

- [x] T001 사전등록 계약 JSON과 결과 스키마를 `specs/175-pead-program-gate/contracts/`에서 형식 검증한다.
- [x] T002 사전등록 spec·plan·tasks·contracts를 결과 실행 전에 별도 커밋해 사후 기준 변경을 막는다.

---

## Phase 2: Foundational Program Calibration

**Goal**: 기존 `3.1`을 깨지 않고 21가족 진단용 `3.2` 프로그램 교정을 만든다.

- [x] T003 [P] [US1] 16·64후보 가족 상한, 21가족 구성, 보수 합계와 결정론을 검증하는 실패 테스트를 `tests/unit/test_edge_gate_calibration.py`에 추가한다.
- [x] T004 [P] [US1] 명령줄 교정 결과의 새 계약을 검증하는 실패 테스트를 `tests/integration/test_edge_gate_calibration_probe.py`에 추가한다.
- [x] T005 [US1] 후보 수별 상한과 프로그램 진단을 `src/auto_invest/analytics/edge_gate_calibration.py`에 구현하되 기존 `3.1` 필드를 유지한다.
- [x] T006 [US1] 교정 단위·통합 테스트를 통과시키고 고정 난수 재현값을 기록한다.

**Checkpoint**: 21가족 보수 상한 0.200, 16·64 가족 검출력 80% 이상, 실자본 적격 false.

---

## Phase 3: User Story 2 - 공개 PEAD 역사 판정 (Priority: P1)

**Goal**: 공개 두 신호를 엄격히 검증하고 16개 사전등록 후보를 개발 구간만으로 선택한다.

**Independent Test**: 1996년 이후 수익을 바꿔도 선택 후보가 같고, 손상된 월·신호·종목 수는 실패 폐쇄한다.

- [x] T007 [P] [US2] 공개 CSV 파서의 신호·월·수익·롱숏 종목 수 실패 사례를 `tests/unit/test_pead_factory.py`에 먼저 작성한다.
- [x] T008 [P] [US2] 16개 후보 ID·지문 고유성과 개발 선택 시간 격리 테스트를 `tests/unit/test_pead_factory.py`에 먼저 작성한다.
- [x] T009 [P] [US2] PBO·PSR·시대·최근 36개월·집중도·낙폭·비용·부호 반전 판정 테스트를 `tests/unit/test_pead_factory.py`에 먼저 작성한다.
- [x] T010 [US2] 자료 모델, 공개 CSV 파서, 품질·SHA-256 검증을 `src/auto_invest/analytics/pead_factory.py`에 구현한다.
- [x] T011 [US2] 사전등록 8가중치×2배율 후보 생성과 개발 전용 선택을 `src/auto_invest/analytics/pead_factory.py`에 구현한다.
- [x] T012 [US2] 출판 후·최근·강건성·위약 관문과 세 단계 판정을 `src/auto_invest/analytics/pead_factory.py`에 구현한다.
- [x] T013 [US2] 공개자료 다운로드·재시도·사전등록 입력·JSON/한글 요약 발행을 `scripts/pead_factory_probe.py`에 구현한다.
- [x] T014 [US2] PEAD 단위 테스트를 통과시킨다.

**Checkpoint**: 역사적 재현 여부는 숫자로 나오지만 돈 경로는 계속 닫혀 있다.

---

## Phase 4: User Story 3 - 역사 엣지와 실계좌 적격 분리 (Priority: P2)

**Goal**: 어떤 역사 판정에서도 전진 관찰·실행 동등성·자본 상태를 과장하지 않는다.

**Independent Test**: `PUBLISHED_EDGE` 표본에서도 연구 캐너리·승격 false, 배포 null, 자본·주문 0이다.

- [x] T015 [P] [US3] `PUBLISHED_EDGE` 합성 표본의 안전 필드와 오염 공개 테스트를 `tests/unit/test_pead_factory.py`에 먼저 추가한다.
- [x] T016 [US3] criterion validity, 현재 계좌 blocker, 2026-09-01 전진 관찰 초기 상태를 `src/auto_invest/analytics/pead_factory.py`에 구현한다.
- [x] T017 [US3] 결과가 `specs/175-pead-program-gate/contracts/pead-result.schema.json`을 만족하도록 통합 테스트를 `tests/integration/test_pead_factory_probe.py`에 작성하고 통과시킨다.

**Checkpoint**: “출판 엣지 있음/없음”과 “현재 계좌 부적격”이 별도 필드로 재현된다.

---

## Phase 5: User Story 4 - 독립 816행 감사와 워크플로 (Priority: P3)

**Goal**: 생산자 요약을 믿지 않고 원시 행에서 816후보·21가족·0.200을 다시 계산한다.

**Independent Test**: ID, 지문, 가족 크기, 교정 상한 중 하나를 변조하면 독립 소비자가 거부한다.

- [x] T018 [P] [US4] 독립 감사의 정상·변조 실패 테스트를 `tests/unit/test_pead_factory_evidence.py`에 먼저 작성한다.
- [x] T019 [P] [US4] 명령줄 증거 소비자 정상·변조 실패 테스트를 `tests/integration/test_pead_evidence_gate.py`에 먼저 작성한다.
- [x] T020 [US4] 원시 장부 재계산과 안전 필드 검증을 `src/auto_invest/analytics/pead_factory_evidence.py`에 구현한다.
- [x] T021 [US4] 독립 소비자 명령줄을 `scripts/pead_evidence_gate.py`에 구현한다.
- [x] T022 [US4] 회계 팩터 sidecar를 보존한 뒤 PEAD 16행을 추가하는 단계를 `.github/workflows/autonomous-strategy-factory.yml`에 연결한다.
- [x] T023 [US4] 기존 돈 경로 소비자가 진단 전용 `3.2`를 계속 거부하는 회귀 테스트를 `tests/integration/test_factory_evidence_gate.py`와 `tests/integration/test_strategy_factory_workflow.py`에 추가한다.

**Checkpoint**: 최종 공개 sidecar는 816행·21가족이고 어떤 결과에서도 주문·자본은 0이다.

---

## Phase 6: End-to-End Result and Quality Gates

- [x] T024 공개 출시본으로 PEAD 탐침과 독립 소비자를 실행해 JSON·한글 요약을 검증한다.
- [x] T025 전체 `uv run pytest`와 `uv run ruff check src tests`를 통과시킨다.
- [x] T026 등급 4 필수 검사 `uv run python scripts/agent_harness_probe.py --strict`와 `uv run python scripts/check_handoff_facts.py`를 통과시킨다.
- [x] T027 PR 본문을 `.github/pull_request_template.md`에 맞춰 작성하고 `scripts/check_pr_quality_gate.py`로 검증한다.
- [x] T028 변경을 커밋·푸시하고 PR의 원격 검사를 확인해 조건 충족 시 merge commit 방식으로 자동 머지한다.
- [ ] T029 `deploy-status` 기술로 main 배포·최신 sidecar를 확인하고 결과가 연구 전용임을 재검증한다.
- [ ] T030 `handoff` 기술로 `HANDOFF.md`의 main 커밋, 테스트, 출시 스펙, 다음 관찰 지점을 갱신·검증·머지한다.

## Dependencies & Execution Order

1. T001-T002가 끝나기 전 실제 공개자료 결과를 실행하지 않는다.
2. T003-T006의 프로그램 교정이 통과해야 PEAD를 21번째 가족으로 합칠 수 있다.
3. T007-T014가 역사 판정의 핵심이며 T015-T017은 그 결과의 과장 방지 계층이다.
4. T018-T023은 생산자 구현 후 수행하지만 생산자 요약을 신뢰하지 않는 독립 경계다.
5. T024 이후 전체 검증과 PR·배포·인계를 순서대로 진행한다.

## Completion Contract

- 사전등록 뒤 임계값 변경 0건.
- 816개 후보 ID·지문 고유, 21가족, 가족 크기 `16:11, 64:10`, 보수 상한 0.200.
- 공개 결과를 `PUBLISHED_EDGE`, `PAPER_CHALLENGER`, `NO_FACTORY_EDGE` 중 하나로 재현.
- 결과와 무관하게 연구 캐너리·승격 false, 배포 null, 주문 0건, 자본 0%.
- 전체 테스트·린트·하네스·인계 검사와 원격 PR 조건 통과.

# Tasks: 회계 기반 횡단면 다요인 전략

**Input**: `specs/174-accounting-cross-sectional-factors/`의 명세·계획·연구·자료모형·계약
**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`

**Tests**: 돈 경로와 연구 판정에 닿으므로 단위·통합·워크플로 시험을 구현보다 먼저 작성하고,
실패를 확인한 뒤 코드를 작성한다.

## 형식

`- [ ] T001 [P?] [US?] 설명과 정확한 파일 경로`

---

## Phase 1: Setup (공유 계약 고정)

**Purpose**: 결과를 보기 전에 후보·자료·구간·비용·관문·출력 계약을 기계 판독 가능하게 고정한다.

- [X] T001 `specs/174-accounting-cross-sectional-factors/contracts/accounting-factor-preregistration.json`과 `accounting-factor-result.schema.json`을 JSON 파서로 검증한다.
- [X] T002 `specs/174-accounting-cross-sectional-factors/quickstart.md`의 실행 경로와 `uv run python` 명령을 현재 저장소 구조에 맞춰 검증한다.
- [X] T003 [P] `specs/174-accounting-cross-sectional-factors/checklists/requirements.md`의 모든 요구사항이 완료됐는지 확인한다.

---

## Phase 2: Foundational (구현 전 공통 기반)

**Purpose**: 기존 통계·장부·워크플로 계약을 읽고 새 가족이 재사용할 경계를 확정한다.

**⚠️ CRITICAL**: 이 단계가 끝나기 전에는 사용자 스토리 구현을 시작하지 않는다.

- [X] T004 `src/auto_invest/analytics/turn_of_month_equity_factory.py`와 `scripts/turn_of_month_equity_factory_probe.py`에서 재사용할 PBO·PSR·집중도·결과 구조를 확인한다.
- [X] T005 [P] `src/auto_invest/portfolio/factory_evidence.py`와 `src/auto_invest/analytics/research_family_audit.py`의 20가족 교정·가족 분류 계약을 확인한다.
- [X] T006 [P] `.github/workflows/autonomous-strategy-factory.yml`과 `tests/integration/test_strategy_factory_workflow.py`의 현재 784행·19가족 게시 흐름을 확인한다.

**Checkpoint**: 회계 모듈이 브로커·주문·라이브 설정을 가져오지 않는 독립 경계가 확정됨.

---

## Phase 3: User Story 1 - 가격 신호와 독립적인 회계 프리미엄 검증 (Priority: P1) 🎯 MVP

**Goal**: 공식 보관본/최신본을 시간 분리하고 사전등록 16개 후보를 비용 후 역사 관문으로 판정한다.

**Independent Test**: 개발 구간만으로 후보가 하나 선택되고, 홀드아웃·비용 스트레스·부호 반전 결과가 고정 기준으로 재현된다.

### Tests for User Story 1

- [X] T007 [P] [US1] 8개 가중 조합×2개 슬리브가 정확히 16개 고유 후보·지문을 만드는 실패 시험을 `tests/unit/test_accounting_factor_factory.py`에 작성한다.
- [X] T008 [P] [US1] 월별 ZIP 파서의 정상·중복·역순·필수열 누락·결측 표식·비유한 수 실패 시험을 `tests/unit/test_accounting_factor_factory.py`에 작성한다.
- [X] T009 [P] [US1] 보관본 개발/차단과 최신본 홀드아웃 분리, 공통 개발 월 불일치, 과거값 재구성 감사 시험을 `tests/unit/test_accounting_factor_factory.py`에 작성한다.
- [X] T010 [US1] 개발 선택·PBO·PSR·시대·최근 36개월·집중도·낙폭·3%/5% 비용·부호 반전 관문 시험을 `tests/unit/test_accounting_factor_factory.py`에 작성한다.
- [X] T011 [US1] T007~T010이 새 모듈 부재 또는 미구현 때문에 실패하는지 확인한다.

### Implementation for User Story 1

- [X] T012 [US1] 엄격한 ZIP/CSV 월자료 파서와 자료 지문·범위·재구성 감사를 `src/auto_invest/analytics/accounting_factor_factory.py`에 구현한다.
- [X] T013 [US1] 사전등록 16개 후보·불변 정책 지문·연 1.5% 비용 수익 계산을 `src/auto_invest/analytics/accounting_factor_factory.py`에 구현한다.
- [X] T014 [US1] 개발 전용 선택·10조각 PBO·홀드아웃 관문·3%/5% 스트레스·부호 반전 위약시험을 `src/auto_invest/analytics/accounting_factor_factory.py`에 구현한다.
- [X] T015 [US1] T007~T010 단위 시험을 통과시키고 결정론적 재실행을 확인한다.

**Checkpoint**: 공식 자료 파일을 주입하면 홀드아웃을 선택에 쓰지 않고 역사 판정 가능.

---

## Phase 4: User Story 2 - 전략 존재와 실자본 적격을 분리 (Priority: P2)

**Goal**: 역사적 엣지, 완화된 종이 관찰 적격, 현재 실자본 부적격을 서로 다른 필드로 공개한다.

**Independent Test**: 합성 자료에서 역사 관문이 통과해도 실행 동등성 부재 때문에 배포 설정·연구 캐너리·승격은 항상 꺼져 있다.

### Tests for User Story 2

- [X] T016 [P] [US2] `FACTORY_EDGE`·`PAPER_CHALLENGER`·`NO_FACTORY_EDGE` 분류와 실패 관문 공개 시험을 `tests/unit/test_accounting_factor_factory.py`에 작성한다.
- [X] T017 [P] [US2] 역사 합격 자료에서도 `selected_deploy_config=null`, `research_canary_eligible=false`, `promotion_allowed=false`인 시험을 `tests/unit/test_accounting_factor_factory.py`에 작성한다.
- [X] T018 [US2] 로컬 파일 주입·공식 URL 재시도·SHA-256·JSON/Markdown 출력을 검증하는 실패 시험을 `tests/integration/test_accounting_factor_factory_probe.py`에 작성한다.

### Implementation for User Story 2

- [X] T019 [US2] 세 상태 분류·기준/현재값·실행 동등성 실패·다음 연구 방향을 `src/auto_invest/analytics/accounting_factor_factory.py` 결과와 Markdown에 구현한다.
- [X] T020 [US2] 공식 자료의 제한된 재시도와 로컬 파일 재현, JSON Schema 검증, JSON/Markdown 출력을 `scripts/accounting_factor_factory_probe.py`에 구현한다.
- [X] T021 [US2] T016~T018 시험을 통과시키고 프로브가 브로커·주문·자본·라이브 설정을 읽지 않는지 확인한다.

**Checkpoint**: 역사적 유망함과 현재 실행 가능성을 섞지 않는 독립 결과 생성 가능.

---

## Phase 5: User Story 3 - 중앙 탐색 장부의 독립성 보존 (Priority: P3)

**Goal**: 기존 784행·19가족을 다시 검증한 뒤 회계 16행·1가족만 추가해 800행·20가족으로 게시한다.

**Independent Test**: 행·지문·가족이 정확히 맞을 때만 20% 교정 예산이 성립하고 누락·중복·알 수 없는 가족은 실패 폐쇄한다.

### Tests for User Story 3

- [X] T022 [P] [US3] `accounting-factor-` 후보를 하나의 `accounting-cross-sectional-factor` 가족으로 분류하는 시험을 `tests/unit/test_research_family_audit.py`에 작성한다.
- [X] T023 [P] [US3] 800행·20가족·0.20 오합격 상한과 실행 동등성 실패를 소비자가 재계산하는 시험을 `tests/unit/test_factory_evidence.py`에 작성한다.
- [X] T024 [US3] 회계 프로브가 이전 784행·19가족의 완전성, 중복, 상태, 교정을 실패 폐쇄하는 시험을 `tests/integration/test_accounting_factor_factory_probe.py`에 작성한다.
- [X] T025 [US3] 중앙 워크플로가 월말 전략 결과 뒤 회계 가족을 실행·검증·최종 게시하는 시험을 `tests/integration/test_strategy_factory_workflow.py`에 작성한다.

### Implementation for User Story 3

- [X] T026 [US3] `src/auto_invest/analytics/research_family_audit.py`에 회계 가족 분류를 추가한다.
- [X] T027 [US3] `src/auto_invest/analytics/accounting_factor_factory.py`와 `scripts/accounting_factor_factory_probe.py`에 784→800행, 19→20가족 감사와 0.20 교정 검증을 구현한다.
- [X] T028 [US3] `.github/workflows/autonomous-strategy-factory.yml`에 회계 프로브, 800/20 단언, 상세/간결 sidecar 게시를 연결한다.
- [X] T029 [US3] T022~T025 시험을 통과시키고 중앙 소비자의 독립 재계산이 원시 결과와 일치하는지 확인한다.

**Checkpoint**: 전체 장부가 800개 변형이 아니라 20개 독립 전략 가족임을 기계 판독 가능하게 표시.

---

## Phase 6: 생산 재생과 운영 증거

**Purpose**: 코드·후보·관문을 먼저 커밋한 뒤 공식 자료를 한 번 열어 실제 판정과 운영 상태를 기록한다.

- [X] T030 구현 코드·시험·워크플로를 공식 자료 열람 전에 커밋해 결과 후 기준 변경 가능성을 차단한다.
- [X] T031 `scripts/accounting_factor_factory_probe.py`로 공식 2015년 보관본과 최신본을 내려받아 실제 생산 결과를 `/tmp/accounting_factor_factory.json`과 `/tmp/accounting_factor_factory.md`에 생성한다.
- [X] T032 `specs/174-accounting-cross-sectional-factors/contracts/accounting-factor-result.schema.json`으로 생산 JSON을 검증하고 같은 입력의 재실행 결과가 동일한지 확인한다.
- [X] T033 실제 선택 후보·PBO·PSR·비용 후 초과수익·시기/집중도/낙폭·스트레스·위약·재구성 차이를 `specs/174-accounting-cross-sectional-factors/production-result.md`에 기록한다.
- [X] T034 역사 결과와 무관하게 주문 0건·자본 배분 0건·라이브 설정 변경 0건과 다음 21번째 가족의 재교정 필요를 `specs/174-accounting-cross-sectional-factors/production-result.md`에 기록한다.

---

## Phase 7: 검증·PR·배포·인계

**Purpose**: 전체 저장소와 실제 자동화 적용 경로를 검증하고 다음 세션이 같은 결론을 재현하게 한다.

- [X] T035 관련 단위·통합 시험과 `uv run ruff check src tests scripts/accounting_factor_factory_probe.py`를 실행한다.
- [X] T036 `uv run pytest`와 `uv run ruff check src tests` 전체 검증을 통과시킨다.
- [X] T037 `uv run python scripts/agent_harness_probe.py --strict`와 `uv run python scripts/check_handoff_facts.py`를 통과시킨다.
- [X] T038 위험 등급 4, 문제 정의, 탐색 근거, 안전 경계, 전체 검증, 되돌림을 담은 PR 본문을 만들고 `scripts/check_pr_quality_gate.py`로 검증한다.
- [X] T039 브랜치를 푸시하고 PR을 만든 뒤 최신 `origin/main`과의 머지 가능성·전체 관문을 다시 확인해 merge 방식으로 자동 머지한다.
- [X] T040 `deploy-status` 기술로 main 배포와 dry-run worker 반영 여부를 확인하고 실제 주문·자본 변경이 없는지 현재 sidecar에서 다시 읽는다.
- [X] T041 중앙 전략 공장 워크플로를 재생해 800행·20가족 결과가 sidecar에 게시됐는지 확인한다.
- [X] T042 `handoff` 기술로 `HANDOFF.md`의 main 커밋·테스트·전략 결과·남은 다음 단계와 현재 실자본 부적격을 갱신하고 별도 PR로 검증·머지한다.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup** → **Foundational** → **US1** → **US2** → **US3** 순으로 진행한다.
- 세 사용자 스토리가 끝난 뒤에만 생산 자료를 연다.
- 생산 판정과 전체 검증 뒤에만 PR·머지·배포·sidecar·인계를 수행한다.

### User Story Dependencies

- **US1**은 독립 월자료·후보·통계 판정을 제공한다.
- **US2**는 US1 결과를 역사/종이/실자본 상태로 분리한다.
- **US3**는 US1·US2 결과를 기존 중앙 장부에 결합한다.

### Within Each User Story

- 시험을 먼저 작성하고 의도한 이유로 실패하는지 확인한다.
- 자료모형/파서 → 계산/관문 → 프로브 → 중앙 워크플로 순으로 구현한다.
- 결과를 보기 전에 코드·후보·관문을 커밋한다.
- 누락 증거는 완화하지 않고 실패 폐쇄한다.

## Implementation Strategy

1. P1에서 가격 전략과 독립적인 회계 프리미엄의 역사적 존재만 검증한다.
2. P2에서 역사 통과와 현재 계좌 실행 가능성을 분리해 과장된 승격을 막는다.
3. P3에서 800개 변형을 20개 독립 가족으로 정확히 세고 중앙 자동화에 연결한다.
4. 공식 결과가 합격이면 SEC 공시시점 종목 구현을 다음 별도 명세로, 탈락이면 실패 관문이
   가리키는 경제 원천을 다음 재교정 뒤 연구한다.

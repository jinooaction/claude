# Tasks: 오너 단회 장중 긴급 배포

**Input**: Design documents from `/specs/179-owner-emergency-live-deploy/`  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`  
**Risk grade**: 4 - 생산 배포 시점과 실주문 상호 배제 경계 변경  
**Tests**: 실패 시험을 먼저 작성하고 의도한 이유로 실패한 뒤 구현한다.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 헌법과 명세를 구현 전에 고정한다.

- [x] T001 헌법 15.0.0의 단회 오너 장중 긴급 배포 계약을 `.specify/memory/constitution.md`에 전용 안전 경계 커밋으로 기록한다.
- [x] T002 Spec 179의 요구·계획·연구·데이터·계약·검증 절차를 `specs/179-owner-emergency-live-deploy/`에 작성하고 `.specify/feature.json`과 `CLAUDE.md` 포인터를 갱신한다.
- [x] T003 `specs/179-owner-emergency-live-deploy/contracts/emergency-deploy-request.schema.json`을 JSON 파서와 필수 필드 검사로 검증한다.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 승인, 감사, 잠금의 실패 시험을 먼저 고정한다.

- [x] T004 [P] 긴급 요청 정상·누락·만료·미래·15분 초과·SHA 불일치·재사용·심볼릭 링크·소유권·권한 실패 시험을 `tests/unit/test_emergency_deploy.py`에 작성한다.
- [x] T005 [P] 열린 정규장의 일반 배포 거부와 유효 요청의 승인→시작→성공/실패 감사 순서 시험을 `tests/integration/test_deploy_end_to_end.py`에 추가한다.
- [x] T006 [P] 고정 SSH 명령·오너 입력·KIS 미체결 0건·요청 파일·정리·복구 실패 잠금 보존 시험을 `tests/unit/test_emergency_deploy_shell.py`에 작성한다.
- [x] T007 [P] 유지보수 잠금이 GitHub helper와 서버 timer를 거래일 선점 전에 막는 시험을 `tests/unit/test_live_canary_gateway.py`, `tests/unit/test_live_canary_workflow.py`, `tests/unit/test_live_canary_server_scheduler.py`에 추가한다.
- [x] T008 [P] 유지보수 잠금이 각 최종 중개사 쓰기를 막고 거부 감사를 남기는 시험을 `tests/integration/test_order_router.py`에 추가한다.
- [x] T009 T004~T008이 새 계약 미구현 때문에 실패하는지 `tests/unit/`과 `tests/integration/test_deploy_end_to_end.py`에서 확인한다.

**Checkpoint**: 돈 경로 실패 조건이 구현보다 먼저 재현된다.

---

## Phase 3: User Story 1 - 특정 커밋을 지금 안전하게 배포 (Priority: P1) 🎯 MVP

**Goal**: 정확한 current-main, namespace 소유자 또는 헌법 등록 시스템 오너, 15분 이내 단회 요청만 장중 배포를 연다.

**Independent Test**: 열린 XNYS에서 유효 요청만 배포가 진행되고 일반·만료·재사용·불일치 요청은 생산 변경 전 거부된다.

### Implementation for User Story 1

- [x] T010 [US1] 고정 요청 모델과 파일 보안·시간·SHA 검증, 감사 기반 단회 소비 검사를 `src/auto_invest/deploy/emergency.py`에 구현한다.
- [x] T011 [US1] `DEPLOY_EMERGENCY_AUTHORIZED` 사건과 긴급 승인 단계를 `src/auto_invest/persistence/audit.py`에 추가한다.
- [x] T012 [US1] 열린 XNYS에서만 유효 요청을 소비하고 승인 사건을 시작 사건보다 먼저 남기는 경로를 `src/auto_invest/deploy/runner.py`에 구현한다.
- [x] T013 [US1] 루트 소유 잠금·KIS 읽기 전용 smoke·고정 요청 생성·배포 서비스 실행·안전 정리를 `deploy/emergency-deploy-on-instance.sh`에 구현한다.
- [x] T014 [US1] `emergency-deploy` 고정 명령과 최소 sudo 권한·helper 설치를 `deploy/repair-ssh-boundary.sh`에 추가한다.
- [x] T015 [US1] 등록 오너·확인 문구·정확한 SHA·이유를 검증하고 고정 긴급 명령만 호출하는 입력을 `.github/workflows/deploy-on-merge.yml`에 구현한다.
- [x] T016 [US1] T004~T006과 기존 배포 회귀를 통과시켜 일반 장중 차단이 유지되는지 `tests/unit/test_emergency_deploy.py`와 `tests/integration/test_deploy_end_to_end.py`에서 확인한다.

**Checkpoint**: 일반 장중 배포는 닫혀 있고 단회 오너 요청만 배포 실행기에 도달한다.

---

## Phase 4: User Story 2 - 배포 동안 주문을 완전히 멈추고 안전하게 복구 (Priority: P1)

**Goal**: 코드 변경과 자동 실주문이 겹치지 않고, 실패 시 확인된 복구 전까지 주문 정지를 유지한다.

**Independent Test**: 유지보수 잠금이 세 주문 경계에서 broker write와 거래일 선점을 0건으로 만들고, 성공·복구 확인 뒤에만 풀린다.

### Implementation for User Story 2

- [x] T017 [P] [US2] 거래일 선점 전에 루트 유지보수 잠금을 검사하도록 `deploy/live-canary-on-instance.sh`를 수정한다.
- [x] T018 [P] [US2] 거래일 선점 전에 같은 잠금을 검사하도록 `deploy/live-canary-scheduled-on-instance.sh`를 수정한다.
- [x] T019 [US2] 각 실제 KIS 주문 쓰기 직전에 유지보수 잠금을 재검사하고 거부 감사를 남기도록 `src/auto_invest/execution/order_router.py`를 수정한다.
- [x] T020 [US2] 배포 성공이나 확인된 롤백에서만 잠금을 제거하고 복구 실패에서는 상태 이유와 잠금을 남기도록 `deploy/emergency-deploy-on-instance.sh`를 완성한다.
- [x] T021 [US2] T007~T008과 장 마감 경쟁·부분 실행·중복 scheduler 회귀를 `tests/unit/test_live_canary_gateway.py`, `tests/unit/test_live_canary_workflow.py`, `tests/unit/test_live_canary_server_scheduler.py`, `tests/integration/test_order_router.py`에서 통과시킨다.

**Checkpoint**: 배포와 broker write가 상호 배제되고 실패 상태가 자동으로 다시 열리지 않는다.

---

## Phase 5: User Story 3 - 재현 가능한 운영 증거와 실제 자동 거래 (Priority: P2)

**Goal**: 오너는 한 번 승인하고, 다음 세션은 승인·배포·건강·복구·자동 주문 결과를 한 실행으로 재현한다.

**Independent Test**: 감사 장부와 workflow 요약이 비밀값 없이 같은 요청·상관관계·대상·결과를 보고하고 후속 자동 거래 경계가 변하지 않는다.

### Implementation for User Story 3

- [x] T022 [P] [US3] 긴급 배포 운영 절차·되돌림·주문 비승인 의미를 `deploy/AUTO-DEPLOY.md`와 `deploy/README.md`에 기록한다.
- [x] T023 [US3] 성공·거부·복구·주문 잠금 상태를 정화된 workflow 요약으로 남기도록 `.github/workflows/deploy-on-merge.yml`을 완성한다.
- [x] T024 [US3] 관련 배포·감사·실주문 시험과 shell syntax 검사를 모두 통과시킨다.

**Checkpoint**: 운영자가 서버 명령을 직접 쓰지 않아도 결과와 안전 상태를 재현할 수 있다.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T025 `uv run pytest`와 `uv run ruff check src tests` 전체 검증을 통과시킨다.
- [x] T026 `uv run python scripts/agent_harness_probe.py --strict`와 `uv run python scripts/check_handoff_facts.py`를 통과시킨다.
- [x] T027 위험 등급 4, K6/K-meta, 문제 정의, 대체·실패·되돌림을 담은 PR 본문을 `scripts/check_pr_quality_gate.py`로 검증한다.
- [x] T028 브랜치를 push하고 PR을 만든 뒤 최신 `origin/main`, 원격 checks, mergeability를 재확인해 merge commit 방식으로 자동 머지한다.
- [ ] T029 exact latest main으로 오너 단회 긴급 workflow를 실행하고 KIS 6/6·미체결 0·승인/시작/완료 감사·90초 건강·주문 잠금 해제를 생산에서 확인한다.
- [ ] T030 기존 GitHub schedule 또는 서버 timer의 첫 유효 자동 실행에서 신규 주문 접수·실제 체결·전략 추가 전용 감사·동일 실행 계좌 대사를 생산에서 확인한다.
- [ ] T031 다른 scheduler 출처가 같은 최초 run ID/source를 반환하고 중복 broker write 0건인지 생산에서 확인한다.
- [ ] T032 `handoff` 기술로 `HANDOFF.md`와 Spec 176·179 tasks의 main·배포·실제 체결 사실을 갱신하고 전체 품질 관문·PR·merge를 완료한다.
- [x] T033 생산 run 33667656920에서 GitHub namespace owner와 실제 시스템 오너가 다른 신원 결함이 SSH·서버·중개사 접근 전에 실패 폐쇄됐음을 확인한다.
- [x] T034 헌법 15.0.1과 Spec 179에 정확한 등록 시스템 오너 actor 계약을 추가하고 입력·변수·secret·역할 기반 권한 확장을 금지한다.
- [x] T035 등록 시스템 오너 보정을 회귀·전체 검증하고 별도 안전 경계 PR로 merge한다.
- [ ] T036 등록 시스템 오너의 exact-main 단회 긴급 workflow가 생산 배포와 감사·건강·잠금 해제를 완료하는지 확인한다.
- [x] T037 run `33671389870`에서 새 helper가 구버전 설치 배포 실행기를 호출해 KIS 6/6·미체결 0 뒤에도 `DEPLOY_STARTED` 전에 실패하는 최초 도입 순환 의존을 생산에서 확인한다.
- [x] T038 헌법 15.1.0과 Spec 179에 exact-target 격리 배포 실행기와 시작 전 HALTED 잠금의 엄격한 인계 계약을 전용 안전 경계 커밋으로 고정한다.
- [x] T039 exact-target bootstrap, 등록 actor 집합, HALTED 유일 승인·시작 0건 인계를 구현하고 변조·임의 경로·시작 후 인계 실패 시험을 통과시킨다.
- [ ] T040 전체 검증·PR 관문·merge 뒤 새 exact-main 단회 요청으로 생산 잠금을 안전 인계하고 배포·90초 건강·자동 timer 복구를 확인한다.
- [x] T041 run `33673819722`에서 exact-target bootstrap과 KIS 6/6·미체결 0은 통과했지만 config dry-run이 systemd 주입에 의존해 비밀값 없음으로 실패하고, 확인된 롤백 뒤 shell 지역변수 소멸로 요청·QUIESCED 잠금 정리가 중단된 생산 결함을 확인한다.
- [x] T042 헌법 15.2.0과 Spec 179에 terminal rollback orphan의 파일·장부·production HEAD 엄격 복구와 고정 env_path 직접 로딩 계약을 전용 안전 경계 커밋으로 고정한다.
- [x] T043 deploy config 검사에 고정 env_path를 전달하고, 정확한 롤백 orphan만 중개사 쓰기 잠금 아래 복구하며 정상·롤백 반환 전 지역 증거 범위에서 cleanup하도록 구현·반례 시험한다.
- [ ] T044 전체 검증·PR 관문·merge 뒤 새 exact-main 단회 요청으로 생산 rollback orphan을 안전 복구하고 배포·90초 건강·자동 timer 복구를 확인한다.
- [x] T045 run `33676023848`에서 terminal rollback 요청의 만료 시각 비교가 객체가 아닌 숫자 범위에서 `issued_at_epoch`를 조회해 생산 변경·KIS·신규 감사 전에 실패 폐쇄된 jq 범위 결함을 확인한다.
- [x] T046 요청 객체를 jq 변수에 고정하고 유효·역전 시각 payload로 실제 필터를 실행하는 회귀 시험을 추가한다.
- [ ] T047 전체 검증·PR 관문·merge 뒤 exact-main 배포 및 다음 정규장 오너 복구 요청으로 rollback orphan 해제·자동 timer 복구를 확인한다.
- [x] T048 헌법 15.3.0과 Spec 179에 후속 정상 live 배포·Git 계보·worker/timer·KIS 증거에 기반한 cleanup-only rollback orphan 회수 계약을 전용 안전 경계 커밋으로 고정한다.
- [x] T049 workflow가 정상 배포 성공 뒤에도 고정 helper에 stale 상태 판정을 맡기고, helper가 완료 감사·두 잠금·미체결 0건 아래에서 전용 복구 완료 사건 뒤 이전 파일만 제거하도록 구현·반례 시험한다.
- [ ] T050 전체 검증·PR 관문·merge·exact-main 정상 배포 뒤 등록 오너 단회 요청으로 생산 orphan 회수, timer 재개, 주문 없는 preflight를 확인한다.
- [x] T051 헌법 15.3.1과 Spec 179에 workflow 결과를 현재 배포 시도 구간에만 묶고 현재 stale-target 거부만 고정 root helper로 넘기는 계약을 전용 안전 경계 커밋으로 고정한다.
- [x] T052 최신 서비스 시작 표식 뒤 구간만 추출해 장중 연기와 긴급 진입을 판정하고 과거 장중 문구의 거짓 성공을 막는 workflow 회귀 시험을 추가한다.
- [ ] T053 전체 검증·PR 관문·merge 뒤 exact-main 등록 오너 요청으로 생산 rollback orphan 복구와 긴급 배포를 다시 확인한다.
- [x] T054 헌법 15.4.0과 Spec 179에 검증된 건강한 중간 배포에서 새 exact-target 긴급 배포로 잠금을 인계하는 계약을 전용 안전 경계 커밋으로 고정한다.
- [x] T055 Git 계보·후속 live 배포 장부·worker/timer·두 잠금·KIS 미체결 0건 아래에서만 비종료 `DEPLOY_EMERGENCY_ORPHAN_RECOVERED`를 기록하고 같은 잠금으로 기존 exact-target 상태기계를 계속하도록 구현·반례 시험한다.
- [ ] T056 전체 검증·PR 관문·merge 뒤 등록 오너 단회 요청으로 생산의 건강한 중간 배포에서 최신 main으로 인계·배포·90초 건강·timer 복구를 확인한다.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: 시작 완료. T003 계약 검증 뒤 구현 가능하다.
- **Phase 2**: Phase 1에 의존하며 모든 실패 시험을 먼저 고정한다.
- **US1**: Phase 2 뒤 시작하며 오너 단회 승인과 배포 진입을 제공한다.
- **US2**: Phase 2 뒤 시작 가능하지만 최종 통합은 US1 helper에 의존한다.
- **US3**: US1과 US2가 끝난 뒤 운영 증거를 마무리한다.
- **Polish**: 모든 사용자 이야기가 끝난 뒤 진행한다.

### Parallel Opportunities

- T004~T008은 서로 다른 파일의 실패 시험이라 병렬 가능하다.
- T017과 T018은 두 자동 scheduler helper에서 병렬 구현 가능하다.
- T022는 핵심 코드 검증과 독립적으로 작성 가능하다.

## Implementation Strategy

1. 헌법·SDD를 먼저 고정한다.
2. 실패 시험으로 단회성·권한·잠금·경쟁 조건을 재현한다.
3. US1의 최소 오너 승인 배포를 구현한다.
4. US2의 세 겹 주문 잠금과 복구 보존을 결합한다.
5. US3의 감사·운영 문서를 완성한다.
6. 전체 검증과 PR 관문 뒤 즉시 merge하고, 이번 오너 지시를 근거로 정확한 main에 단회 긴급 배포한다.
7. 정상 자동 scheduler의 실제 주문·체결·감사·대사·중복 차단까지 관찰한 뒤에만 완료한다.

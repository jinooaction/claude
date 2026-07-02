# Tasks: 운영자 대시보드와 모바일 알림 루프

**Input**: Design documents from `specs/080-operator-dashboard-alert-loop/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup

- [x] T001 SDD 산출물과 `.specify/feature.json`, `CLAUDE.md` 포인터를 `specs/080-operator-dashboard-alert-loop/`에 맞춘다.

## Phase 2: Foundational

- [x] T002 [P] `src/auto_invest/analytics/operator_status.py`에 운영자 상태 보고 데이터 구조와 안전 불변조건을 추가한다.
- [x] T003 [P] `tests/unit/test_operator_status.py`에 상태 분류, 비밀값 마스킹, 알림 판정 단위 테스트를 추가한다.
- [x] T004 [P] `scripts/operator_status_probe.py`에 manifest, JSON 출력, Markdown 출력 진입점을 추가한다.
- [x] T005 [P] `tests/integration/test_operator_status_probe.py`에 probe manifest와 출력 파일 통합 테스트를 추가한다.

## Phase 3: User Story 1 - 모바일 대시보드에서 전체 상태 확인 (Priority: P1)

**Goal**: 기존 모바일 상태판이 운영자 상태 보고를 먼저 보여준다.

**Independent Test**: `uv run pytest tests/integration/test_mobile_status_page.py`

- [x] T006 [US1] `scripts/generate_mobile_status.py`가 operator-status 입력을 읽고 `operator-status-data` JSON을 HTML에 포함하게 한다.
- [x] T007 [US1] `scripts/generate_mobile_status.py` 모바일 HTML에 전체 상태, 실제 돈 상태, 다음 자율 작업, 개입 필요 섹션을 추가한다.
- [x] T008 [US1] `.github/workflows/mobile-status-pages.yml`가 operator-status sidecar도 수집하게 한다.
- [x] T009 [US1] `tests/integration/test_mobile_status_page.py`에 operator status HTML 렌더링 검증을 추가한다.

## Phase 4: User Story 2 - 개입 필요 이벤트만 모바일 알림 (Priority: P1)

**Goal**: 운영 상태가 개입 필요일 때만 Telegram 메시지를 best-effort로 보낸다.

**Independent Test**: `uv run pytest tests/unit/test_operator_status.py tests/unit/test_operator_mobile_alerts_workflow.py`

- [x] T010 [US2] `src/auto_invest/analytics/operator_status.py`에 `ACTION_REQUIRED` 이상에서만 전송하는 메시지 생성 규칙을 구현한다.
- [x] T011 [US2] `.github/workflows/operator-mobile-alerts.yml`를 추가해 sidecar 수집, operator status 생성, Telegram best-effort 전송, sidecar 발행을 수행한다.
- [x] T012 [US2] `tests/unit/test_operator_mobile_alerts_workflow.py`에 workflow 안전 문자열, 비밀값 부재 skip, 발행 파일 검증을 추가한다.

## Phase 5: User Story 3 - 알림 루프 자체 감시와 인계 (Priority: P2)

**Goal**: operator-status 루프도 sidecar와 pipeline liveness에서 추적된다.

**Independent Test**: `uv run pytest tests/unit/test_pipeline_liveness.py tests/integration/test_operator_status_probe.py`

- [x] T013 [US3] `src/auto_invest/analytics/pipeline_liveness.py` 기본 감시 목록에 `operator-status`를 비핵심 sidecar로 등록한다.
- [x] T014 [US3] `tests/unit/test_pipeline_liveness.py`에 `operator-status` 레지스트리 검증을 추가한다.
- [x] T015 [US3] `specs/080-operator-dashboard-alert-loop/contracts/operator-status.md`에 최종 sidecar 계약을 코드와 맞춘다.

## Phase 6: Polish & Validation

- [x] T016 `uv run pytest tests/unit/test_operator_status.py tests/integration/test_operator_status_probe.py tests/integration/test_mobile_status_page.py tests/unit/test_operator_mobile_alerts_workflow.py tests/unit/test_pipeline_liveness.py`를 실행한다.
- [x] T017 `uv run python scripts/operator_status_probe.py --manifest`와 로컬 sample 실행으로 quickstart를 검증한다.
- [x] T018 `uv run pytest` 전체 테스트를 실행한다.
- [x] T019 `uv run ruff check src tests` 린트를 실행한다.
- [x] T020 PR 본문을 `.github/pull_request_template.md` 기준으로 작성하고 `scripts/check_pr_quality_gate.py`로 검증한다.
- [x] T021 PR 생성·푸시·머지 가능 상태 확인·자동 머지를 수행한다.
- [x] T022 main 머지 후 deploy/status와 operator-status 또는 관련 sidecar 실행 상태를 확인한다.
- [x] T023 `HANDOFF.md`와 새 `HANDOFF-084-OPERATOR-DASHBOARD-ALERTS.md`를 갱신하고 handoff 검증을 실행한다.

## Dependencies & Execution Order

- Phase 1과 Phase 2가 모든 사용자 이야기의 기반이다.
- US1과 US2는 같은 `OperatorStatusReport`를 공유하므로 T002~T005 뒤에 진행한다.
- US3은 workflow와 sidecar 이름이 확정된 뒤 진행한다.
- 전체 테스트와 린트가 통과하기 전에는 PR 머지를 하지 않는다.

## Implementation Strategy

1. 상태 보고 코어와 probe를 먼저 만든다.
2. 모바일 상태판을 같은 JSON으로 확장한다.
3. Telegram workflow를 best-effort로 붙인다.
4. pipeline liveness와 handoff로 다음 세션의 관측 경로를 닫는다.

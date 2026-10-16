# Tasks: Capital Path Readiness Loop

**Input**: Design documents from `specs/076-capital-path-readiness-loop/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required because this is a risk grade 2 operating automation and adds a recurring sidecar loop.

## Phase 1: Setup

- [X] T001 Create spec 076 design artifacts in `specs/076-capital-path-readiness-loop/`.
- [X] T002 Move `.specify/feature.json` and `CLAUDE.md` Speckit pointer to spec 076.

## Phase 2: Readiness core

- [X] T003 [P] [US1] Add capital path readiness dataclasses and JSON/Markdown rendering in `src/auto_invest/analytics/capital_path_readiness.py`.
- [X] T004 [P] [US1] Add safe sidecar JSON extraction and missing/malformed evidence handling in `src/auto_invest/analytics/capital_path_readiness.py`.
- [X] T005 [US1] Implement readiness state classification from money-path and reassign evidence in `src/auto_invest/analytics/capital_path_readiness.py`.
- [X] T006 [P] [US1] Add unit tests for accumulating-edge and preview-only classification in `tests/unit/test_capital_path_readiness.py`.

## Phase 3: Candidate routing

- [X] T007 [US2] Parse evolution candidate backlog and learning ledger into priority/suppressed readiness candidates in `src/auto_invest/analytics/capital_path_readiness.py`.
- [X] T008 [P] [US2] Add unit tests proving rejected candidates are suppressed and live-readiness candidates are prioritized in `tests/unit/test_capital_path_readiness.py`.

## Phase 4: Probe and workflow

- [X] T009 [US3] Add `scripts/capital_path_readiness_probe.py` manifest, JSON, and Markdown output support.
- [X] T010 [US3] Add `.github/workflows/capital-path-readiness.yml` to collect sidecars and publish `automation/capital-path-readiness-last-run`.
- [X] T011 [US3] Register `capital-path-readiness` in `src/auto_invest/analytics/pipeline_liveness.py`.
- [X] T012 [P] [US3] Add integration tests for probe manifest/output and pipeline liveness registration in `tests/integration/`.

## Phase 5: Smoke and verification

- [X] T013 Run latest-sidecar local smoke proving current state is not capital-armable and rejected candidates are suppressed.
- [X] T014 Run focused capital path readiness tests.
- [X] T015 Run `uv run pytest`.
- [X] T016 Run `uv run ruff check src tests`.
- [X] T017 Run PR quality gate, handoff fact check, and strict agent harness.
- [X] T018 Commit, push, open PR, satisfy checks, and merge when automatic merge conditions are met.
- [X] T019 Check post-merge workflow/sidecar status and refresh HANDOFF.

## Dependencies & Execution Order

- T001-T002 before implementation.
- T003-T005 before probe/workflow.
- T006/T008 validate core and candidate routing before workflow smoke.
- T009-T012 before latest-sidecar smoke.
- T013-T019 after implementation.

## Parallel Opportunities

- T003, T004, and T006 touch different responsibilities and can be prepared independently.
- T008 and T012 cover different test layers.
- Focused tests can run before full pytest.

## Implementation Strategy

2026-10-16 기존 소비자 보정:
- [x] 실제 원본의 계좌 대사 차단 누락을 재현한다(수정 전 신규1실패/15통과).
- [x] 준비도/정렬/운영판/모바일의 이유 선택과 호환 처리를 함께 고친다.
- [x] 관련50개/0.20초·린트 및 원본accb5f4d 재생으로 실제 차단/NO_EDGE 동시 보존을 확인한다.
- [ ] 정확 PR HEAD 전체 회귀/린트·필수 반례·품질 관문·병합과 후속 보고서 발행을 확인한다.
  최종 근거는 PR 본문에 남긴다. 표시만을 위해 검사를 반복하지 않는다.
  전체181 T013~T016, 정지 해제, 승인 발급·자금 배정·실제 주문 완료는 별개다.

1. Build a pure read-only core that classifies readiness from dictionaries/text.
2. Add a probe that mirrors existing sidecar collection patterns.
3. Publish a dedicated workflow sidecar.
4. Register the sidecar in liveness and prove current sidecars produce a safe, non-capital-armable result.

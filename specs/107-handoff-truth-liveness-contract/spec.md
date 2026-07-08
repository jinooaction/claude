# Feature Specification: HANDOFF Truth Liveness Contract

**Feature Branch**: `Codex/107-handoff-truth-liveness-contract`
**Created**: 2026-07-08
**Status**: Draft
**Input**: User description: "다음 자율 후보 `candidate-handoff-truth-liveness-contract`을 목표 스킬로 꼼꼼하게 진행"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - HANDOFF 사실성을 계약으로 본다 (Priority: P1)

운영자는 최신 `HANDOFF.md`의 요약표가 실제 `origin/main` 상태와 맞는지, 손으로 검사기를 조합하지 않고 하나의 읽기 전용 보고서에서 확인한다.

**Why this priority**: 자율 작업 루프는 다음 세션이 같은 상태를 다시 탐색하지 않도록 HANDOFF를 신뢰 가능한 진입점으로 써야 한다. 지금은 `check_handoff_facts.py`가 있지만, 자율 후보 관점의 완료 후보, 다음 후보, 안전 경계, 판정 JSON이 분리되어 있지 않다.

**Independent Test**: 현재 저장소 또는 fixture HANDOFF를 입력해 보고서를 만들면 `overall_status`, 기준 종류, 검증 게이트, 완료 후보, 다음 후보가 JSON과 Markdown에 드러난다.

**Acceptance Scenarios**:

1. **Given** `HANDOFF.md`의 마지막 main 커밋 행이 실제 `origin/main`과 일치함, **When** 생존성 보고서를 생성하면, **Then** 보고서는 `CONTRACT_READY`와 `baseline_kind=origin_main`을 반환한다.
2. **Given** `HANDOFF.md`가 읽히고 검증 항목이 모두 통과함, **When** Markdown을 렌더링하면, **Then** 다음 세션이 `## 검증 게이트`와 `## HANDOFF 기준`에서 상태를 재현할 수 있다.

---

### User Story 2 - handoff-only 머지를 stale로 오판하지 않는다 (Priority: P2)

운영자는 문서·스펙만 바꾼 handoff-only 머지 때문에 `HANDOFF.md`의 마지막 코드 기준이 한 커밋 뒤로 보일 때, 이것이 정상 지연인지 실제 stale인지 구분한다.

**Why this priority**: 최근 handoff-only PR은 `origin/main` 머지 커밋과 HANDOFF 요약표의 코드 기준이 달라 보이게 만든다. 이 정상 상태를 stale로 오판하면 다음 세션은 불필요한 복구 작업을 반복한다.

**Independent Test**: `origin/main`이 handoff-only merge이고 HANDOFF가 첫 부모 커밋을 가리키는 fixture에서 보고서가 통과하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 최신 main 머지의 변경 파일이 Markdown 또는 `specs/` 경로뿐임, **When** HANDOFF가 그 머지의 첫 부모를 가리키면, **Then** 보고서는 `baseline_kind=handoff_only_first_parent`로 통과한다.
2. **Given** HANDOFF 행이 어떤 허용 기준에도 맞지 않음, **When** 보고서를 생성하면, **Then** 보고서는 `BLOCKED`와 stale 사유를 반환한다.

---

### User Story 3 - 완료 뒤 PR/merge 증거 후보로 전진한다 (Priority: P3)

운영자는 `candidate-handoff-truth-liveness-contract`가 완료 처리된 뒤 같은 후보를 다시 받지 않고, 다음 운영 체계 후보인 PR/merge 증거 생존성 계약으로 넘어간다.

**Why this priority**: 후보가 완료됐는데도 autonomous-work가 같은 후보를 반복하면 운영자는 계속 "다음엔 뭘 해야 하냐"고 물어야 한다. 완료 마커와 전진 경로가 같이 고정되어야 한다.

**Independent Test**: released-work에 `candidate-handoff-truth-liveness-contract`을 넣으면 selected_work가 `candidate-pr-merge-evidence-liveness-contract`로 바뀌는지 확인한다.

**Acceptance Scenarios**:

1. **Given** released-work가 이번 완료 후보를 released로 기록함, **When** autonomous-work 보고서를 생성하면, **Then** selected_work는 `candidate-pr-merge-evidence-liveness-contract`다.
2. **Given** 이번 계약 보고서가 생성됨, **When** 보고서 JSON을 확인하면, **Then** `completed_candidate_id`와 `next_candidate_id`가 명시된다.

### Edge Cases

- `HANDOFF.md`가 없거나 읽을 수 없으면 복구가 필요한 상태로 `BLOCKED`가 된다.
- git 기준 정보를 얻지 못하면 `origin/main` 판단을 통과 처리하지 않는다.
- handoff-only merge의 변경 파일 목록이 비어 있거나 코드 파일을 포함하면 첫 부모 기준을 허용하지 않는다.
- `main 테스트`, `main 린트`, `열린 PR` 같은 선택 기대값이 주어졌고 HANDOFF 행과 맞지 않으면 `BLOCKED`가 된다.
- 이 보고서는 읽기 전용이며 PR 생성, merge, deploy, 브로커 호출, 주문, 자본 배분, 비밀값 접근을 하지 않는다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose a deterministic HANDOFF truth liveness report with `overall_status`, `completed_candidate_id`, `next_candidate_id`, evidence surfaces, baselines, quality gates, and safety invariants.
- **FR-002**: System MUST reuse the existing HANDOFF fact checker semantics so `origin/main` and valid handoff-only first-parent baselines are both accepted.
- **FR-003**: System MUST classify a HANDOFF main commit row that matches no allowed baseline as `BLOCKED`.
- **FR-004**: System MUST provide a CLI probe that prints JSON or Markdown and can write `--json-out` and `--summary-out`.
- **FR-005**: System MUST include `HANDOFF.md`, `scripts/check_handoff_facts.py`, `scripts/agent_harness_probe.py`, `.github/workflows/pr-quality-gate.yml`, `automation/released-work-last-run:released_work.json`, and `automation/autonomous-work-execution-last-run:LAST_RUN.md` as operating evidence references.
- **FR-006**: System MUST mark this work's completed candidate as `candidate-handoff-truth-liveness-contract`.
- **FR-007**: System MUST mark the next autonomous candidate as `candidate-pr-merge-evidence-liveness-contract`.
- **FR-008**: System MUST prove that released-work completion of this candidate advances autonomous-work to the next operating-system candidate.
- **FR-009**: System MUST NOT call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist/caps, read/write secrets, modify constitution/kernel files, run fresh external collection, or invoke paid external services.

### Key Entities *(include if feature involves data)*

- **HANDOFF Truth Liveness Report**: The read-only contract result for HANDOFF freshness, baseline semantics, quality gates, completed candidate, next candidate, and safety boundary.
- **Allowed Main Baseline**: A git-derived acceptable commit baseline, either the latest `origin/main` merge or the previous main commit before a handoff-only merge.
- **Quality Gate**: A PASS/FAIL decision that explains whether an input was readable, whether the main row matched, whether optional expected rows matched, and whether the safety boundary remains read-only.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-handoff-truth-liveness-contract`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Current checkout report returns `CONTRACT_READY` when `check_handoff_facts.py` is OK.
- **SC-002**: Unit tests cover origin-main match, handoff-only first-parent match, stale HANDOFF block, unreadable HANDOFF block, and optional expected row mismatch.
- **SC-003**: Probe JSON and Markdown contain completed candidate, next candidate, quality gates, baseline evidence, and safety invariants.
- **SC-004**: Autonomous-work focused test proves released `candidate-handoff-truth-liveness-contract` advances to `candidate-pr-merge-evidence-liveness-contract`.
- **SC-005**: Local quickstart replay confirms the probe and autonomous-work transition.
- **SC-006**: Full `uv run pytest`, `uv run ruff check src tests`, `git diff --check`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.

## Assumptions

- The correct runtime surface is a read-only analytics module plus probe script, not a workflow that edits HANDOFF or opens PRs automatically.
- `check_handoff_facts.py` remains the source of truth for HANDOFF fact semantics; this feature wraps and structures that verdict for autonomous candidate work.
- handoff-only merge means all changed paths are Markdown files or under `specs/`, matching the existing checker's rule.
- The change is risk grade 2 because it changes operating-system observability and autonomous next-work completion, but it does not touch safety boundaries or money paths.

completed_candidate_id: candidate-handoff-truth-liveness-contract
next_candidate_id: candidate-pr-merge-evidence-liveness-contract

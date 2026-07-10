# Feature Specification: PR/Merge Evidence Liveness Contract

**Feature Branch**: `Codex/108-pr-merge-evidence-liveness-contract`
**Created**: 2026-07-10
**Status**: Draft
**Input**: User description: "다음 자율 후보 `candidate-pr-merge-evidence-liveness-contract`을 목표 스킬로 꼼꼼하게 진행"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - PR 완료 증거를 계약으로 본다 (Priority: P1)

운영자는 작업 완료 보고가 PR 본문 품질 관문을 실제로 통과할 수 있는지, 손으로 PR 본문과 검사 스크립트를 다시 조합하지 않고 하나의 읽기 전용 보고서에서 확인한다.

**Why this priority**: 등급 2 이상 작업은 PR 본문에 문제 정의, 탐색 근거, 검증, 하네스 검증, 안전 경계가 남아야 한다. 지금은 검사 스크립트와 템플릿은 있지만, 자율 후보 완료 증거 관점에서 PASS/WAIT/FAIL 판정이 분리되어 있지 않다.

**Independent Test**: 완성된 PR 본문 fixture를 입력하면 보고서가 `pr_quality_gate=PASS`와 `overall_status=OBSERVATION_WAIT` 또는 `CONTRACT_READY`를 반환한다.

**Acceptance Scenarios**:

1. **Given** PR 본문이 위험 등급 2, 문제 정의 필드, 하네스 평가, HANDOFF 검증을 모두 포함함, **When** 생존성 보고서를 생성하면, **Then** PR 품질 게이트는 `PASS`다.
2. **Given** PR 본문이 없거나 아직 PR 생성 전임, **When** 보고서를 생성하면, **Then** PR 품질 게이트는 `WAIT`로 남고 실패로 오판하지 않는다.

---

### User Story 2 - 머지 뒤 증거 연결을 구분한다 (Priority: P2)

운영자는 main 머지 커밋, released-work 장부, deploy-status 관측이 같은 완료 흐름을 뒷받침하는지 확인한다.

**Why this priority**: PR은 통과했지만 released-work가 완료 후보를 아직 소비하지 않았거나 deploy 관측이 아직 없는 상태는 실패가 아니라 대기다. 반대로 malformed sidecar나 명백한 deploy 실패는 다음 세션이 바로 알 수 있어야 한다.

**Independent Test**: released-work와 deploy-status fixture를 바꿔 PASS, WAIT, FAIL 판정이 분리되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** released-work가 `candidate-pr-merge-evidence-liveness-contract`를 released로 기록함, **When** 보고서를 생성하면, **Then** released-work 게이트는 `PASS`다.
2. **Given** deploy-status 관측이 아직 제공되지 않음, **When** PR 본문과 released-work는 정상이면, **Then** 전체 판정은 `OBSERVATION_WAIT`다.
3. **Given** deploy-status 관측이 실패를 나타냄, **When** 보고서를 생성하면, **Then** 전체 판정은 `BLOCKED`다.

---

### User Story 3 - 완료 뒤 worktree 동시 작업 후보로 전진한다 (Priority: P3)

운영자는 `candidate-pr-merge-evidence-liveness-contract`가 완료 처리된 뒤 같은 후보를 다시 받지 않고, 다음 운영 체계 후보인 worktree 동시 작업 생존성 계약으로 넘어간다.

**Why this priority**: 운영 체계 frontier 지도는 HANDOFF 사실성 다음에 PR/머지 증거를 닫고, 그다음 worktree 동시 작업 방어를 닫는 순서다. 완료 마커가 없으면 autonomous-work가 다음 후보로 전진했는지 재현할 수 없다.

**Independent Test**: released-work에 이번 완료 후보를 넣으면 selected_work가 `candidate-worktree-concurrency-liveness-contract`로 바뀌는지 확인한다.

**Acceptance Scenarios**:

1. **Given** released-work가 HANDOFF 사실성과 PR/머지 증거 후보를 모두 released로 기록함, **When** autonomous-work 보고서를 생성하면, **Then** selected_work는 `candidate-worktree-concurrency-liveness-contract`다.
2. **Given** 이번 계약 보고서가 생성됨, **When** 보고서 JSON을 확인하면, **Then** `completed_candidate_id`와 `next_candidate_id`가 명시된다.

### Edge Cases

- PR 본문 파일이 없으면 `WAIT`이며, 완료 전 대기 상태로 보고한다.
- PR 본문이 있지만 등급 2 필수 하네스 검증이 빠지면 `FAIL`이다.
- released-work JSON이 없으면 `WAIT`이지만, malformed JSON이면 `FAIL`이다.
- deploy-status 관측이 없으면 `WAIT`이고, 실패 또는 rollback 관측은 `FAIL`이다.
- main 머지 커밋을 git에서 읽을 수 없으면 `WAIT`이다. 읽혔지만 Pull Request merge 형태가 아니면 `FAIL`이다.
- 이 보고서는 읽기 전용이며 PR 생성, merge, deploy, 브로커 호출, 주문, 자본 배분, 비밀값 접근을 하지 않는다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose a deterministic PR/merge evidence liveness report with `overall_status`, `completed_candidate_id`, `next_candidate_id`, evidence surfaces, quality gates, and safety invariants.
- **FR-002**: System MUST classify PR body quality evidence as PASS, WAIT, or FAIL using the repository PR quality-gate semantics.
- **FR-003**: System MUST classify latest main merge evidence as PASS, WAIT, or FAIL without creating or modifying PRs.
- **FR-004**: System MUST classify released-work evidence for `candidate-pr-merge-evidence-liveness-contract` as PASS, WAIT, or FAIL.
- **FR-005**: System MUST classify deploy-status observation text as PASS, WAIT, or FAIL, while naming container-visible and operator-only evidence boundaries.
- **FR-006**: System MUST provide a CLI probe that prints JSON or Markdown and can write `--json-out` and `--summary-out`.
- **FR-007**: System MUST include `.github/pull_request_template.md`, `scripts/check_pr_quality_gate.py`, `.github/workflows/pr-quality-gate.yml`, `.github/workflows/deploy-on-merge.yml`, `automation/released-work-last-run:released_work.json`, and `automation/autonomous-work-execution-last-run:LAST_RUN.md` as operating evidence references.
- **FR-008**: System MUST mark this work's completed candidate as `candidate-pr-merge-evidence-liveness-contract`.
- **FR-009**: System MUST mark the next autonomous candidate as `candidate-worktree-concurrency-liveness-contract`.
- **FR-010**: System MUST prove that released-work completion of this candidate advances autonomous-work to the next operating-system candidate.
- **FR-011**: System MUST NOT call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist/caps, read/write secrets, modify constitution/kernel files, run fresh external collection, or invoke paid external services.

### Key Entities *(include if feature involves data)*

- **PR/Merge Evidence Liveness Report**: The read-only contract result for PR body quality, main merge evidence, released-work consumption, deploy observation, completed candidate, next candidate, and safety boundary.
- **Evidence Surface**: A repository file, sidecar reference, git fact, or supplied observation text consumed by the report.
- **Quality Gate**: A PASS, WAIT, or FAIL decision that explains whether a required completion proof is alive, pending, or broken.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-pr-merge-evidence-liveness-contract`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Unit tests cover PR body PASS, PR body WAIT, malformed released-work FAIL, missing deploy WAIT, failed deploy BLOCKED, and all-pass CONTRACT_READY.
- **SC-002**: Probe JSON and Markdown contain completed candidate, next candidate, quality gates, evidence surfaces, deploy evidence boundary, and safety invariants.
- **SC-003**: Autonomous-work focused test proves released `candidate-pr-merge-evidence-liveness-contract` advances to `candidate-worktree-concurrency-liveness-contract`.
- **SC-004**: Local quickstart replay confirms the probe and autonomous-work transition.
- **SC-005**: Full `uv run pytest`, `uv run ruff check src tests`, `git diff --check`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.

## Assumptions

- The correct runtime surface is a read-only analytics module plus probe script, not a workflow that opens or merges PRs automatically.
- PR body quality is judged by the repository's existing PR quality-gate fields, with a local fixture or supplied PR body file as input.
- Deploy status is an observation text supplied by the operator/session after merge; the contract records whether that evidence is present and consistent, but does not query GitHub or SSH by itself.
- The change is risk grade 2 because it changes operating-system observability and autonomous next-work completion, but it does not touch safety boundaries or money paths.

completed_candidate_id: candidate-pr-merge-evidence-liveness-contract
next_candidate_id: candidate-worktree-concurrency-liveness-contract

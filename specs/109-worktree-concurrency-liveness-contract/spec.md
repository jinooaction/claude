# Feature Specification: Worktree Concurrency Liveness Contract

**Feature Branch**: `Codex/109-worktree-concurrency-liveness-contract`
**Created**: 2026-07-10
**Status**: Draft
**Input**: User description: "다음 자율 후보 `candidate-worktree-concurrency-liveness-contract`을 목표 스킬로 꼼꼼하게 진행"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 동시 작업 방어가 살아 있는지 한 번에 본다 (Priority: P1)

운영자는 `local_concurrency_guard`가 세션 시작, 커밋, 푸시 경로에서 실제로 호출되는지 손으로 여러 파일을 조합하지 않고 하나의 읽기 전용 보고서에서 확인한다.

**Why this priority**: 이 저장소는 여러 Codex 세션과 기기가 같은 repo를 다룬다. 가드가 훅에 연결되지 않았거나 훅 순서가 깨지면 WARN/BLOCK 규칙이 있어도 실제 쓰기 전에는 작동하지 않는다.

**Independent Test**: 저장소 fixture를 읽으면 보고서가 session-start hook, pre-commit hook, pre-push hook 연결을 `PASS`로 분류한다.

**Acceptance Scenarios**:

1. **Given** `.codex/hooks.json`이 session-start에서 `scripts/local_concurrency_guard.py --mode session-start`를 호출함, **When** 보고서를 생성하면, **Then** session-start 연결 게이트는 `PASS`다.
2. **Given** `.githooks/pre-commit`과 `.githooks/pre-push`가 각각 guard의 `pre-commit`, `pre-push` 모드를 호출함, **When** 보고서를 생성하면, **Then** git hook 연결 게이트는 `PASS`다.
3. **Given** 필수 훅 파일이 없거나 guard 호출 문자열이 누락됨, **When** 보고서를 생성하면, **Then** 전체 판정은 `BLOCKED`다.

---

### User Story 2 - WARN/BLOCK/isolate/복구 스냅샷 계약을 분리한다 (Priority: P2)

운영자는 동시 세션 충돌이 생겼을 때 정상적인 `WARN`, 쓰기 전 차단 `BLOCK`, 격리 안내, 복구 스냅샷 표면이 살아 있는지 확인한다.

**Why this priority**: 정상 WARN을 장애로 오판하면 작업이 멈추고, 반대로 pre-commit/pre-push BLOCK이 약해지면 같은 브랜치나 같은 파일 묶음의 병렬 수정이 섞인다. 복구 스냅샷 표면도 남아야 사용자 변경을 되돌리지 않고 재구성할 수 있다.

**Independent Test**: in-memory synthetic lease를 guard 평가 함수에 넣어 check 모드는 `WARN`, pre-commit/pre-push 모드는 `BLOCK`, 충돌 없음은 `OK`로 분리되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 같은 worktree 또는 같은 브랜치의 최근 lease가 있음, **When** check 모드 계약을 평가하면, **Then** 보고서는 `WARN`을 정상 생존 신호로 보고 게이트를 `PASS`한다.
2. **Given** 같은 worktree 또는 같은 브랜치의 최근 lease가 있음, **When** pre-commit 또는 pre-push 모드 계약을 평가하면, **Then** 보고서는 `BLOCK`을 확인하고 게이트를 `PASS`한다.
3. **Given** main 브랜치에서 커밋하거나 main으로 푸시하려는 synthetic 상태, **When** 계약을 평가하면, **Then** guard가 `BLOCK`해야 한다.
4. **Given** `write_snapshot` 코드가 복구 파일 표면을 잃음, **When** 보고서를 생성하면, **Then** 복구 스냅샷 게이트는 `FAIL`이다.

---

### User Story 3 - 완료 뒤 다음 agent-ops 후보로 전진한다 (Priority: P3)

운영자는 `candidate-worktree-concurrency-liveness-contract`가 완료 처리된 뒤 같은 후보나 닫힌 과거 후보를 다시 착수 후보처럼 받지 않고, 다음 운영 체계 후보로 넘어간다.

**Why this priority**: 재현 결과 109 후보까지 released로 닫으면 현재 루프는 실행 가능한 새 후보가 아니라 닫힌 `candidate-fd04772a23c5`를 `RELEASED`로 보여준다. 이것은 예전 "닫힌 후보가 selected_work처럼 보이는" 혼동을 되살릴 수 있다.

**Independent Test**: released-work에 agent-ops frontier 후보들을 모두 넣으면 selected_work가 새 `candidate-agent-harness-regression-liveness-contract`로 전진하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** released-work가 HANDOFF 사실성, PR/머지 증거, worktree 동시 작업 후보를 모두 released로 기록함, **When** autonomous-work 보고서를 생성하면, **Then** selected_work는 새 agent harness 회귀 생존성 후보다.
2. **Given** 이번 계약 보고서가 생성됨, **When** 보고서 JSON을 확인하면, **Then** `completed_candidate_id`와 `next_candidate_id`가 명시된다.

### Edge Cases

- `.codex/state/concurrency`는 gitignored runtime 디렉터리라 checkout에 없어도 실패가 아니다. 보고서는 스냅샷 코드 표면과 optional runtime 상태를 분리한다.
- session-start hook은 실패해도 세션을 막지 않는 fail-open 경로다. 보고서는 연결과 순서를 검증하되, 정상 WARN을 실패로 오판하지 않는다.
- pre-commit/pre-push는 같은 worktree, 같은 브랜치, dirty 파일 겹침, main 직접 커밋/푸시를 차단해야 한다.
- malformed released-work JSON은 `FAIL`이다. parseable이지만 완료 후보가 없으면 `WAIT`다.
- 이 보고서는 읽기 전용이며 worktree 생성, 파일 수정, 커밋, 푸시, 브로커 호출, 주문, 자본 배분, 비밀값 접근을 하지 않는다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose a deterministic worktree concurrency liveness report with `overall_status`, `completed_candidate_id`, `next_candidate_id`, evidence surfaces, quality gates, guard behavior summary, optional runtime state summary, and safety invariants.
- **FR-002**: System MUST verify that `.codex/hooks.json` invokes `scripts/local_concurrency_guard.py --mode session-start` before git ground truth.
- **FR-003**: System MUST verify that `.githooks/pre-commit` and `.githooks/pre-push` invoke the guard in the matching modes.
- **FR-004**: System MUST verify synthetic guard behavior for OK, WARN-on-check, BLOCK-on-pre-commit/pre-push conflicts, direct main commit block, and direct main push block.
- **FR-005**: System MUST verify that the recovery snapshot surface still includes `metadata.json`, `worktree.diff`, `index.diff`, and `untracked/`.
- **FR-006**: System MUST classify optional runtime guard output as PASS, WAIT, or FAIL without treating normal WARN as a blocker.
- **FR-007**: System MUST classify released-work evidence for `candidate-worktree-concurrency-liveness-contract` as PASS, WAIT, or FAIL.
- **FR-008**: System MUST provide a CLI probe that prints JSON or Markdown and can write `--json-out` and `--summary-out`.
- **FR-009**: System MUST include `scripts/local_concurrency_guard.py`, `.codex/hooks.json`, `.githooks/pre-commit`, `.githooks/pre-push`, `.codex/state/concurrency`, `scripts/agent_harness_probe.py`, `automation/released-work-last-run:released_work.json`, and `automation/autonomous-work-execution-last-run:LAST_RUN.md` as operating evidence references.
- **FR-010**: System MUST mark this work's completed candidate as `candidate-worktree-concurrency-liveness-contract`.
- **FR-011**: System MUST mark the next autonomous candidate as `candidate-agent-harness-regression-liveness-contract`.
- **FR-012**: System MUST prove that released-work completion of this candidate advances autonomous-work to the next operating-system candidate.
- **FR-013**: System MUST NOT call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist/caps, read/write secrets, modify constitution/kernel files, run fresh external collection, or invoke paid external services.

### Key Entities *(include if feature involves data)*

- **Worktree Concurrency Liveness Report**: The read-only contract result for hook wiring, guard synthetic behavior, recovery snapshot surface, runtime guard observation, completed candidate, next candidate, and safety boundary.
- **Evidence Surface**: A repository file, gitignored runtime path, sidecar reference, or supplied guard output consumed by the report.
- **Quality Gate**: A PASS, WAIT, or FAIL decision that explains whether a required concurrency protection is alive, pending, or broken.
- **Guard Behavior Summary**: Deterministic synthetic outcomes proving that read-only checks warn while write paths block.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-worktree-concurrency-liveness-contract`.
- **Next Candidate Marker**: The autonomous-work value `next_candidate_id: candidate-agent-harness-regression-liveness-contract`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Unit tests cover hook wiring PASS, synthetic guard behavior PASS, missing hook FAIL, malformed released-work FAIL, missing runtime guard output WAIT, and all-pass CONTRACT_READY.
- **SC-002**: Probe JSON and Markdown contain completed candidate, next candidate, guard behavior summary, evidence surfaces, quality gates, runtime state boundary, and safety invariants.
- **SC-003**: Autonomous-work focused test proves released `candidate-worktree-concurrency-liveness-contract` advances to `candidate-agent-harness-regression-liveness-contract`.
- **SC-004**: Local quickstart replay confirms the probe and autonomous-work transition.
- **SC-005**: Full `uv run pytest`, `uv run ruff check src tests`, `git diff --check`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.

## Assumptions

- The correct runtime surface is a read-only analytics module plus probe script. It observes and simulates guard behavior but does not create worktrees or mutate leases.
- `local_concurrency_guard.py` remains the source of truth for enforcement; the new report imports or executes no external service and duplicates only the minimal expected behavior checks needed for a contract.
- `candidate-agent-harness-regression-liveness-contract` is the next operating-system candidate because the harness already has evaluation, first-response quality, and redteam suites, but their own liveness contract is not yet a released frontier item.
- The change is risk grade 2 because it changes operating-system observability and autonomous next-work completion, but it does not touch safety boundaries or money paths.

completed_candidate_id: candidate-worktree-concurrency-liveness-contract
next_candidate_id: candidate-agent-harness-regression-liveness-contract

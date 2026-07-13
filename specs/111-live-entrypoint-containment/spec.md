# Feature Specification: Live Entrypoint Containment

**Feature Branch**: `Codex/111-live-entrypoint-containment`  
**Created**: 2026-07-13  
**Status**: Draft  
**Input**: User description: "지금 인사이트를 코덱스가 이어받아서 바로 완성도 높은 작업 진행할 수 있도록 만들어줘"

## Problem Statement

현재 `operator-design` 경로는 룰 설계와 검증을 넘어 라이브 워커 시작 권한까지 갖는다. 예약 실행, `auto_ok=true` 기본값, 자동 `OK` 입력, 실제로 수행되지 않는 동적 검증의 성공 처리, `start_live_worker` 호출이 연결되면 현재의 전진 검증·실거래 센티넬·자본 사다리와 독립된 평행 실거래 경로가 된다.

이 스펙은 설계 기능을 제거하지 않는다. **설계와 실거래 실행 사이의 경계를 복원해, 설계 결과가 검증 가능한 후보 산출물로만 남고 실거래 권한은 기존 증거 승격 경로로만 이동하도록 한다.**

## Operator Authorization Boundary

이 스펙은 코드, 테스트, 문서, 워크플로의 안전화 변경을 승인받았다. 다음 외부 효과는 승인 범위가 아니다.

- 실제 주문 제출
- `armed: true` 변경
- `AUTO_INVEST_MODE=live` 변경
- 자본 증액이나 자본 사다리 승격
- 허용 종목·포지션 한도·손실 예산 확대
- 운영 서버의 `.env` 변경

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 설계 작업이 라이브 실행을 시작하지 않는다 (Priority: P1)

운영자는 수동 또는 자동으로 룰 설계를 실행해도 그 작업이 라이브 워커, 실제 주문, 실거래 설정 변경으로 이어지지 않는다고 확신할 수 있어야 한다.

**Why this priority**: 현재 경로는 정적 검증만 통과한 생성 룰이 평행 실거래 워커로 이어질 수 있다. 실제 돈에 닿는 직접 위험이므로 가장 먼저 닫아야 한다.

**Independent Test**: `operator-design` 워크플로, 셸 도우미, `design` 명령을 테스트 더블로 실행해도 `start_live_worker`, `auto-invest run`, 브로커 주문 함수가 호출되지 않는다.

**Acceptance Scenarios**:

1. **Given** 운영자가 GitHub Actions에서 설계를 수동 실행함, **When** 설계와 정적 검증이 끝나면, **Then** 후보 룰과 검증 보고서만 생성되고 라이브 워커는 시작되지 않는다.
2. **Given** 아무 운영자 입력이 없음, **When** 시간이 경과해도, **Then** `operator-design` 예약 실행은 발생하지 않는다.
3. **Given** 과거의 `auto_ok=true` 입력 또는 `AUTO_OK=1` 환경변수가 남아 있음, **When** 설계 경로를 실행하면, **Then** 해당 값은 라이브 시작 권한으로 해석되지 않는다.
4. **Given** 설계 결과가 검증을 통과함, **When** 명령이 종료하면, **Then** 다음 행동은 증거 승격 경로에 후보를 제출하는 것이며 직접 실거래가 아니다.

---

### User Story 2 - 동적 검증 결과가 사실대로 표시된다 (Priority: P1)

운영자는 백테스트와 모의 운용이 실제로 수행된 경우와 미구현·미가용·실패한 경우를 구분한다.

**Why this priority**: 현재 `VerifyResult.ok=True`는 동적 검증이 실제로 수행됐음을 보장하지 않는다. 검증되지 않은 후보가 검증된 것처럼 보이면 이후 게이트가 의미를 잃는다.

**Independent Test**: 백테스트 또는 모의 운용 실행기가 없거나 예외를 내거나 결과 증거를 반환하지 않으면 `ok=False`이며, 두 실행기의 성공 증거가 모두 있을 때만 `ok=True`다.

**Acceptance Scenarios**:

1. **Given** 백테스트 실행기가 없음, **When** 검증하면, **Then** 결과는 `blocked`이고 `ok=False`다.
2. **Given** 모의 운용 실행이 아직 구현되지 않음, **When** 검증하면, **Then** 결과는 `blocked`이고 `ok=False`다.
3. **Given** 백테스트와 모의 운용 중 하나가 실패함, **When** 검증하면, **Then** 실패 원인이 구조화돼 남고 승격 가능 상태가 아니다.
4. **Given** 정적 검증, 백테스트, 모의 운용이 모두 실제로 성공함, **When** 검증하면, **Then** `ok=True`와 각 증거 식별자가 함께 반환된다.
5. **Given** 실행기 모듈 가져오기는 성공했지만 함수 호출은 하지 않음, **When** 검증하면, **Then** 성공으로 오인하지 않는다.

---

### User Story 3 - 자연어 입력이 원격 셸 명령으로 해석되지 않는다 (Priority: P1)

운영자는 따옴표, 줄바꿈, 셸 특수문자가 포함된 자연어 의도를 안전하게 전달할 수 있다.

**Why this priority**: 현재 워크플로는 입력을 원격 명령 문자열에 삽입한다. 실행 권한이 있는 운영자 입력이라도 셸 문법과 데이터가 섞이면 오작동과 명령 삽입 가능성이 생긴다.

**Independent Test**: 작은따옴표, 큰따옴표, 역따옴표, `$()`, 세미콜론, 줄바꿈이 포함된 입력이 원문 그대로 설계 도우미에 전달되고 추가 명령은 실행되지 않는다.

**Acceptance Scenarios**:

1. **Given** 의도에 작은따옴표가 있음, **When** 워크플로가 원격 도우미를 호출하면, **Then** 셸 구문 오류 없이 같은 문자열이 전달된다.
2. **Given** 의도에 `$(...)` 또는 세미콜론이 있음, **When** 전달하면, **Then** 데이터로만 처리되고 명령으로 평가되지 않는다.
3. **Given** 여러 줄 의도임, **When** 전달하면, **Then** 줄바꿈이 보존된다.

---

### User Story 4 - 설계 기능은 후보 생성 도구로 계속 쓸 수 있다 (Priority: P2)

운영자는 라이브 실행 권한을 제거한 뒤에도 자연어 의도에서 후보 룰을 만들고 정적 검증 결과를 볼 수 있다.

**Why this priority**: 안전화가 유용한 설계 기능 전체를 제거하면 우회 경로가 다시 만들어질 가능성이 높다. 제안과 실행을 분리해야 한다.

**Independent Test**: 브로커 쓰기 없이 후보 TOML, 정적 검증 결과, 동적 검증 대기 또는 실패 이유를 출력·저장할 수 있다.

**Acceptance Scenarios**:

1. **Given** 유효한 자연어 의도와 모의 계좌 입력이 있음, **When** 설계를 실행하면, **Then** 후보 TOML을 생성하고 저장할 수 있다.
2. **Given** 동적 검증을 아직 통과하지 못함, **When** 명령이 종료하면, **Then** 후보는 `PROPOSAL_ONLY`로 명확히 표시된다.
3. **Given** 후보가 생성됨, **When** 후속 시스템이 읽으면, **Then** 직접 실거래가 아니라 기존 후보·검증·승격 경로로 넘길 수 있는 증거 메타데이터가 있다.

### Edge Cases

- 기존 자동 생성 룰 파일이 이미 존재해도 이번 변경이 자동으로 삭제하거나 라이브 실행하지 않는다.
- 운영 서버에 과거 `design` 프로세스가 남아 있는지는 저장소 변경만으로 판단하지 않는다.
- `AUTO_OK`, `auto_ok`, 예약 실행 설정이 다른 문서나 테스트 fixture에 남아 있으면 용도와 위험을 분류해 제거하거나 역사 기록으로 격리한다.
- 백테스트 실행기가 존재하지만 데이터가 부족하면 성공이 아니라 검증 실패 또는 관찰 대기다.
- 모의 운용 실행 결과가 오래됐거나 후보 지문과 다르면 성공으로 인정하지 않는다.
- 설계 명령의 LLM 호출 비용은 기존 비용 한도를 유지하며, 예약 실행 제거로 불필요한 자동 비용을 늘리지 않는다.
- 이 스펙은 주문 `POST` 재시도, 체결 원장, 계좌 노출 예약을 함께 수정하지 않는다.
- 주요 실거래 센티넬과 배포 포트폴리오 파일은 수정하지 않는다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `.github/workflows/operator-design.yml` MUST NOT contain a scheduled trigger that can invoke rule design or live activation without an explicit operator action.
- **FR-002**: The operator-design workflow MUST NOT default `auto_ok` or any equivalent live-activation input to true.
- **FR-003**: The workflow and shell helper MUST NOT translate `auto_ok`, `AUTO_OK`, workflow dispatch, or schedule execution into an automatic `OK` response.
- **FR-004**: `scripts/operator_design.sh` MUST NOT pipe or inject `OK` into `auto-invest design`.
- **FR-005**: The `auto-invest design` command MUST NOT call `start_live_worker`, `auto-invest run`, `rebalance-once --mode live`, or broker order submission.
- **FR-006**: The design path MUST remain capable of producing a candidate rules file and a structured verification result without live activation.
- **FR-007**: `VerifyResult.ok=True` MUST mean static validation, an actually executed backtest, and an actually executed paper or simulation validation all succeeded for the same candidate fingerprint.
- **FR-008**: Missing, stubbed, skipped, unavailable, stale, fingerprint-mismatched, or failed dynamic validation MUST produce `ok=False`.
- **FR-009**: Verification results MUST expose per-stage status, reason, candidate fingerprint, and evidence reference or run identifier.
- **FR-010**: The workflow MUST transport operator intent as data through stdin, a temporary file, encoded payload, or another non-evaluating mechanism; direct interpolation into a remote shell command is forbidden.
- **FR-011**: The command safety registry MUST classify `design` as `AutonomyLevel.PROPOSAL` with `can_place_order=False`, `can_change_live_config=False`, `can_scale_capital=False`, `can_reassign_strategy=False`, and `uses_broker` limited to read-only account context if still required.
- **FR-012**: Tests MUST fail if any production design path regains a direct reference to live-worker startup or broker order submission.
- **FR-013**: Tests MUST cover shell-special-character intent transport without executing the supplied text.
- **FR-014**: The change MUST preserve secret redaction and MUST NOT print KIS, Anthropic, Telegram, SSH, or account secret values.
- **FR-015**: The change MUST NOT modify `automation/rebalance-live.request`, `automation/rebalance-micro-gtaa.request`, `automation/go-live-canary.request`, `.env`, live portfolio configs, position caps, whitelist, loss budget, constitution, or kernel manifest.
- **FR-016**: Existing generated rule files MUST be treated as inert candidates unless a separate validated promotion path selects them.
- **FR-017**: The CLI and workflow output MUST state that design completion does not mean live activation.
- **FR-018**: Documentation MUST identify the supported successor path from design candidate to backtest, paper/forward validation, canary, and full live.
- **FR-019**: The implementation MUST be backward-safe: removing live activation authority may reduce automation, but it MUST NOT create a new order path or widen an existing limit.
- **FR-020**: No test in this feature may contact KIS, Anthropic, SSH, or any paid external service; all external behavior MUST be mocked or fixture-driven.

### Key Entities *(include if feature involves data)*

- **Design Candidate**: A generated rules configuration plus fingerprint, original intent digest, static-validation result, dynamic-validation state, creation timestamp, and source version. It has no live authority.
- **Verification Stage Result**: One of static validation, backtest, or paper/simulation validation, with status `PASS`, `WAIT`, or `FAIL`, reason, and evidence reference.
- **Design Verification Result**: Aggregate fail-closed result. `ok=True` only when all required stage results are `PASS` for the same candidate fingerprint.
- **Candidate Fingerprint**: Deterministic digest binding generated rules and all validation evidence to the same candidate.
- **Live Activation Authority**: Explicitly out of scope for this feature. Design output cannot create it.
- **Intent Payload**: Operator-provided natural language transmitted as opaque data, never shell-evaluated.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Repository search finds no scheduled `operator-design` trigger and no automatic `OK` injection in its workflow or shell helper.
- **SC-002**: Unit and integration tests prove `design` never invokes `start_live_worker`, `auto-invest run`, or broker order submission.
- **SC-003**: Verification tests cover missing backtest, missing paper validation, stubbed execution, exception, stale evidence, fingerprint mismatch, one-stage failure, and all-stage success.
- **SC-004**: `VerifyResult.ok=True` is impossible without evidence from all three required stages.
- **SC-005**: Intent transport tests preserve quotes, shell metacharacters, Unicode, and newlines without command execution.
- **SC-006**: `command_policy("design")` reports proposal-only authority and no order/live-config capability.
- **SC-007**: Candidate generation remains usable in a no-network test and clearly reports `PROPOSAL_ONLY` until dynamic verification succeeds.
- **SC-008**: The diff contains no changes to live sentinels, caps, whitelist, loss budget, constitution, kernel manifest, or actual account configuration.
- **SC-009**: Focused tests, full `uv run pytest`, `uv run ruff check src tests`, `git diff --check`, HANDOFF fact check, strict agent harness, and PR quality gate pass before merge.
- **SC-010**: The final handoff names the removed call paths, retained design capability, unexecuted live checks, and next execution-safety spec.

## Assumptions

- The current supported strategic direction is proposal → deterministic validation → paper/forward evidence → canary → full live, not proposal → direct worker start.
- Removing scheduled design and direct live startup is a safe contraction of authority.
- The existing `design` implementation may need a compatibility output for callers that expect a generated file, but no compatibility promise exists for automatic live startup.
- This implementation is risk grade 4 because it changes a money-path capability, even though it only removes authority and does not execute live actions.
- The operator's current instruction authorizes implementation and merge of this safety contraction, but not actual live activation or orders.

## Non-Goals

- Fixing broker order retry semantics
- Adding `SUBMISSION_UNKNOWN`
- Making fill ingestion transactional
- Adding account-wide exposure reservations
- Implementing the final single execution authority
- Arming any live strategy
- Proving current server or KIS account state

## Follow-on

- `112-order-submission-uncertainty-recovery`
- `113-atomic-fill-ledger`
- `114-account-exposure-reservation`
- `115-degraded-execution-state`
- `116-single-execution-authority`

# Feature Specification: Candidate Result Executor

**Feature Branch**: `Codex/candidate-result-executor`  
**Created**: 2026-06-30  
**Status**: Draft  
**Input**: User description: "정리한 다음 작업 목표 스킬로 꼼꼼하게 정리해서 진행해줘"

## User Scenarios & Testing

### User Story 1 - ready 패키지를 결과 증거로 변환 (Priority: P1)

자율 후보 구현 공장이 만든 `ready` 패키지를 사람이 다시 실행하지 않아도, 시스템이 안전하게 실행 가능한 검증만 수행하고 후보별 결과 증거를 만든다.

**Why this priority**: 스펙 070은 후보를 실행 패키지로 바꿨지만, 그 패키지를 실제 기계 판독 증거로 바꾸는 루프가 없어 `evidence_passed=0`에서 멈춘다. 이 간극을 닫아야 자율 성장 루프가 후보 목록 생산에서 검증 결과 생산으로 이동한다.

**Independent Test**: fixture `candidate_packages.json`을 넣으면 모든 지원 패키지가 후보별 result row를 얻고, 실행 불가 또는 미지원 패키지는 빠지지 않고 `pending` 또는 `blocked` 사유를 갖는다.

**Acceptance Scenarios**:

1. **Given** candidate factory sidecar에 `ready` 패키지가 있음, **When** result executor가 실행됨, **Then** 각 패키지마다 후보 ID, 패키지 ID, 실행 상태, 증거 상태, source ref가 들어간 result row가 생성된다.
2. **Given** 전략 또는 포트폴리오 패키지가 있음, **When** 안전한 백테스트 실행이 성공함, **Then** `historical_backtest`, `recent_oos`, `walk_forward` 상태가 실제 출력 기준으로 `pass`, `fail`, `pending` 중 하나로 기록된다.
3. **Given** 운영·데이터 패키지가 있음, **When** no-live 검증 명령이 성공함, **Then** `factory_validation`이 `pass` 또는 `pending`으로 기록되고 전략 증거를 허위로 채우지 않는다.

---

### User Story 2 - 안전한 실행만 허용하고 실패를 증거화 (Priority: P2)

결과 실행기는 후보 패키지의 문자열 명령을 무제한 셸로 실행하지 않고, 허용된 패키지 종류와 no-live 검증 명령만 실행한다. 실패, 시간 초과, 누락 입력은 조용히 숨기지 않고 candidate result evidence에 남긴다.

**Why this priority**: 자동 실행기는 강력한 자동화 표면이다. 명령 문자열을 그대로 실행하면 주문·비밀값·외부 비용·live 설정 변경으로 이어질 수 있으므로, 실행 가능 범위와 실패 기록이 안전 경계다.

**Independent Test**: 위험 명령, live 모드, broker/SSH 관련 문자열, 알 수 없는 패키지 종류를 넣으면 실행하지 않고 `blocked` 결과와 한국어 사유를 남긴다.

**Acceptance Scenarios**:

1. **Given** 패키지 명령에 `--mode live`, `ssh`, `KIS_`, sentinel 변경, whitelist/caps 변경이 포함됨, **When** result executor가 실행됨, **Then** 해당 패키지는 실행되지 않고 `blocked`로 기록된다.
2. **Given** 허용된 명령이 시간 초과 또는 비정상 종료함, **When** result executor가 실행됨, **Then** 원인, 종료 코드, 제한된 출력 요약이 result evidence에 기록되고 전체 run은 `degraded`가 된다.
3. **Given** 입력 sidecar가 없거나 JSON이 깨짐, **When** result executor가 실행됨, **Then** 빈 결과와 누락 입력을 발행해 다음 루프가 실패 원인을 볼 수 있다.

---

### User Story 3 - factory와 promotion 루프가 자동 소비 (Priority: P3)

결과 실행기는 `automation/candidate-implementation-results` sidecar를 발행하고, candidate factory는 다음 실행 때 이 결과를 읽어 enriched backlog를 보강한다. promotion loop는 보강된 결과만 보고 다음 검증 단계로 이동한다.

**Why this priority**: 결과가 로컬 파일로만 남으면 영구 자율 루프가 아니다. sidecar branch와 workflow 순서가 있어야 다음날 factory와 promotion이 같은 증거를 자동으로 소비한다.

**Independent Test**: result executor workflow가 factory 이후, promotion scan 이전 또는 factory 재실행 이전에 sidecar를 발행하고, candidate factory workflow가 그 sidecar를 수집하는 경로가 테스트로 확인된다.

**Acceptance Scenarios**:

1. **Given** result executor sidecar가 있음, **When** candidate factory가 다음 실행됨, **Then** `candidate_results.json`을 수집해 `promotion_evidence`를 보강한다.
2. **Given** result executor sidecar가 없음, **When** candidate factory가 실행됨, **Then** 기존처럼 빈 result evidence를 사용하고 `pass`를 만들지 않는다.
3. **Given** result executor workflow가 정상 실행됨, **When** pipeline liveness가 확인함, **Then** `candidate-result-executor`가 비핵심 감시 대상으로 표시된다.

### Edge Cases

- 패키지 목록이 비어 있으면 빈 result sidecar를 성공 상태로 발행한다.
- 같은 candidate ID에 여러 패키지가 있으면 패키지 ID별로 결과를 보존하고 candidate-level 요약은 가장 보수적인 상태를 사용한다.
- 전략 백테스트 출력이 충분한 통계 판단을 제공하지 않으면 `pass`가 아니라 `pending`으로 둔다.
- 비전략 패키지는 `historical_backtest`, `recent_oos`, `walk_forward`를 만들지 않는다.
- 결과 실행기는 주문, 자본 사다리, live 전략 설정, whitelist, caps, sentinels, 비밀값, 브로커 API를 변경하지 않는다.

## Requirements

### Functional Requirements

- **FR-001**: System MUST read candidate package plans from the candidate factory sidecar without requiring broker secrets.
- **FR-002**: System MUST create one result row for every input package and never silently drop a package.
- **FR-003**: System MUST execute only package kinds and command surfaces explicitly allowlisted for no-live validation, such as backtest, paper, probe, or approved public-data validation.
- **FR-004**: System MUST block packages that reference live order mode, SSH, broker secrets, sentinels, whitelist/caps changes, capital changes, or unsupported commands.
- **FR-005**: System MUST normalize each result to machine-readable `pass`, `fail`, `pending`, or `blocked` states.
- **FR-006**: System MUST mark strategy evidence as `pass` only when the underlying validation output meets explicit success rules.
- **FR-007**: System MUST keep non-strategy package validation under `factory_validation` and must not synthesize strategy evidence for it.
- **FR-008**: System MUST publish `LAST_RUN.md`, `candidate_results.json`, and a full run JSON sidecar to `automation/candidate-implementation-results`.
- **FR-009**: System MUST provide a local probe script and an `auto-invest` CLI command that reproduce the workflow decision.
- **FR-010**: System MUST register the command in the safety command registry with no order placement, no live config change, no capital scaling, no broker use, and no DB writes except local operator-specified scratch outputs.
- **FR-011**: System MUST add the result sidecar to pipeline liveness as non-critical.
- **FR-012**: System MUST not weaken constitution principles I-VII, VIII.A, IX, X, or the `Backtest -> Canary -> Full` sequence.

### Key Entities

- **Candidate Package Input**: A package emitted by the candidate implementation factory, including package ID, candidate ID, package kind, commands, produced evidence, and safety note.
- **Candidate Result Row**: Candidate-level evidence produced by one package execution, including status, result fields, source ref, output summary, block reason, and safety note.
- **Executor Run**: One deterministic run over a package list, including counts, missing inputs, blocked packages, and artifacts.
- **Result Sidecar**: The automation branch containing the latest markdown summary and JSON results consumed by the next candidate factory run.

## Success Criteria

### Measurable Outcomes

- **SC-001**: The current nine candidate packages all produce result rows in tests.
- **SC-002**: Unsafe package commands are blocked in tests and never executed.
- **SC-003**: Missing or inconclusive strategy validation never creates a false `pass`.
- **SC-004**: A fixture with passing strategy validation flows through candidate factory into `FORWARD_REGISTRATION_READY`.
- **SC-005**: Workflow regression tests prove the result executor publishes `automation/candidate-implementation-results` and does not reference SSH, KIS secrets, live order mode, sentinels, whitelist, or caps.
- **SC-006**: Full `uv run pytest` and `uv run ruff check src tests` pass before merge.

## Assumptions

- The executor may run lightweight backtest/probe commands, but it must not trade or change live configuration.
- Heavy market-data gaps are represented as `pending`, not as `pass`.
- Strategy pass thresholds use existing CLI/probe output where available; if output is insufficient, the system remains conservative.
- The first version can execute the current known package kinds and block unknown future kinds until explicitly supported.

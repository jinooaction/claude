# Feature Specification: Candidate Pending Next Actions

**Feature Branch**: `Codex/candidate-pending-next-actions`  
**Created**: 2026-07-01  
**Status**: Draft  
**Input**: User description: "다음 작업도 이어서 꼼꼼하게 목표 스킬로 수행할 수 있어?"

## User Scenarios & Testing

### User Story 1 - 자동 실행 가능한 pending 원인을 줄인다 (Priority: P1)

운영자는 후보 결과 실행기의 `pending=5`를 볼 때, 자동화가 스스로 해결할 수 있는 명령 계약 오류와 입력 sidecar 누락을 다음 실행에서 실제로 줄이기를 원한다. 틀린 CLI 옵션, 필수 sidecar 미준비, 존재하지 않는 기본 DB 의존은 후보가 아니라 자동화 배선의 문제이므로, 같은 오류를 반복하지 않아야 한다.

**Why this priority**: spec 072는 원인을 진단했지만 `command_contract_error=2`와 `execution_failed=1`은 여전히 재실행 때 같은 실패를 낸다. 자율 루프가 되려면 진단 다음 단계가 실제 보정으로 이어져야 한다.

**Independent Test**: 현재 후보 패키지를 새 후보 공장 명령과 result executor support input으로 재처리하면 `command_contract_error`와 기본 `data/auto_invest.db` 누락 오류가 사라진다.

**Acceptance Scenarios**:

1. **Given** ops liveness 후보가 생성됨, **When** candidate factory가 명령을 만든다, **Then** `pipeline_liveness_probe.py`는 `--sidecar-dir`와 `--strict --json`을 포함한다.
2. **Given** analytics validation 후보가 생성됨, **When** candidate factory가 명령을 만든다, **Then** `macro-regime`은 현재 CLI 계약인 `--data-dir`와 `--json`을 사용한다.
3. **Given** data quality 후보가 생성됨, **When** result executor가 no-live 검증을 실행한다, **Then** 존재하지 않는 기본 `data/auto_invest.db`에 의존하지 않고 sidecar freshness 검증으로 판정한다.

---

### User Story 2 - result executor가 필요한 support input을 준비한다 (Priority: P2)

후보 결과 실행기는 후보 패키지 JSON만 가져오는 데서 멈추지 않고, 후보 명령이 필요로 하는 read-only sidecar 입력도 결정적 경로에 준비한다. 명령이 스스로 필요한 입력을 찾지 못해 실패하는 상황을 줄인다.

**Why this priority**: `pipeline_liveness_probe.py`는 sidecar 디렉터리를 요구하고, `macro-regime`은 public data snapshot이 있어야 안정적으로 실행된다. 워크플로가 이 입력을 준비하지 않으면 올바른 명령도 자동 실행에서 실패한다.

**Independent Test**: workflow와 로컬 스모크가 `/tmp/candidate_result_sidecars`와 `/tmp/candidate_result_public_data`를 준비한 뒤 result executor를 실행한다.

**Acceptance Scenarios**:

1. **Given** automation sidecar 브랜치가 존재함, **When** candidate result executor workflow가 시작됨, **Then** pipeline liveness manifest에 정의된 `LAST_RUN.md` 파일들이 `/tmp/candidate_result_sidecars`에 복사된다.
2. **Given** `automation/public-data` 브랜치가 존재함, **When** workflow가 시작됨, **Then** public data files가 `/tmp/candidate_result_public_data`에 복사된다.
3. **Given** support input 일부가 없음, **When** workflow가 실행됨, **Then** 브로커나 실거래 경로를 건드리지 않고 후보 결과를 pending으로 남긴다.

---

### User Story 3 - 가격 이력 pending은 정직하게 남긴다 (Priority: P3)

전략/포트폴리오 백테스트 후보는 필요한 가격 이력이 없으면 pass로 위조하지 않는다. 자동화는 해결 가능한 배선 오류를 줄이되, 안전한 가격 이력 수집 경로가 없는 상태에서는 별도 다음 작업으로 남긴다.

**Why this priority**: 최근 pending 5개 중 2개는 `portfolio-walk-forward`가 과거 가격 데이터 없음을 보고한 것이다. 이것은 CLI 명령 한 줄 보정으로 해결할 수 없고, 데이터 출처와 수집 경로를 안전하게 설계해야 한다.

**Independent Test**: 가격 이력이 없는 환경에서 전략/포트폴리오 후보는 계속 `data_history_missing` 진단을 갖고 `pending`으로 남는다.

**Acceptance Scenarios**:

1. **Given** `portfolio-walk-forward`가 "no ingested datasets"를 출력함, **When** result executor가 결과를 만든다, **Then** 전략 후보는 `pending`과 `data_history_missing`을 유지한다.
2. **Given** 비전략 support input 보정은 성공함, **When** 전체 후보를 재처리함, **Then** 비전략 자동화 오류만 pass로 줄고 가격 이력 부족 후보는 분리된 다음 작업으로 남는다.
3. **Given** 운영자가 결과를 봄, **When** `LAST_RUN.md`와 JSON을 확인함, **Then** 해결된 자동화 오류와 남은 데이터 이력 작업을 구분할 수 있다.

### Edge Cases

- sidecar 브랜치가 아직 발행되지 않았으면 워크플로는 실패하지 않고 degraded 결과를 발행한다.
- public data snapshot이 없으면 analytics validation은 pending으로 남기되 명령 계약 오류로 오분류하지 않는다.
- data quality 후보는 broker, KIS, 계좌, 주문, live 설정, whitelist, caps, sentinel을 절대 호출하지 않는다.
- strategy/portfolio 후보의 `pass` 기준은 완화하지 않는다.
- support input 복사는 원격 sidecar를 읽기만 하며 sidecar 원본 브랜치를 수정하지 않는다.

## Requirements

### Functional Requirements

- **FR-001**: Candidate factory MUST emit a valid `pipeline_liveness_probe.py` command for `ops_liveness` candidates, including deterministic `--sidecar-dir`, `--strict`, and `--json`.
- **FR-002**: Candidate factory MUST emit a valid `macro-regime` command for analytics validation candidates, using `--data-dir` and `--json` instead of removed or unsupported options.
- **FR-003**: Candidate factory MUST emit a no-live data quality command that does not require the default local `data/auto_invest.db`.
- **FR-004**: Candidate result executor MUST allow the updated data quality command only within existing safe no-live command surfaces.
- **FR-005**: Candidate result executor workflow MUST collect pipeline liveness sidecars into `/tmp/candidate_result_sidecars` before executing candidate packages.
- **FR-006**: Candidate result executor workflow MUST collect public data sidecar files into `/tmp/candidate_result_public_data` before executing candidate packages.
- **FR-007**: System MUST continue to classify missing historical price datasets as `data_history_missing` and keep strategy/portfolio candidates pending until true backtest evidence exists.
- **FR-008**: System MUST preserve existing no-live safety boundaries: no broker API calls, no orders, no capital changes, no whitelist/caps edits, no live strategy changes, no sentinels, no secret writes.
- **FR-009**: Tests MUST prove command generation, allowed-prefix execution, support-input workflow text, and missing-history semantics.

### Key Entities

- **Candidate Support Inputs**: Read-only files staged under deterministic `/tmp` paths for candidate commands.
- **Pipeline Liveness Sidecars**: Automation `LAST_RUN.md` files collected from existing sidecar branches via `pipeline_liveness_probe.py --manifest`.
- **Public Data Snapshot**: Read-only macro/public data files copied from `automation/public-data`.
- **Pending Next Action Closure**: The reduction of retryable pending causes that are caused by automation wiring rather than by missing market history.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Current candidate package generation emits no known-invalid `--format json`, missing `--sidecar-dir`, or default `data/auto_invest.db` data quality command.
- **SC-002**: Local current-sidecar smoke reduces `command_contract_error` from 2 to 0 and `execution_failed` from 1 to 0.
- **SC-003**: Local current-sidecar smoke increases non-strategy pass count by at least 3 while strategy/portfolio data history candidates remain pending.
- **SC-004**: Missing price history remains visible as `data_history_missing` and is not converted into pass evidence.
- **SC-005**: Full tests, lint, handoff fact check, strict agent harness, PR quality gate, and merge/deploy reporting complete before done.

## Assumptions

- `automation/public-data` and pipeline liveness sidecar branches are the current safe read-only support sources.
- This feature is risk grade 2 because it changes operating automation and candidate execution inputs. It does not change the safety perimeter or money path.
- Solving historical price ingestion requires a separate feature because source quality, storage, and replay semantics affect strategy evidence.

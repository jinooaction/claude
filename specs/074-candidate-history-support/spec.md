# Feature Specification: Candidate History Support

**Feature Branch**: `Codex/074-candidate-history-support`  
**Created**: 2026-07-01  
**Status**: Draft  
**Input**: User description: "다음 작업도 이어서 꼼꼼하게 목표 스킬로 수행할 수 있어?"

## User Scenarios & Testing

### User Story 1 - 후보 백테스트가 가격 이력을 자동으로 쓴다 (Priority: P1)

운영자는 후보 결과 실행기에서 전략/포트폴리오 후보가 `no ingested datasets`로 멈추지 않고, 이미 서버에 쌓인 읽기 전용 가격 이력을 자동으로 준비해 백테스트 판단까지 가기를 원한다.

**Why this priority**: 스펙 073 이후 남은 pending 2개의 공통 원인은 후보 품질이 아니라 가격 이력 입력 부재다. 자율 루프가 스스로 판단하려면 데이터 준비 실패와 전략 실패를 분리해야 한다.

**Independent Test**: 후보 공장이 만든 전략/포트폴리오 검증 명령이 deterministic history root를 포함하고, 해당 history root가 준비된 환경에서는 `portfolio-walk-forward`가 `no ingested datasets`로 멈추지 않는다.

**Acceptance Scenarios**:

1. **Given** strategy backtest 후보가 생성됨, **When** candidate factory가 명령을 만든다, **Then** micro GTAA portfolio walk-forward 명령은 `/tmp/candidate_result_history/micro-gtaa/hist`를 `--history-root`로 사용한다.
2. **Given** portfolio backtest 후보가 생성됨, **When** candidate factory가 명령을 만든다, **Then** global-trend-wide와 multi-asset 명령은 각각 전용 history root를 사용한다.
3. **Given** history root가 준비됨, **When** result executor가 후보 패키지를 실행한다, **Then** 가격 이력 부재 진단 없이 실제 walk-forward 출력으로 pass/fail/pending을 판정한다.

---

### User Story 2 - 워크플로가 읽기 전용 가격 이력을 준비한다 (Priority: P2)

후보 결과 실행기는 후보 패키지를 실행하기 전에 서버의 기존 가격 DB를 읽기 전용으로 내보내고, `ingest-history` 데이터셋으로 변환해 GitHub Actions 러너의 `/tmp`에 배치한다.

**Why this priority**: 후보 명령 안에 SSH나 서버 접근을 넣으면 안전 실행기 경계가 흐려진다. 지원 입력 준비 단계가 가격 이력을 책임지고, 후보 명령은 로컬 파일만 읽어야 한다.

**Independent Test**: workflow text와 회귀 테스트가 `candidate_history_support_probe.py --manifest`, `bars-export`, `ingest-history`, 전용 `/tmp/candidate_result_history` 경로를 포함하고, 주문·실거래·KIS 비밀값 표면을 포함하지 않음을 증명한다.

**Acceptance Scenarios**:

1. **Given** SSH 비밀값이 있음, **When** candidate result executor workflow가 시작됨, **Then** 서버에서 `bars-export -> ingest-history`를 실행하고 결과를 `/tmp/candidate_result_history`로 가져온다.
2. **Given** SSH 비밀값이 없거나 일부 DB에 이력이 부족함, **When** workflow가 실행됨, **Then** workflow 전체는 실패하지 않고 해당 후보는 기존처럼 pending 진단을 남긴다.
3. **Given** 후보 패키지가 실행됨, **When** result executor가 command allowlist를 검사함, **Then** 후보 명령에는 SSH, KIS, live, 주문, 자본, whitelist/caps, sentinel 표면이 없다.

---

### User Story 3 - 가격 이력 지원 표면이 재현 가능하다 (Priority: P3)

다음 세션이나 로컬 smoke는 어떤 portfolio가 어떤 서버 DB와 어떤 history root에 연결되는지 한 명령으로 볼 수 있어야 한다.

**Why this priority**: history root 경로가 workflow YAML과 candidate factory에 흩어지면 다시 불일치가 생긴다. 단일 manifest가 있어야 후보 명령, workflow, 테스트가 같은 지도를 공유한다.

**Independent Test**: `candidate_history_support_probe.py --manifest`가 세 데이터셋을 안정적인 순서와 탭 구분 형식으로 출력한다.

**Acceptance Scenarios**:

1. **Given** local worktree, **When** manifest probe를 실행함, **Then** micro GTAA, global-trend-wide, multi-asset mapping이 출력된다.
2. **Given** candidate factory가 portfolio path를 받음, **When** history root를 찾음, **Then** manifest와 같은 경로를 사용한다.
3. **Given** 새로운 portfolio가 추가됨, **When** manifest에 없는 path를 factory가 쓰려 함, **Then** 테스트가 누락을 잡는다.

### Edge Cases

- 서버 SSH 비밀값이 없으면 history support 단계는 실패 대신 "준비 불가"를 출력하고 후보 판정은 pending으로 남는다.
- 서버 DB 파일이 없거나 특정 종목 bars가 없으면 해당 dataset만 누락되고 다른 dataset 준비는 계속된다.
- `bars-export` 또는 `ingest-history` 실패는 pass로 바뀌지 않고 result executor의 기존 진단으로 남는다.
- 가격 이력 준비는 `/tmp`만 쓰며 repository source, sidecar branch, server forward DB를 수정하지 않는다.
- 후보 명령에는 SSH, KIS, live, 주문, 자본, whitelist/caps, sentinel 문자열이 들어가지 않는다.

## Requirements

### Functional Requirements

- **FR-001**: System MUST define a single candidate history support manifest mapping portfolio path, source DB path, and local history root for all current strategy/portfolio candidate commands.
- **FR-002**: Candidate factory MUST add the correct `--history-root` to every generated `portfolio-walk-forward` command for strategy and portfolio backtest packages.
- **FR-003**: Candidate result executor workflow MUST prepare candidate history datasets before executing candidate packages when server SSH support is available.
- **FR-004**: Workflow history preparation MUST use only read-only `bars-export` followed by `ingest-history`; it MUST NOT use broker backfill, live rebalance, order, capital, whitelist/caps, or sentinel commands.
- **FR-005**: Missing SSH secrets, missing DB files, or missing bars MUST NOT fail the whole workflow; they MUST leave strategy/portfolio candidates pending with existing diagnostics.
- **FR-006**: Candidate package commands MUST remain within the existing no-live allowlist and MUST NOT contain SSH or server secret surfaces.
- **FR-007**: A local manifest probe MUST expose the support mapping in machine-readable JSON and shell-friendly TSV formats.
- **FR-008**: Tests MUST cover manifest determinism, factory command generation, workflow support-input staging, candidate command safety, and missing-history fallback.
- **FR-009**: Full verification MUST include focused tests, full pytest, ruff, PR quality gate, HANDOFF fact check, strict agent harness, merge/deploy reporting, and handoff refresh.

### Key Entities

- **Candidate History Dataset**: One deterministic mapping from portfolio TOML to server price DB and local history root.
- **History Support Manifest**: The ordered list consumed by workflow staging and tests.
- **History Root**: Local `/tmp` directory containing ingested dataset versions for `portfolio-walk-forward`.
- **Candidate Backtest Command**: Allowlisted no-live command that reads a portfolio TOML, audit DB path, halt path, and history root.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Current strategy/portfolio candidate commands all include deterministic `--history-root` arguments.
- **SC-002**: The result executor workflow contains one support-input stage that prepares all three current candidate history datasets with `bars-export -> ingest-history`.
- **SC-003**: Candidate command safety tests confirm SSH and server secret surfaces are absent from candidate packages while workflow support input may use SSH only for read-only staging.
- **SC-004**: A synthetic local smoke proves prepared history roots remove the `no ingested datasets` failure mode for candidate `portfolio-walk-forward` commands.
- **SC-005**: If real server data is still insufficient, the post-merge sidecar reports a real data/edge diagnostic instead of the previous missing-history wiring failure.

## Assumptions

- Server DB paths already used by existing read-only workflows are the safest current price sources: `data/auto_invest.db`, `data/forward_wide.db`, and `data/forward_multiasset.db`.
- This feature is risk grade 2 because it changes workflow support inputs and candidate command generation. It does not change the safety perimeter or money path.
- Historical data quality is judged by existing `ingest-history`, recency guard, and `portfolio-walk-forward` semantics; this feature does not relax pass criteria.

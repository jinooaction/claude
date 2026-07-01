# 스펙 078: 돈 경로 게이트 정렬 루프

**기능 브랜치**: `Codex/078-money-gate-alignment-loop`
**작성일**: 2026-07-01
**상태**: Draft
**위험 등급**: 등급 2(운영 체계 변경, 읽기 전용 보고 루프)

## 사용자 시나리오 및 테스트

### 사용자 이야기 1 - 돈 경로 상태를 한 장으로 맞춘다 (우선순위: P1)

운영자는 `money-path`, `capital-path-readiness`, `edge-autoarm`, `reassign`, 전진 페이퍼, 파이프라인 생존 감시가 서로 같은 상태를 말하는지 매번 손으로 대조하지 않아도 되어야 한다.

**독립 테스트**: 최신 sidecar 스냅샷을 probe에 넣으면 JSON과 Markdown에 각 게이트 표면의 상태, 파싱 여부, 핵심 값, 정렬 판정이 표시된다.

**인수 시나리오**:

1. **Given** `money-path`가 `PREVIEW_ONLY`와 `ACCUMULATING_EDGE`를 보고한다.
2. **When** 자본 준비도와 edge-autoarm도 같은 대기 상태를 보고한다.
3. **Then** 돈 경로 게이트 정렬 루프는 `ALIGNED_WAITING`을 발행하고, 관측 누적이 다음 행동임을 표시한다.

### 사용자 이야기 2 - 게이트 불일치를 다음 작업으로 발행한다 (우선순위: P1)

어떤 루프는 "기다리는 중"이라고 말하는데 다른 루프는 "승격 가능" 또는 "차단"이라고 말하면, 그 차이가 채팅 해석에만 남지 않고 자동 작업 후보로 드러나야 한다.

**독립 테스트**: 같은 입력에서 `money-path.stage`와 `capital-path-readiness.capital_ladder_stage`가 다르면 `MISALIGNED` 이슈와 복구 작업 후보가 생성된다.

**인수 시나리오**:

1. **Given** `money-path`는 `ACCUMULATING_EDGE`인데 자본 준비도는 `EDGE_READY`를 보고한다.
2. **When** 돈 경로 게이트 정렬 루프가 실행된다.
3. **Then** `overall_status`는 `MISALIGNED`가 되고, 이슈에는 기대값, 관측값, 다음 행동, 원천 sidecar가 포함된다.

### 사용자 이야기 3 - 다음 자동 루프가 이 상태를 이어받는다 (우선순위: P2)

다음 Codex 세션과 자동 작업 실행 루프는 새 sidecar만 읽어도 돈 경로의 현재 병목, 불일치 여부, 안전 경계를 이해해야 한다.

**독립 테스트**: workflow가 `LAST_RUN.md`와 `money_gate_alignment.json`을 발행하고, pipeline liveness 레지스트리가 이 sidecar 신선도를 추적한다.

**인수 시나리오**:

1. **Given** main에서 workflow가 실행된다.
2. **When** `automation/money-gate-alignment-last-run` 브랜치를 확인한다.
3. **Then** Markdown 요약과 기계 판독 JSON이 모두 존재하고, 생존 감시가 이 루프를 추적한다.

### 예외 상황

- 핵심 sidecar가 없으면 상태를 추측하지 않고 `BLOCKED` 또는 `UNKNOWN`으로 표시한다.
- 원문은 있지만 JSON 파싱이 실패하면 해당 입력만 `malformed`로 표시하고, 전체 판정은 불완전 증거로 낮춘다.
- 전진 관측 수 부족은 실패가 아니라 `ALIGNED_WAITING`으로 분리한다.
- `pipeline-liveness`가 `CRITICAL`이면 돈 경로 해석보다 파이프라인 복구를 우선한다.

## 요구사항

### 기능 요구사항

- **FR-001**: 시스템은 `money-path`, `capital-path-readiness`, `edge-autoarm`, `reassign`, `rebalance-paper-forward`, `pipeline-liveness`, `autonomous-work-execution`, `kis-smoke` sidecar를 읽어야 한다.
- **FR-002**: 시스템은 Markdown fenced JSON과 순수 JSON을 모두 파싱해야 한다.
- **FR-003**: 시스템은 `money-path.live_money_state.status`와 자본 준비도 `live_money_status`를 비교해야 한다.
- **FR-004**: 시스템은 `money-path.stage`와 자본 준비도 `capital_ladder_stage`를 비교해야 한다.
- **FR-005**: 시스템은 `money-path.blocking_gate`와 자본 준비도 `blocking_gate`를 비교해 서로 다른 차단 사유가 떠도는지 표시해야 한다.
- **FR-006**: 시스템은 `edge-autoarm`의 `WAIT_EDGE` 또는 승격/강등 판정이 `money-path` 상태와 모순되는지 확인해야 한다.
- **FR-007**: 시스템은 `reassign`이 `HOLD`인지, 전진 토너먼트가 관측 부족인지, incumbent/challenger 상태가 현재 돈 경로와 충돌하지 않는지 확인해야 한다.
- **FR-008**: 시스템은 파이프라인 생존 감시가 `CRITICAL`이면 게이트 정렬보다 자동화 복구를 우선 이슈로 표시해야 한다.
- **FR-009**: 시스템은 불일치, 누락, 파싱 실패, 정상 대기 상태를 구분해 `alignment_issues`로 발행해야 한다.
- **FR-010**: 시스템은 `ALIGNED_WAITING`, `ALIGNED_READY`, `MISALIGNED`, `BLOCKED`, `UNKNOWN` 중 하나의 종합 상태를 발행해야 한다.
- **FR-011**: 시스템은 `LAST_RUN.md`와 `money_gate_alignment.json`을 발행해야 한다.
- **FR-012**: 시스템은 주문, 자본 배분, 브로커 호출, 라이브 설정 변경, 허용 종목·포지션 한도 변경, 비밀값 접근, 외부 유료 서비스 호출을 수행하지 않아야 한다.

### 핵심 엔티티

- **GateSurface**: 입력 sidecar 한 개의 출처, 존재 여부, 파싱 상태, 주요 상태값, 요약.
- **GateAlignmentIssue**: 불일치 또는 대기 사유. 심각도, 게이트 이름, 기대값, 관측값, 원인, 다음 행동, 원천 sidecar를 포함한다.
- **MoneyGateAlignmentReport**: 종합 상태, 돈 경로 상태, 자본 준비도 상태, 선택된 자동 작업 후보, 게이트 표면, 정렬 이슈, 안전 불변조건을 포함한다.

## 안전 경계

- 읽기 전용이다. 기존 sidecar를 읽고 자기 sidecar만 발행한다.
- 실거래, 주문, 계좌 자본 배분, 라이브 전략 변경, 허용 종목·포지션 한도 변경을 하지 않는다.
- 헌법, 커널 목록, 자본 사다리 공식, 브로커 비밀값, 감사 로그 기록 방식을 바꾸지 않는다.
- 이 루프는 기존 게이트를 대체하지 않는다. 서로 다른 게이트가 같은 상태를 말하는지 확인하고, 어긋나면 복구 작업 후보를 발행한다.

## 성공 기준

- **SC-001**: 같은 입력 sidecar로 두 번 실행하면 같은 `overall_status`, 같은 이슈 식별자, 같은 다음 행동이 나온다.
- **SC-002**: 최신 실제 sidecar smoke에서 현재 상태가 `ALIGNED_WAITING`으로 판정되고, 전진 관측 부족이 실패가 아니라 누적 대기로 표시된다.
- **SC-003**: 의도적으로 stage나 live status를 어긋나게 한 입력은 `MISALIGNED`를 발행한다.
- **SC-004**: `pipeline-liveness`가 `CRITICAL`인 입력은 `BLOCKED`를 발행하고 파이프라인 복구를 다음 행동으로 둔다.
- **SC-005**: `uv run pytest`와 `uv run ruff check src tests`가 통과한다.
- **SC-006**: 새 workflow에는 브로커, 주문, 라이브 전환, 원격 서버 명령, 외부 배포 명령이 포함되지 않는다.

## 가정

- 현재 돈 경로의 단일 기준 표면은 `money-path`의 `live_money_state.status`이다.
- 자본 준비도 루프는 `money-path`를 해석한 2차 표면이므로, 둘이 어긋나면 정렬 이슈로 본다.
- 관측 부족은 정상 대기 상태다. 세계 최고 수준의 백테스트가 있더라도 기존 헌법의 `Backtest -> Canary -> Full Live` 단계와 자본 사다리 관측 게이트는 유지된다.
- `kis-smoke`는 브로커 연결 생존 증거일 뿐, 실거래 가능 상태의 직접 증명으로 쓰지 않는다.

## 비목표

- 실제 매매, 실거래 전환, 자본 배분, 전략 교체를 수행하지 않는다.
- 기존 자본 사다리, edge-autoarm, reassign의 의사결정 규칙을 바꾸지 않는다.
- GitHub PR 생성, 코드 자동 수정, 자동 머지를 workflow 안에서 수행하지 않는다.

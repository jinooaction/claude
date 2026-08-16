# Feature Specification: Live Canary Gateway And Profit Evidence

**Feature Branch**: `Codex/143-live-canary-gateway-profit-evidence`
**Created**: 2026-08-16
**Status**: Implemented - Awaiting Live Fill And Positive PnL Evidence
**Risk Grade**: 4 - 실제 주문 진입점과 실계좌 손익 증거 자동화 변경
**Input**: 현재 무장된 293달러 자본 사다리 경로를 제한 SSH 관문을 통과하는 실제 주문,
체결 동기화, 양의 계좌 손익 증거까지 끝까지 연결한다.

## User Scenarios & Testing

### User Story 1 - 승인된 실주문만 서버 관문 통과 (Priority: P1)

운영자는 production 환경 승인을 마친 예약 실행만 실제 주문 명령을 서버에 전달하고, 일반 저장소
SSH 비밀값을 가진 다른 작업은 같은 명령을 재현할 수 없기를 원한다.

**Why this priority**: 현재 워크플로의 직접 셸 명령은 제한 SSH 관문에 허용되지 않아 다음 정규장
실주문이 실패한다. 단순히 명령을 허용하면 production 승인 경계를 우회할 수 있으므로 함께 고쳐야 한다.

**Independent Test**: production 전용 개인키로 서명한 짧은 수명 요청은 서버 공개키·센티넬·자본·
배포 지문 검사를 통과하고, 변조·만료·재사용·비무장·자본 불일치 요청은 주문 CLI 진입 전에 거부된다.

**Acceptance Scenarios**:

1. **Given** production 승인 뒤 환경 전용 서명키가 제공되고 현재 센티넬이 293달러로 무장됨,
   **When** 예약 실행이 현재 run·commit·자본·만료·nonce를 서명해 보냄,
   **Then** 서버는 서명과 모든 권위를 검증한 뒤 기존 live CLI를 정확히 한 번 호출한다.
2. **Given** 일반 작업이 저장소 SSH 키만 가짐, **When** 서명 없거나 변조된 주문 명령을 보냄,
   **Then** 서버는 주문·자본 이동·감사 장부 변경 전에 종료 코드 126 또는 2로 거부한다.
3. **Given** 운영자가 수동 production 실행을 승인함, **When** 서명 요청이 서버에 도달함,
   **Then** 같은 권위 검사를 통과하되 주문 CLI를 호출하지 않고 주문 0건으로 끝난다.

---

### User Story 2 - 체결 뒤 첫 실제 수익을 자동 판정 (Priority: P1)

운영자는 라이브 체결이 생긴 뒤 같은 성과 엔진으로 실현·미실현 손익을 측정하고, 완전한 시세가
있는 상태에서 총손익이 0보다 커진 최초 시점을 덮어쓰지 않는 증거로 보고 싶다.

**Why this priority**: 주문 성공만으로 돈을 번 것이 아니다. 체결 수와 양의 총손익을 독립 증거로
분리해야 목표를 거짓 완료하지 않는다.

**Independent Test**: 체결 0, 시세 결측, 손익 0 이하, 완전한 양의 손익, 이후 손실 전환을 차례로
입력하면 `NO_FILLS_YET`, `PNL_INCOMPLETE`, `FILLED_NOT_PROFITABLE`,
`FIRST_PROFIT_OBSERVED`가 결정론적으로 나오고 최초 양의 증거는 이후에도 보존된다.

**Acceptance Scenarios**:

1. **Given** 실제 체결이 한 건 이상이고 모든 열린 종목 시세가 있으며 총손익이 양수임,
   **When** 증거 루프가 실행됨, **Then** 최초 관측 시각·체결 수·실현·미실현·총손익을 기록한다.
2. **Given** 최초 수익 관측 후 현재 손익이 0 이하로 바뀜, **When** 다음 관측이 실행됨,
   **Then** 현재 손익은 갱신하되 최초 수익 달성 증거는 유지한다.

---

### User Story 3 - 주문 완료 후 전체 돈 경로 자동 재평가 (Priority: P2)

운영자는 live-canary가 끝나면 체결·손익 증거, money-path, capital-path-readiness가 순서대로 자동
재실행되어 다음 세션이 수동으로 sidecar를 조합하지 않기를 원한다.

**Why this priority**: 실제 수익이 생겨도 상위 보고가 하루 뒤까지 오래되면 목표 완료를 검증할 수 없다.

**Independent Test**: 워크플로 트리거와 입력 manifest를 검사해 live-canary 완료가 live-profit을,
live-profit 완료가 money-path를, money-path 완료가 capital readiness를 순서대로 깨우는지 확인한다.

**Acceptance Scenarios**:

1. **Given** live-canary production run이 완료됨, **When** GitHub 완료 이벤트가 발생함,
   **Then** 주문 없는 증거 루프가 체결 동기화·성과 측정·sidecar 발행을 수행한다.
2. **Given** 첫 수익 sidecar가 갱신됨, **When** 후속 완료 이벤트가 발생함,
   **Then** money-path와 capital readiness가 같은 수익 상태를 반영한다.

### Edge Cases

- 지정가가 즉시 체결되지 않으면 주문 성공과 수익 달성을 분리하고 후속 예약 관측을 계속한다.
- KIS 시세가 일부 빠지면 양의 수익으로 추정하지 않고 `PNL_INCOMPLETE`로 실패 폐쇄한다.
- 서버 checkout과 서명된 main 사이에 코드 파일 차이가 있으면 실주문을 거부한다. 문서·스펙만
  다른 경우에는 배포 생략 정책과 일치하므로 허용한다.
- 같은 nonce는 첫 시도 뒤 재사용할 수 없고, GitHub 재실행은 새 run attempt nonce를 쓴다.
- 수동 실행과 예약 실행은 겹치지 않으며, 수동 실행은 휴장 여부와 무관하게 주문 함수를 호출하지 않는다.
- 체결 동기화가 실패해도 성과 측정과 실패 sidecar 발행을 시도해 증거 공백을 남기지 않는다.

## Requirements

### Functional Requirements

- **FR-001**: 실제 주문은 production 환경 전용 개인키로 서명된 요청만 서버 관문이 허용해야 한다.
- **FR-002**: 서명 payload는 저장소·워크플로·run id·commit·자본·만료·nonce를 모두 묶어야 한다.
- **FR-003**: 서버는 root 소유 공개키로 서명을 검증하고 만료·재사용·형식 오류를 실패 폐쇄해야 한다.
- **FR-004**: 서버는 센티넬 `armed:true`, 서명 자본과 센티넬 자본 일치, 유효 rung/NAV를 다시
  확인해야 하며 자본은 현재 사다리 권위보다 클 수 없다.
- **FR-005**: 서버는 배포 checkout과 서명 commit 사이 비문서 코드 차이가 있으면 주문을 거부해야 한다.
- **FR-006**: 검증 통과 뒤에도 기존 `rebalance-once --mode live --confirm-live --account-wide`의
  K1/K2, 정규장, 현금, 손실 브레이커, 주문 감사 경로를 그대로 사용해야 한다.
- **FR-007**: 체결 동기화와 손익 측정은 주문 제출 권한이 없는 별도 고정 명령이어야 한다.
- **FR-008**: 손익은 기존 스펙 011 성과 엔진으로 모든 live 체결과 현재 KIS 시세를 계산해야 한다.
- **FR-009**: 최초 실제 수익은 `live fills_count > 0`, 열린 종목 시세 결측 0, 데이터 경고 0,
  `total_pnl_usd > 0`이 동시에 참일 때만 달성으로 판정해야 한다.
- **FR-010**: 최초 달성 시각과 당시 손익은 최신 손익이 다시 음수가 되어도 누적 증거로 보존해야 한다.
- **FR-011**: live-profit 증거는 live-canary 완료 뒤와 평일 장중 후속 예약에서 자동 갱신되어야 한다.
- **FR-012**: live-profit 완료는 money-path를, money-path 완료는 capital readiness를 자동 재실행해야 한다.
- **FR-013**: 모든 sidecar는 비밀값·계좌번호를 마스킹하고 실패 시에도 마지막 시도 결과를 발행해야 한다.
- **FR-014**: 전략·검증 구간·비용 가정·20% rung·293달러 자본·K1/K2·20% 손실 예산을 변경하지 않는다.
- **FR-015**: production 환경의 required reviewer와 main-only 배포 정책을 유지해야 한다.
- **FR-016**: `workflow_dispatch`는 서명·센티넬·배포 정합만 검증하고 주문 0건으로 끝나야 하며,
  실제 주문 명령은 평일 예약 실행에서만 선택해야 한다.
- **FR-017**: live-canary 실행은 단일 동시성 그룹으로 직렬화해 수동 검증과 예약 주문이 겹치지 않아야 한다.

### Key Entities

- **Signed Live Order Request**: 저장소, 워크플로, run, commit, capital, expiry, nonce와 서명.
- **Live Profit Observation**: 현재 live 체결 수, 실현·미실현·총손익, 수익률, 시세 결측, 경고.
- **First Profit Evidence**: 최초 양의 손익 관측 시각과 당시 수치, 이후 관측에도 유지되는 달성 상태.
- **Money Path Projection**: 주문 가능 상태와 첫 수익 증거를 함께 보여주는 최상위 운영 보고.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 서명된 정상 요청 1개는 주문 CLI까지 도달하고 변조·만료·재사용·비무장·자본 불일치
  요청 5종은 모두 주문 호출 0건으로 거부된다.
- **SC-002**: 일반 저장소 SSH 비밀값만으로는 유효한 실제 주문 서명을 만들 수 없다.
- **SC-003**: 라이브 체결과 완전한 양의 손익 입력에서 최초 수익 증거가 한 번 생성되고 이후 보존된다.
- **SC-004**: live-canary 완료 후 세 개 파생 워크플로가 사람의 수동 실행 없이 순서대로 갱신된다.
- **SC-005**: 전체 pytest, ruff, 셸 문법, YAML, diff, 엄격 하네스, HANDOFF 사실, PR 품질 관문을 통과한다.
- **SC-006**: 배포 뒤 주문 없는 live-profit 관측이 현재 계좌에서 체결 0·수익 미달을 정직하게 기록하고,
  다음 정규장 예약을 자동 재개 트리거로 남긴다.

## Assumptions

- GitHub production 환경은 main branch만 허용하고 required reviewer `jinooaction`을 유지한다.
- production 환경 전용 서명 개인키는 GitHub 환경 비밀값으로 저장하고 저장소에는 공개키만 둔다.
- 서버에 OpenSSL, coreutils, flock, git, uv가 설치되어 있다.
- 실제 수익은 세전·수수료 반영 범위가 현재 성과 엔진과 KIS 체결 장부가 제공하는 범위와 같다.
- 양의 수익은 보장하지 않으며 검증 기준이나 시세 결측을 유리하게 해석하지 않는다.

completed_candidate_id: candidate-live-canary-gateway-profit-evidence
next_candidate_id: observe-first-live-profit

# Feature Specification: Paper-Trading Daemon

**Feature Branch**: `claude/continue-previous-session-20p3O`
**Spec Directory**: `specs/009-paper-trading-daemon/`
**Created**: 2026-05-19
**Status**: Draft
**Input**: "auto-invest를 live 자본에 노출시키기 전 일주일짜리 paper-trading 관찰 데몬"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 실시간 시장에서 룰셋 행동을 일주일 동안 관찰 (Priority: P1)

운영자는 자본금 100달러로 KIS 실계좌를 준비해 두었지만, 곧장 live 모드로 자본을 노출시키기 전에 "이 룰셋이 실시간 미국장에서 일주일 동안 어떻게 동작하는지" 직접 관찰하고 싶다. 운영자는 한 줄 명령(`auto-invest paper-run`)으로 데몬을 띄우고, SIGTERM으로 종료할 때까지 데몬이 실시간 quote를 받아 룰을 평가하고 시뮬레이션 체결을 기록하기를 기대한다. KIS 주문 API는 단 한 번도 호출되지 않아야 한다.

**Why this priority**: 이 시나리오를 충족시키지 못하면 운영자는 시뮬레이션 단계 없이 곧바로 live로 가야 하거나, paper-trading 단계 자체를 포기해야 한다. paper-run 데몬 본체가 없으면 후속 리포트·튜닝 피드백도 의미가 없다. P1.

**Independent Test**: paper-run 데몬을 30분 동안 띄우고, 종료 후 KIS 주문 엔드포인트가 호출된 횟수가 0이고 audit_log에 시뮬 체결 이벤트가 1건 이상 기록되었는지 확인하는 것으로 단독 검증 가능.

**Acceptance Scenarios**:

1. **Given** 정상 설정된 룰셋과 KIS 키, 미국장 정규시간, **When** 운영자가 paper-run 데몬을 실행하고 두 시간 후 SIGTERM으로 종료, **Then** KIS 주문 API 호출 카운트는 0이고 audit_log에는 시뮬 체결·차단·해석 이벤트가 시간순으로 기록되어 있다.
2. **Given** paper-run 데몬이 실행 중이고 whitelist에 없는 종목에 대한 시그널이 발생, **When** OrderRouter가 그 시그널을 평가, **Then** live와 동일한 게이트(whitelist·position cap·halt flag·session window)가 작동하여 `ORDER_DENIED` 이벤트가 기록된다.
3. **Given** paper-run 데몬이 실행 중이고 모든 게이트를 통과한 정상 시그널 발생, **When** OrderRouter가 broker 호출 단계에 도달, **Then** 실제 KIS 주문 API 대신 시뮬 체결 경로로 진입하여 `ORDER_PAPER_FILLED` 이벤트가 기록되고 가상 포지션·평가 손익이 갱신된다.
4. **Given** paper-run 도중 운영자가 halt flag를 켬, **When** 다음 tick의 시그널이 평가, **Then** 시뮬 체결이 즉시 멈추고 `ORDER_HALTED` 이벤트가 기록된다 (live와 동일 동작).

---

### User Story 2 — 일주일 관찰 결과를 한눈에 보는 리포트 (Priority: P2)

운영자는 일주일 동안 paper-run을 돌린 뒤 그 결과를 한눈에 보고 룰을 튜닝할지 결정하고 싶다. `auto-invest paper-report --since <ts>` 명령으로 룰별 시그널 수·시뮬 체결 수·가상 PnL·차단 횟수·외부 API 오류 횟수·튜닝 피드백(한 번도 trigger 안 된 룰, 너무 자주 trigger된 룰)을 받아야 한다.

**Why this priority**: 일주일 관찰의 가치는 사후 분석에서 나온다. 데이터는 audit_log에 남지만 운영자가 SQLite를 직접 쿼리해야 한다면 실효성이 떨어진다. P2 — 데몬 본체가 먼저 동작해야 의미 있으므로 P1 뒤.

**Independent Test**: 합성 audit_log를 SQLite에 미리 깔아두고 paper-report 명령을 실행, 룰별 집계가 정확히 나오는지 확인.

**Acceptance Scenarios**:

1. **Given** paper-run이 일주일치 데이터를 audit_log에 쌓아둠, **When** 운영자가 `paper-report --since <7일전ts>`를 실행, **Then** 룰별 시그널 수·시뮬 체결 수·가상 누적 PnL·차단 횟수·외부 API 오류 횟수가 표 형태로 출력되고, 한 번도 trigger 안 된 룰과 trigger 빈도 상위 룰 목록이 함께 나온다.
2. **Given** 같은 SQLite DB에 live 모드 audit_log와 paper 모드 audit_log가 섞여 있음, **When** paper-report 실행, **Then** 리포트는 paper 모드 이벤트만 집계하고 live 이벤트는 무시한다 (이벤트 타입으로 명확히 구분).

---

### User Story 3 — paper-run 도중 안전 invariant가 live와 동일하게 작동 (Priority: P2)

운영자는 paper-run이 "안전 게이트를 우회하지 않는다"는 신뢰를 가져야 한다. position cap·whitelist·halt flag·session window 같은 K1·K6 게이트는 paper에서도 정확히 같은 코드 패스로 평가되어야 한다. paper-run이 live와 다르게 동작한다면 일주일 관찰의 신뢰성이 사라진다.

**Why this priority**: 안전 invariant 회귀는 일주일 관찰의 모든 결과를 무의미하게 만든다. P2 — 시나리오 1·2의 코드 패스 안에 자동으로 포함되어야 하는 속성이지만, 독립적으로 검증할 가치가 있다.

**Independent Test**: paper-run에서 cap 초과 시그널·whitelist 위반 시그널·session window 외부 시그널을 각각 주입하고, audit_log 이벤트가 live와 동일한 형태로 기록되는지 확인.

**Acceptance Scenarios**:

1. **Given** paper-run 실행 중, position cap을 초과하는 시그널 발생, **When** OrderRouter가 평가, **Then** cap 게이트가 차단하고 `ORDER_DENIED` 이벤트의 deny reason이 live와 동일하다.
2. **Given** paper-run 실행 중, 미국장 마감 후 시그널 발생, **When** session window 가드가 평가, **Then** 시그널은 평가 자체가 건너뛰어지고 `TICK_SKIPPED` 이벤트가 기록된다.

---

### Edge Cases

- paper-run 도중 KIS quote API가 일시 장애 — circuit breaker가 열리고 룰 평가는 일시 중단, 복구 후 자동 재개. audit_log에 `EXTERNAL_API_ERROR` 이벤트가 기록된다.
- paper-run 도중 데몬이 비정상 종료 (OOM, kernel panic, 호스트 재부팅) — systemd 재시작 후 데몬은 마지막 상태(가상 포지션·rule fire history)를 audit_log에서 재구성하여 일관성 유지. 또는 데몬은 깨끗하게 새로 시작하고 리포트가 재시작 경계를 인지하여 누적 PnL을 끊지 않는다.
- paper-run과 live-run이 같은 SQLite DB·같은 audit_log 테이블을 공유할 때 이벤트 타입이 명확히 분리되어 집계 혼동이 없다.
- paper-report 실행 시 audit_log가 비어 있음 — 빈 리포트를 명시적으로 출력하고 비정상 종료하지 않음.
- paper-run 도중 룰셋 config 파일이 변경됨 — 데몬은 재시작 전까지 기존 룰셋을 사용 (live와 동일 동작). 리포트는 ruleset_sha256으로 룰셋 변경 경계를 표시.
- 시뮬 체결 가격을 quote의 어떤 필드로 잡을지 (bid·ask·last) — 매수는 ask, 매도는 bid를 기본으로 하되 quote에 해당 필드가 없으면 last 가격 사용.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 시스템은 운영자가 한 줄 명령으로 paper-trading 데몬을 띄울 수 있는 CLI 진입점을 제공해야 한다 (예: `auto-invest paper-run`).
- **FR-002**: paper-run 데몬은 SIGTERM·SIGINT 신호를 받을 때까지 계속 동작하며, 신호 수신 시 다음 tick 완료 후 깨끗하게 종료해야 한다.
- **FR-003**: paper-run은 quote/시장 데이터를 실제 외부 시장 데이터 공급자(현재 KIS)에서 받아와야 한다. 가짜·합성 가격을 사용하지 않는다.
- **FR-004**: paper-run의 broker 주문 호출 경로는 단일 차단 지점에서 시뮬 체결로 분기되어야 한다. 이 차단 지점 외 다른 경로로 broker.order_*() 호출이 가능해서는 안 된다.
- **FR-005**: paper-run에서 K1·K6·K7 안전 게이트(whitelist·position cap·halt flag·session window·외부 API 견고성)는 live와 동일한 코드 경로·동일한 결과로 평가되어야 한다. paper-run이 게이트를 우회하지 않는다.
- **FR-006**: paper-run에서 모든 게이트를 통과한 시그널은 시뮬 체결 처리되어 audit_log에 `ORDER_PAPER_FILLED` 이벤트로 기록되어야 한다. 이벤트에는 최소한 룰 ID·종목·매매 방향·수량·시뮬 체결 가격·차단 시점 timestamp가 포함된다.
- **FR-007**: paper-run의 시뮬 체결 가격은 차단 시점 quote에서 결정한다. 매수는 ask 가격, 매도는 bid 가격을 기본으로 하고, 해당 필드가 없으면 last 가격을 폴백으로 사용한다.
- **FR-008**: paper-run은 가상 포지션을 추적해야 한다. live의 positions 테이블에 직접 쓰면 안 되고, paper 전용 테이블 또는 audit_log 이벤트 누적으로 재구성한다 (선택은 plan 단계).
- **FR-009**: 시스템은 `auto-invest paper-report --since <ts> [--until <ts>]` 명령을 제공해야 한다. 출력에는 룰별 시그널 수·시뮬 체결 수·가상 누적 PnL·게이트별 차단 횟수·외부 API 오류 횟수가 포함되어야 한다.
- **FR-010**: paper-report는 한 번도 trigger 안 된 룰 목록과 trigger 빈도 상위 룰 목록을 별도로 출력하여 운영자의 튜닝 의사결정을 돕는다.
- **FR-011**: paper-run 이벤트와 live-run 이벤트는 audit_log의 이벤트 타입으로 명확히 구분되어야 한다. paper-report는 paper 이벤트만 집계하고 live 이벤트는 무시한다 (역도 동일).
- **FR-012**: paper-run 도중 발생한 외부 API 오류·circuit breaker open·rate limit 적중 이벤트는 audit_log에 기록되어 paper-report가 집계할 수 있어야 한다.
- **FR-013**: paper-run·paper-report 명령은 KIS 실주문 API에 단 한 번도 접근해서는 안 된다. 시스템은 paper 모드임을 확인할 수 있는 가드(예: 시작 시 audit 이벤트 `PAPER_RUN_STARTED`)를 audit_log에 남겨야 한다.
- **FR-014**: paper-run의 룰 평가 코드(시그널 생성·게이트 평가)는 live와 동일한 모듈을 사용해야 한다. paper 전용 룰 평가 분기는 허용하지 않는다.
- **FR-015**: paper-run과 live-run은 같은 호스트에서 동시에 실행될 수 없다. paper-run 시작 시 시스템은 같은 SQLite DB 상에서 live 워커가 실행 중인지 확인하고(예: 최근 `WORKER_STARTED` 이벤트 뒤에 `WORKER_STOPPED`가 없는 상태), 실행 중이면 paper-run 시작을 거부한다. 역도 동일.
- **FR-016**: paper-run의 cap 게이트는 KIS 실계좌 잔고/포지션을 기준으로 평가한다. 가상 포지션을 cap 평가에 반영하지 않는다. 이는 "paper 동작이 live와 100% 동일한 게이트 입력값을 사용한다"는 신뢰를 보장하기 위함이며, 그 함의(같은 종목 시뮬 매수가 반복될 수 있음)는 의도된 동작이다.

### Key Entities *(데이터를 다루는 항목)*

- **Paper-Run Session**: 한 번의 paper-run 데몬 실행 단위. 시작 시각·종료 시각·ruleset_sha256·종료 사유(SIGTERM·crash·정상)로 식별된다. audit_log에 `PAPER_RUN_STARTED`·`PAPER_RUN_STOPPED` 이벤트로 경계를 표시한다.
- **Simulated Fill**: paper-run에서 발생한 가상 체결 한 건. 룰 ID·종목·매매 방향·수량·체결 가격·timestamp·연관된 시그널·세션 식별자를 갖는다. `ORDER_PAPER_FILLED` 이벤트로 audit_log에 기록.
- **Virtual Position**: paper-run의 누적 가상 포지션. 종목·수량·평균 단가·미실현 손익을 갖는다. simulated fill의 누적 결과로 재구성 가능해야 한다 (별도 테이블이든 derived view든 plan에서 결정).
- **Paper Report**: paper-report 명령의 출력. 기간 범위·룰별 집계·게이트별 차단 집계·외부 API 오류 집계·튜닝 피드백을 포함한다.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 운영자가 paper-run 데몬을 30분 이상 실행 후 종료했을 때, 같은 기간 동안 KIS 주문 API에 발생한 호출 수는 0이다 (네트워크 캡처 또는 mocked broker로 검증).
- **SC-002**: paper-run 데몬은 미국장 정규시간 일주일 (5영업일, 약 32.5시간) 동안 연속 실행되어도 비정상 종료·메모리 누수·SQLite DB 손상 없이 동작한다.
- **SC-003**: paper-report 명령은 일주일치(예: 약 1만~10만 이벤트) 데이터를 200ms 이내에 집계하여 출력한다.
- **SC-004**: paper-run의 안전 게이트 동작은 live와 100% 동일하다 — 동일한 시그널·동일한 상태에서 paper와 live는 동일한 deny reason 또는 동일한 fill 동작을 보인다 (테스트로 검증).
- **SC-005**: 운영자는 paper-report 출력만 보고 "어떤 룰을 끄거나 임계값을 조정해야 할지"를 추가 SQLite 쿼리 없이 결정할 수 있다 (튜닝 피드백 섹션이 의사결정을 돕는다).
- **SC-006**: paper-run·paper-report 명령은 live 모드의 audit_log·positions·기타 운영 상태를 단 한 row도 수정하지 않는다.
- **SC-007**: live 워커가 실행 중인 상태에서 paper-run을 시작하면 시작 자체가 거부되고(에러 메시지 + non-zero 종료 코드), audit_log에는 거부 이벤트가 한 줄 기록된다. 역방향(paper 실행 중 live 시작 시도)도 동일하게 거부된다.
- **SC-008**: paper-run의 cap 게이트가 차단/허용한 동일 시그널에 대해, 같은 시각·같은 실계좌 잔고를 가진 live-run 시뮬과 동일한 결정(allow/deny 및 deny reason)을 내린다 (테스트로 검증).

## Assumptions

- 운영자는 KIS App Key·App Secret·계좌번호를 가지고 있다 (paper-run도 quote를 받기 위해 KIS 인증이 필요). 실주문 권한은 사용되지 않지만 quote 권한은 사용된다.
- paper-run은 미국 정규시간(09:30~16:00 ET)에 의미 있게 동작한다. 그 외 시간에는 session window 가드가 평가를 건너뛰는 것이 정상 동작이다.
- paper-run의 시뮬 체결은 즉시 fill·전량 fill·quote 가격 = 체결 가격으로 가정한다. 슬리피지·체결 지연·부분 체결 모델링은 이번 스펙 범위 밖이다.
- paper-run·live-run은 동일 SQLite DB를 공유한다. 별도 DB로 분리하는 옵션은 plan 단계에서 검토.
- paper-run과 live-run은 같은 호스트에서 동시에 실행될 수 없다 (FR-015). 운영자가 일주일 paper 관찰 도중 live로 스위치하려면 paper-run을 먼저 종료해야 한다. 이는 SQLite의 동시 쓰기 부담을 피하고, "어느 모드가 지금 시장에 대해 책임을 지는지"를 명확히 하기 위함이다.
- paper-run의 cap 게이트는 KIS 실계좌 잔고를 기준으로 평가한다 (FR-016). paper 시뮬 누적 매수가 cap을 잠그지 않으므로, 일주일 관찰 도중 같은 종목 시뮬 매수가 여러 차례 반복될 수 있다. 이는 의도된 동작이며 paper-report에서 trigger 빈도 통계로 가시화된다.
- paper-run은 spec 006의 systemd 통합·spec 007의 hardened canary와 독립적이다. 이번 스펙에서는 foreground CLI만 다루고 systemd unit·canary 통합은 후속 스펙으로 둔다.
- audit_log 스키마 확장은 K4 추가 변경(additive)으로 처리한다. 기존 이벤트 타입·기존 row는 건드리지 않고 새 이벤트 타입만 추가한다. constitution v3.0.0 IX.D 자동 머지 채널에 해당.
- 일주일 관찰이 끝난 뒤 운영자가 paper-report를 보고 룰을 튜닝하는 절차는 수동이다. 자동 튜닝(spec 005 autonomous-tuner)과의 연동은 별개 스펙.
- spec 008(backtest-engine)과의 관계: backtest는 과거 CSV로 룰을 사전 검증, paper-trading은 실시간 시장으로 룰을 사후 검증. 두 도구는 보완 관계이며 같은 룰셋을 공유한다.

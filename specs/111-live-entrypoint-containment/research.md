# Research: Live Entrypoint Containment

## R-001 — 설계와 실거래 실행을 분리한다

**Decision**: `auto-invest design`은 후보 생성과 검증 보고만 수행한다. 라이브 워커 시작 권한은 제거한다.

**Rationale**:

- 현재 저장소에는 전진 검증, 캐너리, 자본 사다리, 전략 재지정 게이트가 이미 존재한다.
- 설계 명령이 직접 라이브 워커를 시작하면 이 증거 경로를 우회한다.
- 생성 품질과 실행 권한은 서로 다른 책임이다.
- 제안 기능을 유지하면서 실행 권한만 제거하면 안전성과 활용성을 함께 지킬 수 있다.

**Rejected alternatives**:

- `auto_ok=true`를 유지하고 확인 문자열만 더 복잡하게 만든다.
  - 확인 문자열은 검증 우회를 해결하지 못한다.
- 소액 자본이므로 직접 라이브 시작을 유지한다.
  - 작은 자본은 권한 분산과 중복 워커 문제를 해결하지 못한다.
- 기존 센티넬을 한 번 더 검사한다.
  - 설계 경로가 별도 프로세스를 시작하는 구조 자체가 남는다.

## R-002 — 예약 `operator-design` 실행을 제거한다

**Decision**: `.github/workflows/operator-design.yml`의 주간 `schedule`을 제거한다.

**Rationale**:

- 운영자 의도는 시간에 따라 자동으로 바뀌는 입력이 아니다.
- 예약 실행은 LLM 비용과 후보 파일을 반복 생성한다.
- 현재 경로는 자동 `OK`와 결합해 라이브 시작까지 가능하다.
- 후보 탐색이 필요하면 자율 성장 루프가 증거 기반 후보를 생성하는 별도 경로가 있다.

**Rejected alternatives**:

- 예약 실행을 유지하되 `auto_ok=false`만 적용한다.
  - 불필요한 비용과 오래된 고정 의도 반복 문제는 남는다.
- 예약 실행 결과를 자동 폐기한다.
  - 가치 없는 외부 호출을 계속하는 이유가 없다.

## R-003 — 검증은 가용성 표시가 아니라 실제 실행 증거다

**Decision**: 모듈 가져오기 성공이나 실행기 존재만으로 검증 성공을 판단하지 않는다. 실제 실행 결과와 후보 지문이 있어야 한다.

**Rationale**:

- 현재 verifier는 백테스트 함수를 가져올 수 있어도 호출하지 않는다.
- paper-run은 명시적 stub인데도 정적 검증 후 aggregate `ok=True`가 가능하다.
- 이 상태는 “검증 가능”과 “검증 완료”를 혼동한다.

**Required interpretation**:

- `PASS`: 실제 실행 성공 + 같은 후보 지문 + 신선한 증거
- `WAIT`: 후보는 생성됐지만 필수 동적 검증 증거가 없음
- `FAIL`: 실행 실패, 검증 실패, 지문 불일치, 오래된 증거, 비정상 결과
- aggregate `ok=True`: 모든 필수 단계가 `PASS`

**Safe intermediate behavior**:

후속 통합이 한 PR에 들어가기 어렵다면 후보를 `WAIT_DYNAMIC_VALIDATION`으로 남기고 `ok=False`를 반환한다.

## R-004 — 자연어 입력은 셸 명령 인자가 아니라 데이터다

**Decision**: 운영자 intent를 SSH 명령 문자열에 직접 삽입하지 않는다.

**Preferred mechanisms**:

1. 표준 입력
2. 임시 파일
3. Base64 인코딩 후 고정 스크립트에서 디코딩
4. JSON payload 파일

**Rationale**:

- 따옴표와 줄바꿈은 정상적인 자연어 입력이다.
- `$()`, 세미콜론, 역따옴표도 데이터로 보존돼야 한다.
- 수동 이스케이프는 누락되기 쉽고 유지보수가 어렵다.

**Rejected alternative**:

- 작은따옴표만 치환한다.
  - 다른 셸 메타문자와 다중 줄 문제를 해결하지 못한다.

## R-005 — `start_live_worker` 호환성보다 경계 명확성이 우선이다

**Decision**: 모든 호출부를 확인한 뒤 직접 라이브 시작 함수는 삭제하거나 명시적 경계 오류를 내는 비호출 호환 껍데기로 축소한다.

**Rationale**:

- 살아 있는 편의 함수는 다시 호출되기 쉽다.
- 설계 모듈 아래에 라이브 시작 함수가 있으면 책임 경계가 계속 흐려진다.
- 과거 테스트가 이 기능을 기대하더라도 안전 계약이 바뀌면 테스트도 바뀌어야 한다.

**Implementation choice rule**:

- production caller 0건이고 외부 import 계약이 없으면 삭제
- 역사적 import 호환이 필요하면 `LiveActivationBoundaryError`를 즉시 발생
- 다른 승인된 경로가 실제로 사용하면 해당 경로를 별도 실행 권한 모듈로 이동하되 이번 PR에서 새 라이브 경로를 만들지 않음

## R-006 — 명령 안전 등록부는 설명이 아니라 실행 계약이다

**Decision**: `design`을 `A2/PROPOSAL`로 낮추고 live/order capability flags를 모두 false로 만든다.

**Rationale**:

- 등록부는 CLI가 실제로 무엇을 할 수 있는지 검사하는 코드 소유 정책이다.
- 구현이 proposal-only로 바뀌었는데 등록부가 live-capable로 남으면 자동화와 운영자 보고가 거짓이 된다.
- 향후 테스트가 등록부와 실제 호출 그래프의 불일치를 잡아야 한다.

## R-007 — 이번 PR은 안전 경계 축소지만 위험 등급 4다

**Decision**: 문서 PR 자체는 등급 2 운영 인계 변경이지만, 후속 구현 PR은 돈 경로 능력을 바꾸므로 등급 4로 취급한다.

**Rationale**:

- 실제 주문을 추가하지 않더라도 실거래 진입점 제거는 돈 경로 동작을 바꾼다.
- 등급을 낮게 잡으면 필요한 탐색과 회귀 검증이 누락될 수 있다.
- 방향이 안전 축소라는 사실은 승인과 검증 강도를 낮출 이유가 아니다.

## R-008 — 실제 서버 상태는 이 스펙의 전제값으로 추측하지 않는다

**Decision**: 저장소 코드 경로를 안전하게 만들되, 현재 서버에 과거 라이브 워커가 실행 중인지 단정하지 않는다.

**Rationale**:

- 분리 프로세스는 코드 변경 후에도 남아 있을 수 있다.
- 저장소 센티넬 `armed:false`는 서버 프로세스 부재를 증명하지 않는다.
- 서버 확인은 별도 운영 진단이며 실제 돈 실행 승인과 구분해야 한다.

**Required final wording**:

- “저장소에서 신규 design-driven live startup 경로를 제거했다.”
- “현재 서버의 과거 프로세스 존재 여부는 확인하지 않았다.”

## R-009 — 기존 승격 경로를 대체 수단으로 명시한다

**Decision**: 설계 후보의 다음 경로는 다음 순서로 고정한다.

```text
candidate rules
→ static validation
→ backtest
→ paper/forward validation
→ hardened canary
→ capital ladder / approved live path
```

**Rationale**:

권한을 제거하면서 대체 경로를 명시하지 않으면 운영자가 과거 편의 경로를 복구하려 할 수 있다. 안전화는 기능 제거가 아니라 책임 재배치다.

## R-010 — 후속 안전 문제를 같은 PR에 섞지 않는다

**Decision**: 주문 재시도, 체결 원장, 노출 예약, 저하 상태, 단일 실행 권한은 별도 스펙으로 분리한다.

**Rationale**:

- 각 문제의 실패 모드와 검증 방법이 다르다.
- 한 PR에서 모두 바꾸면 회귀 원인과 되돌림 경계가 흐려진다.
- 첫 PR은 평행 실거래 진입점을 제거하는 것만으로 독립적인 위험 감소를 만든다.

## Evidence Map

| 판단 | 주요 근거 파일 |
|---|---|
| 예약 실행과 자동 승인 | `.github/workflows/operator-design.yml` |
| 자동 `OK` 주입 | `scripts/operator_design.sh` |
| 동적 검증 stub 성공 처리 | `src/auto_invest/design/verifier.py` |
| 라이브 워커 분리 프로세스 | `src/auto_invest/design/deploy.py` |
| 라이브 기본 실행 | `src/auto_invest/cli.py` |
| live-capable 명령 분류 | `src/auto_invest/safety/command_registry.py` |
| 현재 주요 센티넬 해제 | `automation/rebalance-live.request`, `automation/rebalance-micro-gtaa.request` |
| 전체 프로그램 근거 | `HANDOFF-115-EXECUTION-SAFETY-STABILIZATION.md` |

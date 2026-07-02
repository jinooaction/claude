# Research: 주문 거부·체결 품질 손익 관측

## Decision 1: 기존 064번 monitor를 재사용한다

**Decision**: 새 feature는 `opportunity_monitor.py` 계산을 다시 만들지 않고, 이미 발행된 `opportunity_monitor.json`과 `opportunity_history.json`을 읽어 패키징한다.

**Rationale**: 064번은 누적 손익과 `STRATEGY_REVIEW`/`EXECUTION_REVIEW` semantics를 이미 정의했다. 같은 판단을 다른 코드에 복제하면 threshold drift가 생긴다.

**Alternatives Rejected**:

- Recompute rolling monitor from scratch: 기존 검증된 semantics와 달라질 위험이 있다.
- Use only micro GTAA `LAST_RUN.md`: 사람이 읽기는 좋지만 자동 후보 점수화에는 구조화 JSON이 더 안전하다.

## Decision 2: 브로커 오류율은 관측 범위를 명시한다

**Decision**: `broker_rejection_error_rate`는 전체 브로커 가용률이 아니라, opportunity history 안의 rejected-order rows 중 broker error code를 구조적으로 파싱한 비율로 정의한다. KIS smoke는 별도 `smoke_error_rate`로 분리한다.

**Rationale**: 현재 history는 거부 주문 중심이다. 이를 전체 주문 성공률처럼 말하면 과장이다. smoke는 최신 연결 생존이고, rejected rows는 주문 제출 응답 진단이다.

**Alternatives Rejected**:

- Treat rejected rows / all planned orders as broker error rate: planned order 전체 수가 sidecar마다 안정적으로 제공되지 않는다.
- Treat KIS smoke success as order acceptance proof: smoke는 quote/cash/positions/balance 확인이지 주문 접수 검증이 아니다.

## Decision 3: 별도 sidecar workflow를 둔다

**Decision**: `automation/execution-quality-last-run`에 `LAST_RUN.md`와 `execution_quality.json`을 발행한다.

**Rationale**: 후보의 목적은 증거 패키징이다. autonomous evolution이 매번 micro GTAA 세부 Markdown을 직접 해석하는 대신 독립 증거 표면을 읽으면 다음 세션과 자동화가 같은 결론을 재현하기 쉽다.

**Alternatives Rejected**:

- Only enrich autonomous evolution parsing: 패키지 자체가 남지 않아 운영자가 같은 요약을 확인하기 어렵다.
- Add to micro GTAA workflow only: 이미 길고 돈 경로에 가까운 workflow라 보고 패키징을 분리하는 편이 안전하다.

## Decision 4: workflow는 sidecar만 읽는다

**Decision**: 새 workflow는 `git show origin/automation/...`으로 기존 sidecar를 수집하고, KIS secrets, SSH, 브로커 API, order command를 사용하지 않는다.

**Rationale**: 이 feature의 안전 가치는 "실행 품질 관측"이지 주문 경로 재실행이 아니다. 외부 호출 없이도 현재 후보 목표를 충족할 수 있다.

**Alternatives Rejected**:

- Call KIS smoke directly: secrets/SSH를 새 workflow에 추가하고 등급을 높인다.
- Query broker order API: 실제 주문 경계에 가까워지고 운영자 승인 없이 진행할 수 없다.

## Decision 5: liveness는 비핵심 감시로 등록한다

**Decision**: `execution-quality` sidecar는 pipeline liveness에서 `critical=False`로 등록한다.

**Rationale**: 멈추면 자율 성장의 관측 품질이 저하되지만, 돈 경로는 fail-closed 상태를 유지한다. 핵심 빨강보다 비핵심 저하가 정확하다.

**Alternatives Rejected**:

- Critical sidecar: 보고 루프 정지를 돈 경로 장애처럼 과장한다.
- No liveness registration: 침묵 정지를 다시 사람이 찾아야 한다.

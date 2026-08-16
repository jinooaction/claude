# Feature Specification: Heldout Exploration Canary

**Feature Branch**: `codex/140-heldout-exploration-canary`
**Created**: 2026-08-16
**Status**: In Progress
**Risk Grade**: 4 - 실제 자본 사다리와 라이브 전략 설정 변경

## User Scenarios & Testing

### User Story 1 - 오래 검증된 정확한 전략을 제한된 실거래 탐색으로 연결하기 (Priority: P1)

운영자는 장기 홀드아웃과 최근 forward 증거가 있는데도 PSR 0.95만 기다리며 수개월간 자본을
0%로 유지하지 않고, 서로 다른 증거가 모두 맞을 때 정확한 배포 전략을 20% 한도로 탐색하기를 원한다.

**Independent Test**: 정확한 3·6·9·12개월 균등가중 전략의 홀드아웃·forward·강화 캐너리
증거를 입력하면 단 0에서 단 1(실계좌 NAV 20%)로만 승격하는지 확인한다.

### User Story 2 - 불완전한 증거와 전략 대리표현을 거부하기 (Priority: P1)

운영자는 같은 GTAA 계열이라는 이유만으로 다른 가중·다른 추세창의 결과를 라이브 설정에
붙이거나, 강화 캐너리 실패를 무시해 주문하는 일을 원하지 않는다.

**Independent Test**: 정확한 배포 계산, forward Calmar 우위, PSR, 강화 캐너리 중 하나를
삭제하거나 지문을 바꾸면 자본이 0%에 머무는지 확인한다.

### User Story 3 - 탐색 결과가 나빠지면 즉시 줄이기 (Priority: P1)

운영자는 20% 탐색이 원래의 손실 예산과 서킷 브레이커 아래에서 움직이고, 탐색 증거만으로
25% 이상 커지지 않기를 원한다.

**Independent Test**: 단 1에서 EDGE_CONFIRMED가 없으면 라이브 기간·관측 수가 충분해도
단 2로 승격하지 않고, 낙폭이 예산 절반이면 즉시 단 0으로 강등하는지 확인한다.

## Edge Cases

- 수익 증거 sidecar나 강화 캐너리 JSON이 없거나 손상되면 단 0을 유지한다.
- 홀드아웃과 개발 구간이 겹치거나 홀드아웃이 120개월 미만이면 탐색하지 않는다.
- 비용 차감이 연 50bp 미만이면 탐색하지 않는다.
- 전략군 결과만 있고 정확한 배포 설정 결과가 없으면 탐색하지 않는다.
- 휴장·정수 주·추세 신호 때문에 주문이 0건이면 주문을 억지로 만들지 않는다.
- 실주문은 기존 시장시간, production 환경, whitelist, 캡, 감사 로그, 비밀값 게이트를 그대로 통과해야 한다.

## Requirements

- **FR-001**: 자본 사다리는 0%=단0, 20%=단1, 25%=단2, 50%=단3, 100%=단4여야 한다.
- **FR-002**: 기존 `EDGE_CONFIRMED`는 단 0→1 진입의 충분조건으로 계속 인정해야 한다.
- **FR-003**: 대체 탐색 진입은 정확한 라이브 배포 전략의 사전 정의된 계산만 허용해야 한다.
- **FR-004**: 탐색 진입은 시간 분리 홀드아웃 120개월 이상과 연 50bp 이상 비용을 요구해야 한다.
- **FR-005**: 홀드아웃 CAGR·Sharpe는 벤치마크보다 높고 낙폭은 벤치마크의 80% 이하여야 한다.
- **FR-006**: 독립 forward 관측은 40개 이상, PSR은 0.80 이상, Calmar는 벤치마크보다 높아야 한다.
- **FR-007**: 강화 캐너리는 정확한 설정으로 PASS해야 하며 전략 지문이 라이브와 같아야 한다.
- **FR-008**: 누락·손상·불일치·모순 증거는 모두 fail-closed로 단 0을 유지해야 한다.
- **FR-009**: 단 1→2는 원래의 `EDGE_CONFIRMED`와 기존 라이브 증거를 모두 요구해야 한다.
- **FR-010**: 강등·정지, K1 캡, whitelist, 감사 로그, 비밀값, 시장시간, `Backtest -> Canary -> Full`을 보존해야 한다.
- **FR-011**: 라이브 캐너리와 검증 설정은 `global-trend-fixed`, 균등가중, SPY·IEF·GLD,
  추세창 [63,126,189,252]로 정확히 일치해야 한다.
- **FR-012**: 모든 판단 입력과 결과는 sidecar와 센티넬 PR에 남아 재현 가능해야 한다.

## Success Criteria

- **SC-001**: 현재 정확한 배포 후보는 개발 431개월과 홀드아웃 235개월을 분리해 계산한다.
- **SC-002**: 연 50bp 비용 차감 후 홀드아웃 CAGR 8.68% 이상, Sharpe 1.83 이상,
  최대 낙폭 5.58% 이하이며 같은 구간 벤치마크보다 세 기준이 모두 우수하다.
- **SC-003**: 현재 forward 41관측, PSR 0.827 이상, Calmar 우위 입력은 강화 캐너리 PASS와
  지문 일치가 있을 때만 20% 탐색 준비 상태를 만든다.
- **SC-004**: 탐색 증거만으로 25% 이상 승격하는 시험은 100% 차단된다.
- **SC-005**: 전체 pytest, ruff, 엄격 하네스, HANDOFF 사실 검증, PR 품질 관문을 통과한다.
- **SC-006**: 배포 후 실제 sidecar가 exact deployment match와 강화 캐너리 결과를 기록한다.

## Safety And Rollback

헌법 X.4의 첫 자본 진입 조건을 바꾸므로 안전 경계 변경 문구 `this changes the safety perimeter`를
커밋에 남긴다. 첫 노출은 기존 25%보다 작은 20%이며, 25% 이상은 원래 조건을 유지한다.
문제가 생기면 기능 커밋과 센티넬을 되돌려 단 0으로 복귀한다. 데이터베이스 파괴나 감사 로그
삭제는 없고, 이미 체결된 주문은 임의 삭제하지 않으며 기존 청산·정지 절차를 따른다.

completed_candidate_id: candidate-heldout-exploration-canary
next_candidate_id: run-heldout-exploration-canary

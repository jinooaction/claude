# Requirements Checklist: Autonomous Promotion Actions

**Created**: 2026-06-29  
**Scope**: 스펙 069 요구사항 품질 확인

## Completeness

- [x] 주요 사용자 시나리오가 독립적으로 검증 가능하다.
- [x] forward 등록, canary 제출, 생존 감시가 별도 성공 기준으로 분리됐다.
- [x] 실제 주문, 자본 증액, live 설정 변경이 비목표로 명시됐다.

## Safety

- [x] `Backtest -> Canary -> Full` 순서가 유지된다.
- [x] 신규 워크플로의 live order 금지 조건이 테스트 가능한 요구사항으로 적혔다.
- [x] 후보 제공 경로의 traversal/live-sentinel 차단이 요구사항에 포함됐다.

## Testability

- [x] 순수 코어 입력/출력이 fixture로 재현 가능하다.
- [x] workflow 안전 불변식이 텍스트 테스트로 검증 가능하다.
- [x] liveness registry 변경이 회귀 테스트로 검증 가능하다.

## Ambiguity

- [x] 실거래 canary 직접 무장은 이번 범위가 아님을 명시했다.
- [x] 등록 상태 저장 위치가 tracked JSON으로 결정됐다.

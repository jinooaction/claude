# 연구 기록: 돈 경로 게이트 정렬 루프

## 결정: 1차 상태 기준은 money-path

- **선택**: `money-path`의 `live_money_state.status`, `stage`, `blocking_gate`, `gates`를 1차 상태로 본다.
- **이유**: 기존 운영 기억과 코드가 실거래 상태 해석을 `live_money_state.status`로 모았다. 자본 준비도는 이를 읽은 종합 표면이다.
- **대안**: `capital-path-readiness`를 기준으로 삼기. 원천이 아니라 2차 해석이므로 불일치 원인을 가릴 수 있어 제외했다.

## 결정: 정상 대기는 ALIGNED_WAITING

- **선택**: `INSUFFICIENT_DATA`, `WAIT_EDGE`, reassign `HOLD`, pipeline `OK`가 함께 있으면 불일치가 아니라 정상 대기로 본다.
- **이유**: 관측 부족은 실패가 아니라 자본 사다리의 fail-safe 대기 상태다.
- **대안**: 모든 `PENDING`을 문제로 표시하기. 운영자가 정상 누적을 장애로 오해하게 만들어 제외했다.

## 결정: pipeline-liveness CRITICAL은 최우선 BLOCKED

- **선택**: 핵심 sidecar 정지가 있으면 돈 경로 판정보다 자동화 복구를 먼저 발행한다.
- **이유**: 멈춘 파이프라인 위에서 게이트 정렬을 판단하면 오래된 증거를 확신으로 오해한다.
- **대안**: 각 sidecar 나이를 루프마다 재구현하기. 이미 `pipeline-liveness`가 단일 생존 표면이므로 재사용한다.

## 결정: workflow는 자기 sidecar만 발행한다

- **선택**: workflow는 source sidecar를 fetch/read하고 `automation/money-gate-alignment-last-run`만 force-push한다.
- **이유**: 기존 자본 준비도·작업 실행 루프와 같은 운영 패턴이며, 다른 경로를 변경하지 않는다.
- **대안**: 자동으로 issue, PR, strategy config를 만들기. 등급과 안전 경계가 올라가므로 이번 스펙에서는 제외한다.

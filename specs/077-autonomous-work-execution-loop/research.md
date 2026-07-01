# 연구 기록: 자율 작업 실행 루프

## 확인한 기존 루프

- `capital-path-readiness`: money-path, edge-autoarm, reassign, forward, KIS smoke, promotion/evolution sidecar를 읽어 자본 경로 준비도를 발행한다.
- `autonomous-evolution`: 전 영역 성장 후보를 발굴하고 candidate backlog와 learning ledger를 남긴다.
- `autonomous-promotion`: 후보를 검증 단계로 분류한다.
- `candidate-implementation-factory`: 후보를 실행 가능한 검증 패키지로 만든다.
- `candidate-result-executor`: 허용된 no-live 검증 명령만 실행해 결과 evidence를 남긴다.
- `pipeline-liveness`: sidecar 신선도를 감시한다.

## 빈칸

기존 루프는 후보와 결과를 만든다. 그러나 "그럼 지금 Codex가 무슨 작업을 시작해야 하는가"는 아직 운영자가 물어야 했다. 스펙 077은 이 판단을 매일 자동으로 발행한다.

## 안전 결론

완전 자동 코드 작성·PR·머지는 아직 이 저장소의 안전 경계와 비용 경계가 충분히 좁혀지지 않았다. 따라서 이번 스펙은 다음 작업을 자동으로 고르고 설명하는 것까지만 배포한다. 이 선택은 자율성을 줄이는 게 아니라, 다음 단계 자동화를 안전하게 붙이기 위한 고정된 발판이다.

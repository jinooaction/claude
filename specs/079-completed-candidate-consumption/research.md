# 연구 기록: 완료 후보 소비 및 차순위 자동 승격 루프

## 결정: 실패 장부와 완료 장부를 분리한다

- **선택**: 기존 `learning_ledger.json`은 rejected/evidence_dependent/operator_review 상태를 유지하고, 출시 완료 후보는 새 `released-work` sidecar에 기록한다.
- **근거**: 실패와 완료는 재검토 의미가 다르다. 완료 후보는 다시 실행하지 않아야 하지만 실패 후보처럼 전략 실패로 해석하면 안 된다.
- **대안**: `learning_ledger.json`에 `released` decision을 추가한다. 기존 진화 루프의 의미가 넓어져 sidecar 소비자가 실패 장부와 완료 장부를 혼동할 수 있어 제외했다.

## 결정: 완료 근거는 완료된 spec 산출물에서만 읽는다

- **선택**: `tasks.md` 체크박스가 모두 완료된 spec에서 명시 필드(`selected_work_candidate`, `released_candidate_id`, `completed_candidate_id`)만 후보 완료로 해석한다.
- **근거**: handoff 문장은 다음 후보와 완료 후보를 모두 언급하므로 자연어 전체 scan은 오탐 위험이 있다.
- **대안**: 모든 `candidate-...` 정규식 언급을 완료로 본다. 억제·실패·다음 후보 언급까지 완료 처리할 수 있어 제외했다.

## 결정: 자율 작업 실행 workflow는 repository scan fallback을 사용한다

- **선택**: `released-work` sidecar가 아직 최신이 아니어도 checkout된 main repository에서 완료 장부를 즉시 생성해 후보 선택에 넣는다.
- **근거**: main push 때 `released-work`와 `autonomous-work-execution`이 병렬 실행될 수 있다. fallback이 없으면 완료 직후 한 번 더 같은 후보를 고를 수 있다.
- **대안**: schedule 순서만 조정한다. push 경합은 남으므로 충분하지 않다.

## 결정: pipeline liveness는 비핵심 감시로 등록한다

- **선택**: `released-work`는 돈 경로 핵심 sidecar가 아니므로 non-critical freshness로 감시한다.
- **근거**: 완료 장부가 stale이면 작업 선택 품질은 떨어지지만 주문·자본 안전 경계는 깨지지 않는다.
- **대안**: critical 감시로 올린다. 후보 완료 장부 장애가 실거래 안전 장애와 같은 심각도로 보일 수 있어 제외했다.

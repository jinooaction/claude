# Cost-Adjusted Edge Experiment Contract

completed_candidate_id: candidate-cost-adjusted-edge-experiment
experiment_id: cost-adjusted-edge-experiment
risk_grade: 2

## 목적

forward 성과 후보를 비용 차감 관점에서 다시 읽는 no-live 실험 계약이다. 현재 증거가 비용 차감 실험을 시작할 만큼 모였는지, 무엇이 아직 관측 대기인지, 어떤 비용 근거가 부족한지를 기계 판독 가능한 JSON/Markdown으로 고정한다.

## 필수 입력

- `automation/rebalance-paper-forward-last-run:LAST_RUN.md`
- `automation/execution-quality-last-run:LAST_RUN.md`
- `automation/money-path-last-run:LAST_RUN.md`
- `automation/released-work-last-run:released_work.json`
- `automation/autonomous-evolution-last-run:learning_ledger.json`
- `automation/pipeline-liveness-last-run:LAST_RUN.md`

## 출력 계약

- `overall_status`: `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`
- `cost_adjusted_candidates`: 비용 스트레스별 forward track 후보
- `execution_cost`: 실행 품질과 비용 근거 완성도
- `validation_gates`: 입력, 파이프라인, no-live 안전, forward 관측, execution-quality, 비용 기준, released-work closure
- `safety_boundary`: 읽기 전용 불변 조건

## 안전 경계

이 계약은 브로커 API, 주문, 자본 배분, live 전략, whitelist/caps, 비밀값, 헌법/커널, 외부 유료 서비스를 건드리지 않는다.


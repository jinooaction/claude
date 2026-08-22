# Data Model: 자동 전략 공장과 연구 캐너리

## SearchBatch

- `batch_id`: 자료·코드·전략 문법 지문에서 결정되는 ID
- `data_fingerprint`, `code_commit`, `created_at_utc`
- `candidate_count`: 첫 버전은 정확히 64
- `status`: planned, running, complete, partial, failed
- `candidates`, `trial_records`, `decision`

## StrategyCandidate

- `candidate_id`, `trial_index`, `family`
- `parameters`: live 표현 가능한 설정 필드
- `strategy_fingerprint`
- `deploy_config_text`
- `execution_symbols`: SPYM, IEF, GLDM

## TrialRecord

- `candidate_id`, `status`, `error`
- 비용별 전체·구간 수익, Sharpe, Calmar, 최대 낙폭
- 벤치마크 지표, 구간 승리 수, PSR
- 모든 구간의 표본 내·표본 외 순위 입력

## FactoryDecision

- `verdict`: FACTORY_EDGE 또는 NO_FACTORY_EDGE
- `selected_candidate_id`
- `trial_count`, `complete_trial_count`
- `dsr`, `pbo`, `psr`, `segment_win_rate`
- 개별 gate와 실패 이유
- `research_canary_eligible`

## ResearchCanaryEvidence

- 공장 sidecar 지문과 관측 시각
- 선택 전략·배포 전략 지문
- 강화 캐너리 상태
- 정합성·halt·계좌 NAV 상태
- 허용 단 1 비율 10%

## State Transitions

- planned -> running -> complete
- 부분·오류 -> partial/failed -> 승자 없음
- complete + 모든 gate PASS -> FACTORY_EDGE
- FACTORY_EDGE + 운영 증거 PASS -> rung 0 -> rung 1(10%)
- rung 1 + 기존 40개 forward 계약 PASS -> rung 2(20%)
- 누락·손실·정합성 실패 -> rung 0 또는 기존 즉시 하향 규칙

# Data Model: Heldout Exploration Canary

## DeploymentMatchEvidence

- `candidate_id`: 고정 배포 후보 ID
- `validated_config`: 검증 설정 경로
- `live_config`: 라이브 설정 경로
- `ensemble_windows`: [3, 6, 9, 12]개월
- `annual_cost_bps`: 최소 50
- `development` / `holdout` / `benchmark_holdout`: 기간과 성과
- `historical_gates`: CAGR, Sharpe, 낙폭, 기간, 비용의 개별 판정
- `forward`: 관측 수, PSR, Calmar 우위
- `historical_passed`: 역사 조건 전체 결론
- `exploration_canary_ready`: 역사와 forward 조건 전체 결론

## ExplorationVerdict

- 준비 조건: `deployment_match.exploration_canary_ready == true`
- 실행 조건: 강화 캐너리 `verdict == PASS`
- 실패 기본값: 입력 누락·손상·불일치 시 `WAIT_EDGE`

## CapitalLadderState

- 단 0: 0%
- 단 1: 20%, 탐색 캐너리
- 단 2: 25%, EDGE_CONFIRMED 필요
- 단 3: 50%
- 단 4: 100%

# HANDOFF-146 - Heldout Exploration Canary

## 결론

#617로 정확 배포전략의 장기 홀드아웃과 forward 증거를 최대 20% 탐색 캐너리에 연결했다.
기능·배포·sidecar·강화 캐너리·실계좌 NAV는 통과했지만, 첫 autoarm 실행은 안전 분류기의
`cap` 키워드 오탐으로 센티넬 쓰기만 차단됐다. 실주문과 자본 변경은 없었다.

## 현재 사실

- main: `9b5346f` (#617), 기능 커밋 `403187f`
- 헌법: X.4 v7.0.0, 사다리 0% → 20% 탐색 → 25% → 50% → 100%
- exact holdout: 235개월, 연 50bp, CAGR 8.682649%, Sharpe 1.831434, 낙폭 5.572914%
- benchmark: CAGR 8.291414%, Sharpe 1.264685, 낙폭 17.268823%
- forward: 42관측, PSR 0.829449, Calmar 우위
- profit sidecar: `historical_passed=true`, `exploration_canary_ready=true`
- autoarm run `31918671085`: 강화 캐너리·NAV 통과, 센티넬 쓰기 A6 오탐 실패
- 현재 센티넬: 단 0, 실주문 0건

## 후속 브랜치

`codex/140-capital-keyword-guard`에서 bare `cap` 키워드만 제거한다. 명시적 `position cap`,
`exposure cap`, `caps`와 보호 경로 감지는 유지한다. 회귀시험은 허용된 A4 자본 사다리 실행과
실제 포지션 한도 변경 차단을 각각 고정한다.

## 다음 순서

1. 후속 PR을 전체 pytest, ruff, 엄격 하네스, HANDOFF 사실 검사 뒤 merge한다.
2. 배포 성공 뒤 `forward-edge-autoarm.yml`을 다시 실행한다.
3. edge-autoarm sidecar와 센티넬 PR에서 단 0→1, 실계좌 NAV 20%를 확인한다.
4. 미국 정규장에서만 live-canary workflow를 실행하고 주문·체결·잔고를 감사한다.

주문을 만들기 위해 휴장, 가격, 정수 주, 추세 신호, production 환경을 우회하지 않는다.

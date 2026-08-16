# HANDOFF-145 — Forward Edge Watch and KIS Range Query

## 상태

#615가 `main`에 merge됐다. 수익 후보 `three_asset_fixed-w10`은 이제 일반 대기 속에서 사라지지 않고 자율 작업 루프가 `globalfixed` 전진 PSR을 직접 추적한다. KIS 최근 주문 smoke의 외부 500도 범위 조회로 복구됐다.

## 바뀐 동작

- 최근 7일 주문내역은 7개 날짜 x 3거래소가 아니라 한 날짜 범위 x NASD·NYSE·AMEX로 조회한다.
- 호출 수는 최대 21회에서 3회로 줄었다.
- 거래소 하나라도 실패하면 전체 조회가 실패하므로 미체결 주문을 숨기지 않는다.
- profit-evidence JSON이 autonomous-work 입력에 포함된다.
- 역사 통과·forward 미달은 `wait-for-globalfixed-forward-edge` / `OBSERVATION_WAIT`다.
- 역사와 forward가 모두 통과하면 `candidate-globalfixed-promotion-recheck`가 나오지만 실제 주문이 아니라 다중검정·전략 지문·캐너리·자본 사다리 재검토만 수행한다.

## 현재 돈 상태

- 역사 후보: `three_asset_fixed-w10`, `HOLDOUT_EDGE`.
- 전진 후보: `globalfixed`, 관측 41, PSR 0.82727, 기준 0.95, `NO_EDGE`.
- 자율 선택: `wait-for-globalfixed-forward-edge`.
- live money: 기존 `PREVIEW_ONLY` / `NO_EDGE_YET`, 자본 0%, 실주문 불가.

독립 관측은 시간을 실제로 지나야 쌓인다. 같은 날 작업을 여러 번 실행해 관측 수를 부풀리지 않는다.

## 증거

- PR #615, 기능 커밋 `51f9cbe`, merge commit `fe240a5`.
- 전체 테스트 2813 passed, 5 skipped; ruff와 diff 통과.
- strict harness 14/14, HANDOFF facts OK, PR quality gate success.
- deploy run `31916736255`: success.
- autonomous-work run `31916736280`: success, `wait-for-globalfixed-forward-edge` 선택.
- released-work run `31916736259`: success. 이 시점에는 T010~T011이 미완료라 스펙 139 소비 전이며 이 HANDOFF merge 뒤 재확인한다.
- KIS smoke run `31916736347`: 5 passed. 최근 주문 0건, 열린 미체결 0건.

## 다음 확인점

매일 새 `globalfixed` 독립 관측 뒤 profit-evidence와 autonomous-work를 확인한다. PSR 0.95를 넘더라도 `candidate-globalfixed-promotion-recheck`에서 다중검정, 전략 지문, hardened canary, 자본 사다리를 다시 확인한다. 그 전에는 실제 주문과 자본 배분을 열지 않는다.

# HANDOFF-165 - USDA 작물 수급 전략·720회 판정

## 상태

PR #678이 merge 커밋 `4f59ef7`로 `main`에 들어갔고 배포, 생산 전략 공장,
KIS 읽기 전용 점검이 성공했다. USDA 전략은 `NO_FACTORY_EDGE`이며 현재 돈 경로는
`PREVIEW_ONLY`, `ACCUMULATING_EDGE`, 단 0, 자본 0, 실주문 불가다.

## 기준 의심에 대한 결론

- 기준은 불가능하지 않다. 현실 양성 대조군 PSR `0.962691`은 완전 관문을 통과했고,
  평균 제거 무효 대조군 PSR `0.434559`는 탈락했다.
- 16후보 보정에서 실거래 무효 합격률은 `5.0%`, 연 샤프 0.6 신호 검출률은 `84.8%`다.
- 종이 단계는 무효 전략도 `21.6%` 받아 오히려 느슨한 편이다.
- 따라서 이번 탈락은 기준 코드가 모든 후보를 영구 거부해서가 아니다.

## USDA 전략 결과

- 공식 ESMIS 발표 192개, 동일 날짜 별칭 5개, 193개월을 사용했다.
- 개발 60개월, 격리 1개월, 홀드아웃 131개월, 비용 10/25/50bp를 결과 전에 고정했다.
- 옥수수·밀·대두·동시 긴축, 1/3회 변화, GLD 최대 50/100%의 16개 후보다.
- 사전 선택 후보 PSR `0.204521`, 50bp 후 연 초과수익 `-1.710304%`, 기존 상관
  `0.452343`, 혼합 샤프 변화 `-0.117035`, 혼합 낙폭 `15.316546%`다.
- 사후 최상 대두 후보는 PSR `0.965194`, 50bp 후 연 `+3.078124%`였지만 개발 샤프
  `0.110106`, 혼합 샤프 변화 `-0.049875`라 종합 관문을 통과하지 못했다. 이미
  홀드아웃을 본 후보라 승격도 금지된다.
- 실거래 전체 관문 통과 후보 0개, 종이 전체 관문 통과 후보 0개다.

## 생산 증거

- merge: `4f59ef72def122205b29465eb135e5ec47f57b2b`
- deploy: `32846066131` success
- strategy factory: `32846066082` success, 16/16 current, 704 prior, 720/720 unique
- KIS smoke: `32846263963` success, read-only 5/5
- KIS: cash 934.27달러, NAV 1454.23달러, ORANY 28주, 최근 주문·체결·미체결 0건
- money path local replay: `PREVIEW_ONLY`, `ACCUMULATING_EDGE`, rung 0,
  capital 0, forward 0/20, real-order submission false

## 검증

- `uv run pytest -q`: 3060 passed, 5 skipped
- `uv run ruff check src tests`: 통과
- YAML, `git diff --check`, 엄격 하네스 14/14, HANDOFF 사실 검사, PR 품질 관문: 통과
- 생산 `strategy_factory.json`: commit `4f59ef7`, 자료 완전, 192 releases,
  5 aliases, 720 unique, `PASSABLE_BUT_CANDIDATE_UNCONFIRMED`

## 안전 경계

실제 주문, 자본, 무장, 허용목록, 포지션 한도, 손실 예산, 헌법, 커널은 바꾸지 않았다.
`Backtest -> Canary -> Full`과 모든 K1/K2·현금·정규장·기계 승인 관문은 유지된다.

## 다음 우선순위

결과를 본 뒤 USDA 후보나 기준을 바꾸지 않는다. 다음 독립 전략군은
`independent_energy_cross_market`(에너지 교차시장)이며, 코드나 결과를 보기 전에 별도
등급 4 SDD로 자료·후보·비용·분할·관문을 사전등록한다. 역사적으로 유망한
`globalfixed`는 깨끗한 전진 관측 0/20이므로 별도 자동 관측을 계속하되 과거 장부를
복사하지 않는다.

# HANDOFF 022 — 백테스트 거래비용·슬리피지 모델 (스펙 016 슬라이스 1, 2026-05-27)

PR #77 머지 커밋 `f8552c6`. **백테스트가 그동안 거짓 잣대였던 문제를 고쳤습니다.**
운영자 지시("세계 최고 수준 작업 분석·우선순위 판단·자율 수행")의 코드 분석 1순위로
선택했습니다.

## 왜 1순위였나 (거짓 잣대 = 모든 전략 개선의 오염원)

시스템은 **운영 안전성은 성숙**(감사 로그·게이트·캐너리·서킷 브레이커·체결 동기화 —
스펙 001~015)하지만, **측정 잣대가 거짓**이었습니다.

- 헌법 **원칙 VI**는 "백테스트는 API 실패·슬리피지·부분 체결을 모델링하지 못하므로
  성과를 **체계적으로 과대평가**한다"고 경고하는데, 백테스트 엔진
  (`backtest/broker_mock.py`)이 정확히 그 **무비용·무슬리피지** 체결이었습니다(수수료 0,
  슬리피지 0).
- 헌법 **원칙 X.2**("단일 잣대")는 라이브·페이퍼·캐너리·백테스트가 **같은 지표
  정의**를 써야 한다는데, 라이브 성과 엔진(`performance/engine.py`)은 비용 반영 실현
  손익을 재는 반면 백테스트는 비용을 0으로 둬 "백테스트는 X라 했는데 라이브는 Y"
  비교가 무의미했습니다.

**세계 최고 수준의 전제 = 정직한 백테스트.** 신호·사이징을 아무리 개선해도 측정
잣대가 거짓이면 환상을 최적화하게 됩니다. 그래서 신호 과학(다요인·레짐)이나 포지션
사이징보다 **먼저** 잣대를 고쳤습니다 — 이게 다른 모든 개선의 토대입니다.

## 한 줄 요약

- **새 모듈 `backtest/costs.py`** — `BacktestCostModel(commission_bps, slippage_bps,
  min_commission_usd)`. `.zero()`(무비용, 회귀 테스트용) / `.kis_default()`(KIS 미국주식
  현실값: 수수료 25bps, 슬리피지 5bps). `effective_fill_price(side, price)`(슬리피지),
  `commission_usd(qty, price)`(수수료), `describe()`(런 헤더 디스크립터). 전부 결정론적
  Decimal 6자리 정규화.
- **`replay.py` `_record_fill`에 비용 오버레이** — 브로커 목의 기계적 체결
  (`pessimistic_zero_slip`)은 그대로 두고, 체결 처리 단계에서 비용을 입힘. 슬리피지=
  체결가를 불리한 방향으로 이동(BUY ↑, SELL ↓) → 유효 체결가가 감사 FILL 행·포지션
  현금흐름·명목거래액에 반영. 수수료=현금흐름에서 별도 차감. 규칙별 누적기
  (`commission_paid_usd`·`slippage_cost_usd`).
- **정직한 기본값** — 프로덕션 진입점(`run_backtest`/CLI/캐너리) 기본값 =
  `kis_default()`(무비용이 기본이면 원칙 VI 위반 영속화). `replay()` 기본값은 `zero()`
  (모듈 싱글턴 `_ZERO_COST_MODEL`)라 기존 무비용 저수준 단위 테스트는 무손상.
- **비용 노출** — 규칙별·합계 수수료/슬리피지를 `ReplayResult`·`RuleBacktestResult`·
  `BacktestSummary`·`RunOutcome`·`metrics.csv`(새 컬럼 `commission_usd`·
  `slippage_cost_usd`)·`backtest-run.json`(새 필드 `cost_model`·`total_*`)·`summary.md`에
  표면화. CLI `auto-invest backtest --commission-bps --slippage-bps --min-commission-usd`.

## 안전 경계 (핵심)

- **오프라인·읽기 전용** — 백테스트는 실제 브로커/돈에 닿지 않음. 라이브 주문 경로
  무수정. 돈 안 움직임. 비용 모델은 시뮬레이션 정직성만 높임.
- **Kernel 터치 0건** — 손댄 파일 전부 비커널: `backtest/`(costs·replay·report·run·
  data_model)·`cli.py`·`tests/`·`specs/016`. K1~K6·K-meta 0건. **감사 로그 스키마(K4)
  무변경** — 비용은 기존 FILL 행의 가격에 녹이고, 합계는 비커널 리포트에만 노출.
- **byte-equality(FR-B15) 보존** — 모든 비용 연산 결정론적 Decimal 6자리 정규화.
  결정론·end-to-end 통합 테스트가 기본 비용 모델 적용 경로를 그대로 통과.

## 설계 노트 — 왜 브로커가 아니라 replay에 비용을 입혔나

브로커 목(`broker_mock.py`)은 "이 막대에서 체결되는가, 명목 체결가는 얼마인가"라는
**기계적 체결 결정**만 담당합니다. 슬리피지·수수료는 그 위에 얹는 **실행 비용 레이어**라
`replay`의 체결 처리(`_record_fill`)에 두는 게 책임 분리상 깔끔하고, 비용 모델을 모든
브로커 메서드에 실로 꿰지 않아도 됩니다. 그래서 `fill_model="pessimistic_zero_slip"`
리터럴은 정직하게 유지되고(브로커는 여전히 무슬리피지), 새 `cost_model` 디스크립터가
오버레이를 기술합니다.

## 테스트

- 신규 9건: `test_backtest_costs.py` 7건(슬리피지 방향·수수료 바닥·zero 항등·정규화·
  디스크립터) + `test_backtest_replay.py` 2건(zero=레거시 동일 / 비용이 자산을 낮추고
  합계 노출). 기존 리포트 테스트 스키마 단정 갱신(CSV 헤더 2컬럼 추가, `cost_model`
  필드, 요약 비용 라인). 전체 **1040 통과, 4 스킵**(라이브 KIS 게이트). 린트 깨끗.

## 다음 세션 후보 (세계 최고 수준 로드맵)

- **슬라이스 2 — 단일 잣대 통일** (가장 가치 높음, 즉시 착수 가능): 백테스트가 라이브
  엔진(`performance/engine.py`)과 **같은** 승률·손익비·Sortino를 계산하도록
  `backtest/metrics.py` 확장 → 헌법 X.2 완전 충족. 체결 스트림에서 실현 왕복 거래를
  계산해야 함(현재 metrics는 자산 곡선 기반).
- **슬라이스 3 — 워크포워드(표본 외) 검증**: 롤링 윈도우 학습/검증 하니스로 과적합
  탐지. 단일 인-샘플 백테스트의 가장 큰 약점.
- 그 뒤 — **신호/알파 과학**(다요인·레짐 인식·신호 감쇠), **포지션 사이징**(변동성·
  상관 반영). 이제 잣대가 정직해졌으니 이 개선들을 환상 없이 측정 가능.
- **실거래 전환** — `AUTO_INVEST_MODE=live` 토글(운영자 명시 지시 필요, 돈 움직임).

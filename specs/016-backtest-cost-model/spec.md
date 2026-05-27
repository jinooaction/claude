# Spec 016 — 백테스트 거래비용·슬리피지 모델 (Backtest Transaction-Cost & Slippage Model)

**상태**: 구현 중 (슬라이스 1 — 비용 오버레이)
**브랜치**: `claude/zealous-ramanujan-2GRVE`
**선행 스펙**: 008(백테스트 엔진), 011(라이브 성과 측정)

## 문제 (Why)

헌법 원칙 VI는 "백테스트는 API 실패·슬리피지·부분 체결을 모델링하지 못하므로
성과를 체계적으로 과대평가한다"고 명시한다. 그런데 현재 백테스트 엔진
(`backtest/broker_mock.py`)은 **무비용·무슬리피지** 체결이다 — 수수료 0, 슬리피지 0.
따라서 백테스트가 내는 수익률·샤프·낙폭은 모두 낙관 편향이며, 이 거짓 잣대 위에서
튜너(스펙 005)·캐너리(스펙 007)·운영자 판단이 전부 오염된다.

또한 헌법 원칙 X.2("단일 잣대")는 라이브·페이퍼·캐너리·백테스트가 **같은 지표 정의**를
써야 한다고 규정한다. 라이브 성과 엔진(`performance/engine.py`)은 비용을 반영한 실현
손익을 측정하는데, 백테스트는 비용을 0으로 두므로 "백테스트는 X라 했는데 라이브는 Y"
비교가 무의미하다.

**세계 최고 수준을 향한 전제**: 신호·사이징을 아무리 개선해도 측정 잣대가 거짓이면
환상을 최적화하게 된다. 정직한 백테스트는 다른 모든 전략 개선의 토대다.

## 범위 (What)

백테스트 체결에 **거래비용 오버레이**를 추가한다. 브로커 목(`broker_mock.py`)의 기계적
체결 모델(pessimistic limit fill)은 그대로 두고, `replay`의 체결 처리 단계에서 비용을
입힌다:

- **슬리피지(slippage)**: 체결가를 불리한 방향으로 이동. BUY는 더 비싸게, SELL은 더
  싸게 체결된 것으로 본다 (basis point 단위).
- **수수료(commission)**: 체결 명목금액에 비례한 비용(basis point) + 건당 최소 수수료
  바닥. 현금흐름에서 차감한다.

비용은 결정론적 Decimal 연산으로 6자리 정규화하여 byte-equality 계약(FR-B15)을 유지한다.

## 기능 요구사항 (FR)

- **FR-C01**: `BacktestCostModel`(commission_bps, slippage_bps, min_commission_usd)을
  정의한다. `.zero()`(무비용, 회귀 테스트용)와 `.kis_default()`(현실적 KIS 미국주식
  기본값) 생성자를 제공한다.
- **FR-C02**: 슬리피지는 체결가에 적용된다 — BUY: `price × (1 + slippage_bps/10000)`,
  SELL: `price × (1 − slippage_bps/10000)`. 이 유효 체결가가 감사 FILL 행·포지션
  현금흐름·명목거래액에 반영된다.
- **FR-C03**: 수수료는 `max(min_commission_usd, 명목금액 × commission_bps/10000)`이며
  포지션 현금흐름에서 별도로 차감된다(가격이 아니라 비용이므로).
- **FR-C04**: 프로덕션 진입점(`run_backtest`/CLI/캐너리)의 기본값은 `kis_default()`다.
  무비용이 기본이면 원칙 VI 위반을 영속화하므로, **정직한 비용이 기본**이다.
- **FR-C05**: `replay()`의 기본값은 `zero()`다 — 기존 저수준 단위 테스트의 무비용
  역학 단정을 보존하기 위해서다. 프로덕션 경로는 명시적으로 `kis_default()`를 넘긴다.
- **FR-C06**: 비용을 운영자가 볼 수 있게 표면화한다 — 규칙별·합계 수수료/슬리피지
  비용을 `ReplayResult`·`RuleBacktestResult`·`BacktestSummary`·`RunOutcome`·`metrics.csv`·
  `backtest-run.json`에 노출한다.
- **FR-C07**: CLI `auto-invest backtest`에 `--commission-bps`·`--slippage-bps`·
  `--min-commission-usd` 옵션을 추가한다(기본값 = KIS 기본).

## 성공 기준 (SC)

- **SC-C01**: 같은 시나리오에서 `kis_default()` 비용은 `zero()` 대비 수익률을 낮추고
  비용 합계 > 0이다.
- **SC-C02**: 결정론 — 같은 입력 + 같은 비용 모델 → 같은 `metrics.csv` byte 결과.
- **SC-C03**: `zero()` 비용 모델은 기존(무비용) 결과와 정확히 동일하다(회귀 무손상).
- **SC-C04**: 슬리피지 방향이 정확하다(BUY 체결가 ↑, SELL 체결가 ↓).
- **SC-C05**: 수수료 바닥이 적용된다(작은 명목금액에서 min_commission이 비례분을 대체).
- **SC-C06**: 기존 1035개 테스트가 계속 통과(스키마 단정 갱신 포함).

## 안전 경계 (Safety boundary)

- **오프라인·읽기 전용**: 백테스트는 실제 브로커/돈에 닿지 않는다. 비용 모델은
  시뮬레이션 정직성만 높일 뿐 라이브 주문 경로를 건드리지 않는다.
- **Kernel 터치 0건**: 손대는 파일은 전부 `backtest/`(비커널)·`cli.py`(비커널)·
  `tests/`·`specs/`. K1~K6·K-meta 터치 없음. 감사 로그 스키마(K4) 변경 없음 —
  비용은 기존 FILL 행의 가격에 녹이고, 합계는 비커널 리포트에만 노출한다.
- **byte-equality 보존**: 모든 비용 연산은 결정론적 Decimal 6자리 정규화.

## 후속 슬라이스 (이 스펙 이후)

- **슬라이스 2 — 단일 잣대 통일**: 백테스트가 라이브 엔진과 같은 승률·손익비·Sortino를
  계산하도록 `backtest/metrics.py` 확장(헌법 X.2 완전 충족).
- **슬라이스 3 — 워크포워드 검증**: 표본 외(out-of-sample) 롤링 윈도우 검증 하니스로
  과적합 탐지.

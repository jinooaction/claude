# Spec 016 — 백테스트 거래비용·슬리피지 모델 (Backtest Transaction-Cost & Slippage Model)

**상태**: 슬라이스 1 출시 + 슬라이스 2(단일 잣대 통일) 출시 + 슬라이스 3(워크포워드 검증) 출시
**브랜치**: `claude/zealous-ramanujan-2GRVE`(슬라이스 1), `claude/vibrant-galileo-FQnsb`(슬라이스 2), `claude/pensive-carson-eZo3k`(슬라이스 3)
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

## 슬라이스 2 — 단일 잣대 통일 (Single-Yardstick Unification, 출시 완료)

### 문제 (Why)

헌법 원칙 X.2("단일 잣대")는 라이브·페이퍼·캐너리·백테스트가 같은 지표 정의를 써야
한다고 규정한다. 슬라이스 1이 비용을 통일했지만, **거래 단위 지표는 여전히 갈라져
있었다**:

- 라이브 성과 엔진(`performance/engine.py`)은 승률·평균손익·손익비를 계산하지만,
  **백테스트엔 그 거래 단위 지표가 통째로 없었다** — 백테스트 결과로는 한 전략의
  승률조차 볼 수 없는데 라이브 성과는 보여줬다(다른 잣대).
- 둘 다 **Sortino(하방 위험만 보는 샤프의 동생)가 없었다**.
- 승률·손익비 공식이 라이브 엔진에만 인라인으로 박혀 있어, 백테스트가 같은 걸
  계산하려면 코드를 복제해야 했고 → 두 잣대가 갈라질 위험(X.2 위반).

### 범위 (What)

거래 단위 지표 정의를 `backtest/metrics.py` 한 곳에 모아 라이브·백테스트가 **같은
함수를 호출**하게 한다. 실현(청산) 손익 재구성·승률·평균손익·손익비·Sortino의 단일
정의를 만든다.

### 기능 요구사항 (FR)

- **FR-D01**: `sortino_ratio(daily_returns)`를 `backtest/metrics.py`에 추가한다 —
  연율화 √252, MAR=RFR=0, 하방편차(목표 반편차) 기준. 샤프와 같은 시간 기준·같은
  무위험 영(0) 경로(하방 위험 0이면 0)를 따른다.
- **FR-D02**: `win_loss_stats(pnls)`(승률·평균이익·평균손실·손익비)와
  `realized_closed_trades(fills)`(평균단가 실현거래 재구성, 보유 초과 매도는 보유분
  클램프)를 공용 정의로 `backtest/metrics.py`에 둔다.
- **FR-D03**: 라이브 엔진의 `compute_risk_metrics`·`realized_trades`는 FR-D02 공용
  정의를 호출한다(인라인 공식 제거). `RiskMetrics`에 `sortino_ratio` 추가, 리포트
  JSON `schema_version` 1.1 → 1.2.
- **FR-D04**: 백테스트는 자신의 비용 반영 체결(`per_rule_fills`)에서 공용 정의로
  거래 단위 지표를 계산해 `RuleBacktestResult`(closed_trades·win_rate·profit_factor·
  sortino_ratio)·`BacktestSummary`(aggregate_sortino·total_closed_trades·
  aggregate_win_rate·aggregate_profit_factor)에 담는다. 룰별 sortino는 자산곡선 일별
  수익률 기준, 승률·손익비는 청산 손익 기준, 포트폴리오 승률·손익비는 전 룰의 청산을
  한데 모아(pooled) 계산한다.
- **FR-D05**: 새 지표를 운영자 산출물에 표면화한다 — `metrics.csv`(sortino·
  closed_trades·win_rate·profit_factor 컬럼)·`backtest-run.json`·`summary.md`.

### 성공 기준 (SC)

- **SC-D01**: 같은 논리적 체결 시퀀스가 라이브 경로와 백테스트 경로에서 **같은 청산
  손익·승률·손익비**를 낸다(교차 검증, `test_metrics_single_yardstick.py`).
- **SC-D02**: 라이브 위험조정 지표(샤프·낙폭·총수익률·Sortino)가 `backtest/metrics.py`
  공용 정의와 바이트 동일하다(`test_performance_risk.py`).
- **SC-D03**: 하방 위험이 없으면(전부 비음수 수익률) Sortino는 0이고, 청산이 없으면
  승률·손익비는 None(N/A)이다.
- **SC-D04**: 비용·byte-equality 회귀 무손상(전체 테스트 통과, 신규 18건).

### 안전 경계 (Slice 2)

- **오프라인·읽기 전용**: 측정 정의만 통일. 라이브 주문 경로 무수정, 돈 안 움직임.
- **Kernel 터치 0건**: 손댄 파일 전부 `backtest/`(비커널)·`performance/engine.py`
  (비커널)·`tests/`·`specs/`. K1~K6·K-meta 무변경. **감사 스키마(K4) 무변경** — Sortino를
  튜너용 `LIVE_PERFORMANCE_SNAPSHOT` 페이로드(K4)에 추가하는 것은 의도적으로 후속
  K4 추가-전용 작업으로 미룬다(이번 슬라이스는 커널 0건 유지).

## 슬라이스 3 — 워크포워드(표본 외) 검증 (Walk-Forward Validation, 출시 완료)

### 문제 (Why)

헌법 원칙 VI는 백테스트가 성과를 체계적으로 **과대평가**한다고 경고한다. 슬라이스 1·2가
백테스트를 정직(비용)·완전·통일된 잣대로 만들었지만, **단일 기간 백테스트는 여전히 그
한 기간에 과적합(overfitting)될 수 있다** — 좋아 보이는 룰셋이 그 시기의 잡음을 외운
것뿐일 수 있고, 표본 밖에서는 우위가 사라진다. 신호·사이징을 개선하기 전에 "이 우위가
표본 밖에서도 재현되는가?"를 물을 수단이 없으면, 환상을 최적화하게 된다(원칙 X 위반).

### 범위 (What)

같은 룰셋을 **롤링 표본 내(IS) / 표본 외(OOS) 날짜 윈도우**에 걸쳐 돌리고, IS 대비 OOS
성과를 **슬라이스 2의 단일 잣대**(`backtest/metrics.py` → `build_summary`)로 비교하는
오케스트레이션 하니스(`backtest/walk_forward.py`)를 추가한다. 기존 `replay`를 날짜
부분구간에 재실행할 뿐 — 새 체결 로직 없음.

### 기능 요구사항 (FR)

- **FR-E01**: `generate_windows(date_start, date_end, in_sample_days, out_of_sample_days,
  step_days, mode)`가 [시작, 끝]을 IS/OOS 윈도우(포함 경계)로 타일링한다. `mode="rolling"`
  은 고정 길이 IS가 OOS와 함께 미끄러지고, `mode="anchored"`는 IS가 시작점에 고정된 채
  매 스텝 확장한다. `step_days` 기본값은 `out_of_sample_days`(OOS 무중첩 연속 타일링).
  OOS 끝이 `date_end`를 넘는 부분 윈도우는 버린다. 윈도우 0건이면 명확한 오류.
- **FR-E02**: 각 윈도우의 IS·OOS 구간을 **독립 실행**한다 — 구간마다 새 브로커·시계로
  `replay`를 돌려, OOS가 IS 포지션의 연장이 아니라 깨끗한 표본 외 검증이 되게 한다.
  IS·OOS 요약은 슬라이스 2의 `build_per_rule_results`+`build_summary`로 만든다(같은 잣대).
- **FR-E03**: 윈도우별 **워크포워드 효율(WFE = OOS 샤프 / IS 샤프)**을 계산한다. IS
  지표가 0 이하면 비율이 무의미하므로 None(N/A)으로 두고 평균에서 제외한다. Sortino·
  수익률에도 같은 비율을 제공한다.
- **FR-E04**: **표본 외 집계**(윈도우별 OOS 지표의 동일가중 평균 — `aggregate_sharpe`
  규약과 동일)를 헤드라인으로 노출한다: 평균 OOS 수익률·샤프·Sortino, 최악 낙폭,
  IS 평균 샤프(나란히 비교용), 평균·중앙값 WFE, 표본 외 수익 윈도우 수.
- **FR-E05**: 과적합 의심 플래그 + 사람이 읽는 사유를 낸다. 신호: (a) 평균 WFE < 임계
  (기본 0.5), (b) IS 평균 샤프는 양(+)인데 OOS 평균 샤프가 0 이하(표본 외 우위 소멸),
  (c) 표본 외 수익 윈도우가 과반 미만.
- **FR-E06**: CLI `auto-invest walk-forward`(`--rules`·`--from`·`--to`·`--in-sample-days`·
  `--out-of-sample-days`·`--step-days`·`--mode`·`--wfe-threshold` + 비용 옵션)로 운영자가
  실행하고, 마크다운 리포트를 출력한다. 과적합 의심 시 종료코드 1.

### 성공 기준 (SC)

- **SC-E01**: 한 윈도우의 OOS 지표가 같은 OOS 날짜 범위를 독립 백테스트한 결과와
  **바이트 동일**하다(하니스가 단일 잣대를 재사용함을 증명 — 헌법 X.2).
- **SC-E02**: 롤링 모드에서 OOS 윈도우가 무중첩 연속 타일링되고, anchored 모드에서 IS
  시작점이 고정·확장된다. 너무 짧은 범위는 명확한 오류.
- **SC-E03**: WFE는 OOS/IS 비율이며 IS 샤프 ≤ 0이면 None. 과적합 플래그가 세 신호에
  정확히 반응한다.
- **SC-E04**: 결정론·회귀 무손상(전체 테스트 통과, 신규 10건). conn 미지정 시 인메모리
  감사 DB로 동작.

### 안전 경계 (Slice 3)

- **오프라인·읽기 전용**: 기존 `replay`를 날짜 부분구간에 재실행할 뿐. 라이브 주문 경로
  무수정, 돈 안 움직임.
- **Kernel 터치 0건**: 손댄 파일 전부 `backtest/walk_forward.py`(신규 비커널)·`cli.py`
  (비커널)·`tests/`·`specs/`. K1~K6·K-meta 무변경. **감사 스키마(K4) 무변경** — 하니스는
  기존 replay 감사 어휘만 쓴다(새 이벤트 없음).

## 후속 슬라이스 (이 스펙 이후)

- 측정 토대 3단계(정직·통일·표본 외 검증)가 끝났다. 다음은 **신호/알파 과학**(다요인·
  레짐 인식)과 **포지션 사이징**(변동성·상관) — 이제 워크포워드로 표본 외 검증을 받으며
  안전하게 개선할 수 있다.
- **후속 K4 (선택)**: Sortino를 `LIVE_PERFORMANCE_SNAPSHOT` 페이로드에 추가해 자율
  튜너(스펙 005)가 하방 위험 시계열을 읽게 한다(K4 추가-전용 터치 1건).

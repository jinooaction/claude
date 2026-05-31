# 스펙 032 계획 — 횡단면 포트폴리오 재조정 엔진 (슬라이스 1)

## 헌법 점검 (Constitution Check)

| 원칙 | 적합성 |
|------|--------|
| I 포지션 캡 | 준수 — 플래너는 수량 제안만, 모든 매수가 기존 K1 게이트 체인 통과(변형 없음). 캡이 천장. |
| II 화이트리스트 | 준수 — whitelist_gate 그대로 적용. |
| III LLM 판단 지점 | 무관 — 순수 수치, LLM 미호출. |
| IV 감사 로그 | 준수 — 백테스트는 기존 ORDER_*/FILL 어휘 그대로 사용, 스키마 무변경. |
| V 시크릿 | 무관 — 시크릿 미접근. |
| VI 단계적 출시 | 준수 — 슬라이스 1은 백테스트(1단계)에서 검증만. 라이브 투입은 후속(운영자 게이트). |
| VII 외부 API | 무관 — 백테스트 데이터 소스만 사용. |
| VIII 변경 규율 | 준수 — SDD, 테스트·린트 통과, 전용 브랜치. |
| IX 자기수정 경계 | 준수 — Kernel 터치 0건(신규 모듈 + 비커널 추가). |
| X 측정 주도 성장 | **핵심 준수** — 산출물이 단일 잣대(`backtest/metrics.py`) 기반 수익률 측정. 라이브=백테스트 동일 정의. |

## 재사용 자산 (새로 만들지 않음)

- `strategy/factors.py::composite_scores` — 유니버스 합성 점수 순위.
- `strategy/sizing.py` — `covariance_matrix`, `min_variance_weights`,
  `max_sharpe_weights`, `erc_weights`, `inverse_vol_group_scale`,
  `realized_volatility`, `expected_returns_from_closes`.
- `risk/gates.py` — whitelist·halt·per-trade·per-symbol·global 게이트 체인.
- `backtest/replay.py` — `_run_gate_chain`, `_ohlcv_to_pricebar`, `BacktestBroker`,
  `ReplayClock`, `HistoricalDataSource`, 게이트 어댑터 패턴.
- `backtest/metrics.py` — total_return/max_drawdown/sharpe/sortino + 회전율 계산.

## 신규 파일

- `src/auto_invest/strategy/rebalance.py` — 순수 플래너.
- `src/auto_invest/backtest/portfolio_replay.py` — 재조정 백테스트 드라이버.
- `tests/unit/test_spec_032_rebalance.py` — 플래너 단위 테스트.
- `tests/integration/test_spec_032_portfolio_replay.py` — 백테스트 통합 테스트.

## 수정 파일 (비커널, 추가 전용)

- `config/rules.py` — `PortfolioRebalanceConfig` 추가.
- `cli.py` — `backtest-portfolio` 명령 추가.

## 설계 메모

- **비중 합 = 1.0, 롱-온리.** 음수·공매도 금지(헌법 도메인). 점수 비례는 점수를
  최소값 기준 양수 평행이동 후 정규화.
- **최적화기 키 변환.** `sizing` 최적화기는 `Mapping[rule_id, Mapping[date, close]]`
  를 받는다. 재조정은 symbol 을 키로 그대로 넘긴다(rule_id 자리에 symbol).
- **게이트 통과.** `rebalance_plan` 이 만든 매수는 `_run_gate_chain` 으로 캡 검증,
  거부면 그 종목 매수만 스킵(나머지 진행). 매도는 whitelist+halt 만(노출 축소).
- **회전율.** `turnover = Σ|체결 명목| / 평균 자산`. 백테스트 리포트에 포함.
- **결정론.** 모든 정렬은 (값, 심볼명). float 중간계산은 최적화기 내부에 한정되고
  경계에서 Decimal 6자리로 정규화(기존 모듈 규약과 동일).

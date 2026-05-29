**상태**: 진행 중
**브랜치**: `claude/spec-019-regime-erc`
**선행 스펙**: 016(워크포워드 검증), 017(변동성 사이징), 018(다요인 신호)

## 배경

스펙 018로 신호 레이어(모멘텀·볼린저밴드)가 완성됐다. 세계 최고 수준 퀀트 시스템과의
다음 격차 두 가지:

1. **레짐 인식 (Regime Detection)** — 추세·횡보·하락 3상태를 감지해 신호 강도를
   자동 조절. 하락장에서 진입 신호를 줄이고 추세장에서 신호를 강화한다.
2. **완전 공분산 ERC (Equal Risk Contribution)** — 역변동성 근사 대신 자산 간
   공분산 행렬을 반영한 반복 최적화로 진짜 등기여 위험 배분.

두 기능이 함께 시너지를 낸다: 레짐 필터가 어떤 환경인지 알려주면, ERC 사이징이
그 환경에서 위험을 균등 배분한다. 반드시 스펙 016 walk-forward 표본 외 검증 통과.

## 슬라이스 1: 레짐 감지기

### 기능 요구사항

- **FR-R01**: `strategy/regime.py` 에 `RegimeDetector` 클래스 추가 (비커널).
- **FR-R02**: 3상태 — `TRENDING`(추세), `RANGING`(횡보), `BEAR`(하락).
  `Regime` 열거형으로 정의.
- **FR-R03**: 판별 로직 (모두 Decimal, 결정론적):
  - BEAR: `close < sma(200)` AND `close < sma(50)` — 장기·중기 이평선 아래.
  - TRENDING: `close > sma(50)` AND `sma(50) > sma(200)` — 골든크로스 상태.
  - RANGING: 그 외 (두 조건 중 어느 쪽도 아님).
  - `close` 는 시장 전체 대표 기준봉(마켓 인덱스). 개별 종목이 아닌 KOSPI/SPY 같은
    인덱스 시계열을 받는다.
- **FR-R04**: `detect(bars: list[PriceBar]) -> Regime`. 200막대 미만이면 RANGING
  반환(fail-safe, 데이터 부족 시 중립).
- **FR-R05**: `RegimeSignalScale` 매핑 — 레짐별 신호 배율:
  - TRENDING: 1.0 (전체 신호 강도 유지)
  - RANGING: 0.7 (30% 줄임)
  - BEAR: 0.3 (70% 줄임)
  - 기본값이며 룰셋 YAML 로 오버라이드 가능 (`regime_signal_scale` 필드, Optional).
- **FR-R06**: `apply_regime_scale(qty: int, scale: Decimal) -> int` — qty × scale
  내림 정수. qty=0 이면 0 반환.

### 성공 기준

- **SC-R01**: BEAR 조건 데이터 → `detect()` = BEAR.
- **SC-R02**: 골든크로스 조건 → `detect()` = TRENDING.
- **SC-R03**: 200막대 미만 → `detect()` = RANGING (fail-safe).
- **SC-R04**: `apply_regime_scale(100, Decimal("0.3"))` = 30.

## 슬라이스 2: 완전 공분산 ERC

### 기능 요구사항

- **FR-E01**: `sizing.py` 에 `covariance_matrix(closes_by_rule, lookback_bars)`
  추가. 공통 날짜 교집합 위에서 표본 공분산 행렬(Decimal) 계산. Decimal 6자리 정규화.
- **FR-E02**: `erc_weights(cov_matrix: list[list[Decimal]], tol, max_iter) -> list[Decimal]`
  — 반복 최적화(Maillard 2010 방법론). 각 자산의 marginal risk contribution이
  동일하도록 반복(기본 `tol=1e-8`, `max_iter=500`). 합산 1.0 정규화.
  수렴 실패 시 `ERCConvergenceError` 예외.
- **FR-E03**: `sizing_mode="erc"` — `SizingConfig` 모드에 추가.
  `group_scale_for` 가 `erc` 모드일 때 ERC 가중치를 반환하도록 확장.
- **FR-E04**: ERC 가중치는 Down-only — 최대 1 클램핑 유지. K1 caps 여전히 후처리.
- **FR-E05**: 공분산 행렬 계산 불가(데이터 부족, 공통 날짜 < 30일) 시 역변동성
  fallback(기존 `inverse_vol_group_scale`).

### 성공 기준

- **SC-E01**: 동일 분산 자산 3개 → ERC 가중치 [1/3, 1/3, 1/3].
- **SC-E02**: 한 자산 분산 4배 → 해당 자산 가중치 약 1/2 로 감소.
- **SC-E03**: 공분산 데이터 부족(< 30 공통일) → fallback 역변동성 가중치 반환.
- **SC-E04**: 기존 `inverse_vol` 테스트 전부 통과.

## 슬라이스 3: walk-forward 표본 외 검증

### 기능 요구사항

- **FR-W01**: `tests/backtest/test_regime_erc_walkforward.py` — 합성 데이터로
  레짐 필터 + ERC 사이징 조합의 walk-forward 검증 실행.
- **FR-W02**: `WalkForwardReport.avg_oos_sharpe >= 0` (음수 OOS 샤프 불합격).
- **FR-W03**: `WalkForwardReport.pct_profitable_oos_windows >= 0.5` (OOS 수익 윈도우 50% 이상).
- **FR-W04**: 레짐 없음(baseline) vs 레짐 있음 비교 — 레짐 필터가 BEAR 구간에서
  실제로 qty 를 줄이는지 단위 검증.

### 성공 기준

- **SC-W01**: walk-forward 검증 테스트 `pytest -q` 통과 (PASS).
- **SC-W02**: `pct_profitable_oos_windows >= 0.5` 조건 통과.
- **SC-W03**: 레짐 BEAR 구간 qty 감소 확인 테스트 통과.

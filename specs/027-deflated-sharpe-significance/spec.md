# 스펙 027 — 다중검정 보정 통계: 디플레이티드 샤프 비율 (Deflated Sharpe Ratio)

## 한 줄 요약

백테스트·워크포워드의 샤프 비율을 (1) **표본 길이**와 (2) **수익률 비정규성**(왜도·
첨도), (3) **시도한 설정 개수**(다중검정)로 보정해, "이 우위가 통계적으로 진짜인가,
아니면 여러 번 시도해서 우연히 좋아 보이는 것뿐인가?"를 답하는 통계 모듈을 추가한다.
Bailey & López de Prado(2014)의 확률적 샤프(PSR)·디플레이티드 샤프(DSR)·최소
트랙레코드 길이(MinTRL)를 구현하고, 기존 워크포워드 과적합 탐지기에 옵트인으로 배선한다.

## 배경 — 세계 최고 수준 격차

스펙 016 슬라이스 1·2·3이 백테스트를 **정직**(거래비용)·**통일**(단일 잣대)·**표본 외
검증**(워크포워드)되게 만들었다. 하지만 측정 토대에 마지막 한 조각이 빠져 있다:
**다중검정/백테스트 과적합 보정**이다.

- 워크포워드 효율(`WFE = 표본외 샤프 / 표본내 샤프`)은 **한 설정**의 표본 외 안정성만
  본다. "팩터 N개를 시도해 좋아 보이는 3개를 남겼다"의 **선택 편향**은 못 잡는다.
- 이 시스템은 알파 팩터를 계속 추가하고(`strategy/factors.py`에 모멘텀·퀄리티·
  저변동성·평균회귀) 자율 튜너가 후보를 계속 시도한다 — 정확히 다중검정 편향에
  노출되는 구조다.
- 샤프 비율은 또한 **수익률이 정규분포가 아닐 때**(음의 왜도·뚱뚱한 꼬리) 위험을
  과소평가한다. 표본 길이가 짧으면 추정 오차도 크다. 단순 샤프 숫자 하나로는 이
  세 불확실성을 구분할 수 없다.

세계 최고 수준 계량 투자(López de Prado류)는 샤프를 그대로 믿지 않고 **디플레이티드
샤프 비율**로 보정한다: "내가 N개의 설정을 시도했다는 사실을 감안하면, 관측된 샤프가
실제로 0보다 클 확률은 얼마인가?" 이것이 헌법 원칙 X(측정 기반·추측 금지)·스펙 016
(정직한 백테스트)이 막으려던 "환상을 최적화하는" 실패를 정량적으로 차단하는 마지막
규율이다.

## 접근

새 모듈 `backtest/significance.py`(비커널, 순수·결정론적)가 다음을 한다. 입력은
`metrics.py`의 `sharpe_ratio`·`sortino_ratio`와 **같은 일별 수익률 시계열**이라 잣대가
갈라지지 않는다(헌법 X.2).

1. **표본 적률**: `sample_skewness`(왜도 γ3)·`sample_kurtosis`(비초과 첨도 γ4, 정규=3).
2. **확률적 샤프 비율(PSR)** — Bailey-LdP:
   `PSR(SR*) = Φ( (SR_hat − SR*)·√(n−1) / √(1 − γ3·SR_hat + (γ4−1)/4·SR_hat²) )`
   여기서 `SR_hat`은 **기간당**(비연율) 샤프, `SR*`은 기준 샤프, `Φ`는 표준정규 누적
   분포. 분모는 샤프 추정량의 표준오차(Lo/Mertens) — 정규 수익률이면 `√(1+SR²/2)`.
3. **최소 트랙레코드 길이(MinTRL)**: PSR이 목표 신뢰수준(기본 95%)을 넘기는 데 필요한
   최소 관측 수. `MinTRL = 1 + (1 − γ3·SR + (γ4−1)/4·SR²)·(Z_conf/(SR_hat−SR*))²`.
4. **기대 최대 샤프(SR_0)** — N개 시도의 다중검정 디플레이션 기준선:
   `SR_0 = √V·[(1−γ)·Φ⁻¹(1−1/N) + γ·Φ⁻¹(1−1/(N·e))]`
   (γ=오일러-마스케로니 ≈ 0.5772, e=오일러 수, V=시도한 샤프들의 분산). N≤1이면 0
   (선택 편향 없음).
5. **디플레이티드 샤프 비율(DSR)**: 기준선을 0이 아니라 SR_0으로 둔 PSR.
   `DSR = PSR(benchmark = SR_0)`. N=1이면 DSR = PSR(0)으로 환원된다.

`Φ`·`Φ⁻¹`은 외부 라이브러리(scipy) 없이 표준 라이브러리로 구현한다(공급망 표면 최소,
R-B11 정신): `Φ`는 `math.erfc`, `Φ⁻¹`은 Acklam 유리근사. 내부 연산은 numpy float,
경계에서 Decimal 6자리 정규화(`canonicalise_decimal`).

배선: 기존 `backtest/walk_forward.py`의 과적합 탐지기에 **표본 외 풀(pooled OOS)
트랙레코드**의 PSR·MinTRL·(옵션)DSR을 추가한다. 표본 외 윈도우는 기본적으로 연속
타일링되므로 윈도우별 표본 외 일별 수익률을 이어 붙이면 하나의 연속 표본 외 트랙이
된다. CLI `auto-invest walk-forward`에 `--num-trials`·`--trial-sharpe-std`·`--min-psr`·
`--min-dsr` 옵션을 추가한다.

## 기능 요구사항 (FR)

- **FR-S01**: `backtest/significance.py`에 `sample_skewness`·`sample_kurtosis`·
  `probabilistic_sharpe_ratio`·`minimum_track_record_length`·`expected_max_sharpe`·
  `deflated_sharpe_ratio`·`deflated_sharpe_ratio_from_trial_sharpes` 추가. 전부 순수·
  결정론적, Decimal 6자리 정규화.
- **FR-S02**: `Φ`(`_norm_cdf`)·`Φ⁻¹`(`_norm_ppf`)을 표준 라이브러리로 구현(scipy
  의존 없음).
- **FR-S03**: 기준 샤프 입력은 **연율** 단위로 받아 내부에서 기간당으로 환산(÷√252)
  — `metrics.sharpe_ratio`의 연율 규약과 단일 잣대.
- **FR-S04**: `WalkForwardReport`에 표본 외 풀 트랙의 `oos_sharpe_annual`·`oos_skew`·
  `oos_kurtosis`·`oos_n_obs`·`oos_psr`·`oos_min_track_record_obs`·`oos_dsr`·
  `oos_expected_max_sharpe_annual`·`num_trials` 필드 추가(전부 기본값 있음).
- **FR-S05**: `run_walk_forward`에 `num_trials=1`·`trial_sharpe_std_annual=None`·
  `min_psr=None`·`min_dsr=None` 매개변수 추가. **기본값에서 기존 동작과 byte 동일**
  (새 과적합 사유 0건, 기존 `overfit_reasons` 불변).
- **FR-S06**: `min_psr`(또는 `min_dsr`)을 명시하면 표본 외 PSR(또는 DSR)이 그 임계값
  미만일 때 과적합 사유 추가 + 종료코드 1. 옵트인 하드 게이트.
- **FR-S07**: CLI `auto-invest walk-forward`에 `--num-trials`·`--trial-sharpe-std`·
  `--min-psr`·`--min-dsr` 옵션 추가. 마크다운 리포트에 "통계적 유의성" 섹션 추가.

## 합격 기준 (SC)

- **SC-01**: `PSR(SR* = SR_hat)`은 정확히 0.5(기준선이 관측 샤프와 같으면 5:5).
- **SC-02**: PSR은 관측 샤프에 대해 단조 증가한다(높은 샤프 → 높은 확률).
- **SC-03**: 대칭(정규에 가까운) 수익률에서 왜도 ≈ 0, 첨도 ≈ 3.
- **SC-04**: 음의 왜도·뚱뚱한 꼬리는 같은 샤프라도 PSR을 **낮춘다**(꼬리 위험 반영).
- **SC-05**: MinTRL은 양의 샤프·기준 0에서 양수이고, 관측 수가 MinTRL일 때 PSR ≈
  목표 신뢰수준이다.
- **SC-06**: `expected_max_sharpe`는 시도 수 N이 커질수록 증가한다(다중검정 디플레이션
  강화). N≤1이면 0.
- **SC-07**: `deflated_sharpe_ratio(num_trials=1)` == `probabilistic_sharpe_ratio
  (benchmark=0)`. N>1이면 DSR < PSR(디플레이션이 확률을 낮춘다).
- **SC-08**: `deflated_sharpe_ratio_from_trial_sharpes`가 시도 샤프 횡단면에서 N과
  분산 V를 직접 계산해 같은 DSR을 낸다.
- **SC-09**: 워크포워드 기본 호출(`num_trials=1`, `min_psr=None`)은 기존 `overfit_reasons`
  와 판정을 **불변**으로 유지(회귀 무손상).
- **SC-10**: `min_psr` 옵트인 시 표본 외 PSR이 임계 미만이면 과적합 사유 추가 + 종료
  코드 1. 마크다운에 PSR·MinTRL·DSR이 표면화된다.
- **SC-11**: 관측 < 2(또는 표준편차 0)면 PSR·MinTRL·DSR은 `None`(fail-safe, 크래시
  없음).

## 안전 경계

- **Kernel 터치 0건**: `risk/gates.py`(K1)·`persistence/audit.py`(K4) 등 커널 무변경.
  전부 `backtest/significance.py` 신규 + `backtest/walk_forward.py`·`cli.py` 비커널.
- **오프라인·읽기 전용**: 기존 수익률 시계열에 대한 순수 통계 계산. 라이브 주문 경로
  무수정, 돈 안 움직임, 감사 로그 append 0건.
- **옵트인·하향 전용 게이트**: 기본값에서 기존 동작 byte 동일. `min_psr`/`min_dsr`은
  과적합 **경고만** 추가(거래 차단·노출 변경 없음). 운영자가 더 엄격한 통과 기준을
  거는 도구일 뿐.
- **결정론적 Decimal**: 6자리 정규화 — 백테스트 byte-equality(FR-B15)·단일 잣대(헌법
  X.2) 보존.
- **LLM 미사용**: 순수 수치 계산(헌법 III 무관).
- **공급망 최소**: scipy 등 신규 의존성 0건(numpy + 표준 라이브러리만, R-B11 정신).
- **dry-run 그대로**: 실거래 전환과 무관.

## 검증

`auto-invest walk-forward ... --num-trials N --trial-sharpe-std S --min-dsr 0.95`로
"내가 N개 설정을 시도했다"는 사실을 감안한 디플레이티드 샤프를 보고받는다. 새 알파/
사이징 작업은 이제 표본 외 검증(WFE)에 더해 **통계적 유의성**(PSR/DSR)까지 통과해야
한다 — 환상을 최적화하지 않는 마지막 게이트.

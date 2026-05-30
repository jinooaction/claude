# HANDOFF 037 — 스펙 027: 디플레이티드 샤프 비율 (다중검정 보정 통계, 2026-05-30)

main 머지 커밋 **`ec1d040`** (PR #114). 세계 최고 수준 측정 토대의 **마지막 조각** —
백테스트·워크포워드의 샤프 비율을 (1) 표본 길이, (2) 수익률 비정규성(왜도·첨도),
(3) 시도한 설정 개수(다중검정)로 보정하는 통계를 추가했다.

## 왜 1순위였나 (세계 최고 수준 격차)

스펙 016이 백테스트를 **정직**(거래비용)·**통일**(단일 잣대)·**표본 외 검증**(워크
포워드)되게 만들었지만, 측정 토대에 **다중검정/백테스트 과적합 보정**이 빠져 있었다.

- 워크포워드 효율(`WFE = 표본외 샤프 / 표본내 샤프`)은 *한 설정*의 표본 외 안정성만
  본다. "팩터 N개를 시도해 좋아 보이는 3개를 남겼다"의 **선택 편향**은 못 잡는다.
- 이 시스템은 알파 팩터를 계속 추가하고(모멘텀·퀄리티·저변동성·평균회귀, 스펙
  018·021·023·025) 자율 튜너가 후보를 계속 시도한다 — 정확히 다중검정 편향 구조.
- 헌법 원칙 X(측정 기반·추측 금지)·스펙 016(정직한 백테스트)이 막으려던 "환상을
  최적화하는" 실패를 정량적으로 차단하는 마지막 규율.

## 무엇을 했나

- **`backtest/significance.py`(신규, 비커널)** — Bailey & López de Prado(2014):
  - `probabilistic_sharpe_ratio`(PSR): 표본 길이·왜도·첨도를 감안한 "참 샤프 > 기준선"
    확률. 비정규성(뚱뚱한 꼬리·음의 왜도)을 벌점.
  - `minimum_track_record_length`(MinTRL): PSR이 목표 신뢰수준(기본 95%)을 넘기는 데
    필요한 최소 관측 수.
  - `expected_max_sharpe`(SR_0): N개 시도의 기대 최대 샤프(다중검정 디플레이션 기준선,
    극단값 이론 Gumbel 근사). N≤1이면 0.
  - `deflated_sharpe_ratio`(DSR): 기준선을 0이 아니라 SR_0으로 둔 PSR. N=1이면
    PSR(0)으로 환원.
  - `deflated_sharpe_ratio_from_trial_sharpes`: 시도한 모든 설정의 샤프 횡단면에서
    N·분산을 직접 계산.
  - `Φ`/`Φ⁻¹`은 **scipy 없이** 표준 라이브러리(`math.erfc` + Acklam 유리근사)로 구현
    (공급망 표면 최소, R-B11 정신). 입력은 `metrics.sharpe_ratio`와 같은 일별 수익률
    시계열(헌법 X.2 단일 잣대).
- **`backtest/walk_forward.py`(비커널)** — 표본 외 풀(pooled OOS) 트랙(윈도우별 표본 외
  일별 수익률을 이어 붙인 하나의 연속 트랙)의 PSR·MinTRL·DSR을 과적합 탐지기에 배선.
  `WalkForwardReport`에 통계 필드 9개 추가. `num_trials`·`trial_sharpe_std_annual`·
  `min_psr`·`min_dsr` 매개변수.
- **`cli.py`(비커널)** — `auto-invest walk-forward`에 `--num-trials`·`--trial-sharpe-std`·
  `--min-psr`·`--min-dsr` 옵션 + 마크다운 "통계적 유의성" 섹션.

## 안전 경계

- **Kernel 터치 0건** — `risk/gates.py`(K1)·`persistence/audit.py`(K4) 등 커널 무변경.
  전부 `backtest/significance.py` 신규 + `backtest/walk_forward.py`·`cli.py` 비커널 +
  `tests/`·`specs/`.
- **오프라인·읽기 전용·순수 결정론적** Decimal 6자리. 라이브 주문 경로·감사 스키마
  무관, 돈 안 움직임.
- **기본값에서 기존 워크포워드 동작과 byte 동일**(새 과적합 사유 0건) — `--min-psr`/
  `--min-dsr`은 옵트인 하드 게이트(과적합 경고만 추가, 거래 차단·노출 변경 없음).
- **LLM 미사용**. dry-run 그대로.

## 검증

- 신규 테스트 **32건**: 표준정규 `Φ`/`Φ⁻¹` 정확도, SC-01(PSR=0.5 경계)·SC-02(단조성)·
  SC-03(왜도/첨도)·SC-04(음의 왜도 PSR 하락)·SC-05(MinTRL 성질+라운드트립)·SC-06(SR_0
  단조성)·SC-07(DSR 환원/디플레이션)·SC-08(횡단면)·SC-09(워크포워드 기본 회귀 무손상)·
  SC-10(옵트인 게이트)·SC-11(fail-safe).
- 전체 **1250 통과**, 4 스킵, 린트 깨끗.

## 사용법

```bash
# "설정 20개를 시도했고 그 샤프 표준편차가 0.8" 이라는 사실을 감안한 디플레이티드 샤프:
auto-invest walk-forward --rules config/rules.toml --from 2024-01-02 --to 2024-12-31 \
  --in-sample-days 180 --out-of-sample-days 60 \
  --num-trials 20 --trial-sharpe-std 0.8 --min-dsr 0.95
```

## 다음 후보 (스펙 027 이후)

- **거래비용 인식 포트폴리오 최적화** — 스펙 022·024 최적화 목적식에 회전율/거래비용
  페널티 추가(비용 모델은 스펙 016에 이미 있는데 최적화가 안 씀).
- **팩터별 정보계수(IC)·알파 감쇠 측정** — 각 신호의 예측력·반감기 정량화(PSR/DSR 보완).
- **튜너에 DSR 게이트 배선** — 자율 튜너 후보 평가에 `deflated_sharpe_ratio_from_trial_sharpes`
  를 연결해, 다중검정 보정 후 유의한 후보만 통과시키기.
- **실거래 전환** — `AUTO_INVEST_MODE=live` 토글(운영자 명시 지시 필요, 돈 움직임).

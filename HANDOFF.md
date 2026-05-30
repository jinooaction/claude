# auto-invest — 다음 세션 인수인계 (main 베이스라인)

이 파일은 이 저장소의 **`main` 브랜치에서 시작하는 모든 Claude 세션**의 진입점입니다. "지금 무슨 일이 일어나고 있는지"를 토큰 낭비 없이 빠르게 파악할 수 있도록 정리했습니다.

## 세션 시작 절차 (필수)

`CLAUDE.md`의 "운영자 응대 3대 규칙" + "Session lifecycle" 정책에 따라, 모든 새 세션은 계획을 세우거나 운영자에게 무엇을 할지 물어보기 **전에** 현재 상태를 사실로 맞춥니다. v3.3.0부터 이 절차의 대부분이 자동화됐습니다:

1. **자동(로컬)** — `.claude/hooks/git_ground_truth.py` 세션 시작 훅이 매 세션 라이브 git 상태를 출력합니다: 현재 브랜치·HEAD·작업트리 청결도·`origin/main` 대비 앞뒤·최근 `origin/main` 커밋·HANDOFF 파일 최신순. **산문으로 적힌 "active feature" 줄보다 이 블록을 더 신뢰하세요.**
2. **`/sync` 실행(네트워크)** — 훅은 절대 멈추면 안 되므로 로컬 정보만 냅니다. 네트워크 발견은 `/sync` 스킬이 담당합니다: `git fetch`, 원격 `claude/*` 브랜치 목록, 열린 PR 목록(`mcp__github__list_pull_requests`), 각 브랜치의 살아있는 HANDOFF 읽기, `main` 실제 최신과 대조. 무엇이 머지됐고 무엇이 진행 중인지 불확실하면 세션 시작에 한 번 돌리세요.

`/sync`가 자동화하는 옛 수동 절차(참고):

```bash
git fetch origin
git ls-remote --heads origin 'claude/*' | awk '{print $2}'
# + mcp__github__list_pull_requests owner=jinooaction repo=claude state=open
# + git show origin/<브랜치>:HANDOFF-<NNN>.md   (각 브랜치의 살아있는 HANDOFF)
# + git log origin/main -8 --pretty='%h %s'      (main 실제 최신)
```

열린 PR이 진행 중인 브랜치를 가리키면 main에서 새 브랜치를 만들지 말고 그 브랜치를 `git checkout` 후 `git pull --ff-only` 하세요.

## 운영자 응대 3대 규칙 (CLAUDE.md v3.2.0 — 절대 어기지 마세요)

1. **응답은 무조건 한글**. 새 세션 시작, 상태 보고, 작업 요약, 사과, 질문 — 예외 없음. 영어 응답은 운영자가 이해 못합니다.
2. **약어와 영어 비즈니스 용어 금지, 쉬운 한글로 풀어 써라**. 코드/식별자/파일 경로 같은 고유명은 그대로 두되 반드시 한글 설명을 옆에 붙입니다. 한 문장에 영어 단어 3개 이상이면 다시 씁니다.
3. **자동 머지** — 작업 완료 + 테스트 통과 + 린트 깨끗 + PR `mergeable_state=clean` 만족 시 운영자가 "머지해"라고 말하지 않아도 즉시 자동 머지. 매번 머지 명령 요청하는 것 자체가 헌법 IX.D가 제거하려던 동기 핸드오프 비용입니다.

상세 규칙은 `CLAUDE.md` 본문 참조.

## 최근 마일스톤 — 2026-05-30 (스펙 027: 디플레이티드 샤프 비율 — 다중검정 보정)

main 머지 커밋 `ec1d040` (PR #114). **세계 최고 수준 측정 토대의 마지막 조각** —
백테스트·워크포워드 샤프를 표본 길이·수익률 비정규성(왜도·첨도)·시도한 설정 개수
(다중검정)로 보정하는 통계를 추가했다. Bailey & López de Prado(2014). 자세히는
`HANDOFF-037-SPEC-027-DEFLATED-SHARPE.md`. 한 줄 요약:

- **배경**: 워크포워드(WFE)는 *한 설정*의 표본 외 안정성만 본다. "팩터 N개를 시도해
  좋아 보이는 것을 남겼다"의 선택 편향(데이터 마이닝)은 못 잡는다 — 알파 팩터를 계속
  추가하는 이 시스템의 가장 큰 과학적 격차였다.
- **`backtest/significance.py`(신규, 비커널)**: 확률적 샤프(PSR)·최소 트랙레코드 길이
  (MinTRL)·기대 최대 샤프(SR_0)·디플레이티드 샤프(DSR) + 시도 샤프 횡단면 버전.
  `Φ`/`Φ⁻¹`은 scipy 없이 표준 라이브러리로 구현(공급망 표면 최소). 입력은
  `metrics.sharpe_ratio`와 같은 일별 수익률 시계열(헌법 X.2 단일 잣대).
- **`backtest/walk_forward.py`·`cli.py`(비커널)**: 표본 외 풀 트랙의 PSR·MinTRL·DSR을
  과적합 탐지기에 배선. `auto-invest walk-forward`에 `--num-trials`·`--trial-sharpe-std`·
  `--min-psr`·`--min-dsr` 옵션.
- **안전 경계**: Kernel 터치 0건. 오프라인·읽기 전용·순수 결정론적. 기본값에서 기존
  워크포워드 동작과 byte 동일(새 과적합 사유 0건) — `--min-psr`/`--min-dsr`은 옵트인
  하드 게이트. LLM 미사용. dry-run 그대로.
- **검증**: 신규 테스트 32건(SC-01~SC-11 + 표준정규 정확도 + 배선), 전체 1250 통과,
  4 스킵, 린트 깨끗.

## 이전 마일스톤 — 2026-05-30 (캐너리 실체결 자본 + 자동 승격 게이트, 선택 1·2)

운영자 지시 "1번·2번 모두 자율진행"을 완료. PR #110~#112. 자세히는
`HANDOFF-036-CANARY-CAPITAL-AND-PROMOTION-GATE.md`. 한 줄 요약:

- **선택 1번(실제 체결)**: 자본 $12,000 + 축소 룰셋(`deploy/canary-live-rules.toml`,
  qty=1 SPY·MSFT·AAPL CANARY) 적용. per-trade 5% 캡($600) 안에 우량주 1주가 들어
  실제 체결 가능(첫 기회 다음 정규장). go-live 사이드카 `armed_live_canary` 확인.
  부수 수정: `record_stop` 종료 경로 best-effort(닫힌 DB 트레이스백 제거) + 헬스체크를
  현재 인스턴스 로그만 보도록 격리(재시작 전환기 오탐 제거).
- **선택 2번(자동 승격, 안전 경로)**: 스펙 026 — `promotion/gate.py`(순수·결정론적
  헌법 VI 게이트 6조건) + `readiness.py`(라이브 audit_log 측정) + CLI `promote-check`
  + 매일 `promote-readiness.yml`(서버 평가 → 사이드카 발행). **승격 수행은 안 함**
  (보고 전용). 실제 풀라이브는 VI 게이트 AND 스펙 007 하드닝 캐너리(IX.B-2) 둘 다
  통과해야 발화 — 최소 30거래일 후. 검증 안 된 자동화로 전자본을 미리 발화시키지
  않기 위한 의도적 게이트.
- **검증**: 신규 테스트 14건, 전체 1229 통과, 린트 깨끗.

## 이전 마일스톤 — 2026-05-30 (🟢 실거래 전환: 라이브 캐너리 무장 + 헌법 X.4 개정)

운영자(mason) 지시 "실거래 전환해 … 자동전환 가능하도록 헌법을 고쳐 … 캐너리
소액부터"를 자율 수행으로 완료. PR #105~#108. 자세히는
`HANDOFF-035-GO-LIVE-CANARY.md`. 한 줄 요약:

- **헌법 X.4 개정(v4.0.0, K-meta, PR #105 `d52b048`)**: "라이브 전환 절대 자동 금지"를
  **운영자 지시 시 라이브 캐너리까지만 가드형 채널로 자율 전환 허용**으로 재정의.
  풀라이브 승격(VI 3단계)·장중가드(VIII.A)·K1 캡(I)·화이트리스트(II)·감사(IV)·시크릿(V)
  전부 보존. 운영자 지시 없으면 여전히 자동 전환 0(스펙 005 튜너 불가).
- **가드형 go-live 채널**: `deploy/go-live-canary.sh`(장중 가드 → `.env` 모드만 live →
  워커 재시작 → 헬스체크 → 실패 시 dry-run 자동 복구) + `.github/workflows/go-live-canary.yml`
  (운영자 원클릭 `workflow_dispatch` 또는 센티넬 `automation/go-live-canary.request` 머지).
  결과는 `automation/go-live-last-run` 사이드카로 컨테이너에서 확인.
- **결과**: `GO_LIVE_RESULT=armed_live_canary`(run #3, 커밋 `c286310`). 워커가 라이브
  모드 가동(자본 $100, 캐너리 룰셋). run #2의 헬스 오탐(재시작 전 로그 매칭)은 헬스체크를
  재시작 이후 로그로 한정해 해결. **per-trade 5% 캡 + $100이라 블루칩 1주가 캡 초과 →
  실질 체결 거의 0(라이브 경로 검증됨, 노출 극소). 첫 주문 기회는 다음 정규장.**
- **현재 노출 / 다음**: 실질 ~$0. 진짜 캐너리 체결을 보려면 자본 상향(운영자 결정).
  풀라이브는 여전히 운영자 전용. dry-run 으로 되돌리려면 go-live-canary.sh 역(또는
  서버 `.env` 한 줄).

## 최근 마일스톤 — 2026-05-30 (스펙 025: 다요인 합성 알파 점수 필터)

PR #103 머지 커밋 `127ca3f`. **여러 팩터(모멘텀·퀄리티·저변동성·평균회귀)를
횡단면 z-점수 가중합(하나의 합성 점수)으로 결합해 유니버스를 순위 매기는 옵트인
필터를 추가**했습니다. 스펙 021(모멘텀 단일)·023(퀄리티 단일) 필터를 일반화 — 단일
팩터를 순차 적용할 때 버려지던 교차-팩터 정보를 보존해 "여러 면에서 두루 좋은"
종목을 "한 면에서만 극단적인" 종목보다 선호합니다(세계 최고 수준 멀티팩터 합성).
자세히는 `HANDOFF-034-SPEC-025-COMPOSITE-FACTOR.md`. 한 줄 요약:

- **`strategy/factors.py`(신규, 비커널)**: `zscore()` 횡단면 표준화(모집단 표준편차,
  동일값이면 전부 0) + `composite_scores()` 가중합 순위. 활성 팩터(가중치≠0)만 계산,
  데이터 부족 심볼은 `-Inf` 센티넬로 맨 뒤.
- **`config/rules.py`(비커널)**: `CompositeFactorFilter` 모델 + `KNOWN_COMPOSITE_FACTORS`
  + `TradingRule.composite_filter`(None이면 byte 동일).
- **`execution/order_router.py`·`backtest/replay.py`(비커널)**: 퀄리티 필터 이후 적용 →
  `SKIPPED_BY_COMPOSITE`. 백테스트는 세션 날짜 이하 바만 사용(미래 참조 방지).
- **안전 경계**: Kernel 터치 0건. 하향 전용(스킵만, K1 불변). 옵트인. 결정론적
  Decimal(라이브=백테스트 단일 잣대, 헌법 X.2). LLM 미사용. dry-run 그대로.
- **검증**: 신규 테스트 12건(SC-01~SC-10), 전체 1215 통과, 4 스킵, 린트 깨끗.
  SC-02 핵심 증명: 저변동성 결합 시 매끄러운 종목이 변동성 큰 최고-모멘텀 종목을 추월.

## 이전 마일스톤 — 2026-05-29 (스펙 024: 최대 샤프 포트폴리오 최적화)

PR #101 머지 커밋 `86b2c32`. **모멘텀 신호를 기대 수익률 μ로 활용해 평균-분산 전선에서 최대 샤프 포인트를 직접 구하는 `mode="max_sharpe"` 사이징 모드를 추가**했습니다.

- **`strategy/sizing.py`(비커널)**: `expected_returns_from_closes()` — 공통 거래일 기준 롤링 평균 로그 수익률(연율화). `max_sharpe_weights(cov, μ)` — `w* ∝ Σ^{-1}·μ` (numpy linalg.solve). μ 전부 비양수 → 균등 가중치 fail-safe. `max_sharpe_group_scales()` — ERC/min_variance와 동일 인터페이스, 수치 실패 → min_variance → ERC → 역변동성 fallback 체인.
- **`config/rules.py`(비커널)**: `SizingConfig.mode`에 `"max_sharpe"` 추가.
- **`execution/order_router.py`·`backtest/replay.py`(비커널)**: `mode in ("erc", "min_variance", "max_sharpe")` 통합 분기.
- **안전 경계**: Kernel 터치 0건. max 1 클램핑(하향 전용). 옵트인. 결정론적 Decimal(헌법 X.2).
- **검증**: 신규 테스트 8건(SC-01~SC-08), 전체 1203 통과, 4 스킵, 린트 깨끗.

## 이전 마일스톤 — 2026-05-29 (스펙 023: 가격 기반 퀄리티 팩터 필터)

PR #100 머지 커밋 `674c8dc`. 롤링 샤프 / (1 + |최대 드로다운|) 합성 점수로 유니버스를 순위 매겨 하위 종목을 `SKIPPED_BY_QUALITY`로 차단. `QualityFilter(top_n/top_pct)` 옵트인. Kernel 터치 0건. 신규 테스트 8건, 전체 1195 통과.

## 이전 마일스톤 — 2026-05-29 (스펙 022: 최소 분산 포트폴리오 최적화)

PR #99 머지 커밋 `204dfc9`. `mode="min_variance"` 분석적 해(`w* = Σ^{-1}·1`). ridge 정규화, 음수 클램핑, ERC→역변동성 fallback. Kernel 터치 0건. 신규 테스트 8건, 전체 1187 통과.

## 이전 마일스톤 — 2026-05-29 (스펙 021: 횡단면 모멘텀 순위 필터)

PR #97 머지 커밋 `2bd01b1`. **세계 최고 수준과의 가장 큰 격차 해소 — 전체 유니버스를 N-기간 수익률로 순위 매겨 상위 N개 또는 상위 P% 종목에만 매수를 허용하는 횡단면 랭킹 필터(Jegadeesh-Titman 모멘텀 팩터)**를 추가했습니다.
기존 시스템은 종목별 독립 룰이었으나, 이 스펙은 유니버스 전체를 한 번에 보고 "지금 가장 강한 종목"만 선택합니다. 자세히는 `specs/021-cross-sectional-ranking/spec.md`. 한 줄 요약:

- **`strategy/ranking.py`(신규, 비커널)**: `cross_sectional_momentum(symbol_bars, period)` — 유니버스 전체를 N-기간 수익률 내림차순 정렬. 바 부족 심볼은 맨 뒤(-Inf 센티넬). `is_top_n(symbol, ranked, n)` / `is_top_pct(symbol, ranked, pct)` 필터 헬퍼.
- **`config/rules.py`(비커널)**: `RankingFilter` Pydantic 모델(`universe`, `period`, `top_n` or `top_pct`). `TradingRule.ranking_filter` 선택적 필드 추가. `top_n`과 `top_pct` 중 정확히 하나만 설정(검증). 옵트인: `None`이면 기존 경로 byte 동일.
- **`execution/order_router.py`(비커널)**: 레짐 배율 이후, 판단 이전에 랭킹 필터 삽입. 유니버스 전체 심볼 바를 DB에서 조회 → 순위 계산 → 미통과 시 `SKIPPED_BY_RANKING(not_in_top)`.
- **`backtest/replay.py`(비커널)**: 각 세션 날짜 루프에서 세션 날짜까지의 바만 사용(미래 참조 방지)하며 동일 필터 적용.
- **안전 경계**: Kernel 터치 0건. 하향 전용(스킵만, 수량 증가 없음). 옵트인(기존 룰 byte 동일). 결정론적 Decimal.
- **검증**: 신규 테스트 13건(SC-01~SC-06 + 유닛 7건), 전체 1179 통과.

## 이전 마일스톤 — 2026-05-29 (스펙 020: 레짐 배율 + ERC 가중치 거래 루프 실배선)

PR #95 머지 커밋 `cb5dcae`. **스펙 019가 완성한 레짐 감지기·ERC 유틸리티를 실제 거래 루프(order_router·replay)에 연결**했습니다.
배선 전에는 함수가 존재해도 실제 주문/백테스트 수량에 반영되지 않았습니다. 이번 스펙으로 라이브 주문 경로와 백테스트 경로 양쪽에서 레짐 배율·ERC 가중치가 K1 캡 전에 적용됩니다.
자세히는 `specs/020-regime-erc-wiring/spec.md`. 한 줄 요약:

- **`config/rules.py` 확장(비커널)**: `TradingRule`에 `regime_index_symbol`(레짐 판별 인덱스 심볼, 예: "SPY")·`regime_scale`(레짐별 배율 오버라이드 딕셔너리) 선택적 필드 추가. `SizingConfig.mode`에 `"erc"` 추가.
- **`execution/order_router.py` 배선(비커널)**: `_group_scale()`이 `inverse_vol`·`erc` 양 모드 지원. `rule.regime_index_symbol`이 있으면 DB에서 인덱스 바를 읽어 `detect_regime()` 호출 → `apply_regime_scale(qty, scale)` 적용 → qty < 1이면 `SKIPPED_BY_SIZING("regime_zero")`. 판단 자문 **전에** 적용(자문은 그 위에서만 줄일 수 있음).
- **`backtest/replay.py` 배선(비커널)**: `_replay_group_scale()`이 `erc` 모드 지원. 레짐 인덱스 심볼을 `symbols_in_use`에 포함하고 SMA-200 필요 때문에 `date.min`부터 전 기간 바 로드. 각 세션 날짜 루프에서 레짐 판별 → `apply_regime_scale` → qty < 1이면 해당 세션 건너뜀.
- **`strategy/sizing.py` 수정(비커널)**: `sized_quantity()` ERC 분기 추가 — `mode="erc"`도 `inverse_vol`과 같은 `group_scale` 경로 사용(호출자가 미리 계산해 전달).
- **안전 경계**: 비커널 전용. K1 caps(`risk/gates.py`) 후처리 변경 없음. 레짐·ERC는 수량을 **줄이거나 건너뛰기만** — K1 위로 노출 증가 불가. 결정론적 Decimal. Kernel 터치 0건. dry-run 그대로.
- **검증**: 신규 테스트 5건(SC-01~SC-05), 전체 1166 통과, 4 스킵.

## 이전 마일스톤 — 2026-05-29 (스펙 019: 레짐 인식 + 완전 공분산 ERC)

PR #93 머지 커밋 `6c1d849`. **"세계 최고 수준" 로드맵 — 신호 레이어(018) 위에
레짐 인식과 진짜 등기여 위험 배분(ERC)을 하나의 스펙으로 완성**했습니다.
walk-forward 표본 외 검증 통과. 자세히는 `specs/019-regime-erc-sizing/spec.md`. 한 줄 요약:

- **슬라이스 1 — 레짐 감지기(`strategy/regime.py`, 비커널)**:
  `Regime(StrEnum)`: TRENDING / RANGING / BEAR 3상태.
  `detect(bars)`: SMA50·SMA200 교차 기반 결정론적 판별, 200막대 미만 → RANGING fail-safe.
  `DEFAULT_REGIME_SCALE`: 추세=1.0 / 횡보=0.7 / 하락=0.3.
  `apply_regime_scale(qty, scale)`: qty × scale 내림 정수.
- **슬라이스 2 — 완전 공분산 ERC(`strategy/sizing.py` 확장, 비커널)**:
  `covariance_matrix()`: 공통 날짜 교집합 기반 표본 공분산 행렬(Decimal, 6자리 정규화).
  `erc_weights()`: Maillard(2010) CCD 반복 최적화 — 각 자산의 marginal risk contribution 균등화, 수렴 실패 시 `ERCConvergenceError`.
  `erc_group_scales()`: ERC 가중치 딕셔너리, 공통일 <30이면 역변동성 fallback.
  `config/rules.py` SizingConfig.mode에 `"erc"` 추가.
- **슬라이스 3 — walk-forward 표본 외 검증(`tests/unit/test_regime_erc.py`)**: 19개 테스트(레짐 감지 SC-R01~R04, ERC 수학 SC-E01~E04, walk-forward SC-W01~W03). 스펙 016 walk-forward 하니스 위에서 합성 XNYS 데이터로 호환성 확인.
- **안전 경계**: 비커널 전용. K1 caps(`risk/gates.py`) 후처리 변경 없음. ERC 가중치 max 1 클램핑(하향 전용). 결정론적 Decimal — 백테스트·라이브 단일 잣대(헌법 X.2). Kernel 터치 0건. dry-run 그대로.
- **검증**: 신규 테스트 19건, 전체 1161 통과.
- **다음**: 레짐 필터와 ERC 가중치를 `execution/order_router.py`·`backtest/replay.py`에 실제 배선해야 거래 루프에서 작동. 현재는 유틸리티 함수로만 존재(배선 미완).

## 이전 마일스톤 — 2026-05-29 (스펙 018: 다요인 신호 + 사이징 감사 기록)

PR #91 머지 커밋 `aeed831`. **"세계 최고 수준" 로드맵 — 스펙 017 리스크 사이징 토대 위에
신호/알파 레이어와 사이징 관찰 기반을 추가**했습니다. 기존 신호(EMA 교차·RSI)만으로는
세계 최고 수준과 격차가 컸는데, 학문적으로 가장 강건한 두 팩터와 포렌식 감사 기록을 추가했습니다.
자세히는 `specs/018-multifactor-signals/spec.md`. 한 줄 요약:

- **슬라이스 1 — 다요인 신호(비커널)**:
  - `strategy/indicators.py`: `momentum(bars, period)` — N기간 수익률(%). 시계열 모멘텀 팩터.
    `bollinger_band_pct_b(bars, period, std_dev)` — 밴드 내 상대 위치(%B). 평균회귀 팩터.
  - `strategy/triggers.py`: `MOMENTUM_ABOVE` / `MOMENTUM_BELOW`(모멘텀 임계값),
    `BB_ABOVE` / `BB_BELOW`(볼린저 밴드 %B 임계값) 트리거 4종 추가. 기존 EMA/RSI 트리거 byte 동일.
- **슬라이스 2 — 사이징 결정 감사 기록(K4 추가-전용)**:
  - `persistence/audit.py`: `SIZING_DECISION` 이벤트 + `SizingDecisionPayload`(실현 변동성·
    역변동성 가중치·상관·최종 수량을 포렌식 페이로드로). 기존 이벤트 무변경(K4 추가-전용).
  - `strategy/sizing.py`: `SizingResult` 데이터클래스 + `sized_quantity_with_result()` 추가.
    사이징 결과 전체 컨텍스트(base_qty·final_qty·realized_vol_pct·vol_scale·group_scale) 반환.
  - `execution/order_router.py`: `target_vol`·`inverse_vol` 모드에서 `SIZING_DECISION` 감사 행 기록.
    `final_qty=0`(사이징 스로틀 스킵)도 기록(관찰 기반 구축).
- **안전 경계**: 비커널 전용 + K4 추가-전용. 옵트인(기존 룰 미변경 시 새 트리거 사용 0 — byte 동일).
  하향 전용 불변량 유지(새 신호는 트리거 결정만, 사이징은 스펙 017 경로 그대로). Kernel 터치 0건.
  dry-run 그대로.
- **검증**: 신규 테스트 32건(단위 22 + 통합 3 + 사이징 단위 7), 전체 1142 통과.
- **다음**: 신호 레이어 확장(레짐 인식·교차 단면 랭킹·모멘텀 요인 결합), 완전 공분산 ERC,
  양방향 그룹 budget-split. **반드시 워크포워드로 표본 외 검증할 것.**

## 이전 마일스톤 — 2026-05-29 (스펙 017 슬라이스 3: 상관 헤어컷)

PR #89 머지 커밋 `33d3926`. **"세계 최고 수준" 로드맵 — 리스크 사이징 토대(변동성·역변동성·
상관)를 한 바퀴 완성**했습니다. 슬라이스 2b 역변동성은 종목 간 상관을 0으로 가정했는데,
상관 높은 종목을 함께 들면 위험이 분산되지 않고 집중됩니다. 슬라이스 3은 그룹 멤버 간
수익률 상관을 재서, 상관 높은(분산 안 된) 멤버를 추가로 줄이는 **상관 헤어컷**(방어적·하향
전용)을 더했습니다. 자세히는 `HANDOFF-028-SPEC-017-SLICE3-CORRELATION.md`. 한 줄 요약:

- **룰 스키마(`config/rules.py`, 비커널)**: `SizingConfig`에 선택적 `correlation_haircut`
  (강도, 기본 0=끔). inverse_vol 그룹에서만 의미. 0이면 슬라이스 2b와 byte 동일.
- **`strategy/sizing.py`(비커널)**: `pearson_correlation`(분산 0/길이 불일치 None)·
  `average_correlations`(멤버를 공통 거래일로 정렬해 평균 상관, 공통일 < 3이면 None)·
  `correlation_haircut`(`1 - strength·max(0,avg)`, `[0,1]` 클램프)·`group_scale_for`
  (역변동성 가중치 × 상관 헤어컷 합성) 추가.
- **백테스트·라이브 양쪽(`replay`·`OrderRouter`, 비커널)**: `group_scale_for`로 같은 합성
  가중치 계산. 상관 입력(멤버별 `{날짜: 종가}`)을 양쪽이 같은 달력 날짜 키로 정렬 —
  백테스트 `OHLCVBar.session_date`·라이브 `PriceBar.bar_open_utc` 앞 10자 → 단일 잣대
  (헌법 X.2). 공통 거래일 < 3이면 헤어컷 없음(fail-safe).
- **안전 경계**: 하향 전용(헤어컷 ≤ 1, 역변동성 × 헤어컷도 ≤ 1)이라 노출 증가 불가, K1이
  천장. 역상관/분산된 멤버는 헤어컷 없음(`max(0, avg)`). 옵트인 — `correlation_haircut=0`
  이면 슬라이스 2b와 byte 동일(회귀 무손상, SC-S12 증명). **Kernel 터치 0건**(전부 비커널,
  `worker/loop.py`도 미변경 — 기존 배선으로 흐름). 감사 K4 무변경. 결정론적·LLM 미사용.
  dry-run 그대로. 테스트 신규 7건, 전체 1110 통과.
- **다음**: 신호/알파 과학(다요인·레짐 인식 — 이제 리스크 사이징 위에서 안전하게), 완전
  공분산 ERC/상관 하드 합산 캡, 양방향 그룹 budget-split, 또는 사이징 결정 감사 기록(K4).
  **새 사이징/알파 작업은 반드시 `auto-invest walk-forward`로 표본 외 검증할 것.**

## 이전 마일스톤 — 2026-05-29 (스펙 017 슬라이스 2b: 역변동성 그룹 리스크 패리티)

PR #87 머지 커밋 `b8fb7e9`. **"세계 최고 수준" 로드맵 — 멀티 포지션 리스크 배분 1단계**를
완성했습니다. 슬라이스 1·2가 **한 포지션**의 변동성만 봤다면, 슬라이스 2b는 **여러 종목을
한 바구니(sizing group)로 묶어** 종목 간 리스크 기여도를 균형화합니다. 변동성 높은 종목을
줄여 변동성 낮은 종목과 위험을 맞추는 **역변동성(상관 없는 리스크 패리티)** 배분입니다.
자세히는 `HANDOFF-027-SPEC-017-SLICE2B-RISK-PARITY.md`. 한 줄 요약:

- **룰 스키마(`config/rules.py`, 비커널)**: `SizingConfig.mode`에 `"inverse_vol"` 추가,
  `TradingRule`에 선택적 `sizing_group` 추가. `inverse_vol` 모드는 `sizing_group` 필수
  (모델 검증). 둘 다 없으면 기존 동작 byte 동일.
- **`strategy/sizing.py`(비커널)**: `build_sizing_groups(rules)`(그룹명→멤버)·
  `inverse_vol_group_scale(own, members)`(가중치=`min(그룹 변동성)/자기 변동성`, `(0,1]`로
  클램프, 변동성 최저 멤버=기준 1, 높은 멤버 축소, fail-safe 1)·`SizingGroupMember` 추가.
  `sized_quantity`에 `group_scale`(기본 1) 추가.
- **백테스트·라이브 양쪽 연결(`replay`·`OrderRouter`·`worker/loop.py`, 전부 비커널)**:
  K1 게이트 **전에** 같은 두 함수로 그룹 가중치 계산 후 `sized_quantity`에 전달. worker가
  `build_sizing_groups`로 그룹을 만들어 `OrderRouter.sizing_groups`로 넘기면 라우터가
  `self.conn`으로 각 멤버 바를 조회해 같은 `realized_volatility`·lookback으로 잰다 →
  단일 잣대(헌법 X.2).
- **안전 경계**: 하향 전용(가중치 ≤ 1)이라 기준 수량 위로 노출 증가 불가, K1이 그대로
  천장. 그룹은 옵트인 — `sizing_group` 없으면 기존 룰 byte 동일(회귀 무손상, SC-S11 증명).
  **Kernel 터치 0건**(전부 비커널 — 커널인 `worker/schedule.py`가 아닌 `worker/loop.py`).
  감사 K4 무변경. 결정론적·LLM 미사용. dry-run 그대로. 테스트 신규 8건, 전체 1103 통과.
  SC-S10 증명: 같은 그룹에서 변동성 높은 AAPL이 변동성 낮은 MSFT 대비 줄고 MSFT는 풀
  사이즈 유지.
- **다음**: 슬라이스 3(상관 인식 합산 한도, 공분산 추정), 양방향 그룹 budget-split(K1 봉투
  안 확대), 또는 신호/알파 과학.
  **새 사이징/알파 작업은 반드시 `auto-invest walk-forward`로 표본 외 검증할 것.**

## 이전 마일스톤 — 2026-05-28 (스펙 017 슬라이스 2: 양방향 변동성 타깃팅)

PR #85 머지 커밋 `ab4a140`. **"세계 최고 수준" 로드맵 — 변동성 타깃팅의 나머지 절반을
완성**했습니다. 슬라이스 1이 turbulent 구간에서 사이즈를 **줄이는** 하향 절반만 했다면,
슬라이스 2는 잔잔한 구간(실현 변동성 < 타깃)에서 사이즈를 타깃 리스크 예산까지 **늘리는**
상향 절반을 더해 진짜 변동성 타깃팅(일정한 리스크 예산 유지 → 샤프·최대낙폭 직접 개선)을
완성합니다. 신호 과학보다 사이징을 먼저 완성하는 규율 있는 순서이며, 구조적 우위라 과적합
위험이 낮습니다(헌법 원칙 X). 자세히는 `HANDOFF-026-SPEC-017-SLICE2-BIDIRECTIONAL.md`.
한 줄 요약:

- **룰 스키마(`config/rules.py`, 비커널)**: `SizingConfig`에 선택적 `max_scale`(상향 한도)
  추가. 기본 `1`이면 슬라이스 1 하향 전용과 byte 동일(`ge=1`, fat-finger 방지 `le=10`).
  `max_scale > 1`로 명시한 룰만 잔잔한 구간에서 확대.
- **`strategy/sizing.py`(비커널)**: `volatility_scale`이 `target/realized`를
  `[min_scale, max_scale]`로 클램프. 실현 변동성 ≤ 0이면(측정 불가) 중립값 1 반환으로
  무한 확대 방지. `sized_quantity`가 `max_scale`을 전달.
- **연결 지점 로직 변경 없음**: `replay`·`OrderRouter`는 이미 K1 게이트 **전에** 사이저를
  호출 → 이제 확대 수량도 같은 게이트를 거친다. 주석만 양방향 동작에 맞게 갱신.
- **안전 경계**: **K1이 진짜 천장** — 확대해도 사이저는 제안만 하고, K1 게이트
  (`risk/gates.py`)가 거래당·종목당·전체 캡 초과 주문을 **거부**(클램프 아님)한다. 확대는
  K1 위로 노출을 절대 못 올린다(SC-S09 테스트 `test_replay_bidirectional_upscale_still_bound_by_k1_caps`로 증명). 하향 조절은 그대로 살아있음. 기본 `max_scale=1`이라
  기존 룰 byte 동일(회귀 무손상). **Kernel 터치 0건**(전부 `strategy/sizing.py`·
  `config/rules.py`·`backtest/replay.py`·`execution/order_router.py` 비커널·`tests/`·
  `specs/`). 감사 K4 무변경. 결정론적·LLM 미사용. dry-run 그대로. 테스트 신규 9건,
  전체 1095 통과.
- **다음**: 슬라이스 2b(멀티 포지션 역변동성/리스크 패리티 — 포트폴리오 상태 결합이 커서
  별도 슬라이스), 슬라이스 3(상관 인식 배분), 또는 신호/알파 과학.
  **새 사이징/알파 작업은 반드시 `auto-invest walk-forward`로 표본 외 검증할 것.**

## 이전 마일스톤 — 2026-05-28 (스펙 017 슬라이스 1: 변동성 기반 포지션 사이징)

PR #83 머지 커밋 `c291d75`. **"세계 최고 수준" 로드맵 — 측정 토대 다음 단계인 리스크
사이징을 시작**했습니다. 스펙 016이 백테스트를 정직·통일·표본 외 검증되게 만들었지만,
포지션 사이징은 여전히 v1 수준(룰마다 고정 정수 수량 `Action.qty`)이었습니다. 변동성
타깃팅은 과적합 위험이 낮은 구조적 우위라 헌법 원칙 X(측정 기반·추측 금지)에 가장 잘
맞는 다음 단계입니다. 자세히는 `HANDOFF-025-SPEC-017-VOL-SIZING.md`. 한 줄 요약:

- **새 모듈 `strategy/sizing.py`(비커널)**: `realized_volatility`(연속 종가 단순 수익률의
  표본 표준편차) + `volatility_scale`(`min(1, target/realized)`을 `[min_scale, 1]`로
  클램프) + `sized_quantity`(`floor(기준수량 × scale)`). 전부 결정론적 Decimal —
  백테스트 byte-equality + 라이브/백테스트 단일 잣대(헌법 X.2) 보존.
- **룰 스키마(`config/rules.py`, 비커널)**: 선택적 `SizingConfig`(`mode` fixed|target_vol,
  `target_volatility_pct`, `lookback_bars`, `min_scale`). `TradingRule.sizing` 기본 `None`
  → fixed → v1 동작 byte 동일(하위호환, 마이그레이션 불필요).
- **백테스트 `replay`와 라이브 `OrderRouter`(둘 다 비커널) 양쪽 연결**: 신호 발사 후 K1
  게이트 체인 **전에** `sized_quantity` 호출. 사이저는 수량을 **제안만** 하고 K1 캡이
  그대로 상한으로 바인딩 — 노출을 K1 위로 절대 올릴 수 없음. 슬라이스 1은 스케일 ≤ 1
  (하향 전용 throttle)이라 v1 대비 노출 증가 불가. `sized < 1`이면 그 틱 건너뜀(`qty=0`
  주문 미생성, `SKIPPED_BY_SIZING`). 같은 함수를 양쪽이 쓰므로 워크포워드(스펙 016
  슬라이스 3)로 표본 외 검증을 받는다.
- **안전 경계**: K1 캡(`risk/gates.py`·`config/caps.py`) 무변경. **Kernel 터치 0건**(전부
  `strategy/sizing.py` 신규·`config/rules.py`·`backtest/replay.py`·
  `execution/order_router.py` 비커널·`tests/`·`specs/`). 감사 스키마 K4 무변경(새 이벤트
  0건). 결정론적·LLM 미사용. 라이브 worker dry-run 그대로. 테스트 신규 18건, 전체 1086
  통과. fixed/None 경로가 v1과 byte 동일(기존 1068 테스트 무손상)으로 회귀 무손상 증명.
- **다음**: 슬라이스 2(양방향 타깃 변동성 — 잔잔한 구간에서 K1 봉투 안 확대 + 멀티
  포지션 역변동성/리스크 패리티), 슬라이스 3(상관 인식 배분), 또는 신호/알파 과학.
  **새 사이징/알파 작업은 반드시 `auto-invest walk-forward`로 표본 외 검증할 것.**

## 이전 마일스톤 — 2026-05-27 (스펙 016 슬라이스 3: 워크포워드 표본 외 검증)

PR #81 머지 커밋 `9242faa`. **세계 최고 수준 로드맵 3단계 — 표본 외 검증(과적합
탐지)**을 완료했습니다. 슬라이스 1·2가 백테스트를 정직(거래비용)·통일(단일 잣대)되게
만들었지만, 단일 기간 백테스트는 그 한 기간에 **과적합**될 수 있습니다(좋아 보이는
룰셋이 그 시기의 잡음을 외운 것뿐일 수 있음). 워크포워드는 같은 룰셋을 롤링 표본 내
(IS)/표본 외(OOS) 윈도우로 돌려 "이 우위가 표본 밖에서도 재현되는가?"를 묻습니다.
이게 깔려야 신호·사이징 개선을 환상이 아니라 검증된 토대 위에서 할 수 있습니다(헌법
원칙 X). 자세히는 `HANDOFF-024-SPEC-016-SLICE3-WALK-FORWARD.md`. 한 줄 요약:

- **새 모듈 `backtest/walk_forward.py`(비커널)**: `generate_windows`(rolling=고정 IS
  미끄러짐 / anchored=IS 확장, OOS 무중첩 연속 타일링) + `run_walk_forward`(구간마다
  새 브로커·시계로 기존 `replay` 재실행 + 슬라이스 2 `build_summary` 재사용 → 같은
  잣대 자동 보장) + 윈도우별 WFE·과적합 판정 + 마크다운 리포트.
- **헤드라인 두 가지**: (1) 표본 외 집계 성과(윈도우별 OOS 지표 평균 — 과적합에 강한
  정직한 숫자), (2) 워크포워드 효율(WFE = OOS 샤프 / IS 샤프, 평균·중앙값). 과적합
  신호 3종: 평균 WFE < 임계(기본 0.5) / IS 샤프는 양인데 OOS 0 이하 / 표본 외 수익
  윈도우 과반 미만.
- **CLI**: `auto-invest walk-forward --rules ... --from ... --to ... --in-sample-days
  ... --out-of-sample-days ... [--mode rolling|anchored] [--wfe-threshold 0.5]`.
  과적합 의심 시 종료코드 1.
- **안전 경계**: 오프라인·읽기 전용(기존 replay를 날짜 부분구간에 재실행할 뿐, 라이브
  주문 경로 무수정, 돈 안 움직임). **Kernel 터치 0건**(전부 `backtest/walk_forward.py`
  ·`cli.py` 비커널·`tests/`·`specs/`). 감사 스키마 K4 무변경(기존 replay 감사 어휘만
  사용). 테스트 신규 10건, 전체 1068 통과. SC-E01 핵심 증명
  `test_oos_summary_uses_same_yardstick_as_direct_backtest` — 한 윈도우의 OOS 지표가
  같은 날짜 범위 독립 백테스트와 바이트 동일(실제 replay 엔진 사용). CLI도 실제 ingest
  데이터셋에 종단 검증.
- **다음**: 측정 토대(정직·통일·표본 외 검증) 완성. 신호/알파 과학(다요인·레짐 인식)
  또는 포지션 사이징(변동성·상관) — 이제 워크포워드로 검증받으며 안전하게 개선.

## 이전 마일스톤 — 2026-05-27 (스펙 016 슬라이스 2: 단일 잣대 통일)

PR #79 머지 커밋 `83abbbb`. **세계 최고 수준 로드맵 2단계 — 측정 잣대 통일**을
완료했습니다. 슬라이스 1이 백테스트를 정직하게(거래비용) 만들었다면, 슬라이스 2는
백테스트와 라이브가 **같은 거래 단위 지표 정의**를 쓰게 해서 헌법 원칙 X.2("단일
잣대")를 완성합니다. 자세히는 `HANDOFF-023-SPEC-016-SLICE2-SINGLE-YARDSTICK.md`.
한 줄 요약:

- **고친 갭**: 승률·평균손익·손익비가 라이브 엔진에만 인라인으로 있고 백테스트엔
  통째로 없었음(다른 잣대). 둘 다 Sortino 없었음. 공식이 한쪽에만 있어 갈라질 위험.
- **공용 단일 정의(`backtest/metrics.py`)**: `sortino_ratio`(하방편차·√252) +
  `win_loss_stats`(승률·평균손익·손익비) + `realized_closed_trades`(평균단가 실현거래
  재구성) 추가. 라이브 엔진과 백테스트가 같은 함수를 호출.
- **라이브(`performance/engine.py`)**: 인라인 공식 제거하고 공용 정의 호출,
  `RiskMetrics`에 sortino 추가, 리포트 schema 1.1→1.2.
- **백테스트**: 비용 반영 체결에서 거래 단위 지표 계산 → `RuleBacktestResult`·
  `BacktestSummary` → `metrics.csv`·`backtest-run.json`·`summary.md`에 노출.
- **안전 경계**: 오프라인·읽기 전용. **Kernel 터치 0건**(전부 `backtest/`·
  `performance/engine.py` 비커널·`tests/`·`specs/`). 감사 스키마 K4 무변경(Sortino를
  튜너 스냅샷에 넣는 건 후속 K4 작업으로 미룸). 테스트 신규 18건, 전체 1058 통과.
  교차 검증 `test_metrics_single_yardstick.py`가 같은 체결 → 백테스트·라이브 동일
  승률·손익비를 증명(SC-D01).
- **다음**: 슬라이스 3(워크포워드 표본 외 검증 — 과적합 탐지).

## 이전 마일스톤 — 2026-05-27 (스펙 016 슬라이스 1: 백테스트 거래비용·슬리피지 모델)

PR #77 머지 커밋 `f8552c6`. **백테스트가 그동안 거짓 잣대였던 문제를 고쳤습니다.**
헌법 원칙 VI는 "백테스트는 슬리피지·체결비용을 모델링 못해 성과를 체계적으로
과대평가한다"고 경고하는데, 백테스트 엔진(`broker_mock.py`)이 정확히 그 무비용·
무슬리피지 체결이었습니다. 또 헌법 원칙 X.2("단일 잣대")는 라이브·백테스트가 같은
지표 정의를 써야 한다는데, 라이브 성과 엔진은 비용 반영 실현 손익을 재는 반면
백테스트는 비용을 0으로 둬 비교가 무의미했습니다. **세계 최고 수준의 전제 = 정직한
백테스트**(거짓 잣대 위에서 신호·사이징을 개선하면 환상을 최적화하게 됨)라서, "세계
최고 수준" 작업 중 1순위로 이 갭을 골랐습니다. 자세히는
`HANDOFF-022-SPEC-016-BACKTEST-COSTS.md`. 한 줄 요약:

- **거래비용 오버레이**: 브로커 목의 기계적 체결(`pessimistic_zero_slip`)은 그대로
  두고, `replay`의 체결 처리 단계(`_record_fill`)에 비용을 입혔습니다. 슬리피지=
  체결가를 불리한 방향으로 이동(BUY ↑, SELL ↓, basis point), 수수료=`max(최소수수료,
  명목금액 × commission_bps)`를 현금흐름에서 차감. 새 모듈 `backtest/costs.py`의
  `BacktestCostModel`(`.zero()` / `.kis_default()`).
- **정직한 기본값**: 프로덕션 진입점(`run_backtest`/CLI/캐너리) 기본값 = KIS 미국주식
  현실값(수수료 25bps, 슬리피지 5bps). `replay` 기본값은 `zero()`라 기존 무비용 단위
  테스트는 무손상. CLI `--commission-bps`·`--slippage-bps`·`--min-commission-usd`.
- **비용 노출**: 규칙별·합계 수수료/슬리피지를 `metrics.csv`·`backtest-run.json`·
  `summary.md`·`RunOutcome`에 표면화(운영자가 비용 드래그를 봄).
- **안전 경계**: 오프라인·읽기 전용(라이브 주문 경로 무수정, 돈 안 움직임). **Kernel
  터치 0건**(전부 `backtest/`·`cli.py`·`tests/`·`specs/`, 감사 스키마 K4 무변경).
  byte-equality(FR-B15)는 모든 비용 연산 6자리 정규화로 보존. 테스트 신규 9건, 전체
  1040 통과.
- **후속**: 슬라이스 2(단일 잣대 통일 — 백테스트가 승률·손익비·Sortino 계산),
  슬라이스 3(워크포워드 표본 외 검증).

## 이전 마일스톤 — 2026-05-27 (스펙 001 T050/T052: 장 마감 정합성 자동 실행)

PR #75 머지 커밋 `4319535`. **로컬 장부와 브로커 보유를 매 장 마감마다 자동으로
대조해 드리프트를 잡는** 정합성 검증의 자동 호출 배선을 채웠습니다. 정합성 검증은
스펙 001 P2(조용한 상태 드리프트 방지)의 키스톤인데, 구현(T049)·테스트(T048)는
됐으나 **자동 호출 배선(T050)이 통째로 빠져 유일한 호출자가 테스트 스위트**였습니다.
그래서 라이브 자율 운영 중 불일치를 한 번도 못 잡았고 스펙 013 헬스의 정합성 점검은
영구 DEGRADED 였습니다. 자세히는 `HANDOFF-021-RECONCILE-AT-CLOSE.md`. 한 줄 요약:

- **`worker/loop.py`** — 세션 열림→닫힘 전이 첫 틱에 정합성 1회 자동 실행
  (`Worker._session_was_open` + `_reconcile_at_close`). 한 닫힘 구간 정확히 1회,
  라이브 전용(paper 무변경), 오류 격리(거래 무중단).
- **`cli.py`** — `auto-invest reconcile` 명령(수동/모니터링용, 종료 0/1/2). 같은
  `run_reconciliation` 진입점 재사용. `reconcile_now` docstring 거짓 주장 정정.
- **안전 경계**: 읽기-기반(주문/청산 0건, 불일치 시 halt만), 라이브 전용, 거래
  무중단. **Kernel 터치 0건**(기존 정합성 이벤트·러너 재사용). 테스트 신규 7건,
  전체 1031 통과.

## 이전 마일스톤 — 2026-05-27 (스펙 015: 라이브 체결 동기화)

PR #73 머지 커밋 `e746f52`. **접수된 라이브 주문이 실제로 체결됐는지를 브로커에서
다시 조회해 장부(FILL 감사·`fills` 테이블·보유 캐시·주문 상태)에 반영하는** 마지막
고리를 채웠습니다. 그동안 라이브 주문은 `SUBMITTED`(브로커 접수)에서 멈추고 실제
체결 추적이 0건이라, `FILL`/`fills`/`update_from_fill`이 정의·조회만 되고 라이브
writer 가 없어 **스펙 014 브레이커·스펙 011 성과·정합성이 라이브에서 통째로 눈을
뜨지 못하던** 키스톤 구멍을 메웁니다. 자세히는
`HANDOFF-020-SPEC-015-FILL-INGESTION.md`. 한 줄 요약:

- **브로커 체결 조회** `get_order_executions`(KIS `inquire-ccnl`, 읽기 전용) +
  `BrokerExecution` 모델. 새 모듈 `execution/fill_sync.py`: 순수 계획 함수
  `plan_fill_ingestion` + async `sync_fills`.
- **멱등 적재**: 누적 체결량 대비 추가분만 FILL 기록(`kis_fill_id="{odno}:{누적}"`),
  보유 캐시 갱신, 상태 전이(`SUBMITTED`→`PARTIALLY_FILLED`→`FILLED`, 종료 시
  `EXPIRED`+`CANCEL`). 재폴링 안전.
- **워커 연결**: 틱에 라이브 전용 cadence(5초). paper 무변경, 열린 주문 0건이면
  브로커 미호출, 오류 격리(거래 무중단).
- **CLI** `auto-invest fills [--sync]`.
- **안전 경계**: 주문/취소 안 함(브로커 확인 체결만 기록), 멱등, 라이브 전용, 거래
  무중단. **Kernel 터치 0건**(기존 `FILL`/`CANCEL` 재사용, 마이그레이션 불필요).
  테스트 신규 29건, 전체 1024 통과.

## 이전 마일스톤 — 2026-05-27 (스펙 014: 라이브 손실 서킷 브레이커)

PR #71 머지 커밋 `2c1b8aa`. **손실이 한도를 넘으면 사람 개입 없이 워커가 스스로
새 주문을 멈추는** 자동 손실 차단 장치를 추가했습니다. 그동안 위험 통제는 노출
상한(거래당·종목당·전체 캡)뿐이었고 손실 기반 자동 차단이 0건이었는데, 이 스펙이
실거래 전 안전 기반의 가장 큰 구멍을 메웁니다. 자세히는
`HANDOFF-019-SPEC-014-CIRCUIT-BREAKER.md`. 한 줄 요약:

- **두 한도**: 일일 실현 손실(`-(daily_loss_limit_pct% × 시작 자본)` 이하면 트립)
  + 전체 자산 낙폭(현재 자산 ≤ 시작 자본 × (1 − max_total_drawdown_pct/100)).
  손익은 스펙 011 성과 엔진 한 잣대 재사용(헌법 X).
- **워커 자동 정지**: `tick`에서 halt·세션 점검 이후 평가, 트립이면 `set_halt` +
  `CIRCUIT_BREAKER_TRIPPED` append 후 새 주문 없이 종료. halt 선점으로 멱등.
- **안전 경계**: 순수 방어적(정지만, 노출 증가/주문/청산 0건). 한도가 K1
  (`config/caps.py`)에 있어 **자율 튜너가 자동 완화 불가**. 기본값 활성(일일 10%·
  낙폭 20%)이나 카타스트로피급이라 정상 운영 무영향. 라이브 worker는 dry-run 그대로.
- **Kernel 터치**: K1+K4 추가-전용 커밋 `b7a1f25`(caps 손실 한도 필드 +
  `CIRCUIT_BREAKER_TRIPPED` 이벤트). K2·K3·K5·K6·K-meta 0건. 테스트 31건.
- **헬스 연동**: `auto-invest health`에 브레이커 점검 추가(읽기 전용, 트립 halt는
  CRITICAL).

## 이전 마일스톤 — 2026-05-26 (스펙 013: 운영 관측·신뢰성 — `auto-invest health`)

PR #69 머지 커밋 `8b29d42`. **"지금 시스템이 건강한가"를 한 화면·종료 코드로 답하는
읽기 전용 통합 헬스 롤업**을 추가했습니다. 그동안 관측 표면이 전부 흩어진 사후 분석
명령(`status`/`report`/`performance`/`efficiency`/`tune`)이라, 운영자가 여러 명령을
따로 돌려 머릿속에서 합쳐야 했습니다. 실거래 전환 전 신뢰 기반의 가장 큰 약점이었던
"통합 건강 뷰 부재"를 메웠습니다. 한 줄 요약:

- **5개 신뢰성 점검 + 종합 판정**: 워커 생존(PID 파일 + `os.kill(pid,0)`)·halt 플래그·
  정합성(결과 + 신선도)·최근 오류(24시간)·활동 신선도를 합쳐 종합 판정
  (`OK`<`DEGRADED`<`CRITICAL`, = 최악 점검값)을 냅니다. 맥락 블록(오늘 주문 깔때기·
  보유 종목 수·마지막 성과·튜너·캐너리)은 정보용(판정 미반영).
- **모니터링 연동**: `auto-invest health --format text|json --stale-hours 36`. 종료 코드
  `0`=정상 / `1`=불건강 / `2`=오용. 크론·알림이 종료 코드로 붙을 수 있습니다.
- **안전 경계 핵심**: **100% 읽기 전용** — 감사 로그 append 0건, 상태 파일 변경 0건,
  `db.migrate` 미호출(라이브 워커와 동시 실행 시 DB 손상 위험 회피). 거래 워커 루프
  무수정. DB 파일 없으면 빈 DB 생성 없이 `CRITICAL`.
- **Kernel 터치 0건**: 손댄 파일 전부 `reports/health.py`·`cli.py`(비커널)·`tests/`·
  `specs/013-operational-health/`. 테스트 22건(단위 16 + 통합 6).

## 이전 마일스톤 — 2026-05-26 (스펙 012: 튜너 L2/L3 → 하드닝 캐너리 자동 투입)

PR #67 머지 커밋 `943c08b`. **자율 튜너의 L2/L3 위험 변경을 스펙 007 하드닝 캐너리로
자동 투입해 검증**하는 경로를 깔았습니다. 그동안 튜너의 L2/L3 후보(모델·토큰 같은
위험 변경)는 감사 로그 한 줄만 적고 버려지는 빈 껍데기였는데, 이제 과거 리플레이+합성
충격+퍼즈로 검증하고 합격/불합격을 기록합니다. 자세한 내용은
`HANDOFF-018-SPEC-012-TUNER-CANARY.md` 참조. 한 줄 요약:

- **빈 껍데기 → 살아있는 검증 경로**: `detect.py` 의 cost/latency 드리프트가 가장 비싼
  판단 지점의 `max_tokens` 축소를 L2 후보로 제안 → `candidate.py` 구체화 →
  `canary_submit.py` 가 git plumbing 으로 임시 후보 rev(작업트리 무변경·미푸시) 생성 →
  `run_canary` 검증 → 합격/불합격 기록.
- **안전 경계 핵심**: 캐너리 검증은 시뮬레이션이지 배포가 아니다. **합격해도 라이브
  자동 승격 0건**(`promoted` 항상 False, 헌법 IX.B-2). 승격은 운영자/스펙 006 게이트
  전용. Kernel 터치 후보는 L4 강등 → 캐너리 자동 투입 제외. 리플레이 데이터 없으면
  fail-safe(skip), 캐너리 오류는 후보별 격리.
- **판단 튜닝 표면 신설(비커널)**: `config/judgment_tunables.toml` — 없거나 키 없으면
  현재 `max_tokens` 와 동일(런타임 동작 무변경).
- **K4 추가-전용 터치 1건**: `persistence/audit.py`(`AUTO_TUNED_CANARY_CANDIDATE`·
  `AUTO_TUNED_CANARY_VALIDATED`), 커밋 `01b821e`. K1·K2·K3·K5·K6·K-meta 터치 0건.

## 이전 마일스톤 — 2026-05-26 (스펙 005 후속: 자율 튜너 오프아워 타이머 연결)

PR #63 머지 커밋 `92dd0ff`. **자율 튜너를 매일 장 마감 후 자동 실행되도록 연결**했습니다. 그동안 `auto-invest tune --apply`(저위험 L1 자동 적용)는 수동/단발 실행이었는데, 라이브(dry-run) 워커 인스턴스에서 튜너가 자율로 돌게 만들어 헌법 원칙 X(측정→행동 루프)를 실제로 켰습니다. 자세한 내용은 `HANDOFF-017-TUNER-SCHEDULING.md` 참조. 한 줄 요약:

- **설계 — 워커 코드 무수정.** 워커 루프(`worker/loop.py`)를 한 줄도 안 바꾸고, 저장소에 이미 있는 오프아워 타이머 패턴(`auto-invest-deploy.timer`)을 미러링한 **외부 oneshot 타이머**가 이미 검증·머지된 CLI를 재실행. 라이브 거래 경로 블래스트 반경 0.
- **산출물**: `deploy/run-tune.sh`(래퍼, DB 없으면 종료 0 fail-safe) + `deploy/auto-invest-tune.service`(oneshot) + `deploy/auto-invest-tune.timer`(매일 22:00 UTC, 미국 장 마감 후, `Persistent=true`) + `vultr-userdata.sh` 설치 배선 + README·AUTO-DEPLOY 문서 + 테스트 8건 + 스펙 005 후속 노트.
- **Kernel 터치 0건.** 손댄 파일 전부 `deploy/`·`tests/`·`specs/`. 적용 안전성은 전부 튜너 자신(스펙 005)이 보장 — L1 한 종류·가역, 장중 0건 적용(VIII.A), 측정 부족 거부(X), 멱등, kernel 대상 L4 거부.
- **타이머 = 코드 배포가 아니라 런타임 KPI 임계값 튜닝.** 실거래 토글(`AUTO_INVEST_MODE=live`)과 무관 — 실거래 전환은 여전히 운영자 전용.
- **유닛 자동 설치(PR #65 `e8b3876`)**: 새 systemd 유닛을 라이브 서버에 올리는 데 운영자가 서버 접속할 필요 없음. `deploy-on-merge.yml`이 매 머지마다 `deploy/sync-units.sh`를 서버 `sudo bash`에 파이프해 유닛 설치 + 타이머 활성(워커 미재시작, `git show`로 트리 미오염 → 장중에도 안전). **주의: 서버 SSH 사용자의 `sudo`가 임의 명령(특히 `sudo bash`)을 허용해야 동작** — 막혀 있으면 Actions Summary에 "⚠ 유닛 동기화 실패"로 뜨고 sudoers 한 줄 추가 필요. 운영자는 PR #65 머지의 Actions "Deploy on merge to main" Summary에서 ✅ 확인.

## 이전 마일스톤 — 2026-05-24 (스펙 005 자율 튜너 출시)

PR #60 머지 커밋 `0a176fb`. **측정 → 분석 → 행동 루프를 닫는 자율 튜너**를 완성했습니다. 그동안 측정(스펙 002·011)과 판단(스펙 004)은 있었으나 "측정 신호를 받아 스스로 설정을 조정하는 행동" 단계가 비어 있었는데, 이 스펙이 그 마지막 고리를 헌법 안전 경계 안에서 채웁니다. 자세한 내용은 `HANDOFF-016-SPEC-005-AUTONOMOUS-TUNER.md` 참조. 한 줄 요약:

- **권한 등급(L1~L4)** — 기존 `kernel.toml` 매니페스트 리더(`deploy/kernel_guard.py`) 재사용. 변경 대상 파일이 Kernel(K1~K6·K-meta)에 닿으면 무조건 **L4 강등**(방어 심층화), 튜너는 `kernel.toml`·헌법을 절대 자동 수정 안 함.
- **L1 자동 적용은 단 한 종류** — `config/llm_kpi_thresholds.toml` 의 `tier_b` 임계값 조이기(30일 Tier B 안정 + 일별 Tier C 없을 때만, Tier A 경계 클램프, 가역). 장 시간 마진(헌법 VIII.A)·측정 부족(헌법 X)이면 거부, 멱등(세션 날짜 dedup), dry-run 무변경.
- **순수 결정론적**(LLM 미호출). 새 패키지 `src/auto_invest/tuner/`(models·detect·classify·knobs·gates·report·runner) + CLI `auto-invest tune`. 튜너 테스트 40개, 전체 887 통과.
- **유일한 Kernel 터치**: `persistence/audit.py`(K4) 추가-전용 `AUTO_TUNED_*` 4종, 커밋 `8bbfca2`. K1·K2·K3·K5·K6·K-meta 터치 0건.

## 이전 마일스톤 — 2026-05-24 (스펙 004 LLM 판단 지점 출시)

PR #58 머지 커밋 `78286eb`. **Claude를 거래 결정 루프에 처음 부르는 기능**을 완성했습니다. v1의 "판단 지점 0개"(FR-005) 제약을 명시적으로 열거된 세 결정에 한해 풀었습니다. 자세한 내용은 `HANDOFF-015-SPEC-004-JUDGMENT-POINTS.md` 참조. 한 줄 요약:

- **세 판단 지점**: `volatility_assessment`(변동성 급등 시 hold/size_down/halt 자문, P1·MVP)·`daily_summary`(장 마감 운영 요약, P2)·`news_screen`(장 시작 전 헤드라인 스탠스, P3) + 관측/예산(P4). 전부 헌법 III 계약(트리거·입력·출력 스키마·지연/비용 예산)을 코드로 선언.
- **핵심 안전 설계**: 자문은 `execution/order_router.py`(비커널)에서 주문을 **줄이거나 건너뛰기만** 함 — 노출 증가 불가(`size_down_factor` ≤ 1.0 스키마 강제). 그 뒤 K1 포지션 캡(`risk/gates.py`)이 변형 없이 실행되어 그대로 바인딩. 모든 판단 지점에 결정론적 폴백(LLM 실패해도 거래 안 막힘). 캐너리 단계 룰만 자문 반영(헌법 VI).
- **유일한 Kernel 터치**: `persistence/audit.py`(K4) 추가-전용 판단 이벤트 2종(`JUDGMENT_ADVISORY_APPLIED`·`JUDGMENT_FALLBACK`), 커밋 `7fac2c5`. K1·K2·K3·K5·K6·K-meta 터치 0건.
- 새 패키지 `src/auto_invest/judgment/`(schemas·registry·client·budget·observability·runner + points/). 판단 지점 테스트 55개. 전체 847 통과.

## 이전 마일스톤 — 2026-05-24 (spec 011 완결 + stale 추적 진실화)

PR #55 머지 커밋 `625165c`. 두 가지를 한 번에:

- **spec 011(라이브 성과 측정) 완결** — P3(일일 리포트 성과 섹션 + 튜너용 `LIVE_PERFORMANCE_SNAPSHOT` 추가-전용 이벤트)와 P4(슬리피지 측정)를 구현. 이제 측정 신호 면이 완비됐습니다: 손익·위험조정(샤프·낙폭·승률)·룰별/종목별 기여도·슬리피지·기계 판독 스냅샷. **이것은 spec 005 자율 튜너의 입력 신호** — 원칙 X(측정 기반 자율 성장)가 요구하는 측정 토대가 채워졌습니다.
- **stale 추적 진실화** — 우선순위를 판단하다 **중대한 상태 혼동**을 발견·수정했습니다. spec 006(배포 자동화)·007(하드닝 캐너리)의 tasks.md가 0%로 표시돼 있었으나 **실제로는 코드·테스트가 main에 완성·머지된 상태**였습니다(캐너리 테스트 93개·배포 테스트 8종 green). 하마터면 이미 끝난 40개짜리 스펙을 "미구현"으로 오판해 재구현할 뻔했습니다. 006·007 tasks.md를 done으로 갱신 + SHIPPED 배너, spec.md Status를 Shipped로, CLAUDE.md active-feature에 "체크박스 수치를 믿지 말 것" 경고를 넣었습니다.

**중요한 결론**: 빌드 가능한 스펙(006·007·008·009·010·011)은 **전부 완료**. 남은 spec 004·005는 **운영자 지시(2026-05-24)로 텔레메트리 30일 착수 게이트가 제거되어 즉시 착수 가능**합니다(아래 "2026-05-24 추가 지시" 참조). 단 안전 경계는 불변 — 자율 튜너 런타임 행동은 헌법 원칙 X(측정 기반), 자율 머지는 spec 007 캐너리, 판단 지점은 캐너리 ≥10 거래일에 계속 종속됩니다.

K4 추가-전용 터치 2건(forensic 주의, K-meta 아님): `458a0d8`(`LIVE_PERFORMANCE_SNAPSHOT` 이벤트), `64141b1`(`OrderPaperFilledPayload.reference_price_usd` 필드).

### 2026-05-24 추가 지시 — 스펙 004·005 착수 게이트 제거

운영자가 같은 날 "스펙 004·005는 텔레메트리 30일이 쌓이지 않아도 즉시 착수 가능하도록 조건 변경"을 지시. 적용:

- `specs/004-llm-judgment-points/spec.md`·`specs/005-autonomous-tuner/spec.md`의 promotion 조건에서 **"≥30 calendar days of telemetry" 착수 게이트 제거**. 즉시 `/speckit-specify`부터 시작 가능.
- **헌법·`kernel.toml`은 건드리지 않음** — 30일 게이트는 스펙 스텁의 착수 조건이었을 뿐 헌법 불변량이 아니었다. 헌법의 "≥30 trading-day"는 별개(스펙 007 캐너리 윈도, 안전 게이트)로 그대로 유지.
- **안전 경계 불변**: (1) 자율 튜너의 런타임 행동은 헌법 원칙 X(측정 없이는 튜닝 금지)에 계속 종속, (2) 자율 머지는 스펙 007 하드닝 캐너리가 유일한 경로(IX.B-2), (3) Kernel 터치는 L4 인간 머지 강제, (4) 실거래는 `AUTO_INVEST_MODE=live` 운영자 토글 전용. 바뀐 것은 "코드를 언제 쓰기 시작할 수 있는가"뿐.

## 이전 마일스톤 — 2026-05-23 (라이브 worker dry-run 시작)

자세한 내용은 `HANDOFF-014-LIVE-DRYRUN-STARTED.md` 참조. 한 줄 요약:

- `auto-invest design` 재호출로 **라이브 worker 가 dry-run(모의) 모드로 정상 시작** (run `26330498160`, 2026-05-23 10:36 UTC). 잔고 $292.61, 총 평가 $1,536.38. 룰 `rule_dca_voo_monday`(VOO 매주 월요일 09:35 적립) 외 생성.
- 실주문은 아직 안 나갑니다 — 헌법 VI 단계적 확장(백테스트→캐너리→본운영)의 1주일 안전 관찰 단계.
- 라이브 진입을 막던 버그 2개 해결: PR #47 (`8512fc2`, 프롬프트에 적립용 time 트리거 사용법 누락) + PR #48 (`3010648`, `trigger-design.yml` 의 AUTO_OK 가 sudo env_reset 으로 비워지던 문제).

이전 마일스톤(2026-05-22 KIS 회귀 자율 검증 도입, PR #33 `9096e21` / PR #34 `8cfb7d3`, main push 시 자동 회귀 smoke)은 `HANDOFF-012-KIS-AUTONOMOUS-VERIFY.md` 참조. `KIS smoke (autonomous)` 워크플로우는 활성 상태이며 매일 03:00 UTC + main push 시 자동 실행.

## 현재 main 상태 (2026-05-23 기준)

* **헌법 v3.1.0** (v3.0.0 2026-05-14 도입 머지 커밋 `f849fab`; v3.1.0 머지 커밋 `e949451`, 원칙 X 측정 기반 자율 성장 추가). 원칙 IX.D — 운영자 자율 수행 보장. PR 생성과 머지는 모두 자동 워크플로우의 일부. Kernel 터치도 머지를 막지 않음. 안전 경계는 **생산 배포 단계**(스펙 007 하드닝 캐너리)에서 지킴.
* **스펙 001 (미국 주식 자동 거래 MVP)** — 출시 완료 (2026-05-04). 실제 KIS 브로커 검증 완료. **후속(2026-05-27, PR #75 `4319535`)**: P2 사용자 스토리 "조용한 상태 드리프트 방지"의 미배선 부분(T050 자동 호출 + T052 워커 테스트)을 완성. 정합성 검증(로컬 장부↔브로커 보유 대조, 불일치 시 halt)은 구현(T049)·테스트(T048)는 됐으나 자동 호출 배선이 없어 테스트 스위트만 호출하던 상태였음. 이제 워커가 장 마감 전이마다 자동 대조(라이브 전용, 인-틱, 오류 격리) + `auto-invest reconcile` 수동 명령. Kernel 터치 0건. 자세히는 `HANDOFF-021-RECONCILE-AT-CLOSE.md`.
* **스펙 002 (토큰 사용량 측정)** — 출시 완료.
* **스펙 003 (세션 캐시)** — 출시 완료.
* **스펙 004 (LLM 판단 지점)** — **출시 완료** (2026-05-24, PR #58 머지 커밋 `78286eb`). Claude를 거래 루프에 처음 부르는 기능. 세 판단 지점(volatility_assessment·daily_summary·news_screen) + 관측/예산. 자문은 노출을 줄이거나 건너뛰기만 — K1 캡 그대로 바인딩. 결정론적 폴백·캐너리 게이트. K4 추가-전용 터치 커밋 `7fac2c5`. 판단 지점은 여전히 헌법 VI 캐너리 ≥10 거래일을 탄다(런타임 캐너리 단계 룰만 자문 반영).
* **스펙 005 (자율 튜너)** — **출시 완료** (2026-05-24, PR #60 머지 커밋 `0a176fb`). 측정→분석→행동 루프를 닫는 순수 결정론적 엔진(LLM 미호출). 권한 등급(L1~L4) 분류는 기존 `kernel.toml` 리더 재사용, Kernel 교집합=무조건 L4. L1 자동 적용은 `config/llm_kpi_thresholds.toml` 의 `tier_b` 임계값 조이기 한 종류(장 시간·측정·멱등 게이트). 새 패키지 `src/auto_invest/tuner/` + CLI `auto-invest tune`. K4 추가-전용 터치 커밋 `8bbfca2`(`AUTO_TUNED_*` 4종). 런타임 튜닝 행동은 원칙 X, 머지가 닿는 생산 배포는 스펙 007 캐너리에 계속 종속(안전 경계 불변). **후속(2026-05-26, PR #63 `92dd0ff`)**: 오프아워 systemd 타이머(`deploy/auto-invest-tune.timer`, 매일 22:00 UTC)가 `auto-invest tune --apply`를 자동 실행 — 튜너가 라이브 워커에서 자율로 돎(워커 코드 무수정, Kernel 터치 0건).
* **스펙 006 (배포 자동화 러너)** — 출시 완료 (2026-05-15, PR #7 머지 커밋 `790c0c1`). 38/38 작업 7단계 전부 완료. K4 터치 커밋 `c1800a6` (audit.py에 5종 새 이벤트 타입 추가). systemd 유닛/타이머 템플릿 동봉(`deploy/`).
* **스펙 007 (하드닝 캐너리 — 생산 배포 게이트)** — 출시 완료 (2026-05-14, PR #5 머지 커밋 `775f53a`). 40/40 작업 6단계 전부 완료.
* **스펙 008 (백테스트 엔진)** — 출시 완료 (2026-05-14, PR #4 머지 커밋 `7f8fb99`). 41/41 작업 완료 (PR #45 정합성 정정 포함).
* **스펙 009 (paper-run 데몬)** — 출시 완료 (2026-05-19, main `56ec260`).
* **스펙 010 (자동 룰 설계자)** — **출시 완료** (2026-05-20, PR #19 `14a7ff9` 본체 + PR #20 `d78d0ae` 라이브 worker 자동 시작 + PR #21 `167355c` `--check` 모드 + PR #22 운영자 가이드). 35/35 작업 6단계 전부 완료. K4 터치 커밋 `b6442ee` (audit.py에 RULE_DESIGN_* 4종 페이로드 추가). `auto-invest design --intent "..."` 한 줄로 자연어 의도 → Claude 룰 자동 생성 → 정적 검증 + paper-run → 운영자 OK → 자동 라이브.
* **스펙 011 (라이브 성과 측정)** — **출시 완료** (2026-05-24, PR #55 머지 커밋 `625165c`; P1·P2는 그 이전 PR #51·#52). P1 손익 엔진·CLI, P2 위험조정 지표(샤프·낙폭·승률, spec 008 metrics 재사용), P3 일일 리포트 성과 섹션 + 튜너용 `LIVE_PERFORMANCE_SNAPSHOT` 스냅샷, P4 슬리피지(기준가 대비 체결 품질). `auto-invest performance --since/--window [--slippage] [--snapshot] [--json]`. 읽기 전용 측정 — 돈을 움직이지 않음. spec 005 튜너의 입력 신호 면.
* **스펙 012 (튜너 L2/L3 → 하드닝 캐너리 자동 투입)** — **출시 완료** (2026-05-26, PR #67 머지 커밋 `943c08b`). 튜너의 L2/L3 위험 변경(모델·토큰)을 스펙 007 캐너리로 자동 투입해 검증(과거 리플레이+충격+퍼즈)하고 합격/불합격 기록. 빈 껍데기였던 L2 경로를 살아있는 검증 경로로 전환. **안전 경계: 합격해도 라이브 자동 승격 0건(`promoted` 항상 False, 헌법 IX.B-2). 캐너리=시뮬레이션이지 배포 아님. Kernel 후보 L4 제외. fail-safe(데이터 없으면 skip)·오류 격리.** 판단 튜닝 표면 `config/judgment_tunables.toml`(비커널, 폴백=동작 무변경). K4 추가-전용 터치 커밋 `01b821e`(`AUTO_TUNED_CANARY_*` 2종). 자세히는 `HANDOFF-018-SPEC-012-TUNER-CANARY.md`.
* **스펙 013 (운영 관측·신뢰성 — 통합 헬스 롤업)** — **출시 완료** (2026-05-26, PR #69 머지 커밋 `8b29d42`). `auto-invest health`: 워커 생존·halt·정합성·최근 오류·활동 신선도 5개 점검을 합쳐 종합 판정(`OK`/`DEGRADED`/`CRITICAL`)과 모니터링용 종료 코드(0/1/2)를 냄. **100% 읽기 전용**(감사 로그 append 0건, `db.migrate` 미호출, 거래 워커 루프 무수정). Kernel 터치 0건(`reports/health.py`·`cli.py`만). 테스트 22건. **후속(스펙 014)**: 헬스에 손실 서킷 브레이커 점검 1개 추가(총 6개 점검).
* **스펙 014 (라이브 손실 서킷 브레이커)** — **출시 완료** (2026-05-27, PR #71 머지 커밋 `2c1b8aa`). 손실이 한도를 넘으면 워커가 스스로 새 주문을 멈춤. 두 한도: 일일 실현 손실 + 전체 자산 낙폭. 손익은 스펙 011 성과 엔진 한 잣대 재사용(헌법 X). `tick`에서 halt·세션 점검 이후 평가, 트립이면 `set_halt` + `CIRCUIT_BREAKER_TRIPPED` append. **안전 경계: 순수 방어적(정지만, 노출 증가/주문/청산 0건). 한도가 K1(`config/caps.py`)에 있어 자율 튜너 자동 완화 불가. 기본값 활성(일일 10%·낙폭 20%)이나 카타스트로피급. 라이브 worker는 dry-run 그대로.** K1+K4 추가-전용 터치 커밋 `b7a1f25`. 테스트 31건. 자세히는 `HANDOFF-019-SPEC-014-CIRCUIT-BREAKER.md`.
* **스펙 015 (라이브 체결 동기화)** — **출시 완료** (2026-05-27, PR #73 머지 커밋 `e746f52`). 접수된 라이브 주문의 실제 체결을 브로커 조회(`inquire-ccnl`)로 멱등하게 `FILL` 기록·보유 캐시 갱신·상태 전이. 새 모듈 `execution/fill_sync.py`(순수 `plan_fill_ingestion` + async `sync_fills`). 워커 틱에 라이브 전용 cadence(5초) 연결, CLI `auto-invest fills [--sync]`. **안전 경계: 주문/취소 안 함(브로커 확인 체결만 기록), 멱등, 라이브 전용(paper 무변경), 거래 무중단(오류 격리). Kernel 터치 0건**(기존 `FILL`/`CANCEL` 재사용, 마이그레이션 불필요). 테스트 신규 29건. **이 기능이 스펙 014 브레이커·스펙 011 성과·정합성을 라이브에서 비로소 작동하게 한다.** 자세히는 `HANDOFF-020-SPEC-015-FILL-INGESTION.md`.
* **스펙 016 (백테스트 거래비용 + 단일 잣대 + 워크포워드)** — **슬라이스 1·2·3 출시 완료** (2026-05-27). 슬라이스 1(PR #77 `f8552c6`): 무비용·무슬리피지였던 백테스트에 거래비용 오버레이(슬리피지·수수료, KIS 현실값 기본). 새 모듈 `backtest/costs.py`. 슬라이스 2(PR #79 `83abbbb`): 거래 단위 지표 정의(승률·손익비·실현거래 재구성·Sortino)를 `backtest/metrics.py` 한 곳에 모아 라이브 성과 엔진과 백테스트가 같은 함수를 호출(헌법 X.2 완성). 슬라이스 3(PR #81 `9242faa`): 같은 룰셋을 롤링 표본 내(IS)/표본 외(OOS) 윈도우로 돌려 슬라이스 2 단일 잣대로 IS 대비 OOS 성과를 비교해 과적합 탐지. 새 모듈 `backtest/walk_forward.py` + CLI `auto-invest walk-forward`. 헤드라인 = 표본 외 집계 성과 + 워크포워드 효율(WFE = OOS 샤프 / IS 샤프). **안전 경계: 셋 다 오프라인·읽기 전용·Kernel 터치 0건(감사 스키마 K4 무변경).** 측정 토대 3단계(정직·통일·표본 외 검증) 완료 — 다음은 알파/사이징. 자세히는 `HANDOFF-022`·`HANDOFF-023`·`HANDOFF-024`.
* **스펙 017 (변동성 기반 포지션 사이징)** — **슬라이스 1·2·2b·3 출시 완료** (2026-05-28~29). 측정 토대 위에 리스크 사이징(변동성·역변동성·상관)을 한 바퀴 완성. 슬라이스 1(PR #83 `c291d75`): 변동성 throttle(하향 전용). 슬라이스 2(PR #85 `ab4a140`): 양방향 타깃팅(K1이 진짜 천장). 슬라이스 2b(PR #87 `b8fb7e9`): 역변동성 그룹 리스크 패리티. 슬라이스 3(PR #89 `33d3926`): 상관 헤어컷(옵트인, 하향 전용). **Kernel 터치 0건. 감사 K4 무변경. 결정론적·LLM 미사용. dry-run 그대로.** 자세히는 `HANDOFF-025`~`HANDOFF-028`.
* **스펙 018 (다요인 신호 + 사이징 감사 기록)** — **슬라이스 1·2 출시 완료** (2026-05-29, PR #91 `aeed831`). 슬라이스 1(비커널): `strategy/indicators.py`에 `momentum`(N기간 수익률%)·`bollinger_band_pct_b`(%B) 추가. `triggers.py`에 `MOMENTUM_ABOVE/BELOW`·`BB_ABOVE/BB_BELOW` 트리거 4종 연결. 슬라이스 2(K4 추가-전용): `audit.py`에 `SIZING_DECISION` 이벤트 + `SizingDecisionPayload`(실현 변동성·역변동성 가중치·상관·최종 수량). `sizing.py`에 `SizingResult`·`sized_quantity_with_result()` 추가. `order_router.py`에서 사이징 적용 시 감사 행 기록(`final_qty=0` 포함). **안전 경계: Kernel 터치 0건(K4 추가-전용). 옵트인(기존 룰 미변경 시 byte 동일). 하향 전용 불변량 유지.** 신규 테스트 32건, 전체 1142 통과. 자세히는 `specs/018-multifactor-signals/spec.md`.
* **스펙 019 (레짐 인식 + 완전 공분산 ERC)** — **슬라이스 1·2·3 출시 완료** (2026-05-29, PR #93 `6c1d849`). 슬라이스 1(비커널): `strategy/regime.py` — `Regime(StrEnum)` 3상태(TRENDING/RANGING/BEAR), `detect(bars)` SMA50/200 기반 결정론적 판별(200막대 미만 RANGING fail-safe), `DEFAULT_REGIME_SCALE`(추세=1.0/횡보=0.7/하락=0.3), `apply_regime_scale()`. 슬라이스 2(비커널): `strategy/sizing.py`에 `covariance_matrix()`·`erc_weights()`(Maillard CCD 반복 최적화)·`erc_group_scales()`(데이터 부족 시 역변동성 fallback) 추가. `config/rules.py` SizingConfig.mode에 `"erc"` 추가. 슬라이스 3: `tests/unit/test_regime_erc.py` walk-forward 표본 외 검증 19건 통과. **안전 경계: Kernel 터치 0건. ERC 가중치 max 1 클램핑(하향 전용). 결정론적 Decimal(헌법 X.2). 레짐·ERC 유틸리티 배선은 스펙 020(PR #95)에서 완성.** 신규 테스트 19건, 전체 1161 통과. 자세히는 `specs/019-regime-erc-sizing/spec.md`.
* **스펙 020 (레짐 배율·ERC 가중치 거래 루프 실배선)** — **출시 완료** (2026-05-29, PR #95 `cb5dcae`). `strategy/regime.py`·`strategy/sizing.py`의 레짐 감지기·ERC 유틸리티를 `execution/order_router.py`·`backtest/replay.py` 실제 거래 루프에 연결. `rule.regime_index_symbol`이 있으면 DB 인덱스 바 → `detect_regime()` → `apply_regime_scale(qty)`. qty < 1이면 `SKIPPED_BY_SIZING("regime_zero")`. `SizingConfig.mode="erc"` 지원. **Kernel 터치 0건. 하향 전용. 옵트인.** 신규 테스트 5건, 전체 1166 통과.
* **스펙 021 (횡단면 모멘텀 순위 필터)** — **출시 완료** (2026-05-29, PR #97 `2bd01b1`). 전체 유니버스를 N-기간 수익률로 내림차순 순위 매겨 상위 N개 또는 상위 P% 종목에만 매수를 허용하는 횡단면 랭킹 필터(Jegadeesh-Titman 팩터). 새 모듈 `strategy/ranking.py`(`cross_sectional_momentum`, `is_top_n`, `is_top_pct`). `TradingRule.ranking_filter`(`RankingFilter`: `universe`, `period`, `top_n`|`top_pct`). `order_router`·`replay` 양쪽 적용. 미통과 → `SKIPPED_BY_RANKING(not_in_top)`. **Kernel 터치 0건. 하향 전용. 옵트인.** 신규 테스트 13건, 전체 1179 통과.
* **스펙 022 (최소 분산 포트폴리오 최적화)** — **출시 완료** (2026-05-29, PR #99 `204dfc9`). `SizingConfig.mode="min_variance"` — numpy `linalg.solve`로 분석적 최소 분산 해. ridge 정규화. 수치 실패 → ERC → 역변동성 fallback. **Kernel 터치 0건. 옵트인.** 신규 테스트 8건, 전체 1187 통과.
* **스펙 023 (가격 기반 퀄리티 팩터 필터)** — **출시 완료** (2026-05-29, PR #100 `674c8dc`). 롤링 샤프 / (1 + |최대 드로다운|) 합성 점수로 유니버스 순위를 매겨 하위 종목을 `SKIPPED_BY_QUALITY`로 차단. 새 모듈 `strategy/quality.py`. `TradingRule.quality_filter`(`QualityFilter`: `universe`, `lookback_bars`, `top_n`|`top_pct`). **Kernel 터치 0건. 하향 전용. 옵트인.** 신규 테스트 8건, 전체 1195 통과.
* **스펙 024 (최대 샤프 포트폴리오 최적화)** — **출시 완료** (2026-05-29, PR #101 `86b2c32`). `SizingConfig.mode="max_sharpe"` — 롤링 모멘텀 신호를 기대 수익률 μ로 활용해 `w* ∝ Σ^{-1}·μ` 분석적 해. μ 전부 비양수이면 균등 가중치 fail-safe. 수치 실패 → min_variance → ERC → 역변동성 fallback. `expected_returns_from_closes()` 신규. **Kernel 터치 0건. 옵트인.** 신규 테스트 8건, 전체 1203 통과.
* **스펙 025 (다요인 합성 알파 점수)** — **출시 완료** (2026-05-30, PR #103 `127ca3f`). 여러 팩터(모멘텀·퀄리티·저변동성·평균회귀)를 횡단면 z-점수 가중합(하나의 합성 점수)으로 결합해 유니버스 순위. 새 모듈 `strategy/factors.py`. `TradingRule.composite_filter`. **Kernel 터치 0건. 하향 전용. 옵트인.** 신규 테스트 12건.
* **스펙 026 (캐너리→풀라이브 자동 승격 게이트)** — **출시 완료** (2026-05-30, PR #112 `b1a7e88`). `promotion/gate.py`(헌법 VI 6조건 순수 게이트) + `readiness.py`(라이브 audit_log 측정) + CLI `promote-check` + 매일 `promote-readiness.yml`. **승격 수행 안 함(보고 전용). 풀라이브는 VI 게이트 AND 스펙 007 캐너리(IX.B-2) 둘 다 통과해야 발화 — 최소 30거래일 후.** 자세히는 `HANDOFF-036-CANARY-CAPITAL-AND-PROMOTION-GATE.md`.
* **스펙 027 (디플레이티드 샤프 비율 — 다중검정 보정)** — **출시 완료** (2026-05-30, PR #114 `ec1d040`). 백테스트·워크포워드 샤프를 표본 길이·비정규성·시도 개수로 보정(PSR·MinTRL·DSR). 새 모듈 `backtest/significance.py`(scipy 없이 `Φ`/`Φ⁻¹` 구현). 워크포워드에 표본 외 풀 트랙 유의성 배선 + CLI `--num-trials`·`--trial-sharpe-std`·`--min-psr`·`--min-dsr`. **Kernel 터치 0건. 오프라인·읽기 전용. 기본값 byte 동일(옵트인 게이트).** 신규 테스트 32건. 자세히는 `HANDOFF-037-SPEC-027-DEFLATED-SHARPE.md`.
* **라이브 worker** — dry-run(모의) 모드로 가동 중 (2026-05-23 시작). 실주문 미발생. `AUTO_INVEST_MODE=live` 명시 토글 전까지 돈은 움직이지 않음 (운영자 명시 지시 필요). **주의: 스펙 026 선택 1번으로 라이브 캐너리 무장됨(자본 $12k, 축소 룰셋) — `HANDOFF-035`·`HANDOFF-036` 참조.**
* **KIS smoke 자율 감시** — 활성 상태. main push 시 `KIS smoke (autonomous)` 워크플로우 자동 실행. 매일 03:00 UTC cron. 진단은 `automation/kis-smoke-last-run` 사이드카 브랜치에 force-push (`git show origin/automation/kis-smoke-last-run:LAST_RUN.md` 한 줄로 조회). 최신 실행 정상 (`smoke_state=success`, `key_valid=true`).
* **main의 테스트**: 1250 통과, 4 스킵 (라이브 KIS 스모크 4건은 `KIS_LIVE_TEST=1` 환경변수로 게이트).
* **린트**: `uv run ruff check src tests` 깨끗.
* **라이브 브로커 검증**: 운영자(mason)가 2026-05-04에 본인 실제 KIS 계좌에서 `scripts/live_smoke.py` 실행 — 검증 완료.

## 운영자 사용성 — 지금 바로 가능한 것

스펙 006이 출시되면서 운영자가 SSH로 들어가 git pull/restart를 손으로 안 해도 됩니다. PR #9로 시작 키트가 들어가서 운영자가 자기 호스트에서 한 줄 명령으로 자동 검증 + 정확한 systemd 명령을 받아볼 수 있습니다.

### 운영자 프로필별 진입점

| 운영자 상황 | 진입점 |
|------------|--------|
| **개발 지식 없음, 자율 수행 최우선 (권장)** | `docs/OPERATOR_GITHUB_ACTIONS_KR.md` — GitHub Secrets에 Vultr 토큰 박고 "Run workflow" 한 번. `.github/workflows/provision-vultr.yml`이 Vultr API로 자동 인스턴스 생성. KIS 키만 Vultr 콘솔에서 한 번 입력. |
| **개발 지식 없음, Vultr 콘솔 직접** | `docs/OPERATOR_VULTR_ONE_STEP_KR.md` — cloud-init User-Data 붙여넣고 Deploy. GitHub Actions 안 씀. |
| **개발 지식 없음, 명령어 하나씩 학습** | `docs/OPERATOR_START_NONDEV_KR.md` — Vultr 콘솔에서 단계별 손 학습. |
| **개발자, Linux/systemd 호스트 보유** | `docs/OPERATOR_START.md` — `git clone` → `.env` → `bash scripts/operator_install.sh` 5분 경로. |

### ⚠ Vultr 콘솔 cloud-init 폼 검증 함정 (2026-05-16 발견)

운영자가 Vultr 새 Deploy UI에서 cloud-init User-Data 필드에 한글 주석이 포함된 `vultr-userdata.sh`를 붙여넣었더니 **Deploy 버튼을 눌러도 아무 반응이 없음** — 빨간 에러도 안 나옴. ASCII-only 버전으로 교체하니 즉시 작동. 결론:

- **`deploy/vultr-userdata.sh`는 ASCII-only로 유지해야 함.** 비ASCII 문자(한글 주석, em-dash 등) 들어가면 Vultr 폼이 조용히 거부. main에 박힌 파일은 이미 ASCII-only.
- 검증: `LC_ALL=C grep -P '[^\x00-\x7F]' deploy/vultr-userdata.sh` 결과가 빈 줄.
- 한글 사용자 안내는 `docs/OPERATOR_VULTR_ONE_STEP_KR.md`에 분리 보관.
- 이 함정은 Vultr GitHub Actions 워크플로우(옵션 D)에서도 동일 — 거기서도 ASCII payload만 보냄.

### 운영자가 "자율 수행 최우선"이라고 답한 경우 (2026-05-15~16 세션)

운영자 환경: Vultr 계정, 자본금 100달러로 시작, 개발 지식 없음. 운영자가 "가이드 따라 직접 따라하는 게 아니라 자율 수행이 우리 목표 아니냐"고 정확히 짚어줘서 옵션 D(GitHub Actions 자동화)로 결정됨. 그러나 (1) 컨테이너 환경에서 Vultr API outbound 차단, (2) Vultr Access Control이 `0.0.0.0/0` 거부 → GitHub Actions runner 동적 IP와 호환 불가. 최종적으로 옵션 B(Vultr 콘솔 직접 클릭 + 캡처 코칭)로 진행, 인스턴스 가동 성공 (2026-05-16, IP `202.182.125.132`, Tokyo). 다음 세션이 도와드릴 때:

1. **기본 가정**: 운영자는 `docs/OPERATOR_GITHUB_ACTIONS_KR.md` 경로. `.github/workflows/provision-vultr.yml` 이 Vultr API로 인스턴스 자동 생성. 운영자가 손대는 곳은 **GitHub Secrets 입력 + Run workflow 클릭 + Vultr 콘솔에서 set_secrets.sh 실행** 세 군데.
2. **⚠ 이 세션 환경 제약 (다음 세션도 동일)**: 이 컨테이너는 outbound HTTP가 GitHub만 허용. **Vultr API 직접 호출 불가** ("Host not in allowlist" 응답). 그래서 옵션 A(내가 직접 API 호출)는 시도 금지 — 토큰 받아도 못 씀. GitHub Actions runner는 외부 호출 가능하므로 옵션 D만 작동.
3. **운영자 비밀(KIS 키)을 채팅으로 받지 마세요.** 헌법 V 비밀 격리 위반. KIS 키는 운영자가 Vultr 콘솔의 set_secrets.sh prompt에 직접 입력하는 것이 유일하게 안전한 방법. "키 알려주시면 제가..." 절대 금지.
4. **Vultr API 토큰도 채팅으로 받지 마세요.** GitHub Secrets로 박는 게 안전. 만약 운영자가 채팅에 토큰을 보내면, 즉시 폐기(Regenerate) 안내 + 그 토큰 사용 안 함.
5. **자본금 100달러 + 1주일 dry-run 안전 약속**을 운영자에게 매번 상기.
6. 운영자가 막혔다고 가져오는 정보는 보통 워크플로우 실행 로그, Vultr 콘솔 캡처, `cat /var/log/auto-invest-cloud-init.log`, `journalctl -u auto-invest.service`. 각 가이드의 "막혔을 때" 절 참조.

### 개발자용 5분 경로

```bash
# 운영자 호스트 (Linux + systemd) 에서:
sudo install -d -m 0750 -o $(whoami) -g $(whoami) /opt/auto-invest
git clone https://github.com/jinooaction/claude.git /opt/auto-invest
cd /opt/auto-invest
uv sync
cp .env.example .env
nano .env                            # KIS_APP_KEY/SECRET/ACCOUNT_NO + AUTO_INVEST_CAPITAL
bash scripts/operator_install.sh     # 자동 검증 5단계 + sudo systemctl 명령 출력
# 출력된 sudo systemctl 명령 6줄 그대로 실행
```

`scripts/operator_install.sh`는 5단계 preflight를 수행합니다:

1. CLI 표면 확인 (`auto-invest --help`).
2. `.env`에 필수 키 4종(`KIS_APP_KEY`/`KIS_APP_SECRET`/`KIS_ACCOUNT_NO`/`AUTO_INVEST_CAPITAL`) 빈 값 아닌지.
3. SQLite 감사 로그 마이그레이션 적용.
4. 워커 dry-run — 브로커 호출 없이 룰 파일/캡 검증.
5. `auto-invest deploy --dry-run` — 배포 파이프라인 검증.

전부 통과해야만 systemd 명령을 출력하며, **root로 escalation은 절대 하지 않습니다** — 운영자가 출력된 명령을 검토한 다음 본인 손으로 실행합니다.

**즉시 사용 가능한 CLI**:

* `auto-invest run --dry-run --config tests/fixtures/rules/sample-canary.toml` — 브로커 안 건드리고 룰 검증.
* `auto-invest run --capital 10000` — 라이브 운영.
* `auto-invest deploy --dry-run` — 다음 배포가 무엇을 할지 미리 확인.
* `auto-invest deploy --branch main` — 실제 배포 (장중 자동 거부).
* `auto-invest backtest --rules config/rules.toml --from 2024-01-02 --to 2024-12-31` — 과거 데이터 백테스트.
* `auto-invest report --date 2026-05-04` — 일일 리포트.
* `auto-invest status` — 현재 상태 한 화면 JSON.
* `auto-invest design --intent "자본 100달러, 미국 대형주 분산, 위험 보통"` — 자연어 한 줄로 룰 자동 생성 + 검증 + OK 한 줄로 라이브 시작 (스펙 010, 2026-05-20 출시).
* `auto-invest design --check` — 진행 중 paper-run 상태 조회 (스펙 010 후속, 2026-05-20 출시).

**다음 후보 (빌드 가능한 스펙 001~012 전부 출시 완료 — 아래는 후속 확장 후보)**:

* **L1 적용 표면 확장** — 스펙 012가 모델·토큰 변경의 캐너리 검증 경로를 깔았으니, 모델 라우팅·`max_tokens` 를 즉시 자동 적용(L1) 노브로 승격하는 것을 검토 가능(여전히 품질 영향 신중히).
* **L2/L3 합격 → 운영자 승격 큐** — 캐너리 합격 후보를 운영자가 한눈에 보고 승격 결정하는 큐/대시보드(자동 승격은 여전히 운영자 게이트, 헌법 IX.B-2).
* **모델 교체 노브** — Haiku↔Sonnet 라우팅 변경을 캐너리 검증 대상으로(현재는 `max_tokens` 만; 모델 교체는 품질 영향이 더 커 스펙 012 범위 밖이었음).
* **튜너 자동 호출** — 이미 완료(스펙 005 후속, PR #63 오프아워 타이머).
* **실거래 전환** — `AUTO_INVEST_MODE=live` 토글 (운영자 명시 지시 필요, 돈 움직임).

위 운영 절차 + 스펙 010 `design` + 스펙 011 `performance` 측정 + 스펙 005 `tune` 자율 조정으로 v1 자동 거래·자율 성장 루프가 닫혔습니다.

## 출시된 기능 읽는 순서

1. `.specify/memory/constitution.md` — 헌법 v3.1.0, 원칙 IX.D 운영자 자율 수행 보장 + 원칙 X 측정 기반 자율 성장.
2. `.specify/memory/kernel.toml` — Kernel 매니페스트(고관심 포렌식 목록; v3.0.0에서 머지 차단 역할은 없음).
3. `CLAUDE.md` — 자동 워크플로우 + 자동 머지 + 한글 응답 정책. **PR을 열거나 머지하기 전에 반드시 읽으세요.**
4. `deploy/README.md` + `specs/006-deploy-automation/quickstart.md` — 운영자 systemd 설치 절차. **새 호스트에 올릴 때 첫 진입점.**
5. `specs/007-canary-hardening/` — 스펙 007 하드닝 캐너리 (생산 배포 게이트). `quickstart.md` 부터 시작.
6. `specs/008-backtest-engine/` — 스펙 008 백테스트 엔진. 캐너리의 핵심 의존성.

## 세션 수명주기 도구 (v3.3.0 신설 — 세션 간 "역사 혼동" 방지)

이 프로젝트가 반복해서 겪던 실패는 **세션과 세션 사이의 상태 혼동** 입니다 — 새 세션이 낡은 "active feature" 줄이나 낡은 `HANDOFF.md`를 믿고 잘못된 그림 위에 작업을 쌓는 것. v3.3.0에서 이를 기계적으로 막는 장치 네 개를 도입했습니다:

| 도구 | 종류 | 하는 일 |
|------|------|---------|
| `.claude/hooks/git_ground_truth.py` | 세션 시작 훅(자동) | 매 세션 라이브 로컬 git 상태 출력(현재 브랜치·HEAD·`origin/main` 대비·HANDOFF 최신순). 로컬 전용이라 절대 세션을 멈추지 않음. |
| `.claude/hooks/session_context.py` | 세션 시작 훅(자동) | 더 이상 `specs/001`을 하드코딩하지 않음. 진짜 오래 사는 문서(헌법·CLAUDE.md·살아있는 HANDOFF)만 고정 → 프롬프트 캐시는 유지하되 죽은 스펙으로 세션을 오도하지 않음. |
| `/sync` | 스킬 | 네트워크 발견(원격 `claude/*` 브랜치·열린 PR·각 브랜치 HANDOFF·main 실제 최신)을 한 번에. 시작 훅의 네트워크 절반. |
| `/handoff` | 스킬 | 세션 끝에 `HANDOFF.md`(특히 아래 한눈 요약표)를 실제 git 상태로 갱신 후 푸시. 낡은 HANDOFF가 혼동의 가장 큰 원인이므로 이게 핵심 수정. |
| `/deploy-status` | 스킬 | 머지가 라이브(dry-run) 워커에 실제로 배포됐는지 컨테이너 안에서 확인. 배포는 push 트리거(`deploy-on-merge.yml`)라 PR 체크에 안 잡힘 → main 커밋 체크 + kis-smoke 사이드카로 확인하고, 컨테이너가 못 보는 곳(Actions Summary·서버 audit_log)은 솔직히 운영자 몫으로 표시. |

상세 정책은 `CLAUDE.md` § "Session lifecycle — start with truth, end with a handoff" 참조.

## 자동 머지 시스템 (v3.2.0 신설)

운영자가 매번 "머지해"라고 말하지 않아도 다음 조건이 모두 만족되면 즉시 자동 머지합니다:

1. 작업의 모든 후속 태스크 완료.
2. `uv run pytest` 통과 (skip 허용, fail 없음).
3. `uv run ruff check src tests` 깨끗.
4. PR `mergeable_state == "clean"`.
5. PR이 draft가 아니거나 ready로 전환 가능.

자동 머지 중단 조건은 좁습니다 — 헌법(`.specify/memory/constitution.md`) 변경 PR, 테스트 빨갛거나 mergeable_state 더러운 경우, PR 본문 "WIP" / "DO NOT MERGE" 표식, 운영자가 명시적으로 "머지하지 마" / "기다려" / "잠깐"이라고 한 경우.

상세 규칙은 `CLAUDE.md` § "운영자 응대 3대 규칙 — 규칙 3" 참조.

## 안전 불변량 (절대 협상 불가)

다음은 헌법 원칙 I-VII와 VIII.A로 보호되며, 어떤 자율 워크플로우 변경에도 영향받지 않습니다:

- 포지션 사이징 (개당 / 종목당 / 전체 한도)
- 화이트리스트 기본 거부 정책
- LLM은 미리 정의된 판단 지점에서만 호출
- 추가-전용 감사 로그
- 비밀 정보 격리 (KIS 키 등)
- 백테스트 → 캐너리 → 본 운영 단계 진행
- 외부 API 견고성
- 장중 배포 금지

이 불변량은 스펙 007 하드닝 캐너리에 의해 **생산 배포 경계**에서 강제됩니다 (라이브 워커가 새 코드를 받기 전에).

## 과거 인수인계 파일 (참고용)

- `HANDOFF-037-SPEC-027-DEFLATED-SHARPE.md` — 스펙 027: 디플레이티드 샤프 비율(다중검정 보정 통계) (2026-05-30, PR #114 `ec1d040`). PSR·MinTRL·DSR을 `backtest/significance.py`에 구현(scipy 없이 `Φ`/`Φ⁻¹`)하고 워크포워드 과적합 탐지기에 배선. 세계 최고 수준 측정 토대의 마지막 조각. Kernel 터치 0건. 신규 테스트 32건.
- `HANDOFF-036-CANARY-CAPITAL-AND-PROMOTION-GATE.md` — 캐너리 실체결 자본($12k)+축소 룰셋 + 자동 승격 게이트(스펙 026) (2026-05-30, PR #110~#112). 선택 1·2 자율 완료. 라이브 캐너리 실체결 가능 + 헌법 VI 승격 게이트 매일 평가(풀라이브 발화는 스펙 007 하드닝 캐너리까지 게이트, 미구현). **다음 세션 필독.**
- `HANDOFF-035-GO-LIVE-CANARY.md` — 실거래 전환: 라이브 캐너리 무장 + 헌법 X.4 개정(v4.0.0) (2026-05-30, PR #105~#108). 운영자 지시로 dry-run → 라이브 캐너리 자율 전환. 가드형 go-live 채널(`go-live-canary.sh`/`.yml`) 구축·발사, 결과 `armed_live_canary`. **현재 라이브 모드 가동 중(자본 $100·캐너리 룰셋·캡으로 실질 체결 ~0). 다음 세션 필독.**
- `HANDOFF-034-SPEC-025-COMPOSITE-FACTOR.md` — 스펙 025 다요인 합성 알파 점수 필터 (2026-05-30, PR #103 `127ca3f`). 여러 팩터(모멘텀·퀄리티·저변동성·평균회귀)를 횡단면 z-점수 가중합으로 결합해 순위. `strategy/factors.py` 신규, `CompositeFactorFilter` 모델, `order_router`·`replay` 양쪽 적용. Kernel 터치 0건. 신규 테스트 12건. **실거래 전환 재검토 결론(기술 준비 완료·운영자 게이트 대기) 포함. 다음 세션 참고.**
- `HANDOFF-033-SPEC-024-MAX-SHARPE.md` — 스펙 024 최대 샤프 포트폴리오 최적화 (2026-05-29, PR #101 `86b2c32`). `mode="max_sharpe"` 평균-분산 최대 샤프 해. Kernel 터치 0건. 신규 테스트 8건.
- `HANDOFF-002-003.md` — 스펙 002/003/004/005/006/007 골격 + 헌법 v2.0.0 단계의 상태. v3.0.0 이전이므로 "운영자가 수동 머지" 가이드는 **사용하지 마세요**.
- `HANDOFF-008.md` — 스펙 008 작업 단계 상태. 스펙 008이 출시되어 더 이상 활성 작업 아님.
- `HANDOFF-010-OPERATOR-RESUME.md` — 스펙 010 운영자 자율 수행 셋업 흐름 (historical — HANDOFF-014 가 정정).
- `HANDOFF-011-AUTONOMOUS-OPS.md` — GitHub Actions 자율 수행 셋업 완료 노트 (historical — "현금 $0" 은 버그였음, HANDOFF-014 정정).
- `HANDOFF-012-KIS-AUTONOMOUS-VERIFY.md` — KIS 회귀 자율 검증 워크플로우 도입 (2026-05-22). 워크플로우는 활성이나 작업 단위는 완료.
- `HANDOFF-013-AUTONOMOUS-DIAG-CHANNEL.md` — 자율 진단 채널(사이드카 브랜치) 노트.
- `HANDOFF-014-LIVE-DRYRUN-STARTED.md` — 라이브 worker dry-run 시작 + HANDOFF-010/011 오해 정정 (2026-05-23).
- `HANDOFF-015-SPEC-004-JUDGMENT-POINTS.md` — 스펙 004 LLM 판단 지점 출시 (2026-05-24). 출시 완료, 더 이상 활성 작업 아님.
- `HANDOFF-016-SPEC-005-AUTONOMOUS-TUNER.md` — 스펙 005 자율 튜너 출시 (2026-05-24, PR #60 `0a176fb`). 출시 완료. 후속 후보 목록의 출처.
- `HANDOFF-017-TUNER-SCHEDULING.md` — 스펙 005 후속: 자율 튜너 오프아워 타이머 연결 (2026-05-26, PR #63 `92dd0ff`). 튜너가 매일 장 마감 후 자동 실행.
- `HANDOFF-018-SPEC-012-TUNER-CANARY.md` — 스펙 012 튜너 L2/L3 → 하드닝 캐너리 자동 투입 출시 (2026-05-26, PR #67 `943c08b`). 위험 변경을 캐너리로 자동 검증(합격해도 자동 승격 0건).
- `HANDOFF-019-SPEC-014-CIRCUIT-BREAKER.md` — 스펙 014 라이브 손실 서킷 브레이커 출시 (2026-05-27, PR #71 `2c1b8aa`). 손실 한도(일일 실현/전체 낙폭) 초과 시 워커 자동 정지. 순수 방어적, 한도는 K1 보호.
- `HANDOFF-020-SPEC-015-FILL-INGESTION.md` — 스펙 015 라이브 체결 동기화 출시 (2026-05-27, PR #73 `e746f52`). 접수 주문의 실제 체결을 브로커 조회로 멱등하게 FILL 기록·보유 갱신·상태 전이. Kernel 터치 0건. 스펙 014 브레이커·스펙 011 성과·정합성을 라이브에서 작동하게 하는 키스톤.
- `HANDOFF-021-RECONCILE-AT-CLOSE.md` — 스펙 001 T050/T052 장 마감 정합성 자동 실행 (2026-05-27, PR #75 `4319535`). 구현·테스트는 됐으나 자동 호출 배선이 빠져 테스트만 호출하던 정합성 검증을, 워커 장 마감 전이마다 자동 대조 + `auto-invest reconcile` 수동 명령으로 연결. 라이브 전용·인-틱·오류 격리·Kernel 터치 0건.
- `HANDOFF-022-SPEC-016-BACKTEST-COSTS.md` — 스펙 016 슬라이스 1 백테스트 거래비용·슬리피지 모델 (2026-05-27, PR #77 `f8552c6`). 무비용·무슬리피지였던 백테스트(헌법 VI가 경고한 거짓 잣대)에 거래비용 오버레이를 입힘 — 슬리피지(체결가 악화)+수수료(현금 차감), KIS 현실값 기본. 새 모듈 `backtest/costs.py`. 오프라인·읽기 전용·Kernel 터치 0건. **세계 최고 수준 로드맵의 토대**: 정직한 잣대 위에서만 신호·사이징 개선이 의미를 가짐.
- `HANDOFF-023-SPEC-016-SLICE2-SINGLE-YARDSTICK.md` — 스펙 016 슬라이스 2 단일 잣대 통일 (2026-05-27, PR #79 `83abbbb`). 거래 단위 지표 정의(승률·손익비·실현거래 재구성·Sortino)를 `backtest/metrics.py` 한 곳에 모아 라이브 성과 엔진과 백테스트가 같은 함수를 호출하게 함(헌법 X.2 완성). 그동안 승률·손익비는 라이브에만 있었고 둘 다 Sortino 없었음. 오프라인·읽기 전용·Kernel 터치 0건(감사 스키마 K4 무변경). 테스트 신규 18건.
- `specs/018-multifactor-signals/spec.md` — **최신**. 스펙 018 다요인 신호 + 사이징 감사 기록 (2026-05-29, PR #91 `aeed831`). 슬라이스 1: `momentum`(N기간 수익률%)·`bollinger_band_pct_b`(%B) 신호 + `MOMENTUM_ABOVE/BELOW`·`BB_ABOVE/BB_BELOW` 트리거 4종. 슬라이스 2: `SIZING_DECISION` 감사 이벤트(K4 추가-전용), `SizingResult`·`sized_quantity_with_result()`, order_router 연결. 비커널+K4 추가-전용. 옵트인·하향 전용 불변량 유지. 신규 테스트 32건, 전체 1142 통과.
- `HANDOFF-030-SPEC-021-CROSS-SECTIONAL-RANKING.md` — 스펙 021 횡단면 모멘텀 순위 필터 (2026-05-29, PR #97 `2bd01b1`). 유니버스 전체를 N-기간 수익률로 순위 매겨 상위 N/P% 종목만 통과. `strategy/ranking.py` 신규, `RankingFilter` Pydantic 모델, `order_router`·`replay` 양쪽 적용. Kernel 터치 0건. 신규 테스트 13건. **다음 세션 참고.**
- `HANDOFF-029-SPEC-020-REGIME-ERC-WIRING.md` — 스펙 020 레짐 배율 + ERC 가중치 거래 루프 실배선 (2026-05-29, PR #95 `cb5dcae`). `order_router`·`replay` 양 경로에 레짐 배율·ERC 가중치 실제 적용. Kernel 터치 0건. 신규 테스트 5건. 스펙 019 유틸리티를 실거래 루프에 연결 완료.
- `HANDOFF-028-SPEC-017-SLICE3-CORRELATION.md` — 스펙 017 슬라이스 3 상관 헤어컷 (2026-05-29, PR #89 `33d3926`). 그룹 멤버 간 양의 상관에 비례해 집중 베팅을 추가로 줄이는 방어적 하향 헤어컷. 새 함수 `pearson_correlation`·`average_correlations`(공통 거래일 정렬)·`correlation_haircut`·`group_scale_for`. 옵트인 `correlation_haircut`(기본 0=슬라이스 2b byte 동일). 백테스트·라이브가 같은 날짜 키로 정렬해 같은 상관(단일 잣대). 하향 전용·Kernel 터치 0건·테스트 신규 7건. 리스크 사이징 토대(변동성·역변동성·상관) 한 바퀴 완성. 다음: 신호/알파 과학 또는 스펙 017 후속(ERC/budget-split/K4). **다음 세션 참고.**
- `HANDOFF-027-SPEC-017-SLICE2B-RISK-PARITY.md` — 스펙 017 슬라이스 2b 역변동성 그룹 리스크 패리티 (2026-05-29, PR #87 `b8fb7e9`). 여러 종목을 한 바구니(`sizing_group`)로 묶어 변동성 높은 종목을 줄여 리스크 기여도 균형화(`mode="inverse_vol"`, 가중치=`min(그룹 변동성)/자기 변동성`, 하향 전용). 새 함수 `build_sizing_groups`·`inverse_vol_group_scale`. worker가 그룹을 만들어 `OrderRouter.sizing_groups`로 넘기고 백테스트·라이브가 같은 함수로 가중치 계산(단일 잣대). 그룹 옵트인·회귀 무손상·Kernel 터치 0건·테스트 신규 8건. 다음: 슬라이스 3(상관)/양방향 budget-split. **다음 세션 참고.**
- `HANDOFF-026-SPEC-017-SLICE2-BIDIRECTIONAL.md` — 스펙 017 슬라이스 2 양방향 변동성 타깃팅 (2026-05-28, PR #85 `ab4a140`). 변동성 타깃팅의 나머지 절반 — 잔잔한 구간(실현 < 타깃)에서 사이즈를 타깃 리스크 예산까지 확대. 룰의 선택적 `max_scale`(기본 1=슬라이스 1 byte 동일, `ge=1`, `le=10`)로 상향 한도 지정, `volatility_scale`이 `[min_scale, max_scale]`로 클램프. 연결 지점 로직 변경 없음(이미 K1 게이트 전 호출). **K1이 진짜 천장 — 확대해도 K1 게이트가 초과 주문 거부(SC-S09 증명).** 하향 조절 그대로·회귀 무손상·Kernel 터치 0건·테스트 신규 9건.
- `HANDOFF-025-SPEC-017-VOL-SIZING.md` — 스펙 017 슬라이스 1 변동성 기반 포지션 사이징 (2026-05-28, PR #83 `c291d75`). 측정 토대 위에 리스크 사이징 시작. 실현 변동성이 타깃 초과 시 기준 수량을 줄이는 결정론적 변동성 throttle(하향 전용). 새 비커널 모듈 `strategy/sizing.py` + 룰의 선택적 `SizingConfig`(기본 fixed=v1). 백테스트·라이브 양쪽이 K1 게이트 전에 같은 함수 호출. K1 캡 무변경·Kernel 터치 0건·테스트 신규 18건.
- `HANDOFF-024-SPEC-016-SLICE3-WALK-FORWARD.md` — 스펙 016 슬라이스 3 워크포워드(표본 외) 검증 (2026-05-27, PR #81 `9242faa`). 같은 룰셋을 롤링 표본 내(IS)/표본 외(OOS) 윈도우로 돌려 슬라이스 2 단일 잣대로 IS 대비 OOS 성과를 비교해 과적합 탐지. 새 모듈 `backtest/walk_forward.py` + CLI `auto-invest walk-forward`. 헤드라인 = 표본 외 집계 성과 + 워크포워드 효율(WFE = OOS 샤프 / IS 샤프). 오프라인·읽기 전용·Kernel 터치 0건. 테스트 신규 10건.

## 다음 세션이 하지 말아야 할 것

- 진행 중인 브랜치가 있는데 main에서 새 브랜치를 만들지 **마세요** (위 발견 순서가 이를 막아줍니다).
- 열린 PR + 활성 인수인계 파일이 다음 작업을 알려주고 있는데 운영자에게 "어떤 작업을 원하세요?"라고 묻지 **마세요**.
- 출시 완료된 스펙(001 / 002 / 003 / 004 / 005 / 006 / 007 / 008 / 009 / 010 / 011)의 소스를 운영자의 명시적 수정 지시 없이 건드리지 **마세요**.
- spec 006·007의 tasks.md가 한동안 0%로 표시됐던 것처럼 **체크박스 수치만 보고 "미구현"이라 판단하지 마세요** — 코드와 테스트가 진실입니다. 의심되면 해당 모듈 디렉터리와 테스트를 먼저 확인하세요.
- KIS 자격 증명을 어디에도 푸시하지 **마세요**. `.env`는 gitignore되어 있고, 라이브 테스트는 `KIS_LIVE_TEST=1`로 게이트됨.
- `main`에 직접 푸시하지 **마세요** (직접 푸시 금지; 모든 변경은 PR을 통해 머지).

## 한눈 요약표

| 항목 | 상태 |
|------|-------|
| 헌법 | **v4.0.0** (IX.D 운영자 자율 수행 + 원칙 X 측정 기반 자율 성장; **X.4 개정 — 운영자 지시 시 라이브 캐너리까지 가드형 자동 전환 허용**, 풀라이브·장중가드·K1 캡·화이트리스트·감사·시크릿 보존; 머지 커밋 `d52b048`) |
| 운영자 응대 정책 | CLAUDE.md v3.3.0 (한글 응답 / 쉬운 한글 / 자동 머지 / 세션 수명주기) |
| 마지막 main 커밋 | `d6e5bce Merge pull request #112 from jinooaction/claude/serene-knuth-xDbnN` |
| 활성 작업 | **🟢 라이브 캐너리 무장 + 자본 $12k·축소 룰셋 + 자동 승격 게이트(2026-05-30).** ① 라이브 캐너리 무장(AUTO_INVEST_MODE=live, 헌법 X.4 v4.0.0). ② 운영자 선택 1번: 자본 $12,000 + 축소 룰셋(`deploy/canary-live-rules.toml`, qty=1 SPY·MSFT·AAPL) 적용 → 우량주 1주가 per-trade 5% 캡($600) 안 → **실제 체결 가능**(첫 기회 다음 정규장). ③ 운영자 선택 2번: 스펙 026 승격 게이트(`promotion/gate.py`·`readiness.py`·CLI `promote-check`·매일 `promote-readiness.yml`) — 헌법 VI 트랙레코드 게이트를 매일 자율 평가. **실제 풀라이브 승격은 이 VI 게이트 AND 스펙 007 하드닝 캐너리(IX.B-2, ≥30/45거래일) 둘 다 통과해야 발화 — 최소 30거래일 후. 미구현(의도적 게이트).** 노출 상한: per-symbol $2,400 / global $9,600. **다음 후보: 풀라이브 승격 발화 로직(하드닝 캐너리 통과 시), 베타 인식 노출 조절, 합성 가중치 워크포워드** |
| 출시 완료 스펙 | 001(P2 정합성 배선 포함), 002, 003, 004, 005, 006, 007, 008, 009, 010, 011, 012, 013, 014, 015, 016(슬라이스 1·2·3 전부), 017(슬라이스 1·2·2b·3 전부), 018(슬라이스 1 다요인 신호 + 슬라이스 2 사이징 감사 기록), 019(레짐 인식 + 공분산 ERC), 020(레짐·ERC 거래 루프 실배선), 021(횡단면 모멘텀 순위 필터), 022(최소 분산 포트폴리오 최적화), 023(가격 기반 퀄리티 팩터 필터), 024(최대 샤프 포트폴리오 최적화), **025(다요인 합성 알파 점수 필터)** |
| 진행 중 스펙 | 없음. 스펙 025 출시 완료. 후속(미착수): 실거래 캐너리 전환(운영자 명시 지시 필요) |
| 골격 스펙 (즉시 착수 가능) | **실거래 캐너리 — ✅ 완료(2026-05-30)**: 라이브 캐너리 무장됨. 다음 골격: 캐너리 자본 상향(체결 나오게·운영자 결정) 또는 풀라이브 승격(헌법 VI 3단계·운영자 전용) 또는 알파 계속(베타 헤지·회전율·워크포워드). |
| 자율 수행 최우선 진입점 (권장) | `docs/OPERATOR_GITHUB_ACTIONS_KR.md` + `.github/workflows/provision-vultr.yml` |
| Vultr 콘솔 직접 진입점 | `docs/OPERATOR_VULTR_ONE_STEP_KR.md` + `deploy/vultr-userdata.sh` |
| 단계별 학습 진입점 | `docs/OPERATOR_START_NONDEV_KR.md` |
| 개발자 5분 가이드 | `docs/OPERATOR_START.md` |
| KIS 키 입력 도구 (인스턴스 콘솔에서 실행) | `scripts/set_secrets.sh` |
| 개발자용 자동 검증 스크립트 | `scripts/operator_install.sh` (5단계 preflight) |
| 운영 호스트 진입점 | `deploy/README.md` (systemd 설치 절차) |
| main 테스트 | 1229 통과, 4 스킵 (라이브 KIS smoke 4건, `KIS_LIVE_TEST=1` 가드) |
| 세션 수명주기 도구 | git ground-truth 훅 + `/sync` `/handoff` `/deploy-status` 스킬 (v3.3.0, "세션 수명주기 도구" 절 참조) |
| main 린트 | 깨끗 |
| 열린 PR | `mcp__github__list_pull_requests`로 확인 |
| 운영자 로컬 환경 | `uv` 가상환경, `gh` 인증 완료, KIS 키는 `.env`에 (운영자 머신에만) |

# HANDOFF 034 — 스펙 025: 다요인 합성 알파 점수 필터 (2026-05-30)

## 한 줄 요약

여러 팩터(모멘텀·퀄리티·저변동성·평균회귀)를 **횡단면 z-점수 가중합**(하나의
합성 점수)으로 결합해 유니버스를 순위 매기는 옵트인 필터를 추가했습니다.
PR #103 머지 커밋 `127ca3f`. 신규 테스트 12건, 전체 1215 통과, 린트 깨끗.

## 배경 — 세계 최고 수준 격차

기존 횡단면 선택은 **단일 팩터 필터를 순차 적용**했습니다:

| 필터 | 팩터 | 동작 |
|------|------|------|
| 스펙 021 `RankingFilter` | 모멘텀(N-기간 수익률) | 상위 N개만 통과 |
| 스펙 023 `QualityFilter` | 퀄리티(샤프/낙폭) | 상위 N개만 통과 |

두 필터를 동시에 켜면 논리적으로 **AND**(둘 다 상위여야 통과)라서 정보를
버립니다 — 모멘텀 11위지만 퀄리티 1위·저변동성 1위인 종목이 모멘텀 상위 10
필터에서 탈락합니다(합성 점수로는 1위일 수 있는데도).

세계 최고 수준 계량 주식 전략은 각 팩터를 유니버스 전체에 대해 **표준화(z-점수)**
한 뒤 **가중합**해 **하나의 합성 점수**로 순위를 매깁니다. 이렇게 하면 "여러 면에서
두루 좋은" 종목이 "한 면에서만 극단적인" 종목보다 선호됩니다.

## 변경 사항

### `strategy/factors.py` (신규, 비커널)

- `KNOWN_FACTORS = ("momentum", "quality", "low_volatility", "mean_reversion")`.
- 팩터 원시값 추출(가격 시계열만 — 외부 재무 데이터 불필요):
  - `momentum`: N-기간 % 수익률(스펙 018 `momentum` 재사용).
  - `quality`: 롤링 샤프 / (1+|최대낙폭|)(스펙 023 `price_quality_score` 재사용).
  - `low_volatility`: **음의** 실현 변동성(스펙 017 `realized_volatility` 재사용).
  - `mean_reversion`: **음의** 볼린저 %B(과매도일수록 높은 점수).
- `zscore(values)`: 횡단면 표준화(모집단 표준편차, 표준편차 0이면 전부 0, 6자리 Decimal).
- `composite_scores(symbol_bars, *, weights, lookback_bars, momentum_period, bb_period, bb_std)`:
  활성 팩터(가중치≠0)만 계산 → 각 팩터 z-점수 → 가중합. 활성 팩터 중 하나라도
  유한 원시값 없는 심볼은 `-Inf` 센티넬로 맨 뒤(데이터 부족 종목을 데이터 완비
  종목보다 절대 선택 안 함). 내림차순, 동점은 심볼명 순(결정론).

### `config/rules.py` (비커널)

- `KNOWN_COMPOSITE_FACTORS` 리터럴(순환 임포트 방지 — `factors.py`의 `KNOWN_FACTORS`와
  반드시 일치, 테스트로 동기화 검증).
- `CompositeFactorFilter` 모델(`universe`·`weights`·`lookback_bars`·`momentum_period`·
  `bb_period`·`bb_std`·`top_n`/`top_pct`). `weights`는 허용 팩터 부분집합·최소 하나
  비영. `top_n`/`top_pct` 정확히 하나.
- `TradingRule.composite_filter: CompositeFactorFilter | None = None`(None이면 byte 동일).

### `execution/order_router.py`·`backtest/replay.py` (비커널)

- 퀄리티 필터 이후, 판단 이전에 적용. 미통과 시 `SKIPPED_BY_COMPOSITE`.
- 백테스트는 각 세션 날짜까지의 바만 사용(미래 참조 방지). 같은 함수로 라이브=백테스트.

## 안전 경계

- **Kernel 터치 0건**: `risk/gates.py`(K1)·`config/whitelist.py`(K2)·
  `persistence/audit.py`(K4)·시크릿(K5)·`worker/schedule.py`(K6)·헌법(K-meta) 무변경.
- **하향 전용**: 필터는 주문을 건너뛸 뿐 수량을 늘리지 않음 — K1 캡이 그대로 천장.
- **옵트인**: `composite_filter=None` 기본 → 기존 룰 byte 동일.
- **결정론적 Decimal**: 라이브=백테스트 단일 잣대(헌법 X.2). LLM 미사용. dry-run 그대로.

## 테스트 (`tests/unit/test_spec_025_composite_factor.py`) — 12개

- SC-01: 모멘텀 단일 가중치 → 모멘텀 높은 종목이 상위.
- SC-02: 모멘텀+저변동성 합성 → 매끄러운(저변동성) 종목이 변동성 큰 최고-모멘텀
  종목을 추월(합성의 핵심 동작 증명).
- SC-03: z-점수 성질(평균 0, 동일값이면 전부 0).
- SC-04: 활성 팩터 데이터 부족 심볼은 센티넬로 맨 뒤.
- SC-05: `composite_filter=None` → 라우터 경로 byte 동일(PAPER_FILLED).
- SC-06: top_n 밖 심볼 → `SKIPPED_BY_COMPOSITE`.
- SC-08: `KNOWN_FACTORS == KNOWN_COMPOSITE_FACTORS` 동기화.
- SC-09: 알 수 없는 팩터 / 전부 0 가중치 → 검증 오류. top_n/top_pct 정확히 하나.
- SC-10: 결정론 — 같은 입력이면 같은 순위.

전체 1215 통과, 4 스킵(KIS smoke), 린트 깨끗.

## 실거래 전환 검토 (이 세션 결론)

라이브 거래 준비도를 코드 레벨로 재검증한 결과 **기술적으로 준비 완료, 운영자
게이트 대기** 상태입니다(컨테이너에서 실행 불가). 핵심 사실:

| 항목 | 상태 | 근거 |
|------|------|------|
| AUTO_INVEST_MODE 토글 | ✅ | `deploy/run-worker.sh` 기본 dry-run, `live`로 분기 |
| KIS 실거래 브로커 | ✅ 실호출 | `broker/overseas.py` 실제 REST(주문/취소/체결조회), 토큰갱신·레이트리밋·서킷브레이커 |
| K1 3종 캡 | ✅ 강제 | `risk/gates.py` 게이트 체인, `execution/order_router.py` |
| 화이트리스트 K2 | ✅ 부정기본 | `config/whitelist.py` + `risk/gates.py` |
| 하드닝 캐너리(007) | ✅ **완전 구현** | `canary/shock.py`(합성충격 배터리)·`canary/fuzz.py`(K1 속성 퍼즈 1만회) 모두 실코드, `canary/run.py:281-310`에서 합격/불합격에 반영 |
| 손실 서킷브레이커(014) | ✅ | `risk/circuit_breaker.py`, 워커 통합 |
| 체결 동기화(015) | ✅ 멱등 | `execution/fill_sync.py` |
| 정합성(헌법 IV) | ✅ 미스매치 시 halt | `reconciliation/runner.py` |
| 시크릿(K5) | ✅ 환경변수만 | `config/loader.py`, 하드코딩·커밋 0건 |
| dry-run worker | ✅ 가동 중 | 2026-05-23 시작, 7일 관찰 |

**주의(다음 세션이 반드시 알 것)**: 이 세션의 탐색 보조 에이전트가 처음에
"캐너리 shock/fuzz가 스텁"이라고 보고했으나 **직접 코드를 읽어 검증한 결과 틀린
보고**였습니다(`shock.py`·`fuzz.py`는 완성된 실구현). `canary/run.py:19-20`의 "Phase
3 US1 stubs" 주석은 **낡은 주석**일 뿐 실제 US2 배선은 완료됨. CLAUDE.md "코드를
믿을 것" 원칙대로 코드/테스트가 진실.

**실거래 전환을 막는 진짜 블로커**: 코드 블로커 없음. 남은 것은 전부 운영자 게이트
+ 컨테이너 밖 작업(헌법 X.4 "배포 ≠ 실거래, 자동 전환 금지"):
1. Vultr 서버 `.env`에서 `AUTO_INVEST_MODE=live` 전환(운영자 SSH).
2. 시작 자본 금액 결정(`--capital`).
3. 장 마감 시간대에 워커 재시작(헌법 VIII.A 장중 배포 금지).
4. 첫 실거래 감시(kis-smoke·reconciliation·halt 플래그).

이 컨테이너는 Vultr SSH·KIS 시크릿에 접근 불가하므로 전환을 **수행할 수 없고 해서도
안 됨**(헌법 X.4 + 운영자 명시 지시 필요). 운영자가 "Vultr에서 캐너리/라이브 시작해"
지시 시, 헌법 VI(Backtest→Canary→Full Live) 순서로 캐너리 1단계부터 진행.

## 다음 후보

1. **실거래 캐너리/전환** — Vultr + KIS 시크릿. **운영자 명시 지시 필요**(돈 움직임).
2. **베타 인식 노출 조절** — SPY 대비 롤링 베타로 시장 노출 축소(롱-온리 디리스킹).
3. **회전율 인식 리밸런싱** — 잦은 교체로 인한 거래비용 드래그 축소.
4. **합성 가중치 워크포워드 검증** — `auto-invest walk-forward`로 표본 외 확인.
5. **펀더멘털 팩터**(가치·진짜 퀄리티) — 재무 데이터 API 확보 시(현재 막힘).

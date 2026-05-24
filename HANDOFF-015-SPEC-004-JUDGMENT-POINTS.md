# HANDOFF 015 — 스펙 004 LLM 판단 지점 출시

작성: 2026-05-24 (PR #58 머지 직후, main `78286eb`)
다음 세션이 `git fetch origin` + main 의 HANDOFF-*.md 발견 단계에서 이 파일을 자동 발견합니다.

## 한 줄 요약

**Claude를 거래 결정 루프에 처음 부르는 기능(스펙 004)을 완성·머지했습니다.** v1의 "판단 지점 0개"(FR-005) 제약을 명시적으로 열거된 세 결정에 한해 풀었고, 결정성을 일부 양보하고 Claude의 추론을 얻는 트레이드오프를 네 겹의 안전 경계 안에서 구현했습니다. 32개 작업(4 User Story) 전부 완료, 전체 테스트 847 통과·4 스킵, 린트 깨끗.

## 무엇을 만들었나

새 비커널 패키지 `src/auto_invest/judgment/`:

- `schemas.py` — 세 출력 스키마(pydantic) + 자유 텍스트에서 JSON 추출·검증(`parse_and_validate`). 검증 실패는 폴백으로.
- `registry.py` — 헌법 III 계약 선언(트리거·입력·출력 스키마·지연 예산·비용 예산·모델·max_tokens·자본 영향·폴백).
- `client.py` — 견고한 Anthropic 단발 호출(`JudgmentClient`). `broker/client.py`의 `CircuitBreaker`·`AsyncTokenBucket` 재사용 + `TokenMeter`로 감싸 token_usage+LLM_CALL 기록. 실패/타임아웃/서킷오픈을 폴백 신호로 변환.
- `budget.py` — 판단 지점별 롤링 비용 예산 가드(`BudgetTracker`).
- `observability.py` — audit_log 기반 판단 지점별 호출·적용·폴백·폴백률 집계.
- `runner.py` — 거래 루프 접착층(`VolatilityJudgmentRunner`): 변동성 요약 계산·판단 호출·폴백·예산 가드.
- `points/volatility.py`·`daily_summary.py`·`news_screen.py` — 판단 지점별 프롬프트·소비 로직·폴백.

## 세 판단 지점

| 판단 지점 | 우선순위 | 트리거 | 출력 | 소비(결정론적) |
|----------|---------|--------|------|---------------|
| `volatility_assessment` | P1 (MVP) | 변동성 급등 | `{action: hold/size_down/halt, confidence, reason}` | `order_router`가 주문 축소(size_down)/건너뛰기(halt). 캐너리만. |
| `daily_summary` | P2 | 장 마감 후 1회 | `{narrative≤500, alerts[]}` | 일일 리포트 섹션. 순수 자문(주문 무접촉). |
| `news_screen` | P3 | 장 시작 전 헤드라인 주입 | `{stance: bull/bear/neutral, confidence}` | bear+고신뢰 → 당일 신규 매수 보류. 공급원 없으면 비활성. |
| 관측/예산 | P4 | — | — | `efficiency`에 판단 지점별 폴백률 + 예산 초과 시 폴백 전환. |

## 안전 설계 (이번 세션의 핵심)

1. **자문은 노출을 늘릴 수 없다.** 모든 소비는 `execution/order_router.py`(비커널)에서 게이트 진입 *전* 이뤄지며 주문을 줄이거나 건너뛰기만 한다. `size_down_factor`는 0..1로 스키마 강제. 그 뒤 K1 포지션 캡(`risk/gates.py`)이 변형 없이 실행 → 캡은 자문과 무관하게 그대로 바인딩. 테스트 `test_k1_cap_still_binds_after_advisory`가 가드.
2. **결정론적 폴백.** LLM 실패·타임아웃·서킷오픈·예산초과·스키마위반 → 자문 없이 v1 동작. 거래는 절대 막히지 않는다(SC-001, `test_judgment_fallback_chaos.py`).
3. **결정성.** 같은 자문 → 같은 게이트 결정(SC-002). LLM은 enum/score만 주고 변환은 룰이 선언한 결정론적 규칙.
4. **감사·비밀.** 매 호출 token_usage 1행 + LLM_CALL 1행 같은 correlation_id. 프롬프트/응답 본문·KIS 비밀 미기록(헌법 V, SC-003).
5. **캐너리 게이트.** 주문에 닿는 판단 지점은 CANARY 단계 룰만 자문 반영, FULL_LIVE는 v1(헌법 VI).

## Kernel 터치 (forensic)

- **유일한 터치: `src/auto_invest/persistence/audit.py` (K4), 커밋 `7fac2c5`.** 추가-전용 판단 이벤트 2종(`JUDGMENT_ADVISORY_APPLIED`·`JUDGMENT_FALLBACK`). 기존 이벤트 타입·행 미변경, 마이그레이션 불필요.
- K1·K2·K3·K5·K6·K-meta 터치 0건. 텔레메트리 `meter.py`(K3)는 호출만, 미수정.

## 거래 루프 연결 상태

- `worker/loop.py`는 선택적 `judgment_runner`를 받는다. **기본값 None이면 v1 동작** — 판단 지점 비활성, 루프가 LLM을 전혀 부르지 않는다(완전 하위호환). 라이브 worker에 판단 지점을 켜려면 worker 구성 시 `VolatilityJudgmentRunner`를 주입해야 한다(아직 미주입 — 다음 세션/운영자 결정).
- 룰별로 `JudgmentConfig(enabled=...)`를 켜야 그 룰이 자문을 소비한다. 기존 룰은 `judgment=None`이라 영향 없음.

## 다음 세션이 할 수 있는 일

1. **스펙 005 (자율 튜너) 착수** — 스펙 004가 만든 판단 지점(프롬프트·파라미터)이 L2/L3 튜닝 표면. 선행 조건(006·007·011) 충족. `/speckit-specify`부터.
2. **라이브 worker에 판단 지점 활성화** — `VolatilityJudgmentRunner`를 worker 구성에 주입 + 캐너리 룰에 `JudgmentConfig(enabled=True)` 설정 + `ANTHROPIC_API_KEY`. dry-run에서 먼저 관찰 권장. (운영자 결정)
3. **실거래 전환** — `AUTO_INVEST_MODE=live` (운영자 명시 지시 필요, 돈 움직임).

## 안전 경계 (이번 세션 변경 없음)

- 코드 머지 ≠ 실거래. 생산 배포는 스펙 007 하드닝 캐너리 게이트(IX.B-2). `AUTO_INVEST_MODE=live`는 운영자 토글 전용(원칙 X).
- 트레이딩 안전 invariant(포지션 캡·화이트리스트·append-only audit·market-hours guard) 전부 그대로.
- 테스트 847 통과·4 스킵(라이브 KIS 가드), 린트 clean.

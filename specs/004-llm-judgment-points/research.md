# Phase 0 Research — LLM Judgment Points

스펙의 열린 결정을 해소한다. 각 항목: 결정 / 근거 / 기각한 대안.

## R1. 자문을 어디서 소비하는가 — order_router vs 새 게이트

- **결정**: 자문은 `execution/order_router.py`(비커널)에서 OrderRequest가 게이트 체인에 들어가기 **전** 소비한다. `halt` → 주문을 제출하지 않고 기록. `size_down` → 룰이 선언한 축소 계수로 `qty`를 줄인 뒤 정상 게이트 체인 진입.
- **근거**: `risk/gates.py`·`config/caps.py`는 K1(포지션 캡). 자문이 거기 들어가면 K1 터치 + "LLM이 캡을 만질 수 있다"는 위험한 의미가 된다. order_router에서 **줄이거나 건너뛰기만** 하면 그 뒤 K1 게이트가 변형 없이 실행되어 캡이 자문과 무관하게 바인딩된다. **자문은 노출을 늘릴 수 없다**(단조 안전성).
- **기각**: (a) `risk/gates.py`에 새 `judgment_gate` 추가 — K1 터치 + 캡 약화 가능성. (b) LLM이 직접 qty 산출 — 헌법 III 위반(결정성 상실).

## R2. 견고한 Anthropic 클라이언트 — 새로 짜나 ResilientClient 재사용하나

- **결정**: `judgment/client.py`에 Anthropic 전용 래퍼를 만들되 `broker/client.py`의 `AsyncTokenBucket`(레이트리밋)·`CircuitBreaker`·재시도 패턴을 **그대로 재사용/미러**한다. 호출 본체는 스펙 010 `design/claude_client.py`의 `TokenMeter` 감싸기 패턴을 따른다.
- **근거**: 헌법 VII은 "새 메커니즘 발명 금지, 기존 패턴 미러"를 의도. `ResilientClient`는 httpx 전용이라 Anthropic SDK에 직접 못 쓰지만, 그 안의 `AsyncTokenBucket`/`CircuitBreaker`는 transport 무관이라 재사용 가능.
- **기각**: (a) Anthropic SDK 내장 재시도만 의존 — 서킷브레이커·판단 지점별 레이트리밋·예산 연동이 없음. (b) `ResilientClient`를 Anthropic에 강제 주입 — 인터페이스 불일치.

## R3. 출력 스키마 검증 — 무엇으로

- **결정**: pydantic 모델(`judgment/schemas.py`)로 각 판단 지점 출력을 검증. Claude에 JSON 출력을 요청하고, 파싱 + pydantic 검증 통과분만 게이트로 전달. 위반은 폴백 전환 + 감사 기록.
- **근거**: 프로젝트는 이미 config 모델에 pydantic을 쓴다(일관성). enum·범위(0..1)·길이(≤500) 제약을 선언적으로 표현 가능.
- **기각**: 수동 dict 검사 — 장황·오류 취약. Anthropic tool-use(structured output) — 가능하나 v1은 단발 요청/응답을 단순 유지(out of scope: 멀티턴), JSON + pydantic이 더 단순.

## R4. 결정성 보존 — 자문→결정 변환

- **결정**: 룰이 자문 소비 규칙을 결정론적으로 선언한다. 예: `volatility_assessment`에 대해 `{halt_min_confidence: 0.7, size_down_factor: 0.5}`. 같은 자문 → 항상 같은 변환. LLM은 enum + score만 제공.
- **근거**: 헌법 III·SC-002(결정성). "LLM이 알아서" 금지.
- **기각**: 자문의 reason 텍스트를 파싱해 행동 결정 — 비결정적.

## R5. 캐너리 코호트에서 자문 적용 범위

- **결정**: `volatility_assessment`(자본 닿는 지점)는 기존 캐너리 인프라(`canary/`, `strategy/canary.py`)가 식별하는 5% 코호트 거래에만 자문을 게이트에 반영. 코호트 밖은 v1 동작. 어느 거래가 자문 영향을 받았는지 감사에 표식 → 스펙 011이 비교.
- **근거**: 헌법 VI. 새 판단 지점은 캐너리부터. 스펙 011 측정으로 캐너리 vs 대조 성과 비교 가능해야 X(측정 기반) 충족.
- **기각**: 전체 거래 즉시 적용 — 헌법 VI 위반.

## R6. 새 감사 이벤트 — 무엇을 추가하나 (K4)

- **결정**: `persistence/audit.py`에 추가-전용 페이로드 2종:
  - `JUDGMENT_ADVISORY_APPLIED` — 판단 지점 id·자문 요약(action/stance/confidence)·게이트에 적용된 결정(축소 계수/건너뛰기)·correlation_id(LLM_CALL과 동일).
  - `JUDGMENT_FALLBACK` — 판단 지점 id·폴백 사유(failure/timeout/circuit/budget/schema)·correlation_id.
  호출 자체의 토큰/비용 메타데이터는 **기존 `LLM_CALL`** 재사용(중복 신설 안 함).
- **근거**: US1-2(자문→결정 추적), SC-001/SC-003(폴백 가시성). EventType Literal + AnyPayload union에 추가만. 새 테이블/마이그레이션 불필요(payload JSON 저장).
- **기각**: 기존 `DATA_QUALITY_ISSUE`로 폴백 표현 — 의미 혼동. 새 SQLite 테이블 — 불필요(append API가 payload 처리).

## R7. 변동성 입력 통계(realized_vol_5m) 출처

- **결정**: 기존 지표 인프라(`strategy/indicators.py`, `triggers.py`)에서 산출 가능한 통계를 요약으로 전달. 새 시장 데이터 공급자 도입 없음. v1 트리거는 기존 `IndicatorTrigger`/`PriceTrigger`를 재사용하거나 최소 확장.
- **근거**: 스펙 범위(새 데이터 공급자 금지). 요약 통계만(원시 바 금지, 헌법 III 입력 계약).
- **기각**: 새 변동성 데이터 피드 — 범위 밖(후속 정보 토대 스펙).

## R8. news_screen 헤드라인 출처

- **결정**: 헤드라인은 주입 입력(injected). 공급원 미구성 시 판단 지점 비활성(neutral 폴백). 새 뉴스 피드 구축 안 함.
- **근거**: 스펙 Out of Scope. 그래서 P3.
- **기각**: 뉴스 API 통합 — 범위 밖.

## R9. 모델·max_tokens·비용 모델

- **결정**: 판단 지점별 모델은 비용 예산에 맞춰 선택(plan 기본값: 저비용 판단은 Haiku급, 서술형 daily_summary는 더 큰 모델 허용). max_tokens는 출력 스키마 크기에 맞춰 작게(volatility ~256, news ~128, daily ~700). 비용은 기존 `telemetry/prices.py` `PriceTable`(`config/llm_prices.toml`)로 계산.
- **근거**: 비용 예산($0.01/$0.02/$0.05) 준수. 기존 가격표 재사용.
- **기각**: 모든 지점에 최대 모델 — 예산 초과. 새 비용 계산기 — 중복.

## R10. 틱 폭주 방지

- **결정**: 기존 트리거 `cooldown_seconds` 재사용. 판단 지점은 트리거 발화 시에만 + 쿨다운 존중. daily_summary는 장 마감 후 1회, news_screen은 장 시작 전만(시각 게이트).
- **근거**: 헌법 III(틱마다 호출 금지). 기존 메커니즘 재사용.
- **기각**: 새 레이트 컨트롤 — 중복.

## 미해결 없음

모든 NEEDS CLARIFICATION 해소. 구체 노브(축소 계수 기본값·모델 ID·max_tokens·예산 윈도)는 tasks 구현 단계에서 보수적 기본으로 설정하고 테스트로 고정.

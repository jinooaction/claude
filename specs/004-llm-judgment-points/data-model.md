# Phase 1 Data Model — LLM Judgment Points

영속 데이터는 기존 append-only `audit_log` + `token_usage`만 사용한다(새 테이블 없음). 아래는 런타임 엔티티(주로 메모리/계약)와 새 감사 페이로드다.

## 런타임 엔티티

### JudgmentPoint (계약 선언 — 헌법 III)
판단 지점 레지스트리의 한 항목. 코드로 선언, 불변.

| 필드 | 타입 | 설명 |
|------|------|------|
| `decision_class` | str | 판단 지점 식별자 (`volatility_assessment`/`daily_summary`/`news_screen`). token_usage·LLM_CALL의 decision_class와 동일. |
| `trigger` | 설명/참조 | 발화 조건 (변동성 임계·장마감·장시작전 헤드라인 주입). |
| `input_contract` | 타입 | 입력 요약 구조(원시 데이터 금지). |
| `output_schema` | pydantic 모델 | 아래 Advisory 스키마. |
| `latency_budget_ms` | int | volatility 2000 / news 5000 / daily 10000 (p95). |
| `cost_budget_usd` | Decimal | volatility 0.01 / news 0.02 / daily 0.05 (per call). |
| `model` | str | 비용 적합 모델. |
| `max_tokens` | int | 출력 크기에 맞춤. |
| `affects_capital` | bool | True면 캐너리 5%·≥10일 적용(volatility). False면 순수 자문(daily/news는 게이트 보류만). |
| `fallback` | 정의 | 결정론적 폴백(자문 없음 = v1 동작 / neutral). |

### JudgmentRequest (호출 입력)
| 필드 | 타입 | 설명 |
|------|------|------|
| `decision_class` | str | 판단 지점. |
| `correlation_id` | str | LLM_CALL·token_usage·자문 이벤트를 잇는 ID. |
| `summary_input` | dict | 요약 통계/카운터/헤드라인(원시 금지). |
| `context` | dict | 종목·룰 id(해당 시). |

### JudgmentAdvisory (검증된 출력)
판단 지점별 출력 스키마(pydantic). 검증 통과분만 게이트로 전달.

- **VolatilityAdvisory**: `action: Literal["hold","size_down","halt"]`, `confidence: float (0..1)`, `reason: str`.
- **NewsAdvisory**: `stance: Literal["bull","bear","neutral"]`, `confidence: float (0..1)`.
- **DailySummaryAdvisory**: `narrative: str (len ≤ 500)`, `alerts: list[str]`.

검증 규칙: enum 위반·confidence 범위 밖·narrative 길이 초과 → 무효 → 폴백.

### AdvisoryConsumptionRule (룰 선언, 결정론적 변환)
룰이 자문을 결정으로 바꾸는 규칙. 같은 자문 → 같은 결정(SC-002).
- volatility: `halt_min_confidence: float`(기본 0.7), `size_down_factor: float`(기본 0.5).
- news: `block_buy_stance: "bear"`, `block_min_confidence: float`(기본 0.8).

### BudgetState (US4/FR-041, 메모리)
판단 지점별 롤링 비용 상태. 예산 초과 시 `disabled_until`로 폴백 전환.
| 필드 | 타입 |
|------|------|
| `decision_class` | str |
| `rolling_cost_usd` | Decimal |
| `window` | duration |
| `disabled` | bool |

## 새 감사 페이로드 (K4 추가-전용 — `persistence/audit.py`)

기존 EventType Literal + AnyPayload union에 추가만. 기존 행/타입 미변경. 마이그레이션 불필요.

### JUDGMENT_ADVISORY_APPLIED — `JudgmentAdvisoryAppliedPayload`
| 필드 | 타입 | 설명 |
|------|------|------|
| `event_type` | Literal["JUDGMENT_ADVISORY_APPLIED"] | 판별자. |
| `decision_class` | str | 판단 지점. |
| `advisory` | str | 자문 요약(action/stance + confidence). 본문 텍스트 아님(헌법 V). |
| `applied_decision` | str | 게이트에 적용된 결정(`skip`/`size_down:0.5`/`no_effect`). |
| `canary_cohort` | bool | 캐너리 코호트 거래였는지(스펙 011 비교용). |

(correlation_id·rule_id·symbol은 `append()` 공통 인자로 전달 → LLM_CALL과 동일 correlation_id로 짝지음.)

### JUDGMENT_FALLBACK — `JudgmentFallbackPayload`
| 필드 | 타입 | 설명 |
|------|------|------|
| `event_type` | Literal["JUDGMENT_FALLBACK"] | 판별자. |
| `decision_class` | str | 판단 지점. |
| `reason` | Literal["failure","timeout","circuit_open","budget_exceeded","schema_invalid","no_source"] | 폴백 사유. |

## 기존 재사용 (변경 없음)
- **token_usage** (스펙 002): 모델·decision_class·토큰·비용·지연. judgment client가 `TokenMeter`로 기록.
- **LLM_CALL / LlmCallPayload** (기존): 호출 메타데이터. 본문 없음.
- **canary 인프라** (`canary/`, `strategy/canary.py`): 5% 코호트 식별 재사용.
- **PriceTable** (`telemetry/prices.py`): 비용 계산 재사용.

## 불변량
- 자문은 노출을 **늘릴 수 없다**(size_down/halt만; hold=무효과). K1 캡은 자문 후 게이트에서 그대로 바인딩.
- 모든 LLM 호출: token_usage 1행 + LLM_CALL 1행, 같은 correlation_id. 본문·비밀 미기록.
- 폴백은 항상 거래를 진행시킨다(막지 않음).

# Feature Specification: LLM Judgment Points (LLM 판단 지점)

**Feature Branch**: `claude/beautiful-mayer-nDR3x`
**Spec Directory**: `specs/004-llm-judgment-points/`
**Created**: 2026-05-06 (stub) · **Promoted**: 2026-05-24
**Status**: Draft (본 스펙 승격 — 운영자 지시 2026-05-24로 텔레메트리 30일 착수 게이트 제거)
**Input**: "Introduce the first LLM-assisted decision points to auto-invest. v1 declared zero judgment points (FR-005). This feature lifts that restriction for an explicitly enumerated, narrow set of decisions; constitution III requires each judgment point to declare trigger condition, input contract, output schema, latency budget, cost budget."

## 배경 — 왜 이 스펙인가, 그리고 왜 지금 안전한가

지금까지의 시스템(스펙 001~011)은 **Claude를 거래 결정 루프에 한 번도 부르지 않았다.** v1은 "판단 지점 0개"(FR-005)를 명시적으로 선언했고, 룰·트리거·게이트는 전부 결정론적 코드였다. Claude가 등장한 곳은 오직 두 군데였다 — 스펙 010(자동 룰 설계자, 거래 *전* 룰 생성)과 SDD 워크플로우(운영자 측 개발 도구). 둘 다 **돌아가는 거래 루프 안**은 아니었다.

이 스펙은 그 제약을 **명시적으로 열거된 좁은 결정 집합**에 한해 처음으로 푼다. 결정성을 일부 양보하고 Claude의 추론 능력을 얻는 트레이드오프다. 이것이 안전한 이유는 네 겹의 경계가 이미 깔려 있기 때문이다:

1. **헌법 III (판단 지점 계약)** — 모든 판단 지점은 트리거 조건·입력 계약·출력 스키마·지연 예산·비용 예산을 *코드로* 선언한다. 틱마다/시세마다 호출은 금지.
2. **헌법 VI (단계적 확장)** — 모든 판단 지점은 자본의 5%만 노출하는 캐너리 단계에서 ≥10 거래일을 탄 뒤에야 승격된다. 자본을 건드리지 않는 판단 지점(예: 일일 요약)은 노출이 0이므로 캐너리 의미가 다르다(아래 FR 참조).
3. **출력은 자문(advisory)일 뿐, 주문을 직접 내지 않는다** — Claude의 출력은 항상 **결정론적 게이트 로직**이 소비한다. "같은 자문 → 같은 게이트 결정"이 보장되어, LLM이 살아 있든 죽었든 주문 경로는 결정론적이다.
4. **결정론적 폴백(deterministic fallback)** — 모든 판단 지점은 LLM 호출이 실패/지연/예산초과해도 **거래를 막지 않는** 결정론적 대체 경로를 가진다. LLM은 "있으면 더 똑똑하게, 없으면 v1처럼" 동작하는 보너스 오라클이다.

이미 존재하는 토대(재구현 금지): 토큰 텔레메트리(스펙 002, `telemetry/meter.py`의 `TokenMeter` + `token_usage` 테이블), 감사 이벤트 `LLM_CALL`과 `LlmCallPayload`(`persistence/audit.py`, 프롬프트/응답 본문은 기록하지 않고 메타데이터만 — 헌법 V), 견고한 외부 클라이언트 패턴(`broker/client.py`의 `ResilientClient` = 레이트리밋 + 재시도 + 서킷브레이커), 스펙 010이 만든 Anthropic 호출 예시(`design/claude_client.py`).

## User Scenarios & Testing *(mandatory)*

<!-- 각 User Story 는 독립적으로 빌드·테스트·배포 가능한 슬라이스다. 하나만 구현해도 의미 있는 MVP 가 된다. -->

### User Story 1 — 변동성 급등 시 Claude가 "줄여/멈춰"를 자문 (volatility_assessment) (Priority: P1)

거래 루프가 화이트리스트 종목의 단기 실현 변동성이 룰이 정한 임계값을 넘는 것을 감지하면, 시스템은 Claude에게 **요약 통계만**(원시 바 데이터가 아니라) 넘겨 "이 주문을 그대로 둘지(hold), 사이즈를 줄일지(size_down), 멈출지(halt)"를 자문받는다. Claude의 출력은 `{action, confidence, reason}` 구조이며, **결정론적 게이트가 이 자문을 룰이 정한 규칙대로 소비**한다(예: "confidence ≥ 0.7로 halt면 이 주문 건너뜀", "size_down이면 수량을 룰이 정한 계수만큼 축소"). LLM 호출이 실패하면 게이트는 자문 없이 v1과 동일하게(결정론적 폴백) 동작한다.

**Why this priority**: 이것이 "Claude를 거래 루프에 부른다"는 이 스펙의 본질을 가장 직접적으로 구현한다. 변동성 판단은 실제 자본 결정(사이즈·중단)에 닿으므로 헌법 III·IV·VI·VII의 안전 기계 장치를 전부 행사한다 — 판단 지점 계약, 감사 기록, 5% 캐너리, 견고한 클라이언트, 그리고 결정론적 폴백. 이 슬라이스를 빌드하면 나머지 판단 지점이 재사용할 **판단 지점 프레임워크 전체**가 만들어진다. P1.

**Independent Test**: Anthropic 클라이언트를 mock으로 두고(스펙 010 `_AnthropicProtocol` 패턴 재사용), 합성 요약 통계를 트리거에 먹여 (1) 자문이 게이트 입력으로 들어가 결정에 반영되는지, (2) 같은 자문이면 항상 같은 게이트 결정이 나오는지(결정성), (3) 클라이언트가 예외/타임아웃/비용초과를 던질 때 게이트가 폴백 경로로 정상 주문/거부하는지, (4) 매 호출이 `token_usage` + `LLM_CALL` 감사 행으로 같은 correlation_id로 짝지어 기록되는지를 단독 검증.

**Acceptance Scenarios**:

1. **Given** 화이트리스트 종목의 `realized_vol_5m`이 룰 임계값을 초과해 트리거가 발화, **When** 거래 루프가 `volatility_assessment` 판단 지점을 호출, **Then** Claude에 요약 통계(원시 바 아님)가 전달되고 출력 `{action: "hold"|"size_down"|"halt", confidence: 0..1, reason: str}`이 스키마 검증을 통과하며, 그 자문이 후속 게이트 입력에 반영된다.
2. **Given** Claude가 `{action: "halt", confidence: 0.9}`를 반환하고 룰이 "confidence ≥ 0.7 halt → 주문 건너뜀"으로 설정됨, **When** 게이트 체인이 평가됨, **Then** 그 주문은 결정론적으로 건너뛰어지고 그 사실이 감사 로그에 (게이트 결정 + 그 입력이 된 LLM 자문의 correlation_id 와 함께) 남는다.
3. **Given** Anthropic 호출이 지연 예산(p95 < 2s)을 넘기거나 서킷브레이커가 열려 예외를 던짐, **When** 판단 지점이 호출됨, **Then** 시스템은 **거래를 막지 않고** 결정론적 폴백(자문 없음 = v1 동작)으로 진행하며, 폴백 사용 사실이 감사 로그에 기록되고 주문 경로는 정상 동작한다.
4. **Given** 한 번의 판단 호출, **When** 호출이 끝남, **Then** `token_usage`에 모델·decision_class·입출력 토큰·비용·지연이 1행, `audit_log`에 `LLM_CALL` 1행이 **같은 correlation_id**로 기록된다(스펙 002 무결성 점검 통과). 프롬프트/응답 본문은 기록되지 않는다(헌법 V).
5. **Given** `volatility_assessment`가 처음 배포됨, **When** 운영자/시스템이 단계를 확인, **Then** 이 판단 지점은 자본 5% 캐너리 단계에서 시작하며 ≥10 거래일 관찰 전에는 전체 승격되지 않는다(헌법 VI).

---

### User Story 2 — 매일 장 마감 후 Claude가 운영 요약·경보를 작성 (daily_summary) (Priority: P2)

장 마감 시점에 하루 한 번, 시스템은 그날의 감사 로그 집계 카운터(주문/체결/거부/오류/판단 호출 수 등)를 Claude에 넘겨 **사람이 읽는 서술 요약과 경보 목록**(`{narrative: str≤500, alerts: list[str]}`)을 받는다. 이 출력은 **순수 자문**이라 어떤 주문 경로에도 닿지 않고, 일일 리포트(`auto-invest report`)에 한 섹션으로 붙는다.

**Why this priority**: 운영자 가치가 높고(매일 무슨 일이 있었는지 한 문단으로) **주문 경로 위험이 0**이라, US1이 만든 판단 지점 프레임워크(견고한 클라이언트·계약·텔레메트리·감사)를 자본 위험 없이 재사용·검증하는 이상적인 두 번째 슬라이스다. 자본을 건드리지 않으므로 캐너리는 "출력 노출"이 아니라 "리포트에만 표시"로 시작한다. P2.

**Independent Test**: 합성 감사 카운터를 만들고 Claude mock을 둔 뒤 `report --date <d>`에 일일 요약 섹션이 붙는지, 출력이 ≤500자 서술 + 경보 리스트 스키마를 만족하는지, LLM 실패 시 리포트가 "요약 생성 불가"로 결정론적 폴백하되 나머지 리포트는 정상 출력되는지 단독 검증.

**Acceptance Scenarios**:

1. **Given** 그날 거래 활동이 audit_log에 집계됨, **When** `daily_summary` 판단 지점이 장 마감 후 1회 호출됨, **Then** 출력 `{narrative, alerts}`가 스키마 검증(narrative ≤500자)을 통과하고 일일 리포트에 한 섹션으로 포함된다.
2. **Given** Anthropic 호출이 실패, **When** 일일 요약이 생성됨, **Then** 리포트는 "요약 생성 불가(결정론적 카운터만 표시)"로 폴백하고 나머지 리포트(결정론적 집계)는 정상 출력되며, 명령은 비정상 종료하지 않는다.
3. **Given** 한 번의 요약 호출, **When** 호출이 끝남, **Then** `token_usage` + `LLM_CALL` 감사 행이 같은 correlation_id로 기록되고 decision_class는 `daily_summary`다.

---

### User Story 3 — 장 시작 전 뉴스 헤드라인에 대한 Claude의 스탠스 (news_screen) (Priority: P3)

장 시작 전, 화이트리스트 종목에 매칭된 뉴스 헤드라인이 주입되면, 시스템은 헤드라인 텍스트 + 종목을 Claude에 넘겨 `{stance: "bull"|"bear"|"neutral", confidence: 0..1}`를 받는다. 이 스탠스는 자문이며, 결정론적 게이트(예: "bear + confidence ≥ 0.8이면 그 종목 당일 신규 매수 보류")가 룰에 따라 소비한다. LLM 실패 시 폴백은 "neutral 취급"(= v1 동작, 스탠스 영향 없음).

**Why this priority**: 가치는 있으나 **외부 뉴스 헤드라인 공급원에 의존**한다. 이 스펙은 새 뉴스 피드를 구축하지 않는다(out of scope) — 헤드라인은 주입(injected)된 입력으로 가정하고, 공급원이 없으면 판단 지점은 비활성/스텁이다. 의존성 때문에 가장 후순위. P3.

**Independent Test**: 합성 헤드라인 + 종목을 주입하고 Claude mock으로 스탠스를 받아, 게이트가 그 스탠스를 룰대로 소비하는지(결정성), 헤드라인 공급원이 없을 때 판단 지점이 깨끗하게 비활성(neutral 폴백)되는지 단독 검증.

**Acceptance Scenarios**:

1. **Given** 화이트리스트 종목에 매칭된 헤드라인이 장 시작 전 주입됨, **When** `news_screen` 판단 지점이 호출됨, **Then** 출력 `{stance, confidence}`가 스키마 검증을 통과하고 룰이 정한 결정론적 규칙대로 게이트에 반영된다.
2. **Given** 헤드라인 공급원이 구성되지 않음, **When** 거래 루프가 장 시작 전 단계를 지남, **Then** `news_screen`은 호출되지 않고(또는 즉시 neutral 폴백) 주문 경로는 v1과 동일하게 동작한다.
3. **Given** Anthropic 호출 실패, **When** `news_screen`이 호출됨, **Then** 스탠스는 neutral로 폴백되어 그 종목 거래에 영향을 주지 않으며 폴백 사실이 감사 로그에 남는다.

---

### User Story 4 — 운영자가 판단 지점 비용·결정 이력을 본다 (관측성·예산 강제) (Priority: P2)

운영자(그리고 미래의 스펙 005 튜너)는 "Claude를 거래 루프에 부르는 데 돈이 얼마나 드는지, 무슨 결정을 했는지"를 알아야 한다. 판단 지점별 비용·지연·호출 수·폴백 발생률을 기존 `auto-invest efficiency`/`report` 표면으로 조회할 수 있어야 하고, 판단 지점별 비용 예산(예: volatility_assessment $0.01/call)을 넘으면 서킷브레이커처럼 그 판단 지점을 일시 비활성(= 결정론적 폴백 전환)해 비용 폭주를 막아야 한다.

**Why this priority**: 헌법 III(비용 예산)·IV(감사) 준수와 스펙 005 튜너 입력 신호를 위해 필요하다. 판단 지점들(US1~US3)이 동작해야 의미가 있으므로 그 위에 얹히는 P2.

**Independent Test**: 합성 판단 호출들을 기록하고 `efficiency`가 판단 지점별 비용/지연/폴백률을 분해 출력하는지, 비용 예산을 인위적으로 초과시켰을 때 그 판단 지점이 폴백으로 전환되고 `LLM_CALL`/오류 감사가 남는지 단독 검증.

**Acceptance Scenarios**:

1. **Given** 여러 판단 지점이 호출을 누적, **When** `auto-invest efficiency`(또는 동등 명령) 실행, **Then** decision_class(판단 지점)별 총비용·평균지연·호출 수·폴백 발생률이 분해되어 출력된다.
2. **Given** 한 판단 지점의 롤링 비용이 선언된 예산을 초과, **When** 다음 호출이 시도됨, **Then** 그 판단 지점은 결정론적 폴백으로 전환(일시 비활성)되고 그 전환이 감사 로그에 기록되며 거래 경로는 계속 정상 동작한다.

---

### Edge Cases

- **LLM이 스키마 위반 출력을 반환**(잘못된 enum, 범위 밖 confidence, 500자 초과 narrative) → 결정론적 검증이 거부하고 폴백 경로로 전환, `DATA_QUALITY_ISSUE` 또는 동등 감사 기록. 깨진 출력이 게이트에 새지 않는다.
- **LLM 지연이 예산 초과**(p95 < 2s for volatility) → 타임아웃 후 폴백. 거래 결정이 LLM을 기다리느라 막히지 않는다.
- **서킷브레이커 OPEN 상태에서 호출 시도** → 즉시 폴백, 호출 비용 0, 쿨다운 후 HALF_OPEN으로 재시도.
- **비용 예산 초과 직전/직후 경계** → 롤링 윈도 기준으로 판정, 경계에서 단일 호출이 예산을 넘기면 그 호출은 기록되되 다음 호출부터 폴백(US4).
- **장중 vs 장외 트리거 타이밍** — `daily_summary`는 장 마감 후 1회만, `news_screen`은 장 시작 전만. 잘못된 시각의 호출은 결정론적으로 건너뛴다.
- **같은 틱에 같은 판단 지점이 중복 트리거** → 쿨다운(기존 트리거 `cooldown_seconds` 재사용)으로 중복 호출 억제, 판단 지점이 틱마다 호출되지 않음(헌법 III).
- **mock/실클라이언트 불일치** — 테스트는 `_AnthropicProtocol` 덕타이핑으로 실 SDK 없이 결정론적 검증.
- **캐너리 단계에서 판단 지점이 영향을 준 거래와 안 준 거래 구분** — 자본 5% 캐너리 코호트에서만 자문이 게이트에 반영되고 나머지는 v1 동작, 둘의 성과를 스펙 011 측정으로 비교 가능해야 한다.

## Requirements *(mandatory)*

### Functional Requirements

#### 판단 지점 프레임워크 (US1이 만들고 US2~US4가 재사용)

- **FR-001**: 시스템은 각 판단 지점에 대해 헌법 III이 요구하는 다섯 가지 계약을 **코드로 선언**해야 한다: 트리거 조건, 입력 계약(input contract), 출력 스키마(output schema), 지연 예산(latency budget), 비용 예산(cost budget). 이 선언은 단일 레지스트리(판단 지점 목록)에 모여 조회 가능해야 한다.
- **FR-002**: 모든 판단 지점은 **결정론적 폴백 경로**를 가져야 한다. LLM 호출이 실패·타임아웃·서킷오픈·비용초과·스키마위반 중 무엇이든, 거래 경로는 자문 없이 결정론적으로(v1 동작) 진행되며 **거래가 막히지 않는다**.
- **FR-003**: 판단 지점의 LLM 출력은 **자문(advisory)**이며, 항상 **결정론적 게이트 로직**이 소비한다. LLM은 주문을 직접 내지 않는다. "같은 자문 → 같은 게이트 결정"이 보장되어야 한다(결정성, 테스트로 검증).
- **FR-004**: Anthropic 클라이언트는 헌법 VII을 만족하는 견고성 — 레이트리밋, 지수 백오프 재시도(횟수 상한), 서킷브레이커(지속 실패 후 비활성·쿨다운 후 재활성) — 을 가져야 하며, `broker/client.py`의 `ResilientClient` 패턴을 거울처럼 따른다(새 견고성 메커니즘을 발명하지 않는다).
- **FR-005**: 모든 판단 호출은 `token_usage`(스펙 002)에 1행, `audit_log`에 `LLM_CALL` 1행을 **같은 correlation_id**로 기록해야 한다(헌법 IV). 토큰·비용·지연·모델·decision_class·error_class만 기록하고 **프롬프트/응답 본문은 기록하지 않는다**(헌법 V).
- **FR-006**: 각 판단 지점의 LLM 출력은 스키마 검증을 통과해야 게이트로 전달된다. 검증 실패(잘못된 enum, 범위 밖 값, 길이 초과)는 폴백으로 전환하고 감사에 가시화한다.
- **FR-007**: 판단 지점은 **틱마다/시세마다 호출되지 않는다**(헌법 III). 트리거 조건이 발화할 때만, 그리고 쿨다운을 존중하여 호출된다. 트리거 정의는 기존 룰/트리거 인프라(`config/rules.py`, `strategy/triggers.py`)를 재사용하거나 확장한다.

#### 판단 지점 1 — volatility_assessment (US1)

- **FR-010**: 시스템은 화이트리스트 종목의 단기 실현 변동성(예: `realized_vol_5m`)이 룰이 정한 임계값을 초과할 때 발화하는 `volatility_assessment` 판단 지점을 제공해야 한다. 입력은 **요약 통계**(원시 바 데이터 금지)다.
- **FR-011**: `volatility_assessment` 출력 스키마는 `{action: "hold"|"size_down"|"halt", confidence: 0..1, reason: str}`이다. 지연 예산 p95 < 2s, 비용 예산 $0.01/call(plan에서 모델·max_tokens로 구체화).
- **FR-012**: 결정론적 게이트는 이 자문을 룰이 정한 규칙대로 소비한다(예: halt+고신뢰 → 주문 건너뜀, size_down → 룰 계수로 수량 축소). 자문이 어떻게 결정으로 변환됐는지는 감사에 남는다.
- **FR-013**: `volatility_assessment`는 자본 5% 캐너리 단계에서 시작하며 ≥10 거래일 관찰 전 전체 승격되지 않는다(헌법 VI). 캐너리 코호트 밖 거래는 자문을 받지 않고 v1 동작한다.

#### 판단 지점 2 — daily_summary (US2)

- **FR-020**: 시스템은 장 마감 후 하루 1회 발화하는 `daily_summary` 판단 지점을 제공해야 한다. 입력은 그날의 audit_log 집계 카운터(원시 행이 아니라 집계)다.
- **FR-021**: `daily_summary` 출력 스키마는 `{narrative: str≤500, alerts: list[str]}`이다. 지연 예산 p95 < 10s, 비용 예산 $0.05/call.
- **FR-022**: `daily_summary` 출력은 순수 자문이며 어떤 주문 경로에도 닿지 않는다. 출력은 `auto-invest report --date <d>`에 한 섹션으로 통합된다. LLM 실패 시 리포트는 결정론적 카운터만 표시하고 정상 종료한다.

#### 판단 지점 3 — news_screen (US3)

- **FR-030**: 시스템은 장 시작 전 화이트리스트 종목에 매칭된 헤드라인이 **주입될 때** 발화하는 `news_screen` 판단 지점을 제공해야 한다. 입력은 헤드라인 텍스트 + 종목. 새 뉴스 피드 구축은 이 스펙 범위 밖 — 헤드라인 공급원이 없으면 판단 지점은 비활성(neutral 폴백).
- **FR-031**: `news_screen` 출력 스키마는 `{stance: "bull"|"bear"|"neutral", confidence: 0..1}`이다. 지연 예산 p95 < 5s, 비용 예산 $0.02/call.
- **FR-032**: 결정론적 게이트는 스탠스를 룰대로 소비한다(예: bear+고신뢰 → 당일 신규 매수 보류). LLM 실패/공급원 부재 시 neutral 폴백(거래 영향 없음).

#### 관측성·예산 강제 (US4)

- **FR-040**: 운영자는 기존 `auto-invest efficiency`/`report` 표면으로 판단 지점별(decision_class별) 총비용·평균지연·호출 수·폴백 발생률을 조회할 수 있어야 한다.
- **FR-041**: 각 판단 지점은 비용 예산을 가지며, 롤링 비용이 예산을 초과하면 그 판단 지점은 결정론적 폴백으로 전환(일시 비활성)되고 그 전환이 감사 로그에 기록된다. 거래 경로는 계속 동작한다.

### Key Entities *(데이터를 다루는 항목)*

- **Judgment Point (판단 지점)**: 헌법 III 계약을 담은 선언. id(decision_class)·트리거 조건·입력 계약·출력 스키마·지연 예산·비용 예산·캐너리 단계 정책·결정론적 폴백 정의를 갖는다. 레지스트리에 등록된다.
- **Judgment Request**: 한 번의 판단 호출 입력. 판단 지점 id·요약 입력(통계/카운터/헤드라인)·correlation_id·트리거가 발화한 컨텍스트(종목·룰).
- **Judgment Advisory**: Claude의 검증된 출력. 판단 지점별 출력 스키마(volatility=action/confidence/reason, daily=narrative/alerts, news=stance/confidence). 게이트가 소비하기 전 스키마 검증을 통과한 것만 유효.
- **Fallback Decision**: LLM이 자문을 못 줄 때 게이트가 택하는 결정론적 경로 표식. 폴백 사유(실패/타임아웃/서킷/예산/스키마)와 함께 감사에 기록.
- **LLM_CALL audit row + token_usage row**: 한 호출의 메타데이터(모델·decision_class·토큰·비용·지연·error_class·correlation_id). 본문 없음(헌법 V). 이미 존재하는 스키마 재사용.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 어떤 판단 지점에서든 LLM 호출이 실패·타임아웃·서킷오픈·비용초과·스키마위반해도, 거래 경로는 **0건의 막힘 없이** 결정론적 폴백으로 진행한다(혼돈 주입 테스트로 검증 — LLM이 항상 던지는 환경에서 주문 경로가 v1과 동일하게 동작).
- **SC-002**: 같은 판단 자문 입력에 대해 게이트 결정은 **항상 동일**하다(결정성). 같은 자문을 두 번 먹이면 두 번 다 같은 주문/거부 결정이 난다(테스트로 검증).
- **SC-003**: 모든 판단 호출은 `token_usage` 1행 + `LLM_CALL` 감사 1행이 같은 correlation_id로 짝지어 기록되고(스펙 002 무결성 점검 통과), 어디에도 프롬프트/응답 본문·KIS 비밀이 남지 않는다(헌법 V, 테스트로 검증).
- **SC-004**: 각 판단 지점은 선언된 지연 예산(volatility p95<2s, news p95<5s, daily p95<10s)과 비용 예산($0.01/$0.02/$0.05) 안에서 동작하거나, 초과 시 폴백으로 전환된다(롤링 비용 예산 강제 테스트로 검증).
- **SC-005**: `volatility_assessment`(및 자본에 닿는 판단 지점)는 첫 배포 시 자본 5% 캐너리 코호트에서만 자문을 게이트에 반영하며, 캐너리 밖 거래는 v1 동작한다(헌법 VI, 테스트로 검증).
- **SC-006**: 운영자는 단일 명령으로 판단 지점별 비용·지연·호출 수·폴백률을 조회할 수 있고, 그 합은 스펙 002 `token_usage` 총계와 일치한다(합산 보존).
- **SC-007**: 이 스펙의 어떤 코드도 LLM이 직접 주문을 제출하게 하지 않는다 — 모든 주문은 결정론적 게이트 체인을 통과한다(코드 경로 검증 + 테스트). 즉 v1의 안전 불변량(헌법 I·II 포지션 캡·화이트리스트)은 LLM 자문과 무관하게 그대로 강제된다.

## Assumptions

- **착수 게이트 제거**: 운영자 지시(2026-05-24)로 "≥30일 텔레메트리 누적" 착수 게이트는 제거됐다. 토큰 텔레메트리(스펙 002)는 병행 누적되며, 비용 프로파일이 thin한 초기에는 보수적 예산으로 시작한다(구현은 데이터 누적을 기다리지 않음). 단 헌법 III·IV·VI·VII의 런타임 안전 계약은 그대로다.
- **기존 토대 재사용(재구현 금지)**: 텔레메트리(`telemetry/meter.py` `TokenMeter`, `token_usage` 테이블), 감사 이벤트 `LLM_CALL`/`LlmCallPayload`(`persistence/audit.py`), 견고한 클라이언트 패턴(`broker/client.py` `ResilientClient`), 스펙 010의 Anthropic 호출 예시(`design/claude_client.py`)를 재사용·확장한다. 새 텔레메트리·감사·견고성 메커니즘을 발명하지 않는다.
- **출력은 자문, 게이트가 결정**: LLM은 절대 주문을 직접 내지 않는다. 자문은 결정론적 게이트(`risk/gates.py` 체인 또는 그 입력 단계)가 소비한다. "advisory → deterministic gate"는 헌법 III 준수이자 결정성 보존의 핵심.
- **변동성 데이터 출처**: `realized_vol_5m` 같은 입력 통계는 기존 지표/트리거 인프라(`strategy/triggers.py`의 indicator 평가)에서 산출하거나, 없으면 plan에서 최소 산출 경로를 정의한다. 새 시장 데이터 공급자는 도입하지 않는다.
- **뉴스 헤드라인 출처(news_screen)**: 새 뉴스 피드를 구축하지 않는다. 헤드라인은 주입되는 입력으로 가정하고, 공급원이 없으면 판단 지점은 깨끗하게 비활성(neutral 폴백)된다. 그래서 P3.
- **단발 호출만(out of scope: 멀티턴)**: v2 호출은 단일 요청/응답(single-shot)이다. 멀티턴 에이전트 루프는 범위 밖.
- **커스텀 파인튠 없음**: 공개된 Claude 모델(예: `claude-opus-4-7` 또는 plan에서 정하는 비용 적합 모델)을 그대로 탄다.
- **Kernel 터치**: 감사 이벤트 `LLM_CALL`/`LlmCallPayload`는 K4이지만 **이미 존재**한다(스펙 002에서 추가됨). 이 스펙이 새 K4 추가(예: 폴백/예산전환 전용 이벤트 타입)를 한다면 추가-전용 패턴(스펙 009/010과 동일)을 따르고 PR 본문에 커밋 해시를 명시한다. 헌법 III(K3, 판단 지점 계약)을 코드로 처음 채우는 작업이므로 plan에서 K3 관련 파일(`kernel.toml` 참조)을 식별하고, Kernel 터치가 있으면 IX.A 포렌식 콜아웃을 PR에 남긴다(머지는 IX.D 자율 경로, 생산 배포는 스펙 007 캐너리 게이트).
- **결정성 우선**: 게이트가 LLM 자문을 소비하는 방식은 룰이 명시적으로 선언한 결정론적 규칙(임계 confidence·축소 계수 등)이어야 한다. "LLM이 알아서 사이즈를 정한다"는 금지 — LLM은 enum/score만 주고 변환은 결정론적.
- **스펙 005와의 관계**: 이 스펙이 만드는 판단 지점(프롬프트 템플릿·파라미터)은 미래 스펙 005 자율 튜너의 L2/L3 튜닝 대상이 된다. 이 스펙은 그 표면을 만들 뿐, 자동 튜닝 로직은 스펙 005 범위다.
- **스펙 011과의 관계**: 캐너리 코호트(자문 반영) vs 대조군(v1 동작)의 성과 비교는 스펙 011 측정(`auto-invest performance`)으로 한다. 이 스펙은 그 비교가 가능하도록 판단 지점이 영향을 준 거래를 식별 가능하게 남긴다.

## Out of Scope

- 멀티턴 에이전트 루프 (v2는 단일 요청/응답).
- LLM이 주문을 직접 제출 (출력은 자문, 결정론적 게이트가 소비).
- 커스텀 파인튠 (공개 Claude 모델 사용).
- 새 뉴스 피드/시장 데이터 공급자 구축 (news_screen 헤드라인은 주입 입력으로 가정; 정보 토대 강화는 후속 스펙).
- 자동 튜닝 로직 (스펙 005 범위).

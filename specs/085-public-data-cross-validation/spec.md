# Feature Specification: 공개 데이터 교차 검증 확장

**Feature Branch**: `Codex/085-public-data-cross-validation`  
**Created**: 2026-07-02  
**Status**: Draft  
**Input**: User description: "자율 작업 실행 루프가 고른 `candidate-facf2fa31834` 공개 데이터 수집·교차 검증 확장을 목표 스킬로 꼼꼼하게 진행한다."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - FRED 금리 원천을 연구 채널에 추가 (Priority: P1)

운영자는 공개 데이터 채널이 재무부 금리만 단일 직접 경로로 의존하지 않고, 키 없는 FRED 그래프 CSV 금리 원천도 연구 전용 산출물로 발행하기를 원한다.

**Why this priority**: 최신 후보 패키지는 FRED 그래프 CSV가 기본 user-agent 경로에서 열리는 증거를 남겼다. 이 경로를 연구 전용 금리 원천으로 제한해 추가하면 레짐 분석 핵심 입력의 공급망 대조 폭이 넓어진다.

**Independent Test**: 모의 FRED 응답으로 `collect-public-data`를 실행했을 때 FRED 2년·10년 금리 CSV가 발행되고 summary에 성공 항목으로 남으면 이 스토리는 독립적으로 통과한다.

**Acceptance Scenarios**:

1. **Given** FRED 그래프 CSV가 2년·10년 금리 시계열을 정상 반환함, **When** 공개 데이터 수집이 실행됨, **Then** `fred/DGS2.csv`와 `fred/DGS10.csv`가 연구 전용 산출물로 발행된다.
2. **Given** FRED 그래프 CSV가 타임아웃이나 형식 오류를 냄, **When** 공개 데이터 수집이 실행됨, **Then** 해당 FRED 항목만 fail-soft로 미발행되고 나머지 검증 통과 항목은 계속 발행된다.

---

### User Story 2 - 금리 두-기관 대조를 FRED 경로까지 확장 (Priority: P2)

운영자는 재무부 금리와 FRED 금리의 같은 날짜 수준값이 충분한 겹침에서 일치하는지 매 실행 summary에서 보고 싶다.

**Why this priority**: 기존 DBnomics H.15 미러 대조는 유용하지만, FRED 그래프 CSV가 열리는 순간 직접 FRED 경로도 조용한 전송 오류를 잡는 별도 관측 표면이 된다.

**Independent Test**: 재무부와 FRED 모의 금리값이 같으면 교차 검증이 PASS이고, 한쪽 미발행이면 SKIPPED이며, 값이 다르면 FAIL로 overall_ok를 낮추는 것을 확인한다.

**Acceptance Scenarios**:

1. **Given** 재무부 2년·10년 금리와 FRED DGS2·DGS10이 같은 수준값을 반환함, **When** 공개 데이터 수집이 끝남, **Then** 두 FRED 교차 검증이 PASS로 기록된다.
2. **Given** FRED DGS10 값이 재무부 UST10Y와 체계적으로 다름, **When** 공개 데이터 수집이 끝남, **Then** 해당 교차 검증은 FAIL이고 전체 판정은 정상으로 위장되지 않는다.

---

### User Story 3 - 라이브 매매 경로 격리 유지 (Priority: P3)

운영자는 공개 데이터 원천이 늘어나도 라이브 매매 신호, 주문, 자본 배분, KIS 경로가 영향을 받지 않기를 원한다.

**Why this priority**: 공개 데이터 채널은 연구·백테스트·검증 전용이다. 원천 확장은 데이터 신뢰도를 높이는 일이지 live signal을 바꾸는 일이 아니다.

**Independent Test**: 거래 워크플로가 `public-data`를 읽지 않고, 수집 워크플로가 KIS/Vultr/SSH/비밀값을 쓰지 않으며, 설정 교차검증 입력이 모두 수집 목록을 가리키는 불변식 테스트가 통과하면 된다.

**Acceptance Scenarios**:

1. **Given** FRED 수집 설정이 추가됨, **When** 워크플로 불변식 테스트를 실행함, **Then** 라이브·forward 거래 워크플로는 여전히 public-data 산출물을 소비하지 않는다.
2. **Given** FRED 공식 API 키 기반 주소는 여전히 키가 필요함, **When** 설정을 확인함, **Then** 키 기반 API는 수집 대상이 아니라 탐침 또는 기록용으로만 남는다.

### Edge Cases

- FRED 그래프 CSV는 채널 user-agent에서 느리거나 타임아웃이지만 기본 httpx user-agent에서는 열린다.
- FRED 한쪽 만기만 발행되고 다른 만기가 실패한다.
- FRED와 재무부의 겹침 관측 수가 기준 미만이다.
- FRED 값이 일부 날짜에서 사후 정정 시차로 소수 불일치한다.
- 공개 데이터 확장 때문에 거래 워크플로가 public-data를 읽는 회귀가 생긴다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST collect FRED graph CSV DGS2 and DGS10 as research-only series when configured.
- **FR-002**: System MUST support using the default HTTP client user-agent for configured FRED graph CSV requests while preserving the existing channel user-agent for other public sources by default.
- **FR-003**: System MUST publish only validated FRED series and MUST fail-soft per series when a FRED request, parse, freshness, or row-count validation fails.
- **FR-004**: System MUST add level cross-checks from `treasury:UST2Y` to `fred:DGS2` and from `treasury:UST10Y` to `fred:DGS10`.
- **FR-005**: System MUST mark the overall collection result unhealthy when a required FRED cross-check fails, and MUST mark the cross-check SKIPPED when either side was not published.
- **FR-006**: System MUST keep live trading workflows, broker APIs, KIS data paths, whitelist/caps, live strategy, and capital allocation untouched.
- **FR-007**: System MUST keep the FRED API-key endpoint out of the collection list unless a separate approved key-management task adds it.
- **FR-008**: System MUST update operator-facing handoff and validation evidence so the next session knows the new public-data cross-check scope.

### Key Entities

- **Public Data Source**: A configured read-only source that can produce one or more research-only series.
- **FRED Series**: A keyless FRED graph CSV series such as DGS2 or DGS10, validated by row count and freshness before publication.
- **Cross-Check Pair**: A configured comparison between two published registry keys, with status PASS, FAIL, SKIPPED, or INSUFFICIENT_OVERLAP.
- **Collection Summary**: The JSON evidence surface consumed by sidecars, candidate factory, and operators.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A successful official-source collection publishes 11 research-only items instead of 9, adding FRED DGS2 and DGS10.
- **SC-002**: The collection summary records at least 5 cross-checks, including the two new FRED-vs-Treasury checks.
- **SC-003**: If FRED is unavailable, at least the pre-existing 9 official keyless items can still publish and the FRED checks are not silently reported as PASS.
- **SC-004**: The live trading workflow isolation tests continue to pass with zero KIS, SSH, broker order, whitelist/caps, or live strategy changes.

## Assumptions

- FRED graph CSV for DGS2/DGS10 is acceptable as a keyless research-only source when requested with the default HTTP client user-agent.
- FRED DGS2/DGS10 and Treasury UST2Y/UST10Y are comparable level series with tolerance and agreement thresholds matching existing Treasury-vs-H.15 checks.
- Price history expansion remains out of scope; Stooq stays probe-only and KIS remains the price source for live trading.
- The FRED API-key endpoint remains out of scope because it requires key-management decisions.

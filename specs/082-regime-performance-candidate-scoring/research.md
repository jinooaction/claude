# Research: 레짐·성과 후보 점수화

## Decision: `promote-readiness`를 성과 표면으로 사용한다

**Rationale**: 현재 저장소에서 자동 발행되는 성과·트랙레코드 readiness 표면은 `automation/promote-readiness-last-run:LAST_RUN.md`다. 이 표면은 full-live 승격을 수행하지 않고, 헌법 VI 트랙레코드 상태를 보고만 한다. 따라서 후보 점수의 성과 입력으로 쓰기에 안전하다.

**Alternatives considered**:

- `auto-invest performance`를 새로 실행한다. 거부: 서버 DB와 marks가 필요하고 새 실행 경로가 생겨 범위가 커진다.
- `operator-status`만 사용한다. 거부: 운영자 요약 표면이라 성과 지표 자체를 보존하지 않는다.
- `money-path` blocker만 사용한다. 거부: 돈 경로 상태는 중요하지만 레짐별 성과 약점과 트랙레코드 readiness를 직접 표현하지 않는다.

## Decision: 성과 신호는 점수 보강·감점으로만 사용한다

**Rationale**: `READY=true`도 full-live 승격의 충분조건이 아니다. 스펙 007 하드닝 캐너리와 기존 자본 사다리가 따로 있다. 따라서 성과 표면은 후보 점수를 더 근거 있게 만드는 데만 쓰고, 승격·주문·자본 변경으로 연결하지 않는다.

**Alternatives considered**:

- `READY=true`이면 live readiness 후보를 자동 승격한다. 거부: 이 기능의 안전 경계를 넘고 헌법 VI/X의 기존 게이트를 우회한다.
- `READY=false`이면 분석 후보를 폐기한다. 거부: live 기간 부족은 정상 대기일 수 있고, 분석 후보의 가치는 여전히 남는다.

## Decision: 누락·stale 성과 표면은 sidecar freshness 의존으로 남긴다

**Rationale**: 성과 표면을 점수에 넣으면 stale 성과를 과신할 위험이 생긴다. 기존 evolution loop의 stale evidence 처리와 같은 모델을 재사용하면 다음 세션이 "성과 실패"와 "증거 신선도 문제"를 구분할 수 있다.

**Alternatives considered**:

- 성과 표면이 없으면 이전 정적 점수를 그대로 유지한다. 거부: 성과 입력을 요구하는 후보의 의도와 다르며 과신 위험이 남는다.
- 성과 표면이 없으면 전체 루프를 blocked로 만든다. 거부: 분석 후보 하나의 보강 입력이 누락됐다고 전체 자율 성장 후보 발굴을 멈출 필요는 없다.

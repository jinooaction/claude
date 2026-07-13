# Requirements Quality Checklist: Live Entrypoint Containment

**Purpose**: 스펙 111이 구현 전에 필요한 안전 경계, 실패 모드, 증거, 완료 기준을 충분히 정의했는지 검토한다.  
**Created**: 2026-07-13  
**Feature**: `specs/111-live-entrypoint-containment/spec.md`

## Problem and Scope

- [x] CHK001 평행 실거래 진입점이라는 핵심 문제가 명시돼 있다.
- [x] CHK002 설계 기능 제거가 아니라 설계와 실행 권한 분리가 목표임이 명시돼 있다.
- [x] CHK003 실제 주문·재무장·자본 증액은 운영자 승인 범위 밖임이 명시돼 있다.
- [x] CHK004 주문 재시도, 체결 원장, 노출 예약은 비목표로 분리돼 있다.
- [x] CHK005 현재 서버와 KIS 계좌 상태를 추측하지 않는다고 명시돼 있다.

## User Scenarios

- [x] CHK006 수동 설계가 라이브 워커를 시작하지 않는 시나리오가 있다.
- [x] CHK007 예약 실행이 사라지는 시나리오가 있다.
- [x] CHK008 과거 `AUTO_OK` 값이 live 권한으로 해석되지 않는 시나리오가 있다.
- [x] CHK009 실제 동적 검증과 stub·skip을 구분하는 시나리오가 있다.
- [x] CHK010 셸 특수문자가 데이터로 보존되는 시나리오가 있다.
- [x] CHK011 후보 생성 기능을 유지하는 시나리오가 있다.

## Functional Requirements

- [x] CHK012 workflow schedule 제거 요구가 검증 가능하게 쓰여 있다.
- [x] CHK013 자동 `OK` 주입 금지 요구가 검증 가능하게 쓰여 있다.
- [x] CHK014 `design`의 직접 live startup 금지 요구가 명시돼 있다.
- [x] CHK015 실제 백테스트와 paper 증거 없이는 `ok=True`가 불가능함이 명시돼 있다.
- [x] CHK016 후보 지문 일치 요구가 명시돼 있다.
- [x] CHK017 안전한 intent 전달 방식과 금지 방식이 구분돼 있다.
- [x] CHK018 명령 안전 등록부 기대값이 구체적이다.
- [x] CHK019 주요 sentinel/caps/whitelist/constitution/kernel 무변경 요구가 있다.
- [x] CHK020 외부 API를 호출하지 않는 테스트 요구가 있다.

## Failure and Edge Cases

- [x] CHK021 backtest 모듈 import 성공을 실행 성공으로 오인하는 경우가 포함돼 있다.
- [x] CHK022 paper 검증 미구현 상태가 fail-closed로 정의돼 있다.
- [x] CHK023 stale 또는 fingerprint mismatch 증거가 실패로 정의돼 있다.
- [x] CHK024 기존 자동 생성 룰 파일을 자동 실행하지 않는다고 명시돼 있다.
- [x] CHK025 SSH·payload 오류 시 live side effect가 0이어야 한다.
- [x] CHK026 rollback이 unsafe live path를 복원하지 않는다고 명시돼 있다.

## Data and Contract

- [x] CHK027 `DesignCandidate`의 authority가 `PROPOSAL_ONLY`로 고정돼 있다.
- [x] CHK028 단계별 PASS/WAIT/FAIL 규칙이 정의돼 있다.
- [x] CHK029 aggregate success 규칙이 결정론적이다.
- [x] CHK030 intent payload 무결성과 비평가 전달 규칙이 있다.
- [x] CHK031 기존 감사 이벤트의 역사적 호환성을 보존한다.

## Success Criteria

- [x] CHK032 모든 성공 기준이 테스트 또는 정적 검사로 확인 가능하다.
- [x] CHK033 live startup 부재를 증명하는 기준이 있다.
- [x] CHK034 workflow schedule과 자동 confirmation 부재를 증명하는 기준이 있다.
- [x] CHK035 command registry와 실제 권한 정합 기준이 있다.
- [x] CHK036 전체 테스트·린트·하네스·HANDOFF·PR 관문이 포함돼 있다.
- [x] CHK037 실제 서버 상태는 완료 기준에서 제외하고 미확인으로 보고하게 돼 있다.

## Implementation Readiness

- [x] CHK038 첫 수정 대상 파일이 구체적으로 나열돼 있다.
- [x] CHK039 테스트 우선 순서가 정의돼 있다.
- [x] CHK040 안전한 중간 상태가 `proposal + ok=false`로 정의돼 있다.
- [x] CHK041 후속 스펙 순서가 명시돼 있다.
- [x] CHK042 코덱스가 추가 질문 없이 시작할 수 있는 실행 절차가 HANDOFF에 있다.

## Remaining Questions for Code Inspection

아래는 구현 시작 시 코드 검색으로 답해야 하며, 스펙 모호성은 아니다.

- [ ] CHK043 `start_live_worker`의 현재 production call site 전체를 확인했다.
- [ ] CHK044 기존 `design` CLI의 후보 파일 저장과 audit emission 순서를 확인했다.
- [ ] CHK045 실제 재사용 가능한 backtest/paper validator API를 확인했다.
- [ ] CHK046 operator-design 관련 문서와 테스트 fixture의 `AUTO_OK` 참조를 전수 확인했다.
- [ ] CHK047 workflow input transport를 테스트할 기존 셸 테스트 패턴을 확인했다.

이 다섯 항목은 Phase 0 탐색에서 체크하고, 결과를 PR 본문 `## 탐색 근거`에 남긴다.

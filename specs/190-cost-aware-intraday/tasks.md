# 비용 고려 단타 연구 작업

## Phase 1 — 명세와 고정
- [x] T001 `specs/190-cost-aware-intraday/spec.md`에 사용자 흐름·완료 기준·비목표를 정의한다.
- [x] T002 `specs/190-cost-aware-intraday/plan.md`와 research/data-model/quickstart에 구현 경로와 헌법 준수를 기록한다.
- [x] T003 `specs/190-cost-aware-intraday/contracts/preregistration.json`을 성과 계산 전 b85a074로 커밋했다. SHA256=234d71ad3418c10d1f8bcd6c0e6fcf72eece1a6b41d75bed2d912423d8efd181.

## Phase 2 — US1 개발 전용 연구
- [x] T004 [US1] `tests/unit/test_cost_aware_intraday.py`에 계약 변조·후보6개·미래 봉 금지·개발 탈락 반례를 추가한다. 관련37개 통과.
- [x] T005 [US1] `src/auto_invest/analytics/cost_aware_intraday.py`에 exact 계약·입력 검사와 기존177 체결기 기반 후보 평가를 구현한다.
- [x] T006 [US1] `scripts/cost_aware_intraday_probe.py` develop 명령과 출력 독점 생성·실패 상태를 연결한다.
- [x] T007 [US1] `tests/integration/test_cost_aware_intraday_cli.py`에서 명령·파일 보존·출력 변조 검사를 확인했다. 실제 장부4616행 원본 재계산도 valid=true.
- [x] T008 [US1] `specs/190-cost-aware-intraday/results.md`에 실제1,645세션 개발 결과와 모든 후보 지문을 기록한다.6개 모두 비용 후 손실, 확인 자료 미개봉.

## Phase 3 — US2 독립 확인 경계
- [x] T009 [US2] `tests/unit/test_cost_aware_intraday.py`에 선택 조작·기간 중복·미개봉 파일 접근 차단·기존18후보 비교 누락 반례를 추가했다.
- [x] T010 [US2] `src/auto_invest/analytics/cost_aware_intraday.py`에 개발 재구성·247/248일 분리·24후보 비교·기존177 합격 기준 판정을 구현했다. 모의 입력으로 검증.
- [x] T011 [US2] `scripts/cost_aware_intraday_probe.py` confirm 명령과 `scripts/cost_aware_intraday_evidence_gate.py` 원본 재생 검사를 연결했다. 관련55개 통과.
- [x] T012 [US2] `specs/190-cost-aware-intraday/results.md`에 개발 탈락과 confirm 실제 거부(exit2)/확인 산출물 미생성 증거를 기록했다.

## Phase 4 — 검증과 인계
- [x] T013 관련55개, 코드8ca0c9c 전체4797 passed/13 skipped(828.14초), ruff·하네스14/14·HANDOFF 사실 검사 통과. 실제 KIS12개·가동 전 전용1개 생략.
- [x] T014 `HANDOFF.md`에 원본·등록·선택·결과·미완료 실사용 조건을 연결했다. PR837→main9b8c9e1 병합, 배포35543697028 성공. 전체 목표와 통과 전략은 미완료다.

## 의존성과 실행 전략

T001→T002→T003→T004~T007→T008. T009~T011은 실제 확인 성과 접근 없이 모의 입력으로
개발할 수 있으나 T012는 개발 통과 여부와 독립 선택 검사에 종속된다. T013/T014는 마지막이다.
같은 파일을 수정하므로 직렬 수행한다. 독립 병렬 가능 범위는 읽기 전용 문서 검토와 코드 검사다.
개발 탈락은 해당 가설의 결과이며 전체 목표 완료가 아니다. 다음 가설은 새 사전등록을 요구한다.

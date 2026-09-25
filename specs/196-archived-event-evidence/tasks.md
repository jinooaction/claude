# Tasks: 과거 보관 사건의 근거 검사

## Phase 1 — Setup
- [x] T001 명세·계획·조사·자료 계약을 specs/196-archived-event-evidence/에 작성한다.
- [x] T002 .specify/feature.json 및 AGENTS.md의 명세 포인터를 연결한다.

## Phase 2 — Foundation
- [x] T003 src/auto_invest/analytics/archived_event_evidence.py에 엄격한 입력·크기 제한·단일 gzip/WARC 파서를 구현한다.

## Phase 3 — US1 근거 연결
독립 검사: 실제 응답의 지문·연결 일치, 변조 및 다른 metadata 연결 거부.
- [x] T004 [US1] tests/unit/test_archived_event_evidence.py에 구조·압축·길이·지문·ID·인용 반례를 추가한다.
- [x] T005 [US1] src/auto_invest/analytics/archived_event_evidence.py에 색인·응답·metadata·warcinfo 및 인용 대조를 구현한다.

## Phase 4 — US2 시각과 가정
독립 검사: 초 경계·프로필 불일치·잘림 표시 보존·로컬/공급자 시각 구분.
- [x] T006 [US2] tests/unit/test_archived_event_evidence.py에 시각·프로필·거짓 승인 방지 반례를 추가한다.
- [x] T007 [US2] src/auto_invest/analytics/archived_event_evidence.py에 조건부 구간·현재 검사 시각·미확인 항목을 구현한다.
- [x] T008 [US2] scripts/archived_event_evidence.py 및 tests/integration/test_archived_event_evidence_cli.py에 CLI와 파일 덮어쓰기 방지를 구현·검사한다.

## Phase 5 — 통합과 인계
- [x] T009 실제 WMT 자료로 실행해 specs/196-archived-event-evidence/release-evidence.md에 원본·결과 지문과 범위를 기록한다.
- [x] T010 전체 pytest·ruff 및 하네스·인계 검사를 실행하고 release-evidence.md에 기록한다. 코드1b02509: 4989 passed/13 skipped(793.89초), ruff·하네스14/14·인계 사실 검사 통과.
- [ ] T011 품질 관문 PR을 검토·병합하고 HANDOFF.md 및 release-evidence.md에 배포 결과와 전체 목표 잔여 조건을 남긴다.

## Dependencies and implementation strategy

T001~T003 → US1 → US2 → T009~T011. 최소 구현 후 실제 원문으로 통합한다. 기능 일부 완료를 전체 목표 완료로 표시하지 않는다.
US1과 US2의 반례 목록 작성은 서로 다른 관점으로 병렬 가능하지만 같은 테스트 파일의 편집은 순차 진행한다. 단일 작업자가 수행하며 추가 에이전트를 요구하지 않는다.

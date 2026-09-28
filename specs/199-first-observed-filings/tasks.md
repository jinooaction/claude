# Tasks: 최초 관측 원문 누적 수집

## Phase 1 — Setup
- [x] T001 명세·설계·자료계약·체크리스트 작성: specs/199-first-observed-filings/.
- [x] T002 .specify/feature.json과AGENTS.md계획 포인터 연결, 독립설계검토 반영: specs/199-first-observed-filings/research.md.

## Phase 2 — Foundation
- [x] T003 불변저장·완료manifest·실행간시계역행·변조·경로반례 먼저 작성: tests/unit/test_filing_observations.py.
- [x] T004 폐쇄계약·blob/영수증/run/완료표지 검증·추가전용저장 구현: src/auto_invest/analytics/filing_observations.py.

2026-09-29 진행: 관측 영수증 폐쇄계약, UTC 순서, SEC URL 회사/문서 일치,
원문 지문·크기·경로 검증과 원문 추가전용 저장을 구현했다. 먼저 작성한 시험은
모듈 부재로 실패했고 구현 후 18개가 0.12초에 통과했다. 이어 완료 기록 시험6개가
RunStore 부재로 실패하는 것을 확인하고 구현했다. 추가 반례까지37개가0.18초에
통과했다. 실행 간 시계 역행, 완료 전 노출, 실패 기록, 정정 후 과거 조회 불변,
분기/부모 유실, 변조, 잘못된 계약, 저장 중단을 검사했다. 실제 수집/원격 보존은 미완료다.

## Phase 3 — US1 원문 관측
독립검사: 가짜HTTP로수신/차단/잘림/시계역행/잘못된문서/일부실패를검사한다.
- [x] T005 [US1] HTTP·속도·재시도·냉각·한도·부분범위 반례 작성: tests/unit/test_filing_collector.py.
- [x] T006 [US1] SEC목록/고정CIK본문 수집·관측구간·실패기록 구현: src/auto_invest/market_data/filing_collector.py.

2026-09-29 진행: 수집기 모듈 부재의 실패를 먼저 확인했다. 모의HTTP로 원문 성공,
최근5개 한도, 403즉시차단, 429/5xx/접속실패 제한재시도, 지속냉각/재개,
잘린응답/다른회사/크기초과/잘못된목록/시계역행/느린연속응답을 검사했다.
실제 SEC접속과 원격수집은 T011에 남아 있으며 이 단계로 실수집 성공을 주장하지 않는다.

## Phase 4 — US2 과거 조회와 기존195연결
독립검사: 정정/실패를추가해도과거조회불변, 수신완료만으로조기노출0건.
- [ ] T007 [US2] collect/verify/query/export/recover CLI와 새출력검사 구현: scripts/filing_observations.py.
- [ ] T008 [US2] 실제195import/query와의원문연결·현재검토시각보존·ID충돌반례: tests/integration/test_filing_observations_cli.py.

## Phase 5 — US3 원격 누적
독립검사: 쓰기권한분리·기존파일불변·게시충돌·복구artifact·정기누락범위를확인한다.
- [ ] T009 [US3] 고정회사/한도설정과 원격수집·추가전용발행·복구위치보고 구현: deploy/filing-observations.json, .github/workflows/collect-filing-observations.yml.
- [ ] T010 [US3] 권한·비밀값출력금지·force금지·원본보존 검사: tests/unit/test_filing_observation_workflow.py.
- [ ] T011 [US3] 원격실제수집2회·기존원문불변·복구/재조회·195연결 확인: specs/199-first-observed-filings/results.md.

## Phase 6 — Validation and handoff
- [ ] T012 정확한PR커밋 원격전체pytest/ruff 워크플로 연결·성공확인: .github/workflows/filing-observation-checks.yml.
- [ ] T013 하네스·인계·PR품질검사와실제검증근거기록: specs/199-first-observed-filings/results.md.
- [ ] T014 병합·필요배포·정기수집첫실행/영구보존확인 및남은전체목표인계: HANDOFF.md.

## Dependencies and strategy
T001→T002→T003→T004→T005→T006→T007→T008→T009→T010→T011→T012→T013→T014.
첫완성단위는US1이지만그것만으로199/전체목표완료를선언하지않는다.
서로다른가짜HTTP/CLI시험은독립검토가능하나구현은직렬로진행한다.
Mac의무거운검사는금지하며외부실수집도원격에서검증한다.
PR858은별도문서검사대기중이며기존핸들을확인한다. 새작업으로취소하지않는다.

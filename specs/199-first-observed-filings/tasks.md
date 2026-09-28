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
- [x] T007 [US2] collect/verify/query/export/recover CLI와 새출력검사 구현: scripts/filing_observations.py.
  진행: collect/verify/query/export 연결. 읽기 전용 검증·조회는 저장소 생성/변경을
  금지하고 출력 덮어쓰기를 거부한다. collect는 전체 작업에 단일작성자 파일잠금을
  적용하며 연락헤더를 환경에서만 받는다. recover는 원본 snapshot을 지문별 blob으로
  보존하고 새 완료시각 이후에만 노출한다. 동일관측 중복·내용충돌·원본변조·재복구와
  CLI내보내기 연결을 모의검사했다. 합성원문의195연결은 T008에서 확인했고 실제 원격수집은 남아 있다.
- [x] T008 [US2] 실제195import/query와의원문연결·현재검토시각보존·ID충돌반례: tests/integration/test_filing_observations_cli.py.
  합성원문을199 CLI로 내보낸 뒤195 실제 import_bundle/query_bundle에 연결했다.
  수집일 조회는 빈결과, 검토시각부터 노출, live_eligible=false, 원문바이트 동일,
  같은문서ID 거부, 명시적 새ID 정정 후 과거조회 불변을 확인했다. 실공시 해석 검증은 아니다.

## Phase 5 — US3 원격 누적
독립검사: 쓰기권한분리·기존파일불변·게시충돌·복구artifact·정기누락범위를확인한다.
- [x] T009 [US3] 고정회사/한도설정과 원격수집·추가전용발행·복구위치보고 구현: deploy/filing-observations.json, .github/workflows/collect-filing-observations.yml.
- [x] T010 [US3] 권한·비밀값출력금지·force금지·원본보존 검사: tests/unit/test_filing_observation_workflow.py.
  scripts/filing_publication.py는 전체 파일목록·지문·참조를 검사하고 기존파일 수정/삭제를
  거부한다. 읽기권한 수집→90일artifact→별도쓰기권한 게시를 연결했다. 실제실행은 T011에 남긴다.
- [ ] T011 [US3] 원격실제수집2회·기존원문불변·복구/재조회·195연결 확인: specs/199-first-observed-filings/results.md.

## Phase 6 — Validation and handoff
- [x] T012 정확한PR커밋 원격전체pytest/ruff 워크플로 연결·성공확인: .github/workflows/filing-observation-checks.yml.
  35c345d 정확한커밋은 run36459472345에서5131 passed/13 skipped와전체lint를 통과했다.
  실제전달 결함 보정7951980도 run36493749383에서5134 passed/13 skipped·전체lint를 통과했다.
- [x] T013 하네스·인계·PR품질검사와실제검증근거기록: specs/199-first-observed-filings/results.md.
- [ ] T014 병합·필요배포·정기수집첫실행/영구보존확인 및남은전체목표인계: HANDOFF.md.

## Dependencies and strategy
T001→T002→T003→T004→T005→T006→T007→T008→T009→T010→T011→T012→T013→T014.
첫완성단위는US1이지만그것만으로199/전체목표완료를선언하지않는다.
서로다른가짜HTTP/CLI시험은독립검토가능하나구현은직렬로진행한다.
Mac의무거운검사는금지하며외부실수집도원격에서검증한다.
PR858은 병합 완료했다. 199의 실제 수집·복구 검증 완료와는 구분한다.

## 후속 발행사 대안
- [x] T015 고정발행사URL·RSS·원문제목·별도출처계약과 반례검사. 저장/복구 포함55개통과,
  실제저장피드3개대상/7개미선택과발표원문제목일치확인. 네트워크수집기는T016에남음.
- [ ] T016 기존제한HTTP를공유하는발행사수집기·개인정보없는CLI와설정.
- [ ] T017 출처별원격보존·실패/냉각분리·원격실제수집2회와195현재검토연결.
- [ ] T018 최신전체검사·정기첫실행·인계. SEC미확보는명시하고전체181조건은그대로유지.
순서T015→T016→T017→T018. T011의SEC성공요건을대안성공으로거짓체크하지않는다.

# 작업 목록: 증거 수렴형 실거래 검증 캐너리

**입력**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`  
**위험 등급**: 4 - 실제 자본 배분·라이브 주문 경로 변경  
**시험 원칙**: 돈 경로의 실패 시험을 먼저 작성하고 의도한 이유로 실패한 뒤 구현한다.

## 1단계 - 명세와 안전 경계 고정

- [x] T001 `specs/176-live-canary-contract/contracts/operational-canary-evidence.schema.json`을 JSON 파서와 계약 검사로 검증한다.
- [x] T002 `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `tasks.md`를 결과 실행 전에 커밋해 사후 기준 변경을 막는다.
- [x] T003 헌법 X.4에 10% 운영 검증 캐너리, 단 1 상한, 단 2 별도 승격 조건을 추가하고 버전을 올린 전용 안전 경계 커밋을 만든다.

## 2단계 - 실패 시험으로 오류 재현

- [x] T004 [P] [US1] 운영 증거의 정상·역할·신선도·계보·지문·원시 숫자 재계산 실패 시험을 `tests/unit/test_operational_canary_evidence.py`에 작성한다.
- [x] T005 [P] [US1] 장기 성과는 통과하지만 `alpha_confirmed=false`, 10%, 최대 단 1인 시험과 비용 민감도 시험을 `tests/unit/test_operational_canary_evidence.py`에 작성한다.
- [x] T006 [P] [US2] 진단 `strategy_factory.json`과 자본 진입 파일의 역할·게시 경로가 분리되는 정적 실패 시험을 `tests/integration/test_strategy_factory_workflow.py`에 작성한다.
- [x] T007 [P] [US1] 단 0에서 운영 10% 진입, 운영 단 1의 자동 20% 승격 차단, 안전 실패 즉시 단 0 시험을 `tests/unit/test_capital_ladder.py`와 `tests/unit/test_ladder_decide_cli.py`에 작성한다.
- [x] T008 [P] [US3] 첫 매수의 운영 증거·지문·강화·체결 대리·정수 주·정합·킬스위치 실패 시험과 위험 축소 매도 보존 시험을 `tests/unit/test_live_entry_revalidation.py`에 작성한다.
- [x] T009 [US1] T004~T008이 새 계약 미구현 때문에 실패하는지 확인한다.

## 3단계 - 운영 검증 증거 구현

- [x] T010 [US1] 원시 월별 요인에서 CAGR·샤프·낙폭·초과수익 PSR·100/150bp 민감도를 재계산하는 `src/auto_invest/portfolio/operational_canary_evidence.py`를 구현한다.
- [x] T011 [US1] 기존 정확 배포 전략의 분할·비용·지문·강화·체결 대리·구현성을 묶는 운영 증거 제작을 `src/auto_invest/analytics/profit_evidence_engine.py`와 `scripts/profit_evidence_engine_probe.py`에 구현한다.
- [x] T012 [US1] 독립 명령줄 소비자 `scripts/operational_canary_evidence_gate.py`를 구현하고 JSON Schema와 원시 숫자를 모두 다시 검증한다.
- [x] T013 [US1] `.github/workflows/profit-evidence-engine.yml`이 현재 커밋의 `operational_canary_evidence.json`을 별도 sidecar로 발행하게 한다.

## 4단계 - 증거 역할과 자본 사다리 연결

- [x] T014 [US2] `.github/workflows/autonomous-strategy-factory.yml`이 진단 연구 파일과 `capital_entry_evidence.json`을 별도 역할·이름으로 게시하게 한다.
- [x] T015 [US1] `src/auto_invest/portfolio/capital_ladder.py`와 `src/auto_invest/cli.py`가 검증된 운영 증거로만 단 0→1을 허용하고 `entry_route`를 센티넬에 보존하게 한다.
- [x] T016 [US1] 운영 경로 단 1은 깨끗한 전진 알파 관문 없이는 단 2로 오르지 못하고, 위험 실패에서는 즉시 단 0으로 내려가게 한다.
- [x] T017 [US2] `.github/workflows/forward-edge-autoarm.yml`이 역할별 최신 sidecar를 내려받아 독립 검증 뒤 자본 판정기에 전달하게 한다.
- [x] T018 [US2] `src/auto_invest/analytics/money_path.py`가 역사적 유망성·운영 10%·알파 승격을 서로 다른 상태로 보고하게 한다.

## 5단계 - 첫 실제 주문 재검사와 자동화

- [x] T019 [US3] `src/auto_invest/portfolio/live_entry_revalidation.py`와 `scripts/live_entry_revalidation_probe.py`가 첫 운영 매수 직전 최신 증거와 모든 안전 게이트를 재검사하게 한다.
- [x] T020 [US3] `.github/workflows/rebalance-live-canary.yml`이 첫 매수에서 운영 증거와 `entry_route`를 검증하고 기존 서명·nonce·지정가·정규장 주문만 사용하게 한다.
- [x] T021 [US3] 주문·체결·부분 체결·미체결·취소·오류와 사후 정합을 같은 실행 ID의 추가 전용 장부와 정화 sidecar에 남기는 회귀 시험을 통과시킨다.

## 6단계 - 로컬 검증과 PR

- [x] T022 T004~T008의 관련 단위·통합·워크플로 시험을 통과시킨다.
- [x] T023 `uv run pytest`와 `uv run ruff check src tests` 전체 검증을 통과시킨다.
- [x] T024 `uv run python scripts/agent_harness_probe.py --strict`와 `uv run python scripts/check_handoff_facts.py`를 통과시킨다.
- [x] T025 위험 등급 4, 문제 정의, 탐색 근거, 안전 경계, 롤백을 담은 PR 본문을 `scripts/check_pr_quality_gate.py`로 검증한다.
- [x] T026 브랜치를 푸시하고 PR을 만든 뒤 최신 `origin/main`과 머지 가능성·원격 검사를 재확인해 merge 방식으로 자동 머지한다.

## 7단계 - 생산 배포와 실제 체결 완료

- [x] T027 `deploy-status` 기술로 main dry-run worker 배포와 서버 코드 커밋 일치를 확인한다.
- [x] T028 생산 profit-evidence·strategy-factory sidecar를 갱신하고 운영 증거·자본 증거·진단 증거의 역할과 커밋을 각각 검증한다.
- [x] T029 자본 사다리가 최신 NAV의 10% 이하로 단 0→1, `entry_route=operational_canary`를 기록했는지 확인한다.
- [ ] T030 [US3] 미국 정규장 예약 실행에서 실제 KIS 지정가 주문의 접수와 체결을 확인한다.
- [ ] T031 [US3] 체결 수량·가격이 KIS 조회, 전략 장부, 추가 전용 감사 로그에서 일치하고 사후 계좌 정합이 통과했는지 확인한다.
- [ ] T032 운영 경로가 여전히 최대 단 1이고 깨끗한 전진 알파 증거 없이 20%로 승격되지 않았는지 확인한다.
- [ ] T033 `handoff` 기술로 `HANDOFF.md`의 main 커밋, 테스트, 배포, 실제 주문·체결·감사와 남은 관찰 지점을 갱신·검증·머지한다.
- [x] T034 [US3] 자동 센티넬 PR이 일반 PR·push 검사를 발화하지 않는 재귀 억제 오류를 재현하고,
  머지 전 자체 품질 관문과 머지 뒤 exact-main 증거→무주문 사전점검 연쇄 실행을 추가한다.
- [x] T035 [US3] 생산 주문 작업의 로컬 첫 매수 재검증에 프로젝트 의존성이 설치되지 않아
  `pydantic` import에서 실패하는 오류를 재현하고, 고정된 `uv` 런타임으로 실행하게 한다.
- [x] T036 [US3] 최근 예약 실행의 42~80분 및 약 9시간 지연과 GitHub의 정각 혼잡 경고를
  재현 증거로 남기고, 비정각 뉴욕 현지 예약·서머타임 환산·마이크로 예약 비변경 시험을 작성한다.
- [x] T037 [US3] 라이브 캐너리를 뉴욕 현지 10:17 단일 예약으로 바꾸고 money-path의 다음 실행
  표시를 같은 계약으로 맞춘 뒤, 예약 이벤트만 실주문인 기존 경계를 다시 검증한다.
- [x] T038 [US3] 생산 첫 체결 전 재검증 로그가 메타데이터 한 줄 뒤 JSON을 남기는 실제 형식을
  재현하고, 성공 표 행만 있고 JSON이 없으면 통과로 추론하지 않는 실패 시험을 작성한다.
- [x] T039 [US3] 헤더 범위의 첫 JSON 객체를 보수적으로 추출하고 `allowed`·`state`를 money-path
  preflight 사실로 변환한 뒤 현재 생산 sidecar 원문에서 `ok=True`, `ENTRY_READY`를 재현한다.
- [x] T040 [US3] 보정 커밋을 main에 배포한 뒤 읽기 전용 money-path를 다시 실행해 발행 sidecar의
  마지막 preflight도 `ok=True`, `reason=ENTRY_READY`로 표시되는지 확인한다.
- [x] T041 [US3] 생산 설정의 레거시 `canary_capital_pct=5`가 명세상 단 1 NAV 10%와 다르지만
  첫 주문 재검사가 이를 무시하는 실패 시험을 작성하고 의도한 이유로 실패시킨다.
- [x] T042 [US3] 운영 증거의 10%와 라이브 fundability 설정의 `canary_capital_pct`를 직접 대조해
  누락·파싱 실패·불일치를 `operational_canary_capital_contract`로 실패 폐쇄하고 설정을 10%로 맞춘다.
- [x] T043 [US3] 관련·전체 시험과 품질 관문을 통과시키고 main 배포 뒤 exact-main 무주문
  사전점검에서 새 자본 계약을 포함한 `ENTRY_READY`를 다시 확인한다.
- [x] T044 [US3] 비정각 예약도 약 9시간 지연되면 `rebalance-once --mode live`가 정규장 밖에서
  브로커에 도달할 수 있는 오류를 재현하고, 정규장·장 마감 뒤·휴장·종이매매·미리보기 실패
  시험을 `tests/unit/test_rebalance_live_session_guard.py`에 작성한다.
- [x] T045 [US3] 실주문 CLI가 DB 마이그레이션과 브로커 접근 전에 서버 현재 시각을 XNYS
  달력으로 검사하고, 닫힌 장에서는 다음 개장 시각과 종료 코드 75를 남기며 우회 옵션 없이
  실패 폐쇄하게 한다.
- [x] T047 [US3] 정규장 안에 시작한 뒤 처리 중 마감되는 경쟁 상태를 재현하고, `OrderRouter`가
  실행 권한 잠금 뒤 각 실제 중개사 쓰기 직전에 XNYS를 다시 검사해 다음 주문을
  `market_hours_gate`로 감사 거부하게 한다.
- [x] T048 [US3] `rebalance-once`가 도중 마감 거부를 종료 코드 75로 반환하고,
  `rebalance-micro-gtaa-canary.yml`을 포함한 실주문 호출자가 SSH 종료 코드를 단계 실패로
  전파하게 한다.
- [x] T049 [US3] 첫 주문 접수 뒤 다음 주문이 정규장 게이트로 막혀 LIVE 단계가 실패해도 후속
  측정·보고를 항상 실행하고, 결과 JSON의 `SUBMITTED` 행을 세어 부분 실행으로 표시하게 한다.
- [x] T046 [US3] 관련·전체 시험, 린트, 엄격 하네스, HANDOFF 사실 검사, PR 품질 관문을 통과시켜
  merge·배포하고 exact-main 무주문 사전점검에서 정규장 게이트가 실주문 경로에 포함됐는지
  확인한다.
- [x] T050 [US3] 단일 비정각 예약도 2026-08-31 목표 시각 뒤 생성되지 않은 운영 실패를 기록하고,
  복수 장중 예약·거래일 1회 선점·중복 브로커 호출 0건·sidecar 보존의 실패 시험을 먼저 작성한다.
- [x] T051 [US3] production live-canary helper가 XNYS 정규장 확인 뒤 뉴욕 거래일 실행권을 파일 잠금
  아래 추가 전용으로 선점하고, 같은 날 후속 서명 run에는 최초 run ID를 반환한 채 주문 CLI를
  호출하지 않게 한다.
- [x] T052 [US3] `rebalance-live-canary.yml`에 뉴욕 10:17~13:17의 복수 비정각 예약 기회를 추가하고,
  무장 preview와 서버 중복 판정 run이 최초 production sidecar를 덮어쓰지 않게 한다.
- [ ] T053 [US3] 관련·전체 시험, 린트, 엄격 하네스, HANDOFF 사실 검사와 PR 품질 관문을 통과시키고,
  장 마감 뒤 exact-main 배포와 다음 거래일 최초 1회 실행·후속 중복 차단을 생산에서 확인한다.
- [x] T054 [US3] 시간별 복수 예약 보정이 main에 들어온 뒤에도 2026-08-31 12:17 뉴욕 예약 run이
  생성되지 않아 다음 기회까지 한 시간을 잃는 실패를 기록하고, 10:20 뒤 10:29 후보와 촘촘한
  비정각 cron을 요구하는 실패 시험을 먼저 실행해 의도한 이유로 실패시킨다.
- [x] T055 [US3] 라이브 예약을 뉴욕 현지 10:17~13:53의 최대 12분 간격으로 늘리고,
  money-path의 다음 후보 표시를 같은 계약으로 맞춘다. 승인 이벤트·자본·서명·거래일 1회 선점은
  변경하지 않는다.
- [x] T056 [US3] 관련·전체 시험, 린트, 엄격 하네스, HANDOFF 사실 검사와 PR 품질 관문을 통과시켜
  merge하고 장 마감 뒤 exact-main 배포를 확인한다.
- [ ] T057 [US3] 다음 거래일에 최초 schedule run의 실제 주문·체결·감사·정합과 같은 날 후속
  schedule run의 원래 run ID·중복 주문 0건을 생산 증거로 확인한다.
- [x] T058 [US3] 생산 배포 감사 run `33439750122`가 `REQUESTED_CID='' bash -s` 때문에
  forced-command 경계에서 종료 코드 126으로 거부된 계약 오류를 기록하고, 임의 셸 금지·고정
  명령·이중 입력 검증·읽기 전용 helper 설치의 실패 시험을 먼저 실행해 의도한 이유로 실패시킨다.
- [x] T059 [US3] root 소유 `deploy-audit-on-instance.sh`와 gateway의 `deploy-audit` 고정 명령을
  추가하고 workflow가 해당 명령만 호출하게 한다. helper는 고정 DB의 `DEPLOY_%` 행만
  `sqlite3 -readonly`로 읽고 요청 ID를 다시 검증하며 관련 회귀 시험을 통과시킨다.
- [x] T060 [US3] 전체 시험·린트·엄격 하네스·HANDOFF 사실 검사·PR 품질 관문을 통과시키고
  merge·exact-main 배포한 뒤 배포 감사 sidecar의 `DEPLOY_COMPLETED`를 확인한다.
- [x] T061 [US3] exact-main KIS smoke run `33442299948`에서 IAUM의 첫 `EXCD=NAS` 조회 500이
  거래소 자동 해석을 중단해 5/6으로 실패한 생산 오류를 기록하고, 5xx 후속 후보·전 후보 실패·
  4xx 즉시 실패의 회귀 시험을 먼저 실행해 의도한 이유로 실패시킨다.
- [x] T062 [US3] `get_quote_resolving_market`이 5xx 뒤 제한된 다음 거래소를 읽어 유효 시세와 실제
  거래소를 반환하되, 모든 후보 실패 시 마지막 5xx를 다시 전파하고 4xx를 즉시 전파하게 한다.
- [x] T063 [US3] 관련·전체 시험, 린트, 엄격 하네스, HANDOFF 사실 검사와 PR 품질 관문을 통과시켜
  merge·exact-main 배포하고 생산 KIS smoke 6/6과 주문 없는 첫 진입 사전점검을 다시 확인한다.
- [x] T064 [US3] 2026-08-31의 19개 GitHub 후보가 같은 공급자 장애로 장 마감 뒤 생성된 사실을
  기록하고, GitHub 후보 수 증가가 독립 복구가 아니라는 원인과 안전한 server fallback 계약을
  spec·research·plan·data-model·quickstart와 헌법 X.4 12.0.0에 먼저 확정한다.
- [x] T065 [US3] root 소유 systemd 신원, exact-main, 첫 진입 재검증, XNYS, 센티넬, 공유 거래일
  선점, 선점 뒤 무재시도, 고정 읽기 전용 증거를 요구하는 실패 시험을
  `tests/unit/test_live_canary_server_scheduler.py`와 기존 gateway/workflow/unit 시험에 먼저 작성한다.
- [x] T066 [US3] `auto-invest-live-canary.service`·`.timer`와 root 소유
  `live-canary-scheduled-on-instance.sh`를 구현해 뉴욕 10:35 이후 독립 후보가 GitHub와 같은
  첫 진입·위험·정규장·거래일 선점을 거쳐 하루 한 번만 주문하게 한다.
- [x] T067 [US3] 공유 선점 장부에 `github_schedule|server_timer` 출처를 추가하고, server 최초
  실행은 주문 단계 결과와 무관하게 체결 동기화·측정·정합과 추가 전용 정화 요약을 보존하게 한다.
- [x] T068 [US3] SSH forced-command에 최신 또는 검증된 14자리 run ID만 받는
  `live-canary-scheduled-status` 읽기를 추가하고
  server `systemd-order`는 원격에서 계속 거부한다. 뒤늦은 GitHub 중복 run은 최초 server 실행을
  읽어 sidecar에 발행하되 broker·fills·measure·reconciliation을 다시 호출하지 않게 한다.
- [x] T069 [US3] 관련 시험과 `uv run pytest`·ruff·엄격 하네스·HANDOFF 사실 검사·PR 본문 품질
  관문을 통과시키고, constitution 전용 커밋을 포함한 위험 등급 4 PR을 merge한다.
- [x] T070 [US3] 장중 배포 금지를 지켜 장 마감 뒤 exact-main 배포와 server timer 활성·다음 발화
  시각, KIS smoke 6/6, 주문 없는 exact-main 사전점검을 확인한다.
- [ ] T071 [US3] 다음 거래일에 GitHub 또는 server timer 중 최초 유효 실행의 실제 주문·체결·감사·
  정합과 다른 출처의 중복 broker write 0건, 동일 최초 run/source 증거를 생산에서 확인한다.
- [x] T072 [US3] 생산 schedule run `33540003731`의 1주 미만 IAUM 목표와 SCHX 계획이 기존 전체
  목표 66% 분모에서 차단된 원인을 `specs/176-live-canary-contract/{spec,plan,research,data-model,quickstart,tasks}.md`에
  고정하고, 정수 주 표현 가능 목표에만 66%를 적용하되 전체 오차 한도는 유지하는 계약을 확정한다.
- [x] T073 [US3] 생산 입력의 안전한 부분 구현 통과, 모든 목표 1주 미만·표현 가능 목표 미자금·
  큰 누락 오차의 실패와 구형 증거 거부 시험을 `tests/unit/test_fundability.py`에 먼저 작성하고
  의도한 이유로 실패시킨다.
- [x] T074 [US3] 전체 목표 진단과 정수 주 표현 가능 목표 진단을 구분하는 재계산 가능한 새 증거
  계약을 `src/auto_invest/portfolio/fundability.py`에 구현하고 첫 진입 소비자가 같은 입력을 완전
  일치 검증하게 한다.
- [x] T075 [US3] 관련 fundability·rebalancer·첫 진입·자본 사다리 시험을 통과시키고 기존 시세·
  오차·현금·최소 주문·화이트리스트·노출·하향 경계가 완화되지 않았는지 확인한다.
- [x] T076 [US3] `uv run pytest`·ruff·엄격 하네스·HANDOFF 사실 검사·PR 본문 품질 관문을 통과시키고,
  새 헌법 전용 커밋과 구현 커밋을 PR #724에 반영해 장 마감 뒤 merge한다.
- [x] T077 [US3] exact-main 배포, server timer 활성, KIS smoke 6/6과 주문 없는 exact-main 사전점검에서
  새 정수 주 증거 계약과 `ENTRY_READY`를 확인한다.
- [ ] T078 [US3] 다음 첫 유효 자동 실행에서 실제 주문·체결·전략 감사·계좌 정합과 다른 scheduler의
  중복 broker write 0건을 생산 증거로 확인한다.
- [x] T079 [US3] 2026-09-02 exact deploy 뒤 문서 전용 main 머지로 독립 timer가 결과를 내지 못한
  원인을 spec·plan·research·data-model·quickstart·tasks와 헌법 X.4 14.0.0에 먼저 고정하고,
  현재 main 증거와 실제 배포 감사 커밋을 분리하는 안전 경계 전용 커밋을 만든다.
- [x] T080 [US3] 배포 커밋 뒤 `HANDOFF.md`만 추가된 main 통과, `src/`·`deploy/`·workflow·설정·
  기타 경로와 분기 계보 실패, scheduler와 내부 `systemd-order`의 이중 검사, 선점·broker write
  0건을 고정 저장소 실패 시험으로 먼저 작성해 의도한 이유로 실패시킨다.
- [x] T081 [US3] server scheduler가 배포 커밋 조상 관계와 고정 비실행 경로만 운영 동등하게
  판정하고, 현재 main으로 첫 진입을 재검증하되 실제 배포 커밋의 `DEPLOY_COMPLETED`를 요구하게
  한다. 내부 `systemd-order`가 현재 main 경쟁을 포함해 같은 검사를 다시 수행하고 요약 1.1에
  두 커밋과 동등성 판정을 남기게 한다.
- [x] T082 [US3] 관련·전체 시험, ruff, 엄격 하네스, HANDOFF 사실 검사와 PR 본문 품질 관문을
  통과시키고 위험 등급 4 PR을 연다. 미국 정규장 중에는 merge·deploy하지 않는다.
- [x] T083 [US3] 장 마감 뒤 PR을 merge하고 exact latest main 배포, timer active·다음 발화,
  KIS smoke 6/6과 주문 없는 latest-main `ENTRY_READY`를 확인한다.
- [ ] T084 [US3] 다음 첫 유효 자동 실행에서 요약 1.1의 두 커밋, 주문·체결·전략 감사·정합과
  다른 scheduler의 동일 최초 run/source·중복 broker write 0건을 생산 증거로 확인한다.
- [x] T085 [US3] 뉴욕 13:59 뒤 긴급 배포되면 당일 자동 기회가 없는 회복 공백을
  Spec 176에 기록하고, GitHub·수동 주문 경로를 늘리지 않은 채 root server timer만
  10:35~15:35의 12분 간격 26개 자동 후보로 연장한다.
- [x] T086 [US3] timer 후보 정확성, 15:35 상한, 기존 거래일 1회·수동 실주문 금지
  회귀와 전체 시험·린트·하네스·PR 관문을 통과시켜 머지·장중 긴급 배포한다.
- [ ] T087 [US3] 남은 15:11·15:23·15:35 중 첫 유효 server timer가 스스로 실제 주문·체결·
  전략 감사·계좌 대사를 완료하고 후속 후보가 중복 broker write 0건을 재현하는지 확인한다.
- [x] T088 [US3] GitHub 예약 지연 중 독립 서버 timer 결과를 즉시 읽을 수 있도록, 기존 고정
  `live-canary-scheduled-status`만 호출하고 주문·서비스·timer 제어를 포함하지 않는 수동 읽기 전용
  관측 워크플로와 닫힌 summary 1.1·정화 sidecar·실패 폐쇄 시험을 추가한다.
- [x] T089 [US3] 관련·전체 시험, ruff, 엄격 하네스, HANDOFF 사실 검사와 PR 본문 품질 관문을
  통과시키고 등급 2 관측 PR을 merge한다.
- [ ] T090 [US3] 다음 독립 서버 자동 후보 뒤 읽기 전용 관측 워크플로를 실행해 실제 server summary와
  기존 GitHub sidecar의 최초 run/source·주문·체결·감사·대사·중복 broker write 0건을 대조한다.
- [x] T091 [US3] 2026-09-03 server timer가 active지만 `scheduled-status`가 종료 코드 2만 반환해
  미발화와 선점 전 실패를 구분하지 못한 생산 공백을 spec·plan·research·data-model·quickstart에
  기록하고, 고정 systemd 필드와 원문 없는 사건 코드만 허용하는 실패 시험을 먼저 작성한다.
- [x] T092 [US3] root helper와 forced-command에 인자 없는 `live-canary-runtime-status`를 추가하고,
  observer가 성공 요약이 없을 때만 닫힌 runtime JSON을 검증·정화 발행하되 최종 실패 판정과
  주문·서비스·timer 비변경 경계를 유지하게 한다.
- [ ] T093 [US3] 관련·전체 시험, ruff, strict 하네스, HANDOFF 사실 검사와 PR 품질 관문을 통과시켜
  merge·exact-main 배포한 뒤 읽기 전용 observer에서 실제 timer 발화·서비스 종료값·고정 사건 코드를
  확인하고 원인 보정을 같은 거래일 남은 자동 후보에 적용한다.
- [x] T094 [US3] 2026-09-03 자동 server timer가 `ENTRY_READY`·선점·사후 대사를 완료했지만
  `orders_submitted=0`인 생산 사례를 고정하고, 계획 없음·보류·gate·브로커 거부를 구분하지 못하는
  기존 요약의 진단 공백과 민감정보 비노출 계약을 spec·plan·research·data-model에 기록한다.
- [x] T095 [US3] root 전용 `order.log`에서 선택 run의 CLI JSON만 읽어 허용 상태·gate·수량·건수만
  반환하는 `scheduled-order-diagnostics`와 exact forced-command를 구현하고, observer가 주문 0건일 때
  닫힌 스키마로 재검증해 별도 sidecar를 발행하도록 회귀 시험을 추가한다.
- [ ] T096 [US3] 관련·전체 시험, ruff, strict 하네스, HANDOFF 사실 검사와 PR 품질 관문을 통과시켜
  merge·승인된 exact-main 긴급 배포한 뒤 생산 run의 정화 진단으로 실제 0건 원인을 확정한다. 진단
  전에는 거래일 선점 삭제·수동 service 시작·자동 재시도를 추가하지 않는다.
- [x] T097 [US3] 생산 진단에서 IAUM·SCHX가 모두 `REJECTED_BY_BROKER`임을 확인하고, 원문·가격·
  계좌 없이 KIS 코드·HTTP 상태·예외 종류·고정 TR ID·거래소·주문 구분만 반환하는 진단 1.1 계약과
  비밀값 비노출·닫힌 형식 실패 시험을 추가한다.
- [x] T098 [US3] 진단 1.1을 검증·merge·exact-main 배포해 생산 run의 두 주문이 공통으로
  `rt_cd=7`, `msg_cd=APBK1672`, HTTP 200, `TTTT1002U`, `AMEX`, `00`에서 거부됐음을 확정하고,
  KIS 공식 현재 구현과 비교해 공유 REST 헤더의 `custtype`·`tr_cont` 누락으로 원인 범위를 좁힌다.
- [x] T099 [US3] 공유 KIS REST 헤더에 호출자가 바꿀 수 없는 `custtype=P`, `tr_cont=""`를
  추가하고 주문 캡처 회귀·관련 시험·전체 시험·ruff·엄격 하네스·HANDOFF 사실 검사·PR 품질 관문을
  통과시킨 뒤 merge·exact-main 배포·KIS smoke 6/6·주문 없는 `ENTRY_READY`를 확인한다.
- [ ] T100 [US3] 다음 첫 유효 자동 정규장 실행에서 KIS 신규 주문 접수·실제 신규 체결·전략 추가
  전용 감사·같은 실행 계좌 대사와 다른 scheduler의 동일 최초 run/source·중복 broker write 0건을
  production 증거로 확인한다. 수동 주문·수동 service 시작·기존 거래일 선점 삭제는 하지 않는다.
- [x] T101 [US5] 헌법 15.5.0과 spec·plan·research·data-model·quickstart에 원래 선점을 보존하는
  exact-manifest 기반 server timer same-session 복구 계약을 고정하고 안전 경계 전용 커밋을 만든다.
- [x] T102 [US5] 최초 run의 일부 결과·접수 불명·접수·부분체결·체결·열린 주문·사후 실패,
  GitHub 출처, manifest 누락·불일치·미배포 보정·기소비 슬롯이 모두 추가 CLI 0건으로 실패하는
  gateway·scheduler 회귀 시험을 `tests/unit/test_live_canary_gateway.py`와
  `tests/unit/test_live_canary_server_scheduler.py`에 먼저 작성한다.
- [x] T103 [US5] `deploy/live-canary-retry-incident.json`의 닫힌 manifest, root 추가 전용 retry
  장부와 배타 선점, fresh KIS open-order proof, 자동 server timer 전용 재진입을
  `deploy/live-canary-on-instance.sh`와 `deploy/live-canary-scheduled-on-instance.sh`에 구현한다.
- [x] T104 [US5] server summary와 고정 observer가 initial·same_session_retry 및 최초·복구 run
  신원을 구분하되 다른 scheduler의 broker/fill/measure/reconciliation 반복을 막도록
  deploy helper·workflow·계약 시험을 갱신한다.
- [x] T105 [US5] 관련 시험·전체 pytest·ruff·strict harness·HANDOFF 사실 검사·PR 본문 품질
  관문을 통과시키고 위험 등급 4 PR을 merge·exact-main 배포·KIS smoke·주문 없는 preflight까지
  확인한다.
- [ ] T106 [US5] 다음 실제 zero-acceptance 사고가 발생하면 같은 장의 다음 자동 server timer에서
  복구 슬롯 1회·실제 접수/체결·전략 감사·계좌 대사와 이후 후보의 중복 broker write 0건을
  production 증거로 확인한다. 정상 신규 거래일 첫 실행이 체결되면 이 과제는 비발동 증거로 남긴다.
- [x] T107 [US5] 2026-09-04 최초 server timer `20260904143505`의 IAUM `EGW00201`·SCHX
  `APBK1672`, 두 주문 명시적 거부, 접수·열린 주문 0, 사후 측정·대사 정상 증거를 고정하고 KIS
  공식 최소 요청 간격과 기존 15-token 초기 burst의 차이를 spec·plan·research·data-model·
  quickstart에 기록한다.
- [x] T108 [US5] live rebalancer의 KIS REST 제한기를 burst 없는 5회/초·capacity 1로 고정하고
  주문 비재전송·기존 돈 경로 경계 회귀 시험을 먼저 통과시킨 뒤, 정확한 2026-09-04 사고 manifest와
  보정 커밋을 위험 등급 4 PR로 merge·오너 승인 장중 긴급 배포한다.
- [ ] T109 [US5] 다음 자동 server timer가 기존 첫 선점을 보존한 채 복구 슬롯을 정확히 한 번
  소비해 실제 주문 접수·체결·전략 감사·계좌 대사를 남기고, 뒤 자동 후보와 GitHub scheduler가
  동일 first run/retry run을 반환하며 추가 broker write 0건인지 production에서 확인한다.
- [x] T110 [US5] 2026-09-04 15:23 UTC 자동 복구가 슬롯을 한 번 소비하고 `EGW00201`을 제거했지만
  IAUM·SCHX 모두 `APBK1672`로 명시적 거부되어 접수·열린 주문·신규 체결 0건, 사후 측정·대사
  정상으로 끝난 사실과 KIS 공식 오류 목록의 코드 설명 부재를 기록한다.
- [x] T111 [US5] 기존 root 전용 `msg1`을 원문·부분 문자열·길이·해시 없이 닫힌 원인 주제로만
  바꾸는 주문 진단 1.2를 실패 시험부터 구현하고, server helper와 observer가 같은 키·열거값·
  거부 결과 수를 이중 검증하도록 한다.
- [x] T112 [US5] 관련·전체 시험, ruff, strict harness, HANDOFF 사실 검사, PR 본문 품질 관문을
  통과시켜 PR #752로 merge하고 exact-main 배포한 뒤 읽기 전용 observer run `33892995912`의
  실제 `message_topics=[account, service_registration]`으로 다음 수정 지점을 KIS 계좌 거래서비스
  신청 상태로 확정한다. 진단 과정의 주문·재시도·서비스·timer 시작은 0건이었다.
- [ ] T113 [US5] 운영자가 KIS 앱의 본인 인증·약관 동의 경계에서 `해외증권 거래신청`과
  IAUM·SCHX 같은 ETF 주문에 필요한 `해외ETP 거래신청`을 완료 또는 활성 상태로 확인한다.
  시스템은 금융 약관에 대신 동의하거나 계좌 서비스를 임의 활성화하지 않는다.
- [ ] T114 [US5] 서비스 신청 완료 뒤 다음 유효 자동 정규장 실행에서 신규 주문 접수·실제 체결·
  전략 추가 전용 감사·같은 실행 계좌 대사와 다른 scheduler의 중복 broker write 0건을 확인한다.
  수동 주문·수동 service 시작·이미 소비한 2026-09-04 복구 슬롯 재개방은 하지 않는다.
- [x] T115 [US5] 해외증권·해외 ETP·해외 변동성 ETN·범위 불명 서비스를 원문 없이 구분하는
  닫힌 `service_registration_scopes` 계약과 실패 시험을 추가하고, server helper와 observer를
  진단 스키마 1.3으로 올려 주제·범위 모순과 미허용 키를 실패 폐쇄한다.
- [ ] T116 [US5] 관련·전체 시험, ruff, strict harness, HANDOFF 사실 검사와 PR 품질 관문을
  통과시켜 진단 1.3을 merge·exact 배포한 뒤, 읽기 전용 observer가 과거 자동 실행의 실제 신청
  범위를 원문 노출·주문·재시도·service/timer 시작 없이 발행하는지 production에서 확인한다.

## 의존성과 완료 계약

- T001~T003 뒤에만 돈 경로 구현을 시작한다.
- T004~T009의 의도된 실패를 확인한 뒤 T010~T021을 구현한다.
- T022~T026이 모두 통과한 뒤에만 main 배포와 자본 무장을 진행한다.
- T030~T031의 실제 체결·감사·정합이 끝나기 전에는 사용자 목표를 완료로 표시하지 않는다.
- T065 실패 시험 뒤에만 T066~T068을 구현하고, T069~T070 전에는 server timer를 생산 활성화하지 않는다.
- T071의 이중 scheduler 생산 증거가 끝나기 전에는 예약 가동성 문제를 해결됐다고 표시하지 않는다.
- T072의 계약 고정과 헌법 전용 커밋 뒤에만 T073~T074를 구현하고, T076~T077 전에는 새 계약을
  production에 활성화하지 않는다. T078 전에는 사용자 목표를 완료로 표시하지 않는다.
- T079의 계약 고정과 헌법 전용 커밋 뒤에만 T080~T081을 구현하고, T082~T083 전에는 새 운영
  리비전 계약을 production에 활성화하지 않는다. T084 전에는 scheduler 가동성과 사용자 목표를
  완료로 표시하지 않는다.
- T085 계약과 시간 상한 회귀 뒤에만 T086을 완료하고, T087의 자동 생산 증거 전에는
  당일 회복과 사용자 목표를 완료로 표시하지 않는다.
- T088 관측 경로는 주문·서비스를 실행하지 않아야 하며 T089 검증·merge 뒤에만 production 조회에
  사용한다. T090은 T071·T078·T084·T087의 생산 증거를 대체하지 않고 더 빠르게 회수한다.
- T091 실패 시험 뒤에만 T092를 구현하고, T093의 production runtime 진단은 성공 요약이나
  실제 체결 증거를 대체하지 않는다. 진단이 지목한 원인을 고친 뒤 자동 timer 후보로만 재검증한다.
- T094 계약 뒤에만 T095를 구현하고, T096 생산 진단 전에는 당일 선점을 지우거나 재시도하지 않는다.
  진단 결과는 T071의 실제 주문·체결·감사·대사 증거를 대체하지 않는다.
- T097의 닫힌 진단을 production에서 확인하기 전에는 주문 원인을 추측해 고치거나 재시도하지 않는다.
  T098의 production 코드와 공식 현재 예제 대조 뒤에만 T099를 구현한다. T100의 실제 자동 접수·체결
  전에는 헤더 보정을 해결 완료로 표시하지 않는다. 같은 날 추가 자동 재시도가 필요하면 첫 선점을
  삭제하지 않는 별도 추가 전용 권한·중복 차단·헌법 변경을 먼저 설계해야 한다.
- T101 헌법·명세 계약 뒤에만 T102 실패 시험과 T103~T104 구현을 진행한다. T105 전에는 복구
  경로를 production에 활성화하지 않는다. 복구 슬롯은 T100의 정상 다음 거래일 자동 실행을
  대체하지 않으며, T106의 발동 조건이 없는 정상 체결에서는 사용하지 않는다.
- T107의 production 진단과 공식 pacing 대조 뒤에만 T108을 구현한다. T108의 exact manifest가
  배포되기 전에는 복구 슬롯이 실패 폐쇄되어야 하며, T109 전에는 주문 문제와 목표를 완료로
  표시하지 않는다.
- T110의 공식 오류 목록 대조 뒤에만 T111을 구현한다. T112의 production 주제 관측 전에는
  `APBK1672` 의미를 단정하거나 거래소·가격·주문 유형·계좌 설정을 추측으로 바꾸지 않는다.
- T112는 코드·주문 형식이 아니라 KIS 계좌의 서비스 신청 영역을 지목한다. T113은 운영자 본인
  인증과 금융 약관 동의가 필요한 외부 관문이며 자동화하지 않는다. T114 전에는 실제 자동매매
  목표를 완료로 표시하지 않는다.
- T115는 운영자 외부 관문을 더 정확히 설명할 뿐 T113을 자동화하거나 T114의 실제 체결 증거를
  대신하지 않는다. T116 production 범위 관측 전에는 어느 신청이 빠졌는지 단정하지 않는다.
- 시장 휴장, 0개 목표 주문, 증거 불일치, 브로커 장애이면 주문을 만들지 않고 다음 정규장 관찰을 계속한다.
- 10% 운영 캐너리는 수익 보장이 아니며, T032의 승격 차단이 유지돼야 한다.

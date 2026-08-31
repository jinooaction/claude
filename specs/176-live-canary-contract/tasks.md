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
- [ ] T026 브랜치를 푸시하고 PR을 만든 뒤 최신 `origin/main`과 머지 가능성·원격 검사를 재확인해 merge 방식으로 자동 머지한다.

## 7단계 - 생산 배포와 실제 체결 완료

- [ ] T027 `deploy-status` 기술로 main dry-run worker 배포와 서버 코드 커밋 일치를 확인한다.
- [ ] T028 생산 profit-evidence·strategy-factory sidecar를 갱신하고 운영 증거·자본 증거·진단 증거의 역할과 커밋을 각각 검증한다.
- [ ] T029 자본 사다리가 최신 NAV의 10% 이하로 단 0→1, `entry_route=operational_canary`를 기록했는지 확인한다.
- [ ] T030 [US3] 미국 정규장 예약 실행에서 실제 KIS 지정가 주문의 접수와 체결을 확인한다.
- [ ] T031 [US3] 체결 수량·가격이 KIS 조회, 전략 장부, 추가 전용 감사 로그에서 일치하고 사후 계좌 정합이 통과했는지 확인한다.
- [ ] T032 운영 경로가 여전히 최대 단 1이고 깨끗한 전진 알파 증거 없이 20%로 승격되지 않았는지 확인한다.
- [ ] T033 `handoff` 기술로 `HANDOFF.md`의 main 커밋, 테스트, 배포, 실제 주문·체결·감사와 남은 관찰 지점을 갱신·검증·머지한다.

## 의존성과 완료 계약

- T001~T003 뒤에만 돈 경로 구현을 시작한다.
- T004~T009의 의도된 실패를 확인한 뒤 T010~T021을 구현한다.
- T022~T026이 모두 통과한 뒤에만 main 배포와 자본 무장을 진행한다.
- T030~T031의 실제 체결·감사·정합이 끝나기 전에는 사용자 목표를 완료로 표시하지 않는다.
- 시장 휴장, 0개 목표 주문, 증거 불일치, 브로커 장애이면 주문을 만들지 않고 다음 정규장 관찰을 계속한다.
- 10% 운영 캐너리는 수익 보장이 아니며, T032의 승격 차단이 유지돼야 한다.

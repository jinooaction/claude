# 작업 목록: 독립 월말·월초 전략과 교정 의미 정렬

**입력**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`
**위험 등급**: 4(돈 경로 판정 소비와 미래 전략 후보)

## 1단계 — 계약과 회귀 시험

- [x] T001 [US1] `tests/unit/test_forward_gate_calibration.py`에 오합격/검출력 별도 필드 시험을 먼저 추가한다.
- [x] T002 [US1] `tests/unit/test_backtest_anchored.py`에 빈 앵커드+표준 확정 방법 보존 시험을 먼저 추가한다.
- [x] T003 [US1] `tests/unit/test_ladder_decide_cli.py`에 교정 누락·UNDERPOWERED·CALIBRATION_FAILED 차단과 표준 확정 통합 시험을 먼저 추가한다.
- [x] T004 [US1] `tests/unit/test_capital_ladder.py`에 앵커드·탐색 진단 전용, 상향 노출 차단, 위험 축소 허용 시험을 먼저 추가한다.
- [x] T005 [US1] `tests/unit/test_forward_edge_autoarm_workflow.py`에 교정 생성·CLI 전달·10%/20% 설명 정렬 정적 시험을 먼저 추가한다.

## 2단계 — 교정·결합·돈 경로 정렬

- [x] T006 [US1] `src/auto_invest/analytics/forward_gate_calibration.py`에 `false_positive_control_passed`와 `detection_power_passed`를 추가한다.
- [x] T007 [US1] `src/auto_invest/portfolio/backtest_anchored.py`가 선택한 원본 방법과 핵심 증거를 보존하게 한다.
- [x] T008 [US1] `src/auto_invest/portfolio/capital_ladder.py`에 경로별 자격과 상향 노출 fail-closed 결정을 구현한다.
- [x] T009 [US1] `src/auto_invest/cli.py`의 `ladder-decide`에 표준 교정 JSON을 추가하고 빈 앵커드 통합을 안전하게 처리한다.
- [x] T010 [US1] `.github/workflows/forward-edge-autoarm.yml`이 같은 커밋의 교정을 생성·전달하게 한다.
- [x] T011 [US1] `src/auto_invest/analytics/money_path.py`의 첫 자본 설명을 공장 10%, 표준·탐색 20%와 맞춘다.

## 3단계 — 독립 후보·자료·누출 방지 시험

- [x] T012 [P] [US2] `tests/unit/test_turn_of_month_equity_factory.py`에 16개 고정 후보·지문·월 경계·비용 시험을 먼저 추가한다.
- [x] T013 [P] [US2] 같은 파일에 날짜 중복·역순·불완전 월 제외·홀드아웃 변조 불변 시험을 먼저 추가한다.
- [x] T014 [US2] `src/auto_invest/analytics/turn_of_month_equity_factory.py`에 후보·자료 묶음·월별 비용 후 수익 변환을 구현한다.

## 4단계 — 역사 관문과 중앙 장부

- [x] T015 [US3] `tests/unit/test_turn_of_month_equity_factory.py`에 PBO·PSR·시대·최근·집중도·낙폭·비용 스트레스·위약 관문 시험을 먼저 추가한다.
- [x] T016 [US3] `src/auto_invest/analytics/turn_of_month_equity_factory.py`에 개발 선택과 홀드아웃 전체 판정을 구현한다.
- [x] T017 [US4] `tests/unit/test_research_family_audit.py`에 레짐·달력 가족 분류와 19가족 회귀 시험을 먼저 추가한다.
- [x] T018 [US4] `src/auto_invest/analytics/research_family_audit.py`에 `regime-`, `calendar-turn-` 가족을 추가한다.
- [x] T019 [US4] 출시 레짐 결과 16개를 `EXPLORATORY_REJECTED` 감사 행으로 복원하고 달력 16개 뒤에 붙여 784행·19가족을 만든다.
- [x] T020 [US4] `tests/unit/test_factory_evidence.py`에 784행·19가족 소비자 독립 재계산과 승격 금지 시험을 추가한다.

## 5단계 — 프로브와 자동화

- [x] T021 [US4] `tests/integration/test_turn_of_month_equity_factory_probe.py`에 파일 입력·JSON/Markdown·안전 필드 시험을 먼저 추가한다.
- [x] T022 [US4] `scripts/turn_of_month_equity_factory_probe.py`를 구현해 공식 URL 또는 고정 파일만 읽게 한다.
- [x] T023 [US4] `tests/integration/test_strategy_factory_workflow.py`에 새 실행·784행·19가족·sidecar 게시·금지 문자열 시험을 추가한다.
- [x] T024 [US4] `.github/workflows/autonomous-strategy-factory.yml`에 레짐 복원과 달력 실행을 연결하고 최종 산출물을 게시한다.
- [x] T025 [US4] `specs/173-independent-turn-of-month-edge/contracts/turn-of-month-result.schema.json`으로 생산 결과를 검증한다.

## 6단계 — 생산 재생과 완료 관문

- [x] T026 [US4] 공식 Kenneth French 자료와 최신 `origin/main` 이전 공장 sidecar를 이용해 생산 프로브를 재생한다.
- [x] T027 [US4] 실제 결과·실패 관문·자료 지문을 `production-result.json`, `production-result.md`, `production-verification.md`에 기록한다.
- [x] T028 전체 관련 테스트와 `uv run ruff check src tests`를 실행한다.
- [x] T029 전체 `uv run pytest`를 실행한다.
- [x] T030 `uv run python scripts/agent_harness_probe.py --strict`와 `uv run python scripts/check_handoff_facts.py`를 실행한다.
- [x] T031 PR 본문을 `scripts/check_pr_quality_gate.py`로 검증하고 커밋·푸시·자동 머지한다.
- [x] T032 `/deploy-status`로 main dry-run worker 배포를 확인하고 `/handoff`로 `HANDOFF.md`를 갱신·병합한다.

## 의존성

- T001~T005가 실패하는 것을 확인한 뒤 T006~T011을 구현한다.
- T012~T013이 실패하는 것을 확인한 뒤 T014를 구현한다.
- T015가 실패하는 것을 확인한 뒤 T016을 구현한다.
- T017과 T020이 실패하는 것을 확인한 뒤 T018~T019를 구현한다.
- T021과 T023이 실패하는 것을 확인한 뒤 T022와 T024를 구현한다.
- T026은 모든 사전등록 코드와 관문이 커밋된 뒤에만 실행한다.
- T027~T032는 구현·생산 재생이 끝난 뒤 순서대로 실행한다.

## 병렬 가능 작업

- T012/T013과 T017은 서로 다른 시험 파일이라 병렬 가능하다.
- T021과 T023은 서로 다른 통합 계약 시험이라 병렬 가능하다.
- 돈 경로 파일과 전략 공장 파일은 겹치지 않지만 한 작업자가 순서대로 검증해 인계 혼동을 막는다.

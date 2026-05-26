---
description: "Task list — spec 012 Tuner L2/L3 → Hardened-Canary Auto-Submission"
---

# Tasks: Tuner L2/L3 → Hardened-Canary Auto-Submission

**Input**: Design documents from `specs/012-tuner-canary-queue/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/tuner-canary.md
**Branch**: `claude/upbeat-bell-Sq9qm` (새 브랜치 만들지 않음 — 이 브랜치에서 진행)

**Tests**: 포함. 헌법 개발 워크플로우 — 판단 계약(judgment-call contracts)·리스크 인접
모듈은 머지 전 자동 테스트 통과 필수. 본 기능은 판단 지점 튜닝 표면을 다루므로 테스트 필수.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 가능(다른 파일, 미완료 의존 없음)
- **[Story]**: US1/US2/US3 (spec.md 사용자 스토리 매핑)

---

## Phase 1: Setup (공유 인프라)

- [X] T001 데이터 타입 스캐폴드 — `src/auto_invest/tuner/models.py` 에 `CanaryCandidate`·`CanaryValidationResult`(frozen dataclass), `ValidationOutcome` 리터럴, `ChangeKind` 에 `"max_tokens_reduce"`, `SkipReason` 에 `"no_replay_data"`·`"already_validated_this_session"` 추가. `TunerRunResult` 에 기본값 `canary_candidates=()`·`canary_validations=()` 필드 추가. `__all__` 갱신. (data-model.md §1~5)
- [X] T002 [P] 판단 튜닝 config 신설 — `config/judgment_tunables.toml` 작성(volatility_assessment/daily_summary/news_screen 의 `max_tokens` = 현재 registry.py 값과 동일). 헤더 주석에 "비커널·폴백·바닥 클램프" 명시. (data-model.md §7)

---

## Phase 2: Foundational (블로킹 선행 — 모든 스토리 공통)

- [X] T003 [P] 감사 이벤트 추가(K4 추가-전용) — `src/auto_invest/persistence/audit.py` EventType 유니온 + `_PAYLOADS` 레지스트리에 `AutoTunedCanaryCandidatePayload`(`AUTO_TUNED_CANARY_CANDIDATE`)·`AutoTunedCanaryValidatedPayload`(`AUTO_TUNED_CANARY_VALIDATED`) **추가만**. 기존 이벤트·마이그레이션 미수정. `promoted: bool` 필드 포함. (data-model.md §6, research R7)
- [X] T004 [P] 판단 튜닝 config 로더 — `src/auto_invest/judgment/registry.py` 가 `config/judgment_tunables.toml` 를 읽어 `max_tokens` 폴백 적용(파일/키 없으면 현재 하드코딩값과 동일 → 동작 무변경). 로드 실패는 조용히 기본값 폴백. (research R3)
- [X] T005 [P] [test] config 폴백 테스트 — `tests/unit/judgment/test_tunables_config.py`: (a) 파일 없음 → 기존 max_tokens, (b) 일부 키만 있음 → 나머지 폴백, (c) 잘못된 값 → 기본값 폴백. 회귀: 기존 registry 조회 동일.

**Checkpoint**: 데이터 타입·감사 이벤트·config 로더 준비. 동작 무변경(폴백). 여기까지 머지해도 회귀 0.

---

## Phase 3: User Story 1 — 실행 가능한 캐너리 후보 기록 (Priority: P1) 🎯 MVP

**Goal**: L2/L3 분류 후보를 구조화된 CanaryCandidate 로 구체화해 튜너 리포트 + 추가-전용
감사 이벤트에 남긴다(멱등, dry-run 무변경). 캐너리 호출은 아직 없음.

**Independent Test**: 모델 라우팅을 L2로 분류시키는 입력으로 apply 실행 → 리포트·감사에
구조화 후보 기록 1건(멱등), dry-run 무변경.

- [X] T006 [US1] max_tokens 노브 계산 — `src/auto_invest/tuner/knobs.py` 에 `compute_max_tokens_reduce(current:int)->int|None`(STEP_FRACTION 만큼 축소, 바닥 클램프, 변화 없으면 None). 원자적 TOML 1줄 교체 `apply_max_tokens`(기존 `apply_threshold` 패턴 재사용). (research R3)
- [X] T007 [US1] 후보 구체화 — `src/auto_invest/tuner/candidate.py` 신설: `build_canary_candidate(c:Classification,*,tunables_path)->CanaryCandidate|None`. L2/L3·비커널·`max_tokens_reduce` 종류만 구체화, 권장 tier/window 채움. 결정론·LLM 미호출. (contracts C1, data-model §2)
- [X] T008 [US1] detect 확장 — `src/auto_invest/tuner/detect.py`: `cost_drift`·`latency_degradation` 드리프트가 `proposal_only` 대신 `max_tokens_reduce` 제안(target=config/judgment_tunables.toml, 가장 비싼/관련 판단 지점). `cache_miss` 는 proposal_only 유지. (research R3)
- [X] T009 [US1] classify 확장 — `src/auto_invest/tuner/classify.py`: `config/judgment_tunables.toml` 대상 변경을 L2로 분류(L2 규칙에 경로 추가). Kernel 교집합은 기존대로 무조건 L4. (research R4, FR-C12-08)
- [X] T010 [US1] runner 배선(후보 기록) — `src/auto_invest/tuner/runner.py`: L2/L3·비커널 분기에서 `build_canary_candidate` 호출 → `canary_candidates` 채움. apply 모드에서 멱등 체크(`_candidate_already_recorded`) 후 `AUTO_TUNED_CANARY_CANDIDATE` 감사 기록. dry-run 은 후보만(감사 없음). 구체 노브 없으면 기존 `canary_entered`+`AUTO_TUNED_L2_CANARY_ENTERED` 유지. (contracts C5)
- [X] T011 [US1] 리포트 후보 섹션 — `src/auto_invest/tuner/report.py`: 리포트 JSON 에 `canary_candidates` 섹션(후보별 target/old→new/권장 tier·window/근거). (contracts C6)
- [X] T012 [P] [US1] [test] 후보 구체화 단위 테스트 — `tests/unit/tuner/test_candidate.py`: 결정론(같은 입력 같은 출력), 클램프(바닥 이하 None), L4/Kernel 후보 제외, max_tokens 외 종류 None.
- [X] T013 [P] [US1] [test] max_tokens 노브 테스트 — `tests/unit/tuner/test_knobs_max_tokens.py`: 축소 계산·클램프·TOML 1줄 원자 교체(주석·다른 키 보존).
- [X] T014 [US1] [test] 후보 기록 통합 테스트 — `tests/integration/tuner/test_canary_candidate_record.py`: detect→classify→candidate→(apply)감사+리포트 1건, 멱등(재실행 중복 없음), dry-run 무변경(감사·config·git 불변).

**Checkpoint**: US1 독립 출시 가능. 죽은 로그 분기가 실행 가능 후보 기록으로 전환(MVP 가치).

---

## Phase 4: User Story 2 — 캐너리 자동 투입·검증 (Priority: P2)

**Goal**: apply 모드에서 후보를 임시 rev(git plumbing, 무푸시·작업트리 무변경)로 만들고
`run_canary` 호출해 검증, 합격/불합격을 감사+리포트에 기록. 데이터 없으면 fail-safe.

**Independent Test**: 리플레이 데이터 있는 환경에서 L2 후보 apply → 캐너리 1회 실행 +
결과(합격/불합격+실패지표) 감사·리포트 기록. 데이터 없으면 skipped + 종료 0.

- [X] T015 [US2] git plumbing 후보 구체화 — `src/auto_invest/tuner/canary_submit.py` 신설: 임시 인덱스(`GIT_INDEX_FILE`)+`hash-object`/`update-index`/`write-tree`/`commit-tree` 로 임시 후보 커밋 SHA 생성. 작업트리·실인덱스·HEAD·브랜치 미변경, ref 미생성, **push 미호출**, 임시 인덱스 `finally` 삭제. (contracts C4, research R1)
- [X] T016 [US2] 캐너리 투입 — `canary_submit.py`: `submit_to_canary(candidate,*,repo_root,audit_conn,session_date,history_root,run_canary_fn=run_canary)->CanaryValidationResult`. baseline_rev=HEAD 명시(R2). `replay_inputs` 는 캐너리 CLI 패턴으로 구성. (contracts C2·C3)
- [X] T017 [US2] fail-safe(데이터 없음) — `canary_submit.py`: `latest_dataset_dir(history_root) is None` → `CanaryValidationResult(skipped, no_replay_data)`, 캐너리 미호출, 종료 0. (research R5, FR-C12-09)
- [X] T018 [US2] 오류 격리 — `canary_submit.py`: `run_canary_fn` 예외/`EXIT_INTERNAL`/`in_progress` → `internal_error` 결과, 예외 미전파. (research R6, FR-C12-10)
- [X] T019 [US2] runner 배선(검증) — `runner.py`: 후보 기록 후 apply 모드에서 `submit_to_canary` 호출 → `canary_validations` 채움 + `AUTO_TUNED_CANARY_VALIDATED`(promoted=False) 감사. 멱등(`already_validated_this_session`). 후보별 독립 처리(한 후보 오류가 루프 중단 안 함). (contracts C5)
- [X] T020 [US2] 리포트 검증 섹션 — `report.py`: `canary_validations` 섹션(outcome/canary_run_id/failing_metrics/skip_reason/promoted). (contracts C6)
- [X] T021 [P] [US2] [test] git plumbing 테스트 — `tests/unit/tuner/test_canary_submit.py`: 임시 git repo 에서 후보 rev 생성 후 (a) 작업트리 `git status --porcelain` 불변, (b) origin ref 미생성, (c) candidate_rev 트리에 변경 반영, (d) 임시 인덱스 정리.
- [X] T022 [P] [US2] [test] fail-safe·오류격리 테스트 — `tests/unit/tuner/test_canary_submit_failsafe.py`: 데이터 없음→skipped, run_canary 더블 예외→internal_error(미전파), 더블 failed→failing_metrics 채움.
- [X] T023 [US2] [test] 파이프라인 통합 테스트 — `tests/integration/tuner/test_canary_pipeline.py`: detect→classify→candidate→submit(stub run_canary)→audit(CANDIDATE+VALIDATED)+report. passed/failed/skipped 분기 각각. 멱등 재실행.

**Checkpoint**: US2 출시 가능. 후보가 실제 캐너리 검증을 받고 결과가 기록됨.

---

## Phase 5: User Story 3 — 검증은 승격이 아니다 (Priority: P1, 안전 게이트)

**Goal**: 합격해도 라이브 자동 승격 0건. 작업트리·원격·라이브 설정 무변경을 불변으로
고정. CLI·리포트에 "라이브 미승격(운영자 게이트)" 명시.

**Independent Test**: 합격 후보가 있어도 배포/승격 이벤트 0건, 후보 대상 파일 작업트리
불변, origin 새 ref 0건.

- [X] T024 [US3] 승격 금지 불변 — `runner.py`/`canary_submit.py`: 합격 경로가 `DEPLOY_*`·`STRATEGY_PROMOTED` 를 절대 발생시키지 않음 확인, `CanaryValidationResult.promoted` 항상 False 보장(코드 경로상 True 설정 불가). (FR-C12-07, research R8)
- [X] T025 [US3] CLI·리포트 승격 표식 — `report.py` + `src/auto_invest/cli.py` 의 `tune` 출력: 합격 후보 옆 `"promotion": "operator-gated (spec 006); NOT auto-promoted"` + 사람용 요약 줄("캐너리 후보 N / 합격 M / 불합격 K / 건너뜀 S — 라이브 미승격(운영자 게이트)"). (contracts C6)
- [X] T026 [US3] [test] 안전 불변 통합 테스트 — `tests/integration/tuner/test_canary_no_promote.py`: 합격(stub) 후 (a) `DEPLOY_*`·`STRATEGY_PROMOTED` 감사 0건, (b) 후보 대상 파일 작업트리 불변, (c) origin ref 불변, (d) 모든 VALIDATED 이벤트 promoted=False. (SC-C12-03·04)
- [X] T027 [P] [US3] [test] 결정론·dry-run 테스트 — `tests/integration/tuner/test_canary_determinism.py`: 같은 입력 dry-run 2회 동일 후보집합 + config·감사·git 변경 0건. (SC-C12-05)

**Checkpoint**: 안전 경계 테스트로 고정. 자동 승격 0건 증명.

---

## Phase 6: Polish & Cross-Cutting

- [X] T028 [P] 전체 스위트·린트 — `uv run pytest`(전부 통과, fail 0) + `uv run ruff check src tests`("All checks passed!"). 회귀 0(기존 902 + 신규). (SC-C12-07)
- [X] T029 [P] quickstart 검증 — `specs/012-tuner-canary-queue/quickstart.md` 명령들이 실제 동작하는지 확인(감사 조회 쿼리·테스트 경로).
- [X] T030 HANDOFF 갱신 — `/handoff` 로 HANDOFF.md 요약표(마지막 main 커밋·테스트 수·출시 스펙·열린 PR) + 마일스톤 절 갱신. 스펙 012 출시 반영.

---

## Dependencies & Execution Order

- **Phase 1 (Setup)** → **Phase 2 (Foundational)** → **US1** → **US2** → **US3** → **Polish**.
- US1 은 MVP(독립 출시 가능). US2 는 US1 의 후보 구체화에 의존. US3 의 불변 테스트는 US2 의 캐너리 투입 경로가 있어야 의미. 따라서 우선순위(P1 US1 → P2 US2 → P1-safety US3)는 의존성 순서와 일치.
- T024(승격 금지)는 US2 코드 경로 위에 얹는 안전 확인 — US2 완료 후.

### 병렬 기회

- T002·T003·T004·T005 (Foundational, 다른 파일) 병렬 가능.
- T012·T013 (US1 단위 테스트) 병렬. T021·T022 (US2 단위 테스트) 병렬. T027 (US3) 병렬.
- T028·T029 (Polish) 병렬.

## Implementation Strategy

- **MVP = Phase 1+2+US1** (T001~T014): 죽은 L2/L3 로그 분기 → 실행 가능 후보 기록. 단독 머지 가치.
- 이후 US2(캐너리 투입) → US3(안전 불변) 순차. 각 체크포인트에서 테스트+린트 green 이면 커밋/푸시(자동 워크플로우), 단계별 PR 본문 갱신.
- 헌법 IX.A: K4 추가-전용 터치 커밋(T003) 해시를 PR 본문에 forensic callout.

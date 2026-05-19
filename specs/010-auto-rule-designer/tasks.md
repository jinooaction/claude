---

description: "Task list for spec 010 자동 룰 설계자 (Autonomous Rule Designer)"
---

# Tasks: 자동 룰 설계자

**Input**: Design documents from `specs/010-auto-rule-designer/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all committed at ed77bb7)
**Tests**: INCLUDED. SC-002 (Claude 비용 한도), SC-003 (정적 검증 100%), SC-007 (mutex 거부), SC-008 (KIS 주문 0건)은 안전 invariant라 테스트 강제 필요.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일·완료된 의존성에 대해 병렬 가능
- **[Story]**: spec.md의 user story 매핑 (US1, US2, US3)
- 모든 경로는 repo-relative

## Path Conventions

기존 `src/auto_invest/` 단일 패키지. 새 코드는 `src/auto_invest/design/`로 격리. K3 변경은 `telemetry/meter.py` 1개 파일. K4 변경은 `persistence/audit.py` 1개 파일. CLI 진입점은 기존 `cli.py`에 추가.

## K-경로 변경 표

| Kernel | 변경? | 변경 파일 |
|--------|------|----------|
| K1 position sizing | ❌ 무수정 | — |
| K2 whitelist | ❌ 무수정 | — |
| K3 LLM judgment points | ❌ 코드 무수정 | (decision_class 문자열은 free-form, 호출 사이트에서만 `"rule_design"` 명시) |
| **K4 append-only audit** | ✅ additive | `persistence/audit.py` (4 페이로드) |
| K5 secret isolation | ❌ 무수정 | — |
| K6 market hours guard | ❌ 무수정 | — |
| K_meta | ❌ 무수정 | — |

K4 변경 1건만 — IX.D 자율 머지 채널. PR 본문에 commit hash 명시 의무. K3는 contract 확장이지만 K3 파일에는 영향 없음 (meter.py가 decision_class를 자유 문자열로 받음).

---

## Phase 1: Setup

**Purpose**: 디렉토리 + 의존성 확인. 위험 없음.

- [ ] T001 Create `src/auto_invest/design/` with empty `__init__.py` (서브모듈은 후속 phase에서 추가)
- [ ] T002 Verify `pyproject.toml`에 anthropic SDK가 이미 들어 있는지 확인. `uv lock` clean.

**Checkpoint**: skeleton 준비. 동작 변경 없음.

---

## Phase 2: Foundational (K3 + K4 additive)

**Purpose**: K3 cost-band + K4 페이로드 4종 추가 — 모든 후속 user story의 전제.

**⚠️ K3 + K4 NOTE**: T003 + T004 + T005가 본 스펙의 두 Kernel 터치. 하나의 commit으로 묶는다.

제안 commit subject:
`feat(010): K3 + K4 additive — rule_design cost-band + 4 audit payloads`

PR 본문에 이 commit hash 명시 (IX.D 자율 머지 채널 audit 의무).

- [ ] T003 Add `rule_design` cost-band in `src/auto_invest/telemetry/meter.py` per contracts/claude-prompt.md § "비용·토큰 한도". K3 변경 — additive (기존 cost-band 무수정). (K3 — T004·T005와 동일 commit)
- [ ] T004 Add 4 audit payloads in `src/auto_invest/persistence/audit.py`: `RuleDesignRequestedPayload`, `RuleDesignCompletedPayload`, `RuleDesignRejectedPayload`, `RuleDesignDeployedPayload` per contracts/design-audit-events.md. EventType Literal에 4종 추가. AnyPayload Union 확장. (K4 — T003·T005와 동일 commit)
- [ ] T005 [P] Unit test `tests/unit/test_design_audit_payloads.py` — 4개 페이로드 pydantic validation; event_type 문자열 일관; cost_usd ≤ 1.0 강제; 기존 28종 페이로드 무수정 baseline 비교 (spec 009 test_k4_touch_is_purely_additive 패턴 확장).

**Checkpoint**: K3 + K4 commit lands. Phase 3 시작 가능.

---

## Phase 3: User Story 1 — 한 줄 의도로 룰 자동 생성 + 검증 (P1, MVP)

**Goal**: 운영자가 `auto-invest design --intent "..."` 한 번 실행하면 시스템이 룰을 자동 생성하고 정적 검증·paper-run 1일분으로 검증한 결과를 한글 요약으로 반환.

**Independent Test**: Claude API를 mock으로 monkeypatch하고 design CLI를 호출 → audit_log에 RULE_DESIGN_COMPLETED 또는 REJECTED row 1개 + 운영자가 stdout에서 한글 보고 확인 가능.

**제안 commit 시리즈**:
- `feat(010): Claude prompt + client + static validator` (T006~T012)
- `feat(010): design CLI + mutex + paper-run trigger` (T013~T020)

### Tests for US1 (TDD)

- [ ] T006 [P] [US1] Unit test `tests/unit/test_design_mutex.py` — spec 009 mutex 패턴 모방. clean state 허용, stale `RULE_DESIGN_REQUESTED` 거부, exit_code 70, RULE_DESIGN_REJECTED 기록.
- [ ] T007 [P] [US1] Unit test `tests/unit/test_design_validator.py` — 정적 검증 케이스: 정상 TOML 통과, whitelist 외 종목 catch, cap 음수 catch, 자본 부족 catch, 옵션·해외 종목 거부.
- [ ] T008 [P] [US1] Unit test `tests/unit/test_design_prompt.py` — system prompt + user prompt 조립이 contracts/claude-prompt.md 명세와 일치; retry_context_block이 재시도 시에만 포함; INTERPRETATION 주석 파싱 정확.
- [ ] T009 [P] [US1] Unit test `tests/unit/test_design_claude_client.py` — anthropic SDK monkeypatch, Claude 응답을 TOML로 정확히 받아옴, token usage가 spec 002 meter에 기록, cost_usd 계산.

### Implementation for US1

- [ ] T010 [US1] Implement `src/auto_invest/design/mutex.py` — spec 009 `paper/mutex.py`의 구조 모방. `check_and_acquire(conn) -> MutexResult`. audit_log에서 가장 최근 RULE_DESIGN_REQUESTED가 짝맞춤 COMPLETED/REJECTED 없이 떠 있는지 확인.
- [ ] T011 [US1] Implement `src/auto_invest/design/prompt.py` — `build_system_prompt()` + `build_user_prompt(intent, balance, holdings, retry_context=None)` 두 함수. contracts/claude-prompt.md 명세 그대로.
- [ ] T012 [US1] Implement `src/auto_invest/design/validator.py` — `validate_generated_rules(toml_text, intent_capital, kis_balance) -> ValidationResult`. spec 001의 `LoadedConfig` pydantic + 추가 5가지 검증 (R-D3).
- [ ] T013 [US1] Implement `src/auto_invest/design/claude_client.py` — anthropic SDK thin wrapper. `call_rule_design(system_prompt, user_prompt) -> ClaudeDesignResponse`. spec 002 token usage meter 사용. R-D6 cost-band 한도 강제.
- [ ] T014 [US1] Implement `src/auto_invest/design/verifier.py` — `verify_rules(toml_text, ...)` 함수. (a) 백테스트 stub: `try: from auto_invest.backtest.runner import run_backtest` 가드 (R-D11). (b) paper-run 1일분 트리거: subprocess로 `auto-invest paper-run` 띄움 + audit_log polling으로 1일치 결과 수집.
- [ ] T015 [US1] Implement `src/auto_invest/design/state.py` — design session state 머신. audit_log 기반으로 재시도 카운트, paper-run session id 추적, --check 모드 진행 상태 조회.
- [ ] T016 [US1] Implement `src/auto_invest/cli.py::design` 서브커맨드 — typer @app.command(name="design"). 옵션: --intent, --db, --env-file, --base-url, --halt-path, --prices, --check. mutex → KIS 잔고 조회 → Claude 호출 → 정적 검증 → paper-run 트리거 → 검증 결과 한글 보고. 자동 재설계 루프 최대 3회.
- [ ] T017 [US1] KIS 잔고 조회 helper — `src/auto_invest/broker/overseas.py`에 `get_account_balance()` 같은 함수 있으면 reuse, 없으면 신설. design CLI에서 한 번 호출. spec 001 모듈 reuse 원칙.

### Integration tests for US1

- [ ] T018 [P] [US1] Integration test `tests/integration/test_design_claude_mock.py::test_us1_end_to_end_with_mock` — Claude mock + paper-run mock으로 design CLI 1회 실행, RULE_DESIGN_COMPLETED audit row 1개 + 한글 보고 stdout 확인.
- [ ] T019 [P] [US1] Integration test `tests/integration/test_design_cli.py::test_us1_mutex_rejection` (SC-007) — RULE_DESIGN_REQUESTED row 미리 INSERT 후 design 시작, exit 70 + RULE_DESIGN_REJECTED row 검증.
- [ ] T020 [P] [US1] Integration test `tests/integration/test_design_claude_mock.py::test_us1_no_kis_orders` (SC-008) — `ResilientClient.request`를 raise하도록 monkeypatch + Claude mock으로 design CLI 1회 실행, broker.request 호출 카운트 = 0 (KIS quote 호출은 별도 mock).

**Checkpoint**: design CLI 동작. SC-002·SC-003·SC-007·SC-008 검증.

---

## Phase 4: User Story 2 — 운영자 OK 한 줄로 라이브 자동 시작 (P2)

**Goal**: 검증 통과 보고 후 운영자가 OK/y/예/yes 한 줄 답하면 5초 이내 라이브 worker 시작.

**Independent Test**: design CLI가 검증 통과 단계까지 도달하도록 mock 준비 후, `typer.testing.CliRunner` input="OK\n"으로 호출 → 새 worker subprocess 시작 + RULE_DESIGN_DEPLOYED audit row 1개.

**제안 commit**:
- `feat(010): operator OK interactive + auto-deploy` (T021~T026)

### Tests for US2

- [ ] T021 [P] [US2] Unit test `tests/unit/test_design_deploy.py::test_operator_ok_accepts` — typer.prompt mock으로 "OK", "y", "예", "yes" 모두 OK로 인식.
- [ ] T022 [P] [US2] Unit test `tests/unit/test_design_deploy.py::test_operator_ok_timeout` — 60초 안에 응답 없으면 거부 처리 (R-D4).
- [ ] T023 [P] [US2] Unit test `tests/unit/test_design_deploy.py::test_operator_ok_rejection` — "no", "취소" 또는 무응답 시 RULE_DESIGN_REJECTED(reason="operator_declined") 기록.

### Implementation for US2

- [ ] T024 [US2] Implement `src/auto_invest/design/deploy.py` — `prompt_operator_ok(timeout=60) -> bool` + `start_live_worker(rules_toml, capital_usd) -> int` (subprocess로 `auto-invest run` 띄움 + RULE_DESIGN_DEPLOYED audit). VIII.A 시장 시간 가드 의존 — spec 006 deploy guard가 막으면 한글 보고 후 거부 처리.
- [ ] T025 [US2] cli.py design 서브커맨드에 OK prompt 통합 — 검증 통과 후 deploy.prompt_operator_ok 호출 → True면 deploy.start_live_worker → False면 RULE_DESIGN_REJECTED.

### Integration tests for US2

- [ ] T026 [P] [US2] Integration test `tests/integration/test_design_cli.py::test_us2_ok_starts_live` (SC-005) — Claude mock + paper-run mock + typer input "OK\n" → 새 worker subprocess가 5초 이내 시작 + RULE_DESIGN_DEPLOYED audit row 1개 + WORKER_STARTED row 1개.

**Checkpoint**: design 완전 사이클(의도 → 룰 → 검증 → OK → 라이브) 동작. SC-005 검증.

---

## Phase 5: User Story 3 — Claude 해석 매개변수 audit (P2)

**Goal**: Claude가 사용한 정량 매개변수가 audit_log에 명시 기록되어 운영자가 사후 재현 가능.

**Independent Test**: 같은 의도 + 같은 mock 응답으로 design 2회 호출 → 두 RULE_DESIGN_COMPLETED row의 `interpretation` 필드가 정확히 동일.

**제안 commit**:
- `feat(010): explicit interpretation tracking in audit` (T027~T029) — 대부분 Phase 3 코드에 이미 포함, Phase 5는 명시 검증 테스트.

### Tests for US3

- [ ] T027 [P] [US3] Unit test `tests/unit/test_design_prompt.py::test_interpretation_parsing` — Claude 응답의 `# INTERPRETATION: {...}` 주석이 정확히 JSON 파싱되어 `interpretation` 필드에 들어감.
- [ ] T028 [P] [US3] Integration test `tests/integration/test_design_claude_mock.py::test_us3_interpretation_reproducible` (SC-004) — 같은 의도 + 같은 KIS 잔고 + 같은 Claude 응답으로 design 2회 호출 → 두 audit row의 `interpretation` 동일.
- [ ] T029 [P] [US3] Integration test `tests/integration/test_design_claude_mock.py::test_us3_tokens_recorded` — RULE_DESIGN_COMPLETED payload에 `tokens_input`, `tokens_output`, `cost_usd`, `model_id`가 spec 002 meter 결과와 일치.

**Checkpoint**: SC-004 검증.

---

## Phase 6: Polish & Cross-Cutting

**Purpose**: 일주일 paper-run 분리 + --check 모드 + 자동 재설계 루프 + 문서 정합성 + PR 본문.

**제안 commit**:
- `feat(010): --check mode + week-long paper-run separation` (T030~T032)
- `chore(010): integration tests + docs polish` (T033~T035)

- [ ] T030 [P] Integration test `tests/integration/test_design_cli.py::test_polish_check_mode` — `auto-invest design --check`로 진행 중 paper-run 상태 조회 (paper-report 1일분).
- [ ] T031 [P] Integration test `tests/integration/test_design_cli.py::test_polish_retry_loop_max_3` (SC-006) — Claude mock이 1·2회차 잘못된 TOML, 3회차 정상 TOML 반환. RULE_DESIGN_REJECTED 2건(parse_error 1, validator_violation 1) + COMPLETED 1건 audit 확인.
- [ ] T032 [P] Integration test `tests/integration/test_design_cli.py::test_polish_max_retries_exhausted` — Claude mock이 3회 모두 실패. exit 1 + RULE_DESIGN_REJECTED(reason="max_retries") audit row.
- [ ] T033 [P] Integration test `tests/integration/test_design_cli.py::test_polish_claude_cost_limit` (SC-002) — Claude mock이 비용 $0.20 초과 응답. design CLI가 cost-band 위반으로 거부 + RULE_DESIGN_REJECTED.
- [ ] T034 [P] Quickstart docs verification — `quickstart.md`의 명령·exit code·출력 형식이 실제 구현과 일치 검수.
- [ ] T035 [P] Run `uv run ruff check src tests` + `uv run pytest` — all green. PR 본문 갱신 (K3+K4 commit hash 명시, IX.D 자율 머지 채널, SC 매핑 표).

**Checkpoint**: SC-001~SC-008 8개 검증 (SC-001은 24시간 안 한글 보고로 자동 검증; SC-002 비용 한도; SC-003 정적 검증 100% 통과; SC-004 해석 재현; SC-005 5초 라이브 시작; SC-006 재설계 최대 3회; SC-007 mutex 거부; SC-008 KIS 0건). PR 본문 완료. 자동 머지 조건 충족.

---

## Dependencies

```
Phase 1 (T001~T002) → Phase 2 (T003~T005, K3+K4 단일 commit)
                              ↓
                    Phase 3 US1 (T006~T020)
                              ↓
                ┌─────────────┴─────────────┐
                ↓                           ↓
        Phase 4 US2 (T021~T026)    Phase 5 US3 (T027~T029)
                ↓                           ↓
                └─────────────┬─────────────┘
                              ↓
                    Phase 6 Polish (T030~T035)
```

**Story 독립성**:
- US1 만으로 MVP (룰 자동 생성 + 검증 결과 보고. 라이브 시작은 운영자가 수동으로 `auto-invest run`으로 실행).
- US2 (OK 인터랙티브)는 US1 완료 후. US2 만으로는 의미 없음 — US1의 검증 결과가 있어야 OK 단계 도달.
- US3 (해석 기록)는 US1과 거의 동시 가능 (US1 코드에 이미 포함됨, US3 Phase는 명시 검증).

## Parallel Execution Examples

**Phase 3 (US1) 안에서 동시 가능**: T006·T007·T008·T009 (4개 단위 테스트, 서로 다른 파일).

**Phase 6 안에서 동시 가능**: T030·T031·T032·T033 (4개 통합 테스트, 모두 같은 파일이지만 다른 함수 — 한 commit에 묶음).

## Implementation Strategy

**MVP**: Phase 1 + 2 + 3 (US1). 운영자가 `auto-invest design --intent "..."` 1회로 룰 자동 생성 + 한글 보고까지. 라이브 시작은 별도 명령(`auto-invest run --capital ...`).

**점진 출하**:
1. **MVP (Phase 1~3)**: design CLI 동작 → 머지 → 운영자 검증.
2. **OK 자동화 (Phase 4)**: 한 줄 OK로 라이브 → 머지.
3. **사후 추적 (Phase 5)**: interpretation 명시 기록 → 머지.
4. **Polish (Phase 6)**: --check, 재시도 루프, 비용 한도, 문서 → 머지 → spec 010 완료.

한 PR에 전체를 묶거나, MVP 후 점진 분리 PR 모두 가능. 본 스펙은 한 PR에 묶는 방향을 기본으로 한다 (운영자 선호 = 손 적게).

---

## Format validation

전체 35개 태스크가 다음 포맷 만족:
- ✅ `- [ ]` 체크박스
- ✅ T001~T035 순차 ID
- ✅ Phase 3·4·5는 [US1]/[US2]/[US3] 라벨
- ✅ 병렬 가능 태스크는 [P] 마커
- ✅ 모든 태스크에 파일 경로 또는 명확한 산출물
- ✅ Setup·Foundational·Polish는 [Story] 라벨 없음

---

description: "Task list for spec 009 Paper-Trading Daemon implementation"
---

# Tasks: Paper-Trading Daemon

**Input**: Design documents from `specs/009-paper-trading-daemon/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all committed at e60b59b)
**Tests**: INCLUDED. SC-001 (KIS API 호출 0건), SC-004 (게이트 동등성), SC-006 (live row 무수정), SC-007 (mutex 거부), SC-008 (cap 동등성)은 안전 invariant라 테스트 강제 필요.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with adjacent tasks (different files, no incomplete-task dependency)
- **[Story]**: Maps to user story from spec.md (US1, US2, US3)
- All paths in tasks are repo-relative
- TDD 순서 — 가능한 경우 단위 테스트가 구현 앞에 위치

## Path Conventions

Single-package layout under `src/auto_invest/`. Tests under `tests/`. 새 코드는 대부분 신규 `src/auto_invest/paper/` 패키지로 격리. K4 추가 변경은 `src/auto_invest/persistence/audit.py` 1개 파일에만. 단일 차단 지점은 `src/auto_invest/execution/order_router.py` 1줄. Worker는 `src/auto_invest/worker/loop.py`에 paper_mode 플래그 추가.

## K-경로 변경 표 (변경 여부 한눈에)

| Kernel 영역 | 본 스펙에서 변경? | 변경 파일 / 라인 |
|------------|-----------------|------------------|
| K1 position sizing | ❌ 무수정 | — |
| K2 whitelist | ❌ 무수정 | — |
| K3 LLM judgment points | ❌ 무수정 | — |
| K4 append-only audit | ✅ additive | `persistence/audit.py` (4 페이로드 추가) |
| K5 secret isolation | ❌ 무수정 | — |
| K6 market hours guard | ❌ 무수정 | — |
| K_meta | ❌ 무수정 | — |

K4 변경은 IX.D 자율 머지 채널 (constitution v3.0.0). PR 본문에 그 단일 commit hash를 명시.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 디렉토리 skeleton + 의존성 확인. 위험 없음.

- [ ] T001 Create `src/auto_invest/paper/` with empty `__init__.py` exposing public API (Phase 3+ 채울 예정)
- [ ] T002 Verify `pyproject.toml` 기존 의존성으로 충분 (typer, httpx, pydantic, pytest 모두 보유); `uv lock` clean 확인. 본 스펙은 신규 third-party 의존성 0.

**Checkpoint**: 디렉토리 skeleton 준비. 동작 변경 없음.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: K4 페이로드 4종 추가 — 모든 후속 user story가 이걸 import한다.

**⚠️ CRITICAL**: User story 작업은 Phase 2 완료 후에만 시작.

**⚠️ K4 NOTE**: T003 + T004 + T005가 본 스펙의 유일한 Kernel 터치. 셋을 **하나의 commit으로** 묶는다. 제안 commit subject:
`feat(009): K4 additive — paper-trading audit payloads (PaperRunStarted/Stopped/OrderPaperFilled/PaperRunRejected)`

PR 본문에 이 commit hash 명시 (IX.D 자율 머지 채널 audit 의무).

- [ ] T003 Add `PaperRunStartedPayload`, `PaperRunStoppedPayload`, `OrderPaperFilledPayload`, `PaperRunRejectedPayload` pydantic models in `src/auto_invest/persistence/audit.py` per `contracts/paper-audit-events.md` (K4 — T004·T005와 동일 commit)
- [ ] T004 Extend the `AuditPayload` Union in `src/auto_invest/persistence/audit.py` to include the 4 new payloads (K4 — T003·T005와 동일 commit). 기존 24종 무수정 확인.
- [ ] T005 [P] Unit test `tests/test_paper_audit_payloads.py` — 4종 페이로드 pydantic validation; event_type 문자열 일관(`paper_run_started` 등); 기존 24종 클래스 set 무변경 (baseline 캡처 비교).

**Checkpoint**: K4 commit lands (단일 forensic-audit 표면). Phase 3 시작 가능.

---

## Phase 3: User Story 1 — paper-run 데몬으로 실시간 시장 관찰 (Priority: P1) 🎯 MVP

**Goal**: 운영자가 `auto-invest paper-run` 한 줄로 데몬을 띄우면 실시간 KIS quote를 받아 룰을 평가하고, 단일 차단 지점에서 시뮬 체결로 분기해 KIS 주문 API에는 단 한 번도 접근하지 않으며, SIGTERM에 깨끗하게 종료한다. live·paper 상호 배타도 여기서 보장.

**Independent Test**: `tests/test_paper_integration.py`에서 mocked broker(post가 raise하도록 monkeypatch) 환경으로 paper-run을 100 tick 돌리고 KIS 주문 API 호출 카운트 0 + audit_log에 paper 이벤트 기록 확인.

**제안 commit 시리즈**:
- `feat(009): K4 additive — paper-trading audit payloads` (Phase 2 commit)
- `feat(009): paper-run mutex + single-bypass-point in order_router` (T006~T011)
- `feat(009): paper-run CLI entrypoint + Worker paper_mode plumbing` (T012~T015)

### Tests for User Story 1 (TDD order — 테스트가 구현 앞)

- [ ] T006 [P] [US1] Unit test `tests/test_paper_mutex.py` — audit_log에 stop 짝 없는 `worker_started` 또는 `paper_run_started` row를 미리 INSERT, mutex check 호출 시 충돌 감지 + `PaperRunRejectedPayload(reason="mutex_conflict")` 기록 + exit 70. clean state에서는 통과 (data-model.md state transitions).
- [ ] T007 [P] [US1] Unit test `tests/test_paper_order_router.py` — `OrderRouter`에 paper_mode=True 주입 후 submit_order 호출. broker.post를 raise하도록 monkeypatch. 100회 호출 동안 raise 발생 0건, `OrderPaperFilledPayload` 100건 audit_log 기록 (단일 차단 지점 회귀 가드 — SC-001 핵심).
- [ ] T008 [P] [US1] Unit test `tests/test_paper_order_router.py::test_gates_still_block` — paper_mode=True에서도 whitelist·cap·halt 게이트가 live와 동일하게 차단하는지 (각 게이트별 1 case) — SC-004 단위 검증.
- [ ] T009 [P] [US1] Unit test `tests/test_paper_worker.py` — `WorkerSettings(paper_mode=True)`의 `Worker.record_start`가 `PaperRunStartedPayload` 기록 + `record_stop`이 `PaperRunStoppedPayload(reason=...)` 기록.

### Implementation for User Story 1

- [ ] T010 [US1] Implement `src/auto_invest/paper/mutex.py` — `check_and_acquire(conn) -> MutexResult` 함수. audit_log SELECT 1쿼리로 충돌 감지, 충돌 시 `PaperRunRejectedPayload` audit append + exit code 70 hint 리턴. data-model.md "PaperRunSession state transitions" 알고리즘 따름.
- [ ] T011 [US1] Modify `src/auto_invest/execution/order_router.py` — `OrderRouter.__init__`에 `paper_mode: bool = False` 추가, `submit_order` 안의 broker 호출 직전 (현재 line 347 `place_order(self.broker, ...)`)에 `if self.paper_mode:` 분기 1개 삽입. 분기 안에서 `OrderPaperFilledPayload` 기록 + OrderOutcome(state="PAPER_FILLED") 리턴. K1 게이트 코드 무수정 — 분기는 게이트 체인 뒤·broker 호출 직전 1줄.
- [ ] T012 [US1] Modify `src/auto_invest/worker/loop.py` — `WorkerSettings`에 `paper_mode: bool = False` 추가, `Worker.__init__`에서 OrderRouter 생성 시 paper_mode 전달, `record_start`/`record_stop`이 paper_mode면 paper 페이로드 사용. K6 (schedule.py) 무수정 확인.
- [ ] T013 [US1] Implement `src/auto_invest/cli.py::paper_run` 서브커맨드 (typer @app.command()). 기존 `run` 명령 구조를 기반으로 하되: (a) `--dry-run` 옵션 없음 (b) 시작 직전 `paper.mutex.check_and_acquire` 호출 (c) Worker 생성 시 paper_mode=True 전달. contracts/paper-run-cli.md 명세 따름.
- [ ] T014 [US1] Add `OrderRequest`/quote-snapshot 확장: paper 분기에서 ask·bid·last를 골라야 하므로 `worker.tick`이 OrderRouter에 quote를 넘길 때 ask·bid·last 3종을 다 들고 가게 한다. data-model.md "external systems" 표의 "Worker → OrderRouter quote payload" 변경. live 모드 동작 영향 없음 (필드만 늘어남).
- [ ] T015 [P] [US1] Integration test `tests/test_paper_integration.py::test_us1_daemon_no_kis_orders` (SC-001) — 30분 모의 시간 동안 paper-run을 띄우고(빠른 tick 간격으로 축약), broker.post 호출 카운트 0 검증.
- [ ] T016 [P] [US1] Integration test `tests/test_paper_integration.py::test_us1_mutex_rejection` (SC-007) — live `worker_started` 미리 INSERT 후 paper-run 시작, exit code 70 + `PaperRunRejected` audit row 검증.

**Checkpoint**: paper-run 데몬이 동작. SC-001/SC-004/SC-007 단위·통합 테스트 통과. paper-report 없어도 audit_log를 직접 쿼리해서 결과 확인 가능 = MVP.

---

## Phase 4: User Story 2 — 일주일 결과를 한눈에 보는 리포트 (Priority: P2)

**Goal**: 운영자가 `auto-invest paper-report --since <ts>` 한 줄로 룰별 시그널·시뮬 체결·차단 분포·외부 API 오류·튜닝 피드백·가상 포지션을 200ms 안에 받는다.

**Independent Test**: 합성 audit_log(룰 10개, paper 이벤트 10만 row)를 미리 깐 뒤 paper-report 실행. 출력에 룰별 row가 모두 있고 200ms 이내 완료.

**제안 commit 시리즈**:
- `feat(009): paper-report CLI + virtual positions derived view` (T017~T023)

### Tests for User Story 2 (TDD)

- [ ] T017 [P] [US2] Unit test `tests/test_paper_virtual_positions.py` — `recompute_virtual_positions`의 BUY 평균단가·SELL 실현 PnL 계산을 합성 fill 시퀀스로 검증. 음수 qty 발생 시 anomaly 표시.
- [ ] T018 [P] [US2] Unit test `tests/test_paper_report.py::test_aggregation_correctness` — 합성 audit_log(룰별 known 분포)로 paper-report 6 쿼리 결과 검증.
- [ ] T019 [P] [US2] Unit test `tests/test_paper_report.py::test_empty_log` — audit_log 비어 있어도 exit 0 + 빈 표 출력 (edge case).
- [ ] T020 [P] [US2] Unit test `tests/test_paper_report.py::test_excludes_live_events` — live `fill` row 미리 INSERT 후 paper-report 실행, 결과에 미포함 (FR-011).

### Implementation for User Story 2

- [ ] T021 [US2] Implement `src/auto_invest/paper/virtual_positions.py` — `recompute_virtual_positions(conn, paper_session_id=None, since=None, until=None) -> dict[str, VirtualPositionRow]`. 순수 함수, 캐시 없음 (research.md R-P3).
- [ ] T022 [US2] Implement `src/auto_invest/paper/report.py` — `build_paper_report(conn, since, until) -> PaperReport`. 6개 SELECT + virtual_positions.recompute. PRAGMA query_only=ON 사용. text·json 두 출력 포맷 (contracts/paper-report-cli.md).
- [ ] T023 [US2] Implement `src/auto_invest/cli.py::paper_report` 서브커맨드. `--since` 필수, `--until` 선택, `--format text|json` 선택, `--db` 선택. contracts/paper-report-cli.md 명세 따름.
- [ ] T024 [P] [US2] Integration test `tests/test_paper_integration.py::test_us2_report_performance` (SC-003) — 10만 paper 이벤트 합성 후 paper-report 200ms 이내 검증.
- [ ] T025 [P] [US2] Integration test `tests/test_paper_integration.py::test_us2_tuning_feedback` (SC-005) — 일부 룰은 fire 안 됨, 일부는 hot. paper-report 출력의 "Rules that never fired", "Hottest rules" 섹션 검증.

**Checkpoint**: paper-run + paper-report 둘 다 동작. 운영자가 일주일 관찰 사이클을 처음부터 끝까지 수행 가능.

---

## Phase 5: User Story 3 — paper-run 안전 invariant 동등성 (Priority: P2)

**Goal**: paper-run의 안전 게이트 동작이 live와 100% 동일하다는 신뢰. 같은 시그널·같은 상태에서 paper와 live는 같은 deny reason / 같은 fill 결정.

**Independent Test**: 동일 룰셋·동일 capital·동일 positions 상태를 두 번 준비, 한 번은 paper-mode·한 번은 live-mode로 OrderRouter.submit_order 호출. 결과 OrderOutcome의 state·gate·reason이 일치.

**제안 commit 시리즈**:
- `test(009): paper/live gate-equivalence integration suite` (T026~T028)

### Tests for User Story 3 (이 phase는 거의 다 테스트)

- [ ] T026 [P] [US3] Integration test `tests/test_paper_integration.py::test_us3_whitelist_equivalence` — whitelist 위반 시그널을 paper-mode·live-mode 양쪽에서 평가, 동일한 `OrderRejectedByGate.gate="whitelist"` 결과.
- [ ] T027 [P] [US3] Integration test `tests/test_paper_integration.py::test_us3_cap_equivalence` (SC-008) — per_trade_cap·per_symbol_cap·global_exposure 각각, 같은 실계좌 잔고 입력에서 paper·live가 동일한 deny reason. cap 게이트는 실계좌 잔고 기준임을 (FR-016) 검증.
- [ ] T028 [P] [US3] Integration test `tests/test_paper_integration.py::test_us3_halt_and_session` — halt flag 설정 시 paper도 `OrderRejectedByGate.gate="halt"`. session window 외부면 tick 자체 skip. live와 동일 동작.

**Checkpoint**: SC-004·SC-008 통과. paper-run 결과를 운영자가 "live에서도 동일 동작"으로 해석 가능.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 일주일 연속 안정성·live row 무수정·문서 정합성 검증.

- [ ] T029 [P] Integration test `tests/test_paper_integration.py::test_polish_no_live_row_writes` (SC-006) — paper-run 실행 전후로 `positions`, `orders`, `fills` 테이블의 row 수·content snapshot 동일. live audit row(worker_started 등) 신규 0건.
- [ ] T030 [P] Integration test `tests/test_paper_integration.py::test_polish_week_long_stability` (SC-002) — 일주일 시뮬레이션(가속 시간), 메모리 누수·SQLite 손상·예외 미발생 검증. CI에서는 압축 timeline(5분 압축 → 일주일 시뮬)로 실행.
- [ ] T031 [P] Quickstart docs verification — `specs/009-paper-trading-daemon/quickstart.md`의 명령·exit code·출력 형식이 실제 구현과 일치하는지 수동 검수 후 PR 본문에 "quickstart 검수 완료" 명시.
- [ ] T032 [P] Run `uv run ruff check src tests` — clean. Run `uv run pytest` — all green (skip 허용, fail 없음).
- [ ] T033 PR 본문 갱신: K4 commit hash 명시 (Phase 2 commit), 본 PR이 IX.D 자율 머지 채널에 해당함을 본문에 기록. CLAUDE.md 자동 머지 규칙 5단계(테스트·린트·mergeable_state·draft·머지) 점검.

**Checkpoint**: SC-001~SC-008 8개 모두 통과. PR 본문에 K4 commit hash 명시. 자동 머지 조건 충족.

---

## Dependencies

```
Phase 1 (T001~T002) → Phase 2 (T003~T005, K4 단일 commit)
                              ↓
                    Phase 3 US1 (T006~T016)
                              ↓
                ┌─────────────┴─────────────┐
                ↓                           ↓
        Phase 4 US2 (T017~T025)    Phase 5 US3 (T026~T028)
                ↓                           ↓
                └─────────────┬─────────────┘
                              ↓
                    Phase 6 Polish (T029~T033)
```

**Story 독립성**:
- US1 만으로 MVP. paper-report 없어도 운영자가 audit_log를 직접 쿼리해서 일주일 관찰 가능.
- US2 (paper-report)는 US1과 독립적으로 만들 수 있지만, US1의 paper 이벤트가 audit_log에 쌓여 있어야 실효성 있는 결과 검증 가능.
- US3 (게이트 동등성 테스트)는 US1 완료 후만 의미가 있음 (paper-mode OrderRouter가 있어야 비교 가능).

## Parallel Execution Examples

**Phase 3 (US1) 안에서 동시 실행 가능**:
- T006 (mutex 단위 테스트)
- T007 (단일 차단 지점 단위 테스트)
- T008 (게이트 통과 단위 테스트)
- T009 (Worker paper_mode 단위 테스트)
→ 4개 모두 서로 다른 파일·서로 다른 모듈. 한 세션에서 병렬 작성 가능.

**Phase 4 (US2) 안에서 동시 실행 가능**:
- T017 (virtual_positions 단위 테스트)
- T018·T019·T020 (report 단위 테스트 3종)
→ 모두 paper/ 패키지 신규 파일 대상.

**Phase 5 (US3) 안에서 동시 실행 가능**:
- T026·T027·T028 — 모두 같은 통합 테스트 파일이지만 다른 함수. 한 PR 안에서 동시 추가.

## Implementation Strategy

**MVP 정의**: Phase 1 + Phase 2 + Phase 3 (US1).
- 운영자가 paper-run 데몬을 띄우고 일주일 동안 관찰할 수 있다.
- 리포트는 SQLite 직접 쿼리로 대신 — 다소 불편하지만 실효성은 있음.
- 안전 invariant는 paper와 live가 OrderRouter를 공유하므로 자동으로 보장 — 단 SC-004/SC-008은 US3 phase에서 명시적 검증.

**점진 출하**:
1. **MVP (Phase 1~3)**: paper-run 데몬 동작 → 머지 → 운영자 검증.
2. **리포트 추가 (Phase 4)**: paper-report 추가 → 머지 → 운영자가 수동 SQLite 쿼리 부담 제거.
3. **동등성 보장 (Phase 5)**: SC-008 명시 검증 → 머지 → "paper = live 안전 보장" 결정적 진술 가능.
4. **Polish (Phase 6)**: 일주일 안정성 + 문서 정합성 → 머지 → spec 009 완료.

각 단계가 독립 PR이거나, CLAUDE.md "자율 진행" 정책상 한 PR로 묶을 수 있음 (운영자 선호에 따라). 본 spec은 한 PR(claude/continue-previous-session-20p3O 브랜치)에 전체를 묶는 방향을 기본으로 한다.

---

## Format validation

모든 33개 태스크가 다음 포맷을 만족:
- ✅ `- [ ]` 체크박스로 시작
- ✅ T001~T033 순차 ID
- ✅ Phase 3·4·5 태스크는 [US1]/[US2]/[US3] 라벨
- ✅ 병렬 가능 태스크는 [P] 마커
- ✅ 모든 태스크에 파일 경로 또는 명확한 산출물 명시
- ✅ Setup·Foundational·Polish phase는 [Story] 라벨 없음

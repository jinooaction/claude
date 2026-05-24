---
description: "Task list — 스펙 005 자율 튜너"
---

# Tasks: Autonomous Tuner (자율 튜너)

**Input**: Design documents from `specs/005-autonomous-tuner/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/tune-cli.md

**Tests**: 포함(헌법 Development Workflow — 리스크/판단 인접 모듈은 테스트 필수). 전부 결정론적 단위/통합 테스트(LLM·네트워크 미사용).

**Branch**: `claude/wonderful-brown-dkVmU` (feature.json이 `specs/005-autonomous-tuner`를 가리킴)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 가능(다른 파일, 미완 의존 없음)
- **[Story]**: US1~US4 (spec.md User Story 매핑)

---

## Phase 1: Setup (공유 인프라)

- [ ] T001 새 비커널 패키지 골격 생성 — `src/auto_invest/tuner/__init__.py` + 빈 모듈 스텁(`models.py`·`detect.py`·`classify.py`·`knobs.py`·`gates.py`·`report.py`·`runner.py`). 공개 API는 `__init__.py`에서 재노출.

---

## Phase 2: Foundational (모든 User Story의 선행 — 차단)

**목적**: 감사 페이로드(K4 추가-전용)와 데이터 모델은 모든 후속 작업이 의존.

- [ ] T002 `src/auto_invest/persistence/audit.py`(K4 추가-전용)에 이벤트 4종 추가 — `EventType` 리터럴에 `AUTO_TUNED_L1`·`AUTO_TUNED_L2_CANARY_ENTERED`·`AUTO_TUNED_L4_FORENSIC`·`AUTO_TUNER_RUN` 추가, 대응 pydantic 페이로드 4종 정의(data-model.md §9), `AnyPayload` union에 추가. 기존 이벤트·행 불변, 마이그레이션 없음.
- [ ] T003 [P] `src/auto_invest/tuner/models.py` — frozen dataclass 정의: `AuthorityTier`·`SkipReason`(Literal), `ProposedChange`·`CandidateChange`·`Classification`·`AppliedChange`·`TunerRunResult`(data-model.md §2~7).

**체크포인트**: 감사 페이로드 + 모델이 임포트 가능. `uv run pytest`(기존 감사 테스트 무회귀) + `uv run ruff check`.

---

## Phase 3: User Story 1 — KPI 드리프트 감지 + 권한 등급 분류 (P1) 🎯 MVP

**목표**: 튜너가 "무엇을 하려는가"를 결정론적으로 산출(read-only). 어떤 파일도 안 바꿈.
**독립 테스트**: `auto-invest tune --dry-run --as-of <date> --json` → 후보·분류·근거 산출, 파일 무변경.

- [ ] T004 [P] [US1] `src/auto_invest/tuner/classify.py` — 권한 등급 분류기. `deploy/kernel_guard.kernel_diff_check(target_paths, manifest)` 재사용, `not is_clean` → L4 강제 + `touched_groups` 기록(FR-A05). `kernel.toml`·`constitution.md` 경로 → L4 + "튜너는 K-meta 미수정"(FR-A06). 비커널 1차 등급: `threshold_tighten`→L1, `proposal_only`→해당 등급. (data-model.md §4)
- [ ] T005 [P] [US1] `src/auto_invest/tuner/detect.py` — 탐지 규칙. `telemetry/kpi.compute_snapshot`로 7d/30d 스냅샷 + 일별 윈도 안정성 판정(research R-6). 규칙: `threshold_tighten`(30d Tier B 안정 + 일별 Tier C 없음 → tier_b 조이기 후보, 대상 `config/llm_kpi_thresholds.toml`), `cost_drift`/`cache_miss`/`latency_degradation`(Tier C drift → `proposal_only` 후보). 결정론적 `candidate_id`. (data-model.md §3)
- [ ] T006 [US1] `src/auto_invest/tuner/runner.py` — 오케스트레이션 read-only 경로: snapshots→detect→classify→`TunerRunResult` 조립. dry-run은 감사·파일 미기록. (data-model.md §10)
- [ ] T007 [US1] `src/auto_invest/cli.py` — `auto-invest tune` 서브커맨드 골격 추가(`--dry-run` 기본, `--db`·`--as-of`·`--json`·`--thresholds`·`--kernel`). `_exit(2)` 검증 오류 패턴 재사용.
- [ ] T008 [P] [US1] `tests/unit/test_tuner_classify.py` — Kernel K1~K6·K-meta 각 경로가 100% L4(SC-A02), `kernel.toml`/`constitution.md`는 절대 자동 적용 대상 아님(SC-A09), 비커널 config는 L1.
- [ ] T009 [P] [US1] `tests/unit/test_tuner_detect.py` — 합성 `token_usage`로 30d Tier B 안정 → 조이기 후보 생성, 단일 Tier C 일 → 후보 미생성(엣지), 빈 윈도 → 후보 0, 동일 입력 두 번 → 동일 후보(SC-A01 결정성).

**체크포인트**: US1 단독 동작. `tune --dry-run` 후보·분류 출력. 테스트 green + 린트 clean → 커밋·푸시.

---

## Phase 4: User Story 2 — 저위험(L1) 자동 적용 (P1)

**목표**: 측정→행동 루프 닫기. L1 임계값 조이기를 실제 적용(멱등·클램프).
**독립 테스트**: `tune --apply --as-of <date>` → `tier_b` 조여짐 + `AUTO_TUNED_L1` 감사, 재실행 시 멱등.

- [ ] T010 [P] [US2] `src/auto_invest/tuner/knobs.py` — `ThresholdKnob` + `compute_tighten(entry)`(R-5 수학: tier_b를 tier_a 쪽 20% 스텝, tier_a/tier_c 사이 클램프, 조일 여지 없으면 None) + `apply_threshold(path, kpi, new_tier_b)`(TOML 읽기→`[kpi].tier_b`만 교체→원자적 임시파일+`os.replace`, 주석·타 키 보존). (data-model.md §8)
- [ ] T011 [US2] `src/auto_invest/tuner/runner.py` — L1 적용 경로 추가: 세션-날짜 dedup 쿼리(R-8, 이미 적용 시 skip), `apply_threshold` 호출, `append(AutoTunedL1Payload)` 기록, `AppliedChange` 수집. apply 모드만.
- [ ] T012 [US2] `src/auto_invest/cli.py` — `tune`에 `--apply/--dry-run` 토글 배선.
- [ ] T013 [P] [US2] `tests/unit/test_tuner_knobs.py` — 조이기 수학(lower/higher_is_better 양방향), 클램프로 새값이 (tier_a, tier_c) 안(SC-A05), 원자적 쓰기로 타 KPI·주석 보존, `--apply` 두 번 → 한 번만(SC-A04 멱등, 감사 1행).

**체크포인트**: US1+US2 동작. 적용 루프 닫힘. 테스트 green + 린트 clean → 커밋·푸시.

---

## Phase 5: User Story 3 — 안전 게이트: 장 시간 + 측정 기반 (P2)

**목표**: 헌법 VIII.A·X를 코드로 강제.
**독립 테스트**: 장중 시각 주입 → 적용 0건; 표본 < min → "측정 부족" 거부.

- [ ] T014 [P] [US3] `src/auto_invest/tuner/gates.py` — `market_hours_blocked(now)`(R-3: `worker/schedule.is_session_open` True거나 `next_session_open` 30분 전 이내 → 차단, schedule 읽기 전용) + `measurement_sufficient(sample, min_sample)`(헌법 X). 둘 다 `now`·표본을 인자로(테스트 주입).
- [ ] T015 [US3] `src/auto_invest/tuner/runner.py` — apply 경로 앞에 두 게이트 삽입, 차단 시 `skipped`에 `(candidate_id, "market_hours"|"insufficient_measurement")` 기록, 정상 종료. CLI `--min-sample` 배선.
- [ ] T016 [P] [US3] `tests/unit/test_tuner_gates.py` — 개장 후 15분 주입 → 적용 0(SC-A06), 장외 → 통과; 표본 19(<20) → 거부(SC-A07), 20 → 통과; 게이트는 `now`/표본 주입으로 결정론적.

**체크포인트**: US1~US3 동작. 안전 게이트 강제. 테스트 green + 린트 clean → 커밋·푸시.

---

## Phase 6: User Story 4 — 리포트 + CLI 완성 (P2)

**목표**: 운영자 관측성 — auto-tuner-report.json + 전체 CLI 옵션.
**독립 테스트**: `tune --output-root … --apply` → `<date>/auto-tuner-report.json` 작성, `applied`↔`AUTO_TUNED_L1` 정합.

- [ ] T017 [P] [US4] `src/auto_invest/tuner/report.py` — `TunerRunResult`→JSON 직렬화(contracts/tune-cli.md 스키마, `schema_version="1.0"`) + `{output_root}/{session_date}/auto-tuner-report.json` 원자적 작성(reports/daily.py 경로 규칙 미러).
- [ ] T018 [US4] `src/auto_invest/cli.py` + `runner.py` — CLI 옵션 완성(`--window-short`·`--window-long`·`--output-root`·`--json`), runner에 L2/L3 후보 `append(AutoTunedL2CanaryEnteredPayload)`·L4 후보 `append(AutoTunedL4ForensicPayload)`·실행 요약 `append(AutoTunerRunPayload)` 기록(apply 모드), `--json` stdout 출력, `--output-root` 파일 작성.
- [ ] T019 [P] [US4] `tests/unit/test_tuner_report.py` — 리포트 JSON 구조, `applied` 길이 == 기록된 `AUTO_TUNED_L1` 수(SC-A08), dry-run 리포트는 분석 담되 mode="dry_run".
- [ ] T020 [US4] `tests/integration/test_tuner_e2e.py` — CLI end-to-end(typer `CliRunner` 또는 직접 호출): dry-run이 파일·감사 0 변경(SC-A03, mtime+감사 카운트), apply가 임계값 변경+감사+리포트 파일, 같은 as-of 재실행 멱등.

**체크포인트**: US1~US4 전부 동작. 전체 기능 완성.

---

## Phase 7: Polish & 검증

- [ ] T021 전체 `uv run pytest` + `uv run ruff check src tests` 통과 확인, 실패 수정. 회귀 0 확인(기존 847 통과 유지 + 신규 테스트).
- [ ] T022 `tasks.md` 전 작업 done 표시, spec.md Status → 출시 반영, PR 본문에 K4 커밋 해시 명시. `/handoff`로 HANDOFF.md 갱신.

---

## Dependencies

- Phase 1 → Phase 2 → (Phase 3 US1) → (Phase 4 US2) → (Phase 5 US3) → (Phase 6 US4) → Phase 7.
- `runner.py`는 T006(US1)·T011(US2)·T015(US3)·T018(US4)에서 점진 확장 — 순차(같은 파일).
- `cli.py`는 T007·T012·T018에서 점진 확장 — 순차.
- 병렬 가능[P]: 각 Phase 내 서로 다른 파일(classify/detect, knobs, gates, report) + 그 단위 테스트.

## Implementation Strategy

- **MVP = Phase 1+2+3(US1)**: 튜너가 무엇을 하려는지 결정론적으로 산출 + Kernel 안전 분류. 적용 0이어도 가치(안전 핵심).
- 이후 US2(적용)→US3(게이트)→US4(리포트) 순으로 증분. 각 Phase 끝에서 테스트+린트 green이면 커밋·푸시(자율 진행, 권한 질문 없음).
- 전부 완료 + green이면 자동 머지 채널(CLAUDE.md 규칙 3)로 머지 → `/handoff` → 배포 확인(`/deploy-status`).

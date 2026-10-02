# Tasks: 화면 없는 무료 연구 원본 취득

**Input**: `specs/205-hf-research-ingest/` 설계 문서. 반례 검사를 명세에서 요구했다.

## Phase 1: Setup

- [x] T001 기존 원본과 공식 API 한계를 specs/205-hf-research-ingest/research.md에 기록한다.
- [x] T002 설계·헌법 관문·되돌림을 specs/205-hf-research-ingest/plan.md에 기록한다.

## Phase 2: Foundational

- [x] T003 이력·차단·취소 반례를 tests/unit/test_hf_research_ingest.py에 먼저 작성하고 실패를 확인한다.
- [x] T004 엄격한 이력/상태 복원을 src/auto_invest/market_data/hf_research.py에 구현한다.

## Phase 3: US1 공개 목록

독립 검사: 키 없는 수집은 공개 목록 결과만 보존하며 원본 요청 0건이다.

- [x] T005 [US1] 목록·키 부재·리디렉션 반례를 tests/unit/test_hf_research_ingest.py에 작성한다.
- [x] T006 [US1] 고정 목록 취득과 원본 지문을 src/auto_invest/market_data/hf_research.py에 구현한다.

## Phase 4: US2 원본

독립 검사: 정상 두 파일/부분 취득/키 반사 응답이 명확히 구별된다.

- [x] T007 [US2] Parquet·길이·용량·키 반사·403 반례를 tests/unit/test_hf_research_ingest.py에 작성한다.
- [x] T008 [US2] 원본 검증/비노출/완료 순서를 src/auto_invest/market_data/hf_research.py에 구현한다.

## Phase 5: US3 재실행과 원격 경로

독립 검사: 이전 raw 실패를 목록 성공이 초기화하지 않고 최근 기록 유실은 요청하지 않는다.

- [x] T009 [US3] 429·느린 스트림·재실행 차단 반례를 tests/unit/test_hf_research_ingest.py에 작성한다.
- [x] T010 [US3] 비밀 환경 입력과 결과 코드 CLI를 scripts/hf_research_ingest.py에 구현한다.
- [x] T011 [US3] 이력 조회/복원/직렬 수동 작업을 .github/workflows/collect-hf-research.yml에 구현한다.
- [x] T012 [US3] 새 실행 경로의 회귀와 workflow 계약 검사를 .github/workflows/filing-observation-checks.yml 및 tests/unit/test_hf_research_ingest.py에 연결한다.

## Phase 6: Verification and Handoff

- [x] T013 관련 반례·린트·하네스·HANDOFF 사실 검사를 specs/205-hf-research-ingest/results.md에 남긴다.
- [ ] T014 원격 전체 pytest/ruff 결과를 specs/205-hf-research-ingest/results.md에 기록하고 PR 품질 관문을 통과한다.
- [ ] T015 main 수동 실행의 실제 접근/키 부재 결과를 specs/205-hf-research-ingest/results.md와 HANDOFF.md에 기록한다.
- [ ] T016 실제 인증 원본 두 파일과 영구 보관 지문을 specs/205-hf-research-ingest/results.md에 검증한다.

## Dependencies & Execution Order

T001–T002 → T003–T004 → 각 이야기의 검사/구현 → T013–T015 순서다.
T016은 외부 키 입력과 실제 취득 증거가 필요하다. 이 항목을 키 부재로 완료하지 않는다.
원격 구현 출시와 실제 자료 취득 완료를 별도로 보고하며 전체 181 목표도 계속 미완료다.

## Parallel Opportunities

독립 검사의 읽기 전용 검토와 문서 대조는 분리할 수 있다. 같은 소스/테스트 파일의 편집은
순차 진행한다. 이번 구현은 추가 에이전트 없이 수행한다.

## Implementation Strategy

반례 실패 확인 → 목록 → 두 원본 → 차단 복원 → 원격 회귀 → 실제 수동 증거 순서로 진행한다.
한 단계 성공을 수익성·과거 종목 구성·KIS 실거래 준비의 성공으로 해석하지 않는다.

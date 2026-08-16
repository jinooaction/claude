# Tasks: Live Canary Gateway And Profit Evidence

## Phase 1: Setup

- [x] T001 스펙·연구·계획·데이터 모델·계약·체크리스트를 `specs/143-live-canary-gateway-profit-evidence/`에 작성한다.
- [x] T002 production 환경 Ed25519 키쌍을 생성하고 개인키 secret·공개키 파일을 분리한다.

## Phase 2: Foundational

- [x] T003 [US1] `deploy/live-canary-on-instance.sh`에 서명·만료·nonce·센티넬·배포 정합 검증과 고정 주문 명령을 구현한다.
- [x] T004 [US1] `deploy/repair-ssh-boundary.sh`에 root 소유 helper·공개키 설치와 좁은 gateway 명령을 연결한다.
- [x] T005 [P] [US1] `tests/unit/`에 정상·변조·만료·재사용·센티넬 불일치 회귀를 추가한다.

## Phase 3: User Story 1 - 승인된 실주문

- [x] T006 [US1] `.github/workflows/rebalance-live-canary.yml`의 직접 SSH 명령을 production 전용 서명 주문과 고정 체결·측정 명령으로 교체한다.
- [x] T007 [US1] 기존 K1/K2·정규장·현금·손실 브레이커·실패 sidecar 보존 테스트를 확장한다.

## Phase 4: User Story 2 - 첫 실제 수익 증거

- [x] T008 [P] [US2] `src/auto_invest/analytics/live_profit_evidence.py`에 보수적 상태 전이와 sticky 최초 수익을 구현한다.
- [x] T009 [P] [US2] `scripts/live_profit_evidence_probe.py`와 단위·통합 테스트를 구현한다.
- [x] T010 [US2] `.github/workflows/live-profit-evidence.yml`에 체결 동기화·성과 스냅샷·sidecar 발행을 구현한다.

## Phase 5: User Story 3 - 자동 재평가

- [x] T011 [US3] money-path가 live-profit evidence를 소비·표시하고 완료 이벤트로 자동 재실행되게 한다.
- [x] T012 [US3] capital-path-readiness가 money-path 완료 뒤 자동 재실행되게 한다.
- [x] T013 [P] [US3] workflow 순서·manifest·money-path 출력 회귀를 추가한다.

## Phase 6: Verification And Release

- [ ] T014 셸·YAML·focused·전체 pytest·ruff·diff·엄격 하네스·HANDOFF 사실·PR 품질 관문을 통과한다.
- [ ] T015 안전 경계 문구를 포함해 커밋·PR·자동 머지하고 off-hours 배포를 확인한다.
- [ ] T016 주문 없는 live-profit workflow와 파생 money/capital sidecar를 현재 main에서 재발행한다.
- [ ] T017 다음 정규장 production 승인 뒤 주문·체결·양의 손익 또는 단일 외부 조건을 권위 증거로 확정한다.

## Dependencies

- T002-T004가 T006의 주문 경로를 선행한다.
- T008-T009가 T010의 sidecar 생산을 선행한다.
- T010이 T011-T013의 자동 재평가를 선행한다.
- T014-T016이 끝나도 T017의 시장 체결·양의 손익 전에는 전체 목표를 완료하지 않는다.

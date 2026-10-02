# Tasks: 동시 신호의 개장 거래량 우선 처리 검증

**Input**: [명세](spec.md), [계획](plan.md), [조사](research.md), [자료 모형](data-model.md), contracts/.

## Phase 1 — 범위와 봉인

- [x] T001 `spec.md`에 새 가설·위험 등급3·완료 기준과 전체181 미완료 범위를 정의한다.
- [x] T002 `research.md`에194·논문 차이·최소35시도·자료 공개/기기 제약을 확인한다.
- [x] T003 `contracts/preregistration.json`의 새 한 후보를 성과 조회 전에 커밋·푸시하고 지문을 남긴다.39dc9de601c244cd633b4af353bb42991c436294,계약0eb8c1b04bacb8e347f0fc1708d7b392cb37b8526ffe6b18a57d388716546a85.실제 성과 미조회.

## Phase 2 — US1 처리 순서

독립 검사: 거래량·동률·서로 다른 시각·미래 가격·기존194 장부.

- [x] T004 [US1] `tests/unit/test_volume_priority_research.py`에 작은 실패 반례를 먼저 작성한다.구현 전 모듈 부재로수집 실패0.91초를 확인했다.
- [x] T005 [US1] `src/auto_invest/analytics/sparse_opening_research.py`에서194 기본 경로를 유지하며 내부 재생기를 분리한다.기존 공개 실행/장부 전체 동일 반례 통과.
- [x] T006 [US1] `src/auto_invest/analytics/volume_priority_research.py`에 봉인 계약·순서·최소36·새 결과 정체성을 구현한다.두 비용·4보유·부분 매수 반례와기존194 관련54개/9.03초·린트 통과.실제 재생은 T014.

## Phase 3 — US2 현금·체결 재현

독립 검사: 현금·부분 체결·정산·청산 대기와 원본 반복 재생.

- [ ] T007 [US2] `tests/unit/test_volume_priority_research.py`에 현금 부족·시도권·부분 청산·누락·194 호환 반례를 추가한다.
- [ ] T008 [US2] `scripts/volume_priority_research.py`에 새 출력·장부/코드 지문·194 독립 산술 검증을 연결한다.
- [ ] T009 [US2] `tests/integration/test_volume_priority_research_cli.py`에 실제 명령·재계산·변조/덮어쓰기 거부를 검증한다.

## Phase 4 — US3 원본과 원격

독립 검사: 키·암호문·압축·종목·지문 실패를 재생 전 거부.

- [ ] T010 [US3] `scripts/volume_priority_research.py`에 제한된 준비·AES-GCM 인증·원본 지문·비밀 비노출을 구현한다.
- [ ] T011 [US3] `tests/integration/test_volume_priority_research_cli.py`에 잘못된 키·인증/크기·nonce/종목 중복·원본 혼입 반례를 검사한다.
- [ ] T012 [US3] `research-fixtures/206/`에 평문 원본 없는 봉인 암호문·입력 잠금을 준비한다.
- [ ] T013 [US3] `.github/workflows/volume-priority-checks.yml`에 신뢰된 코드·분리 키·원격 재생/재계산·전체 회귀·산출물 보존을 연결한다.

## Phase 5 — 실제 결과와 인계

- [ ] T014 `results.md`에 원격 실제 재생·독립 검증·코드/계약/장부 지문과 정확한 판정을 보존한다.
- [ ] T015 `results.md`와 PR 본문에 원격 전체 pytest/ruff·엄격 하네스·HANDOFF 사실·본문 품질·비밀 비노출 검사를 남긴다.
- [ ] T016 `HANDOFF.md`, `spec.md`, `tasks.md`, PR 본문에 연구 출시·후보 판정·전체181 미완료를 구분하고 검증 후 병합·필요 배포를 확인한다.

## 의존성과 실행 방식

T001~T003→T004→T005/T006→T007~T009→T010~T013→T014/T015→T016.
다른 파일의 반례 설계는 이론상 병렬 가능하지만 현재는 한 작업자가 순차 수행한다.
첫 증분은 봉인과 작은 순서 반례이며 실제 재생·전체 검사·인계까지 범위를 줄이지 않는다.
기존205 초안의 T015/T016은206으로 완료하지 않는다.

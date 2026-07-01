# 작업 목록: 완료 후보 소비 및 차순위 자동 승격 루프

## 1. 명세와 계약

- [x] T001 스펙 079 요구사항 작성
- [x] T002 계획, 연구, 데이터 모델, 계약, 빠른 확인 문서 작성
- [x] T003 `.specify/feature.json`과 `CLAUDE.md` 활성 포인터 갱신

## 2. 완료 장부 발행

- [x] T004 `auto_invest.analytics.released_work` 코어 추가
- [x] T005 `scripts/released_work_probe.py` 진입점 추가
- [x] T006 `.github/workflows/released-work-ledger.yml` 추가
- [x] T007 `pipeline_liveness.default_specs()`에 `released-work` sidecar 등록

## 3. 자율 작업 실행 소비

- [x] T008 `autonomous_work_execution`에 `released-work` evidence 소비 추가
- [x] T009 `autonomous_work_execution_probe.py` manifest와 repository fallback 추가
- [x] T010 `.github/workflows/autonomous-work-execution.yml`에서 repository fallback 배선

## 4. 검증

- [x] T011 완료 장부 단위 테스트 추가
- [x] T012 자율 작업 실행 완료 후보 억제 테스트 추가
- [x] T013 probe/workflow 통합 테스트 추가
- [x] T014 최신 sidecar와 repo scan으로 로컬 smoke 실행
- [x] T015 전체 테스트와 린트 실행

## 5. 배포와 인계

- [x] T016 PR 본문 품질 관문 작성·검증
- [ ] T017 PR 생성, 확인, 자동 머지
- [ ] T018 post-merge workflow sidecar 확인
- [ ] T019 HANDOFF 갱신

# 작업 목록: 돈 경로 게이트 정렬 루프

## 1. 명세와 계약

- [x] T001 스펙 078 요구사항 작성
- [x] T002 계획, 연구, 데이터 모델, 계약, 빠른 확인 문서 작성
- [x] T003 `.specify/feature.json`과 `CLAUDE.md` 활성 포인터 갱신

## 2. 구현

- [x] T004 `auto_invest.analytics.money_gate_alignment` 코어 추가
- [x] T005 `scripts/money_gate_alignment_probe.py` 진입점 추가
- [x] T006 `.github/workflows/money-gate-alignment.yml` 추가
- [x] T007 `pipeline_liveness.default_specs()`에 sidecar 등록

## 3. 검증

- [x] T008 단위 테스트 추가
- [x] T009 probe/workflow 통합 테스트 추가
- [x] T010 최신 automation sidecar로 로컬 smoke 실행
- [x] T011 전체 테스트와 린트 실행

## 4. 배포와 인계

- [x] T012 PR 본문 품질 관문 작성·검증
- [x] T013 PR 생성, 확인, 자동 머지
- [x] T014 post-merge workflow sidecar 확인
- [x] T015 HANDOFF 갱신

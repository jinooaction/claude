# Tasks: 공개 보고서 JSON 보호
**Input**: spec.md, plan.md, research.md, data-model.md, contracts/redaction.md
## Phase 1: Setup
- [x] T001 specs/217-sidecar-json-redaction/spec.md에 등급3·보호계약·미복원·비목표를 확정한다.
- [x] T002 .specify/memory/constitution.md 및 kernel.toml을 점검하고 plan.md에 변경 불필요와 전략 지문 관문 보존을 기록한다.
## Phase 2: Foundation
- [x] T003 scripts/redact_public_sidecar.py와 forward-edge-autoarm.yml의 원본→발행→소비자 경로를 research.md에 기록한다.
## Phase 3: US1 정상 증거·비밀 보호
- [x] T004 [US1] tests/unit/test_public_sidecar_markdown.py에 숫자·비밀·복수 블록의 실패 반례를 먼저 작성한다. 수정 전 첫 2개 실패 확인.
- [x] T005 [US1] scripts/redact_public_sidecar.py에 구조 기반 Markdown/표준 입력 보호와 계좌 NAV 민감 키를 구현한다.
- [x] T006 [US1] tests/unit/test_public_sidecar_markdown.py에서 파일·디렉터리·표준 입력·소비자 파싱을 확인한다.
## Phase 4: US2 손상 증거·경계
- [x] T007 [US2] tests/unit/test_public_sidecar_markdown.py에서 손상·미닫힘·중첩·일반 코드·반복 처리 반례를 확인한다.
- [x] T012 [US2] tests/unit/test_public_sidecar_markdown.py에 재귀/정수 한도 실패3개를 재현하고 scripts/redact_public_sidecar.py에서 기존 보호 복귀를 확인한다.
- [x] T008 [US2] specs/217-sidecar-json-redaction/results.md에 실제 손상 원본 비복원 및 되돌림 검토를 기록한다.
## Phase 5: 검증과 인계
- [x] T009 .github/workflows/volume-priority-checks.yml에 정확 경로/필수 반례를 연결한다. 전체 실행 결과는 아래 출시 관문으로 별도 추적한다.
- [x] T010 HANDOFF.md에 복구/배포/새 보정/남은181을 구분하고 로컬 하네스·인계 관문을 확인한다.
- [x] T011 specs/217-sidecar-json-redaction/results.md에 병합·정규 발행 관측의 외부 대기 조건과 확인 경로를 남긴다.

## 출시 관문
위 체크는 구현과 로컬 검증 완료를 뜻한다. 정확 PR HEAD의 전체 회귀·린트·본문 품질 통과 및 병합 가능 상태가 실제 확인되어야 병합한다.
전체 실행 번호, 정확 커밋, 원래 XML 검사 결과와 병합 해시는 PR 본문의 최종 검증 기록에 남긴다.
자본 사다리의 새 정규 실행이 원본을 재생성하기 전까지 기존 손상 보고서 경고는 남는다. 이를 코드 미구현이나 정상 발행 완료로 혼동하지 않는다.
## Dependencies and strategy
T001→T002→T003→T004→T005→T006→T007→T008→T009→T010→T011.
먼저 재현, 공통 보호 재사용, 반례 확장, 전체 검증 순서다.
US1의 수치/비밀 fixture 작성과 US2의 손상 fixture 설계는 파일 분리 시 병렬 가능하나 여기서는 같은 파일을 순차 수정한다.

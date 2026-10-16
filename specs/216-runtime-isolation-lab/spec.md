# Feature Specification: 합성 실행 환경의 기동·격리 실험

**Branch**: `codex/216-runtime-isolation-lab` | **Created**: 2026-10-16
**Status**: 구현 전 계약 고정
**Input**: 215의 설계를 비밀 없는 GitHub 합성 실험으로 검증한다.

## User Scenarios & Testing
### US1 — 실행 전 설정 거절 (P1)
운영자는 지정한 이미지와 시작 명령·권한·네트워크·마운트가 다르면 합성 프로그램도 시작하지 않는 것을 확인한다.
독립 검사: 잘못된 컨테이너는 created 상태에서 거절되고 start 호출 수가 0이다.
### US2 — 기동 경로와 배포 분리 (P1)
고정된 장난감 모듈은 PYTHONPATH/PYTHONHOME와 자동 site 처리를 사용하지 않으며 호스트의 별도 main 모양 폴더 변경에도 값이 유지된다.
독립 검사: 실제 Python 플래그·검색 경로·모듈 파일 지문과 두 번 실행한 결과를 대조한다.
### US3 — 한계와 실제 운영 기록 (P2)
읽기 전용 bind에서도 호스트 변경이 보이는 부정 실험을 보존한다. 215 실제 예약 반영은 원래 진단 두 건과 감사로 별도 확인한다.
독립 검사: 부정 실험의 값은 바뀌고 일반 격리 실행의 값은 유지되지만 어느 것도 실제 후보 자격을 만들지 않는다.

## Requirements
- **FR-001**: 실행은 Linux GitHub Actions에서만 허용한다. 로컬은 순수 설정 검사 합성만 허용하고 Docker 호출 전 거절한다.
- **FR-002**: 고정 linux/amd64 기반 manifest와 생성한 작은 fixture만 이미지에 넣는다. 저장소 전체·비밀·장부·실제 후보·가격을 복사하지 않는다.
- **FR-003**: docker create 뒤 같은 ID를 inspect하여 이미지 ID/Path/Args/Entrypoint/Cmd/User/cwd/환경/읽기전용/권한/네트워크/자원/마운트/created 상태를 자료형까지 검증한 뒤만 start한다.
- **FR-004**: 일반 실험은 네트워크 none, 읽기 전용 root, 비특권 사용자, 모든 capability 제거, no-new-privileges, PID64/128MiB/CPU1이다. 호스트 bind/장치와 검사 대상의 명시적 host/container namespace 공유 설정을 거절한다. 별도 사용자 namespace 생성은 인증하지 않는다.
- **FR-005**: Python -I -S -B의 실제 플래그와 /candidate/modules의 명시적 장난감 import를 확인한다. 자동 site 주입은 실제 site-packages 위치에서 SystemExit 부정 대조군으로 확인한다.
- **FR-006**: source 쓰기 거절과 일반 호스트 폴더 갱신 독립성을 실제 실행한다. 별도 고정 bind 부정 대조군은 서로 다른 두 기동 사이의 호스트 변경 가시성이다. 실행 중 같은 mount의 변경 실험으로 확대하지 않는다. 임의 우회 옵션은 제공하지 않는다.
- **FR-007**: 결과는 SYNTHETIC_RUNTIME_LAB이며 실제 후보 설치/전체 runtime closure/지속 불변/등록/실거래 자격/승격은 false, 준비 NOT_ASSESSED, orders0이다.
- **FR-008**: 기존 source_identity/정확 HEAD·ROOT/등록 HMAC/독립 재계산/수집증명/90초/60세션 검증을 복제·소비·완화하지 않는다. 실제 환경은 조사·설치·기동하지 않는다.
- **FR-009**: 명령별 유한 시간·작은 출력/보고서·컨테이너와 이미지 정리를 둔다. 실패는 성공 보고서를 만들지 않는다. 타임아웃을 임의 중복 실행하지 않는다.
- **FR-010**: 정확 원격 전체 XML/필수 기존 반례·린트와 별도 실제 Docker 보고서/지문을 보관한다. 기존 고정 release는 변경하지 않는다.

## Success Criteria
- **SC-001**: 설정 반례가 실행 전 거절되며 순수 합성 검사는 Docker 없이 재현된다.
- **SC-002**: GitHub에서 기동·주입 양성/음성 대조·쓰기·독립 폴더 갱신·bind 한계가 실제 실행되고 원래 보고서로 재현된다.
- **SC-003**: 정확 HEAD의 전체 회귀/필수 반례 무생략/린트와 안전한 범위 표기가 통과한다.
- **SC-004**: 실제215 예약 반영·두 정기 원본과 기존 부재가 보관 자료로 재현된다.

## Risk / Scope / Rollback
등급3: 새 합성 실행 경계와 CI를 도입하므로 `this changes the safety perimeter`를 커밋에 남긴다.
헌법/Kernel·운용6파일·기존 생산 관문·자동배포·의존성 파일·장부·키·권한·돈 경로는 불변이다.
제거되는 기존 기능0. 되돌림은 새 도구/CI/포인터를 정상 PR로 제거하는 것이며 기존 실행 경로에는 소비자가 없다.
서버 HMAC은 증권사 서명이 아니다. 전체181·실제 통과 전략/독립확인/생산 체결은 별개 미완료다.
기존1645세션·탈락 사실·최소36·495미개봉·31/40bp·200거래·현금/정산/부분체결 경계를 보존한다.

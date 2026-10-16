# Implementation Plan: 합성 실행 환경의 기동·격리 실험
**Branch**: `codex/216-runtime-isolation-lab` | **Date**: 2026-10-16 | **Spec**: [spec.md](spec.md)

## Summary
215 계약 중 기동 설정·검색 경로·합성 배포 분리의 일부를 GitHub에서 실제 실험한다.
실제 후보 실행기/설치기/전체 환경 인증기가 아니며 기존 프로그램·등록을 import/호출하지 않는다.
214 지역 비교를 링크가 있는 OCI root 전체 인증에 쓰지 않는다.

## Technical Context
Python3.11 표준 라이브러리, Docker CLI는 GitHub Ubuntu에서만 호출한다. 새 의존성0.
기반 python3.11.14-slim-bookworm linux/amd64 manifest는
`sha256:83f339c1be6340ae1096010fdccf6552ac932d8f410d45d206014916bdf37e48`.
최신/실제 서버 동등성 주장이 아니다. 기반 digest·빌드 image ID·container ID를 분리한다.
작은 Dockerfile/entry/모듈/주입 fixture만 임시 생성한다. 빌드 RUN0/외부설치0/실제자료0.
명령180초(빌드)/20초(나머지)·출력64KiB/보고서32KiB/CI 실험12분·회귀45분이다.
로컬은 순수 validator/가짜 호출의 짧은 합성만 실행한다. 전체pytest/실제 Docker는 Actions만 한다.
Docker Engine/host kernel은 신뢰 기반이며 관리자 변경·공급망 진위·지속 불변은 인증하지 않는다.

## Constitution Check — 설계 전후 통과
I/II 한도·종목·계좌/주문 불변; III 외부판단0; IV 장부·감사 보존; V 비밀0;
VI 단계/실거래 승인 유지; VII 시장 API0; VIII.A/B 장중배포/감사/rollback 불변;
IX 헌법/Kernel 불변·등급3 기록; X 성과 없는 합격0. 정확 HEAD/등록HMAC·90초·60세션·최소36·495미개봉·31/40bp·200거래·현금/정산/부분체결 불변.
실제 Git ROOT/원래 의존성·설치 입력 연결은 후속 미평가이며 장난감 값으로 충족시키지 않는다.

## Project Structure / 적용 경로
scripts/intraday_runtime_isolation_lab.py: GitHub 전용 CLI·엄격 inspect 검사.
tests/unit/test_intraday_runtime_isolation_lab.py: Docker 없는 설정 반례.
.github/workflows/runtime-isolation-lab.yml: 정확 PR HEAD 전체회귀/별도 Docker 실험·artifact.
specs/216-runtime-isolation-lab/{spec,plan,tasks,research,data-model,quickstart,results}.md와 contracts/checklists/evidence.
AGENTS/.specify 포인터는216, HANDOFF는 실제 main44/215 완료와216 진행을 구분한다.

## Phase 0 / Phase 1
공식 Docker create/inspect/none/bind·Python -I/-S/-B/site를 독립 읽기 전용 조사 역할로 검토했다.
같은 ID/created 상태의 검사가 성공한 컨테이너만 start한다. 일반 경로 mount0.
별도 고정 site 양성/ro bind 부정 대조군만 두며 임의 bypass 옵션0이다.
site fixture는 실제 site-packages 위치에 SystemExit를 넣고 -S 제거 시 실제 실행됨을 대조한다.
구현 전 계약은 해결됐으며 실제 환경 관련 미관측은 false로 남긴다.

## Complexity Tracking / 되돌림
제거 기능0. 기존213/214/등록·수집·진단·자동배포 유지. 새 CLI/CI 제거 정상 PR로 되돌린다.
main 동결/HEAD 예외/키 복제/자동 재등록/현 서비스 attest 활성화는 범위 밖이다.
실험 성공을 실제 설치·등록·정식전진에 연결하는 소비자0.

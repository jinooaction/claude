# Implementation Plan: 검토 소스·설치 입력과 고정 이미지의 연결 계약
**Branch**: `codex/218-source-installation-contract` | **Date**: 2026-10-17 KST | **Spec**: [spec.md](spec.md)

## Summary
215의 여섯 증거 범주 중 첫 범주인 소스·의존성 원본을 구체화한다.
216은 기동·격리의 실제 합성 실험이고 이번218은 원래 입력→이미지 연결의 설계 문서다.
새 설치기/실행기/검증기/등록 소비자나 합성 컨테이너는 이번에 만들지 않는다.

## Technical Context
현재 main69eb5f99628f9857a0a40bc7e1bfe4a5acf7fe16의 정적 호출부를 읽는다.
기존 source_identity는 지정 실행 소스의 바이트를 묶고, register/prepare_qualification은
각 모듈 ROOT에서 Git HEAD를 읽는다. HMAC·정확 code_commit·연구 독립 재계산은 유지한다.
새로운 저장소 독립성/전체 바이트/설치 입력 조건은 추가 계약이며 기존 등록의 숨은 기능이 아니다.
구현 언어·의존성·서버 경로 변경0. 문서 형식·하네스 검사는 짧게 로컬에서 한다.
정확 문서 HEAD의 전체 회귀·린트는 기존 volume-priority-checks에서 GitHub로 실행한다.
해당 워크플로의 PR 경로 목록에218 문서 경로만 추가한다. 비밀 사용·실제 연구 조건은 그대로다.
216 문서/워크플로는 변경하지 않아 끝난 Docker 실험을 다시 실행하지 않는다.

## Constitution Check — 설계 전후
I/II 한도·허용목록/계좌 불변; III 새 LLM 호출/비용0; IV 장부/감사 보존;
V 운영 폴더·인증 Git 설정·과거 비밀 이력 반입 금지; VI 전략/자본 승격0;
VII 시장 API/수집0; VIII.A/B 현재 장중 배포 제한·예약·감사·되돌림 불변;
IX 헌법/Kernel 변경0, 등급3 안전 경계 설계로 `this changes the safety perimeter` 기록;
X 성과 조회/최종495 개봉/전략 자격 부여0.
90초·60세션·최소36·31/40bp·200거래·현금/정산/부분체결 보존.
PR895의 기존 실주문 예약 복구는 별도 등급4 승인 대기이며 이번 브랜치에서 수정/병합/실행하지 않는다.

## Project Structure / 적용 경로
specs/218-source-installation-contract/{spec,plan,research,data-model,quickstart,tasks,results}.md,
contracts/source-installation.md, checklists/requirements.md에 계약과 검토 근거를 둔다.
AGENTS/.specify 포인터는218, HANDOFF는 실제 main69/서버의 마지막 원래 관측/895 승인 대기를 구분한다.
.github/workflows/volume-priority-checks.yml은218 문서의 전체 회귀 실행 경로만 추가한다.
src/scripts/tests/deploy/의존성/헌법/Kernel은 변경하지 않는다.

## Phase 0 / 연구 결정
독립 읽기 전용 조사에서 기존 실행 지문은 전체 Git/설치물을 보증하지 않는다는 사실을 확인했다.
Git clone/archive와 pip 보안 설치 공식 문서를 확인했다. 원문 근거·선택/대안은 research.md에 둔다.
불완전한 소스 export나 수정한 HEAD, 운영 .git 복사, 버전 목록만의 설치 인증을 제외한다.
새 저장소 준비 방식은 후속 합성에서만 구현하며 현재 사용자 저장소를 정리/복제하지 않는다.

## Phase 1 / 후속 구현 계약
독립 검토 입력→소스 저장소→설치 입력→설치 결과→고정 이미지의 각 연결을 원래 지문으로 묶는다.
정확 ROOT/Git 도구를 실제 이미지에서 확인해야 하며 Git 없는 기반 이미지에 가짜 rev-parse를 넣지 않는다.
기반 Git 실행파일·loader/native까지 출처와 내용이 검토되기 전에는 연결 성공을 선언하지 않는다.
216의 Python 기반 이미지를 그대로 쓸 수 있는지, 실제 프로젝트 lock/설치 파일을 지원할지는 미평가다.
후속 첫 구현은 장난감 단일 초기 커밋과 작고 비실행적인 설치 입력만 사용한다.
실제 프로젝트의 전체 이력/소스/패키지를 반입하는 단계는 별도 검토 전까지 열지 않는다.
실제 신규 검증기·컨테이너 작업은 후속 별도 기능/등급3 SDD로 구현한다.

## Complexity Tracking / 되돌림
기존 기능 제거0. 계약은 기존 소비자를 대체하지 않는다.
되돌림은218 문서·포인터·새 CI 경로를 정상 PR로 복구한다. 기존216/214 및 등록/수집 경로는 유지한다.
설계에 적힌 미평가 조건이 해소되지 않으면 후속 단계가 멈추며, 입력을 자동 보충하거나 기존 관문을 낮추지 않는다.

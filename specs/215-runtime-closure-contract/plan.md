# Implementation Plan: 고정 실행 환경의 증거 계약
**Branch**: `codex/215-runtime-closure-contract` | **Date**: 2026-10-15 | **Spec**: [spec.md](spec.md)

## Summary
이번 구현 대상은 설계 문서 묶음이다. 새 실행기/설치기/검증기·등록 소비자는 만들지 않는다.
213 지역 경로 비교와214 설치 폴더 비교 다음에 필요한 실제 환경의 증거 계약과 단계별 반례를 고정한다.
214 실제 예약 반영·원래 진단 원본을 별도 고정 보관하고 이번 정당한 후속 기록에서214 T008을 닫는다.

## Technical Context
Markdown/작은 안전 JSON, 기존 Python3.11 원본 영수증 검증기만 사용한다. 새 의존성0.
실제 Ubuntu/Linux 서버의 런타임·커널·마운트·설치파일은 이번에 조회하지 않았다.
전체 CI는 기존 installed-tree-checks의 정확 PR HEAD에서 실시하며 로컬은 작은 파일/영수증·하네스만 읽는다.
.specify/feature.json은 기존 deploy-on-merge paths-ignore 대상이 아니므로 병합 뒤 정상배포가 시작될 수 있다.
문서 계약과 SDD 포인터 변경이며 실행파일은 같지만 배포 트리거 제외라고 단정하지 않는다. 장중이면 기존예약에 맡기고 실제 현재시도 로그를 확인한다.
후속 구현의 참조 형태는 원래 소스 저장소와 기반 Python/stdlib/native를 포함한 내용 지문 고정 OCI 이미지다.
이미지 tag 대신 정확 manifest/config/layer/platform 지문과 실제 runtime config를 독립 연결해야 한다.
OCI 런타임 사용 가능성은 미관측이며 현재 선택은 설계 참조일 뿐 설치 가능한 상태라는 결론이 아니다.

## Constitution Check
I/II 한도·종목/계좌·주문 불변; III 외부판단 호출0; IV 장부·감사 추가전용 보존;
V 비밀 입력/전문 공개0; VI 연구→관찰→실거래 단계 유지; VII 새 외부 수집0;
VIII.A 장중배포/예약 불변; IX 헌법/커널·자격 경계 불변; X 성과 없는 합격 선언0.
90초/60세션·정확등록·최소36·495미개봉·31/40bp·200거래·현금/정산/부분체결 유지.
후속 실행환경 규칙을 source_identity/등록/자격에 연결하려면 별도 등급3 풀 SDD와 안전 변경 기록이 필요하다.
설계 전·후 위 관문 통과. 등급4 실행은 이번 범위 밖이다.

## Project Structure
specs/215-runtime-closure-contract/{spec,plan,research,data-model,quickstart,tasks,results}.md,
contracts/runtime-closure.md, checklists/requirements.md, evidence/작은 실제 반영·보관 영수증.
AGENTS/.specify는215 계획을 가리키고 HANDOFF는 actual main9e와214 종료/현재215 설계 상태를 구분한다.
src/scripts/tests/.github/의존성·deploy/헌법/Kernel 파일 변경0.

## Phase 0 — 조사 완료 기준
기존 identity/registration/qualification·진단유닛 호출부를 읽고 공식 Python3.11 및 고정 OCI image1.1.0/runtime1.2.1 문서와 연결한다.
관련 스킬이 요구하는 조사 검토를 별도 읽기 전용 연구 역할로 수행했다. 실제 후보 코드/키/서버 설치 증거는 조사하지 않았다.
기술 선택의 미관측 사항은 만족 가정 대신 계약의 미평가 항목으로 처리한다.

## Phase 1 — 자료/계약/검증
data-model의 여섯 범주를 contracts의 폐쇄형 증거 연결로 정의한다.
입력 봉인과 실제 설치·기동·지속 불변 근거는 독립 단계다. 과거 시각·같은 hash·버전·mtime만으로 원인을 연결하지 않는다.
quickstart의 열두 반례를 문서 검토표로 대조한다. 이는 실제 서버 반례 실행이나 신규 합성 시험 통과가 아니다.

## 후속 구현 순서 — 이번 출시 범위 밖
1. 별도 등급3 SDD에서 입력 봉인·환경 신뢰 주체·기존 정확 등록 연결을 먼저 고정한다. 임의 새 키/서명 체계를 만들지 않는다.
2. GitHub의 비밀 없는 독립 합성 저장소/이미지에서 기존 검증을 그대로 실행할 수 있는 자료 배치를 확인한다.
   기존 ROOT 계산식을 유지하고 후보 모듈의 ROOT가 후보의 정확 Git 저장소 루트를 가리키도록 .git/소스 배치를 보존한다. main과 같은 절대 경로를 요구하지 않는다.
   wheel 설치로 ROOT가 site-packages를 가리키거나 Git 정보를 뺀 이미지면 기존 검증이 실패하는 것이 정상이다.
3. 기반 Python/표준·확장 라이브러리·전이 의존성·이미지 구성·원래 설치 입력을 독립 지문으로 대조한다.
4. 실제 기동 args/cwd/env/검색·이미로드모듈·mount/hooks/platform과 read→execute 연결을 검증한다.
   -I/-S는 검증할 후보 설정일 뿐 그대로 운영 명령으로 채택하지 않는다. -S의 Python3.11 venv prefix 효과 및 기존 의존성 로드를 먼저 확인한다.
5. main을 합성 동시 갱신하면서 후보의 code/tree/image/runtime config가 그대로인지, 외부 공유 쓰기를 거절하는지 검사한다.
6. 실제 통과 전략과 선행 근거가 있을 때만 실제 서버의 설치/기동 가능 조건을 별도 검토한다. 현재 그런 후보/환경을 확인하지 않았다.
7. 기존 등록·수집 인증·90초/60세션·계좌·권한·실체결 관문은 별도로 검증한다. 환경 비교 성공이 이를 대체하지 않는다.

## Complexity Tracking / 되돌림
설치 폴더를 복사한 venv만으로 전체 기반을 고정하는 대안, main 디렉터리 자체를 동결하는 대안,
문서 커밋 예외·자동 재등록으로 HEAD 거절을 완화하는 대안을 제외했다.
이는 기존 실행기 제거가 아니다. 213/214·수집기·등록 검증과 main 자동배포를 그대로 남긴다.
이 설계/포인터/인계만 정상 PR로 되돌릴 수 있다. 실제 유닛/실행 코드가 바뀌지 않아 실행 복구 조치가 필요하지 않다.

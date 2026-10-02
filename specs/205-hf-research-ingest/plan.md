# Implementation Plan: 화면 없는 무료 연구 원본 취득

**Branch**: `codex/205-hf-research-ingest` | **Date**: 2026-10-02 | **Spec**: [spec.md](spec.md)

## Summary

고정 공개 목록과 AMZN/NVDA raw 원본만 요청하는 연구 CLI를 추가한다. 수동 Actions 실행으로
맥북 화면 간섭을 없애며 GitHub 실행 이력과 작은 상태 산출물로 요청 차단을 복원한다.
가격 평가·전략 선택·돈 경로는 연결하지 않는다. 전체 181 목표의 일부 자료 확보 경로다.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: 기존 httpx, 개발 의존성 duckdb 1.4.1, GitHub Actions  
**Storage**: 새 원본 디렉터리와 90일 Actions artifact, 작은 상태 JSON, 별도 장기 보관 폴더
**Testing**: pytest, ruff, 모의 HTTP, 느린 스트림의 실제 경과시간 반례  
**Target Platform**: Linux Actions; POSIX 주 스레드의 신호 기반 시간 제한  
**Project Type**: 연구 CLI  
**Performance Goals**: 요청 20초/전체 180초/직렬 최소 1초 간격  
**Constraints**: 고정 주소, 키 비노출, 3회 실패/900초 차단, 원본당 128MiB  
**Scale/Scope**: 공개 목록 1개와 두 종목 전체 raw 파일; 대량 자료/전략 검증은 범위 밖

## Constitution Check

설계 전/후 모두 확인한다. I/II: 계좌·종목 허용목록·주문 제한을 건드리지 않는다.
III: LLM 호출 없음. IV: 기존 감사·원본 변경 없음. V: HF 키는 환경변수만,
반사 응답·예외·헤더 비노출. VI: 수집은 자격 승격 없음. VII: 유한 재시도와 재실행 차단,
첫 요청 간격, 전체 경과시간, Retry-After를 검증한다. VIII.A: 운영 서버 배포 없음,
연구 Actions만 실행한다. IX/X: 비용 가정·미검증 자격·181 열린 관문을 보존한다.
헌법/커널 목록 수정은 없다. 위반 없음. 되돌림은 수동 수집 중단이며 기존 원본은 보존한다.

## Project Structure

```text
src/auto_invest/market_data/hf_research.py
scripts/hf_research_ingest.py
scripts/hf_research_retain.py
tests/unit/test_hf_research_ingest.py
.github/workflows/collect-hf-research.yml
.github/workflows/filing-observation-checks.yml
specs/205-hf-research-ingest/{spec,plan,research,data-model,quickstart,tasks,results}.md
specs/205-hf-research-ingest/contracts/cli.md
```

목록/원본 상태를 분리한다. 사전 이력 조회 실패·현재 rerun·이전 진행 중은 HTTP 요청 0건이다.
이전 완료 실행의 상태가 없으면 종료 시각+900초의 보수 차단 후 실패 3회 반개방으로 복원한다.
최종 상태/원본 산출물은 분리하고 미완료 파일은 업로드하지 않는다. 정상 두 파일만 COMPLETE다.
실제 인증 원본 취득과 영구 보관은 외부 키와 증거 확인이 필요한 별도 미완료 항목으로 둔다.

## 장기 보관 보완 — 2026-10-02

기존 90일 산출물의 만료는 장기 연구 입력의 보존을 보장하지 않는다. 기존 명세의 원본
보존 단계를 오프라인 CLI로 구체화한다. 위험 등급 3의 기존 수집 기능 보완이며 새 외부
요청·비밀 입력·예약·운영 배포·돈 경로는 없다. 기존 자료와 차단 상태는 제거하지 않는다.
공유 stage_output은 복사본의 파일/디렉터리 저장을 동기화하며 보관은 새 폴더의 source/
아래에 이를 사용한다. 최종 retention.json은 입력 및 보관 manifest 지문·UTC 시각과
연구 경계를 가진다. 보관 실패 시 이번에 만든 폴더만 정리하고 원본은 그대로 둔다.
보관 명령을 중단하면 되돌릴 수 있으며 이미 보존된 원본은 삭제하지 않는다.
모의 자료 보관 성공을 T016의 실제 인증 취득 증거로 사용하지 않는다.

## Complexity Tracking

위반 없음. 범용 broker 차단기의 메모리 상태로 대체하면 재실행 안전성이 없어 전용 작은
상태 모델을 사용한다. Actions 산출물 유실은 GitHub 종료 시각을 이용한 명시적 차단으로 보완한다.

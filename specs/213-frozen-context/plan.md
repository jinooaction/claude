# Implementation Plan: 후보 고정 환경의 읽기 전용 사전 확인

**Branch**: `codex/213-frozen-context` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

## Summary
기존 등록의 정확 HEAD 비교를 유지하기 위해, 설치·수집 전에 선언과 지역 실행 환경의 연결을 확인하는 별도 도구를 제공한다.
한 번의 비교는 불변 환경 설치/지속 불변/전체 파일 인증이나 실행 허가가 아니다. 기존 실행 경로에 자동 배선하지 않는다.

## Technical Context
- Language/Version: Python3.11 이상, 표준 라이브러리.
- Primary Dependencies: 기존 Git 읽기 명령, importlib의 모듈 위치/설치 메타데이터 조회. 새 의존성 없음.
- Storage: 읽기 전용 선언/Git/lock/소스. 결과는 stdout 한 JSON, 자동 저장 없음.
- Testing: pytest의 작은 독립 합성 Git 두 개, runtime 조회 격리/모듈 비실행/동시 변경 반례. 전체는 GitHub.
- Target Platform: Linux/Mac, 현재 실행기의 후보용 prefix를 조회한다. 가상환경을 만들지 않는다.
- Project Type: 설치 전 독립 명령줄 점검 도구.
- Performance Goals: 입력32KiB/lock2MiB/Git3초·출력64KiB/결과16KiB, local 합성만 짧게 수행.
- Constraints: 서버·키·수익·장부·기존6파일·권한·등록·수집·배포 경계 불변.
- Scale/Scope: 후보 한 개/최상위 모듈16/의존성32의 제한된 지역 비교.

## Constitution Check
I/II 주문·종목·한도에 접근하지 않음; III 외부 모델 호출0; IV 장부/감사 변경0; V 비밀·계좌·환경 전문 읽기/출력0;
VI 과거검증→소액실전→전체실전의 단계 불변; VII 외부 API 호출0; VIII.A 장중 배포 제한 불변;
IX Kernel/안전 경계 불변; X main 자율 배포를 정지하지 않고 독립 비교만 추가한다.
돈 경로 없음. 90초/60세션/495미개봉/최소36/비용/계좌/권한 관문을 대체하지 않는다. 설계 후 재점검 통과.

## Project Structure
- scripts/intraday_frozen_context.py: 표준 라이브러리 읽기 전용 도구.
- tests/unit/test_intraday_frozen_context.py: 두 합성 저장소와 경계 반례.
- .github/workflows/frozen-context-checks.yml: 정확 PR 코드 전체 검사/XML/린트, 비밀·가격·서버 없음.
- specs/213-frozen-context/: 명세·계획·연구·자료구조·계약·빠른검사·작업·결과.
- AGENTS/.specify/HANDOFF: 실제 이어받기 포인터와 완료212 근거.

## Complexity Tracking
헌법 예외 없음. 파일 전체의 지속 불변을 새 키나 서명으로 인증하는 복잡한 경로는 만들지 않는다.
실패 시 새 독립 도구를 삭제하면 기존 명령/진단/등록/전진 경로가 그대로 유지된다.

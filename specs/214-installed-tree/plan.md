# Implementation Plan: 설치 폴더 전체의 읽기 전용 파일 비교

**Branch**: `codex/214-installed-tree` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

## Summary
213의 버전·위치 비교는 설치 파일 전체를 묶지 않는다. 독립 도구가 미서명 기대 목록과 복사 이미지의 전체 항목을 비교한다.
MATCHED는 두 번의 지역 관측 일치이며 설치 출처·외부 Python·기동·등록·실행 허가는 미평가다.

## Technical Context
Python3.11/표준 라이브러리, 새 의존성 없음. Linux/Mac fd 기준 읽기.
입력4MiB/항목16384/경로1024바이트/깊이32/파일256MiB/합계1GiB/전체 관측2회·협력적120초/결과16KiB.
일반 파일·디렉터리만 지원하며 빈 파일/폴더 포함. 링크·hardlink·특수 비트·다른 장치 거절.
열린 디렉터리 fd 기준 자식 조회/읽기, O_NOFOLLOW·O_NONBLOCK, 파일/디렉터리 전후 및 각 전체읽기 종료 뒤 모든 항목 상태 재대조.
오류는 코드만 출력. 적대적 파일시스템·지속 불변 인증 아님. 합성만 로컬, 큰 실제이미지/전체회귀 GitHub.

## Constitution Check
I/II 주문·종목·한도 불변; III 외부판단0; IV 장부·감사 변경0; V 비밀 입력 금지·전문 출력0;
VI 단계/전략 관문 유지; VII 외부API0; VIII.A 장중배포 불변; IX Kernel/헌법/위험게이트 불변;
X 성과 없는 자격 주장0. 설계 후 재점검 통과. 90초/60세션·495미개봉·최소36·31/40bp·계좌·현금 관문 유지.

## Project Structure
scripts/intraday_installed_tree.py 독립 비교; tests/unit/test_intraday_installed_tree.py 합성 경계;
.github/workflows/installed-tree-checks.yml 비밀 없는 정확 전체/XML;
specs/214-installed-tree/ 전체SDD; AGENTS/.specify/HANDOFF 포인터/실제213 완료 근거.

## Complexity Tracking
실제 설치·서버기동/불변권한 추가0. 기존 등록 소비자0/자동전환·재서명·시계초기화0.
새 도구/검사 제거로 되돌린다. 전체 실행 환경과 실행자격 연결은 별도 등급3 SDD가 필요하다.

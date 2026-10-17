# Implementation Plan: 소스·설치 입력 합성 검증
**Branch**: codex/219-source-input-lab | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)

## Summary
218 계약 중 원래 입력 검사를 실행 가능한 비밀 없는 실험으로 만든다. 이미지 결합 전 단계이며 218 전체 또는 실제 매매 완료가 아니다.
## Technical Context
Python3.11 표준 라이브러리, GitHub Ubuntu /usr/bin/git, pytest/ruff. 추가 의존성 없음.
실제 lab은 GitHub Linux에서만, 로컬은 작은 함수 시험만. 전체12분/명령20초/출력64KiB/보고32KiB.
## Constitution Check
전후 모두 I~VII/VIII.A/IX/X 보존. 커널·헌법·위험/등록/주문/수집/예산 변경0. 등급3 검토, 풀 SDD.
60세션, 정확 전략 지문, HMAC, 승인 및 EDGE_CONFIRMED 관문은 기존 그대로다.
## Project Structure
scripts/intraday_source_input_lab.py: 고정 fixture 생성, bounded/no-follow 읽기, 독립 기대값 대조, 실제 Git 객체 검사, 변조 실험, 정리 후 보고.
tests/unit/test_intraday_source_input_lab.py: 환경/링크/변조/한도/보고 거짓 플래그 반례.
.github/workflows/source-input-lab.yml: 정확 head, 읽기 권한, 비밀0, 실제 lab 및 전체 회귀.
## Phase 0 / 1
research.md의 공식 Git 설정·인덱스·객체 계약을 적용. 기대값은 검사 대상이 아닌 controller에서 생성·보관한다.
임의 입력 CLI를 추가하지 않는다. 설치는 고정 비실행 toy bytes의 연결만 검증한다.
## Phase 2 / Validation
양성 후 각각 독립 fixture 사본의 반례를 실행한다. 모든 기대 실패를 실제 실패로 관측해야 lab 성공이다.
정확 원격 HEAD의 전체 회귀·원래 XML과 lab JSON 지문 보존. 하네스/인계/PR 품질 통과 뒤 merge.
## Rollback
추가 lab/workflow/tests/문서 포인터만 되돌린다. 제거 기능0, 실제 서버/장부/키/등록 수정0.

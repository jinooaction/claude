# Implementation Plan: 실행 검증의 코드 연결 보완

**Branch**: `codex/197-execution-source-identity` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary
기존38개 소스를 보존하고 검토된 로컬 의존 파일 목록을 고정한다. 상대 경로와 내용 지문을 함께 묶는 버전2 실행 지문을 만들고 필수 파일 오류는 ValueError로 거부한다. 등록·자격 발급 흐름은 바꾸지 않는다.

## Technical Context
Python3.11+, pathlib/hashlib/stat/json과pytest. 새 패키지·네트워크·계좌 접근 없음. Linux/macOS. 매 호출에서 파일 내용을 읽으며 검사 전후 파일 상태를 비교한다. 상태 기반 해시 캐시로 내용 검사를 생략하지 않는다.
실행 단계에는 고정 목록만 사용한다. 회귀 검사에서 목록의 로컬 절대·상대 import 및 package 초기화 누락을 찾는다. 계산 비용을 측정해 기록한다. 사용자 지정 소스 경로나 새 CLI는 없다.

## Constitution Check
등급3 검증 경계 강화. I/II 한도·허용목록 유지, III 모델 호출 없음, IV 감사 보존, V 비밀 읽기 없음, VI 기존60세션·체결 동등성·단계적 검증 유지, VII 외부 API 변화 없음, VIII.A 장중 배포 제한 유지, IX 독립 명세·검증·안전 변경 기록, X 권한·자본 자동 발급 없음. 설계 후 재점검도 동일하며 헌법·커널 파일 변경 없음.
기존 지문과 달라지면 등록/권한의 기존 불일치 거부를 유지한다. 과거 권한을 자동 이전하지 않는다. 되돌림은 코드 배포를 되돌리는 것이며 원본·등록·관측·감사를 삭제하지 않는다.

## Project Structure
- `src/auto_invest/execution/intraday_identity.py`: 소스 목록과 일관된 파일 지문 읽기.
- `src/auto_invest/execution/intraday_signals.py`: 후보·공급자에 버전2 소스 지문 연결.
- `tests/unit/test_intraday_identity.py`: 변경·의존 목록·파일 오류·재현성·문서 비영향.
- `tests/unit/test_intraday_qualification.py`: 과거 지문의 실제 자격 거부.
- 본 폴더: 설계 및 실제 검사·배포 근거.

## Implementation sequence
재현 반례 실패 → 기존 소스 보존/의존 목록 검토 → 검사기·버전2 연결 → 자격 불일치·자체 시험 → 전체 회귀·린트·하네스·인계 → PR·배포 확인.

## Complexity Tracking
전체 저장소 해시는 무관한 연구 변경까지 검증을 무효화하므로 사용하지 않는다. 런타임 AST 탐색은 매 주문 전 지연과 범위 혼동을 만들므로 사용하지 않는다. 기존 후보/등록/권한 구조를 교체하지 않는다.

# Implementation Plan: 공개 보고서 JSON 보호
**Branch**: `codex/217-sidecar-json-redaction` | **Date**: 2026-10-16 | **Spec**: [spec.md](spec.md)

## Summary
기존 .json/.jsonl의 구조 기반 가림을 Markdown JSON 코드 블록에도 적용한다.
기존 텍스트 정규식은 유지하며 전체 구조를 가린 뒤 다시 텍스트 가림을 적용하지 않는다.

## Technical Context
**Language/Version**: Python 3.11+
**Primary Dependencies**: 표준 json/re/pathlib, 새 의존성 없음
**Storage**: 기존 LAST_RUN.md·JSON·JSONL
**Testing**: pytest, ruff, 기존 GitHub 전체 회귀
**Target Platform**: Linux Actions, 로컬 Mac
**Project Type**: 공개 전 파일/표준 입력 CLI
**Performance Goals**: 보고서 줄 순회, 외부 호출 0회
**Constraints**: 비밀값 유지 금지, 손상 수치 추정 금지
**Scale/Scope**: 기존 32개 발행 workflow가 공통 스크립트를 사용

## Constitution Check
- I/II/III: 주문·한도·종목·LLM 호출 변경 없음.
- IV: 감사·과거 공개 기록 수정 없음. 승인된 대사 복구 결과와 새 코드의 효과 구별.
- V: 기존 sensitive key/문자열 마스킹 재사용, 계좌 NAV 별칭 추가. 비밀 반례 필수.
- VI/VII: 단계 승격·외부 API 호출 변경 없음.
- VIII.A/IX: 일반 배포 시간과 검증 관문 유지. 커널 목록 해당 경로 없음.
- X: rung0 진입, 20% 초과 EDGE_CONFIRMED, 정확 전략 지문 및 holdout/forward/canary/broker/NAV 부재 차단 유지.
- 설계 후 재검사: 위반 없음. 안전 경계 등급3과 커밋 문구 `this changes the safety perimeter` 기록.
- 헌법/커널 수정 불필요. 실자본 변화 없음.

## Project Structure
- `scripts/redact_public_sidecar.py`: 블록 구분/유효 JSON 재귀 가림.
- `tests/unit/test_public_sidecar_markdown.py`: 수치·비밀·구분선·CLI·소비자 반례.
- `.github/workflows/volume-priority-checks.yml`: 스크립트/테스트 정확 경로로 기존 전체 회귀 연결.
- `specs/217-sidecar-json-redaction/`: 요구·설계·시험·결과.
- `AGENTS.md`, `.specify/feature.json`: 활성 포인터.
- `HANDOFF.md`: 승인 복구/기존 PR891/새 보정/미완료 구분.

## Implementation
순차 줄 탐색으로 backtick/tilde 최소3개, 최대3칸 들여쓰기의 코드 구분선을 인식한다.
JSON 언어 표시만 구조화하고, 다른 코드 블록은 통째 텍스트로 처리해 내부 가짜 구분선을 오인하지 않는다.
닫힘은 같은 문자/길이 이상이다. json.loads 성공 시 _redact_json_value 후 json.dumps;
실패/미닫힘은 기존 redact 처리. 파싱뿐 아니라 재귀 가림·직렬화의 ValueError/RecursionError도 기존 보호로 복귀한다. CLI 파일 일반 경로와 stdin에 연결한다.
JSON 파일과 JSONL 파싱은 그대로 둔다. 계좌 NAV 필드도 모든 구조화 경로에서 가린다.

## Verification and Rollback
수정 전 긴 소수 파싱 실패를 재현한다. 파일/디렉터리/stdin, 중첩·복수·비밀값·멱등성·손상 기록·소비자 파싱을 검증한다.
기존 보안 및 자금 정렬 검사, 정확 HEAD 전체 회귀·린트·strict 하네스·인계·PR 본문 검사를 한다.
정규 배포·새 보고서 적용과 이미 손상된 과거 보고서를 구분한다.
되돌림은 검토된 revert PR이며 기존 regex/JSONL 경로는 보존되어 있다.

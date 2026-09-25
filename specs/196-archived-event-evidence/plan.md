# Implementation Plan: 과거 보관 사건의 근거 검사

**Branch**: `codex/196-archived-event-evidence` | **Date**: 2026-09-25 | **Spec**: [spec.md](spec.md)

## Summary

오프라인 검사기와 CLI를 추가한다. 실제 Common Crawl 응답·metadata·warcinfo의 연결을 검증하고 공개 코드 검토에 따른 조건부 시각을 보고한다. 기존195의 현재 관측 가져오기·조회는 변경하지 않는다.

## Technical Context

Python 3.12+, 표준 라이브러리 hashlib/json/zlib/datetime/html.parser. 새 패키지·네트워크 요청 없음.
압축 및 해제 기록 각각 10 MiB, 고정된 세 파일, gzip 단일 멤버만 허용한다.
Linux/macOS CLI. pytest 단위·CLI·실물 검사와 ruff·하네스·인계 검사를 수행한다.

## Constitution Check

I~II 포지션·허용 종목 변화 없음. III 모델 호출 없음. IV~V 감사 삭제·비밀값 접근 없음.
VI~VII Backtest → Canary → Full 및 외부 API 방어 유지. VIII.A 기존 장중 배포 제한 유지.
IX 별도 브랜치·명세·검증·PR, 커널 변경 없음. X 입력 연구 결과를 승격·자본 권한으로 해석하지 않는다.
설계 후 재점검도 동일하다. 헌법 예외 없음.

## Project Structure

- `src/auto_invest/analytics/archived_event_evidence.py`: 제한된 파싱, 근거 연결, 조건부 시각.
- `scripts/archived_event_evidence.py`: inspect 명령.
- `tests/unit/test_archived_event_evidence.py`: 구조·지문·연결·시각 반례.
- `tests/integration/test_archived_event_evidence_cli.py`: CLI, 덮어쓰기·실패 동작.
- 본 폴더: research/data-model/contracts/quickstart/tasks 및 release-evidence.

## Implementation sequence

입력 형식 → 압축·WARC 파서 → 색인·기록 연결 → 인용·프로필 → CLI → 실제 자료 → 전체 검증·출시.
기존195를 일반화하는 리팩터링은 하지 않는다. 새 경로를 중단하면 되돌릴 수 있으며 원본은 보존한다.

## Complexity Tracking

단일 공급자 프로필부터 검증한다. 범용 크롤러·가격 재생·실주문 연결은 추가하지 않는다. 전체 단타 목표의 후속 요건은 유지한다.

# Implementation Plan: 고정 공시 시각 자료의 연구용 검증

**Branch**: `codex/201-earnings-clock-input` | **Date**: 2026-10-02 | **Spec**: [spec.md](spec.md)

## Technical context and structure

Python 3.11, DuckDB 1.4.1 개발 의존성, 외부 호출 없는 단일 오프라인 명령.
`source-manifest.json`에 공급자 개정·SHA-256·30개 CIK·시장 날짜 범위를 고정한다.
`scripts/earnings_metadata_audit.py`가 원본 지문과 137 본문 연결을 확인한 뒤
`Item 2.02` 사건을 결합한다. `tests/unit/test_earnings_metadata_audit.py`는
날짜 차이·과거 자격 거절·원본 변조·기업 불일치를 검증한다.
`.github/workflows/filing-observation-checks.yml`은 이 연구 경로가 바뀌면
원격 전체 회귀와 연구 명령 린트를 실행한다.

## Constitution check

I/II: 거래 허용 종목이나 포지션 한도는 변경하지 않는다. 연구용 30개 목록은
허용 목록이 아니다. III: 실행 중 LLM 호출이 없다. IV/V: 기존 주문 감사·비밀값을
읽거나 쓰지 않는다. VI/X: `Backtest -> Canary -> Full` 단계와 실거래 승격 근거를
대체하지 않는다. VII: SEC 403을 우회하려고 요청 한도나 차단을 회피하지 않는다.
VIII.A: 장중 생산 코드 배포와 무관한 연구 도구다. IX: 커널·주문 경계 변경 없음.
원본 공급자의 접수 시각 주장은 `specs/195-earnings-event-inputs/spec.md`의
로컬 관측 시각과 구분한다.

## Design, verification, rollback

1. 출처·개정·원본 지문을 먼저 검사한다. 계보가 바뀐 두 종목은 가격 평가 전에
   제외 표기한다.
2. 8-K 접수 표의 accession 중복·시각/시간대 누락과 로컬 본문의 기업 연결을
   거절한다. `filing date`와 접수 날짜를 합치지 않는다.
3. 실적 사건을 accession+CIK로 연결하고 고정 XNYS 달력에서 접수 기준 세션을 계산한다.
   공급자가 주장하는 `knowledge_date` 일치 여부를 기록하되 과거 공개 증거로 쓰지 않는다.
4. 출력은 새 파일로만 쓰고 연구·실거래 자격을 모두 거짓으로 고정한다.
   변조 반례·실제 자료 재생·린트·하네스·HANDOFF 사실성·원격 전체 회귀 후 병합한다.
5. 오류가 발견되면 새 도구와 포인터/CI 경로를 되돌린다. 기존 공시 원본과
   관측·감사 기록은 삭제하거나 덮어쓰지 않는다.

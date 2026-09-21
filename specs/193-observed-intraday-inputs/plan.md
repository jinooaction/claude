# Implementation Plan: 누락 보존 연구 입력

**Branch**: `codex/193-observed-intraday-inputs` | **Date**: 2026-09-21 | **Spec**: [spec.md](spec.md)

## Summary
독립적인 관측 라이브러리와 읽기 전용 감사 CLI를 추가한다. 기존 전략 엔진의
완전봉 입력을 바꾸지 않는다. 날짜/시각의 예상 격자와 실제 관측을 분리하고,
각 조회에 as_of를 요구해 미래 관측이 과거 적격성을 바꾸지 못하게 한다.

## Technical Context
Python3.11, 기존 pandas/exchange_calendars, pytest/ruff를 사용한다.
원본은 명시된1분 CSV와 SHA256 manifest, 출력은 새 JSON 파일이다.
Mac/Linux 오프라인 분석이며 네트워크·DB·broker import는 없다.
30종목은 종목별 순차 적재해 메모리를 제한한다. 현재2종목 실제 자료로 우선 검증한다.
Parquet 변환은 로컬 자료 준비로 분리하고 생산 의존성에 pyarrow를 추가하지 않는다.

## Constitution Check
I/II 한도·허용종목, IV 감사 기록, V 비밀값, VI 단계적 승격,
VII API 장애 대응, VIII.A 장중 배포 제한, IX 커널 경계, X 측정 관문을 보존한다.
실계좌/돈 경로를 호출하지 않고 연구 보고서에 live_eligible=false를 고정한다.
기존177~192 판정과 자금20% 초과 EDGE_CONFIRMED 조건에 영향 없음.
설계 전후 위반 없음. 전략 승격용 증거가 아닌 입력 검사이며 미확인 가격 연결은
명시적으로 남긴다. 운영 포인터 변경 때문에 등급2 검사와 인계가 필요하다.

## Project Structure
- `src/auto_invest/analytics/observed_intraday_inputs.py`: 고정 범위·원본 검증·격자·관측 조회.
- `scripts/observed_intraday_probe.py`: CSV manifest 감사 전용 CLI.
- `tests/unit/test_observed_intraday_inputs.py`: 인과성/달력/누락 반례.
- `tests/integration/test_observed_intraday_cli.py`: 입력 지문/보고서/실패 코드.
- `specs/193-observed-intraday-inputs/`: 명세, 설계, 작업 목록, 실제 검사 결과.

## Design and validation
신규 타입으로 희소성을 표현한다. 기존 Bar/Dataset는 완전봉 의미를 가지므로
불완전 봉을 그 타입으로 위장하지 않는다. XNYS는 명시된 시작/끝 범위로 구성한다.
관측 종료≤as_of인 봉만 집계/거래량 조회에 사용한다. 시가 조회는 minute start를
가격 프록시로 반환하되 시가 체결 가능 보장은 하지 않고, 양의 거래량 검사는
해당 분봉 종료 후에만 가능하다. 정확 시각과 이후 관측은 서로 다른 결과 유형이다.
조회 실패가 보유 삭제를 유발하지 않도록 이 모듈은 포지션이나 PnL을 변경하지 않는다.
매수/청산의 미해결 처리 연결은 미래 전략 호출부가 책임지며193은 관측 계약을 제공한다.
검증은 불규칙분봉/빈날/조기폐장/DST/미래 데이터 변조/0거래량/무한청산부재와
기존192 회귀, 실제2종목 달력 대조, 전체pytest/ruff, 하네스/인계 순서다.

## Complexity Tracking
기존 로더의 예외를 풀지 않고 별도 모듈을 두는 이유는 기존 결과 재현성을 보존하기 위해서다.
기능 제거 없음. 실패하면 신규 CLI 사용을 중단하고 활성 명세 포인터를192로 되돌린다.

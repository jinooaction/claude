# 구현 계획: 단타 수집·지속 운용

**Branch**: `codex/181-intraday-runtime` | **Date**: 2026-09-06
**Spec**: [spec.md](spec.md)

## Summary

기존 177의 순수 연구 엔진을 유지하고 공급자 어댑터와 별도 지속 모의 실행기를 추가한다.
연구 함수의 신호 계산을 재사용하지만 실행 모형은 별도 지문으로 고정한다.
실제 자료 접근과 실거래 자격이 없음을 오류 코드·상태·미완료 작업에 남긴다.

## Technical Context

Python 3.11+, 기존 httpx/exchange_calendars/SQLite만 사용한다. 공급자 원본 JSON과
177 CSV/manifest는 별도 출력 디렉터리에 보존한다. 모의 상태는 전용 SQLite의 추가 전용
사건에 매 봉 상태와 해시 체인을 저장한다. BEGIN IMMEDIATE 아래 중복검사와 상태전이를
원자적으로 수행한다. 한 프로세스당 공급자 요청은 초당 2회 이하, 4회 재시도 상한이다.
5종목×18후보, 5분 입력을 다루며 CLI는 한 번 실행 및 반복 실행을 지원한다.

## Constitution Check

- I/II: 가상자본 100,000달러, 주문·종목 20%, 전체 80%, 정수주·현금·고정 지정가만.
- III: 봉당 LLM 호출 없음.
- IV: 별도 모의 사건 추가 전용, 원자적 상태전이, 해시 체인 확인. 거래 DB 접근 없음.
- V: 공급자 키는 환경에서 읽고 로그/장부에 기록하지 않음. 임의 주소 요청 금지.
- VI/X: 177 합격/60세션/강화 캐너리/라이브 지문 검증을 대신하지 않음. 자본 0.
- VII: 공급자 요청 제한·유한 재시도·회로차단, KIS 인증은 기존 캐시/갱신 재사용.
- VIII: 기존 배포 경로 유지. 새 주문 서비스나 실거래 예약을 설치하지 않음.
- IX: 헌법·커널 변경 없음. 이후 반복 실주문은 현 하루 1회 경계와 다르므로 별도 등급4.

설계 전후 모두 같은 판단이다. 지금 실거래를 열 수 있다는 계획이 아니다.

## Project Structure

- `src/auto_invest/market_data/intraday.py`: 공급자 수집·정규화·불변 배치 내보내기
- `src/auto_invest/analytics/intraday_runtime.py`: 영속 모의 주문·체결·복구
- `scripts/intraday_runtime.py`: collect/paper/run/status, 제한된 반복 실행
- `tests/unit/test_intraday_data.py`, `tests/unit/test_intraday_runtime.py`
- `tests/integration/test_intraday_runtime_cli.py`

## 검증과 구현 순서

공급자 계약 시험 → 수집기 → 상태 전이 시험 → 실행기 → CLI 통합 → 전체 검증/PR.
KIS 정상 거래소는 고정 ETF 매핑(QQQ/TLT=NAS, 나머지=AMS), 실제 응답 계약이 맞지 않으면 실패한다.
KIS 자료는 역사 SIP와 섞지 않는다. 소급 수집 자료를 전진 관찰로 세지 않는다.
누락·지연은 신규 진입 차단, 청산은 정규장 고정 지정가로만 진행한다.
모의 일손실 2% 정지는 후보별 계좌에만 적용하며 다른 후보의 결과에 영향을 주지 않는다.
체결량 한도는 이전 확정 봉 평가액으로 계산하고 현재 종가는 이후 신호·손실 판단에만 쓴다.

## Complexity Tracking

여러 데이터 공급자를 붙이지만 각각 역할이 다르다: 장기 역사 vs 계좌 시세 관측.
공통 신규 HTTP 계층은 고정된 읽기/인증 endpoint만 노출한다. 범용 주문 프록시가 아니다.

## 서버 실제 자료 계약 점검

`market_data/intraday.py`에 마지막 완결 세션 선택과 정확한 5종목×세션 시간 집합
검사를 추가한다. `tests/integration/test_live_broker.py`의 기존 KIS_LIVE_TEST 경계
안에서 동일 서버 토큰 캐시로 수집하고 정화 요약만 출력한다. 분봉 API 원문·키는
공개 로그에 출력하지 않는다. `tests/unit/test_intraday_data.py`에서 주말·장중·
누락·정상 봉 수를 먼저 검증한다. 기존 gateway/helper는 변경하지 않는다.

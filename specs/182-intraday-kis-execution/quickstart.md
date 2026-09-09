# 검증

실제 계좌의 읽기 전용 대조는 기존 인증 환경에서 다음 명령으로 실행한다.
`uv run python scripts/intraday_balance_check.py`
새 `report_audit`에 항목별 일치(MATCH), 불일치(MISMATCH), 검사 불가(INCOMPLETE),
조회 중 변경(CHANGED)이 표시된다. 계좌 금액과 종목은 공개 출력에 포함하지 않는다.
`status=BALANCE_REPORTS_OBSERVED`와 종료0은 조회 성공이며 산술 합격을 뜻하지 않는다.
산술 MATCH도 현금 합산 계약·전체 계좌 범위·실시간 평가시각의 검증을 대신하지 않는다.

account_assets는 국내외 자산·예수금 등을 포함하는 별도 결제기준 분류표 대조다.
현재 계좌 상품의 공식19/16개 분류와 합계, 두 조회의 안정성을 검증한다. 같은 명령에서
자동 수행하며 추가 계좌·가입·키는 필요없다. 숫자가 빠지거나 분류표가 바뀌면 명확히
조회 실패로 남긴다. 이 분류표의 MATCH도 실시간 USD 현금·실주문 승인은 아니다.

1. `uv run pytest tests/unit/test_intraday_execution.py tests/integration/test_intraday_execution_contract.py`
2. `uv run python scripts/intraday_execution.py rehearse`
3. `uv run pytest`, `uv run ruff check src tests`
4. strict harness, HANDOFF사실검사, PR품질관문.
기존181 KIS서버 timer는 유지한다. rehearsal은 네트워크·실제키를 사용하지 않는다.

## 자본 검토
사용자용 금액 비교와 재현 명령은 [검토안](capital-review/README.md)에 있다.
`uv run pytest tests/unit/test_intraday_capital_review.py`로 실제 신호 계산과의 일치,
정수주 경계, 잘못된 입력, 계좌·네트워크 무접근을 검증한다.
검토 설정을 읽는 생산 서비스나 실거래 시작 명령은 없다.

## 확정 한도 준비 검사
`uv run python scripts/intraday_execution.py preflight`는 확정600/12 설정과
실제 실행기의 모의 주문 수명을 검증한다. 매개변수 변경/실거래 스위치는 없다.
`uv run pytest tests/unit/test_intraday_preparation.py tests/unit/test_intraday_account.py`
는 한도·손실 정지 경계와 KIS 계좌GET 계약을 검사한다.
실서버 검증은 기존 kis-smoke.yml이며 새 계좌 검사도 GET만 사용한다.
과거자료/전진검증/검증된NAV/생산주문은 이 시험 결과와 구분한다.

## 실행 관측 입력 검사

`uv run pytest tests/unit/test_intraday_execution.py tests/unit/test_intraday_preparation.py tests/integration/test_intraday_execution_contract.py`

매도가능수량·시세 발생시각의 누락/범위, 새 매수·매도 차단, 기존 취소 보존,
잠금 대기 중 노후화, on_bars 종료 취소를 확인한다. 모의 공급자의 시각은 모의 시각이며
KIS REST 수신 시각을 실제 발생시각으로 인정하는 생산 변환기는 추가하지 않는다.

### 잔고 결과 해석 보정

`balance-check` 내부 보고서 버전2의 checks/status는 동일 보고서 내부 검증이다.
comparisons의 DIFFERENT는 집계 기준의 동등성이 미입증인 두 숫자가 다르다는 뜻이다.
계좌 오류나 자동 주문 차단 원인으로 단정하지 않는다. EQUAL도 계약 합격을 뜻하지 않는다.
실제 계좌 전체 현금과 장중 순자산 검증 여부는 execution_nav_verified로 별도 확인한다.

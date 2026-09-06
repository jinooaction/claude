# 검증
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

# 자료 모형
Decision은 후보지문·확정봉UTC시각·종목별목표수량·고정지정가다.
AccountView는 조회시각·현금·평가액·계좌보유·가격·증권사미체결을 담는다.
실행claim은 지문/세션/봉/종목/목적으로 만든ID와 입력지문이며 추가전용이다.
claim이후 결과가 없으면 원주문을 찾고 증거없는 재전송은 금지한다.
ExecutionEvent는 claim·kind·정화JSON의 추가전용기록이다.
취소는 원correlation별 REQUESTED→ACKNOWLEDGED/UNCERTAIN 기록이며 종료가 아니다.
실제 FILLED 또는 미완결 종료 EXPIRED는 fill_sync가 확정하고 CANCEL 감사를 기록한다.
단타 체결 시각은 확인한 시각이다. 시간대가 확인되지 않은 주문접수 시각을 체결 시각으로 쓰지 않는다.
귀속보유는 단타rule ID의 확정fills합계로 계산한다. 다른 전략 보유는 팔지 않는다.

CapitalReview 입력은 schema_version=1, currency=USD, quote_as_of, quote_source,
prices(정확한 5종목의 양수 소수 문자열)이다. 예산은 명령의 소수 문자열로 별도 받는다.
출력은 mode=capital_review_only, 자금 변경/주문 0, live_eligible=false다.
예산·16% 목표·20/20/80 한도·2% 정지 발동 기준·가상 수량·최소 1주 예산을 담는다.
입력 파일 지문과 계산기/기존 실행 소스 지문을 남긴다. 승인으로 전이되는 상태는 없다.

ConfirmedPreparationBudget은 USD 자본600/주문120/종목120/총노출480/하루정지12와
준비기준 확정 출처다. orders_enabled=false, approval_scope=preparation_parameters다.
AccountSnapshot은 관측시작UTC, 관측종료UTC, USD 구매가능금액, 보유 수량/평가액,
미체결 주문ID/수량/방향을 담는다. NAV는 None, 계좌전체검증과 실거래 가능은 false다.
공개 검사 결과에는 금액·계좌번호·주문ID 원문 대신 계약 성공과 행 개수만 남긴다.

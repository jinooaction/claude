# 자료 모형
각 관측의 pagination_end는 EXPLICIT_END(D/E) 또는 NO_CONTINUATION(명시적 공란)이다.
헤더 누락과 알 수 없는 비공란 값은 고정 분류의 오류로 반환한다.
BalanceEvidence는 관측시작/종료UTC, 한국 결제기준일, 출처별3개 output행 수와
통화별 보고 금액 행을 갖는다. output2만 crcy_cd/frcr_dncl_amt_2를 추출한다.
빈 통화는 별도 개수로 보존한다. 같은 USD 행도 중복 제거/합산하지 않는다.
current_read_stable은 처음과 마지막 현재잔고 output2가 동일함을 뜻한다.
reported_usd_field_comparison은 EQUAL/DIFFERENT/UNAVAILABLE이다.
수치 동일성은 가용현금·예수금·NAV의 의미 동일성을 뜻하지 않는다.
공개 결과에는 수치/통화/종목/계좌 원문 없이 개수와 판정만 포함한다.
nav_verified/cash_verified/live_eligible는 모두 false, orders_submitted는0이다.

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
unverified_assets는 실제 OTCB 행을 종목별로 분리 보존한다. 보고 수량은 소수 문자열,
reported_market_code=OTCB, valuation_verified=false, reported_valuation_usd=None이다.
정상 보유·주문 대상에 합치거나 평가액0으로 치환하지 않는다. 공개 결과는
unverified_asset_count와 INTRADAY_ACCOUNT_READ_WITH_UNVERIFIED_ASSETS로 구별한다.
USD 외화증거금 내역 미제공은 reported_cash_components=None,
usd_margin_reported=false, USD_MARGIN_COMPONENTS_NOT_REPORTED로 표시한다.
공개 결과의 usd_margin_reported도 false이며 계좌 검증·거래 준비로 승격되지 않는다.
unclassified_margin_row_count는 통화 문자열이 공란인 행의 수다. 그 행의 금액을
USD·합계·현금0으로 해석하지 않고 UNCLASSIFIED_MARGIN_ROWS_PRESENT를 남긴다.

reported_cash_component_rows는 응답 순서의 USD 구성금액 목록이다. 각 항목은
frcr_dncl_amt1, ustl_buy_amt, ustl_sll_amt, frcr_rcvb_amt, frcr_mgn_amt,
frcr_gnrl_ord_psbl_amt의 검증된 문자열만 포함한다. 원문 전체나 국가명을 복제하지 않는다.
같은 값도 별도 행으로 보존한다. usd_margin_row_count는 목록 길이이며,
reported_cash_components는 길이1일 때만 해당 항목, 나머지는 None이다.
cash_aggregation_verified는 항상 false, 여러 행이면 USD_MARGIN_AGGREGATION_UNVERIFIED다.
공개 account_read_complete=true는 GET 조회/형식 계약 완료다. 공개 issues는 고정 코드
목록이며 자산 경고가 현금 경고를 숨기지 않는다. 금액/계좌 식별자는 공개하지 않는다.

실행 Observation.sellable_positions는 positions와 같은 종목 집합의 정수 수량이다.
0 <= sellable <= holding을 요구한다. mark_times는 marks와 같은 종목 집합의
시간대 있는 datetime이다. 증권사 발생시각을 보존하며 관측/최종 주문 시점 대비
0~30초 범위만 사용한다. 두 필드 모두 필수다. 기존 GET AccountSnapshot을
Observation으로 승격하는 형변환은 없으며 모의 공급자만 모의 자료로 이를 채운다.

US9의 audit_records는 현재잔고의 output1/2/3에서 검증에 필요한 허용 필드만
복사한 메모리 자료다. 파일·공개 로그에 저장하지 않는다. report_audit는 금액 없는
검사명·MATCH/MISMATCH/INCOMPLETE/CHANGED·행 번호·오류 필드를 제공한다.
최대100개 검사 상세와30개 오입력 상세만 공개하지만 총개수·상태별 개수와 전체 판정은
모든 행을 반영한다. 실행 NAV 검증과 현금 합산 계약 상태는 별도 필드다.

# 명령 계약

`uv run python scripts/intraday_balance_check.py`
공식 서버의 체결기준→결제기준→체결기준 잔고 GET 대조다. KIS_APP_KEY,
KIS_APP_SECRET, KIS_ACCOUNT_NO와 기존 KIS_TOKEN_CACHE_PATH 환경을 사용한다.
필수 환경 누락은 DATA_ACCESS_REQUIRED/exit2이며 요청·캐시 생성이 없다.
정상은 BALANCE_REPORTS_OBSERVED/exit0이며 행 수·안정성·보고 수치의 비교 결과만 출력한다.
출처별 pagination_end는 명시 종료와 명시적 공란의 연속조회 없음을 구분한다.
조회 실패는 닫힌 오류/exit2이며 일부 페이지를 성공으로 반환하지 않는다.
EQUAL은 수치만 같다는 뜻이고 현금/NAV/실거래 검증은 false다. URL·주문·활성화 인수는 없다.
운영자는 별도 키 발급이나 복사 없이 기존 서버 KIS smoke에서 같은 함수를 사용할 수 있다.

`uv run python scripts/intraday_execution.py rehearse`
계좌·URL·키·--live 인수를 받지 않는다. 임시DB와 MockTransport로만 실행한다.
매수→부분체결→취소접수→추가체결→최종취소→청산을 확인한다.
schema_version=182, mode=offline_rehearsal, orders_submitted=0,
live_eligible=false, simulated_broker_requests와 invariant결과는 별도 표시.
성공exit0, 실패exit2. 실제자료·전략합격·실계좌 체결증거가 아니다.
생산활성화 CLI는 없다. coordinator는 권한guard가 없으면 broker접근 전 거절한다.

## 자본 검토
`uv run python scripts/intraday_capital_review.py --prices <JSON> --capital-usd 600.00`
표준 출력 JSON만 생성한다. --live, --approve, 계좌/키/URL 인수는 없다.
정상 계산 exit0은 검토 완료이며 실거래 가능이 아니다. 잘못된 입력 exit2다.
예산과 같은 가상 전용 현금, 보유 0, 모든 종목에 매수 신호가 있다고 가정하여
고정 종목 순서대로 현금 여유분을 차감한다. 실제 주문 제안이나 신호가 아니다.
가격마다 실제 컴파일러의 지정가 반올림을 적용하며 최소 예산은 센트 단위 올림이다.
2%는 손실 정지 발동 기준이고 최대 손실 보장이 아니다.

## 확정 한도 사전점검
`uv run python scripts/intraday_execution.py preflight`
기본 confirmed-budget.json의600/12를 검증하고 가짜 계정·임시 장부·MockTransport로
주문 수명을 재현한다. 성공 exit0은 준비 코드 검사 성공이며 live_eligible=false다.
임의 한도·실거래·승인 스위치는 없다. 기존 rehearse 명령은 원래 동작을 유지한다.
실제 계좌 GET 수집 계약은 기존 KIS_LIVE_TEST 읽기 검사를 통해 서버에서 검증한다.
OTCB 자산 행이 있으면 읽기 시험 성공도 INTRADAY_ACCOUNT_READ_WITH_UNVERIFIED_ASSETS를
출력하며 미검증 자산 수를 표시한다. 이는 조회 형식 확인일 뿐 계좌 준비/거래 승인이 아니다.
USD 구성 내역이 없으면 usd_margin_reported=false가 함께 출력된다. 미검증 자산이
없어도 USD 내역 미제공은 INTRADAY_ACCOUNT_READ_WITH_UNVERIFIED_CASH다.
공란 통화 행도 unclassified_margin_row_count로 공개 집계되며 미검증 현금 경고를 남긴다.

USD 여러 행은 조회 오류가 아니다. usd_margin_row_count와
USD_MARGIN_AGGREGATION_UNVERIFIED를 공개하며 금액을 합산하지 않는다.
account_read_complete=true와 cash_aggregation_verified=false는 동시에 가능하다.
공개 issues에 모든 미검증 사유가 남으므로 자산 경고도 현금 경고를 가리지 않는다.
행 수와 무관하게 NAV와 live_eligible는 false, 실제 주문은0이다.

rehearse/preflight의 모의 공급자는 매도가능수량과 각 가격의 모의 발생시각도
기존 실행기에 전달한다. CLI 인수·출력 모드·비밀값 무접근은 유지된다.
새 실제 주문 시작 명령이나 KIS 실시간 시세를 받았다는 출력은 추가하지 않는다.

`uv run python scripts/intraday_balance_check.py`는 기존 세 GET 결과에 report_audit를
추가한다. 개별 산술 대조와 누락·변경을 표시하며 새 인수나 비밀값 경로는 없다.
조회 exit0과 산술 MATCH 및 전체 계좌/실행 NAV 승인은 서로 다른 상태다.
기존 서버 test_live_kis_intraday_balance_evidence도 같은 결과를 공개한다.

원화 합계 불일치에는 안정된 USD 자료일 때만 단위·정밀도 가설 diagnostic이 추가된다.
환산 전 합과의 수치 일치나 센트 환산 범위 안이라는 결과를 합격 또는 원인 확정으로
해석하지 않는다. 금액 비공개·조회 횟수·30초 제한·실행기 연결 금지는 변하지 않는다.

US10부터 같은 balance-check 명령은 기존 해외 세 GET 후 전체 자산 두 GET을 수행하고
별도 account_assets 결과를 함께 출력한다. 각 관측 배치는 독립30초 제한이며 다른 기준을
동일 시점 NAV로 합산하지 않는다. 전체 자산 오류도 종료2/FAILED이며 부분 성공으로
가리지 않는다. 기존 서버 읽기 검사에는 test_live_kis_account_asset_table을 추가한다.

US11의 report_audit/account_assets는 schema_version=2다. checks와 status는 보고서
내부 검증이며 별도 comparisons는 서로 다른 출력의 숫자 관계일 뿐이다. 소비자는
DIFFERENT를 계좌 대사 실패로, EQUAL을 실시간 NAV 인증으로 바꾸면 안 된다. 미지원
버전을 임의 해석하지 않는다. 공개 GET 횟수·금액 비노출·실행권한 부재는 유지한다.

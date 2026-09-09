# 조사 결정

## 2026-09-10 체결통보 원본의 실제 한계 확인

공식 포털의 실시간체결통보 속성 원본(fef3c007-4a03-4b3b-9d08-310b88912877)을
직접 조회했다. STCK_CNTG_HOUR 설명은 특정 거래소에서 체결 시각을 보내지 않으며
수신 시각 기록을 대안으로 안내한다. 따라서 H0GSCNI0 추가만으로 확정 체결일·시각을
복원한다고 설계하지 않는다. T029의 관측 시각 출처 구분을 유지한다.

같은 통보의 CNTG_QTY는 주문 통보에서 주문 수량, 체결 통보에서 체결 수량이며
CNTG_YN의1/2 구분 없이 누적 장부에 넣을 수 없다. 미국 CNTG_UNPR는 소수4자리
생략 형식이고 ODER_COND는 NASDAQ6/NYSE7/AMEX8/OTCB9다. 단순25필드 나누기나
수신만으로 현금/수수료 증거를 발급하지 않는다. 개인 계좌 통보에는 HTSID 구독과
암호화 처리가 필요하며 이 확인 중 실제 구독·주문은 수행하지 않았다.

공식 일별거래내역 속성(8e874fea-8e55-464d-b535-75df64fc3048)도 직접 확인했다.
매매일/결제일과 수수료·정산금액은 있으나 주문번호 연결 필드는 없다. 따라서 T031의
제공된 조회들 간 합계 일치가 개별 주문 수수료 인증이나 전체 계좌 범위 인증은 아니다.
등록일/주문일 구간을 같은 거래 집합으로 보장하는 계약, 전체 현금 원본, 실제 모델/체결
검증 제공자는 계속 미완료다. 관찰60일이나 승인 파일로 이 코드 공백을 덮지 않는다.

- https://apiportal.koreainvestment.com/api/apis/guide/property/fef3c007-4a03-4b3b-9d08-310b88912877
- https://apiportal.koreainvestment.com/api/apis/guide/property/8e874fea-8e55-464d-b535-75df64fc3048

- KIS 포털 HDFSCNT0은 RSYM 포함 26필드. GitHub 예제의 25필드에는 RSYM이 빠져
  자동 대체하지 않는다. KYMD/KHMS와 XYMD/XHMS를 각각 한국·뉴욕으로 읽어 교차 검증한다.
  6자리 날짜는 수신 연도의 앞 두 자리로 복원하고 수신 날짜와 1일 이내인지 확인한다.
- websocket 전송은 공식 문서의 asyncio client를 사용하며 크기·대기·종료 상한을 둔다.
  인증이 포함된 프레임은 라이브러리 로그를 비활성화한 전용 logger로 전달한다.
- 외화 구매가능 금액 ovrs_ord_psbl_amt와 수량 max_ord_psbl_qty만 사용한다.
  통합 구매력과 현금·전체 순자산은 서로 다른 값이다.
- 전체 순자산 대안 검토: 같은 USD 여러 행의 합산 규칙 부재, 미니스탁 제외,
  장중 현금·보유 갱신 지연, 외부 현금 흐름 누락 때문에 시작 잔고 수동 입력을 자동 NAV로
  사용하는 안은 채택하지 않는다. 이는 소프트웨어 제작 금지가 아니라 미완료 입력 계약이다.
- 기존 PaperRuntime이 지속 장부를 제공하므로 중복 장부 구현 대신 호출부를 연결한다.

출처:
- https://apiportal.koreainvestment.com/api/apis/public/detail?accessUrl=%2Ftryitout%2FHDFSCNT0
- https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/delayed_ccnl/delayed_ccnl.py
- https://apiportal.koreainvestment.com/api/apis/public/detail?accessUrl=%2Fuapi%2Foverseas-stock%2Fv1%2Ftrading%2Finquire-psamount
- https://apiportal.koreainvestment.com/api/apis/public/detail?accessUrl=%2Fuapi%2Foverseas-stock%2Fv1%2Ftrading%2Finquire-present-balance
- https://websockets.readthedocs.io/en/stable/reference/asyncio/client.html
- https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/kis_auth.py
- https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/delayed_ccnl/chk_delayed_ccnl.py

공식 실행 예제의 접속 경로는 `/tryitout`이며 JSON PINGPONG에는 웹소켓 `pong`으로
응답한다. 기존 주입형 코드의 문자열 echo를 새 실제 전송에 그대로 복사하지 않는다.

후속 조사에서 공식 전체 API 메뉴와 해외주식 예제도 확인했다. 가장 가까운
`CTOS4001R inquire-period-trans`는 매매·결제 일자, 외화 정산금액과 수수료를 주지만
입출금·환전·배당 입금·이자 전체 사건 원장 및 전후 잔액은 제공하지 않는다.
`period-rights`는 계좌 실제 입금이 아닌 종목 권리 일정이다. 현재 공개 목록에서
시작 현금 이후 모든 현금 변동을 재현하는 해외주식 API를 찾지 못했다.
전용 계좌 선언만으로 이 관측 완전성을 증명하지 않는다. 2026-09-08 사용자가
기존 한국투자 계좌 계속 사용을 확정했다. 기존 계좌를 단타 전용으로 간주하거나
이미 확정한600/12를 다시 질문하지 않는다.

현재 코드 확인 결과 일일 잔고 대조는 `reconciliation/external_holdings.py`의 명시적
기준표를 체결 장부에 더하지만 단타 `IntradayExecutor._refresh`는 이를 빠뜨리고 있다.
동일한 계약을 적용해 기존 보유가 있다는 이유만으로 막히는 차이를 해소한다.
기준표는 단타 체결이나 실제 현금 증거가 아니며 누락 자산을 자동 등록하지 않는다.

- https://apiportal.koreainvestment.com/api/apis/public/detail?accessUrl=%2Fuapi%2Foverseas-stock%2Fv1%2Ftrading%2Finquire-period-trans
- https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/period_rights/period_rights.py
# 보관 자료 연결 조사

2026-09-10 시각 출처 조사: 공식 inquire_ccnl/chk_inquire_ccnl.py는 ord_dt와 ord_tmd를
주문일자/주문시각으로 명시한다. 현재 overseas._exec_ordered_at_utc도 해당 필드를
읽지만 fill_sync는 이를 체결 시각으로 복사했다. 과거 날짜의 주문이 나중에 관측된
시험에서 이 잘못된 동작을 성공으로 검사하고 있었다. 주문 시각 복사를 제거하고
관측 출처를 남긴다. 이 수정은 원본에 없는 실제 체결 시각을 복원하는 것이 아니다.
주문 복구의 시간대 해석 문제는 별도 조사 대상이며 이 수정으로 해결됐다고 주장하지 않는다.

- https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/inquire_ccnl/chk_inquire_ccnl.py

2026-09-10 거래/수수료 원본 조사: 공식 inquire_period_trans.py는 CTOS4001R과
등록일 ERLM_STRT_DT/ERLM_END_DT, FK100/NK100 연속 조회를 사용한다. chk 예제는
output1에 매매/결제일·상품·통화·체결수량·거래외화금액·외화정산금액·국내/해외
외화수수료를 정의한다. 주문번호는 이 매핑에 없으므로 행을 개별 주문에 임의 대응하지 않는다.
등록일 범위를 매매일 범위로 주장하지 않으며 요약을 페이지마다 합산하지 않는다.
공식 예제의 중간 오류 시 기존 부분 결과 반환은 실행 검증에 부적합해 채택하지 않는다.
이 경로는 KIS 계산식 문의 없이 읽을 수 있는 원본이다. 실제 현금·비용 검증 연결은 후속이다.

- https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/inquire_period_trans/inquire_period_trans.py
- https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/inquire_period_trans/chk_inquire_period_trans.py

현재181 service_cycle은 소스 식별자별 sessions/YYYY-MM-DD에 write_batch 결과를
보관한다. 실패한 YYYY-MM-DD-partial-uuid 폴더도 보존하므로 결합기는 명시적으로
개수를 기록하고 완료 거래일로 세지 않아야 한다. 기존177 자료 검증기는 개별 봉·CSV
지문·완결 세션을 검사하지만 여러 보관 폴더를 연결하지 않는다. 기존 연구 검증기는
정식 전진 관측을 수행하지 않는다. 새 연결은 원본과 CSV를 대조하고 하나의 연구 입력으로
합치며 756세션 기준·18개 후보·비용·선택 로직은 기존 구현을 재사용한다.
현재 API의 과거30일 조회 제한, 데이터의 부분 시장 성격, 실제 자료 부재를 이 연결로
해결했다고 주장하지 않는다. 정식60세션 연결과 실주문 입력·권한은 별도 미완료다.

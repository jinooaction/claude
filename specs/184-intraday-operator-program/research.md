# 조사 결정

## 2026-09-12 실제 증거금 행 구조 확인

PR805/main6b92ae1의 서버34684108577(11 passed/25.09초)은 원본9응답·장부순번5를
저장하고 금액을 공개하지 않는 구조 분석을 수행했다. USD10행은 국가명10종이며
예수금·미결제매수·미결제매도·미수·증거금5개 구성은 모두 동일하다. 예수금은 양수,
나머지4개는 모두0이다. 일반주문가능금액은5종이므로 국가별 주문 여력은 같지 않다.
다른 통화6행과 미분류34행은 조사한9개 숫자 필드가 모두 유효한0이다. 미분류 국가명은
전부 공란이다. 제외된 응답은0이며 계좌 인증/실주문 권한은 false다.

이 관측은 국가별 공통 현금의 반복 표시 가설을 뒷받침한다. 동일한 숫자 자체는 중복
제거 계약이 아니므로 첫행 선택으로 검증을 통과시키지 않는다. 다음 구현/확인은 같은
보관 배치의 독립 현재잔고/결제잔고 통화 행·외화 총액과 공통 예수금을 대조하는 것이다.
공식 HTS 총자산식과 함께 사용하고 실제 전체 계좌 범위·가격 시각 문제는 별도 유지한다.

## 2026-09-12 공식 HTS 총자산 계산 설명 재발견

공식 해외주식 HTS 안내 PDF의40쪽(페이지 인덱스39)은 해외증권 총자산을
원화예수금+외화예수금+해외주식평가금액+미결제매도금액-미결제매수금액으로 설명한다.
35쪽은 주문가능금액이 예수금에서 증거금과 제비용을 차감한 값임을 설명한다.
이는 새 계산 대조 후보의 공식 근거이며, 계산식 자체를 전혀 찾지 못했다는 전제로
자료 요청만 반복하지 않는다. 다만 과거 HTS 안내이므로 현재 OpenAPI 필드의 통화·범위·
CMA 포함 여부까지 자동 확정한 것은 아니다. PDF의 과거 시세/매도대금 재사용 안내를
현재 거래 규칙으로 적용하지 않는다.

현재 공식 예제의 output3은 dncl_amt, cma_evlu_amt, tot_dncl_amt, frcr_evlu_tota,
evlu_amt_smtl, ustl_sll_amt_smtl, ustl_buy_amt_smtl, tot_asst_amt, tot_loan_amt를
제공한다. 다음 대조는 저장된 동일 응답에서 총예수금/외화평가/주식평가/미결제 구성의
유효성을 확인하고 설명된 산술과 비교하는 것이다. 대출을 중복 차감하거나 통화가
다른 숫자를 합산하지 않는다. 숫자가 일치하더라도 전체 계좌 범위와 평가 시각 증명이
되지 않으며 기존 국내/기타 자산과 OTC 평가 문제를 별도로 유지한다.

- https://file.truefriend.com/Storage/research/hts_guest_0130.pdf (35·40쪽)
- https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py

현재 서버 원본은186/PR803에서 확보했고, PR805의 금액 비노출 구조 분석 검증이
진행 중이다. 그 결과와 위 공식 설명을 함께 사용해184의 계산 계약을 좁힌다.

## 2026-09-10 기존 서버 체결 장부와 시작 시점 방식

최신 automation/live-profit-evidence-last-run을 원격에서 다시 읽었다. 관측 시각
2026-09-09T21:52:22Z의 fills.log는 체결5건과 열린 주문0건을 보여 주며, 성과 보고서는
현재 전략 범위 체결2건이다. 원본 DB 전체 행을 직접 조회한 결과로 확대하지 않는다.
기존 실행 장부가 없다는 전제와 계좌 개설 이후 전체 거래내역 요구를 철회한다.
검증된 시작 상태+그 이후 변동/복구 조회가 목표이며 이전 체결을 다시 현금에 반영하지 않는다.
FR041은 먼저 기존 GET 원본·미체결·보유·외화 구성과 실행 장부 전후 순번을 비공개 보관한다.
장부 기록과 현금 출처 검증은 별개다. 외부 입출금·환전 등을 포함한 실제 순현금 대조와
자격/최종 통합은 아직 연결되지 않았고 이 기능의 서버 설치도 아직 수행하지 않았다.

## 2026-09-10 화면 접근 없는 전체 거래내역 원본 경로 확인

기존 코드 재사용 확인: performance.engine.net_cash_flow_usd는 매수/매도 체결대금만
합산하고 비용·외부 현금 변동을 포함하지 않으며 모르는 매매 방향은 무시한다.
portfolio.nav.compute_nav는 현금이 없으면0, 시세가 없으면 평균매입가로 대체하는
진단 경로다. 두 함수를 단타의 검증된 순현금/실행 NAV 제공자로 그대로 연결하지 않는다.
FR036은 누락 순현금·원본 가격을 거절하므로 이 기존 진단용 대체 동작을 가져오지 않는다.

공식 eFriend Plus 도움말7451은 계좌별 거래내역에 입출금·입출고·매매·외화·
현금/현물 상환이 포함되고 엑셀 저장과 다음 페이지 조회가 가능하다고 설명한다.
웹 도움말은 상품유형/거래구분 전체 선택과 엑셀 저장을 별도로 안내한다. 따라서
OpenAPI 일별 매매 명세만으로 전체 현금 변동을 수집할 수 없다는 사실을, KIS가 전체
거래 원본을 제공하지 않거나 화면 권한이 개발에 필수라는 결론으로 확대하지 않는다.

공개 해외증권 출력 양식 MyAccTrade_A_IB_70001_1_P1.jsp에서 실제 매핑을 확인했다:
TR_DT(거래일), INQR_SYNS_NAME(거래종류), ACNT_SYNS_TR_QTY(거래수량),
APLY_EXRT(환율), TR_AMT3(거래금액), DMST_FRCR_FEE2(수수료),
AF_CBLC_QTY2(유가잔고), CMA_ICLD_DNCL_AMT(잔액),
AF_FRCR_DNCL_AMT(외환잔액), EXCC_AMT1(정산금액), BRKG_TR_TRTX(거래세),
ACPL_TAX_AMT_2(세금), VAL(부가세)다. 일반 출력 P2에는 AF_DNCL_AMT(예수금),
RCVB_OCCR_AMT(미수발생), RCVB_PYBK_AMT(미수변제), RDPT_AMT(상환금액),
RDPT_INT_AMT(상환이자), REAL_TR_DTIME(거래시각)도 별도 존재한다.

이들은 공개된 빈 출력 템플릿의 필드 이름이며 실계좌 응답이나 완성된 입력 계약이 아니다.
P1의 외환잔액을 USD로 단정하지 않는다. 공개 양식 상단은 원 단위로 표시되므로
정산금액·수수료를 외화 거래금액과 임의 합산하지 않는다. 업무별 부호·통화·행 순서·
페이지 완결성과 시작/종료 잔액은 실제 저장 원본 또는 인증된 응답에서 검증할 항목이다.
웹 도움말의 특정 시간대 입출금 반영 지연도 보존하며 조회 시각을 변동 발생 시각으로
대체하지 않는다. 서식 내 조회기준 일시는 그 자체로 전체 사건의 실시간 반영 증거가 아니다.

공식 전체 메뉴 링크에서 MyAccTrade.jsp 경로를 확인했으며 정상 GET은 로그인 화면으로
이동했다. 로그인이나 계좌 조회를 실행하지 않았고 인증 경계를 우회하지 않는다. 다음
입력 설계는 공개 필드와 제공되는 저장 원본을 기준으로 하며 KIS 문의·화면 복구를
모든 구현의 선행 조건으로 요구하지 않는다. 현금/전체 범위 제공자와 실행 자격의
미구현은 계속 별도 추적하며 템플릿 확인만으로 완료 표시하지 않는다.

- https://www.truefriend.com/plus_help/7451.html
- https://www.truefriend.com/main/help/popup_mypage04.jsp?d1=1&d2=4
- https://www.truefriend.com/main/banking/inquiry/_view/MyAccTrade_A_IB_70001_1_P1.jsp
- https://www.truefriend.com/main/banking/inquiry/_view/MyAccTrade_A_IB_70001_1_P2.jsp
- https://www.truefriend.com/templets/truefriend/allMenu.jsp

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
# 2026-09-12 독립 현금 대조 실제 결과

PR807/main2f7c11f의34685116089은 실제 KIS11개(26.44초)와 원본9응답 저장을
통과했다(장부순번6). 공통 margin USD 예수금은 현재 전후/결제 USD 행과 모두 일치하며
현금 조정4항목은0이다. 현재의 USD×최초고시환율과 외화평가총액, HTS 총자산식
후보는 일치하지 않는다. 결제 출력은 두 식의 필요한 항목이 없어 계산할 수 없다.
다른 통화의 해당 금액은0이다. 이 결과는 합산 정의를 확정하지 않으며 USD 원금
보고와 원화 환산/전체 계좌 평가를 분리해 후속 정규화해야 한다.

재확인한 공식 현재잔고 필드 설명: frcr_dncl_amt_2는 외화 사용가능금액,
evlu_amt_smtl은 해외유가증권 평가의 원화 환산액이다. frcr_evlu_tota/tot_asst_amt의
설명은 비어 있다. 합계에 대한 추정 식을 숫자가 맞도록 선택하거나 현재 보고의
수신 시각을 보유자산의 실제 가격 발생 시각으로 주장하지 않는다.
출처: https://apiportal.koreainvestment.com/api/apis/guide/property/09baff2a-6e9d-4502-ba66-d7bb94094b67

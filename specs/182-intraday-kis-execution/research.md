# 연구 및 결정

Alpaca 계정은 없으며 KIS 기존 수집을 유지한다. KIS 공식 레거시 예제의 최대
약1개월과 최신 PINC/KEYB 페이지 계약을 확인했다. 3년 자료를 보장하지 않는다.
- https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/legacy/rest/get_ovsstk_chart_price.py
- https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/overseas_stock/inquire_time_itemchartprice/inquire_time_itemchartprice.py

KIS 무료 Nasdaq 부분 시세는 마감 후 차트가 갱신된다. 당시 원본과 소급자료를 분리한다.
- https://file.koreainvestment.com/Storage/customer/guide/regards/service_03_1%283%29.htm

Dukascopy 무료 export와5ETF는 있지만 CFD호가/호가수량이며 웹약관상 자동수집 제한도
있다. 실제 ETF체결거래량으로 변환하거나 무허가 대량수집하지 않는다.
- https://www.dukascopy.com/swiss/english/marketwatch/historical/
- https://www.dukascopy.com/swiss/english/legal-pages/terms-of-use/

2026-09-07 KIS 취소 공식계약은 PDNO·ORD_QTY·ORD_SVR_DVSN_CD와 업무성공을
요구한다. 기존 함수의 종목누락·수량0·업무결과 미확인·기본재시도와 worker의
즉시CANCELLED/재호가를 수정한다. 접수와 최종상태를 구분한다.
- https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/overseas_stock/order_rvsecncl/order_rvsecncl.py

기존 router/authority/fill_sync를 공유한다. 단타 별도guard는 기본차단하며
기존 X.4 사다리 승인을 상속하지 않는다. 테스트에는 실제키가 필요없다.

체결 조회 공식 예제와 포털 공개 문서를 대조했다. SORT_SQN=DS,
ORD_GNO_BRNO 공란, tr_cont=F/M이면 ctx_area_fk200/nk200 원문을 다음 요청에
보존하고 tr_cont=N으로 연속 조회한다. 반복 커서·100페이지 초과·업무 거절은
불완전 자료로 차단한다. NASD는 미국 전체를 포함하므로 실제 응답 거래소를 보존한다.
- https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/overseas_stock/inquire_ccnl/inquire_ccnl.py
- https://apiportal.koreainvestment.com/apiservice-apiservice?/uapi/overseas-stock/v1/trading/inquire-ccnl

새 단타 경로는 strict_contract를 사용한다. 누적 스냅샷을 합산하지 않고 가장 큰
누적량을 취한다. 취소행은 orgn_odno로 연결하며, 취소유형02·처리완료·동일종목/방향·
남은 수량 이상 취소 확인을 함께 요구한다. 취소 거부/전송은 종료가 아니다.
주문접수 날짜는 현지 날짜이며 시간의 UTC 근거가 없어 단타는 관측시각을 기록한다.
불명확한 주문은 가격·수량이 같아도 자동 연결하지 않는다. 기존 일반 호출의
날짜 해석/부분행 호환은 유지하며, 단타 주문은 기존 워커의 추정 복구에서도 제외한다.
부분 체결 증분 단가는 누적 체결금액에서 이미 기록한 금액을 빼서 계산한다.

## 자본 검토 결정 (2026-09-07)

기존 신호는 capital×0.16과 cash/1.003 중 작은 금액으로 정수주를 산다.
100달러로는 예시 ETF 어느 종목도 1주가 안 된다. 600달러 예시는 TLT만
1주가 가능하며, 이를 5종목 분산 운용 가능이나 적합한 투자금으로 표현하지 않는다.
예산을 자동 상향하거나 저렴한 다른 ETF로 바꾸는 대안은 채택하지 않는다.
가격은 공개 참고 스냅샷이고 실제 주문 시세가 아니다.

독립 KIS 계약 조사 결과 구매가능금액은 총 현금/NAV와 같지 않다.
inquire-psamount의 ovrs_ord_psbl_amt와 frcr_ord_psbl_amt1도 의미가 다르다.
inquire-present-balance에는 미국 장중 반영 지연 안내가 있어 tot_asst_amt/환율을
실시간 USD NAV로 인정할 근거가 부족하다. 기존 합산 잔고를 새 단타 승인에 쓰지 않는다.
이 단계는 계좌 연결 구현 대신 검토 계산을 완성하고 NAV 미검증을 명시한다.
- https://apiportal.koreainvestment.com/apiservice-apiservice?/uapi/overseas-stock/v1/trading/inquire-psamount
- https://apiportal.koreainvestment.com/apiservice-apiservice?/uapi/overseas-stock/v1/trading/inquire-present-balance

## 확정 한도와 계좌 관측 결정 (2026-09-07)

운영자600/12 준비 기준 확정을 기록했다. 실제 실행기의 손실 계산은 체결금액의
0.25% 추정비용도 포함한다. 600달러 가상계좌에서5주×20달러 매수 후17.65달러면
가격손실11.75+비용0.25=12로 정지한다.17.66은11.95로 아직 정지하지 않는다.
시험을 이 경계에 맞추며 기존 실행기의 손실 공식을 변경하지 않는다.

독립 공식 문서 조사에서 foreign-margin(TTTC2101R)의 통화별 예수금·미결제매수/
매도·미수·증거금·일반주문가능금액을 확인했다. 장중 갱신 기준과 NAV 산식이 없어
서로 합산하지 않고 원필드 의미별로 분리한다. 결제기준잔고는 지연 시세이고,
체결기준잔고의 실시간 예외는 애프터연장 가입 여부와 정산시간 조건을 확인해야 한다.
따라서 nav=None을 유지한다. 순자산을 추정해 실행 승인하는 대안은 채택하지 않는다.
- https://apiportal.koreainvestment.com/apiservice-apiservice?/uapi/overseas-stock/v1/trading/foreign-margin
- https://apiportal.koreainvestment.com/apiservice-apiservice?/uapi/overseas-stock/v1/trading/inquire-paymt-stdr-balance

inquire-balance의D/E는 마지막 페이지이며 FK검색조건이 남을 수 있다.
inquire-nccs 포털과 예제의 연속조회 설명은 일치하지 않는다. 헤더만으로
완료를 선언하지 않고 커서가 전진하면 계속 읽으며 반복/상한은 불완전으로 거절한다.
[]는 빈 목록으로 지원하되 누락/null/빈문자/빈객체는 실제 증거 없이 정상화하지 않는다.
모든 요청은GET, NASD미국전체 조회이며 기존 ResilientClient를 사용한다.
- https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/inquire_balance/inquire_balance.py
- https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/inquire_nccs/inquire_nccs.py

## 실서버 페이지 종료 보정

PR775/224558c의 실제 읽기34067976976은 새 계좌검사만 ACCOUNT_CURSOR_STALLED로
실패했고 기존7개는 통과했다. 원문 커서를 공개하거나 실패를 정상 계좌로 바꾸지 않았다.
공식 legacy/Sample01/kis_ovrseastk.py의 get_overseas_inquire_nccs를 추가 확인했다.
같은 inquire-nccs/TTTS3018R/NASD/SORT_SQN=DS 경로이며 함수는D/E를 마지막 페이지,
M/F를 다음 페이지로 구분한다. 마지막 페이지에서 FK/NK 공란을 요구하지 않는다.
따라서 balance에만 적용했던D/E 완료를nccs에도 적용한다. 빈 헤더에서 남은 커서,
M/F의 무진행/반복, 비정상 헤더·필드·페이지 상한은 계속 거절한다.
오류 시 endpoint/페이지수/행수/헤더/커서 공란 여부·반복 여부만 진단한다.
계좌번호·커서 원문·주문ID·보유 내역은 진단에 포함하지 않는다.
- https://github.com/koreainvestment/open-trading-api/blob/main/legacy/Sample01/kis_ovrseastk.py

## 실서버 거래소 코드 보정

PR776/72e8b03의 실제 읽기34072779392는 페이지 종료 오류를 넘었지만
NON_US_MARKET로 거절됐다(기존7개 통과). 공식 사용자용 해외주식 함수의
inquire_balance 문서는 실전 NASD=미국 전체, NAS=나스닥, NYSE=뉴욕,
AMEX=아멕스를 구분한다. 누락했던 NAS를 추가하고 고정 문자열의 양끝 공백을
제거한 뒤 같은 미국 거래소 목록과 USD만 허용한다. 다른 코드·빈값·다른 자료형은
계속 거절한다. 실패 원문 코드 대신 닫힌 분류만 진단한다.
실제 실패 응답의 원문 거래소 값은 공개하지 않았으므로 NAS/공백이 원인이었는지는
후속 서버 조회 성공 여부로 검증한다. 요청용 NASD와 실제 주문 라우팅은 변경하지 않는다.
- https://github.com/koreainvestment/open-trading-api/blob/main/examples_user/overseas_stock/overseas_stock_functions.py

## 실제 거래소 식별자 진단

PR777/2745f99의 실제 읽기34073693815도 NON_US_MARKET/OTHER로 실패했다
(기존7개 통과,20.70초). NAS/공백 보정이 실제 오류를 해결했다고 주장하지 않는다.
정상 미국 코드의 허용 목록을 더 넓히지 않고 실패 발생 endpoint와 거래소 식별자만
진단한다. ovrs_excg_cd는 공개 프로토콜 코드이며 [A-Z][A-Z0-9]{1,7} 형식만 출력한다.
숫자 계좌번호, 긴 토큰, 자유문, 다른 자료형은 REDACTED로 남는다. 이 형식 검사로
계좌 조회가 허용되는 것은 아니며 기존 거절은 그대로 유지한다.

## 실제 OTCB 자산과 조회 범위

PR778/e6674c8의 실제34074654444에서 실패 위치는 inquire-balance, 코드OTCB로
확인됐다(기존7개 통과,20.36초). NAS/공백 가정이 실제 원인은 아니었다.
KIS present-balance 공식 요청표는 미국840에 PINK SHEETS03/OTCBB04를 포함한다.
따라서 미국 잔고 보고가 세 거래소에만 한정된다고 가정할 수 없다. 다만 이것이
응답 OTCB와 OTCBB의 정확한 매핑을 증명하지 않으므로 원래 코드를 보존한다.
공식 권리조회 안내는 상장폐지 후 OTC 이동 종목의 유선 매도 제한을 설명한다.
현재 자산이 그 경우인지는 확인하지 않았으며 보유 사실을 API 주문 가능성으로
해석하지 않는다. OTCB 행은 식별자·보고 수량만 별도 미검증 자산으로 보존하고
평가액/NAV/거래가능을 추정하지 않는다. 다른 오류·미체결 시장 차단은 그대로다.
- https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py
- https://securities.koreainvestment.com/main/bond/right/OverseaRight.jsp?cmd=OverseaRight_list9

## USD 구성 내역의 미제공과 오류 구분

PR779/0b8992b의 실제34075774149는 OTCB 처리를 넘어 USD_MARGIN_ROW_COUNT에서
중단됐다(기존7개 통과,19.77초). 이 오류만으로 USD 행0/중복/공백 중 어느 경우인지
단정하지 않는다. currency 양끝 공백을 제거하고 유효한 통화별 목록에서 USD 행이
없으면 미제공(None/경고)으로 보존한다. 다른 통화나 빈 목록을 USD 현금0으로
해석하지 않는다. 중복 USD·잘못된 코드·USD 행 내부 금액 오류는 계속 거절한다.
USD 구성 내역을 제공받았는지는 공개 결과에도 남기며 전체 NAV/주문 준비는 false다.

## 공식 빈 통화 행 계약

PR780/d05b92e의 실제34076749615는 INVALID_MARGIN_CURRENCY로 거절됐다
(기존7개 통과,20.82초). 공식 legacy 외화증거금 함수는
같은 foreign-margin/TTTC2101R 응답에서 current_data.crcy_cd != "" 행만 남긴다.
따라서 빈 통화 문자열은 통화별 금액 계산에서 제외하고 존재 여부는 별도 집계한다.
그 행의 의미는 공식 설명이 없어 합계/자리채움/USD라고 단정하지 않는다.
누락/null/다른 자료형은 공란으로 바꾸지 않으며 진단에는 필드 존재/자료형/필드명만
남기고 금액·계좌 원문은 숨긴다. 공란 행의 금액을 어느 통화에도 합산하지 않는다.
- https://github.com/koreainvestment/open-trading-api/blob/main/legacy/Sample01/kis_ovrseastk.py#L914

## 최종 외부 확인 사항 — 같은 USD10행

PR781/d602525의 실제34077759009는 공란 통화 행 처리를 넘어 USD10행을 확인했고
USD_MARGIN_ROW_COUNT로 차단됐다(기존7개 통과/신규1개 실패,21.96초).
공식 foreign-margin 규격의 행 식별 관련 필드는 국가명/통화뿐이며 유일성,
동일 통화 합산·중복 제거·대표행 선택 규칙은 없다. 구형 예제는 공란 통화만
제외하고 최신 예제도 행 연결만 한다. 근거 없는 첫행 선택·합산을 하지 않는다.
문의 초안은 capital-review/kis-cash-contract-inquiry.md이며 미발송이다.
이 시점에는 공식 답변을 T020/T027 모두의 선행 조건으로 잘못 요구했다.
아래 FR-022 재검토가 T020 조회 완료와 T027 금액 해석을 분리한다.

execution/intraday_signals.py는 기존 사전등록 신호와 실제 귀속 보유를 연결한다.
전체 5종목의 연속된 확정봉과 소스지문을 검사한다. 종료 청산은 신호 자료 장애에도
계좌 재관측을 먼저 수행한다. 매수·매도 모두 5분 미체결이면 취소 확인을 기다린다.
계좌/배포 잠금을 얻기 전 실패한 취소는 요청을 소비하지 않는다. 잠금 안에서
REQUESTED를 기록한 뒤 결과가 불명확하면 자동 재전송하지 않는다.

## 2026-09-08 재검토 — 여러 USD 행은 조회 실패가 아니다

공식 legacy 및 최신 foreign-margin 예제는 행 목록을 보존한다. 통화의 유일성을
요구하는 코드는 없으며, USD10행을 중복이라고 규정한 것은 우리 수집기의 가정이었다.
읽기 계약은 모든 행을 검증·보존하면 완료할 수 있다. 행 간 집계가 불명확한 사실은
현금/NAV 검증에만 영향을 주며 GET 조회 전체의 실패로 바꿀 이유가 없다.
따라서 FR-022는 모든 USD 구성금액을 순서대로 보존하고 다중 행의 단일 금액을 None으로
남긴다. 동일 금액도 삭제하지 않는다. 고객센터 문의는 집계 계약의 선택적 확인 경로이며
조회 구현 완료의 선행 조건이 아니다. 실제 실행 NAV·전체계좌 범위는 계속 미검증이다.
- https://github.com/koreainvestment/open-trading-api/blob/main/legacy/Sample01/kis_ovrseastk.py#L914
- https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/foreign_margin/foreign_margin.py

## US7 실행 연결 설계 재검토

## US8 문의를 필수로 삼지 않는 직접 조회 — 2026-09-08

선택: CTRP6504R/CTRP6010R의 output2 보고 금액을 직접 읽고 수치 대조한다.
이유: foreign-margin USD10행의 합산 규칙을 기다리지 않고 기존 계좌에서 실제 근거를 수집할 수 있다.
두 API 모두 외화02·일반/미니스탁 전체00을 지원하고 현재잔고는 국가000/시장00이다.
연속조회는 CTX 없이 tr_cont 공백→N, 응답 M/F 다음·D/E 끝이다.
후속34193364010에서 첫 새 검사가 BALANCE_CONTINUATION_HEADER로 실패했다(기존8통과).
실패 코드는 공란/누락/기타를 구분하지 않았으므로 실제 공란이라고 단정하지 않는다.
공식 두 Python 예제의 성공 분기는 M/F에서만 재귀하고 그 밖에는 종료한다.
이 근거로 명시적 공란 종료를 수용하고 누락/기타는 계속 실패시킨다. 종료 분류와
오류 분류를 제한 공개하여 후속 실제 검사에서 재현한다. T027/NAV 검증은 변하지 않는다.
공식 샘플의 깊이 초과/실패 부분 반환을 정상 성공으로 가져오지 않는다.

중요 차이: CTRP6504R output2.frcr_dncl_amt_2의 공식 설명은 외화사용가능금액이며,
CTRP6010R 같은 필드는 외화예수금액2라는 이름만 있고 의미 설명은 공란이다.
current output1 cblc_qty13은 결제보유, ccld_qty_smtl1이 체결현재보유다.
같은 frcr_evlu_amt2도 output1의 외화평가와 output2의 출금가능원화가 서로 다르다.
따라서 필드명만으로 모든 output을 합치거나 구매가능금액/예수금/총자산을 동치로 쓰지 않는다.
금액은 signed Decimal이며 0 클램프·합산·첫 행 선택·중복제거 없이 보존한다.

거절한 대안: 두 금액이 같으면 cash/NAV를 검증 완료로 처리하기.
공식 현재잔고 개요7항에서 일반/통합증거금 미국 내역은 장중 미반영,
통합증거금의 외화 주문금액만 먼저 반영돼 평가가 어긋날 수 있음을 명시한다.
애프터연장 계좌에도 정산/거래량 지연 예외가 있고 결제잔고는 지연시세다.
따라서 수신시각을 실제 평가시각으로 바꿀 수 없으며, 이 조회가 전체 계좌 누락 검증도 대신하지 않는다.
문의는 대체 근거로 남기되 개발과 실제 읽기 검증을 기다리게 하는 조건에서 제외한다.

공식 근거:
- https://apiportal.koreainvestment.com/api/apis/public/detail?accessUrl=%2Fuapi%2Foverseas-stock%2Fv1%2Ftrading%2Finquire-present-balance
- https://apiportal.koreainvestment.com/api/apis/guide/property/09baff2a-6e9d-4502-ba66-d7bb94094b67
- https://apiportal.koreainvestment.com/api/apis/public/detail?accessUrl=%2Fuapi%2Foverseas-stock%2Fv1%2Ftrading%2Finquire-paymt-stdr-balance
- https://apiportal.koreainvestment.com/api/apis/guide/property/8e78ed2f-8c3d-424e-b400-82fc94ca4a6b
- https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_present_balance
- https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_paymt_stdr_balance

### US7 기존 연결 조사 경과

IntradayExecutor.on_bars와 기존 통합 시험이 후보→신호→router/authority를 이미 연결한다.
비활성 factory만 추가하는 것은 누락 해소가 아니다. 실제 누락은 매도가능수량의
전달과 시세 발생시각 검증이다. 현금/NAV나 OTCB를 추정 제외하여 생산 입력을 만드는
대안은 폐기했다. 위 두 입력을 기존 실행기에 필수로 추가하되 생산 권한은 만들지 않는다.

KIS REST price/price-detail의 공식 예제에는 발생시각이 없다. 현재 get_quote의
quoted_at_utc는 수신 시각이므로 단타 mark_times로 사용할 수 없다.
웹소켓 HDFSCNT0에는 현지 XYMD/XHMS와 한국 KYMD/KHMS가 명시돼 있다.
발생시각 입력은 가능하지만 실제 전송·필드 배열 버전·시장 전체 동등성 검증이 남는다.
REST 호가 dymd/dhms는 공식 시간대 확인 없이 UTC로 추정하지 않는다.
- https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/price/chk_price.py
- https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/delayed_ccnl/delayed_ccnl.py

## US9 산술 검증 근거 — 2026-09-09

공식 CTRP6504R 상세와 속성 JSON을 다시 직접 읽었다. 속성004.005는 체결현재수량,
004.007~009는 외화 매입·평가·그 차이인 손익, 004.012는 원화 평가 환율,
006.001~003은 해외유가증권 매입·평가·손익의 원화 합계다. 이 관계를 실제로 계산한다.
005.005는 이름이 예수금이어도 설명은 외화사용가능금액이며, output2.frcr_evlu_amt2는
출금가능원화다. 이를 보유 평가액에 더하지 않는다. 요약의 총자산·미결제·총외화잔고
필드에는 구성 합산식 설명이 없다. foreign-margin의 행별 금액에도 통화중복 합산 규칙이 없다.
명세가 비어 있다는 사실을 새 코드만으로 해소됐다고 주장하지 않는다.

원화 환산 행별 반올림 규칙도 없으므로 정확 일치만 MATCH이며 행당1원 이하 차이는
ROUNDING_DIFFERENCE로 별도 검사 불가다. USD 외 통화는 환율 호가 단위를 추정하지 않는다.
공식 개요7항은 일반/통합증거금 미국 매매의 장중 반영 차이를 명시한다.
따라서 보고서 산술 MATCH는 현재 실주문용 NAV 검증과 다르다.

출처: https://apiportal.koreainvestment.com/api/apis/guide/property/09baff2a-6e9d-4502-ba66-d7bb94094b67
및 같은 API 상세, foreign-margin 공식 상세. 전체 응답은 개인정보가 섞일 수 있어
저장소에 복사하지 않고 계산에 사용한 공개 필드 의미만 이 문서에 기록한다.

실제34291826106에서 2개 자산의 개별 산술과 세 출력 안정성은 일치했지만 원화
매입/평가/손익 합계는 불일치, 요약 손익은 1원 이내 차이였다. 계좌 이상이나 증권사
오류로 단정하지 않는다. WCRC_FRCR_DVSN_CD=02는 외화 조회, 공식 합계 설명은
원화 환산이다. 필드명만 믿고 단위를 바꾸거나 센트 오차를 허용하면 잘못된 합격을
만들 수 있다. 같은 자료에서 환산 전 합과 일치하는지, 차이가 각 행 1센트 환산 합
이내인지 구분하되 원래 불일치와 원인 미확정을 유지한다. 새 GET이나 원문 로그는 없다.

## US11 집계 비교 가정 재검토 — 2026-09-09

공식 CTRP6548R 상세의 real_nass_amt(004.005)와 nass_tot_amt(005.002)는
이름 이외의 계산식 설명이 없다. 같은 output2에 tot_asst_amt도 따로 있으며,
pchs_amt_smtl/evlu_amt_smtl의 설명은 유가매입/유가평가금액이다. 공식 예제는
output1을 HTS0891 결제기준 자산비중 표로 설명할 뿐 두 순자산의 동일성을 주장하지 않는다.
따라서 기존 수치 차이는 유효한 관측이나 등식 검증 실패로 해석할 근거는 부족하다.

해외 현재잔고도 원화 환산 필드라는 근거는 있지만 전체 행 합과 요약의 정확한 집계 범위,
반영 시점, 반올림 계약까지 제공하지 않는다. 앞선3개 차이를 증권사 오류로 확정할 수 없다.
실제 원인을 알아냈다고 주장하거나 우연히 맞는 공식을 선택하지 않고, 보고서 내부 검사와
미입증 교차 출력 비교를 구분한다. 현금 계약과 실행 NAV를 새로 인증하는 변경은 아니다.

출처:
- https://apiportal.koreainvestment.com/api/apis/public/detail?accessUrl=%2Fuapi%2Fdomestic-stock%2Fv1%2Ftrading%2Finquire-account-balance
- https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_account_balance/inquire_account_balance.py
- US9에 기록한 공식 CTRP6504R 필드·정산 기준.

버전2 실제34307196553(main6e66d04)은10개 시험 통과, 자산표의 내부6개 검사 MATCH,
해외 내부15 MATCH/1 INCOMPLETE(요약 손익1원 이내 차이), 교차 비교4개 DIFFERENT다.
기존 숫자 차이를 유지하면서 검증된 등식과 가설을 분리한 결과다. 현금/NAV 인증은 아니다.

## US10 국내외 전체 자산 분류를 위한 별도 공식 API

CTRP6548R `/uapi/domestic-stock/v1/trading/inquire-account-balance`는 해외잔고와
다른 API다. 공식 개요는 HTS0891 계좌 자산비중(결제기준), output1 속성은 일반20행,
21번 계좌17행의 순서와 마지막 합계를 명시한다. 일반 표는 주식·펀드/MMW·IMA·채권·
ELS/DLS·WRAP·신탁·RP/발행어음·해외주식·해외채권·금현물·CD/CP·전자단기사채·
타사상품·외화전자단기사채·외화ELS/DLS·외화·예수금·청약자예수금·합계다.
공식 요청은 계좌번호/상품코드, INQR_DVSN_1/BSPR_BF_DT_APLY_YN 공란이다.
예제 상품19/21은 필수 제한이 아니며 공식 속성은 계좌 뒤2자리로 정의한다.
기존01 계좌를 그대로 사용한다. 요약의 모든 금액에는 충분한 합산식 설명이 없으므로
분류표 같은 열 합과 명시된 순자산 합만 대조한다. 장중 현재 NAV 계약은 아니다.

- https://apiportal.koreainvestment.com/api/apis/public/detail?accessUrl=%2Fuapi%2Fdomestic-stock%2Fv1%2Ftrading%2Finquire-account-balance
- https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_account_balance/inquire_account_balance.py
- https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_account_balance/chk_inquire_account_balance.py

실제34298665338에서 계좌01의19분류+합계가 모두 제공되고 숫자 형식도 통과했다.
0이 아닌 분류3개, 분류별5열 합계 및 두 조회 안정성은 정확 일치했다. 표의 순자산
합계와 별도 nass_tot_amt는 달랐다. 서로 다른 두 필드의 숫자 비교 결과이며 상세
집계식이 공개되지 않은 상태에서 증권사 오류나 잘못된 계좌 잔액으로 단정하지 않는다.
공식0891 도움말의 force_help/pro_help 주소는 조회할 수 없었고 검색에서도 추가
공식 산식을 확보하지 못했다. 정의를 추정해 차액을 보정하거나 MISMATCH를 합격으로
바꾸지 않는다. 기존 해외 보고서의 원화3개 차이도 유지된다. 현재 확정할 수 있는
범위는 선택 계좌의 결제기준 분류표 형식·열 합계이며 장중 USD 현금/NAV는 아니다.

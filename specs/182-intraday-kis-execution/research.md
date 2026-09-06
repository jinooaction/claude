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

execution/intraday_signals.py는 기존 사전등록 신호와 실제 귀속 보유를 연결한다.
전체 5종목의 연속된 확정봉과 소스지문을 검사한다. 종료 청산은 신호 자료 장애에도
계좌 재관측을 먼저 수행한다. 매수·매도 모두 5분 미체결이면 취소 확인을 기다린다.
계좌/배포 잠금을 얻기 전 실패한 취소는 요청을 소비하지 않는다. 잠금 안에서
REQUESTED를 기록한 뒤 결과가 불명확하면 자동 재전송하지 않는다.

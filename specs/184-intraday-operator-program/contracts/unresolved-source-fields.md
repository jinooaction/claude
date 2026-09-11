# 실제 원본 계약의 남은 증거 — 2026-09-11

이 문서는 소프트웨어 완료 선언이 아니다. 전체 과거 내역·화면 접근·문의는 필수 조건이
아니다. 현재 확인한 원본 정의에서 확정 가능한 계산과 아직 입증하지 못한 의미를 구분한다.

## 시작 순현금과 거래 이후 변동

공식 foreign-margin 상세 JSON의 응답 속성을 다시 조회했다.

- frcr_dncl_amt1: 외화예수금액. 설명은 공백.
- ustl_buy_amt / ustl_sll_amt: 미결제매수/매도금액. 설명은 공백.
- frcr_rcvb_amt / frcr_mgn_amt: 외화미수/증거금액. 설명은 공백.
- frcr_ord_psbl_amt1: 원화주문가능환산금액이라는 설명이 있어 USD 순현금으로 사용 불가.

후보식 `예수금 - 미결제매수 + 미결제매도 - 미수`는 아직 채택하지 않았다. 예수금에 이미
반영된 미결제분과 별도 미수의 중복 여부, 미결제 금액의 수수료 포함 여부가 입증되지 않았다.
USD 단일 행·미수0·미결제0으로 시작 범위를 줄이는 안도 검토했지만, 그 조건만으로
부분 체결 이후 계좌를 계속 계산할 정상 단타 경로까지 입증할 수는 없다. 이것을 모든
가능한 계좌가 불가능하다는 증명으로 확대하지 않는다.

현재잔고의 frcr_dncl_amt_2는 공식 설명이 '외화로 표시된 외화사용가능금액'이다.
이를 모든 부채/미결제를 반영한 순현금으로 바꾸면 구매력과 순현금을 혼동한다.
frcr_etc_mgna와 tot_loan_amt에는 추가 계산 설명이 없다. 현재 데이터 범위로는
지원 가능한 정확한 시작/후속 순현금 계약을 확정하지 못했다. 공급자 구현도 미완료다.

## 체결·비용 자격

CTOS4001R은 trad_dt/sttl_dt, tr_frcr_amt2, frcr_excc_amt_1,
dmst_frcr_fee1/frcr_fee1을 제공한다. 현재 확인한 응답 속성에는 주문번호가 없다.
eb22ad4에서 단일 전략의 종료 주문 집합과 종목/방향별 단일 주문의 비용 대조를 실제
인증 GET→SQLite→prepare_qualification에 연결했다. 계좌·연구/실행 지문·조회 기간·
운영 승인 참조를 계산 결과에 묶는다. 이 연결은 이제 미구현이 아니다.
다만 거래명세 등록일과 주문/체결일의 정확한 대응, 실제 체결 시각, 모델 거래량 재생
증거는 여전히 미제공이다. 비용 부분 증명이 통과해도 전체 자격은 거절한다.

2026-09-11 공식 체결통보 속성 원본을 재조회했다. STCK_CNTG_HOUR 설명은 특정
거래소의 시각 미수신과 수신 타임스탬프 대안을 명시한다. 수신 시각을 실제 체결 시각으로
승격하지 않는다. CNTG_YN=2만 체결이며 CNTG_QTY도 이때 체결 수량이다. 통보 구독만
추가하면 과거의 시간·거래량 증명이 완성된다는 결론은 근거가 없다. 별도 시간 증거나
관측 구간을 사용하는 모델 계약과 원본 재생이 필요하다. FR045/046에서 구간 계산과
동일 전진 장부의 완결 봉 자동 소비를 구현했다. 시장 원본 인증과 연구 모델의 전체
동등성은 아직 미입증이며 계산기가 없다는 과거 진단과 구분한다.

## 시세 연결

공식 examples_user/kis_auth.py는 구독 최대40을 검사하고 단일 연결로 요청들을 보낸다.
두 물리 웹소켓 동시 사용 가능성을 입증하지 못했으므로 단일 연결+소비자별 뷰로 보정한다.
전략5종목을 포함해40개 이내다. ORANY의 OTC 원본 발생시각 가격은 확보되지 않았고
다른 거래소·조회 수신시각·0가격으로 대체하지 않는다.

## 재현 출처

- https://apiportal.koreainvestment.com/api/apis/public/detail?accessUrl=%2Fuapi%2Foverseas-stock%2Fv1%2Ftrading%2Fforeign-margin
  의 apiPropertys에서 bodyType=res_b, propertyOrder=004.* 확인.
- https://apiportal.koreainvestment.com/api/apis/guide/property/09baff2a-6e9d-4502-ba66-d7bb94094b67
- https://apiportal.koreainvestment.com/api/apis/guide/property/8e874fea-8e55-464d-b535-75df64fc3048
- https://github.com/koreainvestment/open-trading-api/blob/main/examples_user/kis_auth.py

서버 인증 연결이 현재 없다는 사정은 실제 계좌 검증의 한계다. 비용 자격 소비 연결은
완료했고 실제 CLI→인증→GET→비용 거절→DB 닫기→재시작 경로도 모의 HTTP로 검증한다.
정상 순현금 공급자·시간/거래량 증명·최종 성공 경로를 완료했다는 뜻은 아니며
T009/T010은 미완료로 유지한다.

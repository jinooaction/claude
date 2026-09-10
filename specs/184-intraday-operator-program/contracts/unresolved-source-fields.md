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
단일 주문 그룹에서는 비용 합계 대응이 가능할 수 있지만 현재 대조기는 계좌 소속,
연구/실행 지문, 주문일과 등록일의 자료 범위, 운영 승인 참조를 함께 검증하지 않는다.
prepare_qualification의 상수 false 문제는 소프트웨어 미완료이며 관찰일 부족과 별개다.
이 문서는 이 미구현을 외부 정보 부족만의 문제로 바꾸지 않는다.

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

서버 인증 연결이 현재 없다는 사정은 실제 계좌 검증의 한계다. 위 자격 연결과 최종 CLI
통합이 코드로 완성됐다는 뜻은 아니며 T009/T010은 미완료로 유지한다.

# KIS 외화증거금 응답 확인 요청 초안

상태: 작성 완료, 외부에 보내지 않음. 계좌번호·인증값·금액·보유종목 원문은 포함하지 않았다.

## 확인한 현상

2026-09-07 11:53 KST의 [읽기 전용 검사34077759009](https://github.com/jinooaction/claude/actions/runs/34077759009)에서
`GET /uapi/overseas-stock/v1/trading/foreign-margin`, `TTTC2101R`의 공란 통화 행을
제외한 뒤 `crcy_cd="USD"` 행이10개였다. 첫 행 선택·합산·중복 제거를 하지 않고
`USD_MARGIN_ROW_COUNT`로 차단했다. API 통신 실패가 아니라 금액 해석 미확정이다.

## 문의 내용

해외증거금 통화별조회 `TTTC2101R`의 `output`에서 USD가10행 반환됩니다.

1. 각 행은 국가·시장·결제구분 중 무엇으로 나뉘며 공식 행 식별 키는 무엇인가요?
2. 같은 USD의 `frcr_dncl_amt1`은 행별 금액인가요, 여러 행에 반복되는 계좌 공통 예수금인가요?
3. `ustl_buy_amt`, `ustl_sll_amt`, `frcr_rcvb_amt`, `frcr_mgn_amt`,
   `frcr_gnrl_ord_psbl_amt`의 필드별 합산·중복 제거·대표 행 선택 규칙을 알려주세요.
4. 공란 `crcy_cd` 행의 의미와 합계 행 식별 방법은 무엇인가요?
5. 미국 장중 체결·미체결이 각 금액에 반영되는 시점과, USD 현금 잔액을 계산하는 공식 산식은 무엇인가요?
6. 동일 통화가 여러 행인 정상 응답의 민감정보 없는 예시를 제공해 주실 수 있나요?

## 현재 근거와 재개 기준

[공식 응답 규격](https://apiportal.koreainvestment.com/apiservice-apiservice?/uapi/overseas-stock/v1/trading/foreign-margin)은
국가명과 통화를 제공하지만 동일 통화 행의 합산/대표 선택 규칙을 명시하지 않는다.
[공식 구형 예제](https://github.com/koreainvestment/open-trading-api/blob/main/legacy/Sample01/kis_ovrseastk.py#L914)는
공란 통화만 제외하며, [최신 예제](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/foreign_margin/foreign_margin.py)는
행을 연결할 뿐 통화별 합산을 하지 않는다.

공식 답변으로 행 식별·금액 산식·반영 시점을 확정한 뒤 계약 시험과 읽기 전용 재검증을
진행한다. 실제 계좌 NAV, 전략 합격·전진60세션·생산 주문 권한/체결 증거는 별도 조건이다.
600달러·하루 정지12달러 준비 기준은 이미 확정됐으며 다시 질문하지 않는다.

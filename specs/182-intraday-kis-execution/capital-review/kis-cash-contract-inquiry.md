# KIS 외화증거금 응답 확인 요청 초안

상태: 2026-09-08 운영자 발송 승인 완료, 외부 제출은 아직 하지 않음.
계좌번호·인증값·금액·보유종목 원문은 포함하지 않았다. 같은 여섯 질문의 발송 허락을 다시 묻지 않는다.

## 접수 경로와 현재 막힘 — 2026-09-08 확인

운영자가 "발송 허락할게. 남은 작업도 모두 완료해줘."라고 답했다.
승인 범위는 아래 문의 내용 여섯 질문이다. 개인정보 제공·이용 동의, 실제 주문·자금 배정의 승인이 아니다.

구 Q&A 주소가 열리는 것만 확인하고 현재 접수가 가능하다고 안내했던 판단을 정정한다.
[KIS 공식 FAQ](https://apiportal.koreainvestment.com/community/10000000-0000-0011-0000-000000000002/post/368dc5b9-9815-4b69-bfa3-0ce5565a8daf)는
2025-08-11에 구 Q&A 운영 종료와 고객의 소리(VOC) 문의를 안내했다.
개발자센터 로그인은 문의 제출에 필요한 현재 경로가 아니므로 그 로그인 요청을 철회했다.

[회원 접수창](https://securities.koreainvestment.com/main/customer/support/Support.jsp?cmd=TF04fc010100_PreInput)은
로그인하지 않은 현재 브라우저에서 보안프로그램 설치 화면으로 이동했다.
[공식 비회원 접수창](https://securities.koreainvestment.com/main/customer/support/Support_1.jsp)은
이용동의 화면에 도달했으며 이름·생년월일·휴대폰번호 수집과 민원 종결 후 5년 보유를 요구한다.
해당 동의·개인정보 입력은 진행하지 않았다. 승인된 본문도 아직 웹 양식에 입력되지 않았다.
운영자에게 이 단계의 직접 처리를 요청했으며, 완료 후 동일한 여섯 질문을 제출한다.
발송 완료는 접수번호 또는 성공 화면으로 확인한 뒤 기록한다. 현재 접수번호는 없다.

이 기록은 등급2 운영 인계 보정이다. 오래된 접수 경로와 승인 대기 안내를 현재 확인으로
대체하며 본문·비밀값 분리·실거래 관문은 유지한다. 기록 오류는 문서 커밋을 되돌린다.

2026-09-08 정정: FR-022/PR783은 여러 USD 행을 그대로 보존하여 실제 조회8/8을
통과했다. 이 문의는 금액 집계/NAV 확인용이며 조회 완료의 선행 조건이 아니다.

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

## 금액 집계 후속 확인 기준

[공식 응답 규격](https://apiportal.koreainvestment.com/apiservice-apiservice?/uapi/overseas-stock/v1/trading/foreign-margin)은
국가명과 통화를 제공하지만 동일 통화 행의 합산/대표 선택 규칙을 명시하지 않는다.
[공식 구형 예제](https://github.com/koreainvestment/open-trading-api/blob/main/legacy/Sample01/kis_ovrseastk.py#L914)는
공란 통화만 제외하며, [최신 예제](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/foreign_margin/foreign_margin.py)는
행을 연결할 뿐 통화별 합산을 하지 않는다.

공식 근거로 행 식별·금액 산식·반영 시점을 확정하면 집계 계약 시험을 추가할 수 있다.
기본 조회는 이미 완료됐다. 실제 계좌 NAV, 전략 합격·전진60세션·생산 주문 권한/체결 증거는 별도 조건이다.
600달러·하루 정지12달러 준비 기준은 이미 확정됐으며 다시 질문하지 않는다.

# 조사 결정

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

# Quickstart: Lot-Aware Execution Proxy

1. 설정과 워크플로 회귀를 실행한다.
2. 단위·통합 테스트와 전체 pytest, ruff를 실행한다.
3. 안전 경계 문구가 있는 커밋과 등급 4 PR을 만든다.
4. 머지·배포 뒤 push 미리보기에서 KIS 실제 보유와 매수가능현금을 확인한다.
5. 미리보기가 `SPYM/GLDM` 1주 이상, 내부 모의 보유 매도 0건을 보여줄 때만 다음 정규장
   production 작업이 주문을 제출하게 둔다.
6. 주문 뒤 KIS 주문·체결·잔고와 감사 로그를 대조한다.

실패 시 `automation/rebalance-live.request`를 비무장·단 0으로 내려 신규 주문을 차단한다.

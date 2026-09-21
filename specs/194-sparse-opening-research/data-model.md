# 자료와 상태

- Contract:후보/기간/30파일SHA/비용/자본/참조거래/결제/승격불가.
- Signal:decision_at,symbol,opening_high/low,relative_volume,reason.
- Intent:requested_at,quantity,limit,reserved_cash,attempt_day.
- Position:quantity,cost_basis,opening_low,exit_pending,last_observed_at.
- Settlement:available_session,net_proceeds. 현금과별도이며즉시매수에사용하지않는다.
- LedgerEvent:sequence,kind,decision_at,observation_at,available_at,symbol,
  quantity,reference_price,cost,cash,reserved,unsettled,position_after,source_sha.
- Result:양비용순손익/거래수/미청산/미관측/현금최솟값/지문/실주문0/승격불가.

신호→예약/거절→다음1분확인→전량/부분참조/미관측→예약잔액해제.
보유→청산대기→다음분관측→잔량유지/청산완료→결제대기→사용가능현금.
봉종료에서만관측반영. 종목/날짜별로계좌를초기화하지않는다.

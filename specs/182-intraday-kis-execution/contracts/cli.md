# 명령 계약
`uv run python scripts/intraday_execution.py rehearse`
계좌·URL·키·--live 인수를 받지 않는다. 임시DB와 MockTransport로만 실행한다.
매수→부분체결→취소접수→추가체결→최종취소→청산을 확인한다.
schema_version=182, mode=offline_rehearsal, orders_submitted=0,
live_eligible=false, simulated_broker_requests와 invariant결과는 별도 표시.
성공exit0, 실패exit2. 실제자료·전략합격·실계좌 체결증거가 아니다.
생산활성화 CLI는 없다. coordinator는 권한guard가 없으면 broker접근 전 거절한다.

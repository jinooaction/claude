# 실행 계약

`ExecutionObserver(read_account, quote_snapshot)`는 기존 엔진의 observe에 연결하는
프로그램 내부 소비자다. 사용자 JSON을 읽어 검증 플래그를 발급하지 않는다.
현재 KIS observe_account는 full_account_scope_verified=false를 반환하므로
ACCOUNT_SCOPE_UNVERIFIED로 차단된다. 이 연결만으로 생산 NAV 공급자가 완성된 것은 아니다.
원본 발생시각 보존·현금 필드 대체 금지·보유/주문 완결 검사 후 기존 엔진의 관측 검사를
재사용한다. 입력 실패에는 고정 ObservationError만 사용하고 상위 취소 신호는 전파한다.

`self-test`: 외부 입력 없이 고정 시험 전송·새 임시 DB로 부분 체결과 취소, 늦은 체결,
중지 상태 저장, DB 재열기와 최종 정리를 실제 엔진·운용기로 검증한다. --db 옵션은 없다.
SELF_TEST_PASSED 또는 FAILED와 검사 항목을 반환하며 실패는 종료 코드2다.
항상 mode=OFFLINE_SELF_TEST, live_eligible=false, orders_submitted=0이다.
모의 주문은 실제 금융 거래가 아니며 계좌 키나 실제 가격을 사용하지 않는다.

`run --root PATH [--cycles N]`: 기존 KIS 모의 운용의 반복 실행. N=0 지속.
`status --root PATH`: 잠금으로 실행 중인지 별도로 검증하고 마지막 완료 결과를 표시.
`stop --root PATH`: 현재 실행 식별자의 협조적 중지 요청. 실제 주문·취소·청산 없음.
`quotes --seconds N`: 공식 KIS 웹소켓 구독. 발생시각이 검증된 허용 종목 시세를 반환.
`buying-power --symbol SYMBOL --limit-price PRICE`: 같은 종목·시장·가격으로 외화 구매력 GET.

장부는 root/paper.db, 봉은 root/batches, 상태는 root/status.json, 잠금은 root/operator.lock.
두 명령의 상태·중지 경합은 고정 제어 잠금 아래 처리하며 run_id가 일치할 때만 중지한다.
에러 본문·비밀값은 출력하지 않고 고정 코드만 반환한다. 실제 주문은 이 명령에 없다.

`IntradayExecutor(..., external_holdings=load_external_holdings(path))`는 기존 계좌의
비관리 보유 기준표를 명시적으로 연결한다. 생략하면 빈 기준표로 이전 동작과 같다.
잘못된 매핑은 초기화 전에 거절한다. 실행 중 입력 매핑을 바꿔도 엔진 값은 바뀌지 않는다.
기준표+공용 체결 수량과 브로커 수량이 다르면 주문을 중단한다.
같은 종목의 기존 보유를 단타로 간주하거나 체결 장부에 삽입하지 않는다.
기준표는 전체 계좌 관측 또는 단타 실행 권한을 대신하지 않는다.

`IntradayExecutor.manage()`는 봉 없이 기존 체결·미체결과 위험 상태를 관리한다.
전략 목표가 없으므로 신규 진입이나 목표 변경 취소를 만들지 않는다. 만료 취소·손실 방어·
마감 청산은 기존 계약과 같다. `request_drain()`은 정리 의도를 추가 기록하며,
기존 또는 새 전략 호출도 요청 이후 신규 매수를 만들 수 없다.
관리 주기가 새 대조에서 보유·주문0을 확인하면 STOP_COMPLETED를 추가한다.
`intraday_runtime.run`은 독립 수집 작업보다 관리 주기를 우선하며 새 DB를 만들지 않는다.
`execution-status --db PATH`와 `execution-stop --db PATH`는 실주문 운용기의 상태 조회와
정리 요청이다. 실행 중인 운용기가 없으면 NOT_STARTED/NOT_RUNNING이며 실주문을 시작하지 않는다.
현재 사용자 `run`은 기존 모의 운용이다. 실제 계좌 공급자·권한 연결이 없는데 이름만 실주문으로
바꾼 실행 명령은 제공하지 않는다.

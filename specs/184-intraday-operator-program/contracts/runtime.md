# 실행 계약

`run --root PATH [--cycles N]`: 기존 KIS 모의 운용의 반복 실행. N=0 지속.
`status --root PATH`: 잠금으로 실행 중인지 별도로 검증하고 마지막 완료 결과를 표시.
`stop --root PATH`: 현재 실행 식별자의 협조적 중지 요청. 실제 주문·취소·청산 없음.
`quotes --seconds N`: 공식 KIS 웹소켓 구독. 발생시각이 검증된 허용 종목 시세를 반환.
`buying-power --symbol SYMBOL --limit-price PRICE`: 같은 종목·시장·가격으로 외화 구매력 GET.

장부는 root/paper.db, 봉은 root/batches, 상태는 root/status.json, 잠금은 root/operator.lock.
두 명령의 상태·중지 경합은 고정 제어 잠금 아래 처리하며 run_id가 일치할 때만 중지한다.
에러 본문·비밀값은 출력하지 않고 고정 코드만 반환한다. 실제 주문은 이 명령에 없다.

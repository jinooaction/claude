# 실행 계약

FR041: --history-db는 계좌 읽기 원본 보관만 수행한다. --execution-db를 함께 쓰면 날짜
옵션 없이도 기존 장부의 읽기 전용 전후 순번을 남긴다. 거래 명세/체결 대조에는 기존처럼
명시적 날짜 구간이 필요하다. 보관과 주문 장부는 다른 파일이어야 한다. 기존 관측을
덮어쓰지 않으며 미완결 읽기는 FAILED다. 기록 성공으로 cash/nav/live 검증을 발급하지 않는다.

가격 계산은 `market_data.intraday_pricing.limit_price`를 모의·신호·강제 정리가
공유한다. 매수 기준가×1.0006은 센트 내림, 매도 기준가×0.9994는 센트 올림이다.
100달러 매수는100.06이며25달러 정리매도는24.99다. 모의 float 계산의100.05와
정리의 기본 반올림24.98을 보정했다. 수수료·자본 한도·주문 권한은 변경하지 않는다.
공통 가격 소스가 달라지면 모의/실행 지문도 바뀐다. 기존 모의 장부는 삭제하지 않으며
새 계산 모델은 새 장부에서 관찰한다. 이 수정은 실계좌 수수료/체결 동등성 증명이 아니다.

`intraday_registration.register(archives, preregistration)`는 고정 사본으로 원본 연구를
재계산하고 현재 코드/시각을 사용해 연구 고정 서명 바이트를 반환한다. 이전 합격 보고서,
입력 날짜, 입력 코드 해시, 사용자 키 경로는 받지 않는다. 키는
`/etc/auto-invest/intraday-forward.key`의 root 소유 일반 파일32바이트이며 타인 읽기와
그룹/타인 쓰기를 거절한다. 0400/0600/0640 등 허용 권한에서도 호출자의 실제 읽기
권한이 필요하다. 키를 로그·등록 결과에 싣거나 이번 개발에서 생성/설치하지 않는다.

`assess_registered_forward`는 등록 서명과 현재 연구/실행/사전등록 지문을 검증하고
같은 사전등록 사본으로 기존 전진 장부 재계산을 호출한다. 등록을 검증했을 때만
freeze_authentication_verified=true가 되며 execution_parity_verified/live_eligible는
여전히 false다. 서버 시계·키 보관자는 신뢰 경계이며 악의적인 키 관리자나 과거 시계
오류까지 검출하는 외부 시간 인증 서비스는 아니다. 키 교체는 이전 등록을 무효화한다.
실제 서버 키 설치와 등록 수명주기/실행 권한 연결은 아직 수행하지 않았다.

`build_program(selection, router, observe, qualify, collect_bars, capital_limit, now)`는
내부 의존성을 조립한다. 불일치 연구·자격 검사 누락·계좌/브로커/DB 불일치·600 USD 초과는
기존 엔진 생성 전에 거절한다. 생성 후에도 계좌·자본·소스 지문과 명시적 자격 검사를
주문 경계에서 반복한다. 이 함수는 자격을 발급하지 않으며 실제 자격 공급자의 완료를
대신하지 않는다. 반환한 program.run()은 기존 상태·잠금·중지·재시작 운용기를 호출한다.

`select_research(archives, preregistration, code_commit)`는 이전 합격 보고서를 인자로
받지 않는다. review_archives로 원본 지문·봉 완결성을 검증하고 기존 연구기를 다시
실행한다. 통과할 때만 원래 등록 후보를 반환하며 부족·불합격은 후보 없음으로 반환한다.
결과의 실행 지문에는 실제 후보 매개변수와 관측/선택 코드가 포함된다. 재계산 출력은
새 임시 폴더에만 생성하고 원본 보관 자료는 수정하지 않는다. 계좌/주문 자격은 별도다.

`ExecutionObserver(read_account, quote_snapshot)`는 기존 엔진의 observe에 연결하는
프로그램 내부 소비자다. 사용자 JSON을 읽어 검증 플래그를 발급하지 않는다.
valuation_basis=net_cash_and_listed_equities일 때 순현금 net_cash와 전체 보유의 원본
가격으로 NAV를 직접 계산한다. net_cash는 채무·미결제·모든 현금 변동을 반영한 USD
숫자 문자열이고 음수도 가능하다. execution_cash와 서로 대체하지 않는다. 이 경로는
보고 nav/nav_verified에 의존하지 않지만 전체 범위·현금 검증은 여전히 요구한다.
기준이 없거나 verified_report이면 기존 검증된 NAV 계약을 유지하며 다른 기준은 거절한다.
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
현재 사용자 `run`은 기존 모의 운용이다. `execution-start`는 기존 장부/설정과 내부
자격 재검사·KIS 인증/시세/봉·실제 운용기를 연결한다. 전체 계좌와 체결 검증이 미완료인
현 상태는 시작 거절이다. 명령의 존재나 모의 의존성 시험을 실계좌 준비 완료로 표시하지 않는다.
# 순현금 사건 재계산 계약

`cash_ledger_and_listed_equities`는 내부 계좌 공급자의 cash_ledger를 받는다.
currency=USD, opening/closing={sequence, at, net_cash}, events=[{id, sequence, at,
currency, kind, net_cash_delta, net_cash_after}]이며 금액은 부호 있는 정확한 소수 문자열이다.
kind는 SETTLEMENT/TRANSFER/FX/DIVIDEND/INTEREST/FEE/LIABILITY_ADJUSTMENT 중 하나다.
sequence는 원본 전체 사건의 순서 번호로, 정규화 후 임의 부여하지 않는다. 끝 번호와
시작 번호의 차이는 사건 수와 같아야 하고 원본 순서/각 잔액/최종 잔액을 모두 대조한다.
closing.at은 이번 관측 시작~완료 구간 안에 있어야 한다. 순현금은 채무·미결제까지
포함하며 주문에 쓸 현금과 구분한다. 이 계산은 공급자의 전체 계좌·현금 범위 검증을
대체하지 않고 사용자 파일을 인증하지 않는다. KIS 원본 연결은 미완료다.

# 운용기 신호 소비와 종료

전략 청산 계약: 실제 전략이 전량 매도를 결정하면 첫 매수 체결 순번에 묶어 원래 지정가를
추가 기록한다. 현재 보유 회차의 잔여 단타 수량만 처리하며 manage도 같은 기록을 읽는다.
같은5분 구간의 같은 회차/종목 매도는 중복 발급하지 않는다. 시세/계좌/권한/매도가능수량
검사는 유지하고 새 보유 회차는 옛 기록과 분리한다. 마감/손실/명시적 정리는 기존 경로가
우선하며 정상 전략 기록의 오류가 이 경로를 막지 않는다.

운용 신호 소비 계약: WAIT_BROKER는 일부 종목 처리 대기일 수 있어 해당 수집 세대를
완료로 표시하지 않는다. 다음 관리 이후 같은 자료를 다시 기존 전략/주문 검사에 넣는다.
새 자료 세대는 별도로 처리하며 수집 오류는 캐시를 비운다. 종료 시 자식 수집기 취소
확인만 무시하고 부모 운용기 취소는 INTERRUPTED·지속 정리 요청을 남겨 전달한다.

# 전진 관찰 기록 재계산 계약

`execution.intraday_forward.assess_forward`는 읽기 전용 SQLite 복사에서 각 사건의
원본 봉과 수신시각을 기존 모의 엔진으로 다시 계산한다. 같은 소스·사전등록·공급자의
forward/비합성 장부만 허용한다. 보고서 합격 표시와 재작성된 해시만으로 통과하지 않는다.
고정 이후 완결 거래일 수와 부족분, 불완전/지연일 수를 반환한다. 기록 자체가 없는 날은
관찰일에 포함되지 않는다. 고정 이전 기록도 무결성 검사는 하되 관찰일에서 제외한다.

입력 고정 시각의 진위와 체결 동등성은 이 함수의 범위가 아니다. 반환값은 두 검증 모두
false로 명시하며 실제 주문 자격을 부여하지 않는다. 현재 시험은 인공 시세로 계산 경로를
검사한 것이며 실제 시장의 60일 관찰 실적이 아니다.

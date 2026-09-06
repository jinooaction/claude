# 명령 계약

`scripts/intraday_runtime.py collect --provider alpaca|kis --start UTC --end UTC --out NEW_DIR`
는 새 배치만 생성한다. 기존 출력 경로를 덮어쓰지 않는다. Alpaca의 두 키는
`APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`, KIS는 `KIS_APP_KEY`, `KIS_APP_SECRET`이다.
키를 인수로 받거나 출력하지 않는다. KIS token cache는 별도 private 경로다.

`paper --bars-dir DIR --state NEW_OR_EXISTING_DB`는 177 manifest를 검증한 자료를
진단 재생한다. `run --provider kis --state DB --out NEW_ROOT --poll-seconds 60`
는 매번 별도 수집 배치를 만들고 신선한 확정 봉을 반영한다. `status --state DB`는
읽기 전용이다. live 모드/주문 명령은 없다. API 조회 실패/잘못된 입력은 exit2이며
키 누락은 `DATA_ACCESS_REQUIRED`다. 반복 실패는 프로세스를 종료하여 감시자가 인식한다.

자료 공급자 변경, 실행 모형 변경, synthetic 변경은 기존 장부에 합치지 않는다.

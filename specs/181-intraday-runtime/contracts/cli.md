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

`service`는 systemd가 기존 환경으로 실행하는 단회 감독 명령이다. 기본 저장 위치는
`/var/lib/auto-invest-intraday`, 공유 토큰은 `data/kis_token.json`이다. 배타 잠금을
얻지 못하면 BUSY이며 기존 상태를 덮어쓰지 않는다. 성공/실패는 원자적 상태 JSON에
기록하고 API 실패는 다음 예약에서 복구한다. 장외에는 마지막 완결 세션 원본만
보관하며 소급 데이터를 전진 판단에 반영하지 않는다.

`service-status`는 상태 파일만 읽는다. 미실행 NOT_STARTED, 180초 초과 STALE,
오형식 INVALID_STATUS를 구분한다. 고정 원격 명령 `observe intraday-paper-status`는
인수 없이 timer 상태, service 결과, 생산 커밋과 이 JSON을 반환한다. 원격 명령으로
수집/서비스 시작/주문 실행은 할 수 없다. 60세션 자격은 항상 0으로 표시한다.

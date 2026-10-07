# 설계 판단

- 결정: 별도 래퍼로 기존 조회만 확장한다. 기존6개 지문 파일 변경은 모의 세대를 바꾸므로 피한다.
- 근거: scripts/intraday_runtime.py의 _apply가 observed를 process에 전달하고 payload.observed에 저장한다. publish는 후속 시각을 observed_at_utc에 저장한다.
- 대안: 게시 시각에서 수신/처리 시각 역산은 원본 근거가 없어 거절. 새 수집기/새 HMAC키 설치는 비목표다.
- 기존 collect_attested_kis에는 started_at/received_at이 있지만 service_cycle은 attest_market_data를 쓰지 않는다. 서명 확인 없이 시각을 가져오지 않는다.
- 마지막 기록의 지문/이전 연결은 전체 사슬 검증이 아니다. LATEST_RECORD_LOCAL_LINK 범위를 명시한다.
- 실제209 예약배포는37647142926/112880774412의 원래 감사와 sidecar에서 확인했다. 상관키ffa5c5244ae5ac28b1e362732cffe29c, 시작19818/완료19823,2026-10-06 21:00:15.743UTC,d22→07932,DEPLOY_COMPLETED/live다. 새모드/주문/자본 변화 없음.

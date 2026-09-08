# 자료 모델

- SourceQuote는 수신시각과 발생시각을 분리하며, 26필드의 종목·구독키·시장·가격과
  한국/현지 원문 날짜·시간을 보존한다. 실행용 snapshot은 현재 발생시각 나이 0~30초만 반환한다.
- BuyingPower는 symbol, exchange, limit_price, foreign_orderable_amount,
  foreign_orderable_qty, started_at, completed_at을 묶는다. 음수·소수 수량은 거절한다.
- 상태 파일은 schema=184, run_id, phase, updated_at, last_result만 저장한다.
  인증값·계좌번호 없음. 상태는 원자 교체, 프로세스는 별도 파일 잠금으로 소유한다.
- stop 파일은 현재 run_id에 묶인다. 과거 중지 요청으로 새 실행을 중단시키지 않는다.
- external_holdings는 기존 기준표 로더의 정규화된 종목→양의 정수 수량을 복사한 읽기 전용 매핑.
  실행 엔진의 일별 기준과 주문 결과에는 정렬된 JSON의 SHA-256 해시만 추가한다.
  공용 체결 장부와 합산 대조하며 단타 소유에는 포함하지 않는다.

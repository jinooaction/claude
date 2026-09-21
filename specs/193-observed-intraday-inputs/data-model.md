# 자료 모델

- Scope: 고정 symbols/start/end/calendar; 종목/날짜 제외 없음.
- Source: symbol/path/SHA256/provider/adjustment/issuer_lineage_status.
- MinuteObservation: timezone-aware UTC start, OHLCV; 유한 양의 가격과 음이 아닌 거래량.
- WindowObservation: expected_start/end, observed_count, missing_timestamps,
  complete, available_at; 불완전이면 OHLCV 없음.
- Availability: as_of, required_windows, missing/pending 사유; 미래 자료 사용 없음.
- PriceObservation: requested_at, observed_at, available_at, reference_open,
  observed_volume_available, status(EXACT/LATER/NOT_YET_OBSERVABLE/MISSING).
  EXACT는 정각 체결이 아니라 해당 시각에 시작하는 분봉의 첫 체결 가격이다.
  원본만으로 첫 체결 순간을 모르므로 보수적 available_at은 분 종료다.
  fill_verified=false, capacity_unknown=true를 유지한다.
  늦은 관측은 당초 시각으로 소급하지 않는다.
- AuditReport: scope/source fingerprints, 예상/실제/완성/누락 수,
  lineage 상태, live_eligible=false. 전략 판정/자본/포지션 필드 없음.

원본 유효성 오류는 실행 실패다. 정상 격자의 관측 부재는 감사 결과이며 삭제되지 않는다.
미래 원본이 잘못돼 전체 로더가 실패하는 것과 과거 시점 적격성 판정은 구분한다.

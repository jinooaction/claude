# 자료 계약

고정 입력은 `research-207-public-minute-fcfd9a6c3fe2209830aeaa7adf1725be62788d6f`의6자산이다.
각 크기/SHA는 구현의 INPUT_ASSETS에 봉인한다. 파일 이름을 외부 입력으로 만들지 않는다.
원래207 SourceFile/AAD/nonce·인증 함수와 전체 평문 지문을 재사용한다.

월 결과: month, calendar_sessions, regular_minutes_by_symbol, missing_minutes_by_symbol,
minute_complete_sessions_by_symbol/common_complete_minute_sessions는 분누락 없는 실제 날짜다.
complete_sessions_by_symbol/common_complete_sessions는 추가로 양의 거래량·운영 정규화까지 통과한 실제 날짜다.
sessions는 모든 날짜·5종목을 포함한다. 두 완전성 기준을 합치지 않는다.
일별 결과: expected_minutes/expected_bins, observed_minutes, complete_bins,
missing_bins, zero_volume_bins, usable_bins, complete_session. 누락 봉에는 가격을 만들지 않는다.
시각 모형: 정규장에 맞춘5분 시작/종료, modeled_available_at=종료+60초.
내부 OHLCV는 기존normalize에만 전달하며 보고서에는 가격/집계 거래량/수익률을 넣지 않는다.

출력의 source_authenticated와analysis_complete는 별도다. 오류는 부분 분석을 완료라고 하지 않는다.
provider_eligible/strategy_eligible/promotion_eligible=false,orders_submitted=0,returns_examined=false가 항상 유지된다.
claimed→authenticated→analysis_complete→retained 순서이며 각 실패/완료를 덮어쓰지 않는다.

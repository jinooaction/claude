# 자료와 상태

Bar: symbol, timestamp(UTC 5분 시작), open/high/low/close, volume.
Batch: provider/feed/adjustment, retrieved_at, request interval, raw pages and SHA256, CSV manifest.
Runtime identity: preregistration SHA256, execution_model=limit-next-5m-v1, provider, synthetic.
Event: monotonic sequence, previous hash, payload hash, processed bar timestamp,
observed timestamp, bar digest, decisions, resulting state. UPDATE/DELETE 금지.
State: 후보별 cash/positions/pending orders, 해당일 aggregated signal bars, halt reasons.
Order: fixed limit, side, qty, created bar end; expires after next eligible 5분봉.
Fill: quantity bounded by volume/cash/exposure, fee, resulting cash/position.
Status: model/identity, events, simulated fills, remaining positions, halt reasons,
live_eligible=false, orders_submitted=0, forward_promotion_eligible=false.

일자 변경 시 잔량이 있으면 신규 매수를 계속 차단하고 다음 정규장에 고정 지정가
청산만 요청한다. 이전 세션 잔량을 0으로 바꾸지 않는다. 데이터 정정은 기존 사건을
고치지 않고 실행을 거부한다.

service-status 보기1.1: scope=DIAGNOSTIC_PAPER_SERVICE,
program_readiness=NOT_ASSESSED, blockers는 진단 경로 전용·미평가 조건이다.
실거래/승격 거짓·실주문0·자격 세션0은 해당 서비스의 값이다. 정확한1.0 원본을
읽으면 보기1.1과source_schema_version=1.0을 반환하지만 원본 파일은 바꾸지 않는다.
알 수 없는 버전·필드·범위·권한·옛/새 혼합은 INVALID_STATUS다.

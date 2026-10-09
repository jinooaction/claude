# 자료 구조

`collection_record`: schema1, scope DIAGNOSTIC_COLLECTION_RECORD, integrity_scope LATEST_RECORD_LOCAL_LINK.
상태 RECORDED_UNAUTHENTICATED 또는 UNAVAILABLE. 고정 authentication_verified/authority_assessed/completion_time_assessed/provider_publication_assessed는 false다.

세부값: bar_start_utc/model_bar_end_utc/runtime_observed_at_utc/collection_started_at_utc/collection_returned_at_utc/collection_duration_seconds/return_to_observation_seconds/event_hash.
UNAVAILABLE이면 모두 null. 이유 PROOF_ABSENT, PROOF_INVALID, RECORD_UNAVAILABLE, READER_BUSY, NO_RECORDED_BAR 중 하나다.
정상 이유 LOCAL_COLLECTION_FIELDS_ONLY. 시작/반환 원문UTC를 유지하고 차이는 원래 시각으로 계산한다. 서명/가격/계좌/collector 지문/전체 payload는 출력하지 않는다.

원래event는 변경하지 않는다. 상태나 자격 전이 없음. 출력 구조·같은 timing의 봉/관측/hash를 재검증하되 출력 자체로 원래 서명/가격을 재인증하지 않는다.

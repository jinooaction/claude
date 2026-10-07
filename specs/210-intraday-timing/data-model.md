# 자료 모형

schema1/scopeDIAGNOSTIC_TIMING, 상태RECORDED 또는UNAVAILABLE, 고정 이유,
source_integrity_scope=LATEST_RECORD_LOCAL_LINK, authority_assessed=false,
collection_times_assessed=false, completion_time_assessed=false, provider_publication_assessed=false.
정상은 bar_start_utc/model_bar_end_utc/runtime_observed_at_utc/status_published_at_utc,
runtime_observation_lag_seconds/status_publication_lag_seconds/runtime_observation_within_90s/event_hash.
미확인은 같은8개 항목이 null이다. 저장된 관측은 처리 완료가 아니다.
모형 종료+90초 여부는 자격 판정이 아니다. 가격/계좌/HMAC서명/키/원래payload 출력 없음.

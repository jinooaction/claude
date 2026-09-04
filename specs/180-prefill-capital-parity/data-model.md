# 데이터 계약

입출력 형식 추가 없음. LadderDecision1.0의 RESIZE/new_sentinel_text를 재사용한다.
특별 갱신은 operational_canary/rung1, operational_ready, 새 예산과
operational_verdict.expected_operational_capital_usd의 정확 일치가 필요하다.
성과는 schema_version1.2, mode live, measurement_scope strategy, 64자리 sha256 식별자,
정수(불리언 제외) fills_count0, data_quality_warnings 빈 배열이어야 한다.
같은 금액이면 sentinel 없음. 변경 시 rung_entered 보존, run_seq+1,
account_nav_usd 현재값, capital_usd=floor(NAV×0.10), entry_route 보존.
일반 갱신·손실 방어·전략 mismatch는 이전 계약 그대로다.

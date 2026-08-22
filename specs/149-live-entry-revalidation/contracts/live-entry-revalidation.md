# Contract: Live Entry Revalidation

입력은 최신 `profit_evidence.json`, 강화 캐너리 JSON, 전략 범위 live performance JSON이다.

출력 JSON은 `schema_version`, `allowed`, `state`, `fills_count`, `reasons`, `evidence`를 포함한다. 입력 누락·손상은 `allowed=false`다. `fills_count>0`이면 `ACTIVE_LIVE_TRACK`으로 기존 라이브 위험 게이트에 위임한다. `fills_count=0`이면 탐색 진입 계약 전체가 PASS여야 `ENTRY_READY`다.

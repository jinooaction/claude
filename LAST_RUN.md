# 전략 합격 경로 감사

- 후보: `regime-corr24-thr0p2-weak6-cash`
- 역사 관문: 7/8 통과
- 실패 관문: recent_segment_wins
- 전체 교정 범위: `PARTIAL_COVERAGE`
- 전진 검출력: `UNDERPOWERED` — paper 42.40%, live 15.45%, 요구 80%
- 결론: 역사적으로 유망하지만 연구 합격·실자본 적격 후보는 아니다.
- 안전: 주문 0건, 자본 변경 없음, 라이브 전략 변경 없음.

## 동결 후 레짐 관찰

{
  "schema_version": "regime-forward-observation-v1",
  "candidate_id": "regime-corr24-thr0p2-weak6-cash",
  "candidate_fingerprint": "sha256:f006b817472a487f5d115fc9b833cf3d850e7e092bf576826db954c913adf512",
  "incumbent_id": "globalfixed-ensemble-3-6-9-12",
  "frozen_through": "2026-07",
  "minimum_observations": 20,
  "paper_psr_threshold": 0.8,
  "live_psr_threshold": 0.95,
  "promotion_allowed": false,
  "orders_submitted": 0,
  "capital_changed": false,
  "live_strategy_changed": false,
  "n_obs": 0,
  "observation_start": null,
  "observation_end": null,
  "active_return_psr": null,
  "status": "OBSERVATION_WAIT"
}

## workflow metadata

| 항목 | 값 |
| --- | --- |
| run_id | [REDACTED_ACCOUNT] |
| commit | fc5af9557c9657327bf6ef0e41089951b7cf32ae |
| timestamp_utc | 2026-08-30T14:55:42Z |
| safety | no orders, no capital change, no live strategy change |

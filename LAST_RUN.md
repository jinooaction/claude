# 풀라이브 승격 준비(헌법 VI 게이트) — 최신 평가

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| commit | aa6aa482534d2f192b197de04af2bb9008383b2e |
| trigger | schedule |
| timestamp_utc | 2026-09-05T00:12:59Z |
| READY (VI 트랙레코드) | false |
| ssh_exit | 1 (0=READY,1=NOT READY,그외=셋업/오류) |

> 주의: 이건 헌법 VI(라이브 트랙레코드) 게이트다. 실제 풀라이브 승격은
> 스펙 007 하드닝 캐너리(IX.B-2, ≥30/45 거래일)도 통과해야 한다. 이 평가는
> 승격을 수행하지 않는다(보고 전용).

## promote-check 출력(JSON)

```json
{
  "ready": false,
  "checks": {
    "min_duration": true,
    "track_record": false,
    "drawdown_within_acceptance": false,
    "non_negative_return": false,
    "circuit_breaker_clear": true,
    "reconciliation_clear": false
  },
  "reasons": [
    "라이브 기간 73/10일 충족",
    "청산 거래 0건(최소 1) 미달",
    "최대 낙폭 측정 불가(None) → 불합격(보수적)",
    "총수익률 측정 불가(None) → 불합격(보수적)",
    "서킷브레이커 트립 이력 없음 → 충족",
    "정합성 불일치 이력 있음 → 불합격"
  ]
}
```

## stderr

```
```

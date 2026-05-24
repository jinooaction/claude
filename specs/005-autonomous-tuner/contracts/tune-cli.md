# Contract — `auto-invest tune` CLI + auto-tuner-report.json

## CLI 표면

```
auto-invest tune [OPTIONS]
```

| 옵션 | 기본 | 의미 |
|------|------|------|
| `--apply / --dry-run` | `--dry-run` | `--apply`: L1 자동 적용. `--dry-run`: 분석만(파일·감사 미변경) |
| `--db PATH` | `data/auto_invest.db` | SQLite 경로 |
| `--thresholds PATH` | `config/llm_kpi_thresholds.toml` | 튜닝 대상 임계값 파일 |
| `--kernel PATH` | `.specify/memory/kernel.toml` | Kernel 매니페스트 |
| `--as-of DATE` | 오늘(UTC) | 기준 세션 날짜(`YYYY-MM-DD`). 윈도 끝 = 이 날짜 23:59:59Z |
| `--window-short` | `7d` | 단기 롤링 윈도(드리프트 감지) |
| `--window-long` | `30d` | 장기 롤링 윈도(안정성 판정·조이기) |
| `--min-sample N` | `20` | 헌법 X 최소 표본(미만이면 거부) |
| `--output-root PATH` | (없음) | 주면 `{root}/{session_date}/auto-tuner-report.json` 작성 |
| `--json / --no-json` | `--no-json` | `--json`: stdout에 `TunerRunResult` JSON |

### 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 정상(적용 0건 포함 — 장 시간/표본 부족 스킵도 정상) |
| 2 | 사용법/검증 오류(잘못된 날짜, 파일 없음, 윈도 파싱 실패) |
| 3 | 내부 오류 |

### 불변

- `--dry-run`(기본)은 **어떤 파일도 수정하지 않고 어떤 감사도 기록하지 않는다**(SC-A03).
- `--apply`라도 장 시간 마진 안이면 L1 적용 0건(SC-A06), 측정 부족이면 0건(SC-A07).
- 같은 `--as-of`로 `--apply`를 두 번 = 한 번만 적용·기록(SC-A04, 세션-날짜 dedup).
- 어떤 입력으로도 `kernel.toml`·`constitution.md`를 자동 수정하지 않는다(SC-A09).

## auto-tuner-report.json 스키마 (`TunerRunResult` 직렬화)

```json
{
  "schema_version": "1.0",
  "session_date": "2026-05-24",
  "generated_at_utc": "2026-05-24T22:10:03.too1Z",
  "mode": "apply",
  "candidates": [
    {
      "candidate_id": "threshold_tighten:latency_p95_ms",
      "detection_rule": "threshold_tighten",
      "kpi_name": "latency_p95_ms",
      "observed_value": "1400",
      "observed_tier": "B",
      "window": "30d",
      "authority_tier": "L1",
      "kernel_groups": [],
      "classification_reason": "non-kernel config knob → L1",
      "proposed": {
        "kind": "threshold_tighten",
        "target_paths": ["config/llm_kpi_thresholds.toml"],
        "config_key": "latency_p95_ms.tier_b",
        "old_value": "2000",
        "new_value": "1760"
      },
      "rationale": "30일 집계 Tier B + 일별 Tier C 없음, 표본 충분 → tier_b를 tier_a 쪽으로 20% 조임",
      "measurement_sample": 42
    }
  ],
  "applied": [
    {
      "candidate_id": "threshold_tighten:latency_p95_ms",
      "config_key": "latency_p95_ms.tier_b",
      "old_value": "2000",
      "new_value": "1760",
      "audit_seq": 1234
    }
  ],
  "canary_entered": [],
  "awaiting_human_merge": [],
  "skipped": [
    ["threshold_tighten:cache_hit_rate", "insufficient_measurement"]
  ]
}
```

### 정합 불변
- `applied` 길이 == 그 실행에서 기록된 `AUTO_TUNED_L1` 감사 행 수(SC-A08).
- `awaiting_human_merge`의 각 항목은 `kernel_groups` 비어있지 않음(L4는 Kernel 터치).
- dry-run이면 `applied`·`canary_entered`·`awaiting_human_merge`는 분석 결과를 담되 **감사 미기록**(`mode=="dry_run"`).

# 공개 데이터 수집 채널 — 최신 실행 (계획 ④, 연구 전용)

라이브 매매 신호는 계속 KIS 데이터만 사용 — 이 브랜치의 데이터는
연구·백테스트·검증 전용이다. 검증 통과분만 발행되며, 전 항목의
합격/불합격은 summary.json 에 있다.

| 항목 | 값 |
|------|-----|
| run_id | 31236477085 |
| run_url | https://github.com/jinooaction/claude/actions/runs/31236477085 |
| commit | 758dda2534af38f444ac75361295fb49b489e234 |
| trigger | schedule |
| timestamp_utc | 2026-08-08T03:07:01Z |
| collect_exit | 0 |
| overall_ok | True |
| published (발행 항목 수) | 11 |

## summary.json

```json
{
  "schema_version": "2.0",
  "as_of": "2026-08-08",
  "overall_ok": true,
  "published": 11,
  "total_items": 11,
  "elapsed_seconds": 8.9,
  "cross_checks": [
    {
      "pair": "bls:CUUR0000SA0 vs dbnomics:BLS/cu/CUUR0000SA0",
      "kind": "levels",
      "status": "PASS",
      "overlap": 13,
      "agree_pct": "100.00",
      "max_abs_diff": "0.000000",
      "detail": "일치 13/13 (100.00%) — 허용 오차 ±0.001, 합격선 100%"
    },
    {
      "pair": "treasury:UST2Y vs dbnomics:FED/H15/RIFLGFCY02_N.B",
      "kind": "levels",
      "status": "PASS",
      "overlap": 2399,
      "agree_pct": "100.00",
      "max_abs_diff": "0.000000",
      "detail": "일치 2399/2399 (100.00%) — 허용 오차 ±0.001, 합격선 99.5%"
    },
    {
      "pair": "treasury:UST10Y vs dbnomics:FED/H15/RIFLGFCY10_N.B",
      "kind": "levels",
      "status": "PASS",
      "overlap": 2399,
      "agree_pct": "100.00",
      "max_abs_diff": "0.000000",
      "detail": "일치 2399/2399 (100.00%) — 허용 오차 ±0.001, 합격선 99.5%"
    },
    {
      "pair": "treasury:UST2Y vs fred:DGS2",
      "kind": "levels",
      "status": "PASS",
      "overlap": 2399,
      "agree_pct": "100.00",
      "max_abs_diff": "0.000000",
      "detail": "일치 2399/2399 (100.00%) — 허용 오차 ±0.001, 합격선 99.5%"
    },
    {
      "pair": "treasury:UST10Y vs fred:DGS10",
      "kind": "levels",
      "status": "PASS",
      "overlap": 2399,
      "agree_pct": "100.00",
      "max_abs_diff": "0.000000",
      "detail": "일치 2399/2399 (100.00%) — 허용 오차 ±0.001, 합격선 99.5%"
    }
  ],
  "probes": [
    {
      "url": "https://stooq.com/q/d/l/?s=spy.us&i=d",
      "user_agent": "channel",
      "status": 200,
      "ok": true,
      "elapsed_ms": 583,
      "content_head": "<!DOCTYPE html><html><head><meta charset=\"utf-8\"><meta name=\"robots\" content=\"noindex,nofollow\"></head><body><noscript>This site requires JavaScript to verify your browser. Please enable JavaScript an"
    },
    {
      "url": "https://stooq.com/q/d/l/?s=spy.us&i=d",
      "user_agent": "httpx-default",
      "status": 404,
      "ok": false,
      "elapsed_ms": 453,
      "content_head": "<meta charset=utf-8><title>Stooq</title><center style=font-family:arial;margin-top:50px><p><a href=/><img src=//static.stooq.com/stooq.svg height=68></a><p style=font-size:x-large>The page you request"
    },
    {
      "url": "https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json",
      "user_agent": "channel",
      "status": 400,
      "ok": false,
      "elapsed_ms": 159,
      "content_head": "{\"error_code\":400,\"error_message\":\"Bad Request.  Variable api_key is not set.  Read https:\\/\\/fred.stlouisfed.org\\/docs\\/api\\/api_key.html for more information.\"}"
    },
    {
      "url": "https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json",
      "user_agent": "httpx-default",
      "status": 400,
      "ok": false,
      "elapsed_ms": 149,
      "content_head": "{\"error_code\":400,\"error_message\":\"Bad Request.  Variable api_key is not set.  Read https:\\/\\/fred.stlouisfed.org\\/docs\\/api\\/api_key.html for more information.\"}"
    }
  ],
  "items": [
    {
      "kind": "fred",
      "id": "DGS2",
      "ok": true,
      "rows": 13093,
      "first_date": "1976-06-01",
      "last_date": "2026-08-06",
      "missing": 551,
      "issues": [],
      "published": "fred/DGS2.csv"
    },
    {
      "kind": "fred",
      "id": "DGS10",
      "ok": true,
      "rows": 16853,
      "first_date": "1962-01-02",
      "last_date": "2026-08-06",
      "missing": 719,
      "issues": [],
      "published": "fred/DGS10.csv"
    },
    {
      "kind": "treasury",
      "id": "UST2Y",
      "source_label": "2 Yr",
      "ok": true,
      "rows": 2400,
      "first_date": "2017-01-03",
      "last_date": "2026-08-07",
      "missing": 0,
      "issues": [],
      "published": "treasury/UST2Y.csv"
    },
    {
      "kind": "treasury",
      "id": "UST10Y",
      "source_label": "10 Yr",
      "ok": true,
      "rows": 2400,
      "first_date": "2017-01-03",
      "last_date": "2026-08-07",
      "missing": 0,
      "issues": [],
      "published": "treasury/UST10Y.csv"
    },
    {
      "kind": "treasury",
      "id": "UST10Y2Y",
      "derived": true,
      "ok": true,
      "rows": 2400,
      "first_date": "2017-01-03",
      "last_date": "2026-08-07",
      "missing": 0,
      "issues": [],
      "published": "treasury/UST10Y2Y.csv"
    },
    {
      "kind": "cboe",
      "id": "VIX",
      "ok": true,
      "rows": 9246,
      "first_date": "1990-01-02",
      "last_date": "2026-08-07",
      "missing": 0,
      "issues": [],
      "published": "cboe/VIX.csv"
    },
    {
      "kind": "bls",
      "id": "LNS14000000",
      "ok": true,
      "rows": 31,
      "first_date": "2024-01-01",
      "last_date": "2026-07-01",
      "missing": 1,
      "issues": [],
      "published": "bls/LNS14000000.csv"
    },
    {
      "kind": "bls",
      "id": "CUUR0000SA0",
      "ok": true,
      "rows": 30,
      "first_date": "2024-01-01",
      "last_date": "2026-06-01",
      "missing": 1,
      "issues": [],
      "published": "bls/CUUR0000SA0.csv"
    },
    {
      "kind": "dbnomics",
      "id": "BLS/cu/CUUR0000SA0",
      "ok": true,
      "rows": 1345,
      "first_date": "1913-01-01",
      "last_date": "2025-01-01",
      "missing": 0,
      "issues": [],
      "published": "dbnomics/BLS_CU_CUUR0000SA0.csv"
    },
    {
      "kind": "dbnomics",
      "id": "FED/H15/RIFLGFCY02_N.B",
      "ok": true,
      "rows": 13093,
      "first_date": "1976-06-01",
      "last_date": "2026-08-06",
      "missing": 551,
      "issues": [],
      "published": "dbnomics/FED_H15_RIFLGFCY02_N.B.csv"
    },
    {
      "kind": "dbnomics",
      "id": "FED/H15/RIFLGFCY10_N.B",
      "ok": true,
      "rows": 16853,
      "first_date": "1962-01-02",
      "last_date": "2026-08-06",
      "missing": 719,
      "issues": [],
      "published": "dbnomics/FED_H15_RIFLGFCY10_N.B.csv"
    }
  ],
  "isolation_note": "연구 전용 — 라이브 매매 신호는 KIS 데이터만 사용"
}
```

## 거시 레짐 보고 (연구 전용 — 라이브 신호 아님)

```json
{
  "schema_version": "1.0",
  "as_of": "2026-08-08",
  "indicators": {
    "yield_curve": {
      "status": "OK",
      "state": "FLAT",
      "latest": "0.46",
      "latest_date": "2026-08-07",
      "inverted_days_252": 0,
      "stress": false,
      "source": "treasury/UST10Y2Y.csv"
    },
    "vix": {
      "status": "OK",
      "state": "CALM",
      "latest": "14.900000",
      "latest_date": "2026-08-07",
      "history_percentile": "31.4",
      "history_obs": 9246,
      "stress": false,
      "source": "cboe/VIX.csv"
    },
    "inflation": {
      "status": "OK",
      "state": "HIGH",
      "yoy_pct": "3.53",
      "latest_date": "2026-06-01",
      "stress": true,
      "source": "bls/CUUR0000SA0.csv"
    },
    "sahm": {
      "status": "OK",
      "state": "QUIET",
      "sahm_value_pp": "0.00",
      "current_ma3": "4.20",
      "latest_date": "2026-07-01",
      "stress": false,
      "source": "bls/LNS14000000.csv"
    }
  },
  "overall": {
    "label": "CAUTION",
    "stress_flags": [
      "inflation"
    ],
    "available_indicators": 4,
    "total_indicators": 4,
    "note": "연구 전용 — 라이브 매매 신호 아님 (라이브 신호는 KIS 데이터만)"
  }
}
```

## 읽는 법

```bash
git fetch origin automation/public-data
git show origin/automation/public-data:treasury/UST10Y2Y.csv  # 10년-2년 금리차 (date,value)
git show origin/automation/public-data:cboe/VIX.csv           # VIX 종가 1990~ (date,value)
git show origin/automation/public-data:bls/CUUR0000SA0.csv    # CPI 월간 (date,value)
git show origin/automation/public-data:regime.json            # 거시 레짐 보고 (연구 전용)
git show origin/automation/public-data:regime_timeline.csv    # 일별 레짐 이력 (층화 분석 입력)
git show origin/automation/public-data:summary.json           # 검증 보고
```

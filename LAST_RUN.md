# 공개 데이터 수집 채널 — 최신 실행 (계획 ④, 연구 전용)

기본 용도는 연구·백테스트·검증이다. 검증 통과분만 발행되며,
검증을 통과한 공개자료 기반 전략만 후보·지문·신선도·커밋
관문을 거쳐 주문 전 증거로 읽는다. 이 채널은 주문하지 않는다.

| 항목 | 값 |
|------|-----|
| run_id | 34677231695 |
| run_url | https://github.com/jinooaction/claude/actions/runs/34677231695 |
| commit | aeb175bc1894684d7467adfb13e80b08a658a093 |
| trigger | schedule |
| timestamp_utc | 2026-09-12T06:05:57Z |
| collect_exit | 0 |
| overall_ok | False |
| published (발행 항목 수) | 22 |

## summary.json

```json
{
  "schema_version": "2.0",
  "as_of": "2026-09-12",
  "source_commit": "aeb175bc1894684d7467adfb13e80b08a658a093",
  "generated_at_utc": "2026-09-12T06:05:56.235667+00:00",
  "overall_ok": false,
  "published": 22,
  "total_items": 27,
  "elapsed_seconds": 13.0,
  "cross_checks": [
    {
      "pair": "fred:CPIAUCNS vs dbnomics:BLS/cu/CUUR0000SA0",
      "kind": "levels",
      "status": "PASS",
      "overlap": 1345,
      "agree_pct": "100.00",
      "max_abs_diff": "0.000000",
      "detail": "일치 1345/1345 (100.00%) — 허용 오차 ±0.001, 합격선 100%"
    },
    {
      "pair": "treasury:UST2Y vs dbnomics:FED/H15/RIFLGFCY02_N.B",
      "kind": "levels",
      "status": "PASS",
      "overlap": 2422,
      "agree_pct": "100.00",
      "max_abs_diff": "0.000000",
      "detail": "일치 2422/2422 (100.00%) — 허용 오차 ±0.001, 합격선 99.5%"
    },
    {
      "pair": "treasury:UST10Y vs dbnomics:FED/H15/RIFLGFCY10_N.B",
      "kind": "levels",
      "status": "PASS",
      "overlap": 2422,
      "agree_pct": "100.00",
      "max_abs_diff": "0.000000",
      "detail": "일치 2422/2422 (100.00%) — 허용 오차 ±0.001, 합격선 99.5%"
    },
    {
      "pair": "treasury:UST2Y vs fred:DGS2",
      "kind": "levels",
      "status": "PASS",
      "overlap": 2423,
      "agree_pct": "100.00",
      "max_abs_diff": "0.000000",
      "detail": "일치 2423/2423 (100.00%) — 허용 오차 ±0.001, 합격선 99.5%"
    },
    {
      "pair": "treasury:UST10Y vs fred:DGS10",
      "kind": "levels",
      "status": "PASS",
      "overlap": 2423,
      "agree_pct": "100.00",
      "max_abs_diff": "0.000000",
      "detail": "일치 2423/2423 (100.00%) — 허용 오차 ±0.001, 합격선 99.5%"
    }
  ],
  "probes": [
    {
      "url": "https://stooq.com/q/d/l/?s=spy.us&i=d",
      "user_agent": "channel",
      "status": 200,
      "ok": true,
      "elapsed_ms": 591,
      "content_head": "<!DOCTYPE html><html><head><meta charset=\"utf-8\"><meta name=\"robots\" content=\"noindex,nofollow\"></head><body><noscript>This site requires JavaScript to verify your browser. Please enable JavaScript an"
    },
    {
      "url": "https://stooq.com/q/d/l/?s=spy.us&i=d",
      "user_agent": "httpx-default",
      "status": 404,
      "ok": false,
      "elapsed_ms": 591,
      "content_head": "<meta charset=utf-8><title>Stooq</title><center style=font-family:arial;margin-top:50px><p><a href=/><img src=//static.stooq.com/stooq.svg height=68></a><p style=font-size:x-large>The page you request"
    },
    {
      "url": "https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json",
      "user_agent": "channel",
      "status": 400,
      "ok": false,
      "elapsed_ms": 870,
      "content_head": "{\"error_code\":400,\"error_message\":\"Bad Request.  Variable api_key is not set.  Read https:\\/\\/fred.stlouisfed.org\\/docs\\/api\\/api_key.html for more information.\"}"
    },
    {
      "url": "https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json",
      "user_agent": "httpx-default",
      "status": 400,
      "ok": false,
      "elapsed_ms": 94,
      "content_head": "{\"error_code\":400,\"error_message\":\"Bad Request.  Variable api_key is not set.  Read https:\\/\\/fred.stlouisfed.org\\/docs\\/api\\/api_key.html for more information.\"}"
    }
  ],
  "items": [
    {
      "kind": "fred",
      "id": "DGS3MO",
      "ok": true,
      "rows": 11748,
      "first_date": "1981-09-01",
      "last_date": "2026-09-10",
      "missing": 492,
      "issues": [],
      "published": "fred/DGS3MO.csv"
    },
    {
      "kind": "fred",
      "id": "DGS2",
      "ok": true,
      "rows": 13118,
      "first_date": "1976-06-01",
      "last_date": "2026-09-10",
      "missing": 552,
      "issues": [],
      "published": "fred/DGS2.csv"
    },
    {
      "kind": "fred",
      "id": "DGS5",
      "ok": true,
      "rows": 16878,
      "first_date": "1962-01-02",
      "last_date": "2026-09-10",
      "missing": 720,
      "issues": [],
      "published": "fred/DGS5.csv"
    },
    {
      "kind": "fred",
      "id": "DGS10",
      "ok": true,
      "rows": 16878,
      "first_date": "1962-01-02",
      "last_date": "2026-09-10",
      "missing": 720,
      "issues": [],
      "published": "fred/DGS10.csv"
    },
    {
      "kind": "fred",
      "id": "DGS30",
      "ok": true,
      "rows": 12933,
      "first_date": "1977-02-15",
      "last_date": "2026-09-10",
      "missing": 545,
      "issues": [],
      "published": "fred/DGS30.csv"
    },
    {
      "kind": "fred",
      "id": "HQMCB10YR",
      "ok": true,
      "rows": 512,
      "first_date": "1984-01-01",
      "last_date": "2026-08-01",
      "missing": 0,
      "issues": [],
      "published": "fred/HQMCB10YR.csv"
    },
    {
      "kind": "fred",
      "id": "HQMCB20YR",
      "ok": true,
      "rows": 512,
      "first_date": "1984-01-01",
      "last_date": "2026-08-01",
      "missing": 0,
      "issues": [],
      "published": "fred/HQMCB20YR.csv"
    },
    {
      "kind": "fred",
      "id": "CPIAUCNS",
      "ok": true,
      "rows": 1364,
      "first_date": "1913-01-01",
      "last_date": "2026-08-01",
      "missing": 1,
      "issues": [],
      "published": "fred/CPIAUCNS.csv"
    },
    {
      "kind": "fred",
      "id": "SAHMREALTIME",
      "ok": true,
      "rows": 801,
      "first_date": "1959-12-01",
      "last_date": "2026-08-01",
      "missing": 1,
      "issues": [],
      "published": "fred/SAHMREALTIME.csv"
    },
    {
      "kind": "fred",
      "id": "DEXUSAL",
      "ok": true,
      "rows": 14525,
      "first_date": "1971-01-04",
      "last_date": "2026-09-04",
      "missing": 570,
      "issues": [],
      "published": "fred/DEXUSAL.csv"
    },
    {
      "kind": "fred",
      "id": "DEXCAUS",
      "ok": true,
      "rows": 14525,
      "first_date": "1971-01-04",
      "last_date": "2026-09-04",
      "missing": 557,
      "issues": [],
      "published": "fred/DEXCAUS.csv"
    },
    {
      "kind": "fred",
      "id": "DEXJPUS",
      "ok": true,
      "rows": 14525,
      "first_date": "1971-01-04",
      "last_date": "2026-09-04",
      "missing": 569,
      "issues": [],
      "published": "fred/DEXJPUS.csv"
    },
    {
      "kind": "fred",
      "id": "DEXUSUK",
      "ok": true,
      "rows": 14525,
      "first_date": "1971-01-04",
      "last_date": "2026-09-04",
      "missing": 563,
      "issues": [],
      "published": "fred/DEXUSUK.csv"
    },
    {
      "kind": "fred",
      "id": "IRSTCI01AUM156N",
      "ok": false,
      "rows": 431,
      "first_date": "1990-08-01",
      "last_date": "2026-06-01",
      "missing": 0,
      "issues": [
        "신선도 위반: 마지막 관측 2026-06-01 이 103일 전"
      ]
    },
    {
      "kind": "fred",
      "id": "IRSTCI01CAM156N",
      "ok": false,
      "rows": 618,
      "first_date": "1975-01-01",
      "last_date": "2026-06-01",
      "missing": 0,
      "issues": [
        "신선도 위반: 마지막 관측 2026-06-01 이 103일 전"
      ]
    },
    {
      "kind": "fred",
      "id": "IRSTCI01JPM156N",
      "ok": false,
      "rows": 492,
      "first_date": "1985-07-01",
      "last_date": "2026-06-01",
      "missing": 0,
      "issues": [
        "신선도 위반: 마지막 관측 2026-06-01 이 103일 전"
      ]
    },
    {
      "kind": "fred",
      "id": "IRSTCI01GBM156N",
      "ok": false,
      "rows": 582,
      "first_date": "1978-01-01",
      "last_date": "2026-06-01",
      "missing": 0,
      "issues": [
        "신선도 위반: 마지막 관측 2026-06-01 이 103일 전"
      ]
    },
    {
      "kind": "fred",
      "id": "IRSTCI01USM156N",
      "ok": false,
      "rows": 864,
      "first_date": "1954-07-01",
      "last_date": "2026-06-01",
      "missing": 0,
      "issues": [
        "신선도 위반: 마지막 관측 2026-06-01 이 103일 전"
      ]
    },
    {
      "kind": "treasury",
      "id": "UST2Y",
      "source_label": "2 Yr",
      "ok": true,
      "rows": 2424,
      "first_date": "2017-01-03",
      "last_date": "2026-09-11",
      "missing": 0,
      "issues": [],
      "published": "treasury/UST2Y.csv"
    },
    {
      "kind": "treasury",
      "id": "UST10Y",
      "source_label": "10 Yr",
      "ok": true,
      "rows": 2424,
      "first_date": "2017-01-03",
      "last_date": "2026-09-11",
      "missing": 0,
      "issues": [],
      "published": "treasury/UST10Y.csv"
    },
    {
      "kind": "treasury",
      "id": "UST10Y2Y",
      "derived": true,
      "ok": true,
      "rows": 2424,
      "first_date": "2017-01-03",
      "last_date": "2026-09-11",
      "missing": 0,
      "issues": [],
      "published": "treasury/UST10Y2Y.csv"
    },
    {
      "kind": "cboe",
      "id": "VIX",
      "ok": true,
      "rows": 9271,
      "first_date": "1990-01-02",
      "last_date": "2026-09-11",
      "missing": 0,
      "issues": [],
      "published": "cboe/VIX.csv",
      "close_sanity": {
        "status": "PASS",
        "checked_rows": 9271
      }
    },
    {
      "kind": "bls",
      "id": "LNS14000000",
      "ok": true,
      "rows": 32,
      "first_date": "2024-01-01",
      "last_date": "2026-08-01",
      "missing": 1,
      "issues": [],
      "published": "bls/LNS14000000.csv"
    },
    {
      "kind": "bls",
      "id": "CUUR0000SA0",
      "ok": true,
      "rows": 32,
      "first_date": "2024-01-01",
      "last_date": "2026-08-01",
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
      "rows": 13117,
      "first_date": "1976-06-01",
      "last_date": "2026-09-09",
      "missing": 552,
      "issues": [],
      "published": "dbnomics/FED_H15_RIFLGFCY02_N.B.csv"
    },
    {
      "kind": "dbnomics",
      "id": "FED/H15/RIFLGFCY10_N.B",
      "ok": true,
      "rows": 16877,
      "first_date": "1962-01-02",
      "last_date": "2026-09-09",
      "missing": 720,
      "issues": [],
      "published": "dbnomics/FED_H15_RIFLGFCY10_N.B.csv"
    }
  ],
  "isolation_note": "기본 연구용 — FACTORY_EDGE 공개자료 기반 전략만 후보·지문·신선도·커밋 관문 뒤 주문 전 증거로 사용"
}
```

## 거시 레짐 보고 (연구 전용 — 라이브 신호 아님)

```json
{
  "schema_version": "1.0",
  "as_of": "2026-09-12",
  "indicators": {
    "yield_curve": {
      "status": "OK",
      "state": "FLAT",
      "latest": "0.33",
      "latest_date": "2026-09-11",
      "inverted_days_252": 0,
      "stress": false,
      "source": "treasury/UST10Y2Y.csv"
    },
    "vix": {
      "status": "OK",
      "state": "NORMAL",
      "latest": "15.840000",
      "latest_date": "2026-09-11",
      "history_percentile": "37.7",
      "history_obs": 9271,
      "stress": false,
      "source": "cboe/VIX.csv"
    },
    "inflation": {
      "status": "OK",
      "state": "HIGH",
      "yoy_pct": "3.40",
      "latest_date": "2026-08-01",
      "stress": true,
      "source": "bls/CUUR0000SA0.csv"
    },
    "sahm": {
      "status": "OK",
      "state": "QUIET",
      "sahm_value_pp": "-0.07",
      "current_ma3": "4.13",
      "latest_date": "2026-08-01",
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

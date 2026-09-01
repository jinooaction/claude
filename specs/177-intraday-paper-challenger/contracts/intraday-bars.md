# 장중 5분 봉 입력 계약

## 디렉터리

입력 디렉터리는 다음 파일을 정확히 포함한다.

```text
manifest.json
SPY.csv
QQQ.csv
IWM.csv
TLT.csv
GLD.csv
```

추가 파일은 무시하지만 manifest가 가리키는 경로는 단순 파일명이어야 하며 상위 디렉터리나
절대경로를 포함할 수 없다.

## CSV 열

각 파일은 UTF-8, 쉼표 구분, 헤더 1행이며 열 순서는 다음과 같다.

```csv
timestamp_utc,symbol,open,high,low,close,volume
```

- `timestamp_utc`: 5분 봉 시작 시각. ISO-8601 UTC `Z`, 초·마이크로초는 0.
- `symbol`: 파일명과 같은 허용 심볼.
- `open/high/low/close`: 양수, 유한, `low <= open,close <= high`.
- `volume`: 1 이상 정수.
- 행은 시각 오름차순이며 중복 시각이 없어야 한다.
- XNYS 정규장 개장 이상, 폐장 미만의 봉만 허용한다.
- 한 세션 안에서 5분 간격이 빠지면 해당 세션은 불완전하다. 임의 보간하지 않는다.

## manifest.json

```json
{
  "schema_version": "1.0",
  "dataset_id": "provider-batch-id",
  "provider": "licensed-provider-name",
  "retrieved_at_utc": "2026-09-02T00:00:00Z",
  "adjustment_policy": "split-adjusted; dividend treatment documented",
  "base_timeframe_minutes": 5,
  "synthetic": false,
  "files": {
    "SPY": {"path": "SPY.csv", "sha256": "sha256:<64 hex>", "rows": 1},
    "QQQ": {"path": "QQQ.csv", "sha256": "sha256:<64 hex>", "rows": 1},
    "IWM": {"path": "IWM.csv", "sha256": "sha256:<64 hex>", "rows": 1},
    "TLT": {"path": "TLT.csv", "sha256": "sha256:<64 hex>", "rows": 1},
    "GLD": {"path": "GLD.csv", "sha256": "sha256:<64 hex>", "rows": 1}
  }
}
```

`sha256`은 CSV 원본 바이트의 소문자 SHA-256이다. 행 수는 헤더를 제외한다. 둘 중 하나라도
실제 파일과 다르면 연구 결과를 만들지 않는다.

## 합성 자료

시험 fixture는 반드시 `synthetic=true`다. 합성 자료는 엔진·오류·재현성 시험에만 사용하며
`PAPER_CHALLENGER`가 될 수 없다.

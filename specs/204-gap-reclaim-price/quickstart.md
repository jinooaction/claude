# 실행 안내

가격 성과 확인 전에 사전등록 계약 커밋을 먼저 남긴다. stage는 낮은 우선순위와
쉬는 구간으로 기존30파일 전체 지문을 확인해 필요한 원문 행만 별도 폴더에 전달한다.

```sh
nice -n 19 uv run python scripts/gap_reclaim_price_diagnostic.py stage --manifest /absolute/source/manifest.json --bars-dir /absolute/source --output-dir /absolute/new-fixture --throttle-seconds 0.05
uv run python scripts/gap_reclaim_price_diagnostic.py score --fixture-dir research-fixtures/204 --output /absolute/new-result.json
uv run python scripts/gap_reclaim_price_diagnostic.py verify --fixture-dir research-fixtures/204 --evidence /absolute/new-result.json
```

score/verify는 원격에서 실행한다. 축소본 지문 잠금이 없으면 score를 거부한다.
verify는 기존 산출물을 읽기 전용으로 재계산한다. 양수여도 자본이나177 합격·181 완료를 만들지 않는다.

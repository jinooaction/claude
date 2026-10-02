# Reproduce the offline audit

고정 공급자 자료는 공개 데이터셋 `ZipLime/sec-8k-events`의
`096a24de11c29748f4270d13493b9ea49d03accd` 개정에서 받는다.

```bash
curl -fL --retry 2 -o /tmp/ziplim-sec-acceptance-096a24de.parquet \
  https://huggingface.co/datasets/ZipLime/sec-8k-events/resolve/096a24de11c29748f4270d13493b9ea49d03accd/metadata/acceptance.parquet
curl -fL --retry 2 -o /tmp/ziplim-sec-earnings-096a24de.parquet \
  https://huggingface.co/datasets/ZipLime/sec-8k-events/resolve/096a24de11c29748f4270d13493b9ea49d03accd/data/earnings_8k/part-00000.parquet
uv run python scripts/earnings_metadata_audit.py \
  --manifest specs/201-earnings-clock-input/source-manifest.json \
  --acceptance /tmp/ziplim-sec-acceptance-096a24de.parquet \
  --earnings /tmp/ziplim-sec-earnings-096a24de.parquet \
  --mirror-dir /Users/mason/Projects/claude-data-research/20260921-hf-raw/event-source-pilot-v1/public-mirror-audit-v1/primary-rows-v1 \
  --output /tmp/earnings-metadata-audit-201.json
```

로컬 본문 137개가 없으면 현재 공시 원문 수집 결과를 복원한 뒤 실행한다.
명령은 그 본문이 2014년에 공개됐다는 증명을 만들지 않는다. 이메일은 원본
다운로드/오프라인 검증 명령에 필요 없고 파일에 기록되지 않는다.

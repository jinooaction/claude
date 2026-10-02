# Offline diagnostic

201 감사 JSON과 194의 30개 변환 CSV/manifest를 준비한다. 출력은 새 JSON이다.
이 입력은 저장소 밖에 있으며 실거래 자격 증명이 필요 없다.

```bash
uv run python scripts/earnings_event_price_diagnostic.py \
  --audit /path/to/earnings-metadata-audit.json \
  --manifest /path/to/sparse-194-input-v1/manifest.json \
  --bars-dir /path/to/sparse-194-input-v1 \
  --output /path/to/new-development-result.json
```

원본 지문이 계약과 다르면 거절한다. 기존 출력은 덮어쓰지 않는다.
개발 진단이 양수여도 `PAPER_CHALLENGER` 또는 실거래 허가가 아니다.

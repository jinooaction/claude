# Quickstart

```bash
uv run auto-invest reconcile-recover \
  --confirm \
  --db data/auto-invest.db \
  --halt-path data/HALT \
  --env .env \
  --external-holdings deploy/external-holdings.toml \
  --opening-positions deploy/live-opening-positions.toml \
  --portfolio config/portfolio.toml \
  --format json
```

이 명령은 새 정합성 검사를 수행하지만 주문은 제출하지 않는다. 정합성 오류에서 생긴 halt만 모든 계약이 유효할 때 조건부로 해제한다.


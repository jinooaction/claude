# 구현과 실제 자료 검증

2026-09-21: 신규 입력 라이브러리·감사 CLI 구현. 아직 출시 전이다.
관련23시험 통과, 전체 src/tests 및 신규 CLI ruff 통과.
초기 미구현 모듈 수집 실패 후 구현했고, 지연 바인딩 lint2건은 반복 변수 고정으로 수정했다.

실제 RTX/DD는 원본 SHA256 확인 후 PiTrading만2014-03-01~2020-03-06으로
잘랐다. 시각은 America/New_York→UTC 변환, 가격/거래량은 변경하거나 채우지 않았다.
로컬 `observed-input-193/manifest.json`, `report-v1.json`을 보존했다.
실행77211 exit0, 별도 CSV/달력 검사와 모든 날짜의 누락 마스크가 일치했다.

|종목|예상 거래일|완전 거래일|누락 분봉|
|---|---:|---:|---:|
|DD|1515|1323|288|
|RTX|1515|1125|761|

이것은 관측 감사 성공이며 가격 연결 검증/전략 통과가 아니다.
issuer_lineage_status=unverified, strategy_admitted=false, live_eligible=false,
generated_prices=0, orders_submitted=0을 유지했다.
원본 경로는 `/Users/mason/Projects/claude-data-research/20260921-hf-raw/` 아래다.
전체 회귀·출시·배포 해당 여부 확인은 아직 남았다.

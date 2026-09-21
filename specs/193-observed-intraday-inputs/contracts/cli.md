# 연구 입력 감사 CLI 계약

예정 명령: `uv run python scripts/observed_intraday_probe.py --manifest PATH --output PATH`
입력 manifest: schema_version=1, symbols, start, end, calendar=XNYS,
각 파일의 path/sha256/provider/adjustment/issuer_lineage_status.
CSV 필드: timestamp_utc,symbol,open,high,low,close,volume. 원본 간격1분.
출력: 지문, 종목별 전체 달력의 minute/5분 완성·누락 수, 미확인 식별 상태,
live_eligible=false. 기존 파일 덮어쓰기 거부. 비정상 입력 exit2, 감사 성공 exit0.
감사 성공은 자료 완전/회사 연결/전략 통과를 의미하지 않는다.
이 CLI에는 주문, 계좌, 전략 수익률, 확인용 가격 자동 조회 옵션이 없다.

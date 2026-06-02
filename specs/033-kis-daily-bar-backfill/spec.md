# 스펙 033 — KIS 해외 일봉 백필 (forward 페이퍼 트랙 활성화)

## 왜

스펙 032 forward 페이퍼 트랙(`rebalance-paper-forward.yml`)이 인스턴스에서 무거래였다.
진단(`bars-status`) 결과 인스턴스의 `price_bars` 테이블이 완전히 비어 있었다
(`db_timeframes: []`). 재조정 스코어러는 저장된 일봉을 읽는데, 워커는 일봉을 적재하지
않아(시세→합성 바만, 그조차 dry-run에선 0) 스코어가 비어 아무것도 거래되지 않았다.

해법: KIS 해외주식 기간별시세(시세 조회 엔드포인트)로 유니버스의 최근 일봉을
`price_bars`에 채운다. 그러면 재조정이 점수를 매겨 실제 페이퍼 거래를 시작한다.

## 안전 경계 (중요)

- **읽기 전용 시세 조회.** `get_daily_bars`는 `/uapi/overseas-price/v1/quotations/dailyprice`
  (기간별시세, tr_id HHDFS76240000)만 호출한다. **주문·취소·잔고변경 0건. 돈 안 움직임.**
  `get_quote`와 같은 위험 등급(quotations).
- 쓰기 대상은 `price_bars`(시세 캐시)뿐 — 감사 로그·포지션·주문 테이블 무관.
  insert-or-skip 멱등(기존 행 보존). Kernel(K1~K6) 터치 0건.
- 라이브 캐너리/실거래와 무관. 페이퍼 트랙을 데이터로 채울 뿐.

## 슬라이스

1. **브로커 계층** (`broker/overseas.py`): `_parse_daily_bars(rows, symbol)` 순수 파서 +
   `get_daily_bars(client, ..., symbol, market)` async 호출. `OverseasDailyBar` 데이터클래스
   (symbol·date·OHLCV). low/high 클램프로 OHLCV 검증 호환. 단위 테스트 4건.
2. **CLI** (`backfill-bars`): `--portfolio`(유니버스) 또는 `--symbols` 의 심볼별로 EXCD
   목록(NAS→NYS→AMS)을 순서대로 시도해 일봉을 받아 `price_bars`에 저장(timeframe=1d).
   시크릿 없으면 안전 거부. 멱등.
3. **워크플로 배선**: `rebalance-paper-forward.yml` 재조정 단계 **앞**에 backfill-bars 단계
   추가 → 매 실행 유니버스 일봉을 먼저 채운 뒤 재조정. 결과를 사이드카에 발행.

## 재현 / 확인

```bash
# 인스턴스(KIS 시크릿 보유 환경)에서:
auto-invest backfill-bars --portfolio deploy/canary-portfolio.toml --env-file .env
auto-invest bars-status   --portfolio deploy/canary-portfolio.toml   # count > 0 확인
auto-invest rebalance-once --portfolio deploy/canary-portfolio.toml --mode paper --capital 12000
# 또는 automation/rebalance-paper.request 갱신 머지로 워크플로 자동 발화.
```

EXCD 매핑: AAPL·MSFT = NAS(NASDAQ), SPY = AMS(NYSE Arca). 코드가 자동으로 순서 시도하므로
심볼별 거래소를 하드코딩하지 않는다(빈 응답이면 다음 EXCD).

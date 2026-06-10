-- Migration 0003: order_routing 사이드카 — correlation_id → 제출 거래소(OVRS_EXCG_CD).
--
-- 주문은 종목별 거래소로 나가는데(시세→주문 거래소 자동 해석, 2026-06-10) 취소·재호가는
-- 주문이 *실제로 나간* 거래소로 가야 한다. KIS 정정취소(order-rvsecncl)는 OVRS_EXCG_CD 가
-- 원주문과 일치해야 하므로, 제출 시점에 라우터가 쓴 거래소를 여기 기록하고 수명 관리
-- (스펙 030)가 읽는다. row 가 없으면(과거 주문·단일 거래소 룰 워커) 설정된 기본 주문
-- 거래소로 폴백한다 — 회귀 0.
--
-- ALTER TABLE ADD COLUMN 은 IF NOT EXISTS 가드가 불가능해(부분 적용 재시도 안전 정책,
-- db.py 모듈 독스트링) orders 컬럼 추가 대신 사이드카 테이블로 둔다.

CREATE TABLE IF NOT EXISTS order_routing (
    correlation_id TEXT PRIMARY KEY,
    order_exchange TEXT NOT NULL
);

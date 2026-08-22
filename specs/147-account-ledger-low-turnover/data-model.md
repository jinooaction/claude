# Data Model

## MeasurementContract

- `contract_id`: 포함·제외 규칙의 SHA-256 지문.
- `scope`: `strategy` 또는 `account`.
- `excluded_symbols`: 검증된 시작 전 보유 종목.
- `source_path`: 검증 파일 경로.

## NavPoint

- 기존 시각·NAV·자본 기준.
- `measurement_contract_id`: 같은 성과 정의인지 구분하는 선택 필드.
- 상태 전이: 레거시 `None` -> 새 계약 ID. 서로 다른 계약은 한 수익곡선에 섞지 않는다.

## StrategyPerformanceReport

- 기존 전략 체결·손익 필드.
- `measurement_contract_id`.
- `excluded_symbols`, `excluded_fills_count`, `excluded_realized_pnl_usd`.
- `evidence_quality`: `VALID` 또는 `BLOCKED`.

## ResumeReadiness

- `status`: `RESUME_ELIGIBLE`, `BLOCKED`, `STALE`.
- `reconciliation_state`, `halt_present`, `measurement_quality`.
- `reasons`: 모든 차단 이유.
- 주문·취소·halt 변경 필드는 존재하지 않는다.

## LowTurnoverDecision

- 날짜, 목표 비중, 현금 비중, 회전율.
- 종목별 보유 나이.
- 거래 억제 사유와 횟수.
- 비용 차감 전후 예측 우위.

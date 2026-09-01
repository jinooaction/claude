# 데이터 모델: 비용 현실형 장중매매 페이퍼 챌린저

## IntradayDataManifest

| 필드 | 형식 | 규칙 |
|---|---|---|
| `schema_version` | 문자열 | `1.0` |
| `dataset_id` | 문자열 | 공급자·수집 배치를 식별하는 고유값 |
| `provider` | 문자열 | 비어 있지 않음 |
| `retrieved_at_utc` | UTC 시각 | 미래 시각 금지 |
| `adjustment_policy` | 문자열 | 분할·배당 조정 방식을 설명 |
| `base_timeframe_minutes` | 정수 | 정확히 5 |
| `synthetic` | 불리언 | true면 합격 판정 금지 |
| `files` | 객체 | 5개 심볼별 경로·SHA-256·행 수 |

manifest와 실제 파일 바이트·행 수가 다르면 입력 전체가 무효다.

## IntradayBar

| 필드 | 형식 | 규칙 |
|---|---|---|
| `symbol` | 문자열 | SPY·QQQ·IWM·TLT·GLD 중 하나 |
| `timestamp_utc` | UTC 시각 | 5분 봉 시작, 심볼 안에서 고유·오름차순 |
| `open/high/low/close` | 양의 십진수 | `low <= open,close <= high` |
| `volume` | 1 이상 정수 | 정규장 0이면 자료 품질 실패 |
| `session_date` | 날짜 | XNYS 달력으로 계산 |
| `session_offset_minutes` | 정수 | 개장부터 0,5,10... |

입력 CSV에는 앞의 7개 원시 필드만 있고 세션 필드는 검증기가 계산한다.

## ResampledBar

| 필드 | 형식 | 규칙 |
|---|---|---|
| `timeframe_minutes` | 15·30·60 | 사전등록 값 |
| `bar_index` | 정수 | 세션 개장부터 0 기반 |
| `open/high/low/close/volume` | 수 | 구성 5분 봉의 표준 OHLCV 집계 |
| `complete` | 불리언 | 기대 5분 봉 수가 모두 있을 때 true |
| `entry_eligible` | 불리언 | complete이며 마지막 부분 봉이 아님 |

불완전 봉은 신호·체결에 쓰지 않는다. 마지막 부분 60분 봉은 당일 청산 가격으로만 쓴다.

## IntradayCandidate

| 필드 | 형식 | 규칙 |
|---|---|---|
| `candidate_id` | 문자열 | 18개 전역 고유 ID |
| `family` | 열거 | `momentum`, `opening_range_breakout`, `vwap_mean_reversion` |
| `timeframe_minutes` | 정수 | 15·30·60 |
| `variant` | 열거 | `fast`, `slow` |
| `parameters` | 객체 | 사전등록과 완전 일치 |
| `strategy_fingerprint` | SHA-256 | 공통 경계+후보 본문 지문 |

## SimulatedFill

| 필드 | 형식 | 규칙 |
|---|---|---|
| `candidate_id`, `symbol` | 문자열 | 등록 후보·허용 심볼 |
| `side` | BUY·SELL | 롱·현금만 허용 |
| `signal_at_utc` | UTC 시각 | 닫힌 신호 봉 종료 시각 |
| `eligible_at_utc` | UTC 시각 | `signal_at_utc`보다 늦음 |
| `filled_at_utc` | UTC 시각/null | 체결 때만 존재 |
| `requested_qty`, `filled_qty` | 정수 | `0 <= filled <= requested` |
| `unfilled_qty` | 정수 | `requested_qty - filled_qty` |
| `reference_price`, `fill_price` | 양의 수 | 다음 봉 시가와 불리한 비용 적용가 |
| `commission_usd`, `spread_usd`, `slippage_usd` | 0 이상 수 | 비용별 분리 |
| `fill_status` | FULL·PARTIAL·UNFILLED | 수량과 일치 |
| `reason` | 문자열 | 미체결·부분 체결 사유 포함 |
| `gross_pnl_usd`, `net_pnl_usd` | 수/null | 매도 체결에서만 실현 손익 기록 |
| `holding_minutes` | 정수/null | 매도 체결에서만 실제 보유 분 기록 |

## CandidateEvaluation

| 영역 | 핵심 필드 |
|---|---|
| 동일성 | 후보 ID·지문·가족·주기·변형 |
| 완전성 | 세션·거래·주문·체결·미체결 수 |
| 구간 | development·block·confirmation |
| 성과 | 총수익, 연율 샤프, PSR, 최대낙폭, 이익계수, 양수 분기 비율 |
| 비용 | 수수료·호가·미끄러짐·회전율, 기준·스트레스 결과 |
| 집중도 | 종목별 양의 기여, 상위 5거래 양의 기여 |
| 과최적화 | 개발 8구간 점수, 가족·전체 PBO, DSR |
| 판정 | 통과·실패 관문 목록 |

## IntradayPaperEvidence

| 영역 | 핵심 필드 |
|---|---|
| 계약 | `schema_version=1.0`, `gate_version=intraday-paper-v1` |
| 자료 | manifest·원본·정규화 지문, 세션 범위·수, 품질 사유 |
| 사전등록 | 파일 지문, 18후보 registry와 registry 지문 |
| 선택 | 개발 점수만으로 정한 selected candidate |
| 평가 | 모든 18개 기준·스트레스 평가 |
| 결정 | 상태, 필수 관문, 실패 사유, 다음 단계 |
| 감사 | JSONL 행 수·SHA-256 |
| 안전 | 자본 0, 라이브 적격 false, 승격 false, 주문 0 |

### 상태 전이

```text
입력 부족/손상 ─────────────> INSUFFICIENT_EVIDENCE
완전 입력 + 관문 실패 ──────> NO_INTRADAY_EDGE
완전 입력 + 모든 관문 통과 ─> PAPER_CHALLENGER
```

이 계약에는 라이브·자본 상태로 가는 전이가 없다.

# HANDOFF-144 — Profit Evidence Engine

## 상태

#613이 `main`에 merge되어 설명용 후보 계약을 반복하던 구조가 시간 분리 수익 검증 구조로 바뀌었다. 실제 공개 장기 자료에서는 `three_asset_fixed-w10`이 역사 최종 검증을 통과했지만, 최신 전진 관찰은 아직 기준 미달이므로 실주문은 잠겨 있다.

## 찾은 방법과 결과

- 사전등록 후보: 자산배분 3개 x 추세 창 6·8·10·12개월 = 12개.
- 개발 구간: 1971-02~2006-12, 최종 검증: 2007-01~2026-07, 겹침 0개월.
- 비용: 연 50bp 차감.
- 선택 후보: `three_asset_fixed-w10`.
- 최종 검증 후보: 연복리 8.76027%, 샤프 1.75316, 최대낙폭 4.610754%.
- 벤치마크: 연복리 8.291414%, 샤프 1.264685, 최대낙폭 17.268823%.
- 8개월·12개월 인접 창도 샤프와 낙폭 기준을 통과해 역사 판정은 `HOLDOUT_EDGE`다.
- `globalfixed` 전진 관찰: 41회, PSR 0.82727, 기준 0.95, 판정 `NO_EDGE`.

따라서 현재 상태는 `FORWARD_VALIDATION`이다. 이는 “돈 벌 가능성이 있는 방법을 찾았다”는 뜻이지 “미래 수익이나 실주문이 승인됐다”는 뜻이 아니다.

## 구현

- `src/auto_invest/analytics/profit_evidence_engine.py`: 고정 후보, 시간 분리, 비용 차감, 벤치마크·인접 창 관문.
- `scripts/profit_evidence_engine_probe.py`: 공개 자료와 최신 forward leaderboard 결합.
- `.github/workflows/profit-evidence-engine.yml`: 매일 읽기 전용 sidecar 발행.
- `candidate_result_executor.py`: 장기 역사, 최근 표본 외, 전진 분할 증거를 명령별로 분리하며 혼합 결과는 `pending`으로 보존.
- `candidate_history_support.py`와 원격 관문: `global-trend-fixed`를 `data/forward_globalfixed.db`에 연결.

## 확인 증거

- PR #613, 기능 커밋 `015cf4e`, merge commit `046d0f8`.
- 전체 검증: 2807 passed, 5 skipped; ruff와 `git diff --check` 통과.
- 엄격 하네스: 14/14, HANDOFF 사실 검증 OK, PR 품질 관문 성공.
- 배포 run `31915116844`: success.
- 수익 증거 run `31915116859`: success, `HOLDOUT_EDGE` / `FORWARD_VALIDATION`.
- 후보 결과 run `31915116877`: success. 서버 `globalfixed` 이력 수집 성공, upstream blocked 패키지 2개는 그대로 blocked 보존.
- released-work run `31915116841`: success. 이 run 시점에는 T021~T022가 미완료여서 스펙 138은 아직 소비 전이며 이 HANDOFF merge 뒤 재확인한다.
- KIS smoke run `31915164816`: 새 커밋에서 4/5 통과. 최근 주문 조회 `inquire-ccnl`만 외부 HTTP 500으로 실패했다.

## 안전 경계와 다음 관찰

실제 주문, 실거래 전환, 자본 배분, live 재무장, whitelist/caps, 손실 예산, KIS 비밀값, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다. `Backtest -> Canary -> Full`도 그대로다.

다음 세션은 새 `profit-evidence-engine` sidecar와 `globalfixed` PSR을 먼저 읽는다. PSR 0.95와 기존 다중검정·전략 지문·캐너리·자본 사다리를 모두 통과하기 전에는 실주문을 열지 않는다. KIS 최근 주문 조회도 다음 정기 smoke 결과로 재확인한다.

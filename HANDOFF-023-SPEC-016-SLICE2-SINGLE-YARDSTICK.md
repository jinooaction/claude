# HANDOFF 023 — 백테스트 단일 잣대 통일 (스펙 016 슬라이스 2, 2026-05-27)

PR #79 머지 커밋 `83abbbb`. **세계 최고 수준 로드맵 2단계 — 측정 잣대 통일**을
완료했습니다. 슬라이스 1이 백테스트를 정직하게(거래비용·슬리피지) 만들었다면,
슬라이스 2는 백테스트와 라이브가 **같은 거래 단위 지표 정의**를 쓰게 해서 헌법
원칙 X.2("단일 잣대")를 완성합니다.

## 왜 (고친 갭)

헌법 X.2는 라이브·페이퍼·캐너리·백테스트가 같은 지표 정의를 써야 한다고 규정합니다.
슬라이스 1이 비용을 통일했지만 **거래 단위 지표는 여전히 갈라져 있었습니다**:

- 승률·평균손익·손익비가 라이브 성과 엔진(`performance/engine.py`)에만 인라인으로
  있었고 **백테스트엔 통째로 없었습니다** — 백테스트 결과로는 한 전략의 승률조차
  볼 수 없는데 라이브 성과는 보여줬습니다(다른 잣대).
- 둘 다 **Sortino(하방 위험만 보는 샤프의 동생)가 없었습니다**.
- 공식이 라이브에만 있어 백테스트가 같은 걸 계산하려면 코드를 복제해야 했고,
  그러면 두 잣대가 서로 갈라질 위험이 있었습니다(X.2 위반).

## 한 줄 요약

- **공용 단일 정의(`backtest/metrics.py`)**: `sortino_ratio`(하방편차 기준, 연율화
  √252, MAR=RFR=0) + `win_loss_stats`(승률·평균이익·평균손실·손익비) +
  `realized_closed_trades`(평균단가 실현거래 재구성, 보유 초과 매도는 보유분 클램프)를
  추가. 이제 거래 단위 잣대가 한 곳에 산다.
- **라이브 엔진(`performance/engine.py`)**: `compute_risk_metrics`·`realized_trades`가
  공용 정의를 호출(인라인 공식 제거). `RiskMetrics`에 `sortino_ratio` 추가, 리포트
  JSON `schema_version` 1.1 → 1.2, 텍스트 렌더에 Sortino 줄 추가.
- **백테스트(`data_model`·`report`·`run`)**: 비용 반영 체결(`per_rule_fills`)에서
  공용 정의로 거래 단위 지표를 계산해 `RuleBacktestResult`(closed_trades·win_rate·
  profit_factor·sortino_ratio)·`BacktestSummary`(aggregate_sortino·
  total_closed_trades·aggregate_win_rate·aggregate_profit_factor)에 담고,
  `metrics.csv`·`backtest-run.json`·`summary.md`에 노출. 포트폴리오 승률·손익비는
  전 룰의 청산을 한데 모아(pooled) 계산.
- **안전 경계**: 오프라인·읽기 전용(라이브 주문 경로 무수정, 돈 안 움직임). **Kernel
  터치 0건** — 손댄 파일 전부 `backtest/`·`performance/engine.py`(둘 다 비커널)·
  `tests/`·`specs/`. K1~K6·K-meta 무변경. **감사 스키마(K4) 무변경** — Sortino를 튜너용
  `LIVE_PERFORMANCE_SNAPSHOT` 페이로드(K4)에 넣는 것은 의도적으로 후속 K4 추가-전용
  작업으로 미뤘습니다(이번 슬라이스는 커널 0건 유지).
- **검증**: 테스트 신규 18건(전체 1058 통과, 4 스킵), 린트 깨끗. 핵심 증명(SC-D01)은
  `tests/unit/test_metrics_single_yardstick.py` — 같은 논리적 체결 시퀀스가 백테스트·
  라이브 경로에서 **동일한 청산 손익·승률·손익비**를 냄.

## 다음 세션이 이어받을 것 (세계 최고 수준 로드맵)

측정 토대 1·2단계(정직·통일)가 끝났습니다. 다음은:

- **슬라이스 3 — 워크포워드(표본 외) 검증**: 롤링 윈도우로 과적합을 탐지하는 검증
  하니스. 정직·통일된 잣대 위에서 비로소 의미를 가지는 다음 단계. `specs/016-backtest-cost-model/spec.md`의 "후속 슬라이스" 절 참조.
- 그 뒤: 신호/알파 과학(다요인·레짐 인식)·포지션 사이징(변동성·상관).
- **후속 K4(선택)**: Sortino를 `LIVE_PERFORMANCE_SNAPSHOT`에 추가해 자율 튜너가 하방
  위험 시계열을 읽게 함(K4 추가-전용 터치 1건).

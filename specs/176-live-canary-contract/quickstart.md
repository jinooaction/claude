# 빠른 실행: 증거 수렴형 실거래 검증 캐너리

## 1. 좁은 계약 검사

```bash
uv run pytest tests/unit/test_operational_canary_evidence.py \
  tests/unit/test_capital_ladder.py \
  tests/unit/test_live_entry_revalidation.py
```

운영 증거가 참이어도 `alpha_confirmed=false`, `capital_fraction=0.10`, `max_rung=1`이어야 한다.

## 2. 전체 로컬 검사

```bash
uv run pytest
uv run ruff check src tests
uv run python scripts/agent_harness_probe.py --strict
uv run python scripts/check_handoff_facts.py
```

## 3. 생산 증거 확인

main 배포 뒤 profit-evidence sidecar의 `operational_canary_evidence.json`과 strategy-factory
sidecar의 `capital_entry_evidence.json`을 각각 내려받는다. 역할, 코드 커밋, 생성 시각, 후보 ID,
전략 지문을 독립 검사한다. 진단용 `strategy_factory.json`으로 대체하지 않는다.

## 4. 실제 주문 순서

1. 미국 정규장 밖에서 main 배포와 sidecar 갱신을 끝낸다.
2. 자본 사다리가 단 0에서 `entry_route=operational_canary` 단 1로 바뀌었는지 확인한다.
3. 최신 NAV 10%와 정수 주 주문 미리보기가 한도를 넘지 않는지 확인한다.
4. 기존 예약 `rebalance-live-canary` 실행만 사용한다.
5. 주문 접수, KIS 체결 조회, 전략 장부, 계좌 정합, 감사 sidecar를 같은 실행 ID로 맞춘다.
6. 체결이 없으면 완료하지 않고 다음 정규장 실행을 계속 관찰한다.

## 5. 즉시 복구

문제가 생기면 센티넬을 `armed:false`, 단 0, 자본 0으로 내린다. 기존 주문·체결·감사 행은
삭제하지 않는다. 이미 산 전략 보유분은 기존 위험 축소 주문 경로로만 정리한다.

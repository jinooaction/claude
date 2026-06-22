# HANDOFF 060 — 스펙 063 계좌 전체 micro GTAA 자율 재배치 (2026-06-23 KST)

main 베이스라인: `7a14315`(PR #386). 운영자가 "새 입금은 안 되지만 기존 보유는 수익 관점에서
팔 수도, 보유할 수도 있어야 한다"와 "적용 시점부터 실시간으로 지속 자율 운영돼야 한다"고
명시했다. 이 작업은 기존 micro GTAA live canary가 실제 KIS 계좌 전체 포지션과 현금을 읽어,
현금 부족 시 청산 전용 매도부터 실행하고 이후 확인된 현금으로 목표 종목을 사는 지속 루프로
확장한 등급 4 돈 경로 변경이다.

## 무엇이 바뀌었나

- `src/auto_invest/execution/rebalancer.py`: `account_holdings`, `liquidation_only_symbols`,
  `execution_side`, `purchasable_cash_usd`, `cash_buffer_pct` 입력을 추가했다.
- `execute_rebalance`는 브로커 보유를 계좌 전체 입력으로 쓸 수 있고, 관리 제외 보유는 주문하지
  않으며 `withheld` 증거로 남긴다.
- 청산 전용 종목이 목표 매수 후보가 되면 실패 폐쇄한다. 목표 유니버스는 `SPYM`, `IEF`, `GLDM`이다.
- cash shortfall이면 `effective_side=sell` 또는 `none`으로 좁혀 매수 주문을 보류한다.
- `src/auto_invest/cli.py`: `rebalance-once --account-wide --side both|sell|buy`를 추가했다.
  `--account-wide` dry-run은 읽기 전용 KIS 포지션·현금 조회를 수행할 수 있지만 주문은 제출하지
  않는다. 일반 dry-run은 기존처럼 offline이다.
- `deploy/micro-gtaa-live-portfolio.toml`: `[account_rebalance]`와 청산 전용
  `BHP`, `MRK`, `ORANY`, `RELX`를 추가했다.
- `.github/workflows/rebalance-micro-gtaa-canary.yml`: account-wide dry-run preview,
  sell-first preflight, `--side ${SIDE}` live 실행, sidecar/Telegram evidence를 추가했다.
- `specs/063-account-wide-micro-gtaa/`: spec, plan, research, data model, contract, quickstart,
  tasks, requirements checklist를 추가했다.

## 현재 운영 상태

- `automation/rebalance-micro-gtaa.request`는 계속 `armed:true`, `capital_usd:1000`이다.
- PR #386 이후 다음 비-push schedule 또는 manual-dispatch micro GTAA run부터 새 account-wide
  루프가 적용된다.
- push 이벤트는 계속 preview-only다. main merge 자체로 실주문은 제출되지 않는다.
- KIS 매수 가능 현금이 계획 매수 + 1% 완충금보다 부족하고 청산 전용 매도 후보가 있으면, live
  단계는 `--side sell`로 실행된다.
- 매도 대금은 KIS가 매수 가능 현금으로 다시 확인하기 전까지 같은 실행의 매수 재원으로 쓰지 않는다.

## 안전 경계

- 위험 등급: 4(돈 경로 변경)
- 실제 주문 실행: 이 작업 중 수동 실행 없음
- 돈 경로 변경: 있음. 조건 충족 시 기존 보유 청산 전용 매도 주문이 자동 제출될 수 있다.
- K2 설정 표면 변경: 있음. `BHP`, `MRK`, `ORANY`, `RELX`가 sell routing을 위해 whitelist에 추가됐다.
- 목표 매수 유니버스 변경: 없음. `SPYM`, `IEF`, `GLDM`만 목표 매수 대상이다.
- K1/K2 코드, 주문 라우터, K4 감사 로그, K5 비밀값, K6 배포 제한, 헌법, 커널 목록 변경: 없음.
- 모든 live 주문은 기존 `OrderRouter`, 지정가, 정규장, K1 cap, K2 whitelist, 손실 브레이커를 통과한다.

## 검증

PR #386 머지 전:

- `uv run pytest tests/integration/test_spec_032_live_rebalancer.py tests/unit/test_canary_portfolio_config.py tests/unit/test_micro_gtaa_canary.py` → 23 passed
- `uv run pytest` → 2252 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- `git diff --check` → OK
- `ruby -e 'require "yaml"; YAML.load_file(".github/workflows/rebalance-micro-gtaa-canary.yml"); puts "yaml-ok"'` → yaml-ok
- `python3 scripts/check_pr_quality_gate.py --template .github/pull_request_template.md` → pr-quality-gate-ok
- `python3 scripts/check_pr_quality_gate.py /tmp/account-wide-micro-gtaa-pr.md` → pr-quality-gate-ok
- `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`
- `uv run python scripts/check_handoff_facts.py` → OK
- PR #386 상태: ready, `mergeStateStatus=CLEAN`, remote `pr-quality-gate` success

handoff 갱신 직전:

- `uv run ruff check src tests` → All checks passed
- `uv run pytest -q` → stale `HANDOFF.md` 때문에 하네스 2건만 실패했다. 코드 실패가 아니라
  `HANDOFF.md` 마지막 main 커밋 행이 `7a14315`로 갱신되지 않은 문제였다.

handoff 갱신 후:

- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`
- `uv run pytest -q` → 2252 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed

## 다음 세션 한 줄

micro GTAA는 이제 새 입금 없이 기존 보유까지 계좌 전체 자본으로 보고, 현금 부족 시
`BHP`·`MRK`·`ORANY`·`RELX` 청산 전용 매도부터 반복 실행한 뒤 KIS가 확인한 현금으로
`SPYM`·`IEF`·`GLDM` 목표 매수를 진행한다. 최신 sidecar를 먼저 읽고 실제 접수·체결 여부와
다음 기대 단계를 판단한다.

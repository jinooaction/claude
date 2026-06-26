# HANDOFF 063 — 거부 주문 누적 평가와 자율 재지정 피드백 루프 (2026-06-26 KST)

main 베이스라인: `f76aa07`(PR #392). 운영자가 "전략대로 투자했으면 손해였다는 거면 전략이
수정·고도화돼야 하는 것 아니냐, 자율 자동 시스템이 루프를 돌아야 하는 것 아니냐"고 지적했다.
#390은 거부 주문의 단발 현재가 기준 기회손익을 만들었지만, 누적 전략 평가와 자율 재지정 루프의
입력까지는 연결하지 않았다. 이 작업은 그 빈칸을 닫은 등급 2 운영 관측·평가 루프 변경이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/opportunity_monitor.py`: 거부 주문 기회손익 report를 rolling history로
  누적하고 cumulative monitor summary를 계산한다.
- `auto-invest opportunity-monitor`: 기존 history와 이번 opportunity JSON을 받아 history와 monitor
  JSON을 쓰는 CLI를 추가했다. 브로커 호출, 주문 재시도, 전략 변경은 하지 않는다.
- `scripts/opportunity_monitor_sidecar.py`: GitHub Actions runner가 패키지 설치 없이 같은 계산을
  수행하도록 표준 라이브러리 기반 helper를 추가했다.
- `.github/workflows/rebalance-micro-gtaa-canary.yml`: 이전 `opportunity_history.json`을 읽고 이번
  `/tmp/micro_opportunity.json`을 append한다. 최신 sidecar branch에 `opportunity_history.json`,
  `opportunity_monitor.json`, `LAST_RUN.md`의 `## 거부 주문 누적 평가`를 발행한다.
- micro GTAA Telegram 메시지에 `5. 누적 전략/실행 평가` 섹션을 추가했다. verdict, 누적 전략
  의도 손익, 최신 신호, 연속 손실/이익, 다음 조치, 안전 문구를 표시한다.
- `.github/workflows/reassign-on-tournament.yml`: 최신 `opportunity_monitor.json`을 읽어
  `auto-invest reassign-decide --execution-feedback-json`에 넘긴다.
- `src/auto_invest/portfolio/auto_reassign.py`: decision JSON에 `execution_feedback`을 포함한다.
  `effect=evidence_only_no_gate_override`로 명시하며 기존 action 계산은 5중 게이트 그대로다.
- `specs/064-rejected-opportunity-feedback/`: 이 변경의 목표, 비목표, 안전 경계, quickstart를 남겼다.

## 판단 기준

- 단발 `total_opportunity_pnl_usd` 부호는 #390과 같다.
  - 양수: 거부된 주문이 정상 체결됐으면 현재 더 유리했을 가능성.
  - 음수: 거부된 것이 결과적으로 더 유리했을 가능성, 즉 전략 의도가 손실이었을 가능성.
- monitor verdict:
  - `NO_VALUED_REJECTIONS`: 평가 가능한 거부 주문 없음.
  - `INSUFFICIENT_DATA`: 최신 신호는 있으나 자동 판단 표본 부족.
  - `OBSERVE`: 누적 손익이 검토 임계값 안.
  - `STRATEGY_REVIEW`: 전략 의도 손실 신호가 누적됨.
  - `EXECUTION_REVIEW`: 거부 때문에 이익을 놓친 실행 경로 신호가 누적됨.
- 이 verdict는 회계 손익이 아니라 mark-to-current 진단이다. 수수료, 세금, 환율, 실제 체결 가능성은
  제외한다.

## 현재 운영 상태

- PR #392는 merge 방식으로 main에 머지됐다.
- #392 main push의 `Deploy on merge to main` run `28237830935`는 성공했다.
- 같은 커밋의 KIS smoke run `28237830957`도 성공했다:
  `secrets_present=true`, `key_valid=true`, `smoke_state=success`, `smoke_exit=0`.
- money-path run `28237830995`도 성공했고 `live_money_state.status=REAL_ORDER_PATH_ARMED`를
  보고했다. micro GTAA는 계속 `armed:true`, `capital_usd:1000`이다.
- 새 `opportunity_history.json`과 `opportunity_monitor.json`은 다음 micro GTAA workflow 실행부터
  `automation/rebalance-micro-gtaa-last-run`에 나타난다.
- 첫 실행 또는 평가 가능한 거부 주문이 없는 실행에서는 `NO_VALUED_REJECTIONS` 또는
  `INSUFFICIENT_DATA`가 정상이다.

## 안전 경계

- 위험 등급: 2(운영 관측·평가 루프 변경)
- 돈 경로 변경: 없음
- 실제 주문 실행: 없음
- 주문 재시도, 취소, 체결 동기화, 라우터 제출 로직 변경: 없음
- 전략 파일 자동 교체: 없음
- K1/K2 게이트, 자본, whitelist, 포지션 한도, 손실 브레이커, 헌법, 커널 목록 변경: 없음
- `reassign-decide`는 feedback을 JSON에 기록하지만 기존 5중 게이트를 우회하지 않는다.
- 새 CLI는 안전 명령 레지스트리에서 `PROPOSAL`, `can_place_order=false`, `uses_broker=false`다.

## 검증

PR #392 머지 전:

- focused tests 53 통과:
  `tests/unit/test_opportunity_monitor.py`,
  `tests/integration/test_opportunity_monitor_cli.py`,
  `tests/unit/test_micro_gtaa_telegram_alerts.py`,
  `tests/unit/test_micro_gtaa_canary.py`,
  `tests/unit/test_auto_reassign.py`,
  `tests/unit/test_reassign_decide_cli.py`,
  `tests/unit/test_reassign_workflow_leaderboard_json.py`,
  `tests/unit/test_safety_command_registry.py`
- `uv run pytest` → 2274 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14)
- `python3 scripts/check_pr_quality_gate.py /tmp/opportunity_feedback_pr_body.md` → pr-quality-gate-ok
- helper 직접 실행:
  `python3 scripts/opportunity_monitor_sidecar.py --history-json ... --opportunity-json ... --history-out ... --monitor-out ... --format text`
  → 정상 history/monitor 파일 생성

handoff 갱신 직전:

- `uv run pytest -q` → stale `HANDOFF.md` 때문에 하네스 2건만 실패했다. 코드 실패가 아니라
  `HANDOFF.md` 마지막 main 커밋 행이 `4175f13`으로 오래된 문제였다.
- `uv run ruff check src tests` → All checks passed

handoff 갱신 후:

- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14)
- `uv run pytest -q` → 2274 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed

## 다음 세션 한 줄

거부 주문이 전략 문제인지 실행 문제인지 이제 단발 손익이 아니라
`opportunity_history.json` / `opportunity_monitor.json`의 누적 verdict로 본다. `STRATEGY_REVIEW`는
전략 검토 신호지만, 자동 재지정은 여전히 forward 토너먼트·다중검정·캐너리 5중 게이트를 통과해야만 한다.

# HANDOFF 062 — 거부 주문 기회손익과 Telegram 가독성 보강 (2026-06-26 KST)

main 베이스라인: `4175f13`(PR #390). 운영자가 최근 micro GTAA 주문 거부를 두고
"매수가 정상적으로 진행됐다면 지금 돈 벌었는지 잃었는지 판단해야 전략 평가가 가능하다"고 지적했다.
조사 결과 기존 시스템은 실제 체결 성과와 NAV 평가는 일부 갖고 있었지만, 거부된 주문의
가상 체결 기회손익은 자동 계산하지 않았다. 이 작업은 그 관측 표면을 추가하고 Telegram 메시지
가독성을 높인 등급 2 운영 관측 변경이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/order_opportunity.py`: `rebalance-once --json` 결과와 현재가를 받아
  거부된 BUY/SELL 주문의 기회손익을 계산한다.
- 판단 기준은 단순하다. BUY 거부는 `(현재가 - 거부 당시 매수가) * 수량`, SELL 거부는
  `(거부 당시 매도가 - 현재가) * 수량`이다. 양수는 그 주문이 정상 체결됐으면 현재 더 유리,
  음수는 거부된 것이 결과적으로 더 유리하다는 뜻이다.
- `auto-invest rejected-order-opportunity`: 읽기 전용 CLI를 추가했다.
  `--result-json`, `--env-file`, `--db`, `--marks-json`, `--no-marks`, `--format text|json`을 지원한다.
- `.github/workflows/rebalance-micro-gtaa-canary.yml`: live 결과 이후
  `Evaluate rejected order opportunity` 단계를 추가했다. 서버의 `.env`로 KIS 현재가를 읽어
  `/tmp/micro_opportunity.json`을 만들고, 실패하면 유효한 fallback JSON에 실패 사유를 남긴다.
- micro GTAA sidecar에 `## 거부 주문 기회손익` 섹션을 추가했다.
- micro GTAA Telegram 메시지를 실행, 라이브 전제 확인, 주문 결과, 거부 주문 기회손익,
  확인 링크 섹션으로 재구성했다.
- 일반 audit-log Telegram tailer 메시지를 상태, 이벤트, 대상, 진단, 판단 줄로 재구성했다.
  `ORDER_REJECTED_BY_BROKER`는 주문이 접수·체결되지 않았음을 명시한다.
- `specs/060-telegram-order-alerts/`에 FR-015/FR-016과 후속 작업 기록을 추가했다.

## 현재 운영 상태

- PR #390은 merge 방식으로 main에 머지됐다.
- 새 기회손익 평가는 다음 micro GTAA workflow 실행부터 sidecar와 Telegram 알림에 나타난다.
- 실제 Telegram 전송과 실제 서버 KIS 현재가 조회는 이 PR 안에서 수행하지 않았다. 서버 runtime과
  비밀값이 필요한 외부 효과이기 때문이다.
- 현재가 조회가 실패하면 workflow는 실패하지 않고 `mark_fetch_error`, `missing_mark_symbols`,
  `N/A` 기회손익을 보고한다.
- 이 평가는 수수료, 세금, 환율, 실제 체결 가능성을 제외한 단순 현재가 비교다. 전략 평가의
  빠른 방향성 판단용이지 회계 손익 확정값이 아니다.

## 안전 경계

- 위험 등급: 2(운영 관측 변경)
- 돈 경로 변경: 없음
- 실제 주문 실행: 없음
- 주문 재시도, 취소, 체결 동기화, 라우터 제출 로직 변경: 없음
- K1/K2 게이트, 자본, whitelist, 포지션 한도, 손실 브레이커, 헌법, 커널 목록 변경: 없음
- 새 CLI는 안전 명령 레지스트리에 `READ_ONLY`, `can_place_order=false`, `uses_broker=true`로 등록됐다.
- Telegram 비밀값 마스킹은 기존 sanitization을 유지한다. workflow는 주문 결과 JSON만 base64로
  서버에 전달하고, KIS app key/secret/token/account 값을 로그나 sidecar에 쓰지 않는다.

## 검증

PR #390 머지 전:

- `uv run pytest tests/unit/test_order_opportunity.py tests/integration/test_rejected_order_opportunity_cli.py tests/unit/test_telegram_alerts.py tests/integration/test_telegram_alerts_cli.py tests/unit/test_micro_gtaa_telegram_alerts.py tests/unit/test_micro_gtaa_canary.py tests/unit/test_safety_command_registry.py -q` → 30 passed
- `uv run pytest -q` → 2262 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- `ruby -e 'require "yaml"; YAML.load_file(".github/workflows/rebalance-micro-gtaa-canary.yml"); puts "parsed .github/workflows/rebalance-micro-gtaa-canary.yml"'` → parsed
- `uv run auto-invest rejected-order-opportunity --result-json /tmp/nonexistent-micro-live.json --format json` → valid empty opportunity JSON
- `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`
- `uv run python scripts/check_handoff_facts.py` → OK
- PR #390 본문 품질 관문 → pr-quality-gate-ok
- PR #390 상태: ready, `mergeStateStatus=CLEAN`, remote `pr-quality-gate` success

handoff 갱신 직전:

- `uv run pytest -q` → stale `HANDOFF.md` 때문에 하네스 2건만 실패했다. 코드 실패가 아니라
  `HANDOFF.md` 마지막 main 커밋 행이 `7195c48`로 오래된 문제였다.
- `uv run ruff check src tests` → All checks passed

handoff 갱신 후:

- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`
- `uv run pytest -q` → 2262 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed

## 다음 세션 한 줄

거부된 micro GTAA 주문이 정상 체결됐다면 지금 이익인지 손실인지는 이제
`auto-invest rejected-order-opportunity`와 micro GTAA sidecar/Telegram의 `거부 주문 기회손익`
섹션에서 확인한다. 양수는 체결됐으면 더 유리, 음수는 거부가 결과적으로 더 유리다.

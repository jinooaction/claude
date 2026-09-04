# 검증·운영 순서

1. uv run pytest tests/unit/test_capital_ladder.py tests/unit/test_fundability.py
2. uv run pytest 및 uv run ruff check src tests.
3. uv run python scripts/agent_harness_probe.py --strict 및 scripts/check_handoff_facts.py.
4. PR 품질 관문·merge·배포 후 정확한 main을 확인한다.
5. 기존 forward-edge-autoarm의 현재 NAV·예산·fundability·RESIZE·sentinel PR·merge를 확인한다.
6. 새 main 배포·KIS smoke·no-order preflight ENTRY_READY/CLEAR/OK/VALID/주문0을 확인한다.
7. 다음 XNYS 자동 실행의 접수·체결·감사·대사 전에는 전체 목표를 닫지 않는다.

수동 실주문이나 소비된 거래일 재시도 권한을 추가하지 않는다.

## 생산 기록 (2026-09-05 KST)

- PR757 merge854d81f947e1c0c579996026f15171f6b9dfeaad. 기능 head3443bd0에서 최종 전체3400 passed/7 skipped,
  ruff·엄격 하네스14/14·HANDOFF·PR 품질 관문 통과.
- deploy33928671285 성공. audit33928739275의79b06199af242253aa8e1a96791246a6에서
  DEPLOY_STARTED→DEPLOY_COMPLETED, 실제854d81f9 반영 확인.
- KIS33928671315 6/6, cash934.27/NAV1434.91/ORANY28/open_unfilled0. setup33928740976은
  deploy_timer/live_canary_timer/worker active.
- T008의 승인 예산 갱신 및 최신 no-order 검증, T009의 실제 자동 체결은 아직 미완료다.

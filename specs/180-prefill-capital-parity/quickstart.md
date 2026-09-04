# 검증·운영 순서

1. uv run pytest tests/unit/test_capital_ladder.py tests/unit/test_fundability.py
2. uv run pytest 및 uv run ruff check src tests.
3. uv run python scripts/agent_harness_probe.py --strict 및 scripts/check_handoff_facts.py.
4. PR 품질 관문·merge·배포 후 정확한 main을 확인한다.
5. 기존 forward-edge-autoarm의 현재 NAV·예산·fundability·RESIZE·sentinel PR·merge를 확인한다.
6. 새 main 배포·KIS smoke·no-order preflight ENTRY_READY/CLEAR/OK/VALID/주문0을 확인한다.
7. 다음 XNYS 자동 실행의 접수·체결·감사·대사 전에는 전체 목표를 닫지 않는다.

수동 실주문이나 소비된 거래일 재시도 권한을 추가하지 않는다.

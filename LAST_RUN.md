# KIS smoke 자율 검증 — 최신 실행 진단

이 파일은 `.github/workflows/kis-smoke.yml` 이 매 run 마다 자동 force-push 합니다. 운영자가 GitHub Actions UI 에 들어가지 않고도 외부 (예: claude session) 에서 `git fetch origin automation/kis-smoke-last-run && git show origin/automation/kis-smoke-last-run:LAST_RUN.md` 로 진단 가능합니다.

## 메타데이터

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| commit | 4a5f43add677155382487f23a8a47debd2daa378 |
| trigger | schedule |
| timestamp_utc | 2026-09-05T07:28:24Z |

## 상태

| 변수 | 값 |
|------|-----|
| secrets_present | true |
| key_valid | true |
| smoke_state | failure |
| smoke_exit | 1 |

## SSH/원격 출력 (smoke_output.log)

```
--- smoke 전용 checkout 준비 ---
운영 repo: /opt/auto-invest (읽기 전용: .env/remote URL 확인만)
대상 commit: 4a5f43add677155382487f23a8a47debd2daa378
smoke HEAD: 4a5f43a (Merge pull request #766 from jinooaction/codex/180-stale-base-production-handoff)

--- .env 확인 (KIS 키만 ✓ 표시, 값 노출 안 함) ---
  KIS_APP_KEY=[REDACTED] 설정됨
  KIS_APP_SECRET=[REDACTED] 설정됨
  KIS_ACCOUNT_NO=[REDACTED] 설정됨

--- KIS_LIVE_TEST=1 라이브 smoke 실행 ---
Using CPython 3.11.15
Creating virtual environment at: .venv
   Building auto-invest @ file:///tmp/auto-invest-kis-smoke/repo.GqvsXF
      Built auto-invest @ file:///tmp/auto-invest-kis-smoke/repo.GqvsXF
Installed 55 packages in 496ms
No entry for terminal type "unknown";
using dumb terminal settings.
============================= test session starts ==============================
platform linux -- Python 3.11.15, pytest-9.0.3, pluggy-1.6.0 -- /tmp/auto-invest-kis-smoke/repo.GqvsXF/.venv/bin/python
hypothesis profile 'default'
rootdir: /tmp/auto-invest-kis-smoke/repo.GqvsXF
configfile: pyproject.toml
plugins: anyio-4.13.0, hypothesis-6.152.7, asyncio-1.3.0, respx-0.23.1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 6 items

tests/integration/test_live_broker.py::test_live_kis_token_and_quote 
Live AAPL quote: $319.9700
PASSED
tests/integration/test_live_broker.py::test_live_kis_execution_proxy_parity_and_quotes FAILED
tests/integration/test_live_broker.py::test_live_kis_purchasable_cash 
Live KIS USD purchasable cash: $934.27
PASSED
tests/integration/test_live_broker.py::test_live_kis_positions 
Live KIS positions: 1개 보유
  - ORANY: 28주 (평단 $11.1950)
PASSED
tests/integration/test_live_broker.py::test_live_kis_combined_balance 
Live KIS balance: cash=$934.27, total=$1432.67000000
PASSED
tests/integration/test_live_broker.py::test_live_kis_recent_orders_have_no_open_unfilled 
Live KIS recent order/execution rows: 0개, open_unfilled=0개
PASSED

=================================== FAILURES ===================================
_______________ test_live_kis_execution_proxy_parity_and_quotes ________________

kis_token_bundle = {'access_token': [REDACTED]]', 'token_type': 'Bearer', 'app_key': [REDACTED]]', 'app_secret': [REDACTED]]'}
tmp_path = PosixPath('/tmp/pytest-of-auto-invest/pytest-52/test_live_kis_execution_proxy_0')

    @pytest.mark.asyncio
    async def test_live_kis_execution_proxy_parity_and_quotes(
        kis_token_bundle: dict,
        tmp_path,
    ) -> None:
        """사전등록 실행 대체재의 KIS 일봉 동등성과 주문 거래소 해석(주문 0건)."""
    
        from auto_invest.backtest.data_source import SqliteBarDataSource
        from auto_invest.market_data.feed import backfill_daily_bars
        from auto_invest.persistence import db
        from auto_invest.portfolio.execution_proxy_parity import (
            PREREGISTERED_EXECUTION_SYMBOL_MAP,
            assess_execution_proxy_parity,
        )
    
        access_token=[REDACTED]"]
        app_key = [REDACTED]app_key"]
        app_secret = [REDACTED]app_secret"]
        bars_db = tmp_path / "proxy-parity.db"
        conn = db.get_connection(bars_db)
        db.migrate(conn)
        symbols = sorted(
            set(PREREGISTERED_EXECUTION_SYMBOL_MAP)
            | set(PREREGISTERED_EXECUTION_SYMBOL_MAP.values())
        )
        try:
            async with httpx.AsyncClient(base_url=KIS_BASE_URL, timeout=30.0) as inner:
                broker = _make_broker(inner)
                backfill = await backfill_daily_bars(
                    conn,
                    broker,
                    access_token=[REDACTED]
                    app_key=[REDACTED],
                    app_secret=[REDACTED],
                    symbols=symbols,
                    min_bars=300,
                )
                quotes = {}
                for symbol in PREREGISTERED_EXECUTION_SYMBOL_MAP.values():
>                   quote = await get_quote_resolving_market(
                        broker,
                        access_token=[REDACTED]
                        app_key=[REDACTED],
                        app_secret=[REDACTED],
                        symbol=symbol,
                    )

tests/integration/test_live_broker.py:203: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
src/auto_invest/broker/overseas.py:208: in get_quote_resolving_market
    raise last_http_exc
src/auto_invest/broker/overseas.py:192: in get_quote_resolving_market
    return await get_quote(
src/auto_invest/broker/overseas.py:134: in get_quote
    response = await client.request(
src/auto_invest/broker/client.py:140: in request
    response = await self._do_with_retries(
src/auto_invest/broker/client.py:168: in _do_with_retries
    async for attempt in AsyncRetrying(
.venv/lib/python3.11/site-packages/tenacity/asyncio/__init__.py:170: in __anext__
    do = await self.iter(retry_state=self._retry_state)
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.11/site-packages/tenacity/asyncio/__init__.py:157: in iter
    result = await action(retry_state)
             ^^^^^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.11/site-packages/tenacity/_utils.py:111: in inner
    return call(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.11/site-packages/tenacity/__init__.py:413: in exc_check
    raise retry_exc.reraise()
          ^^^^^^^^^^^^^^^^^^^
.venv/lib/python3.11/site-packages/tenacity/__init__.py:184: in reraise
    raise self.last_attempt.result()
          ^^^^^^^^^^^^^^^^^^^^^^^^^^
/var/lib/auto-invest/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/lib/python3.11/concurrent/futures/_base.py:449: in result
    return self.__get_result()
           ^^^^^^^^^^^^^^^^^^^
/var/lib/auto-invest/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/lib/python3.11/concurrent/futures/_base.py:401: in __get_result
    raise self._exception
src/auto_invest/broker/client.py:178: in _do_with_retries
    response.raise_for_status()
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <Response [500 Internal Server Error]>

    def raise_for_status(self) -> Response:
        """
        Raise the `HTTPStatusError` if one occurred.
        """
        request = self._request
        if request is None:
            raise RuntimeError(
                "Cannot call `raise_for_status` as the request "
                "instance has not been set on this response."
            )
    
        if self.is_success:
            return self
    
        if self.has_redirect_location:
            message = (
                "{error_type} '{0.status_code} {0.reason_phrase}' for url '{0.url}'\n"
                "Redirect location: '{0.headers[location]}'\n"
                "For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/{0.status_code}"
            )
        else:
            message = (
                "{error_type} '{0.status_code} {0.reason_phrase}' for url '{0.url}'\n"
                "For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/{0.status_code}"
            )
    
        status_class = self.status_code // 100
        error_types = {
            1: "Informational response",
            3: "Redirect response",
            4: "Client error",
            5: "Server error",
        }
        error_type = error_types.get(status_class, "Invalid status code")
        message = message.format(self, error_type=error_type)
>       raise HTTPStatusError(message, request=request, response=self)
E       httpx.HTTPStatusError: Server error '500 Internal Server Error' for url 'https://openapi.koreainvestment.com:9443/uapi/overseas-price/v1/quotations/price?AUTH=&EXCD=AMS&SYMB=IAUM'
E       For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500

.venv/lib/python3.11/site-packages/httpx/_models.py:829: HTTPStatusError
=========================== short test summary info ============================
FAILED tests/integration/test_live_broker.py::test_live_kis_execution_proxy_parity_and_quotes
========================= 1 failed, 5 passed in 12.35s =========================
::warning::KIS smoke failed after one token issue; not retrying full live tests to avoid KIS OAuth throttle and duplicate live-read noise.
```

## 다음 단계 추정

- pytest 자체가 실패. smoke_output.log 의 traceback/assertion 메시지로 원인 분석.

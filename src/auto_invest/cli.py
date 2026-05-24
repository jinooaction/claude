"""Operator CLI (T046).

Implements the `auto-invest run` subcommand from
`contracts/cli.md`. Delegates parsing/validation to
`config.loader.load_config`, the gate chain to `risk/gates`, and the
runtime to `worker.loop.Worker`. Dry-run never reaches the broker.

Exit codes:
    0  normal shutdown
    1  runtime error after startup (logged + audited)
    2  startup validation failure (config invalid, secrets missing,
       schema migration required, stage-uniqueness conflict)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
from decimal import Decimal
from pathlib import Path

import httpx
import typer

from auto_invest.broker.auth import get_valid_token
from auto_invest.broker.client import (
    AsyncTokenBucket,
    CircuitBreaker,
    ResilientClient,
)
from auto_invest.config.loader import ConfigError, load_config, load_secrets
from auto_invest.execution.order_router import verify_stage_uniqueness
from auto_invest.logging_config import configure_logging
from auto_invest.persistence import db
from auto_invest.worker.loop import Worker, WorkerSettings

app = typer.Typer(no_args_is_help=True, add_completion=False)
db_app = typer.Typer(help="Database management subcommands.", no_args_is_help=True)
app.add_typer(db_app, name="db")
logger = logging.getLogger(__name__)


def _exit(code: int) -> None:
    raise typer.Exit(code)


def _require_clean_migrations(db_path: Path, *, allow_apply: bool) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.get_connection(db_path)
    try:
        pending = db.pending_migrations(conn)
        if not pending:
            return
        if not allow_apply:
            typer.echo(
                f"Pending migrations: {pending}. Run `auto-invest db migrate`.",
                err=True,
            )
            _exit(2)
        db.migrate(conn)
    finally:
        conn.close()


@app.command()
def run(
    config: Path = typer.Option(
        Path("config/rules.toml"),
        "--config",
        "-c",
        help="Path to the rules TOML.",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite database path.",
    ),
    halt_path: Path = typer.Option(
        Path("data/halt.flag"),
        "--halt-path",
        help="Filesystem halt-flag path.",
    ),
    env_file: Path | None = typer.Option(
        None,
        "--env-file",
        help="Optional .env file (defaults to process environment only).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate config, run migrations, then exit 0 — never contacts the broker.",
    ),
    base_url: str = typer.Option(
        "https://openapi.koreainvestment.com:9443",
        "--base-url",
        help="KIS REST base URL.",
    ),
    capital: float = typer.Option(
        0.0,
        "--capital",
        help="Operator-declared total capital in USD; required for live runs.",
    ),
    require_session_open: bool = typer.Option(
        True,
        "--require-session-open/--ignore-session-window",
        help="Skip ticks outside US regular hours (default) or run anyway.",
    ),
    prices_path: Path = typer.Option(
        Path("config/llm_prices.toml"),
        "--prices",
        help="Anthropic price table (TOML); validated at startup per spec 002.",
    ),
) -> None:
    configure_logging()

    # 1. Secrets + config (refuses on missing required values).
    from auto_invest.telemetry.prices import PriceTableError, load_prices

    try:
        secrets = load_secrets(env_file)
        cfg = load_config(config, env_path=env_file)
        prices = load_prices(prices_path)
    except (ConfigError, PriceTableError) as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        _exit(2)

    # 2. Stage-uniqueness preflight.
    decisions = verify_stage_uniqueness(list(cfg.rules))
    blocked = [d for d in decisions if not d.allow]
    if blocked:
        for decision in blocked:
            typer.echo(
                f"Stage-uniqueness denied: {decision.reason}",
                err=True,
            )
        _exit(2)

    # 3. Migrations gate. Dry-run is allowed to apply pending migrations
    # so the operator can run the full chain (validate -> migrate -> exit)
    # in one safe step.
    _require_clean_migrations(db_path, allow_apply=dry_run)

    # 4. Telemetry integrity check (FR-T12). Mismatches produce a
    # DATA_QUALITY_ISSUE audit row but do not block startup. Also pin
    # the price-table version that priced this process (T503 / spec 002 R-T3).
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _integrity_conn = db.get_connection(db_path)
    try:
        from auto_invest.persistence import audit as _audit_mod
        from auto_invest.persistence.audit import DataQualityIssuePayload as _DQIP
        from auto_invest.persistence.audit import (
            PriceTableLoadedPayload as _PTLP,
        )
        from auto_invest.telemetry.store import integrity_check as _integrity

        _audit_mod.append(
            _integrity_conn,
            _PTLP(path=prices.source_path, sha256=prices.sha256),
        )
        mismatches = _integrity(_integrity_conn)
        for m in mismatches:
            _audit_mod.append(
                _integrity_conn,
                _DQIP(
                    issue="token_usage_audit_mismatch",
                    detail={"correlation_id": m.correlation_id, "kind": m.kind},
                ),
                correlation_id=m.correlation_id,
            )
    finally:
        _integrity_conn.close()

    if dry_run:
        typer.echo("Dry run successful.")
        typer.echo(f"  rules:    {len(cfg.rules)}")
        typer.echo(f"  symbols:  {sorted(cfg.whitelist.symbols)}")
        typer.echo(
            "  caps:     "
            f"per-trade {cfg.caps.per_trade_pct}%, "
            f"per-symbol {cfg.caps.per_symbol_pct}%, "
            f"global {cfg.caps.global_exposure_pct}%"
        )
        typer.echo(f"  database: {db_path}")
        typer.echo(f"  halt:     {halt_path}")
        _exit(0)

    if capital <= 0:
        typer.echo("--capital must be > 0 for a live run.", err=True)
        _exit(2)

    asyncio.run(
        _run_live(
            cfg=cfg,
            secrets=secrets,
            db_path=db_path,
            halt_path=halt_path,
            config_path=config,
            base_url=base_url,
            total_capital_usd=Decimal(str(capital)),
            require_session_open=require_session_open,
        )
    )


@app.command(name="paper-run")
def paper_run(
    config: Path = typer.Option(
        Path("config/rules.toml"),
        "--config",
        "-c",
        help="Path to the rules TOML.",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite database path.",
    ),
    halt_path: Path = typer.Option(
        Path("data/halt.flag"),
        "--halt-path",
        help="Filesystem halt-flag path.",
    ),
    env_file: Path | None = typer.Option(
        None,
        "--env-file",
        help="Optional .env file (defaults to process environment only).",
    ),
    base_url: str = typer.Option(
        "https://openapi.koreainvestment.com:9443",
        "--base-url",
        help="KIS REST base URL (quote 호출에만 사용; 주문 호출은 절대 발생하지 않음).",
    ),
    capital: float = typer.Option(
        0.0,
        "--capital",
        help="Operator-declared total capital in USD; cap 게이트 평가에 사용.",
    ),
    require_session_open: bool = typer.Option(
        True,
        "--require-session-open/--ignore-session-window",
        help="Skip ticks outside US regular hours (default) or run anyway.",
    ),
    prices_path: Path = typer.Option(
        Path("config/llm_prices.toml"),
        "--prices",
        help="Anthropic price table (TOML); validated at startup per spec 002.",
    ),
) -> None:
    """Spec 009 — paper-trading 데몬 (live 자본 노출 전 일주일 관찰용).

    실시간 KIS quote를 받지만 broker 주문 API는 단 한 번도 호출하지 않는다
    (FR-004). 게이트는 live와 동일 코드로 평가되며, 시뮬 체결은 audit_log의
    ORDER_PAPER_FILLED 이벤트로 기록된다. paper-run · live-run은 상호 배타
    (FR-015) — 다른 모드가 떠 있으면 exit 70.
    """
    import hashlib

    configure_logging()

    # 1. Secrets + config + prices (live와 동일 검증).
    from auto_invest.telemetry.prices import PriceTableError, load_prices

    try:
        secrets = load_secrets(env_file)
        cfg = load_config(config, env_path=env_file)
        prices = load_prices(prices_path)
    except (ConfigError, PriceTableError) as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        _exit(2)

    # 2. Stage-uniqueness preflight (live와 동일).
    decisions = verify_stage_uniqueness(list(cfg.rules))
    blocked = [d for d in decisions if not d.allow]
    if blocked:
        for decision in blocked:
            typer.echo(
                f"Stage-uniqueness denied: {decision.reason}",
                err=True,
            )
        _exit(2)

    # 3. Migrations gate (paper-run은 dirty migration 적용 불허).
    _require_clean_migrations(db_path, allow_apply=False)

    # 4. Telemetry integrity check + price-table loaded audit (live와 동일).
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _integrity_conn = db.get_connection(db_path)
    try:
        from auto_invest.persistence import audit as _audit_mod
        from auto_invest.persistence.audit import DataQualityIssuePayload as _DQIP
        from auto_invest.persistence.audit import (
            PriceTableLoadedPayload as _PTLP,
        )
        from auto_invest.telemetry.store import integrity_check as _integrity

        _audit_mod.append(
            _integrity_conn,
            _PTLP(path=prices.source_path, sha256=prices.sha256),
        )
        mismatches = _integrity(_integrity_conn)
        for m in mismatches:
            _audit_mod.append(
                _integrity_conn,
                _DQIP(
                    issue="token_usage_audit_mismatch",
                    detail={"correlation_id": m.correlation_id, "kind": m.kind},
                ),
                correlation_id=m.correlation_id,
            )
    finally:
        _integrity_conn.close()

    if capital <= 0:
        typer.echo(
            "--capital must be > 0 for a paper run (cap 게이트가 실계좌 잔고 "
            "기준으로 평가하지만 시뮬 PnL 계산에는 declared capital이 필요).",
            err=True,
        )
        _exit(2)

    # 5. ruleset_sha256 계산 (PAPER_RUN_STARTED 페이로드에 들어감).
    ruleset_sha256 = hashlib.sha256(config.read_bytes()).hexdigest()

    # 6. paper-run 메인 루프. 리턴 코드를 exit code로 그대로 사용.
    exit_code = asyncio.run(
        _run_paper(
            cfg=cfg,
            secrets=secrets,
            db_path=db_path,
            halt_path=halt_path,
            config_path=config,
            base_url=base_url,
            total_capital_usd=Decimal(str(capital)),
            require_session_open=require_session_open,
            ruleset_sha256=ruleset_sha256,
        )
    )
    if exit_code != 0:
        _exit(exit_code)


@app.command(name="design")
def design(
    intent: str = typer.Option(
        "",
        "--intent",
        help="운영자 자연어 의도 (예: \"자본 100달러, 미국 대형주 분산, 매주 적립, 위험 보통\")",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite database path.",
    ),
    env_file: Path | None = typer.Option(
        None,
        "--env-file",
        help="Optional .env file.",
    ),
    base_url: str = typer.Option(
        "https://openapi.koreainvestment.com:9443",
        "--base-url",
        help="KIS REST base URL (quote/잔고 조회용).",
    ),
    prices_path: Path = typer.Option(
        Path("config/llm_prices.toml"),
        "--prices",
        help="Anthropic price table (spec 002).",
    ),
    max_retries: int = typer.Option(
        3,
        "--max-retries",
        help="자동 재설계 최대 횟수 (기본 3, FR-007).",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help=(
            "최근 design 결과로 시작된 라이브 worker의 현재 상태를 한글로 요약 "
            "(intent 입력 없어도 됨)."
        ),
    ),
    repo_path: Path = typer.Option(
        Path("."),
        "--repo",
        help=(
            "auto-invest 설치 디렉토리 (기본값 cwd). 콘솔에서 sudo -u auto-invest로"
            " 직접 호출할 때 cwd가 /root 등 다른 디렉토리이면 .env / db / config를"
            " 못 찾으므로, --repo /opt/auto-invest 같이 명시하거나 작업 디렉토리를"
            " 옮기세요. 기본 운영 케이스(systemd)에서는 WorkingDirectory가 잡혀"
            " 있으므로 신경 안 써도 됩니다."
        ),
    ),
) -> None:
    """Spec 010 — 자동 룰 설계자.

    운영자가 자연어 한 줄로 의도를 적으면 시스템이 룰을 자동 생성하고
    정적 검증한 뒤 운영자 OK 한 줄을 받아 라이브 시작. 본 PR에서는 KIS
    주문 API는 단 한 번도 호출하지 않습니다 (잔고 조회 quote 제외).

    `--check` 옵션으로 호출하면 가장 최근 RULE_DESIGN_DEPLOYED의 라이브 worker
    현재 상태(시그널·체결·차단 카운트)를 한글 요약으로 출력하고 즉시 종료.
    """
    # 모든 상대 경로를 --repo 기준으로 절대화. sudo -u auto-invest 가 콘솔의
    # cwd=/root 를 그대로 물려주면 .env / db / config 가 /root/ 아래에서
    # 찾아져 KIS 키가 누락되거나 DB가 새로 생성되는 함정이 있어, deploy CLI
    # (PR #24)와 동일한 패턴으로 진입 시점에 한 번에 결합한다.
    repo_path = repo_path.resolve()
    if not db_path.is_absolute():
        db_path = repo_path / db_path
    if not prices_path.is_absolute():
        prices_path = repo_path / prices_path
    if env_file is None:
        # 명시 안 됐을 때만 repo 기준 .env로 자동 결정 (운영자가 명시하면 그대로).
        env_file = repo_path / ".env"
    elif not env_file.is_absolute():
        env_file = repo_path / env_file

    # --check 모드: 최근 design 결과 요약만 출력하고 종료.
    if check:
        _design_check_summary(db_path)
        return

    if not intent.strip():
        typer.echo(
            "--intent가 빈 문자열입니다. (참고: `--check` 옵션으로 최근 상태 요약 가능.)",
            err=True,
        )
        _exit(2)

    import json as _json
    import socket

    from auto_invest.design import claude_client, deploy, mutex, prompt, verifier
    from auto_invest.persistence import audit as _audit
    from auto_invest.persistence import db as _db
    from auto_invest.persistence.audit import (
        RuleDesignCompletedPayload,
        RuleDesignDeployedPayload,
        RuleDesignRejectedPayload,
        RuleDesignRequestedPayload,
    )
    from auto_invest.telemetry.prices import PriceTableError, load_prices

    configure_logging()

    # 1. config·secrets·prices 로드.
    try:
        secrets = load_secrets(env_file)
        prices = load_prices(prices_path)
    except (ConfigError, PriceTableError) as exc:
        typer.echo(f"설정 오류: {exc}", err=True)
        _exit(2)

    # 2. DB + mutex check.
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _db.get_connection(db_path)
    _db.migrate(conn)

    mx = mutex.check_and_acquire(conn)
    if not mx.allowed:
        typer.echo(
            f"design 명령 시작 거부: 다른 design 명령이 이미 실행 중입니다 "
            f"(seq={mx.conflicting_event_id}, 시작 {mx.conflicting_session_started_at})."
            "\n기존 명령 종료 후 다시 시도해주세요.",
            err=True,
        )
        conn.close()
        _exit(mx.exit_code)

    # 3. KIS 잔고 + 보유 종목 조회.
    typer.echo("KIS 잔고 조회 중...")
    try:
        balance, holdings = asyncio.run(
            _fetch_kis_account_state(
                base_url=base_url,
                app_key=secrets["KIS_APP_KEY"],
                app_secret=secrets["KIS_APP_SECRET"],
                account_no=secrets["KIS_ACCOUNT_NO"],
                db_path=db_path,
            )
        )
    except Exception as exc:  # noqa: BLE001 — KIS 오류는 모두 한글 보고
        _audit.append(
            conn,
            RuleDesignRejectedPayload(
                reason="kis_token_failed",
                detail=f"KIS 잔고 조회 실패: {exc}",
            ),
        )
        typer.echo(f"KIS 잔고 조회 실패: {exc}", err=True)
        conn.close()
        _exit(1)

    typer.echo(f"잔고: ${balance.cash_usd} USD, 총 평가: ${balance.total_value_usd}")
    typer.echo(verifier.availability_notice())

    # 4. RULE_DESIGN_REQUESTED 기록.
    design_session_id = _audit.append(
        conn,
        RuleDesignRequestedPayload(
            intent=intent,
            requested_at_utc=_d_iso_now(),
            kis_balance_usd=str(balance.cash_usd),
            kis_holdings=holdings,
            host=socket.gethostname(),
        ),
    )

    # 5. Claude 호출 + 검증 루프 (최대 max_retries).
    # 자본은 항상 KIS 잔고를 사용 — "의도 자본" 별도 입력 정책은 제거됨.
    intent_capital = balance.cash_usd
    retry_context: dict | None = None
    generated_toml: str | None = None
    completed_payload: RuleDesignCompletedPayload | None = None

    async def _design_loop():
        nonlocal retry_context, generated_toml, completed_payload
        async with httpx.AsyncClient(timeout=60.0) as _:
            # anthropic SDK 클라이언트 — async 버전.
            import anthropic
            anth_client = anthropic.AsyncAnthropic(
                api_key=secrets.get("ANTHROPIC_API_KEY", ""),
            )

            for retry_index in range(1, max_retries + 1):
                typer.echo(f"\nClaude 호출 중 (시도 {retry_index}/{max_retries})...")
                sys_p = prompt.build_system_prompt()
                user_p = prompt.build_user_prompt(
                    intent=intent,
                    kis_balance_usd=balance.cash_usd,
                    kis_holdings=holdings,
                    retry_context=retry_context,
                )

                try:
                    response = await claude_client.call_rule_design(
                        anth_client,
                        system_prompt=sys_p,
                        user_prompt=user_p,
                        conn=conn,
                        prices=prices,
                    )
                except Exception as exc:  # noqa: BLE001
                    _audit.append(
                        conn,
                        RuleDesignRejectedPayload(
                            reason="claude_api_error",
                            detail=f"Claude API 오류: {exc}",
                            retry_index=retry_index,
                        ),
                    )
                    typer.echo(f"Claude API 오류: {exc}", err=True)
                    retry_context = {
                        "reason": "claude_api_error",
                        "detail": str(exc),
                        "previous_toml": "",
                    }
                    continue

                typer.echo(
                    f"  모델 {response.model_id}, 토큰 입력 {response.tokens_input}/"
                    f"출력 {response.tokens_output}, 비용 ${response.cost_usd:.4f}"
                )
                if response.cost_exceeded:
                    _audit.append(
                        conn,
                        RuleDesignRejectedPayload(
                            reason="claude_api_error",
                            detail=(
                                f"호출당 비용 한도(${response.cost_usd:.4f}) 초과. "
                                "의도를 짧게 다시 시도해주세요."
                            ),
                            retry_index=retry_index,
                        ),
                    )
                    typer.echo("호출 비용 한도 초과. 거부.", err=True)
                    return False

                parsed = prompt.parse_claude_response(response.text)
                if parsed.error:
                    _audit.append(
                        conn,
                        RuleDesignRejectedPayload(
                            reason="insufficient_balance",
                            detail=parsed.error,
                            retry_index=retry_index,
                        ),
                    )
                    typer.echo(f"Claude 응답 오류: {parsed.error}", err=True)
                    return False

                # 정적 + 백테스트(가용 시) 검증.
                vr = verifier.verify_rules(
                    parsed.rules_toml,
                    kis_balance_usd=balance.cash_usd,
                )
                if not vr.ok:
                    _audit.append(
                        conn,
                        RuleDesignRejectedPayload(
                            reason=vr.reason or "parse_error",  # type: ignore[arg-type]
                            detail=vr.detail,
                            retry_index=retry_index,
                        ),
                    )
                    typer.echo(f"검증 실패: {vr.detail}", err=True)
                    retry_context = {
                        "reason": vr.reason or "parse_error",
                        "detail": vr.detail,
                        "previous_toml": parsed.rules_toml,
                    }
                    continue

                # 통과 — COMPLETED 기록 + 생성된 TOML 보관.
                completed_payload = RuleDesignCompletedPayload(
                    intent=intent,
                    interpretation=parsed.interpretation,
                    generated_rules_toml=parsed.rules_toml,
                    model_id=response.model_id,
                    tokens_input=response.tokens_input,
                    tokens_output=response.tokens_output,
                    cost_usd=str(response.cost_usd),
                    retry_index=retry_index,
                    paper_run_session_id=None,
                )
                _audit.append(conn, completed_payload)
                generated_toml = parsed.rules_toml
                return True

        return False

    success = asyncio.run(_design_loop())

    if not success:
        if completed_payload is None:
            _audit.append(
                conn,
                RuleDesignRejectedPayload(
                    reason="max_retries",
                    detail=(
                        f"{max_retries}회 모두 검증 통과 못함. "
                        "의도를 더 구체적으로 다시 시도해주세요."
                    ),
                ),
            )
        typer.echo(
            f"\n자동 룰 설계 실패: {max_retries}회 모두 검증 통과 못함.",
            err=True,
        )
        conn.close()
        _exit(1)

    # 6. 운영자 OK prompt + 라이브 시작 (stub).
    assert completed_payload is not None
    assert generated_toml is not None
    typer.echo("\n=== 검증 통과 — 생성된 룰 요약 ===")
    typer.echo(f"  해석: {_json.dumps(completed_payload.interpretation, ensure_ascii=False)}")
    typer.echo(f"  KIS 예수금: ${balance.cash_usd} / 총 평가: ${balance.total_value_usd}")
    typer.echo(generated_toml[:500] + ("..." if len(generated_toml) > 500 else ""))
    typer.echo("")

    ok = deploy.prompt_operator_ok()
    if not ok:
        _audit.append(
            conn,
            RuleDesignRejectedPayload(
                reason="operator_declined",
                detail="운영자가 OK를 답하지 않거나 60초 안에 응답 없음.",
            ),
        )
        typer.echo("라이브 시작 거부됨. 생성된 룰은 audit_log에 보관됨.")
        conn.close()
        return  # exit 0 (정상 종료)

    # 라이브 worker subprocess 자동 시작.
    config_dir = db_path.parent / ".." / "config"
    rules_path = deploy.write_auto_rules_file(
        generated_toml, config_dir=config_dir.resolve(),
    )
    typer.echo(f"\n생성된 룰을 저장: {rules_path}")
    typer.echo("라이브 worker subprocess 시작 중...")

    live_session_id = deploy.start_live_worker(
        rules_path=rules_path,
        capital_usd=intent_capital,
        db_path=db_path,
        halt_path=db_path.parent / "halt.flag",
        env_file=env_file,
        base_url=base_url,
        prices_path=prices_path,
        conn=conn,
    )
    if live_session_id is None:
        _audit.append(
            conn,
            RuleDesignRejectedPayload(
                reason="claude_api_error",  # 가장 가까운 reason — 후속 PR에서 새 reason 추가 가능
                detail=(
                    "라이브 worker subprocess가 30초 안에 WORKER_STARTED audit row를 "
                    "남기지 않았습니다. 로그를 확인해주세요."
                ),
            ),
        )
        typer.echo(
            "라이브 worker 시작 실패: 30초 안에 worker가 audit_log에 등록되지 않음. "
            "로그 디렉토리를 확인해주세요.",
            err=True,
        )
        conn.close()
        _exit(1)

    _audit.append(
        conn,
        RuleDesignDeployedPayload(
            design_session_id=design_session_id,
            live_session_id=live_session_id,
            deployed_at_utc=_d_iso_now(),
            total_capital_usd=str(intent_capital),
        ),
    )
    typer.echo(
        f"\n라이브 worker 시작됨. WORKER_STARTED seq={live_session_id}, "
        f"자본 ${intent_capital}. design 명령은 종료. worker는 background에서 계속 실행."
    )
    conn.close()


async def _fetch_kis_account_state(
    *,
    base_url: str,
    app_key: str,
    app_secret: str,
    account_no: str,
    db_path: Path,
):
    """KIS 잔고 + 보유 종목 조회 helper.

    잔고는 외화예수금(주문가능액) + 보유 종목 평가금액의 합. 보유 종목은
    Claude 프롬프트와 audit 페이로드 모두에서 활용된다.
    """
    from auto_invest.broker.overseas import get_balance, get_positions

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as inner:
        token = await get_valid_token(
            inner,
            base_url=base_url,
            app_key=app_key,
            app_secret=app_secret,
            cache_path=db_path.parent / "kis_token.json",
        )
        client = ResilientClient(
            inner,
            rate_limiter=AsyncTokenBucket(rate_per_sec=15.0, capacity=15.0),
            breaker=CircuitBreaker(failure_threshold=5, cooldown_seconds=30.0),
            max_retries=4,
        )
        balance = await get_balance(
            client,
            access_token=token.access_token,
            app_key=app_key,
            app_secret=app_secret,
            account=account_no,
        )
        positions = await get_positions(
            client,
            access_token=token.access_token,
            app_key=app_key,
            app_secret=app_secret,
            account=account_no,
        )
    holdings = [
        {
            "symbol": p.symbol,
            "qty": p.qty,
            "avg_cost_usd": str(p.avg_cost_usd),
        }
        for p in positions
    ]
    return balance, holdings


async def _fetch_marks(
    symbols: list[str],
    *,
    base_url: str,
    app_key: str,
    app_secret: str,
    db_path: Path,
):
    """Spec 011 — 미청산 종목의 현재 시세(mark)를 조회.

    종목별로 독립 조회하며, 실패한 종목은 결과 dict 에서 빠진다(우아한 강등,
    FR-005). 반환: {symbol: 현재가 Decimal}.
    """
    from auto_invest.broker.overseas import get_quote

    marks: dict = {}
    if not symbols:
        return marks
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as inner:
        token = await get_valid_token(
            inner,
            base_url=base_url,
            app_key=app_key,
            app_secret=app_secret,
            cache_path=db_path.parent / "kis_token.json",
        )
        client = ResilientClient(
            inner,
            rate_limiter=AsyncTokenBucket(rate_per_sec=15.0, capacity=15.0),
            breaker=CircuitBreaker(failure_threshold=5, cooldown_seconds=30.0),
            max_retries=4,
        )
        for sym in symbols:
            try:
                quote = await get_quote(
                    client,
                    access_token=token.access_token,
                    app_key=app_key,
                    app_secret=app_secret,
                    symbol=sym,
                )
                marks[sym] = quote.last_price_usd
            except Exception:  # noqa: BLE001 — 종목별 실패는 미실현 미반영으로 흡수
                continue
    return marks


def _d_iso_now() -> str:
    """ISO8601 millis with Z suffix."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _design_check_summary(db_path: Path) -> None:
    """`auto-invest design --check` — 가장 최근 design 결과의 라이브 worker 상태 요약.

    audit_log를 읽기 전용으로 조회해 한글 요약을 stdout에 출력한다. 출력 항목:
    - 가장 최근 RULE_DESIGN_DEPLOYED의 design_session_id + live_session_id.
    - 그 라이브 worker가 실행된 이후의 ORDER_INTENT / FILL / 차단 / ERROR 카운트.
    - 운영자 원본 의도 + Claude 해석.

    DB 파일이 없으면 한글 안내 후 exit 0.
    """
    import json as _json

    if not db_path.exists():
        typer.echo(f"DB 파일이 없습니다: {db_path}")
        return

    conn = db.get_connection(db_path)
    try:
        conn.execute("PRAGMA query_only = ON")

        deployed = conn.execute(
            "SELECT seq, ts_utc, payload_json FROM audit_log "
            "WHERE event_type = 'RULE_DESIGN_DEPLOYED' "
            "ORDER BY seq DESC LIMIT 1"
        ).fetchone()

        if deployed is None:
            typer.echo(
                "아직 라이브로 배포된 design 결과가 없습니다. "
                "`auto-invest design --intent \"...\"`로 새 룰을 설계해주세요."
            )
            return

        dep_payload = _json.loads(deployed["payload_json"])
        design_session_id = int(dep_payload["design_session_id"])
        live_session_id = int(dep_payload["live_session_id"])

        # 대응 RULE_DESIGN_REQUESTED와 COMPLETED 조회.
        requested = conn.execute(
            "SELECT payload_json FROM audit_log WHERE seq = ?",
            (design_session_id,),
        ).fetchone()
        completed = conn.execute(
            "SELECT payload_json FROM audit_log "
            "WHERE event_type = 'RULE_DESIGN_COMPLETED' AND seq > ? AND seq < ? "
            "ORDER BY seq DESC LIMIT 1",
            (design_session_id, int(deployed["seq"])),
        ).fetchone()

        # live worker session 시작 이후의 통계.
        intents = conn.execute(
            "SELECT COUNT(*) AS n FROM audit_log "
            "WHERE event_type = 'ORDER_INTENT' AND seq > ?",
            (live_session_id,),
        ).fetchone()["n"]
        fills = conn.execute(
            "SELECT COUNT(*) AS n FROM audit_log "
            "WHERE event_type = 'FILL' AND seq > ?",
            (live_session_id,),
        ).fetchone()["n"]
        denied = conn.execute(
            "SELECT COUNT(*) AS n FROM audit_log "
            "WHERE event_type = 'ORDER_REJECTED_BY_GATE' AND seq > ?",
            (live_session_id,),
        ).fetchone()["n"]
        errors = conn.execute(
            "SELECT COUNT(*) AS n FROM audit_log "
            "WHERE event_type IN ('ERROR', 'ORDER_REJECTED_BY_BROKER') AND seq > ?",
            (live_session_id,),
        ).fetchone()["n"]

        # worker가 아직 실행 중인지 확인 — 같은 seq 이후 WORKER_STOPPED가 있나.
        worker_stopped = conn.execute(
            "SELECT seq FROM audit_log "
            "WHERE event_type = 'WORKER_STOPPED' AND seq > ? LIMIT 1",
            (live_session_id,),
        ).fetchone()
        worker_state = "종료됨" if worker_stopped is not None else "실행 중"
    finally:
        conn.close()

    typer.echo("=== auto-invest design --check ===")
    typer.echo(f"design session: seq={design_session_id}")
    typer.echo(f"라이브 worker: seq={live_session_id} ({worker_state})")
    typer.echo(f"라이브 시작 시각: {deployed['ts_utc']}")
    typer.echo(f"자본: ${dep_payload['total_capital_usd']}")
    if requested:
        req_payload = _json.loads(requested["payload_json"])
        typer.echo(f"운영자 의도: {req_payload.get('intent', '(없음)')}")
    if completed:
        com_payload = _json.loads(completed["payload_json"])
        typer.echo(
            "Claude 해석: "
            f"{_json.dumps(com_payload.get('interpretation', {}), ensure_ascii=False)}"
        )
    typer.echo("")
    typer.echo("라이브 worker 시작 이후 통계:")
    typer.echo(f"  - 시그널 발생 (ORDER_INTENT):       {intents}")
    typer.echo(f"  - 실제 체결 (FILL):                  {fills}")
    typer.echo(f"  - 게이트 차단 (REJECTED_BY_GATE):    {denied}")
    typer.echo(f"  - 외부 API 오류 (ERROR + BROKER):    {errors}")


@app.command(name="paper-report")
def paper_report(
    since: str = typer.Option(
        ...,
        "--since",
        help="집계 시작 시각 (UTC ISO8601, 예: 2026-05-12T00:00:00Z).",
    ),
    until: str | None = typer.Option(
        None,
        "--until",
        help="집계 종료 시각 (UTC ISO8601). 미지정 시 현재 시각.",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite database path.",
    ),
    output_format: str = typer.Option(
        "text",
        "--format",
        help="text (사람용 표) 또는 json (외부 도구·자동 튜너 입력용).",
    ),
) -> None:
    """Spec 009 — paper-run audit_log를 룰 튜닝용 리포트로 집계.

    read-only — DB의 어떤 row도 수정하지 않는다 (SC-006). live 모드 이벤트는
    집계에서 제외된다 (FR-011).
    """
    import json as _json
    from datetime import UTC, datetime

    from auto_invest.paper.report import build_paper_report, render_text

    if output_format not in ("text", "json"):
        typer.echo("--format must be 'text' or 'json'.", err=True)
        _exit(2)

    def _parse_iso(s: str) -> datetime:
        # 'Z' 접미사를 +00:00로 변환해 fromisoformat에 통과시킴.
        normalized = s.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).astimezone(UTC)

    try:
        since_dt = _parse_iso(since)
        until_dt = _parse_iso(until) if until else datetime.now(UTC)
    except ValueError as exc:
        typer.echo(f"잘못된 ISO8601 시각: {exc}", err=True)
        _exit(2)

    if not db_path.exists():
        typer.echo(f"DB 파일을 찾을 수 없습니다: {db_path}", err=True)
        _exit(1)

    conn = db.get_connection(db_path)
    try:
        # read-only — PRAGMA query_only로 INSERT/UPDATE/DELETE를 차단.
        conn.execute("PRAGMA query_only = ON")
        report = build_paper_report(conn, since=since_dt, until=until_dt)
    finally:
        conn.close()

    if output_format == "json":
        typer.echo(_json.dumps(report.to_json_dict(), indent=2, ensure_ascii=False))
    else:
        typer.echo(render_text(report))


@app.command()
def performance(
    since: str | None = typer.Option(
        None,
        "--since",
        help="집계 시작 시각 (UTC ISO8601, 예: 2026-05-16T00:00:00Z). --window 와 택일.",
    ),
    window: str | None = typer.Option(
        None,
        "--window",
        help="롤링 기간 (예: 30d, 24h). 지정 시 시작 = 종료 − window. --since 와 택일.",
    ),
    until: str | None = typer.Option(
        None,
        "--until",
        help="집계 종료 시각 (UTC ISO8601). 미지정 시 현재 시각.",
    ),
    capital: float | None = typer.Option(
        None,
        "--capital",
        help="위험조정 지표(샤프·낙폭·수익률)의 시작 자본(USD). 미지정 시 총 투입액 대용.",
    ),
    mode: str = typer.Option(
        "paper",
        "--mode",
        help="paper (dry-run 시뮬 체결) 또는 live (실체결). 기본 paper.",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite database path.",
    ),
    output_format: str = typer.Option(
        "text",
        "--format",
        help="text (사람용 표) 또는 json (외부 도구·자동 튜너 입력용).",
    ),
    env_file: Path | None = typer.Option(
        None,
        "--env",
        help="KIS 시세 조회용 .env (미실현 손익 mark-to-market). 미지정 시 실현 손익만.",
    ),
    base_url: str = typer.Option(
        "https://openapi.koreainvestment.com:9443",
        "--base-url",
        help="KIS REST base URL (미실현 손익 시세 조회용).",
    ),
    no_marks: bool = typer.Option(
        False,
        "--no-marks",
        help="현재 시세 조회를 생략하고 실현 손익만 계산.",
    ),
    snapshot: bool = typer.Option(
        False,
        "--snapshot",
        help="성과 결과를 audit_log 에 추가-전용 LIVE_PERFORMANCE_SNAPSHOT 이벤트로 "
        "1건 기록 (FR-014, 튜너용). 기본은 미기록(순수 계산).",
    ),
    slippage: bool = typer.Option(
        False,
        "--slippage",
        help="체결 품질(슬리피지) 섹션 추가 — 기준가 대비 체결가의 불리한 차이를 "
        "매수/매도별 평균·중앙(bps)·총비용(USD)으로 (FR-009).",
    ),
) -> None:
    """Spec 011 — 라이브/페이퍼 매매 성과를 측정 (실현·미실현 손익, 룰별·종목별 기여도).

    read-only — audit_log·positions·orders 의 어떤 row 도 수정하지 않는다 (SC-005).
    미실현 손익은 미청산 종목의 현재 KIS 시세로 계산하며, 시세 조회 실패 시 실현
    손익만 출력한다 (FR-005). live·paper 체결은 모드로 분리 집계된다 (FR-003).
    `--snapshot` 지정 시에만 결과를 추가-전용 이벤트로 1건 기록한다(K4 추가 변경).
    `--slippage` 지정 시 기준가 대비 체결 품질을 함께 출력한다.
    """
    import json as _json
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    from auto_invest.performance.engine import (
        compute_performance,
        compute_slippage,
        read_fills,
        reconstruct,
        render_slippage_text,
        render_text,
        snapshot_fields,
    )

    if output_format not in ("text", "json"):
        typer.echo("--format must be 'text' or 'json'.", err=True)
        _exit(2)
    if mode not in ("paper", "live"):
        typer.echo("--mode must be 'paper' or 'live'.", err=True)
        _exit(2)
    if since is None and window is None:
        typer.echo("--since 또는 --window 중 하나를 지정하세요.", err=True)
        _exit(2)
    if since is not None and window is not None:
        typer.echo("--since 와 --window 는 함께 쓸 수 없습니다.", err=True)
        _exit(2)

    def _parse_iso(s: str) -> datetime:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)

    def _parse_window(w: str) -> timedelta:
        if w.endswith("d"):
            return timedelta(days=int(w[:-1]))
        if w.endswith("h"):
            return timedelta(hours=int(w[:-1]))
        raise ValueError("--window 는 Nd 또는 Nh 형식이어야 합니다 (예: 30d, 24h)")

    try:
        until_dt = _parse_iso(until) if until else datetime.now(UTC)
        since_dt = (
            until_dt - _parse_window(window)
            if window is not None
            else _parse_iso(since)
        )
    except ValueError as exc:
        typer.echo(f"잘못된 기간 인자: {exc}", err=True)
        _exit(2)

    starting_capital = (
        Decimal(str(capital)) if capital is not None and capital > 0 else None
    )

    if not db_path.exists():
        typer.echo(f"DB 파일을 찾을 수 없습니다: {db_path}", err=True)
        _exit(1)

    conn = db.get_connection(db_path)
    try:
        # read-only — PRAGMA query_only로 INSERT/UPDATE/DELETE를 차단.
        conn.execute("PRAGMA query_only = ON")
        fills = read_fills(conn, mode=mode, since=since_dt, until=until_dt)
        positions, _, _, _ = reconstruct(fills)
        open_symbols = sorted(s for s, p in positions.items() if p.qty != 0)
        marks: dict = {}
        if open_symbols and not no_marks and env_file is not None:
            try:
                secrets = load_secrets(env_file)
                marks = asyncio.run(
                    _fetch_marks(
                        open_symbols,
                        base_url=base_url,
                        app_key=secrets["KIS_APP_KEY"],
                        app_secret=secrets["KIS_APP_SECRET"],
                        db_path=db_path,
                    )
                )
            except Exception as exc:  # noqa: BLE001 — 시세 조회 실패는 미실현만 미반영
                typer.echo(
                    f"(시세 조회 실패 — 미실현 손익 미반영: {exc})", err=True
                )
        report = compute_performance(
            fills,
            marks,
            mode=mode,
            since=since_dt,
            until=until_dt,
            starting_capital=starting_capital,
        )
    finally:
        conn.close()

    if snapshot:
        # 측정은 위에서 read-only(query_only)로 끝냈다. 스냅샷은 분리된 쓰기
        # 연결에서 추가-전용으로 단 1건만 기록한다(append-only 불변량 보존).
        from auto_invest.persistence import audit

        write_conn = db.get_connection(db_path)
        try:
            seq = audit.append(
                write_conn,
                audit.LivePerformanceSnapshotPayload(
                    **snapshot_fields(report, computed_at_utc=_d_iso_now())
                ),
            )
        finally:
            write_conn.close()
        typer.echo(
            f"(스냅샷 기록됨: LIVE_PERFORMANCE_SNAPSHOT seq={seq})", err=True
        )

    slippage_stats = compute_slippage(fills) if slippage else None

    if output_format == "json":
        payload = report.to_json_dict()
        if slippage_stats is not None:
            payload["slippage"] = slippage_stats.to_json_dict()
        typer.echo(_json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        typer.echo(render_text(report))
        if slippage_stats is not None:
            typer.echo("")
            typer.echo(render_slippage_text(slippage_stats))


@app.command()
def version() -> None:
    """Print the auto-invest package version."""
    typer.echo("auto-invest 0.1.0")


@app.command()
def efficiency(
    window: str = typer.Option(
        "7d",
        "--window",
        help="Window size: Nd (days) or Nh (hours). Default 7d.",
    ),
    as_of: str | None = typer.Option(
        None,
        "--as-of",
        help="Window end (exclusive). YYYY-MM-DD; default: now (UTC).",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite database path.",
    ),
    prices_path: Path = typer.Option(
        Path("config/llm_prices.toml"),
        "--prices",
        help="Anthropic price table (TOML).",
    ),
    thresholds_path: Path = typer.Option(
        Path("config/llm_kpi_thresholds.toml"),
        "--thresholds",
        help="KPI threshold table (TOML).",
    ),
) -> None:
    """Emit a JSON snapshot of LLM token-efficiency KPIs over a window."""
    import json as _json
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime
    from datetime import timedelta

    from auto_invest.persistence import audit as _audit
    from auto_invest.persistence.audit import PriceTableLoadedPayload
    from auto_invest.telemetry.kpi import compute_snapshot
    from auto_invest.telemetry.prices import PriceTableError, load_prices
    from auto_invest.telemetry.thresholds import TierTableError, load_thresholds

    if window.endswith("d"):
        delta = timedelta(days=int(window[:-1]))
    elif window.endswith("h"):
        delta = timedelta(hours=int(window[:-1]))
    else:
        typer.echo("--window must be Nd or Nh", err=True)
        _exit(2)

    end = (
        _datetime.fromisoformat(as_of).replace(tzinfo=_UTC)
        if as_of is not None
        else _datetime.now(_UTC)
    )
    start = end - delta

    def _iso_ms(d: _datetime) -> str:
        return d.strftime("%Y-%m-%dT%H:%M:%S.") + f"{d.microsecond // 1000:03d}Z"

    try:
        prices = load_prices(prices_path)
        tiers = load_thresholds(thresholds_path)
    except (PriceTableError, TierTableError) as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        _exit(2)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.get_connection(db_path)
    db.migrate(conn)
    try:
        _audit.append(
            conn,
            PriceTableLoadedPayload(path=prices.source_path, sha256=prices.sha256),
        )
        snapshot = compute_snapshot(
            conn,
            window_start_utc=_iso_ms(start),
            window_end_utc=_iso_ms(end),
            tiers=tiers,
        )
    finally:
        conn.close()

    payload = {
        "window_start_utc": snapshot.window_start_utc,
        "window_end_utc": snapshot.window_end_utc,
        "call_count": snapshot.call_count,
        "kpis": [
            {
                "name": k.name,
                "value": str(k.value),
                "tier": k.tier,
                "direction": k.direction,
                "threshold_used": k.threshold_used,
            }
            for k in snapshot.kpis
        ],
        "per_decision_class": snapshot.per_decision_class,
        "top_n_calls": snapshot.top_n_calls,
    }
    typer.echo(_json.dumps(payload, sort_keys=True, indent=2))


@db_app.command("migrate")
def db_migrate(
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite database path.",
    ),
) -> None:
    """Apply any pending schema migrations.

    Refuses to run when the worker's PID file exists and the recorded
    process is still alive — running migrations against an open DB
    risks corrupting the audit log.
    """
    pid_file = db_path.parent / "auto_invest.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
        except (ValueError, OSError):
            # Stale PID file: process is gone, safe to remove.
            pid_file.unlink(missing_ok=True)
        else:
            typer.echo(
                f"Worker process {pid} appears to be running; stop it first.",
                err=True,
            )
            _exit(2)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.get_connection(db_path)
    try:
        applied = db.migrate(conn)
    finally:
        conn.close()

    if applied:
        typer.echo("Applied migrations: " + ", ".join(applied))
    else:
        typer.echo("No pending migrations.")


@app.command()
def report(
    date: str = typer.Option(
        None,
        "--date",
        "-d",
        help="Session date in YYYY-MM-DD (default: yesterday UTC).",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite database path.",
    ),
    output_root: Path = typer.Option(
        Path("data/reports"),
        "--output-root",
        help="Reports directory; one folder per session date.",
    ),
    thresholds_path: Path = typer.Option(
        Path("config/llm_kpi_thresholds.toml"),
        "--thresholds",
        help="KPI threshold table for the Token Efficiency section (spec 002).",
    ),
) -> None:
    """Generate the daily report for the given session date."""
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime
    from datetime import timedelta

    from auto_invest.reports.daily import build_report, write_report
    from auto_invest.telemetry.thresholds import TierTableError, load_thresholds

    session_date = date or ((_datetime.now(_UTC) - timedelta(days=1)).strftime("%Y-%m-%d"))

    tiers = None
    if thresholds_path.exists():
        try:
            tiers = load_thresholds(thresholds_path)
        except TierTableError as exc:
            typer.echo(f"Threshold table error: {exc}", err=True)
            _exit(2)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.get_connection(db_path)
    db.migrate(conn)
    try:
        rep = build_report(
            conn, session_date=session_date, tiers=tiers, include_performance=True
        )
        md_path, json_path = write_report(rep, output_root=output_root)
    finally:
        conn.close()

    typer.echo(f"Daily report written: {md_path}")
    typer.echo(f"  JSON sibling:        {json_path}")
    typer.echo(f"  orders attempted:    {rep.counters.get('orders_attempted', 0)}")
    typer.echo(f"  orders submitted:    {rep.counters.get('orders_submitted', 0)}")
    typer.echo(f"  orders rejected:     {rep.counters.get('orders_rejected_by_gate', 0)}")
    typer.echo(f"  reconciliation:      {rep.reconciliation}")
    if rep.efficiency is not None:
        typer.echo(f"  llm_calls:           {rep.efficiency.call_count}")
    if rep.performance is not None:
        perf = rep.performance
        typer.echo(f"  perf mode:           {perf.mode}")
        typer.echo(f"  day realized PnL:    {perf.day_realized_pnl_usd}")


@app.command()
def status(
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite database path.",
    ),
    halt_path: Path = typer.Option(
        Path("data/halt.flag"),
        "--halt-path",
        help="Filesystem halt-flag path.",
    ),
) -> None:
    """Print a one-screen JSON summary of the current state."""
    import json as _json
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime

    from auto_invest.persistence import positions as _positions
    from auto_invest.worker.halt import read_halt as _read_halt

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.get_connection(db_path)
    db.migrate(conn)
    try:
        halt_state = _read_halt(halt_path)
        last_recon = conn.execute(
            "SELECT result, started_at_utc FROM reconciliation_runs ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        today = _datetime.now(_UTC).strftime("%Y-%m-%d")
        order_counts = dict(
            conn.execute(
                """
                SELECT event_type, COUNT(*) FROM audit_log
                WHERE substr(ts_utc, 1, 10) = ?
                  AND event_type IN ('ORDER_INTENT','ORDER_SUBMITTED',
                                     'ORDER_REJECTED_BY_GATE','FILL')
                GROUP BY event_type
                """,
                (today,),
            ).fetchall()
        )
        positions = [
            {"symbol": p.symbol, "qty": p.qty, "avg_cost_usd": str(p.avg_cost_usd)}
            for p in _positions.get_all_positions(conn)
        ]
    finally:
        conn.close()

    summary = {
        "halt": (
            {"reason": halt_state.reason, "ts_utc": halt_state.ts_utc} if halt_state else None
        ),
        "last_reconciliation": (
            {"result": last_recon["result"], "started_at_utc": last_recon["started_at_utc"]}
            if last_recon
            else None
        ),
        "today_order_counts": order_counts,
        "positions": positions,
    }
    typer.echo(_json.dumps(summary, sort_keys=True, indent=2))


@app.command()
def halt(
    reason: str = typer.Option(..., "--reason", help="Operator-supplied reason for halting."),
    halt_path: Path = typer.Option(
        Path("data/halt.flag"),
        "--halt-path",
        help="Filesystem halt-flag path.",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite database path (audit log destination).",
    ),
) -> None:
    """Set the halt flag so no new orders are submitted."""
    from auto_invest.persistence.audit import HaltSetPayload
    from auto_invest.worker.halt import set_halt as _set_halt

    db_path.parent.mkdir(parents=True, exist_ok=True)
    state = _set_halt(halt_path, reason)
    conn = db.get_connection(db_path)
    db.migrate(conn)
    try:
        from auto_invest.persistence import audit as _audit

        _audit.append(conn, HaltSetPayload(reason=state.reason))
    finally:
        conn.close()
    typer.echo(f"Halt set: {state.reason!r} at {state.ts_utc}")


@app.command()
def resume(
    confirm: bool = typer.Option(
        False,
        "--confirm",
        help="Required to actually clear the halt; prevents accidental resume.",
    ),
    halt_path: Path = typer.Option(
        Path("data/halt.flag"),
        "--halt-path",
        help="Filesystem halt-flag path.",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite database path (audit log destination).",
    ),
) -> None:
    """Clear the halt flag (requires --confirm)."""
    from auto_invest.persistence.audit import HaltClearedPayload
    from auto_invest.worker.halt import clear_halt as _clear_halt

    if not confirm:
        typer.echo(
            "Pass --confirm to actually clear the halt flag.",
            err=True,
        )
        _exit(2)

    cleared = _clear_halt(halt_path)
    if not cleared:
        typer.echo("No halt flag was set.")
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.get_connection(db_path)
    db.migrate(conn)
    try:
        from auto_invest.persistence import audit as _audit

        _audit.append(conn, HaltClearedPayload(cleared_by="cli"))
    finally:
        conn.close()
    typer.echo("Halt cleared.")


async def _run_live(
    *,
    cfg,
    secrets: dict,
    db_path: Path,
    halt_path: Path,
    config_path: Path,
    base_url: str,
    total_capital_usd: Decimal,
    require_session_open: bool,
) -> None:
    settings = WorkerSettings(
        config=cfg,
        db_path=db_path,
        halt_path=halt_path,
        config_path=config_path,
        total_capital_usd=total_capital_usd,
        require_session_open=require_session_open,
    )

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as inner:
        token = await get_valid_token(
            inner,
            base_url=base_url,
            app_key=secrets["KIS_APP_KEY"],
            app_secret=secrets["KIS_APP_SECRET"],
            cache_path=db_path.parent / "kis_token.json",
        )
        broker = ResilientClient(
            inner,
            rate_limiter=AsyncTokenBucket(rate_per_sec=15.0, capacity=15.0),
            breaker=CircuitBreaker(failure_threshold=5, cooldown_seconds=30.0),
            max_retries=4,
        )
        worker = Worker(
            settings,
            broker=broker,
            access_token=token.access_token,
            app_key=secrets["KIS_APP_KEY"],
            app_secret=secrets["KIS_APP_SECRET"],
            account_no=secrets["KIS_ACCOUNT_NO"],
        )

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            with contextlib.suppress(NotImplementedError):  # pragma: no cover (Windows)
                loop.add_signal_handler(sig, worker.request_stop)

        worker.record_start(secret_keys=list(secrets.keys()))
        try:
            await worker.run_forever()
        finally:
            worker.record_stop("normal_shutdown")
            worker.close()


async def _run_paper(
    *,
    cfg,
    secrets: dict,
    db_path: Path,
    halt_path: Path,
    config_path: Path,
    base_url: str,
    total_capital_usd: Decimal,
    require_session_open: bool,
    ruleset_sha256: str,
) -> int:
    """Spec 009 — paper-trading 데몬 메인 루프.

    mutex check → KIS token 발급 (quote용) → paper-mode Worker → run_forever.
    종료 사유에 따라 PAPER_RUN_STOPPED 페이로드의 reason이 결정된다.
    리턴 코드: 0 정상, 70 mutex 충돌.
    """
    from auto_invest.paper import mutex as paper_mutex

    settings = WorkerSettings(
        config=cfg,
        db_path=db_path,
        halt_path=halt_path,
        config_path=config_path,
        total_capital_usd=total_capital_usd,
        require_session_open=require_session_open,
        paper_mode=True,
        ruleset_sha256=ruleset_sha256,
    )

    # mutex check는 token 발급 전에 — 충돌이면 KIS API 호출 0건으로 종료.
    pre_conn = db.get_connection(db_path)
    try:
        mx = paper_mutex.check_and_acquire(pre_conn, attempted_mode="paper")
    finally:
        pre_conn.close()
    if not mx.allowed:
        typer.echo(
            f"paper-run 시작 거부: {mx.conflicting_event_type} (seq={mx.conflicting_event_id}) "
            f"가 {mx.conflicting_session_started_at}에 시작되어 아직 실행 중입니다. "
            "기존 worker 종료 후 paper-run을 다시 시작하세요.",
            err=True,
        )
        return mx.exit_code

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as inner:
        token = await get_valid_token(
            inner,
            base_url=base_url,
            app_key=secrets["KIS_APP_KEY"],
            app_secret=secrets["KIS_APP_SECRET"],
            cache_path=db_path.parent / "kis_token.json",
        )
        broker = ResilientClient(
            inner,
            rate_limiter=AsyncTokenBucket(rate_per_sec=15.0, capacity=15.0),
            breaker=CircuitBreaker(failure_threshold=5, cooldown_seconds=30.0),
            max_retries=4,
        )
        worker = Worker(
            settings,
            broker=broker,
            access_token=token.access_token,
            app_key=secrets["KIS_APP_KEY"],
            app_secret=secrets["KIS_APP_SECRET"],
            account_no=secrets["KIS_ACCOUNT_NO"],
        )

        loop = asyncio.get_running_loop()
        stop_reason = {"value": "normal_shutdown"}

        def _on_signal() -> None:
            stop_reason["value"] = "signal_received"
            worker.request_stop()

        for sig in (signal.SIGTERM, signal.SIGINT):
            with contextlib.suppress(NotImplementedError):  # pragma: no cover (Windows)
                loop.add_signal_handler(sig, _on_signal)

        worker.record_start(secret_keys=list(secrets.keys()))
        session_id = worker.router.paper_session_id
        typer.echo(f"paper-run started (session_id={session_id}, ruleset_sha256={ruleset_sha256})")
        try:
            await worker.run_forever()
        except Exception:  # pragma: no cover — best-effort crash recording
            stop_reason["value"] = "crash"
            raise
        finally:
            worker.record_stop(stop_reason["value"])
            worker.close()
    return 0


# ---------------------------------------------------------------------------
# spec 008 backtest subcommands (T026)
# ---------------------------------------------------------------------------


def _load_rules_for_backtest(rules_path: Path) -> tuple[object, object, list[object], str]:
    """Backtest-friendly TOML loader: no secrets required (contracts/backtest-cli.md).

    Returns `(caps, whitelist, rules, ruleset_sha256)`. Raises `ConfigError`
    on validation failure (caller maps to exit 65). The SHA-256 is over the
    raw file bytes so the same file on two machines hashes identically.
    """
    import hashlib
    import tomllib

    from pydantic import ValidationError as _ValidationError

    from auto_invest.config.caps import SizingCaps
    from auto_invest.config.rules import TradingRule
    from auto_invest.config.whitelist import Whitelist

    if not rules_path.exists():
        raise ConfigError(f"rules file not found: {rules_path}")
    raw_bytes = rules_path.read_bytes()
    ruleset_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    try:
        raw = tomllib.loads(raw_bytes.decode("utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"rules file is not valid TOML: {e}") from e

    try:
        caps = SizingCaps.model_validate(raw.get("caps", {}))
    except _ValidationError as e:
        raise ConfigError(f"[caps] section invalid: {e}") from e
    try:
        whitelist = Whitelist.model_validate(raw.get("whitelist", {}))
    except _ValidationError as e:
        raise ConfigError(f"[whitelist] section invalid: {e}") from e

    rules_raw = raw.get("rules", [])
    rules: list[TradingRule] = []
    seen: set[str] = set()
    for i, rule_data in enumerate(rules_raw):
        try:
            rule = TradingRule.model_validate(rule_data)
        except _ValidationError as e:
            raise ConfigError(f"[[rules]] entry {i} invalid: {e}") from e
        if rule.id in seen:
            raise ConfigError(f"duplicate rule id: {rule.id!r}")
        seen.add(rule.id)
        rules.append(rule)
    return caps, whitelist, rules, ruleset_sha256


@app.command("ingest-history")
def ingest_history_cmd(
    from_dir: Path = typer.Option(
        ...,
        "--from-dir",
        help="Directory of <SYMBOL>.csv files (see contracts/ohlcv-csv.md).",
    ),
    out_dir: Path = typer.Option(
        Path("data/history"),
        "--out-dir",
        help="Versioned subdirectory is created under this root.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate CSVs and print what WOULD be ingested; write nothing.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Print per-file progress; default is one summary line.",
    ),
) -> None:
    """One-shot OHLCV ingest from operator-provided CSVs (T026; see contracts/backtest-cli.md).

    Exit codes:
        0   success; stdout last line is the new dataset_version hex
        64  usage error (missing dir, bad flags)
        65  CSV validation failure (stderr lists offending rows)
        73  out-dir not writable
    """
    from auto_invest.backtest.ingest import IngestError, ingest_history

    if not from_dir.exists() or not from_dir.is_dir():
        typer.echo(f"--from-dir does not exist or is not a directory: {from_dir}", err=True)
        _exit(64)

    if not dry_run:
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            typer.echo(f"out-dir not writable: {out_dir} ({exc})", err=True)
            _exit(73)

    try:
        result = ingest_history(from_dir, out_dir, dry_run=dry_run)
    except IngestError as exc:
        typer.echo(f"CSV validation failed: {exc}", err=True)
        _exit(65)
        return

    if verbose:
        typer.echo(f"dataset_version: {result.dataset_version}")
        typer.echo(f"dataset_dir:     {result.dataset_dir}")
        typer.echo(f"files_ingested:  {result.files_ingested}")
        typer.echo(f"rows_ingested:   {result.rows_ingested}")
        typer.echo(f"reused_existing: {result.reused_existing}")
    else:
        typer.echo(
            f"ingested {result.files_ingested} file(s), "
            f"{result.rows_ingested} row(s) → {result.dataset_dir}"
        )
    # Per contract: stdout's last line is the new dataset_version hex.
    typer.echo(result.dataset_version)


@app.command("backtest")
def backtest_cmd(
    rules: Path = typer.Option(
        ..., "--rules", help="Path to rules TOML (same format as the live worker)."
    ),
    date_from: str = typer.Option(
        None, "--from", help="Inclusive session-date start (YYYY-MM-DD)."
    ),
    date_to: str = typer.Option(
        None, "--to", help="Inclusive session-date end (YYYY-MM-DD)."
    ),
    dataset_version: str = typer.Option(
        None,
        "--dataset-version",
        help="Specific dataset_version; defaults to most recent under data/history/.",
    ),
    invoker: str = typer.Option(
        "cli", "--invoker", help="cli (default) or canary (set by spec 007 harness)."
    ),
    replay_seed: int = typer.Option(
        0, "--replay-seed", help="Reserved for future stochastic strategies."
    ),
    synthetic_shock: bool = typer.Option(
        False,
        "--synthetic-shock",
        help="Replay the canonical shock dates from config/synthetic_shocks.toml.",
    ),
    out_dir: Path = typer.Option(
        Path("data/backtest"),
        "--out-dir",
        help="Per-run subdirectory created under this root.",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite audit-log path.",
    ),
    halt_path: Path = typer.Option(
        Path("data/halt.flag"),
        "--halt-path",
        help="Filesystem halt-flag path (reused unmodified from live worker).",
    ),
    history_root: Path = typer.Option(
        Path("data/history"),
        "--history-root",
        help="Where ingested datasets live (parent of <dataset_version>/).",
    ),
    allow_kernel_edits: bool = typer.Option(
        False,
        "--allow-kernel-edits",
        help="Bypass kernel-touched-tree check (R-B8). Logged on use.",
    ),
) -> None:
    """Run a backtest against an ingested dataset (T026; contracts/backtest-cli.md)."""
    from datetime import date as _date

    from auto_invest.backtest.data_source import CSVDataSource, latest_dataset_dir
    from auto_invest.backtest.run import (
        EXIT_COVERAGE,
        EXIT_OK,
        RunOptions,
        run_backtest,
    )

    if invoker not in ("cli", "canary"):
        typer.echo(f"--invoker must be 'cli' or 'canary', got {invoker!r}", err=True)
        _exit(64)

    # Resolve dataset directory.
    if dataset_version is not None:
        dataset_dir = history_root / dataset_version
        if not (dataset_dir / "manifest.json").exists():
            typer.echo(
                f"dataset_version {dataset_version!r} not found under {history_root}",
                err=True,
            )
            _exit(64)
    else:
        latest = latest_dataset_dir(history_root)
        if latest is None:
            typer.echo(
                f"no ingested datasets under {history_root}; "
                "run `auto-invest ingest-history` first",
                err=True,
            )
            _exit(64)
            return
        dataset_dir = latest

    # Parse dates / resolve shocks.
    shocks: tuple = ()
    shock_windows: tuple = ()
    if synthetic_shock:
        from datetime import date as _date_today

        from auto_invest.backtest.synthetic_shocks import (
            SyntheticShockConfigError,
            resolve_synthetic_shock_dates,
            shock_window,
        )

        try:
            resolved = resolve_synthetic_shock_dates(today=_date_today.today())
        except SyntheticShockConfigError as exc:
            typer.echo(f"synthetic shock config error: {exc}", err=True)
            _exit(64)
            return
        shocks = tuple(resolved)
        shock_windows = tuple(shock_window(s) for s in resolved)
        ds_start = min(w[0] for w in shock_windows)
        ds_end = max(w[1] for w in shock_windows)
    else:
        if date_from is None or date_to is None:
            typer.echo("--from and --to are required (YYYY-MM-DD)", err=True)
            _exit(64)
        try:
            ds_start = _date.fromisoformat(date_from)
            ds_end = _date.fromisoformat(date_to)
        except ValueError as exc:
            typer.echo(f"date parsing failed: {exc}", err=True)
            _exit(64)
            return
        if ds_end < ds_start:
            typer.echo(f"--to ({ds_end}) is before --from ({ds_start})", err=True)
            _exit(64)

    # Load rules (no secrets — backtest never reaches KIS / Anthropic).
    try:
        caps, whitelist, parsed_rules, ruleset_sha256 = _load_rules_for_backtest(rules)
    except ConfigError as exc:
        typer.echo(f"rules validation failed: {exc}", err=True)
        _exit(65)
        return

    data_source = CSVDataSource(dataset_dir)
    # Coverage pre-check (FR-B10).
    holes = data_source.coverage_holes(
        list(data_source.list_symbols()), ds_start, ds_end
    )
    if holes:
        for sym, d in holes[:20]:
            typer.echo(f"coverage hole: {sym} {d.isoformat()}", err=True)
        if len(holes) > 20:
            typer.echo(f"...and {len(holes) - 20} more", err=True)
        _exit(EXIT_COVERAGE)

    # Open audit DB (reused with the live worker; new event types already
    # in audit.py since K4 commit bc47361).
    _require_clean_migrations(db_path, allow_apply=True)
    conn = db.get_connection(db_path)
    try:
        options = RunOptions(
            rules_path=rules,
            rules=parsed_rules,
            ruleset_sha256=ruleset_sha256,
            data_source=data_source,
            date_start=ds_start,
            date_end=ds_end,
            caps=caps,
            whitelist=whitelist,
            halt_path=halt_path,
            out_root=out_dir,
            invoker=invoker,  # type: ignore[arg-type]
            replay_seed=replay_seed,
            synthetic_shock=synthetic_shock,
            allow_kernel_edits=allow_kernel_edits,
            shocks=shocks,
            shock_windows=shock_windows,
        )
        outcome = run_backtest(options, conn=conn)
    finally:
        conn.close()
        data_source.close()

    # Stdout layout per contracts/backtest-cli.md: run_id is the first AND
    # last printable line so both `head -1` and `tail -1` work for scripting.
    typer.echo(f"backtest run_id: {outcome.run_id}")
    typer.echo(f"dataset_version: {data_source.dataset_version}")
    typer.echo(f"ruleset_sha256:  {ruleset_sha256}")
    typer.echo(f"date range:      {ds_start} → {ds_end}")
    typer.echo(f"artefacts:       {outcome.run_dir}")
    if outcome.exit_code == EXIT_OK:
        typer.echo("")
        summary_path = outcome.run_dir / "summary.md"
        if summary_path.exists():
            # Spec US3: identical content goes to stdout AND summary.md.
            typer.echo(summary_path.read_text(encoding="utf-8"), nl=False)
    else:
        typer.echo("")
        typer.echo(f"FAILED: {outcome.failure_reason}", err=True)
    typer.echo(f"backtest run_id: {outcome.run_id}")

    if outcome.exit_code != EXIT_OK:
        _exit(outcome.exit_code)


@app.command("deploy")
def deploy(
    branch: str = typer.Option(
        "main",
        "--branch",
        help="Remote branch to deploy from.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run preconditions+pull+migrate+config-validate without restarting the worker.",
    ),
    allow_dirty: bool = typer.Option(
        False,
        "--allow-dirty",
        help="Permit a dirty working tree (logged in DEPLOY_STARTED.allow_dirty).",
    ),
    health_window_s: int = typer.Option(
        90,
        "--health-window-s",
        help="Seconds to poll for WORKER_STARTED after restart (>=90 per VIII.B-3).",
    ),
    triggered_by: str = typer.Option(
        "manual",
        "--triggered-by",
        help="Routing tag: 'manual' bypasses canary gate (IX.D); 'auto-tuner' enforces it.",
    ),
    ruleset_sha256: str = typer.Option(
        "",
        "--ruleset-sha256",
        help="Required when --triggered-by=auto-tuner; matched against CANARY_PASSED.",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite database path (audit log).",
    ),
    repo_path: Path = typer.Option(
        Path("."),
        "--repo",
        help="Git repository root.",
    ),
    config_path: Path = typer.Option(
        Path("config/rules.toml"),
        "--config",
        help="Worker rules config validated during the dry_run phase.",
    ),
    env_path: Path = typer.Option(
        Path(".env"),
        "--env-path",
        help="Operator .env file (used as fallback if env vars are absent).",
    ),
    supervisor_kind: str = typer.Option(
        "systemd",
        "--supervisor",
        help="Supervisor backend: 'systemd' (production) or 'dryrun' (test).",
    ),
    worker_unit: str = typer.Option(
        "auto-invest.service",
        "--worker-unit",
        help="systemd unit name passed to systemctl restart (ignored for --supervisor=dryrun).",
    ),
) -> None:
    """Deploy the latest branch off-hours per spec 006.

    Runs the full phase machine: preconditions → pull → kernel_check →
    canary_gate (if auto-tuner) → sync → migrate → dry_run → restart →
    health_check, with rollback on failure. Exit codes per
    `specs/006-deploy-automation/contracts/deploy-cli.md`.
    """
    if health_window_s < 90:
        typer.echo(
            f"--health-window-s must be >= 90 (got {health_window_s}); "
            "constitution VIII.B-3 forbids shorter windows.",
            err=True,
        )
        _exit(2)
    if triggered_by not in ("manual", "auto-tuner"):
        typer.echo(
            f"--triggered-by must be 'manual' or 'auto-tuner' (got {triggered_by!r}).",
            err=True,
        )
        _exit(2)
    if triggered_by == "auto-tuner" and not ruleset_sha256:
        typer.echo(
            "--ruleset-sha256 is required when --triggered-by=auto-tuner.",
            err=True,
        )
        _exit(2)
    if supervisor_kind not in ("systemd", "dryrun"):
        typer.echo(
            f"--supervisor must be 'systemd' or 'dryrun' (got {supervisor_kind!r}).",
            err=True,
        )
        _exit(2)

    from auto_invest.deploy.runner import DeployRunner, RunnerConfig
    from auto_invest.deploy.supervisor import (
        DryRunSupervisor,
        SystemdSupervisor,
    )

    if supervisor_kind == "systemd":
        sup = SystemdSupervisor(unit=worker_unit)
    else:
        sup = DryRunSupervisor()

    # Anchor every relative path to --repo so the CLI works regardless of
    # the caller's working directory. Without this, `sudo -u auto-invest`
    # from /root inherits cwd=/root and tries to create data/ under /root
    # where the auto-invest user has no write permission (PermissionError
    # observed when the operator drove deploy from the Vultr console).
    repo_path = repo_path.resolve()
    if not db_path.is_absolute():
        db_path = repo_path / db_path
    if not config_path.is_absolute():
        config_path = repo_path / config_path
    if not env_path.is_absolute():
        env_path = repo_path / env_path
    pid_path = repo_path / "data" / "auto_invest.deploy.pid"

    cfg = RunnerConfig(
        repo=repo_path,
        db_path=db_path,
        branch=branch,
        dry_run=dry_run,
        allow_dirty=allow_dirty,
        health_window_s=health_window_s,
        triggered_by=triggered_by,  # type: ignore[arg-type]
        ruleset_sha256=ruleset_sha256,
        config_path=config_path,
        env_path=env_path,
        pid_path=pid_path,
    )
    runner = DeployRunner(config=cfg, supervisor=sup)
    result = runner.run()
    for line in runner._stdout:
        typer.echo(line)
    for line in runner._stderr:
        typer.echo(line, err=True)
    if result.exit_code != 0:
        _exit(result.exit_code)

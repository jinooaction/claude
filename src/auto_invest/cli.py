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
from auto_invest.safety.autonomy import AutonomyLevel
from auto_invest.safety.boundary import (
    BoundarySurface,
    ProposedChange,
    assert_autonomous_boundary_allowed,
)
from auto_invest.worker.loop import Worker, WorkerSettings

app = typer.Typer(no_args_is_help=True, add_completion=False)
db_app = typer.Typer(help="Database management subcommands.", no_args_is_help=True)
safety_app = typer.Typer(help="Executable safety policy inspection.", no_args_is_help=True)
app.add_typer(db_app, name="db")
app.add_typer(safety_app, name="safety")
logger = logging.getLogger(__name__)


def _exit(code: int) -> None:
    raise typer.Exit(code)


def _assert_autonomous_write_allowed(
    *,
    summary: str,
    paths: tuple[Path | str, ...],
    requested_level: AutonomyLevel,
    declared_surfaces: frozenset[BoundarySurface] = frozenset(),
) -> None:
    assert_autonomous_boundary_allowed(
        ProposedChange(
            summary=summary,
            paths=tuple(str(path) for path in paths),
            declared_surfaces=declared_surfaces,
            requested_level=requested_level,
        )
    )


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


@app.command("telegram-alerts")
def telegram_alerts(
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite audit_log database path.",
    ),
    env_file: Path | None = typer.Option(
        None,
        "--env-file",
        help="Optional .env file containing TELEGRAM_* values.",
    ),
    state_file: Path = typer.Option(
        Path("data/telegram_alerts_state.json"),
        "--state-file",
        help="Cursor state file that stores the last alerted audit seq.",
    ),
    once: bool = typer.Option(
        False,
        "--once",
        help="Process one batch and exit.",
    ),
    follow_mode: bool = typer.Option(
        False,
        "--follow",
        help="Poll continuously for new audit rows.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print would-send messages without requiring Telegram secrets.",
    ),
    replay_existing: bool = typer.Option(
        False,
        "--replay-existing",
        help="If no cursor exists, start from seq 0 instead of current max seq.",
    ),
    include_paper: bool = typer.Option(
        False,
        "--include-paper",
        help="Also alert ORDER_PAPER_FILLED events.",
    ),
    poll_interval_seconds: float = typer.Option(
        5.0,
        "--poll-interval",
        help="Polling interval for --follow.",
    ),
    max_catchup_alerts: int = typer.Option(
        25,
        "--max-catchup-alerts",
        help=(
            "Maximum stale-cursor backlog alerts to send on startup. "
            "Use 0 to skip backlog, negative to disable the cap."
        ),
    ),
    error_cooldown_seconds: float = typer.Option(
        3600.0,
        "--error-cooldown-seconds",
        help="Suppress identical ERROR alerts for this many seconds. Use 0 to disable.",
    ),
    test_message: bool = typer.Option(
        False,
        "--test-message",
        help="Send or print a Telegram test message and exit.",
    ),
) -> None:
    """Send Telegram alerts from audit_log order events.

    This command is an observer. It reads committed audit rows and never submits,
    cancels, modifies, or syncs orders.
    """
    import sys as _sys

    from auto_invest.notifications.audit_tail import follow, process_once
    from auto_invest.notifications.telegram import (
        TelegramConfigError,
        TelegramNotifier,
        load_telegram_config,
    )

    configure_logging()
    try:
        cfg = load_telegram_config(env_file, require=not dry_run)
    except (TelegramConfigError, ValueError) as exc:
        typer.echo(f"Telegram configuration error: {exc}", err=True)
        _exit(2)

    if test_message:
        text = (
            f"{cfg.source_label} Telegram alerts test\n"
            "이 메시지가 보이면 모바일 알림 채널이 연결됐습니다."
        )
        if dry_run:
            typer.echo(text)
            return
        try:
            asyncio.run(TelegramNotifier(cfg).send_message(text))
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"Telegram send failed: {type(exc).__name__}", err=True)
            _exit(1)
        typer.echo("Telegram test message sent.")
        return

    if not once and not follow_mode:
        once = True

    try:
        if follow_mode:
            asyncio.run(
                follow(
                    db_path=db_path,
                    state_file=state_file,
                    config=cfg,
                    dry_run=dry_run,
                    replay_existing=replay_existing,
                    include_paper=include_paper,
                    poll_interval_seconds=poll_interval_seconds,
                    max_catchup_alerts=max_catchup_alerts,
                    error_cooldown_seconds=error_cooldown_seconds,
                    output=_sys.stdout,
                )
            )
        else:
            count = asyncio.run(
                process_once(
                    db_path=db_path,
                    state_file=state_file,
                    config=cfg,
                    dry_run=dry_run,
                    replay_existing=replay_existing,
                    include_paper=include_paper,
                    max_catchup_alerts=max_catchup_alerts,
                    error_cooldown_seconds=error_cooldown_seconds,
                    output=_sys.stdout,
                )
            )
            typer.echo(f"telegram-alerts processed={count}")
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        _exit(1)
    except KeyboardInterrupt:
        raise typer.Exit(130) from None
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Telegram alert loop failed: {type(exc).__name__}", err=True)
        _exit(1)


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
    capital_tracking: bool = typer.Option(
        False,
        "--capital-tracking/--no-capital-tracking",
        help="스펙 029 슬라이스 2: 게이트 캡 기준을 라이브 순자산(NAV)에 맞춘다. "
        "끄면(기본) --capital 시작 자본을 상수로 사용. 켜면 하락은 항상 캡을 줄이고"
        "(방어), 상승은 --capital-growth 일 때만 반영.",
    ),
    capital_growth: bool = typer.Option(
        False,
        "--capital-growth/--no-capital-growth",
        help="스펙 029 슬라이스 2: 순자산이 시작 자본보다 커지면 캡 기준을 키운다(복리 "
        "성장). --capital-max-growth 배수로 상한. --capital-tracking 필요. 끄면 시작 "
        "자본이 천장(상승 미반영, 하락 방어는 그대로).",
    ),
    capital_max_growth: float = typer.Option(
        2.0,
        "--capital-max-growth",
        help="스펙 029 슬라이스 2: 성장 시 유효 자본 상한 = 시작 자본 × 이 배수 "
        "(기본 2.0). 폭주 방지 하드 클램프.",
    ),
    backfill: bool = typer.Option(
        False,
        "--backfill/--no-backfill",
        help="스펙 033: 세션당 1회 유니버스(whitelist) 일봉을 KIS 기간별시세로 받아 "
        "price_bars 를 최신 유지(읽기 전용 시세, 주문 0건). 켜면 재조정 스코어러·지표 "
        "룰이 신선한 일봉을 본다. 기본 끔(옵트인).",
    ),
    prices_path: Path = typer.Option(
        Path("config/llm_prices.toml"),
        "--prices",
        help="Anthropic price table (TOML); validated at startup per spec 002.",
    ),
    external_holdings_path: Path = typer.Option(
        Path("deploy/external-holdings.toml"),
        "--external-holdings",
        help="시스템 비관리 외부 보유 기준선 TOML — 장 마감 정합성이 (원장+기준선)을 "
        "브로커 잔고와 대조한다. 파일이 없으면 기준선 없음(종전 동작).",
    ),
) -> None:
    configure_logging()

    # 1. Secrets + config (refuses on missing required values).
    from auto_invest.reconciliation.external_holdings import load_external_holdings
    from auto_invest.telemetry.prices import PriceTableError, load_prices

    try:
        secrets = load_secrets(env_file)
        cfg = load_config(config, env_path=env_file)
        prices = load_prices(prices_path)
        external_holdings = load_external_holdings(external_holdings_path)
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
            capital_tracking_enabled=capital_tracking,
            capital_growth_enabled=capital_growth,
            capital_max_growth_factor=Decimal(str(capital_max_growth)),
            backfill_enabled=backfill,
            external_holdings=external_holdings,
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
    # 보유·잔고는 모든 미국 거래소(NASD·NYSE·AMEX)를 훑어 합쳐 조회한다 — 멀티에셋 유니버스
    # (SPY·GLD=AMEX, IEF=NASD)에서 다른 거래소 종목이 Claude 프롬프트·감사 계좌상태에서
    # 누락되지 않게(체결·정합성 경로와 동일한 거래소 자동 해석).
    from auto_invest.broker.overseas import (
        get_balance_resolving_market,
        get_positions_resolving_market,
    )

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
        balance = await get_balance_resolving_market(
            client,
            access_token=token.access_token,
            app_key=app_key,
            app_secret=app_secret,
            account=account_no,
        )
        positions = await get_positions_resolving_market(
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
    from auto_invest.broker.overseas import get_quote_resolving_market

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
                # 거래소 자동 해석(NAS→NYS→AMS): SPY·GLD(AMS) 마크가 고정 NAS 로 누락돼
                # NAV 가 과소 계상되던 문제 수정.
                quote = await get_quote_resolving_market(
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


@app.command("rejected-order-opportunity")
def rejected_order_opportunity_cmd(
    result_json: Path = typer.Option(
        ...,
        "--result-json",
        help="rebalance-once --json 결과 파일. 없거나 비어 있으면 거부 주문 0건으로 처리.",
    ),
    marks_json: Path | None = typer.Option(
        None,
        "--marks-json",
        help="선택: {SYMBOL: current_mark_usd} JSON. 지정하면 KIS 시세 조회를 생략.",
    ),
    env_file: Path | None = typer.Option(
        None,
        "--env-file",
        help="선택: KIS 현재가 조회용 .env. --marks-json 이 없을 때만 사용.",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="KIS token cache 위치를 잡기 위한 SQLite 경로. DB 쓰기는 하지 않음.",
    ),
    base_url: str = typer.Option(
        "https://openapi.koreainvestment.com:9443",
        "--base-url",
        help="KIS REST base URL.",
    ),
    no_marks: bool = typer.Option(
        False,
        "--no-marks",
        help="현재가 조회를 생략하고 거부 주문 목록만 보고.",
    ),
    output_format: str = typer.Option(
        "text",
        "--format",
        help="text 또는 json.",
    ),
) -> None:
    """거부된 rebalance 주문의 현재가 기준 기회손익을 계산한다.

    양수는 해당 거부 주문이 정상 체결됐더라면 현재 더 유리했음을 뜻한다. 음수는
    거부된 것이 결과적으로 더 유리했음을 뜻한다. 이 명령은 읽기 전용이며 주문을
    재시도하지 않는다.
    """
    import json as _json
    from decimal import Decimal as _Decimal

    from auto_invest.analytics.order_opportunity import (
        build_rejected_order_opportunity_report,
        rejected_order_symbols,
        render_rejected_order_opportunity_text,
    )

    if output_format not in ("text", "json"):
        typer.echo("--format must be 'text' or 'json'.", err=True)
        _exit(2)

    def _read_json(path: Path) -> dict:
        try:
            text = path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return {}
        if not text or text.startswith("("):
            return {}
        try:
            data = _json.loads(text)
        except _json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    result = _read_json(result_json)
    symbols = list(rejected_order_symbols(result))
    marks: dict[str, _Decimal] = {}
    mark_fetch_error: str | None = None

    if no_marks or not symbols:
        pass
    elif marks_json is not None:
        raw_marks = _read_json(marks_json)
        for symbol, value in raw_marks.items():
            try:
                marks[str(symbol).upper()] = _Decimal(str(value))
            except Exception:  # noqa: BLE001 - bad mark input just leaves that symbol unvalued
                continue
    elif env_file is not None:
        try:
            secrets = load_secrets(env_file)
            marks = asyncio.run(
                _fetch_marks(
                    symbols,
                    base_url=base_url,
                    app_key=secrets["KIS_APP_KEY"],
                    app_secret=secrets["KIS_APP_SECRET"],
                    db_path=db_path,
                )
            )
        except Exception as exc:  # noqa: BLE001 - opportunity report must not block workflows
            mark_fetch_error = f"{type(exc).__name__}: {exc}"
    else:
        mark_fetch_error = "no marks source provided"

    report = build_rejected_order_opportunity_report(
        result,
        marks,
        mark_fetch_error=mark_fetch_error,
    )
    if output_format == "json":
        typer.echo(_json.dumps(report.to_json_dict(), ensure_ascii=False, indent=2))
    else:
        typer.echo(render_rejected_order_opportunity_text(report))


@app.command("opportunity-monitor")
def opportunity_monitor_cmd(
    history_json: Path | None = typer.Option(
        None,
        "--history-json",
        help="기존 opportunity_history.json. 없거나 손상되면 빈 기록으로 처리.",
    ),
    opportunity_json: Path | None = typer.Option(
        None,
        "--opportunity-json",
        help="이번 실행의 rejected-order-opportunity JSON. 지정하면 history 에 추가.",
    ),
    history_out: Path | None = typer.Option(
        None,
        "--history-out",
        help="갱신된 rolling history JSON 출력 경로.",
    ),
    monitor_out: Path | None = typer.Option(
        None,
        "--monitor-out",
        help="누적 monitor summary JSON 출력 경로.",
    ),
    run_id: str | None = typer.Option(None, "--run-id", help="GitHub Actions run id."),
    run_url: str | None = typer.Option(None, "--run-url", help="GitHub Actions run URL."),
    event: str | None = typer.Option(None, "--event", help="workflow event 이름."),
    live_outcome: str | None = typer.Option(
        None,
        "--live-outcome",
        help="LIVE rebalance step outcome.",
    ),
    armed: str | None = typer.Option(
        None,
        "--armed",
        help="micro GTAA armed 값(true/false/unknown).",
    ),
    capital_usd: str | None = typer.Option(
        None,
        "--capital-usd",
        help="micro GTAA declared capital USD.",
    ),
    timestamp_utc: str | None = typer.Option(
        None,
        "--timestamp-utc",
        help="기록 시각 ISO8601 UTC. 생략하면 현재 UTC.",
    ),
    max_entries: int = typer.Option(
        60,
        "--max-entries",
        help="rolling history 최대 보존 실행 수.",
    ),
    min_valued_reports: int = typer.Option(
        2,
        "--min-valued-reports",
        help="자동 verdict 에 필요한 최소 평가 가능 실행 수.",
    ),
    strategy_review_loss_usd: str = typer.Option(
        "-5.00",
        "--strategy-review-loss-usd",
        help="누적 전략 의도 손실 검토 임계값(음수).",
    ),
    execution_review_gain_usd: str = typer.Option(
        "5.00",
        "--execution-review-gain-usd",
        help="거부로 놓친 누적 이익 검토 임계값(양수).",
    ),
    streak_threshold: int = typer.Option(
        2,
        "--streak-threshold",
        help="같은 방향 최신 연속 신호 검토 임계 횟수.",
    ),
    output_format: str = typer.Option("json", "--format", help="json | text."),
) -> None:
    """거부 주문 기회손익을 rolling history 로 누적하고 전략/실행 검토 신호를 낸다.

    이 명령은 브로커를 호출하지 않고 주문을 재시도하지 않는다. 양수 누적은 거부 때문에
    이익을 놓쳤다는 실행 경로 신호, 음수 누적은 전략 의도가 손실이었을 수 있다는 전략
    검토 신호로 해석한다. 단, 이 신호 하나로 자동 전략 교체를 수행하지 않는다.
    """
    import json as _json

    from auto_invest.analytics.opportunity_monitor import (
        OpportunityMonitorThresholds,
        append_opportunity_record,
        empty_opportunity_history,
        render_opportunity_monitor_text,
        summarize_opportunity_history,
    )

    if output_format not in ("json", "text"):
        typer.echo("--format must be 'json' or 'text'.", err=True)
        _exit(2)

    def _read_json(path: Path | None) -> dict:
        if path is None:
            return {}
        try:
            text = path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return {}
        if not text or text.startswith("("):
            return {}
        try:
            data = _json.loads(text)
        except _json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    history = _read_json(history_json)
    if opportunity_json is not None:
        history = append_opportunity_record(
            history,
            _read_json(opportunity_json),
            run_id=run_id,
            run_url=run_url,
            event=event,
            live_outcome=live_outcome,
            armed=armed,
            capital_usd=capital_usd,
            timestamp_utc=timestamp_utc,
            max_entries=max_entries,
        )
    elif not history:
        history = empty_opportunity_history(max_entries=max_entries)

    thresholds = OpportunityMonitorThresholds(
        min_valued_reports=min_valued_reports,
        strategy_review_loss_usd=strategy_review_loss_usd,
        execution_review_gain_usd=execution_review_gain_usd,
        streak_threshold=streak_threshold,
    )
    summary = summarize_opportunity_history(history, thresholds=thresholds)

    history_text = _json.dumps(history, ensure_ascii=False, indent=2) + "\n"
    monitor_text = _json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if history_out is not None:
        history_out.write_text(history_text, encoding="utf-8")
    if monitor_out is not None:
        monitor_out.write_text(monitor_text, encoding="utf-8")
    if output_format == "json":
        typer.echo(monitor_text, nl=False)
    else:
        typer.echo(render_opportunity_monitor_text(summary))


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
        compute_fill_latency,
        compute_performance,
        compute_slippage,
        read_fills,
        reconstruct,
        render_latency_text,
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

    # spec 028: 체결 지연(의사결정→체결) — 라이브에서만 의미가 있다(페이퍼는 동기 체결).
    latency_stats = compute_fill_latency(fills)

    if snapshot:
        # 측정은 위에서 read-only(query_only)로 끝냈다. 스냅샷은 분리된 쓰기
        # 연결에서 추가-전용으로 단 1건만 기록한다(append-only 불변량 보존).
        from auto_invest.persistence import audit

        write_conn = db.get_connection(db_path)
        try:
            seq = audit.append(
                write_conn,
                audit.LivePerformanceSnapshotPayload(
                    **snapshot_fields(
                        report,
                        computed_at_utc=_d_iso_now(),
                        latency=latency_stats if mode == "live" else None,
                    )
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
            payload["fill_latency"] = latency_stats.to_json_dict()
        typer.echo(_json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        typer.echo(render_text(report))
        if slippage_stats is not None:
            typer.echo("")
            typer.echo(render_slippage_text(slippage_stats))
            typer.echo("")
            typer.echo(render_latency_text(latency_stats))


async def _run_fill_sync(
    conn,
    *,
    base_url: str,
    app_key: str,
    app_secret: str,
    account_no: str,
    db_path: Path,
):
    """Spec 015 — 라이브 열린 주문의 체결을 브로커에서 당겨 장부에 반영.

    체결 조회는 모든 미국 거래소(NASD·NYSE·AMEX)를 훑어 합친다(sync_fills 기본
    markets=US_ORDER_EXCHANGES) — 멀티에셋 유니버스의 체결이 단일 거래소 조회에서
    누락되지 않게."""
    from auto_invest.execution.fill_sync import sync_fills

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
        return await sync_fills(
            conn,
            client,
            access_token=token.access_token,
            app_key=app_key,
            app_secret=app_secret,
            account=account_no,
        )


@app.command()
def fills(
    sync: bool = typer.Option(
        False,
        "--sync",
        help="브로커 체결 조회로 라이브 열린 주문의 체결을 한 번 당겨 장부에 반영. "
        "--env 필요. 미지정 시 읽기 전용 요약만 출력.",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"), "--db", help="SQLite database path."
    ),
    env_file: Path | None = typer.Option(
        None, "--env", help="KIS 자격 증명 .env (--sync 에 필요)."
    ),
    base_url: str = typer.Option(
        "https://openapi.koreainvestment.com:9443",
        "--base-url",
        help="KIS REST base URL (--sync 체결 조회용).",
    ),
    market: str = typer.Option(
        "NASD",
        "--market",
        help="(하위 호환) 해외거래소 코드. --sync 는 이제 모든 미국 거래소"
        "(NASD·NYSE·AMEX)를 훑어 합치므로 이 값과 무관하게 멀티에셋 체결을 모두 동기화한다.",
    ),
) -> None:
    """Spec 015 — 라이브 체결 동기화/조회.

    `--sync` 는 열린 주문(SUBMITTED/PARTIALLY_FILLED)의 실제 체결을 브로커에서
    당겨와 FILL 기록·보유 갱신·상태 전이를 멱등하게 적용한다(주문/취소 안 함).
    인자 없이 실행하면 읽기 전용으로 열린 주문·최근 체결 요약만 출력한다.
    종료 코드: 0 정상 / 1 동기화 오류 / 2 오용.
    """
    from auto_invest.persistence import db as _db

    if not db_path.exists():
        typer.echo(f"DB 파일이 없습니다: {db_path}", err=True)
        _exit(1)

    conn = _db.get_connection(db_path)
    try:
        if sync:
            if env_file is None:
                typer.echo("--sync 에는 --env (KIS 자격 증명) 가 필요합니다.", err=True)
                _exit(2)
            try:
                secrets = load_secrets(env_file)
            except ConfigError as exc:
                typer.echo(f"환경 파일 오류: {exc}", err=True)
                _exit(2)
            result = asyncio.run(
                _run_fill_sync(
                    conn,
                    base_url=base_url,
                    app_key=secrets["KIS_APP_KEY"],
                    app_secret=secrets["KIS_APP_SECRET"],
                    account_no=secrets["KIS_ACCOUNT_NO"],
                    db_path=db_path,
                )
            )
            if not result.polled:
                typer.echo("열린 주문이 없어 동기화할 대상이 없습니다.")
            else:
                typer.echo(
                    f"체결 동기화: 열린 주문 {result.open_orders}건, "
                    f"적용 FILL {result.fills_applied}건 "
                    f"(수량 {result.qty_applied}), 상태 전이 {result.transitions}건."
                )
            if result.error is not None:
                typer.echo(f"⚠ 브로커 조회 오류(거래 무중단): {result.error}", err=True)
                _exit(1)

        # 읽기 전용 요약 (항상 출력).
        open_rows = conn.execute(
            "SELECT correlation_id, symbol, side, qty, state, kis_order_id "
            "FROM orders WHERE state IN ('SUBMITTED','PARTIALLY_FILLED') ORDER BY seq"
        ).fetchall()
        typer.echo(f"열린 주문: {len(open_rows)}건")
        for r in open_rows:
            typer.echo(
                f"  {r['correlation_id']}  {r['symbol']} {r['side']} {r['qty']}  "
                f"[{r['state']}]  kis={r['kis_order_id']}"
            )
        fill_rows = conn.execute(
            "SELECT order_correlation_id, qty, price_usd, executed_at_utc "
            "FROM fills ORDER BY seq DESC LIMIT 10"
        ).fetchall()
        typer.echo(f"최근 체결(최대 10): {len(fill_rows)}건")
        for r in fill_rows:
            typer.echo(
                f"  {r['order_correlation_id']}  {r['qty']} @ {r['price_usd']}  "
                f"{r['executed_at_utc']}"
            )
    finally:
        conn.close()
    _exit(0)


async def _run_reconcile(
    conn,
    *,
    base_url: str,
    app_key: str,
    app_secret: str,
    account_no: str,
    halt_path: Path,
    db_path: Path,
    market: str,
    external_holdings: dict[str, int] | None = None,
):
    """스펙 001 T050 — 로컬 보유를 브로커 잔고와 1회 대조(읽기-기반)."""
    from auto_invest.reconciliation.runner import run_reconciliation

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
        return await run_reconciliation(
            conn,
            client,
            access_token=token.access_token,
            app_key=app_key,
            app_secret=app_secret,
            account=account_no,
            halt_path=halt_path,
            # 보유·잔고 정합성은 모든 미국 거래소를 훑어 합친다(기본 markets=US_ORDER_EXCHANGES)
            # — 멀티에셋 유니버스의 다른 거래소 종목이 빠져 허위 halt 나지 않게.
            external_holdings=external_holdings,
        )


@app.command(name="promote-check")
def promote_check(
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"), "--db", help="SQLite database path."
    ),
    rules_path: Path = typer.Option(
        Path("deploy/canary-live-rules.toml"),
        "--rules",
        help="현재 라이브 캐너리 룰셋(caps = canary_min_duration_days·acceptance_drawdown 출처).",
    ),
    capital: float = typer.Option(
        12000.0,
        "--capital",
        help="라이브 캐너리 시작 자본(USD) — 총수익률 계산 기준.",
    ),
    mode: str = typer.Option("live", "--mode", help="live 또는 paper."),
    output_format: str = typer.Option(
        "text", "--format", help="text 또는 json."
    ),
) -> None:
    """스펙 026 — 라이브 캐너리가 풀라이브 승격 준비가 됐는지 평가(헌법 VI 절반).

    read-only. 라이브 audit_log 에서 라이브 기간·청산 거래·최대 낙폭·총수익률·
    서킷브레이커/정합성 이력을 측정해 promotion.gate 로 판정한다. ready=True 면
    종료코드 0, 아니면 1.

    주의(헌법 IX.B-2): 이건 VI(라이브 트랙레코드) 게이트다. **실제 풀라이브 승격**은
    여기에 더해 스펙 007 하드닝 캐너리(다중 지표·충격·퍼즈, ≥30/45 거래일)도 통과해야
    한다(production-deploy 게이트). 이 명령은 자동 승격을 수행하지 않는다 — 준비
    여부만 보고한다.
    """
    import json as _json
    import tomllib

    from auto_invest.config.caps import SizingCaps
    from auto_invest.promotion.readiness import compute_readiness

    if output_format not in ("text", "json"):
        typer.echo("--format must be 'text' or 'json'.", err=True)
        _exit(2)

    # caps 만 필요하므로 [caps] 섹션만 파싱한다 — 전체 load_config 와 달리 KIS 시크릿이
    # 없어도 동작(읽기 전용 평가).
    if not rules_path.exists():
        typer.echo(f"rules file not found: {rules_path}", err=True)
        _exit(2)
    caps = SizingCaps(**tomllib.loads(rules_path.read_text(encoding="utf-8"))["caps"])
    conn = db.get_connection(db_path)
    try:
        readiness = compute_readiness(
            conn,
            caps=caps,
            starting_capital=Decimal(str(capital)),
            mode=mode,
        )
    finally:
        conn.close()

    if output_format == "json":
        typer.echo(_json.dumps(readiness.to_json_dict(), ensure_ascii=False, indent=2))
    else:
        typer.echo(f"승격 준비: {'✅ READY' if readiness.ready else '⏳ NOT READY'}")
        for reason in readiness.reasons:
            typer.echo(f"  - {reason}")
        typer.echo(
            "주의: 실제 풀라이브 승격은 스펙 007 하드닝 캐너리(IX.B-2)도 통과해야 합니다."
        )

    _exit(0 if readiness.ready else 1)


@app.command()
def reconcile(
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"), "--db", help="SQLite database path."
    ),
    halt_path: Path = typer.Option(
        Path("data/halt.flag"), "--halt-path", help="Filesystem halt-flag path."
    ),
    env_file: Path | None = typer.Option(
        None, "--env", help="KIS 자격 증명 .env (브로커 잔고 조회에 필요)."
    ),
    base_url: str = typer.Option(
        "https://openapi.koreainvestment.com:9443",
        "--base-url",
        help="KIS REST base URL.",
    ),
    market: str = typer.Option("NASD", "--market", help="해외거래소 코드."),
    external_holdings_path: Path = typer.Option(
        Path("deploy/external-holdings.toml"),
        "--external-holdings",
        help="시스템 비관리 외부 보유 기준선 TOML — (원장+기준선)을 브로커와 대조. "
        "파일이 없으면 기준선 없음(종전 동작).",
    ),
) -> None:
    """스펙 001 P2 — 로컬 보유를 브로커 잔고와 대조(수동/모니터링용).

    라이브 워커가 매 장 마감마다 자동 수행하는 것과 같은 정합성 검증을 한 번
    실행한다(읽기-기반 — 주문/청산 안 함). 불일치면 halt 플래그를 세워 다음
    거래를 차단한다. 종료 코드: 0 정상(OK) / 1 불일치 또는 결론 불가(브로커 오류)
    / 2 설정·DB 오류.
    """
    import json as _json

    if env_file is None:
        typer.echo("--env (KIS 자격 증명) 가 필요합니다.", err=True)
        _exit(2)
    if not db_path.exists():
        typer.echo(f"DB 파일이 없습니다: {db_path}", err=True)
        _exit(2)
    from auto_invest.reconciliation.external_holdings import load_external_holdings

    try:
        secrets = load_secrets(env_file)
        external_holdings = load_external_holdings(external_holdings_path)
    except ConfigError as exc:
        typer.echo(f"환경 파일 오류: {exc}", err=True)
        _exit(2)

    conn = db.get_connection(db_path)
    try:
        outcome = asyncio.run(
            _run_reconcile(
                conn,
                base_url=base_url,
                app_key=secrets["KIS_APP_KEY"],
                app_secret=secrets["KIS_APP_SECRET"],
                account_no=secrets["KIS_ACCOUNT_NO"],
                halt_path=halt_path,
                db_path=db_path,
                market=market,
                external_holdings=external_holdings,
            )
        )
    finally:
        conn.close()

    typer.echo(f"정합성 검사: {outcome.state}")
    if outcome.diff:
        typer.echo(_json.dumps(outcome.diff, indent=2, ensure_ascii=False))
    if outcome.error:
        typer.echo(f"⚠ 브로커 조회 오류: {outcome.error}", err=True)
    _exit(0 if outcome.state == "OK" else 1)


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
    from auto_invest.judgment.observability import judgment_efficiency

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
        # spec 004: 판단 지점별 호출/적용/폴백/폴백률(audit_log 기반).
        judgment = judgment_efficiency(
            conn, window_start_utc=_iso_ms(start), window_end_utc=_iso_ms(end)
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
        "judgment": judgment,
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


@safety_app.command("commands")
def safety_commands(
    output_format: str = typer.Option(
        "json",
        "--format",
        help="json or markdown.",
    ),
) -> None:
    """Render the executable command safety registry."""
    import json as _json

    from auto_invest.safety.command_registry import command_policies

    if output_format not in ("json", "markdown"):
        typer.echo("--format must be 'json' or 'markdown'.", err=True)
        _exit(2)

    policies = [p.to_json_dict() for p in command_policies().values()]
    if output_format == "json":
        typer.echo(_json.dumps({"commands": policies}, indent=2, ensure_ascii=False))
        return

    rows = [
        "| command | level | orders | live config | capital | strategy | broker | db | llm |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for p in policies:
        rows.append(
            "| {name} | {level} | {can_place_order} | {can_change_live_config} | "
            "{can_scale_capital} | {can_reassign_strategy} | {uses_broker} | "
            "{writes_db} | {uses_llm} |".format(**p)
        )
    typer.echo("\n".join(rows))


def _attach_judgment_summary(conn, rep):  # noqa: ANN001, ANN201
    """daily_summary 판단 지점으로 리포트에 요약 섹션을 채운다(spec 004).

    ANTHROPIC_API_KEY 가 없으면 결정론적 폴백 문장을 쓴다. LLM 호출이 실패해도
    summarize_day 가 폴백 문장을 돌려주므로 리포트는 항상 섹션을 갖는다.
    """
    import asyncio
    import os

    from auto_invest.judgment.points.daily_summary import (
        attach_summary_to_report,
        fallback_narrative,
        summarize_day,
    )

    counters = rep.counters
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return attach_summary_to_report(rep, fallback_narrative(counters))
    try:
        import anthropic

        from auto_invest.judgment.client import JudgmentClient
        from auto_invest.telemetry.prices import load_prices

        prices = load_prices(Path("config/llm_prices.toml"))
        client = JudgmentClient(
            anthropic.AsyncAnthropic(api_key=api_key), conn=conn, prices=prices
        )
        summary = asyncio.run(summarize_day(client, conn=conn, counters=counters))
    except Exception:  # noqa: BLE001 — 어떤 실패든 결정론적 폴백으로
        summary = fallback_narrative(counters)
    return attach_summary_to_report(rep, summary)


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
        # spec 004 daily_summary 판단 지점(순수 자문): ANTHROPIC_API_KEY 가 있으면
        # Claude 서술 요약, 없거나 실패하면 결정론적 카운터 폴백. 어느 경우든
        # 리포트는 정상 생성된다(FR-022).
        rep = _attach_judgment_summary(conn, rep)
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
def health(
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
    output_format: str = typer.Option(
        "text",
        "--format",
        help="Output format: text or json.",
    ),
    stale_hours: float = typer.Option(
        36.0,
        "--stale-hours",
        help="Hours after which reconciliation/activity is flagged stale.",
    ),
) -> None:
    """Print a unified operational-health roll-up (read-only).

    Exit codes: 0 healthy (OK), 1 unhealthy (DEGRADED/CRITICAL), 2 bad usage.
    Never writes to the audit log and never runs migrations.
    """
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime

    from auto_invest.reports import health as _health

    if output_format not in ("text", "json"):
        typer.echo("--format must be 'text' or 'json'.", err=True)
        _exit(2)

    now = _datetime.now(_UTC)
    pid_path = db_path.parent / "auto_invest.pid"

    if not db_path.exists():
        report = _health.db_missing_report(now)
    else:
        conn = db.get_connection(db_path)
        try:
            report = _health.build_health_report(
                conn,
                pid_path=pid_path,
                halt_path=halt_path,
                now=now,
                stale_hours=stale_hours,
            )
        finally:
            conn.close()

    if output_format == "json":
        typer.echo(report.to_json())
    else:
        _icon = {"OK": "✓", "DEGRADED": "△", "CRITICAL": "✗"}
        typer.echo(f"auto-invest health — 종합 판정: {report.overall}")
        for c in report.checks:
            typer.echo(f"  {_icon.get(c.status, '?')} [{c.status}] {c.name}: {c.detail}")
        ctx = report.context
        if ctx:
            typer.echo("맥락:")
            typer.echo(f"  오늘 주문: {ctx.get('today_order_counts', {})}")
            typer.echo(f"  보유 종목 수: {ctx.get('position_count')}")
            if ctx.get("last_performance"):
                typer.echo(f"  마지막 성과: {ctx['last_performance']}")
            typer.echo(f"  마지막 튜너 실행: {ctx.get('last_tuner_run_utc')}")
            typer.echo(f"  마지막 캐너리 검증: {ctx.get('last_canary_validation_outcome')}")

    _exit(0 if report.overall == "OK" else 1)


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
    capital_tracking_enabled: bool = False,
    capital_growth_enabled: bool = False,
    capital_max_growth_factor: Decimal = Decimal("2"),
    backfill_enabled: bool = False,
    external_holdings: dict[str, int] | None = None,
) -> None:
    settings = WorkerSettings(
        config=cfg,
        db_path=db_path,
        halt_path=halt_path,
        config_path=config_path,
        total_capital_usd=total_capital_usd,
        require_session_open=require_session_open,
        capital_tracking_enabled=capital_tracking_enabled,
        capital_growth_enabled=capital_growth_enabled,
        capital_max_growth_factor=capital_max_growth_factor,
        backfill_enabled=backfill_enabled,
        external_holdings=external_holdings or {},
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


def _load_portfolio_for_backtest(
    path: Path, env: dict[str, str] | None = None
) -> tuple[object, object, object]:
    """Load a portfolio-backtest TOML: `[caps]`, `[whitelist]`, `[portfolio]`.

    Reuses the live SizingCaps / Whitelist parsing (single yardstick) and parses
    the `[portfolio]` table into a PortfolioRebalanceConfig (spec 032). The
    universe symbols MUST appear in `[whitelist].symbols` or their buys are
    rejected by the whitelist gate. Returns `(caps, whitelist, portfolio)`.

    When ``env`` is provided, ``${VAR}`` placeholders are expanded (same rule the
    live rules loader uses) — e.g. ``accounts = ["${KIS_ACCOUNT_NO}"]`` resolves to
    the real account so the router's order account matches the whitelist gate.
    """
    import tomllib

    from pydantic import ValidationError as _ValidationError

    from auto_invest.config.caps import SizingCaps
    from auto_invest.config.loader import _expand_env
    from auto_invest.config.rules import PortfolioRebalanceConfig
    from auto_invest.config.whitelist import Whitelist

    if not path.exists():
        raise ConfigError(f"portfolio file not found: {path}")
    try:
        raw = tomllib.loads(path.read_bytes().decode("utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"portfolio file is not valid TOML: {e}") from e
    if env is not None:
        raw = _expand_env(raw, env)
    try:
        caps = SizingCaps.model_validate(raw.get("caps", {}))
    except _ValidationError as e:
        raise ConfigError(f"[caps] section invalid: {e}") from e
    try:
        whitelist = Whitelist.model_validate(raw.get("whitelist", {}))
    except _ValidationError as e:
        raise ConfigError(f"[whitelist] section invalid: {e}") from e
    if "portfolio" not in raw:
        raise ConfigError("missing [portfolio] section")
    try:
        portfolio = PortfolioRebalanceConfig.model_validate(raw["portfolio"])
    except _ValidationError as e:
        raise ConfigError(f"[portfolio] section invalid: {e}") from e
    return caps, whitelist, portfolio


def _load_account_rebalance_settings(path: Path) -> tuple[bool, frozenset[str], Decimal]:
    """Load optional `[account_rebalance]` settings from a portfolio TOML."""
    import tomllib

    if not path.exists():
        raise ConfigError(f"portfolio file not found: {path}")
    try:
        raw = tomllib.loads(path.read_bytes().decode("utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"portfolio file is not valid TOML: {e}") from e

    table = raw.get("account_rebalance", {})
    enabled = bool(table.get("enabled", False))
    liquidation = frozenset(
        str(s).strip().upper() for s in table.get("liquidation_symbols", [])
    )
    cash_buffer_pct = Decimal(str(table.get("cash_buffer_pct", "0.01")))
    if cash_buffer_pct < 0:
        raise ConfigError("[account_rebalance].cash_buffer_pct must be non-negative")
    if any(not s for s in liquidation):
        raise ConfigError("[account_rebalance].liquidation_symbols contains an empty symbol")
    return enabled, liquidation, cash_buffer_pct


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
    commission_bps: float = typer.Option(
        None,
        "--commission-bps",
        help="Per-side commission in basis points (spec 016). Default: KIS US-equity (~25 bps).",
    ),
    slippage_bps: float = typer.Option(
        None,
        "--slippage-bps",
        help="Adverse slippage per fill in basis points (spec 016). Default: KIS (~5 bps).",
    ),
    min_commission_usd: float = typer.Option(
        None,
        "--min-commission-usd",
        help="Per-fill commission floor in USD (spec 016). Default: 0.",
    ),
) -> None:
    """Run a backtest against an ingested dataset (T026; contracts/backtest-cli.md)."""
    from datetime import date as _date
    from decimal import Decimal as _Decimal

    from auto_invest.backtest.costs import BacktestCostModel
    from auto_invest.backtest.data_source import CSVDataSource, latest_dataset_dir
    from auto_invest.backtest.run import (
        EXIT_COVERAGE,
        EXIT_OK,
        RunOptions,
        run_backtest,
    )

    _cost_base = BacktestCostModel.kis_default()
    cost_model = BacktestCostModel(
        commission_bps=(
            _Decimal(str(commission_bps))
            if commission_bps is not None
            else _cost_base.commission_bps
        ),
        slippage_bps=(
            _Decimal(str(slippage_bps))
            if slippage_bps is not None
            else _cost_base.slippage_bps
        ),
        min_commission_usd=(
            _Decimal(str(min_commission_usd))
            if min_commission_usd is not None
            else _cost_base.min_commission_usd
        ),
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
            cost_model=cost_model,
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


@app.command("bars-status")
def bars_status_cmd(
    portfolio: Path = typer.Option(
        None, "--portfolio", help="TOML; reports its [portfolio].universe symbols."
    ),
    symbols: str = typer.Option(
        None, "--symbols", help="Comma-separated symbols (overrides --portfolio)."
    ),
    timeframe: str = typer.Option("1d", "--timeframe", help="Bar timeframe to inspect."),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"), "--db", help="SQLite path with price_bars."
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of text."),
) -> None:
    """Read-only diagnostic: how many stored bars exist per symbol (+ date span).

    Answers "why did the paper rebalance place no trades?" — if a universe symbol
    holds fewer bars than the strategy's lookback/momentum window, the scorer
    returns no target weight for it and nothing trades. Pure read; no money, no
    writes, no migrations applied.
    """
    import json as _json

    from auto_invest.market_data.store import (
        available_timeframes,
        bar_summary,
        distinct_symbols,
    )

    syms: list[str] = []
    if symbols:
        syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    elif portfolio is not None:
        try:
            _caps, _wl, port_cfg = _load_portfolio_for_backtest(portfolio)
        except ConfigError as exc:
            typer.echo(f"portfolio validation failed: {exc}", err=True)
            _exit(65)
            return
        syms = list(port_cfg.universe)  # type: ignore[union-attr]
    else:
        typer.echo("provide --portfolio or --symbols", err=True)
        _exit(64)
        return

    if not db_path.exists():
        typer.echo(f"db not found: {db_path}", err=True)
        _exit(64)
        return

    conn = db.get_connection(db_path)
    rows = []
    try:
        for sym in syms:
            n, lo, hi = bar_summary(conn, symbol=sym, timeframe=timeframe)
            rows.append({"symbol": sym, "count": n, "earliest": lo, "latest": hi})
        # DB-wide availability — distinguishes "wrong timeframe/symbols" from
        # "empty table" when the requested universe has 0 bars.
        tfs = [{"timeframe": tf, "count": n} for tf, n in available_timeframes(conn)]
        sample_syms = distinct_symbols(conn, limit=20)
    finally:
        conn.close()

    if as_json:
        typer.echo(
            _json.dumps(
                {
                    "timeframe": timeframe,
                    "symbols": rows,
                    "db_timeframes": tfs,
                    "db_symbols_sample": sample_syms,
                }
            )
        )
        return
    typer.echo(f"stored bars (timeframe={timeframe}):")
    for r in rows:
        typer.echo(
            f"  {r['symbol']:8} count={r['count']:<6} "
            f"earliest={r['earliest'] or '-'}  latest={r['latest'] or '-'}"
        )
    typer.echo(f"DB timeframes present: {tfs or '(none)'}")
    typer.echo(f"DB symbols (sample): {sample_syms or '(none)'}")


@app.command("bars-export")
def bars_export_cmd(
    out_dir: Path = typer.Option(
        ...,
        "--out-dir",
        help="<SYMBOL>.csv 들을 쓸 디렉터리 (ingest-history --from-dir 입력 형식).",
    ),
    portfolio: Path = typer.Option(
        None, "--portfolio", help="TOML; exports its [portfolio].universe symbols."
    ),
    symbols: str = typer.Option(
        None, "--symbols", help="Comma-separated symbols (overrides --portfolio)."
    ),
    timeframe: str = typer.Option("1d", "--timeframe", help="Bar timeframe to export."),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"), "--db", help="SQLite path with price_bars."
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of text."),
) -> None:
    """저장된 일봉을 백테스트 데이터셋 CSV(ohlcv-csv.md 계약)로 내보낸다 — 읽기 전용.

    KIS 백필이 채운 인스턴스의 일봉(DB)을 ingest-history → backtest-portfolio 가
    소비할 수 있는 계약 형식으로 잇는 다리다. 그래야 *배포된 전략의* 일별 자본
    곡선을 인스턴스의 현재 데이터로 재생하고(단일 잣대), regime-stratify 로 "어떤
    거시 레짐에서 벌고 잃는가"를 잴 수 있다. DB 는 읽기만 한다(쓰기·마이그레이션
    0) — forward 전용 DB 에 안전. 값은 저장된 그대로 내보낸다(조용한 보정 없음;
    품질 검증은 ingest 가 한다). 일봉의 session_date 는 bar_open_utc 의 날짜다.

    Exit codes: 0 = 한 종목 이상 내보냄, 1 = 내보낸 종목 0, 64 = usage 오류.
    """
    import json as _json

    from auto_invest.market_data.store import get_bars

    syms: list[str] = []
    if symbols:
        syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    elif portfolio is not None:
        try:
            _caps, _wl, port_cfg = _load_portfolio_for_backtest(portfolio)
        except ConfigError as exc:
            typer.echo(f"portfolio validation failed: {exc}", err=True)
            _exit(65)
            return
        syms = list(port_cfg.universe)  # type: ignore[union-attr]
    else:
        typer.echo("provide --portfolio or --symbols", err=True)
        _exit(64)
        return

    if not db_path.exists():
        typer.echo(f"db not found: {db_path}", err=True)
        _exit(64)
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    conn = db.get_connection(db_path)
    exported: list[dict[str, object]] = []
    skipped: list[str] = []
    try:
        for sym in syms:
            bars = get_bars(conn, symbol=sym, timeframe=timeframe)
            if not bars:
                skipped.append(sym)
                continue
            lines = ["session_date,open,high,low,close,volume,session_schedule_tag\n"]
            for b in bars:
                session_date = b.bar_open_utc[:10]
                lines.append(
                    f"{session_date},{b.open_usd},{b.high_usd},{b.low_usd},"
                    f"{b.close_usd},{b.volume},regular\n"
                )
            (out_dir / f"{sym}.csv").write_text("".join(lines), encoding="utf-8")
            exported.append(
                {
                    "symbol": sym,
                    "rows": len(bars),
                    "first_date": bars[0].bar_open_utc[:10],
                    "last_date": bars[-1].bar_open_utc[:10],
                }
            )
    finally:
        conn.close()

    if as_json:
        typer.echo(
            _json.dumps(
                {
                    "timeframe": timeframe,
                    "out_dir": str(out_dir),
                    "exported": exported,
                    "skipped": skipped,
                }
            )
        )
    else:
        typer.echo(f"exported (timeframe={timeframe}) → {out_dir}:")
        for r in exported:
            typer.echo(
                f"  {r['symbol']:8} rows={r['rows']:<6} "
                f"{r['first_date']} → {r['last_date']}"
            )
        if skipped:
            typer.echo(f"skipped (0 bars): {', '.join(skipped)}")
    if not exported:
        typer.echo("no symbol had stored bars — nothing exported", err=True)
        _exit(1)


@app.command("backfill-bars")
def backfill_bars_cmd(
    portfolio: Path = typer.Option(
        None, "--portfolio", help="TOML; backfills its [portfolio].universe symbols."
    ),
    symbols: str = typer.Option(
        None, "--symbols", help="Comma-separated symbols (overrides --portfolio)."
    ),
    exchanges: str = typer.Option(
        "NAS,NYS,AMS",
        "--exchanges",
        help="KIS EXCD codes tried per symbol in order until one returns bars.",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"), "--db", help="SQLite path; bars go to price_bars."
    ),
    env_file: Path = typer.Option(
        None, "--env-file", help=".env with KIS_APP_KEY/KIS_APP_SECRET."
    ),
    base_url: str = typer.Option(
        "https://openapi.koreainvestment.com:9443", "--base-url", help="KIS REST base URL."
    ),
    max_symbols: int = typer.Option(
        0,
        "--max-symbols",
        help="스펙 041 — 매 실행 백필할 종목 수 상한(0=무제한). 대형 유니버스(S&P 500 등)"
        " 에서 워크플로 타임아웃을 피하려고 바가 가장 적은(needy-first) N개만 채운다. 여러"
        " 실행에 걸쳐 유니버스 전체가 고르게 채워진다.",
    ),
    min_bars: int = typer.Option(
        0,
        "--min-bars",
        help="스펙 041 — 종목당 확보할 최소 *최신* 일봉 수(0=한 페이지 ~100). KIS 기준일을"
        " 과거로 돌려 페이지네이션해 깊게 채운다. 6~12개월 모멘텀엔 ≥252 필요(예: 300).",
    ),
    order: str = typer.Option(
        "needy",
        "--order",
        help="스펙 041 — 백필 순서. needy=바 적은 것 먼저(breadth, 커버리지 확대). "
        "deepen=이미 바 있는 핵심 종목을 먼저 깊게(depth, IC 비겹침 시점↑ → 유의성↑).",
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of text."),
) -> None:
    """Fetch recent daily OHLCV bars from KIS into price_bars (read-only; no orders).

    The forward paper rebalancer scores from stored daily bars; a fresh instance has
    an empty price_bars table, so it can't trade. This backfills the universe's daily
    history via KIS 기간별시세 (a quotations endpoint — no order is ever placed, no
    money moves). Idempotent: existing (symbol, 1d, date) rows are kept (insert-or-skip).
    """
    import asyncio
    import json as _json

    from auto_invest.market_data.feed import backfill_daily_bars

    syms: list[str] = []
    if symbols:
        syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    elif portfolio is not None:
        try:
            _caps, _wl, port_cfg = _load_portfolio_for_backtest(portfolio)
        except ConfigError as exc:
            typer.echo(f"portfolio validation failed: {exc}", err=True)
            _exit(65)
            return
        syms = list(port_cfg.universe)  # type: ignore[union-attr]
    else:
        typer.echo("provide --portfolio or --symbols", err=True)
        _exit(64)
        return

    try:
        secrets = load_secrets(env_file)
    except ConfigError as exc:
        typer.echo(f"secrets error: {exc}", err=True)
        _exit(2)
        return
    app_key = secrets.get("KIS_APP_KEY")
    app_secret = secrets.get("KIS_APP_SECRET")
    if not app_key or not app_secret:
        typer.echo("KIS_APP_KEY/KIS_APP_SECRET required for backfill", err=True)
        _exit(2)
        return

    excds = [e.strip().upper() for e in exchanges.split(",") if e.strip()]
    _require_clean_migrations(db_path, allow_apply=True)

    # 스펙 041 — 백필 종목 선택/순서(needy=breadth, deepen=depth). 대형 유니버스에서 매 실행
    # 종목 수를 제한(타임아웃 회피)하고, deepen 은 이미 시드된 핵심을 깊게 파 IC 유의성을 올린다.
    if (max_symbols and max_symbols > 0 and len(syms) > max_symbols) or order == "deepen":
        from auto_invest.market_data import store as _store
        from auto_invest.market_data.feed import select_backfill_symbols

        _cnt_conn = db.get_connection(db_path)
        try:
            counts = _store.bar_counts(_cnt_conn, symbols=syms, timeframe="1d")
        finally:
            _cnt_conn.close()
        syms = select_backfill_symbols(
            syms, counts, max_symbols=max_symbols, min_bars=min_bars, order=order
        )

    async def _run() -> list[dict]:
        out: list[dict] = []
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
            conn = db.get_connection(db_path)
            try:
                out = await backfill_daily_bars(
                    conn,
                    client,
                    access_token=token.access_token,
                    app_key=app_key,
                    app_secret=app_secret,
                    symbols=syms,
                    exchanges=tuple(excds),
                    min_bars=min_bars,
                )
            finally:
                conn.close()
        return out

    results = asyncio.run(_run())

    if as_json:
        typer.echo(_json.dumps({"results": results}))
        return
    typer.echo("backfill daily bars -> price_bars:")
    for r in results:
        typer.echo(
            f"  {r['symbol']:8} exchange={r['exchange'] or '-':4} "
            f"fetched={r['fetched']:<5} inserted={r['inserted']}"
        )


@app.command("collect-public-data")
def collect_public_data_cmd(
    config: Path = typer.Option(
        Path("deploy/public-data.toml"),
        "--config",
        help="수집 대상(stooq 심볼·fred 시리즈·교차 검증 짝) TOML.",
    ),
    out_dir: Path = typer.Option(
        Path("public-data"),
        "--out-dir",
        help="검증 통과분 CSV + summary.json 발행 디렉터리.",
    ),
    as_json: bool = typer.Option(False, "--json", help="요약 JSON 만 출력."),
) -> None:
    """공개 소스(Stooq 일봉·FRED 거시) 수집 → 검증 → 통과분만 발행 (계획 ④).

    연구 전용 채널 — 라이브 매매 신호는 계속 KIS 데이터만 쓴다. 주문 0건,
    라이브 DB 무접촉. 항목 단위 fail-soft: 한 심볼의 실패는 그 심볼만 미발행.
    전 항목 실패(네트워크 전체 차단 등)일 때만 exit 1.
    """
    import json as _json
    import tomllib
    from datetime import date as _date

    from auto_invest.market_data.public_data import collect_public_data

    try:
        cfg = tomllib.loads(config.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        typer.echo(f"config error: {exc}", err=True)
        _exit(2)
        return

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        summary = collect_public_data(client, cfg, out_dir=out_dir, as_of=_date.today())

    if as_json:
        typer.echo(_json.dumps(summary, ensure_ascii=False))
    else:
        typer.echo(
            f"public data collect: published={summary['published']}/"
            f"{summary['total_items']} overall_ok={summary['overall_ok']}"
        )
        for item in summary["items"]:
            mark = "✓" if item.get("ok") else "✗"
            detail = item.get("published") or "; ".join(item.get("issues", []))[:120]
            typer.echo(f"  {mark} {item['kind']}:{item['id']:10} {detail}")
        cross = summary.get("cross_check")
        if cross:
            typer.echo(f"  교차 검증: {cross['status']} — {cross.get('detail', '')}")
    if summary["published"] == 0:
        _exit(1)


@app.command("macro-regime")
def macro_regime_cmd(
    data_dir: Path = typer.Option(
        Path("public-data"),
        "--data-dir",
        help="공개 데이터 채널 발행 디렉터리 (treasury/·cboe/·bls/ CSV).",
    ),
    out: Path | None = typer.Option(
        None, "--out", help="보고서 JSON 저장 경로 (생략 시 stdout 만)."
    ),
    timeline_out: Path | None = typer.Option(
        None,
        "--timeline-out",
        help="시점 기준 일별 레짐 이력 CSV 저장 경로 (층화 분석 입력).",
    ),
    as_json: bool = typer.Option(False, "--json", help="JSON 만 출력."),
) -> None:
    """거시 레짐 보고서 — 채널이 발행한 금리차·VIX·CPI·실업률 소비 (연구 전용).

    라이브 매매 신호 아님: 가격 레짐(strategy/regime.py, KIS 데이터)과 분리된
    연구 산출물. 지표 단위 fail-soft — 계산 가능 지표 0개일 때만 exit 1.
    """
    import json as _json
    from datetime import date as _date

    from auto_invest.market_data.macro_regime import (
        build_macro_regime_report,
        build_regime_timeline,
        report_to_json,
        timeline_to_csv,
    )

    report = build_macro_regime_report(data_dir, as_of=_date.today())
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report_to_json(report), encoding="utf-8")
    if timeline_out is not None:
        rows = build_regime_timeline(data_dir)
        timeline_out.parent.mkdir(parents=True, exist_ok=True)
        timeline_out.write_text(timeline_to_csv(rows), encoding="utf-8")
        typer.echo(f"timeline: {len(rows)}일 → {timeline_out}")

    if as_json:
        typer.echo(_json.dumps(report, ensure_ascii=False))
    else:
        overall = report["overall"]
        typer.echo(
            f"macro regime: {overall['label']} "
            f"(지표 {overall['available_indicators']}/{overall['total_indicators']}, "
            f"스트레스 깃발 {len(overall['stress_flags'])}개)"
        )
        for key, ind in report["indicators"].items():
            if ind["status"] == "OK":
                mark = "⚠" if ind.get("stress") else "✓"
                typer.echo(f"  {mark} {key}: {ind['state']}")
            else:
                typer.echo(f"  ? {key}: {ind['reason']}")
    if report["overall"]["available_indicators"] == 0:
        _exit(1)


@app.command("regime-stratify")
def regime_stratify_cmd(
    returns_csv: Path = typer.Option(
        ...,
        "--returns-csv",
        help="성과 시계열 CSV (date,value — NAV 또는 일일 수익률).",
    ),
    timeline_csv: Path = typer.Option(
        ...,
        "--timeline-csv",
        help="거시 레짐 타임라인 CSV (macro-regime --timeline-out 산출물).",
    ),
    kind: str = typer.Option(
        "nav", "--kind", help="returns-csv 해석: 'nav'(기본) 또는 'returns'(소수)."
    ),
    out: Path | None = typer.Option(None, "--out", help="결과 JSON 저장 경로."),
    as_json: bool = typer.Option(False, "--json", help="JSON 만 출력."),
) -> None:
    """레짐별 성과 층화 — d일 레짐 라벨에 d+1 거래일 수익률을 붙여 잰다 (연구 전용).

    "이 전략은 어떤 거시 레짐에서 벌고 어디서 잃는가"의 측정. 전망적 결합이라
    미래 누출이 없다. 라이브 매매 신호 아님.
    """
    import json as _json

    from auto_invest.analytics.regime_stratified import (
        load_timeline_csv,
        load_value_series_csv,
        nav_to_returns,
        stratify_returns,
    )

    try:
        series = load_value_series_csv(returns_csv.read_text(encoding="utf-8"))
        timeline = load_timeline_csv(timeline_csv.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        typer.echo(f"input error: {exc}", err=True)
        _exit(2)
        return
    if kind not in ("nav", "returns"):
        typer.echo(f"--kind 는 nav|returns (받음: {kind!r})", err=True)
        _exit(2)
        return
    returns = nav_to_returns(series) if kind == "nav" else series
    result = stratify_returns(returns, timeline)

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            _json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if as_json:
        typer.echo(_json.dumps(result, ensure_ascii=False))
    else:
        typer.echo(
            f"regime stratify: 수익률 {result['total_return_days']}일 — {result['join_rule']}"
        )
        for label, st in result["by_label"].items():
            line = (
                f"  {label:12} n={st['n_days']:5}  누적 {st.get('total_return_pct', '-'):>8}%"
            )
            if "sharpe" in st:
                line += f"  샤프 {st['sharpe']:>6}  최대낙폭 {st['max_drawdown_pct']}%"
            typer.echo(line)
    if result["total_return_days"] == 0:
        _exit(1)


@app.command("signal-ic")
def signal_ic_cmd(
    portfolio: Path = typer.Option(
        ..., "--portfolio", help="TOML; [portfolio].universe/weights/lookback 로 점수 재계산."
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"), "--db", help="SQLite; price_bars 에서 바를 읽는다."
    ),
    forward_horizon: int = typer.Option(
        21, "--forward-horizon", help="실현 수익률을 재는 앞쪽 거래일 수(21 ≈ 한 달)."
    ),
    momentum_gap_lag: int = typer.Option(
        21, "--momentum-gap-lag", help="momentum_gap 팩터의 최근 제외 바 수(12-1 의 '1', ~21≈한달)."
    ),
    step: int = typer.Option(
        0, "--step", help="평가 시점 간격(0=forward_horizon, 비겹침 → t-통계 과대평가 방지)."
    ),
    min_symbols: int = typer.Option(
        5, "--min-symbols", help="한 시점에서 IC를 재기 위한 최소 횡단면 종목 수."
    ),
    timeframe: str = typer.Option("1d", "--timeframe", help="바 타임프레임."),
    as_json: bool = typer.Option(False, "--json", help="JSON 출력."),
) -> None:
    """합성 점수의 예측 성공률(정보계수 IC)을 저장 바로 측정한다 (스펙 041, 주문 0건).

    운영자 지적("예측 성공률 기준으로 판단해야"): 점수로 순위를 매겨 사는데 그 점수가 *실제로*
    미래 수익을 예측하는지를 IC(점수 순위 vs 다음 기간 실현 수익률 순위의 스피어만 상관)로
    잰다. 평균 IC 가 양수+유의(t≥2)면 예측력 있음, 0 근처면 그 점수로 줄 세워 사는 건 엣지
    아님. 미래 누출 없음(t 시점 점수는 t까지의 바만 사용). 읽기 전용 — 돈 0 이동.
    """
    import json as _json

    from auto_invest.analytics.signal_ic import cross_sectional_ic
    from auto_invest.market_data.store import get_bars

    try:
        _caps, _wl, cfg = _load_portfolio_for_backtest(portfolio)
    except ConfigError as exc:
        typer.echo(f"portfolio validation failed: {exc}", err=True)
        _exit(65)
        return

    _require_clean_migrations(db_path, allow_apply=True)
    conn = db.get_connection(db_path)
    try:
        symbol_bars = {
            s: get_bars(conn, symbol=s, timeframe=timeframe)
            for s in cfg.universe  # type: ignore[union-attr]
        }
    finally:
        conn.close()

    result = cross_sectional_ic(
        symbol_bars,
        weights=cfg.weights,  # type: ignore[union-attr]
        lookback_bars=cfg.lookback_bars,  # type: ignore[union-attr]
        momentum_period=cfg.momentum_period,  # type: ignore[union-attr]
        momentum_gap_lag=momentum_gap_lag,
        forward_horizon=forward_horizon,
        step=(step or None),
        min_symbols=min_symbols,
    )

    if as_json:
        typer.echo(_json.dumps(result.as_dict()))
        return
    typer.echo("합성 점수 예측 성공률 (정보계수 IC):")
    typer.echo(f"  평균 IC          : {result.mean_ic:+.4f}")
    typer.echo(f"  IC 표준편차      : {result.ic_std:.4f}")
    typer.echo(f"  t-통계량         : {result.t_stat:+.2f}")
    typer.echo(f"  방향 적중률      : {result.hit_rate:.1%}")
    typer.echo(f"  측정 시점 수     : {result.n_dates}")
    typer.echo(f"  시점당 평균 종목 : {result.avg_symbols:.1f}")
    typer.echo(f"  forward 수평선   : {result.forward_horizon} 거래일")
    typer.echo(f"  판정             : {result.verdict}")


@app.command("build-universe")
def build_universe_cmd(
    top_n: int = typer.Option(
        100, "--top-n", help="Universe size: the N most liquid eligible symbols."
    ),
    min_history_bars: int = typer.Option(
        250,
        "--min-history-bars",
        help="Minimum bars a symbol must have to be eligible (so the alpha "
        "lookbacks can be computed).",
    ),
    min_dollar_volume: float = typer.Option(
        0.0,
        "--min-dollar-volume",
        help="Liquidity floor: median daily dollar volume (close × volume).",
    ),
    lookback_bars: int = typer.Option(
        60, "--lookback-bars", help="Window for the liquidity median."
    ),
    dataset_version: str = typer.Option(
        None, "--dataset-version", help="Specific dataset; default = most recent."
    ),
    history_root: Path = typer.Option(
        Path("data/history"), "--history-root", help="Parent of <dataset_version>/."
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of text."),
    emit_toml: bool = typer.Option(
        False,
        "--emit-toml",
        help="Print a ready-to-paste [portfolio] universe = [...] snippet.",
    ),
) -> None:
    """Construct a tradeable universe systematically (spec 034).

    World-class systematic equity does not hand-pick tickers; it *constructs* a
    universe from the investable cross-section, ranked by liquidity (median
    dollar volume) and filtered by sufficient price history. This reads an
    ingested dataset, ranks every symbol by liquidity, and prints the top-N
    eligible names — the breadth the cross-sectional alpha stack (spec 021/025/
    032) needs to actually express an edge. Offline, read-only, selection-only.
    """
    import json as _json
    from decimal import Decimal as _Decimal

    from auto_invest.backtest.data_source import CSVDataSource, latest_dataset_dir
    from auto_invest.market_data.store import PriceBar
    from auto_invest.strategy.universe import liquidity_rank, select_universe

    if dataset_version is not None:
        dataset_dir = history_root / dataset_version
        if not (dataset_dir / "manifest.json").exists():
            typer.echo(f"dataset_version {dataset_version!r} not found", err=True)
            _exit(64)
            return
    else:
        latest = latest_dataset_dir(history_root)
        if latest is None:
            typer.echo("no ingested datasets; run `auto-invest ingest-history`", err=True)
            _exit(64)
            return
        dataset_dir = latest

    data_source = CSVDataSource(dataset_dir)
    try:
        symbols = data_source.list_symbols()
        symbol_bars: dict[str, list[PriceBar]] = {}
        for sym in symbols:
            sessions = data_source.session_dates(sym)
            if not sessions:
                symbol_bars[sym] = []
                continue
            ohlcv = data_source.read_bars(sym, sessions[0], sessions[-1])
            symbol_bars[sym] = [
                PriceBar(
                    symbol=b.symbol,
                    timeframe="1d",
                    bar_open_utc=b.session_date.isoformat(),
                    open_usd=b.open,
                    high_usd=b.high,
                    low_usd=b.low,
                    close_usd=b.close,
                    volume=b.volume,
                )
                for b in ohlcv
            ]
        selected = select_universe(
            symbol_bars,
            top_n=top_n,
            min_dollar_volume=_Decimal(str(min_dollar_volume)),
            min_history_bars=min_history_bars,
            lookback_bars=lookback_bars,
        )
        ranked = liquidity_rank(symbol_bars, lookback_bars=lookback_bars)
        liq = {s: v for s, v in ranked}
        dataset_hex = data_source.dataset_version
    finally:
        data_source.close()

    if as_json:
        typer.echo(
            _json.dumps(
                {
                    "dataset_version": dataset_hex,
                    "candidates": len(symbol_bars),
                    "selected": selected,
                    "liquidity": {s: str(liq[s]) for s in selected},
                }
            )
        )
        return

    if emit_toml:
        names = ", ".join(f'"{s}"' for s in selected)
        typer.echo(f"universe = [{names}]")
        return

    typer.echo(
        f"constructed universe: {len(selected)} of {len(symbol_bars)} candidates "
        f"(top-{top_n} by median dollar volume, min_history={min_history_bars}, "
        f"min_dollar_volume={min_dollar_volume:g})"
    )
    for s in selected:
        typer.echo(f"  {s:8} median_dollar_volume={liq[s]}")


@app.command("portfolio-walk-forward")
def portfolio_walk_forward_cmd(
    portfolio: Path = typer.Option(
        ..., "--portfolio", help="TOML with [caps], [whitelist], [portfolio] (spec 032)."
    ),
    date_from: str = typer.Option(
        None, "--from", help="Inclusive start (YYYY-MM-DD). Omit to use --trailing-years."
    ),
    date_to: str = typer.Option(
        None, "--to", help="Inclusive end (YYYY-MM-DD). Omit to use the newest available bar."
    ),
    trailing_years: int = typer.Option(
        None,
        "--trailing-years",
        help="Evaluate only the most recent N years of available data (clear recency "
        "criterion: window = newest bar back N years). Overrides --from. Default: if "
        "neither --from nor this is given, uses the full dataset.",
    ),
    segment_days: int = typer.Option(
        365, "--segment-days", help="Length of each out-of-sample segment (calendar days)."
    ),
    lookback_buffer_days: int = typer.Option(
        160,
        "--lookback-buffer-days",
        help="Calendar days reserved before the first segment for signal lookback "
        "(no parameter is fit on it — a fixed rebalancing config has none).",
    ),
    mode: str = typer.Option("rolling", "--mode", help="'rolling' or 'anchored'."),
    num_trials: int = typer.Option(
        1,
        "--num-trials",
        help="How many DISTINCT configs were tried in the whole search. The "
        "deflated-Sharpe base: the more you tried, the more the selected config's "
        "Sharpe is discounted (multiple-testing correction). Be honest here.",
    ),
    dataset_version: str = typer.Option(
        None, "--dataset-version", help="Specific dataset; default = most recent."
    ),
    capital: float = typer.Option(100000.0, "--capital", help="Starting capital USD."),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"), "--db", help="SQLite audit-log path."
    ),
    halt_path: Path = typer.Option(
        Path("data/halt.flag"), "--halt-path", help="Halt-flag path."
    ),
    history_root: Path = typer.Option(
        Path("data/history"), "--history-root", help="Parent of <dataset_version>/."
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of text."),
    allow_stale: bool = typer.Option(
        False,
        "--allow-stale",
        help="Proceed even when the recency guard rates the data 'stale' (>2y old). "
        "Without this flag, stale data is REFUSED — old-data backtests must not be "
        "read as a verdict (doctrine: FORWARD-VALIDATION.md). Use only for an "
        "explicit limitation demo, never to justify a strategy.",
    ),
) -> None:
    """Out-of-sample, risk-adjusted, multiple-testing-corrected portfolio evaluation.

    The anti-overfitting counterpart to `backtest-portfolio`. Instead of one
    in-sample total-return-vs-buy-and-hold number (which a strong bull market makes
    misleading), this tiles the period into contiguous out-of-sample segments,
    compares the strategy to the naive buy-and-hold benchmark on Sharpe / drawdown
    per segment, and applies the deflated Sharpe ratio (spec 027) — discounting the
    selected config's Sharpe by how many configs were tried. The verdict only calls
    an edge "robust" if it wins a majority of segments AND beats the benchmark mean
    Sharpe AND survives the multiple-testing deflation. Offline, read-only.
    """
    import json as _json
    from datetime import date as _date
    from decimal import Decimal as _Decimal

    from auto_invest.backtest.data_source import CSVDataSource, latest_dataset_dir
    from auto_invest.backtest.portfolio_walk_forward import run_portfolio_walk_forward
    from auto_invest.backtest.recency import (
        assess_recency,
        stale_guard,
        trailing_window,
    )

    if mode not in ("rolling", "anchored"):
        typer.echo(f"--mode must be 'rolling' or 'anchored', got {mode!r}", err=True)
        _exit(64)
        return

    try:
        caps, whitelist, port_cfg = _load_portfolio_for_backtest(portfolio)
    except ConfigError as exc:
        typer.echo(f"portfolio validation failed: {exc}", err=True)
        _exit(65)
        return

    if dataset_version is not None:
        dataset_dir = history_root / dataset_version
        if not (dataset_dir / "manifest.json").exists():
            typer.echo(f"dataset_version {dataset_version!r} not found", err=True)
            _exit(64)
            return
    else:
        latest = latest_dataset_dir(history_root)
        if latest is None:
            typer.echo("no ingested datasets; run `auto-invest ingest-history`", err=True)
            _exit(64)
            return
        dataset_dir = latest

    data_source = CSVDataSource(dataset_dir)

    # Resolve the evaluation window. Recency criterion (operator principle): prefer a
    # clear trailing window over an arbitrary range, and ALWAYS surface data freshness.
    recency = assess_recency(data_source, port_cfg.universe)  # type: ignore[union-attr]
    _refusal = stale_guard(recency, allow_stale=allow_stale)
    if _refusal is not None:
        typer.echo(_refusal, err=True)
        data_source.close()
        _exit(70)
        return
    try:
        if trailing_years is not None:
            window = trailing_window(
                data_source, port_cfg.universe, trailing_years=trailing_years  # type: ignore[union-attr]
            )
            if window is None:
                typer.echo("dataset has no sessions for the portfolio universe", err=True)
                data_source.close()
                _exit(64)
                return
            ds_start, ds_end = window
        else:
            if date_from is None or date_to is None:
                typer.echo(
                    "provide --from and --to, or --trailing-years N (clear recency window)",
                    err=True,
                )
                data_source.close()
                _exit(64)
                return
            ds_start = _date.fromisoformat(date_from)
            ds_end = _date.fromisoformat(date_to)
    except ValueError as exc:
        typer.echo(f"date parsing failed: {exc}", err=True)
        data_source.close()
        _exit(64)
        return
    if ds_end < ds_start:
        typer.echo(f"--to ({ds_end}) is before --from ({ds_start})", err=True)
        data_source.close()
        _exit(64)
        return

    if recency is not None and not as_json:
        typer.echo(recency.banner())
        typer.echo(f"evaluation window: {ds_start} → {ds_end}")

    _require_clean_migrations(db_path, allow_apply=True)
    conn = db.get_connection(db_path)
    try:
        report = run_portfolio_walk_forward(
            config=port_cfg,  # type: ignore[arg-type]
            data_source=data_source,
            date_start=ds_start,
            date_end=ds_end,
            caps=caps,  # type: ignore[arg-type]
            whitelist=whitelist,  # type: ignore[arg-type]
            halt_path=halt_path,
            conn=conn,
            lookback_buffer_days=lookback_buffer_days,
            segment_days=segment_days,
            mode=mode,
            total_capital_usd=_Decimal(str(capital)),
            num_trials=num_trials,
        )
    except Exception as exc:  # WalkForwardError etc — surface as usage error
        typer.echo(f"walk-forward failed: {exc}", err=True)
        conn.close()
        data_source.close()
        _exit(64)
        return
    conn.close()
    data_source.close()

    if as_json:
        typer.echo(
            _json.dumps(
                {
                    "dataset_version": data_source.dataset_version,
                    "data_newest_session": (
                        recency.newest_session.isoformat() if recency else None
                    ),
                    "data_age_days": recency.age_days if recency else None,
                    "data_staleness": recency.staleness if recency else None,
                    "eval_window": [ds_start.isoformat(), ds_end.isoformat()],
                    "n_segments": report.n_segments,
                    "segments_strategy_wins": report.segments_strategy_wins,
                    "mean_strategy_sharpe": str(report.mean_strategy_sharpe),
                    "mean_benchmark_sharpe": str(report.mean_benchmark_sharpe),
                    "pooled_strategy_sharpe_annual": str(report.pooled_strategy_sharpe_annual),
                    "num_trials": report.num_trials,
                    "strategy_psr": str(report.strategy_psr),
                    "strategy_dsr": str(report.strategy_dsr),
                    "verdict": report.verdict,
                }
            )
        )
        return

    typer.echo(f"dataset_version: {data_source.dataset_version}")
    typer.echo(
        f"out-of-sample segments: {report.n_segments}  "
        f"risk-adjusted wins vs buy-and-hold: {report.segments_strategy_wins}/{report.n_segments}"
    )
    for s in report.segments:
        mark = "win " if s.strategy_beats_benchmark else "LOSE"
        typer.echo(
            f"  seg{s.index} {s.start}→{s.end} ({s.n_sessions}d) [{mark}] "
            f"sharpe {s.strategy_sharpe} vs {s.benchmark_sharpe}  "
            f"ret {s.strategy_return_pct}% vs {s.benchmark_return_pct}%  "
            f"maxDD {s.strategy_maxdd_pct}% vs {s.benchmark_maxdd_pct}%"
        )
    typer.echo(
        f"mean Sharpe: strategy {report.mean_strategy_sharpe} vs "
        f"buy-and-hold {report.mean_benchmark_sharpe}"
    )
    typer.echo(
        f"pooled OOS: {report.pooled_obs} sessions, annual Sharpe "
        f"{report.pooled_strategy_sharpe_annual}"
    )
    typer.echo(
        f"PSR (1 trial): {report.strategy_psr}   "
        f"DSR (deflated for {report.num_trials} trials): {report.strategy_dsr}"
    )
    typer.echo(f"verdict: {report.verdict}")


@app.command("backtest-portfolio")
def backtest_portfolio_cmd(
    portfolio: Path = typer.Option(
        ...,
        "--portfolio",
        help="TOML with [caps], [whitelist], [portfolio] sections (spec 032).",
    ),
    date_from: str = typer.Option(
        ..., "--from", help="Inclusive session-date start (YYYY-MM-DD)."
    ),
    date_to: str = typer.Option(
        ..., "--to", help="Inclusive session-date end (YYYY-MM-DD)."
    ),
    dataset_version: str = typer.Option(
        None,
        "--dataset-version",
        help="Specific dataset_version; defaults to most recent under data/history/.",
    ),
    capital: float = typer.Option(
        100000.0, "--capital", help="Starting capital in USD."
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"), "--db", help="SQLite audit-log path."
    ),
    halt_path: Path = typer.Option(
        Path("data/halt.flag"), "--halt-path", help="Filesystem halt-flag path."
    ),
    history_root: Path = typer.Option(
        Path("data/history"),
        "--history-root",
        help="Where ingested datasets live (parent of <dataset_version>/).",
    ),
    commission_bps: float = typer.Option(
        None, "--commission-bps", help="Per-side commission bps. Default: KIS (~25)."
    ),
    slippage_bps: float = typer.Option(
        None, "--slippage-bps", help="Adverse slippage bps per fill. Default: KIS (~5)."
    ),
    min_commission_usd: float = typer.Option(
        None, "--min-commission-usd", help="Per-fill commission floor USD. Default: 0."
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Emit a single JSON object instead of text."
    ),
    equity_out: Path = typer.Option(
        None,
        "--equity-out",
        help="일별 시가평가 자본 곡선을 date,value CSV 로 저장 — regime-stratify 의 "
        "--returns-csv 입력 형식 그대로 (레짐 층화의 소비처). 미지정 시 미저장.",
    ),
    allow_stale: bool = typer.Option(
        False,
        "--allow-stale",
        help="Proceed even when the recency guard rates the data 'stale' (>2y old). "
        "Without this flag, stale data is REFUSED — old-data backtests must not be "
        "read as a verdict (doctrine: FORWARD-VALIDATION.md). Use only for an "
        "explicit limitation demo, never to justify a strategy.",
    ),
) -> None:
    """Backtest the cross-sectional rebalancing portfolio engine (spec 032).

    Scores the universe each rebalance, builds target weights, and routes the
    BUY+SELL rebalance through the SAME K1 gate chain as the live router — then
    reports the single-yardstick metrics (return / drawdown / Sharpe / Sortino)
    plus turnover, so the rebalancing engine's profile is measurable BEFORE any
    money moves. Backtest-only: no live broker, no live-worker change.
    """
    import json as _json
    import uuid as _uuid
    from datetime import UTC
    from datetime import date as _date
    from datetime import datetime as _datetime
    from decimal import Decimal as _Decimal

    from auto_invest.backtest.broker_mock import BacktestBroker
    from auto_invest.backtest.clock import ReplayClock
    from auto_invest.backtest.costs import BacktestCostModel
    from auto_invest.backtest.data_source import CSVDataSource, latest_dataset_dir
    from auto_invest.backtest.portfolio_replay import replay_portfolio
    from auto_invest.backtest.recency import assess_recency, stale_guard

    _cost_base = BacktestCostModel.kis_default()
    cost_model = BacktestCostModel(
        commission_bps=(
            _Decimal(str(commission_bps))
            if commission_bps is not None
            else _cost_base.commission_bps
        ),
        slippage_bps=(
            _Decimal(str(slippage_bps))
            if slippage_bps is not None
            else _cost_base.slippage_bps
        ),
        min_commission_usd=(
            _Decimal(str(min_commission_usd))
            if min_commission_usd is not None
            else _cost_base.min_commission_usd
        ),
    )

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

    try:
        caps, whitelist, port_cfg = _load_portfolio_for_backtest(portfolio)
    except ConfigError as exc:
        typer.echo(f"portfolio validation failed: {exc}", err=True)
        _exit(65)
        return

    if dataset_version is not None:
        dataset_dir = history_root / dataset_version
        if not (dataset_dir / "manifest.json").exists():
            typer.echo(
                f"dataset_version {dataset_version!r} not found under {history_root}",
                err=True,
            )
            _exit(64)
            return
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

    data_source = CSVDataSource(dataset_dir)

    # Recency guard (doctrine: FORWARD-VALIDATION.md). Stale data must not be read
    # as a verdict; refuse unless the caller explicitly opts into a limitation demo.
    recency = assess_recency(data_source, port_cfg.universe)  # type: ignore[union-attr]
    _refusal = stale_guard(recency, allow_stale=allow_stale)
    if _refusal is not None:
        typer.echo(_refusal, err=True)
        data_source.close()
        _exit(70)
        return

    _require_clean_migrations(db_path, allow_apply=True)
    conn = db.get_connection(db_path)
    run_id = f"bt-port-{_uuid.uuid4().hex[:12]}"
    try:
        result = replay_portfolio(
            config=port_cfg,  # type: ignore[arg-type]
            data_source=data_source,
            date_start=ds_start,
            date_end=ds_end,
            caps=caps,  # type: ignore[arg-type]
            whitelist=whitelist,  # type: ignore[arg-type]
            halt_path=halt_path,
            conn=conn,
            clock=ReplayClock(_datetime(ds_start.year - 1, 1, 1, tzinfo=UTC)),
            broker=BacktestBroker(),
            run_id=run_id,
            total_capital_usd=_Decimal(str(capital)),
            cost_model=cost_model,
        )
    finally:
        conn.close()
        data_source.close()

    if equity_out is not None:
        equity_out.parent.mkdir(parents=True, exist_ok=True)
        equity_out.write_text(
            "date,value\n"
            + "".join(f"{d.isoformat()},{eq}\n" for d, eq in result.equity_curve),
            encoding="utf-8",
        )

    if as_json:
        typer.echo(
            _json.dumps(
                {
                    "run_id": run_id,
                    "dataset_version": data_source.dataset_version,
                    "date_start": ds_start.isoformat(),
                    "date_end": ds_end.isoformat(),
                    "portfolio_id": port_cfg.id,  # type: ignore[attr-defined]
                    "weight_scheme": port_cfg.weight_scheme,  # type: ignore[attr-defined]
                    "rebalances": len(result.rebalance_dates),
                    "orders": len(result.orders),
                    "fills": len(result.fills),
                    "gate_rejections": len(result.gate_rejections),
                    "total_return_pct": str(result.total_return_pct),
                    "max_drawdown_pct": str(result.max_drawdown_pct),
                    "sharpe_ratio": str(result.sharpe_ratio),
                    "sortino_ratio": str(result.sortino_ratio),
                    "turnover_ratio": str(result.turnover_ratio),
                    "commission_usd": str(result.commission_usd),
                    "final_equity_usd": str(result.final_equity_usd),
                    "benchmark_total_return_pct": str(result.benchmark_total_return_pct),
                    "benchmark_max_drawdown_pct": str(result.benchmark_max_drawdown_pct),
                    "benchmark_sharpe_ratio": str(result.benchmark_sharpe_ratio),
                    "excess_return_pct": str(result.excess_return_pct),
                }
            )
        )
        return

    typer.echo(f"portfolio backtest run_id: {run_id}")
    typer.echo(f"dataset_version: {data_source.dataset_version}")
    typer.echo(f"date range:      {ds_start} → {ds_end}")
    typer.echo(
        f"portfolio:       {port_cfg.id}  scheme={port_cfg.weight_scheme}  "  # type: ignore[attr-defined]
        f"top_n={port_cfg.top_n} top_pct={port_cfg.top_pct}"  # type: ignore[attr-defined]
    )
    typer.echo(f"cost model:      {cost_model.describe()}")
    typer.echo("")
    typer.echo(f"rebalances:      {len(result.rebalance_dates)}")
    typer.echo(
        f"orders/fills/rej:{len(result.orders)} / {len(result.fills)} / "
        f"{len(result.gate_rejections)}"
    )
    typer.echo(f"total return %:  {result.total_return_pct}")
    typer.echo(f"max drawdown %:  {result.max_drawdown_pct}")
    typer.echo(f"sharpe:          {result.sharpe_ratio}")
    typer.echo(f"sortino:         {result.sortino_ratio}")
    typer.echo(f"turnover ratio:  {result.turnover_ratio}")
    typer.echo(f"commission USD:  {result.commission_usd}")
    typer.echo(f"final equity:    {result.final_equity_usd}")
    typer.echo("")
    typer.echo("─ vs 단순 보유(균등가중 매수후보유) 벤치마크 ─")
    typer.echo(f"benchmark return %: {result.benchmark_total_return_pct}")
    typer.echo(f"benchmark maxDD %:  {result.benchmark_max_drawdown_pct}")
    typer.echo(f"benchmark sharpe:   {result.benchmark_sharpe_ratio}")
    typer.echo(f"EXCESS return %:    {result.excess_return_pct}  (전략 − 벤치마크)")


@app.command("rebalance-once")
def rebalance_once_cmd(
    portfolio: Path = typer.Option(
        ...,
        "--portfolio",
        help="TOML with [caps], [whitelist], [portfolio] sections (spec 032).",
    ),
    mode: str = typer.Option(
        "paper",
        "--mode",
        help="'paper' (default, simulated fills) or 'live' (REAL orders — money moves).",
    ),
    capital: float = typer.Option(
        ..., "--capital", help="Total capital in USD for weight sizing + caps."
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"), "--db", help="SQLite path (bars, positions, audit)."
    ),
    halt_path: Path = typer.Option(
        Path("data/halt.flag"), "--halt-path", help="Filesystem halt-flag path."
    ),
    env_file: Path | None = typer.Option(
        None, "--env-file", help="Optional .env with KIS_APP_KEY/SECRET/ACCOUNT_NO."
    ),
    base_url: str = typer.Option(
        "https://openapi.koreainvestment.com:9443", "--base-url", help="KIS REST base URL."
    ),
    timeframe: str = typer.Option(
        "1d", "--timeframe", help="Bar timeframe for scoring (matches stored bars)."
    ),
    construct_universe_top_n: int = typer.Option(
        0,
        "--construct-universe-top-n",
        help="Spec 034: instead of trading the hand-listed [portfolio].universe, "
        "CONSTRUCT the universe from the CURRENT stored bars — keep the N most "
        "liquid (median dollar volume) eligible names. 0 (default) = off, use the "
        "configured universe unchanged. The constructed set is always a subset of "
        "the configured universe (so it stays within the whitelist). Pair with a "
        "broad backfilled candidate universe to get real cross-sectional breadth.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview the plan WITHOUT placing orders. Normally offline; with "
        "--account-wide it may perform read-only KIS position/cash calls.",
    ),
    account_wide: bool = typer.Option(
        False,
        "--account-wide",
        help="Plan from latest broker positions and purchasable cash. Requires "
        "[account_rebalance].enabled=true in the portfolio file.",
    ),
    side: str = typer.Option(
        "both",
        "--side",
        help="Order side mode: both, sell, or buy. Cash shortfall may narrow both to sell.",
    ),
    confirm_live: bool = typer.Option(
        False,
        "--confirm-live",
        help="Required acknowledgement for '--mode live': without it a live run is "
        "refused. A safety interlock against accidental real orders.",
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit a single JSON object."),
) -> None:
    """Run ONE cross-sectional rebalance against the live/paper account (spec 032 slice 2).

    Scores the universe from stored bars, builds target weights, diffs against
    current holdings, and routes the BUY+SELL rebalance through the SAME K1 gate
    chain as the live worker (via filter-free synthetic rules). Defaults to
    PAPER (simulated fills, no money). `--mode live` places REAL orders and
    REQUIRES `--confirm-live`. `--dry-run` previews the plan offline with no
    orders and no KIS contact. Each order is clamped down to the per-trade cap, so
    a large rebalance converges over repeated runs.
    """
    import json as _json
    from datetime import UTC
    from datetime import datetime as _datetime
    from decimal import Decimal as _Decimal

    from auto_invest.broker.models import Quote
    from auto_invest.broker.overseas import (
        get_positions_resolving_market,
        get_purchasable_cash_usd,
        get_quote_resolving_market,
    )
    from auto_invest.config.enums import StrategyStage
    from auto_invest.execution.order_router import OrderRouter
    from auto_invest.execution.rebalancer import execute_rebalance
    from auto_invest.market_data.store import get_latest_bar

    if mode not in ("paper", "live"):
        typer.echo(f"--mode must be 'paper' or 'live', got {mode!r}", err=True)
        _exit(64)
    side = side.lower().strip()
    if side not in ("both", "sell", "buy"):
        typer.echo(f"--side must be one of both, sell, buy; got {side!r}", err=True)
        _exit(64)

    # Expand ${KIS_ACCOUNT_NO} (and any ${VAR}) in the portfolio whitelist using the
    # real secrets, so the router's order account matches the whitelist gate. Offline
    # dry-run may have no secrets — expansion is skipped then (dry-run routes nothing).
    _pf_env: dict[str, str] | None = None
    try:
        _pf_env = load_secrets(env_file)
    except ConfigError:
        _pf_env = None
    try:
        caps, whitelist, port_cfg = _load_portfolio_for_backtest(portfolio, env=_pf_env)
        account_enabled, liquidation_symbols, cash_buffer_pct = (
            _load_account_rebalance_settings(portfolio)
        )
    except ConfigError as exc:
        typer.echo(f"portfolio validation failed: {exc}", err=True)
        _exit(65)
        return

    # Safety: every universe symbol MUST be on the whitelist, else its buys would
    # be rejected at the gate — surface that BEFORE contacting the broker.
    missing = [s for s in port_cfg.universe if s not in whitelist.symbols]
    if missing:
        typer.echo(
            f"universe symbols not on the whitelist: {missing} — add them to "
            "[whitelist].symbols or they will be gate-rejected.",
            err=True,
        )
        _exit(65)

    if account_wide:
        if not account_enabled:
            typer.echo(
                "--account-wide requires [account_rebalance].enabled=true in the portfolio",
                err=True,
            )
            _exit(65)
        overlap = sorted(set(port_cfg.universe) & set(liquidation_symbols))
        if overlap:
            typer.echo(
                "account_rebalance liquidation symbols overlap target universe: "
                f"{overlap}",
                err=True,
            )
            _exit(65)
        missing_liquidation = sorted(set(liquidation_symbols) - set(whitelist.symbols))
        if missing_liquidation:
            typer.echo(
                "liquidation-only symbols not on the whitelist for sell routing: "
                f"{missing_liquidation}",
                err=True,
            )
            _exit(65)

    # Live safety interlock: real orders require an explicit acknowledgement.
    if mode == "live" and not dry_run and not confirm_live:
        typer.echo(
            "REFUSED: --mode live places REAL orders (money moves). Re-run with "
            "--confirm-live to acknowledge, or use --dry-run to preview safely.",
            err=True,
        )
        _exit(64)

    _require_clean_migrations(db_path, allow_apply=True)

    # Spec 034: optionally CONSTRUCT the universe from the current stored bars by
    # liquidity, instead of trading the hand-listed universe. The constructed set is
    # always a subset of the configured (whitelist-checked) universe, so this can
    # only NARROW the trading set — never widen it past the whitelist (principle II).
    if construct_universe_top_n > 0:
        from auto_invest.market_data.store import get_bars as _get_bars
        from auto_invest.strategy.universe import select_universe as _select_universe

        _conn_u = db.get_connection(db_path)
        try:
            _cand_bars = {
                s: _get_bars(_conn_u, symbol=s, timeframe=timeframe)
                for s in port_cfg.universe
            }
        finally:
            _conn_u.close()
        _constructed = _select_universe(
            _cand_bars,
            top_n=construct_universe_top_n,
            min_history_bars=port_cfg.lookback_bars,
            lookback_bars=port_cfg.lookback_bars,
        )
        if len(_constructed) < 2:
            typer.echo(
                "construct-universe: 현재 저장 바로 적격 종목이 2개 미만 "
                f"({len(_constructed)}) — 백필이 충분한지 확인하세요. 설정된 유니버스 "
                "무변경으로 진행합니다.",
                err=True,
            )
        else:
            port_cfg = port_cfg.model_copy(update={"universe": tuple(_constructed)})
            if not as_json:
                typer.echo(
                    f"construct-universe: {len(_constructed)}/{len(_cand_bars)} 종목을 "
                    f"유동성 상위로 구성 → {list(_constructed)}"
                )

    total_capital = _Decimal(str(capital))

    async def _go_dry() -> object:
        # Offline preview: no secrets, no KIS. Prices from the latest stored bars;
        # a throwaway paper router is built but NEVER called (dry_run routes nothing).
        conn = db.get_connection(db_path)
        async with httpx.AsyncClient(base_url="http://dry-run") as inner:
            broker = ResilientClient(
                inner,
                rate_limiter=AsyncTokenBucket(rate_per_sec=100.0, capacity=10.0),
                breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0),
                max_retries=1,
            )
            router = OrderRouter(
                conn=conn,
                broker=broker,
                access_token="dry-run",
                app_key="dry-run",
                app_secret="dry-run",
                account_no="DRY-RUN",
                whitelist=whitelist,  # type: ignore[arg-type]
                caps=caps,  # type: ignore[arg-type]
                halt_path=halt_path,
                paper_mode=True,
            )

            async def _bar_quote(symbol: str) -> Quote:
                bar = get_latest_bar(conn, symbol=symbol, timeframe=timeframe)
                if bar is None:
                    raise ValueError(f"no stored bar for {symbol}")
                return Quote(
                    symbol=symbol,
                    last_price_usd=bar.close_usd,
                    bid_usd=bar.close_usd,
                    ask_usd=bar.close_usd,
                    quoted_at_utc=_datetime.now(UTC),
                )

            try:
                return await execute_rebalance(
                    config=port_cfg,  # type: ignore[arg-type]
                    router=router,
                    conn=conn,
                    quote_provider=_bar_quote,
                    total_capital_usd=total_capital,
                    caps=caps,  # type: ignore[arg-type]
                    timeframe=timeframe,
                    stage=StrategyStage.CANARY,
                    dry_run=True,
                    execution_side=side,
                )
            finally:
                conn.close()

    async def _go() -> object:
        try:
            secrets = load_secrets(env_file)
        except ConfigError as exc:
            typer.echo(f"secrets error: {exc}", err=True)
            raise
        conn = db.get_connection(db_path)
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
            router = OrderRouter(
                conn=conn,
                broker=broker,
                access_token=token.access_token,
                app_key=secrets["KIS_APP_KEY"],
                app_secret=secrets["KIS_APP_SECRET"],
                account_no=secrets["KIS_ACCOUNT_NO"],
                whitelist=whitelist,  # type: ignore[arg-type]
                caps=caps,  # type: ignore[arg-type]
                halt_path=halt_path,
                paper_mode=(mode == "paper"),
            )

            async def _quote_provider(symbol: str):
                # 거래소 자동 해석(NAS→NYS→AMS): SPY·GLD 는 AMS 상장이라 고정 NAS 로는 빈
                # 값으로 실패한다. 이게 글로벌 분산 추세 포트폴리오가 forward NAV 를 못 쌓던 원인.
                return await get_quote_resolving_market(
                    broker,
                    access_token=token.access_token,
                    app_key=secrets["KIS_APP_KEY"],
                    app_secret=secrets["KIS_APP_SECRET"],
                    symbol=symbol,
                )

            try:
                broker_holdings: dict[str, int] | None = None
                purchasable_cash: _Decimal | None = None
                if account_wide:
                    positions = await get_positions_resolving_market(
                        broker,
                        access_token=token.access_token,
                        app_key=secrets["KIS_APP_KEY"],
                        app_secret=secrets["KIS_APP_SECRET"],
                        account=secrets["KIS_ACCOUNT_NO"],
                    )
                    broker_holdings = {p.symbol: p.qty for p in positions if p.qty > 0}
                    purchasable_cash = await get_purchasable_cash_usd(
                        broker,
                        access_token=token.access_token,
                        app_key=secrets["KIS_APP_KEY"],
                        app_secret=secrets["KIS_APP_SECRET"],
                        account=secrets["KIS_ACCOUNT_NO"],
                    )
                return await execute_rebalance(
                    config=port_cfg,  # type: ignore[arg-type]
                    router=router,
                    conn=conn,
                    quote_provider=_quote_provider,
                    total_capital_usd=total_capital,
                    caps=caps,  # type: ignore[arg-type]
                    timeframe=timeframe,
                    stage=StrategyStage.CANARY,
                    dry_run=dry_run,
                    account_holdings=broker_holdings,
                    liquidation_only_symbols=(
                        liquidation_symbols if account_wide else frozenset()
                    ),
                    execution_side=side,
                    purchasable_cash_usd=purchasable_cash,
                    cash_buffer_pct=cash_buffer_pct,
                )
            finally:
                conn.close()

    outcome = asyncio.run(_go() if account_wide or not dry_run else _go_dry())
    mode_label = "dry-run" if dry_run else mode

    if as_json:
        typer.echo(
            _json.dumps(
                {
                    "portfolio_id": outcome.portfolio_id,  # type: ignore[attr-defined]
                    "mode": mode_label,
                    "account_wide": outcome.account_wide,  # type: ignore[attr-defined]
                    "requested_side": outcome.requested_side,  # type: ignore[attr-defined]
                    "effective_side": outcome.effective_side,  # type: ignore[attr-defined]
                    "purchasable_cash_usd": (
                        str(outcome.purchasable_cash_usd)  # type: ignore[attr-defined]
                        if outcome.purchasable_cash_usd is not None  # type: ignore[attr-defined]
                        else None
                    ),
                    "required_cash_usd": (
                        str(outcome.required_cash_usd)  # type: ignore[attr-defined]
                        if outcome.required_cash_usd is not None  # type: ignore[attr-defined]
                        else None
                    ),
                    "planned_buy_notional_usd": str(
                        outcome.planned_buy_notional_usd  # type: ignore[attr-defined]
                    ),
                    "planned_sell_notional_usd": str(
                        outcome.planned_sell_notional_usd  # type: ignore[attr-defined]
                    ),
                    "target_weights": {
                        s: str(w) for s, w in outcome.target_weights.items()  # type: ignore[attr-defined]
                    },
                    "results": [
                        {
                            "symbol": r.symbol,
                            "side": r.side,
                            "requested_qty": r.requested_qty,
                            "routed_qty": r.routed_qty,
                            "limit_price_usd": str(r.limit_price_usd),
                            "state": r.state,
                            "reason": r.reason,
                        }
                        for r in outcome.results  # type: ignore[attr-defined]
                    ],
                    "withheld_orders": [
                        {
                            "symbol": w.symbol,
                            "side": w.side,
                            "requested_qty": w.requested_qty,
                            "reason": w.reason,
                        }
                        for w in outcome.withheld  # type: ignore[attr-defined]
                    ],
                }
            )
        )
        return

    typer.echo(f"rebalance {outcome.portfolio_id}  mode={mode_label}")  # type: ignore[attr-defined]
    typer.echo(
        "account_wide="
        f"{outcome.account_wide} side={outcome.requested_side}->{outcome.effective_side}"  # type: ignore[attr-defined]
    )
    if outcome.purchasable_cash_usd is not None:  # type: ignore[attr-defined]
        typer.echo(
            "cash: purchasable="
            f"{outcome.purchasable_cash_usd} required={outcome.required_cash_usd}"  # type: ignore[attr-defined]
        )
    typer.echo(
        "target weights: "
        + ", ".join(
            f"{s}={w}" for s, w in sorted(outcome.target_weights.items())  # type: ignore[attr-defined]
        )
    )
    typer.echo("")
    for r in outcome.results:  # type: ignore[attr-defined]
        typer.echo(
            f"  {r.side:4} {r.symbol:6} req={r.requested_qty} routed={r.routed_qty} "
            f"@~{r.limit_price_usd}  -> {r.state}"
            + (f" ({r.reason})" if r.reason else "")
        )
    if outcome.withheld:  # type: ignore[attr-defined]
        typer.echo("")
        typer.echo("withheld:")
        for w in outcome.withheld:  # type: ignore[attr-defined]
            typer.echo(
                f"  {w.side:4} {w.symbol:6} req={w.requested_qty} -> WITHHELD "
                f"({w.reason})"
            )


@app.command("walk-forward")
def walk_forward_cmd(
    rules: Path = typer.Option(
        ..., "--rules", help="Path to rules TOML (same format as the live worker)."
    ),
    date_from: str = typer.Option(
        ..., "--from", help="Inclusive session-date start (YYYY-MM-DD)."
    ),
    date_to: str = typer.Option(..., "--to", help="Inclusive session-date end (YYYY-MM-DD)."),
    in_sample_days: int = typer.Option(
        ..., "--in-sample-days", help="In-sample (fit) window length in calendar days."
    ),
    out_of_sample_days: int = typer.Option(
        ..., "--out-of-sample-days", help="Out-of-sample (test) window length in calendar days."
    ),
    step_days: int = typer.Option(
        None,
        "--step-days",
        help="Advance between windows (default = out-of-sample-days for contiguous OOS).",
    ),
    mode: str = typer.Option(
        "rolling", "--mode", help="rolling (sliding fixed IS) or anchored (expanding IS)."
    ),
    wfe_threshold: float = typer.Option(
        0.5,
        "--wfe-threshold",
        help="Mean WFE below this flags overfitting (OOS sharpe / IS sharpe).",
    ),
    num_trials: int = typer.Option(
        1,
        "--num-trials",
        help="설정을 몇 개 시도했는지(다중검정 디플레이션용, 스펙 027). 기본 1=보정 없음.",
    ),
    trial_sharpe_std: float = typer.Option(
        None,
        "--trial-sharpe-std",
        help="시도한 설정들의 (연율) 샤프 표준편차. --num-trials>1 + 이 값이 있어야 DSR 계산.",
    ),
    min_psr: float = typer.Option(
        None,
        "--min-psr",
        help="표본 외 PSR 이 이 값 미만이면 과적합 플래그(옵트인 하드 게이트, 종료 1).",
    ),
    min_dsr: float = typer.Option(
        None,
        "--min-dsr",
        help="표본 외 DSR 이 이 값 미만이면 과적합 플래그(옵트인 하드 게이트, 종료 1).",
    ),
    dataset_version: str = typer.Option(
        None,
        "--dataset-version",
        help="Specific dataset_version; defaults to most recent under history-root.",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"), "--db", help="SQLite audit-log path."
    ),
    halt_path: Path = typer.Option(
        Path("data/halt.flag"), "--halt-path", help="Filesystem halt-flag path."
    ),
    history_root: Path = typer.Option(
        Path("data/history"), "--history-root", help="Where ingested datasets live."
    ),
    commission_bps: float = typer.Option(
        None, "--commission-bps", help="Per-side commission bps (default: KIS US-equity)."
    ),
    slippage_bps: float = typer.Option(
        None, "--slippage-bps", help="Adverse slippage per fill bps (default: KIS)."
    ),
    min_commission_usd: float = typer.Option(
        None, "--min-commission-usd", help="Per-fill commission floor USD (default: 0)."
    ),
) -> None:
    """Walk-forward (out-of-sample) validation — overfitting detector (spec 016 슬라이스 3).

    Runs the same ruleset across rolling IS/OOS date windows and reports the
    honest pooled out-of-sample performance plus Walk-Forward Efficiency. Same
    single-yardstick metrics as `backtest` (헌법 X.2). Offline, read-only.
    """
    from datetime import date as _date
    from decimal import Decimal as _Decimal

    from auto_invest.backtest.costs import BacktestCostModel
    from auto_invest.backtest.data_source import CSVDataSource, latest_dataset_dir
    from auto_invest.backtest.run import EXIT_COVERAGE
    from auto_invest.backtest.walk_forward import (
        WalkForwardError,
        render_walk_forward_report,
        run_walk_forward,
    )

    _cost_base = BacktestCostModel.kis_default()
    cost_model = BacktestCostModel(
        commission_bps=(
            _Decimal(str(commission_bps))
            if commission_bps is not None
            else _cost_base.commission_bps
        ),
        slippage_bps=(
            _Decimal(str(slippage_bps)) if slippage_bps is not None else _cost_base.slippage_bps
        ),
        min_commission_usd=(
            _Decimal(str(min_commission_usd))
            if min_commission_usd is not None
            else _cost_base.min_commission_usd
        ),
    )

    if mode not in ("rolling", "anchored"):
        typer.echo(f"--mode must be 'rolling' or 'anchored', got {mode!r}", err=True)
        _exit(64)

    # Resolve dataset directory.
    if dataset_version is not None:
        dataset_dir = history_root / dataset_version
        if not (dataset_dir / "manifest.json").exists():
            typer.echo(
                f"dataset_version {dataset_version!r} not found under {history_root}", err=True
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

    try:
        caps, whitelist, parsed_rules, _ruleset_sha256 = _load_rules_for_backtest(rules)
    except ConfigError as exc:
        typer.echo(f"rules validation failed: {exc}", err=True)
        _exit(65)
        return

    data_source = CSVDataSource(dataset_dir)
    holes = data_source.coverage_holes(list(data_source.list_symbols()), ds_start, ds_end)
    if holes:
        for sym, d in holes[:20]:
            typer.echo(f"coverage hole: {sym} {d.isoformat()}", err=True)
        if len(holes) > 20:
            typer.echo(f"...and {len(holes) - 20} more", err=True)
        _exit(EXIT_COVERAGE)

    _require_clean_migrations(db_path, allow_apply=True)
    conn = db.get_connection(db_path)
    try:
        report = run_walk_forward(
            rules=parsed_rules,
            data_source=data_source,
            date_start=ds_start,
            date_end=ds_end,
            caps=caps,
            whitelist=whitelist,
            halt_path=halt_path,
            conn=conn,
            in_sample_days=in_sample_days,
            out_of_sample_days=out_of_sample_days,
            step_days=step_days,
            mode=mode,
            cost_model=cost_model,
            wfe_threshold=_Decimal(str(wfe_threshold)),
            num_trials=num_trials,
            trial_sharpe_std_annual=(
                _Decimal(str(trial_sharpe_std)) if trial_sharpe_std is not None else None
            ),
            min_psr=_Decimal(str(min_psr)) if min_psr is not None else None,
            min_dsr=_Decimal(str(min_dsr)) if min_dsr is not None else None,
        )
    except WalkForwardError as exc:
        typer.echo(f"walk-forward window error: {exc}", err=True)
        _exit(64)
        return
    finally:
        conn.close()
        data_source.close()

    typer.echo(render_walk_forward_report(report))
    if report.overfit_suspected:
        _exit(1)


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


@app.command()
def tune(
    apply: bool = typer.Option(
        False,
        "--apply/--dry-run",
        help="--apply: 저위험(L1) 변경 자동 적용. --dry-run(기본): 분석만(무변경).",
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"),
        "--db",
        help="SQLite database path.",
    ),
    thresholds_path: Path = typer.Option(
        Path("config/llm_kpi_thresholds.toml"),
        "--thresholds",
        help="튜닝 대상 KPI 임계값 파일.",
    ),
    kernel_path: Path = typer.Option(
        Path(".specify/memory/kernel.toml"),
        "--kernel",
        help="Kernel 매니페스트(권한 등급 분류용).",
    ),
    as_of: str | None = typer.Option(
        None,
        "--as-of",
        help="기준 세션 날짜(YYYY-MM-DD). 미지정 시 오늘(UTC).",
    ),
    window_short_days: int = typer.Option(
        7,
        "--window-short-days",
        help="단기 롤링 윈도(드리프트 감지), 일 단위.",
    ),
    window_long_days: int = typer.Option(
        30,
        "--window-long-days",
        help="장기 롤링 윈도(안정성 판정·조이기), 일 단위.",
    ),
    min_sample: int = typer.Option(
        20,
        "--min-sample",
        help="헌법 X 최소 표본 — 윈도 호출 수가 미만이면 튜닝 거부.",
    ),
    output_root: Path | None = typer.Option(
        None,
        "--output-root",
        help="주면 {root}/{session_date}/auto-tuner-report.json 작성.",
    ),
    output_json: bool = typer.Option(
        False,
        "--json/--no-json",
        help="--json: stdout 에 TunerRunResult JSON.",
    ),
) -> None:
    """Spec 005 — 자율 튜너. KPI 드리프트를 감지·분류하고 저위험 L1 변경을 자동 적용.

    순수 결정론적(LLM 미호출). --dry-run(기본)은 어떤 파일·감사도 바꾸지 않는다.
    --apply 라도 장 시간 마진 안(헌법 VIII.A)·측정 부족(헌법 X)이면 적용하지 않는다.
    대상 파일이 kernel.toml 에 닿으면 무조건 L4(자동 적용 거부, 포렌식 콜아웃).
    """
    from datetime import UTC
    from datetime import datetime as _dt

    from auto_invest.telemetry.thresholds import TierTableError
    from auto_invest.tuner.detect import parse_as_of
    from auto_invest.tuner.report import to_json
    from auto_invest.tuner.runner import run_tuner

    try:
        as_of_date = parse_as_of(as_of)
    except ValueError:
        typer.echo("--as-of must be YYYY-MM-DD.", err=True)
        _exit(2)
    if window_short_days < 1 or window_long_days < 1:
        typer.echo("--window-*-days must be >= 1.", err=True)
        _exit(2)
    if not thresholds_path.exists():
        typer.echo(f"thresholds file not found: {thresholds_path}", err=True)
        _exit(2)
    if not db_path.exists():
        typer.echo(f"database not found: {db_path}", err=True)
        _exit(2)

    mode = "apply" if apply else "dry_run"
    try:
        result = run_tuner(
            db_path=db_path,
            thresholds_path=thresholds_path,
            kernel_path=kernel_path,
            as_of=as_of_date,
            mode=mode,  # type: ignore[arg-type]
            window_short_days=window_short_days,
            window_long_days=window_long_days,
            min_sample=min_sample,
            now=_dt.now(UTC) if apply else None,
            output_root=output_root,
        )
    except (TierTableError, ValueError) as exc:
        typer.echo(f"tune failed: {exc}", err=True)
        _exit(2)

    if output_json:
        typer.echo(to_json(result))
    else:
        typer.echo(
            f"[tune {result.mode}] session={result.session_date} "
            f"candidates={len(result.candidates)} applied={len(result.applied)} "
            f"canary={len(result.canary_entered)} l4={len(result.awaiting_human_merge)} "
            f"skipped={len(result.skipped)}"
        )
        for cls in result.candidates:
            typer.echo(
                f"  - {cls.candidate.candidate_id} [{cls.tier}] {cls.reason}"
            )
        for cid, reason in result.skipped:
            typer.echo(f"  · skipped {cid}: {reason}")
        if result.canary_candidates or result.canary_validations:
            n = len(result.canary_candidates)
            passed = sum(1 for v in result.canary_validations if v.outcome == "passed")
            failed = sum(1 for v in result.canary_validations if v.outcome == "failed")
            sk = sum(1 for v in result.canary_validations if v.outcome == "skipped")
            typer.echo(
                f"캐너리 후보 {n} / 합격 {passed} / 불합격 {failed} / 건너뜀 {sk}"
                " — 라이브 미승격(운영자/스펙 006 게이트)"
            )


@app.command("nav-snapshot")
def nav_snapshot_cmd(
    mode: str = typer.Option("paper", "--mode", help="paper | live — 어느 장부의 NAV."),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"), "--db", help="SQLite path (fills·audit_log)."
    ),
    env_file: Path = typer.Option(
        None, "--env-file", "--env", help="KIS 시세 조회용 .env (미실현 mark-to-market)."
    ),
    base_url: str = typer.Option(
        "https://openapi.koreainvestment.com:9443", "--base-url"
    ),
    no_marks: bool = typer.Option(
        False, "--no-marks", help="시세 조회 생략 — 평균단가로 보수 평가."
    ),
    snapshot: bool = typer.Option(
        False,
        "--snapshot",
        help="결과를 audit_log 에 추가-전용 PORTFOLIO_NAV_SNAPSHOT 1건으로 기록"
        " (스펙 029·035 시계열 생산자). 기본은 미기록(순수 계산).",
    ),
    capital: float = typer.Option(
        None,
        "--capital",
        help="트랙 시작 자본 USD — 장부 현금 = 자본 + 순현금흐름(매도 − 매수)으로"
        " NAV 에 현금을 포함한다. 없으면 현금 0(레거시) — 매수/매도가 NAV 를 출렁여"
        " forward 수익률이 오염되므로, 판정용 페이퍼 트랙은 반드시 줄 것.",
    ),
    output_format: str = typer.Option("text", "--format", help="text | json."),
) -> None:
    """Spec 029/035 — 현재 시가평가 순자산(NAV)을 계산하고 (옵션) 시계열에 1점 기록한다.

    스펙 029 의 `compute_nav` 는 만들어졌으나 어떤 실행 경로에도 안 꽂혀 있어 NAV 시계열이
    기록되지 않았다. 이 명령이 그 생산자다 — 장부 보유(fills 재구성)를 현재 KIS 시세로
    평가해 순자산을 내고, `--snapshot` 이면 PORTFOLIO_NAV_SNAPSHOT 으로 append 한다.
    그 시계열을 `forward-verdict` 가 읽어 엣지를 판정한다.

    측정 전용 — 주문 0건, 돈 0 이동. 기본 동작은 순수 계산(미기록), read-only.
    """
    import json as _json
    from datetime import UTC, datetime

    from auto_invest.performance.engine import net_cash_flow_usd, read_fills, reconstruct
    from auto_invest.portfolio import compute_nav
    from auto_invest.portfolio.nav import render_text as nav_render_text

    if mode not in ("paper", "live"):
        typer.echo("--mode must be 'paper' or 'live'.", err=True)
        _exit(2)
    if output_format not in ("text", "json"):
        typer.echo("--format must be 'text' or 'json'.", err=True)
        _exit(2)
    if not db_path.exists():
        typer.echo(f"DB 파일을 찾을 수 없습니다: {db_path}", err=True)
        _exit(1)

    # 보유는 전체 누적 체결로 재구성한다 — 넓은 기간으로 모든 fills 를 읽는다.
    since_dt = datetime(1970, 1, 1, tzinfo=UTC)
    until_dt = datetime.now(UTC)
    conn = db.get_connection(db_path)
    try:
        conn.execute("PRAGMA query_only = ON")
        fills = read_fills(conn, mode=mode, since=since_dt, until=until_dt)
        positions, _, _, _ = reconstruct(fills)
    finally:
        conn.close()

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
        except Exception as exc:  # noqa: BLE001 — 시세 실패는 평균단가 폴백
            typer.echo(f"(시세 조회 실패 — 평균단가 평가: {exc})", err=True)

    capital_dec: Decimal | None = None
    ledger_cash: Decimal | None = None
    if capital is not None:
        capital_dec = Decimal(str(capital))
        ledger_cash = capital_dec + net_cash_flow_usd(fills)
        if ledger_cash < 0:
            typer.echo(
                f"(경고: 장부 현금 음수 ${ledger_cash} — 자본 기준이 누적 순투입보다"
                " 작음. NAV 는 그래도 자본+손익으로 일관되게 계산됨)",
                err=True,
            )

    snap = compute_nav(
        broker_cash_usd=None,
        broker_positions=None,
        broker_reported_total_value_usd=None,
        ledger_positions=positions,
        marks=marks,
        ledger_cash_usd=ledger_cash,
    )

    if snapshot:
        from auto_invest.persistence import audit

        write_conn = db.get_connection(db_path)
        try:
            seq = audit.append(
                write_conn,
                audit.PortfolioNavSnapshotPayload(
                    mode=mode,  # type: ignore[arg-type]
                    schema_version=snap.SCHEMA_VERSION,
                    source=snap.source,
                    computed_at_utc=_d_iso_now(),
                    cash_usd=str(snap.cash_usd),
                    total_market_value_usd=str(snap.total_market_value_usd),
                    total_nav_usd=str(snap.total_nav_usd),
                    total_unrealized_pnl_usd=str(snap.total_unrealized_pnl_usd),
                    broker_reported_nav_usd=(
                        None
                        if snap.broker_reported_nav_usd is None
                        else str(snap.broker_reported_nav_usd)
                    ),
                    holdings_count=len([h for h in snap.holdings if h.qty != 0]),
                    total_qty_drift=snap.total_qty_drift,
                    total_value_drift_usd=str(snap.total_value_drift_usd),
                    capital_basis_usd=(
                        None if capital_dec is None else str(capital_dec)
                    ),
                ),
            )
        finally:
            write_conn.close()
        typer.echo(f"(스냅샷 기록됨: PORTFOLIO_NAV_SNAPSHOT seq={seq})", err=True)

    if output_format == "json":
        out = snap.to_json_dict()
        out["mode"] = mode
        typer.echo(_json.dumps(out))
    else:
        typer.echo(nav_render_text(snap))


@app.command("forward-verdict")
def forward_verdict_cmd(
    portfolio: Path = typer.Option(
        None,
        "--portfolio",
        help="TOML; [portfolio].universe 로 단순 보유 벤치마크를 구성한다.",
    ),
    mode: str = typer.Option("paper", "--mode", help="paper | live — 어느 트랙을 판정."),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"), "--db", help="SQLite path (audit_log·price_bars)."
    ),
    timeframe: str = typer.Option("1d", "--timeframe", help="벤치마크 가격 바 타임프레임."),
    num_trials: int = typer.Option(
        1,
        "--num-trials",
        help="시도한 전략 설정 개수 — 디플레이티드 샤프(과적합 보정)용. 정직히 세라.",
    ),
    trial_sharpe_std: float = typer.Option(
        None,
        "--trial-sharpe-std",
        help="시도한 설정들의 연율 샤프 표준편차 — num_trials>1 일 때 DSR 계산에 필요.",
    ),
    min_obs: int = typer.Option(
        20, "--min-obs", help="이보다 적은 관측이면 판정 보류(INSUFFICIENT_DATA)."
    ),
    dsr_threshold: float = typer.Option(
        0.95, "--dsr-threshold", help="PSR/DSR 합격선 (0..1)."
    ),
    output_format: str = typer.Option("text", "--format", help="text | json."),
) -> None:
    """Spec 035 — forward 페이퍼 트랙이 '실제로 돈을 버는가'를 자동 판정한다.

    쌓인 PORTFOLIO_NAV_SNAPSHOT 시계열(생산자: `nav-snapshot --snapshot`)을 읽어 위험조정
    성과를 단순 보유 벤치마크와 비교하고, 디플레이티드/확률적 샤프(스펙 027)로 우연·과적합을
    처벌한 뒤 EDGE_CONFIRMED / NO_EDGE / INSUFFICIENT_DATA 를 낸다. 관측이 적으면 보수적으로
    INSUFFICIENT_DATA — 모르면 엣지 선언 금지(돈을 잃지 않게 막는다).

    측정/분석 전용 — 주문 0건, 돈 0 이동. EDGE_CONFIRMED 는 운영자 라이브 게이트(헌법 X.4)에
    올릴 증거이지 자동 배포가 아니다.
    """
    import json as _json
    from datetime import datetime as _dt

    from auto_invest.market_data.store import get_bars
    from auto_invest.portfolio import (
        forward_edge_verdict,
        read_nav_points,
        stitch_basis_segments,
    )
    from auto_invest.portfolio.edge_verdict import equal_weight_buy_hold_curve
    from auto_invest.portfolio.edge_verdict import render_text as verdict_render_text

    if mode not in ("paper", "live"):
        typer.echo("--mode must be 'paper' or 'live'.", err=True)
        _exit(2)
    if output_format not in ("text", "json"):
        typer.echo("--format must be 'text' or 'json'.", err=True)
        _exit(2)
    if not db_path.exists():
        typer.echo(f"DB 파일을 찾을 수 없습니다: {db_path}", err=True)
        _exit(1)

    universe: list[str] = []
    if portfolio is not None:
        try:
            _caps, _wl, port_cfg = _load_portfolio_for_backtest(portfolio)
        except ConfigError as exc:
            typer.echo(f"portfolio validation failed: {exc}", err=True)
            _exit(65)
            return
        universe = list(port_cfg.universe)  # type: ignore[union-attr]

    def _to_date(ts: str):
        return _dt.fromisoformat(ts.replace("Z", "+00:00")).date()

    conn = db.get_connection(db_path)
    try:
        conn.execute("PRAGMA query_only = ON")
        all_points = read_nav_points(conn, mode=mode)
        # 시간가중수익률(TWR): 자본 베이시스 경계(자금 흐름)만 건너뛰고 같은 전략의 구간
        # 내부 수익률을 사슬로 이어 전체 track record 를 보존한다. 옛 방식(최신 베이시스
        # 구간만)은 같은 전략인데 자본이 바뀌면 forward 관측을 통째로 리셋해 낭비했다 —
        # 수익률은 자본 규모와 무관하므로 과거를 버릴 이유가 없다(GIPS 표준).
        points = stitch_basis_segments(all_points)
        nav_curve = [p.nav_usd for p in points]
        nav_dates = [_to_date(p.at_utc) for p in points]
        bars_by_symbol: dict[str, list] = {}
        if universe and len(nav_dates) >= 2:
            for sym in universe:
                bars = get_bars(conn, symbol=sym, timeframe=timeframe)
                bars_by_symbol[sym] = [
                    (_to_date(b.bar_open_utc), b.close_usd)
                    for b in bars
                    if b.close_usd > 0
                ]
    finally:
        conn.close()

    benchmark_curve = (
        equal_weight_buy_hold_curve(nav_dates, bars_by_symbol)
        if bars_by_symbol
        else None
    )

    verdict = forward_edge_verdict(
        nav_curve,
        benchmark_curve,
        num_trials=num_trials,
        trial_sharpe_std_annual=(
            None if trial_sharpe_std is None else Decimal(str(trial_sharpe_std))
        ),
        min_obs=min_obs,
        dsr_threshold=Decimal(str(dsr_threshold)),
    )

    if output_format == "json":
        out = verdict.to_json_dict()
        out["mode"] = mode
        out["snapshot_count"] = len(points)
        out["legacy_snapshots_excluded"] = len(all_points) - len(points)
        out["universe"] = universe
        typer.echo(_json.dumps(out))
    else:
        typer.echo(verdict_render_text(verdict))


@app.command("forward-verdict-anchored")
def forward_verdict_anchored_cmd(
    portfolio: Path = typer.Option(
        ..., "--portfolio", help="TOML [caps]/[whitelist]/[portfolio] (OOS 평가 대상)."
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"), "--db", help="라이브 forward NAV 스냅샷 SQLite."
    ),
    mode: str = typer.Option("paper", "--mode", help="forward NAV 장부: paper | live."),
    timeframe: str = typer.Option("1d", "--timeframe", help="바 타임프레임."),
    history_root: Path = typer.Option(
        Path("data/history"), "--history-root", help="인제스트 데이터셋 부모 디렉터리."
    ),
    dataset_version: str = typer.Option(
        None, "--dataset-version", help="특정 데이터셋; 기본 = 최신."
    ),
    trailing_years: int = typer.Option(
        None, "--trailing-years", help="최근 N년만 OOS 평가(명확 recency 창)."
    ),
    date_from: str = typer.Option(None, "--from", help="OOS 시작(YYYY-MM-DD)."),
    date_to: str = typer.Option(None, "--to", help="OOS 끝(YYYY-MM-DD)."),
    segment_days: int = typer.Option(365, "--segment-days", help="OOS 구간 길이(일)."),
    lookback_buffer_days: int = typer.Option(
        160, "--lookback-buffer-days", help="첫 구간 앞 신호 lookback 버퍼(일)."
    ),
    wf_mode: str = typer.Option("rolling", "--wf-mode", help="walk-forward: rolling|anchored."),
    num_trials: int = typer.Option(
        1, "--num-trials", help="시도한 설정 수 — DSR 다중검정 보정(정직히)."
    ),
    capital: float = typer.Option(100000.0, "--capital", help="OOS 시작 자본 USD."),
    halt_path: Path = typer.Option(
        Path("data/halt.flag"), "--halt-path", help="Halt 깃발 경로."
    ),
    min_oos_obs: int = typer.Option(60, "--min-oos-obs", help="앵커 최소 OOS 관측(일)."),
    min_forward_obs: int = typer.Option(
        5, "--min-forward-obs", help="지속 확인 최소 forward 관측(일)."
    ),
    consistency_z: float = typer.Option(
        2.0, "--consistency-z", help="forward 가 OOS 보다 이 z 이상 나쁘면 NO_EDGE."
    ),
    dsr_threshold: float = typer.Option(0.95, "--dsr-threshold", help="OOS PSR/DSR 합격선."),
    allow_stale: bool = typer.Option(
        False, "--allow-stale", help="recency 가드가 stale 로 봐도 진행(주의)."
    ),
    output_format: str = typer.Option("json", "--format", help="json | text."),
) -> None:
    """스펙 035 후속 — 백테스트 앵커드 엣지 판정(읽기 전용 진단, 주문 0건).

    깊은 표본외(OOS) walk-forward(인제스트 데이터셋)가 엣지를 세우고, 라이브 forward 페이퍼
    스냅샷이 그 엣지가 *지속* 하는지만 확인한다 → 일별 20일 재발견 불필요(운영자 지적 해법).
    이 명령은 **판정 JSON 을 발행만** 한다(게이트 변경·무장·주문 0). 게이트 소비는 별도.
    """
    import json as _json
    from datetime import date as _date
    from decimal import Decimal as _Decimal

    from auto_invest.backtest.data_source import CSVDataSource, latest_dataset_dir
    from auto_invest.backtest.portfolio_walk_forward import run_portfolio_walk_forward
    from auto_invest.backtest.recency import assess_recency, stale_guard, trailing_window
    from auto_invest.portfolio import (
        daily_returns_from_curve,
        read_nav_points,
        stitch_basis_segments,
    )
    from auto_invest.portfolio.backtest_anchored import backtest_anchored_verdict

    if mode not in ("paper", "live"):
        typer.echo("--mode must be 'paper' or 'live'.", err=True)
        _exit(2)
    if output_format not in ("text", "json"):
        typer.echo("--format must be 'text' or 'json'.", err=True)
        _exit(2)
    if not db_path.exists():
        typer.echo(f"DB 파일을 찾을 수 없습니다: {db_path}", err=True)
        _exit(1)

    try:
        caps, whitelist, port_cfg = _load_portfolio_for_backtest(portfolio)
    except ConfigError as exc:
        typer.echo(f"portfolio validation failed: {exc}", err=True)
        _exit(65)
        return

    # 1) 깊은 OOS — 인제스트 데이터셋에서 walk-forward.
    if dataset_version is not None:
        dataset_dir = history_root / dataset_version
        if not (dataset_dir / "manifest.json").exists():
            typer.echo(f"dataset_version {dataset_version!r} not found", err=True)
            _exit(64)
            return
    else:
        dataset_dir = latest_dataset_dir(history_root)
        if dataset_dir is None:
            typer.echo("no ingested datasets; run `auto-invest ingest-history`", err=True)
            _exit(64)
            return
    data_source = CSVDataSource(dataset_dir)
    recency = assess_recency(data_source, port_cfg.universe)  # type: ignore[union-attr]
    refusal = stale_guard(recency, allow_stale=allow_stale)
    if refusal is not None:
        typer.echo(refusal, err=True)
        data_source.close()
        _exit(70)
        return
    try:
        if trailing_years is not None:
            window = trailing_window(
                data_source, port_cfg.universe, trailing_years=trailing_years  # type: ignore[union-attr]
            )
            if window is None:
                typer.echo("dataset has no sessions for the universe", err=True)
                data_source.close()
                _exit(64)
                return
            ds_start, ds_end = window
        elif date_from is not None and date_to is not None:
            ds_start = _date.fromisoformat(date_from)
            ds_end = _date.fromisoformat(date_to)
        else:
            typer.echo("provide --from/--to or --trailing-years", err=True)
            data_source.close()
            _exit(64)
            return
    except ValueError as exc:
        typer.echo(f"date parsing failed: {exc}", err=True)
        data_source.close()
        _exit(64)
        return

    _require_clean_migrations(db_path, allow_apply=True)
    conn = db.get_connection(db_path)
    try:
        report = run_portfolio_walk_forward(
            config=port_cfg,  # type: ignore[arg-type]
            data_source=data_source,
            date_start=ds_start,
            date_end=ds_end,
            caps=caps,  # type: ignore[arg-type]
            whitelist=whitelist,  # type: ignore[arg-type]
            halt_path=halt_path,
            conn=conn,
            lookback_buffer_days=lookback_buffer_days,
            segment_days=segment_days,
            mode=wf_mode,
            total_capital_usd=_Decimal(str(capital)),
            num_trials=num_trials,
        )
        oos_returns = report.pooled_returns
        # 2) 짧은 forward — 라이브 페이퍼 NAV(시간가중수익률 스티치)에서 일수익률.
        conn.execute("PRAGMA query_only = ON")
        fwd_points = stitch_basis_segments(read_nav_points(conn, mode=mode))
        forward_returns = daily_returns_from_curve([p.nav_usd for p in fwd_points])
    except Exception as exc:  # 데이터 부족·창 불가 등 — 사용 오류로 표면화
        typer.echo(f"anchored verdict failed: {exc}", err=True)
        conn.close()
        data_source.close()
        _exit(64)
        return
    conn.close()
    data_source.close()

    # 3) 앵커드 판정 — 깊은 OOS 증거 + 짧은 forward 지속성.
    verdict = backtest_anchored_verdict(
        oos_returns=oos_returns,
        forward_returns=forward_returns,
        oos_edge_confirmed=report.verdict.startswith("강건한 엣지 신호"),
        oos_rejection_reason=report.verdict,
        num_trials=num_trials,
        dsr_threshold=_Decimal(str(dsr_threshold)),
        min_oos_obs=min_oos_obs,
        min_forward_obs=min_forward_obs,
        consistency_z=_Decimal(str(consistency_z)),
    )
    out = verdict.to_json_dict()
    out["mode"] = mode
    out["dataset_version"] = report.segments[0].start.isoformat() if report.segments else None
    out["wf_segments"] = report.n_segments
    out["wf_verdict"] = report.verdict
    if output_format == "json":
        typer.echo(_json.dumps(out))
    else:
        typer.echo(
            f"[{verdict.verdict}] {verdict.reason}\n"
            f"OOS 관측 {verdict.oos_n_obs} · forward 관측 {verdict.forward_n_obs} · "
            f"walk-forward 구간 {report.n_segments}"
        )


@app.command("autoarm-decide")
def autoarm_decide_cmd(
    verdict_json: Path = typer.Option(
        ...,
        "--verdict-json",
        help="forward-verdict --format json 출력 파일(검증된 앙상블 ARM E 트랙).",
    ),
    live_portfolio: Path = typer.Option(
        Path("deploy/canary-live-portfolio.toml"),
        "--live-portfolio",
        help="라이브 캐너리가 *실제로 거래할* 설정(무장 대상).",
    ),
    validated_portfolio: Path = typer.Option(
        Path("deploy/global-trend-portfolio.toml"),
        "--validated-portfolio",
        help="forward 페이퍼에서 검증한 설정(ARM E).",
    ),
    sentinel: Path = typer.Option(
        Path("automation/rebalance-live.request"),
        "--sentinel",
        help="현재 무장 센티넬(armed/capital_usd/run_seq).",
    ),
    kill_switch: Path = typer.Option(
        Path("automation/AUTOARM_DISABLED"),
        "--kill-switch",
        help="존재하면 자동 무장 정지(운영자 킬스위치).",
    ),
    write_sentinel: bool = typer.Option(
        False,
        "--write-sentinel",
        help="결정이 ARM 이면 새 무장 센티넬 본문을 --sentinel 경로에 쓴다(기본: 안 씀).",
    ),
    output_format: str = typer.Option("json", "--format", help="json | text."),
) -> None:
    """스펙 049 — forward 엣지 자동 무장 게이트 결정(읽기 전용 판정, 주문 0건).

    검증된 앙상블(ARM E)의 forward 판정이 EDGE_CONFIRMED 이고, 라이브 캐너리 설정의 전략
    지문이 그 검증한 앙상블과 일치하며(검증=무장 정합성), 아직 미무장이고 킬스위치가 없으면
    **ARM**(새 armed:true 센티넬 제안)을 낸다. 그 외에는 보수적으로 WAIT/BLOCKED/
    ALREADY_ARMED/DISABLED — 절대 무모하게 무장하지 않는다.

    `--write-sentinel` 을 주면 ARM 일 때만 새 센티넬 본문을 파일에 쓴다(워크플로가 그 변경을
    PR 로 올려 운영자 X.4 검토 후 머지 → 라이브 캐너리 채널 발화). 머지 자체는 미리보기만
    이고 첫 실주문은 다음 미국 정규장 스케줄 — 운영자가 검토·disarm 할 시간이 있다.
    """
    import json as _json

    from auto_invest.portfolio.autoarm import decide_autoarm

    try:
        verdict = _json.loads(verdict_json.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        # 판정 파일을 못 읽으면 보수적으로 WAIT — 절대 무장하지 않는다.
        out = {
            "schema_version": "1.0",
            "action": "WAIT",
            "reason": f"forward 판정 JSON 을 못 읽음({e}) — 보수적으로 무장 보류.",
            "verdict": None,
            "n_obs": None,
            "proposed_capital_usd": None,
            "new_run_seq": None,
        }
        typer.echo(_json.dumps(out))
        raise typer.Exit(0) from None

    # 정합성 지문은 [portfolio] 전략 블록만 쓴다([whitelist].accounts 의 ${VAR} 미사용) →
    # env 확장 불필요. env=None 으로 로드.
    try:
        _, _, live_cfg = _load_portfolio_for_backtest(live_portfolio, env=None)
        _, _, validated_cfg = _load_portfolio_for_backtest(validated_portfolio, env=None)
    except ConfigError as e:
        out = {
            "schema_version": "1.0",
            "action": "BLOCKED",
            "reason": f"포트폴리오 설정 로드 실패({e}) — 정합성 확인 불가, 무장 차단.",
            "verdict": verdict.get("verdict") if isinstance(verdict, dict) else None,
            "n_obs": None,
            "proposed_capital_usd": None,
            "new_run_seq": None,
        }
        typer.echo(_json.dumps(out))
        raise typer.Exit(0) from None

    sentinel_text = sentinel.read_text(encoding="utf-8") if sentinel.exists() else ""
    decision = decide_autoarm(
        verdict=verdict,
        live_config=live_cfg,
        validated_config=validated_cfg,
        sentinel_text=sentinel_text,
        kill_switch_present=kill_switch.exists(),
    )

    if decision.should_arm and write_sentinel and decision.new_sentinel_text:
        _assert_autonomous_write_allowed(
            summary="autoarm write live-canary arming sentinel",
            paths=(sentinel,),
            requested_level=AutonomyLevel.CAPITAL_SCALING,
        )
        sentinel.write_text(decision.new_sentinel_text, encoding="utf-8")

    if output_format == "json":
        typer.echo(_json.dumps(decision.to_json_dict()))
    else:
        typer.echo(f"[{decision.action}] {decision.reason}")


@app.command("account-nav")
def account_nav_cmd(
    env_file: Path = typer.Option(
        None, "--env-file", help=".env with KIS_APP_KEY/KIS_APP_SECRET/KIS_ACCOUNT_NO."
    ),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"), "--db", help="토큰 캐시 위치 산출용 SQLite 경로."
    ),
    base_url: str = typer.Option(
        "https://openapi.koreainvestment.com:9443", "--base-url", help="KIS REST base URL."
    ),
    as_json: bool = typer.Option(False, "--json", help="JSON 출력."),
) -> None:
    """실계좌 순자산(NAV = USD 예수금 + 보유 평가금액)을 멀티 거래소 스윕으로 조회.

    스펙 050 자본 사다리의 사이징 기준(운영자 위임 2026-06-11: "기준은 계좌 잔고와
    포트폴리오"). 읽기 전용 — 주문 0건, 돈 0 이동. 조회 실패는 비0 종료(게이트가
    보수적으로 BLOCKED 처리하도록 fail-closed).
    """
    import json as _json

    from auto_invest.broker.overseas import get_balance_resolving_market

    try:
        secrets = load_secrets(env_file)
    except ConfigError as exc:
        typer.echo(f"secrets error: {exc}", err=True)
        _exit(2)
        return
    app_key = secrets.get("KIS_APP_KEY")
    app_secret = secrets.get("KIS_APP_SECRET")
    account = secrets.get("KIS_ACCOUNT_NO")
    if not app_key or not app_secret or not account:
        typer.echo("KIS_APP_KEY/KIS_APP_SECRET/KIS_ACCOUNT_NO required", err=True)
        _exit(2)
        return

    async def _run():
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
            return await get_balance_resolving_market(
                client,
                access_token=token.access_token,
                app_key=app_key,
                app_secret=app_secret,
                account=account,
            )

    try:
        snap = asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001 — 조회 실패는 fail-closed 비0 종료.
        typer.echo(f"account NAV fetch failed: {exc}", err=True)
        _exit(1)
        return

    if as_json:
        typer.echo(
            _json.dumps(
                {
                    "schema_version": "1.0",
                    "cash_usd": str(snap.cash_usd),
                    "total_value_usd": str(snap.total_value_usd),
                    "fetched_at_utc": snap.fetched_at_utc.isoformat(),
                }
            )
        )
        return
    typer.echo(f"cash_usd        : {snap.cash_usd}")
    typer.echo(f"total_value_usd : {snap.total_value_usd}")


@app.command("growth")
def growth_cmd(
    mode: str = typer.Option("paper", "--mode", help="paper | live."),
    db_path: Path = typer.Option(
        Path("data/auto_invest.db"), "--db", help="SQLite database path."
    ),
    since: str = typer.Option(
        None,
        "--since",
        help="이 날짜(YYYY-MM-DD, UTC 자정) 이후 스냅샷만 — 스펙 050 단(rung) 진입 후"
        " 실적 측정용. 생략 시 전체.",
    ),
    consistent_basis: bool = typer.Option(
        True,
        "--consistent-basis/--all-points",
        help="같은 측정 기준(자본 베이시스)의 최신 연속 구간만(기본) / 전체 점.",
    ),
    output_format: str = typer.Option("json", "--format", help="json | text."),
) -> None:
    """NAV 스냅샷 시계열 → 성장 지표(총수익률·최대낙폭·CAGR). 읽기 전용(스펙 029/050).

    스펙 050 자본 사다리의 라이브 실적 증거 산출기: `--mode live --since <단 진입일>`
    로 현재 단에서의 관측 수·낙폭을 계산한다. 측정 기준이 섞인 점은 기본으로 걸러
    자금 흐름이 수익률로 오인되는 오염(PR #243에서 수정한 클래스)을 차단한다.
    """
    import json as _json
    from datetime import UTC
    from datetime import datetime as _dt

    from auto_invest.portfolio.growth import (
        compute_growth,
        consistent_basis_suffix,
        read_nav_points,
    )

    if mode not in ("paper", "live"):
        typer.echo("mode must be 'paper' or 'live'", err=True)
        _exit(2)
        return
    since_dt = None
    if since:
        try:
            d = _dt.fromisoformat(since)
            since_dt = d if d.tzinfo else d.replace(tzinfo=UTC)
        except ValueError:
            typer.echo(f"invalid --since date: {since!r}", err=True)
            _exit(2)
            return
    if not db_path.exists():
        typer.echo(f"DB not found: {db_path}", err=True)
        _exit(2)
        return

    conn = db.get_connection(db_path)
    try:
        points = read_nav_points(conn, mode=mode, since=since_dt)
    finally:
        conn.close()
    if consistent_basis:
        points = consistent_basis_suffix(points)
    report = compute_growth(points, mode=mode)

    if output_format == "json":
        typer.echo(_json.dumps(report.to_json_dict()))
        return
    from auto_invest.portfolio.growth import render_text

    typer.echo(render_text(report))


@app.command("ladder-decide")
def ladder_decide_cmd(
    verdict_json: Path = typer.Option(
        ...,
        "--verdict-json",
        help="forward-verdict --format json 출력 파일(검증 앙상블 ARM E, 단 0→1 게이트).",
    ),
    anchored_verdict_json: Path = typer.Option(
        None,
        "--anchored-verdict-json",
        help="forward-verdict-anchored --format json 출력 파일(선택). 주면 표준 판정과 "
        "결합 — 둘 중 하나라도 EDGE_CONFIRMED 면 확정(앵커드가 깊은 OOS+짧은 forward "
        "지속으로 20일을 기다리지 않고 가속). 없으면 기존 표준 판정만(하위 호환).",
    ),
    live_growth_json: Path = typer.Option(
        None,
        "--live-growth-json",
        help="growth --mode live --since <단 진입일> --format json 출력 파일(단 ≥1 증거)."
        " 없거나 못 읽으면 증거 없음으로 처리(승격 불가, fail-safe).",
    ),
    account_nav_json: Path = typer.Option(
        None,
        "--account-nav-json",
        help="account-nav --json 출력 파일(실계좌 NAV — 사이징 기준). 없으면 BLOCKED.",
    ),
    live_portfolio: Path = typer.Option(
        Path("deploy/canary-live-portfolio.toml"),
        "--live-portfolio",
        help="라이브 캐너리가 실제로 거래할 설정.",
    ),
    validated_portfolio: Path = typer.Option(
        Path("deploy/global-trend-portfolio.toml"),
        "--validated-portfolio",
        help="forward 페이퍼에서 검증한 설정(ARM E).",
    ),
    sentinel: Path = typer.Option(
        Path("automation/rebalance-live.request"),
        "--sentinel",
        help="현재 무장 센티넬(armed/capital/ladder_rung/rung_entered).",
    ),
    kill_switch: Path = typer.Option(
        Path("automation/AUTOARM_DISABLED"),
        "--kill-switch",
        help="존재하면 사다리 정지(운영자 킬스위치).",
    ),
    dd_budget_pct: float = typer.Option(
        20.0,
        "--dd-budget-pct",
        help="운영자 낙폭 예산 %(2026-06-11 위임 계약 기본 20). 변경은 운영자 결정.",
    ),
    write_sentinel: bool = typer.Option(
        False,
        "--write-sentinel",
        help="센티넬 변경이 필요한 결정(PROMOTE/DEMOTE/HALT/RESIZE)이면 새 본문을 쓴다.",
    ),
    output_format: str = typer.Option("json", "--format", help="json | text."),
) -> None:
    """스펙 050 — 자본 사다리 결정(읽기 전용 판정, 주문 0건).

    운영자 위임(2026-06-11) 하 자본 배치 규모를 증거 게이트 공식으로 결정한다:
    단0=0% → 단1=25% → 단2=50% → 단3=100% (실계좌 NAV 대비). 내려가는 건 낙폭
    하나로 즉시(예산/2 강등·예산 정지), 올라가는 건 세 증거(관측·경과일·낙폭) 전부.
    헌법 X.4 v5.0.0. 비위임 불변(캡·화이트리스트·감사·서킷 브레이커)은 그대로다.
    """
    import json as _json
    from datetime import UTC
    from datetime import datetime as _dt
    from decimal import Decimal as _Dec

    from auto_invest.portfolio.capital_ladder import decide_ladder

    def _read_json(path: Path | None) -> dict | None:
        if path is None:
            return None
        try:
            return _json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    verdict = _read_json(verdict_json) or {}
    anchored = _read_json(anchored_verdict_json)
    edge_source = "standard"
    if anchored is not None:
        # 앵커드 판정이 있으면 표준과 결합 — 둘 중 하나라도 EDGE_CONFIRMED 면 확정(가속).
        # 없으면 이 블록을 건너뛰어 기존 표준 판정만 쓴다(하위 호환·동작 무변경).
        from auto_invest.portfolio.backtest_anchored import combine_edge_verdicts

        combined = combine_edge_verdicts(verdict, anchored)
        edge_source = combined.get("source", "standard")
        verdict = combined  # decide_ladder 는 verdict["verdict"]/["n_obs"] 만 읽음 — 호환.
    growth = _read_json(live_growth_json)
    nav_doc = _read_json(account_nav_json)
    account_nav = None
    if isinstance(nav_doc, dict) and nav_doc.get("total_value_usd") is not None:
        try:
            account_nav = _Dec(str(nav_doc["total_value_usd"]))
        except ArithmeticError:
            account_nav = None

    try:
        _, _, live_cfg = _load_portfolio_for_backtest(live_portfolio, env=None)
        _, _, validated_cfg = _load_portfolio_for_backtest(validated_portfolio, env=None)
    except ConfigError as e:
        out = {
            "schema_version": "1.0",
            "action": "BLOCKED",
            "reason": f"포트폴리오 설정 로드 실패({e}) — 정합성 확인 불가, 차단.",
        }
        typer.echo(_json.dumps(out))
        raise typer.Exit(0) from None

    sentinel_text = sentinel.read_text(encoding="utf-8") if sentinel.exists() else ""
    decision = decide_ladder(
        sentinel_text=sentinel_text,
        forward_verdict=verdict,
        live_growth=growth,
        account_nav_usd=account_nav,
        live_config=live_cfg,
        validated_config=validated_cfg,
        kill_switch_present=kill_switch.exists(),
        today=_dt.now(UTC).date(),
        dd_budget_pct=_Dec(str(dd_budget_pct)),
    )

    if decision.sentinel_changes and write_sentinel:
        declared = (
            frozenset({BoundarySurface.LOSS_BUDGET})
            if _Dec(str(dd_budget_pct)) != _Dec("20.0")
            else frozenset()
        )
        _assert_autonomous_write_allowed(
            summary=f"capital ladder write sentinel action={decision.action}",
            paths=(sentinel,),
            requested_level=AutonomyLevel.CAPITAL_SCALING,
            declared_surfaces=declared,
        )
        sentinel.write_text(decision.new_sentinel_text, encoding="utf-8")

    if output_format == "json":
        out = decision.to_json_dict()
        out["edge_source"] = edge_source  # standard | anchored | both | none (포렌식)
        typer.echo(_json.dumps(out))
    else:
        typer.echo(
            f"[{decision.action}] rung {decision.current_rung}"
            f"→{decision.target_rung}: {decision.reason} (edge={edge_source})"
        )


@app.command("reassign-decide")
def reassign_decide_cmd(
    leaderboard_json: Path = typer.Option(
        ...,
        "--leaderboard-json",
        help="forward_tournament_probe --json 출력 파일(challenger_key/incumbent_key/"
        "champion_multiplicity_robust 포함). 없거나 못 읽으면 도전자 없음으로 처리(HOLD).",
    ),
    canary_verdict: str = typer.Option(
        "",
        "--canary-verdict",
        help="챔피언에 대한 하드닝 캐너리(스펙 007) 결과: PASS | FAIL | (빈값=미실행). "
        "PASS 가 아니면 ④ 게이트 미통과 → WAIT_CANARY(라이브 무변경).",
    ),
    execution_feedback_json: Path | None = typer.Option(
        None,
        "--execution-feedback-json",
        help="선택: opportunity-monitor JSON. 재지정 결정 증거에 포함하되 게이트를 우회하지 않음.",
    ),
    kill_switch: Path = typer.Option(
        Path("automation/AUTOARM_DISABLED"),
        "--kill-switch",
        help="존재하면 자동 재지정 정지(운영자 킬스위치) → DISABLED.",
    ),
    live_portfolio: Path = typer.Option(
        Path("deploy/canary-live-portfolio.toml"),
        "--live-portfolio",
        help="재지정이 교체하는 라이브 설정(rebalance-live-canary.yml 이 읽음).",
    ),
    challenger_portfolio: Path = typer.Option(
        None,
        "--challenger-portfolio",
        help="챔피언 전략 설정. 생략하면 challenger_key → TRACK_DEPLOY_CONFIGS 로 유도.",
    ),
    account_nav_json: Path = typer.Option(
        None,
        "--account-nav-json",
        help="account-nav --json 출력(rung 0 센티넬에 기록할 실계좌 NAV). 없으면 0.",
    ),
    sentinel: Path = typer.Option(
        Path("automation/rebalance-live.request"),
        "--sentinel",
        help="무장 센티넬 — REASSIGN + --write-config 시 rung 0(무장 해제)으로 덮어쓴다.",
    ),
    run_seq: int = typer.Option(
        None,
        "--run-seq",
        help="rung 0 센티넬 run_seq. 생략하면 현재 센티넬 run_seq+1(없으면 1).",
    ),
    dd_budget_pct: float = typer.Option(
        20.0,
        "--dd-budget-pct",
        help="운영자 낙폭 예산 %(센티넬 기록용, 2026-06-11 위임 기본 20).",
    ),
    write_config: bool = typer.Option(
        False,
        "--write-config",
        help="REASSIGN 이고 안전 가드 통과 시 새 라이브 설정 + rung 0 센티넬을 디스크에 쓴다.",
    ),
    output_format: str = typer.Option("json", "--format", help="json | text."),
) -> None:
    """스펙 055 — 자율 전략 재지정 결정+실행(읽기 전용 판정; --write-config 시에만 파일 기록).

    forward 토너먼트 리더보드 + 하드닝 캐너리 결과 → 5중 게이트(decide_reassignment).
    REASSIGN 이면 챔피언 전략을 라이브 설정에 이식 + 자본 사다리 rung 0 리셋(build_reassignment).
    안전 가드(헌법 II): 챔피언 유니버스가 라이브 화이트리스트 밖이면 실행 차단(운영자 게이트).
    주문 0건·돈 0 이동 — 실주문은 재무장(사다리) 후 시장시간 스케줄에서만.
    """
    import json as _json
    from datetime import UTC
    from datetime import datetime as _dt
    from decimal import Decimal as _Dec

    from auto_invest.analytics.forward_tournament import (
        OBS_HEALTH_BLOCKED,
        TournamentLeaderboard,
    )
    from auto_invest.portfolio.auto_reassign import ACTION_REASSIGN, decide_reassignment
    from auto_invest.portfolio.reassign_exec import (
        TRACK_DEPLOY_CONFIGS,
        ReassignExecError,
        build_reassignment,
    )

    def _read_json(path: Path | None) -> dict | None:
        if path is None:
            return None
        try:
            return _json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    board = _read_json(leaderboard_json)
    if board is None:
        board = {
            "observation_health": OBS_HEALTH_BLOCKED,
            "observation_note": (
                f"leaderboard_json '{leaderboard_json}' 를 읽지 못함 — 재지정 입력 품질 차단."
            ),
        }
    observation_health = str(board.get("observation_health") or OBS_HEALTH_BLOCKED)
    leaderboard = TournamentLeaderboard(
        schema_version=str(board.get("schema_version", "1.0")),
        as_of_utc=board.get("as_of_utc"),
        rows=[],  # 결정은 challenger/incumbent/multiplicity 만 읽음(순위 행 불필요).
        champion_key=board.get("champion_key"),
        incumbent_key=board.get("incumbent_key"),
        challenger_key=board.get("challenger_key"),
        headline=str(board.get("headline", "")),
        note=str(board.get("note", "")),
        comparable_count=int(board.get("comparable_count", 0) or 0),
        adjusted_dsr_threshold=None,
        champion_multiplicity_robust=board.get("champion_multiplicity_robust"),
        track_count=int(board.get("track_count", 0) or 0),
        known_count=int(board.get("known_count", 0) or 0),
        unknown_count=int(board.get("unknown_count", 0) or 0),
        max_n_obs=board.get("max_n_obs"),
        min_n_obs=board.get("min_n_obs"),
        lagging_keys=tuple(board.get("lagging_keys") or ()),
        observation_health=observation_health,
        observation_note=str(board.get("observation_note", "")),
    )

    decision = decide_reassignment(
        leaderboard=leaderboard,
        canary_verdict=(canary_verdict.strip() or None),
        kill_switch_present=kill_switch.exists(),
        execution_feedback=_read_json(execution_feedback_json),
    )
    out: dict = decision.to_json_dict()
    out["wrote_files"] = False

    if decision.action == ACTION_REASSIGN:
        ck = decision.challenger_key or ""
        chal_path = challenger_portfolio or (
            Path(TRACK_DEPLOY_CONFIGS[ck]) if ck in TRACK_DEPLOY_CONFIGS else None
        )
        # 실계좌 NAV(센티넬 기록용 — rung 0 자본은 NAV 무관하게 0).
        nav_doc = _read_json(account_nav_json)
        nav = _Dec("0")
        if isinstance(nav_doc, dict) and nav_doc.get("total_value_usd") is not None:
            try:
                nav = _Dec(str(nav_doc["total_value_usd"]))
            except ArithmeticError:
                nav = _Dec("0")
        # run_seq: 명시값 우선, 없으면 현 센티넬 +1(없으면 1).
        seq = run_seq
        if seq is None:
            cur_seq = None
            if sentinel.exists():
                import re as _re

                m = _re.search(
                    r"^run_seq:\s*(\d+)\s*$",
                    sentinel.read_text(encoding="utf-8"),
                    _re.MULTILINE,
                )
                cur_seq = int(m.group(1)) if m else None
            seq = (cur_seq + 1) if cur_seq is not None else 1
        try:
            if chal_path is None:
                raise ReassignExecError(
                    f"challenger_key '{ck}' 의 deploy 설정 경로를 찾을 수 없음 — 거부."
                )
            execution = build_reassignment(
                decision=decision,
                live_text=live_portfolio.read_text(encoding="utf-8"),
                challenger_text=chal_path.read_text(encoding="utf-8"),
                account_nav_usd=nav,
                run_seq=seq,
                dd_budget_pct=_Dec(str(dd_budget_pct)),
                rung_entered=_dt.now(UTC).date(),
                now=_dt.now(UTC),
            )
            out["execution"] = execution.to_json_dict()
            if write_config:
                declared = (
                    frozenset({BoundarySurface.LOSS_BUDGET})
                    if _Dec(str(dd_budget_pct)) != _Dec("20.0")
                    else frozenset()
                )
                _assert_autonomous_write_allowed(
                    summary=(
                        "strategy reassignment write live config and rung0 sentinel "
                        f"challenger={execution.challenger_key}"
                    ),
                    paths=(live_portfolio, sentinel),
                    requested_level=AutonomyLevel.STRATEGY_REASSIGNMENT,
                    declared_surfaces=declared,
                )
                live_portfolio.write_text(
                    execution.new_live_config_text, encoding="utf-8"
                )
                sentinel.write_text(execution.rung0_sentinel_text, encoding="utf-8")
                out["wrote_files"] = True
        except (ReassignExecError, OSError) as e:
            # 5중 게이트는 통과했으나 실행 안전 가드(거래집합 확대 등)·I/O 가 막음 →
            # 라이브 무변경(파일 미기록). 운영자 게이트 필요할 수 있음.
            out["execution_blocked"] = str(e)

    if output_format == "json":
        typer.echo(_json.dumps(out, ensure_ascii=False))
    else:
        extra = ""
        if out.get("execution_blocked"):
            extra = f" [실행 차단: {out['execution_blocked']}]"
        elif decision.action == ACTION_REASSIGN:
            extra = f" [wrote_files={out['wrote_files']}]"
        typer.echo(f"[{decision.action}] {decision.reason}{extra}")


@app.command("reassign-challenger-path")
def reassign_challenger_path_cmd(
    leaderboard_json: Path = typer.Option(
        ..., "--leaderboard-json", help="forward_tournament_probe --json 출력 파일."
    ),
) -> None:
    """리더보드의 challenger_key → 챔피언 deploy 설정 경로를 출력(없으면 빈 줄).

    워크플로가 캐너리를 돌릴 *챔피언 설정 파일*을 알아내는 단일 출처 — 트랙 key → deploy toml
    매핑(TRACK_DEPLOY_CONFIGS)이 YAML 에 중복되지 않게 한다. 도전자 없으면 빈 출력(재지정 없음).
    """
    import json as _json

    from auto_invest.analytics.forward_tournament import OBS_HEALTH_OK
    from auto_invest.portfolio.reassign_exec import TRACK_DEPLOY_CONFIGS

    try:
        board = _json.loads(leaderboard_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        typer.echo("")
        return
    if (board or {}).get("observation_health") != OBS_HEALTH_OK:
        typer.echo("")
        return
    ck = (board or {}).get("challenger_key")
    typer.echo(TRACK_DEPLOY_CONFIGS.get(ck, "") if ck else "")


@app.command("canary-portfolio")
def canary_portfolio_cmd(
    portfolio: Path = typer.Option(
        ..., "--portfolio", help="검증할 챔피언 포트폴리오 설정([portfolio] TOML)."
    ),
    history_root: Path = typer.Option(
        Path("data/history"),
        "--history-root",
        help="스펙 008 ingest-history 가 만든 CSV 데이터셋 루트.",
    ),
    bars_db: Path = typer.Option(
        None,
        "--bars-db",
        help="라이브/페이퍼 워커의 price_bars SQLite DB. 주면 CSV 대신 인스턴스 바로 검증 "
        "(토너먼트·라이브와 같은 바 — 폐회로가 인스턴스 데이터로 실제로 닫힌다).",
    ),
    bars_timeframe: str = typer.Option(
        "1d", "--bars-timeframe", help="--bars-db 의 timeframe(일봉 기본 1d)."
    ),
    window_days: int = typer.Option(
        45, "--window-days", help="낙폭 측정 정상 윈도우 거래일 수(L3 최소 45)."
    ),
    tier: str = typer.Option("L3", "--tier", help="밴드 tier(L2/L3/L4). 재지정 기본 L3."),
    bands_toml: Path = typer.Option(
        None,
        "--bands-toml",
        help="합격 밴드 TOML. 기본은 재지정 전용(config/canary_bands_reassign.toml).",
    ),
    db_path: Path = typer.Option(Path("data/auto_invest.db"), "--db", help="감사 로그 DB."),
    halt_path: Path = typer.Option(Path("data/halt.flag"), "--halt-path", help="halt 깃발."),
    shocks_toml: Path = typer.Option(
        None, "--shocks-toml", help="합성 충격 설정(기본 config/synthetic_shocks.toml)."
    ),
    capital: float = typer.Option(
        12000.0, "--capital", help="백테스트 사이징 자본 USD(페이퍼 — 돈 0 이동)."
    ),
    skip_fuzz: bool = typer.Option(
        False, "--skip-fuzz", help="퍼즈 패스 생략(테스트 전용 — 프로덕션 캐너리는 퍼즈 필수)."
    ),
    skip_shock: bool = typer.Option(
        False, "--skip-shock", help="충격 패스 생략(테스트 전용 — 프로덕션은 충격 필수)."
    ),
    output_format: str = typer.Option("json", "--format", help="json | text."),
) -> None:
    """스펙 055 ④ 게이트 — 포트폴리오 챔피언을 하드닝 캐너리로 검증(PASS=exit 0, FAIL=exit 1).

    검증된 포트폴리오 백테스트 엔진으로 챔피언 전략을 최근 윈도우 + 실제 과거 급락 윈도우(합성
    충격) + K1 게이트 퍼즈로 돌려, 스펙 007 의 같은 5지표로 PASS/FAIL 을 낸다. 주문 0건·돈 0.
    이 verdict 가 reassign-decide --canary-verdict 입력(재지정 ④ 게이트)이 된다.
    """
    import json as _json
    from datetime import date as _date
    from decimal import Decimal as _Dec

    from auto_invest.backtest.data_source import (
        CSVDataSource,
        SqliteBarDataSource,
        latest_dataset_dir,
    )
    from auto_invest.canary.portfolio_harness import (
        DEFAULT_REASSIGN_BANDS_PATH,
        PortfolioCanaryInputs,
        run_portfolio_canary,
    )
    from auto_invest.canary.run import EXIT_COVERAGE, EXIT_FAILED, EXIT_OK, EXIT_USAGE
    from auto_invest.persistence import db as _db

    try:
        caps, whitelist, port_cfg = _load_portfolio_for_backtest(portfolio, env=None)
    except ConfigError as e:
        typer.echo(f"포트폴리오 설정 로드 실패: {e}", err=True)
        raise typer.Exit(EXIT_USAGE) from None

    # 바 출처: --bars-db(인스턴스 price_bars) 우선, 없으면 CSV 데이터셋.
    bars_conn = None
    if bars_db is not None:
        bars_conn = _db.get_connection(bars_db)
        data_source = SqliteBarDataSource(bars_conn, timeframe=bars_timeframe)
    else:
        latest = latest_dataset_dir(history_root)
        if latest is None:
            typer.echo(
                f"{history_root} 아래 데이터셋 없음 — 먼저 ingest-history 실행", err=True
            )
            raise typer.Exit(EXIT_COVERAGE)
        data_source = CSVDataSource(latest)

    # 윈도우: 유니버스 심볼의 가용 세션 합집합에서 최근 window_days 거래일.
    sessions: set[_date] = set()
    for sym in port_cfg.universe:
        sessions.update(data_source.session_dates(sym))
    if not sessions:
        typer.echo(
            f"데이터셋에 유니버스 {list(port_cfg.universe)} 세션 없음 — 백필 필요", err=True
        )
        if bars_conn is not None:
            bars_conn.close()
        raise typer.Exit(EXIT_COVERAGE)
    ordered = sorted(sessions)
    window = ordered[-window_days:] if len(ordered) >= window_days else ordered
    date_start, date_end = window[0], window[-1]

    inputs = PortfolioCanaryInputs(
        config=port_cfg,
        caps=caps,
        whitelist=whitelist,
        data_source=data_source,
        date_start=date_start,
        date_end=date_end,
        halt_path=halt_path,
        total_capital_usd=_Dec(str(capital)),
        shocks_toml=shocks_toml,
        today=date_end,
    )

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _db.get_connection(db_path)
    _db.migrate(conn)
    try:
        outcome = run_portfolio_canary(
            inputs,
            audit_conn=conn,
            tier=tier,
            bands_path=bands_toml or DEFAULT_REASSIGN_BANDS_PATH,
            skip_fuzz=skip_fuzz,
            skip_shock=skip_shock,
        )
    finally:
        conn.close()
        if bars_conn is not None:
            bars_conn.close()

    if output_format == "json":
        out = outcome.to_json_dict()
        out["portfolio_id"] = port_cfg.id
        out["window_start"] = date_start.isoformat()
        out["window_end"] = date_end.isoformat()
        typer.echo(_json.dumps(out, ensure_ascii=False))
    else:
        typer.echo(
            f"[{outcome.verdict}] {port_cfg.id} 낙폭={outcome.candidate_drawdown_pct:.2f}% "
            f"충격위반={outcome.shock_violations} 무결성={outcome.audit_integrity_count} "
            f"실패지표={outcome.failing_metrics}"
        )
    raise typer.Exit(EXIT_OK if outcome.passed else EXIT_FAILED)


@app.command("evolution-scan")
def evolution_scan_cmd(
    evidence_dir: Path = typer.Option(
        ...,
        "--evidence-dir",
        help="Collected evidence markdown directory.",
    ),
    ledger_json: Path | None = typer.Option(
        None,
        "--ledger-json",
        help="Existing learning ledger JSON. Missing file means empty ledger.",
    ),
    summary_out: Path | None = typer.Option(
        None,
        "--summary-out",
        help="Markdown latest-run summary output path.",
    ),
    json_out: Path | None = typer.Option(
        None,
        "--json-out",
        help="Machine-readable summary JSON output path.",
    ),
    ledger_out: Path | None = typer.Option(
        None,
        "--ledger-out",
        help="Updated learning ledger JSON output path.",
    ),
    candidate_backlog_out: Path | None = typer.Option(
        None,
        "--candidate-backlog-out",
        help="Candidate backlog JSON output path.",
    ),
    output_format: str = typer.Option(
        "text",
        "--format",
        help="stdout format: text or json.",
    ),
    now: str | None = typer.Option(
        None,
        "--now",
        help="As-of timestamp ISO-8601 UTC for deterministic tests.",
    ),
    run_id: str = typer.Option(
        "local",
        "--run-id",
        help="Run identifier recorded in the summary.",
    ),
) -> None:
    """Run the read-only autonomous evolution scan.

    The command reads already-collected evidence files. It does not call broker
    APIs, place orders, modify capital, widen whitelists, relax caps, or swap
    live strategies.
    """
    import json as _json
    import subprocess as _subprocess
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime

    from auto_invest.analytics.evolution_loop import (
        DEFAULT_EVIDENCE_REQUIREMENTS,
        scan_evolution,
        write_summary_artifacts,
    )

    def _read_json(path: Path | None) -> dict | None:
        if path is None:
            return None
        try:
            raw = path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            return None
        try:
            data = _json.loads(raw)
        except _json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def _read_evidence(path: Path) -> dict[str, str | None]:
        evidence: dict[str, str | None] = {}
        for req in DEFAULT_EVIDENCE_REQUIREMENTS:
            item = path / f"{req.key}.md"
            try:
                evidence[req.key] = item.read_text(encoding="utf-8")
            except (FileNotFoundError, OSError):
                evidence[req.key] = None
        for item in sorted(path.glob("*.md")):
            if item.stem in evidence:
                continue
            try:
                evidence[item.stem] = item.read_text(encoding="utf-8")
            except OSError:
                evidence[item.stem] = None
        return evidence

    def _parse_now(text: str | None):
        if not text:
            return _datetime.now(_UTC)
        parsed = _datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=_UTC)
        return parsed.astimezone(_UTC)

    def _commit() -> str:
        try:
            return _subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                text=True,
                stderr=_subprocess.DEVNULL,
            ).strip()
        except (OSError, _subprocess.CalledProcessError):
            return "unknown"

    if output_format not in {"text", "json"}:
        typer.echo("--format 은 text 또는 json 이어야 합니다.", err=True)
        raise typer.Exit(2)

    summary = scan_evolution(
        _read_evidence(evidence_dir),
        ledger_doc=_read_json(ledger_json),
        now=_parse_now(now),
        commit=_commit(),
        run_id=run_id,
    )
    write_summary_artifacts(
        summary,
        summary_out=summary_out,
        json_out=json_out,
        ledger_out=ledger_out,
        candidate_backlog_out=candidate_backlog_out,
    )
    if output_format == "json":
        typer.echo(_json.dumps(summary.as_dict(), ensure_ascii=False))
    else:
        typer.echo(summary.as_markdown())


@app.command("candidate-factory")
def candidate_factory_cmd(
    candidate_backlog: Path = typer.Option(
        ...,
        "--candidate-backlog",
        help="Candidate backlog JSON from autonomous evolution or factory sidecar.",
    ),
    promotion_summary: Path | None = typer.Option(
        None,
        "--promotion-summary",
        help="Optional promotion summary JSON for source stage context.",
    ),
    result_evidence: Path | None = typer.Option(
        None,
        "--result-evidence",
        help="Optional machine-readable candidate result evidence JSON.",
    ),
    summary_out: Path | None = typer.Option(
        None,
        "--summary-out",
        help="Markdown latest-run summary output path.",
    ),
    json_out: Path | None = typer.Option(
        None,
        "--json-out",
        help="Machine-readable factory summary JSON output path.",
    ),
    enriched_backlog_out: Path | None = typer.Option(
        None,
        "--enriched-backlog-out",
        help="Candidate backlog with factory promotion_evidence patches.",
    ),
    package_plan_out: Path | None = typer.Option(
        None,
        "--package-plan-out",
        help="Machine-readable candidate implementation package plan.",
    ),
    output_format: str = typer.Option(
        "text",
        "--format",
        help="stdout format: text or json.",
    ),
    now: str | None = typer.Option(
        None,
        "--now",
        help="As-of timestamp ISO-8601 UTC for deterministic tests.",
    ),
    run_id: str = typer.Option(
        "local",
        "--run-id",
        help="Run identifier recorded in the summary.",
    ),
) -> None:
    """Build candidate implementation packages without live side effects.

    The command converts every autonomous candidate into a deterministic
    backtest/validation package and merges machine-readable result evidence
    into promotion_evidence only when the evidence explicitly passes.
    It does not call broker APIs, place orders, modify capital, widen
    whitelists, relax caps, swap live strategies, or edit sentinels.
    """
    import json as _json
    import subprocess as _subprocess
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime

    from auto_invest.analytics.candidate_factory import (
        build_candidate_factory_run,
        write_candidate_factory_artifacts,
    )

    def _read_json(path: Path | None) -> dict | None:
        if path is None:
            return None
        try:
            raw = path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            return None
        try:
            data = _json.loads(raw)
        except _json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def _parse_now(text: str | None):
        if not text:
            return _datetime.now(_UTC)
        parsed = _datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=_UTC)
        return parsed.astimezone(_UTC)

    def _commit() -> str:
        try:
            return _subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                text=True,
                stderr=_subprocess.DEVNULL,
            ).strip()
        except (OSError, _subprocess.CalledProcessError):
            return "unknown"

    if output_format not in {"text", "json"}:
        typer.echo("--format 은 text 또는 json 이어야 합니다.", err=True)
        raise typer.Exit(2)

    run = build_candidate_factory_run(
        candidate_backlog=_read_json(candidate_backlog),
        promotion_summary=_read_json(promotion_summary),
        result_evidence=_read_json(result_evidence),
        now=_parse_now(now),
        commit=_commit(),
        run_id=run_id,
    )
    write_candidate_factory_artifacts(
        run,
        summary_out=summary_out,
        json_out=json_out,
        enriched_backlog_out=enriched_backlog_out,
        package_plan_out=package_plan_out,
    )
    if output_format == "json":
        typer.echo(_json.dumps(run.as_dict(), ensure_ascii=False))
    else:
        typer.echo(run.as_markdown())


@app.command("candidate-results")
def candidate_results_cmd(
    package_plan: Path = typer.Option(
        ...,
        "--package-plan",
        help="Candidate implementation package plan JSON.",
    ),
    summary_out: Path | None = typer.Option(
        None,
        "--summary-out",
        help="Markdown latest-run summary output path.",
    ),
    json_out: Path | None = typer.Option(
        None,
        "--json-out",
        help="Machine-readable executor summary JSON output path.",
    ),
    results_out: Path | None = typer.Option(
        None,
        "--results-out",
        help="Machine-readable candidate result evidence JSON output path.",
    ),
    timeout_seconds: int = typer.Option(
        120,
        "--timeout-seconds",
        help="Maximum seconds per package command.",
    ),
    output_format: str = typer.Option(
        "text",
        "--format",
        help="stdout format: text or json.",
    ),
    now: str | None = typer.Option(
        None,
        "--now",
        help="As-of timestamp ISO-8601 UTC for deterministic tests.",
    ),
    run_id: str = typer.Option(
        "local",
        "--run-id",
        help="Run identifier recorded in the summary.",
    ),
) -> None:
    """Execute safe candidate validation packages and emit result evidence.

    The command runs only allowlisted no-live validation commands. It may
    create validation artifacts, but blocks live-order, broker, capital,
    whitelist/caps, sentinel, SSH, and secret-bearing surfaces before execution.
    """
    import json as _json
    import subprocess as _subprocess
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime

    from auto_invest.analytics.candidate_result_executor import (
        build_candidate_result_executor_run,
        write_candidate_result_artifacts,
    )

    def _read_json(path: Path | None) -> dict | None:
        if path is None:
            return None
        try:
            raw = path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            return None
        try:
            data = _json.loads(raw)
        except _json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def _parse_now(text: str | None):
        if not text:
            return _datetime.now(_UTC)
        parsed = _datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=_UTC)
        return parsed.astimezone(_UTC)

    def _commit() -> str:
        try:
            return _subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                text=True,
                stderr=_subprocess.DEVNULL,
            ).strip()
        except (OSError, _subprocess.CalledProcessError):
            return "unknown"

    if output_format not in {"text", "json"}:
        typer.echo("--format 은 text 또는 json 이어야 합니다.", err=True)
        raise typer.Exit(2)

    run = build_candidate_result_executor_run(
        package_plan=_read_json(package_plan),
        now=_parse_now(now),
        commit=_commit(),
        run_id=run_id,
        timeout_seconds=timeout_seconds,
    )
    write_candidate_result_artifacts(
        run,
        summary_out=summary_out,
        json_out=json_out,
        results_out=results_out,
    )
    if output_format == "json":
        typer.echo(_json.dumps(run.as_dict(), ensure_ascii=False))
    else:
        typer.echo(run.as_markdown())


@app.command("promotion-scan")
def promotion_scan_cmd(
    evidence_dir: Path = typer.Option(
        ...,
        "--evidence-dir",
        help="Collected promotion evidence directory.",
    ),
    summary_out: Path | None = typer.Option(
        None,
        "--summary-out",
        help="Markdown latest-run summary output path.",
    ),
    json_out: Path | None = typer.Option(
        None,
        "--json-out",
        help="Machine-readable summary JSON output path.",
    ),
    queue_out: Path | None = typer.Option(
        None,
        "--queue-out",
        help="Machine-readable promotion queue JSON output path.",
    ),
    output_format: str = typer.Option(
        "text",
        "--format",
        help="stdout format: text or json.",
    ),
    now: str | None = typer.Option(
        None,
        "--now",
        help="As-of timestamp ISO-8601 UTC for deterministic tests.",
    ),
    run_id: str = typer.Option(
        "local",
        "--run-id",
        help="Run identifier recorded in the summary.",
    ),
) -> None:
    """Run the read-only autonomous promotion scan.

    The command classifies evolution candidates into backtest, OOS, forward,
    canary, or existing-gate stages. It does not call broker APIs, place orders,
    modify capital, widen whitelists, relax caps, swap live strategies, or edit
    sentinels.
    """
    import json as _json
    import subprocess as _subprocess
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime

    from auto_invest.analytics.promotion_loop import (
        scan_promotion,
        write_promotion_artifacts,
    )

    def _read_json(path: Path) -> dict | None:
        try:
            raw = path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            return None
        try:
            data = _json.loads(raw)
        except _json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def _read_evidence(path: Path) -> dict[str, str | None]:
        evidence: dict[str, str | None] = {}
        for item in sorted(path.glob("*.md")):
            try:
                evidence[item.stem] = item.read_text(encoding="utf-8")
            except OSError:
                evidence[item.stem] = None
        return evidence

    def _parse_now(text: str | None):
        if not text:
            return _datetime.now(_UTC)
        parsed = _datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=_UTC)
        return parsed.astimezone(_UTC)

    def _commit() -> str:
        try:
            return _subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                text=True,
                stderr=_subprocess.DEVNULL,
            ).strip()
        except (OSError, _subprocess.CalledProcessError):
            return "unknown"

    if output_format not in {"text", "json"}:
        typer.echo("--format 은 text 또는 json 이어야 합니다.", err=True)
        raise typer.Exit(2)

    summary = scan_promotion(
        candidate_backlog=_read_json(evidence_dir / "candidate_backlog.json"),
        evolution_summary=_read_json(evidence_dir / "evolution_summary.json"),
        evidence_texts=_read_evidence(evidence_dir),
        now=_parse_now(now),
        commit=_commit(),
        run_id=run_id,
    )
    write_promotion_artifacts(
        summary,
        summary_out=summary_out,
        json_out=json_out,
        queue_out=queue_out,
    )
    if output_format == "json":
        typer.echo(_json.dumps(summary.as_dict(), ensure_ascii=False))
    else:
        typer.echo(summary.as_markdown())


@app.command("promotion-actions")
def promotion_actions_cmd(
    promotion_summary: Path = typer.Option(
        ...,
        "--promotion-summary",
        help="Machine-readable promotion summary JSON.",
    ),
    forward_registry: Path = typer.Option(
        ...,
        "--forward-registry",
        help="Current promotion forward registry JSON.",
    ),
    canary_submissions: Path = typer.Option(
        ...,
        "--canary-submissions",
        help="Current promotion canary submissions JSON.",
    ),
    summary_out: Path | None = typer.Option(
        None,
        "--summary-out",
        help="Markdown latest-run summary output path.",
    ),
    json_out: Path | None = typer.Option(
        None,
        "--json-out",
        help="Machine-readable promotion actions JSON output path.",
    ),
    forward_registry_out: Path | None = typer.Option(
        None,
        "--forward-registry-out",
        help="Next promotion forward registry JSON output path.",
    ),
    canary_submissions_out: Path | None = typer.Option(
        None,
        "--canary-submissions-out",
        help="Next promotion canary submissions JSON output path.",
    ),
    output_format: str = typer.Option(
        "text",
        "--format",
        help="stdout format: text or json.",
    ),
    now: str | None = typer.Option(
        None,
        "--now",
        help="As-of timestamp ISO-8601 UTC for deterministic tests.",
    ),
    run_id: str = typer.Option(
        "local",
        "--run-id",
        help="Run identifier recorded in the summary.",
    ),
) -> None:
    """Build promotion forward/canary action state without live orders.

    The command converts a promotion summary into promotion-only forward paper
    registrations and hardened canary submissions. It does not call broker APIs,
    place orders, modify capital, edit live strategy config, or touch sentinels.
    """
    import json as _json
    import subprocess as _subprocess
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime

    from auto_invest.analytics.promotion_actions import (
        build_promotion_actions,
        write_promotion_action_artifacts,
    )

    def _read_json(path: Path) -> dict | None:
        try:
            raw = path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            return None
        try:
            data = _json.loads(raw)
        except _json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def _parse_now(text: str | None):
        if not text:
            return _datetime.now(_UTC)
        parsed = _datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=_UTC)
        return parsed.astimezone(_UTC)

    def _commit() -> str:
        try:
            return _subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                text=True,
                stderr=_subprocess.DEVNULL,
            ).strip()
        except (OSError, _subprocess.CalledProcessError):
            return "unknown"

    if output_format not in {"text", "json"}:
        typer.echo("--format 은 text 또는 json 이어야 합니다.", err=True)
        raise typer.Exit(2)

    run = build_promotion_actions(
        promotion_summary=_read_json(promotion_summary),
        forward_registry=_read_json(forward_registry),
        canary_submissions=_read_json(canary_submissions),
        now=_parse_now(now),
        commit=_commit(),
        run_id=run_id,
    )
    write_promotion_action_artifacts(
        run,
        summary_out=summary_out,
        json_out=json_out,
        forward_registry_out=forward_registry_out,
        canary_submissions_out=canary_submissions_out,
    )
    if output_format == "json":
        typer.echo(_json.dumps(run.as_dict(), ensure_ascii=False))
    else:
        typer.echo(run.as_markdown())

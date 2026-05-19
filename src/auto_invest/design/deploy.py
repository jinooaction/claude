"""Spec 010 T024 + 후속 PR — 운영자 OK 인터랙티브 + 라이브 자동 시작.

검증 통과 후 typer.prompt로 OK/y/예/yes 한 줄 받음. 60초 타임아웃. 거부 또는
타임아웃이면 RULE_DESIGN_REJECTED(reason="operator_declined") audit.

OK 받으면 새 라이브 worker subprocess 시작. `RULE_DESIGN_DEPLOYED` audit row
1건 + 새 worker의 WORKER_STARTED row 1건 짝맞춤. subprocess는 detach되어
운영자가 design 명령을 종료해도 live worker는 계속 실행.
"""

from __future__ import annotations

import signal
import sqlite3
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import typer

_OK_TOKENS = {"OK", "ok", "Ok", "y", "Y", "yes", "Yes", "예"}


class _TimeoutError(Exception):
    pass


def _signal_alarm(seconds: int) -> None:
    def _handler(signum, frame):  # noqa: ARG001
        raise _TimeoutError()

    signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)


def prompt_operator_ok(
    timeout_seconds: int = 60,
    *,
    prompt_fn: Callable[[str], str] = typer.prompt,
) -> bool:
    """검증 통과 후 운영자가 OK 한 줄 답하는지 확인.

    - `timeout_seconds` 안에 응답 없으면 False (거부 처리).
    - 응답이 OK/y/yes/예 중 하나와 정확히 일치해야 True.
    - 그 외는 모두 거부.

    `prompt_fn`은 테스트에서 주입 가능 — typer.prompt를 mock하지 않고 직접 콜.
    """
    try:
        _signal_alarm(timeout_seconds)
        answer = prompt_fn(
            "이 룰로 라이브 시작하려면 'OK' 또는 'y' 또는 '예' 또는 'yes'를 "
            "60초 안에 입력해주세요"
        )
    except _TimeoutError:
        return False
    finally:
        signal.alarm(0)

    return answer.strip() in _OK_TOKENS


def write_auto_rules_file(toml_text: str, *, config_dir: Path) -> Path:
    """Claude가 생성한 TOML을 `config/rules_auto_<timestamp>.toml`에 저장.

    파일명에 timestamp가 들어가므로 여러 design 호출이 서로 다른 파일에 적힘.
    config_dir이 없으면 만든다.
    """
    config_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    path = config_dir / f"rules_auto_{ts}.toml"
    path.write_text(toml_text, encoding="utf-8")
    return path


def start_live_worker(
    *,
    rules_path: Path,
    capital_usd: Decimal,
    db_path: Path,
    halt_path: Path,
    env_file: Path | None,
    base_url: str,
    prices_path: Path,
    conn: sqlite3.Connection,
    poll_timeout_seconds: int = 30,
    cli_entry: list[str] | None = None,
    log_dir: Path | None = None,
) -> int | None:
    """라이브 worker subprocess를 띄우고 새 WORKER_STARTED row의 seq를 리턴.

    동작:
      1. `auto-invest run --config <rules_path> --capital <usd> ...`를 detach
         subprocess로 띄움 (start_new_session=True).
      2. audit_log를 polling — 새 WORKER_STARTED row(현재 max seq 이후로 생긴)가
         poll_timeout_seconds 안에 나타나는지 확인.
      3. 나타나면 그 seq 리턴. 안 나타나면 None 리턴 (호출자가 한글 보고).

    `cli_entry`는 테스트에서 주입 가능 — 기본은 `["python", "-m", "auto_invest"]`
    가 아니라 `["auto-invest"]` (entry point) 또는 sys.executable + 모듈 호출.
    """
    # 1. 현재 audit_log의 max seq 기록 — polling baseline.
    baseline = conn.execute(
        "SELECT COALESCE(MAX(seq), 0) AS m FROM audit_log",
    ).fetchone()["m"]

    # 2. subprocess args 조립.
    if cli_entry is None:
        cli_entry = [sys.executable, "-m", "auto_invest"]
    cmd = [
        *cli_entry,
        "run",
        "--config", str(rules_path),
        "--db", str(db_path),
        "--halt-path", str(halt_path),
        "--base-url", base_url,
        "--capital", str(capital_usd),
        "--prices", str(prices_path),
    ]
    if env_file is not None:
        cmd.extend(["--env-file", str(env_file)])

    # 3. log 파일 (subprocess stdout/stderr).
    if log_dir is None:
        log_dir = db_path.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"live_worker_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}.log"
    log_file = log_path.open("ab")

    # 4. Popen — start_new_session=True로 detach. 자식이 부모 죽음 영향 안 받음.
    subprocess.Popen(  # noqa: S603 — cmd는 우리가 제어
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    # 5. audit_log polling — 새 WORKER_STARTED row 등장 확인.
    deadline = time.time() + poll_timeout_seconds
    while time.time() < deadline:
        row = conn.execute(
            "SELECT seq FROM audit_log "
            "WHERE event_type = 'WORKER_STARTED' AND seq > ? "
            "ORDER BY seq LIMIT 1",
            (baseline,),
        ).fetchone()
        if row is not None:
            return int(row["seq"])
        time.sleep(0.5)
    return None

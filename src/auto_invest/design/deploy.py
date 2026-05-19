"""Spec 010 T024 — 운영자 OK 인터랙티브 + 라이브 자동 시작.

검증 통과 후 typer.prompt로 OK/y/예/yes 한 줄 받음. 60초 타임아웃. 거부 또는
타임아웃이면 RULE_DESIGN_REJECTED(reason="operator_declined") audit.

OK 받으면 새 라이브 worker 시작 (spec 001의 `auto-invest run` subprocess).
`RULE_DESIGN_DEPLOYED` audit row 1건 + 새 worker의 WORKER_STARTED row 1건 짝맞춤.
"""

from __future__ import annotations

import signal
from collections.abc import Callable

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

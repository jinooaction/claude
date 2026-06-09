"""Worker supervisor abstraction — spec 006 R-D1.

Two implementations:

- `SystemdSupervisor` calls `systemctl restart <unit>` via subprocess.
- `DryRunSupervisor` captures intents in-memory for tests and `--dry-run`.

The runner depends only on the `Supervisor` protocol.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class SupervisorResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


class Supervisor(Protocol):
    name: str

    def stop_worker(self) -> SupervisorResult:
        ...

    def start_worker(self) -> SupervisorResult:
        ...

    def is_running(self) -> bool:
        ...


@dataclass
class DryRunSupervisor:
    """Test/dry-run supervisor — never touches systemd."""

    name: str = "dryrun"
    _running: bool = True
    intents: list[str] = field(default_factory=list)

    def stop_worker(self) -> SupervisorResult:
        self.intents.append("stop")
        self._running = False
        return SupervisorResult(ok=True)

    def start_worker(self) -> SupervisorResult:
        self.intents.append("start")
        self._running = True
        return SupervisorResult(ok=True)

    def is_running(self) -> bool:
        return self._running


@dataclass
class SystemdSupervisor:
    """Production supervisor — invokes `systemctl` over subprocess.

    The deploy automation (`auto-invest-deploy.service`) runs as the unprivileged
    `auto-invest` user, so managing the worker unit needs an authorization path.
    polkit proved unreliable on the production host (the JS rule loads but the
    `manage-units` action still returns "Interactive authentication required"),
    so we use `sudo -n systemctl …` instead, scoped by a tight sudoers drop-in
    (`deploy/auto-invest-deploy.sudoers`) to ONLY the worker unit's stop/start/
    restart/is-active. `sudo -n` is deterministic (no JS evaluation) and works
    as long as the service does not set `NoNewPrivileges=true` (which blocks
    setuid). Running as root also works (sudo is a no-op for root).
    """

    unit: str = "auto-invest.service"
    name: str = "systemd"

    def _systemctl(self, *args: str) -> SupervisorResult:
        try:
            proc = subprocess.run(
                ["sudo", "-n", "systemctl", *args],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            return SupervisorResult(ok=False, stderr=str(exc), returncode=127)
        return SupervisorResult(
            ok=(proc.returncode == 0),
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
        )

    def stop_worker(self) -> SupervisorResult:
        return self._systemctl("stop", self.unit)

    def start_worker(self) -> SupervisorResult:
        return self._systemctl("start", self.unit)

    def is_running(self) -> bool:
        result = self._systemctl("is-active", self.unit)
        return result.ok and result.stdout.strip() == "active"

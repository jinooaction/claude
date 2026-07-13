from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "auto_invest"

BROKER_MUTATION_ALLOWLIST = {
    "place_order": {
        Path("src/auto_invest/execution/authority.py"),
    },
    "cancel_order": {
        Path("src/auto_invest/execution/authority.py"),
    },
}


def _python_files() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def _rel(path: Path) -> Path:
    return path.relative_to(ROOT)


def _mutating_broker_calls(tree: ast.AST) -> set[str]:
    calls: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in BROKER_MUTATION_ALLOWLIST:
            calls.add(node.func.id)
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in BROKER_MUTATION_ALLOWLIST
        ):
            calls.add(node.func.attr)
    return calls


def test_live_broker_mutations_are_only_called_from_canonical_paths():
    offenders: list[str] = []
    for path in _python_files():
        if _rel(path) == Path("src/auto_invest/broker/overseas.py"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for call_name in _mutating_broker_calls(tree):
            if _rel(path) not in BROKER_MUTATION_ALLOWLIST[call_name]:
                offenders.append(f"{_rel(path)} calls {call_name}()")

    assert offenders == []


def test_live_order_submission_remains_order_router_only():
    assert BROKER_MUTATION_ALLOWLIST["place_order"] == {
        Path("src/auto_invest/execution/authority.py")
    }


def test_live_broker_cancellation_remains_execution_authority_only():
    assert BROKER_MUTATION_ALLOWLIST["cancel_order"] == {
        Path("src/auto_invest/execution/authority.py")
    }

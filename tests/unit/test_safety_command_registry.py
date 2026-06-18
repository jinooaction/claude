from __future__ import annotations

import json

from typer.testing import CliRunner

from auto_invest.cli import app
from auto_invest.safety.autonomy import LEVEL_POLICIES, AutonomyLevel
from auto_invest.safety.command_registry import command_policies


def _registered_command_names() -> set[str]:
    names: set[str] = set()
    for command in app.registered_commands:
        names.add(command.name or command.callback.__name__.replace("_", "-"))
    for group in app.registered_groups:
        group_name = group.name
        assert group_name is not None
        for command in group.typer_instance.registered_commands:
            command_name = command.name or command.callback.__name__.replace("_", "-")
            names.add(f"{group_name} {command_name}")
    return names


def test_every_cli_command_has_safety_policy():
    assert _registered_command_names() == set(command_policies())


def test_command_policy_invariants():
    for policy in command_policies().values():
        if policy.can_place_order:
            assert policy.level.rank >= AutonomyLevel.BOUNDED_LIVE.rank
        if policy.can_scale_capital:
            assert policy.level.rank >= AutonomyLevel.CAPITAL_SCALING.rank
        if policy.can_reassign_strategy:
            assert policy.level.rank >= AutonomyLevel.STRATEGY_REASSIGNMENT.rank
        if policy.level is AutonomyLevel.SAFETY_BOUNDARY_CHANGE:
            level_policy = LEVEL_POLICIES[policy.level]
            assert not level_policy.autonomous_allowed
            assert level_policy.operator_approval_required
            assert policy.requires_operator_boundary


def test_safety_commands_json_cli():
    result = CliRunner().invoke(app, ["safety", "commands", "--format", "json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    commands = {row["name"]: row for row in payload["commands"]}
    assert commands["run"]["level"] == "A3"
    assert commands["run"]["can_place_order"] is True
    assert commands["status"]["level"] == "A0"
    assert commands["status"]["can_place_order"] is False


def test_safety_commands_bad_format_exits_2():
    result = CliRunner().invoke(app, ["safety", "commands", "--format", "xml"])
    assert result.exit_code == 2

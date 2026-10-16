"""Pure configuration counterexamples; never call Docker locally."""

import copy
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

SPEC = importlib.util.spec_from_file_location(
    "isolation_lab",
    Path(__file__).resolve().parents[2] / "scripts/intraday_runtime_isolation_lab.py",
)
lab = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lab)
LabError, guard = lab.LabError, lab.guard
start_checked, validate_container = lab.start_checked, lab.validate_container

IMAGE = "sha256:" + "a" * 64
CID = "b" * 64
ENV = ["PATH=/usr/local/bin:/usr/bin:/bin"]


def container():
    return {
        "Id": CID,
        "Image": IMAGE,
        "Path": "/usr/local/bin/python",
        "Args": ["-I", "-S", "-B", "/candidate/entry.py", "baseline"],
        "State": {"Status": "created", "Running": False, "Pid": 0},
        "Config": {
            "Entrypoint": ["/usr/local/bin/python", "-I", "-S", "-B", "/candidate/entry.py"],
            "Cmd": ["baseline"],
            "User": "65532:65532",
            "WorkingDir": "/candidate",
            "Env": ENV.copy(),
            "Image": IMAGE,
        },
        "HostConfig": {
            "ReadonlyRootfs": True,
            "Privileged": False,
            "NetworkMode": "none",
            "CapDrop": ["ALL"],
            "CapAdd": None,
            "SecurityOpt": ["no-new-privileges=true"],
            "Memory": 134217728,
            "NanoCpus": 1000000000,
            "PidsLimit": 64,
            "Binds": None,
            "Mounts": None,
            "Tmpfs": None,
            "Devices": [],
            "DeviceRequests": None,
            "VolumesFrom": None,
            "PidMode": "",
            "IpcMode": "private",
            "UTSMode": "",
            "UsernsMode": "",
        },
        "Mounts": [],
    }


def test_valid_created_configuration():
    validate_container(container(), CID, IMAGE, ENV, "baseline")


@pytest.mark.parametrize(
    "section,key,bad",
    [
        (None, "Image", "sha256:" + "c" * 64),
        (None, "Id", "c" * 64),
        (None, "Path", "/bin/sh"),
        (None, "Args", ["-c", "pass"]),
        (None, "Mounts", [{"RW": False}]),
        ("Config", "Entrypoint", ["/bin/sh"]),
        ("Config", "Cmd", ["other"]),
        ("Config", "User", "0"),
        ("Config", "WorkingDir", "/tmp"),
        ("Config", "Env", ENV + ["PYTHONPATH=/tmp"]),
        ("Config", "Image", "floating:latest"),
        ("HostConfig", "ReadonlyRootfs", False),
        ("HostConfig", "ReadonlyRootfs", 1),
        ("HostConfig", "Privileged", True),
        ("HostConfig", "NetworkMode", "host"),
        ("HostConfig", "CapDrop", []),
        ("HostConfig", "CapAdd", ["SYS_ADMIN"]),
        ("HostConfig", "SecurityOpt", []),
        ("HostConfig", "Memory", 0),
        ("HostConfig", "NanoCpus", True),
        ("HostConfig", "PidsLimit", 0),
        ("HostConfig", "Binds", ["/tmp:/tmp:ro"]),
        ("HostConfig", "Mounts", [{"Type": "bind"}]),
        ("HostConfig", "Tmpfs", {"/tmp": "rw"}),
        ("HostConfig", "Devices", [{"PathOnHost": "/dev/null"}]),
        ("HostConfig", "DeviceRequests", [{"Count": -1}]),
        ("HostConfig", "VolumesFrom", ["other"]),
        ("HostConfig", "PidMode", "host"),
        ("HostConfig", "IpcMode", "host"),
        ("HostConfig", "UTSMode", "host"),
        ("HostConfig", "UsernsMode", "host"),
        ("State", "Status", "running"),
        ("State", "Running", True),
        ("State", "Pid", 123),
    ],
)
def test_changed_setting_rejected_before_start(section, key, bad):
    observed = container()
    target = observed if section is None else observed[section]
    target[key] = bad
    call = Mock(return_value=(0, json.dumps([observed]), ""))
    with pytest.raises(LabError):
        start_checked(call, CID, IMAGE, ENV, "baseline")
    assert call.call_count == 1
    assert call.call_args.args[0][:2] == ["inspect", "--type=container"]


@pytest.mark.parametrize(
    "section,key",
    [(None, "Image"), ("Config", "Env"), ("HostConfig", "ReadonlyRootfs"), ("State", "Status")],
)
def test_missing_field_fails(section, key):
    obj = copy.deepcopy(container())
    del (obj if section is None else obj[section])[key]
    with pytest.raises(LabError):
        validate_container(obj, CID, IMAGE, ENV, "baseline")


@pytest.mark.parametrize(
    "env,system",
    [
        ({}, "Linux"),
        ({"GITHUB_ACTIONS": "true", "RUNNER_OS": "macOS"}, "Darwin"),
        ({"GITHUB_ACTIONS": "true", "RUNNER_OS": "Linux", "DOCKER_HOST": "tcp://host"}, "Linux"),
    ],
)
def test_local_or_remote_docker_guard(env, system):
    with pytest.raises(LabError):
        guard(env, system)


def test_guard_accepts_linux_runner_only():
    guard({"GITHUB_ACTIONS": "true", "RUNNER_OS": "Linux"}, "Linux")


@pytest.mark.parametrize(
    "key,empty", [("Mounts", None), ("Mounts", []), ("Tmpfs", None), ("Tmpfs", {})]
)
def test_moby_optional_empty_fields(key, empty):
    obj = container()
    obj["HostConfig"][key] = empty
    validate_container(obj, CID, IMAGE, ENV, "baseline")
    del obj["HostConfig"][key]
    validate_container(obj, CID, IMAGE, ENV, "baseline")


@pytest.mark.parametrize("raw", ["null", "[]", "{}", "[{},{}]", "invalid"])
def test_bad_inspect_never_starts(raw):
    call = Mock(return_value=(0, raw, ""))
    with pytest.raises(LabError):
        start_checked(call, CID, IMAGE, ENV, "baseline")
    assert call.call_count == 1


def test_valid_inspect_starts_same_id_once():
    call = Mock(side_effect=[(0, json.dumps([container()]), ""), (0, "fixture", "")])
    assert start_checked(call, CID, IMAGE, ENV, "baseline") == (0, "fixture", "")
    assert call.call_count == 2
    assert call.call_args.args[0] == ["start", "--attach", CID]


def test_local_cli_rejects_before_docker_lookup(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    lookup = Mock(side_effect=AssertionError("must not look up Docker"))
    monkeypatch.setattr(lab.shutil, "which", lookup)
    with pytest.raises(LabError):
        lab.run_lab(tmp_path / "report.json")
    assert not lookup.called and not (tmp_path / "report.json").exists()


def test_docker_user_env_precedes_image_defaults_without_changing_content():
    obj = container()
    obj["Args"][-1] = "environment_injection"
    obj["Config"]["Cmd"] = ["environment_injection"]
    obj["Config"]["Env"] = lab.INJECTION + ENV
    validate_container(obj, CID, IMAGE, ENV, "environment_injection")


@pytest.mark.parametrize("value", [ENV[0], "PATH=changed"])
def test_duplicate_env_rejected_before_start(value):
    obj = container()
    obj["Config"]["Env"].append(value)
    call = Mock(return_value=(0, json.dumps([obj]), ""))
    with pytest.raises(LabError):
        start_checked(call, CID, IMAGE, ENV, "baseline")
    assert call.call_count == 1


@pytest.mark.parametrize("values", [None, {}, ["INVALID"], ["=empty"], [True]])
def test_bad_environment_structure(values):
    obj = container()
    obj["Config"]["Env"] = values
    with pytest.raises(LabError):
        validate_container(obj, CID, IMAGE, ENV, "baseline")


def test_env_preserves_full_value_and_case():
    obj = container()
    expected = ENV + ["Exact=left=right "]
    obj["Config"]["Env"] = list(reversed(expected))
    validate_container(obj, CID, IMAGE, expected, "baseline")
    obj["Config"]["Env"][0] = "exact=left=right "
    with pytest.raises(LabError):
        validate_container(obj, CID, IMAGE, expected, "baseline")

"""GitHub-only synthetic runtime experiments. No production consumer or authority."""

import argparse
import errno
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

BASE = (
    "docker.io/library/python@"
    "sha256:83f339c1be6340ae1096010fdccf6552ac932d8f410d45d206014916bdf37e48"
)
ENTRY = ["/usr/local/bin/python", "-I", "-S", "-B", "/candidate/entry.py"]
INJECTION = ["PYTHONPATH=/injected", "PYTHONHOME=/missing-python-home"]
FALSE_FLAGS = (
    "actual_candidate_environment_installed",
    "runtime_closure_verified",
    "continuous_immutability_verified",
    "registration_verified",
    "live_eligible",
    "promotion_allowed",
    "declaration_authenticated",
)
CASES = {
    "baseline",
    "environment_injection",
    "source_write",
    "host_main_independent",
    "mount_rejected",
    "network_rejected",
    "command_rejected",
    "site_positive",
    "ro_bind_host_change",
}
HOST = {
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
}
ENTRY_SOURCE = """import errno, hashlib, json, sys
from pathlib import Path
sys.path.insert(0, "/candidate/modules")
import value
mode = sys.argv[1]
result = {"value": value.VALUE, "file": value.__file__,
          "sha256": hashlib.sha256(Path(value.__file__).read_bytes()).hexdigest(),
          "flags": [sys.flags.isolated, sys.flags.no_site, sys.flags.dont_write_bytecode],
          "path": sys.path[1:], "site_loaded": "site" in sys.modules}
if mode == "source_write":
    try:
        Path(value.__file__).write_text("VALUE = 'changed'\\n")
    except OSError as e:
        result["write_errno"] = e.errno
    else:
        raise SystemExit("UNEXPECTED_WRITE")
if mode == "bind_control":
    result["host_value"] = Path("/host-control").read_text()
print(json.dumps(result, sort_keys=True))
"""


class LabError(Exception):
    """Fixed-code failure with no arbitrary command/environment disclosure."""


def require(condition, reason="LAB_MISMATCH"):
    if not condition:
        raise LabError(reason)


def guard(env, system):
    require(system == "Linux" and env.get("GITHUB_ACTIONS") == "true")
    require(env.get("RUNNER_OS") == "Linux" and not env.get("DOCKER_HOST"))


def same(actual, expected):
    return type(actual) is type(expected) and actual == expected


def environment(values):
    require(type(values) is list, "LAB_INVALID_ENV")
    result = {}
    for item in values:
        require(type(item) is str and "=" in item, "LAB_INVALID_ENV")
        name, value = item.split("=", 1)
        require(re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name) is not None, "LAB_INVALID_ENV")
        require(name not in result, "LAB_DUPLICATE_ENV")
        result[name] = value
    return result


def validate_container(obj, cid, image, image_env, case, bind=None):
    """Validate one same-ID created object. Fixed controls are internal lab cases."""
    try:
        require(
            case
            in {"baseline", "environment_injection", "source_write", "site_control", "bind_control"}
        )
        require(re.fullmatch(r"[0-9a-f]{64}", cid) is not None)
        require(re.fullmatch(r"sha256:[0-9a-f]{64}", image) is not None)
        entry = [a for a in ENTRY if a != "-S"] if case == "site_control" else ENTRY
        mode = "baseline" if case == "site_control" else case
        for key, expected in {
            "Id": cid,
            "Image": image,
            "Path": entry[0],
            "Args": entry[1:] + [mode],
        }.items():
            require(same(obj[key], expected), "INSPECT_" + key.upper())
        for key, expected in {"Status": "created", "Running": False, "Pid": 0}.items():
            require(same(obj["State"][key], expected), "INSPECT_STATE_" + key.upper())
        env = image_env + (INJECTION if case == "environment_injection" else [])
        for key, expected in {
            "Entrypoint": entry[:1] if case == "site_control" else entry,
            "Cmd": entry[1:] + [mode] if case == "site_control" else [mode],
            "User": "65532:65532",
            "WorkingDir": "/candidate",
            "Env": env,
            "Image": image,
        }.items():
            if key == "Env":
                require(
                    environment(obj["Config"][key]) == environment(expected), "INSPECT_CONFIG_ENV"
                )
            else:
                require(same(obj["Config"][key], expected), "INSPECT_CONFIG_" + key.upper())
        host = HOST.copy()
        mounts = []
        if case == "bind_control":
            require(type(bind) is str and Path(bind).is_absolute())
            host["Binds"] = [bind + ":/host-control:ro"]
            mounts = [
                {
                    "Type": "bind",
                    "Source": bind,
                    "Destination": "/host-control",
                    "Mode": "ro",
                    "RW": False,
                    "Propagation": "rprivate",
                }
            ]
        for key, expected in host.items():
            if key in {"Mounts", "Tmpfs"}:
                actual = obj["HostConfig"].get(key)
                empty = [] if key == "Mounts" else {}
                require(actual is None or same(actual, empty), "INSPECT_HOST_" + key.upper())
            else:
                require(same(obj["HostConfig"][key], expected), "INSPECT_HOST_" + key.upper())
        require(same(obj["Mounts"], mounts))
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise LabError("LAB_INVALID_INSPECT") from exc


def start_checked(call, cid, image, image_env, case, bind=None):
    code, stdout, _ = call(["inspect", "--type=container", cid])
    require(code == 0)
    try:
        objects = json.loads(stdout)
        require(type(objects) is list and len(objects) == 1)
        validate_container(objects[0], cid, image, image_env, case, bind)
    except (ValueError, TypeError) as exc:
        raise LabError("LAB_INVALID_JSON") from exc
    return call(["start", "--attach", cid])


def validate_report(report):
    require(type(report) is dict and same(report["schema"], 1))
    require(report["scope"] == "SYNTHETIC_RUNTIME_LAB" and report["base"] == BASE)
    require(re.fullmatch(r"[0-9a-f]{40}", report["source_sha"]) is not None)
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", report["fixture_image_id"]) is not None)
    require(report["platform"] == "linux/amd64")
    require(set(report["cases"]) == CASES)
    require(all(v["observed_as_expected"] is True for v in report["cases"].values()))
    require(report["cases"]["ro_bind_host_change"]["host_change_visible"] is True)
    require(
        report["cases"]["ro_bind_host_change"]["observation_scope"]
        == "HOST_CHANGE_BETWEEN_SEPARATE_STARTS"
    )
    require(report["cases"]["ro_bind_host_change"]["values"] == ["HOST_V1", "HOST_V2"])
    for name in ("mount_rejected", "network_rejected", "command_rejected"):
        require(report["cases"][name]["start_calls"] == 0)
    require(all(report[k] is False for k in FALSE_FLAGS))
    observations = report["inspections"]
    require(type(observations) is list and len(observations) == 13)
    env = observations[0]["Config"]["Env"]
    image = report["fixture_image_id"]
    for index, case in (
        (0, "baseline"),
        (1, "environment_injection"),
        (2, "source_write"),
        (3, "site_control"),
        (4, "baseline"),
        (11, "bind_control"),
        (12, "bind_control"),
    ):
        obj = observations[index]
        validate_container(
            obj,
            obj["Id"],
            image,
            env,
            case,
            "/synthetic-lab/main-value.txt" if case == "bind_control" else None,
        )
    for index in (5, 7, 9):
        require(observations[index] == observations[index + 1])
        try:
            validate_container(
                observations[index], observations[index]["Id"], image, env, "baseline"
            )
        except LabError:
            pass
        else:
            raise LabError("LAB_REJECTION_MISSING")
    for name in ("baseline", "environment_injection", "source_write"):
        obj = report["cases"][name]["output"]
        require(obj["flags"] == [1, 1, 1] and obj["site_loaded"] is False)
        require(obj["value"] == "FROZEN_SYNTHETIC" and obj["file"] == "/candidate/modules/value.py")
        require(obj["sha256"] == hashlib.sha256(b"VALUE = 'FROZEN_SYNTHETIC'\n").hexdigest())
        require(all(p and "site-packages" not in p and "/injected" not in p for p in obj["path"]))
    require(report["cases"]["source_write"]["output"]["write_errno"] == errno.EROFS)
    require(report["cases"]["site_positive"]["pth_executed_without_S"] is True)
    require(report["program_readiness"] == "NOT_ASSESSED" and same(report["orders_submitted"], 0))
    require(len(json.dumps(report).encode()) + 1 <= 32768)  # Include stored newline.
    return report


def run_lab(output):
    guard(os.environ, platform.system())  # Before Docker lookup, config or socket access.
    require(
        not output.exists()
        and re.fullmatch(r"[0-9a-f]{40}", os.environ.get("LAB_SOURCE_SHA", "")) is not None
    )
    docker = shutil.which("docker")
    require(docker is not None)
    image = None
    containers = []
    inspections = []
    with tempfile.TemporaryDirectory(prefix="synthetic-runtime-") as directory:
        root = Path(directory)
        config = root / "docker-config"
        config.mkdir()

        def call(args, timeout=20):
            with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
                try:
                    result = subprocess.run(
                        [
                            docker,
                            "--host",
                            "unix:///var/run/docker.sock",
                            "--config",
                            str(config),
                            *args,
                        ],
                        cwd=root,
                        env={"PATH": os.environ["PATH"], "LANG": "C.UTF-8"},
                        stdout=out,
                        stderr=err,
                        timeout=timeout,
                        check=False,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise LabError("LAB_COMMAND_TIMEOUT") from exc
                out.seek(0)
                err.seek(0)
                stdout, stderr = out.read(65537), err.read(65537)
                require(len(stdout) <= 65536 and len(stderr) <= 65536)
                decoded = stdout.decode("utf-8", "strict")
                if args[:2] == ["inspect", "--type=container"] and result.returncode == 0:
                    original = json.loads(decoded)[0]
                    selected = {
                        key: original[key] for key in ("Id", "Image", "Path", "Args", "Mounts")
                    }
                    selected["State"] = {
                        k: original["State"][k] for k in ("Status", "Running", "Pid")
                    }
                    selected["Config"] = {
                        k: original["Config"][k]
                        for k in ("Entrypoint", "Cmd", "User", "WorkingDir", "Env", "Image")
                    }
                    selected["HostConfig"] = {
                        k: original["HostConfig"][k] for k in HOST if k in original["HostConfig"]
                    }
                    # Only generated fixture paths are present; retain a stable safe alias.
                    inspections.append(
                        json.loads(json.dumps(selected).replace(str(root), "/synthetic-lab"))
                    )
                return result.returncode, decoded, stderr.decode("utf-8", "strict")

        try:
            fixture = root / "fixture"
            fixture.mkdir()
            files = {
                "entry.py": ENTRY_SOURCE,
                "value.py": "VALUE = 'FROZEN_SYNTHETIC'\n",
                "lab-injection.pth": "import sys; sys.exit('LAB_SITE_PTH_EXECUTED')\n",
                "sitecustomize.py": "raise SystemExit('LAB_SITECUSTOMIZE_EXECUTED')\n",
                "Dockerfile": (
                    f"FROM {BASE}\n"
                    "COPY --chmod=0644 entry.py /candidate/entry.py\n"
                    "COPY --chmod=0666 value.py /candidate/modules/value.py\n"
                    "COPY --chmod=0644 lab-injection.pth sitecustomize.py "
                    "/usr/local/lib/python3.11/site-packages/\n"
                    "WORKDIR /candidate\nUSER 65532:65532\n"
                    f"ENTRYPOINT {json.dumps(ENTRY)}\nCMD []\n"
                ),
            }
            for name, content in files.items():
                (fixture / name).write_text(content)
            require(call(["pull", "--platform=linux/amd64", BASE], 180)[0] == 0)
            code, _, _ = call(
                [
                    "build",
                    "--pull",
                    "--network=none",
                    "--platform=linux/amd64",
                    "--iidfile",
                    str(root / "iid"),
                    str(fixture),
                ],
                180,
            )
            require(code == 0)
            image = (root / "iid").read_text().strip()
            require(re.fullmatch(r"sha256:[0-9a-f]{64}", image) is not None)
            code, text, _ = call(["image", "inspect", image])
            require(code == 0)
            image_obj = json.loads(text)[0]
            image_env = image_obj["Config"]["Env"]
            require(image_obj["Architecture"] == "amd64" and image_obj["Os"] == "linux")
            require(len(image_env) == len(set(v.split("=", 1)[0] for v in image_env)))
            code, text, _ = call(["image", "inspect", BASE])
            require(code == 0)
            base_obj = json.loads(text)[0]
            require(base_obj["Architecture"] == "amd64" and base_obj["Os"] == "linux")
            require(any(v.endswith("@" + BASE.split("@", 1)[1]) for v in base_obj["RepoDigests"]))
            layers = base_obj["RootFS"]["Layers"]
            require(image_obj["RootFS"]["Layers"][: len(layers)] == layers)

            def create(case, extra=(), network="none"):
                args = [
                    "create",
                    "--read-only",
                    "--network=" + network,
                    "--cap-drop=ALL",
                    "--security-opt=no-new-privileges=true",
                    "--user=65532:65532",
                    "--pids-limit=64",
                    "--memory=128m",
                    "--cpus=1",
                    "--ipc=private",
                ]
                if case == "environment_injection":
                    for var in INJECTION:
                        args += ["--env", var]
                if case == "site_control":
                    args += ["--entrypoint=/usr/local/bin/python"]
                args += list(extra) + [image]
                args += (
                    ["-I", "-B", "/candidate/entry.py", "baseline"]
                    if case == "site_control"
                    else [case]
                )
                code, stdout, _ = call(args)
                require(code == 0)
                cid = stdout.strip()
                require(re.fullmatch(r"[0-9a-f]{64}", cid) is not None)
                containers.append(cid)
                return cid

            def observe(case="baseline", extra=(), bind=None):
                cid = create(case, extra)
                return start_checked(call, cid, image, image_env, case, bind)

            cases = {}
            baseline = None
            for case in ("baseline", "environment_injection", "source_write"):
                code, stdout, _ = observe(case)
                require(code == 0)
                obj = json.loads(stdout)
                require(obj["flags"] == [1, 1, 1] and obj["site_loaded"] is False)
                require(
                    obj["value"] == "FROZEN_SYNTHETIC"
                    and obj["file"] == "/candidate/modules/value.py"
                )
                require(obj["sha256"] == hashlib.sha256(files["value.py"].encode()).hexdigest())
                require(
                    all(
                        "site-packages" not in p and "/injected" not in p and p for p in obj["path"]
                    )
                )
                if case == "source_write":
                    require(obj["write_errno"] == errno.EROFS)
                cases[case] = {"observed_as_expected": True, "output": obj}
                if case == "baseline":
                    baseline = obj
            code, _, stderr = observe("site_control")
            require(code != 0 and "LAB_SITE_PTH_EXECUTED" in stderr)
            cases["site_positive"] = {"observed_as_expected": True, "pth_executed_without_S": True}
            main = root / "main-value.txt"
            main.write_text("host-main-before")
            cid = create("baseline")
            main.write_text("host-main-after")
            code, stdout, _ = start_checked(call, cid, image, image_env, "baseline")
            require(code == 0 and json.loads(stdout) == baseline)
            cases["host_main_independent"] = {
                "observed_as_expected": True,
                "in_image_value_unchanged": True,
                "host_file_changed": True,
            }
            for name, extra in (
                ("mount_rejected", ["--volume", str(main) + ":/host-control:ro"]),
                ("network_rejected", []),
                ("command_rejected", ["--entrypoint=/bin/false"]),
            ):
                cid = create("baseline", extra, "bridge" if name == "network_rejected" else "none")
                count = 0

                def counted(args):
                    nonlocal count
                    if args[0] == "start":
                        count += 1
                    return call(args)

                try:
                    start_checked(counted, cid, image, image_env, "baseline")
                except LabError:
                    require(count == 0)
                else:
                    raise LabError("LAB_REJECTION_MISSING")
                code, raw, _ = call(["inspect", "--type=container", cid])
                require(code == 0 and json.loads(raw)[0]["State"]["Status"] == "created")
                cases[name] = {
                    "observed_as_expected": True,
                    "start_calls": count,
                    "state": "created",
                }
            seen = []
            for content in ("HOST_V1", "HOST_V2"):
                main.write_text(content)
                main.chmod(0o644)
                code, stdout, _ = observe(
                    "bind_control", ["--volume", str(main) + ":/host-control:ro"], str(main)
                )
                require(code == 0 and json.loads(stdout)["host_value"] == content)
                seen.append(json.loads(stdout)["host_value"])
            require(seen[0] != seen[1])
            cases["ro_bind_host_change"] = {
                "observed_as_expected": True,
                "host_change_visible": True,
                "values": seen,
                "continuous_immutability_verified": False,
                "observation_scope": "HOST_CHANGE_BETWEEN_SEPARATE_STARTS",
            }
            report = {
                "schema": 1,
                "scope": "SYNTHETIC_RUNTIME_LAB",
                "source_sha": os.environ["LAB_SOURCE_SHA"],
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "base": BASE,
                "base_image_id": base_obj["Id"],
                "fixture_image_id": image,
                "platform": "linux/amd64",
                "fixture_sha256": {
                    k: hashlib.sha256(v.encode()).hexdigest() for k, v in files.items()
                },
                "cases": cases,
                "inspections": inspections,
                "program_readiness": "NOT_ASSESSED",
                "orders_submitted": 0,
                **dict.fromkeys(FALSE_FLAGS, False),
            }
            validate_report(report)
        finally:
            cleanup_failed = False
            for cid in containers:
                try:
                    cleanup_failed |= call(["rm", "--force", cid])[0] != 0
                except (LabError, OSError, ValueError):
                    cleanup_failed = True
            if image:
                try:
                    cleanup_failed |= call(["image", "rm", image])[0] != 0
                except (LabError, OSError, ValueError):
                    cleanup_failed = True
            require(not cleanup_failed)
        # No success report if experiments or cleanup failed.
        with output.open("x") as handle:
            handle.write(json.dumps(report, sort_keys=True) + "\n")
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = run_lab(args.output)
    except (LabError, OSError, ValueError, KeyError, TypeError) as exc:
        reason = str(exc) if isinstance(exc, LabError) else "LAB_FAILED"
        if not re.fullmatch(r"[A-Z_]{1,64}", reason):
            reason = "LAB_FAILED"
        print(
            json.dumps(
                {
                    "scope": "SYNTHETIC_RUNTIME_LAB",
                    "status": "LAB_FAILED",
                    "reason": reason,
                    "orders_submitted": 0,
                }
            )
        )
        return 1
    print(
        json.dumps({"scope": report["scope"], "cases": len(report["cases"]), "orders_submitted": 0})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

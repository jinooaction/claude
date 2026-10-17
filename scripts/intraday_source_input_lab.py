"""Fixed, non-executing toy inputs. Never a production registration validator."""

import argparse
import hashlib
import json
import os
import platform
import re
import selectors
import shutil
import stat
import subprocess
import tempfile
import time
from pathlib import Path

SOURCE = {"source/value.txt": b"synthetic-only\n", "lock.txt": b"toy==1\n"}
INPUTS = {
    "toy.txt": b"not an executable package\n",
    "contract.json": b'{"platform":"toy-linux","tool":"none","transitive":[]}\n',
}
FALSE_FLAGS = (
    "declaration_authenticated", "actual_candidate_environment_installed",
    "image_binding_verified", "runtime_closure_verified",
    "continuous_immutability_verified", "registration_verified",
    "live_eligible", "promotion_allowed",
)


class LabError(Exception):
    """Only fixed error codes leave the controller."""


def require(condition, reason="LAB_MISMATCH"):
    if not condition:
        raise LabError(reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identity(info):
    # Reading may legitimately change atime; it must not change these fields.
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def guard(env, system):
    require(system == "Linux" and env.get("GITHUB_ACTIONS") == "true", "REMOTE_ONLY")
    require(env.get("RUNNER_OS") == "Linux", "REMOTE_ONLY")


def git_environment():
    # No inherited loader, Git, credential, configuration, or search-path inputs.
    return {
        "PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_ATTR_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
        "GIT_NO_REPLACE_OBJECTS": "1", "GIT_NO_LAZY_FETCH": "1",
        "GIT_AUTHOR_NAME": "Toy", "GIT_AUTHOR_EMAIL": "toy@example.invalid",
        "GIT_COMMITTER_NAME": "Toy", "GIT_COMMITTER_EMAIL": "toy@example.invalid",
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z",
        "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
    }


def inventory(root, *, max_bytes=8 * 1024 * 1024, max_entries=256, max_depth=12):
    """Read through directory descriptors; never follow any link or special file."""
    result, total = {}, 0

    def visit(fd, prefix, depth):
        nonlocal total
        require(depth <= max_depth, "INPUT_LIMIT")
        with os.scandir(fd) as scan:
            for entry in scan:
                require(len(result) < max_entries, "INPUT_LIMIT")
                name = entry.name
                require(re.fullmatch(r"[A-Za-z0-9_.-]+", name), "INPUT_NAME")
                path = prefix + name
                before = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISDIR(before.st_mode):
                    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                    dir_fd=fd)
                    try:
                        require(os.fstat(child).st_ino == before.st_ino, "INPUT_CHANGED")
                        result[path] = ("dir", stat.S_IMODE(before.st_mode), 0, "")
                        visit(child, path + "/", depth + 1)
                    finally:
                        os.close(child)
                else:
                    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                            "INPUT_TYPE")
                    total += before.st_size
                    require(total <= max_bytes, "INPUT_LIMIT")
                    child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                    dir_fd=fd)
                    try:
                        current = os.fstat(child)
                        require(identity(current) == identity(before), "INPUT_CHANGED")
                        data = bytearray()
                        while True:
                            chunk = os.read(child, min(65536, before.st_size + 1 - len(data)))
                            if not chunk:
                                break
                            data.extend(chunk)
                            require(len(data) <= before.st_size, "INPUT_CHANGED")
                        require(identity(os.fstat(child)) == identity(before)
                                and len(data) == before.st_size,
                                "INPUT_CHANGED")
                        result[path] = ("file", stat.S_IMODE(before.st_mode),
                                        len(data), digest(data))
                    finally:
                        os.close(child)

    try:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            visit(fd, "", 0)
        finally:
            os.close(fd)
    except OSError:
        raise LabError("INPUT_IO") from None
    return result


def command(argv, cwd, *, timeout=20, output_limit=65536):
    """Bound output while reading, not after an unlimited communicate()."""
    start = time.monotonic()
    data = bytearray()
    with subprocess.Popen(argv, cwd=cwd, env=git_environment(),
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT) as proc:
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(proc.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    require(time.monotonic() - start < timeout, "COMMAND_TIMEOUT")
                    for key, _ in selector.select(0.05):
                        chunk = os.read(key.fd, 4096)
                        if not chunk:
                            selector.unregister(key.fd)
                        data.extend(chunk)
                        require(len(data) <= output_limit, "OUTPUT_LIMIT")
                remaining = timeout - (time.monotonic() - start)
                require(remaining > 0, "COMMAND_TIMEOUT")
                require(proc.wait(timeout=remaining) == 0, "GIT_FAILED")
        except BaseException:
            proc.kill()
            proc.wait()
            raise
    return bytes(data)


def git(repo, *args):
    return command([
        "/usr/bin/git", "--no-optional-locks", "--no-replace-objects",
        "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
        "-c", "core.untrackedCache=false", "-c", "core.attributesFile=/dev/null",
        "-c", "core.autocrlf=false", "-c", "protocol.allow=never", *args,
    ], repo)


def create_fixture(root):
    repo, inputs = root / "repo", root / "inputs"
    repo.mkdir(parents=True)
    inputs.mkdir()
    for directory, files in ((repo, SOURCE), (inputs, INPUTS)):
        for name, data in files.items():
            p = directory / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            p.chmod(0o644)
    git(repo, "init", "--quiet", "--template=", "--initial-branch=fixture")
    git(repo, "add", "--", *SOURCE)
    git(repo, "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "synthetic")
    head = git(repo, "rev-parse", "HEAD").decode().strip()
    git(repo, "checkout", "--quiet", "--detach", head)
    # Kept only in controller memory, outside every later candidate copy.
    return {
        "repo": inventory(repo), "inputs": inventory(inputs, max_entries=16,
                                                         max_bytes=1024 * 1024),
        "commit": head, "tree": git(repo, "rev-parse", "HEAD^{tree}").decode().strip(),
        "ls_tree": git(repo, "ls-tree", "-rz", "HEAD"),
    }


def verify(root, expected):
    repo, inputs = root / "repo", root / "inputs"
    # Git configuration, objects, index and refs are rejected before Git sees them.
    require(inventory(repo) == expected["repo"], "INPUT_MISMATCH")
    require(inventory(inputs, max_entries=16, max_bytes=1024 * 1024)
            == expected["inputs"], "INPUT_MISMATCH")
    require((repo / ".git/HEAD").read_bytes() == (expected["commit"] + "\n").encode(),
            "HEAD_MISMATCH")
    output = {}
    for label, args, wanted in (
        ("commit", ("rev-parse", "HEAD"), (expected["commit"] + "\n").encode()),
        ("tree", ("rev-parse", "HEAD^{tree}"), (expected["tree"] + "\n").encode()),
        ("history", ("rev-list", "--count", "HEAD"), b"1\n"),
        ("tree_files", ("ls-tree", "-rz", "HEAD"), expected["ls_tree"]),
        ("clean", ("status", "--porcelain=v1", "--untracked-files=all"), b""),
    ):
        raw = git(repo, *args)
        require(raw == wanted, "GIT_MISMATCH")
        output[label] = digest(raw)
    for name, original in SOURCE.items():
        raw = git(repo, "cat-file", "blob", "HEAD:" + name)
        require(raw == original, "BLOB_MISMATCH")
        output[name] = digest(raw)
    require(inventory(repo) == expected["repo"], "INPUT_CHANGED")
    require(inventory(inputs, max_entries=16, max_bytes=1024 * 1024)
            == expected["inputs"], "INPUT_CHANGED")
    return output


def mutate(root, case):
    """Every mutation is to our disposable synthetic copy, never a user repo."""
    repo, inputs = root / "repo", root / "inputs"
    if case == "same_tree_other_commit":
        git(repo, "-c", "commit.gpgsign=false", "commit", "--quiet", "--allow-empty",
            "-m", "other synthetic commit")
    elif case == "archive_only":
        shutil.rmtree(repo / ".git")
    elif case == "external_git_pointer":
        shutil.rmtree(repo / ".git")
        (repo / ".git").write_text("gitdir: /nonexistent\n")
    elif case in {"assume_unchanged", "skip_worktree"}:
        option = "--assume-unchanged" if case == "assume_unchanged" else "--skip-worktree"
        git(repo, "update-index", option, "source/value.txt")
        (repo / "source/value.txt").write_bytes(b"hidden change\n")
    elif case in {"filter_config", "partial_clone", "remote_config", "sparse"}:
        key, value = {
            "filter_config": ("filter.toy.clean", "false"),
            "partial_clone": ("extensions.partialClone", "missing"),
            "remote_config": ("remote.origin.url", "https://example.invalid/never"),
            "sparse": ("core.sparseCheckout", "true"),
        }[case]
        git(repo, "config", "--local", key, value)
    elif case == "missing_blob":
        blob = git(repo, "rev-parse", "HEAD:source/value.txt").decode().strip()
        (repo / ".git/objects" / blob[:2] / blob[2:]).unlink()
    elif case in {"shallow", "alternates", "graft", "replace", "hook"}:
        name = {"shallow": ".git/shallow", "alternates": ".git/objects/info/alternates",
                "graft": ".git/info/grafts", "replace": ".git/refs/replace/toy",
                "hook": ".git/hooks/post-checkout"}[case]
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"synthetic unsupported input\n")
    elif case == "mode":
        (repo / "source/value.txt").chmod(0o755)
    elif case in {"symlink", "hardlink"}:
        p = repo / "source/value.txt"
        p.unlink()
        if case == "symlink":
            p.symlink_to("../lock.txt")
        else:
            os.link(repo / "lock.txt", p)
    elif case == "missing_source":
        (repo / "source/value.txt").unlink()
    elif case == "changed_source":
        (repo / "source/value.txt").write_bytes(b"synthetic-only\r\n")
    elif case in {"secret_name", "ledger_name", "extra_source"}:
        name = {"secret_name": ".env", "ledger_name": "ledger.sqlite",
                "extra_source": "extra.txt"}[case]
        (repo / name).write_bytes(b"synthetic contaminant, no real data\n")
    elif case == "unreviewed_object":
        git(repo, "hash-object", "-w", "--", "lock.txt")
        (repo / "extra.txt").write_bytes(b"unreviewed synthetic history input\n")
        git(repo, "hash-object", "-w", "--", "extra.txt")
        (repo / "extra.txt").unlink()
    elif case == "install_bytes":
        (inputs / "toy.txt").write_bytes(b"changed original bytes\n")
    elif case in {"platform", "transitive", "tool"}:
        p = inputs / "contract.json"
        value = json.loads(p.read_text())
        value[case] = ["extra"] if case == "transitive" else "different"
        p.write_text(json.dumps(value))
    elif case == "input_limit":
        (inputs / "oversized").write_bytes(b"x" * (1024 * 1024 + 1))
    else:
        raise LabError("CASE_UNKNOWN")


CASES = (
    "same_tree_other_commit", "archive_only", "external_git_pointer",
    "assume_unchanged", "skip_worktree", "sparse", "filter_config", "partial_clone",
    "remote_config", "missing_blob", "shallow", "alternates", "graft", "replace",
    "hook", "mode", "symlink", "hardlink", "missing_source", "changed_source",
    "secret_name", "ledger_name", "extra_source", "unreviewed_object",
    "install_bytes", "platform", "transitive", "tool", "input_limit",
)


def receipt(source, git_digest, observations):
    require(isinstance(source, str) and re.fullmatch(r"[0-9a-f]{40}", source),
            "SOURCE_MISSING")
    return {"schema_version": "1.0", "scope": "synthetic_input_only",
            "source_commit": source, "git_executable_sha256": git_digest,
            "observations": observations, "container_starts": 0, "package_installs": 0,
            **dict.fromkeys(FALSE_FLAGS, False)}


def run_lab(source):
    guard(os.environ, platform.system())
    require(isinstance(source, str) and re.fullmatch(r"[0-9a-f]{40}", source),
            "SOURCE_MISSING")
    started = time.monotonic()
    observations = []
    # Returning from the context first ensures cleanup failure yields no report.
    with tempfile.TemporaryDirectory(prefix="source-input-lab-") as directory:
        temp = Path(directory)
        baseline = temp / "baseline"
        expected = create_fixture(baseline)
        observations.append({"case": "baseline", "accepted": True,
                             "fixture_commit": expected["commit"],
                             "fixture_tree": expected["tree"],
                             "expected_inputs_sha256": digest(json.dumps(
                                 expected["inputs"], sort_keys=True).encode()),
                             "expected_repository_sha256": digest(json.dumps(
                                 expected["repo"], sort_keys=True).encode()),
                             "git_output_sha256": verify(baseline, expected)})
        for case in CASES:
            require(time.monotonic() - started < 660, "LAB_TIMEOUT")
            candidate = temp / case
            shutil.copytree(baseline, candidate)
            mutate(candidate, case)
            try:
                verify(candidate, expected)
            except LabError as exc:
                observations.append({"case": case, "accepted": False, "reason": str(exc)})
            else:
                raise LabError("MUTATION_ACCEPTED")
        # The independent baseline still passes after every candidate mutation.
        verify(baseline, expected)
        git_digest = digest(Path("/usr/bin/git").read_bytes())
    return receipt(source, git_digest, observations)


def publish(path, result):
    data = json.dumps(result, sort_keys=True, indent=2).encode() + b"\n"
    require(len(data) <= 32768, "REPORT_LIMIT")
    with path.open("xb") as stream:
        stream.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = run_lab(os.environ.get("LAB_SOURCE_SHA"))
        publish(args.output, result)
    except (LabError, OSError, subprocess.SubprocessError):
        print("SOURCE_INPUT_LAB_FAILED")
        return 1
    print("SOURCE_INPUT_LAB_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

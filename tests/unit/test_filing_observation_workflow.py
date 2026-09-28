"""Prevent research publication from inheriting trading authority or losing history."""

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from auto_invest.market_data.filing_collector import Scope

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/collect-filing-observations.yml"


def test_collection_and_publication_have_separate_authority():
    text = WORKFLOW.read_text()
    collect, publish = text.split("  publish:\n", 1)
    assert "permissions:\n  contents: read" in collect
    assert "contents: write" not in collect
    assert "contents: write" in publish
    assert "SEC_USER_AGENT" in collect and "SEC_USER_AGENT" not in publish
    assert "persist-credentials: false" in collect and "persist-credentials: false" in publish
    assert not any(word in text for word in ("VULTR_", "KIS_APP", "ssh ", "--force"))
    assert "cancel-in-progress: false" in text


def test_artifact_precedes_publish_and_failures_remain_observable():
    text = WORKFLOW.read_text()
    assert "retention-days: 90" in text
    assert "needs.collect.outputs.artifact_id != ''" in text
    assert "steps.stage.outputs.ready == 'true'" in text
    assert 'exit "${COLLECT_STATUS:-2}"' in text
    assert "--diff-filter=CDMRTUXB" in text
    assert 'push origin "HEAD:refs/heads/$branch"' in text
    assert "schedule:" not in text  # No unattended collection before real acceptance.
    actions = re.findall(r"uses: ([^\s]+)", text)
    assert actions and all(re.search(r"@[a-f0-9]{40}$", action) for action in actions)


def test_shell_blocks_parse_without_execution():
    lines = WORKFLOW.read_text().splitlines()
    blocks = []
    for index, line in enumerate(lines):
        if line.strip() != "run: |":
            continue
        indentation = len(line) - len(line.lstrip())
        body = []
        for following in lines[index + 1:]:
            if following.strip() and len(following) - len(following.lstrip()) <= indentation:
                break
            body.append(following[indentation + 2:])
        blocks.append("\n".join(body))
    assert len(blocks) >= 5
    for block in blocks:
        result = subprocess.run(["bash", "-n"], input=block, text=True, capture_output=True,
                                timeout=5)
        assert result.returncode == 0, result.stderr


def test_deployed_scope_contains_only_public_collection_settings():
    config = json.loads((ROOT / "deploy/filing-observations.json").read_bytes())
    scope = Scope.from_dict(config)
    assert scope.ciks == ("0000789019",)
    assert scope.max_documents == 5
    assert "@" not in json.dumps(config)


@pytest.mark.parametrize("collect_code, step_code", [(0, 0), (3, 0), (2, 2)])
@pytest.mark.parametrize("source", ["sec", "microsoft"])
def test_collection_exit_is_recorded_under_github_errexit(
        tmp_path, collect_code, step_code, source):
    text = WORKFLOW.read_text()
    section = text.split("      - name: Collect within fixed limits\n", 1)[1]
    block = section.split("        run: |\n", 1)[1].split("      - name:", 1)[0]
    script = 'uv() { echo "$*" > "$TEST_ARGS"; return "$TEST_CODE"; }\n' + "\n".join(
        line[10:] for line in block.splitlines())
    output = tmp_path / "outputs"
    environment = dict(os.environ, TEST_CODE=str(collect_code), GITHUB_OUTPUT=str(output),
                       RUNNER_TEMP=str(tmp_path), GITHUB_RUN_ID="1", GITHUB_RUN_ATTEMPT="1",
                       OBSERVATION_SOURCE=source, TEST_ARGS=str(tmp_path / "arguments"))
    result = subprocess.run(["bash", "-e", "-c", script], env=environment,
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == step_code, result.stderr
    assert output.read_text() == f"status={collect_code}\n"
    arguments = (tmp_path / "arguments").read_text().split()
    assert arguments[3] == ("collect-issuer" if source == "microsoft" else "collect")
    assert arguments[5] == ("deploy/issuer-filings.json" if source == "microsoft"
                            else "deploy/filing-observations.json")


def test_fixed_sources_have_separate_history_and_contact_headers():
    text = WORKFLOW.read_text()
    assert "options: [sec, microsoft]" in text
    assert "'automation/issuer-observations' || 'automation/filing-observations'" in text
    assert "ref: ${{ env.OBSERVATION_BRANCH }}" in text
    assert 'branch="$OBSERVATION_BRANCH"' in text
    assert "inputs.source != 'microsoft' && secrets.SEC_USER_AGENT || ''" in text

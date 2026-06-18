"""스펙 055 — `auto-invest reassign-decide` CLI 글루 테스트.

결정 두뇌(decide_reassignment) + 실행 함수(build_reassignment)를 잇는 얇은 CLI 가
입력 JSON 을 읽고, REASSIGN 일 때만 새 라이브 설정 + rung 0 센티넬을 쓰는지 검증한다.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from typer.testing import CliRunner

from auto_invest.cli import app

runner = CliRunner()

_LIVE = """# 라이브 설정(옛 전략 역변동성).
[caps]
per_trade_pct       = 50.0
per_symbol_pct      = 60.0
global_exposure_pct = 100.0

[whitelist]
symbols     = ["SPY", "IEF", "GLD"]
accounts    = ["${KIS_ACCOUNT_NO}"]
order_types = ["LIMIT"]
sessions    = ["REGULAR"]

[portfolio]
id            = "global-trend"
universe      = ["SPY", "IEF", "GLD"]
weight_scheme = "inverse_vol"
top_n         = 3

[portfolio.trend_filter]
method = "sma"
"""

_CHALLENGER_FIXED = """[caps]
per_trade_pct = 99.0

[whitelist]
symbols = ["SPY", "IEF", "GLD"]

[portfolio]
id            = "global-trend-fixed"
universe      = ["SPY", "IEF", "GLD"]
weight_scheme = "equal"
top_n         = 3

[portfolio.trend_filter]
method           = "sma"
ensemble_windows = [63, 126, 189, 252]
"""

_CHALLENGER_WIDE = """[caps]
per_trade_pct = 50.0

[whitelist]
symbols = ["SPY", "QQQ"]

[portfolio]
id            = "wide"
universe      = ["SPY", "QQQ"]
weight_scheme = "inverse_vol"
top_n         = 2
"""


def _write(tmp: Path, name: str, content: str) -> Path:
    p = tmp / name
    p.write_text(content, encoding="utf-8")
    return p


def _leaderboard(tmp: Path, **fields: object) -> Path:
    base = {
        "schema_version": "1.1",
        "incumbent_key": "global",
        "challenger_key": None,
        "champion_multiplicity_robust": None,
        "observation_health": "OK",
        "observation_note": "테스트 입력 정상",
    }
    base.update(fields)
    return _write(tmp, "lb.json", json.dumps(base))


def _invoke(tmp: Path, args: list[str]) -> object:
    return runner.invoke(app, ["reassign-decide", *args])


def test_no_challenger_holds(tmp_path: Path) -> None:
    lb = _leaderboard(tmp_path, challenger_key=None)
    res = _invoke(tmp_path, ["--leaderboard-json", str(lb), "--canary-verdict", "PASS"])
    assert res.exit_code == 0
    out = json.loads(res.stdout)
    assert out["action"] == "HOLD"
    assert out["wrote_files"] is False


def test_challenger_without_canary_waits(tmp_path: Path) -> None:
    lb = _leaderboard(
        tmp_path, challenger_key="globalfixed", champion_multiplicity_robust=True
    )
    res = _invoke(tmp_path, ["--leaderboard-json", str(lb), "--canary-verdict", ""])
    assert res.exit_code == 0
    out = json.loads(res.stdout)
    assert out["action"] == "WAIT_CANARY"
    assert "execution" not in out


def test_blocked_observation_health_holds(tmp_path: Path) -> None:
    lb = _leaderboard(
        tmp_path,
        challenger_key="globalfixed",
        champion_multiplicity_robust=True,
        observation_health="BLOCKED",
        observation_note="라이브 검증 트랙 판정 없음",
    )
    res = _invoke(tmp_path, ["--leaderboard-json", str(lb), "--canary-verdict", "PASS"])
    assert res.exit_code == 0
    out = json.loads(res.stdout)
    assert out["action"] == "HOLD"
    assert out["gates"]["observation_quality_ok"] is False
    assert out["observation_health"] == "BLOCKED"
    assert out["wrote_files"] is False


def test_degraded_observation_health_holds(tmp_path: Path) -> None:
    lb = _leaderboard(
        tmp_path,
        challenger_key="globalfixed",
        champion_multiplicity_robust=True,
        observation_health="DEGRADED",
        observation_note="관측 뒤처짐: globalfixed",
    )
    res = _invoke(tmp_path, ["--leaderboard-json", str(lb), "--canary-verdict", "PASS"])
    assert res.exit_code == 0
    out = json.loads(res.stdout)
    assert out["action"] == "HOLD"
    assert "DEGRADED" in out["reason"]
    assert out["wrote_files"] is False


def test_kill_switch_disables(tmp_path: Path) -> None:
    lb = _leaderboard(
        tmp_path, challenger_key="globalfixed", champion_multiplicity_robust=True
    )
    kill = _write(tmp_path, "AUTOARM_DISABLED", "stop\n")
    res = _invoke(
        tmp_path,
        ["--leaderboard-json", str(lb), "--canary-verdict", "PASS", "--kill-switch", str(kill)],
    )
    out = json.loads(res.stdout)
    assert out["action"] == "DISABLED"


def test_reassign_writes_config_and_sentinel(tmp_path: Path) -> None:
    lb = _leaderboard(
        tmp_path, challenger_key="globalfixed", champion_multiplicity_robust=True
    )
    live = _write(tmp_path, "live.toml", _LIVE)
    chal = _write(tmp_path, "fixed.toml", _CHALLENGER_FIXED)
    sentinel = tmp_path / "rebalance-live.request"
    res = _invoke(
        tmp_path,
        [
            "--leaderboard-json", str(lb),
            "--canary-verdict", "PASS",
            "--live-portfolio", str(live),
            "--challenger-portfolio", str(chal),
            "--sentinel", str(sentinel),
            "--write-config",
        ],
    )
    assert res.exit_code == 0, res.stdout
    out = json.loads(res.stdout)
    assert out["action"] == "REASSIGN"
    assert out["wrote_files"] is True
    assert out["execution"]["challenger_key"] == "globalfixed"
    # 라이브 설정에 등가중 전략이 이식되고, 운영 블록(caps 50.0)은 보존됐다.
    data = tomllib.loads(live.read_text(encoding="utf-8"))
    assert data["portfolio"]["weight_scheme"] == "equal"
    assert data["caps"]["per_trade_pct"] == 50.0
    assert data["whitelist"]["symbols"] == ["SPY", "IEF", "GLD"]
    # rung 0 센티넬(무장 해제)로 사다리 리셋.
    s = sentinel.read_text(encoding="utf-8")
    assert "armed: false" in s
    assert "ladder_rung: 0" in s


def test_reassign_without_write_does_not_touch_files(tmp_path: Path) -> None:
    lb = _leaderboard(
        tmp_path, challenger_key="globalfixed", champion_multiplicity_robust=True
    )
    live = _write(tmp_path, "live.toml", _LIVE)
    chal = _write(tmp_path, "fixed.toml", _CHALLENGER_FIXED)
    res = _invoke(
        tmp_path,
        [
            "--leaderboard-json", str(lb),
            "--canary-verdict", "PASS",
            "--live-portfolio", str(live),
            "--challenger-portfolio", str(chal),
        ],
    )
    out = json.loads(res.stdout)
    assert out["action"] == "REASSIGN"
    assert out["wrote_files"] is False
    # --write-config 없으면 라이브 설정 원본 그대로(역변동성).
    assert "inverse_vol" in live.read_text(encoding="utf-8")


def test_universe_outside_whitelist_execution_blocked(tmp_path: Path) -> None:
    lb = _leaderboard(
        tmp_path, challenger_key="wide", champion_multiplicity_robust=True
    )
    live = _write(tmp_path, "live.toml", _LIVE)
    chal = _write(tmp_path, "wide.toml", _CHALLENGER_WIDE)
    sentinel = tmp_path / "rebalance-live.request"
    res = _invoke(
        tmp_path,
        [
            "--leaderboard-json", str(lb),
            "--canary-verdict", "PASS",
            "--live-portfolio", str(live),
            "--challenger-portfolio", str(chal),
            "--sentinel", str(sentinel),
            "--write-config",
        ],
    )
    assert res.exit_code == 0
    out = json.loads(res.stdout)
    # 5중 게이트는 통과(action REASSIGN)했으나 거래집합 확대라 실행 차단 — 파일 미기록.
    assert out["action"] == "REASSIGN"
    assert out["wrote_files"] is False
    assert "화이트리스트" in out["execution_blocked"]
    assert not sentinel.exists()
    assert "inverse_vol" in live.read_text(encoding="utf-8")  # 라이브 무변경


def test_challenger_path_maps_key_to_deploy_toml(tmp_path: Path) -> None:
    lb = _leaderboard(tmp_path, challenger_key="globalfixed")
    res = runner.invoke(app, ["reassign-challenger-path", "--leaderboard-json", str(lb)])
    assert res.exit_code == 0
    assert res.output.strip() == "deploy/global-trend-fixed-portfolio.toml"


def test_challenger_path_empty_when_no_challenger(tmp_path: Path) -> None:
    lb = _leaderboard(tmp_path, challenger_key=None)
    res = runner.invoke(app, ["reassign-challenger-path", "--leaderboard-json", str(lb)])
    assert res.exit_code == 0
    assert res.output.strip() == ""


def test_challenger_path_empty_when_observation_not_ok(tmp_path: Path) -> None:
    lb = _leaderboard(
        tmp_path,
        challenger_key="globalfixed",
        champion_multiplicity_robust=True,
        observation_health="DEGRADED",
    )
    res = runner.invoke(app, ["reassign-challenger-path", "--leaderboard-json", str(lb)])
    assert res.exit_code == 0
    assert res.output.strip() == ""


def test_missing_leaderboard_holds(tmp_path: Path) -> None:
    # 리더보드 파일이 없으면 관측 품질 BLOCKED 로 보수 처리(HOLD) — fail-safe.
    res = _invoke(
        tmp_path,
        ["--leaderboard-json", str(tmp_path / "nope.json"), "--canary-verdict", "PASS"],
    )
    assert res.exit_code == 0
    out = json.loads(res.stdout)
    assert out["action"] == "HOLD"
    assert out["observation_health"] == "BLOCKED"

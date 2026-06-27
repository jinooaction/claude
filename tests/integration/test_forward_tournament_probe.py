"""스펙 053 — forward 토너먼트 리더보드 프로브 통합 테스트.

두 입력 경로를 모두 검증한다:
  - --verdict-dir : 워크플로가 만드는 /tmp/verdict_<key>.json 7개를 읽는 경로.
  - --from-sidecar: 발행된 forward 사이드카 LAST_RUN.md 를 트랙 헤더별로 파싱하는 경로.
scripts/ 는 패키지가 아니므로 파일 경로로 직접 로드한다(실제 진입점 검증).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_PROBE_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "forward_tournament_probe.py"
)
_spec = importlib.util.spec_from_file_location("forward_tournament_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main
TRACKS = _probe.TRACKS


def _verdict(verdict="INSUFFICIENT_DATA", n_obs=1, calmar=None, universe=("SPY",)):
    return {
        "schema_version": "1.1",
        "verdict": verdict,
        "n_obs": n_obs,
        "min_obs_required": 20,
        "strategy_sharpe_annual": None,
        "strategy_total_return_pct": "1.0",
        "strategy_max_drawdown_pct": "0.0",
        "strategy_calmar": calmar,
        "excess_return_pct": None,
        "dsr": None,
        "universe": list(universe),
    }


# ---- --manifest -------------------------------------------------------------------


def test_manifest_lists_all_tracks(capsys):
    rc = probe_main(["--manifest"])
    assert rc == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 7
    # global 이 incumbent(True)로 표시되는 유일한 트랙.
    incumbents = [ln for ln in out if ln.endswith("True")]
    assert len(incumbents) == 1
    assert incumbents[0].startswith("global\t")


def test_track_registry_has_one_incumbent():
    incs = [k for k, _l, _h, inc in TRACKS if inc]
    assert incs == ["global"]


# ---- --verdict-dir (워크플로 모드) -------------------------------------------------


def _write_verdict_dir(tmp_path: Path, mapping: dict[str, dict | None]) -> Path:
    d = tmp_path / "verdicts"
    d.mkdir()
    for key, vj in mapping.items():
        body = "{}" if vj is None else json.dumps(vj, ensure_ascii=False)
        (d / f"verdict_{key}.json").write_text(body, encoding="utf-8")
    return d


def test_verdict_dir_all_premature(tmp_path, capsys):
    mapping = {key: _verdict(n_obs=1) for key, *_ in TRACKS}
    d = _write_verdict_dir(tmp_path, mapping)
    rc = probe_main(["--verdict-dir", str(d), "--json", "--now", "2026-06-14T00:00:00Z"])
    assert rc == 0
    obj = json.loads(capsys.readouterr().out)
    assert obj["champion_key"] is None
    assert obj["incumbent_key"] == "global"
    assert len(obj["rows"]) == 7
    assert "아직 비교 불가" in obj["headline"]


def test_verdict_dir_current_all_premature_lag_is_observation_ok(tmp_path, capsys):
    mapping = {key: _verdict(n_obs=12) for key, *_ in TRACKS}
    mapping["globalfixed"] = _verdict(n_obs=9)
    d = _write_verdict_dir(tmp_path, mapping)
    rc = probe_main(["--verdict-dir", str(d), "--json", "--now", "2026-06-27T00:00:00Z"])
    assert rc == 0
    obj = json.loads(capsys.readouterr().out)
    assert obj["known_count"] == 7
    assert obj["unknown_count"] == 0
    assert obj["max_n_obs"] == 12
    assert obj["min_n_obs"] == 9
    assert obj["lagging_keys"] == ["globalfixed"]
    assert obj["observation_health"] == "OK"
    assert "최소 관측 전" in obj["observation_note"]


def test_verdict_dir_challenger(tmp_path, capsys):
    # wide 가 EDGE_CONFIRMED 1위, global(incumbent)도 비교 가능 NO_EDGE → 도전자 경보.
    mapping = {key: _verdict(verdict="NO_EDGE", n_obs=25, calmar="0.3")
               for key, *_ in TRACKS}
    mapping["wide"] = _verdict(verdict="EDGE_CONFIRMED", n_obs=25, calmar="2.0")
    d = _write_verdict_dir(tmp_path, mapping)
    rc = probe_main(["--verdict-dir", str(d), "--json", "--now", "2026-06-14T00:00:00Z"])
    assert rc == 0
    obj = json.loads(capsys.readouterr().out)
    assert obj["champion_key"] == "wide"
    assert obj["challenger_key"] == "wide"
    assert "도전자" in obj["headline"]


def test_verdict_dir_missing_file_is_unknown(tmp_path, capsys):
    mapping = {key: _verdict(n_obs=1) for key, *_ in TRACKS}
    d = _write_verdict_dir(tmp_path, mapping)
    (d / "verdict_wide.json").unlink()  # 한 트랙 파일 없음
    rc = probe_main(["--verdict-dir", str(d), "--json"])
    assert rc == 0
    obj = json.loads(capsys.readouterr().out)
    wide = next(r for r in obj["rows"] if r["key"] == "wide")
    assert wide["comparability"] == "UNKNOWN"


# ---- --from-sidecar (컨테이너 검증 모드) -------------------------------------------


def _sidecar(verdicts_by_key: dict[str, dict]) -> str:
    """실제 forward 사이드카 헤더 구조를 흉내 낸 마크다운(트랙 헤더 + ```json 블록)."""
    # 헤더 부분 문자열은 TRACKS 의 header_substr 를 포함해야 파서가 찾는다.
    headers = {
        "trend": "## 🧭 판정 — 추세 필터 ON (drawdown 방어 오버레이)",
        "notrend": "## 🧭 판정 — 추세 필터 OFF (대조군)",
        "rmbeta": "## 🛡️ 판정 — 위험관리 베타 (스펙 042)",
        "multiasset": "## 🌐 판정 — 멀티에셋 분산 추세 (스펙 043)",
        "global": "## 🪙 판정 — 글로벌 분산 추세 (주식+채권+금, 스펙 047)",
        "globalfixed": "## ⚖ 판정 — 글로벌 3자산 추세 고정(등가중) 재지정 후보",
        "wide": "## 🌍 판정 — 글로벌 분산 추세 확대 유니버스 (11 슬리브)",
    }
    parts = [
        "# forward 페이퍼 A/B 토너먼트\n",
        "추세 필터 **ON**(canary-portfolio.toml) vs **OFF**(대조군).",
        "글로벌 분산 추세와 글로벌 3자산 추세 고정 후보를 함께 비교한다.",
        "",
        "```",
        "이 일반 코드블록은 halt 진단 같은 부가 로그다. JSON 판정이 아니다.",
        "```",
        "",
    ]
    for key, *_ in TRACKS:
        vj = verdicts_by_key[key]
        parts.append(headers[key])
        parts.append("")
        parts.append("```json")
        parts.append(json.dumps(vj, ensure_ascii=False))
        parts.append("```")
        parts.append("")
    return "\n".join(parts)


def test_from_sidecar_parses_all_tracks(tmp_path, capsys):
    # global 과 wide 를 헷갈리지 않고 각각 뽑는지(접두 부분문자열 충돌 방지) 확인.
    vmap = {key: _verdict(n_obs=1) for key, *_ in TRACKS}
    vmap["global"] = _verdict(verdict="EDGE_CONFIRMED", n_obs=25, calmar="2.0",
                              universe=("SPY", "IEF", "GLD"))
    vmap["wide"] = _verdict(verdict="NO_EDGE", n_obs=25, calmar="0.4")
    md = _sidecar(vmap)
    p = tmp_path / "forward.md"
    p.write_text(md, encoding="utf-8")
    rc = probe_main(["--from-sidecar", str(p), "--json", "--now", "2026-06-14T00:00:00Z"])
    assert rc == 0
    obj = json.loads(capsys.readouterr().out)
    assert len(obj["rows"]) == 7
    # global 이 EDGE_CONFIRMED 로 정확히 파싱되어 챔피언(= incumbent).
    assert obj["champion_key"] == "global"
    assert obj["known_count"] == 7
    assert obj["unknown_count"] == 0
    g = next(r for r in obj["rows"] if r["key"] == "global")
    assert g["verdict"] == "EDGE_CONFIRMED"
    assert g["comparability"] == "COMPARABLE"
    # wide 는 NO_EDGE 로(global 블록과 안 섞임).
    w = next(r for r in obj["rows"] if r["key"] == "wide")
    assert w["verdict"] == "NO_EDGE"


def test_from_sidecar_heading_only_parser_ignores_intro_collisions(tmp_path, capsys):
    # 실제 사고: 상단 설명의 "추세 필터 ON" 문구를 트랙 헤더로 오인해, 그 뒤의
    # 일반 코드블록을 JSON 으로 파싱하려다 trend/notrend 등이 UNKNOWN 이 됐다.
    vmap = {key: _verdict(n_obs=4) for key, *_ in TRACKS}
    md = _sidecar(vmap)
    p = tmp_path / "forward.md"
    p.write_text(md, encoding="utf-8")

    rc = probe_main(["--from-sidecar", str(p), "--json", "--now", "2026-06-14T00:00:00Z"])
    assert rc == 0
    obj = json.loads(capsys.readouterr().out)

    assert obj["known_count"] == 7
    assert obj["unknown_count"] == 0
    assert {r["key"]: r["comparability"] for r in obj["rows"]} == {
        key: "PREMATURE" for key, *_ in TRACKS
    }


def test_from_sidecar_text_output(tmp_path, capsys):
    vmap = {key: _verdict(n_obs=1) for key, *_ in TRACKS}
    md = _sidecar(vmap)
    p = tmp_path / "forward.md"
    p.write_text(md, encoding="utf-8")
    rc = probe_main(["--from-sidecar", str(p), "--now", "2026-06-14T00:00:00Z"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "🏆 forward 토너먼트 리더보드" in out
    assert "라이브 검증, SPY·IEF·GLD" in out  # global 라벨


def test_requires_an_input_mode(capsys):
    # --manifest 도 --verdict-dir 도 --from-sidecar 도 없으면 에러(argparse SystemExit).
    try:
        probe_main([])
    except SystemExit as exc:
        assert exc.code != 0
    else:
        raise AssertionError("입력 모드 없이 종료해야 한다")

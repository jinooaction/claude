"""스펙 053 — forward 토너먼트 리더보드 순수 코어 단위 테스트."""

from __future__ import annotations

from auto_invest.analytics.forward_tournament import (
    COMPARABLE,
    EDGE_CONFIRMED,
    INSUFFICIENT_DATA,
    NO_EDGE,
    PREMATURE,
    UNKNOWN,
    build_track_result,
    rank_tournament,
)


def _verdict(
    *,
    verdict=INSUFFICIENT_DATA,
    n_obs=1,
    min_obs=20,
    calmar=None,
    sharpe=None,
    excess=None,
    dd="0.0",
    universe=("SPY", "IEF", "GLD"),
):
    return {
        "verdict": verdict,
        "n_obs": n_obs,
        "min_obs_required": min_obs,
        "strategy_calmar": calmar,
        "strategy_sharpe_annual": sharpe,
        "strategy_max_drawdown_pct": dd,
        "excess_return_pct": excess,
        "strategy_total_return_pct": "1.0",
        "dsr": None,
        "universe": list(universe),
    }


def _track(key, *, incumbent=False, vj=None, label=None):
    return build_track_result(
        key=key,
        label=label or key,
        is_incumbent=incumbent,
        verdict_json=vj,
    )


# ---- build_track_result: 비교 가능성 등급 ----------------------------------------


def test_none_verdict_is_unknown():
    t = _track("x", vj=None)
    assert t.comparability == UNKNOWN
    assert t.verdict is None


def test_empty_dict_is_unknown():
    t = _track("x", vj={})
    assert t.comparability == UNKNOWN


def test_garbage_verdict_label_is_unknown():
    # 인식 못 하는 라벨은 비교 불가(UNKNOWN)이되, 원본 문자열은 포렌식용으로 보존한다.
    t = _track("x", vj=_verdict(verdict="WAT"))
    assert t.comparability == UNKNOWN
    assert t.verdict == "WAT"


def test_insufficient_data_is_premature():
    t = _track("x", vj=_verdict(verdict=INSUFFICIENT_DATA, n_obs=1))
    assert t.comparability == PREMATURE


def test_confirmed_but_low_obs_is_premature():
    # 라벨이 EDGE_CONFIRMED 라도 관측 < 최소면 잠정(관측 게이트가 우선).
    t = _track("x", vj=_verdict(verdict=EDGE_CONFIRMED, n_obs=5, min_obs=20))
    assert t.comparability == PREMATURE


def test_confirmed_enough_obs_is_comparable():
    t = _track("x", vj=_verdict(verdict=EDGE_CONFIRMED, n_obs=25, min_obs=20))
    assert t.comparability == COMPARABLE


def test_no_edge_enough_obs_is_comparable():
    t = _track("x", vj=_verdict(verdict=NO_EDGE, n_obs=30))
    assert t.comparability == COMPARABLE


def test_min_obs_falls_back_to_default_when_absent():
    vj = _verdict(verdict=EDGE_CONFIRMED, n_obs=25)
    del vj["min_obs_required"]
    t = _track("x", vj=vj)
    assert t.min_obs == 20
    assert t.comparability == COMPARABLE


# ---- rank_tournament: 현재 상태(전부 잠정) -----------------------------------------


def test_all_premature_no_champion():
    tracks = [
        _track("trend", vj=_verdict(n_obs=1)),
        _track("global", incumbent=True, vj=_verdict(n_obs=1)),
        _track("wide", vj=_verdict(n_obs=1)),
    ]
    board = rank_tournament(tracks, as_of_utc="2026-06-14T00:00:00Z")
    assert board.champion_key is None
    assert board.challenger_key is None
    assert board.incumbent_key == "global"
    assert "아직 비교 불가" in board.headline


def test_premature_sorted_by_obs_desc():
    tracks = [
        _track("a", vj=_verdict(n_obs=3)),
        _track("b", vj=_verdict(n_obs=11)),
        _track("c", vj=_verdict(n_obs=7)),
    ]
    board = rank_tournament(tracks)
    # 관측 많을수록 비교 가능에 가까움 → 앞 순위.
    assert [r.key for r in board.rows] == ["b", "c", "a"]
    assert [r.rank for r in board.rows] == [1, 2, 3]


# ---- rank_tournament: 챔피언 / 도전자 --------------------------------------------


def test_incumbent_champion_no_challenger():
    tracks = [
        _track("global", incumbent=True,
               vj=_verdict(verdict=EDGE_CONFIRMED, n_obs=25, calmar="2.0")),
        _track("wide", vj=_verdict(verdict=NO_EDGE, n_obs=25, calmar="0.5")),
    ]
    board = rank_tournament(tracks)
    assert board.champion_key == "global"
    assert board.challenger_key is None
    assert "라이브 검증 트랙" in board.headline
    assert "선두" in board.headline


def test_challenger_beats_comparable_incumbent():
    # 비-incumbent 가 EDGE_CONFIRMED 1위 + incumbent 도 비교 가능 → 도전자 경보.
    tracks = [
        _track("global", incumbent=True,
               vj=_verdict(verdict=NO_EDGE, n_obs=25, calmar="0.4")),
        _track("wide", label="확대",
               vj=_verdict(verdict=EDGE_CONFIRMED, n_obs=25, calmar="1.9")),
    ]
    board = rank_tournament(tracks)
    assert board.champion_key == "wide"
    assert board.challenger_key == "wide"
    assert "도전자" in board.headline
    assert "운영자 게이트" in board.headline or "X.4" in board.headline


def test_challenger_confirmed_but_incumbent_premature_no_alert():
    # 도전자만 확정, 검증 트랙은 관측 부족 → 사과 대 사과 아님 → 도전자 경보 0.
    tracks = [
        _track("global", incumbent=True, vj=_verdict(n_obs=2)),  # 잠정
        _track("multiasset", label="멀티",
               vj=_verdict(verdict=EDGE_CONFIRMED, n_obs=25, calmar="1.5")),
    ]
    board = rank_tournament(tracks)
    assert board.champion_key == "multiasset"
    assert board.challenger_key is None  # incumbent 비교 불가 → 경보 보류
    assert "먼저 엣지 확정" in board.headline


def test_all_comparable_but_no_edge():
    tracks = [
        _track("global", incumbent=True, vj=_verdict(verdict=NO_EDGE, n_obs=25)),
        _track("wide", vj=_verdict(verdict=NO_EDGE, n_obs=30)),
    ]
    board = rank_tournament(tracks)
    assert board.champion_key is None
    assert "엣지 확정 트랙 없음" in board.headline


def test_all_unknown():
    tracks = [_track("a", vj=None), _track("b", vj={})]
    board = rank_tournament(tracks)
    assert board.champion_key is None
    assert "판정 불가" in board.headline


# ---- 순위 정렬: 티어 + 품질 --------------------------------------------------------


def test_tier_order_confirmed_before_noedge_before_premature_before_unknown():
    tracks = [
        _track("unk", vj=None),
        _track("prem", vj=_verdict(n_obs=5)),
        _track("noedge", vj=_verdict(verdict=NO_EDGE, n_obs=25, calmar="0.3")),
        _track("conf", vj=_verdict(verdict=EDGE_CONFIRMED, n_obs=25, calmar="1.0")),
    ]
    board = rank_tournament(tracks)
    assert [r.key for r in board.rows] == ["conf", "noedge", "prem", "unk"]


def test_confirmed_ranked_by_calmar_desc():
    tracks = [
        _track("lo", vj=_verdict(verdict=EDGE_CONFIRMED, n_obs=25, calmar="0.8")),
        _track("hi", vj=_verdict(verdict=EDGE_CONFIRMED, n_obs=25, calmar="2.5")),
        _track("mid", vj=_verdict(verdict=EDGE_CONFIRMED, n_obs=25, calmar="1.4")),
    ]
    board = rank_tournament(tracks)
    assert [r.key for r in board.rows] == ["hi", "mid", "lo"]
    assert board.champion_key == "hi"


def test_calmar_tie_breaks_on_sharpe():
    tracks = [
        _track("a", vj=_verdict(verdict=EDGE_CONFIRMED, n_obs=25,
                                calmar="1.0", sharpe="1.1")),
        _track("b", vj=_verdict(verdict=EDGE_CONFIRMED, n_obs=25,
                                calmar="1.0", sharpe="1.9")),
    ]
    board = rank_tournament(tracks)
    assert [r.key for r in board.rows] == ["b", "a"]


def test_none_calmar_sorts_after_present_within_tier():
    tracks = [
        _track("none", vj=_verdict(verdict=EDGE_CONFIRMED, n_obs=25, calmar=None)),
        _track("has", vj=_verdict(verdict=EDGE_CONFIRMED, n_obs=25, calmar="0.1")),
    ]
    board = rank_tournament(tracks)
    assert [r.key for r in board.rows] == ["has", "none"]


# ---- 직렬화 / 결정론 --------------------------------------------------------------


def test_to_json_dict_shape_and_universe_capped():
    big_universe = tuple(f"T{i}" for i in range(50))
    t = _track("x", vj=_verdict(verdict=EDGE_CONFIRMED, n_obs=25,
                                calmar="1.0", universe=big_universe))
    board = rank_tournament([t])
    d = board.to_json_dict()
    assert d["schema_version"] == "1.0"
    assert d["rows"][0]["universe_size"] == 50
    assert len(d["rows"][0]["universe"]) == 8  # 미리보기 8개로 제한
    assert d["rows"][0]["calmar"] == "1.0"


def test_as_text_contains_markers():
    tracks = [
        _track("global", incumbent=True,
               vj=_verdict(verdict=EDGE_CONFIRMED, n_obs=25, calmar="2.0")),
        _track("wide", vj=_verdict(verdict=NO_EDGE, n_obs=25, calmar="0.5")),
    ]
    txt = rank_tournament(tracks).as_text()
    assert "🏆 forward 토너먼트 리더보드" in txt
    assert "🏠" in txt  # incumbent 표식
    assert "👑" in txt  # 챔피언 표식
    assert "돈 0 이동" in txt


def test_deterministic():
    tracks = [
        _track("a", vj=_verdict(verdict=EDGE_CONFIRMED, n_obs=25, calmar="1.0")),
        _track("global", incumbent=True, vj=_verdict(n_obs=3)),
        _track("c", vj=_verdict(verdict=NO_EDGE, n_obs=25, calmar="0.2")),
    ]
    a = rank_tournament(tracks, as_of_utc="2026-06-14T00:00:00Z").to_json_dict()
    b = rank_tournament(tracks, as_of_utc="2026-06-14T00:00:00Z").to_json_dict()
    assert a == b

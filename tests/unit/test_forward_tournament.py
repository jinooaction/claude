"""스펙 053 — forward 토너먼트 리더보드 순수 코어 단위 테스트."""

from __future__ import annotations

from decimal import Decimal

from auto_invest.analytics.forward_tournament import (
    COMPARABLE,
    EDGE_CONFIRMED,
    INSUFFICIENT_DATA,
    NO_EDGE,
    OBS_HEALTH_BLOCKED,
    OBS_HEALTH_DEGRADED,
    OBS_HEALTH_OK,
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
    psr=None,
    dsr=None,
    dsr_threshold="0.95",
    universe=("SPY", "IEF", "GLD"),
):
    return {
        "verdict": verdict,
        "n_obs": n_obs,
        "min_obs_required": min_obs,
        "strategy_calmar": calmar,
        "beats_benchmark_calmar": True,
        "strategy_sharpe_annual": sharpe,
        "strategy_max_drawdown_pct": dd,
        "excess_return_pct": excess,
        "strategy_total_return_pct": "1.0",
        "psr_vs_benchmark": psr,
        "dsr": dsr,
        "dsr_threshold": dsr_threshold,
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
    assert t.beats_benchmark_calmar is True
    assert t.to_json_dict()["beats_benchmark_calmar"] is True


def test_missing_calmar_superiority_fails_closed() -> None:
    verdict = _verdict(verdict=NO_EDGE, n_obs=40)
    del verdict["beats_benchmark_calmar"]
    assert _track("x", vj=verdict).beats_benchmark_calmar is False


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
    assert board.observation_health == OBS_HEALTH_OK
    assert board.known_count == 3
    assert board.unknown_count == 0


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
    assert board.observation_health == OBS_HEALTH_BLOCKED
    assert board.known_count == 0
    assert board.unknown_count == 2


def test_non_incumbent_unknown_degrades_observation_health():
    tracks = [
        _track("global", incumbent=True, vj=_verdict(n_obs=4)),
        _track("wide", vj=None),
    ]
    board = rank_tournament(tracks)
    assert board.observation_health == OBS_HEALTH_DEGRADED
    assert board.known_count == 1
    assert board.unknown_count == 1
    assert "wide" in board.observation_note


def test_incumbent_unknown_blocks_observation_health():
    tracks = [
        _track("global", incumbent=True, vj=None),
        _track("wide", vj=_verdict(n_obs=4)),
    ]
    board = rank_tournament(tracks)
    assert board.observation_health == OBS_HEALTH_BLOCKED
    assert "라이브 검증 트랙" in board.observation_note


def test_all_premature_lagging_track_is_observation_ok():
    tracks = [
        _track("global", incumbent=True, vj=_verdict(n_obs=4)),
        _track("globalfixed", vj=_verdict(n_obs=1)),
    ]
    board = rank_tournament(tracks)
    assert board.observation_health == OBS_HEALTH_OK
    assert board.max_n_obs == 4
    assert board.min_n_obs == 1
    assert board.lagging_keys == ("globalfixed",)
    assert "최소 관측 전" in board.observation_note


def test_lagging_below_min_degrades_after_any_track_comparable():
    tracks = [
        _track("global", incumbent=True, vj=_verdict(verdict=NO_EDGE, n_obs=20)),
        _track("globalfixed", vj=_verdict(n_obs=18)),
    ]
    board = rank_tournament(tracks)
    assert board.observation_health == OBS_HEALTH_DEGRADED
    assert board.max_n_obs == 20
    assert board.min_n_obs == 18
    assert board.lagging_keys == ("globalfixed",)
    assert "최소 관측 미달" in board.observation_note


def test_lagging_after_all_tracks_comparable_is_observation_ok():
    tracks = [
        _track("global", incumbent=True, vj=_verdict(verdict=NO_EDGE, n_obs=23)),
        _track("globalfixed", vj=_verdict(verdict=NO_EDGE, n_obs=20)),
    ]
    board = rank_tournament(tracks)
    assert board.observation_health == OBS_HEALTH_OK
    assert board.max_n_obs == 23
    assert board.min_n_obs == 20
    assert board.lagging_keys == ("globalfixed",)
    assert "참고 정보" in board.observation_note


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


# ---- 교차-트랙 다중비교(본페로니) 보정 ----------------------------------------------


def _confirmed(key, *, calmar, psr=None, dsr=None, inc=False, n_obs=25):
    return _track(
        key,
        incumbent=inc,
        vj=_verdict(verdict=EDGE_CONFIRMED, n_obs=n_obs, calmar=calmar, psr=psr, dsr=dsr),
    )


def test_multiplicity_adjusted_threshold_k2():
    # K=2 비교 가능 → 보정 기준 = 1 − 0.05/2 = 0.975.
    tracks = [
        _confirmed("global", calmar="2.0", psr="0.99", inc=True),
        _track("wide", vj=_verdict(verdict=NO_EDGE, n_obs=25, calmar="0.5", psr="0.5")),
    ]
    board = rank_tournament(tracks)
    assert board.comparable_count == 2
    assert board.adjusted_dsr_threshold == Decimal("0.975")


def test_multiplicity_robust_champion_passes_bar():
    # 6 비교 가능, 챔피언 PSR 0.999 ≥ 보정 기준(0.991667) → robust True.
    tracks = [_confirmed("global", calmar="2.0", psr="0.999", inc=True)]
    tracks += [
        _track(f"t{i}", vj=_verdict(verdict=NO_EDGE, n_obs=25, calmar="0.4", psr="0.5"))
        for i in range(5)
    ]
    board = rank_tournament(tracks)
    assert board.comparable_count == 6
    assert board.adjusted_dsr_threshold == Decimal("0.991667")
    assert board.champion_multiplicity_robust is True
    assert "보정 통과" in board.headline or "보정도 통과" in board.headline


def test_multiplicity_lucky_winner_fails_bar():
    # 6 비교 가능, 챔피언 PSR 0.96 < 보정 기준(0.991667) → 운 좋은 우승 의심(robust False).
    tracks = [_confirmed("global", calmar="2.0", psr="0.96", inc=True)]
    tracks += [
        _track(f"t{i}", vj=_verdict(verdict=NO_EDGE, n_obs=25, calmar="0.4", psr="0.5"))
        for i in range(5)
    ]
    board = rank_tournament(tracks)
    assert board.champion_multiplicity_robust is False
    assert "미통과" in board.headline


def test_multiplicity_unassessed_without_significance():
    # PSR·DSR 둘 다 없으면 평가 불가(robust None) — 보수적, 거짓 자신만만 0.
    tracks = [
        _confirmed("global", calmar="2.0", inc=True),  # psr/dsr 없음
        _track("wide", vj=_verdict(verdict=NO_EDGE, n_obs=25, calmar="0.5")),
    ]
    board = rank_tournament(tracks)
    assert board.champion_multiplicity_robust is None
    assert board.champion_key == "global"  # 챔피언 선정 자체는 그대로


def test_multiplicity_uses_lower_of_psr_dsr():
    # 보수적: PSR·DSR 중 낮은 값을 유의확률로. DSR 0.96 < 보정 0.975(K=2) → 미통과.
    tracks = [
        _confirmed("global", calmar="0.4", psr="0.99", inc=True),
        _confirmed("wide", calmar="1.9", psr="0.999", dsr="0.96"),
    ]
    board = rank_tournament(tracks)
    assert board.champion_key == "wide"
    assert board.challenger_key == "wide"
    # wide 의 유의확률 = min(0.999, 0.96) = 0.96 < 0.975 → 도전자 정직 강등.
    assert board.champion_multiplicity_robust is False
    assert "재지정 보류" in board.headline


def test_multiplicity_challenger_robust_keeps_alert():
    # 도전자가 보정도 통과하면 정상 도전자 경보 유지.
    tracks = [
        _confirmed("global", calmar="0.4", psr="0.99", inc=True),
        _confirmed("wide", calmar="1.9", psr="0.999"),
    ]
    board = rank_tournament(tracks)
    assert board.challenger_key == "wide"
    assert board.champion_multiplicity_robust is True
    assert "도전자" in board.headline
    assert "운영자 게이트" in board.headline or "X.4" in board.headline


def test_multiplicity_in_to_json_dict():
    tracks = [_confirmed("global", calmar="2.0", psr="0.96", inc=True)]
    tracks += [
        _track(f"t{i}", vj=_verdict(verdict=NO_EDGE, n_obs=25, calmar="0.4", psr="0.5"))
        for i in range(5)
    ]
    d = rank_tournament(tracks).to_json_dict()
    assert d["comparable_count"] == 6
    assert d["adjusted_dsr_threshold"] == "0.991667"
    assert d["champion_multiplicity_robust"] is False
    assert d["rows"][0]["psr_vs_benchmark"] == "0.96"


def test_as_text_shows_multiplicity_line():
    tracks = [_confirmed("global", calmar="2.0", psr="0.96", inc=True)]
    tracks += [
        _track(f"t{i}", vj=_verdict(verdict=NO_EDGE, n_obs=25, calmar="0.4", psr="0.5"))
        for i in range(5)
    ]
    txt = rank_tournament(tracks).as_text()
    assert "교차-트랙 다중비교" in txt
    assert "본페로니" in txt

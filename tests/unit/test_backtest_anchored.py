"""백테스트 앵커드 엣지 판정 단위 테스트 — 깊은 OOS + 짧은 forward 지속성."""

from __future__ import annotations

from decimal import Decimal

from auto_invest.portfolio.backtest_anchored import (
    EDGE_CONFIRMED,
    INSUFFICIENT_DATA,
    NO_EDGE,
    backtest_anchored_verdict,
)


def _rets(values: list[float]) -> list[Decimal]:
    return [Decimal(str(v)) for v in values]


def _strong_oos(n: int = 120, mean: float = 0.001, amp: float = 0.004) -> list[Decimal]:
    """양(+)의 평균 + 진동(변동성>0) 일수익률 n개 — 유의한 엣지의 깊은 OOS."""
    out: list[float] = []
    for i in range(n):
        out.append(mean + (amp if i % 2 == 0 else -amp))
    return _rets(out)


def test_shallow_oos_is_insufficient():
    v = backtest_anchored_verdict(
        oos_returns=_strong_oos(n=30), forward_returns=_strong_oos(n=10)
    )
    assert v.verdict == INSUFFICIENT_DATA
    assert "OOS 관측" in v.reason


def test_weak_oos_is_no_edge():
    # 평균 0(엣지 없음) 깊은 OOS → PSR 낮음 → NO_EDGE.
    flat = _rets([0.003 if i % 2 == 0 else -0.003 for i in range(120)])
    v = backtest_anchored_verdict(oos_returns=flat, forward_returns=_strong_oos(n=10))
    assert v.verdict == NO_EDGE
    assert v.oos_significance is not None


def test_strong_oos_short_forward_consistent_confirms():
    # 깊은 유의 OOS + 짧은(5일) forward 가 OOS 와 일관 → EDGE_CONFIRMED(20일 불필요).
    v = backtest_anchored_verdict(
        oos_returns=_strong_oos(n=120),
        forward_returns=_strong_oos(n=5),
        min_forward_obs=5,
    )
    assert v.verdict == EDGE_CONFIRMED
    assert v.forward_n_obs == 5
    assert v.consistency_z is not None


def test_strong_oos_but_forward_too_short_insufficient():
    v = backtest_anchored_verdict(
        oos_returns=_strong_oos(n=120),
        forward_returns=_strong_oos(n=3),
        min_forward_obs=5,
    )
    assert v.verdict == INSUFFICIENT_DATA
    assert "forward 관측" in v.reason


def test_strong_oos_but_forward_degraded_is_no_edge():
    # 깊은 OOS 는 +엣지인데 라이브 forward 가 크게 음(−) → 지속 실패 → NO_EDGE.
    crash = _rets([-0.05] * 8)
    v = backtest_anchored_verdict(
        oos_returns=_strong_oos(n=120), forward_returns=crash, min_forward_obs=5
    )
    assert v.verdict == NO_EDGE
    assert "지속 실패" in v.reason
    assert v.consistency_z is not None and v.consistency_z < 0


def test_forward_mildly_below_still_confirms():
    # forward 가 약간 낮아도(유의하지 않게) 검증된 엣지는 지속으로 본다.
    mild = _rets([0.0005 if i % 2 == 0 else -0.0003 for i in range(8)])
    v = backtest_anchored_verdict(
        oos_returns=_strong_oos(n=120), forward_returns=mild, min_forward_obs=5
    )
    assert v.verdict == EDGE_CONFIRMED


def test_num_trials_uses_dsr_deflation():
    # num_trials>1 이면 DSR(다중검정 보정) 사용 — 시도 많을수록 깎인다(엄격).
    oos = _strong_oos(n=120)
    fwd = _strong_oos(n=8)
    v1 = backtest_anchored_verdict(oos_returns=oos, forward_returns=fwd, num_trials=1)
    v50 = backtest_anchored_verdict(
        oos_returns=oos,
        forward_returns=fwd,
        num_trials=50,
        trial_sharpe_std_annual=Decimal("0.5"),
    )
    assert v1.num_trials == 1
    assert v50.num_trials == 50
    assert v50.oos_significance is not None and v1.oos_significance is not None
    assert v50.oos_significance <= v1.oos_significance


def test_to_json_dict_shape():
    v = backtest_anchored_verdict(
        oos_returns=_strong_oos(n=120), forward_returns=_strong_oos(n=6)
    )
    d = v.to_json_dict()
    assert d["method"] == "backtest_anchored"
    assert d["verdict"] == EDGE_CONFIRMED
    assert d["oos_n_obs"] == 120
    assert d["forward_n_obs"] == 6
    assert d["dsr_threshold"] == "0.95"


def test_deterministic():
    a = backtest_anchored_verdict(
        oos_returns=_strong_oos(n=120), forward_returns=_strong_oos(n=6)
    )
    b = backtest_anchored_verdict(
        oos_returns=_strong_oos(n=120), forward_returns=_strong_oos(n=6)
    )
    assert a.to_json_dict() == b.to_json_dict()

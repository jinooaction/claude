"""탐지 규칙 (스펙 005, FR-A08·A11, R-6).

기존 `telemetry/kpi.compute_snapshot` 로 롤링 윈도 KPI 를 읽어 후보 변경을
만든다. 규칙:

- `threshold_tighten` (적용 경로 있음, L1): 30일 집계가 Tier B 안정이고
  일별로 Tier C 가 한 번도 없으면 `tier_b` 를 `tier_a` 쪽으로 조이는 후보.
- `cost_drift`/`cache_miss`/`latency_degradation` (적용 노브 없음, proposal):
  7일 KPI 가 Tier C 이하로 떨어지면 드리프트 후보(감지만, runner 가 스킵).

전부 결정론적 — 같은 입력이면 같은 후보(SC-A01).
"""

from __future__ import annotations

import sqlite3
import tomllib
from datetime import date, datetime, timedelta
from pathlib import Path

from auto_invest.telemetry.kpi import compute_snapshot
from auto_invest.telemetry.thresholds import TierTable
from auto_invest.tuner.knobs import compute_max_tokens_reduce, compute_tighten
from auto_invest.tuner.models import CandidateChange, ProposedChange

# 드리프트 감지 대상(7일 윈도).
#   - cost_drift / latency_degradation: 판단 지점 max_tokens 축소(L2, 캐너리)로 적용.
#   - cache_miss: 깨끗한 숫자 노브 없음(프롬프트 캐시 구조) → proposal_only 유지.
_DRIFT_RULES = {
    "usd_per_decision_mean": "cost_drift",
    "cache_hit_rate": "cache_miss",
    "latency_p95_ms": "latency_degradation",
}

# max_tokens 노브로 적용 가능한 드리프트(나머지는 proposal_only).
_MAX_TOKENS_DRIFTS = {"cost_drift", "latency_degradation"}

_DEFAULT_TUNABLES_PATH = "config/judgment_tunables.toml"


def _pick_max_tokens_target(tunables_path: Path) -> tuple[str, int] | None:
    """튜닝 config 에서 max_tokens 가 가장 큰 판단 지점을 결정론적으로 고른다.

    가장 비싼/긴 응답 지점을 줄이는 것이 비용·지연 드리프트에 가장 효과적.
    동률이면 이름 오름차순. 파일/유효 섹션 없으면 None(→ proposal_only 폴백).
    """
    try:
        if not tunables_path.exists():
            return None
        data = tomllib.loads(tunables_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    best: tuple[str, int] | None = None
    for name in sorted(data):
        section = data[name]
        if not isinstance(section, dict):
            continue
        raw = section.get("max_tokens")
        if not isinstance(raw, int) or isinstance(raw, bool):
            continue
        if best is None or raw > best[1]:
            best = (name, raw)
    return best


def _day_bounds(d: date) -> tuple[str, str]:
    start = f"{d.isoformat()}T00:00:00.000Z"
    end = f"{(d + timedelta(days=1)).isoformat()}T00:00:00.000Z"
    return start, end


def _window_bounds(as_of: date, days: int) -> tuple[str, str]:
    start = f"{(as_of - timedelta(days=days - 1)).isoformat()}T00:00:00.000Z"
    end = f"{(as_of + timedelta(days=1)).isoformat()}T00:00:00.000Z"
    return start, end


def _kpi_of(snapshot, kpi_name: str):
    for kpi in snapshot.kpis:
        if kpi.name == kpi_name:
            return kpi
    return None


def _is_30d_stable(
    conn: sqlite3.Connection,
    *,
    as_of: date,
    kpi_name: str,
    tiers: TierTable,
    window_long_days: int,
) -> bool:
    """일별 윈도로 Tier C(이하)가 한 번도 없는지 확인(R-6).

    데이터가 있는 날의 KPI tier 가 전부 A 또는 B 여야 안정으로 본다. 단 하나의
    Tier C/N/A 일이 있으면 불안정(엣지 케이스 직접 구현).
    """
    saw_data_day = False
    for offset in range(window_long_days):
        d = as_of - timedelta(days=offset)
        start, end = _day_bounds(d)
        snap = compute_snapshot(
            conn, window_start_utc=start, window_end_utc=end, tiers=tiers
        )
        if snap.call_count == 0:
            continue
        saw_data_day = True
        kpi = _kpi_of(snap, kpi_name)
        if kpi is None or kpi.tier not in ("A", "B"):
            return False
    return saw_data_day


def detect(
    conn: sqlite3.Connection,
    *,
    as_of: date,
    tiers: TierTable,
    thresholds_path: str,
    window_short_days: int = 7,
    window_long_days: int = 30,
    tunables_path: str = _DEFAULT_TUNABLES_PATH,
) -> list[CandidateChange]:
    """롤링 윈도 KPI 를 읽어 후보 변경 리스트를 만든다(결정론적)."""
    candidates: list[CandidateChange] = []
    tunables_target = str(tunables_path).replace("\\", "/")
    max_tokens_target = _pick_max_tokens_target(Path(tunables_path))

    short_start, short_end = _window_bounds(as_of, window_short_days)
    long_start, long_end = _window_bounds(as_of, window_long_days)
    short_snap = compute_snapshot(
        conn, window_start_utc=short_start, window_end_utc=short_end, tiers=tiers
    )
    long_snap = compute_snapshot(
        conn, window_start_utc=long_start, window_end_utc=long_end, tiers=tiers
    )

    # 규칙 1: threshold_tighten (각 KPI, 30일 안정 시) — 적용 경로 있음.
    for kpi_name, entry in tiers.entries.items():
        long_kpi = _kpi_of(long_snap, kpi_name)
        if long_kpi is None or long_kpi.tier != "B":
            continue
        if not _is_30d_stable(
            conn,
            as_of=as_of,
            kpi_name=kpi_name,
            tiers=tiers,
            window_long_days=window_long_days,
        ):
            continue
        new_b = compute_tighten(entry)
        if new_b is None:
            continue
        candidates.append(
            CandidateChange(
                candidate_id=f"threshold_tighten:{kpi_name}",
                detection_rule="threshold_tighten",
                kpi_name=kpi_name,
                observed_value=str(long_kpi.value),
                observed_tier="B",
                window=f"{window_long_days}d",
                proposed=ProposedChange(
                    kind="threshold_tighten",
                    target_paths=(thresholds_path,),
                    config_key=f"{kpi_name}.tier_b",
                    old_value=str(entry.tier_b),
                    new_value=str(new_b),
                ),
                rationale=(
                    f"{window_long_days}일 집계 Tier B 안정 + 일별 Tier C 없음 → "
                    f"tier_b 를 tier_a 쪽으로 한 스텝 조임"
                ),
                measurement_sample=long_snap.call_count,
            )
        )

    # 규칙 2~4: drift 감지(7일 Tier C 이하) — 적용 노브 없음, proposal 로만.
    for kpi_name, rule in _DRIFT_RULES.items():
        short_kpi = _kpi_of(short_snap, kpi_name)
        if short_kpi is None:
            continue
        if short_kpi.tier in ("A", "B"):
            continue
        if short_snap.call_count == 0:
            continue

        proposed = ProposedChange(kind="proposal_only", target_paths=())
        rationale = (
            f"{window_short_days}일 {kpi_name} Tier {short_kpi.tier} (드리프트) — "
            f"v1 적용 노브 없음, 제안으로만 기록"
        )
        # cost/latency 드리프트 → 가장 비싼 판단 지점 max_tokens 축소(L2, 캐너리).
        if rule in _MAX_TOKENS_DRIFTS and max_tokens_target is not None:
            dc, current = max_tokens_target
            new_mt = compute_max_tokens_reduce(current)
            if new_mt is not None:
                proposed = ProposedChange(
                    kind="max_tokens_reduce",
                    target_paths=(tunables_target,),
                    config_key=f"{dc}.max_tokens",
                    old_value=str(current),
                    new_value=str(new_mt),
                )
                rationale = (
                    f"{window_short_days}일 {kpi_name} Tier {short_kpi.tier} (드리프트) → "
                    f"{dc}.max_tokens {current}→{new_mt} 축소 후보 (L2 캐너리 검증 대상)"
                )

        candidates.append(
            CandidateChange(
                candidate_id=f"{rule}:{kpi_name}",
                detection_rule=rule,
                kpi_name=kpi_name,
                observed_value=str(short_kpi.value),
                observed_tier=short_kpi.tier,
                window=f"{window_short_days}d",
                proposed=proposed,
                rationale=rationale,
                measurement_sample=short_snap.call_count,
            )
        )

    candidates.sort(key=lambda c: c.candidate_id)
    return candidates


def parse_as_of(value: str | None) -> date:
    """`YYYY-MM-DD` 문자열을 date 로. None 이면 오늘(UTC)."""
    if value is None:
        return datetime.now().date()
    return datetime.strptime(value, "%Y-%m-%d").date()


__all__ = ["detect", "parse_as_of"]

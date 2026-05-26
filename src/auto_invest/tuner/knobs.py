"""튜닝 가능 노브 — KPI 임계값 조이기 (스펙 005, FR-A10·A11·A12, R-5).

v1 의 유일한 적용 가능 L1 노브는 `config/llm_kpi_thresholds.toml` 의 `tier_b`
임계값이다. 조이기는 `tier_b` 를 `tier_a` 쪽으로 gap 의 STEP_FRACTION 만큼
한 스텝 옮긴다(`tier_a`/`tier_c` 사이 클램프). `tier_a`·`tier_c` 는 외곽 레일로
고정한다.

쓰기는 원자적이다(임시 파일 + os.replace). 대상 KPI 의 `tier_b` 한 줄만
교체하고 주석·다른 키·다른 KPI 는 보존한다.
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from auto_invest.telemetry.thresholds import ThresholdEntry

STEP_FRACTION = Decimal("0.2")

# 판단 지점 max_tokens 를 이 아래로 내리지 않는다(품질 바닥, 스펙 012).
MAX_TOKENS_FLOOR = 32


@dataclass(frozen=True)
class ThresholdKnob:
    kpi_name: str
    config_path: Path


def _format_number(d: Decimal) -> str:
    """Decimal 을 TOML 숫자 문자열로. 정수면 int, 아니면 후행 0 제거."""
    if d == d.to_integral_value():
        return str(int(d))
    s = format(d.quantize(Decimal("0.000001")), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def compute_tighten(entry: ThresholdEntry) -> Decimal | None:
    """`tier_b` 를 `tier_a` 쪽으로 한 스텝 조인 값. 조일 여지 없으면 None.

    클램프: 결과는 `tier_a` 와 `tier_c` 사이에 엄격히 유지된다(밴드 순서
    `ThresholdEntry` 검증 통과 보장, SC-A05).
    """
    tb, ta, tc = entry.tier_b, entry.tier_a, entry.tier_c
    if entry.direction == "lower_is_better":
        # 밴드: tc > tb > ta. 더 낮을수록 좋음 → tb 를 ta 쪽(아래)으로.
        gap = tb - ta
        if gap <= 0:
            return None
        new_b = tb - STEP_FRACTION * gap
        if not (ta < new_b < tc):
            return None
    else:
        # higher_is_better, 밴드: tc < tb < ta. 더 높을수록 좋음 → tb 를 ta 쪽(위)으로.
        gap = ta - tb
        if gap <= 0:
            return None
        new_b = tb + STEP_FRACTION * gap
        if not (tc < new_b < ta):
            return None
    new_b = Decimal(_format_number(new_b))
    if new_b == tb:
        return None
    return new_b


def compute_max_tokens_reduce(current: int, *, floor: int = MAX_TOKENS_FLOOR) -> int | None:
    """`max_tokens` 를 STEP_FRACTION 만큼 줄인 값. 조일 여지 없으면 None (스펙 012).

    바닥(`floor`) 아래로는 내려가지 않는다. 한 스텝이 0 이거나 결과가 현재값과
    같으면(이미 바닥 등) None. 결정론적·가역(old 보존).
    """
    if current <= floor:
        return None
    step = int((STEP_FRACTION * Decimal(current)).to_integral_value(rounding="ROUND_DOWN"))
    if step <= 0:
        step = 1
    new_value = current - step
    if new_value < floor:
        new_value = floor
    if new_value >= current:
        return None
    return new_value


def apply_max_tokens(
    config_path: Path,
    decision_class: str,
    new_max_tokens: int,
) -> tuple[str, str]:
    """`[decision_class].max_tokens` 한 줄만 원자적 교체. 반환 `(old, new)` 문자열.

    `apply_threshold` 와 동일한 span 교체 패턴 — 주석·다른 키·다른 섹션 보존.
    섹션이나 키를 못 찾으면 ValueError.
    """
    text = config_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    section_re = re.compile(r"^\s*\[(?P<name>[^\]]+)\]\s*$")
    key_re = re.compile(r"^\s*max_tokens\s*=\s*(?P<val>[^\s#]+)")

    in_section = False
    old_value: str | None = None
    new_text_value = str(new_max_tokens)
    for i, line in enumerate(lines):
        m = section_re.match(line)
        if m:
            in_section = m.group("name").strip() == decision_class
            continue
        if in_section:
            km = key_re.match(line)
            if km:
                old_value = km.group("val")
                start, end = km.span("val")
                lines[i] = line[:start] + new_text_value + line[end:]
                break
    if old_value is None:
        raise ValueError(
            f"max_tokens for {decision_class!r} not found in {config_path}"
        )

    new_text = "".join(lines)
    dir_ = config_path.parent
    fd, tmp = tempfile.mkstemp(dir=dir_, prefix=".tune-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(new_text)
        os.replace(tmp, config_path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return old_value, new_text_value


def apply_threshold(
    config_path: Path,
    kpi_name: str,
    new_tier_b: Decimal,
) -> tuple[str, str]:
    """`[kpi_name].tier_b` 한 줄만 교체(원자적). 반환 `(old, new)` 문자열.

    주석·다른 키·다른 KPI 는 보존한다. 대상 KPI 섹션이나 tier_b 키를 못 찾으면
    ValueError.
    """
    text = config_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    section_re = re.compile(r"^\s*\[(?P<name>[^\]]+)\]\s*$")
    # `tier_b = <val>` 의 값 토큰만 span 으로 교체한다(주석·개행·다른 키 보존).
    tier_b_re = re.compile(r"^\s*tier_b\s*=\s*(?P<val>[^\s#]+)")

    in_section = False
    old_value: str | None = None
    new_text_value = _format_number(new_tier_b)
    for i, line in enumerate(lines):
        m = section_re.match(line)
        if m:
            in_section = m.group("name").strip() == kpi_name
            continue
        if in_section:
            tm = tier_b_re.match(line)
            if tm:
                old_value = tm.group("val")
                start, end = tm.span("val")
                lines[i] = line[:start] + new_text_value + line[end:]
                break
    if old_value is None:
        raise ValueError(f"tier_b for KPI {kpi_name!r} not found in {config_path}")

    new_text = "".join(lines)
    # 원자적 쓰기: 같은 디렉터리에 임시 파일 후 os.replace.
    dir_ = config_path.parent
    fd, tmp = tempfile.mkstemp(dir=dir_, prefix=".tune-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(new_text)
        os.replace(tmp, config_path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return old_value, new_text_value


__all__ = ["STEP_FRACTION", "ThresholdKnob", "apply_threshold", "compute_tighten"]

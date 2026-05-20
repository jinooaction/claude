"""Spec 010 T014 — 자동 룰 동적 검증 (백테스트 + paper-run 트리거).

본 PR에서는 다음을 수행:

1. **정적 검증**: `design.validator.validate_generated_rules` 호출.
2. **백테스트 (stub)**: spec 008 미완성. `BACKTEST_AVAILABLE`이 False면 한글
   경고 후 통과 처리. spec 008 완성 후 별도 PR에서 활성화 (R-D11).
3. **paper-run 1일분 (stub)**: 본 PR에서는 paper-run subprocess 트리거 stub.
   spec 009 통합은 후속 PR. 현재는 정적 검증만 통과해도 OK로 본다.

후속 PR에서 verifier가 spec 008 backtest + spec 009 paper-run을 실제 호출하도록
교체된다. 이번 PR은 자동 룰 설계자의 명령 진입점·Claude 호출·정적 검증·OK
인터랙티브까지를 안전하게 동작시키는 데 집중.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from auto_invest.design.validator import (
    validate_generated_rules,
)

try:
    from auto_invest.backtest.runner import run_backtest  # type: ignore
    BACKTEST_AVAILABLE = True
except ImportError:
    BACKTEST_AVAILABLE = False
    run_backtest = None  # type: ignore[assignment]


@dataclass(frozen=True)
class VerifyResult:
    """`verify_rules`의 결과.

    - ok=True: 모든 검증 통과. 호출자가 운영자 OK 단계 진입.
    - ok=False: 거부. `reason`/`detail`로 RULE_DESIGN_REJECTED 작성.
    """

    ok: bool
    reason: str | None = None
    detail: str = ""
    backtest_skipped: bool = False
    paper_run_skipped: bool = False


def verify_rules(
    toml_text: str,
    *,
    kis_balance_usd: Decimal,
) -> VerifyResult:
    """생성된 룰 TOML을 정적 + (가능하면) 동적 검증.

    backtest 미가용 시 한글 안내 + 통과 처리. paper-run 동적 검증은 후속 PR.
    """
    # 1. 정적 검증.
    static = validate_generated_rules(
        toml_text,
        kis_balance_usd=kis_balance_usd,
    )
    if not static.ok:
        return VerifyResult(
            ok=False,
            reason=static.reason,
            detail=static.detail,
        )

    # 2. 백테스트 (스펙 008 가용 시) — TODO 후속 PR에서 run_backtest 호출.
    backtest_skipped = not BACKTEST_AVAILABLE

    # 3. paper-run 1일분 — 본 PR에서는 stub.
    paper_run_skipped = True

    return VerifyResult(
        ok=True,
        backtest_skipped=backtest_skipped,
        paper_run_skipped=paper_run_skipped,
    )


def availability_notice() -> str:
    """운영자에게 어느 검증 단계가 가용한지 한글로 안내."""
    parts = []
    if not BACKTEST_AVAILABLE:
        parts.append("- 백테스트 검증: spec 008 완성 후 활성화 예정 (현재는 통과 처리)")
    parts.append("- paper-run 1일분 검증: 후속 PR에서 활성화 예정 (현재는 통과 처리)")
    parts.append("- 정적 검증: 활성화 (cap·whitelist·자본 한도·종목 형식)")
    return "검증 단계 가용성:\n" + "\n".join(parts)

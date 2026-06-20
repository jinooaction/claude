#!/usr/bin/env python3
"""Validate that a pull request body keeps the required quality-gate sections."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQUIRED_HEADINGS = [
    "# 변경 요약",
    "## 위험 등급",
    "## 문제 정의",
    "## 탐색 근거",
    "## 변경 내용",
    "## 검증",
    "## 하네스 검증",
    "## 안전 경계",
    "## 인계",
    "## 자동 머지 준비",
]

REQUIRED_FIELDS = [
    "요청",
    "실제 목표",
    "비목표",
    "위험",
    "완료 기준",
]


def _line_value(body: str, label: str) -> str | None:
    match = re.search(
        rf"^- {re.escape(label)}:[^\S\r\n]*([^\r\n]*)$",
        body,
        re.MULTILINE,
    )
    if not match:
        return None
    value = match.group(1).strip()
    if not value or value == "-":
        return None
    return value


def _selected_risk_grade(body: str) -> int | None:
    match = re.search(r"^- \[[xX]\] 등급 ([0-4]):", body, re.MULTILINE)
    if not match:
        return None
    return int(match.group(1))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check that a PR body includes the Codex quality-gate sections."
    )
    parser.add_argument("path", type=Path, help="Path to a pull request body markdown file")
    parser.add_argument(
        "--template",
        action="store_true",
        help="Only validate template structure; do not require filled-in values.",
    )
    args = parser.parse_args()

    try:
        body = args.path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"failed to read {args.path}: {exc}", file=sys.stderr)
        return 2

    missing = [heading for heading in REQUIRED_HEADINGS if heading not in body]
    if missing:
        print("missing required PR quality-gate sections:", file=sys.stderr)
        for heading in missing:
            print(f"- {heading}", file=sys.stderr)
        return 1

    if not args.template:
        errors: list[str] = []
        selected_grade = _selected_risk_grade(body)
        if selected_grade is None:
            errors.append("위험 등급 하나를 [x]로 선택해야 합니다.")

        for field in REQUIRED_FIELDS:
            value = _line_value(body, field)
            if not value:
                errors.append(f"문제 정의의 '{field}' 값을 채워야 합니다.")

        harness_value = _line_value(body, "하네스 평가")
        if not harness_value:
            errors.append("하네스 검증의 '하네스 평가' 값을 채워야 합니다.")
        elif (
            selected_grade is not None
            and selected_grade >= 2
            and "agent_harness_probe.py --strict" not in harness_value
        ):
            errors.append(
                "등급 2 이상 변경은 "
                "`uv run python scripts/agent_harness_probe.py --strict` "
                "실행 결과를 하네스 평가에 남겨야 합니다."
            )

        if "없음 / 있음" in body:
            errors.append("안전 경계의 '없음 / 있음' 선택지를 실제 값으로 바꿔야 합니다.")

        if errors:
            print("PR quality gate failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1

    print("pr-quality-gate-ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

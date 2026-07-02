"""Generate the mobile-first operator status page.

This is read-only visibility tooling. It reads already-published automation
sidecars and renders a static HTML page for GitHub Pages. It never reaches the
broker, the live server, secrets, or the trading database.
"""

from __future__ import annotations

import argparse
import html
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.operator_status import OperatorStatusReport, parse_operator_status
from auto_invest.analytics.pipeline_liveness import (
    CRITICAL,
    DEGRADED,
    HEALTHY,
    LivenessCheck,
    SidecarSpec,
    assess_liveness,
    default_specs,
)

WORKFLOW_BY_KEY = {
    "rebalance-paper-forward": "rebalance-paper-forward.yml",
    "edge-autoarm": "forward-edge-autoarm.yml",
    "kis-smoke": "kis-smoke.yml",
    "rebalance-live-canary": "rebalance-live-canary.yml",
    "collect-public-data": "collect-public-data.yml",
    "regime-stratify": "regime-stratify.yml",
    "promote-readiness": "promote-readiness.yml",
    "money-path": "money-path.yml",
    "reassign": "reassign-on-tournament.yml",
    "operator-status": "operator-mobile-alerts.yml",
}

LABEL_BY_KEY = {
    "rebalance-paper-forward": "전진 페이퍼",
    "edge-autoarm": "자본 사다리",
    "kis-smoke": "KIS 연결",
    "rebalance-live-canary": "라이브 캐너리",
    "collect-public-data": "공개 데이터",
    "regime-stratify": "레짐 층화",
    "promote-readiness": "승격 준비",
    "money-path": "첫 자본 경로",
    "reassign": "전략 재지정",
    "operator-status": "운영자 상태",
}

STATUS_LABEL = {
    "OK": "정상",
    "LATE": "지연",
    "STALE": "오래됨",
    "MISSING": "없음",
    "PENDING": "대기",
}

OVERALL_LABEL = {
    HEALTHY: "정상",
    DEGRADED: "주의",
    CRITICAL: "위험",
}

OVERALL_SUMMARY = {
    HEALTHY: "핵심 자동화가 기대 시간 안에 갱신됐습니다.",
    DEGRADED: "핵심 주문 경로는 막히지 않았지만, 일부 보조 보고가 늦었습니다.",
    CRITICAL: "핵심 자동화 중 하나 이상이 멈췄을 수 있습니다.",
}


@dataclass(frozen=True)
class RenderContext:
    repository: str
    commit: str
    run_url: str | None
    generated_at: datetime
    source: str


def _read_observations(sidecar_dir: Path, specs: list[SidecarSpec]) -> dict[str, str | None]:
    observations: dict[str, str | None] = {}
    for spec in specs:
        path = sidecar_dir / f"{spec.key}.md"
        try:
            observations[spec.key] = path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            observations[spec.key] = None
    return observations


def _read_operator_status(sidecar_dir: Path) -> OperatorStatusReport | None:
    try:
        raw = (sidecar_dir / "operator-status.md").read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    return parse_operator_status(raw)


def _format_age(check: LivenessCheck) -> str:
    if check.age_hours is None:
        return "-"
    if check.age_hours < 1:
        return f"{check.age_hours * 60:.0f}분 전"
    return f"{check.age_hours:.1f}시간 전"


def _workflow_url(repository: str, key: str) -> str | None:
    workflow = WORKFLOW_BY_KEY.get(key)
    if not workflow:
        return None
    return f"https://github.com/{repository}/actions/workflows/{workflow}"


def _branch_url(repository: str, branch: str, filename: str) -> str:
    return f"https://github.com/{repository}/blob/{branch}/{filename}"


def _html_link(label: str, url: str | None) -> str:
    safe_label = html.escape(label)
    if not url:
        return safe_label
    return f'<a href="{html.escape(url)}">{safe_label}</a>'


def _status_class(status: str) -> str:
    return status.lower().replace("_", "-")


def _render_rows(
    *,
    checks: list[LivenessCheck],
    specs_by_key: dict[str, SidecarSpec],
    repository: str,
    critical_only: bool,
) -> str:
    rows: list[str] = []
    selected = [c for c in checks if c.critical == critical_only]
    for check in selected:
        spec = specs_by_key[check.key]
        workflow = _workflow_url(repository, check.key)
        sidecar = _branch_url(repository, spec.branch, spec.filename)
        label = LABEL_BY_KEY.get(check.key, check.key)
        status_label = STATUS_LABEL.get(check.status, check.status)
        rows.append(
            "\n".join(
                [
                    f'<article class="status-row {html.escape(_status_class(check.status))}">',
                    '  <div class="row-main">',
                    f"    <h3>{html.escape(label)}</h3>",
                    f"    <p>{html.escape(spec.description)}</p>",
                    "  </div>",
                    '  <div class="row-state">',
                    f'    <span class="badge">{html.escape(status_label)}</span>',
                    f"    <strong>{html.escape(_format_age(check))}</strong>",
                    f"    <small>{html.escape(check.timestamp_utc or '갱신 기록 없음')}</small>",
                    "  </div>",
                    '  <div class="row-links">',
                    f"    {_html_link('실행', workflow)}",
                    f"    {_html_link('기록', sidecar)}",
                    "  </div>",
                    "</article>",
                ]
            )
        )
    return "\n".join(rows)


def _render_json_script(report_dict: dict) -> str:
    payload = json.dumps(report_dict, ensure_ascii=False, separators=(",", ":"))
    return (
        '<script type="application/json" id="status-data">'
        f"{html.escape(payload)}"
        "</script>"
    )


def _render_optional_json_script(report: OperatorStatusReport | None) -> str:
    if report is None:
        return ""
    payload = json.dumps(report.to_dict(), ensure_ascii=False, separators=(",", ":"))
    return (
        '<script type="application/json" id="operator-status-data">'
        f"{html.escape(payload)}"
        "</script>"
    )


def _operator_status_class(status: str) -> str:
    return {
        "OK": "ok",
        "ATTENTION": "degraded",
        "ACTION_REQUIRED": "critical",
        "CRITICAL": "critical",
    }.get(status, "degraded")


def _render_operator_block(report: OperatorStatusReport | None) -> str:
    if report is None:
        return """
    <section class="operator-panel degraded" aria-labelledby="operator-title">
      <div>
        <p id="operator-title">운영자 요약</p>
        <h2>대기</h2>
        <p>operator-status sidecar가 아직 없습니다. 다음 알림 루프 실행 뒤 이 영역이 채워집니다.</p>
      </div>
    </section>
"""
    sections = "\n".join(
        "\n".join(
            [
                '<article class="operator-section">',
                f"  <span>{html.escape(section.title_ko)}</span>",
                f"  <strong>{html.escape(section.status)}</strong>",
                f"  <p>{html.escape(section.body_ko)}</p>",
                "</article>",
            ]
        )
        for section in report.dashboard_sections
    )
    action_surfaces = [
        surface
        for surface in report.surfaces
        if surface.severity in {"action", "critical"}
    ]
    if action_surfaces:
        action_list = "\n".join(
            f"<li><strong>{html.escape(surface.key)}</strong>: "
            f"{html.escape(surface.summary_ko)}</li>"
            for surface in action_surfaces
        )
    else:
        action_list = "<li>개입 필요 항목이 없습니다.</li>"
    status_class = html.escape(_operator_status_class(report.overall_status))
    return f"""
    <section class="operator-panel {status_class}" aria-labelledby="operator-title">
      <div>
        <p id="operator-title">운영자 요약</p>
        <h2>{html.escape(report.overall_status)}</h2>
        <p>{html.escape(report.headline_ko)}</p>
      </div>
      <div class="operator-next">
        <span>다음 행동</span>
        <strong>{html.escape(report.next_action_ko)}</strong>
      </div>
      <div class="operator-grid">
        {sections}
      </div>
      <div class="action-list">
        <span>개입 필요</span>
        <ul>{action_list}</ul>
      </div>
    </section>
"""


def render_status_page(
    *,
    sidecar_dir: Path,
    context: RenderContext,
) -> str:
    specs = default_specs()
    observations = _read_observations(sidecar_dir, specs)
    report = assess_liveness(specs, observations, context.generated_at)
    operator_report = _read_operator_status(sidecar_dir)
    specs_by_key = {spec.key: spec for spec in specs}
    report_dict = report.as_dict()

    generated_at = context.generated_at.strftime("%Y-%m-%d %H:%M UTC")
    commit_short = context.commit[:7] if context.commit else "unknown"
    repo_url = f"https://github.com/{context.repository}"
    actions_url = f"{repo_url}/actions"
    source_label = context.source

    critical_rows = _render_rows(
        checks=report.checks,
        specs_by_key=specs_by_key,
        repository=context.repository,
        critical_only=True,
    )
    support_rows = _render_rows(
        checks=report.checks,
        specs_by_key=specs_by_key,
        repository=context.repository,
        critical_only=False,
    )
    run_link = _html_link("생성 실행", context.run_url)
    operator_block = _render_operator_block(operator_report)

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>auto-invest 모바일 상태판</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --surface: #ffffff;
      --surface-soft: #eef2f5;
      --text: #17202a;
      --muted: #617080;
      --border: #d9e0e7;
      --ok: #16835a;
      --late: #b7791f;
      --bad: #c93434;
      --pending: #52677a;
      --focus: #1f6feb;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #101418;
        --surface: #171d23;
        --surface-soft: #202832;
        --text: #eef3f7;
        --muted: #9aa8b5;
        --border: #303b45;
        --ok: #43c18f;
        --late: #d89b3d;
        --bad: #f36a6a;
        --pending: #9aa8b5;
        --focus: #78aaff;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }}
    a {{
      color: var(--focus);
      text-decoration: none;
    }}
    a:focus-visible, button:focus-visible {{
      outline: 3px solid var(--focus);
      outline-offset: 3px;
    }}
    main {{
      width: min(980px, 100%);
      margin: 0 auto;
      padding: 16px;
    }}
    header {{
      padding: 18px 0 14px;
      border-bottom: 1px solid var(--border);
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: clamp(1.45rem, 6vw, 2.4rem);
      letter-spacing: 0;
    }}
    h2 {{
      margin: 24px 0 10px;
      font-size: 1rem;
      letter-spacing: 0;
    }}
    p {{ margin: 0; }}
    .hero {{
      display: grid;
      gap: 12px;
      padding: 16px;
      margin-top: 16px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
    }}
    .overall {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }}
    .overall strong {{
      font-size: clamp(2rem, 13vw, 4rem);
      line-height: 1;
    }}
    .overall.ok strong {{ color: var(--ok); }}
    .overall.degraded strong {{ color: var(--late); }}
    .overall.critical strong {{ color: var(--bad); }}
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }}
    .meta-item {{
      min-width: 0;
      padding: 10px;
      background: var(--surface-soft);
      border-radius: 8px;
    }}
    .meta-item span {{
      display: block;
      color: var(--muted);
      font-size: .76rem;
    }}
    .meta-item strong {{
      display: block;
      margin-top: 2px;
      overflow-wrap: anywhere;
      font-size: .92rem;
    }}
    .status-row {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: center;
      padding: 12px;
      margin: 8px 0;
      background: var(--surface);
      border: 1px solid var(--border);
      border-left-width: 5px;
      border-radius: 8px;
    }}
    .status-row.ok {{ border-left-color: var(--ok); }}
    .status-row.late {{ border-left-color: var(--late); }}
    .status-row.stale, .status-row.missing {{ border-left-color: var(--bad); }}
    .status-row.pending {{ border-left-color: var(--pending); }}
    .row-main h3 {{
      margin: 0 0 3px;
      font-size: 1rem;
    }}
    .row-main p {{
      color: var(--muted);
      font-size: .82rem;
    }}
    .row-state {{
      min-width: 92px;
      text-align: right;
    }}
    .badge {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 999px;
      background: var(--surface-soft);
      font-size: .78rem;
      font-weight: 700;
    }}
    .row-state strong {{
      display: block;
      margin-top: 4px;
      font-size: .86rem;
    }}
    .row-state small {{
      display: block;
      max-width: 150px;
      margin-top: 2px;
      color: var(--muted);
      font-size: .7rem;
      overflow-wrap: anywhere;
    }}
    .row-links {{
      grid-column: 1 / -1;
      display: flex;
      gap: 12px;
      padding-top: 4px;
      font-size: .88rem;
    }}
    .note {{
      margin: 18px 0 32px;
      padding: 12px;
      color: var(--muted);
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      font-size: .88rem;
    }}
    .operator-panel {{
      display: grid;
      gap: 12px;
      margin-top: 16px;
      padding: 16px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-left: 5px solid var(--pending);
      border-radius: 8px;
    }}
    .operator-panel.ok {{ border-left-color: var(--ok); }}
    .operator-panel.degraded {{ border-left-color: var(--late); }}
    .operator-panel.critical {{ border-left-color: var(--bad); }}
    .operator-panel h2 {{
      margin: 2px 0 6px;
      font-size: 1.45rem;
    }}
    .operator-next {{
      padding: 12px;
      background: var(--surface-soft);
      border-radius: 8px;
    }}
    .operator-next span, .operator-section span, .action-list span {{
      display: block;
      color: var(--muted);
      font-size: .76rem;
      font-weight: 700;
    }}
    .operator-next strong {{
      display: block;
      margin-top: 4px;
      overflow-wrap: anywhere;
    }}
    .operator-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 8px;
    }}
    .operator-section {{
      min-width: 0;
      padding: 10px;
      background: var(--surface-soft);
      border-radius: 8px;
    }}
    .operator-section strong {{
      display: block;
      margin-top: 2px;
      font-size: .9rem;
    }}
    .operator-section p {{
      margin-top: 4px;
      color: var(--muted);
      font-size: .82rem;
      overflow-wrap: anywhere;
    }}
    .action-list ul {{
      margin: 6px 0 0;
      padding-left: 18px;
      color: var(--muted);
    }}
    .action-list li {{
      margin: 4px 0;
      overflow-wrap: anywhere;
    }}
    @media (min-width: 720px) {{
      main {{ padding: 28px; }}
      .hero {{ grid-template-columns: 1.2fr 1fr; align-items: center; }}
      .meta-grid {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
      .status-row {{ grid-template-columns: minmax(0, 1fr) 170px 100px; }}
      .row-links {{ grid-column: auto; justify-content: flex-end; }}
      .operator-panel {{ grid-template-columns: minmax(0, 1fr) 1fr; }}
      .operator-grid, .action-list {{ grid-column: 1 / -1; }}
      .operator-grid {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>auto-invest 상태판</h1>
      <p>모바일에서 자동화 생존 상태를 빠르게 확인하는 읽기 전용 화면입니다.</p>
    </header>

    <section class="hero" aria-labelledby="overall-title">
      <div>
        <p id="overall-title">전체 상태</p>
        <div class="overall {html.escape(report.overall.lower())}">
          <strong>{html.escape(OVERALL_LABEL.get(report.overall, report.overall))}</strong>
        </div>
        <p>{html.escape(OVERALL_SUMMARY.get(report.overall, report.overall))}</p>
      </div>
      <div class="meta-grid" aria-label="생성 정보">
        <div class="meta-item">
          <span>생성 시각</span><strong>{html.escape(generated_at)}</strong>
        </div>
        <div class="meta-item">
          <span>기준 커밋</span><strong>{html.escape(commit_short)}</strong>
        </div>
        <div class="meta-item">
          <span>데이터 원천</span><strong>{html.escape(source_label)}</strong>
        </div>
        <div class="meta-item">
          <span>저장소</span><strong>{_html_link(context.repository, repo_url)}</strong>
        </div>
      </div>
    </section>

    {operator_block}

    <h2>핵심 자동화</h2>
    {critical_rows}

    <h2>보조 보고</h2>
    {support_rows}

    <section class="note" aria-label="안전 설명">
      이 화면은 GitHub Actions와 automation 사이드카의 공개 실행 기록만 읽습니다.
      KIS 비밀값, 계좌번호, 주문 권한, 서버 데이터베이스에는 접근하지 않습니다.
      실거래 가능 여부의 최종 판단은 라이브 서버의 halt 상태와 감사 로그 확인이 필요합니다.
      빠른 이동: {_html_link("전체 Actions", actions_url)} · {run_link}
    </section>

    {_render_json_script(report_dict)}
    {_render_optional_json_script(operator_report)}
  </main>
</body>
</html>
"""


def _parse_now(raw: str | None) -> datetime:
    if raw:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return datetime.now(UTC)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sidecar-dir", required=True)
    parser.add_argument("--output", default="docs/status.html")
    parser.add_argument("--repository", default="jinooaction/claude")
    parser.add_argument("--commit", default="")
    parser.add_argument("--run-url", default=None)
    parser.add_argument("--source", default="automation sidecars")
    parser.add_argument("--now", default=None)
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="Print key<TAB>branch<TAB>filename for required sidecars and exit.",
    )
    args = parser.parse_args(argv)

    if args.manifest:
        for spec in default_specs():
            print(f"{spec.key}\t{spec.branch}\t{spec.filename}")
        return 0

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    html_text = render_status_page(
        sidecar_dir=Path(args.sidecar_dir),
        context=RenderContext(
            repository=args.repository,
            commit=args.commit,
            run_url=args.run_url,
            generated_at=_parse_now(args.now),
            source=args.source,
        ),
    )
    output.write_text(html_text, encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""스펙 051 — 자율 파이프라인 생존 감시(staleness watchdog).

운영자 상시 지시(2026-06-13): "세계 최고 수준의 사람 개입 없는 완벽한 자동 시스템 +
세계 최고 수준의 안정성." 이 모듈은 그 빈칸을 메운다.

배경(왜 필요한가):
  자율 시스템은 여러 스케줄 워크플로(전진 페이퍼·자본 사다리 게이트·KIS smoke·
  라이브 캐너리·수집·층화·승격 평가)로 굴러간다. 각 워크플로는 *자기* 사이드카에
  *자기* 타임스탬프만 찍을 뿐, "전체 파이프라인이 살아있나 — 모든 핵심 사이드카가
  기대 주기 안에 갱신됐나"를 보는 단일 감시자가 없었다. 그래서 예컨대 전진 페이퍼가
  조용히 멈추면(시크릿 만료·서버 SSH 단절·GitHub 60일 비활동 스케줄 정지) 전진 엣지가
  *얼어붙는데*, 자본 사다리는 계속 WAIT_EDGE(단 0, 자본 0%)만 보고해 "정상 누적 중"과
  "2주 전 죽어서 멈춤"이 구분되지 않는다. 이 프로젝트가 반복적으로 물렸던 "침묵 실패"
  부류다.

이 모듈이 하는 일:
  각 핵심 사이드카의 `timestamp_utc` 를 읽어 나이를 계산하고, 사이드카별 기대 주기
  (`max_age_hours`)에 비춰 OK/LATE/STALE/MISSING 으로 등급을 매긴다. 종합 판정은
  최악값. *핵심(critical)* 사이드카가 STALE/MISSING 이면 종합 CRITICAL → 워크플로가
  빨갛게 실패(loud)한다. 연구/보고용 사이드카는 저하(DEGRADED)로만 잡아 거짓 경보를
  줄인다.

안전 경계(중요):
  읽기 전용·순수·결정론·비커널. 주문 0건, 돈 0 이동. 이건 *감시/보고*이지 거래나
  자본 변경이 아니다. 전진 페이퍼가 멈춰 엣지가 얼어붙는 것은 자본 측면에서는 이미
  fail-safe(얼어붙은 엣지는 EDGE_CONFIRMED 를 못 만들어 절대 승격하지 않는다) — 이
  감시자의 가치는 그 정지를 *드러내는 것*이지 돈을 지키는 게 아니다(돈은 자본 사다리
  게이트의 fail-closed + 스펙 014 서킷 브레이커가 지킨다).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

SCHEMA_VERSION = "1.0"

# 사이드카별 등급 (per-check)
OK = "OK"  # 신선 — 기대 주기 안
LATE = "LATE"  # 1주기~2주기 지연 — 일시적일 수 있음
STALE = "STALE"  # 2주기 초과 — 명백한 정지
MISSING = "MISSING"  # 사이드카/타임스탬프 없음(첫 실행 예정 지남 또는 확립 후 소실)
PENDING = "PENDING"  # 신규 루프 — 첫 실행 예정 시각 전이라 아직 사이드카 없음(정상, 거짓경보 아님)

# 종합 판정 (overall)
HEALTHY = "OK"
DEGRADED = "DEGRADED"
CRITICAL = "CRITICAL"

_OVERALL_SEVERITY = {HEALTHY: 0, DEGRADED: 1, CRITICAL: 2}

# `timestamp_utc` 옆에 붙은 ISO-8601 UTC 타임스탬프(소수 초·Z 허용)를 찾는다.
# LAST_RUN.md 의 마크다운 표 행(`| timestamp_utc | ... |`)과 JSON 둘 다 매칭.
_TS_RE = re.compile(
    r"timestamp_utc[^0-9]*?(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)"
)


@dataclass(frozen=True)
class SidecarSpec:
    """감시 대상 사이드카 한 개의 명세."""

    key: str
    branch: str  # automation/<...>-last-run
    filename: str  # 보통 LAST_RUN.md
    max_age_hours: float  # 정상 최대 나이(주말/연휴 갭 + 여유 포함)
    critical: bool  # True 면 STALE/MISSING 시 종합 CRITICAL(워크플로 빨강)
    description: str
    # 신규 루프의 첫 사이드카 예상 시각(ISO-8601 UTC). 설정 시: 사이드카 없음이 이
    # 시각+max_age 전이면 PENDING(정상, 첫 실행 대기), 후면 MISSING(첫 실행 실패 의심).
    # None(기본) = 확립된 루프 — 사이드카 없으면 즉시 MISSING(기존 동작).
    first_expected_utc: str | None = None


@dataclass(frozen=True)
class LivenessCheck:
    """사이드카 한 개의 생존 판정."""

    key: str
    status: str  # OK | LATE | STALE | MISSING
    critical: bool
    age_hours: float | None
    max_age_hours: float
    timestamp_utc: str | None
    detail: str

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "status": self.status,
            "critical": self.critical,
            "age_hours": (round(self.age_hours, 2) if self.age_hours is not None else None),
            "max_age_hours": self.max_age_hours,
            "timestamp_utc": self.timestamp_utc,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class LivenessReport:
    """전체 파이프라인 생존 종합 보고."""

    schema_version: str
    as_of_utc: str
    overall: str  # OK | DEGRADED | CRITICAL
    checks: list[LivenessCheck]

    @property
    def exit_code(self) -> int:
        """종합 CRITICAL 일 때만 1(워크플로 빨강). 그 외 0."""
        return 1 if self.overall == CRITICAL else 0

    @property
    def stale_critical(self) -> list[LivenessCheck]:
        return [c for c in self.checks if c.critical and c.status in (STALE, MISSING)]

    def as_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "as_of_utc": self.as_of_utc,
            "overall": self.overall,
            "checks": [c.to_dict() for c in self.checks],
        }

    def as_text(self) -> str:
        icon = {OK: "🟢", LATE: "🟡", STALE: "🔴", MISSING: "⬛", PENDING: "⏳"}
        overall_icon = {HEALTHY: "🟢", DEGRADED: "🟡", CRITICAL: "🔴"}[self.overall]
        lines = [
            f"# 파이프라인 생존 감시 (as of {self.as_of_utc}) — 읽기 전용, 돈 0 이동",
            "",
            f"종합 판정: {overall_icon} **{self.overall}**",
            "",
            "| 사이드카 | 핵심 | 상태 | 나이(h) | 한계(h) | 마지막 갱신 |",
            "|----------|:----:|:----:|--------:|--------:|-------------|",
        ]
        for c in self.checks:
            age = f"{c.age_hours:.1f}" if c.age_hours is not None else "—"
            crit = "✔" if c.critical else ""
            lines.append(
                f"| {c.key} | {crit} | {icon.get(c.status, '?')} {c.status} | "
                f"{age} | {c.max_age_hours:.0f} | {c.timestamp_utc or '(없음)'} |"
            )
        lines.append("")
        for c in self.checks:
            if c.status != OK:
                lines.append(f"- **{c.key}** ({c.status}): {c.detail}")
        if self.overall == CRITICAL:
            lines += [
                "",
                "🔴 **핵심 사이드카 정지** — 자율 머니루프의 일부가 며칠째 갱신되지 않았다.",
                "   GitHub Actions 탭에서 해당 워크플로의 마지막 실행 실패 사유를 확인하라",
                "   (시크릿 만료·서버 SSH 단절·스케줄 비활성화 등). 돈은 안 움직이지만",
                "   (얼어붙은 엣지는 절대 자동 승격 안 함), 자율 성장이 멈춘 상태다.",
            ]
        elif self.overall == HEALTHY:
            lines += ["", "🟢 모든 핵심 사이드카 신선 — 자율 파이프라인 정상 가동."]
        lines += [
            "",
            "⚠ 이건 감시 보고다(읽기 전용). 거래·자본 변경 없음 — "
            "라이브는 운영자 게이트(헌법 X.4).",
        ]
        return "\n".join(lines)


def parse_timestamp_utc(text: str | None) -> str | None:
    """사이드카 본문에서 `timestamp_utc` ISO-8601 값을 추출(없으면 None)."""
    if not text:
        return None
    m = _TS_RE.search(text)
    return m.group(1) if m else None


def _age_hours(ts_str: str, now: datetime) -> float:
    """ISO-8601 UTC 타임스탬프와 now 사이의 시간(시간 단위)."""
    parsed = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return (now - parsed).total_seconds() / 3600.0


def _classify(age_hours: float, max_age_hours: float) -> str:
    if age_hours <= max_age_hours:
        return OK
    if age_hours <= 2 * max_age_hours:
        return LATE
    return STALE


def _contribution(status: str, critical: bool) -> str:
    """이 판정이 종합 판정에 기여하는 심각도."""
    if status in (OK, PENDING):
        return HEALTHY  # PENDING = 첫 실행 전 신규 루프 — 정상(경보 아님)
    if status == LATE:
        return DEGRADED if critical else HEALTHY
    # STALE 또는 MISSING
    return CRITICAL if critical else DEGRADED


def assess_liveness(
    specs: list[SidecarSpec],
    observations: dict[str, str | None],
    now: datetime,
) -> LivenessReport:
    """사이드카 명세 + 관측(원문 dict)으로 생존 보고를 구성(순수·결정론).

    observations: spec.key → 사이드카 원문(없으면 None). 워크플로가 git show 로 채운다.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    checks: list[LivenessCheck] = []
    overall = HEALTHY
    for spec in specs:
        raw = observations.get(spec.key)
        ts = parse_timestamp_utc(raw)
        if ts is None:
            age = None
            # 사이드카 없음 — "첫 실행 전 신규 루프(정상)"인지 "침묵 정지(이상)"인지
            # 구분해 거짓경보를 막는다. first_expected_utc 가 있으면 그 시각+한계로 판단.
            if spec.first_expected_utc is not None and (
                _age_hours(spec.first_expected_utc, now) < spec.max_age_hours
            ):
                # 첫 실행 예정 시각 + 한계 전 — 아직 안 태어남(정상, 거짓경보 아님).
                status = PENDING
                detail = (
                    f"{spec.description} — 신규 루프, 첫 실행 예정("
                    f"{spec.first_expected_utc}) 전이라 사이드카 미발행(정상)."
                )
            elif spec.first_expected_utc is not None:
                # 첫 실행 예정 + 한계 지났는데도 없음 — 첫 실행 자체가 실패했을 가능성.
                status = MISSING
                detail = (
                    f"{spec.description} — 첫 실행 예정({spec.first_expected_utc})"
                    f"+한계 {spec.max_age_hours:.0f}h 지났는데 미발행({spec.branch}). "
                    f"첫 실행 실패 의심."
                )
            else:
                # 확립된 루프 — 사이드카 없으면 비정상(기존 동작).
                status = MISSING
                detail = (
                    f"{spec.description} — 사이드카/타임스탬프 없음("
                    f"{spec.branch} 미발행 또는 비정상)."
                )
        else:
            age = _age_hours(ts, now)
            status = _classify(age, spec.max_age_hours)
            if status == OK:
                detail = f"{spec.description} — 신선({age:.1f}h)."
            elif status == LATE:
                detail = (
                    f"{spec.description} — {age:.1f}h 경과(한계 {spec.max_age_hours:.0f}h "
                    f"초과). 일시적 지연일 수 있음."
                )
            else:  # STALE
                detail = (
                    f"{spec.description} — {age:.1f}h 경과(한계 {spec.max_age_hours:.0f}h "
                    f"의 2배 초과). 워크플로가 멈췄을 가능성이 높다."
                )
        checks.append(
            LivenessCheck(
                key=spec.key,
                status=status,
                critical=spec.critical,
                age_hours=age,
                max_age_hours=spec.max_age_hours,
                timestamp_utc=ts,
                detail=detail,
            )
        )
        contrib = _contribution(status, spec.critical)
        if _OVERALL_SEVERITY[contrib] > _OVERALL_SEVERITY[overall]:
            overall = contrib

    return LivenessReport(
        schema_version=SCHEMA_VERSION,
        as_of_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        overall=overall,
        checks=checks,
    )


def default_specs() -> list[SidecarSpec]:
    """자율 머니루프의 핵심·연구 사이드카 레지스트리.

    max_age_hours 는 *정상* 최대 나이로 넉넉히 잡는다(거짓 경보가 최악 — 운영자가
    경보를 무시하게 된다). 평일(`* * 1-5`) 스케줄 사이드카는 주말 갭(금요일 밤 →
    월요일 밤 ≈ 72h)을 견디도록 80h. 매일 스케줄은 한 번 빠뜨려도 안 울리고 연속
    정지만 잡도록 30h.
    """
    return [
        # ── 핵심: 자율 머니루프의 직접 경로 ──
        SidecarSpec(
            key="rebalance-paper-forward",
            branch="automation/rebalance-paper-forward-last-run",
            filename="LAST_RUN.md",
            max_age_hours=80.0,  # 평일 22:30, 주말 갭 견딤
            critical=True,
            description="전진 페이퍼 A/B 토너먼트(전진 엣지 관측 생산)",
        ),
        SidecarSpec(
            key="edge-autoarm",
            branch="automation/edge-autoarm-last-run",
            filename="LAST_RUN.md",
            max_age_hours=80.0,  # 평일 23:50
            critical=True,
            description="자본 사다리 게이트(단 승격/강등 결정)",
        ),
        SidecarSpec(
            key="kis-smoke",
            branch="automation/kis-smoke-last-run",
            filename="LAST_RUN.md",
            max_age_hours=30.0,  # 매일 03:00 — 한 번 미스 허용
            critical=True,
            description="KIS 브로커 연결 생존(매일)",
        ),
        SidecarSpec(
            key="rebalance-live-canary",
            branch="automation/rebalance-live-canary-last-run",
            filename="LAST_RUN.md",
            max_age_hours=80.0,  # 평일 15:00 — 라이브 NAV 스냅샷(무장 시 드로다운 감지의 눈)
            critical=True,
            description="라이브 캐너리 + 라이브 NAV 스냅샷",
        ),
        # ── 연구/보고: 멈춰도 돈 경로 무관(저하로만 잡음) ──
        SidecarSpec(
            key="collect-public-data",
            branch="automation/public-data",
            filename="LAST_RUN.md",
            max_age_hours=80.0,  # 화~토 01:30
            critical=False,
            description="공개 데이터 수집·교차검증(연구 전용)",
        ),
        SidecarSpec(
            key="regime-stratify",
            branch="automation/regime-stratify-last-run",
            filename="LAST_RUN.md",
            max_age_hours=80.0,  # 평일 23:30
            critical=False,
            description="레짐 층화(연구 전용)",
        ),
        SidecarSpec(
            key="promote-readiness",
            branch="automation/promote-readiness-last-run",
            filename="LAST_RUN.md",
            max_age_hours=30.0,  # 매일 22:30
            critical=False,
            description="풀라이브 승격 준비 평가(보고 전용)",
        ),
        SidecarSpec(
            key="money-path",
            branch="automation/money-path-last-run",
            filename="LAST_RUN.md",
            max_age_hours=30.0,  # 매일 08:00 — 첫-자본까지의 길 종합(보고 전용)
            critical=False,
            description="첫-자본까지의 길 종합·ETA(스펙 052, 보고 전용)",
        ),
        SidecarSpec(
            key="capital-path-readiness",
            branch="automation/capital-path-readiness-last-run",
            filename="LAST_RUN.md",
            max_age_hours=30.0,  # 매일 08:10 — 자본 경로 준비도 종합(보고 전용)
            critical=False,
            description="자본 경로 준비도 루프(스펙 076, 보고 전용)",
        ),
        SidecarSpec(
            key="autonomous-work-execution",
            branch="automation/autonomous-work-execution-last-run",
            filename="LAST_RUN.md",
            max_age_hours=30.0,  # 매일 09:10 — 다음 Codex 작업 패킷 발행(보고 전용)
            critical=False,
            description="자율 작업 실행 루프(스펙 077, 다음 작업 패킷 보고 전용)",
            first_expected_utc="2026-07-01T09:10:00Z",
        ),
        SidecarSpec(
            key="released-work",
            branch="automation/released-work-last-run",
            filename="LAST_RUN.md",
            max_age_hours=30.0,  # 매일 09:05 — 완료 후보 소비 장부(보고 전용)
            critical=False,
            description="완료 후보 소비 장부(스펙 079, 보고 전용)",
            first_expected_utc="2026-07-02T09:05:00Z",
        ),
        SidecarSpec(
            key="money-gate-alignment",
            branch="automation/money-gate-alignment-last-run",
            filename="LAST_RUN.md",
            max_age_hours=30.0,  # 매일 09:20 — 돈 경로 sidecar 정렬(보고 전용)
            critical=False,
            description="돈 경로 게이트 정렬 루프(스펙 078, 보고 전용)",
            first_expected_utc="2026-07-01T09:20:00Z",
        ),
        SidecarSpec(
            key="autonomous-evolution",
            branch="automation/autonomous-evolution-last-run",
            filename="LAST_RUN.md",
            max_age_hours=30.0,  # 매일 08:30 — 영구 자율 성장 후보 발굴(보고 전용)
            critical=False,
            description="영구 자율 성장 루프(스펙 067, 고레버리지 돌파 후보 보고 전용)",
        ),
        SidecarSpec(
            key="autonomous-promotion",
            branch="automation/autonomous-promotion-last-run",
            filename="LAST_RUN.md",
            max_age_hours=30.0,  # 매일 08:45 — 성장 후보를 검증 단계로 승격 분류
            critical=False,
            description="자율 승격 루프(스펙 068, 후보→검증 단계 분류 보고 전용)",
        ),
        SidecarSpec(
            key="candidate-implementation-factory",
            branch="automation/candidate-implementation-factory-last-run",
            filename="LAST_RUN.md",
            max_age_hours=30.0,  # 매일 08:40 — 후보를 검증 패키지와 evidence patch로 변환
            critical=False,
            description="후보 구현 공장(스펙 070, BACKTEST_REQUIRED 후보→검증 패키지)",
        ),
        SidecarSpec(
            key="candidate-result-executor",
            branch="automation/candidate-implementation-results",
            filename="LAST_RUN.md",
            max_age_hours=30.0,  # 매일 08:42 — 후보 패키지를 candidate result evidence로 변환
            critical=False,
            description="후보 결과 실행기(스펙 071, 검증 패키지→결과 evidence)",
        ),
        SidecarSpec(
            key="autonomous-promotion-actions",
            branch="automation/autonomous-promotion-actions-last-run",
            filename="LAST_RUN.md",
            max_age_hours=30.0,  # 매일 09:00 — 승격 후보를 검증 큐로 자동 연결
            critical=False,
            description="자율 승격 실행 루프(스펙 069, forward/canary 큐 연결)",
        ),
        SidecarSpec(
            key="promotion-forward",
            branch="automation/promotion-forward-last-run",
            filename="LAST_RUN.md",
            max_age_hours=80.0,  # 평일 22:45 — promotion 후보 forward paper 관측
            critical=False,
            description="promotion 전용 forward paper 검증(스펙 069, paper only)",
        ),
        SidecarSpec(
            key="promotion-canary",
            branch="automation/promotion-canary-last-run",
            filename="LAST_RUN.md",
            max_age_hours=80.0,  # 화~토 00:40 — promotion 후보 hardened canary
            critical=False,
            description="promotion 전용 hardened canary 검증(스펙 069, live order 없음)",
        ),
        SidecarSpec(
            key="reassign",
            branch="automation/reassign-last-run",
            filename="LAST_RUN.md",
            max_age_hours=80.0,  # 평일 00:20(cron 20 0 * * 2-6) — 주말 갭 견딤
            critical=False,
            description="자율 전략 재지정 폐회로(스펙 055, 챔피언→라이브 5중 게이트)",
            # 워크플로가 main 에 든 시각(2026-06-16 15:26 UTC) 다음 첫 cron(수~토 00:20).
            # 그 전엔 사이드카 없음이 정상(PENDING). 첫 실행이 실패하면 +80h 후 MISSING 으로
            # 승격해 침묵 실패를 드러낸다(거짓경보 없이 진짜 정지만 잡는다).
            first_expected_utc="2026-06-17T00:20:00Z",
        ),
    ]


__all__ = [
    "CRITICAL",
    "DEGRADED",
    "HEALTHY",
    "LATE",
    "MISSING",
    "OK",
    "PENDING",
    "SCHEMA_VERSION",
    "STALE",
    "LivenessCheck",
    "LivenessReport",
    "SidecarSpec",
    "assess_liveness",
    "default_specs",
    "parse_timestamp_utc",
]

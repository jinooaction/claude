# Quickstart — Autonomous Tuner (스펙 005)

## 무엇인가

`auto-invest tune`은 측정 → 분석 → 행동 루프를 닫는 결정론적 엔진이다. 텔레메트리 KPI 드리프트를 감지하고, 권한 등급(L1~L4)으로 분류하고, 안전한 L1 변경(KPI 임계값 조이기)을 장외에 자동 적용한다. **LLM을 호출하지 않는다**(순수 룰).

## 흔한 사용

```bash
# 1) 분석만 — 무엇을 하려는지 본다(아무것도 안 바꿈)
auto-invest tune --dry-run --json

# 2) 세션 마감 후 자동 적용(장외에서만 실제 변경)
auto-invest tune --apply --output-root data/reports

# 3) 특정 날짜 기준(백필·테스트)
auto-invest tune --dry-run --as-of 2026-05-23 --json
```

## 안전 보장(한눈에)

- **dry-run(기본)**: 파일·감사 0 변경.
- **장 시간 마진**: 정규장 + 개장 30분 전이면 L1 적용 0건(헌법 VIII.A).
- **측정 부족**: 윈도 표본 < 20이면 거부(헌법 X).
- **Kernel 보호**: 대상 파일이 `kernel.toml`에 닿으면 무조건 L4(자동 적용 거부). 튜너는 `kernel.toml`·헌법을 절대 수정 안 함.
- **멱등**: 같은 세션 날짜로 두 번 돌려도 한 번만 적용.
- **가역**: 모든 L1 변경은 이전값이 감사에 남아 되돌릴 수 있음.

## 산출물

- `{output_root}/{session_date}/auto-tuner-report.json` — 후보·분류·적용·캐너리 후보·L4 콜아웃.
- `audit_log`의 `AUTO_TUNED_L1`/`AUTO_TUNED_L2_CANARY_ENTERED`/`AUTO_TUNED_L4_FORENSIC`/`AUTO_TUNER_RUN` 행.

## 검증 흐름(스펙 매핑)

| 검증 | 명령/테스트 |
|------|-------------|
| 탐지+분류 결정론(SC-A01) | `tune --dry-run --as-of <d> --json` 두 번 → 동일 출력 |
| Kernel=L4 전수(SC-A02) | `test_tuner_classify.py` — K1~K6·K-meta 각각 |
| dry-run 무변경(SC-A03) | `test_tuner_e2e.py` — 파일 mtime + 감사 카운트 |
| 멱등(SC-A04) | `tune --apply --as-of <d>` 두 번 → 한 번만 |
| 밴드 클램프(SC-A05) | `test_tuner_knobs.py` — new_tier_b ∈ (tier_a, tier_c) |
| 장 시간 차단(SC-A06) | `test_tuner_gates.py` — 장중 시각 주입 |
| 측정 게이트(SC-A07) | `test_tuner_gates.py` — 표본 < min |
| 리포트↔감사 정합(SC-A08) | `test_tuner_report.py` |
| K-meta 불가침(SC-A09) | `test_tuner_classify.py` — 헌법/매니페스트 경로 |

# HANDOFF 033 — 스펙 024: 최대 샤프 포트폴리오 최적화 (2026-05-29)

## 한 줄 요약

모멘텀 신호를 기대 수익률 μ로 활용해 평균-분산 전선에서 최대 샤프 포인트를
직접 구하는 `mode="max_sharpe"` 사이징 모드를 추가했습니다.
PR #101 머지 커밋 `86b2c32`. 신규 테스트 8건, 전체 1203 통과, 린트 깨끗.

## 배경 — 세계 최고 수준 격차 분석

이 세션에서 출시한 스펙들:

| 레이어 | 기존 | 이 세션 후 |
|--------|------|-----------|
| 시계열 모멘텀 | ✅ 스펙 018 | ✅ |
| 횡단면 모멘텀 순위 | ✅ 스펙 021 | ✅ |
| ERC 등기여 위험 | ✅ 스펙 019 | ✅ |
| 최소 분산 최적화 | ✅ 스펙 022 | ✅ |
| 퀄리티 팩터 필터 | ❌ | ✅ 스펙 023 |
| **최대 샤프 최적화** | ❌ | ✅ 스펙 024 |

`min_variance`는 `w'Σw`를 최소화합니다. `max_sharpe`는 기대 수익률 정보를 더해
`w'μ / sqrt(w'Σw)`를 최대화합니다. 분석적 해: `w* ∝ Σ^{-1}·μ`.

μ는 각 자산의 롤링 평균 로그 수익률(연율화 × 252)로 추정합니다 — 모멘텀 신호를
포트폴리오 최적화 입력으로 자연스럽게 연결합니다.

## 변경 사항

### `strategy/sizing.py` (비커널)

- `MaxSharpeConvergenceError`: 수치 실패 시 발생하는 예외.
- `expected_returns_from_closes(closes_by_rule, *, lookback_bars)`:
  - 공통 거래일 기준 각 자산의 평균 로그 수익률(일별 × 252로 연율화).
  - 공통일 < 30이면 None.
- `max_sharpe_weights(cov_matrix, expected_returns)`:
  - numpy `linalg.solve(Σ + εI, μ)` — 분석적 해.
  - ε = max_diag(Σ) × 1e-6 ridge 정규화.
  - μ 전부 비양수 → 균등 가중치 반환(모멘텀 신호 없는 구간 fail-safe).
  - 음수 클램핑 + 재정규화 → 롱-온리 보장.
  - lstsq fallback.
  - Decimal 변환 + max 1 클램핑.
- `max_sharpe_group_scales(closes_by_rule, *, lookback_bars, member_vols)`:
  - ERC/min_variance와 동일 signature.
  - 수치 실패 → min_variance → ERC → 역변동성 순 fallback 체인.

### `config/rules.py` (비커널)

- `SizingConfig.mode`에 `"max_sharpe"` 추가:
  `Literal["fixed", "target_vol", "inverse_vol", "erc", "min_variance", "max_sharpe"]`

### `execution/order_router.py` (비커널)

- `_group_scale()` — `mode in ("erc", "min_variance", "max_sharpe")` 통합 분기.

### `backtest/replay.py` (비커널)

- `_replay_group_scale()` — 동일 패턴. 세션 날짜 이하 바만 사용(미래 참조 없음).

## 안전 경계

- **Kernel 터치 0건**: `risk/gates.py`(K1) 변경 없음.
- **하향 전용**: max 1 클램핑 — K1 위로 노출 증가 불가.
- **옵트인**: `mode` 기본값 `"fixed"`, 기존 룰 byte 동일.
- **Fallback 체인**: 수치 실패 → min_variance → ERC → 역변동성.
- **결정론적**: Decimal 출력, 백테스트=라이브 단일 잣대(헌법 X.2).
- `AUTO_INVEST_MODE=live` 전환 미포함 — 운영자 명시 지시 필요.

## 테스트 (`tests/unit/test_spec_024_max_sharpe.py`) — 8개

- SC-01: 같은 분산에서 기대 수익률 높은 자산에 더 높은 가중치
- SC-02: 균등 수익률·분산 → 균등 가중치
- SC-03: 데이터 부족(< 30일) → 역변동성 fallback
- SC-04: 음수 가중치 없음 (롱-온리)
- SC-05: 가중치 합 ≈ 1 (정규화 검증)
- SC-06: `mode="max_sharpe"` 옵트인 검증
- SC-07: 모든 μ ≤ 0이면 균등 가중치 반환
- SC-08: max_sharpe 포트폴리오 기대 수익률 ≥ min_variance (기대 수익률 정보 반영)

전체 1203 통과, 4 스킵(KIS smoke), 린트 깨끗.

## 이 세션 전체 요약

이 세션에서 세계 최고 수준 격차 분석 후 3개 스펙을 자율 수행으로 완료:

| 스펙 | PR | 커밋 | 테스트 |
|------|-----|------|--------|
| 023 퀄리티 팩터 필터 | #100 | `674c8dc` | 8건 신규, 전체 1195 |
| 024 최대 샤프 최적화 | #101 | `86b2c32` | 8건 신규, 전체 1203 |

(스펙 022는 이전 세션에서 완료, PR #99 `204dfc9`)

## 실거래 전환 가능성

| 항목 | 상태 |
|------|------|
| K1 포지션 한도 | ✅ |
| 손실 서킷 브레이커(스펙 014) | ✅ |
| 체결 동기화(스펙 015) | ✅ |
| 일일 정합성(스펙 001) | ✅ |
| 하드닝 캐너리(스펙 007) 합성 데이터 통과 | ✅ (이 세션, CANARY_PASSED 감사 기록) |
| 실서버 캐너리(Vultr + KIS 시크릿) | ❌ **블로커** |
| 페이퍼 트레이딩 실적 | ⚠️ 컨테이너에서 접근 불가 |

**결론**: 아키텍처 준비 완료. 헌법 VI조(Backtest→Canary→Full Live)에 따라
실서버(Vultr)에서 KIS 시크릿으로 캐너리 1단계를 실행해야 합니다.
운영자 "캐너리 시작해줘(Vultr에서)" 지시 시 즉시 실행 가능.

## 다음 후보

1. **실거래 캐너리** — Vultr 서버에서 KIS 시크릿으로 `AUTO_INVEST_MODE=live` 전환.
   **운영자 명시 지시 필요.**
2. **베타 헤지 / 시장 중립 포지션** — SPY 대비 롤링 베타 계산, 시장 노출 감소.
3. **퀄리티 팩터 고도화** — 재무 데이터 API 확보 시 ROE·이익률 기반으로 교체.

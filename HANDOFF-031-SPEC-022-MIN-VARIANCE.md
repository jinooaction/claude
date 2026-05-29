# HANDOFF 031 — 스펙 022: 최소 분산 포트폴리오 최적화 (2026-05-29)

## 한 줄 요약

ERC(등기여 위험 배분)를 넘어 포트폴리오 분산을 직접 최소화하는
`mode="min_variance"` 사이징 모드를 추가했습니다.
PR #99 머지 커밋 `204dfc9`. 신규 테스트 8건, 전체 1187 통과, 린트 깨끗.

## 배경 — 세계 최고 수준 격차 분석 결과

이 세션에서 세계 최고 수준 격차를 체계적으로 분석했을 때 다음 단계로 포트폴리오
최적화가 가장 임팩트가 높다고 판단했습니다.

| 레이어 | 기존 | 스펙 022 후 |
|--------|------|------------|
| 시계열 모멘텀 | ✅ 스펙 018 | ✅ |
| 횡단면 모멘텀 순위 | ✅ 스펙 021 | ✅ |
| ERC 등기여 위험 | ✅ 스펙 019 | ✅ |
| 최소 분산 최적화 | ❌ | ✅ `min_variance` |
| 레짐 필터 | ✅ 스펙 020 | ✅ |

ERC는 `w'Σw` 최소화와 무관합니다. 최소 분산은 분석적으로
`w* = Σ^{-1}·1 / (1'·Σ^{-1}·1)` 이 해법으로 진짜 포트폴리오 분산 최소값에 도달합니다.

## 변경 사항

### `strategy/sizing.py` (비커널, numpy 의존성 추가)

- `MinVarianceConvergenceError`: 수치 실패 시 발생하는 예외.
- `min_variance_weights(cov_matrix)`:
  - numpy `linalg.solve(Σ + εI, 1)` — 분석적 해.
  - ε = max_diag(Σ) × 1e-6 ridge 정규화 (특이 행렬 방지).
  - 음수 클램핑(`np.maximum`) + 재정규화 → 롱-온리 보장.
  - linalg.solve 실패 시 lstsq fallback.
  - Decimal 변환 + max 1 클램핑.
- `min_variance_group_scales(closes_by_rule, *, lookback_bars, member_vols)`:
  - ERC와 동일한 signature.
  - 수치 실패 → ERC → 역변동성 순 fallback 체인.

### `config/rules.py` (비커널)

- `SizingConfig.mode`에 `"min_variance"` 추가:
  `Literal["fixed", "target_vol", "inverse_vol", "erc", "min_variance"]`
- 기존 모드 무변경(옵트인).

### `execution/order_router.py` (비커널)

- `_group_scale()` — `mode in ("erc", "min_variance")` 통합 분기.
  `scale_fn = min_variance_group_scales if mode == "min_variance" else erc_group_scales`

### `backtest/replay.py` (비커널)

- `_replay_group_scale()` — 동일 패턴. 세션 날짜 이하 바만 사용(미래 참조 없음).

## 안전 경계

- **Kernel 터치 0건**: `risk/gates.py`(K1) 변경 없음.
- **하향 전용**: max 1 클램핑 — K1 위로 노출 증가 불가.
- **옵트인**: `mode` 기본값 `"fixed"`, 기존 룰 byte 동일.
- **Fallback 체인**: 수치 실패 → ERC → 역변동성.
- **결정론적**: Decimal 출력, 백테스트=라이브 단일 잣대(헌법 X.2).
- `AUTO_INVEST_MODE=live` 전환 미포함 — 여전히 운영자 명시 지시 필요.

## 테스트 (`tests/unit/test_spec_022_min_variance.py`) — 8개

- SC-01: 저변동 자산에 더 높은 가중치
- SC-02: 균등 공분산 → 균등 가중치
- SC-03: 데이터 부족(< 30일) → 역변동성 fallback
- SC-04: 음수 가중치 없음 (롱-온리)
- SC-05: 가중치 합 ≈ 1 (정규화 검증)
- SC-06: `mode="min_variance"` 옵트인 검증
- SC-07: 고변동 룰 < 저변동 룰 가중치 (그룹 스케일)
- SC-08: min_variance 포트폴리오 분산 ≤ ERC 포트폴리오 분산

전체 1187 통과, 4 스킵(KIS smoke), 린트 깨끗.

## 실거래 전환 가능성 (이 세션 평가)

| 항목 | 상태 |
|------|------|
| K1 포지션 한도 | ✅ |
| 손실 서킷 브레이커(스펙 014) | ✅ |
| 체결 동기화(스펙 015) | ✅ |
| 일일 정합성(스펙 001) | ✅ |
| 하드닝 캐너리(스펙 007) 실제 운영 | ❌ **유일한 블로커** |
| 페이퍼 트레이딩 실적 | ⚠️ 컨테이너에서 접근 불가 |

**결론**: 아키텍처 준비 완료. 헌법 VI조(Backtest→Canary→Full Live)에 따라
5% 소자본 캐너리 실제 운영이 필수. 운영자 "캐너리 시작해줘" 지시 시 즉시 실행 가능.

## 다음 후보

1. **퀄리티 팩터 (스펙 023 후보)** — KIS API 재무 데이터 가용 여부 확인 후.
   가용 불가 시 가격 기반 퀄리티 지표(롤링 샤프, 드로다운 회복 등) 대안.
2. **실거래 캐너리** — 5% 소자본으로 `AUTO_INVEST_MODE=live` 전환.
   **운영자 명시 지시 필요.**
3. **기대 수익률 모델 + 최대 샤프 (스펙 024 후보)** — 모멘텀 신호를 기대 수익률로 활용,
   mean-variance 전선에서 최대 샤프 포인트 직접 최적화.

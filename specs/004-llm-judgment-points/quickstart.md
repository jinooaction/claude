# Quickstart — LLM Judgment Points 검증

구현 후 이 시나리오로 기능을 확인한다. 전부 mock Anthropic(`_AnthropicProtocol`)으로 실 SDK·실 비용 없이 동작.

## 1. 결정론적 폴백 (SC-001 — 가장 중요)

```bash
# LLM이 항상 예외를 던지는 mock으로 거래 루프 단위/통합 테스트 실행
uv run pytest tests/integration/test_judgment_fallback_chaos.py -v
```
기대: 모든 판단 지점에서 호출이 실패해도 주문 경로가 v1과 **동일하게** 동작(0건 막힘). `JUDGMENT_FALLBACK` 감사 행이 사유와 함께 남음.

## 2. 결정성 (SC-002)

```bash
uv run pytest tests/integration/test_judgment_volatility_gate.py -v
```
기대: 같은 `VolatilityAdvisory`를 두 번 먹이면 게이트 결정(축소 계수/건너뛰기)이 두 번 다 동일.

## 3. 감사·텔레메트리 짝 + 본문 미기록 (SC-003)

```bash
uv run pytest tests/integration/test_judgment_audit_telemetry.py -v
```
기대: 매 호출당 token_usage 1행 + LLM_CALL 1행, 같은 correlation_id. DB 어디에도 프롬프트/응답 본문·KIS 비밀 없음.

## 4. K1 캡 불변 (SC-007)

기대(통합 테스트): `size_down` 자문은 qty를 줄일 수만 있고, 그 뒤 K1 게이트가 변형 없이 실행되어 포지션 캡이 그대로 바인딩. 자문이 캡을 넘기게 만들 수 없음(노출 단조 비증가).

## 5. 캐너리 코호트 (SC-005)

기대: `volatility_assessment`는 5% 캐너리 코호트 거래에만 자문 반영, 코호트 밖은 v1 동작. `JUDGMENT_ADVISORY_APPLIED.canary_cohort`로 구분 → 스펙 011이 비교.

## 6. 예산 강제 (SC-004, US4)

```bash
uv run pytest tests/unit/test_judgment_budget.py -v
```
기대: 판단 지점 롤링 비용이 예산 초과 시 그 지점이 폴백으로 전환, `JUDGMENT_FALLBACK(reason="budget_exceeded")` 기록, 거래 계속.

## 7. 일일 요약 리포트 (US2)

```bash
uv run pytest tests/integration/test_judgment_daily_summary.py -v
# 수동: 합성 audit DB로
uv run auto-invest report --date 2026-05-24
```
기대: 리포트에 판단 요약 섹션. LLM 실패 시 결정론적 카운터만, 정상 종료.

## 8. 관측 (US4)

```bash
uv run auto-invest efficiency
```
기대: decision_class별 비용·지연·호출 수·폴백률 분해. 합은 token_usage 총계와 정합.

## 전체 게이트

```bash
uv run pytest && uv run ruff check src tests
```
기대: 전부 통과(skip 허용), 린트 깨끗. 자동 머지 조건(CLAUDE.md 규칙 3) 충족.

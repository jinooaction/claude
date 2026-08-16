# HANDOFF-151 — AI 확신도 기반 추세 앙상블

## 상태

PR #637이 `main`에 merge되어 스펙 145가 완료됐다. 출시된 것은 실거래 전략 교체가 아니라, AI 후보를 미래 누출 없이 매주 재학습·재검증하고 기준 통과 후보만 자율 연구 루프로 보내는 no-live 환경이다.

최신 실제 자료 판정은 `NO_EDGE`다. AI 후보는 기존 전략보다 CAGR과 최대 낙폭이 조금 개선됐지만, 통계적 우위와 여러 시기에서의 반복 승률이 부족해 실거래 승격 자격이 없다.

## 무엇을 만들었나

- `src/auto_invest/analytics/ml_edge_ensemble.py`에 주식·채권·금 pooled panel, 지연 특징, 자산별 물가·금리 상호작용, Ridge, Gradient Boosting, 확장형 워크포워드를 추가했다.
- 기존 3·6·9·12개월 추세 앙상블을 기본 비중으로 두고, 검증 잔차와 두 모델의 불일치에서 계산한 확신도만큼 AI 목표 비중으로 기울인다.
- 단일 자산 40%, 총투자 99%, long-only, 현금 잔여 규칙과 10/25/50bp 회전 비용을 적용한다.
- passive 동일가중과 기존 추세를 같은 기간에 비교하고, Sharpe margin, PSR, DSR, fold 승률, 최대 낙폭, 50bp 생존 관문을 모두 통과해야만 후보 자격을 준다.
- `.github/workflows/ml-edge-ensemble.yml`이 매주 일요일 03:35 UTC와 수동 실행에서 보고서와 후보 객체를 sidecar로 발행한다.
- 자율 작업 실행기는 `eligible=true`인 후보만 작업 패킷으로 만들며 `NO_EDGE`는 증거로만 보관한다.

## 실제 증거

- PR: #637 `https://github.com/jinooaction/claude/pull/637`
- 기능 커밋: `1f48d12541f26ec80c9623fc7fcffc7938bc975b`
- merge commit: `bc33a7f0b58184596ecc5ab93954460716dcab0d`
- PR 품질 관문: run `31928411143`, success
- ML 연구: run `31928435772`, success
- released-work: run `31928435773`, success
- autonomous-work: run `31928435787`, success
- deploy-on-merge: run `31928435817`, success
- 전체 검증: 2870 passed, 6 skipped
- 린트: `uv run ruff check src tests` 통과
- 하네스: strict 14/14, HANDOFF 사실 검사 OK

## 최신 성과 판정

1971년 이후 509개 표본 외 월과 43개 서로 겹치지 않는 test fold를 사용했다.

| 항목 | AI 후보 | 기존 추세 |
|------|--------:|----------:|
| 25bp CAGR | 9.55% | 9.29% |
| Sharpe | 2.037 | 2.015 |
| 최대 낙폭 | 5.14% | 5.56% |

통과하지 못한 관문:

- Sharpe 우위: 0.022, 필요 0.20 이상
- PSR: 0.551, 필요 0.95 이상
- fold 승률: 34.9%, 필요 60% 이상

따라서 후보는 `eligible=false`, `status=rejected`, `live_promotion_authorized=false`다. 성과가 조금 좋아 보인다는 이유로 기준을 낮추지 않는다.

## 안전 경계

이번 변경은 등급 2 운영 변경이다. 브로커 API 호출, 주문 제출·취소, live 전략 교체, 자본 배분, whitelist, caps, 손실 예산, 비밀값, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.

sidecar 안전 증거는 `orders_submitted=0`, `orders_cancelled=0`, `live_strategy_changed=false`, `capital_changed=false`, `whitelist_changed=false`, `caps_changed=false`다.

## 다음 세션 판단

이 AI 후보를 실거래로 전환하지 않는다. 매주 새 데이터로 자동 재검증하며, 모든 사전 등록 관문이 통과될 때만 정확한 데이터·모델·특징 지문을 고정해 독립 no-live 재현과 Canary 승격 검토를 시작한다.

기존 production 자동매매는 별도 경로다. 현재 AI 후보의 `NO_EDGE`가 기존 무장 상태를 해제하거나 우회하지 않으며, 반대로 기존 무장 상태가 AI 후보의 승격 기준을 낮추지도 않는다.

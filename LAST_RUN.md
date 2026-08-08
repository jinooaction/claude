# 돈 경로 상태 / 첫-자본까지의 길 (as of 2026-08-08T08:36:56Z) — 읽기 전용, 돈 0 이동

## 실제 돈 최상위 상태

> ⚪ 미리보기 전용 — 실주문 불가

| 항목 | 값 |
|------|-----|
| 경로 | micro-gtaa-live-canary |
| 상태 | PREVIEW_ONLY |
| 실주문 단계 도달 가능 | 아니오 |
| 선언 자본 / 한도 | $1000 / $1000 |
| 다음 예약 live 후보 | (없음) |
| 남은 필수 게이트 | strategy intent gate clear, non-push workflow event, US regular session, KIS purchasable cash >= planned buys + 1% buffer, micro circuit breaker clear, K1 caps and K2 whitelist |
| 판정 근거 | armed:false — push/스케줄 모두 미리보기만, 실주문 0건. |
| 마지막 run | [REDACTED_ACCOUNT] / 2026-07-28T16:14:45Z / event=schedule |
| 마지막 LIVE 스텝 | skipped |
| 마지막 전략 의도 게이트 | ok=False, reason=latest_intent_loss |
| 마지막 preflight | ok=None, reason=preflight evidence absent |
| 마지막 손실 브레이커 | (불명) |
| 마지막 주문 상태 | (주문 결과 없음) |
| 마지막 접수·체결 판단 | 브로커 접수·체결 0건, 브로커 거부 0건 |

## 기존 자본 사다리 상태

단계: ➖ **NO_EDGE_YET**

> ➖ 단0 — 관측(39)은 충분하나 엣지가 기준 미달(NO_EDGE). 아직 배치할 검증된 엣지가 없다(정상 — 과적합 방어).

| 항목 | 값 |
|------|-----|
| 현재 단(rung) | 0 / 3 |
| 배치 비율 | 0% |
| 실계좌 NAV | 1458.99000000 |
| 배치 자본(USD) | 0 |
| 캐너리 무장 | 아니오(드라이런) |
| 지금 막는 것 | 엣지 미확정: 전진 성과가 벤치마크/유의 기준을 넘지 못함. |

## 게이트 (다음 한 발의 합격 조건)

| 조건 | 상태 | 현재 | 기준 |
|------|:----:|------|------|
| 벤치마크 대비 칼마 | ✅ PASS | 넘음 | 전략 칼마 > 벤치마크 칼마 |
| 엣지 신뢰도(PSR) | ❌ FAIL | 0.567128 | ≥ 0.95 |
| 전략 지문 정합(검증=배포) | ✅ PASS | 일치 | 라이브 배포 설정 == 전진 검증 설정 |

## 첫-자본 추정 시점(ETA)

- 해당 없음.

## 자본 방어선 예산 (다운사이드 한계 — 내려가는 길)

- 첫 자본은 단1(NAV 의 25%) ≈ **$364** 로 들어간다.
- 자동 강등(→단0, 무장 해제): 낙폭 ≥ **10%** → 약 -$37 손실.
- 절대 정지: 낙폭 ≥ **20%** → 약 -$73 손실.
- 즉 첫 자본의 다운사이드는 약 -$37(강등) 안에서 시스템이 스스로 자본을 회수한다 — 사람 개입 없이 작동하는 방어선.

## 다음 행동

- 자율 시스템은 계속 전진 관측을 쌓으며 엣지를 재평가한다. 전략 자체를 갈아엎으면 지문이 바뀌어 누적이 리셋되므로, 후보 전략은 전진 토너먼트에 *추가*로 검증한다.

⚠ 이건 종합 보고다(읽기 전용). 거래·자본 변경 없음 — 실제 배치는 자본 사다리 게이트가 자율로 한다(헌법 X.4 상시 위임). 운영자 전용은 입금·킬스위치·낙폭 예산뿐.

## 메타데이터

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| commit | 758dda2534af38f444ac75361295fb49b489e234 |
| trigger | schedule |
| timestamp_utc | 2026-08-08T08:36:56Z |

## 결정 JSON

```json
{"schema_version": "1.1", "as_of_utc": "2026-08-08T08:36:55Z", "stage": "NO_EDGE_YET", "headline": "➖ 단0 — 관측(39)은 충분하나 엣지가 기준 미달(NO_EDGE). 아직 배치할 검증된 엣지가 없다(정상 — 과적합 방어).", "blocking_gate": "엣지 미확정: 전진 성과가 벤치마크/유의 기준을 넘지 못함.", "current_rung": 0, "capital_pct": "0", "account_nav_usd": "1458.99000000", "deployed_capital_usd": 0, "canary_armed": false, "live_money_state": {"status": "PREVIEW_ONLY", "can_submit_real_orders": false, "path": "micro-gtaa-live-canary", "capital_usd": 1000, "max_capital_usd": 1000, "next_scheduled_live_utc": null, "required_gates": ["strategy intent gate clear", "non-push workflow event", "US regular session", "KIS purchasable cash >= planned buys + 1% buffer", "micro circuit breaker clear", "K1 caps and K2 whitelist"], "detail": "armed:false — push/스케줄 모두 미리보기만, 실주문 0건.", "last_run": {"run_id": "[REDACTED_ACCOUNT]", "timestamp_utc": "2026-07-28T16:14:45Z", "event": "schedule", "live_step": "skipped", "intent_gate_ok": false, "intent_gate_reason": "latest_intent_loss", "preflight_ok": null, "preflight_reason": "preflight evidence absent", "breaker_reason": null, "order_states": [], "accepted_or_filled_count": 0, "broker_rejected_count": 0}}, "gates": [{"name": "벤치마크 대비 칼마", "status": "PASS", "current": "넘음", "required": "전략 칼마 > 벤치마크 칼마", "detail": "자본 방어(낙폭 대비 수익)가 벤치마크보다 나아야 한다."}, {"name": "엣지 신뢰도(PSR)", "status": "FAIL", "current": "0.567128", "required": "≥ 0.95", "detail": "참 샤프가 벤치마크보다 클 확률(스큐·첨도 보정). 높을수록 우연이 아닐 확신이 큼."}, {"name": "전략 지문 정합(검증=배포)", "status": "PASS", "current": "일치", "required": "라이브 배포 설정 == 전진 검증 설정", "detail": "지문(유니버스·가중·추세 게이트 등, 캡/자본 제외)이 다르면 자본 사다리가 어떤 단에서도 자본을 배치하지 않는다(BLOCKED). 두 TOML 을 일치시켜야 첫 자본이 들어간다."}], "eta": {"basis": "n/a", "obs_remaining": null, "obs_per_trading_day": null, "trading_days_remaining": null, "projected_date": null, "assumption": "해당 없음.", "convergence": "unknown", "sample_stability": "unknown", "legacy_excluded": null, "snapshot_count": null}, "safety_budget": {"reference_rung": 1, "capital_usd": 364, "demote_dd_pct": "10", "halt_dd_pct": "20", "loss_at_demote_usd": 37, "loss_at_halt_usd": 73, "current_dd_pct": null, "margin_to_demote_pct": null, "margin_to_halt_pct": null, "prospective": true}, "next_action": "자율 시스템은 계속 전진 관측을 쌓으며 엣지를 재평가한다. 전략 자체를 갈아엎으면 지문이 바뀌어 누적이 리셋되므로, 후보 전략은 전진 토너먼트에 *추가*로 검증한다.", "forward_n_obs": 39, "forward_legacy_excluded": 4}
```

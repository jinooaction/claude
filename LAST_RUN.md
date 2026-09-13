# 돈 경로 상태 / 첫-자본까지의 길 (as of 2026-09-13T08:25:19Z) — 읽기 전용, 돈 0 이동

## 실제 돈 최상위 상태

> 🟠 실제 돈 경로 무장 — preflight 통과 후 실주문 가능

| 항목 | 값 |
|------|-----|
| 경로 | capital-ladder-live-canary |
| 상태 | REAL_ORDER_PATH_ARMED |
| 실주문 단계 도달 가능 | 예(비-push 실행 + preflight 통과 필요) |
| 선언 자본 / 한도 | $143 / $143 |
| 다음 예약 live 후보 | 2026-09-14T14:17:00Z |
| 남은 필수 게이트 | production environment machine authorization, non-push workflow event, US regular session, KIS purchasable cash >= planned buys + 1% buffer, portfolio circuit breaker clear, K1 caps and K2 whitelist |
| 판정 근거 | 자본 사다리 단1 센티넬 armed:true + 유효 자본. 다음 비-push 실행은 production 기계 승인·정규장·현금·손실 브레이커·K1/K2를 통과하면 실주문 단계에 도달한다. |
| 마지막 run | [REDACTED_ACCOUNT] / 2026-09-11T18:27:32Z / event=schedule |
| 마지막 LIVE 스텝 | failure |
| 마지막 전략 의도 게이트 | ok=None, reason=(불명) |
| 마지막 preflight | ok=True, reason=ACTIVE_LIVE_TRACK |
| 마지막 손실 브레이커 | (불명) |
| 마지막 주문 상태 | (주문 결과 없음) |
| 마지막 접수·체결 판단 | 브로커 접수·체결 0건, 브로커 거부 0건 |

## 실계좌 체결·손익 증거

| 항목 | 값 |
|------|-----|
| 누적 상태 | FILLED_NOT_PROFITABLE |
| 현재 상태 | FILLED_NOT_PROFITABLE |
| 실제 체결 수 | 2 |
| 현재 총손익 USD | -0.63720000 |
| 최초 양의 손익 확인 | 아니오 |
| 최초 확인 시각 | (없음) |

## 기존 자본 사다리 상태

단계: 💰 **DEPLOYED**

> 🧪 주문·체결 운영 검증 자본 배치 — 단1(NAV 10%, $143). 확정 알파가 아니며 단1이 상한이다.

| 항목 | 값 |
|------|-----|
| 현재 단(rung) | 1 / 5 |
| 진입 근거 | operational_canary |
| 배치 비율 | 10% |
| 실계좌 NAV | 1438.44000000 |
| 배치 자본(USD) | 143 |
| 캐너리 무장 | 예(armed) |
| 지금 막는 것 | 20% 승격은 별도 깨끗한 전진 40관측·PSR 0.80·칼마 우위·전체 경로 교정 필요. |

## 게이트 (다음 한 발의 합격 조건)

| 조건 | 상태 | 현재 | 기준 |
|------|:----:|------|------|
| 운영 검증과 알파 승격 분리 | ⏳ PENDING | 운영 검증 ready / alpha_confirmed=false | 깨끗한 전진 알파 계약 별도 통과 |
| 라이브 관측 수 | ⏳ PENDING | 12 | ≥ 20 |
| 경과일 | ⏳ PENDING | 6.695058333333334 | ≥ 27일 |
| 낙폭 < 예산/2 | ✅ PASS | 0.889930% | < 10% |
| 전략 지문 정합(검증=배포) | ✅ PASS | 일치 | 라이브 배포 설정 == 전진 검증 설정 |

## 첫-자본 추정 시점(ETA)

- 해당 없음.

## 자본 방어선 예산 (다운사이드 한계 — 내려가는 길)

- 배치 자본: 단1 ≈ **$143**, 현재 낙폭 **0.889930%**.
- 강등까지 여유: **9.110070%포인트** (강등 임계 10% ≈ -$15).
- 정지까지 여유: **19.110070%포인트** (정지 임계 20% ≈ -$29).

## 다음 행동

- 예약 라이브 실행으로 실제 주문·체결·정합·감사를 확인하되 단1을 유지한다. 20%는 깨끗한 전진 알파 계약을 따로 벌어야 한다.

⚠ 이건 종합 보고다(읽기 전용). 거래·자본 변경 없음 — 실제 배치는 자본 사다리 게이트가 자율로 한다(헌법 X.4 상시 위임). 운영자 전용은 입금·킬스위치·낙폭 예산뿐.

## 메타데이터

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| commit | f69c4b01a49dc4089715c50e165cf95996776859 |
| trigger | workflow_run |
| timestamp_utc | 2026-09-13T08:25:19Z |

## 결정 JSON

```json
{"schema_version": "1.8", "as_of_utc": "2026-09-13T08:25:18Z", "stage": "DEPLOYED", "headline": "🧪 주문·체결 운영 검증 자본 배치 — 단1(NAV 10%, $143). 확정 알파가 아니며 단1이 상한이다.", "blocking_gate": "20% 승격은 별도 깨끗한 전진 40관측·PSR 0.80·칼마 우위·전체 경로 교정 필요.", "current_rung": 1, "entry_route": "operational_canary", "capital_pct": "10", "account_nav_usd": "1438.44000000", "deployed_capital_usd": 143, "canary_armed": true, "live_money_state": {"status": "REAL_ORDER_PATH_ARMED", "can_submit_real_orders": true, "path": "capital-ladder-live-canary", "capital_usd": 143, "max_capital_usd": 143, "next_scheduled_live_utc": "2026-09-14T14:17:00Z", "required_gates": ["production environment machine authorization", "non-push workflow event", "US regular session", "KIS purchasable cash >= planned buys + 1% buffer", "portfolio circuit breaker clear", "K1 caps and K2 whitelist"], "detail": "자본 사다리 단1 센티넬 armed:true + 유효 자본. 다음 비-push 실행은 production 기계 승인·정규장·현금·손실 브레이커·K1/K2를 통과하면 실주문 단계에 도달한다.", "last_run": {"run_id": "[REDACTED_ACCOUNT]", "timestamp_utc": "2026-09-11T18:27:32Z", "event": "schedule", "live_step": "failure", "intent_gate_ok": null, "intent_gate_reason": null, "preflight_ok": true, "preflight_reason": "ACTIVE_LIVE_TRACK", "breaker_reason": null, "order_states": [], "accepted_or_filled_count": 0, "broker_rejected_count": 0}}, "halt_recovery_evidence": {"evidence_quality": "VALID", "halt_cleared": false, "halt_present_after": false, "halt_present_before": false, "halt_reason_before": null, "measurement_contract_id": "sha256:2542c0ddd4499481582d820ebee48fadbbfbab9b6208c749d843c025b74288d8", "observed_at_utc": "2026-09-13T08:24:56.187Z", "orders_submitted": 0, "reasons": [], "reconciliation_state": "OK", "remote_exit": 0, "schema_version": "1.0", "status": "CLEAR", "workflow_commit": "f69c4b01a49dc4089715c50e165cf95996776859", "workflow_run_id": "[REDACTED_ACCOUNT]"}, "live_profit_evidence": {"current_status": "FILLED_NOT_PROFITABLE", "data_quality_warnings": [], "detail": "live 체결은 있으나 완전한 현재 총손익이 0 이하.", "fills_count": 2, "first_profit_fills_count": null, "first_profit_observed": false, "first_profit_observed_at_utc": null, "first_profit_realized_pnl_usd": null, "first_profit_total_pnl_usd": null, "first_profit_unrealized_pnl_usd": null, "gross_invested_usd": "104.45260000", "measurement_contract_id": "sha256:2542c0ddd4499481582d820ebee48fadbbfbab9b6208c749d843c025b74288d8", "measurement_scope": "strategy", "observed_at_utc": "2026-09-11T21:52:07Z", "realized_pnl_usd": "0", "return_pct": "-0.6100374715421157539400646801", "schema_version": "1.1", "source_run_id": "[REDACTED_ACCOUNT]", "status": "FILLED_NOT_PROFITABLE", "total_pnl_usd": "-0.63720000", "unmarked_symbols": [], "unrealized_pnl_usd": "-0.63720000"}, "gates": [{"name": "운영 검증과 알파 승격 분리", "status": "PENDING", "current": "운영 검증 ready / alpha_confirmed=false", "required": "깨끗한 전진 알파 계약 별도 통과", "detail": "현재 10%는 실제 주문·체결·정합·감사 배관 검증 전용이며 수익 우위 확정이 아니다."}, {"name": "라이브 관측 수", "status": "PENDING", "current": "12", "required": "≥ 20", "detail": "현재 단 진입 이후 라이브 NAV 관측."}, {"name": "경과일", "status": "PENDING", "current": "6.695058333333334", "required": "≥ 27일", "detail": "현재 단 진입 후 경과 캘린더일(라이브 실적 JSON 의 period_days)."}, {"name": "낙폭 < 예산/2", "status": "PASS", "current": "0.889930%", "required": "< 10%", "detail": "낙폭 ≥ 예산/2(10%) 강등, ≥ 예산(20%) 정지."}, {"name": "전략 지문 정합(검증=배포)", "status": "PASS", "current": "일치", "required": "라이브 배포 설정 == 전진 검증 설정", "detail": "지문(유니버스·가중·추세 게이트 등, 캡/자본 제외)이 다르면 자본 사다리가 어떤 단에서도 자본을 배치하지 않는다(BLOCKED). 두 TOML 을 일치시켜야 첫 자본이 들어간다."}], "eta": {"basis": "n/a", "obs_remaining": null, "obs_per_trading_day": null, "trading_days_remaining": null, "projected_date": null, "assumption": "해당 없음.", "convergence": "unknown", "sample_stability": "unknown", "legacy_excluded": null, "snapshot_count": null}, "safety_budget": {"reference_rung": 1, "capital_usd": 143, "demote_dd_pct": "10", "halt_dd_pct": "20", "loss_at_demote_usd": 15, "loss_at_halt_usd": 29, "current_dd_pct": "0.889930", "margin_to_demote_pct": "9.110070", "margin_to_halt_pct": "19.110070", "prospective": false}, "next_action": "예약 라이브 실행으로 실제 주문·체결·정합·감사를 확인하되 단1을 유지한다. 20%는 깨끗한 전진 알파 계약을 따로 벌어야 한다.", "forward_n_obs": 14, "forward_legacy_excluded": 0}
```

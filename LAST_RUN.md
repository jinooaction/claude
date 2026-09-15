# 돈 경로 상태 / 첫-자본까지의 길 (as of 2026-09-15T22:24:52Z) — 읽기 전용, 돈 0 이동

## 실제 돈 최상위 상태

> 🟠 실제 돈 경로 무장 — preflight 통과 후 실주문 가능

| 항목 | 값 |
|------|-----|
| 경로 | capital-ladder-live-canary |
| 상태 | REAL_ORDER_PATH_ARMED |
| 실주문 단계 도달 가능 | 예(비-push 실행 + preflight 통과 필요) |
| 선언 자본 / 한도 | $143 / $143 |
| 다음 예약 live 후보 | 2026-09-16T14:17:00Z |
| 남은 필수 게이트 | production environment machine authorization, non-push workflow event, US regular session, KIS purchasable cash >= planned buys + 1% buffer, portfolio circuit breaker clear, K1 caps and K2 whitelist |
| 판정 근거 | 자본 사다리 단1 센티넬 armed:true + 유효 자본. 다음 비-push 실행은 production 기계 승인·정규장·현금·손실 브레이커·K1/K2를 통과하면 실주문 단계에 도달한다. |
| 마지막 run | [REDACTED_ACCOUNT] / 2026-09-15T18:15:53Z / event=schedule |
| 마지막 LIVE 스텝 | success |
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
| 현재 총손익 USD | -1.88570000 |
| 최초 양의 손익 확인 | 아니오 |
| 최초 확인 시각 | (없음) |

## 기존 자본 사다리 상태

단계: ➖ **NO_EDGE_YET**

> ➖ 단0 — 깊은 표본외(OOS) 판정이 NO_EDGE. 짧은 forward는 15/20 관측이지만 현재 전략을 배치할 근거가 없다.

| 항목 | 값 |
|------|-----|
| 현재 단(rung) | 0 / 5 |
| 진입 근거 | (레거시/없음) |
| 배치 비율 | 0% |
| 실계좌 NAV | (측정 불가) |
| 배치 자본(USD) | 0 |
| 캐너리 무장 | 예(armed) |
| 지금 막는 것 | 앵커드 OOS 실패: OOS walk-forward 엣지 미확정 — 강건한 엣지 없음: 구간 과반 실패(0/3); 평균 샤프가 단순 보유 이하. 라이브 배포 정당화 안 됨. |

## 게이트 (다음 한 발의 합격 조건)

| 조건 | 상태 | 현재 | 기준 |
|------|:----:|------|------|
| 앵커드 표본외 판정 | ❌ FAIL | NO_EDGE (OOS 748개) | EDGE_CONFIRMED |
| 짧은 전진 관측 | ⏳ PENDING | 15/20 | ≥ 20 |
| 전략 지문 정합(검증=배포) | ✅ PASS | 일치 | 라이브 배포 설정 == 전진 검증 설정 |

## 첫-자본 추정 시점(ETA)

- 해당 없음.

## 자본 방어선 예산 (다운사이드 한계 — 내려가는 길)

- 첫 자본은 단2(NAV 의 20%) ≈ **(측정 불가)** 로 들어간다.
- 자동 강등(→단0, 무장 해제): 낙폭 ≥ **10%** → 약 (측정 불가) 손실.
- 절대 정지: 낙폭 ≥ **20%** → 약 (측정 불가) 손실.
- 즉 첫 자본의 다운사이드는 약 (측정 불가)(강등) 안에서 시스템이 스스로 자본을 회수한다 — 사람 개입 없이 작동하는 방어선.

## 다음 행동

- 현재 전략은 돈을 배치하지 않는다. forward 관측은 감사용으로 계속 쌓고, 독립 전략 후보를 같은 과적합 방어 기준으로 추가 검증한다.

⚠ 이건 종합 보고다(읽기 전용). 거래·자본 변경 없음 — 실제 배치는 자본 사다리 게이트가 자율로 한다(헌법 X.4 상시 위임). 운영자 전용은 입금·킬스위치·낙폭 예산뿐.

## 메타데이터

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| commit | d244c62f12d975e17e9d2f9af4952bf4dc3ec17f |
| trigger | workflow_run |
| timestamp_utc | 2026-09-15T22:24:52Z |

## 결정 JSON

```json
{"schema_version": "1.8", "as_of_utc": "2026-09-15T22:24:51Z", "stage": "NO_EDGE_YET", "headline": "➖ 단0 — 깊은 표본외(OOS) 판정이 NO_EDGE. 짧은 forward는 15/20 관측이지만 현재 전략을 배치할 근거가 없다.", "blocking_gate": "앵커드 OOS 실패: OOS walk-forward 엣지 미확정 — 강건한 엣지 없음: 구간 과반 실패(0/3); 평균 샤프가 단순 보유 이하. 라이브 배포 정당화 안 됨.", "current_rung": 0, "entry_route": null, "capital_pct": "0", "account_nav_usd": null, "deployed_capital_usd": null, "canary_armed": true, "live_money_state": {"status": "REAL_ORDER_PATH_ARMED", "can_submit_real_orders": true, "path": "capital-ladder-live-canary", "capital_usd": 143, "max_capital_usd": 143, "next_scheduled_live_utc": "2026-09-16T14:17:00Z", "required_gates": ["production environment machine authorization", "non-push workflow event", "US regular session", "KIS purchasable cash >= planned buys + 1% buffer", "portfolio circuit breaker clear", "K1 caps and K2 whitelist"], "detail": "자본 사다리 단1 센티넬 armed:true + 유효 자본. 다음 비-push 실행은 production 기계 승인·정규장·현금·손실 브레이커·K1/K2를 통과하면 실주문 단계에 도달한다.", "last_run": {"run_id": "[REDACTED_ACCOUNT]", "timestamp_utc": "2026-09-15T18:15:53Z", "event": "schedule", "live_step": "success", "intent_gate_ok": null, "intent_gate_reason": null, "preflight_ok": true, "preflight_reason": "ACTIVE_LIVE_TRACK", "breaker_reason": null, "order_states": [], "accepted_or_filled_count": 0, "broker_rejected_count": 0}}, "halt_recovery_evidence": {"evidence_quality": "VALID", "halt_cleared": false, "halt_present_after": false, "halt_present_before": false, "halt_reason_before": null, "measurement_contract_id": "sha256:2542c0ddd4499481582d820ebee48fadbbfbab9b6208c749d843c025b74288d8", "observed_at_utc": "2026-09-15T08:47:32.829Z", "orders_submitted": 0, "reasons": [], "reconciliation_state": "OK", "remote_exit": 0, "schema_version": "1.0", "status": "CLEAR", "workflow_commit": "d244c62f12d975e17e9d2f9af4952bf4dc3ec17f", "workflow_run_id": "[REDACTED_ACCOUNT]"}, "live_profit_evidence": {"current_status": "FILLED_NOT_PROFITABLE", "data_quality_warnings": [], "detail": "live 체결은 있으나 완전한 현재 총손익이 0 이하.", "fills_count": 2, "first_profit_fills_count": null, "first_profit_observed": false, "first_profit_observed_at_utc": null, "first_profit_realized_pnl_usd": null, "first_profit_total_pnl_usd": null, "first_profit_unrealized_pnl_usd": null, "gross_invested_usd": "104.45260000", "measurement_contract_id": "sha256:2542c0ddd4499481582d820ebee48fadbbfbab9b6208c749d843c025b74288d8", "measurement_scope": "strategy", "observed_at_utc": "2026-09-15T22:24:30Z", "realized_pnl_usd": "0", "return_pct": "-1.805316478479233642819805347", "schema_version": "1.1", "source_run_id": "[REDACTED_ACCOUNT]", "status": "FILLED_NOT_PROFITABLE", "total_pnl_usd": "-1.88570000", "unmarked_symbols": [], "unrealized_pnl_usd": "-1.88570000"}, "gates": [{"name": "앵커드 표본외 판정", "status": "FAIL", "current": "NO_EDGE (OOS 748개)", "required": "EDGE_CONFIRMED", "detail": "짧은 forward 관측보다 먼저 깊은 표본외 구간의 반복 가능성을 확인한다."}, {"name": "짧은 전진 관측", "status": "PENDING", "current": "15/20", "required": "≥ 20", "detail": "계속 관측하되 앵커드 OOS 실패를 숨기거나 뒤집은 것으로 간주하지 않는다."}, {"name": "전략 지문 정합(검증=배포)", "status": "PASS", "current": "일치", "required": "라이브 배포 설정 == 전진 검증 설정", "detail": "지문(유니버스·가중·추세 게이트 등, 캡/자본 제외)이 다르면 자본 사다리가 어떤 단에서도 자본을 배치하지 않는다(BLOCKED). 두 TOML 을 일치시켜야 첫 자본이 들어간다."}], "eta": {"basis": "n/a", "obs_remaining": null, "obs_per_trading_day": null, "trading_days_remaining": null, "projected_date": null, "assumption": "해당 없음.", "convergence": "unknown", "sample_stability": "unknown", "legacy_excluded": null, "snapshot_count": null}, "safety_budget": {"reference_rung": 2, "capital_usd": null, "demote_dd_pct": "10", "halt_dd_pct": "20", "loss_at_demote_usd": null, "loss_at_halt_usd": null, "current_dd_pct": null, "margin_to_demote_pct": null, "margin_to_halt_pct": null, "prospective": true}, "next_action": "현재 전략은 돈을 배치하지 않는다. forward 관측은 감사용으로 계속 쌓고, 독립 전략 후보를 같은 과적합 방어 기준으로 추가 검증한다.", "forward_n_obs": 15, "forward_legacy_excluded": 0}
```

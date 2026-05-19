# Research: 자동 룰 설계자 (spec 010)

**Phase**: 0 · **Date**: 2026-05-19 · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

---

## R-D1. Claude system prompt에 constitution 안전 제약 포함

**Decision**: Claude system prompt에 constitution I·II·III·VI 원칙을 한국어 + 영어 혼합 요약으로 포함. 운영자 의도 + KIS 계좌 상태 + 안전 제약 → "다음 TOML 형식으로 룰 생성" 지시.

**Rationale**: Claude가 안전 제약을 모르면 cap 게이트 위반·whitelist 외 종목 포함·LLM judgment point 외 호출 등 생성 가능. 시스템 prompt에 박아두면 1차 방어. 그래도 위반 시 정적 검증(R-D3)이 2차 방어.

**Alternatives considered**:
- (a) 운영자 입력만으로 호출 → 거부: 안전 제약 누락 위험.
- (b) Claude tool use(function calling) → 거부: anthropic SDK tool 정의가 prompt보다 복잡. 본 스펙은 prompt + structured TOML 출력만으로 충분.

**Implication**: prompt 길이가 ~3KB(시스템 + 의도 + 계좌 상태). 입력 토큰 ~1K 추정. Claude 4.5/4.6 가격(input $3/M)으로 호출당 < $0.01.

---

## R-D2. Claude 응답 형식 — structured TOML 직접 출력

**Decision**: Claude에게 "응답을 다음 TOML 블록 1개만으로 작성하세요 (코드 펜스 제외, ```toml 시작·``` 종료 안 함)" 지시. 응답 전체를 TOML 파서에 그대로 통과.

**Rationale**:
- structured output(예: JSON tool use)은 SDK 복잡도 증가.
- TOML 직접 출력은 운영자가 audit_log에서 그대로 읽고 검토 가능 — FR-008·SC-004 정합.
- 파싱 실패 시 자동 재설계 1회 차감 (edge case 4).

**Alternatives considered**:
- (a) JSON 출력 → TOML 변환 → 거부: 변환 단계가 추가 실패 지점.
- (b) Tool use → 거부: 복잡도·테스트 비용.

**Implication**: validator.py가 TOML 파싱 실패를 명확한 한글 메시지로 audit + 재설계 트리거.

---

## R-D3. 정적 검증 — TOML 파싱 후 spec 001 validator 재사용

**Decision**: 생성된 TOML을 spec 001의 `auto_invest.config.loader.load_config_from_text(...)` 같은 함수로 파싱(없으면 신설). 그 함수가 이미 caps·whitelist·rules pydantic validation 수행. 추가로 design/validator.py에서:

1. `caps`의 per_trade_pct·per_symbol_pct·global_exposure_pct가 모두 양수.
2. 모든 `[[rules]]` 항목의 symbol이 `[whitelist].symbols`에 들어 있음.
3. 모든 rule의 `action.order_type`이 `whitelist.order_types`에 들어 있음.
4. 운영자 의도의 자본 ≤ KIS 계좌 잔고.
5. 운영자 의도의 종목 범위가 미국 주식·ETF (US 6자 미만 티커 휴리스틱).

**Rationale**: pydantic + 추가 정적 검증으로 SC-003(생성 룰 100% 통과) 달성.

**Alternatives considered**:
- (a) 동적 검증(시뮬 1 tick)만 → 거부: 정적 검증이 더 빠르고 결정적.

**Implication**: validator.py 단위 테스트가 SC-003 회귀 가드.

---

## R-D4. 운영자 OK 인터랙티브 — typer.prompt + 60초 타임아웃

**Decision**: 검증 통과 후 `typer.prompt("이 룰로 라이브 시작하려면 OK / y / 예 / yes 중 하나를 입력하세요")`. 60초 안에 응답 없으면 거부 처리. 응답이 OK/y/예/yes 정확히 일치하지 않으면 거부.

**Rationale**:
- 타임아웃 60초는 운영자가 의도 보고 결정할 시간으로 충분.
- 명확한 OK 키워드 매칭으로 오타·실수 방어.
- 거부는 안전한 기본값.

**Alternatives considered**:
- (a) 무한 대기 → 거부: design 명령이 영구 정지될 위험.
- (b) 5초 → 거부: 너무 짧음.
- (c) typer.confirm (Y/n) → 거부: "OK"라는 명시적 키워드가 운영자가 의식적으로 결정한 신호로 더 안전.

**Implication**: typer.prompt에 타임아웃 옵션이 없으면 `signal.alarm` 또는 `asyncio.wait_for`로 구현.

---

## R-D5. paper-run 일주일 처리 — background + 사후 확인 명령

**Decision**: design 명령은 백테스트(stub) + paper-run 1일분만 동기 실행. 통과 시 운영자 OK 받음 → 라이브 시작이거나, 또는 운영자가 "일주일 검증 옵션"을 선택하면:

1. design 명령이 paper-run을 background로 띄움 (subprocess + nohup).
2. audit_log에 `RULE_DESIGN_PAPER_RUN_STARTED(session_id=...)` 기록.
3. design 명령은 즉시 종료 + 운영자에게 "paper-run 일주일 진행 중. 7일 후 `auto-invest design --check`로 결과 확인" 안내.

`auto-invest design --check` 옵션:
- 가장 최근 `RULE_DESIGN_PAPER_RUN_STARTED`의 session_id로 paper-run 상태 조회.
- 일주일이 안 됐으면 진행 상황(현재 시점 paper-report) 보여줌.
- 일주일 지났으면 최종 리포트 + 운영자 OK 받고 라이브 시작.

**Rationale**: 본 spec의 단순화 — 운영자 부담을 줄이기 위해 design 명령 1회만 칠 수 있으면 충분. 일주일 후 알림은 spec 005/006/007의 자동 배포가 들어오면 자동화 가능.

**Alternatives considered**:
- (a) systemd timer로 일주일 후 자동 검증 → 거부: 운영자 환경 의존, 본 스펙 범위 밖.
- (b) design 명령이 일주일 동안 foreground 유지 → 거부: 비현실적.

**Implication**: state.py가 audit_log 기반 상태 머신 관리 (PAPER_RUN_STARTED → 진행 중 → 완료 → 운영자 OK 대기 → 라이브).

---

## R-D6. K3 cost-band 추가 — `rule_design`

**Decision**: `telemetry/meter.py`에 `rule_design` cost-band 추가. 호출당 입력 ≤ 50KB(약 12K 토큰), 출력 ≤ 10KB(약 2.5K 토큰). 1회 호출 비용 한도 $0.20 (여유 5배로 SC-002 $1 만족).

**Rationale**: constitution III의 "judgment points마다 KPI 한도" 원칙. cost-band 없이 호출하면 prompt 폭주·비용 폭주 가능.

**Alternatives considered**:
- (a) cost-band 없이 호출 → 거부: spec 002 KPI가 호출별 한도를 강제하지 못함.
- (b) 비용 한도 더 낮게(예: $0.05) → 거부: 룰 설계는 긴 system prompt + 계좌 정보가 필요해 비용 한도가 너무 빡빡하면 정상 호출도 차단됨.

**Implication**: K3 파일 (`telemetry/meter.py`) 1줄 변경 (cost-band 사전에 새 키 추가). additive.

---

## R-D7. K4 페이로드 4종 — RULE_DESIGN_*

**Decision**: 신규 페이로드:
- `RuleDesignRequestedPayload`: 운영자 의도 + 호출 시점.
- `RuleDesignCompletedPayload`: 원본 의도 + Claude 해석 매개변수 + 생성 룰 TOML + Claude 모델 ID + 토큰 사용량.
- `RuleDesignRejectedPayload`: 실패 사유 (parse_error · whitelist_violation · cap_violation · backtest_fail · paper_run_fail · operator_declined · max_retries · mutex_conflict · insufficient_balance · kis_token_failed).
- `RuleDesignDeployedPayload`: 운영자 OK 후 라이브 시작 시 기록. 새 worker session id 포함.

**Rationale**: FR-008·SC-004 — 사후 추적 가능성. 기존 LLM_CALL과 분리되어야 룰 설계 호출만 grep 가능.

**Implication**: K4 파일(`persistence/audit.py`) 1회 추가 변경. spec 009의 K4 additive 패턴과 동일.

---

## R-D8. mutex — spec 009 패턴 그대로

**Decision**: `design/mutex.py`는 spec 009의 `paper/mutex.py`와 같은 구조. audit_log에서 가장 최근 `RULE_DESIGN_REQUESTED`가 짝맞춤 `RULE_DESIGN_COMPLETED` 또는 `RULE_DESIGN_REJECTED` 없이 떠 있는지 확인. 충돌 시 즉시 거부.

**Rationale**: 같은 패턴 재사용으로 회귀 위험 최소화. SQLite advisory lock 의존성 0.

**Implication**: spec 009의 mutex 단위 테스트 패턴을 spec 010에 거의 그대로 적용 가능.

---

## R-D9. Claude API 호출 mock 전략

**Decision**: anthropic SDK의 `Anthropic.messages.create(...)`를 monkeypatch로 mock. 테스트에서는 미리 준비한 TOML 문자열을 응답으로 주입.

**Rationale**: 실제 Claude API 호출은 비용 + 비결정성 → 테스트 자동화 불가. mock으로 모든 시나리오(정상·파싱 실패·whitelist 위반·재설계 트리거) 검증.

**Implication**: claude_client.py에 thin wrapper만 두고, 테스트에서는 그 wrapper의 메서드를 monkeypatch.

---

## R-D10. 자동 재설계 루프 — 최대 3회

**Decision**: 1회 호출이 (a) TOML 파싱 실패 (b) 정적 검증 실패 (c) 백테스트 합격 미달 (d) paper-run 1일분 실패 중 하나면 자동 재설계 1회 트리거. Claude에게 "직전 실패 사유 + 직전 생성 룰 + 운영자 원본 의도"를 다시 prompt에 포함해 재시도. 최대 3회 합산. 3회 모두 실패 시 운영자에게 한글 보고.

**Rationale**: FR-007. 3회는 비용·시간 균형. 더 늘리면 비용 폭주 + 운영자 대기 시간 증가.

**Alternatives considered**:
- (a) 무한 재시도 → 거부: 비용 폭주.
- (b) 1회만 → 거부: Claude의 첫 시도가 실패할 가능성이 5~10%로 추정되므로 여유가 너무 적음.

**Implication**: state.py가 재시도 카운트를 audit_log 기반으로 추적. claude_client.py가 prompt에 직전 실패 사유 포함.

---

## R-D11. 백테스트 stub 가드 — ImportError 처리

**Decision**: verifier.py에서:
```python
try:
    from auto_invest.backtest.runner import run_backtest
    BACKTEST_AVAILABLE = True
except ImportError:
    BACKTEST_AVAILABLE = False
```
백테스트 단계에서 `BACKTEST_AVAILABLE`이 False면 한글 경고 + 백테스트 패스 처리 (paper-run만 검증). True면 정상 호출.

**Rationale**: spec 008 미완성 상태에서도 spec 010 머지·동작 가능. spec 008이 완성되면 import 가드가 자동으로 True가 되어 백테스트 활성화.

**Implication**: verifier.py 단위 테스트에서 두 시나리오 모두 검증 — `BACKTEST_AVAILABLE=False`일 때 진행, `True`일 때 호출.

---

## Open Questions

없음. R-D1~R-D11이 spec.md의 모든 FR·SC·Edge Case를 커버. Phase 1로 진행 가능.

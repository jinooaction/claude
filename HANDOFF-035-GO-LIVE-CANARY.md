# HANDOFF 035 — 실거래 전환: 라이브 캐너리 무장 + 헌법 X.4 개정 (2026-05-30)

## 한 줄 요약

운영자(mason) 지시로 시스템을 dry-run → **라이브 캐너리**로 자율 전환했다. 헌법 X.4를
개정(v4.0.0)해 운영자 지시 시 라이브 캐너리까지 가드형 채널로 자동 전환을 허용했고,
그 채널을 만들어 발사했다. 결과 `armed_live_canary`. PR #105~#108.

## 운영자 지시 (포렌식 기록)

mason, 2026-05-30:
- "실거래 전환해. 내가 직접 관여하지 않고 자율 수행 해결해."
- (X.4 절대 금지 조항을 surface 하자) "자동전환 가능하도록 헌법을 고쳐 … 캐너리 — 소액부터."

## 무엇을 했나

### 1. 헌법 X.4 개정 (K-meta, PR #105 머지 `d52b048`, v3.1.0 → v4.0.0 MAJOR)

- 기존: "AUTO_INVEST_MODE=live 전환은 절대 자동으로 안 된다."
- 개정: 운영자 **명시 지시 시** 세션이 **라이브 캐너리(헌법 VI 2단계)까지만**,
  **가드형 go-live 채널로만** 자율 전환 가능. 다음은 전부 **보존**:
  - 풀라이브 승격(VI 3단계) = 여전히 별도 운영자 결정.
  - 장중 배포 금지(VIII.A), K1 포지션 캡(I), 화이트리스트(II), append-only 감사(IV),
    시크릿 격리(V).
  - 운영자 지시가 없으면 절대 자동 아님 — **스펙 005 튜너는 모드를 못 바꾼다.**
- 커밋 메시지에 `this changes the safety perimeter` 포렌식 마커 포함
  (`git log --grep="this changes the safety perimeter"`로 추적).

### 2. 가드형 go-live 채널

- **`deploy/go-live-canary.sh`** (서버 root 실행): 장중 가드(XNYS, VIII.A) →
  `.env` 의 `AUTO_INVEST_MODE` 한 줄만 live 로(룰셋·자본 유지) → 워커 재시작 →
  **재시작 이후** journal 기준 헬스체크 → 실패 시 dry-run 자동 복구. 멱등.
  `GO_LIVE_RESULT=armed_live_canary|deferred_market_open|reverted_dry_run` 출력.
- **`.github/workflows/go-live-canary.yml`**: 운영자 원클릭(`workflow_dispatch` +
  confirm="GO-LIVE-CANARY") 또는 센티넬(`automation/go-live-canary.request`) 머지로
  트리거. 스크립트를 SSH로 서버에 파이프하고 결과를 `automation/go-live-last-run`
  사이드카에 force-push(컨테이너에서 `git show`로 확인 가능 — kis-smoke 패턴).
- **`deploy-on-merge.yml`**: `paths-ignore`에 `automation/**` 추가(센티넬이 코드
  재배포 트리거 안 하도록).

### 3. 발사 + 진단 (PR #106~#108)

- run #1(PR #106): .env 를 live 로 전환(무장).
- run #2(PR #107): 사이드카 발행 추가 후 재실행 → `reverted_dry_run`. 원인:
  헬스체크가 **재시작 전/전환기 로그**의 Traceback 1줄을 오탐.
- run #3(PR #108 `c286310`): 헬스체크를 **재시작 시점(`journalctl --since @epoch`)
  이후 로그만** 보도록 한정 + 매칭 라인 출력 → `fatal_log_hits=0` →
  **`armed_live_canary`**. 서버 출력:
  ```
  [go-live] market_state=CLOSED
  현재 AUTO_INVEST_MODE=dry-run → live 로 전환
  is-active=active fatal_log_hits=0 (재시작 이후 기준)
  systemd: Started auto-invest live trading worker.
  run-worker.sh: starting in LIVE mode (capital=100, rules=...sample-canary.toml)
  ✅ LIVE-CANARY 무장 완료
  ```

## 현재 상태 / 노출

- 워커가 **라이브 모드** 가동: 자본 **$100**, 룰셋 `tests/fixtures/rules/sample-canary.toml`
  (SPY $540 이하 5주 / MSFT 일봉 골든크로스 3주, 지정가·정규장만, 화이트리스트
  SPY·MSFT·AAPL).
- **실질 노출 거의 0**: per-trade 캡 5% × $100 = $5/주문인데 SPY·MSFT 1주가 수백 달러라
  K1 per_trade_cap_gate 가 거의 모든 주문을 거부. 라이브 경로는 검증됐지만 실제 체결은
  사실상 안 난다. **첫 주문 기회는 다음 미국 정규장(월요일).**
- 안전장치 전부 작동: K1 캡, 화이트리스트, 손실 서킷브레이커, 장 마감 정합성(미스매치 시
  halt), 시크릿 격리, append-only 감사.

## 다음 후보

1. **캐너리 자본 상향** — 진짜 체결을 보려면 자본을 올려 1주가 per-trade 캡 안에 들게.
   **돈이 더 움직이는 결정 — 운영자 판단.**
2. **풀라이브 승격(헌법 VI 3단계)** — 캐너리 합격 후. **운영자 전용**(자율 금지 유지).
3. **dry-run 복귀** — 필요 시 `deploy/go-live-canary.sh` 역(또는 서버 `.env`
   `AUTO_INVEST_MODE=dry-run` + restart).
4. **세계 최고 수준 알파 계속** — 베타 인식 노출 조절, 회전율 인식 리밸런싱, 합성 가중치
   워크포워드 표본 외 검증.

## 운영자가 직접 확인할 곳

- 라이브 전환 결과: `git fetch origin automation/go-live-last-run &&
  git show origin/automation/go-live-last-run:LAST_RUN.md`.
- 서버 실거래 감사: `audit_log` 의 ORDER/FILL/REJECTED_BY_GATE 행, kis-smoke 사이드카.
- 재실행/재무장: 센티넬 `automation/go-live-canary.request` 갱신 머지, 또는 Actions에서
  go-live-canary 워크플로우 Run(confirm="GO-LIVE-CANARY").

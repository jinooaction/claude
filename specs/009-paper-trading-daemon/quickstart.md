# Quickstart: Paper-Trading Daemon (spec 009)

**대상**: 운영자 (mason)
**전제**: spec 001~008 완료, KIS App Key/Secret/계좌번호 보유, `auto-invest` CLI 설치됨.
**목적**: live 노출 전 일주일짜리 paper-trading 관찰을 시작·종료·해석하기.

---

## 시나리오: 일주일 paper 관찰 시작하기

### 1단계: 환경 점검

```bash
# 현재 live worker가 떠 있는지 확인 (paper-run mutex 충돌 사전 회피)
ps aux | grep "auto-invest run" | grep -v grep

# audit_log에 stop 짝 없는 started 이벤트가 있는지 확인
sqlite3 data/auto_invest.db \
  "SELECT id, event_type, created_at FROM audit_log
   WHERE event_type IN ('worker_started', 'paper_run_started')
   ORDER BY id DESC LIMIT 5;"
```

만약 stale `worker_started`나 `paper_run_started`가 보이고 PID가 살아 있지 않다면 mutex가 잘못된 stale 락으로 막을 수 있다. 그 경우 운영자는 audit_log에 수동 stop 이벤트를 INSERT하거나, paper-run을 강제 시작하는 옵션을 사용 (후속 task에서 결정).

### 2단계: paper-run 시작

```bash
# foreground 시작 — terminal 1개를 점유
auto-invest paper-run \
    --config config/rules.toml \
    --db data/auto_invest.db \
    --halt-path data/halt.flag \
    --env-file .env \
    --capital 100.00 \
    --prices config/llm_prices.toml
```

stdout에 `paper-run started (session_id=N, ruleset_sha256=...)` 1줄이 보이면 성공. 그 뒤로 매 tick의 INFO 로그와 시뮬 체결 시 `[PAPER FILL] ...` 메시지가 흐른다.

### 3단계: 일주일 동안 그대로 두기

- 미국장 정규시간 외에는 session window 가드가 평가를 스킵 — 정상 동작.
- 데몬을 백그라운드로 보내려면 systemd 유닛으로 띄우는 게 권장 (본 스펙 범위 밖 — spec 010 후속).
- 임시로는 `nohup auto-invest paper-run ... &` 또는 `tmux`/`screen` 세션 사용.

### 4단계: 중간 점검 (며칠 뒤)

```bash
# 현재 시점까지 paper-report
auto-invest paper-report --since "$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)"
```

룰별 시그널·체결 수·차단 분포를 보면서 룰셋이 의도대로 동작하는지 즉각 확인 가능. 명백한 회귀(예: 모든 룰이 cap 게이트에 막힘)가 보이면 즉시 종료하고 룰셋 수정.

### 5단계: 종료

```bash
# foreground라면 Ctrl+C (SIGINT). nohup이라면 kill <PID>.
kill -TERM <paper-run PID>
```

stdout에 `paper-run stopped (reason=signal_received)` 메시지. exit code 0이면 정상.

### 6단계: 최종 리포트

```bash
auto-invest paper-report \
    --since "$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)" \
    --format text > paper-report-week1.txt

# JSON으로도 보관 (후속 분석용)
auto-invest paper-report \
    --since "$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)" \
    --format json > paper-report-week1.json
```

---

## 시나리오: paper-run 도중 live로 전환하고 싶을 때

paper-run과 live-run은 **상호 배타**(FR-015). 다음 순서로 전환:

```bash
# 1. paper-run 깨끗하게 종료
kill -TERM <paper-run PID>

# 2. 최종 리포트 확인 후 룰셋 OK 판단
auto-invest paper-report --since ...

# 3. live 시작 (canary 적용 또는 100달러 자본으로 직접)
auto-invest run --config config/rules.toml --capital 100.00 ...
```

paper-run을 종료하지 않고 live를 시작하면 live 쪽도 mutex 거부로 exit 70.

---

## 시나리오: paper-report로 룰 튜닝 결정하기

리포트 출력의 **Tuning feedback** 섹션이 핵심:

- **Rules that never fired**: 일주일간 단 한 번도 시그널이 발생 안 한 룰 → 임계값이 너무 보수적이거나 시장 상황이 미달. 룰셋에서 임시 제거 또는 임계값 완화.
- **Hottest rules**: 너무 자주 trigger되는 룰 → 너무 공격적이거나 노이즈 흡수. cap에 자주 차단되는지 확인 (Gate denials 섹션).
- **quote_source fallback (last 비율)**: 5% 이상이면 quote 신선도 문제. KIS 시장 데이터 권한 점검.

리포트만 보고 결정이 안 서면 같은 기간의 audit_log를 직접 쿼리해 시그널 시점·종목 분포를 확인.

---

## 잘 안 될 때

### "live worker가 실행 중입니다" — mutex 충돌

stale lock 의심 시:
```bash
sqlite3 data/auto_invest.db \
  "SELECT id, event_type, created_at, payload FROM audit_log
   WHERE event_type IN ('worker_started','paper_run_started','worker_stopped','paper_run_stopped')
   ORDER BY id DESC LIMIT 10;"
```
running PID가 살아 있는지 `ps -p <PID>`로 확인. 죽었으면 운영자가 수동으로 stop 이벤트 INSERT (또는 후속 자동 정리 기능 도입까지 기다림).

### KIS quote API 401/403

`auto-invest paper-run`도 quote 권한이 필요. KIS 키 갱신 또는 권한 확인. paper-run 데몬이 시작은 됐지만 첫 tick부터 `order_rejected_by_broker` 또는 `error`가 쌓이면 quote 권한 점검.

### audit_log가 너무 커지면

일주일 paper-run = ~10만 row. paper-report는 200ms 안에 끝나야 정상. 200ms 초과 시 `EXPLAIN QUERY PLAN`으로 인덱스 사용 확인. spec 002에서 만든 `idx_audit_event_type_created_at`이 살아 있어야 함.

---

## 다음 단계

- paper-report 결과로 룰셋 튜닝 → 다시 paper-run 1~2일 → live 캐너리 → 100달러 live.
- systemd 통합(spec 010, 후속), hardened canary 통합(spec 007 후속)이 paper-trading을 자동화 흐름에 편입시킬 예정.
- 자동 튜닝(spec 005)이 paper-report를 입력으로 받는 인터페이스도 후속 스펙.

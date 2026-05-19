# Quickstart: 자동 룰 설계자 (spec 010)

**대상**: 운영자 (mason)
**전제**: spec 001~009 완료, KIS·Claude API 키 보유.
**목적**: 자연어 한 줄로 룰 설계 → 자동 검증 → 라이브 시작.

---

## 시나리오 1: 첫 룰 설계

```bash
auto-invest design \
    --intent "자본 100달러, 미국 대형주 분산, 매주 월요일 적립, 위험 보통"
```

진행 과정 (예상 약 6~7시간 — paper-run 1일분 포함):

1. 시스템이 KIS 잔고를 조회. 잔고가 의도 자본보다 작으면 한글 경고.
2. Claude가 룰 설계 (수 초).
3. 정적 검증 통과 확인 (수 초).
4. paper-run 1일분 자동 실행 (약 6.5시간, 미국 정규장 1일).
5. 검증 통과 시 한글 요약 + OK prompt.
6. 운영자가 `OK` 한 줄 → 라이브 시작.

운영자가 자리를 비워야 할 때:

```bash
# 1단계: paper-run 1일분이 background로 진행되도록 띄움
auto-invest design --intent "..." &

# 2단계: 다음 날 오후에 결과 확인
auto-invest design --check
```

---

## 시나리오 2: 의도 바꾸기

한 달 후 위험도 조정을 원하면:

```bash
auto-invest design --intent "자본 100달러, 미국 대형주 분산, 위험 낮음으로 변경"
```

시스템이 새 룰 생성 + 검증. 통과하면 운영자 OK 후 기존 라이브 worker 정상 종료 + 새 룰로 재시작.

---

## 시나리오 3: 의도가 모호할 때

```bash
auto-invest design --intent "안전하게 굴려"
```

Claude가 다음 기본값으로 해석:
- 위험 "안전" → max_drawdown 3%, per_symbol_pct 10%.
- 종목 우주 → VOO 단일 (S&P 500 ETF).
- 적립 주기 → 매주 월요일.

해석 결과는 audit_log + stdout에 한글로 표시되므로 운영자가 사후 확인 가능.

---

## 시나리오 4: 자동 재설계

Claude 첫 시도가 실패한 경우 (예: whitelist 외 종목 포함):

```
1회차 룰 생성 실패: Claude가 'BTC-USD'를 룰에 포함 (미국 주식 아님).
재설계 시도 2/3 중...

2회차 룰 생성 성공. 검증 진행 중.
```

3회 모두 실패하면:

```
자동 룰 설계 실패: 3회 모두 검증 통과 못 함.
의도를 좀 더 구체적으로 다시 알려주세요.
마지막 시도 실패 사유: paper_run_fail (외부 API 오류율 5% 초과)
```

---

## 시나리오 5: 일주일 paper-run

운영자가 일주일 검증을 원하면:

```bash
auto-invest design --intent "..." 
# (paper-run 1일분 진행 후 운영자 OK 단계 도달)
# 운영자는 OK 대신 'wait' 입력
> wait
```

시스템이 paper-run을 추가 6일 background로 계속 + design 명령은 즉시 종료.

일주일 후:

```bash
auto-invest design --check
```

7일치 paper-report + 운영자 OK prompt → 라이브 시작.

---

## 트러블슈팅

### "mutex 충돌" — 다른 design 명령이 떠 있음

```bash
# audit_log 확인
sqlite3 data/auto_invest.db \
  "SELECT seq, event_type, ts_utc FROM audit_log
   WHERE event_type LIKE 'RULE_DESIGN%' 
   ORDER BY seq DESC LIMIT 5;"
```

stale 상태면 운영자가 수동으로 `RULE_DESIGN_REJECTED` INSERT 후 재시도.

### "Claude API 오류" 반복

- spec 002 KPI 대시보드로 입력 토큰 한도 초과인지 확인.
- 의도 텍스트를 더 짧게 줄여 재시도.

### "잔고 부족" 경고

KIS 계좌의 실제 예수금을 확인 + 입금 후 재시도.

---

## 다음 단계

- spec 008(백테스트)이 완성되면 verifier.py가 자동으로 백테스트 단계도 활성화.
- spec 007(hardened canary)이 완성되면 운영자 OK 단계도 자동화 가능.
- spec 005(autonomous tuner)이 완성되면 룰 자동 진화로 의도 변경 없이 룰 업데이트.

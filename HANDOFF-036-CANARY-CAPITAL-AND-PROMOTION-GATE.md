# HANDOFF 036 — 캐너리 실체결 자본 + 자동 승격 게이트 (2026-05-30)

## 한 줄 요약

운영자(mason) "다음 선택지 1번과 2번 모두 자율진행" 지시를 완료. ① 라이브 캐너리를
실제 체결 가능하게(자본 $12k + 축소 룰셋), ② 캐너리→풀라이브 자동 승격의 **결정
게이트**(스펙 026)를 구축. PR #110~#112. 전체 1229 통과.

## 선택 1번 — 실제 캐너리 체결 (자본 $12k + 축소 룰셋)

- **`deploy/canary-live-rules.toml`(신규)**: qty=1 축소 룰셋(SPY 눌림목·MSFT 골든
  크로스·AAPL RSI 과매도), 전부 CANARY 스테이지, 지정가·정규장·화이트리스트만.
  테스트 픽스처(sample-canary.toml) 무변경.
- **`deploy/go-live-canary.sh` 확장**: (0) 서버 repo 를 origin/main 으로 동기화,
  (0b) 센티넬에서 `capital_usd`/`rules_path` 읽기, (3b) `.env` 에 적용. 멱등.
- **센티넬** `automation/go-live-canary.request`: `capital_usd: 12000`,
  `rules_path: deploy/canary-live-rules.toml`.
- **결과**(go-live 사이드카 run #5, 커밋 `ce85cda`): `armed_live_canary`.
  서버: `starting in LIVE mode (capital=12000, rules=deploy/canary-live-rules.toml)`,
  `is-active=active fatal_log_hits=0`.
- **per-trade 5% 캡($600)** 안에 우량주 1주(~$540)가 들어 **실제 체결 가능**.
  첫 주문 기회는 다음 미국 정규장. 노출 상한: per-symbol $2,400 / global $9,600.

### 부수 수정 (헬스체크 오탐 2건)

run #2·#4 가 `is-active=active` 인데 `reverted_dry_run` 된 원인 = 재시작 때 종료되는
이전 인스턴스의 트레이스백이 헬스 윈도에 섞임. 둘 다 수정:
- **`worker/loop.py`(비커널)**: `record_stop` 을 best-effort 로(systemd SIGTERM 순서상
  DB 가 이미 닫혀 `sqlite3.ProgrammingError` 로 워커가 비정상 종료하던 것을 try/except).
- **`go-live-canary.sh`**: 헬스체크를 마지막 "Started … worker" 마커 이후(현재
  인스턴스) 로그만 스캔하도록 격리.

## 선택 2번 — 자동 승격 게이트 (스펙 026, 안전 경로)

- **`promotion/gate.py`(신규, 비커널)**: `evaluate_promotion_readiness()` — 순수·
  결정론적. 6조건(라이브 기간≥min_duration·청산거래≥1·낙폭≤허용·수익률≥0·
  서킷브레이커 무사고·정합성 무사고) 전부 만족해야 ready. None 이면 보수적 불합격.
- **`promotion/readiness.py`(신규, 비커널)**: `compute_readiness(conn)` — 라이브
  audit_log 에서 입력 측정(스펙 011 성과 + 감사 조회). read-only.
- **CLI `auto-invest promote-check [--format text|json]`**: 준비 여부 보고(ready→exit 0).
  `[caps]` 만 파싱해 KIS 시크릿 불요. **승격을 수행하지 않음**(보고 전용).
- **`.github/workflows/promote-readiness.yml`**: 매일 22:30 UTC 서버에서 promote-check
  실행 → `automation/promote-readiness-last-run` 사이드카로 발행(컨테이너 확인 가능).

### 의도적 미구현 — 실제 풀라이브 발화

**자본→풀·스테이지→FULL_LIVE 전환(비가역·전자본)은 아직 안 한다.** 그건 다음을
**모두** 통과해야 한다(헌법 VI·IX.B-2):
1. 이 스펙의 VI 라이브 트랙레코드 게이트(`promote-check` ready=True), 그리고
2. 스펙 007 하드닝 캐너리(다중 지표·충격·퍼즈, ≥30/45 거래일).

캐너리 시작 후 **최소 30거래일** 지나야 가능하므로 지금 발화하지 않는다. 매일
readiness 가 사이드카에 발행되므로 두 게이트가 녹색이 되는 시점을 관찰 가능.
**다음 작업**: 하드닝 캐너리(스펙 007) 통과까지 결합한 승격 발화 로직(가드형 채널로
자본→풀 + 스테이지→FULL_LIVE + 헬스체크/롤백). 검증 안 된 자동화로 전자본을 미리
발화시키지 않기 위해 의도적으로 분리했다.

## 현재 상태 / 노출

- 워커: **라이브 모드**, 자본 **$12,000**, 룰셋 `deploy/canary-live-rules.toml`(qty=1).
- 실제 노출: 체결 발생 시 우량주 1주 단위(per-symbol $2,400 / global $9,600 상한).
  서킷브레이커(일 10%·누적 20%)·정합성 halt·K1 캡·화이트리스트 전부 작동.
- 자동 승격: **결정 게이트만** 가동(매일 평가·보고). 실제 풀라이브 발화 없음.

## 운영자가 확인할 곳

- 라이브 전환 결과: `git show origin/automation/go-live-last-run:LAST_RUN.md`.
- 승격 준비도: `git show origin/automation/promote-readiness-last-run:LAST_RUN.md`
  (매일 22:30 UTC 갱신; 수동은 Actions 에서 promote-readiness Run).
- 서버 실거래: `audit_log` 의 ORDER/FILL/REJECTED_BY_GATE, kis-smoke 사이드카.
- dry-run 복귀: 센티넬을 dry-run 으로 바꾸거나 서버 `.env` `AUTO_INVEST_MODE=dry-run`.

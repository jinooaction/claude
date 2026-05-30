# 라이브 캐너리 전환 — 최신 실행 결과

이 파일은 `go-live-canary.yml` 이 매 run 마다 force-push 합니다.
외부에서 `git fetch origin automation/go-live-last-run && git show origin/automation/go-live-last-run:LAST_RUN.md` 로 확인.

| 항목 | 값 |
|------|-----|
| run_id | 26684166751 |
| run_url | https://github.com/jinooaction/claude/actions/runs/26684166751 |
| commit | ce85cdaf9338a5d51a47946386ca54a3a18724ba |
| trigger | push |
| timestamp_utc | 2026-05-30T12:47:45Z |
| GO_LIVE_RESULT | armed_live_canary |
| ssh_exit | 0 |

## 의미

✅ **라이브 캐너리 무장됨** — AUTO_INVEST_MODE=live (캐너리 룰셋·소액·K1 캡). 첫 실주문 기회는 다음 미국 정규장.

## 서버 출력 (go-live-canary.sh)

```
Warning: Permanently added '202.182.125.132' (ED25519) to the list of known hosts.
HEAD is now at ce85cda Merge pull request #111 from jinooaction/claude/serene-knuth-xDbnN
[go-live] server repo @ ce85cda
[go-live] market_state=CLOSED
[go-live] 현재 AUTO_INVEST_MODE=dry-run → live 로 전환(캐너리 룰셋·자본 유지).
[go-live] AUTO_INVEST_CAPITAL=12000 적용(중간 자본).
[go-live] AUTO_INVEST_RULES=deploy/canary-live-rules.toml 적용(포지션 축소 룰셋).
[go-live] 워커 재시작 완료 — 헬스 윈도 95초 대기…
[go-live] is-active=active fatal_log_hits=0 (현재 인스턴스 기준)
[go-live] --- 현재 인스턴스 journal 발췌(마지막 30줄) ---
May 30 12:46:10 auto-invest systemd[1]: Started auto-invest live trading worker.
May 30 12:46:10 auto-invest run-worker.sh[155373]: [run-worker.sh] starting in LIVE mode (capital=12000, rules=deploy/canary-live-rules.toml)
[go-live] --- 발췌 끝 ---
[go-live] ✅ LIVE-CANARY 무장 완료(mode=live). K1 캡·화이트리스트·서킷브레이커·정합성 그대로 작동.
GO_LIVE_RESULT=armed_live_canary
```

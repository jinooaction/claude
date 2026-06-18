# 스펙 055 — 자율 전략 재지정 (autonomous strategy reassignment, 5중 게이트 폐회로)

**날짜**: 2026-06-16 · **운영자 위임**: "자율 전략 진화 폐회로 — 더 나은 전략을 시스템이
스스로 라이브로 교체. 완전 자율 + 5중 안전장치." · **헌법**: X.5 v6.0.0 개정 동반

## 왜 (문제)

스펙 053 forward 토너먼트는 7개 추세 트랙을 병렬로 돌려 정직성 게이트로 챔피언/도전자를
계산하지만, **라이브 전략을 무엇으로 쓰는가**는 운영자/배포 설정이 정했다 — 토너먼트가
"이 도전자가 현 라이브를 이긴다"고 판정해도 사람이 손으로 재지정해야 했다. 자본 사다리(스펙
050, X.4)가 **얼마나(자본 규모)**를 증거 게이트로 위임했듯, 운영자는 **무엇을(어느 전략)**의
재지정도 증거 게이트로 위임했다(2026-06-16). 단, 손실면은 절대 키우지 않는다.

## 무엇 (요구)

- **FR-1 (5중 게이트)**: 도전자를 라이브로 재지정하려면 다섯 관문을 *전부* 통과해야 한다.
  하나라도 불충족이면 incumbent 유지(HOLD/WAIT — 보수적 fail-safe).
  ① 엣지 확정(도전자 forward EDGE_CONFIRMED) ② 다중검정 보정(6트랙 동시검정의 운 좋은
  우승 배제, 본페로니) ③ 사과 대 사과(도전자가 incumbent 를 *둘 다 비교 가능* 상태에서 앞섬)
  ④ 하드닝 캐너리 PASS(과거 리플레이+충격+퍼즈, 스펙 007) ⑤ 재지정 후 자본 사다리 rung 0
  리셋(새 전략을 25%부터 자율 재검증).
- **FR-2 (결정 — 순수)**: `portfolio/auto_reassign.decide_reassignment` — 리더보드 +
  캐너리 판정 → REASSIGN/WAIT_CANARY/HOLD/DISABLED. 주문 0·네트워크 0·결정만.
- **FR-3 (실행 — 순수)**: `portfolio/reassign_exec.build_reassignment` — REASSIGN 시 챔피언
  트랙의 전략 블록(`[portfolio]` 이후)을 라이브 설정(`deploy/canary-live-portfolio.toml`)에
  *텍스트로 그대로 이식*(값 변환 위험 0), 운영/거래집합(`[caps]`·`[whitelist]`)은 라이브
  원본 보존, 자본 사다리 rung 0(무장 해제) 센티넬 산출.
- **FR-4 (④ 게이트 — 포트폴리오 캐너리)**: `canary/portfolio_harness.run_portfolio_canary` —
  검증된 포트폴리오 백테스트 엔진으로 챔피언을 최근 윈도우(낙폭+데이터 결손) + 실제 과거
  급락 윈도우(K1 게이트 거부 합산) + K1 퍼즈로 돌려 스펙 007 의 같은 5지표(`evaluate_metrics`)
  로 PASS/FAIL. 밴드는 재지정 전용(`config/canary_bands_reassign.toml`, 낙폭 임계 = 사다리
  강등선 10%). 위반=0·무결성=0 고정(로더 강제).
- **FR-5 (거래 집합 무확대 — 헌법 II)**: 챔피언 유니버스가 라이브 화이트리스트의 부분집합이
  아니면 재지정 거부(`ReassignExecError`). global(역변동성)↔globalfixed(등가중)는 SPY·IEF·GLD
  안이라 허용, wide(11슬리브, QQQ 등)는 거래집합 밖이라 자율 재지정 거부(운영자 게이트).
- **FR-6 (실행 채널)**: 결정/실행은 테스트된 순수 모듈, 집행은 워크플로
  `reassign-on-tournament.yml`(리더보드 → 캐너리 → reassign-decide → 변경 시 센티넬 PR +
  best-effort 자동 머지), 실주문은 `rebalance-live-canary.yml` 시장시간 스케줄에서만.
- **FR-7 (인스턴스 데이터 가동)**: 캐너리는 `SqliteBarDataSource` 로 라이브/페이퍼 워커가
  채운 `price_bars`(토너먼트·라이브와 같은 바)를 읽는다 — 별도 CSV ingest 없이 폐회로가
  인스턴스 데이터로 실제로 닫힌다. 데이터 없으면 coverage 종료 → verdict 없음 → 재지정 0.

## 손실면 불변 (헌법 X.5: WHICH not HOW MUCH)

재지정은 **어느 전략을 라이브로 쓰는가**만 바꾼다. **얼마나(자본 규모)**는 여전히 자본
사다리(X.4) + 운영자 소유 낙폭 예산(20%) + 즉시 정지가 가른다. 재지정 직후 rung 0(무장 해제)
이라 실주문 0건 — 실제 자본은 새 전략이 forward 재검증(스펙 050)을 *다시* 통과해야 25%·50%·
100% 로 들어간다. 따라서 손실면은 v5.0.0과 동일(캐너리는 사전 선별, 실제 돈 게이트는 하류 사다리
— 심층 방어). 비위임 불변(I 캡·II 화이트리스트·IV 감사·VI 단계 승격·VIII.A 장중 배포 금지·
스펙 014 서킷 브레이커·킬스위치 `automation/AUTOARM_DISABLED`)은 그대로다.

## 폐회로 데이터 흐름

```
rebalance-paper-forward.yml (6트랙 A/B 토너먼트, 매 거래일 22:30 UTC)
  → forward_tournament_probe (정직성 게이트 순위 → challenger_key/incumbent_key/multiplicity)
  → [reassign-on-tournament.yml, 평일 00:20 UTC]
       reassign-challenger-path (challenger_key → deploy/*.toml, 단일 출처)
       → canary-portfolio --bars-db (④ 하드닝 캐너리, 전용 DB·halt 격리) → PASS/FAIL
       → reassign-decide --write-config (decide_reassignment 5중 게이트)
            → REASSIGN 이면 build_reassignment: 새 라이브 설정 + rung 0 센티넬
       → git diff 있으면 재지정 PR (+best-effort 자동 머지)
  → rebalance-live-canary.yml (시장시간 스케줄, 자본 사다리 게이트 통과분만 실주문)
사이드카: automation/reassign-last-run:LAST_RUN.md (매 실행 발행)
```

## 트랙 key → deploy 설정 (단일 출처)

`portfolio/reassign_exec.TRACK_DEPLOY_CONFIGS` 가 `rebalance-paper-forward.yml` 각 ARM 의
`cfg=` 와 일치한다(trend/notrend/rmbeta/multiasset/global/globalfixed/wide). incumbent="global"
→ `deploy/global-trend-portfolio.toml`. 라이브 설정 = `deploy/canary-live-portfolio.toml`.

## 구성요소 (전부 테스트됨)

| 역할 | 모듈 / 산출물 | 테스트 |
|------|---------------|--------|
| ①②③ 결정 두뇌 | `portfolio/auto_reassign.py` | `test_auto_reassign.py` (9) |
| 실행(설정 교체+rung0) | `portfolio/reassign_exec.py` | `test_reassign_exec.py` (14) |
| ④ 포트폴리오 캐너리 | `canary/portfolio_harness.py` | `test_portfolio_canary.py` (8) |
| 인스턴스 바 어댑터 | `backtest/data_source.SqliteBarDataSource` | `test_sqlite_bar_data_source.py` (3) |
| 재지정 밴드 | `config/canary_bands_reassign.toml` | (로더 검증) |
| CLI 글루 | `reassign-decide` · `canary-portfolio` · `reassign-challenger-path` | `test_reassign_decide_cli.py` (9) · `test_canary_portfolio_cli.py` (4) |
| 워크플로 배선 | `.github/workflows/reassign-on-tournament.yml` | (YAML 구조 검증) |

## 운영 (운영자/세션)

- **상태 확인**: `git show origin/automation/reassign-last-run:LAST_RUN.md` (결정·캐너리·리더보드 JSON).
- **즉시 정지**: `automation/AUTOARM_DISABLED` 를 main 에 두면 자율 재지정 DISABLED no-op.
- **수동 실행**: `reassign-on-tournament.yml` workflow_dispatch.
- **밴드 조정**: `config/canary_bands_reassign.toml` 편집 + PR(위반=0·무결성=0 고정은 로더가 강제).

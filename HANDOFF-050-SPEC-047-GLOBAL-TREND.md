# HANDOFF 050 — 스펙 047: 글로벌 분산 추세추종(+금) + 배포 polkit 진단 (2026-06-07)

main 베이스라인: `5b36bc2`(PR #219). 운영자 지시: "세계 최고 수준이 되기 위한 작업 분석·우선순위
판단 뒤 자율 수행 — 실제로 많은 돈을 벌어야." 이번 세션은 두 갈래로 진행됐다: ① 검증된 전략을
세계 최고 수준 차원으로 확장(스펙 047 = 금 추가 3자산 GTAA), ② 그 과정에서 *끊긴 배포의 새 원인*
(polkit)을 진단.

## ① 스펙 047 — 글로벌 분산 추세추종 (주식+채권+금, 역변동성) ✅ 머지 완료

main 머지 `a53a63f`(PR #217). 상세: `specs/047-global-trend/{spec,FINDINGS}.md`.

- **우선순위 판단**: "많은 돈" = (고샤프 전략) × (자본·레버리지) × (복리). 자본·레버리지·라이브는
  운영자 게이트(헌법 X.4), forward 누적은 시간 문제 → 자율로 당길 수 있는 유일한 레버 = **샤프를
  올리는 것**(스펙 044: 샤프↑ = 복리 천장↑). 샤프를 올리는 공짜 점심 = 비상관 추세 흐름 추가.
  스펙 043은 주식+채권 2자산까지였고, 일일 모니터가 지금 `DIVERSIFICATION_WEAKENED`(주식·채권
  상관 양수 전환)를 경고 중 → **금이 바로 그 약점(인플레 regime)의 구조적 헤지**.
- **실측(Shiller 1871~ + 런던 금 1833~, 둘 다 GitHub)**: 금은 변동성 큰 자산(≈15%)이라 균등가중
  (1/3씩)은 위험 과배분으로 일부 구간 낙폭 악화(NO_GOLD_BENEFIT). **위험으로 사이징하면**(고정
  14% 또는 역변동성) 분산 이득만 취한다 — 고정 위험가중은 4/4 구간 샤프·칼마·낙폭 모두 개선,
  역변동성은 **모든 구간 낙폭 ~5%로 박살** + 칼마 대폭↑(전체 0.45→1.10, 1971~ 1.49→1.77).
  금↔주식 −0.07~+0.01, 금↔채권 +0.03~+0.17(최근 인플레 신호).
- **배선(ARM E)**: `deploy/global-trend-portfolio.toml`(SPY+IEF+GLD, `weight_scheme=inverse_vol`,
  sma 200) + `rebalance-paper-forward.yml` ARM E(전용 DB `forward_global.db`, graceful degrade).
  weight_scheme=inverse_vol는 스펙 017/020/024에서 검증된 기존 리밸런서 경로(신규 아님).
- **안전**: Kernel 터치 0건, 돈 0 이동, PAPER 전용. 신규 모듈 `analytics/global_trend.py` +
  probe + 단위 14건. 전체 1613 통과, 린트 깨끗.

## ② 배포 polkit 진단 — 끊긴 배포의 *새* 원인 (부분 완화, 서버측 미해결)

main 머지 `340f482`(PR #218) + `5b36bc2`(PR #219).

- **증상**: deploy-on-merge가 `phase=stop_worker`에서 실패·롤백.
  `deploy failed at phase=stop_worker: Failed to stop auto-invest.service: Interactive authentication required.`
- **진단**: `auto-invest-deploy.service`는 최소권한으로 `User=auto-invest` + `NoNewPrivileges=true`.
  상태기계 `supervisor.stop_worker()`가 `systemctl stop auto-invest.service` 호출 → polkit이 비대화식
  인증 막음. sudo는 NoNewPrivileges 때문에 못 씀(setuid 불가) → polkit 인가가 정답.
- **완화(머지함)**: polkit 규칙(`deploy/50-auto-invest.rules`, 좁은 범위)을 cloud-init에서 빼내
  단일 소스화 + `sync-units.sh`가 매 배포(sudo)마다 설치 + polkit reload/restart + 워크플로에서
  유닛/polkit 동기화를 배포 *앞*으로 이동. **그러나 규칙 설치+polkit restart 후에도 stop_worker가
  계속 같은 오류로 거부** — 규칙이 로드돼도 이 호출을 인가하지 못한다. 더 깊은 서버측 polkit 문제
  (버전/세션/평가)로 보이며, **이 컨테이너에서 SSH 진단 불가**.
- **★ 결정적: 이 배포 실패는 forward 검증(ARM A~E)을 막지 않는다.** 배포 상태기계는 `pull`(깃
  체크아웃 갱신, 4단계)을 `stop_worker`(14단계) *이전*에 하고, stop_worker 실패는 `rollback=False`
  라 **체크아웃은 최신 main에 그대로 남는다**(증거: stop_worker 실패 직후 서버가 "HEAD == a53a63f"
  보고; 이후 배포는 "no changes" no-op). forward 페이퍼는 워커 프로세스가 아니라 *체크아웃*에서
  CLI를 돌리므로 `deploy/global-trend-portfolio.toml`이 서버에 있고 **ARM E는 다음 cron(평일 22:30
  UTC)에 정상 동작**. 배포 실패의 유일한 피해 = 장기 dry-run 워커 프로세스가 묵음(라이브 캐너리
  무장 해제 상태라 현재 유휴, 중요 작업 없음).
- **운영자 결정 필요(라이브 전 단계)**: 실제 라이브 거래 전엔 워커 프로세스 배포가 성공해야 한다.
  두 길 — (a) 서버 SSH로 polkit 진단(`pkaction --action-id org.freedesktop.systemd1.manage-units
  --verbose`, polkit 버전, `journalctl -u polkit`), 또는 (b) `auto-invest-deploy.service`를
  `User=root`로(또는 NoNewPrivileges 해제 + sudoers)로 전환 = polkit 우회(보안 자세 변경이라 운영자
  승인 필요). 세션은 (b)를 자율로 하지 않았다(안전 경계 판단).

## 한눈 요약 (2026-06-07 기준)

| 항목 | 값 |
|------|-----|
| 마지막 main 커밋 | `5b36bc2` (PR #219) |
| 테스트 | 1613 통과·4 스킵 |
| 린트 | `ruff check src tests` 깨끗 |
| 열린 PR | 없음 |
| 출시 스펙(이번) | 047(글로벌 추세 +금) |
| forward ARM | A(추세ON)·B(추세OFF)·C(위험관리베타 SPY·QQQ)·D(멀티에셋 SPY·IEF)·**E(글로벌 SPY·IEF·GLD)** |
| 서버 체크아웃 | 최신 main 추종(배포 pull이 전진시킴) — forward 검증 정상 |
| 미해결 | 배포 워커-프로세스 restart(polkit stop_worker) — 서버측, forward 무영향 |

## 다음 (운영자 결정 / 후속 자율)

1. **ARM D(2자산) vs ARM E(3자산) 사이드카 비교** — 금이 *우리 KIS 체결* forward로도 분산을
   더하는가(≈20 거래일 누적까지 INSUFFICIENT_DATA 정상). 확인:
   `git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md`.
2. **배포 워커-프로세스 polkit** — 위 (a)/(b) 중 운영자 선택. 라이브 거래의 전제.
3. **"많은 돈"의 정직한 경로** — 역변동성 3자산의 낮은 낙폭(~5%)은 낙폭 예산 레버리지(스펙 044)를
   키울 여지를 준다. 단 레버리지·자본·라이브는 운영자 게이트(헌법 X.4).
4. **후속 자율 후보** — 원자재·통화 장기 시계열을 GitHub에서 확보하면 4~5자산 GTAA로 확장(진짜
   managed futures 다발). 데이터 가용성부터 조사.

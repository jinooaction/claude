# 검증·운영 순서

1. uv run pytest tests/unit/test_capital_ladder.py tests/unit/test_fundability.py
2. uv run pytest 및 uv run ruff check src tests.
3. uv run python scripts/agent_harness_probe.py --strict 및 scripts/check_handoff_facts.py.
4. PR 품질 관문·merge·배포 후 정확한 main을 확인한다.
5. 기존 forward-edge-autoarm의 현재 NAV·예산·fundability·RESIZE·sentinel PR·merge를 확인한다.
6. 새 main 배포·KIS smoke·no-order preflight ENTRY_READY/CLEAR/OK/VALID/주문0을 확인한다.
7. 다음 XNYS 자동 실행의 접수·체결·감사·대사 전에는 전체 목표를 닫지 않는다.

수동 실주문이나 소비된 거래일 재시도 권한을 추가하지 않는다.

## 생산 기록 (2026-09-05 KST)

- FR-010은 PR765 merge7acd7093583d2b393257102484c549b03c33b032로 출시됐다.
  head7ba9f21 전체3414/7(727.92초),ruff,harness14/14,HANDOFF,PR 관문 통과.
  deploy33938162479·audit33938198034의7d3e5a546bdbacfc6bb393e8c07e3764에서02:07UTC
  DEPLOY_COMPLETED, KIS33938189596 6/6. autoarm33938200698은현재main 확인과 운영증거
  통과 후 STAY/rung1→1/센티넬변경false/새PR없음이다. no-order33938199313은exact7acd7093,
  capital143,첫진입success,manual-no-order-preflight,CLEAR/OK/VALID/haltfalse/orders0이다.
  T016 완료. 실제자동 접수·체결T009는 미완료이며 다음 유효거래일Sep8을 추적한다.

- 최신: autoarm33935656168은 전체3405/7(1397.10초),ruff,하네스14/14,HANDOFF,본문 관문을
  통과해 PR763으로142→143/rung1/run_seq9를 승인했다. main fdb9149a1790fc57ed1f33739a4d2380cefb1507.
  deploy33937154453·감사33937198586(4c6227d2241200efa30f3170f8df9a5d)은01:46UTC
  DEPLOY_COMPLETED를 확인했고 KIS33937196360은6/6이다. 배포 전33936963890은 옛 서버
  sentinel142 때문에 실패했으나 배포 후33937207081은143 첫진입 success, CLEAR/OK/VALID,
  haltfalse, orders0이다. T008/T011/T013은 완료, 실제체결T009는 미완료다.
- 지연 schedule33936156498이 이전87c0095 이벤트와 새fdb9149a 증거를 섞어 만든 강등PR764는
  충돌·미병합이었다. 최신 동일코드 검증 통과와 code_commit 단일 실패 근거를 남기고 닫았다.
  FR-010의 상태 무변경 종료 보정을 검증 중이다. 아래는 이전 생산 기록이다.

- PR757 merge854d81f947e1c0c579996026f15171f6b9dfeaad. 기능 head3443bd0에서 최종 전체3400 passed/7 skipped,
  ruff·엄격 하네스14/14·HANDOFF·PR 품질 관문 통과.
- deploy33928671285 성공. audit33928739275의79b06199af242253aa8e1a96791246a6에서
  DEPLOY_STARTED→DEPLOY_COMPLETED, 실제854d81f9 반영 확인.
- KIS33928671315 6/6, cash934.27/NAV1434.91/ORANY28/open_unfilled0. setup33928740976은
  deploy_timer/live_canary_timer/worker active.
- T008의 승인 예산 갱신 및 최신 no-order 검증, T009의 실제 자동 체결은 아직 미완료다.
- PR759 merge aa6aa482534d2f192b197de04af2bb9008383b2e는 자동 승인 checkout의 전체 이력을
  선언했다. 실제Git shallow/전체이력 회귀 포함 전체3402 passed/7 skipped, ruff·하네스14/14·
  HANDOFF·PR 관문 통과. 중단된 autoarm33929694159의 판단은 RESIZE142→143이었으나
  승인PR은 생성되지 않았으므로 T008/T011 재실행이 필요하다.
- exact aa6aa482 deploy33931335050 성공. audit33931382855의
  10fc4c29934c0707520b7a89add952f2는 DEPLOY_COMPLETED를 확인했다.
  KIS33931381162는6/6, cash934.27/NAV1434.91/open_unfilled0이다.
- PR761 merge21f63d64160ed36e70a58cb28c65ebd0f665fe09는 승인 시험의 호스트 의존성과
  생성 PR 증거 형식을 보정했다. head a17fabc에서 master 기본값·GitHub 색상 환경으로 전체
  3405 passed/7 skipped(729.17초),ruff,하네스14/14,HANDOFF,PR 관문 통과.
- exact deploy33934694258 성공. audit33934744194의 상관값
  3dc3cb3b85d6409722f32556290e5ba4에서00:59UTC DEPLOY_COMPLETED 확인.
  KIS33934742508은6/6,cash934.27/NAV1434.91/ORANY28/open_unfilled0이다.
- autoarm33932341774는 승인PR 전 전체시험에서5실패로 종료됐으므로 승인액은142다.
  새 인계 main에서 T008/T011/T013 자동 승인 재실행이 필요하며 실제체결T009도 미완료다.

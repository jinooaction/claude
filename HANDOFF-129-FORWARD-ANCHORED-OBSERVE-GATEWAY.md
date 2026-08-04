# HANDOFF-129 — Forward Anchored Observe Gateway Repair

## 상태

완료. #576이 main에 merge됐고, post-merge `Forward anchored verdict` workflow가 새 코드로 자동 실행되어 sidecar를 정상 발행했다.

운영자 질문에 대한 결론은 이렇다. 엣지 신뢰도(PSR)를 높이면 자본 사다리의 첫 배치 문제는 풀릴 수 있다. 하지만 기준을 낮추거나 같은 숫자를 보기 좋게 다시 포장하는 방식은 안전한 해결이 아니다. 새 forward 관측과 검증된 후보가 실제로 기준 `0.95`를 넘어야 한다.

## 왜 했나

최신 forward paper를 수동으로 돌리자 엣지 신뢰도는 실제로 좋아졌다. 가장 가까운 후보인 `globalfixed`는 PSR `0.947063`까지 접근했지만, 기준 `0.95`에는 닿지 못했다. 최신 최종 sidecar에서는 `globalfixed`가 `0.945953 < 0.95`, 라이브 검증 지문 `global`이 `0.773542 < 0.95`다.

동시에 별도 앵커드 판정 워크플로가 실질적으로 깨져 있었다. `Forward anchored verdict` run `30960153902`는 GitHub job은 success로 보였지만, sidecar 안에는 `refused command`와 `ssh_exit=126`이 남았다. 원인은 workflow가 production SSH forced-command 경계에 raw `cd /opt/auto-invest && /usr/local/bin/uv run ...` 명령을 직접 보냈기 때문이다.

## 무엇을 고쳤나

- `.github/workflows/forward-anchored-verdict.yml`의 GLOBAL-TREND 앵커드 판정 단계를 고정 관측 명령 `observe ladder-anchored-verdict`로 교체했다.
- raw 원격 shell, 직접 `/usr/local/bin/uv run auto-invest ...`, 원격 `cd /opt/auto-invest` 경로를 제거했다.
- `tests/unit/test_observation_gateway_workflows.py`에 forward anchored workflow 회귀 테스트를 추가했다.
- 기존 forced-command 안전 경계를 우회하지 않고, `forward-edge-autoarm`에서 이미 쓰던 같은 observe gateway 명령을 재사용했다.

## 확인한 증거

- PR #576 merge commit: `9bbe288deddbc9e8e8554b7e3f98dd59535773d5`.
- 기능 커밋: `1631ac3`.
- 실패 재현 증거: `Forward anchored verdict` run `30960153902`, sidecar `GLOBAL-TREND ssh_exit=126`, `refused command`.
- post-merge 자동 실행: `Forward anchored verdict` run `30960522122` success.
- 최신 `forward-anchored-verdict` sidecar: commit `9bbe288`, timestamp `2026-08-04T23:36:16Z`, `GLOBAL-TREND ssh_exit=0`.
- 최신 앵커드 JSON 판정: `verdict=INSUFFICIENT_DATA`, `forward_n_obs=36`, walk-forward 요약은 강건한 엣지 없음.
- 최신 `rebalance-paper-forward` sidecar: timestamp `2026-08-04T23:36:11Z`, 7개 트랙 모두 `NO_EDGE`, `globalfixed` PSR `0.945953 < 0.95`, `global` PSR `0.773542 < 0.95`.
- 로컬 검증: focused observation gateway tests 22 passed, `git diff --check`, `uv run pytest` 2714 passed/5 skipped, `uv run ruff check src tests` 통과, `agent_harness_probe.py --strict` OK(14/14), `check_handoff_facts.py` OK, PR quality gate 통과.

## 안전 경계

이번 변경은 등급 2 운영 workflow 보정이다.

실제 주문, 실거래 전환, live 재무장, 자본 배분, live 전략 설정, whitelist/caps, 손실 예산, KIS secret, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.

`forward-edge-autoarm`는 엣지가 합격하면 자본 사다리 PR을 만들 수 있으므로 이번 승인 범위에서 수동 실행하지 않았다. 이번 세션에서 실행한 것은 forward paper 검증과 read-only 앵커드 관측뿐이다.

## 다음 세션 판단

PSR 부족이 직접 blocker라는 판단은 유지한다. 이번 세션은 PSR을 조작하지 않고, 최신 forward 관측을 쌓았고, 앵커드 엣지 증거 sidecar가 실제로 측정되도록 운영 경로를 복구했다.

다음 실제 관찰 지점은 다음 scheduled sidecar 갱신 뒤 `rebalance-paper-forward`, `forward-anchored-verdict`, `money-path`, `autonomous-work`를 함께 읽는 것이다. `globalfixed`가 계속 `0.95`에 근접하더라도, 라이브 전략 지문 변경이나 자본 사다리 승격은 운영자 승인과 기존 안전 게이트 없이 실행하지 않는다.

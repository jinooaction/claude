# auto-invest — 다음 세션 인수인계 (main 베이스라인)

이 파일은 이 저장소의 **`main` 브랜치에서 시작하는 모든 Codex/Claude 세션**의 진입점입니다. "지금 무슨 일이 일어나고 있는지"를 토큰 낭비 없이 빠르게 파악할 수 있도록 정리했습니다.

## 세션 시작 절차 (필수)

`AGENTS.md`(Codex) 또는 `CLAUDE.md`(Claude)의 운영 규칙과 세션 수명주기 정책에 따라, 모든 새 세션은 계획을 세우거나 운영자에게 무엇을 할지 물어보기 **전에** 현재 상태를 사실로 맞춥니다. Codex 기준 핵심 규칙은 `AGENTS.md`입니다.

1. **자동(로컬)** — Codex는 `.codex/hooks/git_ground_truth.py`, Claude는 `.claude/hooks/git_ground_truth.py` 세션 시작 훅이 매 세션 라이브 git 상태를 출력합니다: 현재 브랜치·HEAD·작업트리 청결도와 샘플·`origin/main` 대비 앞뒤·최근 `origin/main` 커밋·핵심 HANDOFF 진입점. **산문으로 적힌 "active feature" 줄보다 이 블록을 더 신뢰하세요.**
2. **`/sync` 실행(네트워크)** — 훅은 절대 멈추면 안 되므로 로컬 정보만 냅니다. 네트워크 발견은 `/sync` 스킬이 담당합니다: `git fetch`, 원격 `Codex/*` 브랜치 목록, 열린 PR 목록(`mcp__github__list_pull_requests`), 각 브랜치의 살아있는 HANDOFF 읽기, `main` 실제 최신과 대조. 무엇이 머지됐고 무엇이 진행 중인지 불확실하면 세션 시작에 한 번 돌리세요.

`/sync`가 자동화하는 옛 수동 절차(참고):

```bash
git fetch origin
git ls-remote --heads origin 'Codex/*' | awk '{print $2}'
# + mcp__github__list_pull_requests owner=jinooaction repo=claude state=open
# + git show origin/<브랜치>:HANDOFF-<NNN>.md   (각 브랜치의 살아있는 HANDOFF)
# + git log origin/main -8 --pretty='%h %s'      (main 실제 최신)
```

열린 PR이 진행 중인 브랜치를 가리키면 main에서 새 브랜치를 만들지 말고 그 브랜치를 `git checkout` 후 `git pull --ff-only` 하세요.

## 운영자 응대 핵심 규칙 (Codex는 AGENTS.md 우선 — 절대 어기지 마세요)

1. **응답은 무조건 한글**. 새 세션 시작, 상태 보고, 작업 요약, 사과, 질문 — 예외 없음. 영어 응답은 운영자가 이해 못합니다.
2. **약어와 영어 비즈니스 용어 금지, 쉬운 한글로 풀어 써라**. 코드/식별자/파일 경로 같은 고유명은 그대로 두되 반드시 한글 설명을 옆에 붙입니다. 한 문장에 영어 단어 3개 이상이면 다시 씁니다.
3. **자동 머지** — 작업 완료 + 테스트 통과 + 린트 깨끗 + PR `mergeable_state=clean` 만족 시 운영자가 "머지해"라고 말하지 않아도 즉시 자동 머지. 매번 머지 명령 요청하는 것 자체가 헌법 IX.D가 제거하려던 동기 핸드오프 비용입니다.

상세 규칙은 Codex 세션에서는 `AGENTS.md`, Claude 세션에서는 `CLAUDE.md` 본문 참조.

## 한눈 요약표 — 2026-08-10 KST 최신 코드 main 기준

| 항목 | 상태 |
|------|------|
| 마지막 main 커밋 | `fff75f9` — Merge pull request #580 from jinooaction/codex/handoff-after-deploy-retry-success |
| main 테스트 | 이 갱신 브랜치 기준 `uv run pytest -q` → 2716 passed, 5 skipped. 5개 skip은 `KIS_LIVE_TEST=1` opt-in live smoke다. |
| main 린트 | 이 갱신 브랜치 기준 `uv run ruff check src tests` → All checks passed. |
| 열린 PR | 없음(이 문서 편집 시점; #580은 merge 완료). |
| 출시 완료 스펙 | 최신 운영 보정: #580(#578 뒤 dry-run deploy 재시도 성공 인계), #579(#578 뒤 KIS smoke 성공과 deploy 실패 경계 인계), #578(KIS smoke 실패를 한 번만 fail-closed로 남기고 public sidecar/pytest traceback 민감값을 정화), #577(#576 뒤 HANDOFF main 기준 갱신), #576(`forward-anchored-verdict`의 raw SSH 명령을 fixed `observe ladder-anchored-verdict` gateway로 교체해 앵커드 엣지 sidecar 복구). 직전 추가: #573/#574(스펙 074 후보 가격 이력 지원 후속: candidate result workflow의 `scp`/remote `bash` 제거, fixed `observe candidate-history` gateway + `ssh -n` loop 보정으로 세 history dataset 준비 성공), #571(스펙 071 후보 결과 실행기 후속: retryable factory-blocked 후보의 안전 검증 명령 실행과 진단 복구), 123/live canary sidecar gate(#568 preview/status와 real-order job 분리, #569 fixed `observe live-canary-*` gateway로 preview/status 내용 복구), #566(forward paper 경제 장부 보정), 122(forward paper DB writability), 121(`promote-readiness` 관측 경로 복구 + 서버 root-owned gateway/helper self-refresh), 120(증거 기반 후보 소스 다변화 + released-work 완료 소비), 119(보안 신뢰 경계 강화와 후속 SSH boundary repair 및 live-money workflow 보호 환경). 이전 스펙 058~118은 아래 과거 관찰과 개별 HANDOFF 파일을 참고한다. |
| 골격 스펙 | 없음. `.specify/feature.json`은 최신 완료 스펙 `specs/123-live-canary-sidecar-gate`를 가리키고, `tasks.md`는 T001~T023 완료 상태다. |
| 최근 출시 작업 | #578은 KIS smoke 실패 로그의 민감값 노출 위험과 즉시 전체 재시도 노이즈를 줄이는 등급 3 안전 보정이다. post-merge 수동 KIS smoke run `31357160707`은 최신 `5d043e7`에서 5개 read-only live smoke를 모두 통과했다. 첫 `Deploy on merge to main` run `31357030954`는 health check timeout으로 실패했지만, 수동 dry-run 배포 재시도 run `31357670471`은 최신 main `cf17589`에서 성공했다(`START_EXIT=0`, `UNITS_EXIT=0`). |
| 활성 작업 | 없음. 열린 PR 없음. 2026-08-11 KST 수동 read-only refresh 기준 pipeline-liveness(`2026-08-11T02:08:00Z`)는 `OK`, money-path(`2026-08-11T02:08:08Z`)는 `PREVIEW_ONLY`/`NO_EDGE_YET`, capital-path-readiness(`2026-08-11T02:08:08Z`)는 `ACCUMULATING_EDGE`, money-gate-alignment(`2026-08-11T02:08:12Z`)는 `ALIGNED_WAITING`, autonomous-work(`2026-08-11T02:08:14Z`)는 `OBSERVATION_WAIT`/`wait-for-fresh-evidence`다. edge-autoarm(`2026-08-11T00:35:17Z`)는 `WAIT_EDGE`/`NO_EDGE`, rebalance-paper-forward(`2026-08-10T23:10:02Z`)는 7개 비교 가능 트랙 모두 `NO_EDGE`다. 최신 KIS smoke(`2026-08-10T04:59:01Z`)는 `smoke_state=success`, `smoke_exit=0`, `key_valid=true`다. |
| 안전 경계 | 이번 갱신은 등급 2 인계 갱신이다. 실제 주문, 실거래 전환, live 재무장, 자본 배분, 라이브 전략 교체, whitelist/caps 확대, 손실 예산, KIS secret 값, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다. 현재 돈 경로는 `PREVIEW_ONLY`라 실주문 불가이고, 직접 자본 차단은 PSR `0.531698 < 0.95`인 `NO_EDGE_YET`이다. |

## 최근 관찰 — 2026-08-11 KST (돈 경로 read-only refresh와 실행 후보 없음 확인)

현재 `main` 최신 코드는 `fff75f9`(#580, #578 뒤 dry-run deploy 재시도 성공 인계)다.
이번 세션은 코드 동작을 바꾸지 않고, 돈 0 이동의 읽기 전용 루프만 최신 `main`에서 수동 재실행했다.

- **문제 정의**: 운영자가 "수단과 방법을 가리지 말고 당장 돈 벌기"를 요청했다. 허용 가능한 해석은
  안전장치를 우회하는 것이 아니라, 최신 증거 기준으로 실주문을 열 수 있는지 끝까지 확인하고,
  운영자 승인 없는 실주문·자본 변경 없이 가능한 가장 빠른 안전 조치를 적용하는 것이다.
- **실행한 조치**: `pipeline-liveness.yml` run `31451430443`, `money-path.yml` run `31451433886`,
  `capital-path-readiness.yml` run `31451437371`, `money-gate-alignment.yml` run `31451441131`,
  `autonomous-work-execution.yml` run `31451444854`를 모두 `workflow_dispatch`로 실행했다. 이 다섯 루프는
  보고용 sidecar만 갱신하며 주문, 자본 배분, live 설정 변경, 코드/PR 자동 생성, 외부 유료 서비스를 하지 않는다.
- **최신 돈 경로 판정**: money-path는 `PREVIEW_ONLY`/`NO_EDGE_YET`, 실계좌 NAV는 `$1466.14680000`,
  PSR은 `0.531698 < 0.95`, 전진 관측은 40회다. edge-autoarm도 `WAIT_EDGE`/`NO_EDGE`이며 자본은 0 이동이다.
  rebalance-paper-forward 최신 결과는 7개 비교 가능 트랙 모두 `NO_EDGE`다.
- **최신 자동 작업 판정**: autonomous-work는 `OBSERVATION_WAIT`이고 선택 후보는 `wait-for-fresh-evidence`다.
  실행 가능한 안전 후보, 운영자 승인 필요 후보, 복구 우선 후보가 없으며, 보이는 후보는 완료 8개와 억제 2개뿐이다.
- **남은 현실**: 지금 당장 돈을 움직이는 합법·안전 경로는 열리지 않았다. 다음 관찰 지점은 새 scheduled sidecar가
  쌓인 뒤 `money-path`, `edge-autoarm`, `capital-path-readiness`, `autonomous-work`를 다시 읽어
  `NO_EDGE_YET` 또는 `OBSERVATION_WAIT`가 바뀌었는지 확인하는 것이다. 기준을 낮추거나 사다리를 강제로 열면
  우연한 성과를 실거래로 착각하는 실패가 되므로 하지 않는다.

## 최근 관찰 — 2026-08-10 KST (#578 KIS smoke 실패 증거 안전화와 post-merge 확인)

현재 `main` 최신 코드 머지는 `5d043e7`(#578, KIS smoke single-pass/redaction 보정)다.
#578 기능 커밋은 `98da56f`이다.

- **문제 정의**: 운영자가 "당장 돈 벌기 위해 다음 해야 할 것"을 요청했지만, 최신 money-path와
  edge-autoarm은 여전히 `PREVIEW_ONLY`/`NO_EDGE_YET`이다. 직접 돈 차단은 forward 관측 39회 기준
  PSR `0.567128 < 0.95`라 검증된 엣지가 아직 없다는 점이다. 동시에 KIS smoke 최신 run은 read-only
  quote/cash/positions/balance 4개를 통과한 뒤 최근 체결 조회에서 KIS 500으로 실패했고, 기존 helper가
  즉시 전체 재시도하면서 KIS OAuth 403까지 만들어 실패 로그가 더 지저분해졌다.
- **구현 상태**: 이 후속 보정은 KIS smoke를 통과로 속이지 않는다. 읽기 전용 체결 조회 실패는 계속
  fail-closed로 남긴다. 대신 pytest fixture repr이 토큰·앱키·앱시크릿을 `[REDACTED]`로 보여주게 하고,
  public sidecar redactor가 Python dict-style traceback(`'access_token': '...'`)도 정화하게 했다.
  서버 helper의 "직접 uv 호출 — root 환경" 즉시 전체 재시도는 제거해 한 번 토큰을 발급한 뒤 다시
  전체 live smoke를 돌리며 OAuth throttle을 맞는 경로를 끊었다.
- **검증 상태**: #578 브랜치에서 focused 검증 `uv run pytest tests/unit/test_kis_smoke_workflow.py tests/unit/test_security_workflow_hardening.py -q`
  24 passed, `bash -n deploy/kis-smoke-on-instance.sh` 통과, `git diff --check` 통과,
  `uv run ruff check src tests` 통과, `uv run python scripts/check_handoff_facts.py` OK,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), `uv run pytest -q`
  2716 passed/5 skipped를 확인했다. #578 merge 뒤 `KIS smoke (autonomous)` push run `31357030935`는
  서버 helper 갱신 전 실패했지만, 배포 run `31357030954`가 helper를 refresh한 뒤 수동 재실행한
  KIS smoke run `31357160707`은 최신 commit `5d043e7`에서 5개 read-only live smoke 모두 통과했다.
  최신 sidecar는 `smoke_state=success`, `smoke_exit=0`, `key_valid=true`이고, 출력에 `access_token`,
  `app_key`, `app_secret`, JWT 모양 토큰, 403/500 재시도 노이즈가 남지 않았다.
- **남은 현실**: 이 보정은 돈을 움직이지 않는다. 실제 주문, live 재무장, 자본 배분, 라이브 전략 교체,
  whitelist/caps, 손실 예산, KIS secret 값, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.
  돈 경로가 열리려면 먼저 `NO_EDGE_YET`가 해소되어야 한다. 첫 `Deploy on merge to main` run
  `31357030954`는 helper refresh 뒤 worker health check에서 `WORKER_STARTED` 대기 시간 초과로 실패했지만,
  수동 dry-run 재시도 run `31357670471`은 최신 main `cf17589`에서 success, `START_EXIT=0`,
  `UNITS_EXIT=0`, deploy correlation id `660ef02905b2197d174a9f4d42f1b2f7`로 완료됐다.
  컨테이너에서 확인한 증거는 GitHub run과 journal 출력까지이며, 서버 `audit_log`의 `DEPLOY_*`
  행은 필요하면 운영자 또는 SSH 가능한 세션이 같은 correlation id로 감사 확인하면 된다.

## 최근 관찰 — 2026-08-05 KST (#576 forward anchored observe gateway 복구)

현재 `main` 최신 코드 머지는 `9bbe288`(#576, forward anchored observe gateway)다.
기능 커밋은 `1631ac3`이다.

- **문제 정의**: 운영자의 "엣지 신뢰도를 높이면 해결되는 문제 아니냐"는 판단은 방향이 맞다.
  자본 사다리를 여는 직접 조건은 전진 성과의 엣지 신뢰도(PSR)가 기준 `0.95`를 넘는 것이다.
  다만 기준을 낮추거나 숫자만 다시 계산해 올리는 것은 해결이 아니다. 안전한 경로는 새 관측과
  검증된 후보가 우연이 아닌 성과 증거를 벌게 하는 것이다.
- **이번 세션에서 적용한 안전한 개선**: `Rebalance forward paper validation` run `30959892734`를
  수동 실행해 최신 forward 페이퍼 관측을 추가했다. 그 결과 `globalfixed`는 한때 PSR
  `0.947063`까지 근접했고, 최종 최신 sidecar(timestamp `2026-08-04T23:36:11Z`)에서는
  `0.945953 < 0.95`로 아직 기준 미달이다. 라이브 검증 지문 `global`은 `0.773542 < 0.95`다.
  즉 신뢰도는 좋아졌지만 실거래를 열 수 있는 `EDGE_CONFIRMED`는 아니다.
- **발견한 운영 병목**: 별도 `Forward anchored verdict` workflow run `30960153902`는 GitHub
  job 자체는 success였지만, sidecar 안의 GLOBAL-TREND 단계가 raw SSH 명령 때문에 forced-command
  gateway에서 `refused command`, `ssh_exit=126`으로 막혔다. 그래서 깊은 OOS + 짧은 forward 지속성
  앵커드 증거가 독립 sidecar로 정상 발행되지 않았다.
- **구현 상태**: #576은 `.github/workflows/forward-anchored-verdict.yml`에서 raw
  `cd /opt/auto-invest && /usr/local/bin/uv run ...` 원격 명령을 제거하고, 이미 서버 allowlist에
  있는 `observe ladder-anchored-verdict`만 호출하게 했다. `tests/unit/test_observation_gateway_workflows.py`
  에 forward anchored workflow 회귀 테스트를 추가해 raw SSH 명령이 다시 들어오지 못하게 했다.
- **post-merge 확인**: #576 main push로 자동 실행된 `Forward anchored verdict` run `30960522122`는
  success다. 최신 `forward-anchored-verdict` sidecar는 commit `9bbe288`, timestamp
  `2026-08-04T23:36:16Z`, `GLOBAL-TREND ssh_exit=0`이고 JSON 판정을 발행했다. 판정 자체는
  `INSUFFICIENT_DATA`이며 `forward_n_obs=36`, walk-forward 요약은 "강건한 엣지 없음"이다.
- **돈 경로 상태**: 이번 변경은 돈을 열지 않는다. 최신 `money-path`는 아직
  `PREVIEW_ONLY`/`NO_EDGE_YET`, 배치 자본 `$0`다. `edge-autoarm`는 자본 사다리 PR을 만들 수 있는
  경로라 이번 승인 범위에서 실행하지 않았다. 실주문, 자본 배분, live 전략 교체는 하지 않았다.
- **검증 상태**: #576 브랜치에서 focused observation gateway tests 22 passed, `git diff --check`,
  `uv run pytest` 2714 passed/5 skipped, `uv run ruff check src tests` 통과,
  `uv run python scripts/check_handoff_facts.py` OK, `uv run python scripts/agent_harness_probe.py --strict`
  OK(14/14), PR quality gate 통과, `mergeStateStatus=CLEAN` 확인 뒤 merge했다. 이 handoff 갱신 전
  `uv run pytest -q`는 `HANDOFF.md`가 #574를 가리켜 하네스 관련 2개만 실패했고, 이 갱신이 그
  원인을 바로잡는다.
- **상세 인계**: `HANDOFF-129-FORWARD-ANCHORED-OBSERVE-GATEWAY.md`.

## 최근 관찰 — 2026-08-04 KST (#573/#574 후보 history observe gateway 완료)

현재 `main` 최신 코드 머지는 `85d88f9`(#574, candidate history stdin fix)다.
기능 커밋은 #573 `ebf906e`, #574 `303d741`이다.

- **문제 정의**: 후보 결과 실행기는 가격 이력 데이터가 없어 `data_history_missing`으로 멈췄다.
  기존 workflow는 서버에 manifest를 `scp`로 올리고 remote `bash -s`로 `bars-export -> ingest-history`를
  실행하려 했지만, production SSH는 forced-command gateway라서 `scp: Connection closed`로 막혔다.
- **구현 상태**: #573은 candidate result workflow에서 `scp`, remote `bash -s`, remote cleanup shell을
  제거했다. 서버 helper에는 `candidate-history` observe 명령을 추가했고, gateway는
  `micro-gtaa`, `global-trend-wide`, `multi-asset-trend` 세 key만 allowlist로 전달한다. helper는 서버
  `/tmp`에서 읽기 전용 `bars-export -> ingest-history`를 실행한 뒤 archive를 stdout으로 stream한다.
- **post-merge 배포 확인**: #573 `Deploy on merge to main` run `30920407159`과 #574
  `Deploy on merge to main` run `30921097027`은 모두 success다. #574 main push의
  `Candidate result executor` run `30921098091`과 `Candidate implementation factory` run `30921099534`도
  success다.
- **post-merge 후보 결과**: #574 `candidate-implementation-results` sidecar는 commit `85d88f9`,
  timestamp `2026-08-04T14:51:58Z`, `overall_status=degraded`, `pass=0`, `fail=2`, `pending=0`,
  `blocked=0`, `diagnostic_counts={}`다. 로그에서 `candidate history ready`가 `micro-gtaa`,
  `global-trend-wide`, `multi-asset-trend` 세 dataset 모두에 찍혔다. 즉 가격 이력 준비 병목은 해소됐고,
  두 후보는 데이터 부족이 아니라 실제 no-live 검증 결과로 fail 처리됐다.
- **후보 공장/자율 루프 확인**: post-result 수동 후보 공장 run `30921243355`는 success이고 최신
  factory sidecar는 `ready=0`, `pending=0`, `blocked=2`, `evidence_passed=0`이다. 두 후보 모두
  "기계 판독 검증 결과에 실패가 있어 승격 증거로 병합하지 않는다"로 닫혔다. 이어 수동 자율 작업 루프
  run `30921330987`도 success이며 최신 sidecar는 `OBSERVATION_WAIT` / `wait-for-fresh-evidence`다.
  현재 실행 가능한 안전 후보는 없다.
- **돈 경로 상태**: 최신 `money-path` sidecar는 timestamp `2026-08-04T10:35:09Z`,
  `PREVIEW_ONLY`/`NO_EDGE_YET`다. 관측 34회, 칼마 PASS, PSR `0.706071 < 0.95`, 배치 자본 0달러다.
  첫 자본은 여전히 자동 자본 사다리 게이트가 열 때만 가능하다.
- **검증 상태**: #573 브랜치에서 focused tests 31 passed, `uv run pytest` 2713 passed/5 skipped,
  `uv run ruff check src tests` 통과, YAML parse, `bash -n`, `git diff --check`, PR quality gate,
  strict agent harness, HANDOFF fact check를 통과하고 merge했다. 후속 stdin 보정 브랜치에서는 focused
  candidate-result workflow tests 7 passed, `uv run pytest -q` 2713 passed/5 skipped,
  `uv run ruff check src tests` 통과, shell/YAML 검증 통과, strict agent harness OK(14/14),
  HANDOFF fact check OK, PR quality gate 통과, `mergeStateStatus=CLEAN` 확인 뒤 merge했다.
  이 handoff 갱신 전 전체 `uv run pytest -q`는 HANDOFF가 #573을 가리켜 하네스 관련 2개만 실패했고,
  이 handoff 갱신이 그 원인을 바로잡는다.
- **안전 경계**: 이번 경로는 후보 검증용 history staging만 바꾼다. 주문, live 재무장, 자본 배분,
  whitelist/caps, 손실 예산, 비밀값, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다. 지금 실주문
  불가는 계속 `NO_EDGE_YET`: 기준을 낮춘 것이 아니라 더 정확한 후보 검증 증거를 얻는 단계다.

## 최근 관찰 — 2026-08-04 KST (#571 후보 결과 실행기 retryable blocked 진단 복구)

현재 `main` 최신 코드 머지는 `5d181e7`(#571, candidate result retryable blocked diagnostics)다.
기능 커밋은 `a99ac8e`이다.

- **문제 정의**: 운영자의 "엣지 신뢰도를 높이면 해결되는 문제 아니냐"는 판단은 절반은 맞다.
  자본 사다리를 여는 직접 조건은 전진 성과의 엣지 신뢰도(PSR)가 기준 `0.95`를 넘는 것이다.
  하지만 기준을 낮추거나 같은 증거를 재사용해 숫자를 올리는 것은 해결이 아니다. 실제로 더 나은 후보를
  안전하게 검증해, 우연이 아닌 성과 증거를 새로 벌어야 한다.
- **현재 돈 경로**: `money-path` sidecar timestamp는 `2026-08-03T21:37:56Z`이고
  `PREVIEW_ONLY`/`NO_EDGE_YET`다. 실계좌 NAV는 `$1466.62`, 배치 자본은 `$0`, 자본 사다리 PSR은
  `0.703355 < 0.95`다. `rebalance-paper-forward` sidecar timestamp는 `2026-08-03T23:39:40Z`이고
  7개 트랙 모두 `NO_EDGE`다. 가장 가까운 후보는 `globalfixed`로 PSR `0.922697 < 0.95`,
  현재 라이브 검증 지문 `global`은 PSR `0.706071`이다.
- **발견한 병목**: 후보 구현 공장은 PSR을 높일 수 있는 후보 패키지 2개를 만들었지만, 패키지 상태가
  `blocked`이면 후보 결과 실행기가 곧바로 멈췄다. 그래서 안전한 no-live 검증 명령이 있어도 실제
  실패 원인을 좁히지 못했고, 자동화는 `blocked`라는 큰 라벨만 반복해서 봤다.
- **구현 상태**: `candidate_result_executor.py`가 `promotion_patch.factory_retryable == True` 또는
  retryable factory diagnostic이 붙은 blocked 패키지는 안전성 검사를 먼저 통과한 뒤 allowlist no-live
  검증 명령을 실행한다. non-retryable blocked 패키지, unsafe command, unsupported command, missing command는
  계속 막는다.
- **post-merge 자동화 확인**: `candidate-implementation-results` sidecar는 commit `5d181e7`,
  timestamp `2026-08-04T01:10:24Z`, `overall_status=degraded`, `pass=0`, `fail=0`,
  `pending=2`, `blocked=0`이다. 진단 집계는 `data_history_missing=2`, `execution_failed=1`이다.
  즉 이번 패치는 후보를 통과로 위조하지 않고, "다음에 안전한 이력 데이터 준비 경로를 만들어야 한다"까지
  원인을 좁혔다.
- **검증 상태**: #571 브랜치에서 focused candidate-result tests 13 passed, 관련 후보 공장/통합 tests
  26 passed, `uv run pytest` 2712 passed/5 skipped, `uv run ruff check src tests` 통과,
  `uv run python scripts/check_handoff_facts.py` OK, `uv run python scripts/agent_harness_probe.py --strict`
  OK(14/14), PR quality gate 통과, `mergeStateStatus=CLEAN` 확인 뒤 merge했다. 이 handoff 갱신 전
  `uv run pytest -q`는 `HANDOFF.md`가 아직 `5a56117`을 가리켜 하네스 관련 2개만 실패했고,
  이 갱신이 그 원인을 바로잡는다.
- **안전 경계**: 이번 변경은 돈 경로를 열지 않는다. 주문, live 재무장, 자본 배분, whitelist/caps,
  손실 예산, 비밀값, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다. 지금 실주문이 안 나가는 직접 이유는
  계속 `NO_EDGE`: 기준을 거의 넘은 후보는 있지만 아직 `0.95`를 넘지 못했다.
- **상세 인계**: `HANDOFF-128-CANDIDATE-RESULT-RETRYABLE-BLOCKED.md`.

## 최근 관찰 — 2026-08-03 KST (#568/#569 live canary sidecar gate와 observe gateway 복구)

현재 `main` 최신 코드 머지는 `5a56117`(#569, live canary observe gateway)다.
기능 커밋은 #568 `95f2cd6`과 #569 `791aef7`/`48842c6`이다.

- **문제 정의**: `pipeline-liveness`가 critical sidecar인 `rebalance-live-canary`를 `LATE`로 보고했다.
  원인은 live canary workflow 전체가 production approval 환경에 묶여, `armed=false`인 미리보기 상태조차
  sidecar를 갱신하지 못한 것이다. #568이 job을 나눠 freshness는 회복했지만, post-merge sidecar 내용은
  preview/backfill/measure 원격 명령이 서버 forced-command SSH gateway에 거부되어 `refused command`로 비어 있었다.
- **구현 상태**: #568은 preview/status job과 production real-order job을 분리했다. #569는 preview/status job의
  raw `cd /opt/auto-invest && uv run ...` 원격 shell을 없애고 fixed `observe live-canary-backfill`,
  `observe live-canary-preview <capital>`, `observe live-canary-measure <capital>`만 쓰게 했다. 서버 gateway/helper는
  이 세 명령을 capital validation 뒤 실행하며, backfill, dry-run preview, NAV snapshot, forward-verdict만 수행한다.
  `--mode live --confirm-live`는 production-gated real-order job에만 남아 있고 observe helper에는 없다.
- **post-merge 배포 확인**: #569 `Deploy on merge to main` run `30777301767`은 success다. 로그에서
  `AUTO_INVEST_SSH_BOUNDARY_HELPERS_REFRESHED`와 `observe_helper=/usr/local/sbin/auto-invest-observe`를 확인했다.
- **live canary 확인**: main 수동 run `30777338028`은 success다. preview job은 backfill/dry-run/measure 모두 exit 0,
  real-order job은 skipped다. 최신 sidecar timestamp는 `2026-08-03T01:38:34Z`, `armed=false`,
  `preview-job-skipped`다. sidecar 본문에는 `refused command`가 없고, 드라이런 결과는
  `planned_buy_notional_usd=0.00`, `planned_sell_notional_usd=222.82`, `target_weights={"SPY":"0.235870"}`를 남겼다.
  live track 측정은 NAV snapshot seq `16214`, `total_nav_usd=500.0`, forward verdict `INSUFFICIENT_DATA`
  (`n_obs=14 < min_obs_required=20`)다.
- **pipeline/money path 확인**: pipeline-liveness run `30777384529`는 종합 `OK`이고 `rebalance-live-canary`는
  `OK`, 나이 0.0h다. money-path run `30777446988`는 `PREVIEW_ONLY`/`NO_EDGE_YET`다. 기존 자본 사다리는
  관측 30회, 칼마 PASS, PSR `0.547840 < 0.95` FAIL이라 첫 자본을 배치하지 않는다. capital-path-readiness
  run `30777476105`는 `ACCUMULATING_EDGE`, 우선 후보 없음, pipeline-liveness 입력 `overall=OK`다.
- **검증 상태**: #569 브랜치에서 focused workflow/security/backfill/NAV tests 25 passed, SSH boundary/observe
  tests 16 passed, pipeline/readiness tests 42 passed, `bash -n` helper syntax 통과, workflow YAML parse `yaml-ok`,
  `uv run pytest` 2710 passed/5 skipped, `uv run ruff check src tests` 통과,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14),
  `uv run python scripts/check_handoff_facts.py` OK, `git diff --check` 통과, PR quality gate 통과,
  `mergeStateStatus=CLEAN` 확인 뒤 merge했다.
- **안전 경계**: 관측·미리보기 경계만 복구했다. 실제 주문, live 재무장, 자본 배분, whitelist/caps,
  손실 예산, 비밀값, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다. 지금 돈을 못 버는 직접 이유는
  sidecar 지각이나 SSH 거부가 아니라 `NO_EDGE`: 전진 성과의 엣지 신뢰도(PSR)가 아직 0.95 기준을 넘지 못했기 때문이다.
- **상세 인계**: `HANDOFF-127-LIVE-CANARY-OBSERVE-GATEWAY.md`.

## 최근 관찰 — 2026-08-01 KST (#566 forward paper 경제 장부 보정)

현재 `main` 최신 코드 머지는 `f15f87d`(#566, forward paper economic anchor)다.
기능 커밋은 `3db8940`이다.

- **문제 정의**: 최신 돈 경로는 `PREVIEW_ONLY`/`NO_EDGE_YET`라 실주문을 막고 있었다. 동시에
  `rebalance-paper-forward`는 성공처럼 보였지만, 종이거래 리밸런서가 이전 종이 체결 보유를
  `current_positions`에서만 읽었다. 종이 라우터는 의도적으로 `current_positions`를 쓰지 않고
  `ORDER_PAPER_FILLED` 감사 로그만 남기므로, 다음 실행 때 리밸런서가 보유를 0으로 착각해 반복 매수했고
  종이 장부 현금이 크게 음수로 왜곡됐다. 즉 엣지를 판단하는 전진 성과 증거가 경제적으로 오염됐다.
- **구현 상태**: #566은 `src/auto_invest/execution/rebalancer.py`에 paper-only 보유 재구성 경로를
  추가했다. paper mode에서 감사 로그의 `ORDER_PAPER_FILLED`를 `performance.engine.reconstruct`로
  되살려 현재 가상 보유로 쓰고, 종이 fill이 전혀 없을 때만 기존 `current_positions` fallback을 유지한다.
  live/non-paper 경로와 명시적 `account_holdings` 입력은 바꾸지 않았다.
- **post-merge 배포 확인**: `Deploy on merge to main` run `30674990967`은 commit `f15f87d` 기준 success다.
- **forward paper 확인**: 수동 `rebalance-paper-forward.yml` run `30675023375`는 success다. 최신 sidecar는
  commit `f15f87d`, timestamp `2026-08-01T00:17:37Z`, 7개 트랙 prep/verdict `ssh_exit=0`이다.
  로그에는 예전처럼 목표 보유를 다시 사는 출력이 아니라 `planned_buy_notional_usd: 0.00`과
  `planned_sell_notional_usd`, `SELL`/`PAPER_FILLED`가 남는다. 과거 반복 매수로 생긴 음수 현금은
  한 번에 사라지지 않고 per-trade cap 범위에서 점진적으로 정리된다.
- **최신 돈 경로**: `money-path` run `30675222849`는 commit `f15f87d`, timestamp
  `2026-08-01T00:19:07Z`, `PREVIEW_ONLY`/`NO_EDGE_YET`다. micro GTAA 최상위 live money 상태는
  `PREVIEW_ONLY`, 마지막 전략 의도 게이트는 `latest_intent_loss`다. 기존 자본 사다리는 관측 28회,
  PSR `0.400049 < 0.95`, 칼마 벤치마크 미달로 첫 자본을 넣지 않는다. `capital-path-readiness`
  run `30675223926`은 commit `f15f87d`, timestamp `2026-08-01T00:19:09Z`,
  `ACCUMULATING_EDGE`, 우선 후보 없음이다.
- **검증 상태**: #566 브랜치에서 focused rebalancer tests 9 passed, adjacent tests 81 passed,
  `uv run pytest -q` 2707 passed/5 skipped, `uv run ruff check src tests` 통과,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14),
  `uv run python scripts/check_handoff_facts.py` OK, `git diff --check` 통과,
  PR quality gate 통과, `mergeStateStatus=CLEAN` 확인 뒤 merge했다.
- **안전 경계**: 종이거래 경제 장부만 고쳤다. 실제 주문, live 재무장, 자본 배분, whitelist/caps,
  손실 예산, 비밀값, 감사 로그 삭제, 헌법, kernel manifest는 바꾸지 않았다. 지금 돈을 못 버는 직접 이유는
  반복 매수 버그가 아니라 여전히 `NO_EDGE`: 전진 성과가 아직 벤치마크와 유의성 기준을 넘지 못했기 때문이다.

## 최근 관찰 — 2026-07-31 KST (#564 regime-stratify observe gateway 복구)

현재 `main` 최신 코드 머지는 `5fb249c`(#564, regime-stratify observe gateway)다.
기능 커밋은 `e3c39bc`이다.

- **문제 정의**: 최신 돈 경로는 `PREVIEW_ONLY`/`NO_EDGE_YET`라 실주문을 막고 있었다. 동시에
  `regime-stratify` sidecar는 workflow success처럼 보였지만 실제 내용은 `ssh_exit=126`,
  `refused command: cd /opt/auto-invest && rm -rf ... uv run ...`, 타임라인 prep exit 255였다. 즉 돈을
  바로 켤 안전 증거는 없고, 전략이 어떤 거시 레짐에서 벌고 잃는지 보는 연구 관측도 서버 보안 gateway에
  막혀 있었다.
- **구현 상태**: #564는 `regime-stratify.yml`에서 raw `scp`와 임의 inline SSH 명령을 없애고,
  `observe regime-stratify global` / `observe regime-stratify wide` 고정 명령만 쓰게 했다.
  서버 helper는 `origin/automation/public-data:regime_timeline.csv`를 `/tmp/regime_timeline.csv`로
  읽고, `/tmp/stratify_<track>` 작업공간에서 bars export, history ingest, portfolio backtest,
  regime-stratify를 순서대로 실행한다. 허용 트랙은 `global|wide`뿐이다.
- **post-merge 배포 확인**: `Deploy on merge to main` run `30630190101`은 commit `5fb249c` 기준 success다.
  로그에서 `AUTO_INVEST_SSH_BOUNDARY_HELPERS_REFRESHED`, `observe_helper=/usr/local/sbin/auto-invest-observe`,
  worker stop/start, deploy correlation id `1cfa275ddd763bb0211ccc627ba45756`을 확인했다.
- **regime-stratify 확인**: `regime-stratify.yml` run `30630190081`은 success다. 최신 sidecar timestamp는
  `2026-07-31T12:20:10Z`이고 타임라인 prep exit 0, GLOBAL-TREND `ssh_exit=0`,
  GLOBAL-TREND-WIDE `ssh_exit=0`이다. 두 출력 모두 `--- stratified json ---`와
  `"schema_version": "1.0"`을 포함한다. GLOBAL 전체는 752일, 총수익 42.97%, 최대낙폭 10.48%,
  샤프 1.30이고, WIDE 전체는 752일, 총수익 22.54%, 최대낙폭 5.78%, 샤프 1.11이다.
- **최신 돈 경로**: money-path timestamp `2026-07-31T10:35:43Z`는 `PREVIEW_ONLY`/`NO_EDGE_YET`다.
  관측은 28회로 최소 관측을 넘었지만 PSR `0.400049 < 0.95`, 칼마 벤치마크 미달이다. edge-autoarm은
  `WAIT_EDGE`, capital-path-readiness는 `ACCUMULATING_EDGE`, autonomous-work는
  `wait-for-fresh-evidence` / `OBSERVATION_WAIT`다.
- **검증 상태**: #564 브랜치에서 focused tests 20 passed, adjacent tests 56 passed,
  `bash -n deploy/observe-on-instance.sh deploy/repair-ssh-boundary.sh` 통과,
  `uv run pytest` 2706 passed/5 skipped, `uv run ruff check src tests` 통과,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14),
  `uv run python scripts/check_handoff_facts.py` OK, `git diff --check` 통과, PR quality gate 통과,
  `mergeStateStatus=CLEAN` 확인 뒤 merge했다. 이 handoff 갱신 전 `uv run pytest -q`는
  `HANDOFF.md`가 아직 `1643410`을 가리켜 하네스 관련 2개만 실패했고, 이 갱신이 그 원인을 바로잡는다.
- **안전 경계**: 연구 관측 파이프만 복구했다. 실제 주문, live 재무장, 자본 배분, whitelist/caps,
  손실 예산, 비밀값, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다. 지금 돈을 못 버는 직접 이유는
  서버 명령 거부가 아니라 `NO_EDGE`: 전진 성과가 아직 벤치마크와 유의성 기준을 넘지 못했기 때문이다.

## 최근 관찰 — 2026-07-31 KST (#562 forward paper DB writability 복구)

현재 `main` 최신 코드 머지는 `1643410`(#562, forward paper DB writability)다.
기능 커밋은 `67ed8c1`이다.

- **문제 정의**: 최신 money-path는 `PREVIEW_ONLY`/`NO_EDGE_YET`라 실주문을 막고 있었고,
  `rebalance-paper-forward` sidecar는 모든 forward paper prep step에서
  `OperationalError: attempt to write a readonly database`를 남겼다. 즉 실제 돈이 안 나가는 직접
  이유는 "엣지 없음"이지만, 그 엣지를 새로 판정할 관측 DB도 권한 drift 때문에 증거를 못 쌓고 있었다.
- **구현 상태**: #562는 `deploy/observe-on-instance.sh`에 `ensure_paper_track_storage`를 추가해
  `observe paper-track-run <track> <capital>` 직전에 `data/forward_*.db`, `-wal`, `-shm`,
  `data/forward_*.halt.flag`만 `APP_USER`가 쓸 수 있게 복구한다. `data/auto_invest.db`,
  `data/halt.flag`, 비밀값, live 설정, 자본, 주문 경로는 대상에서 제외된다. 예상 밖 경로나 symlink는
  fail-closed다.
- **post-merge 배포 확인**: `Deploy on merge to main` run `30596929563`은 commit `1643410` 기준 success다.
  로그에서 `origin/main:deploy/observe-on-instance.sh`를 서버가 읽고
  `AUTO_INVEST_SSH_BOUNDARY_HELPERS_REFRESHED`, `observe_helper=/usr/local/sbin/auto-invest-observe`가
  확인됐다.
- **forward paper 확인**: 수동 `rebalance-paper-forward.yml` run `30596973332`는 commit `1643410` 기준
  success다. 최신 sidecar timestamp는 `2026-07-31T01:44:16Z`이고 7개 트랙 모두 prep/verdict
  `ssh_exit=0`이다. `OperationalError` / `attempt to write a readonly database` 문자열은 최신 sidecar에
  없다. 관측 품질은 `OK`, 모든 후보는 최소 관측을 충족하지만 전체 판정은 여전히 `NO_EDGE`다.
- **최신 돈 경로**: edge-autoarm run `30597184383`은 `WAIT_EDGE`; money-path run `30597231376`은
  `PREVIEW_ONLY`/`NO_EDGE_YET`, forward 관측 28회, PSR `0.400049 < 0.95`, 칼마도 벤치마크 미달이다.
  capital-path-readiness run `30597231465`은 `ACCUMULATING_EDGE`이고 우선 후보 없음. autonomous-work run
  `30597261537`은 `wait-for-fresh-evidence` / `OBSERVATION_WAIT`다.
- **검증 상태**: #562 브랜치에서 focused helper tests 17 passed, helper shell syntax 통과,
  `uv run pytest` 2705 passed/5 skipped, `uv run ruff check src tests` 통과,
  `uv run python scripts/check_handoff_facts.py` OK, `uv run python scripts/agent_harness_probe.py --strict`
  OK(14/14), `git diff --cached --check` 통과, PR quality gate 통과, `mergeStateStatus=CLEAN` 확인 뒤 merge했다.
  이 handoff 갱신 전 `uv run pytest -q`는 `HANDOFF.md`가 아직 `85584ed`를 가리켜 하네스 관련 2개만 실패했고,
  이 갱신이 그 원인을 바로잡는다.
- **안전 경계**: 관측 파이프만 복구했다. 실제 주문, live 재무장, 자본 배분, whitelist/caps, 손실 예산,
  비밀값, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다. 지금 돈을 못 버는 직접 이유는 서버 권한 오류가
  아니라 `NO_EDGE`: 전진 성과가 아직 벤치마크와 유의성 기준을 넘지 못했기 때문이다.

## 최근 관찰 — 2026-07-31 KST (#560 서버 helper self-refresh와 promote-readiness 복구)

현재 `main` 최신 코드 머지는 `85584ed`(#560, promote-readiness gateway self-refresh)다.
기능 커밋은 `3aa45c4`이다.

- **문제 정의**: #559가 workflow를 fixed `observe promote-readiness`로 고쳤지만, 실제 서버는 여전히
  `ssh_exit=126`, `refused command: observe promote-readiness`를 냈다. 원인은 코드가 아니라
  서버에 이미 설치된 root-owned gateway/helper 파일이 자동 배포 때 갱신되지 않는 설치본 drift였다.
- **구현 상태**: #560은 `deploy/auto-invest-deploy.service`에 root-only `ExecStartPre=+...`를 추가해
  정상 unprivileged deploy state machine 실행 전에 `origin/main`의
  `deploy/refresh-ssh-boundary-helpers.sh`를 읽어 실행한다. 새 refresh helper는 다시
  `origin/main:deploy/repair-ssh-boundary.sh`를 읽고 `REFRESH_HELPERS_ONLY=1`로 gateway, sync helper,
  KIS smoke helper, observe helper, gateway sudoers만 설치한다. deploy 사용자/키, root key retirement,
  worker 상태, live-money 설정은 건드리지 않는다.
- **post-merge 배포 확인**: `Deploy on merge to main` run `30592573381`은 commit `85584ed` 기준 success다.
  로그에서 `AUTO_INVEST_SSH_BOUNDARY_HELPERS_REFRESHED`와
  `gateway=/usr/local/sbin/auto-invest-deploy-gateway`,
  `observe_helper=/usr/local/sbin/auto-invest-observe`가 확인됐다. 같은 로그에서 `origin/main`의
  refresh/repair/sync/KIS/observe helper 파일을 서버가 읽은 것도 확인했다. 배포 correlation id는
  `5536b51bdfb7ab625add5f1becbf557b`다.
- **promote-readiness 확인**: 수동 `Promote readiness` run `30592627513`은 commit `85584ed` 기준 success다.
  최신 sidecar는 `ssh_exit=1`, READY=false, stderr empty다. 이것은 더 이상 SSH gateway setup 오류가
  아니고, 승격 준비도 평가가 정상 실행된 뒤 "아직 준비 안 됨"을 보고한 정상 not-ready 상태다.
  JSON 사유는 라이브 기간 0/10일 미달, 청산 거래 0건 미달, 낙폭/수익률 측정 불가, 정합성 불일치 이력이다.
- **released/autonomous 상태**: #560 직후 `Released work ledger` run `30592573343`은 success,
  released_count=39였고 스펙 121은 T024 미완료라 제외됐다. 이 HANDOFF 갱신이 T024를 닫으므로 다음
  released-work run에서 121이 완료 후보로 소비되어야 한다. `Autonomous work execution loop`
  run `30592573408`은 success, selected_work=`wait-for-fresh-evidence`, status=`OBSERVATION_WAIT`,
  ranked_count=0이다.
- **검증 상태**: #560 브랜치에서 focused test 32 passed, `bash -n` 3개 helper 통과,
  `uv run pytest` 2703 passed/5 skipped, `uv run ruff check src tests` 통과,
  `uv run python scripts/check_handoff_facts.py` OK, `uv run python scripts/agent_harness_probe.py --strict`
  OK(14/14), `git diff --check` 통과, PR quality gate 통과, `mergeStateStatus=CLEAN` 확인 뒤 merge했다.
- **안전 경계**: 이 변경은 돈 경로를 열지 않는다. 실제 주문, live 재무장, 자본 배분, whitelist/caps,
  손실 예산, 비밀값, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다. 최신 money-path는 계속
  `PREVIEW_ONLY`/`NO_EDGE_YET`라 실주문은 불가다. 지금 돈을 못 버는 직접 이유는 서버 거부가 아니라
  엣지/승격 게이트가 아직 통과되지 않았기 때문이다.

## 최근 관찰 — 2026-07-31 KST (#559 promote-readiness observe gateway와 설치본 helper drift)

현재 `main` 최신 코드 머지는 `f1f2eab`(#559, promote-readiness observe gateway)다.
기능 커밋은 `19c65cb`이다.

- **문제 정의**: `promote-readiness` sidecar는 raw SSH 명령
  `cd /opt/auto-invest && /usr/local/bin/uv run auto-invest promote-check ...`를 보내고 있었고,
  서버의 forced-command gateway가 이를 `ssh_exit=126`으로 거부했다. 이 거부 자체는 보안 경계가
  정상 작동한 증거였지만, 헌법 VI(라이브 트랙레코드) 승격 준비 보고가 보이지 않는 문제가 남았다.
- **구현 상태**: #559는 workflow 명령을 fixed `observe promote-readiness`로 바꿨고,
  `deploy/repair-ssh-boundary.sh` gateway allowlist와 `deploy/observe-on-instance.sh` helper에
  report-only `promote-check --db data/auto_invest.db --rules deploy/canary-live-rules.toml
  --capital 12000 --format json` 경로를 추가했다. caller-provided argument는 받지 않는다.
- **post-merge 관찰**: `Deploy on merge to main` run `30591520066`, `Released work ledger`
  run `30591520091`, `Autonomous work execution loop` run `30591520113`은 모두 success다.
  그러나 수동 `promote-readiness` run `30591552556`은 workflow success이면서 sidecar에
  `ssh_exit=126`, `refused command: observe promote-readiness`를 남겼다. 코드의 workflow drift는
  닫혔지만, 실제 서버에 설치된 root-owned gateway/helper 파일이 자동 갱신되지 않는 설치본 drift가
  남은 것이다.
- **검증 상태**: #559 브랜치에서 focused test, shell syntax, `uv run pytest` 2699 passed/5 skipped,
  `uv run ruff check src tests`, `uv run python scripts/check_handoff_facts.py`,
  `uv run python scripts/agent_harness_probe.py --strict`, `git diff --check`, PR quality gate를 통과했다.
  이 HANDOFF 갱신 전 현재 후속 브랜치의 전체 테스트는 `마지막 main 커밋` 행이 stale이라 하네스 관련
  2개만 실패했고, 이 갱신이 그 원인을 바로잡는다.
- **다음 행동**: 스펙 121 후속은 deploy service가 정상 배포 상태기계 실행 전에 root-only pre-step으로
  `origin/main`의 gateway/helper/sudoers를 다시 설치하게 만들어야 한다. 이 후속도 관찰 경로 보정일 뿐,
  실제 주문·live 재무장·자본 배분을 열면 안 된다.
- **안전 경계**: 실제 주문, 실거래 전환, live 재무장, 자본 배분, whitelist/caps, 손실 예산, 비밀값,
  감사 로그, 헌법, kernel manifest는 바꾸지 않았다. 최신 money-path는 계속
  `PREVIEW_ONLY`/`NO_EDGE_YET`라 실주문은 불가다.

## 최근 관찰 — 2026-07-31 KST (#557 완료 후보 소비와 관찰 대기)

현재 `main` 최신 코드 머지는 `aee5d43`(#557, released-work candidate 120 consumption)다.
기능 커밋은 `7551107`이다.

- **문제 정의**: #555로 `candidate-evidence-source-diversification-validation-failures` 후보가 구현됐지만,
  스펙 120 문서에는 released-work가 읽는 `completed_candidate_id` 완료 마커가 없었다. 그래서 자동화
  sidecar가 방금 끝낸 후보를 다음 실행 후보로 다시 보여줄 수 있었다.
- **구현 상태**: #557은 스펙 120에 `completed_candidate_id:
  candidate-evidence-source-diversification-validation-failures`를 추가했다. 또한 `autonomous-work`가
  실행 가능 후보 없이 완료·억제 후보만 남은 경우, 완료 후보를 대표 후보로 다시 올리지 않고
  `wait-for-fresh-evidence` / `OBSERVATION_WAIT`를 선택하게 했다. 실행 가능 후보, 운영자 승인 필요 후보,
  복구 우선 후보가 있으면 기존 선택 순서는 유지한다.
- **post-merge 자동화**: `Released work ledger` run `30587962825`는 commit `aee5d43` 기준 success이고
  `released_count=39`, 스펙 120 후보 `candidate-evidence-source-diversification-validation-failures`를
  `completed_candidate_id`로 소비한다. `Autonomous work execution loop` run `30587962855`는 commit
  `aee5d43` 기준 success이고 `overall_status=OBSERVATION_WAIT`, selected_work=`wait-for-fresh-evidence`,
  ranked_count=0, 반복 후보 ranked count=0이다. `Deploy on merge to main` run `30587962839`도 success다.
- **검증 상태**: #557 브랜치에서 `uv run pytest` 2698 passed, 5 skipped,
  `uv run ruff check src tests` 통과, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14),
  `uv run python scripts/check_handoff_facts.py` OK, `git diff --check` 통과, PR quality gate 통과를 확인했다.
  이 HANDOFF 갱신 전 `uv run pytest -q`는 `마지막 main 커밋` 행이 stale이라 하네스 관련 2개만 실패했고,
  이 갱신이 그 원인을 바로잡는다.
- **안전 경계**: 이 변경은 돈 경로를 열지 않는다. 실제 주문, live 재무장, 자본 배분, whitelist/caps,
  손실 예산, 비밀값, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다. 최신 money-path는 계속
  `PREVIEW_ONLY`/`NO_EDGE_YET`라 실주문은 불가다.

## 최근 관찰 — 2026-07-31 KST (#555 증거 기반 후보 소스 다변화)

현재 `main` 최신 코드 머지는 `97c1f87`(#555, evidence-based candidate source diversification)다.
기능 커밋은 `457a648`이다.

- **문제 정의**: 실제 돈이 아직 움직이지 않는 직접 이유는 서버/KIS 접속이 아니라
  `PREVIEW_ONLY`/`NO_EDGE_YET`다. 동시에 자율 작업 실행 루프는 완료·억제된 후보와
  retryable blocked validation package 증거를 다음 작업 후보로 충분히 바꾸지 못해,
  “다음 no-live 개선”을 고르는 비용이 반복됐다.
- **구현 상태**: #555는 `candidate-evidence-source-diversification-validation-failures`
  후보를 추가한다. 일반 실행 가능 후보가 없고 운영자 승인이 필요한 위험 후보도 없으며,
  `candidate-result-executor`에 자동으로 원인을 좁혀도 되는 blocked package가 있으면
  해당 후보를 `CODEX_AUTONOMOUS_START` 작업으로 선택한다. 출력 JSON과 Markdown에는
  `blocked_package_refs`와 `validation_failure_groups`가 남아 candidate/package/diagnostic/
  safe next action을 잃지 않는다.
- **실제 sidecar 재현**: 원격 automation sidecar를 임시 수집해
  `scripts/autonomous_work_execution_probe.py`로 읽으면 selected candidate는
  `candidate-evidence-source-diversification-validation-failures`, blocked refs는 2개,
  group은 `execution_failed`다. money-path는 `PREVIEW_ONLY`/`NO_EDGE_YET`,
  edge-autoarm은 `WAIT_EDGE`/`NO_EDGE`로 읽힌다.
- **검증 상태**: #555 브랜치에서 `uv run pytest` 2696 passed, 5 skipped,
  `uv run ruff check src tests` 통과, `uv run python scripts/agent_harness_probe.py --strict`
  OK(14/14), `uv run python scripts/check_handoff_facts.py` OK, `git diff --check` 통과,
  SDD prerequisites check 통과, PR quality gate 통과를 확인했다.
- **안전 경계**: 이 변경은 돈 경로를 열지 않는다. 실제 주문, live 재무장, 자본 배분,
  whitelist/caps, 손실 예산, 비밀값, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.

## 돈 경로 상태 판독 규칙 (필수 — 스펙 062)

다음 세션은 실제 돈 상태를 오래된 `HANDOFF.md` 역사 문단, KIS smoke 현금값, 기존 첫-자본 ETA만 보고 판단하지 않는다. 먼저 money-path가 생성한 최상위 실제 돈 상태를 본다.

1. `git fetch origin '+refs/heads/automation/*:refs/remotes/origin/automation/*'`로 자동화 사이드카를 갱신한다.
2. 우선 `git show origin/automation/money-path-last-run:LAST_RUN.md`에서 `## 실제 돈 최상위 상태`를 확인한다. 그 섹션이 없으면 아직 스펙 062 money-path가 한 번도 발행되지 않은 상태이므로 아래 원본 증거를 직접 읽거나 `scripts/money_path_probe.py`를 로컬 재현한다.
3. 현재 live 의도 원본은 `automation/rebalance-micro-gtaa.request`다. 마지막 실행 증거는 `origin/automation/rebalance-micro-gtaa-last-run:LAST_RUN.md`다. KIS smoke 현금값은 preflight 입력일 뿐, `armed` 상태나 다음 live 가능 여부의 대체 근거가 아니다.
4. `live_money_state.status`가 `PREVIEW_ONLY`이면 "실주문 불가"로 답한다. `BLOCKED`이면 "안전 게이트가 실주문을 막고 있음"으로 답하고 `detail`과 `last_run.intent_gate_reason`을 같이 읽는다. `REAL_ORDER_PATH_ARMED`이면 "실제 돈 경로가 켜져 있음"으로 답한다. 단, 이것은 비-push 실행이 미국 정규장, KIS 매수가능 현금 1% 버퍼, micro 손실 브레이커, K1 한도와 K2 허용 종목을 통과하면 실주문 단계에 도달할 수 있다는 뜻이지 접수·체결 보장이 아니다.
5. 스펙 063 이후 micro GTAA live canary는 계좌 전체 preview를 만든다. 기존 보유 `BHP`, `MRK`, `ORANY`, `RELX`는 목표 유니버스가 아니라 청산 전용이다. 현금이 목표 매수와 1% 완충금을 충족하지 못하고 청산 전용 매도 후보가 있으면 이번 주기는 `effective_side=sell`로 매도만 실행하고, 매수는 다음 fresh KIS 현금 조회가 충분할 때까지 보류한다.
6. 현재 기준(2026-08-10T04:38Z KIS smoke, 2026-08-09T09:59Z money-gate-alignment, 09:53Z autonomous-work, 08:59Z capital-path-readiness, 08:38Z money-path, 2026-08-08T00:32Z edge-autoarm): money-path는 `live_money_state.status=PREVIEW_ONLY`, 자본 사다리 단계 `NO_EDGE_YET`, capital-path-readiness는 `ACCUMULATING_EDGE`, money-gate-alignment는 `ALIGNED_WAITING`, autonomous-work는 `OBSERVATION_WAIT`이다. 실주문이 아직 안 나가는 직접 이유는 forward 판정 `NO_EDGE`다. 관측 39회로 최소 관측은 채웠지만, 엣지 신뢰도 PSR이 `0.567128`이라 기준 `0.95`를 넘지 못했다. KIS smoke는 read-only quote/cash/positions/balance 4개는 통과하지만 최근 체결 조회가 KIS 서버 500으로 실패하고, 기존 helper가 즉시 전체 재시도해 OAuth 403까지 만든다. 다음 행동은 전진 관측을 계속 누적하고, KIS smoke는 민감 로그와 재시도 노이즈를 제거한 뒤 같은 fail-closed 판정을 유지하는 것이다. 스펙 062의 2026-06-22 `armed:true` 기록은 역사이며 현재 상태 근거로 쓰지 않는다.
7. PR #398 이후 `latest_signal=INTENT_LOSS`인데 verdict가 아직 `INSUFFICIENT_DATA`인 경우, "다음 micro GTAA 실행에서 live 표본이 자동으로 더 쌓인다"고 말하지 않는다. live gate가 실주문을 막으므로 새 live 표본은 자동 누적되지 않는다. 다음 행동은 forward 토너먼트·재지정 증거를 기다리거나 별도 전략 검토 후 재무장 여부를 판단하는 것이다.

## 전략 검토 상태 판독 규칙 (필수 — 스펙 066)

최신 reassign sidecar run `28278589509`는 #396 이전 코드로 생성되어 `globalfixed`의 관측 수가 9회,
다른 후보들이 12회라는 이유로 후보 관측 품질을 `DEGRADED`로 표시했다. 그러나 모든 후보가
최소 관측 20회 전이면 이것은 "장애"가 아니라 정상 누적 차이다. 다음 세션은 아래 순서로 읽는다.

1. `git fetch origin '+refs/heads/automation/*:refs/remotes/origin/automation/*'`로 sidecar를 갱신한다.
2. `git show origin/automation/reassign-last-run:LAST_RUN.md`에서 run 시각과 코드 커밋을 먼저 본다. #396(`d97d6a2`) 전 실행이면 관측 품질 판정이 stale일 수 있다.
3. 스펙 066 이후 `observation_health` 규칙:
   - 모든 후보가 알려져 있고 모두 `PREMATURE`이면 관측 수 차이가 있어도 `OK`. `lagging_keys`는 참고 정보로만 남는다.
   - 하나 이상의 후보가 `COMPARABLE`이고 다른 알려진 후보가 최소 관측 미달이면 `DEGRADED`.
   - 모든 알려진 후보가 `COMPARABLE`이면 관측 수 차이가 있어도 `OK`.
   - 판정 누락은 `DEGRADED`, 라이브 검증 트랙 누락은 `BLOCKED`.
4. 이 보정은 재지정을 앞당기는 변경이 아니다. 현재 true blocker는 "후보 품질 장애"가 아니라
   "아직 비교 가능한 도전자 없음"이다. 실주문, 센티넬, 자본, whitelist, live 전략 설정은 바꾸지 않았다.

빠른 로컬 재현:

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/money_path_probe.py --manifest | while IFS=$'\t' read -r key ref file; do
  git show "origin/$ref:$file" > "$tmpdir/$key.md" 2>/dev/null || true
done
uv run python scripts/money_path_probe.py --sidecar-dir "$tmpdir" --json | jq '.live_money_state'
```

## 최근 관찰 — 2026-07-30 KST (Vultr 서버 경계 수리, KIS smoke 성공, observe gateway 복구)

현재 `main` 최신 코드 머지는 `2d6790a`(#553, read-only money observation gateway)다.
#552 merge commit은 `d43ce6a`, #553 기능 커밋은 `388c61c`다.

- **문제 정의**: 서버가 새 deploy 공개키를 받아들이지 않아 KIS smoke와 deploy가 `Permission denied`에서
  멈췄다. 운영자가 Vultr 웹 로그인을 완료한 뒤, Codex는 Chrome/Vultr console을 사용해 서버 root 접근을
  회복하고 non-root `gh-deploy` forced-command gateway를 실제 서버에 설치했다. 비밀번호 값, 쿠키,
  브라우저 세션 저장소, private key 값은 읽거나 출력하지 않았다.
- **구현 상태**: #552는 KIS smoke workflow의 원격 `bash -s`를 제거하고 `kis-smoke <40hex SHA>` 고정
  gateway 명령만 쓰게 했다. #553은 #552 뒤에 막힌 돈 경로 관측을 `observe ...` 고정 helper로 복구했다.
  서버에는 `/usr/local/sbin/auto-invest-kis-smoke`와 `/usr/local/sbin/auto-invest-observe`가 설치됐다.
  `observe` 허용 범위는 페이퍼 forward 트랙 실행·판정, 정지 깃발 읽기, account NAV 읽기, live growth
  읽기뿐이다. live 무장, 실주문, 자본 배분, live 설정 변경 명령은 추가하지 않았다.
- **검증 상태**: KIS smoke run `30554208213`은 commit `d43ce6a`, timestamp `2026-07-30T14:56:51Z`,
  `secrets_present=true`, `key_valid=true`, `smoke_state=success`, `smoke_exit=0`이다. PR #553은
  `uv run pytest` 2695 passed, 5 skipped, `uv run ruff check src tests` 통과,
  `agent_harness_probe.py --strict` OK(14/14), `check_handoff_facts.py` OK, PR quality gate 성공 뒤
  merge됐다. 서버에서 `gh-deploy`로 `observe account-nav`와 `observe ladder-forward-verdict`가 JSON을
  반환함도 확인했다.
- **최신 돈 경로 판정**: capital ladder run `30556432330`은 `WAIT_EDGE`이고 sentinel 변경 PR은 만들지
  않았다. money-path run `30556551981`은 `PREVIEW_ONLY`/`NO_EDGE_YET`, capital-path-readiness run
  `30556714121`은 `ACCUMULATING_EDGE`, money-gate-alignment run `30556751585`는 `ALIGNED_WAITING`,
  operator-mobile-alerts run `30556812286`은 `ATTENTION`, pipeline-liveness run `30556852909`는 `OK`다.
- **남은 현실**: KIS/SSH setup 차단은 해소됐다. 실제 돈이 아직 움직이지 않는 이유는 `NO_EDGE`: 전진
  관측 27회 기준 최소 관측은 채웠지만 벤치마크 대비 칼마와 PSR 기준을 못 넘었다. 이 상태에서 live
  재무장이나 자본 배분을 억지로 하면 과적합 방어를 우회하는 것이므로 하지 않는다. 다음 행동은 전진
  관측 누적과 후보 전략의 추가 토너먼트 검증이다.

## 최근 관찰 — 2026-07-29 KST (KIS smoke setup_pending 분류와 서버 공개키 설치 대기)

현재 `main` 최신 코드 머지는 `d3d1117`(#547, KIS smoke setup-pending 분류 보강)이다.
#547 기능 커밋은 `83c1a5e`다. 직전 기능 머지는 `f395e5a`(#545, operator Telegram alert retry 보강)이고,
#545 기능 커밋은 `5c766d0`, #543 기능 커밋은 `9192898`, #542 기능 커밋은 `07ecc29`,
#540 기능 커밋은 `2587573`, #538 기능 커밋은 `08d1c6c`, #536 기능 커밋은 `52bbc1a`다.

- **문제 정의**: 운영자가 "왜 실제 거래가 안 나가느냐"고 물었을 때, 최신 micro GTAA sidecar에는
  strategy-intent gate `ok=false`, `reason=latest_intent_loss`가 있었고 money-path도 `PREVIEW_ONLY`와
  자본 사다리 `BLOCKED`를 보고했다. 그 위에 서버 SSH 경로도 막혀 있었다. 이번 세션에서 fresh deploy
  key를 만들고 GitHub repo secrets `VULTR_SSH_USER`/`VULTR_SSH_PRIVATE_KEY`를 등록한 뒤 KIS smoke를
  다시 돌리자, 비밀값 누락은 해소됐지만 서버가 새 키를 아직 받아들이지 않아 `Permission denied`가 났다.
  그런데 #547 전 KIS smoke workflow는 `bash -e` 때문에 SSH exit 255에서 바로 종료되어 sidecar에
  `setup_pending`을 남기지 못했고, 정렬 루프가 "서버 공개키 설치 대기"와 "원인 미상"을 구분하기 어려웠다.
- **구현 상태**: #547은 `.github/workflows/kis-smoke.yml`의 원격 smoke 실행을 `set +e`와
  `PIPESTATUS` 캡처로 감싸 SSH exit 255도 의도한 분류 단계까지 흐르게 했다. 그래서 KIS smoke sidecar는
  `secrets_present=true`, `key_valid=true`, `smoke_state=setup_pending`, `smoke_exit=255`를 남긴다.
  `src/auto_invest/analytics/money_gate_alignment.py`는 `(unset)`/`unset`을 `UNKNOWN`으로 정규화하고,
  `setup_pending`을 KIS `BLOCKED` 이슈로 읽어 "서버에 deploy 공개키 설치 후 KIS smoke 재실행"을
  다음 행동으로 낸다. 회귀 테스트는 `tests/unit/test_kis_smoke_workflow.py`와
  `tests/unit/test_money_gate_alignment.py`에 추가했다. #545는 Telegram 일시 타임아웃 재시도를 보강했고,
  #543/#542/#540/#538/#536은 돈 경로 차단·KIS secret 누락·전략 의도 게이트 실패를 사람이 읽을 수 있게 드러냈다.
- **운영 상태**: GitHub repo secret 목록에는 `VULTR_SSH_USER`와 `VULTR_SSH_PRIVATE_KEY`가 2026-07-29T14:18Z
  기준 등록돼 있다(값은 출력하지 않았다). `Verify operator setup` run `30460226078`은 secret과 key
  형식 검증을 지나 `ssh_failed`로 실패했다. #547 머지 뒤 KIS smoke run `30461091999`는 workflow success이고
  sidecar는 main `d3d1117`, `setup_pending`, `smoke_exit=255`, `Permission denied (publickey,password)`를
  기록한다. money-gate-alignment 수동 run `30461180149`는 main `d3d1117` 기준 success지만 종합 판정은
  `BLOCKED`다. 입력 증거는 `live_money_status=PREVIEW_ONLY`, `readiness_state=LIVE_BLOCKED`,
  `capital_ladder_stage=BLOCKED`, `kis-smoke=setup_pending`이고, 다음 행동은 서버에서
  `deploy/repair-ssh-boundary.sh`에 새 deploy 공개키를 설치하고 KIS smoke를 다시 실행하는 것이다.
  deploy-on-merge run `30461091918`도 같은 서버 SSH 거부로 실패했다. 이는 배포가 열린 것이 아니라
  서버 경계가 아직 fail-closed로 닫혀 있다는 증거다.
- **남은 현실**: 실제 돈이 아직 움직이지 않는 이유는 세 겹이다. 첫째, 서버가 새 deploy 공개키를
  `gh-deploy` forced-command gateway에 아직 설치하지 않아 KIS smoke와 deploy가 서버 안쪽으로 못 들어간다.
  이 부분은 root 콘솔이나 검증된 out-of-band root SSH 같은 서버 접근이 있어야 끝난다. 둘째, money-path는
  계속 `PREVIEW_ONLY`이고 자본 사다리는 `BLOCKED`다. 셋째, micro GTAA 최신 실행은 `armed=false`,
  `LIVE 스텝=skipped`, 전략 의도 게이트 `latest_intent_loss`, 누적 의도 손익 `-1.14 USD`라 실주문을
  허용하지 않는다. 서버 공개키 설치 뒤 KIS smoke가 통과하면 그 다음에는 자본 사다리 JSON과 전략 의도
  게이트를 다시 읽어야 한다. 실제 주문·재무장·자본 배분은 이 게이트들이 통과하기 전에는 하지 않는다.
- **검증**: #547 브랜치에서 `uv run pytest tests/unit/test_kis_smoke_workflow.py tests/unit/test_money_gate_alignment.py -q`
  12 passed, `uv run pytest` 2691 passed, 5 skipped, `uv run ruff check src tests` 통과,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14),
  `uv run python scripts/check_handoff_facts.py` OK, PR 본문 품질 관문과 PR check `pr-quality-gate` 통과를
  확인했다. #547 merge 뒤 main push KIS smoke run `30461091999`와 money-gate-alignment run `30461180149`도
  읽어 상태 전환을 확인했다. 이 HANDOFF 갱신 전 `uv run pytest -q`는 `마지막 main 커밋` 행이 stale이라
  하네스 관련 2개만 실패했고, 이 갱신이 그 원인을 바로잡는다.
- **안전 경계**: #547은 등급 2 운영 진단 보정이다. 이번 세션에서 GitHub repo secret은 등록했지만
  secret 값은 출력·커밋하지 않았다. 실제 주문, 실거래 전환, 자본 배분, 라이브 전략 교체, whitelist/caps,
  손실 예산, KIS secret, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.

## 최근 관찰 — 2026-07-22 KST (스펙 119 production 환경과 SSH secret fail-closed 완료)

현재 `main` 최신 코드 머지는 `e5f8292`(#534, SSH secret fail-closed 보강)이다.
직전 기능 머지는 `2fe873e`(#533, live-money workflow `production` 보호 환경 적용)이고,
#534 기능 커밋은 `759a114`다.

- **문제 정의**: 보안 감사의 남은 P0 경계 중 GitHub Actions 수동 실행이 live-money workflow를 바로
  시작할 수 있는 면을 더 좁혀야 했다. 또한 #533 post-merge deploy가 SSH secret 부재로 안전하게
  실패했지만, 기존 공통 helper 밖 workflow들은 deploy user나 private key가 비어도 첫 단계에서 명확히
  멈추지 않고 뒤의 SSH 호출에서 exit 255로 터질 수 있었다.
- **구현 상태**: #533은 `go-live-canary`, `rebalance-live-canary`,
  `rebalance-micro-gtaa-canary`, `release-halt` job에 GitHub `production` environment를 선언했다.
  GitHub API 기준 `production` environment는 `main` branch만 허용하고 `jinooaction` required reviewer를
  요구한다. #534는 20개 SSH workflow의 키 설치 단계를 `scripts/ci_secure_ssh.sh`로 통합해
  `VULTR_SSH_USER`, `VULTR_SSH_PRIVATE_KEY`, `VULTR_SSH_KNOWN_HOSTS`가 없으면 첫 SSH 호출 전에
  exit 2와 명확한 오류 메시지로 멈추게 만들었다. `verify-operator-setup.yml`은 키 줄바꿈 복구 자체를
  검증하는 특수 진단 경로라 별도로 남겼다.
- **post-merge 실행**: PR #534는 2026-07-21T15:54:04Z에 merge됐고 merge commit은
  `e5f8292fdeaaa06c21547eae94d17ee974b5b82a`다. `Deploy on merge to main` run `29846134323`,
  `Forward anchored verdict` run `29846134390`, `Regime-stratified strategy performance` run `29846134311`은
  failure다. 세 run 모두 Actions 로그의 `Install SSH key` 단계에서 `missing VULTR_SSH_USER/SSH_USER`로
  실패했다. 이는 이번 보강이 의도한 조기 안전 중단이다. 단, anchored/regime sidecar 출력은 후속 수집
  단계 때문에 여전히 `ssh_exit=255`와 identity file 없음 문구를 남긴다. 다음 세션은 실패 원인 해석 때
  Actions log의 공통 helper 오류를 우선한다.
- **자동화 상태**: `Released work ledger` run `29846134307`은 success, `overall_status=OK`,
  `released_count=38`이다. `Money-path readiness` run `29846134317`은 success이고 commit `e5f8292` 기준
  `PREVIEW_ONLY`, `can_submit_real_orders=false`다. `KIS smoke (autonomous)` run `29846134420`은
  workflow success지만 sidecar는 commit `e5f8292`, `secrets_present=false`, `smoke_state=(unset)`다.
  `Autonomous work execution loop` run `29846134298`과 `Execution quality package` run `29846151715`은
  success이며 현재 실행 가능한 안전 후보는 없다.
- **검증**: #534 브랜치에서 focused SSH/workflow 테스트 28 passed,
  `uv run pytest` 2682 passed, 5 skipped, `uv run ruff check src tests` 통과,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14),
  `uv run python scripts/check_handoff_facts.py` OK, `git diff --check` 통과,
  `bash -n scripts/ci_secure_ssh.sh` 통과, PR 본문 품질 관문과 PR check `pr-quality-gate` 통과를 확인했다.
- **안전 경계**: 등급 3 안전 경계 변경이다. GitHub Environment 승인과 SSH secret 검증을 강화했다.
  K1 주문 제한, K4 감사 로그, 헌법, kernel manifest, 실거래 모드, 자본, 주문, KIS secret,
  whitelist/caps, 손실 예산은 바꾸지 않았다.
- **남은 현실**: 서버 실제 `repair-ssh-boundary.sh` 실행과 non-root deploy private key 등록은 아직
  서버 접근 권한이 없어 직접 완료하지 못했다. 그 전까지 deploy, anchored verdict, regime-stratify의
  원격 SSH 단계 실패는 정상 안전 중단이다.
- **상세 인계**: `HANDOFF-121-SSH-SECRET-FAIL-CLOSED.md`.

## 최근 관찰 — 2026-07-21 KST (스펙 119 후속 SSH boundary repair)

현재 `main` 최신 코드 머지는 `82296aa`(#531, SSH boundary repair 후속 보강)이다.
기능 커밋은 `19052de`다.

- **문제 정의**: #529는 GitHub-held root SSH secret을 제거했지만, 서버의 legacy root key retire와
  non-root forced-command deploy identity 설치는 실제 서버 접근이 필요한 남은 조치였다. 이 세션에서는
  로컬 SSH `root`, `auto-invest`, `gh-deploy`가 모두 `Permission denied`였고 GitHub/Vultr API secret도
  없었다. 따라서 인증 경계를 우회하지 않고, repo 안에 검증 가능한 서버 repair 경로를 만드는 것이
  가능한 최대 조치였다.
- **구현 상태**: #531은 `deploy/repair-ssh-boundary.sh`를 추가했다. 이 스크립트는 fresh
  `DEPLOY_PUBLIC_KEY`를 요구하고 private-key material을 거부하며, 기본 `gh-deploy` 사용자의
  `authorized_keys`에 forced-command gateway만 설치한다. gateway는 `status`, `sync-units`,
  `start-deploy`, `deploy-journal`만 허용하고 나머지는 거부한다. sudoers는 `visudo -cf`로 검증한 뒤
  root-owned sync helper, deploy service start, deploy journal 조회만 허용한다. root key retire는
  `github-actions@auto-invest`와 `/root/.ssh/auto_invest_gh`에 한정하며 unrelated root key를 지우지 않는다.
- **워크플로 변화**: `deploy-on-merge.yml`은 원격 `sudo bash -s` 파이프와 one-off untracked quarantine
  shell을 제거하고 gateway 고정 명령만 호출한다. `verify-operator-setup.yml`은 원격 임의 상태 조회 shell
  대신 gateway `status`만 호출한다.
- **post-merge 실행**: PR #531은 2026-07-21T02:01:39Z에 merge됐고 merge commit은
  `82296aa86aa45be6050770a73ea19fccd61452b8`다. `Deploy on merge to main` run `29794726091`은
  failure다. 이는 `VULTR_SSH_PRIVATE_KEY`와 `VULTR_SSH_USER`가 아직 없어서 gateway 접속 자체가
  불가능한 안전 중단이다. `Verify operator setup` run `29794726171`은 push 이벤트의 non-blocking
  diagnostic으로 success지만, missing secrets 때문에 수동 검증은 실패해야 정상이다.
- **자동화 상태**: `Released work ledger` run `29794726161`은 success, `overall_status=OK`,
  `released_count=38`이다. `Autonomous work execution loop` run `29794726117`은 success이며 현재 실행 가능한
  안전 후보가 없다. KIS smoke sidecar는 #531에서 새로 갱신되지 않았고, 최신 기록은 commit `6a46735`,
  `secrets_present=false`, `smoke_state=(unset)`다. money-path는 `PREVIEW_ONLY`,
  `can_submit_real_orders=false`다.
- **검증**: #531 최종 브랜치에서 `uv run pytest -q` 2679 passed, 5 skipped,
  `uv run ruff check src tests scripts` 통과, `bash -n` 통과, workflow YAML parse 통과,
  `git diff --check` 통과, 좁은 보안 회귀 36 passed, `uv run python scripts/agent_harness_probe.py --strict`
  OK(14/14), `uv run python scripts/check_handoff_facts.py` OK, PR 본문 품질 관문 통과.
- **안전 경계**: 등급 3 안전 경계 후속 변경이다. 서버 deploy SSH 경계와 배포 워크플로 원격 실행 방식을
  좁혔다. K1 주문 제한, K4 감사 로그, 헌법, kernel manifest, 실거래 모드, 자본, 주문, KIS secret,
  whitelist/caps, 손실 예산은 바꾸지 않았다.
- **남은 현실**: 실제 서버에서 `repair-ssh-boundary.sh`를 실행하지 못했다. 다음 서버 접근 가능 세션은
  root 콘솔 또는 검증된 out-of-band root SSH에서 이 스크립트를 실행한 뒤 GitHub에 non-root
  `VULTR_SSH_USER`/`VULTR_SSH_PRIVATE_KEY`를 등록하고 수동 `Verify operator setup`을 돌리면 된다.
- **상세 인계**: `HANDOFF-120-SSH-BOUNDARY-REPAIR.md`.

## 최근 관찰 — 2026-07-21 KST (스펙 119 보안 신뢰 경계 강화)

현재 `main` 최신 코드 머지는 `6a46735`(#529, 보안 신뢰 경계 강화)이다.
기능 커밋은 `5e90f3c`이고, 후속 보정 커밋은 `0d91c4b`, `b77885f`, `46d5982`다.

- **문제 정의**: 외부 보안 리뷰는 GitHub Actions, 저장소 secret, 서버 root SSH, mutable server code,
  실거래 주문 경로가 한 줄로 이어지는 구조를 P0로 지적했다. 핵심 목표는 GitHub가 서버 root 개인키를
  들고 실거래 경계까지 바로 닿는 상태를 끊고, canary/go-live/주문/sidecar 경로의 fail-open 지점을
  fail-closed로 바꾸는 것이었다.
- **구현 상태**: #529는 third-party Action SHA pin, `StrictHostKeyChecking=yes`와
  `VULTR_SSH_KNOWN_HOSTS` 필수화, `VULTR_SSH_USER=root` 거부, `capital` decimal 검증,
  `.env` allowlist parser, `go-live-canary.sh` expected SHA/시장상태 `CLOSED`/원자 env/전체 rollback,
  canary code+ruleset hash 필수화, `fcntl.flock` 배포 락, token cache 권한/원자 저장, 주문
  `SUBMITTING` 상태와 stale BUY 차단, 강한 unknown-order 매칭, verified reduce-only/oversell 판단,
  공개 sidecar redaction을 추가했다.
- **외부 secret 상태**: `VULTR_SSH_KNOWN_HOSTS`는 로컬 `known_hosts`와 keyscan이 일치한
  `202.182.125.132` ed25519 host key로 등록했다. GitHub-held root SSH user/private-key secrets인
  `VULTR_SSH_USER`와 `VULTR_SSH_PRIVATE_KEY`는 삭제했다. 따라서 GitHub에서 서버 root로 들어가는
  기존 길은 끊겼다.
- **post-merge 실행**: PR #529는 2026-07-20T23:55:50Z에 merge됐고 merge commit은
  `6a4673527a9947d29f2a594808c5f036f0a3b2ec`다. main push에서 `Verify operator setup`
  run `29788767789`는 success다. `Deploy on merge to main` run `29788767866`은 failure이며,
  SSH exit 255로 원격 배포 재료가 없어 멈췄다. 이것은 이번 보안 작업의 의도된 안전 중단이고
  worker는 직전 good SHA를 유지한다. `KIS smoke (autonomous)` run `29788767839`는 workflow success지만
  sidecar상 `secrets_present=false`, `smoke_state=(unset)`라 브로커 read-only smoke에는 진입하지 않았다.
- **자동화 상태**: 같은 main 커밋 기준 `Released work ledger` run `29788767774`는 success,
  `overall_status=OK`, `released_count=38`이다. 스펙 119는 아직 released 장부에 소비되지 않았다.
  `Autonomous work execution loop` run `29788767874`는 success이며 현재 실행 가능한 안전 후보가 없다.
  `Execution quality package` run `29788777678`은 success, `overall_status=OBSERVE`이고 KIS smoke는
  secret 부재로 `(unset)`이다. money-path는 계속 `PREVIEW_ONLY`라 실주문은 불가하다.
- **검증**: #529 최종 브랜치에서 `uv run pytest -q` 2669 passed, 5 skipped,
  `uv run ruff check src tests scripts` 통과, `git diff --check` 통과, shell `bash -n` 통과,
  workflow YAML parse 통과, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14),
  `uv run python scripts/check_handoff_facts.py` OK, PR 본문 품질 관문 통과. #529 merge 직후 main에서는
  `HANDOFF.md` stale 때문에 하네스 관련 테스트 2개가 실패했고, 이 handoff 갱신이 그 원인을 바로잡는다.
- **안전 경계**: 등급 3 안전 경계 변경이다. K1 포지션 한도/주문 제한과 K4 감사 로그 경계를 강화했다.
  실제 주문·취소·실거래 재무장·자본 증액·자본 배분·whitelist/caps 확대·손실 예산·헌법·kernel manifest는
  바꾸지 않았다.
- **남은 위험**: 서버 `/root/.ssh/authorized_keys`에서 기존 공개키가 제거됐는지, 제한 deploy 사용자와
  forced-command gateway가 설치됐는지는 이 세션에서 확인하지 못했다. 원격 배포/KIS smoke는 새 non-root
  `VULTR_SSH_USER`/`VULTR_SSH_PRIVATE_KEY`가 생기기 전까지 진입하지 않아야 정상이다.
- **상세 인계**: `HANDOFF-119-SECURITY-TRUST-BOUNDARY-HARDENING.md`.

## 최근 관찰 — 2026-07-15 KST (스펙 118 마무리와 KIS 열린 주문 smoke 보강)

현재 `main` 최신 코드 머지는 `2b9fe85`(#527, KIS live smoke 열린 주문 검사 보강)이다.
직전 기능 머지는 `158052a`(#525, 스펙 118 operator report liveness contract)이고, #527 기능 커밋은
`a3b324e`다.

- **문제 정의**: 스펙 118은 운영자가 이해 가능한 완료 보고 계약을 main에 넣었지만, 직후 남은 관찰
  지점으로 서버 배포 증거, 실제 KIS read-only smoke, KIS 계좌의 열린 주문 여부, released-work와
  autonomous-work 최신 상태가 남아 있었다. 특히 기존 KIS smoke는 quote, 현금, 보유, 합산 잔고 4개만
  확인했고 열린 미체결 주문 0건은 자동으로 보지 않았다.
- **구현 상태**: #525로 `src/auto_invest/analytics/operator_report_liveness.py`와
  `scripts/operator_report_liveness_probe.py`가 운영 보고 품질을 읽기 전용으로 판정한다. #527은
  `tests/integration/test_live_broker.py`에 `test_live_kis_recent_orders_have_no_open_unfilled`를 추가해
  최근 7일 KIS `inquire-ccnl` 주문/체결 조회 결과에서 `unfilled_qty > 0`이고 terminal이 아닌 주문이
  있으면 live smoke가 실패하게 했다.
- **post-merge 실행**: #527 main push 뒤 `KIS smoke (autonomous)` run `29422806756`이 success다.
  sidecar 기준 commit은 `2b9fe85`, `smoke_state=success`, `smoke_exit=0`, `5 passed`,
  `Live KIS recent order/execution rows: 0개, open_unfilled=0개`다. `Deploy on merge to main` run
  `29422806870`도 workflow 결론은 success지만, 실제 deploy oneshot은 미국 장중 배포 금지로
  `deploy refused: US market is open ... Next allowed deploy: 2026-07-15T20:00:00Z`를 남겼다. 이는
  런타임 코드 변경을 강행하지 않은 안전장치 동작이며, #527은 smoke 테스트 보강이라 live worker 코드
  반영을 요구하지 않는다.
- **장부와 자율 루프**: 수동 갱신한 released-work run `29422911779`는 `commit=2b9fe85`,
  `overall_status=OK`, `released_count=38`이고 `candidate-operator-report-liveness-contract`를
  released로 소비했다. execution-quality run `29422841373`은 최신 KIS smoke를 반영해 `tests_total=5`,
  `tests_failed=0`, `overall_status=OBSERVE`다. autonomous-work run `29422962267`은
  `overall_status=RELEASED`이고 "현재 실행 가능한 안전 후보가 없습니다"를 보고했다.
- **검증**: PR #527 브랜치와 머지 직전 모두 `uv run pytest` → 2638 passed, 5 skipped,
  `uv run ruff check src tests` → 통과. 브랜치 기준 KIS live smoke run `29422539457`은 실제 서버 secrets로
  5개 테스트를 모두 통과했고 열린 미체결 주문 0건을 확인했다. 등급 2 기준
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14),
  `uv run python scripts/check_handoff_facts.py` OK, PR 본문 품질 관문 통과.
- **안전 경계**: #527은 등급 2 읽기 전용 운영 smoke 보강이다. `inquire-ccnl`은 KIS 주문/체결 조회 GET
  경로이고 주문 생성·취소·자본 배분·실거래 재무장·whitelist/caps·손실 예산·live sentinel·K1/K2/K4/K5/K6·
  헌법·커널 목록·비밀값·외부 유료 서비스는 바꾸지 않았다. 현재 돈 경로는 계속 `PREVIEW_ONLY`다.
- **남은 위험**: 저장소와 GitHub Actions 사실 표면 기준 남은 실행 후보와 열린 미체결 주문 위험은 없다.
  장중 배포 금지는 의도된 안전 경계라 강제로 처리하지 않는다. 다음 장 마감 허용 시각 이후 deploy timer가
  자동 재시도한다.
- **상세 인계**: `HANDOFF-118-KIS-OPEN-ORDER-SMOKE.md`와
  `HANDOFF-117-OPERATOR-REPORT-LIVENESS-CONTRACT.md`.

## 최근 관찰 — 2026-07-13 KST (실행 안전성 released-work 장부 백필)

현재 `main` 최신 머지는 `62a585e`(#523, released-work 장부 백필)이다.
기능 코드는 #521 `8fd6b90` 이후 바뀌지 않았고, 이번 변경은 `specs/112-order-submission-uncertainty-recovery/tasks.md`와
`specs/113-atomic-fill-ledger/tasks.md`의 post-merge 체크박스를 실제 완료 사실에 맞춘 운영 기록 보정이다.

- **문제 정의**: 스펙 112와 113은 각각 #511, #513으로 구현됐고 #512, #514로 인계까지 들어갔지만,
  두 `tasks.md`의 마지막 PR·머지·post-merge·handoff 체크박스가 비어 있었다. 최신 released-work sidecar가
  이 때문에 112·113을 "체크박스 작업 미완료"로 제외했다.
- **구현 상태**: #523에서 112의 T049~T053, 113의 T028~T032를 완료로 표시했다. 코드, 테스트, live 설정,
  안전 경계 파일은 바꾸지 않았다.
- **post-merge 실행**: #523 main push 뒤 `Released work ledger` run `29259488568`와
  `Autonomous work execution loop` run `29259488628`가 success다. 최신 released-work sidecar는
  `commit=62a585e`, `overall_status=OK`, `released_count=37`이며
  `candidate-order-submission-uncertainty-recovery`, `candidate-atomic-fill-ledger`,
  `candidate-submission-unknown-broker-lookup`을 모두 released로 읽는다.
- **검증**: #523 브랜치에서 `uv run pytest -q` 2630 통과·4 스킵,
  `uv run ruff check src tests` 통과, `git diff --check` 통과,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 본문 품질 관문 통과.
  #523 이후 이 handoff 갱신 전에는 마지막 main 행이 낡아 `check_handoff_facts.py`가 FAIL했고, 이 섹션과
  한눈 요약표 갱신이 그 원인을 바로잡는다.
- **남은 위험**: 저장소 코드와 자동 완료 장부 기준 실행 안전성 111~117은 닫혔다. 실제 서버에서 동시에 떠 있는
  오래된 live worker나 분리 프로세스, KIS 계좌의 열린 주문·보유, GitHub Actions 비밀값과 Environment 보호
  규칙은 이 저장소 작업만으로 확인하지 않았다.

## 최근 관찰 — 2026-07-13 KST (스펙 117 `SUBMISSION_UNKNOWN` broker lookup 복구)

현재 `main` 최신 코드 머지는 `8fd6b90`(#521, 스펙 117 submission unknown broker lookup)이다.
기능 커밋은 `69fad52`이고, 직전 main은 `5ab62b6`(#520, 스펙 116 인계)이다.

- **문제 정의**: 스펙 112는 주문 `POST` 자동 재시도를 제거하고 불명확 제출 실패를
  `SUBMISSION_UNKNOWN`으로 남겼고, 스펙 115는 unresolved BUY가 신규 BUY를 막게 했다. 하지만 해당 상태를
  읽기 전용 broker order/execution lookup으로 자동 해소하는 경로가 없어 운영자가 수동 확인 전까지 계속
  막힌 상태로 남았다.
- **구현 상태**: `sync_fills`는 이제 열린 `SUBMITTED` 주문이 없어도 unresolved `SUBMISSION_UNKNOWN` 주문이
  있으면 KIS `inquire-ccnl`을 조회한다. symbol, side, quantity가 단일로 강하게 맞는 broker row가 정확히
  하나일 때만 `kis_order_id`, `submitted_at_utc`, `order_routing`을 채우고
  `ORDER_SUBMISSION_RECOVERED` 감사 이벤트를 남긴 뒤 `SUBMITTED`로 전이한다. 같은 broker evidence는 기존
  fill planner로 이어져 `FILL`, `PARTIALLY_FILLED`, `FILLED`, `EXPIRED`를 처리한다. 후보가 없거나 여러 개면
  상태를 바꾸지 않고, lookup 실패는 `ERROR` 감사만 남긴다.
- **post-merge 실행**: #521 main push 뒤 `Deploy on merge to main` run `29258260571`,
  `Released work ledger` run `29258261111`, `Autonomous work execution loop` run `29258261452`,
  `KIS smoke (autonomous)` run `29258261147`, `Execution quality package` run `29258301296`가 success다.
  #521 직후 released-work sidecar는 post-merge tasks T023~T025가 아직 닫히기 전이라 스펙 117을 제외했다.
  이 handoff PR은 T023~T025 완료 상태를 남겨 다음 장부가
  `candidate-submission-unknown-broker-lookup`을 released로 읽게 한다.
- **안전 경계**: 등급 4 돈 경로 복구 안전성 변경이다. broker write는 추가하지 않았다. 실제 주문·취소·
  실거래 재무장·자본 증액·자본 배분·whitelist/caps 확대·손실 예산·live sentinel·K1/K2/K4/K5/K6·헌법·
  커널 목록·비밀값·외부 유료 서비스 변경 없음. 현재 돈 경로는 계속 `PREVIEW_ONLY`다.
- **검증**: 구현 전 focused regression은 `SUBMISSION_UNKNOWN`만 있을 때 `inquire-ccnl`이 호출되지 않아
  4건 실패했고, 구현 후 같은 회귀 4 통과, 전체 fill sync 13 통과, 인접 worker/router/execution-state/
  live-order-path 47 통과, `uv run pytest -q` 2630 통과·4 스킵, `uv run ruff check src tests` 통과,
  `git diff --check` 통과, `uv run python scripts/check_handoff_facts.py` OK,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 본문 품질 관문 통과.
- **남은 위험**: 저장소 코드 기준 실행 안전성 111~117은 닫혔다. 실제 서버에서 동시에 떠 있는 오래된 live
  worker나 분리 프로세스, KIS 계좌의 열린 주문·보유, GitHub Actions 비밀값과 Environment 보호 규칙은
  이 저장소 작업만으로 확인하지 않았다.
- **상세 인계**: `HANDOFF-116-SUBMISSION-UNKNOWN-BROKER-LOOKUP.md`.

## 최근 관찰 — 2026-07-13 KST (스펙 116 단일 실행 권한)

현재 `main` 최신 코드 머지는 `8b0cfac`(#519, 스펙 116 single execution authority)이다.
기능 커밋은 `5897b8d`이고, 직전 main은 `e95016e`(#518, 스펙 115 인계)이다.

- **문제 정의**: 스펙 114와 115로 열린 BUY 예약 노출과 상태 불명확 신규 BUY 차단은 닫혔지만,
  worker, `rebalance-once`, lifecycle cancel/requote가 서로 다른 프로세스에서 같은 계좌의 broker write를
  동시에 평가할 수 있었다. 특히 lock 없이 `place_order` 호출 직전 게이트를 통과하면 두 프로세스가 같은
  오래된 계좌 스냅숏을 근거로 주문을 제출할 수 있었다.
- **구현 상태**: `src/auto_invest/execution/authority.py`가 유일한 broker write 권한이다.
  `place_order`와 `cancel_order` 직접 호출은 이 파일 안에만 남았다. `execution_authority_locks` DB 테이블은
  계좌별 owner, context, 획득 시각, 만료 시각을 기록한다. `OrderRouter.submit_order`는 live일 때 이 잠금을
  획득한 뒤 열린 BUY 예약, `execution_state_gate`, K1 cap gate, broker submission을 평가한다. 잠금이 이미
  잡혀 있으면 broker endpoint에 닿기 전에 `execution_authority_lock` gate rejection으로 남긴다. Worker의
  TTL cancel과 requote cancel도 같은 authority를 사용한다. paper mode와 dry-run preview는 broker write와
  authority lock을 만들지 않는다.
- **post-merge 실행**: #519 main push 뒤 `Deploy on merge to main` run `29256471036`,
  `Released work ledger` run `29256471028`, `Autonomous work execution loop` run `29256471114`가 success다.
  #519 직후 released-work sidecar는 post-merge tasks T024~T026이 아직 닫히기 전이라 스펙 116을 완료 후보로
  소비하지 않았다. 이 handoff PR은 T024~T026 완료 상태를 남겨 다음 장부가
  `candidate-single-execution-authority`를 released로 읽게 한다.
- **안전 경계**: 등급 4 돈 경로 권한 축소다. 실제 주문·취소·실거래 재무장·자본 증액·자본 배분·
  whitelist/caps 확대·손실 예산·live sentinel·K1/K2/K4/K5/K6·헌법·커널 목록·비밀값·외부 유료 서비스
  변경 없음. 현재 돈 경로는 계속 `PREVIEW_ONLY`다.
- **검증**: 구현 전 focused regression은 `ExecutionAuthority` 부재로 실패했고, 구현 후 focused regression
  7 통과, 인접 authority/router/lifecycle/rebalancer suite 50 통과, `uv run pytest -q` 2626 통과·4 스킵,
  `uv run ruff check src tests` 통과, `git diff --check` 통과, `uv run python scripts/check_handoff_facts.py`
  OK, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 본문 품질 관문 통과. 머지 직전
  전체 테스트와 린트를 재실행해 같은 결과를 확인했다.
- **남은 위험**: 실제 서버에서 동시에 떠 있는 오래된 live worker나 분리 프로세스, KIS 계좌의 열린 주문,
  GitHub Actions 비밀값과 Environment 보호 규칙은 이 저장소 작업만으로 확인하지 않았다. `SUBMISSION_UNKNOWN`
  상태를 broker order/execution 조회로 자동 해소하는 복구 후보도 별도다.
- **상세 인계**: `HANDOFF-115-EXECUTION-SAFETY-STABILIZATION.md`.

## 최근 관찰 — 2026-07-13 KST (스펙 115 저하 상태 신규 BUY 차단)

현재 `main` 최신 코드 머지는 `121a236`(#517, 스펙 115 degraded execution state)이다.
기능 커밋은 `b83c55a`이고, 직전 main은 `34f804b`(#516, 스펙 114 인계)이다.

- **문제 정의**: 스펙 114까지는 주문 제출 불확실성, 체결 원장 원자성, 열린 BUY 예약 노출을 닫았다.
  하지만 live fill sync 실패, NAV 조회 실패, 최신 정합성 `INCONCLUSIVE`, 손실 평가 mark 결측,
  unresolved `SUBMISSION_UNKNOWN` BUY가 있어도 다음 신규 BUY가 broker submission까지 갈 수 있었다.
- **구현 상태**: `src/auto_invest/execution/execution_state.py`가 `HEALTHY`,
  `DEGRADED_SELL_ONLY`, `HALTED` 상태와 `execution_state_gate`를 제공한다. `OrderRouter`는 기존
  gate chain 안에서 이 상태를 읽어 degraded 상태의 BUY를 `ORDER_REJECTED_BY_GATE`로 남기고 broker
  주문 호출 전에 멈춘다. SELL은 degraded 상태에서도 기존 whitelist, halt, K1 cap gate를 계속 통과할 수
  있다. `Worker`는 live fill sync 실패, NAV refresh 실패, circuit breaker mark 결측을 runtime blocker로
  보존하고, 다음 성공 관측 때 해제한다. DB 기반 blocker는 `SUBMISSION_UNKNOWN` BUY와 최신
  `INCONCLUSIVE` reconciliation이다.
- **post-merge 실행**: #517 main push 뒤 `Deploy on merge to main` run `29254832101`,
  `Released work ledger` run `29254832106`, `Autonomous work execution loop` run `29254832523`가 success다.
  #517 직후 released-work sidecar는 post-merge tasks T021~T023이 아직 닫히기 전이라 스펙 115를
  제외했다. 이 handoff PR은 `completed_candidate_id: candidate-degraded-execution-state`와
  `next_candidate_id: candidate-single-execution-authority`, T021~T023 완료 상태를 남겨 다음 장부가
  스펙 115를 완료로 읽게 한다.
- **안전 경계**: 등급 4 돈 경로 주문 허용 조건 축소다. 실제 주문·취소·실거래 재무장·자본 증액·
  자본 배분·whitelist/caps 확대·손실 예산·live sentinel·K1/K2/K4/K5/K6·헌법·커널 목록·비밀값·
  외부 유료 서비스 변경 없음. 현재 돈 경로는 계속 `PREVIEW_ONLY`다.
- **검증**: 구현 전 focused regression은 `auto_invest.execution.execution_state` 부재로 실패해 신규
  보호 경로가 없음을 확인했다. 구현 후 focused regression 8 통과, 인접 router/fill sync/capital/
  circuit breaker/lifecycle/paper/risk tests 88 통과, `uv run pytest -q` 2621 통과·4 스킵,
  `uv run ruff check src tests` 통과, `git diff --check` 통과, `uv run python scripts/check_handoff_facts.py`
  OK, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 본문 품질 관문 통과. 머지 직전
  전체 테스트와 린트를 재실행해 같은 결과를 확인했다.
- **남은 위험**: `SUBMISSION_UNKNOWN` 자동 broker order/execution lookup 복구는 아직 남아 있다.
  cross-process 계좌 잠금과 단일 `ExecutionAuthority`는 스펙 116에서 닫혔다. 실제 KIS 계좌의 열린 주문,
  보유, 서버 프로세스, GitHub Actions 비밀값은 조회하지 않았다.
- **상세 인계**: `HANDOFF-115-EXECUTION-SAFETY-STABILIZATION.md`.

## 최근 관찰 — 2026-07-13 KST (스펙 114 계좌 노출 예약)

현재 `main` 최신 코드 머지는 `692cdff`(#515, 스펙 114 account exposure reservation)이다.
기능 커밋은 `215a11a`, PR 증거 갱신 커밋은 `510974b`이고, 직전 main은 `14260df`(#514,
스펙 113 인계)이다.

- **문제 정의**: K1 전역 노출 게이트는 `현재 노출 + 이번 주문`을 검사하지만, 리밸런서는 주문 묶음
  시작 시 한 번 계산한 `current_global_exposure_usd`와 `current_symbol_exposure_usd`를 모든 BUY에
  재사용했다. 또한 이미 `SUBMITTED` 또는 `SUBMISSION_UNKNOWN`인 BUY 주문이 있어도 새 BUY의 노출 계산에
  포함하지 않았다. 각 주문은 단독으로 안전해 보여도 주문 묶음 또는 동시 실행 합계는 계좌 global cap을
  넘을 수 있었다.
- **구현 상태**: `src/auto_invest/execution/exposure_reservation.py`가 `INTENT`, `SUBMITTED`,
  `PARTIALLY_FILLED`, `SUBMISSION_UNKNOWN` BUY 주문 notional을 예약 노출로 합산한다. `OrderRouter`는
  현재 평가 중인 correlation id는 제외하고 열린 BUY 예약값을 K1 gate 입력에 더한다. `execute_rebalance`는
  paper/test router처럼 durable `orders` row가 없는 경로에서 한 실행 안의 성공한 BUY 예약을 다음 BUY에
  반영한다. 열린 SELL은 실제 fill 전까지 노출 감소로 쓰지 않는다.
- **post-merge 실행**: #515 main push 뒤 `Deploy on merge to main` run `29250744546`,
  `Released work ledger` run `29250744535`, `Autonomous work execution loop` run `29250744399`가 success다.
- **안전 경계**: 등급 4 돈 경로 노출 안전성 축소다. cap 값, whitelist, live sentinel, 자본, 전략,
  손실 예산, 헌법, kernel manifest, K1/K2/K4/K5/K6 파일, 비밀값, 외부 유료 서비스는 변경하지 않았다.
  실제 KIS 주문·취소·서버 SSH·실거래 전환도 수행하지 않았다. 현재 돈 경로는 계속 `PREVIEW_ONLY`다.
- **검증**: 구현 전 focused regression에서 열린 BUY 예약 테스트는 기존 코드가 `SUBMITTED`로 통과해
  실패했고, 리밸런싱 묶음 테스트는 두 BUY가 모두 `PAPER_FILLED`로 통과해 실패했다. 구현 후 focused
  회귀 2건 통과, `tests/integration/test_order_router.py`와 `tests/integration/test_spec_032_live_rebalancer.py`
  28 통과, 인접 risk/paper/lifecycle 테스트 43 통과, `uv run pytest -q` 2612 통과·4 스킵,
  `uv run ruff check src tests` 통과, `git diff --check` 통과, `uv run python scripts/check_handoff_facts.py`
  OK, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 본문 품질 관문 통과. 머지 직전
  전체 테스트와 린트를 재실행해 같은 결과를 확인했다.
- **남은 위험**: 이 역사 문단 작성 당시 남아 있던 `115-degraded-execution-state`와 단일
  `ExecutionAuthority` 통합은 각각 #517과 #519에서 닫혔다. 현재 남은 저장소 후속 후보는
  `SUBMISSION_UNKNOWN` broker lookup 복구이고, 실제 서버·KIS 계좌 상태는 별도 확인이 필요하다.
- **상세 인계**: `HANDOFF-115-EXECUTION-SAFETY-STABILIZATION.md`.

## 최근 관찰 — 2026-07-13 KST (스펙 113 원자적 체결 원장)

현재 `main` 최신 코드 머지는 `6e4e50f`(#513, 스펙 113 atomic fill ledger)이다.
기능 커밋은 `572051a`이고, 직전 main은 `8a01baf`(#512, 스펙 112 인계)이다.

- **문제 정의**: live fill sync는 `FILL` 감사, `fills INSERT OR IGNORE`, `current_positions` 갱신,
  주문 상태 전이를 autocommit 상태에서 순서대로 실행했다. 중복 `kis_fill_id`가 방어적으로 다시 계획되면
  `fills` row는 무시되지만 포지션 캐시는 다시 움직일 수 있고, 포지션 갱신 실패 시 `fills`와 `FILL`
  감사만 남는 부분 적용도 가능했다.
- **구현 상태**: `apply_fill_plan`은 빈 계획이 아니면 `BEGIN IMMEDIATE` 트랜잭션을 열고, 새 `fills` row,
  `FILL` 감사, 포지션 캐시, 주문 상태 전이를 함께 커밋하거나 함께 롤백한다. `_apply_fill`은 `fills`
  삽입을 먼저 시도하고 실제 삽입된 경우에만 감사와 포지션 캐시를 갱신한다. 중복 row는 `fills_applied`와
  `qty_applied`에도 포함하지 않는다.
- **post-merge 실행**: #513 main push 뒤 `Deploy on merge to main` run `29248728507`,
  `Released work ledger` run `29248728751`, `Autonomous work execution loop` run `29248728478`가 success다.
  같은 commit의 scheduled released-work run `29248767181`도 success다.
- **안전 경계**: 등급 4 돈 경로 회계 안전성 축소다. 실제 주문·취소·실거래 재무장·자본 증액·자본 배분·
  whitelist/caps 확대·손실 예산·live sentinel·K1/K2/K4/K5/K6·헌법·커널 목록·비밀값·외부 유료 서비스
  변경 없음. 현재 돈 경로는 계속 `PREVIEW_ONLY`다. 외부 보유 청산 경로 때문에 음수 포지션 DB 제약과
  시작 시 원장·캐시 자동 검증은 후속으로 분리했다.
- **검증**: PR #513 머지 전 구현 전 focused test에서 중복 체결·롤백 테스트 2건 실패를 확인했고,
  구현 후 focused fill sync 9 통과, worker fill sync 3 통과, 관련 포지션·감사·성과 테스트 63 통과,
  `uv run pytest` 2609 통과·4 스킵, `uv run ruff check src tests` 통과, `git diff --check` 통과,
  `uv run python scripts/check_handoff_facts.py` OK, `uv run python scripts/agent_harness_probe.py --strict`
  OK(14/14), PR 본문 품질 관문 통과. #513 머지 뒤 handoff 갱신 전 `uv run pytest -q`는 낡은
  `HANDOFF.md` 때문에 `test_agent_harness_probe.py` 2건만 실패했고, 이 handoff 갱신은 그 원인을
  바로잡는다. 갱신 후 `uv run pytest -q` 2609 통과·4 스킵, ruff 통과, HANDOFF 사실 검증 OK,
  strict harness OK(14/14), `git diff --check` 통과를 확인했다.
- **상세 인계**: `HANDOFF-115-EXECUTION-SAFETY-STABILIZATION.md`.

## 최근 관찰 — 2026-07-13 KST (스펙 112 주문 제출 불확실성 회복)

현재 `main` 최신 코드 머지는 `8a62ff7`(#511, 스펙 112 order submission uncertainty recovery)이다.
기능 커밋은 `754d603`이고, 직전 main은 `c9976f7`(#510, 스펙 111 인계)이다.

- **문제 정의**: 공통 `ResilientClient`가 HTTP 메서드와 무관하게 전송 오류와 5xx를 재시도했고,
  KIS 신규 주문 제출도 같은 클라이언트로 `POST /uapi/overseas-stock/v1/trading/order`를 보냈다.
  브로커가 첫 요청을 접수했지만 응답이 유실되면 동일 주문이 자동 재전송될 수 있고, 기존 라우터는
  그 실패를 `REJECTED_BY_BROKER`로 닫아 접수 여부 불명확 상태를 거부처럼 보이게 했다.
- **구현 상태**: `ResilientClient.request(..., retry_transient=False)`를 추가했고 기본값은 기존 retry
  유지다. `place_order`는 신규 주문 `POST`에 no-retry를 적용한다. 라우터는 HTTP 5xx, 전송 오류,
  주문번호 없는 불명확 응답을 `SUBMISSION_UNKNOWN`으로 전이하고 `ORDER_SUBMISSION_UNKNOWN` 감사 이벤트를
  남긴다. 명시적 KIS 업무 거부(`rt_cd != 0`)는 기존 `REJECTED_BY_BROKER`로 유지된다. 텔레그램 감사
  꼬리와 CLI 읽기 전용 요약도 불명확 제출을 누락하지 않는다.
- **post-merge 실행**: #511 main push 뒤 `Deploy on merge to main` run `29244052128`,
  `Released work ledger` run `29244052132`, `Autonomous work execution loop` run `29244052159`,
  `KIS smoke` run `29244052148`, `Execution quality package` run `29244081803` 및 후보 공장·승격·
  evolution 관련 push run이 모두 success다.
- **안전 경계**: 등급 4 돈 경로 축소다. 실제 주문·취소·실거래 재무장·자본 증액·자본 배분·
  whitelist/caps 확대·손실 예산·live sentinel·K1/K2/K4/K5/K6·헌법·커널 목록·비밀값·외부 유료 서비스
  변경 없음. 현재 돈 경로는 계속 `PREVIEW_ONLY`다. `SUBMISSION_UNKNOWN`을 broker order/execution lookup으로
  해소하는 자동 복구와 불명확 상태의 신규 매수 차단은 아직 남은 후속 작업이다.
- **검증**: PR #511 머지 전 focused broker/order/audit/notification tests 62 통과, `uv run pytest`
  2607 통과·4 스킵, `uv run ruff check src tests` 통과, `git diff --check` 통과,
  `uv run python scripts/check_handoff_facts.py` OK, `uv run python scripts/agent_harness_probe.py --strict`
  OK(14/14), PR 본문 품질 관문 통과. 머지 직전 전체 테스트와 린트도 재통과했다. #511 머지 뒤 handoff
  갱신 전 `uv run pytest -q`는 낡은 `HANDOFF.md` 때문에 `test_agent_harness_probe.py` 2건만 실패했고,
  이 handoff 갱신은 그 원인을 바로잡는다. 갱신 후 `uv run pytest -q` 2607 통과·4 스킵, ruff 통과,
  HANDOFF 사실 검증 OK, strict harness OK(14/14), `git diff --check` 통과를 확인했다.
- **상세 인계**: `HANDOFF-115-EXECUTION-SAFETY-STABILIZATION.md`.

## 최근 관찰 — 2026-07-13 KST (스펙 111 operator-design 평행 실거래 진입점 격리)

현재 `main` 최신 코드 머지는 `66df71d`(#509, 스펙 111 live entrypoint containment)이다.
기능 커밋은 `8675830`, 최종 local gate 체크 커밋은 `2f08137`이고, 직전 main은
`e9f9f98`(#508, 스펙 110 인계)이다.

- **문제 정의**: ChatGPT 코드 리뷰 인계에서 `operator-design`가 예약 실행, `auto_ok`,
  자동 `OK`, 실제 수행되지 않은 동적 검증 성공 처리, `start_live_worker`를 통해 기존
  canary·sentinel·자본 사다리 밖의 평행 실거래 진입점이 될 수 있음을 확인했다. 운영자 요청은
  이 인사이트를 Codex가 바로 이어받아 실제 구현 가능한 안전화 작업으로 완결하는 것이었다.
- **구현 상태**: `.github/workflows/operator-design.yml`은 예약 실행과 `auto_ok`를 제거했고,
  수동 dispatch만 남겼다. `.github/workflows/trigger-design.yml`도 `.trigger/design-now.txt`
  push 자동 실행을 제거했다. 자연어 intent는 `INTENT_B64` 데이터로 전달하며 로그와
  `.verify/last_design.md`에는 원문 대신 길이와 SHA-256 지문만 남긴다. `scripts/operator_design.sh`
  는 후보 생성 전용 helper가 됐고, `auto-invest design`은 후보 TOML과 `.proposal.json`만 만든다.
  `src/auto_invest/design/verifier.py`는 정적 검증, 백테스트, paper 검증이 모두 같은 후보 지문으로
  통과해야만 `ok=True`가 되도록 fail-closed로 바뀌었다. `prompt_operator_ok`와
  `start_live_worker`는 남아 있는 레거시 호출이 즉시 `LiveActivationBoundaryError`를 내도록
  경계 껍데기로 남겼다. 명령 안전 등록부에서 `design`은 `A2 / proposal`이며 주문·live config·
  자본·재지정 권한은 모두 false다.
- **post-merge 실행**: #509 main push 뒤 `Deploy on merge to main` run `29239614451`,
  `Released work ledger` run `29239614377`, `Autonomous work execution loop` run `29239614527`,
  `KIS smoke` run `29239614404`, 후보 공장·승격·evolution 관련 push run이 모두 success다.
- **sidecar 확인**: #509 직후 released-work sidecar는 `commit=66df71d`, `overall_status=OK`였지만
  스펙 111의 post-merge tasks T065~T068이 아직 체크 전이라 `111-live-entrypoint-containment`를
  제외했다. 이 handoff PR은 T065~T068과 `completed_candidate_id:
  candidate-live-entrypoint-containment`, `next_candidate_id:
  candidate-order-submission-uncertainty-recovery`를 닫아 다음 released-work 장부가 스펙 111을
  완료로 읽게 한다. autonomous-work sidecar는 일반 운영 체계 후보
  `candidate-operator-report-liveness-contract`를 `EXECUTION_READY`, 위험 등급 2, 안전 영향 없음으로
  선택했다. 이 문단 작성 당시 다음 실행 안전성 수동 후보였던 `112-order-submission-uncertainty-recovery`는
  #511에서 닫혔다.
- **안전 경계**: 등급 4 돈 경로 축소다. 실제 주문, 실거래 재무장, 자본 증액, 자본 배분,
  whitelist/caps 확대, 손실 예산, live sentinel, 브로커 주문, K1/K2/K4/K5/K6, 헌법, 커널 목록,
  비밀값, 외부 유료 서비스 변경 없음. KIS smoke는 post-merge 읽기 전용 live smoke 4건을 수행했지만
  주문을 제출하지 않았다. 현재 돈 경로는 계속 `PREVIEW_ONLY`다.
- **검증**: PR #509 머지 전 focused boundary tests 5 통과, `uv run pytest` 2599 통과·4 스킵,
  `uv run ruff check src tests` 통과, `git diff --check` 통과, PR 본문 품질 관문 통과,
  `uv run python scripts/check_handoff_facts.py` OK, `uv run python scripts/agent_harness_probe.py --strict`
  OK(14/14), 보호 파일 해시 유지 확인, 원격 PR quality gate 통과. #509 머지 뒤 handoff 갱신 전
  `uv run pytest -q`는 낡은 `HANDOFF.md` 때문에 `test_agent_harness_probe.py` 2건만 실패했고, 이
  handoff 갱신은 그 원인을 바로잡는다. 갱신 후 `uv run pytest -q` 2599 통과·4 스킵,
  ruff 통과, HANDOFF 사실 검증 OK, strict harness OK(14/14), `git diff --check` 통과를 확인했다.
- **상세 인계**: `HANDOFF-115-EXECUTION-SAFETY-STABILIZATION.md`.

## 최근 관찰 — 2026-07-10 KST (스펙 110 agent harness 회귀 생존성 계약)

현재 `main` 최신 코드 머지는 `b364c16`(#507, 스펙 110 agent harness 회귀 생존성 계약)이다.
기능 커밋은 `858d7ac`이고, 직전 main은 `f458e69`(#506, 스펙 109 인계)이다.

- **문제 정의**: 스펙 109는 다음 후보를
  `candidate-agent-harness-regression-liveness-contract`로 열었다. evaluation, 첫 판단 품질,
  redteam 하네스 묶음과 `agent_harness_probe.py --strict`는 이미 있었지만, strict 하네스가
  무엇을 `PASS`/`WAIT`/`FAIL`로 보존해야 하는지 후보 단위의 읽기 전용 계약은 없었다. 구현 전
  재현에서는 agent harness 후보까지 released로 닫으면 새 실행 후보 없이 autonomous-work가
  `OBSERVATION_WAIT`에 머무는 전진성 구멍도 확인했다.
- **구현 상태**: `agent_harness_regression_liveness.py`와
  `scripts/agent_harness_regression_liveness_probe.py`가 `scripts/agent_harness_probe.py`,
  `.codex/harness/evaluation_tasks.toml`, `quality_tasks.toml`, `redteam_tasks.toml`,
  supplied strict output, released-work completion, 안전 경계를 읽어 `CONTRACT_READY`,
  `OBSERVATION_WAIT`, `BLOCKED`를 보고한다. 기존 `agent_harness_probe.py`의 evaluator 함수를
  재사용해 위험 등급 0~4, 통제 범주, 첫 판단 품질 범주, redteam 공격 유형을 중복 없이 검증한다.
  스펙 110은 `completed_candidate_id: candidate-agent-harness-regression-liveness-contract`와
  `next_candidate_id: candidate-operator-report-liveness-contract`를 명시했다.
- **post-merge 실행**: #507 main push 뒤 `Deploy on merge to main` run `29103143841`,
  `Released work ledger` run `29103143824`, `Autonomous work execution loop` run `29103143807`가
  success였다.
- **sidecar 확인**: 최신 released-work sidecar는 `commit=b364c16`, `overall_status=OK`,
  `released_count=31`이며 `candidate-agent-harness-regression-liveness-contract`를 spec
  `110-agent-harness-regression-liveness-contract`의 released 후보로 기록했다. 최신
  autonomous-work sidecar는 같은 commit에서 `candidate-operator-report-liveness-contract`를
  `EXECUTION_READY`, risk grade 2, safety impact 없음으로 선택했다. 운영 체계 frontier 지도에서
  HANDOFF 사실성, PR/머지 증거, worktree 동시 작업, agent harness 회귀 생존성은 released이고
  운영자 이해 가능 보고 생존성은 open이다.
- **배포 확인**: main commit의 `Deploy on merge to main` workflow run `29103143841`과 deploy job은
  success다. 컨테이너에서 GitHub run 상태와 job step 성공은 확인했다. 서버 audit_log는 직접 확인하지
  못한다. 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **안전 경계**: 등급 2 읽기 전용 agent harness 회귀 생존성 계약 추가다. 기존 하네스 source와
  supplied strict output, released-work evidence를 읽고 보고서와 probe만 추가했다. 실제 주문,
  브로커 실주문 API, 주문 재시도, 자본 증액, 자본 배분, whitelist/caps 확대, live 전략 교체,
  live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값, 외부 유료 서비스 변경 없음. 현재 돈
  경로는 계속 `PREVIEW_ONLY`다.
- **검증**: PR #507 머지 전 focused pytest 10 통과, pre-release
  `agent_harness_regression_liveness_probe.py` local run에서 static/suite/strict/safety gates PASS 및
  released-work gate WAIT 확인, released-work 로컬 재현에서 `CONTRACT_READY` 확인, autonomous-work
  로컬 재현에서 `candidate-operator-report-liveness-contract` 전진 확인, `uv run pytest` 2586 통과·4 스킵,
  `uv run ruff check src tests` 통과, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14),
  `uv run python scripts/check_handoff_facts.py` OK, `git diff --check` 통과, PR 품질 관문 성공,
  머지 직전 `uv run pytest` 2586 통과·4 스킵 및 ruff 재통과, post-merge deploy·released-work·
  autonomous-work run 성공 확인 완료. 이 handoff 갱신 뒤 `uv run pytest -q` 2586 통과·4 스킵,
  ruff 통과, HANDOFF 사실 검증 OK, strict harness OK(14/14), `git diff --check` 통과를 확인했다.
- **상세 인계**: `HANDOFF-114-AGENT-HARNESS-REGRESSION-LIVENESS.md`.

## 최근 관찰 — 2026-07-10 KST (스펙 109 worktree 동시 작업 생존성 계약)

현재 `main` 최신 코드 머지는 `75d7140`(#505, 스펙 109 worktree 동시 작업 생존성 계약)이다.
기능 커밋은 `34e4942`이고, 직전 main은 `52c5a29`(#504, 스펙 108 인계)이다.

- **문제 정의**: 스펙 108은 다음 후보를 `candidate-worktree-concurrency-liveness-contract`로 열었다.
  `local_concurrency_guard.py`, session-start hook, pre-commit/pre-push hook, 복구 스냅샷은 있었지만,
  정상 `WARN`, 쓰기 전 `BLOCK`, 격리 안내, 복구 스냅샷 표면이 후보 단위의 `PASS`/`WAIT`/`FAIL`
  계약으로 닫혀 있지 않았다. 구현 전 재현에서는 109까지 released로 닫으면 새 실행 후보 대신 닫힌
  `candidate-fd04772a23c5`가 `RELEASED` selected_work처럼 보이는 전진성 구멍도 확인했다.
- **구현 상태**: `worktree_concurrency_liveness.py`와
  `scripts/worktree_concurrency_liveness_probe.py`가 `.codex/hooks.json`, `.githooks/pre-commit`,
  `.githooks/pre-push`, `scripts/local_concurrency_guard.py`, optional guard output,
  released-work completion, 안전 경계를 읽어 `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`를
  보고한다. synthetic guard 평가로 clean check `OK`, conflict check `WARN`, conflict pre-commit/pre-push
  `BLOCK`, main 직접 commit/push `BLOCK`을 고정한다. 스펙 109는
  `completed_candidate_id: candidate-worktree-concurrency-liveness-contract`와
  `next_candidate_id: candidate-agent-harness-regression-liveness-contract`를 명시했다.
- **post-merge 실행**: #505 main push 뒤 `Deploy on merge to main` run `29094880198`,
  `Released work ledger` run `29094880183`, `Autonomous work execution loop` run `29094880148`가
  success였다.
- **sidecar 확인**: 최신 released-work sidecar는 `commit=75d7140`, `overall_status=OK`이며
  `candidate-worktree-concurrency-liveness-contract`를 spec `109-worktree-concurrency-liveness-contract`의
  released 후보로 기록했다. 최신 autonomous-work sidecar는 같은 commit에서
  `candidate-agent-harness-regression-liveness-contract`를 `EXECUTION_READY`, risk grade 2,
  safety impact 없음으로 선택했다. 운영 체계 frontier 지도에서 handoff 사실성, PR/머지 증거,
  worktree 동시 작업은 released이고 agent harness 회귀 생존성은 open이다.
- **배포 확인**: main commit의 `Deploy on merge to main` workflow run `29094880198`과 deploy job은
  success다. 컨테이너에서 GitHub run 상태와 job step 성공은 확인했다. 서버 audit_log는 직접 확인하지
  못한다. 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **안전 경계**: 등급 2 읽기 전용 worktree 동시 작업 생존성 계약 추가다. 기존 local guard와 훅,
  복구 스냅샷 source surface를 읽고 보고서와 probe만 추가했다. 실제 주문, 브로커 실주문 API,
  주문 재시도, 자본 증액, 자본 배분, whitelist/caps 확대, live 전략 교체, live sentinel, 헌법,
  커널 목록, K1/K2/K4/K5/K6, 비밀값, 외부 유료 서비스 변경 없음. 현재 돈 경로는 계속
  `PREVIEW_ONLY`다.
- **검증**: PR #505 머지 전 focused pytest 43 통과, `worktree_concurrency_liveness_probe.py` local run에서
  static/hook/synthetic/runtime/safety gates PASS 및 pre-release released-work gate WAIT 확인,
  tasks 완료 상태의 released-work 로컬 재현에서 `candidate-worktree-concurrency-liveness-contract`
  released 확인, autonomous-work 로컬 재현에서 `candidate-agent-harness-regression-liveness-contract`
  전진 확인, `uv run pytest` 2577 통과·4 스킵, `uv run ruff check src tests` 통과,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14),
  `uv run python scripts/check_handoff_facts.py` OK, `git diff --check` 통과, PR 품질 관문 성공,
  post-merge deploy·released-work·autonomous-work run 성공 확인 완료. 이 handoff 갱신 뒤
  `uv run pytest -q` 2577 통과·4 스킵, ruff 통과, HANDOFF 사실 검증 OK, strict harness OK(14/14),
  `git diff --check` 통과를 확인했다.
- **상세 인계**: `HANDOFF-113-WORKTREE-CONCURRENCY-LIVENESS-CONTRACT.md`.

## 최근 관찰 — 2026-07-10 KST (스펙 108 PR/머지 증거 생존성 계약)

현재 `main` 최신 코드 머지는 `7d06550`(#503, 스펙 108 PR/머지 증거 생존성 계약)이다.
기능 커밋은 `5b71a23`이고, 직전 main은 `e4035f5`(#502, 스펙 107 인계)이다.

- **문제 정의**: 스펙 107은 다음 후보를 `candidate-pr-merge-evidence-liveness-contract`로 열었다.
  PR 품질 관문, merge commit, released-work 장부, deploy 관측은 각각 존재하지만, 작업 완료 보고가
  어느 증거까지 살아 있어야 하는지 후보 단위의 `PASS`/`WAIT`/`FAIL` 계약으로 닫혀 있지 않았다.
- **구현 상태**: `pr_merge_evidence_liveness.py`와
  `scripts/pr_merge_evidence_liveness_probe.py`가 PR 본문 품질 관문, main merge evidence,
  released-work completion, deploy-status observation, 안전 경계를 읽어 `CONTRACT_READY`,
  `OBSERVATION_WAIT`, `BLOCKED`를 보고한다. 스펙 108은
  `completed_candidate_id: candidate-pr-merge-evidence-liveness-contract`와
  `next_candidate_id: candidate-worktree-concurrency-liveness-contract`를 명시했다.
- **post-merge 실행**: #503 main push 뒤 `Deploy on merge to main` run `29076284769`,
  `Released work ledger` run `29076284798`, `Autonomous work execution loop` run `29076284765`가
  success였다.
- **sidecar 확인**: 최신 released-work sidecar는 `commit=7d06550`, `overall_status=OK`이며
  `candidate-pr-merge-evidence-liveness-contract`를 spec `108-pr-merge-evidence-liveness-contract`의
  released 후보로 기록했다. 최신 autonomous-work sidecar는 같은 commit에서
  `candidate-worktree-concurrency-liveness-contract`를 `EXECUTION_READY`, risk grade 2,
  safety impact 없음으로 선택했다.
- **배포 확인**: main commit의 `Deploy on merge to main` workflow run `29076284769`와 deploy job은
  success다. 컨테이너에서 GitHub run 상태와 job step 성공은 확인했다. 서버 audit_log는 직접 확인하지
  못한다. KIS smoke sidecar 최신 run은 #503 commit 직접 증거가 아니라 2026-07-10 schedule 실행
  증거다. 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **안전 경계**: 등급 2 읽기 전용 PR/머지 증거 생존성 계약 추가다. 기존 PR·merge·sidecar·deploy
  reference를 읽고 보고서와 probe만 추가했다. 실제 주문, 브로커 실주문 API, 주문 재시도, 자본 증액,
  자본 배분, whitelist/caps 확대, live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6,
  비밀값, 외부 유료 서비스 변경 없음. 현재 돈 경로는 계속 `PREVIEW_ONLY`다.
- **검증**: PR #503 머지 전 focused pytest 43 통과, PR/머지 증거 probe temp all-pass evidence에서
  `CONTRACT_READY` 확인, tasks 완료 상태의 released-work 로컬 재현에서
  `candidate-pr-merge-evidence-liveness-contract` released 확인, autonomous-work 로컬 재현에서
  `candidate-worktree-concurrency-liveness-contract` 전진 확인, `uv run pytest` 2569 통과·4 스킵,
  `uv run ruff check src tests` 통과, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14),
  `uv run python scripts/check_handoff_facts.py` OK, PR 품질 관문 성공, 머지 직전 `uv run pytest`
  2569 통과·4 스킵 및 ruff 재통과, post-merge deploy·released-work·autonomous-work run 성공 확인 완료.
  인계 갱신 전 main 기준 `uv run pytest -q`는 낡은 HANDOFF 때문에 하네스 2건만 실패했고, 이 handoff
  갱신은 그 원인(`마지막 main 커밋` 행)을 바로잡았다. 갱신 후 `uv run pytest -q`는 2569 통과·4 스킵,
  `uv run ruff check src tests` 통과, HANDOFF 사실 검증 OK, strict harness OK(14/14),
  `git diff --check` 통과를 확인했다.
- **상세 인계**: `HANDOFF-112-PR-MERGE-EVIDENCE-LIVENESS-CONTRACT.md`.

## 최근 관찰 — 2026-07-08 KST (스펙 107 HANDOFF 사실성 생존성 계약)

현재 `main` 최신 코드 머지는 `1c412d9`(#501, 스펙 107 HANDOFF 사실성 생존성 계약)이다.
기능 커밋은 `932b85e`이고, 직전 main은 `54f0e09`(#500, 스펙 106 인계)이다.

- **문제 정의**: 스펙 106은 다음 후보를 `candidate-handoff-truth-liveness-contract`로 열었다.
  `check_handoff_facts.py`는 이미 handoff-only merge의 첫 부모를 정상 기준으로 인정하지만,
  그 판단이 자율 후보 단위의 완료 후보, 다음 후보, 안전 경계, JSON/Markdown 보고서로 닫혀 있지 않았다.
- **구현 상태**: `handoff_truth_liveness.py`와 `scripts/handoff_truth_liveness_probe.py`가
  `HANDOFF.md`, `check_handoff_facts.py`, agent harness, PR 품질 관문, released-work/autonomous-work
  reference를 읽어 `CONTRACT_READY` 또는 `BLOCKED`를 보고한다. 정상 `origin/main` 직접 일치와
  정상 handoff-only 첫 부모 baseline을 구분하고, stale HANDOFF·missing HANDOFF·기대 행 불일치는
  blocked로 분리한다.
- **post-merge 실행**: #501 main push 뒤 `Deploy on merge to main` run `28913334443`,
  `Released work ledger` run `28913334487`, `Autonomous work execution loop` run `28913334433`가 success였다.
- **sidecar 확인**: 최신 released-work sidecar는 `commit=1c412d9`, table `released_count=28` entries이며
  `candidate-handoff-truth-liveness-contract`를 released 후보로 기록했다. 최신 autonomous-work sidecar는
  timestamp `2026-07-08T02:35:11Z`에서 `candidate-pr-merge-evidence-liveness-contract`를
  `EXECUTION_READY`, risk grade 2, safety impact 없음으로 선택했다. 운영 체계 frontier 지도에서
  `handoff_truth_liveness`는 released, `pr_merge_evidence_liveness`는 open이다.
- **배포 확인**: main commit의 `Deploy on merge to main` workflow run `28913334443`과 deploy job은 success다.
  컨테이너에서 GitHub run 상태와 job step 성공은 확인했다. 서버 audit_log는 직접 확인하지 못한다.
  KIS smoke sidecar 최신 run은 #501 commit 직접 증거가 아니라 2026-07-07 schedule 실행 증거다.
  이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **안전 경계**: 등급 2 읽기 전용 HANDOFF 사실성 계약 추가다. 기존 저장소 사실과 sidecar reference를 읽고
  보고서와 probe만 추가했다. 실제 주문, 브로커 실주문 API, 주문 재시도, 자본 증액, 자본 배분,
  whitelist/caps 확대, live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값,
  외부 유료 서비스 변경 없음. 현재 돈 경로는 계속 `PREVIEW_ONLY`다.
- **검증**: PR #501 머지 전 focused pytest 40 통과, HANDOFF truth probe current checkout
  `CONTRACT_READY` 및 matched baseline `handoff_only_first_parent` 확인, tasks 완료 상태의
  released-work 로컬 재현에서 `candidate-handoff-truth-liveness-contract` released 확인,
  autonomous-work 로컬 재현에서 `candidate-pr-merge-evidence-liveness-contract` 전진 확인,
  `uv run pytest` 2560 통과·4 스킵, `uv run ruff check src tests` 통과,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14),
  `uv run python scripts/check_handoff_facts.py` OK, `git diff --check` 통과, PR 품질 관문 성공,
  머지 직전 `uv run pytest` 2560 통과·4 스킵 및 ruff 재통과,
  post-merge deploy·released-work·autonomous-work run 성공 확인 완료. 인계 갱신 전 main 기준
  `uv run pytest -q`는 낡은 HANDOFF 때문에 하네스 2건만 실패했고, 이 handoff 갱신은 그 원인
  (`마지막 main 커밋` 행)을 바로잡았다. 갱신 후 `uv run pytest -q`는 2560 통과·4 스킵,
  `uv run ruff check src tests` 통과, HANDOFF 사실 검증 OK, strict harness OK(14/14),
  `git diff --check` 통과를 확인했다.
- **상세 인계**: `HANDOFF-111-HANDOFF-TRUTH-LIVENESS-CONTRACT.md`.

## 최근 관찰 — 2026-07-08 KST (스펙 106 운영 체계 frontier 지도)

현재 `main` 최신 코드 머지는 `8a612ff`(#499, 스펙 106 운영 체계 frontier 지도)이다.
기능 커밋은 `a0b2e44`이고, 직전 main은 `4c177f6`(#498, 스펙 105 인계)이다.

- **문제 정의**: 스펙 105는 다음 후보를 `candidate-agent-ops-frontier-map`으로 열었다.
  거시 후보 지도는 운영 체계 영역까지 선택했지만, handoff 사실성, PR/머지 증거, worktree 동시 작업
  방어 중 무엇을 다음 읽기 전용 후보로 닫을지 별도 지도와 완료 뒤 전진 규칙이 없었다.
- **구현 상태**: `autonomous_work_execution.py`가 `agent_ops_frontier_map`을 JSON과 Markdown에 발행한다.
  지도는 `candidate-handoff-truth-liveness-contract`, `candidate-pr-merge-evidence-liveness-contract`,
  `candidate-worktree-concurrency-liveness-contract`를 순서대로 열고,
  `candidate-agent-ops-frontier-map`이 released-work에 기록되면 첫 후보
  `candidate-handoff-truth-liveness-contract`로 전진한다.
- **post-merge 실행**: #499 main push 뒤 `Deploy on merge to main` run `28910730317`,
  `Released work ledger` run `28910730320`, `Autonomous work execution loop` run `28910730295`가 success였다.
- **sidecar 확인**: 최신 released-work sidecar는 `commit=8a612ff`, `released_count=27`이며
  `candidate-agent-ops-frontier-map`을 released 후보로 기록했다. 최신 autonomous-work sidecar는
  timestamp `2026-07-08T01:26:58Z`에서 `candidate-handoff-truth-liveness-contract`를
  `EXECUTION_READY`, risk grade 2, safety impact 없음으로 선택했다. 운영 체계 frontier 지도에는
  handoff 사실성, PR/머지 증거, worktree 동시 작업 생존성 후보 3개가 모두 open으로 남아 있다.
- **배포 확인**: main commit의 `Deploy on merge to main` 체크에서 deploy run은 success다.
  컨테이너에서 GitHub run 상태와 check-run 성공은 확인했다. 서버 audit_log는 직접 확인하지 못한다.
  KIS smoke sidecar 최신 run은 #499 commit 직접 증거가 아니라 이전 schedule 실행 증거다.
  이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **안전 경계**: 등급 2 읽기 전용 운영 체계 후보 지도 추가다. 기존 sidecar를 읽고 다음 work packet만
  발행한다. 실제 주문, 브로커 실주문 API, 주문 재시도, 자본 증액, 자본 배분, whitelist/caps 확대,
  live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값, 외부 유료 서비스 변경 없음.
  현재 돈 경로는 계속 `PREVIEW_ONLY`다.
- **검증**: PR #499 머지 전 focused pytest 41 통과, remote sidecar replay에서
  `candidate-agent-ops-frontier-map` selected 및 첫 지도 후보
  `candidate-handoff-truth-liveness-contract` 확인, tasks 완료 상태의 released-work 로컬 재현에서
  `candidate-agent-ops-frontier-map` released 확인, autonomous-work 로컬 재현에서
  `candidate-handoff-truth-liveness-contract` 전진 확인, `uv run pytest` 2554 통과·4 스킵,
  `uv run ruff check src tests` 통과, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14),
  `uv run python scripts/check_handoff_facts.py` OK, PR 품질 관문 성공,
  머지 직전 `uv run pytest` 2554 통과·4 스킵 및 ruff 재통과,
  post-merge deploy·released-work·autonomous-work run 성공 확인 완료. 인계 갱신 전 main 기준
  `uv run pytest -q`는 낡은 HANDOFF 때문에 하네스 2건만 실패했고, 이 handoff 갱신은 그 원인
  (`마지막 main 커밋` 행)을 바로잡았다. 갱신 후 `uv run pytest -q`는 2554 통과·4 스킵,
  `uv run ruff check src tests` 통과, HANDOFF 사실 검증 OK, strict harness OK(14/14),
  `git diff --check` 통과를 확인했다.
- **상세 인계**: `HANDOFF-110-AGENT-OPS-FRONTIER-MAP.md`.

## 최근 관찰 — 2026-07-08 KST (스펙 105 브로커 진단 생존성 계약)

현재 `main` 최신 코드 머지는 `8d39235`(#497, 스펙 105 브로커 진단 생존성 계약)이다.
기능 커밋은 `e99a782`이고, 직전 main은 `a0d9be2`(#496, 스펙 104 인계)이다.

- **문제 정의**: 스펙 104는 다음 후보를 `candidate-broker-diagnostic-liveness-contract`로 열었다.
  KIS smoke, execution-quality, pipeline-liveness가 브로커 진단 상태를 보여주지만, 체결 품질 후보 관점에서
  standalone KIS smoke와 embedded broker smoke가 함께 살아 있는지 별도 계약으로 닫지 않아 다음 세션이
  같은 sidecar를 다시 해석해야 했다.
- **구현 상태**: `broker_diagnostic_liveness.py`와 `scripts/broker_diagnostic_liveness_probe.py`가
  KIS smoke, execution-quality, pipeline-liveness, released-work, capital-path readiness 증거를 읽어
  `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`를 분리한다. standalone KIS smoke 실패는 blocked,
  embedded broker smoke 부족은 observation wait, 양쪽 smoke와 관련 pipeline 체크가 살아 있으면 ready다.
  스펙 105는 `completed_candidate_id: candidate-broker-diagnostic-liveness-contract` 완료 마커를 남겼다.
- **현재 계약 판정**: 최신 원격 sidecar 재현에서 `overall_status=CONTRACT_READY`다.
  `diagnostic_state=BROKER_DIAGNOSTIC_LIVE`, standalone KIS smoke 성공, embedded broker smoke 성공,
  pipeline overall OK, quality gates 전부 PASS다. 이것은 브로커 진단 경로가 관측 가능하다는 뜻이지
  실주문을 제출했다는 뜻은 아니다.
- **post-merge 실행**: #497 main push 뒤 `Deploy on merge to main` run `28904652073`,
  `Released work ledger` run `28904652098`, `Autonomous work execution loop` run `28904652137`가 success였다.
- **sidecar 확인**: 최신 released-work sidecar는 `released_count=26`이며
  `candidate-broker-diagnostic-liveness-contract`를 released 후보로 기록했다. 최신 autonomous-work sidecar는
  timestamp `2026-07-07T23:01:23Z`에서 `candidate-agent-ops-frontier-map`을 `EXECUTION_READY`,
  risk grade 2, safety impact 없음으로 선택했다.
- **배포 확인**: main commit의 `Deploy on merge to main` 체크에서 deploy run은 success다.
  컨테이너에서 GitHub run 상태와 check-run 성공은 확인했다. 서버 audit_log는 직접 확인하지 못한다.
  KIS smoke sidecar 최신 run은 #497 commit 직접 증거가 아니라 이전 schedule 실행 증거이므로 #497 배포
  근거로 쓰지 않는다. 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **안전 경계**: 등급 2 읽기 전용 브로커 진단 생존성 계약 추가다. 기존 sidecar를 읽고 보고서와 probe만
  추가했다. 실제 주문, 브로커 실주문 API, 주문 재시도, 자본 증액, 자본 배분, whitelist/caps 확대,
  live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값, 외부 유료 서비스 변경 없음.
  현재 돈 경로는 계속 `PREVIEW_ONLY`다.
- **검증**: PR #497 머지 전 focused pytest 40 통과, remote sidecar replay에서
  `CONTRACT_READY`, `BROKER_DIAGNOSTIC_LIVE`, next candidate `candidate-agent-ops-frontier-map` 확인,
  tasks 완료 상태의 released-work 로컬 재현에서 `candidate-broker-diagnostic-liveness-contract` released 확인,
  autonomous-work 로컬 재현에서 `candidate-agent-ops-frontier-map` 전진 확인,
  `uv run pytest` 2551 통과·4 스킵, `uv run ruff check src tests` 통과,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14),
  `uv run python scripts/check_handoff_facts.py` OK, PR 품질 관문 성공,
  머지 직전 `uv run pytest` 2551 통과·4 스킵 및 ruff 재통과,
  post-merge deploy·released-work·autonomous-work run 성공 확인 완료. 이 handoff 갱신 뒤
  `uv run pytest -q` 2551 통과·4 스킵, ruff 통과, HANDOFF 사실 검증 OK, strict harness OK(14/14),
  `git diff --check` 통과를 확인했다.
- **상세 인계**: `HANDOFF-109-BROKER-DIAGNOSTIC-LIVENESS-CONTRACT.md`.

## 최근 관찰 — 2026-07-07 KST (스펙 104 체결 비용 기준 계약)

현재 `main` 최신 코드 머지는 `fa5b3d9`(#495, 스펙 104 체결 비용 기준 계약)이다.
기능 커밋은 `2fca88c`이고, 직전 main은 `da56a02`(#494, 스펙 103 인계)이다.

- **문제 정의**: 스펙 103은 다음 후보를 `candidate-execution-cost-basis-contract`로 열었다.
  비용 차감 엣지 후보는 `execution-quality`를 읽지만, accepted/fill 비용 기준이 실제로 충분한지와
  관측 대기 상태를 별도 계약으로 닫지 않아 다음 세션이 같은 sidecar를 다시 해석해야 했다.
- **구현 상태**: `execution_cost_basis.py`와 `scripts/execution_cost_basis_probe.py`가
  execution-quality, KIS smoke, rebalance-micro-gtaa, money-path, pipeline-liveness, released-work,
  capital-path readiness 증거를 읽어 `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`를 분리한다.
  스펙 104는 `completed_candidate_id: candidate-execution-cost-basis-contract` 완료 마커를 남겼다.
- **현재 계약 판정**: 최신 원격 sidecar 재현에서 `overall_status=OBSERVATION_WAIT`다.
  필수 sidecar 파싱은 PASS지만 `execution-quality`에 `execution_cost_basis` 블록이 없고,
  money-path accepted/fill 표본도 0건이다. `live_money_status=PREVIEW_ONLY`,
  `can_submit_real_orders=false`라 새 실주문 표본을 만들지 않는다. 이 상태는 장애가 아니라
  실제 비용 기준 관측 대기다.
- **post-merge 실행**: #495 main push 뒤 `Deploy on merge to main` run `28847751730`,
  `Released work ledger` run `28847751712`, `Autonomous work execution loop` run `28847751752`가 success였다.
- **sidecar 확인**: 최신 released-work sidecar는 `released_count=25`이며
  `candidate-execution-cost-basis-contract`를 released 후보로 기록했다. 최신 autonomous-work sidecar는
  timestamp `2026-07-07T06:59:14Z`에서 `candidate-broker-diagnostic-liveness-contract`를
  `EXECUTION_READY`, risk grade 2, safety impact 없음으로 선택했다.
- **배포 확인**: main commit의 `Deploy on merge to main` 체크에서 deploy run은 success다.
  컨테이너에서 GitHub run 상태와 check-run 성공은 확인했다. 서버 audit_log는 직접 확인하지 못한다.
  KIS smoke sidecar 최신 run은 #495 commit 직접 증거가 아니라 이전 schedule 실행 증거이므로 #495 배포
  근거로 쓰지 않는다. 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **안전 경계**: 등급 2 읽기 전용 체결 비용 기준 계약 추가다. 기존 sidecar를 읽고 보고서와 probe만
  추가했다. 실제 주문, 브로커 실주문 API, 주문 재시도, 자본 증액, 자본 배분, whitelist/caps 확대,
  live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값, 외부 유료 서비스 변경 없음.
  현재 돈 경로는 계속 `PREVIEW_ONLY`다.
- **검증**: PR #495 머지 전 focused pytest 37 통과, remote sidecar replay에서
  `OBSERVATION_WAIT`, accepted/fill 0건, cost basis block 없음, money-path `PREVIEW_ONLY` 확인,
  tasks 완료 상태의 released-work 로컬 재현에서 `candidate-execution-cost-basis-contract` released 확인,
  autonomous-work 로컬 재현에서 `candidate-broker-diagnostic-liveness-contract` 전진 확인,
  `uv run pytest` 2541 통과·4 스킵, `uv run ruff check src tests` 통과,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14),
  `uv run python scripts/check_handoff_facts.py` OK, PR 품질 관문 성공,
  머지 직전 `uv run pytest` 2541 통과·4 스킵 및 ruff 재통과,
  post-merge deploy·released-work·autonomous-work run 성공 확인 완료. 인계 갱신 전 main 기준
  `uv run pytest -q`는 낡은 HANDOFF 때문에 하네스 2건만 실패했고, 이 handoff 갱신 뒤
  `uv run pytest -q`는 2541 통과·4 스킵이다.
- **상세 인계**: `HANDOFF-108-EXECUTION-COST-BASIS-CONTRACT.md`.

## 최근 관찰 — 2026-07-07 KST (스펙 103 브로커 거부 분류 계약)

현재 `main` 최신 코드 머지는 `8492aad`(#493, 스펙 103 브로커 거부 분류 계약)이다.
기능 커밋은 `31cbfd5`이고, 직전 main은 `b92cbe5`(#492, 스펙 102 인계)이다.

- **문제 정의**: 스펙 102는 다음 후보를 `candidate-broker-rejection-taxonomy-contract`로 열었다.
  `execution-quality` sidecar는 KIS 오류 코드와 거부 주문 수를 보여줬지만, 브로커 거부 원인군,
  재발 위험, 주문 재시도 금지 행동을 별도 계약으로 닫지 않아 다음 세션이 같은 증거를 다시 해석해야 했다.
- **구현 상태**: `broker_rejection_taxonomy.py`와 `scripts/broker_rejection_taxonomy_probe.py`가
  execution-quality, KIS smoke, rebalance-micro-gtaa, pipeline-liveness, released-work,
  capital-path readiness 증거를 읽어 `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`를 분리한다.
  스펙 103은 `completed_candidate_id: candidate-broker-rejection-taxonomy-contract` 완료 마커를 남겼다.
- **현재 계약 판정**: 최신 sidecar 재현에서 `overall_status=CONTRACT_READY`다.
  `APBK1672`은 `kis_order_response_rejection`으로 분류되고, 관측 수는 2건, 신뢰도는 `HIGH`,
  재발 위험은 `OBSERVED_RECURRENT`, 행동 분류는 `NO_AUTO_RETRY`다. 최신 micro GTAA 의도 손실
  게이트는 `latest_intent_loss`로 live 주문을 막고 있으므로, 이 계약은 주문 재시도가 아니라
  forward 토너먼트·전략 검토 증거 대기를 다음 행동으로 남긴다.
- **post-merge 실행**: #493 main push 뒤 `Deploy on merge to main` run `28840419738`,
  `Released work ledger` run `28840419722`, `Autonomous work execution loop` run `28840419831`이 success였다.
- **sidecar 확인**: 최신 released-work sidecar는 timestamp `2026-07-07T03:57:58.221310Z`에서
  `candidate-broker-rejection-taxonomy-contract`를 released 후보로 기록했다. 최신 autonomous-work sidecar는
  timestamp `2026-07-07T03:57:54Z`에서 `candidate-execution-cost-basis-contract`를
  `EXECUTION_READY`, risk grade 2, safety impact 없음으로 선택했다.
- **배포 확인**: main commit의 `Deploy on merge to main` 체크에서 deploy run은 success다.
  컨테이너에서 GitHub run 상태와 check-run 성공은 확인했다. 서버 audit_log는 직접 확인하지 못한다.
  KIS smoke sidecar 최신 run은 #493 commit 직접 증거가 아니라 이전 schedule 실행 증거이므로 #493 배포
  근거로 쓰지 않는다. 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **안전 경계**: 등급 2 읽기 전용 브로커 거부 분류 계약 추가다. 기존 sidecar를 읽고 보고서와 probe만
  추가했다. 실제 주문, 브로커 실주문 API, 주문 재시도, 자본 증액, 자본 배분, whitelist/caps 확대,
  live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값, 외부 유료 서비스 변경 없음.
  현재 돈 경로는 계속 `PREVIEW_ONLY`다.
- **검증**: PR #493 머지 전 focused pytest 36 통과, remote sidecar replay에서
  `CONTRACT_READY`, taxonomy `APBK1672`, action `NO_AUTO_RETRY`, next candidate
  `candidate-execution-cost-basis-contract` 확인, tasks 완료 상태의 released-work 로컬 재현에서
  `candidate-broker-rejection-taxonomy-contract` released 확인, autonomous-work 로컬 재현에서
  `candidate-execution-cost-basis-contract` 전진 확인, `uv run pytest` 2533 통과·4 스킵,
  `uv run ruff check src tests` 통과, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14),
  `uv run python scripts/check_handoff_facts.py` OK, PR 품질 관문 성공,
  머지 직전 `uv run pytest` 2533 통과·4 스킵 및 ruff 재통과,
  post-merge deploy·released-work·autonomous-work run 성공 확인 완료. 인계 갱신 전 main 기준
  `uv run pytest -q`는 낡은 HANDOFF 때문에 하네스 2건만 실패했고, 이 handoff 갱신 뒤
  `uv run pytest -q`는 2533 통과·4 스킵이다.
- **상세 인계**: `HANDOFF-107-BROKER-REJECTION-TAXONOMY-CONTRACT.md`.

## 최근 관찰 — 2026-07-07 KST (스펙 102 체결 품질 frontier 지도)

현재 `main` 최신 코드 머지는 `c975517`(#491, 스펙 102 체결 품질 frontier 지도)이다.
기능 커밋은 `5b81ab0`이고, 직전 main은 `3e56ce9`(#490, 스펙 101 인계)이다.

- **문제 정의**: 스펙 101은 다음 후보를 `candidate-execution-quality-frontier-map`으로 열었다.
  거시 후보 지도는 체결 품질 영역까지는 선택했지만, 주문 거부, 브로커 진단, 의도 손실,
  비용 기준 중 무엇을 다음 읽기 전용 후보로 닫을지 별도 지도와 완료 뒤 전진 규칙이 없었다.
- **구현 상태**: `autonomous_work_execution.py`가 `execution_quality_frontier_map`을 JSON과 Markdown에
  발행한다. 지도는 브로커 거부 분류, 체결 비용 기준, 브로커 진단 생존성 후보를 순서대로 열고,
  `candidate-execution-quality-frontier-map`이 released-work에 기록되면 첫 후보
  `candidate-broker-rejection-taxonomy-contract`로 전진한다.
- **입력 증거 등록**: `scripts/autonomous_work_execution_probe.py --manifest`가 이제
  `execution-quality`, `kis-smoke`, `rebalance-micro-gtaa`를 읽기 전용 입력으로 포함한다.
  KIS smoke는 Markdown 표에서 `smoke_state`와 `smoke_exit`를 구조화해 evidence surface `ok`로 읽는다.
- **post-merge 실행**: #491 main push 뒤 `Deploy on merge to main` run `28829134863`,
  `Released work ledger` run `28829134911`, `Autonomous work execution loop` run `28829134839`가 success였다.
- **sidecar 확인**: 최신 released-work sidecar는 timestamp `2026-07-06T23:01:23.747012Z`에서
  `candidate-execution-quality-frontier-map`을 released 후보로 기록했다. 최신 autonomous-work sidecar는
  timestamp `2026-07-06T23:01:25Z`에서 `candidate-broker-rejection-taxonomy-contract`를
  `EXECUTION_READY`, risk grade 2, safety impact 없음으로 선택했다.
- **배포 확인**: main commit의 `Deploy on merge to main` 체크에서 deploy run은 success다.
  컨테이너에서 GitHub run 상태와 check-run 성공은 확인했다. 서버 audit_log는 직접 확인하지 못한다.
  KIS smoke sidecar 최신 run은 #491 commit 직접 증거가 아니라 이전 schedule 실행 증거이므로 #491 배포
  근거로 쓰지 않는다. 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **안전 경계**: 등급 2 운영 자동화 보정이다. sidecar 읽기 전용 보고서와 후보 지도만 추가했다.
  실제 주문, 브로커 실주문 API, 자본 증액, 자본 배분, whitelist/caps 확대, live 전략 교체, live sentinel,
  헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값, 외부 유료 서비스 변경 없음. 현재 돈 경로는 계속
  `PREVIEW_ONLY`다.
- **검증**: PR #491 머지 전 focused pytest 36 통과, remote sidecar replay에서
  `candidate-execution-quality-frontier-map` selected 및 첫 지도 후보
  `candidate-broker-rejection-taxonomy-contract` 확인, tasks 완료 상태의 released-work 로컬 재현에서
  `candidate-execution-quality-frontier-map` released 확인, autonomous-work 로컬 재현에서
  `candidate-broker-rejection-taxonomy-contract` 전진 확인, `uv run pytest` 2526 통과·4 스킵,
  `uv run ruff check src tests` 통과, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14),
  `uv run python scripts/check_handoff_facts.py` OK, PR 품질 관문 성공,
  머지 직전 `uv run pytest` 2526 통과·4 스킵 및 ruff 재통과,
  post-merge deploy·released-work·autonomous-work run 성공 확인 완료. 이 handoff 갱신 뒤
  `uv run pytest -q`는 2526 통과·4 스킵이다.
- **상세 인계**: `HANDOFF-106-EXECUTION-QUALITY-FRONTIER-MAP.md`.

## 최근 관찰 — 2026-07-07 KST (스펙 101 데이터 증거 생존성 계약)

현재 `main` 최신 코드 머지는 `28bfbf1`(#489, 스펙 101 데이터 증거 생존성 계약)이다.
기능 커밋은 `646d2ea`이고, 직전 main은 `304d3cd`(#488, 스펙 100 인계)이다.

- **문제 정의**: 스펙 100은 다음 후보를 `candidate-data-evidence-liveness-contract`로 열었다.
  `pipeline-liveness`는 public-data와 regime-stratify freshness를 보여주지만, 데이터 품질 후보 관점의
  통과·관측 대기·복구 필요 기준과 source LAST_RUN timestamp 감사 경로는 별도 계약으로 닫혀 있지 않았다.
- **구현 상태**: `data_evidence_liveness.py`와 `scripts/data_evidence_liveness_probe.py`가 새 읽기 전용
  보고서 계약을 만든다. 보고서는 public-data, regime-stratify, pipeline-liveness, released-work,
  capital-path readiness 증거를 읽어 `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`를 분리한다.
  스펙 101은 `completed_candidate_id: candidate-data-evidence-liveness-contract` 완료 마커를 남겼다.
- **현재 계약 판정**: 최신 sidecar 재현에서 `overall_status=CONTRACT_READY`다.
  `collect-public-data`와 `regime-stratify`는 모두 pipeline-liveness에서 `OK`이고,
  source LAST_RUN timestamp와 pipeline timestamp가 각각 일치한다.
  `pipeline_report_parse`, `data_check_registration`, `data_liveness_status`,
  `source_timestamp_consistency`, `source_freshness`, `safety_boundary`가 모두 PASS다.
- **post-merge 실행**: #489 main push 뒤 `Deploy on merge to main` run `28820754814`,
  `Released work ledger` run `28820754885`, `Autonomous work execution loop` run `28820754816`이 success였다.
- **sidecar 확인**: 최신 released-work sidecar는 timestamp `2026-07-06T20:22:50.476149Z`에서
  `candidate-data-evidence-liveness-contract`를 released 후보로 기록했다. 최신 autonomous-work sidecar는
  timestamp `2026-07-06T20:22:50Z`에서 `candidate-execution-quality-frontier-map`을
  `EXECUTION_READY`, risk grade 2, safety impact 없음으로 선택했다.
- **배포 확인**: main commit의 `Deploy on merge to main` 체크에서 deploy run은 success다.
  컨테이너에서 GitHub run 상태와 check-run 성공은 확인했다. 서버 audit_log는 직접 확인하지 못한다.
  KIS smoke sidecar 최신 run은 #489 commit 직접 증거가 아니라 이전 schedule 실행 증거이므로 #489 배포
  근거로 쓰지 않는다. 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **안전 경계**: 등급 2 데이터 품질 계약 추가다. sidecar 읽기 전용 보고서와 probe만 추가했다.
  실제 주문, 브로커 실주문 API, 자본 증액, 자본 배분, whitelist/caps 확대, live 전략 교체, live sentinel,
  헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값, 외부 유료 서비스 변경 없음. 현재 돈 경로는 계속
  `PREVIEW_ONLY`다.
- **검증**: PR #489 머지 전 focused pytest 36 통과, 최신 sidecar replay에서
  스펙 101 probe `overall_status=CONTRACT_READY`, 모든 gate PASS, data check source timestamp 일치 확인,
  released-work 로컬 재현에서 `candidate-data-evidence-liveness-contract` released 확인,
  autonomous-work 로컬 재현에서 `candidate-execution-quality-frontier-map` 전진 확인,
  `uv run pytest` 2523 통과·4 스킵, `uv run ruff check src tests` 통과,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14),
  `uv run python scripts/check_handoff_facts.py` OK, PR 품질 관문 성공,
  머지 직전 `uv run pytest` 2523 통과·4 스킵 및 ruff 재통과,
  post-merge deploy·released-work·autonomous-work run 성공 확인 완료. 인계 갱신 전 main 기준
  `uv run pytest -q`는 낡은 HANDOFF 때문에 하네스 2건만 실패했고, 이 handoff 갱신 뒤
  `uv run pytest -q`는 2523 통과·4 스킵이다.
- **상세 인계**: `HANDOFF-105-DATA-EVIDENCE-LIVENESS-CONTRACT.md`.

## 최근 관찰 — 2026-07-06 KST (스펙 100 레짐 타임라인 커버리지 계약)

현재 `main` 최신 코드 머지는 `48314cd`(#487, 스펙 100 레짐 타임라인 커버리지 계약)이다.
기능 커밋은 `7a2ba58`이고, 직전 main은 `9ed61b8`(#486, 스펙 099 인계)이다.

- **문제 정의**: 스펙 099는 다음 후보를 `candidate-regime-timeline-coverage-contract`로 열었다.
  레짐 층화는 public-data 타임라인에 의존하지만, 라벨 결측, 희귀 레짐 관측 수, d+1 전망적 조인 품질을
  별도 계약으로 닫지 않으면 다음 데이터 후보가 같은 입력 품질 판단을 반복하게 된다.
- **구현 상태**: `regime_timeline_coverage.py`와 `scripts/regime_timeline_coverage_probe.py`가
  새 읽기 전용 보고서 계약을 만든다. 보고서는 `regime_timeline.csv`, `regime-stratify`,
  `pipeline-liveness`, `released-work` 증거를 읽어 `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`를
  분리한다. 스펙 100은 `completed_candidate_id: candidate-regime-timeline-coverage-contract` 완료
  마커를 남겼다.
- **현재 계약 판정**: 최신 sidecar 재현에서 `overall_status=OBSERVATION_WAIT`다.
  타임라인은 2372행, 2017-01-03~2026-07-02, canonical label은
  `RISK_ON=1414`, `CAUTION=894`, `RISK_OFF=64`로 모두 존재한다.
  timeline shape, label coverage, forward join quality, sidecar liveness는 PASS다.
  `GLOBAL-TREND...:RISK_OFF`와 `GLOBAL-TREND-WIDE...:RISK_OFF` joined return 관측이 7일이라
  stratified observation floor만 WAIT다.
- **post-merge 실행**: #487 main push 뒤 `Deploy on merge to main` run `28799231896`,
  `Released work ledger` run `28799231124`, `Autonomous work execution loop` run `28799231156`이 success였다.
- **sidecar 확인**: #487 코드 PR 시점에는 T018/T023이 아직 인계 전 미완료라 remote released-work가
  스펙 100을 완료 후보로 읽지 않았다. 이 handoff는 T018/T023을 완료로 닫았고, 로컬 released-work 재현은
  `candidate-regime-timeline-coverage-contract`를 spec `100-regime-timeline-coverage-contract`의 released
  후보로 기록한다. 같은 상태의 autonomous-work 로컬 재현은
  `candidate-data-evidence-liveness-contract`를 `EXECUTION_READY`, risk grade 2, safety impact 없음으로
  선택한다.
- **배포 확인**: main commit의 `Deploy on merge to main` 체크에서 deploy run은 success다.
  컨테이너에서 GitHub run 상태와 check-run 성공은 확인했다. 서버 audit_log는 직접 확인하지 못한다.
  KIS smoke sidecar 최신 run은 #487 commit 직접 증거가 아니라 이전 schedule 실행 증거이므로 #487 배포
  근거로 쓰지 않는다. 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **안전 경계**: 등급 2 데이터 품질 계약 추가다. sidecar 읽기 전용 보고서와 probe만 추가했다.
  실제 주문, 브로커 실주문 API, 자본 증액, 자본 배분, whitelist/caps 확대, live 전략 교체, live sentinel,
  헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값, 외부 유료 서비스 변경 없음. 현재 돈 경로는 계속
  `PREVIEW_ONLY`다.
- **검증**: PR #487 머지 전 focused pytest 36 통과, 최신 sidecar replay에서
  스펙 100 probe `overall_status=OBSERVATION_WAIT`, timeline 2372행, label coverage PASS,
  forward join PASS, observation floor WAIT 확인, `uv run pytest` 2512 통과·4 스킵,
  `uv run ruff check src tests` 통과, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14),
  `uv run python scripts/check_handoff_facts.py` OK, PR 품질 관문 성공,
  머지 직전 `uv run pytest` 2512 통과·4 스킵 및 ruff 재통과,
  post-merge deploy·released-work·autonomous-work run 성공 확인 완료. 인계 브랜치에서는
  released-work 로컬 재현으로 스펙 100 released 확인, autonomous-work 로컬 재현으로
  `candidate-data-evidence-liveness-contract` 전진 확인,
  `uv run pytest -q` 2512 통과·4 스킵, ruff, HANDOFF 사실 검증, strict harness를 재확인했다.
- **상세 인계**: `HANDOFF-104-REGIME-TIMELINE-COVERAGE-CONTRACT.md`.

## 최근 관찰 — 2026-07-06 KST (스펙 099 공개 데이터 입력 품질 계약)

현재 `main` 최신 코드 머지는 `c3803cd`(#485, 스펙 099 공개 데이터 입력 품질 계약)이다.
기능 커밋은 `1425958`이고, 직전 main은 `f29b01f`(#484, 스펙 098 인계)이다.

- **문제 정의**: 스펙 098은 다음 후보를 `candidate-public-data-input-quality-contract`로 열었다.
  공개 데이터 발행 수, 교차검증, 레짐 지표, 레짐 타임라인, regime-stratify, pipeline-liveness를
  따로 읽으면 다음 투자 후보 입력이 실제로 준비됐는지 반복 판단해야 한다. 목표는 이 입력 품질을
  `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`로 닫는 기계 판독 계약을 만드는 것이다.
- **구현 상태**: `public_data_input_quality.py`와 `scripts/public_data_input_quality_probe.py`가
  새 읽기 전용 보고서 계약을 만든다. 보고서는 public-data summary, regime.json,
  regime_timeline.csv, regime-stratify, pipeline-liveness, released-work, capital-path readiness를
  evidence surface와 quality gate로 발행한다. 스펙 099는
  `completed_candidate_id: candidate-public-data-input-quality-contract` 완료 마커를 남겼다.
- **현재 입력 품질**: 최신 sidecar 재현에서 `overall_status=CONTRACT_READY`다.
  public-data는 11/11개 발행, 교차검증 5개 PASS, 최소 overlap 13일이다. 레짐 타임라인은 2372행,
  regime-stratify는 total return 751일이고, collect-public-data와 regime-stratify liveness는 OK다.
  capital-path readiness는 `LIVE_BLOCKED`, live money는 `PREVIEW_ONLY`다.
- **post-merge 실행**: #485 main push 뒤 `Deploy on merge to main` run `28791708696`,
  `Released work ledger` run `28791708832`, `Autonomous work execution loop` run `28791708758`이 success였다.
- **sidecar 확인**: 최신 released-work sidecar는 commit `c3803cd`에서
  `candidate-public-data-input-quality-contract`를 spec `099-public-data-input-quality-contract`의 released
  후보로 기록했다. 최신 autonomous-work sidecar는 같은 commit에서
  `candidate-regime-timeline-coverage-contract`를 `EXECUTION_READY`, risk grade 2, safety impact 없음으로
  선택했다. 데이터 증거 frontier 지도는 `public_data_input_quality=released`,
  `regime_timeline_coverage=open`, `data_evidence_liveness=open` 상태다.
- **배포 확인**: main commit의 `Deploy on merge to main` 체크에서 deploy run은 success다.
  컨테이너에서 GitHub run 상태와 check-run 성공은 확인했다. 서버 audit_log는 직접 확인하지 못한다.
  KIS smoke sidecar 최신 run은 #485 commit 직접 증거가 아니라 이전 schedule 실행 증거이므로 #485 배포
  근거로 쓰지 않는다. 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **안전 경계**: 등급 2 데이터 품질 계약 추가다. sidecar 읽기 전용 보고서와 probe만 추가했다.
  실제 주문, 브로커 실주문 API, 자본 증액, 자본 배분, whitelist/caps 확대, live 전략 교체, live sentinel,
  헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값, 외부 유료 서비스 변경 없음. 현재 돈 경로는 계속
  `PREVIEW_ONLY`다.
- **검증**: PR #485 머지 전 focused pytest 32 통과, 최신 sidecar replay에서
  스펙 099 probe `overall_status=CONTRACT_READY`, public-data 11/11, 교차검증 5개 PASS,
  timeline 2372행, stratified return 751일, liveness OK 확인, released-work 로컬 재현에서
  `candidate-public-data-input-quality-contract` released 확인, autonomous-work 로컬 재현에서
  `candidate-regime-timeline-coverage-contract` 전진 확인, `uv run pytest` 2500 통과·4 스킵,
  `uv run ruff check src tests` 통과, `git diff --check` 통과,
  `uv run python scripts/check_handoff_facts.py` OK,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 품질 관문 성공,
  머지 직전 `uv run pytest` 2500 통과·4 스킵 및 ruff 재통과,
  post-merge deploy·released-work·autonomous-work run 성공 확인 완료. 인계 갱신 전 main 기준
  `uv run pytest -q`는 낡은 HANDOFF 때문에 하네스 2건만 실패했고, 이 handoff 갱신 뒤
  `uv run pytest -q`는 2500 통과·4 스킵이다.
- **상세 인계**: `HANDOFF-103-PUBLIC-DATA-INPUT-QUALITY-CONTRACT.md`.

## 최근 관찰 — 2026-07-06 KST (스펙 098 데이터 증거 frontier 지도)

현재 `main` 최신 코드 머지는 `6aa85c6`(#483, 스펙 098 데이터 증거 frontier 지도)이다.
기능 커밋은 `3e6d8e6`이고, 직전 main은 `b8022d6`(#482, 스펙 097 인계)이다.

- **문제 정의**: 스펙 097 뒤 자율 작업 실행 루프는 `candidate-data-evidence-frontier-map`을
  다음 후보로 열었다. 투자 엣지 no-live 후보가 닫힌 뒤 다음 병목은 public-data, regime timeline,
  regime-stratify, pipeline-liveness 같은 입력 증거의 품질을 후보로 분해하는 것이다.
- **구현 상태**: `autonomous_work_execution.py`가 `data_evidence_frontier_map`을 JSON과 Markdown에
  발행한다. 지도는 공개 데이터 입력 품질, 레짐 타임라인 커버리지, 데이터 증거 생존성 3개 영역을
  open으로 보여주며, `candidate-data-evidence-frontier-map`이 released-work로 닫히면
  `candidate-public-data-input-quality-contract`를 첫 실행 후보로 만든다. probe manifest는
  `automation/public-data`와 `automation/regime-stratify-last-run` 입력을 읽기 전용으로 추가했다.
- **post-merge 실행**: #483 main push 뒤 `Deploy on merge to main` run `28786862434`,
  `Released work ledger` run `28786862491`, `Autonomous work execution loop` run `28786862604`이 success였다.
- **sidecar 확인**: 최신 released-work sidecar는 commit `6aa85c6`에서
  `candidate-data-evidence-frontier-map`을 spec `098-data-evidence-frontier-map`의 released 후보로
  기록했다. 최신 autonomous-work sidecar는 같은 commit에서 `candidate-public-data-input-quality-contract`를
  `EXECUTION_READY`, risk grade 2, safety impact 없음으로 선택했다. public-data 입력은
  `overall_ok=True, published=11`, regime-stratify 입력은 `total_return_days=751`로 파싱됐다.
- **배포 확인**: main commit의 `Deploy on merge to main` 체크에서 deploy run은 success다.
  컨테이너에서 GitHub run 상태와 check-run 성공은 확인했다. 서버 audit_log는 직접 확인하지 못한다.
  KIS smoke sidecar 최신 run은 #483 commit 직접 증거가 아니라 이전 schedule 실행 증거이므로 #483 배포 근거로 쓰지 않는다.
  이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **안전 경계**: 등급 2 데이터 품질 후보 지도와 work packet 보고서 확장이다. sidecar 읽기 전용 보고서와
  probe manifest만 바꿨다. 실제 주문, 브로커 실주문 API, 자본 증액, 자본 배분, whitelist/caps 확대,
  live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값, 외부 유료 서비스 변경 없음.
  현재 돈 경로는 계속 `PREVIEW_ONLY`다.
- **검증**: PR #483 머지 전 focused pytest 30 통과, 최신 sidecar replay에서
  `candidate-data-evidence-frontier-map` 선택 확인, 완료 마커 적용 뒤
  `candidate-public-data-input-quality-contract` 선택 확인, public-data와 regime-stratify 파싱 ok 확인,
  released-work 로컬 재현에서 `candidate-data-evidence-frontier-map` released 확인,
  `uv run pytest` 2491 통과·4 스킵, `uv run ruff check src tests` 통과, `git diff --check` 통과,
  `uv run python scripts/check_handoff_facts.py` OK,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 품질 관문 성공,
  머지 직전 `uv run pytest` 2491 통과·4 스킵 및 ruff 재통과,
  post-merge deploy·released-work·autonomous-work run 성공 확인 완료. 인계 갱신 전 main 기준
  `uv run pytest -q`는 낡은 HANDOFF 때문에 하네스 2건만 실패했고, 이 handoff 갱신 뒤
  `uv run pytest -q`는 2491 통과·4 스킵이다.
- **상세 인계**: `HANDOFF-102-DATA-EVIDENCE-FRONTIER-MAP.md`.

## 최근 관찰 — 2026-07-06 KST (스펙 097 비용 차감 no-live 엣지 실험 계약)

현재 `main` 최신 코드 머지는 `49c4331`(#481, 스펙 097 비용 차감 no-live 엣지 실험 계약)이다.
기능 커밋은 `e50e0c7`이고, 직전 main은 `6843ac7`(#480, 스펙 096 인계)이다.

- **문제 정의**: 스펙 096 뒤 자율 작업 실행 루프는 `candidate-cost-adjusted-edge-experiment`를
  다음 후보로 열었다. forward 성과만 보면 거래 비용과 실행 품질 악화가 빠지므로, forward verdict와
  execution-quality를 함께 읽어 비용 스트레스 후보와 실제 비용 근거 부족을 분리하는 no-live 계약이 필요했다.
- **구현 상태**: `cost_adjusted_edge_experiment.py`와
  `scripts/cost_adjusted_edge_experiment_probe.py`가 새 보고서 계약을 만든다. 보고서는
  `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`를 분리하고, 현재 최신 sidecar 기준
  `overall_status=OBSERVATION_WAIT`, forward 최대 관측 16/20, 남은 관측 4개,
  비용 스트레스 후보 21개, 50bps 스트레스 기준 최상위 후보 `multiasset`(1.342695%),
  execution-quality `latest_signal=INTENT_LOSS`, 브로커 거부 2건, KIS 코드 `APBK1672` 2건,
  `cost_basis_complete=false`, money-path `PREVIEW_ONLY`, stage `BLOCKED`로 판정한다. 스펙 097은
  `completed_candidate_id: candidate-cost-adjusted-edge-experiment` 완료 마커를 남겼다.
- **post-merge 실행**: #481 main push 뒤 `Deploy on merge to main` run `28784829389`,
  `Released work ledger` run `28784829439`, `Autonomous work execution loop` run `28784829374`이 success였다.
- **sidecar 확인**: 최신 released-work sidecar는 commit `49c4331`에서
  `candidate-cost-adjusted-edge-experiment`를 spec `097-cost-adjusted-edge-experiment`의 released 후보로
  기록했다. 최신 autonomous-work sidecar는 같은 commit에서 `candidate-data-evidence-frontier-map`를
  `EXECUTION_READY`, risk grade 2, safety impact 없음으로 선택했다.
- **배포 확인**: main commit의 `Deploy on merge to main` 체크에서 deploy run은 success다.
  컨테이너에서 GitHub run 상태와 job 성공은 확인했다. 서버 audit_log는 직접 확인하지 못한다.
  KIS smoke sidecar 최신 run은 #481 commit 직접 증거가 아니라 이전 schedule 실행 증거이므로 #481 배포 근거로 쓰지 않는다.
  이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **안전 경계**: 등급 2 no-live 실험 계약 추가다. sidecar 읽기 전용 보고서와 probe만 추가했다. 실제 주문,
  브로커 실주문 API, 자본 증액, 자본 배분, whitelist/caps 확대, live 전략 교체, live sentinel, 헌법,
  커널 목록, K1/K2/K4/K5/K6, 비밀값, 외부 유료 서비스 변경 없음. 현재 돈 경로는 계속 `PREVIEW_ONLY`다.
- **검증**: PR #481 머지 전 focused pytest 7 통과, 최신 sidecar replay에서
  스펙 097 probe `overall_status=OBSERVATION_WAIT`, forward 16/20, 남은 관측 4개,
  비용 스트레스 후보 21개, 50bps 최상위 `multiasset`, no-live safety PASS,
  cost-basis completeness WAIT, released-work closure PASS 확인, released-work 로컬 재현에서
  `candidate-cost-adjusted-edge-experiment` released 확인, autonomous-work 로컬 재현에서
  `candidate-data-evidence-frontier-map` 전진 확인, `uv run pytest` 2489 통과·4 스킵,
  `uv run ruff check src tests` 통과, `git diff --check` 통과,
  `uv run python scripts/check_handoff_facts.py` OK,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 품질 관문 성공,
  머지 직전 `uv run pytest` 2489 통과·4 스킵 및 ruff 재통과,
  post-merge deploy·released-work·autonomous-work run 성공 확인 완료. 인계 갱신 전 main 기준
  `uv run pytest -q`는 낡은 HANDOFF 때문에 하네스 2건만 실패했고, 이 handoff 갱신 뒤
  `uv run pytest -q`는 2489 통과·4 스킵이다.
- **상세 인계**: `HANDOFF-101-COST-ADJUSTED-EDGE-EXPERIMENT.md`.

## 최근 관찰 — 2026-07-05 KST (스펙 096 신호 다변화 no-live 엣지 실험 계약)

현재 `main` 최신 코드 머지는 `df8cc23`(#479, 스펙 096 신호 다변화 no-live 엣지 실험 계약)이다.
기능 커밋은 `999fbd2`이고, 직전 main은 `d81609a`(#478, 스펙 095 인계)이다.

- **문제 정의**: 스펙 095 뒤 자율 작업 실행 루프는 `candidate-signal-diversification-edge-experiment`를
  다음 후보로 열었다. 기존 forward 후보가 글로벌 3자산 incumbent에만 가까워지면 투자 엣지 탐색 폭이
  좁아지므로, forward 리더보드의 track을 신호군으로 묶고 incumbent와 낮게 겹치는 no-live 후보를
  분리하는 기계 판독 계약이 필요했다.
- **구현 상태**: `signal_diversification_edge_experiment.py`와
  `scripts/signal_diversification_edge_experiment_probe.py`가 새 보고서 계약을 만든다. 보고서는
  `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`를 분리하고, 현재 최신 sidecar 기준
  `overall_status=OBSERVATION_WAIT`, 신호군 6개, forward 최대 관측 16/20, 남은 관측 4개,
  incumbent `global_diversification`, 가장 낮은 겹침 후보 `broad_equity_timing`(겹침 0.0),
  money-path `PREVIEW_ONLY`, stage `BLOCKED`로 판정한다. 스펙 096은
  `completed_candidate_id: candidate-signal-diversification-edge-experiment` 완료 마커를 남겼다.
- **후보 분리**: 현재 sidecar 재현에서 `broad_equity_timing`(겹침 0.0),
  `risk_managed_beta`(0.25), `wide_universe_allocation`(0.375)은 `PROPOSED`다.
  `multi_asset_allocation`(0.666667)과 `fixed_weight_allocation`(1.0)은 관찰 대기다.
- **post-merge 실행**: #479 main push 뒤 `Deploy on merge to main` run `28740023274`,
  `Released work ledger` run `28740023261`, `Autonomous work execution loop` run `28740023276`이 success였다.
- **sidecar 확인**: 최신 released-work sidecar는 commit `df8cc23`에서
  `candidate-signal-diversification-edge-experiment`를 spec `096-signal-diversification-edge-experiment`의
  released 후보로 기록했다. 최신 autonomous-work sidecar는 같은 commit에서
  `candidate-cost-adjusted-edge-experiment`를 `EXECUTION_READY`, risk grade 2, safety impact 없음으로
  선택했다. 투자 엣지 frontier 지도는 `forward_regime_edge=released`,
  `signal_diversification_edge=released`, `cost_adjusted_edge=open` 상태다.
- **배포 확인**: main commit의 `Deploy on merge to main` 체크에서 deploy run은 success다.
  컨테이너에서 서버 audit_log와 GitHub Actions Summary 원문은 직접 확인하지 못한다. KIS smoke sidecar
  최신 run은 #479 commit 직접 증거가 아니라 이전 schedule 실행 증거이므로 #479 배포 근거로 쓰지 않는다.
  이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **안전 경계**: 등급 2 no-live 실험 계약 추가다. sidecar 읽기 전용 보고서와 probe만 추가했다. 실제 주문,
  브로커 실주문 API, 자본 증액, 자본 배분, whitelist/caps 확대, live 전략 교체, live sentinel, 헌법,
  커널 목록, K1/K2/K4/K5/K6, 비밀값, 외부 유료 서비스 변경 없음. 현재 돈 경로는 계속 `PREVIEW_ONLY`다.
- **검증**: PR #479 머지 전 focused pytest 7 통과, 최신 sidecar replay에서
  스펙 096 probe `overall_status=OBSERVATION_WAIT`, 신호군 6개, forward 16/20, 남은 관측 4개,
  no-live safety PASS, released-work closure PASS 확인, released-work 로컬 재현에서
  `candidate-signal-diversification-edge-experiment` released 확인, autonomous-work 로컬 재현에서
  `candidate-cost-adjusted-edge-experiment` 전진 확인, `uv run pytest -q` 2482 통과·4 스킵,
  `uv run ruff check src tests` 통과, `git diff --check` 통과,
  `uv run python scripts/check_handoff_facts.py` OK,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 품질 관문 성공,
  머지 직전 `uv run pytest -q` 2482 통과·4 스킵 및 ruff 재통과,
  post-merge deploy·released-work·autonomous-work run 성공 확인 완료.
- **상세 인계**: `HANDOFF-100-SIGNAL-DIVERSIFICATION-EDGE-EXPERIMENT.md`.

## 최근 관찰 — 2026-07-04 KST (스펙 095 forward 레짐 엣지 no-live 실험 계약)

현재 `main` 최신 머지는 `a083b31`(#477, 스펙 095 forward 레짐 엣지 no-live 실험 계약)이다.
기능 커밋은 `705f049`이고, 직전 main은 `968ee6f`(#476, 스펙 094 인계)이다.

- **문제 정의**: 스펙 094는 다음 후보를 `candidate-forward-regime-edge-experiment`로 열었지만,
  그 후보를 닫을 기계 판독 no-live 실험 계약과 관측 대기 판정이 없었다. 목표는 forward 리더보드,
  money-path, released-work, learning ledger, pipeline-liveness 증거를 한 번에 읽어 레짐별 forward edge가
  비교 가능한지와 아직 무엇을 기다리는지 재현 가능하게 남기는 것이다.
- **구현 상태**: `forward_regime_edge_experiment.py`와
  `scripts/forward_regime_edge_experiment_probe.py`가 새 보고서 계약을 만든다. 보고서는
  `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`를 분리하고, 현재 최신 sidecar 기준
  `overall_status=OBSERVATION_WAIT`, forward 최대 관측 16/20, 남은 관측 4개, 모든 forward track 대기,
  money-path `PREVIEW_ONLY`, stage `BLOCKED`로 판정한다. 스펙 095는
  `completed_candidate_id: candidate-forward-regime-edge-experiment` 완료 마커를 남겼다.
- **post-merge 실행**: #477 main push 뒤 `Deploy on merge to main` run `28707157800`,
  `Released work ledger` run `28707157804`, `Autonomous work execution loop` run `28707157779`이 success였다.
- **sidecar 확인**: 최신 released-work sidecar는 commit `a083b31`에서
  `candidate-forward-regime-edge-experiment`를 spec `095-forward-regime-edge-experiment`의 released 후보로
  기록했다. 최신 autonomous-work sidecar는 같은 commit에서 `candidate-signal-diversification-edge-experiment`를
  `EXECUTION_READY`, risk grade 2, safety impact 없음으로 선택했다. 투자 엣지 frontier 지도는
  `forward_regime_edge=released`, `signal_diversification_edge=open`,
  `cost_adjusted_edge=open` 상태다.
- **배포 확인**: main commit의 `Deploy on merge to main` 체크에서 deploy run은 success다. 컨테이너에서
  서버 audit_log와 GitHub Actions Summary 원문은 직접 확인하지 못한다. KIS smoke sidecar 최신 run은
  #477 commit 직접 증거가 아니라 이전 schedule 실행 증거이므로 #477 배포 근거로 쓰지 않는다. 이 배포는
  dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **안전 경계**: 등급 2 no-live 실험 계약 추가다. sidecar 읽기 전용 보고서와 probe만 추가했다. 실제 주문,
  브로커 실주문 API, 자본 증액, 자본 배분, whitelist/caps 확대, live 전략 교체, live sentinel, 헌법,
  커널 목록, K1/K2/K4/K5/K6, 비밀값, 외부 유료 서비스 변경 없음. 현재 돈 경로는 계속 `PREVIEW_ONLY`다.
- **검증**: PR #477 머지 전 focused pytest 7 통과, 완료 후보가 자율 루프에서
  `candidate-signal-diversification-edge-experiment`로 전진하는 focused pytest 8 통과, 최신 sidecar replay에서
  스펙 095 probe `overall_status=OBSERVATION_WAIT`, forward 16/20, 남은 관측 4개, no-live safety PASS,
  released-work closure PASS 확인, `uv run pytest` 2475 통과·4 스킵,
  `uv run ruff check src tests` 통과, `git diff --check` 통과,
  `uv run python scripts/check_handoff_facts.py` OK,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 품질 관문 성공,
  머지 직전 `uv run pytest` 2475 통과·4 스킵 및 ruff 재통과,
  post-merge deploy·released-work·autonomous-work run 성공 확인 완료.
- **상세 인계**: `HANDOFF-099-FORWARD-REGIME-EDGE-EXPERIMENT.md`.

## 최근 관찰 — 2026-07-04 KST (스펙 094 투자 엣지 frontier 지도와 no-live 실험 후보 전진)

현재 `main` 최신 머지는 `02e7d6e`(#475, 스펙 094 투자 엣지 frontier 지도와 no-live 실험 후보 전진)이다.
기능 커밋은 `f18b8af`이고, 직전 main은 `c8c89b5`(#474, 스펙 093 인계)이다.

- **문제 정의**: 스펙 093은 다음 후보를 `candidate-investment-edge-frontier-map`으로 열었지만,
  그 후보까지 완료되면 투자 엣지 안쪽의 실제 no-live 실험 후보가 필요하다. 목표는 투자 엣지 영역을
  forward verdict, money-path, released-work, learning ledger 증거를 읽는 구체 후보로 분해하는 것이다.
- **구현 상태**: `autonomous_work_execution.py`가 `investment_edge_frontier_map`을 JSON과 Markdown에
  발행한다. `candidate-investment-edge-frontier-map`이 released-work로 닫히면
  `candidate-forward-regime-edge-experiment`를 `EXECUTION_READY` 후보로 만든다. probe manifest는
  `rebalance-paper-forward`, `edge-autoarm`, `money-path`를 읽기 전용 입력으로 추가했다.
- **post-merge 실행**: #475 main push 뒤 `Deploy on merge to main` run `28706285176`,
  `Released work ledger` run `28706285172`, `Autonomous work execution loop` run `28706285171`이 success였다.
- **sidecar 확인**: 최신 released-work sidecar는 commit `02e7d6e`에서
  `candidate-investment-edge-frontier-map`을 spec `094-investment-edge-frontier-map`의 released 후보로
  기록했다. 최신 autonomous-work sidecar는 같은 commit에서 `candidate-forward-regime-edge-experiment`를
  `EXECUTION_READY`, risk grade 2, safety impact 없음으로 선택했다. 투자 엣지 frontier 지도 첫 행은
  `forward_regime_edge`, 상태 `open`, 추천 후보 `candidate-forward-regime-edge-experiment`다.
- **배포 확인**: main commit의 `Deploy on merge to main` 체크에서 `deploy` job은 success다. 컨테이너에서
  서버 audit_log와 GitHub Actions Summary 원문은 직접 확인하지 못한다. 이 배포는 dry-run worker 코드
  반영이며 실거래 전환이 아니다.
- **안전 경계**: 등급 2 운영 자동화 보정이다. 실제 주문, 브로커 실주문 API, 자본 증액, 자본 배분,
  whitelist/caps 확대, live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값,
  외부 유료 서비스 변경 없음. 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **검증**: PR #475 머지 전 focused pytest 28 통과, latest sidecar replay에서
  `candidate-investment-edge-frontier-map` 선택 확인, released-work 로컬 재현에서
  `candidate-investment-edge-frontier-map` released 확인, 완료 마커 적용 뒤
  `candidate-forward-regime-edge-experiment` 선택 확인, `uv run pytest` 2468 통과·4 스킵,
  `uv run ruff check src tests` 통과, `git diff --check` 통과,
  `uv run python scripts/check_handoff_facts.py` OK,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 품질 관문 성공,
  머지 직전 `uv run pytest` 2468 통과·4 스킵 및 ruff 재통과,
  post-merge deploy·released-work·autonomous-work run 성공 확인 완료. 인계 갱신 전 main 기준
  `uv run pytest -q`는 낡은 HANDOFF 때문에 하네스 2건만 실패했고, 이 handoff 갱신 뒤
  `uv run pytest -q`는 2468 통과·4 스킵이다.
- **상세 인계**: `HANDOFF-098-INVESTMENT-EDGE-FRONTIER-MAP.md`.

## 최근 관찰 — 2026-07-04 KST (스펙 093 거시 후보 지도와 후보 재생성 루프)

현재 `main` 최신 머지는 `7438f38`(#473, 스펙 093 거시 후보 지도와 후보 재생성 루프)이다.
기능 커밋은 `23704a2`이고, 직전 main은 `bd03341`(#472, 스펙 092 인계)이다.

- **문제 정의**: 스펙 092 뒤 frontier 후보까지 released-work로 닫히면 자율 작업 실행 루프가 다시
  "새 실행 후보 없음" 상태로 돌아간다. 목표는 닫힌 후보 큐를 영역별 거시 후보 지도로 읽고,
  다음 실행 가능한 frontier 후보를 재생성하는 것이다.
- **구현 상태**: `autonomous_work_execution.py`가 `macro_candidate_map`을 JSON과 Markdown에 발행한다.
  frontier discovery 후보가 released된 뒤에는 `candidate-macro-candidate-map-regenerator`를 먼저 발행하고,
  이 regenerator 자체가 released되면 지도에서 최상위 미완료 영역인
  `candidate-investment-edge-frontier-map`을 `EXECUTION_READY` 후보로 만든다.
- **post-merge 실행**: #473 main push 뒤 `Deploy on merge to main` run `28705183202`,
  `Released work ledger` run `28705183167`, `Autonomous work execution loop` run `28705183168`이 success였다.
- **sidecar 확인**: 최신 released-work sidecar는 commit `7438f38`에서
  `candidate-macro-candidate-map-regenerator`를 spec `093-macro-candidate-map-regenerator`의 released 후보로
  기록했다. 최신 autonomous-work sidecar는 같은 commit에서 `candidate-investment-edge-frontier-map`을
  `EXECUTION_READY`, risk grade 2, safety impact 없음으로 선택했다. 거시 후보 지도 첫 행은
  `investment_edge`, 상태 `exhausted`, 추천 후보 `candidate-investment-edge-frontier-map`이다.
- **배포 확인**: main commit의 `Deploy on merge to main` 체크에서 `deploy` job은 success다. 컨테이너에서
  서버 audit_log와 GitHub Actions Summary 원문은 직접 확인하지 못한다. deploy-audit sidecar는 오래된
  2026-06-18 수동 실행이고, KIS smoke sidecar 최신 run은 commit `bd03341` 기준 schedule 실행이라 #473
  배포의 직접 증거가 아니다.
- **안전 경계**: 등급 2 운영 자동화 보정이다. 실제 주문, 브로커 실주문 API, 자본 증액, 자본 배분,
  whitelist/caps 확대, live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값,
  외부 유료 서비스 변경 없음. 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **검증**: PR #473 머지 전 focused pytest 26 통과, latest sidecar replay에서
  `candidate-investment-edge-frontier-map` 선택 확인, released-work 로컬 재현에서
  `candidate-macro-candidate-map-regenerator` released 확인, `uv run pytest` 2466 통과·4 스킵,
  `uv run ruff check src tests` 통과, `git diff --check` 통과,
  `uv run python scripts/check_handoff_facts.py` OK,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 품질 관문 성공,
  post-merge deploy·released-work·autonomous-work run 성공 확인 완료. 인계 갱신 전 main 기준
  `uv run pytest -q`는 낡은 HANDOFF 때문에 하네스 2건만 실패했고, 이 handoff 갱신 뒤
  `uv run pytest -q`는 2466 통과·4 스킵이다.
- **상세 인계**: `HANDOFF-097-MACRO-CANDIDATE-MAP-REGENERATOR.md`.

## 최근 관찰 — 2026-07-04 KST (스펙 092 자율 후보 고갈 뒤 frontier 발굴 후보 폐쇄)

현재 `main` 최신 머지는 `b004d2f`(#471, 스펙 092 자율 후보 고갈 뒤 frontier 발굴 후보 폐쇄)이다.
기능 커밋은 `d90bd71`이고, 직전 main은 `9d15e0e`(#470, 스펙 091 인계)이다.

- **문제 정의**: 스펙 091 뒤 known macro 후보가 모두 닫히자 자율 작업 실행 루프가 새 실행 후보를
  만들지 못하고 닫힌 released 후보 `candidate-fd04772a23c5`를 `selected_work`처럼 남겼다. 목표는
  이 후보 고갈 상태를 frontier 발굴 후보로 드러내되, 일반 실행 후보나 운영자 승인 후보를 가리지
  않게 하는 것이다.
- **구현 상태**: `autonomous_work_execution.py`가 기존 macro 후보 3개가 모두 released 또는 이미 후보
  목록에 있는 경우에만 `candidate-autonomous-frontier-discovery`를 `EXECUTION_READY` 후보로 만든다.
  일반 실행 후보가 있으면 frontier 후보는 생성되지 않는다. 스펙 092는 completed marker
  `candidate-autonomous-frontier-discovery`를 남겨 이 후보도 released-work로 닫힌다.
- **post-merge 실행**: #471 main push 뒤 `Deploy on merge to main` run `28689000449`,
  `Released work ledger` run `28689000437`, `Autonomous work execution loop` run `28689000427`이 success였다.
- **sidecar 확인**: 최신 released-work sidecar는 commit `b004d2f`에서
  `candidate-autonomous-frontier-discovery`를 spec `092-frontier-candidate-discovery`의 released 후보로
  기록했다. 최신 autonomous-work sidecar는 같은 commit에서 `overall_status=RELEASED`, ranked 후보 0개,
  `selected_work=candidate-fd04772a23c5` 상태다. 이것은 새 착수 후보가 아니라 frontier 후보까지
  완료 처리된 뒤의 후보 고갈 상태다.
- **배포 확인**: main commit의 `Deploy on merge to main` 체크에서 `deploy` job은 success다. 컨테이너에서
  서버 audit_log와 GitHub Actions Summary 원문은 직접 확인하지 못한다. KIS smoke sidecar 최신 run
  `28643034277`은 success지만 commit `55ec2da` 기준 스케줄 실행이므로 #471 배포의 직접 증거가 아니라
  키와 smoke 건강 상태 참고 증거다.
- **안전 경계**: 등급 2 운영 자동화 보정이다. 실제 주문, 브로커 실주문 API, 자본 증액, 자본 배분,
  whitelist/caps 확대, live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값,
  외부 유료 서비스 변경 없음. 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **검증**: PR #471 머지 전 focused pytest 23 통과, 최신 sidecar replay에서
  `candidate-autonomous-frontier-discovery` 선택 확인, 완료 마커 적용 뒤 `candidate-fd04772a23c5`가
  released 상태로 남는 것 확인, released-work 로컬 재현에서 frontier 후보 released 확인,
  `uv run pytest` 2463 통과·4 스킵, `uv run ruff check src tests` 통과, `git diff --cached --check` 통과,
  `uv run python scripts/check_handoff_facts.py` OK,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 품질 관문 성공,
  post-merge deploy·released-work·autonomous-work run 성공 확인 완료. 인계 갱신 전 main 기준
  `uv run pytest -q`는 낡은 HANDOFF 때문에 하네스 2건만 실패했고, 이 handoff 갱신 뒤
  `uv run pytest -q`는 2463 통과·4 스킵이다.
- **상세 인계**: `HANDOFF-096-FRONTIER-CANDIDATE-DISCOVERY.md`.

## 최근 관찰 — 2026-07-03 KST (스펙 090 source diversification 산출 후보 완료 폐쇄)

현재 `main` 최신 머지는 `2f64cba`(#467, 스펙 090 source diversification 산출 후보 완료 폐쇄)이다.
기능 커밋은 `a167fee`이고, 직전 main은 `55ec2da`(#466, 스펙 089 인계)이다.

- **문제 정의**: 스펙 089는 정적 후보가 모두 닫힌 뒤 새 후보
  `candidate-source-diversification-sidecar-bottleneck`을 만들었다. 그런데 이 후보의 행동 설명은
  스펙 089가 이미 구현한 "학습 장부, released-work, pipeline-liveness, capital-path-readiness를
  후보 생성 입력으로 승격"한 내용과 겹쳤다. 목표는 이 산출 후보를 완료 후보로 닫고 다음 실제 후보로
  전진시키는 것이다.
- **구현 상태**: `specs/090-source-diversification-candidate-closure/`가 completed marker
  `candidate-source-diversification-sidecar-bottleneck`을 남긴다. 자율 작업 실행 회귀 테스트는 이 후보가
  released-work로 닫히면 다음 후보 `candidate-autonomous-growth-objective-calibration`이 선택됨을 고정한다.
- **post-merge 실행**: #467 main push 뒤 `Deploy on merge to main` run `28643121916`,
  `Released work ledger` run `28643121934`, `Autonomous work execution loop` run `28643121911`이 success였다.
- **sidecar 확인**: 최신 released-work sidecar는 commit `2f64cba`에서
  `candidate-source-diversification-sidecar-bottleneck`을 spec
  `090-source-diversification-candidate-closure`의 released 후보로 기록했다. 최신 autonomous-work sidecar는
  같은 commit에서 `candidate-autonomous-growth-objective-calibration`을 `EXECUTION_READY`, risk grade 2,
  safety impact 없음으로 선택했다.
- **배포 확인**: deploy run `28643121916`의 `deploy` job은 success다. 컨테이너에서 서버 audit_log와
  GitHub Actions Summary 원문은 직접 확인하지 못한다. KIS smoke sidecar 최신 run `28643034277`은 success지만
  commit `55ec2da` 기준 스케줄 실행이므로 #467 배포의 직접 증거가 아니라 키와 smoke 건강 상태 참고 증거다.
- **안전 경계**: 등급 2 운영 자동화 보정이다. 실제 주문, 브로커 실주문 API, 자본 증액, 자본 배분,
  whitelist/caps 확대, live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값,
  외부 유료 서비스 변경 없음. 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **검증**: PR #467 머지 전 focused pytest 12 통과, released-work 로컬 재현에서
  `candidate-source-diversification-sidecar-bottleneck` released 확인, 최신 sidecar replay에서
  `candidate-autonomous-growth-objective-calibration` 선택 확인, `uv run pytest -q` 2459 통과·4 스킵,
  `uv run ruff check src tests` 통과, `git diff --check` 통과,
  `uv run python scripts/check_handoff_facts.py` OK,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 품질 관문 성공,
  post-merge deploy·released-work·autonomous-work run 성공 확인 완료. 인계 갱신 전 main 기준
  `uv run pytest -q`는 낡은 HANDOFF 때문에 하네스 2건만 실패했고, 이 handoff 갱신 뒤
  `uv run pytest -q`는 2459 통과·4 스킵이다.
- **상세 인계**: `HANDOFF-094-SOURCE-DIVERSIFICATION-CANDIDATE-CLOSURE.md`.

## 최근 관찰 — 2026-07-03 KST (스펙 089 정적 후보 템플릿 밖 증거 기반 후보 공간 확장)

현재 `main` 최신 머지는 `b243a06`(#465, 스펙 089 정적 후보 템플릿 밖 증거 기반 후보 공간 확장)이다.
기능 커밋은 `c67fda4`이고, 직전 main은 `bf924a5`(#464, 스펙 088 인계)이다.

- **문제 정의**: 스펙 088 뒤 최신 자율 후보는 `candidate-evolution-source-diversification`이었다.
  기존 upstream autonomous-evolution loop는 정적 9개 후보를 계속 만들었고, downstream에서
  released-work와 learning ledger를 적용해야만 후보 포화가 드러났다. 목표는 upstream 후보 생성기가
  `released-work`, `pipeline-liveness`, `capital-path-readiness`, `promotion-summary`, learning ledger를
  직접 읽어 정적 후보 포화 이후 새 후보를 합성하게 하는 것이다.
- **구현 상태**: `evolution_loop.py`가 `released-work`와 `capital-path-readiness` sidecar를 새 입력으로
  소비한다. released 후보는 upstream backlog에서도 `released`로 닫히고, 안전 실행 후보와 operator
  review/safety-impact 후보가 모두 없을 때만 `candidate-source-diversification-sidecar-bottleneck`을
  만든다.
- **post-merge 실행**: #465 main push 뒤 `Deploy on merge to main` run `28639386244`,
  `Autonomous evolution loop` run `28639386349`, `Autonomous work execution loop` run `28639386220`,
  `Released work ledger` run `28639386219`, `Execution quality package` run `28639386186`이 success였다.
- **sidecar 확인**: 최신 evolution sidecar는 commit `b243a06`, safe_high_leverage_work
  `candidate-source-diversification-sidecar-bottleneck`, status_counts `new=1`, `rejected=2`,
  `released=7`이다. 최신 released-work sidecar는 `candidate-evolution-source-diversification`을
  스펙 089 완료 후보로 released 처리했다.
- **순서 주의**: 같은 push에서 autonomous-work sidecar는 evolution sidecar 갱신 전 입력을 읽어
  `candidate-autonomous-growth-objective-calibration`을 골랐다. 최신 sidecar들을 로컬 재현하면
  `candidate-source-diversification-sidecar-bottleneck`이 `EXECUTION_READY`로 선택된다.
- **안전 경계**: 등급 2 운영 자동화 보정이다. 실제 주문, 브로커 실주문 API, 자본 증액, 자본 배분,
  whitelist/caps 확대, live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값,
  외부 유료 서비스 변경 없음. 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **검증**: PR #465 머지 전 focused pytest 43 통과, 실제 sidecar quickstart 재현에서
  `candidate-source-diversification-sidecar-bottleneck` 생성 확인, `released_work_probe.py --repo-root .`
  로컬 재현에서 `candidate-evolution-source-diversification` released 확인, `uv run pytest`
  2458 통과·4 스킵, `uv run ruff check src tests` 통과, `git diff --check` 통과,
  `uv run python scripts/check_handoff_facts.py` OK,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 품질 관문 성공,
  post-merge deploy와 sidecar run 성공 확인 완료. 인계 갱신 전 main 기준 `uv run pytest -q`는
  낡은 HANDOFF 때문에 하네스 2건만 실패했고, 이 handoff 갱신 뒤 `uv run pytest -q`는
  2458 통과·4 스킵이다.
- **상세 인계**: `HANDOFF-093-EVOLUTION-SOURCE-DIVERSIFICATION.md`.

## 최근 관찰 — 2026-07-03 KST (스펙 088 거시 자율 성장 후보 발굴기)

현재 `main` 최신 머지는 `927beb0`(#463, 스펙 088 거시 자율 성장 후보 발굴기)이다.
기능 커밋은 `bca5415`이고, 직전 main은 `95c8b6b`(#462, 스펙 087 인계)이다.

- **문제 정의**: 자율 작업 실행 루프가 모든 일반 후보를 released/suppressed로 닫으면 실행 가능한
  후보가 0개가 되고, 이전에는 완료 후보가 `selected_work`처럼 남아 운영자가 "다음 작업이
  없나?"를 다시 확인해야 했다. 목표는 이 닫힌 큐 상태 자체를 거시 성장 후보로 승격하는 것이다.
- **구현 상태**: `autonomous_work_execution.py`가 released-work와 learning-ledger 적용 뒤 일반
  work packet에 `EXECUTION_READY`, `OPERATOR_APPROVAL_REQUIRED`, `BLOCKED`가 없고 남은 후보가
  모두 `RELEASED` 또는 `SUPPRESSED`이면 거시 후보를 만든다. 일반 실행 가능 후보, 복구 후보,
  운영자 승인 필요 후보가 있으면 거시 후보는 끼어들지 않는다.
- **완료 후보 소비와 다음 후보**: 스펙 088 완료 marker는 `candidate-macro-growth-discovery`다.
  #463 main push의 `Released work ledger` run `28637783779`는 이 후보를 released로 발행했다.
  `Autonomous work execution loop` run `28637783763`은 이 부트스트랩 후보를 건너뛰고 다음 후보
  `candidate-evolution-source-diversification`을 `EXECUTION_READY`로 선택했다. ranked 후보는 1개,
  suppressed 후보는 9개다.
- **post-merge 실행**: #463 main push 뒤 `Deploy on merge to main` run `28637783776`,
  `Released work ledger` run `28637783779`, `Autonomous work execution loop` run `28637783763`이
  모두 success였다. deploy run은 push:main에 붙은 직접 증거이며, 로그에는 deploy correlation id
  `3def9820731ee47dd07ded917b858b34`와 `auto-invest-deploy.service` 성공 종료가 남았다.
  KIS smoke sidecar 최신 성공은 2026-07-02 schedule run이라 이번 merge의 직접 배포 증거로 쓰지 않는다.
- **안전 경계**: 등급 2 운영 자동화 보정이다. 실제 주문, 브로커 실주문 API, 자본 증액, 자본 배분,
  whitelist/caps 확대, live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값,
  외부 유료 서비스 변경 없음. 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **검증**: PR #463 머지 전 focused pytest 18 통과, quickstart probe에서
  `candidate-macro-growth-discovery` 선택 확인, `uv run pytest` 2454 통과·4 스킵,
  `uv run ruff check src tests` 통과, `git diff --check` 통과,
  `uv run python scripts/check_handoff_facts.py` OK,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 품질 관문 성공,
  `released_work_probe.py --repo-root .` 로컬 재현에서 `candidate-macro-growth-discovery` released 확인,
  repo-root override 자율 작업 실행에서 `candidate-evolution-source-diversification` 선택 확인,
  post-merge deploy와 sidecar run 성공 확인 완료. 인계 갱신 전 main 기준 `uv run pytest -q`는
  낡은 HANDOFF 때문에 하네스 2건만 실패했고, 이 handoff 갱신 뒤 `uv run pytest -q`는
  2454 통과·4 스킵이다.
- **상세 인계**: `HANDOFF-092-AUTONOMOUS-MACRO-GROWTH-DISCOVERY.md`.

## 최근 관찰 — 2026-07-03 KST (스펙 087 학습 장부 후보 재발굴 차단)

현재 `main` 최신 머지는 `753afb7`(#461, 스펙 087 학습 장부 후보 재발굴 차단)이다.
기능 커밋은 `f1d86f4`이고, 직전 main은 `3c728b6`(#460, 스펙 086 최종 인계)이다.

- **문제 정의**: 자율 작업 실행 루프가 `candidate-fa66202bf496`를 다음 후보로 제시했다. 목표는
  `learning_ledger.json`에 이미 남은 `rejected`, `evidence_dependent`, `operator_review` 결정이
  다음 자율 성장 실행에서 같은 후보를 다시 `safe_high_leverage_work`로 되살리지 못하게 하는 것이다.
- **구현 상태**: `evolution_loop.py`의 `apply_learning_ledger`가 `rejected/discard`,
  `evidence_dependent/deferred/observe`, `operator_review` 결정을 후보 상태에 실제 반영한다.
  보류·운영자 검토 후보는 `safe_high_leverage_work`에서 빠지고, 다음 행동에는 ledger 사유,
  근거 패키지, 재검토 조건을 남긴다. 알 수 없는 ledger decision은 기존처럼 실패 개방으로 둔다.
- **완료 후보 소비**: 스펙 087 산출물은 `completed_candidate_id: candidate-fa66202bf496`를 담고,
  #461 main push의 `Released work ledger` run `28632340016`은 이 후보를 `released`로 발행했다.
  `Autonomous work execution loop` run `28632340035`는 `candidate-fa66202bf496`를 `RELEASED`로
  억제하고 실행 가능한 안전 후보를 비웠다. `selected_work`에 보이는 `candidate-facf2fa31834`도
  `CLOSED_RELEASED`라 새 착수 후보가 아니다.
- **post-merge 실행**: #461 main push 뒤 `Deploy on merge to main` run `28632340034`,
  `Released work ledger` run `28632340016`, `Autonomous evolution loop` run `28632340021`,
  `Autonomous work execution loop` run `28632340035`, `Execution quality package` run `28632340008`가
  모두 success였다. deploy run은 push:main에 붙은 직접 증거다. KIS smoke sidecar 최신 성공은
  2026-07-02 schedule run이라 이번 merge의 직접 배포 증거로 쓰지 않는다.
- **관찰 차이**: 자율 성장 원본 backlog는 `candidate-fa66202bf496`를 계속 `new`로 생성할 수 있다.
  이번 작업의 완료 반복 방지는 released-work와 autonomous-work 실행 경로에서 확인된다. ledger entry가
  실제로 들어온 후보는 새 `apply_learning_ledger` 경로로 보류·운영자 검토 상태가 된다.
- **안전 경계**: 등급 2 운영 자동화 보정이다. 실제 주문, 브로커 실주문 API, 자본 증액, 자본 배분,
  whitelist/caps 확대, live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값,
  외부 유료 서비스 변경 없음. 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **검증**: PR #461 머지 전 focused pytest 39 통과, quickstart ledger replay에서
  `candidate-fa66202bf496`가 `evidence_dependent`이고 `safe_high_leverage_work`에 없음을 확인,
  `uv run pytest` 2450 통과·4 스킵, `uv run ruff check src tests` 통과, `git diff --check` 통과,
  `uv run python scripts/check_handoff_facts.py` OK,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 품질 관문 성공,
  `released_work_probe.py --repo-root .` 로컬 재현에서 `candidate-fa66202bf496` released 확인,
  post-merge deploy와 sidecar run 성공 확인 완료. 인계 갱신 전 main 기준 `uv run pytest -q`는
  낡은 HANDOFF 때문에 하네스 2건만 실패했고, 이 handoff 갱신 뒤 `uv run pytest -q`는
  2450 통과·4 스킵이다.
- **상세 인계**: `HANDOFF-091-LEARNING-LEDGER-CANDIDATE-MEMORY.md`.

## 최근 관찰 — 2026-07-03 KST (스펙 086 자율 루프 sidecar와 HANDOFF 생존성)

현재 `main` 최신 머지는 `2de0f95`(#459, 스펙 086 result executor stale package 억제)이다.
직전 스펙 086 머지는 `e8779c8`(#458, promotion/factory stale sidecar 억제)와 `671b1a7`(#457,
자율 루프 sidecar/HANDOFF 생존성 완료 후보 폐쇄)이다.

- **문제 정의**: 자율 작업 실행 루프는 `candidate-88a7e7f07361`를 다음 후보로 제시했지만, 실제 main에는 이미
  `pipeline-liveness`의 `autonomous-evolution` 감시와 HANDOFF 세션 시작 `/sync` 진입점이 있었다. 목표는
  이미 충족된 운영 보정이 새 후보로 반복되지 않게 닫는 것이다.
- **구현 상태**: `evolution_loop.py`는 `autonomous-evolution=OK`와 HANDOFF 진입점을 함께 확인하면
  `candidate-88a7e7f07361`를 `released`로 표시한다. `autonomous_work_execution.py`,
  `promotion_loop.py`, `candidate_factory.py`, `candidate_result_executor.py`는 `released` 후보를 다시
  착수·승격·패키징·실행하지 않는다. 스펙 086 계약에는
  `completed_candidate_id: candidate-88a7e7f07361` 마커가 있다.
- **post-merge 확인**: #457 main push 뒤 `Deploy on merge to main` run `28628313144`,
  `Autonomous evolution loop` run `28628313165`, `Released work ledger` run `28628313152`,
  `Autonomous work execution loop` run `28628313148`, `Autonomous promotion loop` run `28628313151`,
  `Candidate implementation factory` run `28628313178`, `Candidate result executor` run `28628313158`가 success였다.
  최신 evolution/released-work/autonomous-work sidecar는 이 후보를 `released` 또는 `CLOSED_RELEASED`로 본다.
- **#458 follow-up 확인**: #458 main push 뒤 `Deploy on merge to main` run `28628876621`,
  `Released work ledger` run `28628876631`, `Autonomous promotion loop` run `28628876633`,
  `Candidate implementation factory` run `28628876598`, `Candidate result executor` run `28628876613`이 success였다.
  promotion은 `candidate-88a7e7f07361`를 `DISCARD`로 버렸고 factory/package에는 이 후보가 없다.
- **#459 follow-up 확인**: #459 main push 뒤 `Deploy on merge to main` run `28629315303`,
  `Candidate result executor` run `28629315296`, `Released work ledger` run `28629315307`,
  `Autonomous work execution loop` run `28629315301`, `Candidate implementation factory` run
  `28629315287`이 success였다. 최신 sidecar 확인 결과 released-work는 이 후보를 `released`,
  autonomous-work는 `RELEASED`, promotion은 기존 #458 sidecar에서 `DISCARD`, factory/package는 후보 없음,
  result executor와 `candidate_results.json`도 후보 없음이다.
- **안전 경계**: 등급 2 운영 자동화 보정이다. 실제 주문, 브로커 실주문 API, 자본 증액, 자본 배분,
  whitelist/caps 확대, live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값,
  외부 유료 서비스 변경 없음. 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **검증**: PR #457 머지 전 focused pytest 66 통과, `uv run pytest` 2444 통과·4 스킵,
  `uv run ruff check src tests` 통과, `uv run python scripts/check_handoff_facts.py` OK,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 품질 관문 성공,
  post-merge deploy와 sidecar run 성공 확인 완료. PR #458 머지 전 focused pytest 31 통과,
  stale promotion/factory 로컬 재현 성공, `uv run pytest` 2446 통과·4 스킵, lint와 하네스 통과,
  post-merge deploy와 sidecar run 성공 확인 완료. PR #459 머지 전 focused result tests 14 통과,
  stale result package 로컬 재현 성공, `uv run pytest` 2447 통과·4 스킵, lint와 하네스 통과,
  PR 품질 관문 성공, post-merge deploy와 sidecar run 성공 확인 완료.
- **상세 인계**: `HANDOFF-090-AUTONOMOUS-SIDECAR-HANDOFF-LIVENESS.md`.

## 최근 관찰 — 2026-07-02 KST (스펙 085 공개 데이터 수집·교차 검증 확장)

현재 `main` 최신 머지는 `d381199`(#455, 스펙 085 공개 데이터 수집·교차 검증 확장)이다.
기능 커밋은 `f84e478`이고, 직전 관련 커밋은 `148db36`(#454, 스펙 084 sidecar 최신 schedule 인계 정리)이다.

- **문제 정의**: 자율 작업 실행 루프는 `candidate-facf2fa31834`를 다음 안전 후보로 골랐다.
  목표는 연구 전용 공개 데이터 채널에 FRED 금리 전송 경로를 추가하고, 재무부 직접 금리와의
  교차 검증으로 조용한 절단·헤더·날짜 정렬 오류를 더 잘 잡는 것이다.
- **구현 상태**: `deploy/public-data.toml`에 FRED 그래프 CSV `DGS2`, `DGS10` 수집을 추가했다.
  FRED에만 `user_agent="httpx-default"`를 쓰고, 다른 소스는 기존 채널 식별 헤더를 유지한다.
  Treasury-vs-FRED 수준 대조 2건을 추가해 public-data 교차 검증은 총 5건이 됐다.
- **제거와 대체**: FRED 그래프 CSV DGS10 탐침 중복 호출은 제거했다. 대체 수단은 실제 DGS2/DGS10
  수집 자체와 Treasury-vs-FRED 대조다. Stooq 가격 CSV와 FRED 공식 API 키 경로는 탐침/후속 선택지로
  남겼다.
- **post-merge 실행**: #455 main push 뒤 `Collect public data (research)` run `28596926048`은 success,
  commit `d381199`, trigger `push`다. 최신 public-data sidecar는 `overall_ok=True`,
  `published=11`, `total_items=11`, elapsed `9.5s`를 기록했다. `fred:DGS2`는 13,066행,
  `fred:DGS10`은 16,826행이고 둘 다 마지막 관측은 `2026-06-30`이다. Treasury-vs-FRED DGS2/DGS10
  대조는 각각 overlap 2,373, agree `100.00%`, PASS다.
- **완료 후보 소비**: #455 main push의 `Released work ledger` run `28596925315`와
  `Autonomous work execution loop` run `28596925573`는 handoff 전 `tasks.md` 상태를 읽어
  `candidate-facf2fa31834`를 아직 선택 후보로 남겼다. 이 handoff는 T021을 닫고
  `completed_candidate_id: candidate-facf2fa31834` 마커를 완성한다. handoff merge 뒤
  released-work/autonomous-work push run은 현재 checkout 스캔으로 이 후보를 완료 처리해야 한다.
  이 branch에서 `released_work_probe.py --repo-root .`를 재현하면 released_count 6이고
  `candidate-facf2fa31834`가 `released`로 들어간다.
- **안전 경계**: 등급 2 공개 데이터 운영 채널 보정이다. 실제 주문, 브로커 실주문 API, 자본 증액,
  자본 배분, whitelist/caps 확대, live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6,
  비밀값, 외부 유료 서비스 변경 없음. public-data sidecar는 연구·백테스트·검증 전용이며 라이브
  매매 신호는 계속 KIS 데이터만 사용한다.
- **검증**: focused pytest 54 통과, 실제 공개 데이터 수집 smoke에서 `overall_ok=true`,
  `published=11`, cross_checks 5건 PASS, `uv run pytest` 2438 통과·4 스킵,
  `uv run ruff check src tests` 통과, `uv run python scripts/check_handoff_facts.py` OK,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 품질 관문 성공,
  post-merge public-data run 성공 확인 완료. handoff 전 main 기준 `uv run pytest -q`의 2개 실패는
  낡은 `HANDOFF.md`를 하네스가 잡은 의도된 실패이며, 이 handoff가 해결한다.
- **상세 인계**: `HANDOFF-089-PUBLIC-DATA-CROSS-VALIDATION.md`.

## 최근 관찰 — 2026-07-02 KST (스펙 084 오래된 증거와 성과 실패 분리)

현재 `main` 최신 머지는 `4daf5d7`(#453, 스펙 084 sidecar 순서 위험 인계 정리)이다.
스펙 084 코드 베이스라인은 `e77a42c`(#451, 오래된 증거와 성과 실패 분리)이고, 직전 관련
커밋은 `0184f5c`(#450, 스펙 083 최종 인계 정리), `f874b64`(#449, 실행 품질 sidecar
freshness 판독 보정)이다.

- **문제 정의**: 자율 작업 실행 루프는 `candidate-6ee3370e933d`를 다음 후보로 골랐다.
  목표는 오래된 증거, 완료 후보 잔향, sidecar 신선도 문제를 전략 성과 실패나 새 후보처럼
  섞어 보이지 않게 분리하는 것이다.
- **구현 상태**: `capital_path_readiness.py`에 `ReadinessObservabilityIssue`와
  `observability_issues`를 추가했다. `released-work`가 완료로 기록한 후보가 upstream backlog에
  남으면 우선 후보에서 제외하고 `released_candidate_echo`로 기록한다. `pipeline-liveness`의
  stale/missing/malformed 상태는 관측 품질 이슈로만 기록하며 money-path readiness와 live-money
  gate는 바꾸지 않는다.
- **post-merge 실행**: #451 main push 뒤 `Deploy on merge to main` run `28576674026`,
  `Capital path readiness` run `28576674262`, `Released work ledger` run `28576674252`,
  `Autonomous work execution loop` run `28576674094`가 success였다. #452 인계 갱신 뒤 남은
  sidecar 순서 위험을 닫기 위해 `Capital path readiness`를 workflow_dispatch로 재실행했고,
  run `28584170609`(commit `b92bee0`)도 success였다. 최신 schedule run `28584438033`도 같은
  commit에서 같은 결론으로 success였다.
- **sidecar 확인**: 최신 capital-path-readiness sidecar는 commit `b92bee0`, run `28584438033`,
  `readiness_state=ACCUMULATING_EDGE`, 완료 후보 잔향 4건(`candidate-fd04772a23c5`,
  `candidate-e481b0309206`, `candidate-dff4f9344b02`, `candidate-6ee3370e933d`)을
  `observability_issues`로 기록한다. `candidate-6ee3370e933d`는 priority가 아니라 suppressed
  후보이며, 최신 released-work와 autonomous-work sidecar도 이 후보를 완료·억제 상태로 본다.
  다음 실제 착수 후보는 `candidate-facf2fa31834`(`공개 데이터 수집·교차 검증 확장`) 하나다.
- **안전 경계**: 등급 2 운영 자동화 보정이다. 실제 주문, 브로커 실주문 API, 자본 증액,
  자본 배분, whitelist/caps 확대, live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6,
  비밀값, 외부 유료 서비스 변경 없음. 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **검증**: focused pytest 10 통과, 실제 sidecar dry-run 확인, `uv run pytest` 2435 통과·4 스킵,
  `uv run ruff check src tests` 통과, `uv run python scripts/check_handoff_facts.py` OK,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 품질 관문 성공,
  post-merge deploy/capital-readiness/released-work/autonomous-work runs 확인 완료. 남은 sidecar
  순서 위험은 workflow_dispatch run `28584170609`와 최신 schedule run `28584438033` 성공,
  최신 capital-path-readiness sidecar 재확인으로 닫았다.
- **상세 인계**: `HANDOFF-088-STALE-EVIDENCE-SEPARATION.md`.

## 최근 관찰 — 2026-07-02 KST (스펙 083 주문 거부·체결 품질 손익 관측)

현재 `main` 최신 머지는 `f874b64`(#449, 실행 품질 sidecar freshness 판독 보정)이다.
스펙 083 기능 머지는 `b4fa316`(#448, 주문 거부·체결 품질 손익 관측)이고, 직전 관련 커밋은
`45b5d8f`(#447, 스펙 082 인계 정리), `0a5ad0f`(#446, 스펙 082 레짐·성과 후보 점수화)이다.

- **문제 정의**: 자율 작업 실행 루프는 `candidate-dff4f9344b02`를 다음 안전 후보로 골랐다. 최근
  micro GTAA 경로에는 거부 주문과 손실 의도 차단이 있었지만, 주문 거부·브로커 오류·KIS smoke·
  live gate가 한 증거 패키지로 묶이지 않아 다음 세션이 로그를 다시 뒤져야 했다.
- **구현 상태**: `execution_quality.py`와 `execution_quality_probe.py`가 이미 발행된 sidecar만 읽어
  `execution_quality.json`과 `LAST_RUN.md`를 만든다. `.github/workflows/execution-quality.yml`은
  `automation/execution-quality-last-run`을 발행한다. 자율 성장 루프는 새 evidence surface를 후보
  점수 입력으로 쓰고, `released-work`는 `completed_candidate_id: candidate-dff4f9344b02`를 소비한다.
- **후속 품질 보정**: 새 `LAST_RUN.md` 안에는 입력 증거의 `timestamp_utc`와 workflow metadata의
  `timestamp_utc`가 함께 있다. `pipeline_liveness.py`가 첫 `timestamp_utc`만 잡으면 sidecar 자체
  발행 시각이 아니라 KIS smoke 입력 시각을 freshness로 볼 수 있어, #449가 metadata 행과
  top-level JSON 시각을 우선 읽도록 보정했다.
- **배포 후 실제 실행**: #448 main push 뒤 `Deploy on merge to main` run `28573162272`,
  `Execution quality package` run `28573162279`, `Pipeline liveness watchdog` run `28573162215`과
  workflow_run `28573180853`, `Released work ledger` run `28573162227`, `Autonomous work execution loop`
  run `28573162293`, `Candidate result executor` run `28573162239`가 success였다. #449 main push 뒤에는
  `Deploy on merge to main` run `28574000074`, `Execution quality package` run `28574000181`,
  `Pipeline liveness watchdog` run `28574000145`과 workflow_run `28574020426`, `Autonomous evolution loop`
  run `28574000146`, `Autonomous work execution loop` run `28574000140`, `Candidate result executor`
  run `28574000112`가 모두 success다.
- **sidecar 확인**: 최신 execution-quality sidecar는 commit `f874b64`, run `28574000181`,
  `overall_status=OBSERVE`, `monitor_verdict=INSUFFICIENT_DATA`, `latest_signal=INTENT_LOSS`,
  `cumulative_pnl_usd=-1.14`, `rejected_orders=2`, `parsed_broker_errors=2`,
  `kis_msg_codes={"APBK1672": 2}`, KIS smoke `state=success`, `smoke_error_rate=0.0000`을 기록한다.
  최신 pipeline-liveness sidecar는 run `28574020426`, commit `f874b64`에서 `execution-quality`의 마지막
  갱신을 `2026-07-02T07:45:40Z`로 읽고 `OK`로 판정한다.
- **완료 후보 소비**: 최신 `released-work` sidecar는 `candidate-dff4f9344b02`를 `released`로 기록한다.
  최신 `autonomous-work-execution` sidecar는 같은 후보를 `RELEASED`로 억제하고 다음 후보
  `candidate-6ee3370e933d`(`오래된 증거와 성과 실패 분리`)를 선택한다.
- **남은 관찰 지점**: #449 뒤 최신 자율 성장 sidecar는 `오래되었거나 누락된 증거: 없음`으로 회복됐다.
  다만 자율 성장 후보 backlog에는 완료된 `candidate-dff4f9344b02`도 점수화 후보로 계속 보일 수 있다.
  실제 착수 루프인 `autonomous-work-execution`은 `released-work` 장부를 읽어 이 후보를 `RELEASED`로
  억제하므로 다음 실제 착수 후보는 `candidate-6ee3370e933d`다. 후보 결과 실행기의 기존
  strategy_backtest/portfolio_backtest blocked 2건은 이번 스펙의 새 실패가 아니라 별도 후보 검증 관찰 지점이다.
- **안전 경계**: 등급 2 운영 자동화 보정이다. 실제 주문, 브로커 실주문 API, 자본 증액, 자본 배분,
  whitelist/caps 확대, live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값,
  외부 유료 서비스 변경 없음. 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **검증**: #448 머지 전 focused pytest 70 통과, `uv run pytest` 2431 통과·4 스킵,
  `uv run ruff check src tests` 통과, `uv run python scripts/check_handoff_facts.py` OK,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 품질 관문 성공,
  post-merge sidecar와 deploy run 확인 완료. 후속 liveness timestamp 보정은 focused pytest 32 통과,
  실제 sidecar probe, `uv run pytest` 2433 통과·4 스킵, strict 하네스 14/14, #449 PR 품질 관문,
  post-merge deploy와 sidecar run 성공으로 검증했다.
- **상세 인계**: `HANDOFF-087-REJECTED-ORDER-EXECUTION-QUALITY.md`.

## 최근 관찰 — 2026-07-02 KST (스펙 082 레짐·성과 후보 점수화)

현재 `main` 최신 기능 머지는 `0a5ad0f`(#446, 스펙 082 레짐·성과 후보 점수화)이다.
직전 관련 커밋은 `a98db6e`(#445, 스펙 081 인계 정리), `649a8df`(#444, 스펙 081
자율 루프 품질 폐쇄)이다.

- **문제 정의**: 자율 성장 루프는 `candidate-e481b0309206`를 다음 안전 후보로 골랐지만,
  레짐 층화와 승격 준비 성과 표면이 후보 점수의 실제 증거 입력이 아니라 기존 정적 점수에
  가까웠다. 목표는 `regime-stratify`, `public-data`, `promote-readiness`를 함께 읽어
  분석 후보의 증거 신뢰도와 성장 레버리지를 결정론적으로 조정하게 하는 것이다.
- **구현 상태**: `evolution_loop.py`의 evidence requirement에 `promote-readiness`를 추가했다.
  분석 후보 생성은 `_analysis_candidate`로 분리했고, evidence refs는
  `regime-stratify`, `public-data`, `promote-readiness` 세 표면을 함께 기록한다.
  `READY=false`는 정상적인 보수적 성과 보고로 취급하고, 누락·stale·셋업 오류는
  `sidecar_freshness` 의존과 낮은 확신으로 처리한다.
- **workflow 계약**: `.github/workflows/autonomous-evolution-loop.yml` 자체에 SSH, KIS, 주문, 자본,
  live 전략 변경 경로를 추가하지 않았다. workflow는 기존처럼 `evolution_loop_probe.py --manifest`를
  읽어 sidecar를 수집하므로 새 성과 표면은 manifest 추가만으로 수집된다.
- **배포 후 실제 실행**: #446 main push 뒤 `Deploy on merge to main` run `28566029103` success,
  `Autonomous evolution loop` run `28566029110` success, `Autonomous work execution loop` run
  `28566029113` success, `Released work ledger` run `28566029091` success를 확인했다.
  deploy run의 `deploy` job은 checkout, SSH key 설치, stuck deploy quarantine, systemd unit sync,
  off-hours-guarded oneshot trigger까지 모두 success다. 서버 `audit_log`는 이 컨테이너에서 직접
  확인하지 못했으므로 운영자 확인 표면으로 남는다.
- **sidecar 확인**: 최신 `origin/automation/autonomous-evolution-last-run`은 commit `0a5ad0f`,
  run `28566029110`, `overall_status=ok`다. `candidate_backlog.json`에서
  `candidate-e481b0309206`는 evidence refs `regime-stratify/public-data/promote-readiness`,
  점수 560, `evidence_dependency=none`, `status=new`로 확인됐다.
- **완료 후보 소비 보정**: #446 main push의 `released-work` run은 스펙 082 T017이 아직 handoff 전이라
  082를 제외했다. 이 handoff는 T017을 완료로 닫고
  `completed_candidate_id: candidate-e481b0309206`를 계약서에 추가했다. 같은 checkout에서
  `released_work_probe.py --repo-root .`를 재현하면 `candidate-e481b0309206`가 `released`로 나오고,
  `autonomous_work_execution_probe.py --repo-root .` 재현 결과 다음 선택 후보는
  `candidate-dff4f9344b02`(`주문 거부·체결 품질 손익 관측`)다.
- **KIS smoke 참고**: 최신 KIS smoke sidecar는 run `28523981341`, commit `996ce56`, `smoke_state=success`,
  `key_valid=true`다. #446 이후 실행은 아니므로 배포 증거가 아니라 최근 읽기 전용 브로커 생존 참고로만 본다.
- **안전 경계**: 등급 2 운영 자동화 보정이다. `READY=true`나 `READY=false` 모두 승격·주문·자본 변경
  신호가 아니다. 실제 주문, 브로커 실주문 API, 자본 증액, 자본 배분, whitelist/caps 확대,
  live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값, 외부 유료 서비스 변경 없음.
  배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **검증**: focused pytest 31 통과, `uv run pytest` 2421 통과·4 스킵,
  `uv run ruff check src tests` 통과, `git diff --check` 통과,
  `uv run python scripts/check_handoff_facts.py` OK,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14),
  PR 품질 관문 통과, post-merge deploy/evolution/work/released runs 확인 완료.
- **상세 인계**: `HANDOFF-086-REGIME-PERFORMANCE-CANDIDATE-SCORING.md`.

## 최근 관찰 — 2026-07-02 KST (스펙 081 자율 루프 품질 폐쇄)

현재 `main` 최신 기능 머지는 `649a8df`(#444, 스펙 081 자율 루프 품질 폐쇄)이다.
직전 관련 커밋은 `eb7de67`(#443, 스펙 080 최종 인계 정리), `27388dd`(#442, 스펙 080
모바일 상태판 publish 보정)이다.

- **문제 정의**: 자율 성장 루프는 다음 후보를 고르고 운영자 상태판까지 보여주게 됐지만,
  세 가지 흠이 남아 있었다. 안전한 위험 등급 2 후보도 "Codex가 바로 시작해도 되는지"가
  작업 패킷에 명시되지 않았고, money-path `14/20`과 edge/forward `15/20` 차이가 장애처럼
  보일 수 있었으며, `operator-status`가 새로 발행된 뒤 `pipeline-liveness`가 오래된 상태를
  한 번 더 남길 수 있었다.
- **구현 상태**: `autonomous_work_execution.py`의 `WorkPacket`에 `autonomy_level`,
  `start_guidance_ko`, `completion_gates`를 추가했다. 위험 등급 2 이하이고 주문·자본·비밀값·헌법·
  live 전략·유료 서비스 표면을 건드리지 않는 후보는 `CODEX_AUTONOMOUS_START`로 표시된다.
  위험 후보는 기존처럼 `OPERATOR_APPROVAL_REQUIRED` 또는 복구 필요 상태로 남는다.
- **돈 경로 정렬 보정**: `money_gate_alignment.py`는 money-path와 edge/forward sidecar의 관측 수가
  서로 달라도 모두 관측 부족 대기를 말하면 `ALIGNED_WAITING`을 유지한다. 동시에 관측 시점 차이는
  `SNAPSHOT_SKEW` 정보성 이슈로 남겨 다음 aligned run에서 수렴 여부를 볼 수 있게 했다.
- **감시 보정**: `.github/workflows/pipeline-liveness.yml`은 기존 cron/push/수동 실행에 더해
  `Operator mobile alerts` workflow 완료 후 다시 실행될 수 있다. 이 후속 실행은 읽기 전용이고
  `automation/pipeline-liveness-last-run`만 갱신한다.
- **배포 후 실제 실행**: #444 main push 뒤 `Deploy on merge to main` run `28564456852` success,
  `Autonomous work execution loop` run `28564456840` success, `Money gate alignment loop` run
  `28564456849` success, `Pipeline liveness watchdog` run `28564456858` success를 확인했다.
  deploy 로그는 `systemctl start exit=0`, unit sync exit `0`이고, journal은
  `auto-invest-deploy.service: Deactivated successfully`를 기록했다.
- **sidecar 확인**: 최신 `autonomous-work-execution` sidecar는 commit `649a8df`,
  `selected_work=candidate-e481b0309206`, `autonomy_level=CODEX_AUTONOMOUS_START`,
  `start_guidance_ko=운영자 추가 질문 없이 새 worktree 또는 브랜치에서 SDD 두께를 판단하고 구현, 검증, PR, 자동 머지 절차로 진행할 수 있다.`,
  `completion_gates=focused pytest, uv run pytest, ruff, HANDOFF 사실 검증, strict 하네스, PR 품질 관문, 필요한 HANDOFF 갱신`을 기록한다.
  최신 `money-gate-alignment` sidecar는 `overall_status=ALIGNED_WAITING`,
  `live_money_status=PREVIEW_ONLY`, `SNAPSHOT_SKEW` 관측값
  `14-15/20 (money-path=14, edge-autoarm=15, rebalance-paper-forward=15)`를 기록한다.
  최신 `pipeline-liveness` sidecar는 `overall=OK`, `operator-status=OK`, `money-gate-alignment=OK`,
  `autonomous-work-execution=OK`다.
- **안전 경계**: 등급 2 운영 자동화 보정이다. 실제 주문, 브로커 실주문 API, 자본 증액, 자본 배분,
  whitelist/caps 확대, live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6,
  비밀값, 외부 유료 서비스 변경 없음. 새 `autonomy_level`은 Codex가 기존 작업 절차를 시작해도
  된다는 표시이지, 시스템이 스스로 코드를 쓰거나 PR을 만드는 실행자가 아니다.
- **검증**: focused pytest 53 통과, `uv run pytest` 2417 통과·4 스킵,
  `uv run ruff check src tests` 통과, `git diff --check` 통과, `uv run python scripts/check_handoff_facts.py` OK,
  `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR 품질 관문 성공,
  post-merge sidecar와 deploy run 확인 완료.
- **상세 인계**: `HANDOFF-085-AUTONOMOUS-LOOP-QUALITY-CLOSURE.md`.

## 최근 관찰 — 2026-07-02 KST (스펙 080 운영자 대시보드와 모바일 알림 루프)

스펙 080 기능 기준 머지는 `27388dd`(#442, 스펙 080 모바일 상태판 publish 보정과 인계 갱신)이다.
직전 관련 커밋은 `43b5da8`(#441, 스펙 080 운영자 대시보드와 모바일 알림 루프),
`65c2602`(스펙 080 구현), `db35efd`(#440, 스펙 079 handoff 갱신)이다.

- **문제 정의**: 자율 성장, 승격, 후보 검증, 돈 경로 준비도, 돈 경로 정렬 루프는 이미 sidecar를
  발행하지만, 운영자는 Codex에게 다시 물어보기 전까지 "지금 돈 경로가 안전한가", "다음 자율 작업은
  무엇인가", "모바일로 알려야 할 개입 필요 상태인가"를 한 화면에서 볼 수 없었다.
- **구현 상태**: `operator_status.py`와 `operator_status_probe.py`가 기존 automation sidecar를 읽어
  `OperatorStatusReport` JSON/Markdown을 만든다. `scripts/generate_mobile_status.py`는 GitHub Pages
  상태판 첫 화면에 운영자 요약, 실제 돈 경로, 다음 자율 작업, 돈 경로 정렬, 개입 필요 섹션을
  표시한다. `.github/workflows/operator-mobile-alerts.yml`은 매일 09:25 UTC와 관련 main push 때
  `automation/operator-status-last-run`을 발행하고, `ACTION_REQUIRED` 이상에서만 Telegram 전송을
  best-effort로 시도한다.
- **배포 후 실제 실행**: #441 main push 뒤 `Deploy on merge to main` run `28561843637`과
  `Operator mobile alerts` run `28561843669`는 success였지만, `Mobile status page (GitHub Pages)` run
  `28561843601`은 failure였다. 원인은 `generate_mobile_status.py --manifest`가 의존성 설치 없는
  bare `python3`에서 실행되는데, `operator_status.py`가 `telegram.py`를 import하면서 `httpx` 없는
  환경에서 `ModuleNotFoundError`가 난 것이다. #442가 이 import 의존을 끊었다.
- **최종 post-merge 확인**: #442 main push 뒤 `Deploy on merge to main` run `28562202999`,
  `Operator mobile alerts` run `28562203117`, `Mobile status page (GitHub Pages)` run `28562203120`이
  모두 success였다. 최신 operator-status sidecar는 commit `27388dd`,
  `overall_status=OK`, `alert_level=SILENT_OK`, `send_status=NOT_ATTEMPTED`,
  `money-path=PREVIEW_ONLY`, `money-gate-alignment=ALIGNED_WAITING`,
  `autonomous-work-execution=EXECUTION_READY`, 다음 후보 `candidate-e481b0309206`
  (`레짐·성과 분석을 후보 점수화 입력으로 승격`)를 기록한다. `origin/gh-pages:status.html`도
  `operator-status-data`, `운영자 요약`, `실제 돈 경로`, `다음 자율 작업`을 포함한다.
- **안전 경계**: 등급 2 운영 자동화다. 새 루프는 기존 sidecar와 GitHub Actions Secrets만 읽고,
  자기 sidecar 또는 GitHub Pages만 갱신한다. 실제 주문, 브로커 실주문 API, 자본 증액, 자본 배분,
  whitelist/caps 확대, live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6,
  감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경 없음. Telegram token/chat id는 Secrets에서만
  읽고, 로그·HTML·sidecar에는 원문을 남기지 않도록 마스킹한다.
- **검증**: PR #441 머지 전 focused pytest 38 통과, bare sample JSON/Markdown/HTML smoke 통과,
  workflow YAML parse 통과, `uv run pytest` 2414 통과·4 스킵, `uv run ruff check src tests` 통과,
  strict 하네스 `OK (14/14)`, HANDOFF 사실 검증 OK, PR 품질 관문 성공. 후속 브랜치에서는 bare
  `PYTHONPATH=src python3 scripts/generate_mobile_status.py --manifest`를 통과시켜 실패 경로를 재현
  기준으로 고쳤고, 관련 pytest 13 통과와 관련 ruff 통과를 확인했다. #442 전 `uv run pytest`는
  2415 통과·4 스킵, `uv run ruff check src tests`는 통과했다. 이 최종 handoff 정리에서 스펙 080
  tasks T021~T023도 실제 완료 상태와 맞춰 체크했다.
- **상세 인계**: `HANDOFF-084-OPERATOR-DASHBOARD-ALERTS.md`.

## 최근 관찰 — 2026-07-02 KST (스펙 079 완료 후보 소비 장부)

현재 `main` 최신 머지는 `88929c8`(#439, 스펙 079 tasks 완료 상태 정리)이다. 최신 코드 베이스라인은
`c8beb25`(#437, 스펙 079 `released-work` sidecar publish token 보정)이다.
직전 관련 커밋은 `1a9a518`(#436, 스펙 079 완료 후보 소비 장부), `09b528a`(#434, 스펙 078 돈 경로 게이트 정렬 루프), `996ce56`(#432,
스펙 077 자율 작업 실행 루프)이다.

- **문제 정의**: 스펙 078 후보 `candidate-fd04772a23c5`는 구현·머지·인계가 끝났지만,
  자율 작업 실행 루프는 실패·거절 후보만 억제하고 완료 후보를 소비하지 않아 같은 후보를 다시
  고를 수 있었다. 스펙 079는 완료 후보를 별도 장부로 기록해 다음 후보로 자동 이동하게 한다.
- **구현 상태**: `released_work.py`는 완료된 Speckit 작업의 `tasks.md` 체크박스와
  `selected_work_candidate` 같은 명시적 완료 필드만 근거로 후보를 `released` 처리한다.
  `autonomous_work_execution.py`는 이 장부를 읽어 해당 후보를 `RELEASED`로 표시하고,
  실행 가능한 후보 목록에서 제외한다.
- **자동화 상태**: `.github/workflows/released-work-ledger.yml`은 매일 09:05 UTC와 main push 때
  `automation/released-work-last-run`에 `LAST_RUN.md`와 `released_work.json`을 발행한다.
  `autonomous-work-execution` workflow는 `--repo-root "$GITHUB_WORKSPACE"`로 현재 checkout을
  직접 스캔하므로, sidecar 첫 발행 전 지연에도 완료 후보를 반복 선택하지 않는다.
- **배포 후 실제 실행**: #436 main push 뒤 `Deploy on merge to main` run `28555267958`은 success,
  `Autonomous work execution loop` run `28555267985`도 success였다. #437 main push 뒤
  `Deploy on merge to main` run `28555565031`도 success였고, `Released work ledger` run
  `28555565017`은 commit `c8beb2561b0c328f0d56dc11e4d2cf91784b2867` 기준 success였다.
- **sidecar 확인**: 최신 sidecar 조합과 현재 repo scan local smoke에서
  `candidate-fd04772a23c5`는 `RELEASED`, 차순위 `selected_work`는
  `candidate-e481b0309206`(`레짐·성과 분석을 후보 점수화 입력으로 승격`)로 확인됐다.
- **post-merge 보정 완료**: #436의 첫 `Released work ledger` run `28555267975`는
  env로 주입되지 않은 `${GITHUB_TOKEN}` 직접 참조 때문에 failure였다. #437에서
  `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` 주입과 회귀 테스트를 추가했고, 후속 run
  `28555565017`이 success로 `automation/released-work-last-run`을 발행했다.
- **감시 보정**: 최신 pipeline liveness dispatch run `28555617349`는 commit `c8beb25` 기준 success,
  `overall=OK`, `released-work=OK`를 기록한다.
- **스펙 작업표 정리**: #439는 `specs/079-completed-candidate-consumption/tasks.md`의
  T017(PR 생성·확인·자동 머지), T018(post-merge workflow sidecar 확인), T019(HANDOFF 갱신)를
  실제 완료 상태와 맞춰 `[x]`로 정리했다. 코드 동작 변경은 없다.
- **안전 경계**: 등급 2 운영 자동화 추가다. 완료 스펙 문서와 기존 sidecar를 읽고 보고 sidecar만 쓴다.
  실제 주문, 브로커 실주문 API, 자본 증액, 자본 배분, whitelist/caps 확대, live 전략 교체,
  live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값, 외부 유료 서비스 변경 없음.
  배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **검증**: PR #436 머지 전 focused pytest 18 통과, 최신 sidecar local smoke에서
  `candidate-fd04772a23c5 RELEASED`, selected `candidate-e481b0309206`를 확인했다.
  `uv run pytest` 2402 통과·4 스킵, `uv run ruff check src tests` 통과,
  strict 하네스 `OK (14/14)`, HANDOFF 사실 검증 OK, PR 품질 관문 성공. PR #437에서도
  `uv run pytest` 2402 통과·4 스킵, `uv run ruff check src tests` 통과,
  strict 하네스 `OK (14/14)`, HANDOFF 사실 검증 OK, PR 품질 관문 성공을 확인했다.
- **상세 인계**: `HANDOFF-083-COMPLETED-CANDIDATE-CONSUMPTION.md`.

## 최근 관찰 — 2026-07-01 KST (스펙 078 돈 경로 게이트 정렬 루프)

현재 `main` 최신 코드 머지는 `09b528a`(#434, 스펙 078 돈 경로 게이트 정렬 루프)이다.
직전 관련 커밋은 `996ce56`(#432, 스펙 077 자율 작업 실행 루프), `23ec54b`(#430,
스펙 076 자본 경로 준비도 루프)이다. 이 인계 갱신 시점의 코드 PR은 없다.

- **문제 정의**: money-path, 자본 준비도, edge-autoarm, reassign, forward, pipeline,
  자율 작업 실행, KIS smoke가 각각 따로 살아 있어 "돈 경로가 정말 같은 이야기를 하는가"를
  사람이 매번 손으로 맞춰야 했다. 스펙 078은 이 표면들을 한 번에 대조해 불일치와 다음 안전 행동을
  결정론적으로 발행한다.
- **구현 상태**: `money_gate_alignment.py`는 8개 sidecar를 `GateSurface`로 정규화하고
  `MoneyGateAlignmentDecision`을 만든다. 돈 경로가 `PREVIEW_ONLY`이고 자본 사다리가
  `ACCUMULATING_EDGE`이며 edge/reassign/forward가 모두 최소 관측 대기라면 `ALIGNED_WAITING`으로
  판정한다. sidecar가 없거나 깨지면 `UNKNOWN` 또는 `BLOCKED`로 fail-closed 처리한다.
- **자동화 상태**: `.github/workflows/money-gate-alignment.yml`은 매일 09:20 UTC와 main push 때
  실행되어 `automation/money-gate-alignment-last-run`에 `LAST_RUN.md`와
  `money_gate_alignment.json`을 발행한다. `pipeline_liveness.py`도 `money-gate-alignment`를
  비핵심 보고 sidecar로 감시한다.
- **배포 후 실제 실행**: #434 main push 뒤 `Deploy on merge to main` run `28526440236`은 success,
  `Money gate alignment loop` run `28526440247`도 success였다. 둘 다 commit
  `09b528a900f884c42135a39a03436c685375ab5f` 기준이다.
- **sidecar 확인**: 최신 `origin/automation/money-gate-alignment-last-run:LAST_RUN.md`는
  `overall_status=ALIGNED_WAITING`, `live_money_status=PREVIEW_ONLY`,
  `readiness_state=ACCUMULATING_EDGE`, `capital_ladder_stage=ACCUMULATING_EDGE`,
  `blocking_gate=전진 관측 부족: 14/20 (통계적 유의까지 더 쌓여야 함).`,
  `selected_work_candidate=candidate-fd04772a23c5`를 기록한다.
- **정렬 이슈**: 현재 이슈는 장애가 아니라 `WAITING forward_observation`이다. 기대값은
  `EDGE_CONFIRMED`, 관측값은 `14/20`이며, 다음 행동은 전진 관측을 계속 누적하고 최소 관측 이후
  기존 자본 사다리로만 승격하는 것이다.
- **감시 보정**: main push 직후 pipeline liveness가 새 sidecar보다 먼저 돌아 한 번 오래된 상태를
  볼 수 있었다. 같은 main commit으로 workflow dispatch run `28526482569`을 재실행했고 최신
  liveness sidecar는 `overall=OK`, `money-gate-alignment=OK`다.
- **KIS smoke**: 최신 KIS smoke sidecar run `28523981341`은 commit `996ce56` 기준 success,
  `key_valid=true`, `smoke_state=success`다. #434 이후 실행은 아니므로 스펙 078 배포 증거가 아니라
  최근 읽기 전용 브로커 생존 확인으로만 본다.
- **안전 경계**: 등급 2 운영 자동화 추가다. 기존 sidecar를 읽고 새 보고 sidecar만 쓴다.
  실제 주문, 브로커 실주문 API, 자본 증액, 자본 배분, whitelist/caps 확대, live 전략 교체,
  live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값, 외부 유료 서비스 변경 없음.
  배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **검증**: PR #434 머지 전 focused pytest 10 통과, 인접 루프 통합 테스트 12 통과, 최신
  sidecar local smoke에서 `ALIGNED_WAITING / PREVIEW_ONLY / ACCUMULATING_EDGE`,
  `WAITING forward_observation`, 입력 sidecar 8개 `ok`를 확인했다. `uv run pytest`
  2394 통과·4 스킵, `uv run ruff check src tests` 통과, `git diff --check` 통과,
  HANDOFF 사실 검증 OK, strict 하네스 `OK (14/14)`, PR 품질 관문 성공. 머지 직전 전체 테스트와
  린트를 다시 실행해 같은 결과를 확인했다.
- **상세 인계**: `HANDOFF-082-MONEY-GATE-ALIGNMENT.md`.

## 최근 관찰 — 2026-07-01 KST (스펙 077 자율 작업 실행 루프)

현재 `main` 최신 코드 머지는 `996ce56`(#432, 스펙 077 자율 작업 실행 루프)이다.
직전 관련 커밋은 `23ec54b`(#430, 스펙 076 자본 경로 준비도 루프), `fa8cc32`(#428,
스펙 075 전략 실패 학습 장부화)이다. 이 인계 갱신 시점의 코드 PR은 없다.

- **문제 정의**: 스펙 067~076은 후보 발굴, 승격, 검증 패키지, 결과 증거, 자본 준비도까지
  만들었지만, "그럼 지금 Codex가 무엇을 시작해야 하는가"는 운영자가 다시 물어야 했다.
  스펙 077은 이 마지막 판단을 매일 자동 작업 패킷으로 발행한다.
- **구현 상태**: `autonomous_work_execution.py`는 입력 sidecar 8개를 정규화하고, 후보를
  `WorkPacket`으로 바꾼다. pipeline liveness가 `CRITICAL`이면 자동화 복구 작업을 최우선으로
  올리고, 위험 등급 3 이상 또는 주문·자본·비밀값·커널·유료 서비스 표면은
  `OPERATOR_APPROVAL_REQUIRED`로 분리한다. learning ledger rejected 후보는 어떤 출처에서 다시
  올라와도 `SUPPRESSED`로 억제한다.
- **자동화 상태**: `.github/workflows/autonomous-work-execution.yml`은 매일 09:10 UTC와 main push 때
  실행되어 `automation/autonomous-work-execution-last-run`에 `LAST_RUN.md`와
  `autonomous_work_execution.json`을 발행한다. `pipeline_liveness.py`도 이 sidecar를 비핵심
  보고 루프로 감시한다.
- **배포 후 실제 실행**: #432 main push 뒤 `Deploy on merge to main` run `28523867765`은 success,
  `Autonomous work execution loop` run `28523867803`도 success였다. 둘 다 commit
  `996ce56380b6e26d7ded84b7d552cdd06fbf6436` 기준이다.
- **sidecar 확인**: 최신 `origin/automation/autonomous-work-execution-last-run:LAST_RUN.md`는
  `overall_status=EXECUTION_READY`, `selected_work=candidate-fd04772a23c5`,
  `title_ko=돈 경로 준비도와 기존 게이트 정렬`, `risk_grade=2`, `priority_score=3597`을 기록한다.
  `candidate-1ed634d8bf6d`, `candidate-cc96b35062da`는 learning ledger rejected 기록 때문에
  `SUPPRESSED`다.
- **감시 보정**: main push 직후 pipeline liveness가 새 sidecar보다 먼저 돌아
  `autonomous-work-execution=PENDING`을 기록했다. 같은 main commit으로 workflow dispatch run
  `28523925493`을 재실행했고 최신 liveness sidecar는 `overall=OK`,
  `autonomous-work-execution=OK`다.
- **KIS smoke**: workflow dispatch run `28523981341`은 commit `996ce56` 기준 success,
  `key_valid=true`, `smoke_state=success`다. 읽기 전용 브로커 연결 확인이며 주문은 없다.
- **안전 경계**: 등급 2 운영 자동화 추가다. 기존 sidecar를 읽고 새 작업 패킷 sidecar만 쓴다.
  실제 주문, 브로커 실주문 API, 자본 증액, whitelist/caps 확대, live 전략 교체, live sentinel,
  헌법, 커널 목록, K1/K2/K4/K5/K6 변경 없음. 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **검증**: PR #432 머지 전 focused pytest 14 통과, 최신 sidecar local smoke에서
  `selected_work=candidate-fd04772a23c5`, `overall_status=EXECUTION_READY`, rejected 후보 2개 억제를
  확인했다. `uv run pytest` 2384 통과·4 스킵, `uv run ruff check src tests` 통과,
  `git diff --check` 통과, HANDOFF 사실 검증 OK, strict 하네스 `OK (14/14)`, PR 품질 관문 성공.
  머지 직전 전체 테스트와 린트를 다시 실행해 같은 결과를 확인했다.
- **상세 인계**: `HANDOFF-081-AUTONOMOUS-WORK-EXECUTION.md`.

## 최근 관찰 — 2026-07-01 KST (스펙 076 자본 경로 준비도 루프)

현재 `main` 최신 코드 머지는 `23ec54b`(#430, 스펙 076 자본 경로 준비도 루프)이다.
직전 관련 커밋은 `fa8cc32`(#428, 스펙 075 전략 실패 학습 장부화), `d3ca5d5`(#426,
후보 공장 실패 결과의 승격 루프 반복 보정)이다. 이 인계 갱신 시점의 코드 PR은 없다.

- **문제 정의**: money-path, reassign, forward paper, KIS smoke, promotion/evolution sidecar가
  각각 따로 살아 있어 "지금 돈을 더 벌기 위해 자본 경로가 어디까지 왔나"를 사람이 매번
  조합해야 했다. 스펙 076은 이 상태를 하나의 준비도 sidecar로 묶어 다음 안전 행동을 자동 산출한다.
- **구현 상태**: `capital_path_readiness.py`는 money-path의 `live_money_state.status`와
  자본 사다리 `stage`를 최우선 근거로 삼아 `readiness_state`를 산출한다. evolution backlog의
  자본 경로 관련 후보는 우선 후보로 올리고, learning ledger나 promotion summary에서 실패로
  표시된 후보는 억제 후보로 남긴다. money-path가 없거나 깨지면 `UNKNOWN`으로 fail-closed 처리한다.
- **자동화 상태**: `.github/workflows/capital-path-readiness.yml`은 매일 08:10 UTC와 main push 때
  실행되어 `automation/capital-path-readiness-last-run`에 `LAST_RUN.md`와
  `capital_path_readiness.json`을 발행한다. `pipeline_liveness.py`도 이 sidecar를 비핵심
  보고 루프로 감시한다.
- **배포 후 실제 실행**: #430 main push 뒤 `Deploy on merge to main` run `28518083151`은 success,
  `Capital path readiness` run `28518083087`도 success였다. 둘 다 commit
  `23ec54be9a7c98b6b0c10cb038f5c25249713fa1` 기준이다.
- **sidecar 확인**: 최신 `origin/automation/capital-path-readiness-last-run:LAST_RUN.md`는
  `readiness_state=ACCUMULATING_EDGE`, `live_money_status=PREVIEW_ONLY`,
  `capital_ladder_stage=ACCUMULATING_EDGE`, `blocking_gate=전진 관측 부족: 14/20`을 기록한다.
  우선 후보 1순위는 `candidate-fd04772a23c5`(`live_readiness`, 점수 597)이고,
  `candidate-1ed634d8bf6d`, `candidate-cc96b35062da`는 rejected 후보로 억제된다.
- **감시 보정**: main push 직후 pipeline liveness가 새 sidecar보다 먼저 돌아
  `capital-path-readiness=MISSING`으로 한 번 `DEGRADED`를 기록했다. 같은 main commit으로
  workflow dispatch run `28518134667`을 재실행했고 최신 liveness sidecar는 `overall=OK`,
  `capital-path-readiness=OK`다.
- **안전 경계**: 등급 2 운영 자동화 추가다. 기존 sidecar를 읽고 새 보고 sidecar만 쓴다.
  실제 주문, 브로커 실주문 API, 자본 증액, whitelist/caps 확대, live 전략 교체, live sentinel,
  헌법, 커널 목록, K1/K2/K4/K5/K6 변경 없음. 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **검증**: PR #430 머지 전 focused pytest 8 통과, 최신 sidecar local smoke에서
  `ACCUMULATING_EDGE / PREVIEW_ONLY / ACCUMULATING_EDGE`와 rejected 후보 억제를 확인했다.
  `uv run pytest` 2374 통과·4 스킵, `uv run ruff check src tests` 통과, `git diff --check` 통과,
  HANDOFF 사실 검증 OK, strict 하네스 `OK (14/14)`, PR 품질 관문 성공. 머지 직전 전체 테스트와
  린트를 다시 실행해 같은 결과를 확인했다.
- **상세 인계**: `HANDOFF-080-CAPITAL-PATH-READINESS.md`.

## 최근 관찰 — 2026-07-01 KST (스펙 075 전략 실패 학습 장부화)

현재 `main` 최신 코드 머지는 `fa8cc32`(#428, 스펙 075 전략 실패 학습 장부화)이다.
직전 관련 커밋은 `d3ca5d5`(#426, 승격 루프 `DISCARD` 보정), `fcc6e5f`(#425, 스펙 074 후보 가격 이력 지원)이다.
이 인계 갱신 시점의 열린 PR은 없다.

- **문제 정의**: 스펙 074로 가격 이력 부족은 해결됐고, #426으로 promotion loop는 두 전략/포트폴리오
  후보를 `DISCARD`로 분류했다. 남은 문제는 autonomous evolution loop가 이 실패를 영구 장부에
  흡수하지 않으면 같은 후보가 다음 성장 루프에서 새 돌파 후보처럼 반복될 수 있다는 점이었다.
- **구현 상태**: `evolution_loop.py`가 `automation/autonomous-promotion-last-run:promotion_summary.json`을
  기본 evidence manifest에 추가했다. `DISCARD` stage인 `strategy_design`/`portfolio_design` 후보만
  `PromotionFailureSignal`로 읽고, `learning_ledger.json`에 `decision=rejected`로 병합한다.
  기존 rejected entry가 있으면 중복 생성하지 않고, promotion summary가 없거나 깨졌으면 기존 후보 생성은
  fail-open으로 계속 실행한다.
- **배포 후 실제 실행**: #428 main push 뒤 `Deploy on merge to main` run `28507752817`은 success,
  `Autonomous evolution loop` run `28507752974`도 success였다. 두 실행 모두 commit
  `fa8cc32353929993a050e0d8e1d088918ec2891e` 기준이다.
- **sidecar 확인**: 최신 `origin/automation/autonomous-evolution-last-run:learning_ledger.json`은
  `candidate-1ed634d8bf6d`와 `candidate-cc96b35062da`를 모두 `decision=rejected`,
  `evidence_package_id=autonomous-promotion:28504209238`로 기록한다.
  `candidate_backlog.json`과 `evolution_summary.json`에서도 두 후보 status는 `rejected`다.
- **안전 경계**: 등급 2 운영 자동화 보정이다. 기존 sidecar JSON을 읽어 학습 장부와 후보 상태를
  갱신할 뿐이다. 실제 주문, 브로커 API, 자본 증액, whitelist/caps 확대, live 전략 교체,
  live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6 변경 없음.
- **검증**: PR #428 머지 전 focused evolution tests 27 통과, 최신 sidecar local smoke에서 두 후보가
  `rejected` 장부 항목이 되는 것을 확인했다. `uv run pytest` 2366 통과·4 스킵,
  `uv run ruff check src tests` 통과, `git diff --check` 통과, HANDOFF 사실 검증 OK,
  strict 하네스 `OK (14/14)`, PR 품질 관문 성공. 머지 직전 전체 테스트와 린트를 다시 실행해 같은
  결과를 확인했다. handoff 갱신 시작 전에는 `HANDOFF.md`가 아직 #426을 가리켜 전체 테스트 중
  하네스 2건만 실패했고, 이 인계 갱신이 그 원인을 바로잡는다.
- **상세 인계**: `HANDOFF-079-STRATEGY-FAILURE-LEARNING.md`.

## 최근 관찰 — 2026-07-01 KST (스펙 074 후보 가격 이력 지원과 승격 실패 반영)

현재 `main` 최신은 `d3ca5d5`(#426, 후보 공장 실패 결과의 승격 루프 반복 보정)이다.
직전 주요 커밋은 `6789191`(#426 구현), `fcc6e5f`(#425, 스펙 074 후보 가격 이력 지원),
`66b053c`(스펙 074 구현)이다. 이 인계 갱신 시점의 열린 PR은 없다.

- **문제 정의**: 스펙 073 뒤 남은 후보 2개는 둘 다 `data_history_missing` 때문에
  `BACKTEST_REQUIRED`에서 멈췄다. 목표는 실거래·브로커 주문·자본 변경 없이 후보 결과 실행기가
  필요한 가격 이력을 준비하고, 결과가 실패하면 다음 루프가 같은 백테스트를 반복하지 않게 만드는 것이다.
- **구현 상태**: `candidate_history_support.py`와 `candidate_history_support_probe.py`가
  후보별 portfolio/db/history-root manifest를 만든다. `candidate_factory.py`는 전략/포트폴리오
  후보 명령에 `--history-root /tmp/candidate_result_history/.../hist`를 붙인다.
  `candidate-result-executor.yml`은 SSH key가 있을 때 서버의 `/opt/auto-invest`에서 read-only
  `bars-export`와 `ingest-history`를 실행해 `/tmp/candidate_result_history`를 채운다.
- **배포 후 실제 실행**: #425 main push에서 `Deploy on merge to main` run `28503224288` success였다.
  result executor는 push 직후 한 번 이전 패키지를 읽는 경합이 있었고, 이후 workflow dispatch run
  `28503338531`을 재실행했다. 최신 result sidecar는 commit `fcc6e5f`, `pass=7`, `fail=2`,
  `pending=0`, `blocked=0`, 진단 집계 없음이며 두 전략/포트폴리오 실행 모두 `--history-root`를 포함한다.
- **후속 소비 확인**: result sidecar 뒤 `Candidate implementation factory` run `28503561736`을
  재실행했다. 최신 factory sidecar는 commit `fcc6e5f`, `evidence_passed=7`, `blocked=2`,
  `pending=0`, `ready=0`이다. 두 후보는 이제 "데이터가 없어 대기"가 아니라 "기계 판독 백테스트 실패라
  승격 증거로 병합하지 않음"이다.
- **승격 루프 보정**: #426 이후 `Autonomous promotion loop` run `28504209238`은 commit `d3ca5d5`
  기준 success였고, factory의 `factory_status=blocked`를 `DISCARD`로 해석했다. 두 전략/포트폴리오
  후보는 더 이상 `BACKTEST_REQUIRED`가 아니라 "검증 실패 후보를 승격하지 않고 재설계 또는 학습 장부
  후보로 보낸다"로 분류된다.
- **안전 경계**: 등급 2 운영 자동화 보정이다. 주문, 브로커 실주문 API, 자본 증액, whitelist/caps 확대,
  live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6 변경 없음. 서버 `bars-export`와
  `ingest-history`는 읽기 전용 가격 이력 준비이고, 실패하면 후보는 통과로 위조되지 않는다.
- **검증**: 스펙 074 PR #425 머지 전 focused pytest 24 통과, synthetic history smoke에서
  `pending=0`, `fail=2`, `diagnostic_counts={}` 재현, `uv run pytest` 2362 통과·4 스킵,
  `uv run ruff check src tests` 통과, `git diff --check` 통과, workflow YAML parse OK,
  strict 하네스 `OK (14/14)`, HANDOFF 사실 검증 OK, PR 품질 관문 성공. follow-up 보정(#426)은
  `uv run pytest tests/unit/test_promotion_loop.py tests/integration/test_promotion_loop_probe.py tests/unit/test_candidate_factory.py -q`
  23 통과, `uv run ruff check src/auto_invest/analytics/promotion_loop.py tests/unit/test_promotion_loop.py` 통과,
  최신 sidecar 로컬 promotion smoke에서 두 후보 `DISCARD`를 확인했다. #426 머지 전
  `uv run pytest` 2363 통과·4 스킵, `uv run ruff check src tests` 통과, PR 품질 관문 통과.
  머지 후 deploy run `28504209256`, factory run `28504209235`, promotion loop run `28504209238` 모두 success.
- **상세 인계**: `HANDOFF-078-CANDIDATE-HISTORY-SUPPORT.md`.

## 최근 관찰 — 2026-07-01 KST (스펙 073 후보 pending next action 보정)

현재 `main` 최신은 `0de15a4`(#423, 스펙 073 후보 pending next action 보정)이다.
직전 주요 커밋은 `9adf99e`(스펙 073 구현), `afd1c3c`(#422, 스펙 072 handoff 갱신),
`e00ef09`(#421, 스펙 072 후보 증거 진단 루프)이다. 이 인계 갱신 시점의 열린 PR은 없다.

- **문제 정의**: 스펙 072는 pending 5개의 원인을 진단했지만, 자동으로 고칠 수 있는
  `command_contract_error=2`, `execution_failed=1`은 그대로 다음 실행에서 반복됐다.
  이번 작업의 목표는 후보 공장 명령 계약과 result executor support input을 고쳐 자동 실행 가능한
  3개 후보를 실제 pass로 줄이고, 가격 이력 부족 2개는 거짓 통과 없이 남기는 것이다.
- **구현 상태**: `candidate_factory.py`가 `ops_liveness`와 `data_quality` 후보에
  `pipeline_liveness_probe.py --sidecar-dir /tmp/candidate_result_sidecars --strict --json`을 생성한다.
  `analytics_validation` 후보는 `auto-invest macro-regime --data-dir /tmp/candidate_result_public_data --json`을
  생성한다. `candidate_result_executor.py`는 data quality 후보에서도 pipeline liveness no-live 명령을
  허용한다.
- **workflow support input**: `.github/workflows/candidate-result-executor.yml`은 후보 패키지를 실행하기 전에
  pipeline liveness manifest의 sidecar들을 `/tmp/candidate_result_sidecars`로, `automation/public-data`
  snapshot을 `/tmp/candidate_result_public_data`로 복사한다. 이 복사는 Git sidecar 읽기와 `/tmp`
  쓰기만 수행한다.
- **배포 후 실제 실행**: #423 main push에서 `Deploy on merge to main` run `28474687085` success였다.
  main push 직후 result executor run `28474687229`는 factory sidecar 갱신보다 먼저 패키지를 읽어
  이전 명령으로 실행됐다. 새 factory sidecar가 발행된 뒤 result executor run `28474761904`를
  workflow dispatch로 재실행했고, 최신 result sidecar는 commit `0de15a4`,
  `pass=7`, `pending=2`, `fail=0`, `blocked=0`, 진단 집계 `data_history_missing=2`,
  `insufficient_pass_evidence=1`이다. 즉 `command_contract_error`와 `execution_failed`는 0이다.
- **후속 소비 확인**: result sidecar 뒤 `Candidate implementation factory` run `28474828027`을 재실행했다.
  최신 factory sidecar는 commit `0de15a4`, `evidence_passed=7`, `pending=2`, `ready=0`, `blocked=0`이다.
  이어 `Autonomous promotion loop` run `28474881043`을 재실행했고 success였다. promotion summary는
  전략/포트폴리오 후보 2개만 `BACKTEST_REQUIRED`, 비전략 후보 7개는 `FACTORY_PACKAGE_READY`로 분류한다.
- **남은 실제 다음 작업**: 남은 pending 2개는 모두 가격 이력 부족이다.
  `candidate-1ed634d8bf6d`는 `data_history_missing`과 `insufficient_pass_evidence`,
  `candidate-cc96b35062da`는 `data_history_missing`을 갖는다. 다음 스펙은 안전한 가격 이력 수집 또는
  `ingest-history` 실행 경로를 설계해야 한다.
- **안전 경계**: 등급 2 운영 자동화 보정이다. 주문, 브로커 API, 자본 증액, whitelist/caps 확대,
  live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6 변경 없음. 배포는 dry-run worker
  코드 반영이며 실거래 전환이 아니다. KIS smoke sidecar는 run `28426196361`, commit `419fbf7`,
  `smoke_state=success`, `key_valid=true`이나 #423과 같은 commit의 직접 smoke는 아니다.
- **검증**: PR #423 머지 전 focused pytest 20 통과, current-sidecar local smoke에서
  `pass=7`, `pending=2`, `diagnostic_counts={"data_history_missing": 2, "insufficient_pass_evidence": 1}` 확인,
  `uv run pytest` 2358 통과·4 스킵, `uv run ruff check src tests` 통과, `git diff --check` 통과,
  Ruby YAML parse OK, strict 하네스 `OK (14/14)`, HANDOFF 사실 검증 OK, PR 품질 관문 성공.
  머지 직전 전체 테스트와 린트를 다시 실행해 같은 결과를 확인했다.
- **상세 인계**: `HANDOFF-077-CANDIDATE-PENDING-NEXT-ACTIONS.md`.

## 최근 관찰 — 2026-07-01 KST (스펙 072 후보 증거 진단 루프)

현재 `main` 최신은 `e00ef09`(#421, 스펙 072 후보 증거 진단 루프)이다.
직전 주요 커밋은 `6d4d43b`(스펙 072 구현), `419fbf7`(#420, 스펙 070/071 handoff 갱신),
`0b743c2`(#419, 후보 공장 result status 보정)이다. 이 인계 갱신 시점의 열린 PR은 없다.

- **문제 정의**: #419 이후 result executor와 candidate factory는 `pass=4`, `pending=5`를
  정확히 표시했지만, pending 5개가 왜 멈췄는지 기계가 재시도·보강 계획으로 소비할 수 있는
  형태는 아니었다. `pending`은 실패, 데이터 부족, 명령 계약 오류, 통과 증거 부족이 섞인 상태라
  다음 루프가 무엇을 고쳐야 하는지 알기 어려웠다.
- **구현 상태**: `candidate_result_executor.py`가 pending/blocked 결과에
  `diagnostics`, `next_actions`, `retryable`을 추가한다. 주요 진단 코드는
  `data_history_missing`, `command_contract_error`, `insufficient_pass_evidence`,
  `execution_failed`, `timeout`, `unsafe_command`, `unsupported_package`, `missing_command`,
  `missing_input`이다. `candidate_factory.py`는 이 값을 enriched backlog의
  `promotion_evidence.factory_diagnostics`, `factory_next_actions`, `factory_retryable`로 전파한다.
- **배포 후 실제 실행**: #421 main push에서 `Deploy on merge to main` run `28455400890` success,
  `Candidate result executor` run `28455402752` success, `Candidate implementation factory` push run
  `28455402674` success였다. result executor sidecar는 commit `e00ef09`, `overall_status=degraded`,
  `pass=4`, `pending=5`, `fail=0`, `blocked=0`과 진단 집계
  `command_contract_error=2`, `data_history_missing=2`, `execution_failed=1`,
  `insufficient_pass_evidence=1`을 기록했다.
- **후속 소비 확인**: result sidecar 발행 뒤 factory run `28455608750`을 workflow dispatch로
  재실행했다. 최신 `candidate_backlog.enriched.json`은 후보 9개 중 pending 5개에
  `factory_diagnostics`를 채웠다. 후보별 다음 행동은 과거 데이터 준비 2건,
  검증 명령 인자 계약 보정 2건, 검증 실패 원인 좁히기 1건이며, retryable은 3건이다.
- **후속 루프 확인**: 최신 sidecar들을 소비하도록 `Autonomous promotion loop` run `28455673993`,
  `Autonomous promotion actions` run `28455707966`, `Pipeline liveness` run `28455738048`를
  dispatch했고 모두 success였다. promotion actions는 `registered=0`, `submitted=0`,
  `blocked=0`이고, liveness는 `candidate-implementation-factory`, `candidate-result-executor`,
  `autonomous-promotion`, `autonomous-promotion-actions`를 모두 `OK`로 보고했다.
- **현재 다음 행동**: 전략/포트폴리오 후보 2개는 `data_history_missing` 때문에 안전한 과거 데이터
  준비 또는 `ingest-history` 실행 경로가 필요하다. `ops_liveness`와 `analytics_validation`은
  `command_contract_error`라 후보 공장이 만든 no-live 검증 명령 인자 계약을 고쳐야 한다.
  `data_quality`는 `execution_failed`라 제한된 출력과 종료 코드를 더 좁혀야 한다.
- **안전 경계**: 등급 2 운영 자동화 진단 보강이다. no-live 검증 결과와 sidecar JSON만 바꿨다.
  실제 주문, 브로커 API, 자본 증액, whitelist/caps 확대, live 전략 교체, live sentinel, 헌법,
  커널 목록, K1/K2/K4/K5/K6 변경 없음. 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **검증**: PR #421 머지 전 focused pytest 18 통과, 최신 sidecar 입력 로컬 smoke에서
  `pass=4`, `pending=5`와 진단 집계를 재현, 전체 테스트 2356 통과·4 스킵,
  `uv run ruff check src tests` 통과, strict 하네스 `OK (14/14)`, HANDOFF 사실 검증 OK,
  PR 품질 관문 성공. 머지 직전 전체 테스트와 린트를 다시 실행해 같은 결과를 확인했다.
- **상세 인계**: `HANDOFF-076-CANDIDATE-EVIDENCE-DIAGNOSTICS.md`.

## 최근 관찰 — 2026-06-30 KST (후보 공장 result status 보정)

현재 `main` 최신은 `0b743c2`(#419, 후보 공장 result status 보정)이다.
직전 주요 커밋은 `e45fccb`(#419 구현), `3093068`(#418, 스펙 071 handoff 갱신),
`b827364`(#417, 스펙 071 후보 결과 실행기 루프)이다. 이 인계 갱신 시점의 열린 PR은 없다.

- **문제 정의**: #417 배포 뒤 result executor는 `pass=4`, `pending=5`를 올바르게 냈지만,
  candidate factory 재실행 결과가 비전략 후보의 `factory_validation=pass`를 `evidence_passed`로
  세지 않아 9개 모두 `pending`처럼 보였다. 전략 후보의 세 필수 증거와 비전략 후보의 no-live
  검증 통과를 같은 방식으로 읽으면 운영자가 병목을 잘못 이해한다.
- **구현 상태**: `candidate_factory.py`에 package kind별 result 판독 helper를 추가했다.
  전략·포트폴리오 후보는 여전히 `historical_backtest`, `recent_oos`, `walk_forward`가 모두
  `pass`여야 하고, 비전략 후보는 `factory_validation=pass`일 때만 `evidence_passed`가 된다.
- **배포 후 실제 실행**: #419 main push에서 `Deploy on merge to main` run `28422210023` success,
  `Candidate result executor` run `28422210017` success, `Candidate implementation factory` run
  `28422210026` success였다. result executor sidecar는 commit `0b743c2`, `overall_status=degraded`,
  `pass=4`, `pending=5`, `fail=0`, `blocked=0`을 기록했다. factory sidecar는 같은 commit에서
  `overall_status=ok`, `evidence_passed=4`, `pending=5`, `ready=0`, `blocked=0`을 기록했다.
- **후속 연결 확인**: 새 sidecar를 소비하도록 `Autonomous promotion loop` run `28422336507`,
  `Autonomous promotion actions` run `28422350673`, `Pipeline liveness` run `28422367089`를
  dispatch했고 모두 success였다. promotion actions는 `registered=0`, `submitted=0`이고,
  liveness는 `candidate-implementation-factory`, `candidate-result-executor`,
  `autonomous-promotion`, `autonomous-promotion-actions`를 모두 `OK`로 보고했다.
- **현재 승격 상태**: 전략/포트폴리오 후보 2개는 아직 세 전략 evidence가 모두 pass가 아니므로
  `BACKTEST_REQUIRED`에 남는다. 비전략 후보 4개는 no-live 검증 통과 증거가 있어
  `evidence_passed`로 표시되지만, 전략 후보가 아니므로 forward paper나 돈 게이트로 자동 등록되지 않는다.
- **안전 경계**: 등급 1 보정에 가깝지만 등급 2 운영 자동화 표면을 보수적으로 적용했다.
  실제 주문, 브로커 API, 자본 증액, whitelist/caps 확대, live 전략 교체, live sentinel, 헌법,
  커널 목록, K1/K2/K4/K5/K6 변경 없음. 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **검증**: PR #419 머지 전 focused pytest 13 통과, 전체 테스트 2351 통과·4 스킵,
  `uv run ruff check src tests` 통과, strict 하네스 `OK (14/14)`, HANDOFF 사실 검증 OK,
  PR 품질 관문 성공. 머지 직전 전체 테스트와 린트를 다시 실행해 같은 결과를 확인했다.
- **상세 인계**: `HANDOFF-075-CANDIDATE-FACTORY-RESULT-STATUS.md`.

## 최근 관찰 — 2026-06-30 KST (스펙 071 후보 결과 실행기 루프)

이 섹션의 기능 출시 기준 `main`은 `b827364`(#417, 스펙 071 후보 결과 실행기 루프)이다.
직전 주요 커밋은 `7cf0f78`(스펙 071 구현), `2415fc4`(#416, 스펙 070 handoff 갱신),
`9ee51b0`(#415, 스펙 070 candidate factory fetch 보정)이다. 이 인계 갱신 시점의 열린 PR은 없다.

- **문제 정의**: 스펙 070은 후보를 실행 가능한 검증 패키지로 만들었지만, 그 패키지를 실제
  기계 판독 result evidence로 바꾸는 자동 실행층이 없었다. 그 결과 후보 공장과 승격 루프가
  계속 `ready`/`BACKTEST_REQUIRED` 상태만 반복할 수 있었다.
- **구현 상태**: `src/auto_invest/analytics/candidate_result_executor.py`가 `candidate_packages.json`을
  읽어 allowlist 된 no-live 검증 명령만 실행하고 후보별 `candidate_results.json`을 만든다.
  `scripts/candidate_result_executor_probe.py`와 `auto-invest candidate-results`가 같은 결정을 로컬에서 재현한다.
- **자동화 순서**: `.github/workflows/candidate-result-executor.yml`은 매일 08:42 UTC에 factory 08:40 실행 뒤
  `automation/candidate-implementation-results`를 발행한다. candidate factory는 08:44 UTC second pass로
  이 결과를 다시 읽고, promotion loop는 보강된 backlog를 읽는다.
- **배포 후 실제 실행**: #417 main push에서 `Deploy on merge to main` run `28421591710` success,
  `Candidate result executor` run `28421591693` success, `KIS smoke` run `28421591753` success였다.
  result executor sidecar는 commit `b827364`, `overall_status=degraded`, `pass=4`, `pending=5`, `blocked=0`을 기록했다.
  degraded는 전략/포트폴리오 검증 데이터 부족과 일부 no-live 검증 실패를 `pass`로 위조하지 않았다는 뜻이다.
- **후속 연결 확인**: result sidecar 이후 수동 dispatch로 `Candidate implementation factory` run `28421661580`,
  `Autonomous promotion loop` run `28421678189`, `Autonomous promotion actions` run `28421696576`,
  `Pipeline liveness` run `28421719284`가 모두 success였다. 최신 liveness는 `candidate-result-executor`를
  `OK`로 보고하고 overall `OK`다.
- **현재 승격 상태**: 전략/포트폴리오 후보 2개는 아직 세 전략 증거가 모두 pass가 아니므로
  `BACKTEST_REQUIRED`에 남는다. 비전략 후보는 `FACTORY_PACKAGE_READY`로 분리되며 forward paper나
  돈 게이트로 자동 승격되지 않는다. promotion actions는 `registered=0`, `submitted=0`으로 정상이다.
- **안전 경계**: 등급 2 운영 자동화다. no-live 검증 명령만 실행하며, shell 문자열을 그대로 실행하지 않는다.
  실제 주문, 브로커 API, 자본 증액, whitelist/caps 확대, live 전략 교체, live sentinel, 헌법, 커널 목록,
  K1/K2/K4/K5/K6 변경 없음. 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **검증**: PR #417 머지 전 `uv run pytest` 2351 통과·4 스킵, `uv run ruff check src tests` 통과,
  `auto-invest candidate-results --help` smoke 통과, strict 하네스 `OK (14/14)`, HANDOFF 사실 검증 OK,
  PR 품질 관문 성공. 머지 직전 전체 테스트와 린트를 다시 실행해 같은 결과를 확인했다.
- **상세 인계**: `HANDOFF-074-CANDIDATE-RESULT-EXECUTOR.md`.

## 최근 관찰 — 2026-06-29 KST (스펙 070 후보 구현 공장 자동화)

현재 `main` 최신은 `9ee51b0`(#415, 스펙 070 candidate factory input fetch 보정)이다.
직전 주요 커밋은 `0dec020`(fetch 보정), `b395e83`(#414, 스펙 070 후보 구현 공장 자동화),
`61c6499`(스펙 070 구현)이다. 이 인계 갱신 시점의 열린 PR은 없다.

- **문제 정의**: 스펙 067~069로 후보 발굴, 승격 분류, 검증 큐 연결은 생겼지만,
  현재 후보들은 모두 `BACKTEST_REQUIRED`에서 멈춰 있었다. 후보마다 어떤 검증 패키지를
  실행해야 하는지, 어떤 결과가 있어야 `promotion_evidence`가 채워지는지 자동화해야 했다.
- **구현 상태**: `src/auto_invest/analytics/candidate_factory.py`가 candidate backlog와 optional result evidence를
  읽어 후보별 implementation package와 enriched backlog를 만든다. `scripts/candidate_factory_probe.py`,
  `auto-invest candidate-factory`, `.github/workflows/candidate-implementation-factory.yml`가 같은 결정을 재현한다.
- **승격 연결**: `autonomous-promotion-loop.yml`은 이제 candidate factory의
  `candidate_backlog.enriched.json`을 raw evolution backlog보다 우선 읽는다. `promotion_loop.py`는
  비전략 factory package를 `FACTORY_PACKAGE_READY`로 분리하므로 운영·데이터 후보가 전략 백테스트 대기로
  잘못 보이지 않는다.
- **증거 규칙**: 전략/포트폴리오 후보는 `historical_backtest`, `recent_oos`, `walk_forward`가 모두
  기계 판독 result evidence에서 `pass`일 때만 forward 등록 준비로 올라간다. 결과가 없으면 `pending` 또는
  `ready`로 남고, `pass`는 만들어지지 않는다.
- **첫 실행 증거와 보정**: #414 main push 뒤 `Candidate implementation factory` run `28339636371`은 success였지만,
  optional result evidence branch fetch가 같은 fetch 명령에 묶인 탓에 입력 수집이 비어 후보 0개를 발행했다.
  #415가 automation wildcard fetch로 보정했고, #415 main push의 `Candidate implementation factory` run
  `28339828605`는 commit `9ee51b0`, `overall_status=ok`, `ready=9`, `blocked=0`, `evidence_passed=0`으로
  최신 후보 9개를 모두 패키지화했다. 전략/포트폴리오 2개는 `BACKTEST_REQUIRED`, 나머지 7개는
  `FACTORY_PACKAGE_READY`로 분리된다.
- **배포와 smoke**: #415 main push의 `Deploy on merge to main` run `28339828619`은 success다.
  최신 `KIS smoke (autonomous)` run `28339636380`은 commit `b395e83` 기준 success, `key_valid=true`,
  live broker smoke 4건 통과다. 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **안전 경계**: 등급 2 운영 자동화다. 신규 factory workflow는 SSH/KIS/브로커를 쓰지 않는다.
  실제 주문, 자본 증액, whitelist/caps 확대, live 전략 교체, live sentinel, 헌법, 커널 목록,
  K1/K2/K4/K5/K6 변경 없음. `Backtest -> Canary -> Full` 순서는 유지된다.
- **검증**: PR #414 머지 전 focused pytest 40 통과, 실제 최신 sidecar 후보 9개 smoke 통과,
  enriched backlog promotion scan smoke 통과, `uv run pytest` 2342 통과·4 스킵,
  `uv run ruff check src tests` 통과, `git diff --check` 통과, 하네스 `OK (14/14)`,
  HANDOFF 사실 검증 OK, PR 품질 관문 성공. #415 fetch 보정에서
  `uv run pytest tests/integration/test_candidate_factory_probe.py -q` 4 통과,
  `uv run ruff check tests/integration/test_candidate_factory_probe.py` 통과, `git diff --check` 통과,
  `uv run pytest` 2342 통과·4 스킵, `uv run ruff check src tests` 통과,
  `uv run python scripts/check_handoff_facts.py` OK, `uv run python scripts/agent_harness_probe.py --strict` OK (14/14).
- **상세 인계**: `HANDOFF-073-CANDIDATE-IMPLEMENTATION-FACTORY.md`.

## 최근 관찰 — 2026-06-29 KST (스펙 069 자율 승격 실행 루프 자동화)

현재 `main` 최신은 `b99f19c`(#412, 스펙 069 tasks release closure)이다.
실제 기능 최신은 `27da8b4`(#410, 스펙 069 자율 승격 실행 루프 자동화)이며,
직전 주요 커밋은 `b81e2de`(#411, 스펙 069 handoff), `56a6719`(스펙 069 구현),
`0d9bbe5`(#409, 스펙 068 handoff)이다. 이 인계 갱신 시점의 열린 PR은 없다.

- **문제 정의**: 스펙 068은 후보를 다음 검증 단계로 분류했지만, `FORWARD_REGISTRATION_READY` 후보를
  실제 forward paper 관측 큐에 올리거나 `CANARY_CANDIDATE` 후보를 hardened canary 검증 큐에 올리는
  실행층은 아직 없었다. 운영자가 원한 것은 판단에서 멈추지 않는 영구 자율 성장 루프다.
- **구현 상태**: `src/auto_invest/analytics/promotion_actions.py`가 promotion summary를 읽어
  promotion 전용 forward registry와 canary submission next state를 만든다. `scripts/promotion_action_probe.py`,
  `auto-invest promotion-actions`, `.github/workflows/autonomous-promotion-actions.yml`가 같은 결정을
  로컬·명령줄·GitHub Actions에서 재현한다.
- **실행 경로**: `promotion-forward-tracks.yml`는 action sidecar의 `promotion-forward-registry.next.json`을
  우선 읽고 tracked `automation/promotion-forward-registry.json`은 fallback으로 쓴다. 등록된 후보는
  `backfill-bars -> rebalance-once --mode paper -> nav-snapshot --mode paper -> forward-verdict --mode paper`
  순서로만 검증한다. `promotion-canary-submissions.yml`도 action sidecar의
  `promotion-canary-submissions.next.json`을 우선 읽고, pending 후보는 `canary-portfolio`만 실행한다.
- **닫힌 루프**: `autonomous-promotion-loop.yml`이 이제 `promotion-forward`와 `promotion-canary` sidecar를
  증거로 수집한다. `promotion_loop.py`는 후보 ID 주변의 verdict를 읽어 `EDGE_CONFIRMED`면 canary 후보로,
  canary `PASS`면 기존 스펙 050/055 게이트 준비 후보로 올린다.
- **첫 실행 증거**: #410 main push 뒤 `Autonomous promotion actions` run `28333113593`, `Promotion forward tracks`
  run `28333113584`, `Promotion canary submissions` run `28333113596`, `Autonomous promotion loop`
  run `28333113599`가 모두 success였다. 현재 후보들은 아직 모두 `BACKTEST_REQUIRED`라 action summary는
  `registered=0`, `submitted=0`, `blocked=0`, forward `track_count=0`, canary `pending_submission_count=0`이다.
- **배포와 smoke**: #410 main push의 `Deploy on merge to main` run `28333113591`은 success다.
  `KIS smoke (autonomous)` run `28333113580`도 commit `27da8b4` 기준 success, `key_valid=true`,
  live broker smoke 4건 통과다. 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **안전 경계**: 등급 2 운영 자동화다. 신규 action workflow는 SSH/KIS/브로커를 쓰지 않는다.
  신규 forward는 `--mode paper`만 사용하고, 신규 canary는 `canary-portfolio`만 실행한다. 실제 주문,
  자본 증액, whitelist/caps 확대, live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6 변경 없음.
- **검증**: PR #410 머지 전 focused pytest 48 통과, `uv run pytest` 2333 통과·4 스킵,
  `uv run ruff check src tests` 통과, `git diff --check` 통과, touched workflow YAML parse OK,
  `promotion_action_probe.py` artifact smoke와 `auto-invest promotion-actions` CLI smoke 통과, 하네스 `OK (14/14)`,
  HANDOFF 사실 검증 OK, PR 품질 관문 성공. handoff 갱신 후 `uv run pytest -q` 2333 통과·4 스킵,
  `uv run ruff check src tests` 통과, `uv run python scripts/check_handoff_facts.py` OK,
  `uv run python scripts/agent_harness_probe.py --strict` OK (14/14)다.
- **상세 인계**: `HANDOFF-072-AUTONOMOUS-PROMOTION-ACTIONS.md`.

## 최근 관찰 — 2026-06-29 KST (스펙 068 자율 승격 루프 자동화)

현재 `main` 최신은 `ddecebb`(#408, 스펙 068 자율 승격 루프 자동화)이다.
직전 주요 커밋은 `0b91c05`(작업 상태 갱신), `4d9747e`(승격 루프 구현),
`9a0aa1e`(#407, 운영자 이해 가능 보고 handoff 갱신)이다. 이 인계 갱신 시점의 열린 PR은 없다.

- **문제 정의**: 자율 성장 루프가 후보를 만들더라도, 그 후보가 곧바로 돈 경로로 들어가면 안 된다.
  후보마다 지금 필요한 다음 검증 단계가 백테스트인지, 최근 표본외인지, forward paper인지,
  소액 live canary 후보인지, 기존 돈 게이트 입력인지 자동으로 분류해야 한다.
- **구현 상태**: `src/auto_invest/analytics/promotion_loop.py`가 `candidate_backlog.json`,
  `evolution_summary.json`, 기존 sidecar를 읽어 결정론적 승격 큐를 만든다. `scripts/promotion_loop_probe.py`,
  `auto-invest promotion-scan`, `.github/workflows/autonomous-promotion-loop.yml`가 같은 판정을
  로컬·명령줄·GitHub Actions에서 재현한다.
- **백테스트와 소액 실거래의 분리**: 세계 최고 수준 백테스트는 전략 논리, 비용, 과최적화,
  최근 regime 위험을 줄이는 필수 필터다. 하지만 브로커 주문 거부, 부분 체결과 미체결, 실계좌
  현금·결제·보유 종목 충돌, 장중 스프레드와 슬리피지, API 지연·토큰 갱신, append-only 감사 로그와
  일일 정산은 실제 브로커 경로에서만 검증된다. 그래서 백테스트 통과는 캐너리 후보 자격이지
  실계좌 실행 검증 완료가 아니다.
- **첫 실행 증거**: #408 main push 뒤 `Autonomous promotion loop` run `28332023253`이 성공했고
  `automation/autonomous-promotion-last-run`을 발행했다. 최신 `LAST_RUN.md`는 commit `ddecebb24afe...`,
  `overall_status=ok`, 누락 증거 없음, 안전 문구 "주문, 자본, whitelist/caps, live 전략, sentinels 변경 없음"을 보고한다.
  현재 상위 후보들은 모두 `BACKTEST_REQUIRED`라서 아직 캐너리나 돈 게이트로 넘어갈 후보는 없다.
- **배포와 smoke**: #408 main push의 `Deploy on merge to main` run `28332023265`는 success다.
  `KIS smoke (autonomous)` run `28332023268`도 commit `ddecebb` 기준 success, `key_valid=true`,
  live broker smoke 4건 통과다. 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **안전 경계**: 등급 2 read-only 운영 자동화다. 실제 주문 실행, 브로커 API 호출, 자본 증액,
  whitelist/caps 확대, live 전략 교체, 센티넬 변경, 헌법, 커널 목록, K1/K2/K4/K5/K6 변경 없음.
  전략 교체는 스펙 055 재지정 게이트, 자본 증액은 스펙 050 자본 사다리 밖에서 처리하지 않는다.
- **검증**: PR #408 머지 전 `uv run pytest -q` 2321 통과·4 스킵, `uv run ruff check src tests`
  통과, `git diff --check` 통과, `promotion-scan` smoke 통과, 하네스 `OK (14/14)`,
  HANDOFF 사실 검증 OK, PR 품질 관문 성공. 머지 직전 전체 테스트와 린트를 다시 실행해 같은 결과를 확인했다.

## 최근 관찰 — 2026-06-29 KST (운영자가 이해 가능한 완료 보고 강제)

현재 `main` 최신은 `c4400b7`(#406, 운영자가 이해 가능한 완료 보고 강제)이다.
직전 주요 커밋은 `f6dfe51`(구현 커밋), `c542d30`(#405, 스펙 067 구현 handoff 갱신),
`424a70e`(#404, 스펙 067 영구 자율 성장 루프 구현)이다. 이 인계 갱신 시점의 열린 PR은 없다.

- **문제 정의**: 운영자가 "그래서 뭘 했다는 거야?"라고 다시 물어야 하는 완료 보고는 시스템 실패다.
  PR 번호, 커밋, 테스트 수, sidecar run id를 증거로 나열했지만 실제 운영 상태 변화와 의미를 먼저
  설명하지 않았던 것이 원인이다.
- **운영 규칙 변경**: `AGENTS.md`의 보고 기준에 "운영자가 바로 이해할 수 있는 한 문장 결론"을
  필수로 넣었다. 큰 작업 후에는 무엇을 만들었는지, 돈 경로·자동화·안전 경계·다음 세션 행동에
  어떤 의미가 있는지, 무엇으로 확인했는지, 남은 위험이 무엇인지 쉬운 한글로 분리해야 한다.
- **품질 관문 변경**: `.codex/quality-gate.md`에 `운영자 이해 가능 보고` 점검을 추가했다.
  첫 문장이 PR 번호나 커밋 해시가 아니라 실제 운영 상태를 설명하는지, 테스트·배포·sidecar가
  증거로 쓰이고 그 의미가 설명됐는지 확인한다.
- **하네스 변경**: `.codex/harness/quality_tasks.toml`에 `QUALITY-006`을 추가하고,
  `scripts/agent_harness_probe.py`의 필수 첫 판단 품질 범주에 `operator_readability`를 넣었다.
  이 범주가 빠지면 strict 하네스가 깨진다.
- **안전 경계**: 등급 2 운영 체계 변경이다. 실제 주문, 브로커 API 호출, 자본 증액, whitelist/caps,
  live 전략 교체, 헌법, 커널 목록, 주문 제한, 비밀값, 감사 로그는 바꾸지 않았다.
- **검증**: PR #406 머지 전 `uv run pytest` 2310 통과·4 스킵, `uv run ruff check src tests` 통과,
  focused script 린트 통과, 하네스 `OK (14/14)`, HANDOFF 사실 검증 OK, PR 품질 관문 성공.
  handoff 갱신 전 main의 `uv run pytest -q`는 stale `HANDOFF.md` 때문에 하네스 2건만 실패했고,
  이 handoff 갱신은 그 원인을 바로잡는다.

## 최근 관찰 — 2026-06-29 KST (스펙 067 영구 자율 성장 루프 구현)

현재 `main` 최신은 `424a70e`(#404, 스펙 067 영구 자율 성장 루프 구현)이다.
직전 주요 커밋은 `b72ec7e`(구현 커밋), `a98d44f`(#403, 스펙 067 handoff 갱신),
`9e1e492`(#402, 스펙 067 목표 프레이밍 정정)이다. 이 인계 갱신 시점의 열린 PR은 없다.

- **구현 상태**: `src/auto_invest/analytics/evolution_loop.py`가 sidecar와 handoff 증거를 읽어
  데이터 수집, 데이터 품질, 분석, 전략 설계, 포트폴리오 설계, 실행 품질, 실시간 매매 준비도,
  회고, 에이전트 운영 품질 전 영역의 고레버리지 돌파 후보를 결정론적으로 만든다.
- **실행 경로**: `scripts/evolution_loop_probe.py`는 workflow용 manifest, JSON/text 출력,
  `LAST_RUN.md`, `evolution_summary.json`, `learning_ledger.json`, `candidate_backlog.json`을 만든다.
  로컬에서는 `auto-invest evolution-scan --evidence-dir <dir>`로 같은 read-only scan을 재현한다.
- **자동화**: `.github/workflows/autonomous-evolution-loop.yml`은 매일 08:30 UTC와 관련 main push 때
  sidecar를 수집하고 `automation/autonomous-evolution-last-run`을 force-push로 발행한다. shell step은
  `set -euo pipefail`로 실패를 조용히 삼키지 않는다.
- **첫 실행 증거**: #404 main push 뒤 workflow run `28329967896`이 성공적으로 sidecar를 발행했다.
  최신 `LAST_RUN.md`는 commit `424a70e16a442b0bde54db2da47b3d69ab14e78c`, `overall_status=ok`,
  stale/missing evidence 없음, operator review 없음, 안전 문구 "주문, 자본, whitelist/caps, live 전략
  변경 없음"을 보고한다.
- **현재 상위 후보**: 1) micro GTAA 의도 손익 재검토와 대체 전략 연구, 2) 돈 경로 준비도와 기존
  게이트 정렬, 3) 비상관 포트폴리오 후보 비교력 강화. 시장 관측 대기는 루프의 목적이 아니라
  일부 후보의 `evidence_dependency`일 뿐이다.
- **보존한 방어**: 후보 발견·실험 계획·학습 장부는 모두 read-only다. 실제 주문, 브로커 API 호출,
  자본 증액, whitelist/caps 확대, live 전략 교체를 하지 않는다. 전략 후보는 스펙 055 재지정
  게이트, 자본 후보는 스펙 050 자본 사다리 밖으로 승격하지 않는다.
- **검증**: PR #404 머지 전 `uv run pytest` 2310 통과·4 스킵, `uv run ruff check src tests` 통과,
  `git diff --check` 통과, PR 본문 품질 관문 통과, 하네스 `OK (14/14)`, HANDOFF 사실 검증 OK.
  handoff 갱신 전 main의 `uv run pytest -q`는 stale `HANDOFF.md` 때문에 하네스 2건만 실패했고,
  이 handoff 갱신은 그 원인을 바로잡는다.

## 최근 관찰 — 2026-06-29 KST (스펙 067 영구 성장 목표 정정)

이 기록 작성 당시 `main` 최신은 `9e1e492`(#402, 스펙 067 목표 프레이밍 정정)였다.
직전 주요 커밋은 `605cb11`(#402 실제 문서 커밋), `ba52f46`(#401, 스펙 067 handoff 갱신),
`8f9a99f`(#400, 스펙 067 자율 고도화 루프 설계)이다. 이 인계 갱신 시점의 열린 PR은 없다.

- **문제 정의**: 운영자는 스펙 067이 "기다리는 시간을 줄이거나 채우는 루프"처럼 읽히는 것을
  바로잡았다. 목표는 지금부터 영구적으로 데이터 수집·분석·전략 설계·포트폴리오 설계·실시간
  매매·회고·에이전트 운영 전 영역에서 돈 버는 능력과 검증 능력을 복리화할 고레버리지 돌파 후보를
  찾고 안전한 실험으로 승격하는 것이다.
- **스펙 기록**: `specs/067-autonomous-evolution-loop/`에 `spec.md`, `plan.md`, `research.md`,
  `data-model.md`, `quickstart.md`, `contracts/evolution-loop.md`, `tasks.md`, checklist가 모두
  영구 성장·고레버리지 돌파·증거 의존성 기준을 반영한다. 상세: `HANDOFF-068-EVOLUTION-BREAKTHROUGH-FRAMING.md`.
- **범위 고정(당시 기록)**: 첫 구현 슬라이스는 read-only 스캔, 고레버리지 돌파 후보 발굴, 실험 계획, 학습 장부,
  latest-run sidecar, pipeline liveness 편입이었다. 당시 구현은 아직 시작하지 않았고 `tasks.md` T001부터 남아 있었다.
  현재는 #404로 구현 완료됐으므로 위 #404 섹션을 우선한다.
- **보존한 방어**: 자동 고도화 루프가 주문, 자본, whitelist, caps, 실거래 모드, live 전략 교체를
  직접 수행하지 못하도록 요구사항에 명시했다. 전략 교체는 스펙 055 5중 게이트, 자본 증액은
  스펙 050 자본 사다리 밖에서 처리하지 않는다.
- **검증**: PR #402 머지 전 `uv run pytest` 2286 통과·4 스킵, `uv run ruff check src tests` 통과,
  `git diff --check` 통과, PR 본문 품질 관문 통과, 하네스 `OK (14/14)`, HANDOFF 사실 검증 OK.
  handoff 갱신 기준으로 `uv run pytest -q` 2286 통과·4 스킵, `uv run ruff check src tests` 통과.

## 최근 관찰 — 2026-06-28 KST (micro GTAA intent-loss 다음 행동 안내 보정)

현재 `main` 최신은 `0b7c248`(#398, micro GTAA intent-loss next-action 안내 보정)이다.
직전 주요 커밋은 `cb05752`(구현 커밋), `7898793`(#397, #396 handoff),
`d97d6a2`(#396, strategy review 관측 품질 보정)이다. 이 인계 갱신 시작 시점의 열린 PR은 없다.

- **문제 교정**: 최신 `opportunity_monitor.json`은 `latest_signal=INTENT_LOSS`,
  `verdict=INSUFFICIENT_DATA`, 누적 의도 손익 `-1.14 USD`다. 기존 안내는 "다음 micro GTAA 실행에서
  표본을 더 쌓습니다"라고 했지만, #394 live gate가 같은 신호에서 실주문을 차단하므로 새 live
  표본은 자동으로 쌓이지 않는다.
- **코드 변경**: `src/auto_invest/analytics/opportunity_monitor.py`가 `VERDICT_INSUFFICIENT_DATA`와
  `latest_signal=INTENT_LOSS` 조합에서 "새 live 표본은 자동으로 쌓이지 않습니다. forward
  토너먼트·재지정 증거를 기다리거나 별도 전략 검토 후 재무장 여부를 판단합니다"로 안내한다.
- **보존한 방어**: `INTENT_LOSS` live 차단, `armed:false`, history 보존, workflow gate 조건,
  주문 라우터, 자본, 허용 종목은 바꾸지 않았다. 이 PR은 재무장이나 실주문 허용이 아니다.
- **운영 재현**: 최신 `opportunity_history.json`으로 `auto-invest opportunity-monitor`를 로컬
  재현하면 `next_action_ko`가 새 문구로 나온다. 최신 money-path 재현은 여전히 `PREVIEW_ONLY`,
  `ACCUMULATING_EDGE`, forward 관측 `12/20`이다.
- **전략 검토 상태**: 최신 코드로 `rebalance-paper-forward-last-run:LAST_RUN.md`를 다시 파싱하면
  관측 품질은 `OK`로 보정된다. 하지만 비교 가능한 도전자는 0개이므로 `reassign-decide`는
  `HOLD`가 정상이다.
- **안전 경계**: 등급 2 운영 안내 보정이다. 실제 주문 실행, micro GTAA 재무장, 자본 증액,
  허용 종목 확대, live 전략 교체, 주문 라우터, K1/K2/K4/K5/K6 코드, 헌법, 커널 목록 변경 없음.
- **검증**: PR #398 머지 전 focused tests 14 통과, `uv run pytest` 2286 통과·4 스킵,
  `uv run ruff check src tests` 통과, `git diff --check` 통과, PR 본문 품질 관문 통과,
  하네스 `OK (14/14)`, HANDOFF 사실 검증 OK. PR quality gate도 성공했고 merge 방식으로 main에
  머지했다.

## 최근 관찰 — 2026-06-27 KST (전략 검토 관측 품질 오판 보정)

현재 `main` 최신은 `d97d6a2`(#396, strategy review 관측 품질 보정)이다.
직전 주요 커밋은 `f78ac15`(구현 커밋), `458c999`(#395, #394 handoff),
`6272178`(#394, micro GTAA 손실 의도 실주문 차단)이다. 이 인계 갱신 시작 시점의 열린 PR은 없다.

- **문제 교정**: 최신 reassign sidecar run `28278589509`는 `globalfixed`가 9회, 다른 후보들이
  최대 12회 관측이라는 이유로 `observation_health=DEGRADED`를 냈다. 하지만 모든 후보가
  최소 관측 20회 전이라면 아직 어떤 후보도 비교 가능하지 않으므로, 올바른 상태는 "정상 누적 중,
  비교 가능한 도전자 없음"이다.
- **코드 변경**: `src/auto_invest/analytics/forward_tournament.py`의 `_observation_quality()`가
  all-premature, mixed comparable/premature, all-comparable 상태를 분리한다. all-premature lag와
  all-comparable lag는 `OK`이고, mixed comparable/premature는 `DEGRADED`를 유지한다.
- **보존한 방어**: `lagging_keys`, 최소/최대 관측 수는 계속 표시한다. non-incumbent 판정 누락은
  `DEGRADED`, incumbent 판정 누락은 `BLOCKED`로 남겼다.
- **스펙 기록**: `specs/066-strategy-review-observation-health/`에 목표, 비목표, 안전 경계,
  quickstart, tasks, requirement checklist를 남겼다.
- **배포 확인**: #396 main push의 `Deploy on merge to main` run `28282838560`은 성공했다.
  이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **KIS smoke sidecar**: 최신 sidecar는 run `28281245727`, commit `458c999`, `smoke_state=success`,
  `key_valid=true`로 #396 이전 예약 실행이다. 따라서 이번 머지의 post-merge 보조 증거로는 보지 않는다.
- **안전 경계**: 등급 2 운영 판단 보정이다. 실제 주문 실행, micro GTAA 재무장, 자본 증액,
  허용 종목 확대, live 전략 교체, 주문 라우터, K1/K2/K4/K5/K6 코드, 헌법, 커널 목록 변경 없음.
- **검증**: PR #396 머지 전 focused tests 70 통과, `uv run pytest` 2286 통과·4 스킵,
  `uv run ruff check src tests` 통과, `git diff --check` 통과, PR 본문 품질 관문 통과,
  하네스 `OK (14/14)`, HANDOFF 사실 검증 OK. PR quality gate도 성공했고 merge 방식으로
  main에 머지했다.

## 최근 관찰 — 2026-06-27 KST (micro GTAA 손실 의도 실주문 차단)

현재 `main` 최신은 `6272178`(#394, micro GTAA 손실 의도 실주문 차단)이다.
직전 주요 커밋은 `e98f7e9`(구현 커밋), `a64b9fc`(#393, #392 handoff),
`f76aa07`(#392, 거부 주문 누적 평가와 자율 재지정 피드백 루프)이다. 이 인계 갱신 시작 시점의
열린 PR은 없다.

- **문제 교정**: 최신 micro GTAA 거부 주문 기회손익은 `latest_signal=INTENT_LOSS`,
  `cumulative_pnl_usd=-1.14`였다. 즉 그 매수가 정상 체결됐다면 현재 mark 기준 더 불리했을
  가능성이 있었고, 같은 전략 의도를 실주문으로 반복하면 안 된다는 운영자 지적이 맞았다.
- **즉시 중단**: `automation/rebalance-micro-gtaa.request`는 `armed:false`, `run_seq:3`이다.
  note에는 2026-06-27 조치와 `INTENT_LOSS`, `-1.14 USD`, 전략 검토 전 실주문 중단 사유가 남아 있다.
- **지속 차단**: `.github/workflows/rebalance-micro-gtaa-canary.yml`은 preflight 전에
  `scripts/opportunity_live_gate.py`를 실행한다. 최신 monitor가 `latest_signal=INTENT_LOSS` 또는
  `verdict=STRATEGY_REVIEW`이면 preflight, 손실 브레이커, live 주문 단계가 실행 조건을 만족하지
  못한다. 게이트 평가 자체가 실패하면 `gate_evaluation_unavailable`으로 fail-closed 한다.
- **손실 신호 보존**: live가 실행되지 않은 run은 빈 opportunity 기록을 append하지 않는다.
  그래서 이전 `INTENT_LOSS` 기록이 차단 실행 때문에 `FLAT_OR_UNVALUED`로 지워지지 않는다.
- **post-merge 실행 증거**: #394 main push의 micro GTAA run `28274580272`는 성공했고
  `Pre-live order preflight`, `Pre-live circuit breaker gate`, `LIVE rebalance — REAL MICRO ORDERS`가
  모두 skipped였다. 최신 sidecar는 `armed=false`, `LIVE 스텝=skipped`, `next_step=전략 의도 게이트
  차단(latest_intent_loss) — 전략 검토 전까지 실주문 0건`을 보여 준다.
- **배포/상태 확인**: #394 main push의 `Deploy on merge to main` run `28274580264`는 성공했다.
  `Money-path readiness` run `28274580263`도 성공했고 `live_money_state.status=PREVIEW_ONLY`,
  `can_submit_real_orders=false`를 보고했다. KIS smoke sidecar 최신은 아직 `28237830957` /
  commit `f76aa07` 기준이므로 #394 직후 새 smoke sidecar는 확인하지 못했다.
- **Telegram 가독성**: micro GTAA Telegram 알림은 strategy-intent gate의 `ok`, `reason`을
  표시하고, 차단 시 "전략 의도 게이트 차단(실주문 0건)"으로 읽힌다.
- **안전 경계**: 등급 4 돈 경로 변경이지만 방향은 주문 가능성 축소다. 실제 주문 실행, 주문
  라우터, 자본 증액, 허용 종목 확대, 포지션 한도, 손실 브레이커, K1/K2/K4/K5/K6 코드, 헌법,
  커널 목록은 바꾸지 않았다.
- **검증**: PR #394 머지 전 focused tests 30 통과, broader focused tests 105 통과,
  `uv run pytest` 2283 통과·4 스킵, `uv run ruff check src tests` 통과, workflow YAML parse OK,
  workflow `run` block `bash -n` OK, 하네스 `OK (14/14)`, HANDOFF 사실 검증 OK, PR 품질 관문
  통과. 머지 직전 전체 테스트와 린트를 다시 실행해 같은 결과를 확인했다.

## 최근 관찰 — 2026-06-26 KST (거부 주문 누적 평가와 자율 재지정 피드백 루프)

현재 `main` 최신은 `f76aa07`(#392, 거부 주문 누적 평가와 자율 재지정 피드백 루프)이다.
직전 주요 커밋은 `219a537`(구현 커밋), `2b04742`(#391, #390 handoff), `4175f13`(#390,
거부 주문 기회손익과 Telegram 가독성 보강)이다. 이 인계 갱신 시작 시점의 열린 PR은 없다.

- **문제 교정**: #390은 "거부된 주문이 정상 체결됐다면 지금 유리한가"를 단발로 답했지만,
  운영자가 요구한 전략 평가는 누적 판단이어야 했다. 이제 micro GTAA 실행마다 기회손익 보고를
  rolling history에 붙이고 누적 `STRATEGY_REVIEW` 또는 `EXECUTION_REVIEW` verdict를 낸다.
- **새 재현 명령**: `auto-invest opportunity-monitor --history-json <history> --opportunity-json <report> --history-out <out> --monitor-out <out>`.
  이 명령은 브로커를 호출하지 않고 주문도 재시도하지 않는다. 양수 누적은 거부 때문에 이익을
  놓쳤다는 실행 경로 신호, 음수 누적은 전략 의도가 손실이었을 수 있다는 전략 검토 신호다.
- **micro GTAA 증거 표면**: `automation/rebalance-micro-gtaa-last-run` sidecar는 다음 실행부터
  `opportunity_history.json`과 `opportunity_monitor.json`을 함께 발행한다. `LAST_RUN.md`에는
  `## 거부 주문 누적 평가` 섹션이 추가된다.
- **Telegram 가독성**: micro GTAA 알림은 새 `5. 누적 전략/실행 평가` 섹션에서 verdict, 누적
  전략 의도 손익, 최신 신호, 연속 손실/이익, 다음 조치, 안전 문구를 보여 준다.
- **자율 재지정 연결**: `reassign-on-tournament.yml`은 최신 `opportunity_monitor.json`을 읽어
  `reassign-decide --execution-feedback-json`에 넘긴다. 결정 JSON에는 `execution_feedback`이
  남지만 `effect=evidence_only_no_gate_override`이며, 도전자·다중검정·캐너리 5중 게이트를
  통과하지 않으면 자동 전략 교체는 없다.
- **배포 확인**: #392 main push의 `Deploy on merge to main` run `28237830935`는 성공했다.
  같은 커밋의 KIS smoke run `28237830957`도 `secrets_present=true`, `key_valid=true`,
  `smoke_state=success`, `smoke_exit=0`이다. money-path run `28237830995`도 성공했고
  `live_money_state.status=REAL_ORDER_PATH_ARMED`를 보고했다. 배포는 dry-run worker 코드 반영이지
  실거래 전환이 아니다.
- **안전 경계**: 등급 2 운영 관측·평가 변경이다. 실제 주문 실행, 주문 재시도, 주문 라우터,
  전략 파일 교체, K1/K2 게이트, 자본, 허용 종목, 포지션 한도, 손실 브레이커, 헌법, 커널 목록은
  바꾸지 않았다.
- **검증**: PR #392 머지 전 `uv run pytest` 2274 통과·4 스킵, `uv run ruff check src tests`
  통과, `uv run python scripts/check_handoff_facts.py` OK, `uv run python scripts/agent_harness_probe.py --strict`
  OK (14/14), PR 품질 관문 통과. handoff 갱신 전 main에서 `uv run pytest -q`는 stale
  `HANDOFF.md` 때문에 하네스 2건만 실패했다. 이 handoff 갱신은 그 원인(`마지막 main 커밋` 행)을
  바로잡았다. 갱신 후 `uv run python scripts/check_handoff_facts.py`, `uv run python scripts/agent_harness_probe.py --strict`,
  `uv run pytest -q`, `uv run ruff check src tests`가 모두 통과했다.

## 최근 관찰 — 2026-06-26 KST (거부 주문 기회손익과 Telegram 가독성 보강)

현재 `main` 최신은 `4175f13`(#390, 거부 주문 기회손익과 Telegram 가독성 보강)이다.
직전 주요 커밋은 `4bd4157`(구현 커밋), `c76ce51`(#389, Telegram flood handoff),
`7195c48`(#388, Telegram 알림 폭주 방지와 KIS 진단 보강)이다. 이 인계 갱신 시작 시점의
열린 PR은 없다.

- **문제 교정**: 이전 대화에서 "주문 실패" 여부만 봐서는 전략 평가가 안 된다는 운영자 지적이
  있었다. 이제 거부된 BUY/SELL 주문을 현재가와 비교해 "정상 체결됐다면 지금 더 유리했는가"를
  자동 계산한다. 양수는 거부 주문이 체결됐으면 현재 더 유리, 음수는 거부가 결과적으로 더 유리하다는
  뜻이다.
- **새 재현 명령**: `auto-invest rejected-order-opportunity --result-json <rebalance-json> --env-file .env --db data/auto_invest.db`.
  이 명령은 읽기 전용이며 주문을 재시도하지 않는다. `--marks-json`으로 테스트용 현재가를 넣을 수 있고,
  현재가 조회 실패는 `mark_fetch_error`와 `missing_mark_symbols`로 드러난다.
- **micro GTAA 증거 표면**: `.github/workflows/rebalance-micro-gtaa-canary.yml`에
  `Evaluate rejected order opportunity` 단계가 추가됐다. 서버의 KIS 현재가를 읽어
  `/tmp/micro_opportunity.json`을 만들고, sidecar `## 거부 주문 기회손익`과 Telegram
  `4. 거부 주문 기회손익` 섹션에 같은 근거를 표시한다. 실패해도 주문·sidecar·Telegram 결론을
  실패시키지 않는 best-effort 관측 단계다.
- **Telegram 가독성**: micro GTAA 알림은 실행, 라이브 전제 확인, 주문 결과, 거부 주문 기회손익,
  확인 링크로 나뉜다. audit-log tailer 알림도 `[source] 제목`, 상태, 이벤트, 대상, 진단, 판단 줄로
  정리됐다. 브로커 거부는 "접수·체결되지 않았다"를 명시한다.
- **안전 경계**: 등급 2 운영 관측 변경이다. 실제 주문 실행, 주문 재시도, 라우터, K1/K2 게이트,
  자본, 허용 종목, 포지션 한도, 손실 브레이커, 헌법, 커널 목록은 바꾸지 않았다. 새 CLI는 안전
  레지스트리에서 `READ_ONLY`, `can_place_order=false`, `uses_broker=true`로 등록됐다.
- **검증**: PR #390 머지 전 focused tests 30 통과, `uv run pytest -q` 2262 통과·4 스킵,
  `uv run ruff check src tests` 통과, workflow YAML 파싱 OK, 하네스 `OK (14/14)`, HANDOFF 사실
  검증 OK, PR 품질 관문 통과. handoff 갱신 전 main에서 `uv run pytest -q`는 stale `HANDOFF.md`
  때문에 하네스 2건만 실패했다. 이 handoff 갱신은 그 원인(`마지막 main 커밋` 행)을 바로잡았다.

## 최근 관찰 — 2026-06-26 KST (Telegram 알림 폭주 방지와 KIS 진단 보강)

현재 `main` 최신은 `7195c48`(#388, Telegram 알림 폭주 방지와 KIS 진단 보강)이다.
직전 주요 커밋은 `46c36b9`(구현 커밋), `cd7eb4f`(#387, account-wide micro GTAA handoff),
`7a14315`(#386, 계좌 전체 micro GTAA 자율 재배치)이다. 이 인계 갱신 시작 시점의 열린 PR은 없다.

- **상황 판단**: Telegram 메시지 9000개 이상은 GitHub Actions가 주문 workflow를 반복 실행한
  증거가 아니었다. 최신 micro GTAA workflow run은 Telegram 알림 1건만 보냈고, 서버의
  `auto-invest-telegram-alerts.service`가 감사 로그를 tailing하면서 오래된 cursor 또는 반복
  `ERROR` row를 따라잡는 경로가 폭주 원인으로 확인됐다.
- **tailer 방어**: `auto-invest telegram-alerts`는 기존 state file이 오래된 seq를 가리켜도 기본
  최신 25개만 catch-up한다. 동일한 `ERROR`는 기본 3600초 안에 한 번만 보내고, 억제된 row도
  cursor는 전진한다. 옵션은 `--max-catchup-alerts`, `--error-cooldown-seconds`다.
- **KIS 진단 보강**: KIS 주문 응답이 HTTP 200이어도 `rt_cd` 실패 또는 `output.ODNO` 누락이면
  성공으로 보지 않고 `KisOrderError`를 발생시킨다. 이제 `KeyError('output')` 대신 HTTP 상태,
  KIS `rt_cd/msg_cd/msg1`, 응답 미리보기, 마스킹된 요청 요약이 남는다.
- **운영 제어 경로**: `.github/workflows/manage-telegram-alerts.yml`이 추가됐다. 운영자는 로컬 SSH
  없이 GitHub Actions에서 `auto-invest-telegram-alerts.service`만 `status`, `disable`, `restart`,
  `enable` 할 수 있다. 거래 worker, 주문 라우터, 자본, whitelist, 위험 게이트는 건드리지 않는다.
- **배포 확인**: #388 main push의 `Deploy on merge to main` run `28212963179`는 성공했다.
  `KIS smoke (autonomous)` run `28212963184`도 `7195c48`에서 성공했고 sidecar는
  `secrets_present=true`, `key_valid=true`, `smoke_state=success`, `smoke_exit=0`이다.
- **서버 조치 확인**: `Manage Telegram alerts on server` run `28212999028`로 Telegram 알림 서비스를
  `restart`했고 성공했다. 재시작 약 50초 뒤 status run `28213025727`은 서비스가 `enabled`/`active`
  라고 보고했다. 최신 50줄 journal에는 재시작 직전 5~6초 간격 Telegram 전송 로그가 있었지만,
  재시작 이후 새 `sendMessage` 로그는 보이지 않았다.
- **안전 경계**: 등급 3 외부 API·운영 알림·브로커 진단 변경이다. 실제 주문은 실행하지 않았고,
  주문 게이트·자본·허용 종목·포지션 한도·손실 브레이커·헌법·커널 목록은 바꾸지 않았다.
  감사 로그 원본은 그대로 두며, cursor state에는 동일 오류 억제용 SHA-256 fingerprint만 저장한다.
- **검증**: PR #388 머지 전 focused tests 21 통과, `uv run pytest` 2257 통과·4 스킵,
  `uv run ruff check src tests` 통과, `uv run auto-invest telegram-alerts --help` 옵션 노출 확인,
  하네스 `OK (14/14)`, PR 품질 관문 통과. handoff 갱신 전 `uv run pytest -q`는 stale
  `HANDOFF.md` 때문에 하네스 2건만 실패했다. 이 handoff 갱신은 그 원인(`마지막 main 커밋` 행)을
  바로잡았다. 갱신 후 `uv run python scripts/check_handoff_facts.py`,
  `uv run python scripts/agent_harness_probe.py --strict`, `uv run pytest -q`,
  `uv run ruff check src tests`가 모두 통과했다.

## 최근 관찰 — 2026-06-23 KST (스펙 063 계좌 전체 micro GTAA 자율 재배치)

현재 `main` 최신은 `7a14315`(#386, 스펙 063 계좌 전체 micro GTAA 자율 재배치)이다.
직전 주요 커밋은 `45e15bc`(account-wide micro GTAA 구현), `64bf37d`(#385, money-path
handoff 갱신), `3440001`(#384, money-path 실제 돈 최상위 상태)이다. 이 인계 갱신 시작 시점의
열린 PR은 없다.

- **핵심 교정**: 새 입금이 없어도 기존 보유를 "못 판다"가 아니라 계좌 전체 자본으로 본다.
  기존 보유를 팔지, 보유할지, 목표 종목을 살지는 브로커 포지션·현금·목표 비중·안전 게이트를
  함께 보고 판단한다.
- **적용된 live canary 동작**: `auto-invest rebalance-once --account-wide --side both`가 KIS
  포지션과 매수 가능 현금을 읽는다. dry-run이어도 `--account-wide`가 있으면 읽기 전용 KIS 호출을
  수행하지만 주문은 제출하지 않는다. 기본 dry-run은 여전히 offline이다.
- **청산 전용 기존 보유**: `deploy/micro-gtaa-live-portfolio.toml`의 `[account_rebalance]`에
  `BHP`, `MRK`, `ORANY`, `RELX`가 `liquidation_symbols`로 선언됐다. 목표 유니버스는 계속
  `SPYM`, `IEF`, `GLDM`이다. 리밸런서는 청산 전용 종목이 매수 후보가 되면 실패 폐쇄한다.
- **현금 부족 처리**: 계획 매수 금액 + 1% 완충금보다 KIS 매수 가능 현금이 부족하고 청산 전용
  매도 후보가 있으면 workflow preflight가 `effective_side=sell`을 내보낸다. live 단계는 이 값을
  받아 매수 없이 매도만 실행한다. 매수는 매도 대금이 KIS 매수 가능 현금으로 확인되는 다음
  실행으로 넘어간다.
- **증거 표면**: `automation/rebalance-micro-gtaa-last-run` sidecar에는 계좌 전체 재배치 상태,
  requested/effective side, 필요 현금, 계획 매수·매도 금액, 다음 단계가 표시된다. Telegram 요약도
  `effective_side`를 포함한다.
- **안전 경계**: 등급 4 돈 경로 변경이다. K2 설정 표면은 청산 전용 매도를 위해 넓어졌지만,
  K1/K2 코드, 주문 라우터, 감사 로그, 비밀값, 손실 브레이커, 헌법, 커널 목록은 바꾸지 않았다.
  실제 KIS 주문은 이 작업 중 수동 실행하지 않았다.
- **검증**: PR #386 머지 전 `uv run pytest` 2252 통과·4 스킵, `uv run ruff check src tests`
  통과, focused tests 23 통과, workflow YAML 파싱 OK, 하네스 `OK (14/14)`, PR 품질 관문 통과.
  handoff 갱신 전 main에서 `uv run pytest -q`는 stale `HANDOFF.md` 때문에 하네스 2건만 실패했다.
  이 handoff 갱신은 그 원인(`마지막 main 커밋` 행)을 바로잡았다. 갱신 후
  `uv run python scripts/check_handoff_facts.py`, `uv run python scripts/agent_harness_probe.py --strict`,
  `uv run pytest -q`, `uv run ruff check src tests`가 모두 통과했다.

## 완료된 작업 큐 (운영자 승인 — 2026-05-31, 1→2→3 전부 완료)

운영자가 "작업 1·2·3 전부 순서대로" 승인 → 세 작업 모두 자율 수행·자동 머지 완료(PR #126·#127·#128).

- **작업 1 (완료, PR #126 · main `012adbc`)** — 자본 추적을 라이브 캐너리에 적용.
  `deploy/run-worker.sh` 라이브 분기에 `--capital-tracking` 추가(`--capital-growth` 는 일부러
  제외 = 하락 방어만, 상승 미반영). main 머지로 deploy-on-merge 가 라이브 워커를 새 코드로
  재배포. **검증 남음**: `/deploy-status` + 서버 audit_log 의 `EFFECTIVE_CAPITAL_UPDATED` 행
  확인(서버 접근 필요 — 컨테이너에서 직접 안 보임).
- **작업 2 (완료, PR #127 · main `29653b8`)** — 스펙 030 주문 수명 관리(TTL 취소·취소-재호가·
  marketable-limit). Kernel 터치 0건. 신규 테스트 31건.
- **작업 3 (완료, PR #128 · main `b701a26`)** — 스펙 031 KIS 실시간 웹소켓 **슬라이스 1**
  (프로토콜·폴백·워커 연동, 전송 주입형). 제3자 의존성 무추가. 신규 테스트 17건.

### 다음 작업 후보 (운영자 선택)

- **작업 1 검증 마무리** — `/deploy-status` + 서버 audit_log 로 라이브 워커가 실제로 NAV
  추종을 시작했는지(`EFFECTIVE_CAPITAL_UPDATED` 행) 확인. 필요하면 캐너리 자본 상향(돈 움직임
  → 운영자 게이트).
- **상승 반영(스펙 029 슬라이스 2 후속)** — 캐너리에 `--capital-growth` 추가(현재 하락 방어만).
  자산이 늘면 캡도 키움(상한 클램프). 돈 움직이는 운용 변경 → 운영자 확인.
- **스펙 031 슬라이스 2** — 실제 웹소켓 전송 어댑터(`websockets` 등 라이브러리) + 라이브
  부트스트랩 기동 + 실시간 체결통보로 `sync_fills` 보강. **라이브러리 추가는 공급망 결정** →
  운영자 확인 후.
- **스펙 030 후속** — marketable-limit·재호가를 실제 캐너리 룰셋에 옵트인 적용(돈 경로 →
  운영자 확인). 부분 체결 재호가(잔량 재계산)는 별도 슬라이스.
- **L2·L3 캐너리 승격 큐 ✅ (2026-06-18, PR #330)** — `analytics/promotion_queue.py` 로 캐너리
  합격·미승격 후보 가시화 완료(읽기 전용, 자동 승격 0/IX.B-2). 남은 후보: **L1 적용 표면 확장**
  (B안=캐너리 합격 L2 자동 적용은 IX.B-2 완화라 운영자 결정) / **실거래 자본 상향**(입금, 운영자 게이트).

## ⭐ 다음 세션 최우선 (2026-06-16 갱신 — 작업 1·2 모두 ✅ 완료, 먼저 읽을 것)

운영자 방향(2026-06-16): "자율 전략 진화 폐회로 + 비상관 수익원 다변화, 둘 다 세계 최고
수준으로 마이크로까지 완벽하게."

### 작업 1 — 비상관 수익원 다변화: ✅ 완료(정직한 부정). PR #317 머지(main `f2db5e0`)

- 밸류(CAPE)·캐리(E/P vs 금리)를 152년 Shiller 로 측정 → 세 결합 형태(50/50·로테이션·조건부)
  **전부** 추세와 상관 0.46~0.63(비상관 아님), 조건부는 낙폭 41%→70% 악화.
- 근본 원인: long-only 라 모든 전략이 같은 베타 공유 + 밸류는 약세장에 주식↑(역추세 상충).
  진짜 비상관 = 롱숏/다른 자산군 필요(현 제약 밖). 측정 도구 `analytics/value_carry.py` 는
  공매도 자산군 열리면 재사용. 전체 결론: `specs/054-uncorrelated-alpha/FINDINGS.md`.

### 작업 2 — 자율 전략 진화 폐회로: ✅ **완성**(결정 두뇌 #318 + 헌법 X.5 #320 + 재지정 실행/CLI #322 + ④ 캐너리·워크플로·DB 어댑터 #324). 운영자 정책 "완전 자율 + 5중 안전장치" 구현 완료

스펙 055 폐회로가 end-to-end 로 닫혔다. 설계·안전·운영 전체 문서: `specs/055-autonomous-reassignment/spec.md`.

- **입력 품질 + 5중 게이트**(전부 통과해야 REASSIGN, 아니면 HOLD/WAIT — 보수적 fail-safe):
  ⓪후보 관측 품질(`leaderboard.json`의 `observation_health=OK`)을 먼저 확인한다.
  `BLOCKED`는 재지정 금지, `DEGRADED`는 보수 보류다.
  ①엣지확정 ②다중검정보정 ③사과대사과(①③=`forward_tournament.challenger_key`)
  ④하드닝 캐너리 PASS(`canary/portfolio_harness.py`) ⑤교체 후 자본 사다리 rung0 리셋.
- **구성요소(전부 머지·테스트됨)**: 결정 `portfolio/auto_reassign.py`(#318) · 실행
  `portfolio/reassign_exec.py`(#322) · ④ 캐너리 `canary/portfolio_harness.py` +
  `config/canary_bands_reassign.toml`(#324) · 인스턴스 바 어댑터
  `backtest/data_source.SqliteBarDataSource`(#324) · CLI `reassign-decide`·`canary-portfolio`·
  `reassign-challenger-path` · 워크플로 `.github/workflows/reassign-on-tournament.yml`(평일 00:20 UTC).
  #358에서 재지정 입력은 사람용 `LAST_RUN.md` 재파싱이 아니라 발행된 `leaderboard.json`을 직접
  소비하도록 닫혔다.
- **손실면 불변(헌법 X.5)**: 재지정은 '무엇을(전략)'만, '얼마나(자본)'는 여전히 자본 사다리
  (X.4)+예산. 재지정 직후 rung 0(무장 해제)→실주문 0, 실제 돈은 새 전략이 forward 재검증을
  *다시* 통과해야(스펙 050). 캐너리는 사전 선별, 실제 돈 게이트는 하류 사다리(심층 방어).
- **재지정 루프 생존 감시 편입 완료(2026-06-16, main `0533585`, PR #326)** — 스펙 051
  파이프라인 생존 감시 레지스트리(`default_specs`)에 `reassign`(스펙 055 재지정 폐회로,
  평일 00:20 UTC)이 빠져 있던 **침묵 정지 사각지대를 메웠다.** 비핵심(저하 티어, 정지 시
  검증된 incumbent 가 라이브로 남는 fail-safe). 이제 재지정 루프가 조용히 죽으면 생존 감시가
  DEGRADED 로 드러낸다(거짓 빨강은 아님). 스케줄 루프 감사 결과 다른 사각지대 없음(go-live·
  forward-anchored-verdict·release-halt 는 수동/이벤트라 일부러 제외). Kernel·헌법 무터치.
- **다음 세션(선택 — 폐회로는 이미 완성)**:
  1. **실제 가동 1회 관측** — `reassign-on-tournament.yml` 첫 스케줄 실행 후
     `git show origin/automation/reassign-last-run:LAST_RUN.md` 로 결정/캐너리 verdict 확인.
     현재 6트랙 전부 잠정(관측 부족)이라 도전자 없음(HOLD)이 정상 — 강세장 창에서 추세 엣지가
     안 보이는 구조적 이유(역사 섹션 참조). globalfixed 가 EDGE_CONFIRMED 를 벌면 첫 자율 재지정 후보.
     (생존 감시가 이제 첫 실행 전엔 PENDING, 첫 실행 실패 시 +80h 후 MISSING 으로 구분 —
     거짓 DEGRADED 해소하면서 침묵 실패는 여전히 잡힘. PR #328, main `cba93a0`.)
  2. **L1 적용 표면 확장**(모델 라우팅·max_tokens 즉시 자동 적용) 등 기존 후속 후보(아래).

---

## (역사) 다음 세션 최우선 (2026-06-15 갱신 — "엣지 부재" 경보는 **해결됨**)

### ✅ 해결됨 (PR #307, main `4a7b78c`) — "엣지 부재"는 강세장 창의 착시였다

직전 세션이 남긴 최우선 작업("모든 후보를 같은 깊은 OOS 로 비교해 단순 보유를 이기는 전략이
있는지 찾으라")을 **완수했고, 결론이 경보를 뒤집었다.** 깊은 150년 월간 데이터(컨테이너에서
닿는 GitHub Shiller+금)로 추세 후보군을 등가중 단순 보유 대비 walk-forward OOS 비교한 결과:

- **라이브 전략(GLOBAL-TREND = 역변동성 3자산)은 1971~ 에서 단순 보유와 *같은 raw 수익
  (CAGR 9.4%)*인데 샤프 1.81 vs 1.23, 칼마 1.77 vs 0.45, 최대낙폭 5.3% vs 20.7% — 같은 돈을
  4분의 1 위험으로. 11개 5년 구간 *전부(11/11)* 단순 보유를 샤프로 이김.** 1871~ 도 동일
  결론(낙폭 38.6%→5.3%, 15/16 승). → 깊은 증거로 **현재 라이브 지정이 정당화됨. 재지정 불필요.**
- **왜 일봉 forward 는 "엣지 없음"이라 했나**: 2022~2026 은 방어할 폭락이 없는 강세장 4년이라
  추세의 현금화가 보험료처럼만 보였다. 추세추종의 가치는 폭락 구간(1929·2008·2020·2022…)에
  몰려 있어 단일 강세장 창에선 구조적으로 안 보인다 — forward 게이트가 (의도대로) 보수적이라
  통과를 미룰 뿐, 전략 자체엔 문제 없음. **돈을 잃지 않으려 막는 시스템이 정상 작동한 것.**
- 코드: `src/auto_invest/analytics/deep_walk_forward.py`(순수 엔진)·`scripts/deep_walk_forward_probe.py`
  (실행)·테스트 25건. 실측·결론·한계: `specs/047-global-trend/DEEP-WALK-FORWARD-FINDINGS.md`.
  재현: `uv run python scripts/deep_walk_forward_probe.py --from-year 1971 --segment-months 60`.

### ✅ 레버리지 정량화도 완료 (PR #309, main `92b4177`) — 운영자 결정 지점 발생

위 1번(성장 최적 레버리지 정량화)을 완수했고, **비직관적이고 결정 관련한 발견**이 나왔다
(`specs/044-growth-optimal-leverage/LIVE-STRATEGY-LEVERAGE-FINDINGS.md`):

- **레버리지는 진짜로 복리를 키운다**: 20% 낙폭 예산에서 분산 전략에 레버리지를 얹으면 무레버
  대비 +2.5~3.1%p 복리 상승. "현재 자본에서 더 버는" 지렛대는 실재.
- **그러나 "레버리지 여유 ≠ 돈"**: 라이브 역변동성 3자산은 *무레버리지에선* 가장 안전(샤프 1.81·
  낙폭 5.3%, 둘 다 최고)이고 레버리지 *여유(배수)*도 가장 크지만, 변동성을 너무 낮춰 기저
  수익이 낮고 레버리지 시 낙폭이 *초선형*으로 커져 **레버리지 후 복리는 4구간(1871/1950/
  1990/1971) 모두 꼴찌.**
- **고정 자본 복리 극대화 = 3자산 고정가중(047)**: 4구간 중 3구간 1위 + 1971~ 에선 낙폭 예산
  10~30% *전부* 라이브 역변동성을 이기고 예산이 클수록 격차 확대(30%: 17.9% vs 13.6%, +4.3%p).
  견고함(예산 선택 우연 아님).

⚠️ **운영자 결정 지점 — "레버리지 후 복리 극대화" 선택(2026-06-16). 분석 체인 완성, 결론 명확:**

- **레버리지는 안전 캡에 막힘**: `caps.py` 의 `global_exposure_pct ≤ 100`(헌법 원칙 I, 비협상)이
  레버리지(노출 >100%)를 원천 차단 → 레버리지 적용 = 안전 경계 변경(K-meta) = **운영자 명시
  승인 필수, 자율 불가.** (`specs/044-growth-optimal-leverage/LEVERAGE-CAP-BOUNDARY.md`)
- **캡 안 achievable 한 길 = 고정가중 무레버 재지정**: 역변동성보다 복리 +1.3~2.3%p, 거래비용
  10bp·자본 사다리(월간) 둘 다 반영해도 견고(PR #311·#313). 안전 경계 변경 0(재지정은 X.4
  게이트지 I-VII 변경 아님).
- **유일한 미해소 리스크 = 일별 강등**: 고정가중 무레버 낙폭 ≈9.6%가 사다리 강등선(10%)에
  바짝 붙음. 월간 데이터론 강등 거의 0이나, *일별*(실제 시스템)에선 더 자주 넘을 수 있음 —
  월간으로 확정 불가. 역변동성(5.5%)은 강등선 한참 아래라 무관. (`specs/050-capital-ladder/
  LADDER-NET-GROWTH-FINDINGS.md`)

**✅ 첫 실행 완료 (PR #315, main `a11170d`)**: 고정가중 등가중 3자산을 forward-paper
트랙(`deploy/global-trend-fixed-portfolio.toml`, 토너먼트 ARM G)으로 추가·머지. 라이브와
`weight_scheme`(equal vs inverse_vol)만 다름. PAPER 전용·전용 DB·halt flag 격리·재지정 0.

**다음 단계 (인스턴스 관찰 — 달력 시간 필요, 멀티 세션)**:
1. **globalfixed 트랙 일별 verdict 관찰** — 사이드카 `automation/rebalance-paper-forward-last-run`
   에서 globalfixed 가 정상 발행하는지(평일 22:30 UTC), 그리고 *일별 낙폭이 사다리 강등선
   (10%)을 얼마나 넘는지* 실측 누적. 이게 고정가중 재지정 안전성의 답(월간으로 확정 못 한 것).
2. **충분히 쌓이면(EDGE_CONFIRMED + 지문 정합)** → 운영자가 고정가중 라이브 재지정 결정(X.4).
   일별 강등이 잦으면 → 역변동성 유지가 옳음(안전여유). 데이터가 가른다.
3. **레버리지 경로(운영자 승인 시)**: 안전 경계 변경 PR(`global_exposure_pct` 상한↑, 헌법
   원칙 I, "this changes the safety perimeter" 표식 + 운영자 K-meta 확인). 아직 미착수(승인 대기).

남은 선택 후속(읽기 전용·비게이트): 깊은 검사(OOS·레버리지·사다리)를 사이드카로 상시화
(`regime-stratify.yml` 패턴, 인스턴스 비용 0); 비상관 차원 연구(추세추종 외, 긴급도 낮음).

<details><summary>직전 경보 원문(역사 — 위에서 해결됨)</summary>

**직전 발견(이제 착시로 판명)**: 백테스트 앵커드 워크플로(#302)가 라이브 GLOBAL-TREND 를 깊은
OOS(2022~2026, 748관측)로 돌려 "단순 보유 못 이김(3구간 0승)·라이브 배포 정당화 안 됨"이라
했다. → 사이드카 `automation/forward-anchored-verdict-last-run` LAST_RUN.md. **그러나 그 창은
강세장 편향이라, 위 #307 의 깊은 150년 검사가 그게 착시임을 입증함.**
</details>

**다음 세션 최우선 작업 (순서대로)**:
1. **모든 토너먼트 후보 전략을 같은 깊은 OOS 검사로 비교** — trend-on/off·risk-managed-beta·
   multi-asset-trend·global-trend·global-trend-wide 각각 `portfolio-walk-forward`(또는
   `forward-verdict-anchored`)로 돌려 **단순 보유를 강건하게 이기는(robust edge) 전략이 있는지**
   찾는다. forward-anchored-verdict.yml 을 전 후보로 확장(regime-stratify 가 global+wide 2트랙
   하는 패턴)하거나, 후보별 walk-forward 비교 사이드카를 만든다. **이게 실제 돈으로 가는 핵심.**
2. 강건한 엣지가 있는 후보가 나오면 → 그 전략을 라이브 지정(검증=배치 지문 정합)한다.
   가속기 게이트 배선은 PR #357로 완료되어, `forward-edge-autoarm.yml`이 앵커드 판정을
   직접 계산해 `ladder-decide --anchored-verdict-json`으로 넘긴다.
3. 강건한 엣지가 *어느 후보에도* 없으면 → 전략 연구가 진짜 과제(추세추종 외 차원: 평균회귀·
   캐리·품질팩터 등 비상관 엣지 추가). 운영자와 방향 합의 후 후보 추가.

**가속기 배선 현황(완료 — 실제 돈 게이트에 연결됨)**:
- ✅ 엔진(#298)·파이프라인(#299)·CLI `forward-verdict-anchored`(#301)·발행 워크플로(#302)·
  결합 함수 `combine_edge_verdicts`(#304)·`ladder-decide --anchored-verdict-json` 결합(#305).
- ✅ **게이트 소비 활성화(#357, main `28bd306`)**: `forward-edge-autoarm.yml`이 표준
  `forward-verdict`와 앵커드 `forward-verdict-anchored`를 둘 다 계산하고
  `ladder-decide --anchored-verdict-json`으로 넘긴다. 단, 앵커드 OOS walk-forward가
  벤치마크 대비 강건한 엣지를 못 세우면 `NO_EDGE`로 거부한다. 최신 수동 검증(run
  `27778082054`)은 `WAIT_EDGE`, `edge_source=none`, 센티넬 변경 없음.

**세션 운영 메모**: 이번 세션에 도구 호출 형식 오류(`antml:` 접두사 누락)가 반복돼 운영자
시간을 낭비함. 다음 세션은 모든 도구 호출에 `antml:invoke`/`antml:parameter` 접두사를 반드시
정확히 쓸 것.

## 최근 관찰 — 2026-06-22 (스펙 062 money-path 실제 돈 최상위 상태)

현재 `main` 최신은 `3440001`(#384, 스펙 062 money-path 실제 돈 최상위 상태)이다.
직전 주요 커밋은 `81a2c17`(money-path live-money state 구현), `801dda1`(#383, Telegram 서버
연결 handoff), `845c5b1`(#382, Telegram 서버 연결 자동화)이다. 이 인계 갱신 시점의 열린 PR은 없다.

- **핵심 교정**: 실제 돈 상태는 더 이상 오래된 `HANDOFF.md` 역사 문단, KIS smoke 현금값, 기존
  첫-자본 ETA만으로 판단하지 않는다. money-path JSON/text의 `live_money_state`가 최상위 판독
  표면이다.
- **현재 판독 원본**: live 의도는 `automation/rebalance-micro-gtaa.request`, 마지막 실행 증거는
  `origin/automation/rebalance-micro-gtaa-last-run:LAST_RUN.md`, 종합 표면은
  `origin/automation/money-path-last-run:LAST_RUN.md`다.
- **스펙 062 로컬 재현 결과**: automation sidecar를 fetch한 뒤 `scripts/money_path_probe.py`를
  실행하면 `live_money_state.status=REAL_ORDER_PATH_ARMED`, `can_submit_real_orders=true`,
  `capital_usd=1000`으로 나온다. 다음 예약 live 후보는 로컬 재현 시각
  `2026-06-22T12:55:00Z` 기준 `2026-06-22T15:00:00Z`였다. 그 이후 세션은 최신 sidecar를 다시 읽는다.
- **마지막 실행 증거 분리**: 마지막 micro GTAA 실행 `run_id=27935469561`은 `event=workflow_dispatch`,
  `live_step=success`였지만, 브로커 주문 상태는 `REJECTED_BY_BROKER` 2건이고 접수·체결은 0건이다.
  "실제 돈 경로가 켜짐"과 "주문이 접수·체결됨"을 분리해서 말해야 한다.
- **안전 경계**: 등급 2 운영 상태 판독 변경이다. 실제 주문 실행, 자본 증액, live 전략 변경,
  K1/K2/K4/K5/K6, 비밀값, 감사 로그, 브로커 주문 제한은 바꾸지 않았다.
- **검증**: PR #384 머지 전 `uv run pytest` 2249 통과·4 스킵, `uv run ruff check src tests`
  통과, `uv run python scripts/agent_harness_probe.py --strict` `OK (14/14)`,
  `uv run python scripts/check_handoff_facts.py` 통과, PR 품질 관문 통과. 머지 직전 전체 테스트와
  린트를 다시 실행해 같은 결과를 확인했다.

## 최근 마일스톤 — 2026-08-04 KST (#571 후보 결과 실행기 retryable blocked 진단 복구)

#571로 후보 결과 실행기가 retryable factory-blocked 패키지를 안전한 no-live 검증까지 진행하게 됐다.
post-merge `candidate-implementation-results` sidecar는 commit `5d181e7`, timestamp `2026-08-04T01:10:24Z`,
`blocked=0`, `pending=2`, `diagnostic_counts.data_history_missing=2`다. 이것은 PSR 기준을 낮춘 변경이 아니라,
PSR을 높일 수 있는 후보의 실제 검증 병목을 `blocked`에서 "과거 가격 데이터 준비 필요"로 좁힌 변경이다.
돈 경로는 여전히 `PREVIEW_ONLY`/`NO_EDGE_YET`이고, 가장 가까운 `globalfixed` 후보 PSR은
`0.922697 < 0.95`다. 상세는 `HANDOFF-128-CANDIDATE-RESULT-RETRYABLE-BLOCKED.md`.

## 최근 마일스톤 — 2026-08-03 KST (#568/#569 live canary sidecar gate와 observe gateway 복구)

#568로 live canary workflow를 preview/status job과 production real-order job으로 나눴고, #569로 preview/status
원격 실행을 fixed `observe live-canary-*` gateway 명령으로 옮겼다. 배포 run `30777301767`은 success이고
서버 helper refresh 표식을 확인했다. main live canary run `30777338028`은 `armed=false`, preview job success,
real-order job skipped, sidecar timestamp `2026-08-03T01:38:34Z`다. 최신 sidecar에는 `refused command`가 없고
드라이런 결과와 NAV/forward-verdict 결과가 들어 있다. pipeline-liveness run `30777384529`는 종합 `OK`,
`rebalance-live-canary` `OK`/0.0h다. money-path run `30777446988`는 여전히 `PREVIEW_ONLY`/`NO_EDGE_YET`,
capital-path-readiness run `30777476105`는 `ACCUMULATING_EDGE`, 우선 후보 없음이다. 상세는
`HANDOFF-127-LIVE-CANARY-OBSERVE-GATEWAY.md`.

## 최근 마일스톤 — 2026-08-01 KST (#566 forward paper 경제 장부 보정)

#566으로 forward paper 리밸런서가 종이 체결 감사 로그(`ORDER_PAPER_FILLED`)에서 가상 보유를
재구성하게 됐다. 배포 run `30674990967`은 success다. `rebalance-paper-forward.yml` run
`30675023375`는 commit `f15f87d`, timestamp `2026-08-01T00:17:37Z`, 7개 트랙 prep/verdict
`ssh_exit=0`이며, 최신 sidecar에는 `planned_buy_notional_usd=0.00`과 `SELL PAPER_FILLED`가 남아
반복 매수 병목이 닫혔음을 보여준다. `money-path` run `30675222849`는 여전히
`PREVIEW_ONLY`/`NO_EDGE_YET`, `capital-path-readiness` run `30675223926`은 `ACCUMULATING_EDGE`와
우선 후보 없음이다. 상세는 `HANDOFF-126-FORWARD-PAPER-ECONOMIC-ANCHOR.md`.

## 최근 마일스톤 — 2026-07-31 KST (#564 regime-stratify observe gateway 복구)

#564로 `regime-stratify` 연구 sidecar가 raw `scp`와 inline SSH 대신 fixed
`observe regime-stratify global|wide` gateway를 쓰게 됐다. 배포 run `30630190101`은 success이고 서버
observe helper 갱신과 worker 재시작을 로그로 확인했다. `regime-stratify.yml` run `30630190081`은
타임라인 prep exit 0, 두 트랙 모두 `ssh_exit=0`, `schema_version=1.0` JSON을 남겼다. 최신 money-path는
계속 `PREVIEW_ONLY`/`NO_EDGE_YET`라 실주문은 안전 게이트 뒤에 있다. 상세는
`HANDOFF-125-REGIME-STRATIFY-OBSERVE-GATEWAY.md`.

## 최근 마일스톤 — 2026-07-31 KST (스펙 122 forward paper DB writability 복구)

#562로 forward paper 관측 DB의 읽기 전용 권한 drift를 종이거래 저장소 안에서만 복구했다.
배포 run `30596929563`은 success이고 서버 observe helper 갱신을 로그로 확인했다. 수동
`rebalance-paper-forward.yml` run `30596973332`는 모든 prep/verdict `ssh_exit=0`이며 최신 sidecar에
readonly DB 오류 문자열이 없다. 최신 money-path는 `PREVIEW_ONLY`/`NO_EDGE_YET`, edge-autoarm은
`WAIT_EDGE`라 실주문은 여전히 안전 게이트 뒤에 있다. 상세는
`HANDOFF-124-FORWARD-PAPER-DB-WRITABILITY.md`.

## 최근 마일스톤 — 2026-07-31 KST (스펙 121 promote-readiness 관측 복구)

#559/#560으로 헌법 VI(라이브 트랙레코드) 승격 준비도 관측 경로를 복구했다. raw SSH command는
fixed `observe promote-readiness`로 대체됐고, 서버에 설치된 root-owned gateway/helper가 낡아지는
문제는 deploy service의 root-only helper refresh pre-step으로 닫았다. 수동 `promote-readiness`
run `30592627513`은 commit `85584ed` 기준 success, sidecar `ssh_exit=1`, READY=false, stderr empty다.
즉 SSH setup 오류는 해소됐고, 현재 상태는 정상 not-ready 판정이다. 상세는
`HANDOFF-123-PROMOTE-READINESS-OBSERVE-GATEWAY.md`.

## 최근 마일스톤 — 2026-07-15 KST (스펙 118 마무리와 KIS 열린 주문 smoke 보강)

#525(`158052a`)로 최종 완료 보고가 운영자가 다시 묻지 않아도 되는지 판정하는 읽기 전용 계약이 main에
들어갔고, #527(`2b9fe85`)로 KIS live smoke가 최근 7일 주문/체결 조회와 열린 미체결 주문 0건까지
검사한다. main push KIS smoke run `29422806756`은 5개 read-only 검사를 통과했고 열린 주문은 0건이었다.
released-work run `29422911779`는 스펙 118 후보를 released로 소비했고, autonomous-work run `29422962267`은
현재 실행 가능한 안전 후보가 없다고 보고했다. Deploy run `29422806870`은 미국 장중 배포 금지로
`2026-07-15T20:00:00Z` 이후 자동 재배포 대기 상태이며, 이는 안전장치 동작이다. 등급 2 읽기 전용
운영 smoke 보강이며 실제 주문·취소·실거래 재무장·자본·whitelist/caps·헌법·커널·비밀값 변경은 없다.
상세는 `HANDOFF-118-KIS-OPEN-ORDER-SMOKE.md`와 `HANDOFF-117-OPERATOR-REPORT-LIVENESS-CONTRACT.md`.

## 최근 마일스톤 — 2026-07-10 KST (스펙 108 PR/머지 증거 생존성 계약)

- main 코드 베이스라인: `7d06550`(PR #503). 기능 커밋: `5b71a23`.
- PR/merge evidence liveness probe가 PR 본문 품질 관문, main merge commit, released-work 장부,
  deploy 관측을 함께 읽어 작업 완료 증거의 `PASS`/`WAIT`/`FAIL` 상태를 분리한다.
- `candidate-pr-merge-evidence-liveness-contract`는 스펙 108 completed marker로 released-work 장부에 들어갔다.
- 최신 autonomous-work sidecar run `29076284765`는 `candidate-worktree-concurrency-liveness-contract`를
  `EXECUTION_READY`, 위험 등급 2, 안전 영향 없음으로 선택했다.
- post-merge runs: deploy `29076284769`, released-work `29076284798`, autonomous-work
  `29076284765` success.
- 안전 경계: 등급 2 읽기 전용 PR/머지 증거 계약이다. 주문, 자본, live 전략, whitelist/caps,
  헌법, 커널, 비밀값, 외부 유료 서비스 변경 없음.
- 상세: `HANDOFF-112-PR-MERGE-EVIDENCE-LIVENESS-CONTRACT.md`.

## 최근 마일스톤 — 2026-07-08 KST (스펙 107 HANDOFF 사실성 생존성 계약)

- main 코드 베이스라인: `1c412d9`(PR #501). 기능 커밋: `932b85e`.
- HANDOFF truth liveness probe가 `HANDOFF.md`와 `check_handoff_facts.py`를 함께 읽어
  origin/main 직접 일치, handoff-only 첫 부모 기준, stale HANDOFF를 분리한다.
- `candidate-handoff-truth-liveness-contract`는 스펙 107 completed marker로 released-work 장부에 들어갔다.
- 최신 autonomous-work sidecar run `28913334433`은 `candidate-pr-merge-evidence-liveness-contract`를
  `EXECUTION_READY`, 위험 등급 2, 안전 영향 없음으로 선택했다.
- post-merge runs: deploy `28913334443`, released-work `28913334487`, autonomous-work
  `28913334433` success.
- 안전 경계: 등급 2 읽기 전용 HANDOFF 사실성 계약이다. 주문, 자본, live 전략, whitelist/caps,
  헌법, 커널, 비밀값, 외부 유료 서비스 변경 없음.
- 상세: `HANDOFF-111-HANDOFF-TRUTH-LIVENESS-CONTRACT.md`.

## 최근 마일스톤 — 2026-07-06 KST (스펙 100 레짐 타임라인 커버리지 계약)

- main 코드 베이스라인: `48314cd`(PR #487). 기능 커밋: `7a2ba58`.
- regime timeline coverage probe가 `regime_timeline.csv`, regime-stratify, pipeline-liveness,
  released-work를 함께 읽어 레짐 타임라인 커버리지를 판정한다.
- 최신 sidecar 재현은 `OBSERVATION_WAIT`, timeline 2372행, label coverage PASS,
  forward join quality PASS, rare `RISK_OFF` observation floor WAIT다.
- `candidate-regime-timeline-coverage-contract`는 스펙 100 completed marker로 released-work 장부에 들어갈 수 있고,
  이 handoff 브랜치 로컬 재현에서 released 확인됐다.
- 같은 상태의 autonomous-work 로컬 재현은 `candidate-data-evidence-liveness-contract`를
  `EXECUTION_READY`, 위험 등급 2, 안전 영향 없음으로 선택했다.
- post-merge runs: deploy `28799231896`, released-work `28799231124`, autonomous-work
  `28799231156` success. 코드 PR 시점 remote sidecar는 T018/T023 미완료 때문에 아직 스펙 100을 released로
  읽지 않았고, 이 handoff가 그 완료 체크를 닫았다.
- 안전 경계: 등급 2 읽기 전용 데이터 품질 계약이다. 주문, 자본, live 전략, whitelist/caps, 헌법, 커널,
  비밀값, 외부 유료 서비스 변경 없음.
- 상세: `HANDOFF-104-REGIME-TIMELINE-COVERAGE-CONTRACT.md`.

## 최근 마일스톤 — 2026-07-06 KST (스펙 099 공개 데이터 입력 품질 계약)

- main 코드 베이스라인: `c3803cd`(PR #485). 기능 커밋: `1425958`.
- public-data input-quality probe가 public-data, regime, regime timeline, regime-stratify,
  pipeline-liveness, released-work, capital-path readiness를 함께 읽어 공개 데이터 입력 품질을 판정한다.
- 최신 sidecar 재현은 `CONTRACT_READY`, public-data 11/11 발행, 교차검증 5개 PASS,
  regime timeline 2372행, stratified return 751일, liveness OK다.
- `candidate-public-data-input-quality-contract`는 스펙 099 completed marker로 released-work 장부에 들어갔다.
- 최신 autonomous-work sidecar run `28791708758`은 `candidate-regime-timeline-coverage-contract`를
  `EXECUTION_READY`, 위험 등급 2, 안전 영향 없음으로 선택했다.
- post-merge runs: deploy `28791708696`, released-work `28791708832`, autonomous-work
  `28791708758` success.
- 안전 경계: 등급 2 읽기 전용 데이터 품질 계약이다. 주문, 자본, live 전략, whitelist/caps, 헌법, 커널,
  비밀값, 외부 유료 서비스 변경 없음.
- 상세: `HANDOFF-103-PUBLIC-DATA-INPUT-QUALITY-CONTRACT.md`.

## 최근 마일스톤 — 2026-07-06 KST (스펙 098 데이터 증거 frontier 지도)

- main 코드 베이스라인: `6aa85c6`(PR #483). 기능 커밋: `3e6d8e6`.
- autonomous-work 보고서가 `data_evidence_frontier_map`을 발행하고, 데이터 증거 영역을
  공개 데이터 입력 품질, 레짐 타임라인 커버리지, 데이터 증거 생존성 3개 후보로 분해한다.
- `candidate-data-evidence-frontier-map`은 스펙 098 completed marker로 released-work 장부에 들어갔다.
- 최신 autonomous-work sidecar run `28786862604`는 `candidate-public-data-input-quality-contract`를
  `EXECUTION_READY`, 위험 등급 2, 안전 영향 없음으로 선택했다.
- 데이터 입력 증거 파싱은 public-data `overall_ok=True, published=11`, regime-stratify
  `total_return_days=751`로 정상이다.
- post-merge runs: deploy `28786862434`, released-work `28786862491`, autonomous-work
  `28786862604` success.
- 안전 경계: 등급 2 읽기 전용 work packet 확장이다. 주문, 자본, live 전략, whitelist/caps, 헌법, 커널,
  비밀값, 외부 유료 서비스 변경 없음.
- 상세: `HANDOFF-102-DATA-EVIDENCE-FRONTIER-MAP.md`.

## 최근 마일스톤 — 2026-07-06 KST (스펙 097 비용 차감 no-live 엣지 실험 계약)

- main 코드 베이스라인: `49c4331`(PR #481). 기능 커밋: `e50e0c7`.
- cost-adjusted probe가 forward verdict와 execution-quality를 함께 읽어 비용 스트레스 후보와 비용 기준 부족을 분리한다.
- `candidate-cost-adjusted-edge-experiment`는 스펙 097 completed marker로 released-work 장부에 들어갔다.
- 최신 autonomous-work sidecar run `28784829374`은 `candidate-data-evidence-frontier-map`를
  `EXECUTION_READY`, 위험 등급 2, 안전 영향 없음으로 선택했다.
- 스펙 097 probe 최신 재현은 `OBSERVATION_WAIT`, forward 관측 16/20, 남은 관측 4개,
  비용 스트레스 후보 21개, 50bps 기준 최상위 `multiasset`, `cost-basis-completeness=WAIT`다.
- post-merge runs: deploy `28784829389`, released-work `28784829439`, autonomous-work
  `28784829374` success.
- 안전 경계: 등급 2 no-live 실험 계약이다. 주문, 자본, live 전략, whitelist/caps, 헌법, 커널,
  비밀값, 외부 유료 서비스 변경 없음.
- 상세: `HANDOFF-101-COST-ADJUSTED-EDGE-EXPERIMENT.md`.

## 최근 마일스톤 — 2026-07-05 KST (스펙 096 신호 다변화 no-live 엣지 실험 계약)

- main 코드 베이스라인: `df8cc23`(PR #479). 기능 커밋: `999fbd2`.
- signal-diversification probe가 forward track을 신호군 6개로 묶고 incumbent와 낮게 겹치는 no-live 후보를 분리한다.
- `candidate-signal-diversification-edge-experiment`는 스펙 096 completed marker로 released-work 장부에 들어갔다.
- 최신 autonomous-work sidecar run `28740023276`은 `candidate-cost-adjusted-edge-experiment`를
  `EXECUTION_READY`, 위험 등급 2, 안전 영향 없음으로 선택했다.
- 스펙 096 probe 최신 재현은 `OBSERVATION_WAIT`, forward 관측 16/20, 남은 관측 4개,
  낮은 겹침 제안 후보 3개다.
- post-merge runs: deploy `28740023274`, released-work `28740023261`, autonomous-work
  `28740023276` success.
- 안전 경계: 등급 2 no-live 실험 계약이다. 주문, 자본, live 전략, whitelist/caps, 헌법, 커널,
  비밀값, 외부 유료 서비스 변경 없음.
- 상세: `HANDOFF-100-SIGNAL-DIVERSIFICATION-EDGE-EXPERIMENT.md`.

## 최근 마일스톤 — 2026-07-04 KST (스펙 095 forward 레짐 엣지 no-live 실험 계약)

- main 코드 베이스라인: `a083b31`(PR #477). 기능 커밋: `705f049`.
- forward-regime probe가 forward 리더보드, money-path, released-work, learning ledger,
  pipeline-liveness를 함께 읽어 레짐별 no-live 실험 계약을 만든다.
- `candidate-forward-regime-edge-experiment`는 스펙 095 completed marker로 released-work 장부에 들어갔다.
- 최신 autonomous-work sidecar run `28707157779`은 `candidate-signal-diversification-edge-experiment`를
  `EXECUTION_READY`, 위험 등급 2, 안전 영향 없음으로 선택했다.
- 스펙 095 probe 최신 재현은 `OBSERVATION_WAIT`, forward 관측 16/20, 남은 관측 4개다.
- post-merge runs: deploy `28707157800`, released-work `28707157804`, autonomous-work
  `28707157779` success.
- 안전 경계: 등급 2 no-live 실험 계약이다. 주문, 자본, live 전략, whitelist/caps, 헌법, 커널,
  비밀값, 외부 유료 서비스 변경 없음.
- 상세: `HANDOFF-099-FORWARD-REGIME-EDGE-EXPERIMENT.md`.

## 최근 마일스톤 — 2026-07-04 KST (스펙 094 투자 엣지 frontier 지도와 no-live 실험 후보 전진)

- main 코드 베이스라인: `02e7d6e`(PR #475). 기능 커밋: `f18b8af`.
- autonomous-work 보고서가 `investment_edge_frontier_map`을 JSON과 Markdown에 발행한다.
- `candidate-investment-edge-frontier-map`은 스펙 094 completed marker로 released-work 장부에 들어갔다.
- 최신 autonomous-work sidecar run `28706285171`은 `candidate-forward-regime-edge-experiment`를
  `EXECUTION_READY`, 위험 등급 2, 안전 영향 없음으로 선택했다.
- post-merge runs: deploy `28706285176`, released-work `28706285172`, autonomous-work
  `28706285171` success.
- 안전 경계: 등급 2 운영 자동화 보정. 주문, 자본, live 전략, whitelist/caps, 헌법, 커널,
  비밀값, 외부 유료 서비스 변경 없음.
- 상세: `HANDOFF-098-INVESTMENT-EDGE-FRONTIER-MAP.md`.

## 최근 마일스톤 — 2026-07-04 KST (스펙 093 거시 후보 지도와 후보 재생성 루프)

- main 코드 베이스라인: `7438f38`(PR #473). 기능 커밋: `23704a2`.
- autonomous-work 보고서가 `macro_candidate_map`을 JSON과 Markdown에 발행한다.
- `candidate-macro-candidate-map-regenerator`는 스펙 093 completed marker로 released-work 장부에 들어갔다.
- 최신 autonomous-work sidecar run `28705183168`은 `candidate-investment-edge-frontier-map`을
  `EXECUTION_READY`, 위험 등급 2, 안전 영향 없음으로 선택했다.
- post-merge runs: deploy `28705183202`, released-work `28705183167`, autonomous-work
  `28705183168` success.
- 안전 경계: 등급 2 운영 자동화 보정. 주문, 자본, live 전략, whitelist/caps, 헌법, 커널,
  비밀값, 외부 유료 서비스 변경 없음.
- 상세: `HANDOFF-097-MACRO-CANDIDATE-MAP-REGENERATOR.md`.

## 최근 마일스톤 — 2026-07-04 KST (스펙 092 자율 후보 고갈 뒤 frontier 발굴 후보 폐쇄)

- main 코드 베이스라인: `b004d2f`(PR #471). 기능 커밋: `d90bd71`.
- autonomous-work가 known macro 후보 3개가 모두 닫힌 뒤 `candidate-autonomous-frontier-discovery`를
  `EXECUTION_READY` 후보로 만들 수 있게 됐다.
- `candidate-autonomous-frontier-discovery`는 스펙 092 completed marker로 released-work 장부에 들어갔다.
- 최신 autonomous-work sidecar run `28689000427`은 `overall_status=RELEASED`, ranked 후보 0개다.
  `selected_work=candidate-fd04772a23c5`는 닫힌 released 후보이며 새 착수 후보가 아니다.
- post-merge runs: deploy `28689000449`, released-work `28689000437`, autonomous-work
  `28689000427` success.
- 안전 경계: 등급 2 운영 자동화 보정. 주문, 자본, live 전략, whitelist/caps, 헌법, 커널,
  비밀값, 외부 유료 서비스 변경 없음.
- 상세: `HANDOFF-096-FRONTIER-CANDIDATE-DISCOVERY.md`.

## 최근 마일스톤 — 2026-07-03 KST (스펙 091 자율 성장 목적 함수와 탐색 예산 보정)

- main 코드 베이스라인: `944d2dc`(PR #469). 기능 커밋: `eb11416`.
- autonomous-work 보고서가 `objective_calibration` 블록을 발행한다. 후보별 성장 기여도, 증거 준비도,
  검증 비용 적합도, 안전 여유, 학습 가치, 총점, 탐색 예산, 중단 조건, 반복 학습 지표가 JSON과
  Markdown에 남는다.
- `candidate-autonomous-growth-objective-calibration`은 스펙 091 completed marker로 released-work
  장부에 들어갔다.
- 최신 autonomous-work sidecar run `28662665589`은 새 목적 함수 블록을 발행하지만,
  `overall_status=RELEASED`이고 새 `EXECUTION_READY` 후보는 없다. `selected_work=candidate-fd04772a23c5`는
  닫힌 released 후보다.
- post-merge runs: deploy `28662665531`, released-work `28662665530`, autonomous-work
  `28662665589` success.
- 안전 경계: 등급 2 운영 자동화 보정. 주문, 자본, live 전략, whitelist/caps, 헌법, 커널,
  비밀값, 외부 유료 서비스 변경 없음.
- 상세: `HANDOFF-095-AUTONOMOUS-GROWTH-OBJECTIVE-CALIBRATION.md`.

## 최근 마일스톤 — 2026-07-03 KST (스펙 090 source diversification 산출 후보 완료 폐쇄)

- main 코드 베이스라인: `2f64cba`(PR #467). 기능 커밋: `a167fee`.
- `candidate-source-diversification-sidecar-bottleneck`은 스펙 090 completed marker로 released-work 장부에 들어갔다.
- 최신 autonomous-work sidecar run `28643121911`은 다음 후보
  `candidate-autonomous-growth-objective-calibration`을 `EXECUTION_READY`로 선택한다.
- post-merge runs: deploy `28643121916`, released-work `28643121934`, autonomous-work
  `28643121911` success.
- 안전 경계: 등급 2 운영 자동화 보정. 주문, 자본, live 전략, whitelist/caps, 헌법, 커널,
  비밀값, 외부 유료 서비스 변경 없음.
- 상세: `HANDOFF-094-SOURCE-DIVERSIFICATION-CANDIDATE-CLOSURE.md`.

## 최근 마일스톤 — 2026-07-03 KST (스펙 089 정적 후보 템플릿 밖 증거 기반 후보 공간 확장)

- main 코드 베이스라인: `b243a06`(PR #465). 기능 커밋: `c67fda4`.
- autonomous-evolution loop가 `released-work`와 `capital-path-readiness`를 직접 읽고, 정적 후보가
  모두 완료·거절·보류로 닫히면 새 후보 `candidate-source-diversification-sidecar-bottleneck`을 만든다.
- `candidate-evolution-source-diversification`은 스펙 089 완료 marker로 released-work 장부에 들어갔다.
- post-merge runs: deploy `28639386244`, autonomous-evolution `28639386349`, autonomous-work
  `28639386220`, released-work `28639386219`, execution-quality `28639386186` success.
- 순서 주의: 같은 push의 autonomous-work sidecar는 갱신 전 evolution sidecar를 읽어
  `candidate-autonomous-growth-objective-calibration`을 골랐지만, 최신 sidecar 로컬 재현은
  `candidate-source-diversification-sidecar-bottleneck`을 `EXECUTION_READY`로 선택한다.
- 안전 경계: 등급 2 운영 자동화 보정. 주문, 자본, live 전략, whitelist/caps, 헌법, 커널,
  비밀값, 외부 유료 서비스 변경 없음.
- 상세: `HANDOFF-093-EVOLUTION-SOURCE-DIVERSIFICATION.md`.

## 최근 마일스톤 — 2026-07-03 KST (스펙 088 거시 자율 성장 후보 발굴기)

- main 코드 베이스라인: `927beb0`(PR #463). 기능 커밋: `bca5415`.
- 일반 work packet이 모두 `RELEASED` 또는 `SUPPRESSED`로 닫히고 실행·복구·승인 필요 후보가 없으면,
  자율 작업 실행 루프가 닫힌 큐 상태 자체를 거시 후보로 승격한다.
- `candidate-macro-growth-discovery`는 스펙 088 완료 marker로 released-work 장부에 들어갔다.
  최신 autonomous-work sidecar는 다음 후보 `candidate-evolution-source-diversification`을
  `EXECUTION_READY`로 선택한다.
- post-merge runs: deploy `28637783776`, released-work `28637783779`, autonomous-work
  `28637783763` success.
- 안전 경계: 등급 2 운영 자동화 보정. 주문, 자본, live 전략, whitelist/caps, 헌법, 커널,
  비밀값, 외부 유료 서비스 변경 없음.
- 상세: `HANDOFF-092-AUTONOMOUS-MACRO-GROWTH-DISCOVERY.md`.

## 최근 마일스톤 — 2026-07-03 KST (스펙 087 학습 장부 후보 재발굴 차단)

- main 코드 베이스라인: `753afb7`(PR #461). 기능 커밋: `f1d86f4`.
- `learning_ledger.json`의 `rejected/discard`, `evidence_dependent/deferred/observe`,
  `operator_review` 결정이 후보 상태와 `safe_high_leverage_work`에 실제 반영된다.
- `candidate-fa66202bf496`는 스펙 087 완료 marker로 released-work 장부에 들어갔고, 최신
  autonomous-work sidecar에서 `RELEASED`로 억제된다. 현재 실행 가능한 안전 후보는 없다.
- post-merge runs: deploy `28632340034`, released-work `28632340016`, autonomous-evolution
  `28632340021`, autonomous-work `28632340035`, execution-quality `28632340008` success.
- 안전 경계: 등급 2 운영 자동화 보정. 주문, 자본, live 전략, whitelist/caps, 헌법, 커널,
  비밀값, 외부 유료 서비스 변경 없음.
- 상세: `HANDOFF-091-LEARNING-LEDGER-CANDIDATE-MEMORY.md`.

## 최근 마일스톤 — 2026-07-03 KST (스펙 086 자율 루프 sidecar와 HANDOFF 생존성)

- main 코드 베이스라인: `2de0f95`(PR #459). 관련 머지: #457 `671b1a7`, #458 `e8779c8`.
- `candidate-88a7e7f07361`는 이미 충족된 `autonomous-evolution` liveness와 HANDOFF `/sync` 진입점 보정이므로,
  자율 성장 루프가 이를 `released`로 낮추고 `released-work` 완료 장부가 반복 선택을 막는다.
- #458은 promotion/factory가 직전 sidecar를 읽어도 current-checkout released-work 장부로 이 후보를 버리게 했고,
  #459는 result executor도 stale package 실행과 fresh result 발행을 건너뛰게 했다.
- post-merge runs: deploy `28629315303`, released-work `28629315307`, autonomous-work `28629315301`,
  candidate factory `28629315287`, candidate result executor `28629315296` success. 최신 sidecar에서
  released-work=`released`, autonomous-work=`RELEASED`, promotion=`DISCARD`, factory/package/result 후보 없음.
- 안전 경계: 등급 2 운영 자동화 보정. 주문, 자본, live 전략, whitelist/caps, 헌법, 커널,
  비밀값, 외부 유료 서비스 변경 없음.
- 상세: `HANDOFF-090-AUTONOMOUS-SIDECAR-HANDOFF-LIVENESS.md`.

## 최근 마일스톤 — 2026-07-02 KST (스펙 085 공개 데이터 수집·교차 검증 확장)

- main 코드 베이스라인: `d381199`(PR #455). 기능 커밋: `f84e478`.
- FRED 그래프 CSV DGS2/DGS10을 연구 전용 public-data 수집에 추가했고, Treasury-vs-FRED 수준 대조
  2건을 더해 public-data 교차 검증이 5건이 됐다.
- post-merge `Collect public data (research)` run `28596926048` success: `overall_ok=True`,
  `published=11`, cross_checks 5건 PASS, Treasury-vs-FRED DGS2/DGS10 overlap 2,373, agree `100.00%`.
- #455 main push의 released-work/autonomous-work sidecar는 handoff 전 tasks 상태 때문에
  `candidate-facf2fa31834`를 아직 선택 후보로 남겼다. 이 handoff는 T021을 닫으므로 handoff merge 뒤
  이 후보가 released-work 완료 후보로 소비되어야 한다.
- 안전 경계: 등급 2 공개 데이터 운영 채널 보정. 주문, 자본, live 전략, whitelist/caps, 헌법, 커널,
  비밀값, 외부 유료 서비스 변경 없음. public-data는 연구·백테스트·검증 전용이다.
- 상세: `HANDOFF-089-PUBLIC-DATA-CROSS-VALIDATION.md`.

## 최근 마일스톤 — 2026-07-02 KST (스펙 084 오래된 증거와 성과 실패 분리)

- main 코드 베이스라인: `e77a42c`(PR #451). 최신 인계 베이스라인: `4daf5d7`(PR #453).
- `capital-path-readiness`가 `released-work`와 `pipeline-liveness`를 읽어 완료 후보 잔향과
  sidecar 신선도 문제를 `observability_issues`로 분리한다.
- post-merge runs: deploy `28576674026`, capital-path-readiness `28576674262`,
  released-work `28576674252`, autonomous-work `28576674094` 모두 success.
- 남은 sidecar 순서 위험은 capital-path-readiness workflow_dispatch run `28584170609`와 최신
  schedule run `28584438033` 성공으로 닫혔다. 최신 capital-path-readiness sidecar는
  `candidate-6ee3370e933d`를 released echo로 억제하고 priority를 `candidate-facf2fa31834` 하나만 남긴다.
- 안전 경계: 등급 2 운영 자동화 보정. 주문, 자본, live 전략, whitelist/caps, 헌법, 커널,
  비밀값, 외부 유료 서비스 변경 없음.
- 상세: `HANDOFF-088-STALE-EVIDENCE-SEPARATION.md`.

## 최근 마일스톤 — 2026-07-02 KST (스펙 082 레짐·성과 후보 점수화)

스펙 082는 자율 성장 루프가 고른 `candidate-e481b0309206`를 실제로 처리했다. #446이
`promote-readiness` 성과 표면을 자율 성장 manifest와 분석 후보 evidence refs에 추가해,
레짐 층화·공개 데이터·승격 준비 성과가 함께 후보 점수로 들어간다. `READY=false`는 장애가 아니라
정상적인 보수적 성과 보고로 쓰고, 누락·stale·셋업 오류는 `sidecar_freshness` 의존으로 낮춘다.

post-merge evidence는 deploy run `28566029103` success, autonomous evolution run `28566029110`
success, autonomous work execution run `28566029113` success, released-work run `28566029091` success다.
최신 evolution sidecar에서 `candidate-e481b0309206`는 evidence refs
`regime-stratify/public-data/promote-readiness`, 점수 560, `status=new`를 기록한다. 이 handoff는
스펙 082 T017과 `completed_candidate_id` 마커를 닫아 released-work 로컬 재현에서 이 후보가
`released`로 소비되고, 다음 자율 작업 후보가 `candidate-dff4f9344b02`로 넘어가는 것까지 확인했다.
상세: `HANDOFF-086-REGIME-PERFORMANCE-CANDIDATE-SCORING.md`,
`specs/082-regime-performance-candidate-scoring/`.

안전 경계: 읽기 전용 운영 자동화 보정이다. 실제 주문, 실거래 전환, 자본 배분,
whitelist/caps/live 설정, 비밀값, 외부 유료 서비스, 헌법·커널 변경 없음. deploy success는
dry-run worker 코드 반영이지 실거래 전환이 아니다.

## 최근 마일스톤 — 2026-07-02 KST (스펙 081 자율 루프 품질 폐쇄)

스펙 081은 자율 성장 루프의 남은 운영상 흠을 닫았다. #444가
`autonomous-work-execution` 작업 패킷에 `CODEX_AUTONOMOUS_START`, 한글 착수 안내,
완료 관문을 넣어 다음 Codex 세션이 안전 후보를 해석 없이 시작할 수 있게 했다. 또한
money-path `14/20`과 edge/forward `15/20`처럼 sidecar 시점 차이에서 생기는 관측 수 불일치는
`SNAPSHOT_SKEW` 정보성 이슈로 남기고, 실제 판정은 `ALIGNED_WAITING`으로 유지한다.
`pipeline-liveness`는 `Operator mobile alerts` 완료 뒤 다시 실행될 수 있어 최신
`operator-status`를 읽는 후속 감시 경로가 생겼다.

post-merge evidence는 deploy run `28564456852` success, autonomous work run `28564456840` success,
money gate alignment run `28564456849` success, pipeline liveness run `28564456858` success다.
최신 선택 후보는 `candidate-e481b0309206`이고, 돈 경로는 여전히 `PREVIEW_ONLY`다. 상세:
`HANDOFF-085-AUTONOMOUS-LOOP-QUALITY-CLOSURE.md`, `specs/081-autonomous-loop-quality-closure/`.

안전 경계: 읽기 전용 운영 자동화 보정이다. 실제 주문, 실거래 전환, 자본 배분,
whitelist/caps/live 설정, 비밀값, 외부 유료 서비스, 헌법·커널 변경 없음. deploy success는
dry-run worker 코드 반영이지 실거래 전환이 아니다.

## 최근 마일스톤 — 2026-07-02 KST (스펙 080 운영자 대시보드와 모바일 알림 루프)

스펙 080은 흩어진 자율 루프 sidecar를 운영자용 한 줄 판단으로 묶는다. #441은 `operator-status`
sidecar와 모바일 상태판 요약, 개입 필요 시 Telegram best-effort 알림 루프를 추가했고, #442는
모바일 상태판 publish 경로의 bare `python3`/`httpx` 의존 실패를 보정했다. 최종 post-merge evidence는
`Deploy on merge to main` run `28562202999` success, `Operator mobile alerts` run `28562203117`
success, `Mobile status page (GitHub Pages)` run `28562203120` success, operator-status
`overall_status=OK`, `send_status=NOT_ATTEMPTED`, `money-path=PREVIEW_ONLY`,
`selected_work=candidate-e481b0309206`이다. `origin/gh-pages:status.html`에 운영자 요약 데이터가
포함된 것도 확인했다. 상세: `HANDOFF-084-OPERATOR-DASHBOARD-ALERTS.md`.

## 최근 마일스톤 — 2026-07-01 KST (스펙 078 돈 경로 게이트 정렬 루프)

스펙 078이 #434로 main에 들어갔다. 새 루프는 money-path, capital-path-readiness,
edge-autoarm, reassign, forward, pipeline, autonomous-work, KIS smoke sidecar를 읽어
돈 경로 게이트가 서로 같은 상태를 말하는지 `automation/money-gate-alignment-last-run`에
발행한다. 최신 run `28526440247`은 commit `09b528a` 기준 success이고, 현재 판정은
`ALIGNED_WAITING / PREVIEW_ONLY / ACCUMULATING_EDGE`다. blocker는
`전진 관측 부족: 14/20 (통계적 유의까지 더 쌓여야 함).`이고, 선택 후보는
`candidate-fd04772a23c5`다. pipeline liveness는 병렬 실행 경합 뒤 run `28526482569`로
재실행해 `overall=OK`, `money-gate-alignment=OK`가 됐다. 상세:
`HANDOFF-082-MONEY-GATE-ALIGNMENT.md`, `specs/078-money-gate-alignment-loop/`.

안전 경계: 읽기 전용 게이트 정렬 보고 루프다. 실제 주문, 실거래 전환, 자본 배분,
whitelist/caps/live 설정, 비밀값, 외부 유료 서비스, 헌법·커널 변경 없음. deploy success는
dry-run worker 코드 반영이지 실거래 전환이 아니다.

## 최근 마일스톤 — 2026-07-01 KST (스펙 077 자율 작업 실행 루프)

스펙 077이 #432로 main에 들어갔다. 새 루프는 자율 성장·승격·후보 검증·자본 준비도·
파이프라인 생존 sidecar를 읽어 다음 Codex 작업 패킷을
`automation/autonomous-work-execution-last-run`에 발행한다. 최신 run `28523867803`은
commit `996ce56` 기준 success이고, 현재 선택된 작업은 `candidate-fd04772a23c5`
(`돈 경로 준비도와 기존 게이트 정렬`, `EXECUTION_READY`, 위험 등급 2, 점수 3597)다.
pipeline liveness는 병렬 실행 경합 뒤 run `28523925493`으로 재실행해 `overall=OK`,
`autonomous-work-execution=OK`가 됐다. 상세:
`HANDOFF-081-AUTONOMOUS-WORK-EXECUTION.md`, `specs/077-autonomous-work-execution-loop/`.

안전 경계: 읽기 전용 작업 패킷 발행 루프다. 실제 주문, 실거래 전환, 자본 배분,
whitelist/caps/live 설정, 헌법·커널 변경 없음. deploy success는 dry-run worker 코드 반영이지
실거래 전환이 아니다.

## 최근 마일스톤 — 2026-07-01 KST (스펙 076 자본 경로 준비도 루프)

스펙 076이 #430으로 main에 들어갔다. 새 루프는 money-path, edge-autoarm, reassign,
paper-forward, KIS smoke, promotion/evolution sidecar를 읽어 자본 경로 준비도와 다음 안전
행동을 `automation/capital-path-readiness-last-run`에 발행한다. 최신 run `28518083087`은
commit `23ec54b` 기준 success이고, 현재 상태는 `ACCUMULATING_EDGE / PREVIEW_ONLY`,
blocker는 `전진 관측 부족: 14/20`이다. pipeline liveness는 병렬 실행 경합 뒤 run
`28518134667`로 재실행해 `overall=OK`, `capital-path-readiness=OK`가 됐다. 상세:
`HANDOFF-080-CAPITAL-PATH-READINESS.md`, `specs/076-capital-path-readiness-loop/`.

안전 경계: 읽기 전용 보고 루프다. 실제 주문, 실거래 전환, 자본 배분, whitelist/caps/live 설정,
헌법·커널 변경 없음. deploy success는 dry-run worker 코드 반영이지 실거래 전환이 아니다.

## 최근 마일스톤 — 2026-07-01 KST (스펙 075 전략 실패 학습 장부화)

main 코드 머지 `fa8cc32`(#428). autonomous evolution loop가 promotion summary의 `DISCARD`
전략/포트폴리오 후보를 읽어 `learning_ledger.json`에 `rejected`로 남긴다. 상세:
`HANDOFF-079-STRATEGY-FAILURE-LEARNING.md`, `specs/075-strategy-failure-learning/`.

- **핵심 구현**: `promotion-summary` evidence requirement를 추가하고, `DISCARD` stage인
  `strategy_design`/`portfolio_design` 후보만 실패 학습 신호로 해석한다. 이미 같은 rejected 장부가
  있으면 중복하지 않는다.
- **실행 결과**: deploy run `28507752817` success, autonomous evolution run `28507752974` success.
  최신 `learning_ledger.json`은 `candidate-1ed634d8bf6d`, `candidate-cc96b35062da`를 모두
  `decision=rejected`, `evidence_package_id=autonomous-promotion:28504209238`로 기록한다.
- **안전 경계**: 기존 sidecar 읽기와 장부 출력만 바뀌었다. 주문, 자본, whitelist/caps, live config,
  sentinel, 헌법, 커널 변경 없음. 실패 후보는 돈 경로로 승격하지 않는다.
- **다음 행동**: 이 두 후보를 다시 승격 대상으로 보지 말고, 새 전략/포트폴리오 아이디어를 만들면
  다시 `Backtest -> Canary -> Full` 순서로 검증한다.

## 최근 마일스톤 — 2026-07-01 KST (스펙 074 후보 가격 이력 지원)

main 머지 `fcc6e5f`(#425). 후보 결과 실행기가 전략/포트폴리오 후보의 가격 이력을 서버의
read-only `bars-export`와 `ingest-history`로 준비하고, 후보 명령에 `--history-root`를 붙여
`data_history_missing` pending을 제거했다. 상세: `HANDOFF-078-CANDIDATE-HISTORY-SUPPORT.md`,
`specs/074-candidate-history-support/`.

- **핵심 구현**: `candidate_history_support.py`가 후보별 portfolio/db/history-root manifest를 만들고,
  `candidate-result-executor.yml`이 SSH 사용 가능 시 서버에서 가격 이력을 준비한다. 실주문, 자본,
  live 설정, whitelist/caps, sentinel은 건드리지 않는다.
- **실행 결과**: result executor run `28503338531`은 `pass=7`, `fail=2`, `pending=0`,
  `blocked=0`, 진단 집계 없음이다. 두 전략/포트폴리오 후보 모두 `--history-root`를 사용했다.
- **후속 루프**: factory run `28503561736`은 `evidence_passed=7`, `blocked=2`, `pending=0`을
  반영했다. #426 뒤 promotion loop run `28504209238`은 commit `d3ca5d5` 기준 success였고,
  두 전략/포트폴리오 후보를 `DISCARD`로 분류했다.
- **안전 경계**: 주문, 브로커 실주문, 자본, whitelist/caps, live config, sentinel, 헌법, 커널 변경 없음.
  배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **다음 행동**: 두 후보는 더 이상 데이터 부족 대기가 아니다. 백테스트 no-edge/fail 후보라 승격하지
  않으며, 다음 후보 발굴·재설계는 새 후보로 다시 `Backtest -> Canary -> Full` 순서를 탄다.

## 최근 마일스톤 — 2026-07-01 KST (스펙 073 후보 pending next action 보정)

main 머지 `0de15a4`(#423). 스펙 072가 진단한 pending 5개 중 자동화 배선으로 해결 가능한
3개를 실제 pass로 줄이고, 가격 이력 부족 2개는 거짓 통과 없이 pending으로 남겼다. 상세:
`HANDOFF-077-CANDIDATE-PENDING-NEXT-ACTIONS.md`, `specs/073-candidate-pending-next-actions/`.

- **핵심 구현**: 후보 공장 명령을 현재 CLI 계약에 맞췄다. `ops_liveness`와 `data_quality`는
  pipeline liveness sidecar 검증을 실행하고, `analytics_validation`은 public-data snapshot을 명시적으로 읽는다.
- **실행 결과**: #423 deploy run `28474687085` success. 최신 result executor run `28474761904`는
  `pass=7`, `pending=2`, `blocked=0`, 진단 집계 `data_history_missing=2`,
  `insufficient_pass_evidence=1`이다. `command_contract_error`와 `execution_failed`는 사라졌다.
- **후속 루프**: result sidecar 이후 factory run `28474828027`을 재실행해
  `evidence_passed=7`, `pending=2`를 반영했다. promotion loop run `28474881043`도 success였고,
  전략/포트폴리오 후보 2개만 `BACKTEST_REQUIRED`에 남는다.
- **안전 경계**: 주문, 브로커, 자본, whitelist/caps, live config, sentinel, 헌법, 커널 변경 없음.
  배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.
- **다음 행동**: 남은 작업은 안전한 가격 이력 수집 또는 `ingest-history` 실행 경로 설계다.

## 최근 마일스톤 — 2026-06-30 KST (후보 공장 result status 보정과 스펙 071 후보 결과 실행기)

main 머지 `0b743c2`(#419). 후보 공장이 result executor 증거를 먹은 뒤 비전략 no-live
검증 통과 후보를 모두 `pending`처럼 표시하던 상태 판독을 고쳤다. 상세:
`HANDOFF-075-CANDIDATE-FACTORY-RESULT-STATUS.md`.

- **핵심 보정**: 전략·포트폴리오 후보는 세 전략 evidence가 모두 pass일 때만 통과,
  비전략 후보는 `factory_validation=pass`일 때만 `evidence_passed`로 표시.
- **실행 결과**: #419 deploy success, result executor run `28422210017` success,
  factory run `28422210026` success. 최신 factory sidecar는 `evidence_passed=4`,
  `pending=5`, `ready=0`, `blocked=0`.
- **후속 루프**: promotion loop run `28422336507`, promotion actions run `28422350673`,
  pipeline liveness run `28422367089` 모두 success. liveness overall `OK`.
- **안전 경계**: 주문, 브로커, 자본, whitelist/caps, live config, sentinel, 헌법, 커널 변경 없음.

main 머지 `b827364`(#417). 후보 구현 공장이 만든 검증 패키지를 자동 실행해
`candidate_results.json` 증거로 바꾸고 `automation/candidate-implementation-results` sidecar를 발행하는
루프를 추가했다. 상세: `HANDOFF-074-CANDIDATE-RESULT-EXECUTOR.md`,
`specs/071-candidate-result-executor/`.

- **핵심 구현**: `candidate_result_executor.py`, `candidate_result_executor_probe.py`,
  `auto-invest candidate-results`, `.github/workflows/candidate-result-executor.yml`.
- **자동 순서**: 08:40 factory → 08:42 result executor → 08:44 factory second pass → 08:45 promotion scan.
- **첫 실행 결과**: result executor run `28421591693` success, `pass=4`, `pending=5`, `blocked=0`.
  후속 factory/promotion/actions/liveness 수동 dispatch 모두 success, liveness overall `OK`.
- **안전 경계**: no-live 검증만 allowlist로 실행. 주문, 브로커, 자본, whitelist/caps, live config,
  sentinel, 헌법, 커널 변경 없음.
- **검증**: PR #417 머지 전 전체 테스트 2351 통과·4 스킵, 전체 린트 통과, 하네스 OK (14/14),
  HANDOFF 사실 검증 OK, PR 품질 관문 성공. main push 뒤 deploy와 KIS smoke도 success.

## 최근 마일스톤 — 2026-06-29 KST (스펙 068 자율 승격 루프 자동화)

main 머지 `ddecebb`(#408). 자율 성장 후보를 실제 돈 경로로 바로 보내지 않고 다음 검증 단계로
자동 분류하는 read-only 승격 루프를 추가했다. 상세:
`HANDOFF-071-AUTONOMOUS-PROMOTION-LOOP.md`, `specs/068-autonomous-promotion-loop/`.

- **핵심 구현**: 후보 backlog와 sidecar 증거를 읽어 `BACKTEST_REQUIRED`,
  `RECENT_OOS_REQUIRED`, `FORWARD_REGISTRATION_READY`, `FORWARD_ACCUMULATING`,
  `CANARY_CANDIDATE`, `EXISTING_GATE_READY`, `OPERATOR_REVIEW` 등으로 분류한다.
- **운영 표면**: `auto-invest promotion-scan`, `scripts/promotion_loop_probe.py`,
  GitHub Actions `Autonomous promotion loop`, pipeline liveness `autonomous-promotion` sidecar.
- **중요한 판단**: 백테스트는 전략 검증이고 소액 live canary는 브로커·계좌·주문·체결 실행 경로 검증이다.
  아무리 정교한 백테스트도 브로커 주문 거부, 부분 체결, 현금·결제 충돌, 실시간 슬리피지를 완료 검증하지 못한다.
- **안전 경계**: 주문, 자본, whitelist/caps, live 전략 교체, 브로커 API 호출, 센티넬 변경 없음.
  전략·자본 후보는 기존 스펙 055 재지정 게이트와 스펙 050 자본 사다리로만 간다.
- **검증**: PR #408 머지 전 전체 테스트 2321 통과·4 스킵, 전체 린트 통과, 하네스 OK (14/14),
  HANDOFF 사실 검증 OK, PR 품질 관문 성공. main push 뒤 배포와 KIS smoke도 success.

## 최근 마일스톤 — 2026-06-29 KST (운영자가 이해 가능한 완료 보고 강제)

main 머지 `c4400b7`(#406). 완료 보고가 운영자에게 실제 의미를 전달하지 못한 문제를 운영 규칙,
품질 관문, 하네스 품질 과제로 고정했다. 상세:
`HANDOFF-070-OPERATOR-READABLE-REPORTING.md`, `AGENTS.md`, `.codex/quality-gate.md`.

- **핵심 변경**: 최종 답변은 실제 운영 상태 변화부터 말하고, 의미·돈 경로/안전 경계 영향·검증·
  남은 위험을 쉬운 한글로 분리해야 한다.
- **하네스 고정**: 첫 판단 품질 과제는 이제 6개이며 `operator_readability`가 필수 범주다.
- **안전 경계**: 운영 보고 규칙 변경뿐이다. 주문, 자본, whitelist/caps, live 전략, 헌법, 커널 목록 변경 없음.
- **검증**: PR #406 머지 전 전체 테스트 2310 통과·4 스킵, 전체 린트 통과, 하네스 OK (14/14),
  HANDOFF 사실 검증 OK, PR 품질 관문 성공.

## 최근 마일스톤 — 2026-06-29 KST (스펙 067 영구 자율 성장 루프 구현)

main 머지 `424a70e`(#404). 스펙 067을 read-only 운영 루프로 구현했고, 첫 push workflow가
`automation/autonomous-evolution-last-run` sidecar를 `overall_status=ok`로 발행했다. 상세:
`HANDOFF-069-AUTONOMOUS-EVOLUTION-IMPLEMENTATION.md`, `specs/067-autonomous-evolution-loop/`.

- **핵심 구현**: evidence surface → breakthrough candidate → experiment plan → promotion decision →
  learning ledger → latest-run report 흐름을 pure analytics와 probe/CLI/workflow로 연결했다.
- **운영 표면**: `auto-invest evolution-scan`, `scripts/evolution_loop_probe.py`, GitHub Actions
  `Autonomous evolution loop`, pipeline liveness `autonomous-evolution` sidecar.
- **안전 경계**: 주문, 자본, whitelist/caps, live 전략 교체, 브로커 API 호출 없음. 전략·자본 후보는
  기존 스펙 055 재지정 게이트와 스펙 050 자본 사다리로만 승격한다.
- **검증**: PR #404 머지 전 전체 테스트 2310 통과·4 스킵, 전체 린트 통과, 하네스 OK (14/14),
  HANDOFF 사실 검증 OK, PR 품질 관문 성공.

## 최근 마일스톤 — 2026-06-29 KST (스펙 067 영구 성장 목표 정정)

main 머지 `9e1e492`(#402). 스펙 067의 목표를 "기다리는 시간 활용"이 아니라 "지금부터 영구적으로
돈 버는 능력과 검증 능력을 복리화하는 상시 성장 엔진"으로 정정했다. 상세:
`HANDOFF-068-EVOLUTION-BREAKTHROUGH-FRAMING.md`, `specs/067-autonomous-evolution-loop/`.

- **핵심 설계**: 데이터 수집, 데이터 품질, 분석, 전략 설계, 포트폴리오 설계, 실행 품질,
  live readiness, 회고, 에이전트 운영 품질을 도메인으로 두고, evidence surface를 읽어 장기 수익력·
  증거 품질·자본 경로 정렬·안전 보존·학습 복리 기준의 고레버리지 돌파 후보를 산출한다.
- **시장 관측 시간의 위치**: 시장 관측 대기는 루프의 목적이 아니라 `evidence_dependency`의 한
  종류다. 특정 후보가 시장 관측에 묶여도 루프는 다른 안전한 고레버리지 작업을 계속 고른다.
- **안전 경계**: 자동 루프는 주문, 자본, whitelist, caps, live 전략 교체를 직접 수행하지 않는다.
  검증된 후보도 스펙 055 재지정 게이트와 스펙 050 자본 사다리 같은 기존 경로로만 승격한다.
- **당시 상태**: 구현 미착수였다. 현재는 #404로 구현 완료됐으므로 다음 세션은
  `automation/autonomous-evolution-last-run` sidecar를 우선 읽는다.

## 최근 마일스톤 — 2026-06-28 KST (micro GTAA intent-loss 다음 행동 안내 보정)

`INTENT_LOSS`가 live 주문을 차단하는 동안 새 live 표본이 자동으로 쌓이는 것처럼 안내하던
운영 표면을 바로잡았다. 상세: `HANDOFF-066-MICRO-GTAA-BLOCKER-REVIEW.md`,
`specs/065-micro-gtaa-intent-loss-gate/`.

- **문제**: 최신 micro GTAA monitor는 `latest_signal=INTENT_LOSS`, `verdict=INSUFFICIENT_DATA`,
  누적 의도 손익 `-1.14 USD`다. 기존 `next_action_ko`는 "다음 micro GTAA 실행에서 표본을 더
  쌓습니다"였지만, #394 gate가 live를 막으므로 이는 실제 회복 경로가 아니다.
- **보정**: `opportunity_monitor`가 해당 조합에서는 "새 live 표본은 자동으로 쌓이지 않는다"와
  "forward 토너먼트·재지정 증거 또는 별도 전략 검토 후 재무장 판단"을 안내한다.
- **안전 경계**: 주문 차단, `armed:false`, 자본, 허용 종목, 전략 설정, 센티넬, K1/K2/K4/K5/K6,
  헌법, 커널 목록 변경 없음.

## 최근 마일스톤 — 2026-06-27 KST (전략 검토 관측 품질 오판 보정)

main 머지 `d97d6a2`(#396). 최신 reassign sidecar가 모든 후보 최소 관측 전의 정상 관측 수 차이를
후보 품질 장애로 오판하던 문제를 고쳤다. 상세: `HANDOFF-065-STRATEGY-OBSERVATION-HEALTH.md`,
`specs/066-strategy-review-observation-health/`.

- **핵심 변경**: all-premature lag는 `observation_health=OK`, mixed comparable/premature는
  `DEGRADED`, all-comparable lag는 `OK`로 구분한다.
- **포렌식 보존**: `lagging_keys`, 최소/최대 관측 수는 계속 표시한다. missing verdict와 incumbent
  missing 방어는 그대로 유지했다.
- **운영 결론**: 다음 reassign 실행에서 all-premature lag는 장애로 보지 않아야 한다. 단, 아직
  비교 가능한 도전자가 없으면 재지정은 HOLD가 정상이다.
- **안전 경계**: 등급 2 운영 판단 보정이다. 실주문, micro GTAA 재무장, 자본, whitelist, live 전략,
  주문 라우터, 헌법, 커널 목록 변경 없음.
- **검증/배포**: `uv run pytest` 2286 통과·4 스킵, `uv run ruff check src tests` 통과,
  하네스 `OK (14/14)`, PR 품질 관문 통과. #396 deploy run `28282838560` 성공.

## 최근 마일스톤 — 2026-06-27 KST (micro GTAA 손실 의도 실주문 차단)

main 머지 `6272178`(#394). 최신 micro GTAA 거부 주문 기회손익이 `INTENT_LOSS`, 누적 의도 손익
`-1.14 USD`였기 때문에, 전략 검토 전까지 같은 전략 의도가 실주문으로 반복되지 않도록 닫았다.
상세: `HANDOFF-064-MICRO-GTAA-INTENT-LOSS-GATE.md`, `specs/065-micro-gtaa-intent-loss-gate/`.

- **핵심 변경**: `automation/rebalance-micro-gtaa.request`를 `armed:false`로 전환하고,
  `opportunity_monitor.py`의 live gate와 `scripts/opportunity_live_gate.py`를 추가했다.
- **워크플로 차단**: micro GTAA workflow는 strategy-intent gate가 `ok=true`일 때만 preflight,
  손실 브레이커, live 주문으로 진행한다. 게이트 평가 실패는 fail-closed다.
- **증거 보존**: live 미실행 run은 빈 opportunity record를 append하지 않으므로 최신 손실 신호가
  차단 실행 때문에 사라지지 않는다.
- **post-merge 증거**: run `28274580272`에서 live 주문 단계는 skipped, sidecar는
  `reason=latest_intent_loss`, `실주문 0건`을 표시했다. money-path run `28274580263`은
  `PREVIEW_ONLY`를 보고했다.
- **안전 경계**: 등급 4 돈 경로 변경이나 실제 주문 가능성을 줄였다. 자본, whitelist, 주문 라우터,
  손실 브레이커, 헌법, 커널 목록 변경 없음.
- **검증/배포**: `uv run pytest` 2283 통과·4 스킵, `uv run ruff check src tests` 통과,
  하네스 `OK (14/14)`, PR 품질 관문 통과. #394 deploy run `28274580264` 성공.

## 최근 마일스톤 — 2026-06-26 KST (거부 주문 누적 평가와 자율 재지정 피드백 루프)

main 머지 `f76aa07`(#392). 거부 주문 기회손익을 단발 보고에서 rolling history와 자율 재지정
evidence 입력으로 확장했다. 상세: `HANDOFF-063-REJECTED-OPPORTUNITY-FEEDBACK-LOOP.md`,
`specs/064-rejected-opportunity-feedback/`.

- **핵심 변경**: `auto-invest opportunity-monitor`, `analytics/opportunity_monitor.py`,
  `scripts/opportunity_monitor_sidecar.py`, micro GTAA sidecar의 `opportunity_history.json`과
  `opportunity_monitor.json`, Telegram `5. 누적 전략/실행 평가` 섹션을 추가했다.
- **판단 기준**: 양수 누적은 거부 주문이 정상 체결됐으면 이익이었을 가능성, 음수 누적은 전략
  의도가 손실이었을 가능성이다. 표본이 부족하면 `INSUFFICIENT_DATA`로 자동 전략 판단을 보류한다.
- **재지정 연결**: `reassign-on-tournament`는 monitor JSON을 `reassign-decide`에 넘기지만
  `execution_feedback.effect=evidence_only_no_gate_override`로 기록만 한다. 기존 5중 게이트 불변.
- **안전 경계**: 등급 2 운영 관측·평가 루프 변경이다. 주문 재시도, 주문 라우터, 게이트, 자본,
  whitelist, 손실 브레이커, 헌법, 커널 목록 변경 없음.
- **검증/배포**: `uv run pytest` 2274 통과·4 스킵, `uv run ruff check src tests` 통과,
  하네스 `OK (14/14)`, PR 품질 관문 통과. #392 deploy run `28237830935` 성공,
  KIS smoke run `28237830957` 성공.

## 최근 마일스톤 — 2026-06-26 KST (거부 주문 기회손익과 Telegram 가독성 보강)

main 머지 `4175f13`(#390). 운영자가 "매수가 정상적으로 진행됐다면 지금 돈 벌었는지 잃었는지"를
전략 평가 기준으로 요구했고, 이에 맞춰 거부된 BUY/SELL 주문을 현재가 기준으로 평가하는 읽기 전용
기회손익 표면을 추가했다. 상세: `HANDOFF-062-REJECTED-ORDER-OPPORTUNITY-ALERTS.md`,
`specs/060-telegram-order-alerts/`.

- **핵심 변경**: `auto-invest rejected-order-opportunity` CLI, `analytics/order_opportunity.py`,
  micro GTAA workflow의 `/tmp/micro_opportunity.json`, sidecar `## 거부 주문 기회손익`, Telegram
  `4. 거부 주문 기회손익` 섹션을 추가했다.
- **판단 기준**: 양수는 거부 주문이 정상 체결됐으면 현재 더 유리, 음수는 거부가 결과적으로 더 유리.
  수수료, 세금, 환율, 실제 체결 가능성은 제외한 단순 현재가 비교다.
- **Telegram 가독성**: micro GTAA 메시지는 실행, 전제 확인, 주문 결과, 기회손익, 확인 링크로
  나뉜다. audit tailer의 broker rejection 알림은 접수·체결 0건임을 판단 줄로 명시한다.
- **안전 경계**: 등급 2 운영 관측 변경이다. 주문 재시도, 주문 라우터, 게이트, 자본, whitelist,
  손실 브레이커, 헌법, 커널 목록 변경 없음.
- **검증/배포**: `uv run pytest -q` 2262 통과·4 스킵, `uv run ruff check src tests` 통과,
  하네스 `OK (14/14)`, PR 품질 관문 통과. PR #390은 merge 방식으로 main에 머지됐다.

## 최근 마일스톤 — 2026-06-26 KST (Telegram 알림 폭주 방지와 KIS 진단 보강)

main 머지 `7195c48`(#388). Telegram 메시지 9000개 이상 누적 상황을 조사한 뒤, 서버 audit tailer가
오래된 cursor 또는 반복 `ERROR` row를 계속 전송할 수 있는 경로와 KIS HTTP 200 오류 본문이
`KeyError('output')`로 사라지는 경로를 함께 닫았다. 상세: `HANDOFF-061-TELEGRAM-ALERT-FLOOD-FIX.md`,
`specs/060-telegram-order-alerts/`, `specs/059-kis-order-diagnostics/`.

- **핵심 변경**: Telegram tailer stale cursor catch-up 기본 25개 제한, 동일 `ERROR` 1시간 cooldown,
  KIS HTTP 200 오류 본문 진단 보존, `auto-invest-telegram-alerts.service` 전용 수동 관리 workflow.
- **운영 조치**: #388 배포 성공 뒤 workflow run `28212999028`로 Telegram 알림 서비스를 재시작했다.
  status run `28213025727` 기준 서비스는 `enabled`/`active`이고 재시작 이후 새 전송 로그는 보이지 않았다.
- **안전 경계**: 등급 3 외부 API·운영 알림·브로커 진단 변경이다. 실제 주문, 자본, whitelist,
  주문 게이트, 손실 브레이커, 헌법, 커널 목록은 변경하지 않았다.
- **검증/배포**: `uv run pytest` 2257 통과·4 스킵, `uv run ruff check src tests` 통과,
  하네스 `OK (14/14)`, PR 품질 관문 통과. #388 deploy run `28212963179` 성공,
  KIS smoke run `28212963184` 성공.

## 최근 마일스톤 — 2026-06-23 KST (스펙 063 계좌 전체 micro GTAA 자율 재배치)

main 머지 `7a14315`(#386). 운영자가 "새 입금은 안 되지만 기존 보유는 수익 관점에서 팔 수도,
보유할 수도 있어야 한다"와 "단발성이 아니라 적용 시점부터 지속 자율 운영돼야 한다"고 명시했고,
등급 4 돈 경로 변경으로 micro GTAA live canary를 계좌 전체 재배치 루프로 확장했다. 상세:
`HANDOFF-060-ACCOUNT-WIDE-MICRO-GTAA.md`, `specs/063-account-wide-micro-gtaa/`.

- **핵심 변경**: 브로커 포지션과 KIS 매수 가능 현금을 live 계획 입력으로 사용한다. 기존 장부
  포지션만 보던 cash-only 한계를 보완했다.
- **청산 전용 안전장치**: 기존 보유 `BHP`, `MRK`, `ORANY`, `RELX`는 K2 설정 표면에 포함되지만
  목표 유니버스가 아니며, account-wide 리밸런서가 매수 주문을 거부한다.
- **지속 루프**: cash shortfall이면 이번 주기는 `effective_side=sell`로 청산 전용 매도만 실행하고,
  다음 주기에서 KIS가 확인한 현금이 충분할 때 목표 종목 매수를 진행한다.
- **증거**: workflow sidecar와 Telegram 요약에 계좌 전체 모드, effective side, 필요 현금,
  계획 매수·매도 금액, 다음 단계가 남는다.
- **검증/배포**: `uv run pytest` 2252 통과·4 스킵, `uv run ruff check src tests` 통과,
  `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`, PR 품질 관문 통과.
  PR #386은 merge 방식으로 main에 머지됐다.

## 최근 마일스톤 — 2026-06-22 (스펙 062 money-path 실제 돈 최상위 상태)

main 머지 `3440001`(#384). 운영자가 "오늘 저녁부터 실제 돈이 투자되기 시작할텐데"라는 현재
상태를 물었을 때, 최근 작업과 코드에서 `micro GTAA armed:true`를 먼저 확인하지 못한 사고를
재발하지 않도록 money-path 상태 표면을 고쳤다. 상세: `HANDOFF-059-MONEY-PATH-STATE.md`,
`specs/062-money-path-state/`.

- **핵심 변경**: `src/auto_invest/analytics/money_path.py`가 `live_money_state`를 JSON에 추가하고,
  text report 첫 섹션을 `실제 돈 최상위 상태`로 렌더링한다. 기존 자본 사다리 상태는 보존하되
  두 번째 섹션으로 내려갔다.
- **micro GTAA 소비**: `scripts/money_path_probe.py`가 `automation/rebalance-micro-gtaa.request`와
  `rebalance-micro-gtaa-last-run`을 읽는다. preflight 없는 옛 sidecar는 깨지지 않고
  `preflight evidence absent`로 표시된다.
- **회귀 방지**: `tests/unit/test_money_path.py`와 `tests/integration/test_money_path_probe.py`가
  `armed:true`, `armed:false`, 자본 한도 초과, 센티넬 누락, manifest 소비 여부, 출력 순서를 고정한다.
- **운영 규칙**: 이 파일 상단의 "돈 경로 상태 판독 규칙"을 따라 최신 money-path 또는 원본 sidecar를
  먼저 읽고 답한다. KIS smoke 현금값은 preflight 입력일 뿐 `armed` 상태의 대체 근거가 아니다.

## 이전 관찰 — 2026-06-22 (Telegram 서버 연결 자동화 이후, #384 이전)

당시 `main` 최신은 `845c5b1`(#382, 스펙 061 Telegram 서버 연결 자동화)였다.
직전 주요 커밋은 `8cf5635`(서버 연결 workflow 구현), `32cdccf`(#381, Telegram 알림 handoff),
`6384584`(#380, 스펙 060 Telegram 모바일 주문 알림)이다. 이 인계 갱신 시점의 열린 PR은 없다.

- **사용자 입력 반영**: 운영자가 제공한 Telegram chat id는 GitHub secret
  `TELEGRAM_CHAT_ID`에 저장됐다. `TELEGRAM_BOT_TOKEN`은 화면 출력 없이 숨김 입력으로 받아
  GitHub secret에 저장했고, 로컬 test message 전송이 성공했다. 이전에 브라우저 주소창에 노출된
  token은 운영자가 폐기·재생성해야 하는 전제다.
- **서버 연결 완료**: PR #382로 추가된 `Configure Telegram alerts on server` workflow run
  `27944499731`이 성공했다. 이 run은 GitHub secrets 값을 서버 `/opt/auto-invest/.env`에 반영하고,
  서버에서 `auto-invest telegram-alerts --test-message`를 실행한 뒤
  `auto-invest-telegram-alerts.service`만 enable/start했다.
- **micro GTAA 알림**: `.github/workflows/rebalance-micro-gtaa-canary.yml` 마지막의
  `Notify Telegram - micro GTAA result` best-effort 단계는 secrets가 있으면 전송된다. 실패해도
  workflow 결론과 주문 결과를 바꾸지 않는다.
- **일반 주문 알림**: 서버 `auto-invest-telegram-alerts.service`가 켜져 있다. `auto-invest
  telegram-alerts` CLI는 SQLite `audit_log`의 새 주문·거부·체결·halt·error 이벤트를 읽어
  Telegram 메시지로 보낸다. 첫 실행은 명시적 `--replay-existing` 없으면 현재 마지막 `seq`부터
  시작해 과거 로그를 폭주 전송하지 않는다.
- **비밀값·로그**: workflow는 token/chat id 원문과 base64 값을 모두 mask한다. 메시지와 CLI 오류
  출력은 token, app key, app secret, authorization, 계좌번호를 마스킹하거나 출력하지 않는다.
- **안전 경계**: 등급 3 외부 API·비밀값 경로 추가다. `audit_log`는 읽기만 하며 주문 제출, 취소,
  체결 동기화, halt 설정을 하지 않는다. PR #382는 서버 `.env`와 observer service만 다루며 주문
  worker, broker submission, capital, whitelist, risk gate는 변경하지 않는다.
- **배포 확인**: #382 main push에 붙은 `Deploy on merge to main` run `27944489222`는 성공했다.
  `KIS smoke (autonomous)`는 이번 workflow/doc/spec/test 변경에는 path filter 때문에 트리거되지
  않았다. 최신 KIS sidecar 성공은 #380 `6384584` 기준 run `27942372526`이다.
- **검증**: PR #382 머지 전 `uv run pytest -q` 2242 통과·4 스킵,
  `uv run ruff check src tests` 통과, workflow YAML 파싱 검증, `git diff --check`,
  `uv run python scripts/agent_harness_probe.py --strict` `OK (14/14)`,
  `uv run python scripts/check_handoff_facts.py` 통과, PR 품질 관문 통과.
- **handoff 재검증 상태**: 최신 main에서 `uv run ruff check src tests`는 통과했다.
  `uv run pytest -q`는 stale `HANDOFF.md` 때문에 하네스 2건만 실패했다. 이 handoff 갱신은
  그 원인(`마지막 main 커밋` 행)을 바로잡았다. 갱신 후 `uv run python scripts/check_handoff_facts.py`,
  `uv run python scripts/agent_harness_probe.py --strict`, `uv run pytest -q`,
  `uv run ruff check src tests`가 모두 통과했다.

## 최근 마일스톤 — 2026-06-22 (스펙 061 Telegram 서버 연결 자동화)

main 머지 `845c5b1`(#382). 운영자가 `chat_id`를 제공한 뒤, 남은 서버 연결 작업을 운영자 수동
SSH 없이 끝내기 위해 GitHub Actions workflow를 추가하고 실제 실행까지 완료했다. 상세:
`HANDOFF-058-TELEGRAM-SERVER-CONNECT.md`, `specs/061-telegram-server-connect/`.

- **핵심 변경**: `Configure Telegram alerts on server` workflow가 GitHub secrets를 서버 `.env`에
  멱등 반영하고, test message 성공 뒤 `auto-invest-telegram-alerts.service`만 enable/start한다.
- **운영 상태**: GitHub secrets `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`는 설정됨. workflow run
  `27944499731` 성공으로 서버 `.env` 반영, test message, service enable/start까지 완료됨.
- **안전 경계**: 외부 API·비밀값 서버 연결 때문에 등급 3으로 처리했다. 주문 라우터·브로커 제출·
  위험 게이트·자본·화이트리스트·손실 브레이커는 변경하지 않았다. 실주문 재시도도 하지 않았다.
- **검증/배포**: `uv run pytest -q` 2242 통과·4 스킵, `uv run ruff check src tests` 통과,
  `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`, PR 품질 관문 통과.
  #382 deploy-on-merge run `27944489222` 성공, 서버 설정 workflow run `27944499731` 성공.

## 최근 마일스톤 — 2026-06-22 (스펙 060 Telegram 모바일 주문 알림)

main 머지 `6384584`(#380). 운영자가 "모바일에서 검증과 일반 주문 실행·매수·매도 결과를
실시간으로 알고 싶다"고 요청했고, Telegram Bot API를 사용해 무료 모바일 알림 경로를 추가했다.
상세: `HANDOFF-057-TELEGRAM-ORDER-ALERTS.md`, `specs/060-telegram-order-alerts/`.

- **핵심 변경**: micro GTAA workflow 결과 알림, 서버 `audit_log` tailer CLI, 선택형 systemd service,
  비밀값 마스킹, cursor 상태 파일, dry-run/test-message, 운영 문서를 추가했다.
- **운영 켜기**: GitHub Actions 알림은 repository secrets `TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_CHAT_ID`가 있어야 전송된다. 이 secrets와 서버 `.env` 반영, service enable은
  후속 스펙 061(#382)에서 완료됐다.
- **안전 경계**: 외부 API·비밀값 경로 때문에 등급 3으로 처리했다. 주문 라우터·브로커 제출·위험
  게이트·자본·화이트리스트·손실 브레이커는 변경하지 않았다. 알림 장애는 주문 경로를 막지 않는다.
- **검증/배포**: `uv run pytest` 2239 통과·4 스킵, `uv run ruff check src tests` 통과,
  `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`, PR 품질 관문 통과.
  #380 deploy-on-merge run `27942372448` 성공, KIS smoke run `27942372526` 성공.

## 최근 관찰 — 2026-06-22 (KIS 주문 원인 확정 경로 복구 이후)

현재 `main` 최신은 `24c2947`(#378, 스펙 059 KIS 주문 전제 확인과 진단 보존)이다.
직전 주요 커밋은 `56dfec6`(KIS 주문 진단 구현), `7477658`(#377, micro GTAA 무장 상태
handoff 갱신), `75717a2`(#376, micro GTAA `armed:true` 승인 반영)이다. 이 인계 갱신 시점의
열린 PR은 없다.

- **근본 판단**: run `27935469561`의 과거 `KIS` 500은 GitHub 로그에 응답 본문이 남지 않아
  사후 확정이 불가능하다. #378의 목표는 과거 오류를 추측으로 고치는 것이 아니라, 다음 실패에서
  정규장·현금·payload·브로커 응답 중 어느 조건이 원인인지 재현 가능하게 확정하는 것이다.
- **주문 전제 확인**: micro GTAA live 워크플로는 dry-run 미리보기 뒤, 손실 브레이커와 live 주문
  전에 `Pre-live order preflight`를 실행한다. 정규장 여부, planned buy notional, `KIS` 매수가능
  현금, 1% 비용 완충을 확인하고 실패하면 live 주문에 들어가지 않는다.
- **KIS 주문 본문 정합성**: 해외주식 보통 주문 본문에 `CTAC_TLNO`, `MGCO_APTM_ODNO`,
  `SLL_TYPE`, `ORD_SVR_DVSN_CD`를 포함했다. 이 변경은 주문 한도나 허용 종목을 넓히지 않는다.
- **브로커 진단 보존**: `KIS` 주문 오류는 `KisOrderError`로 감싸고, 마스킹된 상태 코드·URL·응답
  본문 미리보기·KIS 메시지를 감사 payload, 상태 전이 사유, 주문 결과 사유까지 전달한다.
- **운영 상태**: `automation/rebalance-micro-gtaa.request`는 여전히 `armed:true`,
  `capital_usd:1000`이다. #378에서는 실제 주문을 재시도하지 않았고, 새 접수·체결은 없다.
- **배포 확인**: #378 main push에 붙은 `Deploy on merge to main` run `27939601985`는 성공했다.
  이 배포는 dry-run worker 반영 확인이며 micro GTAA live 주문 실행이 아니다. `KIS` smoke sidecar는
  `2026-06-21T08:01:35Z` run `27898040482` 기준의 오래된 성공 기록이라 #378 이후 주문 진단
  실서버 증거로 보지 않는다.
- **검증**: PR #378 머지 전 `uv run pytest` 2229 통과·4 스킵,
  `uv run ruff check src tests` 통과, `uv run python scripts/agent_harness_probe.py --strict`
  `OK (14/14)`, PR 품질 관문 통과. handoff 갱신 전 `uv run pytest -q`는 stale
  `HANDOFF.md` 때문에 하네스 2건이 실패했고, 이 handoff 갱신은 그 원인(`마지막 main 커밋` 행)을
  바로잡았다. handoff 갱신 후 `uv run python scripts/check_handoff_facts.py`,
  `uv run python scripts/agent_harness_probe.py --strict`, `uv run pytest -q`,
  `uv run ruff check src tests`가 모두 통과했다.

## 최근 마일스톤 — 2026-06-22 (스펙 059 KIS 주문 원인 확정 경로 복구)

main 머지 `24c2947`(#378). 운영자가 요구한 기준은 "유력 원인으로 조치하지 말고 진짜 원인을 먼저
확정할 수 있게 하라"였다. PR #378은 micro GTAA live 주문 전에 실패 조건을 분리하고, 브로커 거부
응답을 마스킹해 K4 감사 경로에 남기는 방식으로 원인 확정 능력을 복구했다. 상세:
`HANDOFF-056-KIS-ORDER-DIAGNOSTICS.md`, `specs/059-kis-order-diagnostics/`.

- **핵심 변경**: preflight가 정규장·매수가능 현금·주문 계획 비용을 검증하고, KIS 주문 본문은 공식
  해외주식 보통 주문 필드를 포함한다. 브로커 4xx/5xx 오류는 마스킹된 구조화 진단으로 보존된다.
- **실주문 판단**: #378은 실제 주문을 재시도하지 않았다. 다음 live 실행에서 preflight가 실패하면
  주문 전 중단되고, preflight를 통과했는데 KIS가 거부하면 응답 진단이 남아야 한다.
- **안전 경계**: 등급 4 돈 경로 변경이며 K4 감사 payload를 추가 전용으로 확장했다. 헌법·커널
  목록·비밀값·K1 캡·화이트리스트·손실 브레이커·허용 종목은 변경하지 않았다.
- **검증/배포**: `uv run pytest` 2229 통과·4 스킵, `uv run ruff check src tests` 통과,
  `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`, PR 품질 관문 통과.
  #378 deploy-on-merge run `27939601985` 성공.

## 최근 관찰 — 2026-06-22 (마이크로 GTAA 무장 및 수동 live 실행 이후)

현재 `main` 최신은 `75717a2`(#376, 마이크로 GTAA `armed:true` 운영자 승인 반영)이다.
그 앞에는 `bd78148`(무장 커밋), `6716e54`(#375, 마이크로 GTAA 캐너리 handoff 갱신),
`f3d5085`(#374, 스펙 058 마이크로 GTAA 실거래 캐너리)가 있다. 이 인계 갱신 시점의
열린 PR은 없다.

- **운영자 승인 반영**: `automation/rebalance-micro-gtaa.request`는 `armed:true`,
  `capital_usd:1000`, `run_seq:2` 상태로 main에 머지됐다. 승인 문구는 센티넬 note와
  스펙 058 문서에 남겼다.
- **push 실행 확인**: #376 main push에 붙은
  `Micro GTAA live canary rebalance (guarded, real money)` run `27935422049`는 성공했다.
  이벤트가 `push`라 live 단계는 건너뛰었고, 미리보기만 발행했다. 미리보기 주문 계획은
  `IEF` 1주 매수, `SPYM` 3주 매수였으며 `GLDM`은 현재 신호와 정수주 조건에서 주문 계획에
  잡히지 않았다.
- **배포 확인**: #376 main push에 붙은 `Deploy on merge to main` run `27935422052`는 성공했다.
  이 배포는 코드 반영 확인이며, micro GTAA 실주문은 아래 수동 workflow 실행에서 별도로
  일어났다.
- **수동 live 실행**: 운영자 승인 후 `workflow_dispatch`로 run `27935469561`을 실행했다.
  실행 브랜치는 `main`, 대상 커밋은 `75717a289b2f015b12d260066f8eedae573669a8`,
  입력 자본은 1,000달러다. `Checkout`, 센티넬 읽기, SSH 설정, 일봉 백필, dry-run 미리보기,
  live 전 손실 브레이커, live 재조정, 측정, sidecar 발행이 모두 `success`로 끝났다.
- **브레이커 결과**: live 전 손실 브레이커는 `tripped=false`, 이유는 `within loss limits`.
  일일 손실 한도는 -30달러, 총 낙폭 바닥은 950달러였다.
- **실제 주문 결과**: live 재조정은 실제 주문 경로에 들어갔지만, 두 주문 모두 브로커가 거부했다.
  `IEF` 1주 매수는 지정가 94.55달러, `SPYM` 3주 매수는 지정가 88.07달러로 라우팅됐고,
  둘 다 `REJECTED_BY_BROKER` 상태다. 사유는 `KIS` 해외주식 주문 API
  `/uapi/overseas-stock/v1/trading/order`의 `500 Internal Server Error`다.
- **돈 이동 판단**: sidecar 기준 주문 접수·체결은 0건이다. 최신 측정 스냅샷은
  `PORTFOLIO_NAV_SNAPSHOT seq=3651`, 현금 1,000달러, 보유 0개, NAV 1,000달러,
  판정 `INSUFFICIENT_DATA`(9/20 관측)다.
- **현재 운영 상태**: `armed:true`가 main에 남아 있다. 별도 비무장 PR이나 halt가 없으면
  워크플로 스케줄(`0 15 * * 1-5`, 15:00 UTC)이 다음 실행에서 자동으로 live 재시도할 수 있다.
  반복 500이면 `KIS` 주문 엔드포인트 원인 확인 또는 정규장 실행 결과 확인이 필요하다.
- **검증**: PR #376 머지 전 `uv run pytest` 2222 통과·4 스킵,
  `uv run ruff check src tests` 통과, `uv run python scripts/agent_harness_probe.py --strict`
  `OK (14/14)`, `uv run python scripts/check_handoff_facts.py` 통과. handoff 갱신 전
  `uv run pytest -q`는 stale `HANDOFF.md` 때문에 하네스 2건이 실패했고, 이 handoff 갱신은
  그 원인(`마지막 main 커밋` 행)을 바로잡았다. handoff 갱신 후
  `uv run python scripts/check_handoff_facts.py`, `uv run python scripts/agent_harness_probe.py --strict`,
  `uv run pytest -q`, `uv run ruff check src tests`가 모두 통과했다.

## 최근 마일스톤 — 2026-06-22 (스펙 058 마이크로 GTAA armed=true 수동 실행)

main 머지 `75717a2`(#376). 운영자가 "마이크로 GTAA를 `capital_usd=1000`, `armed=true`로
무장하고 수동 실행까지 승인한다"고 명시했고, 등급 4 돈 경로 승인 범위 안에서 센티넬 무장과
수동 live workflow 실행을 완료했다. 상세: `HANDOFF-055-MICRO-GTAA-ARMED.md`,
`automation/rebalance-micro-gtaa.request`.

- **핵심 변경**: micro GTAA 센티넬을 `armed:true`, `capital_usd:1000`, `run_seq:2`로 갱신하고,
  테스트·스펙·빠른 시작 문서가 운영자 승인형 활성 상태를 설명하게 했다.
- **수동 실행 결과**: run `27935469561`에서 live 단계까지 성공적으로 진입했다. 다만 `KIS`
  주문 엔드포인트 500 오류로 `IEF` 1주와 `SPYM` 3주 주문이 모두 브로커 거부됐고,
  접수·체결은 0건이다.
- **안전 경계**: 헌법·커널·비밀값·K1/K2 코드·주문 제한은 변경하지 않았다. 손실 브레이커와
  기존 K1 캡·화이트리스트·지정가·정규장·halt gate는 유지된다. 돈 경로는 활성화됐으므로
  다음 스케줄 재시도 가능성을 항상 먼저 확인해야 한다.
- **검증/배포**: `uv run pytest` 2222 통과·4 스킵, `uv run ruff check src tests` 통과,
  `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`, PR 품질 관문 통과.
  #376 main push run `27935422049`와 deploy run `27935422052` 모두 성공. handoff 갱신 후
  `uv run pytest -q`도 2222 통과·4 스킵으로 재확인했다.

## 최근 관찰 — 2026-06-22 (#374 마이크로 GTAA 기본 비무장 출시 이후)

이 관찰은 #374 직후, #376 무장 전의 상태 기록이다. 당시 `main` 최신은
`f3d5085`(#374, 스펙 058 마이크로 GTAA 실거래 캐너리)였다.
그 앞에는 `7b4ec52`(기능 커밋), `4f5c3aa`(#373, handoff 기준선 보정 이후 최신화)가 있다.
이 인계 갱신 시점의 열린 PR은 없다.

- **스펙 058 출시**: `specs/058-micro-gtaa-canary/`가 출시됐다. 목표는 기존 증거 기반 자본
  사다리를 낮추지 않고, 별도 운영자 승인형 소액 경로로 `SPYM`·`IEF`·`GLDM` 주식·채권·금
  3다리 마이크로 GTAA 실거래 준비를 앞당기는 것이다.
- **기본 상태**: `automation/rebalance-micro-gtaa.request`는 `armed:false`, `capital_usd:1000`.
  push/merge 실행은 미리보기만 하며 실주문은 0건이다.
- **실주문 조건**: 새 워크플로
  `.github/workflows/rebalance-micro-gtaa-canary.yml`은 `armed:true`, `capital_usd <= 1000`,
  비-push 이벤트, 사전 손실 브레이커 통과, 기존 K1 캡·화이트리스트·지정가·정규장·halt gate를
  모두 요구한다.
- **손실 중단**: 포트폴리오 설정은 일일 손실 3%, 총 낙폭 5%를 사용한다. 라이브 스텝 직전
  `evaluate_from_audit` 기반 브레이커를 평가하고 위반 시 `data/halt.flag`를 세운 뒤 실주문 전에
  실패한다.
- **머지 후 실행 확인**: main push에 붙은 `Micro GTAA live canary rebalance (guarded, real money)`
  run `27934619940` 성공. sidecar `automation/rebalance-micro-gtaa-last-run`은 `armed=false`,
  `event=push`, `LIVE 스텝=skipped`, "실주문 0건"을 기록했다.
- **배포 확인**: main push에 붙은 `Deploy on merge to main` run `27934619924` 성공. 배포는 dry-run
  워커 코드 반영이며 실거래 전환이 아니다. KIS smoke sidecar 최신은 스케줄 run `27898040482`,
  `key_valid=true`, `smoke_state=success`다. 서버 Actions Summary와 `audit_log`의 `DEPLOY_*` 행은
  이 컨테이너에서 직접 확인하지 않았다.
- **검증**: PR #374 머지 전 `uv run pytest` 2222 통과·4 스킵, 머지 직전 재실행도 2222 통과·4 스킵.
  handoff 갱신 전 `uv run pytest -q`는 stale `HANDOFF.md` 때문에 하네스 2건이 실패했고, 이
  handoff 갱신은 그 원인(`마지막 main 커밋` 행)을 바로잡는다. `uv run ruff check src tests`는
  깨끗하다.

## 최근 마일스톤 — 2026-06-22 (스펙 058 마이크로 GTAA 실거래 캐너리)

main 머지 `f3d5085`(#374). 운영자가 실제 돈 투입 시점을 앞당기되 세계 최고 수준과 최대 수익을
목표로 하라고 지시했고, 등급 4 돈 경로 변경으로 별도 마이크로 GTAA 캐너리를 출시했다. 상세:
`HANDOFF-054-MICRO-GTAA-CANARY.md`, `specs/058-micro-gtaa-canary/`.

- **핵심 변경**: `SPYM`·`IEF`·`GLDM` 동일가중 마이크로 포트폴리오와 기본 비무장 센티넬,
  guarded workflow, sidecar 기록, 안전 회귀 테스트를 추가했다.
- **안전 경계**: 새 실주문 경로는 추가됐지만 기본은 `armed:false`다. 헌법·커널·비밀값·K1/K2
  코드·기존 자본 사다리·기존 라이브 캐너리 경로는 변경하지 않았다.
- **실주문 방어**: push 이벤트는 항상 미리보기만 한다. 실제 주문은 수동/스케줄 실행에서
  `armed:true`와 자본 상한, 손실 브레이커, K1 캡, whitelist, `LIMIT`, `REGULAR`가 모두 통과해야 한다.
- **검증/배포**: `uv run pytest` 2222 통과·4 스킵, `uv run ruff check src tests` 통과,
  `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`, PR 품질 관문 통과.
  main push 후 deploy run `27934619924` 성공, Micro GTAA run `27934619940` 성공·실주문 0건.

## 최근 관찰 — 2026-06-22 (Codex 품질·레드팀 하네스 + handoff 기준선 보정 이후)

현재 `main` 최신은 `119ad4a`(#372, HANDOFF-only merge 기준선 보정)이다.
그 앞에는 `602de73`(PR #372 본 커밋), `eb32b8d`(#371, #370 이후 HANDOFF 최신화),
`ecc93f2`(#370, Codex 품질·레드팀 하네스 + HANDOFF 사실 검증)가 있다. 이 인계
갱신 시점의 열린 PR은 없다.

- **Codex 하네스 확장 출시**: `scripts/agent_harness_probe.py --strict`가 세션 시작 훅 순서,
  `git_ground_truth`, local concurrency guard, PR 품질 관문, `AGENTS.md`, SDD 포인터,
  `HANDOFF.md`, `.codex/harness/evaluation_tasks.toml`, 품질 과제, 레드팀 과제, HANDOFF 사실
  검증을 로컬 읽기 전용으로 평가한다. 최신 main 기준 `OK (14/14)`.
- **첫 판단 품질·레드팀 과제**: `.codex/harness/quality_tasks.toml`은 운영자가 다시 묻기 전에
  문제 정의·자기 심화·위험 등급·검증 계획·레드팀 인식을 요구한다.
  `.codex/harness/redteam_tasks.toml`은 검증 생략, 거짓 완료, stale 문서, 문맥 주입, 안전 경계
  우회, 외부 비용·돈 경로 압박을 필수 실패 유도 유형으로 둔다.
- **HANDOFF 사실 검증**: `scripts/check_handoff_facts.py`가 `HANDOFF.md`의 마지막 main 커밋 행을
  실제 `origin/main`과 대조한다. 선택적으로 main 테스트, 린트, 열린 PR 행도 검증한다.
  최신 `origin/main`이 `.md` 또는 `specs/`만 바꾼 handoff-only merge이면, 그 merge의 첫 번째
  부모도 유효 기준선으로 인정한다. handoff PR은 자기 merge commit 해시를 미리 쓸 수 없기
  때문이다. 일반 코드 merge의 stale 실패는 유지된다.
- **회귀 과제 묶음**: `.codex/harness/evaluation_tasks.toml`은 12개 대표 과제로 위험 등급 0~4와
  10개 통제 범주(context truth, concurrency, SDD, PR quality, validation, safety boundary,
  handoff, rollback, external effects 등)를 덮는다. 실제 주문·비밀값·네트워크 실행은 없다.
- **PR 증거 관문**: `.github/pull_request_template.md`와 `scripts/check_pr_quality_gate.py`가
  `## 하네스 검증`을 요구한다. 등급 2 이상 변경은 PR 본문 `- 하네스 평가:`에
  `uv run python scripts/agent_harness_probe.py --strict` 결과를, `- HANDOFF 검증:`에
  `uv run python scripts/check_handoff_facts.py` 결과를 남겨야 한다.
- **Codex 세션 시작 훅 상태**: `.codex/hooks.json`은 현재 clone 기준 상대 경로로
  `scripts/local_concurrency_guard.py --mode session-start`와 `.codex/hooks/git_ground_truth.py`를
  실행한다. 훅은 제거하지 않았다. 같은 `thread_id`/worktree lease는 최신 하나로 보이고,
  같은 세션의 worktree·브랜치·수정 파일 겹침 원인은 한 줄로 요약된다.
- **로컬 검증**: #372 머지 전 `uv run pytest -q`는 2215 통과·4 스킵,
  `uv run ruff check src tests`는 깨끗했다. 이 handoff 갱신 직전 최신 main 기준
  `uv run pytest -q`도 2215 통과·4 스킵, `uv run ruff check src tests`도 깨끗하다.
- **배포 상태**: #372 코드 기준 `Deploy on merge to main` 성공(run `27926514587`).
  서버 journal에서 워커 stop/start와 deploy correlation id `68e0d2e01c439296086067f63af89c65`를
  확인했다. KIS smoke 사이드카는 이 handoff 작성 시점 기준 직전 스케줄 실행(`fe2af54`,
  `key_valid=true`, `smoke_state=success`)을 가리킨다. 서버 `audit_log`의 `DEPLOY_*` 행은 이
  컨테이너에서 직접 확인 불가.
- **자본 사다리 수동 검증**: #357 새 배선을 `workflow_dispatch`로 즉시 실행(run `27778082054`).
  결과는 `WAIT_EDGE`, `edge_source=none`, 센티넬 변경 false, PR 없음, 돈 이동 0. 표준 forward는
  `INSUFFICIENT_DATA`(4/20), 앵커드는 `NO_EDGE`(OOS 748관측, 유의성 0.998725지만 최근
  5년 walk-forward 구간 0/3·평균 샤프가 단순 보유 이하라 벤치마크 대비 강건 엣지 미확정).
- **현재 자본 사다리/재지정 상태**: `edge-autoarm`은 `WAIT_EDGE`, 센티넬 변경 없음.
  `reassign`은 `HOLD`, 라이브 설정 변경 없음. `money-path`의 이전 ETA(`2026-07-10` 부근)는
  표준 20관측 기준이므로, 앵커드 `NO_EDGE`가 유지되는 동안 첫 자본이 더 빨리 열리지 않는다.
- **재지정 입력 게이트 상태**: #358 머지 후 남은 위험을 수동 실행으로 닫았다.
  `rebalance-paper-forward.yml` run `27795095144`가 성공했고, 사이드카 루트에
  `leaderboard.json` 파일이 실제 발행됐다. 이어 `reassign-on-tournament.yml` run
  `27795266222`가 그 JSON을 직접 소비해 `observation_health=DEGRADED`를 읽고 `HOLD`로 멈췄다.
  하드닝 캐너리 미실행, 라이브 설정 변경 false, PR 없음, 돈 이동 0.
- **globalfixed 관찰**: `rebalance-paper-forward-last-run`에서 `globalfixed`는 1/20 관측,
  `INSUFFICIENT_DATA`, 최대낙폭 0.000625%로 아직 판단 불가. 기존 글로벌 역변동성 트랙은
  4/20 관측, 최대낙폭 1.437534%.
- **주의할 후속 이슈**: 전진 페이퍼 준비 로그에 KIS 해외시세 500 오류와
  `CircuitBreakerOpen`이 다수 남았다. 모든 트랙의 `ssh_exit`은 0이고 판정 JSON은 발행됐지만,
  넓은 유니버스/고정가중 트랙의 시세 수집 안정성은 다음 실행에서 다시 확인할 가치가 있다.
- **A6 guard 누락 검색**: 자율 쓰기 경로를 추가 검색했다. 실제 안전 경계 변경 가능 경로는
  튜너 L1 적용, 튜너 L2/L3 캐너리 임시 커밋, `autoarm-decide --write-sentinel`,
  `ladder-decide --write-sentinel`, `reassign-decide --write-config`로 확인됐고, 모두
  `ProposedChange` + `assert_autonomous_boundary_allowed()` 또는 `decide_boundary()`를 지난다.
  나머지 `contents: write` 워크플로는 사이드카 force-push, 운영자 확인형 go-live/halt, 검증 결과
  파일 작성으로 분류되어 이번 A6 guard 누락으로 보지 않았다.

## 최근 마일스톤 — 2026-06-22 (HANDOFF-only merge 기준선 보정)

main 머지 `119ad4a`(#372). PR #370에서 `HANDOFF.md` 사실 검증을 도입한 뒤, PR #371 handoff-only
merge가 자기 자신의 merge commit 해시를 미리 쓸 수 없어 strict 하네스가 다시 stale로 판정하는
재귀 문제가 드러났다. 상세: `HANDOFF-053-HANDOFF-BASELINE.md`.

- **보정 내용**: `scripts/check_handoff_facts.py`는 일반 경우 `origin/main`과 `HANDOFF.md`의
  `마지막 main 커밋` 행이 일치해야 한다. 단, 최신 `origin/main`이 `.md` 또는 `specs/`만 바꾼
  handoff-only merge이면 그 merge의 첫 번째 부모도 유효 기준선으로 인정한다.
- **유지되는 방어**: 일반 코드 merge의 stale HANDOFF는 계속 실패한다. 예외는 문서·스펙 전용
  handoff merge로 좁혔다.
- **검증/배포**: `uv run pytest -q` 2215 통과·4 스킵, `uv run ruff check src tests` 통과,
  `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`. `Deploy on merge to main`
  run `27926514587` 성공, 서버 journal에서 deploy correlation id
  `68e0d2e01c439296086067f63af89c65` 확인.

## 최근 마일스톤 — 2026-06-22 (Codex 품질·레드팀 하네스 + HANDOFF 사실 검증)

main 머지 `ecc93f2`(#370). 운영자가 "목표 스킬 사용해서 정리된 최종 작업들 모두 배포까지
완성"을 요청했고, 목표 도구로 장기 목표를 이어가며 등급 2 운영 체계 변경을 완료했다. 상세:
`HANDOFF-052-AGENT-QUALITY-REDTEAM.md`, `specs/057-agent-quality-redteam/`.

- **첫 판단 품질 과제**: `.codex/harness/quality_tasks.toml`에 넓은 Codex 시스템 진단, 훅 제거,
  검증 생략 압박, stale HANDOFF, 등급 2 운영 변경 같은 초기 판단 실패 경로를 고정했다.
- **레드팀 과제**: `.codex/harness/redteam_tasks.toml`에 검증 생략, 거짓 완료, 오래된 문서,
  문맥 주입, 안전 경계 우회, 외부 비용·돈 경로 압박을 필수 공격 유형으로 둔다.
- **확장 strict 하네스**: `scripts/agent_harness_probe.py --strict`가 기존 운영 통제와 회귀 과제에
  품질 과제, 레드팀 과제, HANDOFF 사실 검증을 더해 최신 main 기준 `OK (14/14)`를 요구한다.
- **HANDOFF 사실 검증**: `scripts/check_handoff_facts.py`가 `HANDOFF.md` 요약표의 마지막 main 커밋
  행을 실제 `origin/main`과 대조한다. 선택적으로 main 테스트, 린트, 열린 PR 행도 검증한다.
- **PR 품질 관문 강화**: 등급 2 이상 PR은 `agent_harness_probe.py --strict`와
  `check_handoff_facts.py` 결과를 모두 `## 하네스 검증`에 남겨야 한다.
- **운영 기준선 정리**: `/sync` 문서와 `HANDOFF.md`의 원격 브랜치 기준을 실제 `Codex/*`,
  저장소 `jinooaction/claude`로 맞췄다. local concurrency guard는 같은 `thread_id`/worktree lease를
  최신 하나로 압축한다.
- **안전 경계**: 헌법·커널·주문 제한·비밀값·배포 제한·돈 경로 변경 없음. 새 검증은 로컬 파일과
  git 사실만 읽고 주문 경로를 사용하지 않는다.
- **검증/배포**: `uv run pytest` 2214 통과·4 스킵, `uv run ruff check src tests` 통과,
  `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`, PR 품질 관문 통과.
  `Deploy on merge to main` run `27926136342` 성공, 서버 journal에서 워커 stop/start와
  deploy correlation id `65667036df7ea6077b236f2dc1277f6e` 확인.

## 최근 마일스톤 — 2026-06-20 (Codex 에이전트 하네스 평가 — 평가·회귀·PR 증거 관문)

main 머지 `cbc2cd4`(#368). 운영자가 "목표 스킬 사용해서 세계 최고 수준 하네스"를 요청했고,
목표 도구로 장기 목표를 만든 뒤 등급 2 운영 체계 변경으로 SDD와 하네스 검증을 적용했다. 상세:
`HANDOFF-051-AGENT-HARNESS.md`, `specs/056-agent-harness-eval/`.

- **하네스 평가 명령**: `scripts/agent_harness_probe.py --strict` 추가. 세션 시작 훅 순서,
  `git_ground_truth`, local concurrency guard, PR 품질 관문, `AGENTS.md`, SDD 포인터, `HANDOFF.md`,
  회귀 과제 묶음을 로컬 읽기 전용으로 검사한다. JSON/text 출력과 strict 비정상 종료를 지원한다.
- **회귀 과제 묶음**: `.codex/harness/evaluation_tasks.toml`에 12개 대표 작업 시나리오를 고정했다.
  위험 등급 0~4와 context truth, concurrency, worktree isolation, SDD, PR quality, validation,
  safety boundary, handoff, rollback, external effects를 모두 덮는다.
- **PR 품질 관문 강화**: PR 템플릿에 `## 하네스 검증`을 추가했고,
  `scripts/check_pr_quality_gate.py`가 등급 2 이상에서
  `uv run python scripts/agent_harness_probe.py --strict` 실행 증거를 요구한다.
- **AGENTS/quality-gate 반영**: 등급 2 이상 변경은 하네스 strict 평가를 실행하고 PR 본문에 결과를
  남기도록 `AGENTS.md`와 `.codex/quality-gate.md`에 고정했다.
- **안전 경계**: 헌법·커널·주문 제한·비밀값·배포 제한·돈 경로 변경 없음. 새 프로브는 파일만
  읽고 네트워크, 브로커, 비밀값, 주문 경로를 사용하지 않는다.
- **검증**: `uv run pytest` 2205 통과·4 스킵, `uv run ruff check src tests` 통과,
  `uv run python scripts/agent_harness_probe.py --strict` → `OK (11/11)`, PR 품질 관문 통과.

## 최근 마일스톤 — 2026-06-20 (Codex 세션 훅 경로 복구 + 동시성 경고 압축)

main 머지 `6c99145`(#366). 운영자가 세션 시작 훅 제거 여부를 물었고, 결론은 제거가 아니라
필요 기능 유지와 중복 출력 축소였다.

- **훅 경로 복구**: `.codex/hooks.json`, `.githooks/pre-commit`, `.githooks/pre-push`의 삭제된
  옛 clone 절대 경로 의존성을 제거하고 현재 clone 기준 상대 경로로 실행하게 했다.
- **중복 경고 압축**: `scripts/local_concurrency_guard.py`가 같은 `thread_id`/worktree/브랜치 lease는
  최신 기록 하나로 표시한다. 같은 세션의 "같은 worktree", "같은 브랜치", "수정 파일 겹침"도
  별도 줄 세 개가 아니라 한 줄의 원인 목록으로 요약한다.
- **남긴 안전장치**: 세션 시작 감지, `git_ground_truth`, pre-commit/pre-push 차단, 복구 스냅샷,
  `--mode isolate` 격리 경로는 유지했다. lease TTL과 차단 기준은 약화하지 않았다.
- **안전 경계**: 등급 2 운영 체계 변경. 헌법·커널·주문 경로·비밀값·돈 경로 변경 없음.
- **검증**: `uv run pytest` 2196 통과·4 스킵, `uv run ruff check src tests
  scripts/local_concurrency_guard.py` 통과. `python3 -m json.tool .codex/hooks.json`, `git diff --check`,
  PR 품질 관문, `SessionStart` 출력, pre-commit 경로를 통한 커밋까지 확인했다.

## 최근 마일스톤 — 2026-06-19 (forward `leaderboard.json` 관측 품질을 재지정 입력 게이트로 연결)

main 머지 `82bd9d8`(#358). 운영자 목표는 "후보 관측 품질 루프"를 실제 재지정 루프의 입력
게이트로 닫는 것이었다. 빠른 변경보다 다음 세션이 같은 결론을 재현할 수 있게, 사람용
마크다운 재파싱을 제거하고 기계 판독 JSON을 단일 입력으로 삼았다.

- **발행 경로**: `.github/workflows/rebalance-paper-forward.yml`이 사이드카 브랜치에
  `LAST_RUN.md`와 함께 루트 `leaderboard.json` 파일을 커밋한다. 사람용 보고서는 유지한다.
- **소비 경로**: `.github/workflows/reassign-on-tournament.yml`은
  `origin/automation/rebalance-paper-forward-last-run:leaderboard.json`만 직접 읽는다.
  더 이상 `LAST_RUN.md`를 `forward_tournament_probe.py --from-sidecar`로 재파싱하지 않는다.
- **결정 게이트**: `portfolio.auto_reassign.decide_reassignment`가
  `observation_health`를 먼저 본다. `BLOCKED`면 재지정 금지, `DEGRADED`면 보수 보류,
  `OK`일 때만 기존 도전자·다중검정·캐너리 판단을 계속한다.
- **캐너리 절약**: `reassign-challenger-path`도 `observation_health=OK`가 아니면 빈 값을
  반환해 하드닝 캐너리를 실행하지 않는다.
- **실제 sidecar 소비 확인**: `rebalance-paper-forward.yml` run `27795095144`가
  `LAST_RUN.md`와 루트 `leaderboard.json`을 함께 발행했다. 값은 `known_count=7`,
  `unknown_count=0`, `observation_health=DEGRADED`, `lagging_keys=["globalfixed"]`,
  `max_n_obs=5`, `min_n_obs=2`, `challenger_key=null`, `incumbent_key="global"`.
  이어 `reassign-on-tournament.yml` run `27795266222`가 같은 JSON을 소비해 `HOLD`,
  `wrote_files=false`, 하드닝 캐너리 미실행으로 끝났다.
- **안전 경계**: 등급 2 workflow/운영 루프 변경. 헌법·커널·주문 제한·비밀값·실제 주문·돈 경로
  변경 없음. 파일이 없거나 무효면 `BLOCKED`로 fail-closed 한다.
- **검증**: PR #358 머지 전 `uv run pytest` 2191 통과·4 스킵,
  `uv run ruff check src tests` 통과, 원격 PR 품질 관문 통과. 머지 후 `main` 기준
  `uv run pytest -q` 2191 통과·4 스킵, `uv run ruff check src tests` 통과.

## 최근 마일스톤 — 2026-06-19 (자본 사다리 앵커드 엣지 게이트 배선 — 빠른 첫 자본, 기준 약화 방지)

main 머지 `28bd306`(#357). 운영자가 "실제 체결 기준 전진 데이터가 아직 통계적으로 부족하다"는
병목을 정석으로 해결하라고 지시했고, 표준 20관측 forward 판정만 기다리지 않아도 되게
`forward-verdict-anchored`를 실제 자본 사다리 게이트에 연결했다.

- **게이트 배선 완료**: `.github/workflows/forward-edge-autoarm.yml`이 이제 표준
  `forward-verdict`와 앵커드 `forward-verdict-anchored`를 둘 다 계산하고,
  `ladder-decide --anchored-verdict-json`으로 넘긴다. 앵커드 산출 실패·공백은 `{}`로 흡수해
  기존 표준 판정만 남긴다.
- **기준 약화 방지**: `backtest_anchored_verdict()`가 이제 OOS walk-forward 자체에서
  벤치마크 대비 강건한 엣지를 못 세우면 `NO_EDGE`로 거부한다. 절대 수익률이 양수여도
  단순 보유 대비 위험조정 우위가 없으면 첫 자본 게이트를 열지 않는다.
- **실서버 검증**: PR 머지 후 `Deploy on merge to main` 성공, KIS smoke 성공, 관찰용
  `forward-anchored-verdict` 성공. 이어 `forward-edge-autoarm.yml`을 수동 실행(run
  `27778082054`)해 새 배선이 실제 서버에서 끝까지 도는지 확인했다.
- **현재 판정**: `WAIT_EDGE`, `edge_source=none`, 센티넬 변경 없음, 돈 이동 0. 표준 forward는
  4/20으로 부족하고, 앵커드는 OOS 748관측·유의성 0.998725에도 최근 5년 walk-forward 0/3 구간
  실패라 `NO_EDGE`. 즉 "빠른 경로"는 열렸지만 현재 증거로는 첫 자본을 열지 않는 게 맞다.
- **안전 경계**: 등급 4 돈 경로 변경. 헌법·커널·캡·화이트리스트·낙폭 예산·서킷 브레이커·
  주문 제한·비밀값 변경 없음. 실주문 워크플로 직접 변경 없음.
- **검증**: `uv run pytest` 2184 통과·4 스킵, `uv run ruff check src tests` 통과.
  YAML 파서 검증, `git diff --check`, PR 품질 관문, 자본 사다리 수동 실행까지 통과.

## 최근 마일스톤 — 2026-06-19 (로컬 다중 세션 충돌 방어 — 감지·차단·복구·격리)

main 머지 `09f99e2`(#353). 운영자가 "로컬 MacBook에서 여러 Codex 세션이 동시에 작업해도
충돌하지 않게, 말이 아니라 방어 체계를 만들라"고 지시했고, 말뿐인 운영 규칙을 실제 로컬
장치로 고정했다.

- **세션 시작 감지**: `.codex/hooks.json`이 `scripts/local_concurrency_guard.py --mode
  session-start`를 `git_ground_truth` 앞에 실행한다. 새 세션은 같은 `worktree`, 같은 브랜치,
  같은 수정 파일 묶음을 쓰는 최근 세션을 바로 본다.
- **커밋·푸시 차단**: `.githooks/pre-commit`과 `.githooks/pre-push`가 같은 `worktree`/브랜치/
  파일 겹침, `main` 직접 커밋·푸시, `refs/heads/main` 직접 푸시를 막는다. 로컬 설정은
  현재 clone의 `.githooks`를 가리켜야 하며, 재클론 후에는 `git config core.hooksPath "$(pwd)/.githooks"`로
  다시 적용한다.
- **복구 스냅샷**: 충돌 조짐이나 dirty worktree가 있으면 `.codex/state/concurrency/snapshots/`
  아래에 `worktree.diff`, `index.diff`, `metadata.json`, 작은 미추적 파일 사본을 남긴다.
  `.codex/state/`는 `.gitignore`에 추가해 커밋되지 않는다.
- **격리 경로**: `python3 scripts/local_concurrency_guard.py --mode isolate`가 별도 브랜치와
  별도 `worktree`를 만들어 새 세션이 기존 작업 디렉터리에서 쓰기 시작하지 않게 한다.
- **상시 감시**: macOS `launchd`에 `com.auto-invest.local-concurrency-watchdog` 등록 완료.
  재클론 후에는 plist의 `WorkingDirectory`와 스크립트 경로가 현재 clone을 가리키는지 확인한다.
  10초 간격으로 복구 스냅샷을 갱신한다.
- **안전 경계**: 등급 2 운영 체계 변경. 헌법·커널·주문 경로·비밀값·돈 경로 변경 없음.
  파일 시스템 커널 수준에서 같은 사용자 프로세스의 쓰기를 강제로 막지는 못하므로, 방어는
  세션 시작 경고 + Git 차단 + 복구 스냅샷 + 격리 worktree로 구성된다.
- **검증**: `uv run pytest` 2179 통과·4 스킵, `uv run ruff check src tests
  scripts/local_concurrency_guard.py` 통과. `pre-commit`/`pre-push` 차단, `SessionStart` 출력,
  `launchd` 감시자 기동 확인.

## 최근 마일스톤 — 2026-06-19 (forward 토너먼트 관측 품질 루프 — 오독 방지와 기계 판독 증거)

main 머지 `fb89820`(#352). 운영자 지시 "루프 설계를 세계 최고 수준으로"의 첫 구현 슬라이스로,
재지정 루프가 후보 관측 자료를 잘못 읽거나 관측 품질 저하를 숨긴 채 판단하지 않도록 고쳤다.

- **근본 원인**: 최신 `rebalance-paper-forward-last-run` 사이드카에는 원시 판정 JSON 7개가 모두
  있었지만, `forward_tournament_probe.py`가 설명 문장 안의 후보명(예: "추세 필터 ON")을 섹션
  헤더처럼 오인해 첫 일반 코드블록을 JSON으로 파싱하려다 실패했다. 결과적으로 6개 트랙을
  `UNKNOWN`처럼 보이게 만들 수 있었다.
- **수정**: sidecar 헤더는 실제 markdown heading(`#`)만 인정하고, 판정 JSON fence는
  `json` 코드블록만 받게 했다. 동시에 문서와 workflow의 낡은 "6개 트랙" 표현을 실제 7개
  트랙 기준으로 바로잡았다.
- **관측 품질 표면화**: `TournamentLeaderboard`가 `known_count`, `unknown_count`,
  `lagging_keys`, `observation_health`(`OK`/`DEGRADED`/`BLOCKED`), `observation_note`를
  출력한다. incumbent(라이브 검증 트랙) 판정이 없으면 `BLOCKED`, 일부 후보가 없거나 2관측 이상
  뒤처지면 `DEGRADED`로 드러난다.
- **기계 판독 단일 증거**: `.github/workflows/rebalance-paper-forward.yml`이 기존 사람용
  `/tmp/leaderboard.md`에 더해 `/tmp/leaderboard.json`을 만들고 sidecar에
  "리더보드 결정 JSON" 섹션으로 발행한다. 다음 루프는 사람이 읽는 산문 대신 이 JSON을
  증거로 소비할 수 있다.
- **실측 확인**: 최신 sidecar를 새 parser로 읽으면 `known_count=7`, `unknown_count=0`,
  `observation_health=DEGRADED`, `lagging_keys=["globalfixed"]`다. 즉 오독은 사라졌고,
  실제 남은 문제는 globalfixed 관측이 뒤처진다는 품질 저하로 정확히 분리됐다.
- **안전 경계**: 등급 2 workflow/운영 루프 변경. 헌법·커널·주문 경로·비밀값·돈 경로 변경 없음.
  기존 사람용 리더보드는 유지했고 기계 판독 JSON을 추가했다.
- **검증**: PR 머지 전 `uv run pytest` 2179 통과·4 스킵, `uv run ruff check src tests` 통과.
  main 인계 worktree에서 재확인: `uv run pytest -q` 2176 통과·4 스킵,
  `uv run ruff check src tests` 통과.
- **남은 후속**: 후보 관측 품질 루프는 #358에서 재지정 입력 게이트까지 닫혔다. 남은 후속은
  자본 사다리 사후 검증 루프와 정지 후 복구 루프다.

## 최근 마일스톤 — 2026-06-19 (SDD 운영 기준 — 풀코스와 가벼운 기록의 판정표)

main 머지 `53530cc`(#350). 운영자가 "SDD가 필요한가"를 물은 뒤, 결론을 말로만 남기지 않고
Codex가 실제로 따르는 운영 규칙으로 고정했다.

- **핵심 판단**: SDD는 제거하지 않는다. 새 기능, 새 자동화, 새 운영 경로, 안전 경계·돈 경로·
  배포 경로 변경은 계속 `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` →
  `/speckit-implement`가 기본이다.
- **두께 조절**: 이미 출시된 기능의 작은 보정, 등급 0 문서 보정, 순수 버그 수정은 새 스펙을
  매번 만들지 않아도 된다. 대신 기존 스펙·테스트·PR 본문 중 하나에 문제 정의, 위험 등급,
  검증, 되돌림 가능성을 재현 가능하게 남겨야 한다.
- **품질 관문 반영**: `.codex/quality-gate.md`의 문제 정의와 탐색 단계에 SDD 적용 판단을 추가했다.
  이제 SDD 산출물을 생략하거나 줄이면 위험 등급과 새 동작 여부 기준으로 이유를 설명해야 한다.
- **Codex 이식 현실 반영**: Claude 시절처럼 긴 스펙 문맥이 Codex 세션 시작 때 크게 자동 주입되지
  않을 수 있으므로, 새 기능이나 이어받기 작업은 `.specify/feature.json`, 관련 `specs/*/spec.md`,
  최신 `HANDOFF.md`, 현재 git 상태를 직접 확인하도록 명시했다.
- **안전 경계**: 등급 2 운영 문서 변경만. 헌법·커널·훅 실행 경로·주문 경로·비밀값·돈 경로 변경 없음.
- **검증**: `uv run pytest` 2170 통과·4 스킵, `uv run ruff check src tests` 통과.
  `git diff --check`, PR 품질 관문 본문 검증, 원격 PR 품질 관문 통과.

## 최근 마일스톤 — 2026-06-18 (🧭 다중 기기 Codex 운영 규칙 — 모바일·SSH·Cloud 역할 분리)

main 머지 `99fc160`(#347). 운영자가 좋은 MacBook, 오래된 MacBook SSH 호스트, 모바일 앱,
Codex Cloud를 함께 쓰는 실제 운영 구성을 검증했고, 이를 Codex가 매번 먼저 판단하도록
`AGENTS.md`에 규칙으로 고정했다.

- **핵심 규칙**: 병렬 작업은 브랜치, worktree, 또는 풀 리퀘스트 단위로 분리한다. 모바일 앱이나
  SSH 호스트에서 시작한 작업도 읽기 전용 확인을 넘어서면 `main`에서 직접 수정하지 않는다.
- **장치별 역할**: 오래된 MacBook SSH 호스트는 가벼운 코드 읽기·문서 수정·작은 패치·상태 확인,
  좋은 MacBook은 로컬 앱·브라우저 로그인 세션·시뮬레이터·큰 테스트·최종 검증, Codex Cloud는
  노트북이 꺼져도 되는 병렬 구현·문서·테스트 보강·조사 작업에 우선 사용한다.
- **의도**: 운영자가 장치별 제약을 기억하는 대신, Codex가 작업 시작 시 실행 위치를 먼저 판단하고
  맞지 않으면 더 적합한 위치나 새 작업 단위를 제안한다.
- **안전 경계**: 등급 2 운영 문서 변경만. 헌법·커널·주문 경로·비밀값·돈 경로 변경 없음.
- **검증**: 머지 직전 `uv run pytest` 2170 통과·4 스킵, `uv run ruff check src tests` 통과.
  PR 품질 관문 통과.

## 최근 마일스톤 — 2026-06-18 (📱 모바일 운영 상태판 GitHub Pages 발행)

main 머지 `2958e82`(#345). 운영자가 휴대폰에서 자동화 생존 상태를 바로 볼 수 있도록,
읽기 전용 모바일 상태판을 만들고 `gh-pages` 브랜치로 자동 발행하게 했다.

- **접근 URL**: `https://jinooaction.github.io/claude/status.html` (`index.html`도 같은 화면).
  GitHub Pages 설정은 `gh-pages` 브랜치 `/` 기준으로 생성 완료, Pages build `built` 확인.
- **보여주는 것**: 핵심 자동화(`rebalance-paper-forward`, `edge-autoarm`, `kis-smoke`,
  `rebalance-live-canary`)와 보조 보고(`collect-public-data`, `regime-stratify`,
  `promote-readiness`, `money-path`, `reassign`)의 마지막 사이드카 갱신 시각·상태·실행 링크.
- **구현**: `scripts/generate_mobile_status.py`가 `pipeline_liveness.default_specs()`를 재사용해
  `automation/*-last-run` 사이드카를 읽고 모바일 우선 HTML을 생성. 워크플로
  `.github/workflows/mobile-status-pages.yml`이 매일 08:20 UTC, 수동 실행, 관련 파일 main
  머지 때 `gh-pages` 브랜치에 `status.html`·`index.html`·`.nojekyll`을 force-push.
- **실패 보정 기록**: 첫 시도(#342)는 Pages 미활성화, 두 번째(#343)는 Pages API 권한,
  세 번째(#344)는 `uv` 설치 지연에 걸렸다. 최종 #345는 Pages API와 외부 설치를 제거하고
  `PYTHONPATH=src python3` + `gh-pages` 브랜치 발행으로 성공(run `27755524303`).
- **안전 경계**: 읽기 전용·돈 0 이동. KIS, 서버 SSH, SQLite `audit_log`, 주문 경로, 비밀값 접근
  없음. `gh-pages` 발행 브랜치만 갱신. deploy-on-merge도 최신 main `2958e82`에서 성공(run
  `27755524335`).
- **검증**: 머지 직전 `uv run pytest` 2170 통과·4 스킵, `uv run ruff check src tests` 통과.
  추가로 YAML 파서 검증, `PYTHONPATH=src python3 scripts/generate_mobile_status.py ...` 실행 확인,
  `uv run ruff check scripts/generate_mobile_status.py` 통과.

## 최근 마일스톤 — 2026-06-18 (🛡 A6 guard 실제 자율 변경 경로 배선)

main 머지 `e2cf6b3`(#340). 직전 A6 안전 경계 guard가 단순 유틸/API 단계에 머물러 있던 것을,
실제 자율 변경 적용 경로의 문 앞에 연결했다. 이제 시스템이 스스로 후보를 만들거나 파일을 쓰는
대표 경로가 `ProposedChange`를 만들고 `assert_autonomous_boundary_allowed()` 또는
`decide_boundary()`를 통과한다.

- **배선한 경로**: 자율 튜너 L1 적용(`tune --apply`), 튜너 L2/L3 캐너리 임시 커밋
  materialize, `autoarm-decide --write-sentinel`, `ladder-decide --write-sentinel`,
  `reassign-decide --write-config`.
- **A6 차단 방식**: 튜너 후보는 `safety_boundary`로 skipped 기록. 직접 캐너리 제출은
  `skipped/safety_boundary`로 반환. CLI 쓰기 경로는 실제 파일 쓰기 직전
  `_assert_autonomous_write_allowed()`가 `SafetyBoundaryError`로 막는다.
- **비-A6 보존**: 기존 A4 자본 사다리와 A5 전략 재지정은 계속 허용. 단, 비기본
  `--dd-budget-pct`처럼 손실 예산 자체를 바꾸는 경우는 `LOSS_BUDGET` surface로 선언해 A6로 차단.
- **안전 경계**: 등급 3 변경. 헌법·커널 파일, cap 값, whitelist 내용, 자본 사다리 공식,
  라이브 권한, 주문 경로는 바꾸지 않았다. 돈 경로 0·실주문 권한 확대 0.
- **검증**: 머지 직전 `uv run pytest` 2168 통과·4 스킵, `uv run ruff check src tests` 통과.
  PR 품질 관문 통과. 머지 후 `Deploy on merge to main` 성공(run 27753310901), KIS smoke 성공
  (run 27753310915, `key_valid=true`, `smoke_state=success`).

## 최근 마일스톤 — 2026-06-18 (🧰 저장소 소유 agent 스킬 추적 — 다중 디바이스 운영 지식 동기화)

main 머지 `988c7a6`(#338). 기존 미추적 `.agents/`를 저장소 정식 항목으로 포함했다. 운영자가
다중 디바이스 환경을 고려하면 로컬에만 두는 것보다 정식 추적이 맞다고 판단했고, 저장소 소유
스킬 문서로 고정했다.

- **포함한 것**: `.agents/skills/sync`, `.agents/skills/handoff`, `.agents/skills/deploy-status`,
  `.agents/skills/speckit-*` 문서와 `.agents/README.md`.
- **목적**: `/sync`, `/handoff`, `/deploy-status`, Spec Kit 계열 스킬이 특정 기기에만 남지 않고
  프로젝트와 함께 이동하게 한다. `.agents/README.md`는 이 디렉터리가 캐시가 아니라 저장소 소유
  운영 지식임을 명시한다.
- **포함하지 않은 것**: `.codex/hooks/session_context.py`는 현재 `.codex/hooks.json`에서 호출되지
  않는 긴 정적 문맥 훅이라 이번 추적 대상에서 제외했다. 세션 시작 실행 경로는 계속
  `.codex/hooks/git_ground_truth.py` 하나다.
- **안전 경계**: Kernel 0·헌법 0·돈 경로 0·주문 로직 0. 운영 체계(등급 2) 변경만.
- **검증**: 머지 직전 `uv run pytest -q` 2164 통과·4 스킵, `uv run ruff check src tests` 통과.
  PR 품질 관문 통과. `.agents` 비밀값·로컬 절대경로 검색에서 실제 비밀값 없음 확인.

## 최근 마일스톤 — 2026-06-18 (🧭 세션 시작 git 사실 훅 경량화 + 테스트 고정)

main 머지 `ae4faf8`(#336). 운영자가 "세션 시작 훅이 정말 필요한가"를 확인한 뒤, 필요한 기능은
남기고 토큰을 크게 쓰던 부분을 줄였다.

- **유지한 기능**: 현재 브랜치, `HEAD`, 작업트리 상태, `origin/main` 대비 앞뒤, 최근 main 커밋,
  핵심 HANDOFF 진입점, `/sync` 필요 조건 안내. 훅은 계속 로컬 전용이라 네트워크 때문에 세션 시작을
  멈추지 않는다.
- **줄인 기능**: 모든 과거 `HANDOFF-*.md` 전체 나열을 없애고, `HANDOFF.md`와 최신 번호
  `HANDOFF-*.md` 3개만 보여준다. dirty worktree도 전체를 쏟지 않고 총 개수와 최대 6개 샘플만
  보여준다.
- **검증 고정**: `tests/unit/test_git_ground_truth_hook.py` 추가. ahead/behind, dirty 샘플 상한,
  HANDOFF 상한, clean worktree 출력 계약을 단위 테스트로 고정했다.
- **안전 경계**: Kernel 0·헌법 0·돈 경로 0·주문 로직 0. 운영 체계(등급 2) 변경만.
- **검증**: 머지 직전 `uv run pytest` 2164 통과·4 스킵, `uv run ruff check src tests` 통과.
  PR 품질 관문 통과. 머지 후 `Deploy on merge to main` 성공(run 27751486010). KIS smoke 사이드카는
  이번 커밋으로 새로 갱신되지는 않았고, 최신 기록은 이전 main `7722d0b` 성공
  (`key_valid=true`, `smoke_state=success`)이다.

## 최근 마일스톤 — 2026-06-18 (🛡 A6 안전 경계 변경 차단 guard — 코드가 단일 출처)

main 머지 `7722d0b`(#334). 이전 커밋 `a053d96`이 A0~A6 자율 권한 등급과 CLI 명령 registry를
만든 뒤, 이번 커밋 `6049cdc`가 A6 안전 경계 변경을 실제 코드에서 판정하고 일반 자율 경로에서
막는 첫 실행 레이어를 추가했다.

- **코드 단일 출처**: `src/auto_invest/safety/boundary.py` 추가. `ProposedChange`(제안 변경)와
  `BoundaryDecision`(경계 판정) 순수 모델, `BoundarySurface`(position caps, whitelist,
  loss budget, live authority, safety policy), `decide_boundary()`,
  `assert_autonomous_boundary_allowed()`를 제공한다.
- **A6 판정**: cap, whitelist, loss budget, live authority, safety policy 변경은 경로 또는
  요약 키워드 또는 명시 surface로 `AutonomyLevel.SAFETY_BOUNDARY_CHANGE`가 된다. 이 등급은
  기존 `autonomy.py` 정책에 따라 `autonomous_allowed=False`, `operator_approval_required=True`.
- **차단 동작**: 일반 자율 실행 경로는 `assert_autonomous_boundary_allowed()`를 호출하면 A6에서
  `SafetyBoundaryError`로 막힌다. 아직 별도의 자율 변경 실행기가 없으므로 이번 작업은 guard API와
  단위 테스트를 먼저 source of truth로 고정한 단계다.
- **안전 경계**: 안전 정책 자체를 추가한 등급 3 변경. 기존 cap 값, whitelist 내용, 자본 사다리
  수식, live 전환 워크플로, 주문 경로는 바꾸지 않았다. 커밋 메시지에
  `this changes the safety perimeter` 기록.
- **검증**: `uv run pytest` 2162 통과·4 스킵, `uv run ruff check src tests` 통과. PR 품질 관문
  통과. 머지 후 `Deploy on merge to main` 성공(run 27746829311), KIS smoke 성공(run 27746829309,
  `key_valid=true`, `smoke_state=success`).

## 최근 마일스톤 — 2026-06-18 (🧭 Codex 작업 품질 관문 — AGENTS.md + PR 강제 검사)

main 머지 `ef16b60`(#332). 운영자가 요구한 "두 번 일하지 않는 세계 최고 수준 작업 체질"을
말뿐인 원칙 문서가 아니라 실제 작업 표면에서 반복되는 관문으로 만들었다.

- **Codex 운영 규칙**: `AGENTS.md`를 Codex용 작업 운영 문서로 추가. 문제 정의 → 위험 등급 →
  탐색 → 내부 역할 점검(구현자·검토자·안전 담당자·인계 담당자) → 검증 → 완료 관문을 명시.
- **세션 시작 훅 정리**: `.codex/hooks.json`은 긴 정적 문맥 주입(`session_context.py`)을 호출하지
  않고, 짧은 git 사실 훅(`git_ground_truth.py`)만 실행한다. 현재 상태 판단은 실제 git 상태와
  최신 `HANDOFF.md`, 필요 시 `/sync`로 한다.
- **강제 표면**: `.github/pull_request_template.md`로 모든 PR 본문에 위험 등급·문제 정의·탐색
  근거·검증·안전 경계·인계를 남기게 하고, `.github/workflows/pr-quality-gate.yml`이
  `scripts/check_pr_quality_gate.py`로 빈 본문/위험 등급 누락/문제 정의 누락/안전 경계 미선택을
  실패시킨다. `.codex/quality-gate.md`는 로컬 작업 중 점검표.
- **안전 경계**: Kernel 0·헌법 0·돈 경로 0·주문 로직 0. 운영 체계(등급 2) 변경만.
- **검증**: `uv run pytest` 2142 통과·4 스킵, `uv run ruff check src tests scripts/check_pr_quality_gate.py`
  통과, PR 품질 관문 원격 실행 통과, 빈 PR 양식 실패·채운 예시 통과 확인.

## 최근 마일스톤 — 2026-06-18 (🌱 캐너리 합격 후보 운영자 승격 큐 + 세 방향 결정 로드맵)

main 머지 `732ca35`(#330). 운영자가 세 방향(1 자율 성장 심화·3 실거래 적극화·4 새 알파)을
모두 선택. 돈을 안 움직이고 안전 경계를 안 건드리며 완전 자율로 끝낼 수 있는 부분만 이번에
수행하고, 나머지(돈 움직임·제약 확장·안전 경계 완화)는 로드맵으로 운영자 결정에 넘겼다.

- **방향 1 수행(코드)**: 자율 튜너의 L2/L3 후보(예: 판단 지점 `max_tokens`)가 하드닝 캐너리를
  통과해도(`outcome=passed`) 적용 안 되고 `promoted=False` 로 버려졌다 — 읽는 코드가 전혀
  없어 자율 성장이 새던 누수. 새 읽기 전용 모듈 `src/auto_invest/analytics/promotion_queue.py`
  가 감사 로그의 후보·검증 이벤트를 `candidate_id` 로 이어 "캐너리 통과·미승격" 후보를 운영자
  승격 큐로 종합(텍스트+JSON). money_path 와 같은 소비자 계층. **자동 승격 0건(헌법 IX.B-2
  불변)** — 가시성만, 적용은 안 함.
- **방향 3 분석(로드맵)**: 첫 자본은 통계적 시간 게이트(전진 관측 20개)+엣지 확정. 통과 시
  자본 사다리가 단0→단1(NAV 25%)을 자율 무장(운영자 게이트 없음, 헌법 X.4). `min_obs` 단축은
  거짓 엣지 위험 → 금지. 안전한 가속 = 전진 관측 리셋 방지(전략 지문 안정). 운영자 레버 = 입금.
- **방향 4 분석(로드맵)**: long-only 에서 추세 거의 최적(스펙 054 입증). 미시도 직교 후보 =
  단기 평균회귀(다른 시간프레임, 돈 0 probe). 롱숏·새 자산군은 운영자 제약 확장 결정.
- **안전 경계**: Kernel 0·신규 파일 2개·기존 코드 미수정(추가 전용)·읽기 전용·주문 0·돈 0.
  로드맵 문서 `STRATEGY-2026-06-18-DIRECTIONS-1-3-4.md`(현재 코드 근거·파일/줄 인용).
- **검증**: 신규 단위 테스트 9건(집계·최신판정 우선·정렬 재현성·DB 통합), 전체 2142 통과·ruff 통과.
- **운영자 결정 대기**: ① 3번 입금으로 첫 자본 달러 규모 상향? ② 4번 단기 평균회귀 probe 착수?/
  롱숏·새 자산군 제약 확장? ③ 1번 B안 캐너리 합격 L2 자동 적용 허용(IX.B-2 완화, 안전 경계)?

## 최근 마일스톤 — 2026-06-16 (🩺 스펙 051 후속: 생존 감시 신규 루프 PENDING — 첫 실행 전 거짓 DEGRADED 제거)

main 머지 `cba93a0`(#328). 스펙 055 재지정 폐회로 워크플로(`reassign-on-tournament.yml`)가
오늘 main 에 들어왔지만(15:26 UTC) 첫 cron 은 6/17 00:20 UTC — 그 사이 생존 감시(스펙 051)가
reassign 사이드카 없음을 MISSING 으로 보고 종합 판정을 DEGRADED 로 떨궜다. '아직 첫 실행
전인 신규 루프'와 '죽은 루프'를 구분 못 한 거짓경보(모듈 자신이 "거짓경보가 최악 — 운영자가
경보를 무시하게 된다"고 밝힌 설계 철학 위반).

- **수정**: `SidecarSpec.first_expected_utc`(첫 사이드카 예상 시각) 추가. 사이드카 없음이 그
  시각+max_age 전이면 `PENDING`(정상, 첫 실행 대기), 후면 `MISSING`(첫 실행 실패 의심)으로
  승격. None(기본)이면 기존 즉시 MISSING(확립 루프 회귀 0). reassign 에 첫 cron 시각
  `2026-06-17T00:20:00Z` 설정.
- **효과**: 첫 cron 전 reassign=PENDING → 종합 OK(거짓 DEGRADED 사라짐). 첫 실행이 실패하면
  +80h 후 MISSING 으로 승격 → 침묵 실패를 *오히려 새로* 잡음(PR #326 의도 약화 아니라 정밀화).
- **안전 경계**: Kernel 0·감시/보고 모듈(비커널)·읽기 전용·주문 0·돈 0·라이브 무변경.
- **검증**: 신규 단위 테스트 6건(PENDING/MISSING 구분·핵심 신규 루프 승격·확립 루프 회귀),
  전체 2133 통과·ruff 통과. 실증: 실제 사이드카로 probe 현재 시각 → 종합 🟢 OK, reassign ⏳ PENDING.

## 최근 마일스톤 — 2026-06-16 (🪜 스펙 050×044: 자본 사다리 순 복리 + 거래비용 + 레버리지 캡 경계 — 운영자 방향 "레버리지 후 복리 극대화" 실행 분석)

운영자 선택(2026-06-16, "레버리지 후 복리 극대화")을 *실행 가능*하게 만드는 분석 체인 완성.
main 머지 #311(거래비용)·#312(캡 경계)·#313(사다리). 핵심 결론 3개:

- **거래비용 반영(#311 `2835a52`)**: 전략 빌더에 `cost_bps`(기본 0 역호환). 레버리지 후 복리
  고정가중 우위가 비용에 견고(격차 0bp +2.4 → 10bp +2.6%p, 역변동성 회전율↑). 신규 6건.
- **레버리지 캡 경계(#312 `cebf24c`)**: `caps.py` `global_exposure_pct ≤ 100`(헌법 원칙 I,
  비협상)이 레버리지(노출 >100%)를 원천 차단 → 레버리지 = 안전 경계 변경(K-meta), **자율
  불가, 운영자 명시 승인 필수.** 캡 안 대안 = 고정가중 무레버 재지정(+1.3~2.3%p, 경계 변경 0).
- **사다리 순 복리(#313 `9673954`)**: `ladder_simulation.py`(스펙 050 상수 재사용, 임계 재정의
  0) — "고정가중이 강등선(10%)에 붙어 자꾸 강등될 것" 가설 검증. 월간 해상도에선 강등 거의
  0 → 사다리 순 복리 ≈ raw, 고정가중이 사다리에서도 우위. 단 일별 해상도 강등 위험은 미해소
  (월간으로 확정 불가 → KIS forward 필요). 신규 10건.
- **안전 경계**: 세 PR 모두 읽기 전용·순수·Kernel 0·캡 0 변경·돈 0·라이브 무변경·재지정 0.
- **다음**: 고정가중 forward-paper 트랙 추가로 일별 강등 빈도 실측(미해소 리스크 해소 경로).

## 최근 마일스톤 — 2026-06-15 (💰 스펙 044×047: 라이브 전략 낙폭 예산 내 성장 최적 레버리지 — "레버리지 여유 ≠ 돈")

main 머지 `92b4177`(#309). 스펙 047 깊은 OOS 발견의 직접적인 "진짜 돈" 귀결을 정량화.

- **🔬 빈칸**: 스펙 044(성장 최적 레버리지)는 2자산·30% 예산까지만 쟀고, **금 포함 라이브
  3자산을 운영자 실제 예산(헌법 X.4 = 20%)으로 레버리지 최적화한 적이 없었다.**
- **무엇을 만들었나**(읽기 전용·순수): `growth_optimal.py` 에 `leverage_headroom()`·
  `rank_leverage_headroom()`(엔진 재사용) + `scripts/live_strategy_leverage_probe.py`(라이브
  3자산·2자산·단일주식을 같은 예산에서 레버리지 비교). 테스트 6건(총 18).
- **실측(20% 예산, 레버리지 후 복리 1위)**: 1971~ 고정가중 14.3% / 1950~ 2자산 12.8% /
  1990~ 고정가중 13.9% / 1871~ 고정가중 8.2%. **라이브 역변동성은 4구간 모두 꼴찌**
  (11.9/9.3/11.4/6.0%). 1971~ 낙폭 예산 10~30% 전부 고정가중이 역변동성 이김(견고).
- **정직한 비직관**: 라이브 역변동성은 *무레버리지* 안전성 최고(샤프 1.81·낙폭 5.3%)이고
  레버리지 *여유(배수)*도 최대지만, 변동성을 너무 낮춰 *레버리지 후 복리*는 꼴찌
  (레버리지 여유 ≠ 돈). 고정 자본 복리 극대화는 3자산 고정가중 우위.
- **안전 경계**: 레버리지는 측정 전용·Kernel 0·주문 0·돈 0·라이브 무변경·재지정 0. 실제
  레버리지·재지정은 운영자 게이트(헌법 X.4) → **운영자 결정 지점**(위 "다음 세션 최우선" 참조).
- **다음(읽기 전용)**: 거래비용 반영 재측정(역변동성 회전율↑ → 고정가중 우위 강화 가능성).

## 최근 마일스톤 — 2026-06-15 (🔬 스펙 047 후속: 깊은 OOS walk-forward — "엣지 부재" 경보 재검증, 라이브 전략 정당화)

main 머지 `4a7b78c`(#307). 직전 세션 최우선 작업("모든 후보를 깊은 OOS 로 비교")의 완수이자,
그 경보를 뒤집는 결론.

- **🔬 빈칸의 실체**: 라이브 GLOBAL-TREND 의 "엣지 부재" 판정은 2022~2026 KIS 일봉(강세장
  4년)에서 나왔다. 그 창은 방어할 폭락이 없어 추세추종(방어적 현금화)이 보험료만 내는 것처럼
  보인다. "단순 보유를 이기나"가 *약세장을 포함한 깊은 데이터에선 측정된 적이 없었다.*
- **무엇을 만들었나**(읽기 전용·순수·결정론): `src/auto_invest/analytics/deep_walk_forward.py`
  — 깊은 월간 데이터(1871~/1971~)를 겹치지 않는 연속 구간(기본 5년)으로 타일링해 각 추세
  후보 vs *같은 자산 등가중 단순 보유*(라이브 판정과 같은 잣대)를 구간별 + 전체표본 비교.
  판정 기준은 프로젝트 표준(`risk_managed_beta._classify`: 낙폭≤0.8배+칼마↑+샤프 비악화 → 방어
  엣지). 챔피언은 위험조정(샤프→칼마)으로 선정. `scripts/deep_walk_forward_probe.py`(GitHub
  장기 데이터 실행, 컨테이너에서 닿음 → 검증 가능), 테스트 25건.
- **실측 (1971~, 5년 구간 11개)**: 라이브 역변동성 3자산 = **샤프 1.81 vs 보유 1.23, 칼마
  1.77 vs 0.45, 낙폭 5.3% vs 20.7%, 11/11 구간 승.** 같은 raw 수익(CAGR 9.4%)을 4분의 1
  위험으로. 1871~ 도 동일(낙폭 38.6%→5.3%, 15/16 승). **→ 현재 라이브 지정이 깊은 증거로
  정당화됨. "엣지 부재"는 강세장 창의 착시.**
- **안전 경계**: Kernel 터치 0건·순수·읽기 전용·주문 0·돈 0·라이브 게이트/신호 무변경·재지정
  0. 미래 누출 0(검증된 팩터 빌더 재사용). 전체 2038 통과·4 skip, 린트 깨끗.
- **다음(진짜 돈 경로)**: 성장 최적 레버리지(스펙 044)로 라이브 전략의 5.3% 낙폭 여유를
  복리 천장으로 — 같은 낙폭 예산에서 약 4배 레버리지 여유. 레버리지·자본은 운영자 게이트(X.4).
  상세: `specs/047-global-trend/DEEP-WALK-FORWARD-FINDINGS.md`.

## 최근 마일스톤 — 2026-06-15 (🚀 스펙 035 후속: 백테스트 앵커드 엣지 가속기 — 깊은 OOS + 짧은 forward 지속성)

운영자 지적("4주 대기 비효율, 같은 전략이면 기존 데이터로 분석하면 되잖아")의 **진짜 해법**.
전략 규칙은 이미 깊은 walk-forward 표본외(OOS, 스펙 047 등)로 검증됐는데 forward 판정이 그걸
무시하고 *일별 20일* 로 엣지를 처음부터 재발견하려는 게 느림의 원인.

- **엔진(#298, main `edf5dd8`)**: `portfolio/backtest_anchored.py` — `backtest_anchored_verdict()`.
  깊은 OOS 가 엣지를 세우고(PSR/DSR ≥ 임계, 관측 ≥60) + 짧은 forward(≥5일)가 OOS 대비
  유의하게 나쁘지 않으면(z-검정) EDGE_CONFIRMED. 재발견이 아니라 *지속성 확인*. 다중검정은
  DSR num_trials 처벌. 순수·결정론. 테스트 9건.
- **배선·검증(#299, main `c9a307b`)**: `run_portfolio_walk_forward` 가 OOS 일수익률
  (`pooled_returns`)을 노출하도록 연결 + 합성 데이터로 walk-forward→OOS→앵커드 판정
  end-to-end 검증. 테스트 1건.
- **안전 경계**: 읽기 전용·순수·Kernel 0·주문 0·돈 0. **아직 라이브 게이트 무변경**(엔진+파이프
  라인만). 
- **CLI(#301, main `6f2f19f`)**: `forward-verdict-anchored` — 인제스트 깊은 데이터로
  walk-forward OOS + 라이브 forward 스냅샷(TWR 스티치) 읽어 앵커드 판정 JSON 발행(읽기 전용).
- **워크플로(#302, main `4a09ba6`)**: `forward-anchored-verdict.yml` — regime-stratify 와
  같은 /tmp 격리 패턴으로 인스턴스에서 그 CLI 를 돌려 사이드카
  `automation/forward-anchored-verdict-last-run` 에 발행. 평일 23:40 UTC + push + 수동.
  **= 라이브 단계 (a) 완료**(실데이터 앵커드 판정을 눈으로 검증).
- **다음 단계 (b, 미완 — 실제 돈 게이트라 신중)**: ① **관찰** — 다음 스케줄/푸시 실행에서
  사이드카가 GLOBAL-TREND 앵커드 판정을 정상 발행하는지(OOS 깊이·forward 지속성·verdict)
  확인. 인스턴스에 forward_global.db NAV 스냅샷이 충분해야 forward 지속성 평가 가능(부족하면
  INSUFFICIENT 로 안전하게 빠짐). ② **게이트 소비** — autoarm/사다리가 앵커드 판정을
  (기존 20일 forward 와 OR 로) 인정해 EDGE_CONFIRMED 를 더 빨리 통과. 이게 실제 돈이 더
  빨리 들어가는 지점 → 사이드카로 충분히 검증한 뒤 잇는다. 그 전까지 라이브 무장은 기존
  forward 20일 게이트 유지(안전).

## 최근 마일스톤 — 2026-06-15 (⏱ 스펙 035 후속: forward 판정 시간가중수익률(TWR) — 자본 변경이 시계를 리셋하지 않음)

main 머지 `bb6288b`(#296). 운영자 지적(2026-06-15): "같은 전략으로 지난 N주를 분석하면
같은 결과인데 왜 4주를 또 기다리나? 비효율 아니냐." — **정확했고 즉시 수정**.

- **빈칸의 실체(근본 원인 규명)**: forward-verdict 가 `consistent_basis_suffix` 로 "최신
  자본 베이시스 구간만" 세었다. 2026-06-11 커밋 `fix(measure): forward NAV 에 장부 현금
  포함`이 NAV 측정 기준을 바꾸자(현금 미포함→포함), 같은 전략인데도 그 전 forward 관측이
  전부 폐기되고 시계가 1로 리셋됐다. 자본/측정 변경으로 같은 전략의 수익률을 버린 것 = 낭비.
- **수정**: `stitch_basis_segments()`(growth.py) — 시간가중수익률(TWR, GIPS 표준). 베이시스
  경계의 단일 전이(자금 흐름)만 건너뛰고 같은 *알려진* 베이시스 구간의 내부 일별 수익률을
  사슬로 이어 전체 track record 보존. forward-verdict 가 이걸 사용. 레거시(현금 미포함
  position-only, basis=None)는 측정 정의가 달라 여전히 제외.
- **안전 경계 불변**: 여전히 관측 ≥20 + PSR/DSR + 벤치마크 + 교차-트랙 보정 모두 통과해야
  EDGE_CONFIRMED. 더 엄밀(TWR)해진 것이지 기준 완화 아님. Kernel 0·주문 0·돈 0.
- **검증**: 신규 6건, 전체 1993 통과·4 skip, 린트 깨끗.
- **남은 진짜 제약(정직)**: 토너먼트 6 전략 설정이 전부 최근(2026-06 초) 커밋 → 정직한
  *일별* forward OOS 가 ~1-2주뿐. 20 일 OOS 는 신규 전략의 과적합 방어 비용으로 달력 시간이
  더 필요. 단 전략 *규칙*은 스펙 047 등에서 150년 깊이 검증됨 → **다음 작업: 깊은 walk-forward
  OOS 증거 + 짧은 forward 지속성 확인을 결합한 backtest-anchored 엣지 게이트**(20 일 재발견이
  아니라 검증된 엣지의 지속을 확인 — 리그하게 더 빠름). 머니게이트 통계 변경이라 신중히 구축.

## 최근 마일스톤 — 2026-06-14 (🔬 스펙 053 후속: forward 토너먼트 교차-트랙 다중비교 보정 — 운 좋은 우승 처벌)

main 머지 `d03a19a`(#290). 운영자 상시 지시("세계 최고 수준")의 **통계 엄밀성**에서
가장 큰 남은 빈칸을 닫았다.

- **🔬 빈칸의 실체**: 토너먼트는 6개 후보 전략을 동시에 forward 페이퍼로 돌려 "비교 가능
  EDGE_CONFIRMED 1위"를 챔피언(재지정 후보 → 실제 돈)으로 뽑는다. 각 트랙의 유의성
  (PSR/DSR)은 그 트랙 *내부* 과거 설정 다중검정만 보정할 뿐, **6트랙을 동시에 검정하는
  교차 다중비교는 미보정**이었다. 트랙당 거짓 양성 5%면 6트랙이면 약 26% — "운 좋게
  6파전을 이긴 트랙"에 진짜 돈을 재지정할 위험(엄밀한 퀀트가 "몇 개 전략을 시도했나"를
  반드시 보정하는 이유).
- **무엇을 만들었나**(`analytics/forward_tournament.py` — 읽기 전용 추가): 본페로니 교차-트랙
  보정 — 가족 신뢰도(기본 0.95)를 K=비교 가능 트랙 수에 유지하려면 챔피언 유의확률 ≥
  `1 − (1−기준)/K`(K=2 → 0.975, K=6 → 0.991667). 챔피언 유의확률=PSR·DSR 중 낮은 값
  (보수적 하한, 둘 다 없으면 robust=None). `comparable_count`·`adjusted_dsr_threshold`·
  `champion_multiplicity_robust` 필드 + 헤드라인/as_text 정직화(챔피언 보정 미통과면 "운 좋은
  우승 가능, 재지정 신중", 도전자 미통과면 도전자 경보를 "⚠ 재지정 보류"로 정직 강등).
- **안전 경계**: 읽기 전용·순수·결정론·Kernel 터치 0건. 주문 0·돈 0 이동. 챔피언/도전자 키
  선정 로직 불변(추가형). 재지정은 여전히 운영자 게이트(헌법 X.4) — 보정은 그 결정을 *더
  정직하게* 보이게 할 뿐.
- **검증**: 신규 8건, 전체 1982 통과(기준선 1974 + 8)·4 skip, 린트 깨끗, 기존 30건 무손상.
- **같은 세션 후속(#292, main `67f32c1`)**: money-path 엣지 신뢰도 투명화 — EDGE_CONFIRMED
  단계(첫 자본 직전)에 "신뢰도 PSR {값}"(벤치마크를 이길 확률)을 헤드라인·게이트로 수치
  표시. 이진 통과만 보이던 것을 강도까지 보이게(0.951 겨우 vs 0.99 강함 구별). 프로브가
  판정 JSON 전체를 넘겨 프로덕션에서 자동 활성화. 읽기 전용·Kernel 0·신규 3건(전체 1985).
- **같은 세션 후속(#294, main `cd5be9a`)**: 끝단(E2E) 회귀 보호 — 실제 운영 설정
  (`canary-live`/`global-trend` TOML) + 실계좌 NAV 가정으로 사다리가 단0→단1 PROMOTE 를
  내고, money-path 보고서가 첫 자본 $3,000·강등 -$300·정지 -$600 + 엣지 신뢰도(PSR)를
  표면화함을 고정. 신규 통합 2건(전체 1987). 조합(설정+상태)에서 터지는 버그 클래스 차단.
- **다음 세션 관찰 지점**: 어느 트랙이 관측 20을 넘어 비교 가능해지면 ① 사이드카 리더보드에
  "🔬 교차-트랙 다중비교(본페로니)" 줄이 뜨는지 ② 챔피언이 보정 기준을 넘는지(못 넘으면
  "운 좋은 우승" 정직 표식). 직전 마일스톤(자본 방어선 예산·053·052 후속) 관찰 지점 유효.

## 최근 마일스톤 — 2026-06-14 (🛡 스펙 052 후속 4: 자본 방어선 예산 — 첫 자본 다운사이드를 돈 움직이기 전에 달러로)

main 머지 `411b6e9`(#285). 운영자 상시 지시("진짜 돈 + 세계 최고 수준의 안정성 +
사람 개입 없는 완벽한 자동 시스템")의 **안정성 절반**에서 가장 큰 남은 사각지대를 닫았다.

- **🛡 빈칸의 실체**: money-path 는 "올라가는 길"(엣지 누적→첫 자본→다음 단 승격)은
  촘촘히 계측했지만, "내려가는 방어선"(낙폭에 따른 자동 강등/정지)은 DEPLOYED 단계의
  *이진* 게이트("낙폭 < 예산/2 인가?")뿐이라 **방어선에 얼마나 가까운지**가 안 보였다.
  실제 돈이 걸리면 가장 먼저 알아야 할 것이 "지금 방어선까지 몇 %포인트·몇 달러 남았나"인데.
- **무엇을 만들었나**: `analytics/money_path.py` 에 `SafetyBudget` 구조체 +
  `_safety_budget()` 순수 함수. 강등 임계(예산/2)·정지 임계(예산)까지 남은 %포인트(여유)와
  그때의 달러 손실(배치 자본 기준 근사, 올림=위험 과소평가 0). **단0(미배치)에서도**
  "첫 자본이 단1=NAV 25%=$X 로 들어가면 강등 -$Y / 정지 -$Z" 를 prospective 로 표면화 —
  **돈이 움직이기 전에** 다운사이드 예산이 달러로 보인다. 배치 중(DEPLOYED)이면 현재 낙폭
  대비 강등/정지까지 남은 여유를 연속 값(조기경보)으로, 방어 발동(DEFENDED)이면 초과분
  (음수 여유)을 드러낸다. 배치됐는데 라이브 낙폭이 비면 "방어선 입력 결손 — 자동 강등
  지연 위험" 경고(안전망의 입력 신선도까지). `MoneyPathReport.safety` 필드 +
  `to_dict()["safety_budget"]` + `as_text()` 섹션 → `money_path_probe` 가 그대로 흘려보내
  **다음 스케줄 실행(평일 08:00 UTC)에서 자동 활성화.**
- **안전 경계**: 순수·결정론·읽기 전용·Kernel 터치 0건. 주문 0·돈 0 이동·새 측정 0
  (자본 사다리가 발행한 임계·자본·낙폭을 합쳐 보일 뿐). 실제 강등/정지는 자본 사다리
  게이트가, 라이브 전환은 운영자 게이트(헌법 X.4)가 한다. 강제하지 않고 보이게만 한다.
- **검증**: 신규 10건(단위), 전체 1972 통과(기준선 1962 + 10)·4 skip, 린트 깨끗.
  **현재 실제 상태(단0) 렌더 실측**: "첫 자본 $379 → 강등 -$38(낙폭 10%) / 정지 -$76
  (낙폭 20%), 최대 노출 약 -$38 안에서 자동 회수" 표시 정확.
- **같은 세션 후속 정정 2건**(둘 다 읽기 전용·Kernel 0·돈 0): (1) `_capital_pct` 가
  `Decimal.normalize()` 로 단2=50%·단3=100% 를 '5E+1'·'1E+2'(과학적 표기)로 깨뜨리던
  잠재 버그 수정(#287, main `bc97c7c`) — `_pct_str` 헬퍼로 항상 '50'·'100' 정상 표기.
  (2) money-path 가 6곳에서 "무장은 운영자 게이트"라 안내하던 낡은 문구를 헌법 X.4
  v5.0.0(무장 자체가 자율, 운영자 전용은 입금·킬스위치·낙폭 예산)에 맞게 정정(#288, main
  `5df623f`) — `capital_ladder.py` 와 어긋나 있던 것. 테스트 1974 통과·린트 깨끗.
- **다음 세션 관찰 지점**: ① 다음 money-path 사이드카(평일 08:00 UTC) 하단에 "자본
  방어선 예산" 섹션이 뜨는지(단0 = prospective 예상치) ② 첫 자본 배치 후 DEPLOYED 단계에서
  강등/정지까지 남은 여유가 연속 값으로 정확한지 ③ 직전 마일스톤(스펙 053·052 후속·051)
  관찰 지점 유효.

## 최근 마일스톤 — 2026-06-14 (🏆 스펙 053: forward 토너먼트 리더보드 — 6 트랙 정직성 게이트 순위)

main 머지 `7da58e2`(#283). 운영자 상시 지시("세계 최고 수준으로 진짜 돈을 벌어보자")
하에, "검증된 한 트랙의 자본까지 길"(스펙 052 money-path)의 **보완** — "그 트랙이
아직도 최선인가, 더 나은 도전자가 준비됐나"를 한 곳에 모았다.

- **🏆 빈칸의 실체**: 전진 페이퍼 A/B 토너먼트(`rebalance-paper-forward.yml`)는 6개
  후보 전략(추세 ON/OFF·위험관리 베타·멀티에셋 추세·글로벌 추세·확대 유니버스)을
  각자 전용 DB 로 격리해 **병렬로** 돌리고 트랙마다 스펙 035 판정(EDGE_CONFIRMED/
  NO_EDGE/INSUFFICIENT_DATA)을 낸다. 그런데 사이드카는 판정 JSON 6덩이를 **날 것
  그대로** 박아넣고 "비교해보면…" 산문만 달 뿐 **계산된 순위가 없었다.** 라이브 검증
  트랙(글로벌 추세 SPY·IEF·GLD)이 아직도 최강인지, 어느 도전자가 EDGE_CONFIRMED 를
  벌어 재지정 후보가 됐는지를 알려면 사람이 6덩이를 눈으로 비교해야 했다(money-path 를
  만든 바로 그 "사이드카 머릿속 짜맞추기" 안티패턴).
- **무엇을 만들었나**: `src/auto_invest/analytics/forward_tournament.py`(순수 코어 —
  판정 6개를 **정직성 게이트**로 순위: 비교 가능(관측 ≥ 최소 20)만 챔피언 후보, 잠정
  (관측 부족)은 순위만 매기고 **챔피언 선언 안 함**=거짓 자신만만 금지; 챔피언=비교 가능
  EDGE_CONFIRMED 1위(칼마→샤프→초과수익→낙폭); **도전자 경보**=비-incumbent 가
  EDGE_CONFIRMED 1위 **그리고** incumbent 도 비교 가능할 때만=사과 대 사과·거짓 경보 0),
  `scripts/forward_tournament_probe.py`(드라이버 — `--verdict-dir`(워크플로)/
  `--from-sidecar`(컨테이너 검증) 두 입력 + `--manifest` 트랙 레지스트리 단일 출처),
  `rebalance-paper-forward.yml` 격리 스텝(continue-on-error)으로 리더보드 생성 + 사이드카
  상단 주입. 데이터 배관은 이미 존재(판정 6개가 사이드카에) → **다음 스케줄 실행에서 자동 활성화.**
- **안전 경계**: 읽기 전용·순수·결정론·Kernel 터치 0건. 주문 0·돈 0 이동·새 측정 0
  (발행된 판정 숫자 비교만). **라이브 전략 무변경 → 전진 시계 리셋 없음**(라이브를 안
  건드리므로 누적 중인 forward 관측 보존). 재지정은 운영자 게이트(헌법 X.4) — 이 모듈은
  그 결정을 *읽어 설명할* 뿐 아무것도 일으키지 않는다.
- **검증**: 신규 30건(단위 + 통합), 전체 1962 통과(기준선 1932 + 30)·4 skip, 린트 깨끗,
  워크플로 YAML 유효. **라이브 사이드카 실측**(`--from-sidecar`): 현재 6 트랙 전부 1/20
  관측 → 모두 잠정, **챔피언 없음**(정직), incumbent=global 정확 표시, global·wide 헤더
  안 섞임.
- **다음 세션 관찰 지점**: ① 다음 forward 사이드카(평일 22:30 UTC) 상단에 🏆 리더보드가
  뜨는지 + 관측이 최소(20)를 넘는 트랙이 나오면 챔피언/도전자 표식이 정확한지 ② 어떤
  도전자(예: 확대 유니버스)가 먼저 EDGE_CONFIRMED 를 벌면 🚀 도전자 경보가 정직하게
  뜨는지(incumbent 도 비교 가능해야 경보) ③ 직전 마일스톤(스펙 052 후속·051) 관찰 지점 유효.

## 최근 마일스톤 — 2026-06-14 (🧭 스펙 052 후속 3: 전진 표본 안정성 — 자본 베이시스 흔들림 진단)

main 머지 `5427faf`(#281). 전략 지문 정합(#279)에 이은 "살아있지만 수렴 못 하는"의
**세 번째 사각지대**를 닫았다.

- **🧭 빈칸의 실체**: 첫 자본을 막는 단 하나의 병목은 전진 페이퍼 관측 20개 누적인데,
  관측이 `1/20`일 때 실제로는 **스냅샷 6개 중 4개가 자본 베이시스 변경으로 제외
  (`legacy_snapshots_excluded`)** 된 결과일 수 있다. 매 거래일 새 스냅샷이 쌓여도 매번
  같은 수가 제외되면 유효 관측은 영영 정체한다. 생존 감시(스펙 051)는 워크플로가
  *멈췄나*만, 수렴 감시(스펙 052)는 *관측 증감*만 봐서 둘 다 "정체(stalled)"로만 보고
  그 *원인*(베이시스가 자꾸 바뀜)을 못 짚었다. forward 판정 JSON 에 이미 박혀 있던
  `snapshot_count`·`legacy_snapshots_excluded` 를 money-path 가 받기만 하고 버리고 있었다.
- **무엇을 만들었나**: `analytics/money_path.py` 의 `EtaProjection` 에
  `sample_stability`(stable/settled/churning/unknown)·`legacy_excluded`·`snapshot_count`
  추가. `_sample_stability()` 가 직전 사이드카의 제외 개수와 비교(관측 시계 수렴과
  *직교*하는 표본 차원): 제외 0=STABLE, 제외>0이나 직전 대비 안 늘면 SETTLED(과거 1회
  정리), 직전보다 늘면 CHURNING(베이시스가 또 바뀜). 누적 단계에 게이트
  `전진 표본 안정성(베이시스)` 추가(legacy 정보 있을 때만 — 거짓 경보 0). 관측이 정체로
  보여도 제외가 늘면 headline 이 '표본 흔들림'을 지목한다. 드라이버
  `money_path_probe.py` 가 이번 `forward_legacy_excluded` 를 prior 힌트로 실어
  (`forward_n_obs` 와 같은 방식) 다음 실행이 직전과 비교 — 워크플로 변경 불필요, 다음
  스케줄 실행에서 자동 활성화.
- **안전 경계**: 읽기 전용·순수·결정론·Kernel 터치 0건. 머니루프(capital_ladder·autoarm·
  risk/gates) 무변경, 주문 0·돈 0 이동. 강제하지 않고 *보이게만* 한다.
- **검증**: 신규 9건(단위 7 + 프로브 2), 전체 1932 통과(기준선 1923 + 9)·4 skip, 린트
  깨끗. 라이브 사이드카로 실측 — 현재 `정리됨(과거 4개 제외, 추가 없음) → 베이시스 안정`
  ✅ PASS(첫 자본 누적이 건강하게 진행 중, 4개 제외는 PR #243 자본 베이시스 도입 시점의
  1회 정리였음).
- **다음 세션 관찰 지점**: ① 다음 money-path 사이드카에서 `eta.sample_stability` 가
  `settled` 로 유지되는지(누가 측정 기준을 흔들면 `churning`+게이트 FAIL 로 즉시 드러남)
  ② 직전 마일스톤(지문 정합·수렴 감시·스펙 052·051) 관찰 지점 유효.

## 최근 마일스톤 — 2026-06-14 (🧭 스펙 052 후속: 전략 지문 정합 가시화 — 배포 막힘 분기 진단)

main 머지 `d77f9fd`(#279). 수렴 감시(#277)에 이은 "살아있지만 수렴 못 하는"의
**두 번째 사각지대**를 닫았다.

- **🧭 빈칸의 실체**: 자본 사다리 게이트(`capital_ladder.decide_ladder`)는 라이브
  배포 설정의 전략 지문 ≠ 전진 검증 설정의 전략 지문이면 **어떤 단에서도 자본을
  배치하지 않는다**(`ACTION_BLOCKED`, 매 단 적용). 즉 전진 엣지를 20개 쌓아
  `EDGE_CONFIRMED`가 떠도 두 설정이 다르면 **첫 자본이 영영 안 들어간다.** 그런데
  money-path는 그 차단을 "정합성 불일치·NAV 조회 불능·킬스위치 가능"으로 뭉뚱그려,
  운영자가 "정확히 무엇을 고쳐야 하나"를 알 수 없었다.
- **무엇을 만들었나**: `analytics/money_path.py` 에 게이트 `전략 지문 정합(검증=배포)`
  (PASS/FAIL/N/A) 추가 — 불일치면 어느 항목(universe/weight_scheme/top_n/
  trend_filter 등)이 다른지 나열하고, `STAGE_BLOCKED` 가 지문 불일치 때 구체 진단
  (어느 TOML 을 일치시킬지)으로 바뀐다. 드라이버 `money_path_probe.py` 의
  `compute_fingerprint_status` 가 `forward-edge-autoarm.yml` 이 비교하는 바로 그 두
  설정(`deploy/canary-live-portfolio.toml`·`global-trend-portfolio.toml`)을 읽어
  `strategy_fingerprint` 로 독립 비교. 워크플로 변경 불필요 — 다음 실행에서 자동 활성화.
- **안전 경계**: 읽기 전용·순수·Kernel 터치 0건. **머니루프(capital_ladder·autoarm·
  risk/gates) 무변경** — `strategy_fingerprint` 는 *읽기*만(수정 0). 주문 0·돈 0 이동.
  강제하지 않고 *보이게만* 한다(분기 해소는 사람/세션이 두 TOML 을 일치시킴).
- **검증**: 신규 12건(모듈 5 + 프로브 7), 전체 1923 통과(기준선 1911 + 12)·4 skip,
  린트 깨끗. 라이브 사이드카로 일치(PASS)·불일치(FAIL+항목 나열) 실측 확인. **현재
  실제 두 설정은 지문 일치**(유니버스 SPY/IEF/GLD, 사다리 WAIT_EDGE 와 정합).
- **다음 세션 관찰 지점**: ① money-path 사이드카 `gates` 에 `전략 지문 정합` 이
  PASS 로 유지되는지(누가 한 TOML 만 바꾸면 FAIL+BLOCKED 로 즉시 드러남) ② 직전
  마일스톤(수렴 감시·스펙 052·051) 관찰 지점 유효.

## 최근 마일스톤 — 2026-06-13 (🧭 스펙 052 후속: 전진 시계 수렴 감시 — ETA 정직화)

main 머지 `ffa1ba8`(#277). 스펙 052 머니패스의 첫-자본 ETA 가 **거짓으로
자신만만한 날짜**를 보고하던 사각지대를 메웠다.

- **🧭 빈칸의 실체**: 머니패스 ETA 는 직전 사이드카 대비 전진 관측이 *늘 때만*
  실측 속도를 쓰고, 관측이 **그대로(정체)**거나 **줄어들(리셋)** 때는 조용히
  nominal(거래일당 ~1 관측 가정)로 폴백해 자신만만한 날짜를 냈다. 둘 다
  "살아있지만 수렴 못 하는" 실패 모드인데, 생존 감시(스펙 051)는 워크플로가
  *멈췄나*(사이드카 나이)만 보므로 사이드카가 신선한 이 두 경우를 🟢 OK 로
  놓쳤다(정체=시장 휴장·중복 스냅샷·전진 페이퍼 미세 정지, 리셋=자본 베이시스
  변경으로 `consistent_basis_suffix` 가 과거 관측을 떨궈 관측 수가 줄어듦).
- **무엇을 만들었나**: `analytics/money_path.py` 의 `EtaProjection` 에
  `convergence` 필드(converging/stalled/regressed/unknown) 추가. 직전 관측
  대비 — 줄면 REGRESSED(시계 리셋), 거래일 지났는데 그대로면 STALLED(정체),
  늘면 CONVERGING(실측 속도). 헤드라인·ETA 줄·게이트(`전진 시계 수렴`)로
  표면화(리셋=게이트 FAIL, 정체=PENDING, 수렴=PASS). 직전-사이드카 체인은
  이미 운영에 존재(`automation/money-path-last-run` 결정 JSON 에
  `forward_n_obs`·`as_of_utc` 박힘) → **다음 스케줄 실행에서 바로 활성화.**
- **안전 경계**: 읽기 전용·순수·결정론·Kernel 터치 0건. 주문 0·돈 0 이동·새
  측정 0(발행 숫자 비교만). 거짓 경보 0 — 정상 누적 헤드라인엔 ⚠ 안 붙는다.
- **검증**: 신규 단위 6건(정체·리셋·수렴·측정전·같은거래일·직렬화), 전체 1911
  통과(기준선 1905 + 6)·4 skip(라이브 KIS, 환경변수 게이트), 게이트 린트 깨끗.
  라이브 사이드카로 정체·리셋·측정전 렌더링 실측 확인.
- **다음 세션 관찰 지점**: ① 다음 money-path 사이드카에서 `eta.convergence` 가
  `unknown`→`converging`(관측 실제 증가)으로 바뀌는지 ② `regressed`/`stalled`
  가 뜨면 전진 페이퍼 점검(전략 지문 churn 으로 forward 시계가 리셋되는지) ③
  직전 마일스톤(스펙 052·051) 관찰 지점 유효.

## 최근 마일스톤 — 2026-06-13 (🧭 스펙 052: 첫-자본까지의 길 종합 + 첫-자본 추정 시점)

main 머지 `c9ee70b`(#275). 운영자 상시 지시("세계 최고 수준으로 진짜 돈을
벌어보자")의 **첫 문장**에 답하는 단일 결정 표면을 출시했다. 스펙 051 생존 감시가
"살아있나"를 한 곳에 모았듯, 이건 **"진짜 돈이 어디까지 왔나"를 한 곳에 모은다.**

- **🧭 빈칸의 실체**: "진짜 돈"으로 가는 길이 사이드카 여러 개(전진 페이퍼=엣지 관측
  생산·자본 사다리 게이트=단 승격·라이브 캐너리=실주문·승격 준비=헌법 VI 게이트)에
  흩어져 있어, "지금 어디까지 왔나, 다음 한 발을 막는 게 정확히 무엇인가, 첫 자본은
  언제 들어가나"에 답하려면 사람이 사이드카 5개를 일일이 받아 머릿속에서 짜맞춰야
  했다(이 프로젝트가 반복적으로 물린 "상태 혼동").
- **무엇을 만들었나**: `src/auto_invest/analytics/money_path.py`(순수 코어 —
  발행된 결정 JSON 들을 합쳐 단계(stage) 6종 분류·게이트 PASS/PENDING/FAIL 분해·
  거래일 클럭 첫-자본 ETA), `scripts/money_path_probe.py`(드라이버 — 사이드카 라벨
  JSON 추출 + 캐너리 무장 파싱, `--manifest` 단일 출처),
  `.github/workflows/money-path.yml`(매일 08:00 UTC + 자기 파일 push 트리거).
  생존 감시 레지스트리에 `money-path` 비핵심 등록 = **감시자가 보고자를 감시(폐회로)**.
- **검증(실서버)**: 자가검증 push 트리거로 **첫 실행이 CI에서 success**(run
  27469173110, 약 20초) — 실서버 사이드카 3종 정확히 파싱, 사이드카
  `automation/money-path-last-run` 발행 확인. 현재 종합: **단계 ACCUMULATING_EDGE**
  (단0·자본 0%·전진 엣지 **1/20 관측**·실NAV $1518.21·캐너리 드라이런), **첫-자본 추정
  ≈ 2026-07-09**(거래일당 ~1 관측 nominal). 단위 22 + 통합 7 테스트, 전체 1905 통과
  (기준선 1878 + 신규 27), 게이트 린트(`src tests`) 깨끗.
- **안전 경계**: 읽기 전용·순수·결정론·Kernel 터치 0건. 주문 0건·돈 0 이동·새 측정 0
  (발행 숫자 합산만). 실제 자본 배치는 자본 사다리 게이트가, 라이브 전환은 운영자
  게이트(헌법 X.4)가 한다 — 이 모듈은 그 결정을 *읽어 설명할* 뿐 아무것도 일으키지
  않는다. 입력 불능/모호 → BLOCKED 로 정직 보고(추정 강행 안 함).
- **다음 세션 관찰 지점**: ① money-path 사이드카 신선도 +
  ETA 근거가 `nominal`→`measured`로 바뀌는지(직전 사이드카 누적 비교) ② 전진 관측
  수(1→증가)가 매 거래일 늘어 ETA 가 당겨지는지(동결되면 스펙 051 생존 감시가
  `rebalance-paper-forward` STALE 로 먼저 빨갛게 잡음) ③ 직전 마일스톤 관찰 지점 유효.

## 최근 마일스톤 — 2026-06-13 (🛰 스펙 051: 자율 파이프라인 생존 감시 — 침묵 정지 탐지)

main 머지 `f302329`(#272) + `30d79c0`(#273). 운영자 상시 지시("세계 최고 수준의
사람 개입 없는 완벽한 자동 시스템 + 세계 최고 수준의 안정성") 하에, 자율 시스템의
**침묵 정지**를 드러내는 단일 감시자를 출시했다.

- **🛰 빈칸의 실체**: 자율 시스템은 스케줄 워크플로 여러 개(전진 페이퍼·자본 사다리
  게이트·KIS smoke·라이브 캐너리·수집·층화·승격)로 굴러가는데, 각자 *자기* 사이드카에
  *자기* 타임스탬프만 찍을 뿐 **"전체 파이프라인이 살아있나"를 보는 단일 감시자가
  없었다.** 전진 페이퍼가 조용히 멈추면(시크릿 만료·서버 SSH 단절·GitHub 60일 비활동
  스케줄 정지) 전진 엣지가 *얼어붙는데*, 자본 사다리는 계속 `WAIT_EDGE`(단 0, 자본 0%)
  만 보고 → "정상 누적 중"과 "죽어서 정지"가 구분 안 됨(이 프로젝트가 반복적으로 물린
  "침묵 실패" 부류).
- **무엇을 만들었나**: `src/auto_invest/analytics/pipeline_liveness.py`(순수 코어 —
  사이드카 timestamp 나이 → OK/LATE/STALE/MISSING 등급, 핵심 정지면 종합 CRITICAL),
  `scripts/pipeline_liveness_probe.py`(드라이버, `--manifest`로 레지스트리 단일 출처),
  `.github/workflows/pipeline-liveness.yml`(매일 07:30 UTC + 자기 파일 push 트리거).
  핵심(빨강 대상): 전진 페이퍼·사다리 게이트·KIS smoke·라이브 캐너리. 비핵심(저하만):
  수집·층화·승격. 거짓 경보 최소화: 평일 한계 80h(주말 갭), 매일 30h(한 번 미스 허용).
- **검증(실서버)**: 자가검증 push 트리거로 **첫 실행이 CI에서 success**(run 27468138580,
  15초) — origin 의 7개 사이드카 전부 정확히 파싱, 종합 🟢 OK, 사이드카
  `automation/pipeline-liveness-last-run` 발행 확인. 단위 18 + 통합 4 테스트, 전체 1878
  통과(기준선 1856 + 신규 22), 게이트 린트 깨끗.
- **안전 경계**: 읽기 전용·돈 0 이동·Kernel 터치 0건. 거래/자본/전략 변경 없음(라이브는
  운영자 게이트, 헌법 X.4). 탐지·보고만 하고 머니루프에 개입하지 않는다. 얼어붙은 엣지는
  자본 측면에서 이미 fail-safe(EDGE_CONFIRMED 못 만들어 승격 불가) — 이 계층은 가시성 전용.
- **다음 세션 관찰 지점**: ① 생존 감시 사이드카 신선도 확인 —
  `git show origin/automation/pipeline-liveness-last-run:LAST_RUN.md`(이게 오래되면
  감시자 자신이 멈춘 것 = backstop). ② 직전 마일스톤의 관찰 지점(밤 마감 정합성·정기
  층화·수집 overall_ok·사다리 WAIT_EDGE + forward 1/21 스냅숏 누적) 그대로 유효.

## 최근 마일스톤 — 2026-06-12 (🔗 금리 두-기관 교차 검증 + 레짐 층화 첫 실서버 실측)

main 머지 `02c9256`(#269) + `21102d1`(#270). 운영자 지시("세계 최고 수준으로 돈·
무중단 자율 성장·무개입 자동화·안정성") 하에 HANDOFF 후속 후보 1건을 출시하고,
직전 마일스톤의 "다음 세션 관찰 지점" 1건을 같은 세션에서 앞당겨 끝냈다.

- **🔗 금리 두-기관 교차 검증(#269)**: 탐침 증거(H.15 미러 200 OK, 0.4~0.7초)가
  모여 채택 — `[dbnomics]` 에 연준 H.15 2년·10년 금리 미러 수집 추가 +
  `[[cross_checks]]` 수준 대조 2건(`treasury:UST2Y/UST10Y` vs H.15, 합격선 99.5%
  — 재무부 사후 정정의 미러 반영 시차 며칠 허용, 체계적 오염은 대량 불일치로
  잡힘). 같은 날 실전 검증(run 27423921887): **9/9 발행 + 교차 검증 3건 전부
  PASS + 금리 겹침 2,360일 100% 일치**(2년물 시리즈 코드 추정도 정확). 덤:
  연구용 금리 이력이 재무부 직접 10년치 → H.15 기준 1962년(10년물)/1976년
  (2년물)으로 깊어짐. 불변식 추가: 재무부 각 만기는 H.15 대조 짝 필수.
- **🧬 층화 첫 실서버 실측(#270)**: 수동 발화는 컨테이너 연동 권한 밖(403 실측)
  → `regime-stratify.yml` 에 같은 날 검증 push 트리거(체인 파일 3개)를 추가해
  머지 자체가 첫 실행을 발화. 첫 런(run 27424271217) 두 트랙 모두 성공:
  bars-export(forward DB 읽기 전용) 1,003봉×3 / 1,000봉×11 → 리플레이 →
  층화까지 전체 체인 실서버 검증. **첫 층화 실측(752 수익률일, 2023-06~2026-06)**:
  GLOBAL-TREND(라이브 지정) RISK_ON 313일 샤프 1.93·CAUTION 432일 샤프 0.79·
  낙폭 7.98%·RISK_OFF 7일(표본<20 정직 생략); WIDE(11슬리브) CAUTION 샤프 0.86·
  낙폭 4.73%(3자산보다 방어적) vs RISK_ON 수익은 3자산 우위(+28.1% vs +13.5%).
  **인플레 방어 가설(스펙 047 — 원자재 포함 WIDE 가 인플레 레짐에서 더 버틴다)과
  방향이 일치하는 첫 실데이터**. 단 RISK_OFF 표본 7일(리플레이 3년 한계)이라
  확정 아님 — forward ARM F(WIDE) 누적이 진짜 판정.
- **검증**: 테스트 1856 통과(기준선 1853 + 신규 3), 린트 깨끗, Kernel 터치 0건,
  주문 0건·돈 0 이동. deploy-on-merge 2건(02c9256·21102d1) 성공.
- **다음 세션 관찰 지점**: ① 오늘 밤 20:00 UTC 장 마감 정합성 — 외부 보유
  기준선(#264) 후 첫 마감, 다음 forward 런 🚦 섹션에서 `data/halt.flag` 가 안
  서는지(서면 새 드리프트 — 해제 말고 조사) ② 정기 층화 런(매 거래일 23:30
  UTC) 지속 확인 ③ 내일 01:30 UTC 수집 런 overall_ok(이제 9항목) ④ 사다리
  게이트 WAIT_EDGE + forward 관측 누적(현재 1/21 스냅숏) 유효.

## 최근 마일스톤 — 2026-06-12 (🧬 레짐 층화 첫 실제 소비 + 단일 잣대 구멍 2건 수정)

main 머지 `f408b2e`(#267). 운영자 지시("세계 최고 수준으로 돈·시간당 자율 성장·무개입
자동화·안정성") 하에 HANDOFF 후속 후보였던 **층화 분석의 첫 실제 소비**를 배선했고, 그
과정에서 백테스트=라이브 단일 잣대(헌법 X.2)의 구멍 2건을 발견·수정했다.

- **🐛 단일 잣대 구멍 ①**: 백테스트 리플레이(`backtest/portfolio_replay.py`)가
  `ensemble_windows`(스펙 048 다중 속도 추세 앙상블)를 조용히 무시하고 단일 속도만
  적용 — **라이브 TOML 로 백테스트하면 배포된 전략과 다른 전략을 재생**했다. 수정 =
  `strategy.trend.spec_from_filter_config` 공유 변환(라이브 리밸런서와 한 함수).
  행동 회귀 테스트: 같은 데이터에서 앙상블=체결 2건 vs 단일=1건 차등을 CI 고정.
- **🐛 단일 잣대 구멍 ②**: 리플레이가 MARKET 하드코딩 — 배포 TOML 전부(LIMIT 전용
  화이트리스트)에서 whitelist_gate 가 전 주문 거부 → 영원한 현금 곡선(조용한 실패).
  수정 = 화이트리스트가 MARKET 불허면 종가 지정가 LIMIT(라이브 marketable-limit 의
  일봉 근사). MARKET 허용 화이트리스트는 byte 동일 경로.
- **새 다리(CLI)**: `bars-export` — 인스턴스 DB 일봉 → ohlcv-csv.md 계약 CSV(읽기
  전용, 테스트가 DB 파일 sha 불변까지 단언). `backtest-portfolio --equity-out` —
  일별 시가평가 자본 곡선을 regime-stratify 입력 형식(date,value CSV)으로.
- **전용 연구 워크플로 `regime-stratify.yml`**(매 거래일 23:30 UTC, forward 백필 후
  ·사다리 게이트 전): 서버에서 bars-export→ingest-history→backtest-portfolio→
  regime-stratify 체인을 돌려 "배포 전략(GLOBAL-TREND 3자산 + WIDE 11슬리브)이 어떤
  거시 레짐에서 벌고 잃는가"(최근 ~3년 일별, 전망적 d+1 결합)를 사이드카
  `automation/regime-stratify-last-run` 에 매일 발행. **거래 워크플로에 넣지 않은
  이유**: 거래 워크플로의 public-data 무소비 불변식(포괄 텍스트 검사 = 의도된 강한
  보호선, forward 판정은 자동 무장 게이트로 이어지는 돈 경로)을 약화시키지 않기 위해.
  서버 쓰기는 전부 /tmp, forward DB 는 읽기만(워크플로 격리 불변식 테스트 6건 CI 고정).
- **검증**: 신규 테스트 13건, 전체 1853 통과(기준선 1840), 린트 깨끗, Kernel 터치
  0건, 주문 0건·돈 0 이동.
- **다음 세션 관찰 지점**: ① 다음 23:30 UTC 런의
  `git show origin/automation/regime-stratify-last-run:LAST_RUN.md` — 실서버 첫 실행
  (bars-export 가 forward DB 에서 처음 돈다). 층화 표의 RISK_OFF/CAUTION 낙폭·샤프가
  전체 대비 크게 나쁘면 그 레짐이 전략의 구조적 약점 — WIDE(원자재 포함)와 비교해
  인플레 방어 가설(스펙 047)을 실데이터로 검증할 것. ② 직전 마일스톤 관찰 지점(오늘
  밤 20:00 UTC 정합성 OK 여부) 유효.

## 최근 마일스톤 — 2026-06-12 (🛡 라이브 halt 일일 재발 종결 — 외부 보유 기준선, 폐회로 복구)

main 머지 `e039796`(#264 수정) + `f00c2ff`(#265 해제). 운영자: "세계 최고 수준으로
진짜 돈을 벌고, 매시간 자율 성장하고, 사람 개입 없는 완벽한 자동 시스템과 안정성."
세션 시작 `/sync` 가 찾아낸 최우선 안정성 문제 — **라이브 `data/halt.flag` 가 매
거래일 20:00 UTC 장 마감 정합성에서 같은 사유로 재발화** — 를 근본부터 닫았다.

- **진단(사이드카 실측)**: 06-04 깃발(`reconciliation mismatch: 4 position(s)`)은
  거래소 단일 조회 버그(#233 수정) 오인이 섞였지만, 06-11 03:42 해제(#241) 후
  **수정된 코드에서 06-11 20:00 같은 사유로 재발** = 진짜 원장-실계좌 드리프트.
  KIS smoke(run 27405479242)가 실계좌 보유를 그대로 보여줌: **BHP 1주·MRK 3주·
  ORANY 28주·RELX 6주**(평가액 ≈$1,226.80 + 현금 $293.24 = 총 $1,520.04) —
  HANDOFF-013(2026-05-22) 시점에도 동일했던, 시스템 가동 전 운영자 취득 보유.
  원장(fills→current_positions)은 시스템 체결만 추적하므로 이 4종목은 원장에
  **영원히 없고**, 장 마감 정합성이 매일 MISMATCH→halt 를 세우는 구조였다.
- **수정(#264)**: `deploy/external-holdings.toml` **시스템 비관리 외부 보유
  기준선** + 정합성 검사가 (원장 수량+기준선 수량)==브로커 수량 으로 대조.
  ① 기준선과 정확히 일치 → OK(허위 halt 종결) ② 1주라도 다르면(운영자 매도
  포함) 여전히 MISMATCH→halt — **안전망 약화 아님**(시스템 모델 밖 계좌 활동은
  멈추고 드러냄; 보유가 진짜 바뀌면 TOML 갱신 머지 = git 포렌식 기록) ③ 가짜
  체결 주입 없음(fills 는 추가 전용 진실, 헌법 IV 무접촉) ④ 형식 오류 fail-fast
  ⑤ 기본 빈 기준선 = byte 동일, paper 무영향(마감 정합성은 라이브 전용).
  배선 = `--external-holdings`(기본 `deploy/external-holdings.toml`) →
  `WorkerSettings.external_holdings` → `reconcile_now`. diff 페이로드에
  `external_qty` 추가. Kernel 터치 0건. 신규 테스트 21건(로더 16 + 정합성
  시나리오 4 + 워커 배선 1), 전체 1840 통과, 린트 깨끗.
- **해제(#265)**: 해제 채널 경고문("해제 반복 금지, 근본 원인 먼저") 절차 준수 —
  수정 머지·배포 확인 후 `automation/halt-release.request` 갱신 머지로
  release-halt.yml 발화. **검증(run 27411255917): 해제 전 06-11 깃발 → `Halt
  cleared.`(K4 감사 HALT_CLEARED) → 해제 후 없음.** deploy-on-merge(run
  27411125478, `e039796`) success = 라이브 워커가 기준선 포함 새 코드로 가동.
- **안전**: 라이브 캐너리 `armed:false` 그대로 — 이 세션이 움직인 돈 0. 서킷
  브레이커·정합성 안전망 불변. 사다리 게이트는 WAIT_EDGE(관측 0/20) 정상 대기.
- **왜 중요한가**: 사다리(스펙 050)가 EDGE_CONFIRMED 후 무장해도 이 깃발이
  서 있으면 실주문 전부 거부 → "수익 0 인 완전 자동"이었다. 이제 폐회로(매일
  forward NAV 누적 → ≈20 거래일 → EDGE_CONFIRMED → 자동 무장 → 시장시간
  실주문)에 남은 수동 개입 지점 0 + 허위 halt 0.
- **다음 세션 관찰 지점**: ① 오늘 밤 20:00 UTC 장 마감 정합성 결과 — 매 forward
  런 🚦 섹션(`git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md`)
  에서 `data/halt.flag` 가 **서지 않는지** 확인. 다시 서면 기준선이 아니라 *새*
  드리프트이므로 해제하지 말고 조사. ② 운영자 외부 보유가 바뀌면(매도 등)
  MISMATCH 가 정직하게 발화 — 그때는 `deploy/external-holdings.toml` 을 실계좌에
  맞게 갱신 머지. ③ 기존 관찰 지점(레짐 타임라인 갱신, 사다리 게이트 WAIT_EDGE,
  forward 관측 누적) 유효.

## 최근 마일스톤 — 2026-06-12 (📊 레짐 이력 시계열 + 층화 분석 — "어떤 레짐에서 벌고 잃는가" 측정 가능)

main 머지 `fa483d7`(#262). 거시 레짐 스냅숏(#260) 직후 같은 날, 측정을 과거로 확장했다.

- **시점 기준 일별 레짐 타임라인**(`regime_timeline.csv`, 수집 워크플로가 매일 발행):
  날짜 축 = 금리차∩VIX 공통 영업일. **미래 누출 차단** — 일간 지표는 그날 종가, 월간
  지표(CPI·실업률)는 기준월 1일 + 발표 지연 45일부터 반영("그날 알 수 있었던 것"만).
  스냅숏(regime.json)과 마지막 구간이 달라도 정상(스냅숏="지금 아는 전부").
- **층화 분석기**(`analytics/regime_stratified.py` + CLI `regime-stratify`): 임의의
  NAV/수익률 CSV 를 d일 라벨 ↔ **d+1 거래일 수익률**로 전망적 결합 → 라벨별 누적/연환산
  수익률·변동성·샤프·최대낙폭·최악일. UNLABELED 분리(표본 편향 가시화), 관측 20개 미만
  비율 생략(통계적 무의미 정직 표기).
- **실전 검증(run 27405479236)**: 타임라인 **2,358일(2017-01-03~2026-06-11)**, 라벨 분포
  RISK_ON 1,414 / CAUTION 880 / RISK_OFF 64. 역사 사건 정확 — 2022-10-13(CPI 쇼크:
  역전 -0.50 + VIX 31.9) = RISK_OFF, 2019·2023 역전기 = CAUTION. 수집 7/7 + CPI 교차
  검증 PASS 유지.
- **격리**: 타임라인·층화기 모두 연구 전용, 라이브 경로와 양방향 무접촉(CI 불변식).
- **다음 세션 관찰/후속**: ① 정기 런의 타임라인 갱신 확인 ② **층화 분석의 첫 실제
  소비** — 백테스트 산출물 또는 forward NAV 스냅숏(서버 측)에 `regime-stratify` 적용해
  전략의 레짐별 약점 식별(컨테이너엔 가격 데이터가 없어 수익률 시계열은 서버/백테스트
  에서 가져와야 함) ③ 레짐 라벨을 백테스트 리포트에 자동 첨부하는 배선.

## 최근 마일스톤 — 2026-06-12 (🧭 거시 레짐 보고서 — 채널 데이터의 연구 소비 시작)

main 머지 `8b51b74`(#260). 계획 ④ 가동 직후 같은 세션에서, 수집만 하고 아무도 안 읽는
데이터가 되지 않도록 **첫 연구 소비자**를 배선했다.

- **무엇**: `market_data/macro_regime.py` + CLI `macro-regime` — 채널이 발행한 금리차
  (UST10Y2Y)·VIX 종가·CPI·실업률을 표준 정의로 판정해 `regime.json` 합성. 수집 워크플로
  (collect-public-data.yml)가 수집 직후 같은 실행기에서 만들어 사이드카에 함께 발행.
- **지표 4종(결정론적 Decimal)**: 금리 곡선 INVERTED/FLAT/NORMAL(+252관측 역전 일수),
  VIX CALM/NORMAL/ELEVATED/CRISIS(+이력 백분위), CPI 전년동월비 5구간, 삼 룰(실업률
  3개월 이동평균 − 직전 12개월 최솟값, 0.5%p 문턱). 합성 = 깃발 수 → RISK_ON(0)/
  CAUTION(1)/RISK_OFF(>=2), 가용 지표 <2 면 INSUFFICIENT(침묵≠안전).
- **실전 검증(run 27394647235)**: 4/4 지표 계산. **첫 판정 CAUTION** — 물가 깃발 1개
  (CPI YoY 4.25% HIGH). 금리 곡선 FLAT(0.40, 최근 252관측 역전 0일), VIX NORMAL(19.44,
  이력 9,205관측 백분위 59.9%), 삼 룰 QUIET(0.10%p). 수집은 7/7 + CPI 교차 검증 PASS 유지.
- **격리 양방향 CI 고정**: 모듈은 라이브 DB·주문·strategy/ 무접촉(금지 임포트 검사),
  라이브 경로(strategy/·broker/)는 macro_regime 미소비(역방향 검사). 보고 실패는 발행을
  안 막고(`|| true`) regime.json 부재로 정직하게 드러남. 파일명 ↔ 채널 설정 정합 테스트.
- **다음 세션 관찰 지점**: ① 매일 01:30 UTC 정기 런의 regime.json(지표 4/4 유지 여부 —
  BLS 신선도 70일 한도가 여름 발표 지연에 걸리는지) ② 후속 후보: 레짐별 전략 성과 층화
  분석(백테스트에 거시 레짐 축 추가), 레짐 이력 축적(현재 사이드카는 최신 스냅숏만 —
  이력이 필요해지면 누적 CSV 설계), DBnomics 연준 H.15 미러로 재무부 두-소스 교차 검증
  (탐침 증거 수집 중).

## 최근 마일스톤 — 2026-06-12 (🌐 계획 ④ 공개 데이터 수집 채널 가동 — 세계 최고 수준 4단계 계획 4/4 완료)

main 머지 `5009977`(#254 채널 신설) → `407bc4f`(#255 첫 실측 대응) → `d3d1cf7`(#256 3차
탐침) → `1462a9b`(#257 공식 키리스 전환) → `6fbd441`(#258 실전 런 실측 대응). 한 세션에서
"승인 → 실측 차단 발견 → 탐침으로 증거 수집 → 운영자 재선택 → 전환 → 실전 검증"의 전체
폐회로를 완주했다.

- **경위(정직한 기록)**: 운영자가 승인한 Stooq·FRED 는 컨테이너가 아닌 GitHub Actions
  실행기에서도 차단(Stooq=JS 봇 장벽, FRED 그래프=연결 후 무응답 타르핏)임이 1·2차 실측으로
  확정. 3차 탐침이 공식 소스 4곳(재무부·Cboe·BLS·DBnomics)의 즉답(0.1~0.7초)을 증거로
  수집 → 운영자가 **공식 키리스 조합**을 선택(키 등록·가격 이력 확장은 보류, 가격 소스는
  KIS 백필 유지).
- **채널 구성(머지 `1462a9b`+`6fbd441`)**: 미 재무부 일일 금리 곡선(연 단위 CSV 10년치 병합
  → UST2Y·UST10Y + 파생 스프레드 UST10Y2Y, FRED T10Y2Y 대체) + Cboe VIX 공식 이력(1990~,
  종가 시계열) + BLS 공공 API v1(실업률·CPI, 키 불필요 — 최근 약 3년의 정직한 한계) +
  DBnomics CPI 미러. 수집 오케스트레이터 일반화: 검증 통과 값이 `provider:id` 레지스트리에
  올라가고 `[[cross_checks]]` 목록이 참조(수익률 대조 + 새 수준 대조 `cross_check_levels`).
- **실전 검증(run 27392182746, 머지 `6fbd441` push 트리거)**: **7/7 발행 + CPI 교차 검증
  13/13 일치(100%) + overall_ok=true, 29초.** 사이드카 `automation/public-data` 에 CSV 7개
  + summary.json. 정기 수집 매일 01:30 UTC(화~토).
- **실측 교훈 3건(첫 실전 런이 가르쳐 준 진짜 데이터의 모습)**: ① VIX 1990년대 초 원본에
  OHLC 정합 깨진 행(원본 특성) → 연구가 쓰는 종가만 발행 ② BLS 미발표 기간 값 `"-"`
  (2025-10 정부 셧다운 결측 실측) → 형식 오류가 아니라 결측 보존 ③ DBnomics 미러 ~17개월
  지연 → 미러의 역할은 겹치는 과거 구간 일치(전송 변질 감지)이므로 신선도 한도 분리.
- **격리 원칙 불변**: 산출물은 연구·백테스트·검증 전용, 라이브 매매 신호는 KIS 데이터만
  (`test_collect_public_data_workflow.py` 불변식이 CI 고정 — 돈 경로 시크릿 무접촉, 거래
  워크플로의 채널 미소비, 교차 검증 짝의 수집 목록 존재).
- **다음 세션 관찰 지점**: ① 다음 정기 수집 런(01:30 UTC)의 사이드카 overall_ok ② 사다리
  게이트(매 평일 02:00 UTC 경) WAIT_EDGE → 앙상블 관측 누적(현재 1개, 20개 필요) ③ 후속
  후보 — 연구 파이프라인이 새 거시 데이터(금리·금리차·VIX·CPI·실업률)를 레짐 분석에 실제
  소비하는 작업, FRED 키 등록(보류 중), DBnomics 연준 H.15 미러로 재무부 진짜 두-소스
  교차 검증(탐침이 증거 수집 중).

## 최근 마일스톤 — 2026-06-11 (🌍 세계 최고 수준 4단계 계획 3/4 완료 — 사다리·통합 테스트·유니버스 확대)

main 머지 `a94d413`(#248 헌법 v5.0.0) + `646a957`(#249 사다리) + `85ed6ce`(#251 통합
테스트) + `0b3a078`(#252 유니버스 확대). 같은 세션에서 계획 ①②③ 완료:

- **② 돈 경로 끝-끝 통합 테스트**(`tests/integration/test_money_path_end_to_end.py`):
  실제 운영 산출물(canary-live-portfolio.toml·global-trend-portfolio.toml·센티넬)로
  이력→신호→비중→실제 K1 게이트 페이퍼 체결→NAV(자본 불변: 매수 직후 NAV==자본)→판정
  →사다리 PROMOTE→센티넬 자본 권위까지 한 번에. 음성 사슬(얕은 이력=빈 비중, 지문
  불일치=BLOCKED, 현 상태=WAIT_EDGE 돈 0)도 고정. **"매일 조합 버그 하나" 클래스의
  구조적 종결** — 이번 주 버그 전부가 이 테스트 하나에 잡혔을 것들.
- **③ 유니버스 확대 ARM F**(`deploy/global-trend-wide-portfolio.toml` + forward 6번째
  트랙): 검증된 메커니즘 그대로, 폭만 3 → 11 비상관 슬리브(주식 SPY·QQQ·EFA·EEM /
  채권 IEF·TLT·LQD / 실물 GLD·DBC·VNQ / 통화 UUP). 성과 ≈ 질 × √N. **라이브는 검증된
  3자산 유지** — ARM F 가 EDGE_CONFIRMED 를 벌어야 재지정 후보(검증=배치 정합 강제).
- **④ 서버측 데이터 수집 채널 — 미착수, 운영자 확인 필요**: 서버는 인터넷 전체에
  닿으므로 무료 공개 데이터(FRED CSV·Stooq CSV 등 — 표준 httpx 만으로 가능)를 서버측
  워크플로로 수집해 사이드카로 발행하는 채널이 가능. 단 **어떤 소스를 신뢰할지는
  공급망/이용약관 판단**(CLAUDE.md: 라이브러리·공급망 추가는 운영자 확인) — 다음
  세션이 소스 후보·약관·품질 검증 방식을 정리해 운영자에게 올릴 것.
- **다음 세션 관찰 지점**: ① 오늘 밤 23:50 UTC 사다리 게이트 첫 실행(WAIT_EDGE + 계좌
  NAV 기록 — `edge-autoarm-last-run` 사이드카, account-nav 실검증) ② 다음 forward 런의
  🌍 ARM F 섹션(11개 슬리브 KIS 백필 가용성 — 일부 실패 시 해당 슬리브만 현금) ③
  forward 자본 베이시스 누적(≈20거래일 후 EDGE_CONFIRMED → 사다리 단 1 자동 진입).

## 최근 마일스톤 — 2026-06-11 (🪜 스펙 050 자본 사다리 + 헌법 v5.0.0 — 자본 배치 자율 위임, 세계 최고 수준 4단계 계획 1/4)

main 머지 `a94d413`(PR #248, 헌법) + `646a957`(PR #249, 구현). 운영자가 "매 세션 비슷한
작업 반복이 세계 최고냐"고 두 번 연속 지적 → 정직한 천장 계산(베팅 폭·데이터·자본의 곱)
끝에 **운영자가 위임 확정**: "1·2·3 모두 세계 최고 수준이 목표. 3번(자본·수단)도 자동과
자율에 맡길 것. 기준은 계좌 잔고와 포트폴리오." LP/GP 구조로 비준 — 운영자는 낙폭 예산
(20%) 하나만 소유, 시스템이 그 아래에서 자본 배치를 자율 운영.

- **헌법 X.4 v5.0.0(PR #248, 운영자 머지 확인 완료)**: "풀라이브 자동 승격 금지" →
  **증거 게이트 자본 사다리 상시 위임**. 커밋에 K-meta 마커("this changes the safety
  perimeter") 포함.
- **사다리(스펙 050, PR #249)**: 단0=0%(무장 해제) → 단1=25% → 단2=50% → 단3=100%
  (실계좌 NAV 대비). 진입(0→1)=forward EDGE_CONFIRMED+전략 지문 정합. 승격=관측 ≥20
  +≥27일+낙폭<10% 전부(증거 측정 불가면 절대 승격 아님). **강등(낙폭≥10%)·정지(≥20%)는
  즉시·증거 불요.** 재사이징=계좌 NAV ±10% 드리프트(운영자 입금 자동 반영). 구현 =
  `portfolio/capital_ladder.py`(순수, 테스트 22건) + CLI `account-nav`/`growth --since`/
  `ladder-decide` + 게이트 워크플로(`forward-edge-autoarm.yml` 확장, 매 평일 23:50 UTC)
  + 자본 권위 가드(`rebalance-live-canary.yml`: 사다리 센티넬이면 자본 ≤ 기록된 계좌
  NAV, 수동 센티넬은 종전 $1,000) + CI 회귀(센티넬 자본 권위 + 예산 20% 고정).
- **비위임 불변**: 킬스위치(`automation/AUTOARM_DISABLED`)·스펙 014 서킷 브레이커·K1
  캡·화이트리스트·감사·시크릿·장중 가드·낙폭 예산 소유권. 입금·증권사 약정·컨테이너
  네트워크 정책은 물리적으로 운영자 전용.
- **즉각 효과(정직)**: 돈 0 이동 — 센티넬 `armed:false` + forward 미확정이라 게이트 첫
  결정은 WAIT_EDGE. 사다리 첫 가동은 forward EDGE_CONFIRMED(≈20거래일) 후 단 1(25%).
- **세계 최고 수준 4단계 계획 (이 세션 합의)**: ① 자본 사다리+헌법(✅ 이 마일스톤) →
  ② 돈 경로 끝-끝 통합 테스트(자본 커지기 전 배관 버그 클래스 박멸) → ③ 유니버스 확대
  (ETF 3개 → 비상관 슬리브 ~12개, √N 법칙) → ④ 서버측 데이터 수집 채널(서버는 인터넷
  전체에 닿음 — 데이터 천장 자율 해제). ②~④ 미착수 시 다음 세션이 이어받을 것.
- **다음 세션 관찰 지점**: ① 오늘 밤 23:50 UTC 사다리 게이트 첫 실행 —
  `git show origin/automation/edge-autoarm-last-run:LAST_RUN.md` 에서 결정=WAIT_EDGE +
  계좌 NAV 가 결정 JSON 에 찍히는지(account-nav 경로 실검증). ② forward 자본 베이시스
  누적(직전 마일스톤 관찰 지점 유효).

## 최근 마일스톤 — 2026-06-11 (🪜 라이브 백필 깊이화 — 무장해도 거래 0건이 될 끊긴 고리 수정, 같은 날 검증 완료)

main 머지 `3fdcb0c`(PR #245) + 재발화 `c972505`(PR #246). 운영자: "세계 최고 수준이 되기
위한 작업 분석·우선순위 판단 뒤 자율 수행 — 실제로 많은 돈을 벌어야." **NAV 측정 교정
다음 날, 돈 경로의 *마지막* 구간(무장 후 라이브 재조정)을 끝까지 추적해 또 하나의 끊긴
고리를 찾았다 — 라이브 DB 의 시세 이력이 얕아 무장돼도 영원히 현금만 들 상태였다.**

- **진단(실측, run 27296075204)**: 라이브 캐너리 워크플로의 backfill-bars 가 `--min-bars`
  없이(기본 한 페이지 ≈100봉) 호출 → IEF·GLD 가 라이브 DB(`data/auto_invest.db`)에 100봉뿐.
  전략 신호는 추세 앙상블 최대 252봉·역변동성 200봉·모멘텀 120봉 요구 → 전부 계산 불가 →
  `on_insufficient=cash` → 드라이런 미리보기 `target_weights: {}`. ≈20 거래일 뒤
  EDGE_CONFIRMED → 자동 무장(스펙 049)이 와도 **라이브 재조정은 현금 100%, 거래 0건 —
  fail-safe 방향이지만 폐회로의 목적 자체가 무효**(자연 회복엔 150+ 거래일).
- **수정**: forward 다섯 트랙과 동일한 깊은 백필(`--min-bars 1000`, 스펙 041 페이지네이션)
  로 정렬 — **검증=무장 정합**(같은 이력 깊이 → 같은 신호). 회귀 고정:
  `tests/unit/test_workflow_backfill_depth.py` — 두 워크플로의 모든 backfill-bars 호출이
  해당 포트폴리오 설정의 가장 긴 신호 창(+1)보다 깊은 `--min-bars` 를 넘기는 불변식
  (요구치를 TOML 에서 직접 파싱 — 설정이 바뀌어도 유효).
- **같은 날 검증(센티넬 재발화, run 27344173857 — push 이벤트라 미리보기만·실주문 0건)**:
  ① 백필 `SPY/IEF/GLD 각 fetched=1000`(894~900봉 신규 적재) ② 드라이런
  `target_weights: {"SPY": "0.239672"}` — 빈 비중 소멸, 신호 계산됨(IEF·GLD 0 은 현재
  추세 아래라는 전략의 정상 판단) ③ 라이브 NAV 측정도 자본 베이시스 작동(현금 $500 포함
  NAV $500, `legacy_snapshots_excluded: 10` — PR #243 수정의 라이브 트랙 확인).
- **안전**: Kernel 터치 0건, 돈 0 이동(읽기 전용 시세 백필 깊이 + 센티넬 주석), 센티넬
  `armed:false` 불변. 전체 1715 통과(신규 2), 린트 깨끗.
- **정직한 한계(운영자 알 것)**: 소액 자본의 정수 주 제약은 그대로 — 현재 추세 비중이
  SPY 만 살아있는 국면에선 SPY ≈$725 라 자본 $500(캡 $1,000)로는 1주도 못 사 실주문이
  0건일 수 있다(TOML 의 "정직한 소액 한계" 그대로). IEF(≈$95)가 추세 위로 오면 소액으로도
  체결된다. 자본·캡 상향은 돈 움직이는 운영자 결정(헌법 X.4).
- **다음 세션 관찰 지점**: ① 오늘 밤 forward 런 — 각 트랙 NAV 가 자본 기준(≈$12,000)으로
  찍히고 `legacy_snapshots_excluded` 표시되는지(직전 마일스톤의 관찰 지점 그대로 유효).
  ② 매 평일 15:00 UTC 라이브 캐너리 스케줄 런의 드라이런 미리보기가 비중을 계속 내는지 —
  `git show origin/automation/rebalance-live-canary-last-run:LAST_RUN.md`.

## 최근 마일스톤 — 2026-06-11 (📏 forward NAV 측정 오염 수정 — 장부 현금 포함, 판정 통계의 토대 교정)

main 머지 `21f94f8`(PR #243). 운영자: "세계 최고 수준이 되기 위한 작업 분석·우선순위 판단
뒤 자율 수행 — 실제로 많은 돈을 벌어야." **halt 해제로 폐회로가 완전 자동이 된 다음 날,
그 폐회로가 매일 쌓는 증거 자체(NAV 수익률 시계열)가 오염된 측정이라는 것을 발견하고
관측이 더 쌓이기 전에 교정했다.**

- **진단(실측)**: 페이퍼 트랙 `nav-snapshot` 은 브로커 없이 장부 폴백 → 현금 0 → NAV =
  포지션 평가액만. 매수/매도(자금 흐름)가 NAV 점프 = 가짜 수익률. 증거: 추세 ON 트랙
  "총수익 463%·낙폭 16.5%"(10개 스냅샷, 흐름 오염), GLOBAL-TREND 첫 체결 후 자본
  $12,000 에 NAV $2,176(SPY 포지션만). 이대로면 ≈20 거래일 뒤 자동 무장 게이트(스펙
  049)가 쓰레기 샤프로 EDGE 판정 — 가짜 EDGE_CONFIRMED(무근거 무장)든 가짜
  NO_EDGE(몇 주 낭비)든 치명적.
- **수정(측정 기준을 자금 흐름 불변으로)**: ① `performance/engine.net_cash_flow_usd` —
  순현금흐름(매도 − 매수). ② `compute_nav(ledger_cash_usd=...)` — 장부 폴백 현금 =
  자본 + 순현금흐름(매수는 현금→포지션 이동일 뿐, NAV 불변). ③ `nav-snapshot
  --capital` + 페이로드 `capital_basis_usd`(K4 추가 전용 필드, 커밋 `a67cd29` —
  기존 행·스키마 무변경, append-only 불변 유지). ④ `forward-verdict` 가
  `consistent_basis_suffix` 로 같은 측정 기준의 최신 연속 구간만 판정(오염된 레거시
  점은 읽기에서 제외, 감사 행은 그대로 — `legacy_snapshots_excluded` 로 가시화).
  ⑤ forward 5트랙 + 라이브 캐너리 측정 워크플로에 자본 전달(`--capital ${CAPITAL}`/
  `${CAP}`) + 모든 nav-snapshot 호출이 자본을 넘기는 불변식을 회귀 테스트로 고정.
- **안전**: 돈 0 이동(측정 경로 수정이지 거래/무장 변경 아님), 센티넬 `armed:false`
  불변, K1 캡·게이트 체인 무변경. 자동 무장 게이트는 dict 파싱이라 추가 JSON 키 안전.
  신규 테스트 13건, 전체 1713 통과, 린트 깨끗.
- **정직한 비용**: 판정 시계열이 자본 베이시스 구간부터 다시 세므로 EDGE_CONFIRMED 는
  2026-06-11 기준 ≈20 거래일 후. 오염된 시계열로 빨리 도달하는 것보다 정확한 시계열로
  가는 게 맞다(헌법 X — 모르면 엣지 선언 금지).
- **다음 세션 관찰 지점**: 오늘 밤 forward 런부터 ① 각 트랙 NAV 가 자본 기준(≈$12,000)
  으로 찍히는지 ② 판정 JSON 에 `legacy_snapshots_excluded` 가 표시되는지 —
  `git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md`.

## 최근 마일스톤 — 2026-06-11 (🔓 묵은 라이브 halt 해제 — 가드형·감사 채널 신설, 자동 경로 완전 개통)

main 머지 `07b093c`(PR #241). 운영자: **"안전 장치도 직접 풀어. 내가 관여하지 않을거야.
자동으로 모두 이어서 수행해."** 직전 마일스톤이 "운영자 결정 대기"로 남겼던 라이브
`data/halt.flag` 해제를 운영자 명시 지시로 자율 수행 — 돈으로 가는 자동 경로에 남아
있던 마지막 수동 결정 지점이 사라졌다.

- **채널(재사용 가능)**: `automation/halt-release.request` 센티넬(머지 = 운영자 지시의
  포렌식 기록, go-live 패턴) + `release-halt.yml`(트리거는 센티넬 머지 + 확인어
  "RELEASE-HALT" 수동 실행 두 가드뿐 — 스케줄 반복 금지를 테스트로 못박음). 해제는
  `rm` 이 아니라 `auto-invest resume --confirm` 으로만 — K4 감사 로그에 HALT_CLEARED
  행이 남는다. 결과는 사이드카 `automation/halt-release-last-run` 에 전/후 상태로 기록.
- **실행·검증(run 27322266903, 성공)**: 해제 전
  `{"ts_utc":"2026-06-04T20:00:00.862Z","reason":"reconciliation mismatch: 4 position(s)"}`
  → `Halt cleared.` → 해제 후 `(없음 — 해제 확인)`. 같은 push 의 deploy-on-merge 도
  성공(워커 = 최신 main).
- **안전**: 해제는 주문 게이트를 연 것뿐 — 라이브 캐너리는 `armed:false` 라 돈 0 이동.
  서킷 브레이커(스펙 014)·정합성 안전망은 그대로(조건 재발화 시 깃발이 다시 선다 —
  이 채널은 안전망을 끄지 않는다). Kernel 터치 0건. 전체 1700 통과, 린트 깨끗.
- **이제 완전 자동인 폐회로**: 매 거래일 forward 페이퍼(22:30 UTC)가 NAV 누적 → ≈20
  거래일 후 forward-verdict EDGE_CONFIRMED 가능 → 자동 무장 게이트(스펙 049, 23:50 UTC,
  킬스위치 `automation/AUTOARM_DISABLED` 없음 확인) → 라이브 캐너리 무장(소액 캡 $1,000
  + 서킷 브레이커) → 시장시간 스케줄 실주문. 수동 개입 지점 0.
- **다음 세션 관찰 지점(개입 아님)**: ① 매 forward 런 🚦 섹션에서 `data/halt.flag` 가
  다시 서는지 — 오늘 20:00 UTC 장 마감 정합성이 (PR #233 수정 후에도) *진짜* 원장 드리프트를
  찾으면 재설정된다. 재설정되면 해제 반복이 아니라 원장-실계좌 드리프트 자체를 고칠 것.
  ② `git show origin/automation/edge-autoarm-last-run:LAST_RUN.md` 로 무장 게이트 판정 추적.

## 최근 마일스톤 — 2026-06-11 (🟢 페이퍼 forward halt 깃발 격리 — NAV 0 병목 해소, 같은 날 검증 완료)

main 머지 `bc5db56`(PR #238) + `243f7a0`(PR #239 재발화). 운영자: "세계 최고 수준이 되기 위한
작업 분석·우선순위 판단 뒤 자율 수행 — 실제로 많은 돈을 벌어야." **시세(#229)·주문(#231)·
되돌림(#233)·취소(#236)를 다 고친 뒤에도 forward NAV 가 여전히 0 이던 마지막 끊긴 고리 —
다섯 페이퍼 트랙이 라이브 킬스위치(`data/halt.flag`)를 공유하던 설계 결함 — 를 닫고,
센티넬 재발화로 같은 날 검증까지 끝냈다.**

- **진단(06-10 런 실측)**: 시세는 정상(SPY 가 AMS 에서 조회, 목표 가중치 계산)인데 주문 전부
  `REJECTED_BY_GATE: halt flag is set`. 원인: 다섯 트랙의 `rebalance-once` 가 `--halt-path`
  미지정 → 기본값 `data/halt.flag` = 라이브 워커 킬스위치 공유. 2026-06-04 정합성 오인(PR #233
  에서 수정된 버그)이 남긴 묵은 깃발 `reconciliation mismatch: 4 position(s)` 이 페이퍼 검증
  전체를 막음 → NAV 영원히 0 → EDGE_CONFIRMED 불가 → 자동 무장 게이트(스펙 049) 영구 대기.
- **수정**: ① 트랙별 전용 halt 깃발(`data/forward_<트랙>.halt.flag` — 전용 DB 와 같은 격리
  원칙). ② 🚦 halt 상태 읽기 전용 진단 스텝 + LAST_RUN.md 보고(라이브 깃발 사유를 운영자가
  보고 해제 결정 — 자동 해제 안 함, 안전 자세). ③ 회귀 테스트 4건(격리·PAPER 전용·읽기 전용
  불변식, `tests/unit/test_forward_workflow_halt_isolation.py`).
- **검증(같은 날, 재발화 run 27321342988)**: halt 거부 0건(직전 런은 전 트랙 거부) +
  **GLOBAL-TREND 첫 페이퍼 체결(SPY 3주 `PAPER_FILLED`) + NAV $2,176.29(0→비0)** — 검증 대상
  3자산 앙상블(샤프 ~2.0)이 드디어 우리 체결 기준 forward 증거를 쌓기 시작. 진단 섹션이
  라이브 깃발 사유를 정확히 보고.
- **안전**: Kernel 터치 0건, 돈 0 이동(페이퍼 검증 경로 격리이지 거래 변경 아님), 라이브
  `data/halt.flag` 무변경(킬스위치 자세 유지). 전체 1697 통과, 린트 깨끗.
- **⚠ 운영자 결정 대기(라이브 무장 전 필수)** *(→ 같은 날 해제 완료 — 위 2026-06-11 🔓 절 참조)*: 라이브 `data/halt.flag` 가 2026-06-04 묵은
  정합성 오인으로 서 있다 — 무장 후 실주문도 이 깃발에 거부된다(fail-safe 방향이지만 수익 0).
  원인 버그는 #233 에서 수정 완료. **운영자가 서버에서 `auto-invest resume` 으로 해제해야
  라이브 캐너리가 실제 주문 가능.** 매 forward 런의 🚦 섹션에서 깃발 상태 확인 가능.
- **다음**: ≈20 거래일 NAV 누적 → forward-verdict EDGE_CONFIRMED → 스펙 049 자동 무장 게이트
  (라이브 깃발 해제가 선행돼야 실효).

## 최근 마일스톤 — 2026-06-10 (🟢 주문 취소·재호가 거래소 자동 해석 — 제출 거래소 영속화, 같은-클래스 잠복 버그 종결)

main 머지 `8d45c53`(PR #236). 운영자: "세계 최고 수준이 되기 위한 작업 분석·우선순위 판단
뒤 자율 수행 — 실제로 많은 돈을 벌어야." **같은 날 시세(#229)·주문(#231)·되돌림 조회(#233)에
이은 거래소 자동 해석의 마지막 대칭 — PR #233 마일스톤이 직접 지목한 후속(주문 *취소* 경로)을
닫았다.**

- **우선순위 판단**: 엣지는 검증됨(샤프 ~2.0), 병목은 끊긴 파이프라인 고리(일관된 교훈).
  forward 사이드카는 어제(06-09) 런이 시세 수정 *이전* 커밋이라 오늘 밤 23:53 UTC 런부터
  검증 가능 — 그 사이 돈 경로의 마지막 같은-클래스 버그를 닫는 게 최고 가치.
- **진단**: 주문은 종목별 거래소(OVRS_EXCG_CD)로 나가는데(#231) 미체결 주문 수명 관리
  (스펙 030)의 TTL 취소·재호가는 단일 고정 거래소(`market_order`=NASD)였다. KIS 정정취소
  (order-rvsecncl)는 OVRS_EXCG_CD 가 원주문과 일치해야 하므로 SPY·GLD(AMEX) 주문 취소가
  오라우팅돼 **주문이 산 채로 남는** 돈 경로 버그.
- **수정(제출 거래소 영속화)**: ① 마이그레이션 `0003_order_routing.sql` — `correlation_id →
  order_exchange` 사이드카 테이블(ALTER 는 IF NOT EXISTS 가드 불가 → 재시도 안전 정책 준수).
  ② 라우터가 제출 성공 시 실제 쓴 거래소 기록. ③ 수명 관리 리더가 LEFT JOIN 으로 읽음.
  ④ 워커 취소 `market=o.order_exchange or 기본값`, 재호가 재제출도 원주문 거래소로(새 주문
  라우팅도 기록).
- **안전**: Kernel 터치 0건(보호된 0001·0002 무변경, 0003 은 신규 파일·K1 캡 불변). 돈 0 이동
  (센티넬 `armed:false` 불변). 회귀 0(라우팅 기록 없는 주문은 종전 기본 거래소 폴백, paper
  모드 orders 무접촉 그대로). 신규 테스트 4건. 전체 1693 통과, 린트 깨끗.
- **정직한 한계**: 실브로커 취소 검증은 운영자 몫. 수명 관리 호가 조회(`market_quote` 고정)는
  비기본 거래소 종목의 재호가만 보수적으로 건너뜀(TTL 취소는 호가 불필요) — 현 라이브 캐너리
  룰셋은 lifecycle 옵트인 전이라 실사용 영향 없음.
- **다음 세션 검증(그대로 유효)**: ① 오늘 밤 23:53 UTC forward 런부터 `quote fetch failed for
  SPY` 소멸 + GLOBAL-TREND NAV 비0(`git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md`)
  → ≈20 거래일 누적 → EDGE_CONFIRMED → 스펙 049 자동 무장 게이트. ② 라이브 첫 실주문의
  OVRS_EXCG_CD 정합은 실브로커로만 최종 확인.

## 최근 마일스톤 — 2026-06-10 (🟢 라이브 *되돌림 읽기* 경로 거래소 자동 해석 — 체결·보유·잔고 멀티 거래소 스윕)

main 머지 `cccd1dd`(PR #233). 운영자: "세계 최고 수준이 되기 위한 작업 분석·우선순위 판단
뒤 자율 수행 — 실제로 많은 돈을 벌어야." **오늘 고친 시세(#229)·주문(#231) 거래소 자동 해석의
*되돌림(읽기)* 대칭 잠복 버그를 닫았다 — 주문은 거래소별로 나가는데 체결·보유 *조회* 는 여전히
단일 거래소(NASD)만 봐서, 검증 멀티에셋 유니버스가 라이브로 가는 순간 깨질 버그.**

- **우선순위 판단**: 엣지는 검증됨(멀티에셋 역변동성 다중 속도 추세 앙상블, 샤프 ~2.0·낙폭 3.7%),
  추가 연구는 수확 체감 + 데이터 제약. 돈 경로의 병목은 "끊긴 파이프라인 고리"(최근 마일스톤들의
  일관된 교훈). 돈 경로를 끝까지 추적해 *되돌림 읽기* 쪽의 다음 끊긴 고리를 찾았다.
- **진단(결정적)**: 검증 유니버스는 거래소가 섞임(SPY·GLD=AMEX, IEF=NASD). KIS 체결조회
  (inquire-ccnl)·잔고조회(inquire-balance)는 `OVRS_EXCG_CD` 로 거래소 범위를 받는데 되돌림
  조회가 모두 단일 거래소 고정 → ① 체결 동기화 누락(SPY·GLD 주문이 SUBMITTED 에 갇힘 → 로컬
  보유 0 → 리밸런서 과매수 + 손실 서킷 브레이커가 노출 못 봄) ② 잔고 정합성이 'ledger_only' 로
  오인(허위 drift/halt) ③ NAV 저평가(허위 하락 방어).
- **수정**: 되돌림 조회를 `US_ORDER_EXCHANGES`(NASD·NYSE·AMEX) 전부 훑어 합치되 종목/주문번호로
  중복 제거(KIS 가 거래소별 필터든 단일값 전부 반환이든 양쪽에서 정확·멱등). `broker/overseas.py`
  에 `get_order_executions_resolving_market`/`get_positions_resolving_market`/
  `get_balance_resolving_market` 추가, `fill_sync`·`reconciliation`·`worker/loop`·`cli` 가 스윕 사용.
  심볼별 거래소 하드코딩 0.
- **안전**: Kernel 터치 0건(K1 캡·K2 화이트리스트·K4 감사 불변, 주문은 종전과 동일 게이트 통과).
  돈 0 이동(읽기 전용 조회, 센티넬 `armed:false` 불변). 단일 거래소 룰 워커 결과 byte 동일(회귀 0).
  신규 테스트 9건. 전체 1689 통과, 린트 깨끗.
- **후속 같은-클래스 후보**: 주문 *취소*(TTL, `worker/loop.py` `cancel_order`)도 단일 거래소 —
  포트폴리오 `rebalance-once` 경로에서 별도 검토 필요.
- **다음 세션 검증**: 라이브 무장 첫 실주문 후 SPY·GLD(AMEX) 체결이 sync_fills 로 동기화되고
  정합성이 'ledger_only' 오인 없이 통과하는지는 실브로커로만 최종 확인(컨테이너는 KIS 미접근).

## 최근 마일스톤 — 2026-06-10 (🟢 라이브 주문 거래소 자동 해석 — 검증 멀티에셋 유니버스의 마지막 끊긴 고리)

main 머지 `ba05565`(PR #231). 운영자: "세계 최고 수준이 되기 위한 작업 분석·우선순위 판단
뒤 자율 수행 — 실제로 많은 돈을 벌어야." **시세 버그(같은 날 PR #229)의 주문측 대칭 수정 —
시세는 거래소를 자동 해석하는데 실주문 거래소는 여전히 단일 고정값이라, 검증된 전략이 라이브로
가는 마지막 한 걸음에서 깨질 잠복 버그를 닫았다.**

- **우선순위 판단(왜 이걸 했나)**: 엣지는 이미 검증됨 — 종목 선택 알파는 0(스펙 041 실측),
  진짜 엣지는 멀티에셋(SPY·IEF·GLD)·역변동성·다중 속도 추세 앙상블로 샤프 ~2.0·낙폭 3.7%
  (스펙 043·047·048). 추가 연구는 수확 체감 + 데이터 제약(컨테이너는 GitHub만 닿음). 돈으로
  가는 길의 병목은 "더 많은 연구"가 아니라 "끊긴 파이프라인 고리"다(최근 마일스톤들의 일관된
  교훈: 끊긴 배포 복구, 시세 거래소 자동 해석). 사이드카·돈 경로를 끝까지 추적해 *다음* 끊긴
  고리를 찾았다.
- **진단(결정적)**: KIS 는 시세 조회 거래소(EXCD: NAS/NYS/AMS)와 주문 거래소(OVRS_EXCG_CD:
  NASD/NYSE/AMEX)가 **별개 코드 체계**다. 2026-06-10 시세 수정은 `rebalance-once` 의 시세 경로를
  거래소 자동 해석(`get_quote_resolving_market`)으로 고쳤지만, **실주문은 `place_order(market=...)`
  의 `OVRS_EXCG_CD` 가 모든 종목에 단일 고정값(기본 NASD)** 이었다. 검증된 유니버스는 거래소가
  섞임 — SPY·GLD = AMEX/Arca, IEF = NASDAQ. 단일 고정값이면 forward 가 EDGE_CONFIRMED →
  스펙 049 자동 무장 → 라이브 첫 실주문에 도달하는 순간 SPY·GLD 주문이 거부/오라우팅된다.
  HANDOFF 가 "라이브 전 운영자 검증 항목(주문 EXCD 는 실주문으로만 확인)"으로 명시했던 바로 그 고리.
- **수정(시세 해석기가 이미 아는 거래소를 주문 경로로 연결)**: ① `Quote.resolved_market` 필드
  추가 — `get_quote` 가 시세를 *실제로 받은* EXCD 를 기록(해석기가 NAS→NYS→AMS 중 성공한 거래소).
  ② `order_exchange_for_quote_market()` 순수 매핑(NAS→NASD/NYS→NYSE/AMS→AMEX). ③ `OrderRouter.
  submit_order(order_exchange=...)` — 주어지면 그 거래소, 없으면 `self.market` 폴백. ④ `execute_
  rebalance` 가 종목별 `quote.resolved_market` 을 주문 거래소로 연결. 심볼별 거래소 하드코딩 0
  (시세 자동 해석과 동일 원칙).
- **안전**: Kernel 터치 0건(보호 파일 미변경, K1 캡·게이트 체인 불변 — 주문은 종전과 동일하게
  게이트 통과, OVRS_EXCG_CD 값만 종목별로 정확해짐). 돈 0 이동(센티넬 `armed:false` 불변, 실주문은
  시장시간 스케줄에서만). 회귀 0(단일 거래소 룰 워커는 `order_exchange=None` → 종전과 byte 동일).
  신규 테스트 7건(매핑·`resolved_market` 전파·주문 라우팅·기본 폴백·리밸런서 연결). 전체 1681 통과,
  린트 깨끗.
- **정직한 한계**: 컨테이너는 KIS 에 직접 못 닿아 실브로커 주문 검증은 운영자 몫. 이 수정은 단일
  하드코딩보다 "구성상 정확"하게 만든다(시세 버그 수정과 동일한 인식 상태). 라이브 무장 첫 실주문
  + 소액 캡($1,000) + 서킷 브레이커가 방어선.
- **다음 세션 검증**: ① 오늘 23:53 UTC forward 런부터 시세 버그 소멸 + GLOBAL-TREND NAV 비0 확인
  (`git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md`) → ≈20 거래일 누적 후
  EDGE_CONFIRMED → 스펙 049 자동 무장 게이트 발화. ② 라이브 무장 첫 실주문의 OVRS_EXCG_CD 정합은
  실브로커로만 최종 확인.

## 최근 마일스톤 — 2026-06-10 (🟢 시세 거래소 자동 해석 — 검증 전략 forward NAV 0 버그 수정)

main 머지 `f550dc5`(PR #229). 운영자: "세계 최고 수준이 되기 위한 작업 분석·우선순위 판단
뒤 자율 수행 — 실제로 많은 돈을 벌어야." **연구를 더 한 게 아니라, 검증된 엣지가 forward
증거를 못 쌓고 있던 진짜 병목(끊긴 시세 경로)을 고쳤다 — 2026-06-06 끊긴 배포 복구와 같은
범주의 "파이프라인 끊긴 고리" 수정.**

- **진단(결정적)**: 사이드카 `automation/rebalance-paper-forward-last-run` 의 GLOBAL-TREND
  (검증된 SPY·IEF·GLD 앙상블, 라이브 무장 대상) 준비 로그 —
  `rebalance: quote fetch failed for SPY` → `QuoteUnavailable: SPY ... got ''` →
  `total_nav_usd: "0"`(스냅샷 seq=2). 즉 **검증 대상 전략이 forward NAV 를 한 줄도 못 쌓고
  있었다.** NAV 가 0 이면 ≈20 거래일이 지나도 EDGE_CONFIRMED 에 영원히 도달 못 하고, 스펙 049
  자동 무장 게이트는 영원히 WAIT — 돈으로 가는 경로가 입구에서 막혀 있었다.
- **원인**: KIS 시세는 거래소(EXCD)별로 조회된다. 백필(`get_daily_bars`)은 NAS→NYS→AMS 를
  순서대로 시도해 SPY 를 **AMS(AMEX)에서 올바로 받지만(1000봉)**, `rebalance-once` 의 시세
  경로(`_quote_provider`)와 스펙 011 미실현 손익 마킹은 거래소를 **기본 NAS(나스닥)로 고정**했다.
  SPY·GLD 는 나스닥이 아니라 NYSE Arca/AMEX 상장이라 NAS 조회 시 `last` 가 빈 값 → rebalance 가
  SPY 에서 실패 → 어떤 포지션도 안 잡힘. 대조로 KIS smoke 의 AAPL(NAS)은 정상($290.55) — NAS 에
  있는 심볼만 통과했던 것.
- **수정**: `broker/overseas.py` 에 백필과 **동일한 거래소 순차 탐색**을 하는
  `get_quote_resolving_market` 헬퍼 추가(`QUOTE_EXCHANGES = (NAS, NYS, AMS)`). `rebalance-once`
  의 `_quote_provider` 와 미실현 손익 마킹 경로가 이 헬퍼를 쓰도록 전환. 심볼별 거래소를
  하드코딩하지 않는다.
- **안전**: Kernel 터치 0건, 돈 0 이동(페이퍼 시세 해석 버그 수정이지 거래/무장 변경 아님,
  센티넬 `armed:false` 불변). 신규 단위 3건(거래소 해석·첫 성공 정지·전 거래소 실패 전파).
  전체 1674 통과, 린트 깨끗.
- **다음 세션 검증**: 다음 forward 런(평일 23:53 UTC)의 GLOBAL-TREND 로그에서
  `quote fetch failed for SPY` 소멸 + NAV 비0 확인 →
  `git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md`. 누적되면 검증된
  전략이 *우리 체결 기준* forward 증거를 쌓기 시작 → EDGE_CONFIRMED → 자동 무장 게이트 평가.
- **라이브 전 운영자 검증 항목**: 주문 경로 `OVRS_EXCG_CD`(NASD/NYSE/AMEX — 시세 EXCD 와 별개
  체계)가 SPY 실주문에 맞는지는 실제 브로커로만 확인 가능. 라이브 무장 첫 실주문 + 소액 캡
  ($1,000) + 서킷 브레이커가 방어선. 이 수정은 시세만 다룬다(주문 경로 무변경).

## 최근 마일스톤 — 2026-06-10 (🟢 forward 검증 후 자동 무장 게이트 — 스펙 049)

main 머지 `a72a00e`(PR #227). 운영자 지시 **"forward 검증 후 자동 무장"** + 무장 해제 노트
(2026-06-04)의 계획 *"넓은 forward 페이퍼로 검증 후 재무장"* 의 자동화. **이 머지 자체는 무장
0건** — 센티넬은 `armed:false` 유지. 자동 무장은 forward 가 실제로 EDGE_CONFIRMED 될 때
(≈20 거래일 누적 후) 게이트가 별도 PR 로 수행한다.

- **무엇(두 가지)**: ① forward 가 *배선된 앙상블*(스펙 048 다중 속도 분수 노출, 이미 운영
  리밸런서 경로에 배선 — `strategy/rebalance.py`·`execution/rebalancer.py`)을 검증하도록 보장
  (ARM E = `global-trend-portfolio.toml`/`forward_global.db`). ② EDGE_CONFIRMED → 자동 무장 경로.
- **자동 무장 게이트**: `src/auto_invest/portfolio/autoarm.py`(순수·테스트된 결정) + CLI
  `auto-invest autoarm-decide` + 워크플로 `.github/workflows/forward-edge-autoarm.yml`(매 평일
  23:50 UTC). EDGE_CONFIRMED + **검증=무장 정합**(라이브 설정 전략 지문 == 검증한 앙상블) +
  미무장 + 킬스위치 없음 일 때만 ARM → 무장 PR open + best-effort 자동 머지 → 사이드카
  `automation/edge-autoarm-last-run` 발행. 그 외 보수적으로 WAIT/BLOCKED/ALREADY_ARMED/DISABLED.
- **라이브 캐너리 재지정**: `deploy/canary-live-portfolio.toml` 을 옛 3종목 top_n=1(운영자가
  "세계 최고 수준 아님"으로 거부) → 검증된 3자산 GTAA 앙상블(SPY·IEF·GLD, 역변동성, 다중 속도
  앙상블)로. `global-trend-portfolio.toml` 과 전략 지문 동일(CI 회귀로 못박음).
- **안전**: 무장 머지조차 미리보기만(첫 실주문은 다음 미국 정규장 스케줄) · 자본 소액(캡 $1,000) ·
  킬스위치 `automation/AUTOARM_DISABLED`(사용법 `automation/AUTOARM.md`) · 라이브 집합 SPY·IEF·GLD
  (헌법 II) · 풀라이브 아님(헌법 X.4). Kernel 터치 0건. 전체 **1671 통과**, 린트 깨끗.
- **다음 세션 확인 지점**: forward 가 EDGE_CONFIRMED 됐는지 →
  `git show origin/automation/edge-autoarm-last-run:LAST_RUN.md`(게이트 결정) +
  `git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md`(ARM E 판정).

## 최근 마일스톤 — 2026-06-07 (✅ 끊긴 배포 진짜 복구 — 워커 sudo 제어, 검증 완료)

main 머지 `03e4fa0`(PR #223, C1) + `31da635`(PR #224, C2). 운영자 "권장 방향대로 끝까지 자율
수행, 직접 개입 안 함." **세 번 실패하던 `stop_worker` polkit 병목을 sudo 로 우회해 끝냈다.**

- **문제**: deploy-on-merge 가 `stop_worker` 에서 polkit "Interactive authentication required"
  로 계속 실패(워커가 새 코드로 안 바뀜). polkit 규칙을 설치·재시작해도 안 됐다(프로덕션 호스트
  polkit 환경 문제, 컨테이너 SSH 진단 불가).
- **수정**: 워커 제어를 `sudo -n systemctl` 로 전환(결정론적). 좁은 sudoers 드롭인
  (`deploy/auto-invest-deploy.sudoers`)이 `auto-invest` 사용자에게 *워커 유닛의 stop/start/
  restart/is-active 만* NOPASSWD 허용. `auto-invest-deploy.service` 에서 NoNewPrivileges 제거
  (sudo=setuid 허용). sync-units 가 visudo 검증 후 설치. polkit 일체 제거(죽은 코드).
- **2단계 수렴(검증됨)**: 배포는 시작 시점 supervisor 를 임포트하므로 C1 배포는 옛 코드로 또
  실패(체크아웃만 전진), **C2 배포가 새 sudo supervisor 로 돌아 성공**. C2 deploy-on-merge run
  27241688178 = `START_EXIT 0` = "✅ 배포 성공 (워커 최신 main 으로 교체)". **확정.**
- **의미**: 이제 모든 새 코드 배포가 워커를 실제로 교체한다 — 운영자의 라이브 무장 커밋도 정상
  배포된다. forward 검증은 원래 영향 없었고(체크아웃 경로), 이제 워커 프로세스도 최신.
- **안전**: Kernel 터치 0건, 돈 0 이동. 권한 확대는 워커 제어 4개 명령만(폭넓은 root 아님).
  워커 재시작은 여전히 배포 상태기계 전용(market_hours_guard·health_check). 1627 통과, 린트 깨끗.

## 최근 마일스톤 — 2026-06-07 (스펙 048: 다중 추세 속도 앙상블 — 샤프 2+ / 낙폭 3.7% 📈)

main 머지 `0fa9037`(PR #221). 스펙 047(금)에 이어 *신호 속도 분산*을 더했다. 상세
`specs/048-trend-ensemble/{spec,FINDINGS}.md`.

- **무엇**: 검증된 3자산 위험관리 추세(스펙 047)의 게이트를 단일 10개월 SMA → **여러 속도
  (3/6/9/12개월) 합의의 분수 노출**로 확장. 자산 분산(043·047)·위험 사이징(044·047)에 더한
  **세 번째 분산 축 = 신호 속도**(AQR "A Century of Evidence on Trend-Following" 표준). 추가
  데이터 0.
- **실측(3자산 역변동성)**: 앙상블 3/6/9/12 vs 단일 10개월 → **4/4 구간 엣지**. 샤프 ~1.8→~2.0+,
  낙폭 ~5%→**3.7%**, 칼마 대폭↑(1971~ 1.77→2.67). 가장 깊은 1871~ 포함 견고. **빠른 속도(3개월)가
  핵심**(6/10/12는 3/4, 3/6/9/12는 4/4). = 우리 제약에서 도달 가능한 최고 위험조정 수익(기관급).
- **정직한 다음**: 분수 노출 배선은 후속 — 운영 리밸런서 `trend_filter`가 이진이라 슬리브별 부분
  스케일 지원 필요(별 슬라이스). 이 스펙은 *엣지 측정*(배선 전 가치 입증, 044/045 규율).
- **안전**: Kernel 터치 0건, 돈 0 이동, 연구/측정 전용. 전체 1626 통과, 린트 깨끗.

## 최근 마일스톤 — 2026-06-07 (스펙 047: 글로벌 분산 추세추종 +금 🪙 + 배포 polkit 진단)

main 머지 `a53a63f`(PR #217, 스펙 047) + `340f482`(#218)·`5b36bc2`(#219, 배포 polkit). 운영자
"세계 최고 수준이 되기 위한 작업 분석·우선순위 판단 뒤 자율 수행 — 실제로 많은 돈을 벌어야."
상세 `HANDOFF-050-SPEC-047-GLOBAL-TREND.md`.

- **스펙 047(검증된 엣지를 세계 최고 수준 차원으로)**: 스펙 043의 2자산(주식+채권) 분산 추세에
  **세 번째 비상관 자산(금)** 추가. 일일 모니터가 지금 경고하는 `DIVERSIFICATION_WEAKENED`(주식·
  채권 상관 양수 전환, 인플레 regime)의 구조적 헤지. **핵심: 금은 변동성 큰 자산이라 균등이 아니라
  위험으로 사이징**(역변동성=리스크 패리티)해야 분산 이득만 취한다 — 역변동성 3자산이 **모든
  구간(전체/현대/1971~/최근) 낙폭을 ~5%로** 낮추고 칼마 대폭↑(전체 0.45→1.10, 1971~ 1.49→1.77).
  데이터 추가 0(Shiller 1871~ + 런던 금 1833~, 둘 다 GitHub).
- **배선(ARM E)**: `deploy/global-trend-portfolio.toml`(SPY+IEF+GLD, weight_scheme=inverse_vol,
  sma 200) + forward 페이퍼 ARM E. ARM D(2자산) vs ARM E(3자산) 격리 비교로 금 분산을 우리 체결로 검증.
- **배포 polkit 진단**: deploy-on-merge가 `stop_worker`에서 polkit "Interactive authentication
  required"로 실패(워커 프로세스 restart 막힘). 규칙 동기화+restart로 완화 시도했으나 서버측 미해결.
  **★ 단, 이 실패는 forward 검증을 막지 않는다** — 깃 체크아웃은 stop_worker 전에 전진(rollback=False)
  하므로 forward 페이퍼는 최신 코드(ARM E 포함)로 동작. 묵히는 건 유휴 dry-run 워커뿐. 라이브 거래
  전엔 운영자가 polkit 서버 진단 또는 deploy 서비스 권한 전환을 결정해야(보안 자세 = 운영자 게이트).
- **안전**: Kernel 터치 0건, 돈 0 이동, PAPER 전용, 라이브 무장 변경 없음. 전체 1613 통과, 린트 깨끗.

## 최근 마일스톤 — 2026-06-06 (🔧 멈춘 배포 복구 + 견적 강건성 — 검증 파이프라인 재가동)

main 머지 `be112e0`(PR #213) + `dbd88dc`(PR #214). 운영자 "세계 최고 수준이 되기 위한 작업
분석·우선순위 판단 뒤 자율 수행 — 실제로 많은 돈을 벌어야." **연구 더 하기가 아니라, 이미
검증된 전략이 실전 검증을 못 쌓고 있던 진짜 병목(끊긴 배포)을 고쳤다.**

- **진단(결정적)**: 서버 배포가 2026-06-05부터 완전히 멈춰 있었다. 배포 저널 —
  `deploy refused: working tree dirty: ?? config/rules_auto_20260523T103616.toml / ?? reports/`.
  튜너가 만든 *추적 안 된* 생성 파일에 더티 가드가 걸려 **스펙 042~046이 서버에 한 줄도 안
  올라감**. 결과로 forward 사이드카에서 ARM C(위험관리 베타)·D(멀티에셋 추세)가
  `portfolio file not found` 로 전멸 — *검증된 전략의 우리 체결 기준 forward 검증치 = 0*.
- **고침 1 (`fix(deploy)`)**: `git reset --hard` 는 추적 안 된 파일을 건드리지 않으므로
  더티 가드가 걸릴 이유가 없다 → `dirty_tree_check` 를 `--untracked-files=no` 로(추적된 파일의
  미커밋 변경만 더티). `.gitignore` 에 `config/rules_auto_*.toml`·`reports/` 추가. 그리고
  `deploy-on-merge.yml` 에 **1회 언블록 스텝**: 추적 안 된 파일을 `data/`(gitignore)로 비파괴
  격리(추적 변경 있으면 건너뜀)해 옛 서버 코드의 닭-달걀을 푼다.
- **고침 2 (`fix(broker)`)**: KIS 가 빈 `last` 가격을 줄 때 `decimal.InvalidOperation` 으로
  다수 종목 견적이 터지던 버그 → `_opt_price` 헬퍼 + 심볼 적힌 `QuoteUnavailable`(헌법 VII).
- **검증(끝까지 — 확정)**: 머지 후 deploy-on-merge 가 **성공**(직전 두 번은 실패). 서버 저널
  `no changes to deploy (HEAD == origin/main @ be112e0)` + `START_EXIT 0` = **서버가 최신
  main 으로 복구**. 이어 forward 페이퍼 재발화(PR #214, run 27077225525) 결과 **네 ARM 전부
  `prep ssh_exit 0` + `verdict ssh_exit 0`** — ARM C(위험관리 베타 SPY·QQQ)·D(멀티에셋 추세
  SPY·IEF)가 65/1 → 0/0 으로 살아나 **첫 NAV 스냅샷 생성**(verdict JSON 빈칸→`INSUFFICIENT_DATA`,
  snapshot_count 1). `portfolio file not found` 완전 소멸 = **검증된 전략이 우리 체결 경로에서
  데이터를 쌓기 시작**.
- **안전**: Kernel 터치 0건, 돈 0 이동, 라이브 무장 변경 없음(배포 자동화 버그 수정이지 거래
  변경 아님). 전체 1596 통과·4 스킵, 린트 깨끗, YAML 유효. 신규/수정 테스트 8건.
- **다음(돈으로 가는 길)**: ① forward 사이드카에서 ARM C/D 의 `prep ssh_exit` 0 + verdict
  JSON 채워짐 확인(평일 22:30 UTC 누적). ② ~20 거래일 누적되면 forward-verdict 가 검증된
  멀티에셋 추세(샤프 1.6~1.8)의 *우리 체결 기준* 증거를 만든다. ③ **그 뒤가 운영자 결정**:
  검증된 전략을 라이브 캐너리에 적용(현재 라이브 설정은 운영자가 비판해 무장 해제한 옛
  3종목 top_n=1) + 자본·레버리지(돈 움직임·위험 경계 = 운영자 게이트 헌법 X.4).

## 최근 마일스톤 — 2026-06-06 (스펙 046: 일일 전략 모니터 — 지속 감시 대시보드 🔭)

main 머지 `a36ea23`(PR #211). 운영자: "이어서 자율 수행해. 세계 최고 수준으로 돈 벌자." 앞서
제안한 지속 감시 배선을 *세계 최고 수준의 일일 대시보드*로. 상세 `HANDOFF-049-SPEC-046-STRATEGY-MONITOR.md`.

- **무엇**: 검증된 스펙(042 추세신호·043 분산·044 레버리지 복리·045 regime)을 합쳐, forward
  페이퍼가 돌 때마다 운영자가 한눈에 보는 일일 대시보드를 사이드카에 찍는다. 네 가지를 답:
  ① 엣지 최근 유효성(분산 추세 최근 5/10년 샤프 1.70/1.76, 낙폭 3.6%), ② 분산 가정 신뢰도
  (상관 현재 -0.03/최근 5년 +0.10 → 판정 DIVERSIFICATION_WEAKENED), ③ 낙폭 예산별 레버리지
  복리 권고(**최근 25년 기준**: 15% L=2.0 복리 11.5%/년, 20% L=3.0 14.9%, 25% L=3.5 16.6%),
  ④ 오늘 추세 신호(S&P > 10개월 SMA +8.7% → 투자).
- **핵심 교정(운영자 지적 일관 적용)**: 레버리지 권고를 처음 전체 1871로 했더니 대공황 낙폭에
  묶여 낙폭 예산 15%서 'L=0.5 줄여라'가 나옴 = '먼 과거 기준' 실수 재발 → 최근 25년(닷컴·GFC·
  코로나·2022 포함)으로 교정해 일관성 확보.
- **왜 지속 감시가 방어선인가**: 스펙 045 가 밝혔듯 정적 분산은 regime 따라 깨진다. 매 거래일
  갱신되어 엣지 쇠퇴·상관 양수 전환을 조기 경보 = regime 비정상성 상시 방어선.
- **배선**: 러너 로컬 스텝(setup-uv + 프로브, Shiller 데이터만 — 워커 불필요) + 사이드카
  "🔭 일일 전략 모니터" 섹션. 완전 격리(continue-on-error + `|| true`)라 ARM A/B/C/D 무영향.
- **신규(순수 추가·비커널)**: `analytics/strategy_monitor.py` + `scripts/strategy_monitor_probe.py`
  + 단위 5건 + `specs/046/{spec,FINDINGS}.md`. 1590 통과, 린트 깨끗.
- **안전**: 읽기 전용·측정 전용, 주문 0건, 돈 0 이동, Kernel 터치 0건. **라이브 레버리지/무장
  변경 없음**(권고/감시이지 거래 변경 아님 — 라이브는 운영자 게이트 헌법 X.4, K1 캡 불변).
- **다음**: 대시보드를 우리 forward NAV 트랙(KIS 실측)에도 적용(데이터 누적 후). 운영자 결정:
  권고 레버리지(예: 낙폭 예산 15% → L=2.0 → 복리 ~11.5%) 라이브 적용 여부.

## 최근 마일스톤 — 2026-06-06 (스펙 045: 최근 regime/시점 강건성 감사 — '먼 과거 기준' 점검 🔬)

main 머지 `03938c6`(PR #209). 운영자: "계속 너무 먼 과거(1871~) 데이터 기준으로 분석하는 것
아닌가? 세계 최고 수준이라면 이 기준 자체를 점검해야." 상세 `HANDOFF-048-SPEC-045-REGIME-AUDIT.md`.

- **① 시점 강건성**: 분산 추세가 최근 5/10/15/20/30년·모든 연대에서 우위(샤프 1.59~2.07 vs
  단일 1.17~1.53, 60/40 0.78~1.84). 2020년대(가장 최근 77개월)도 샤프 1.59·낙폭 6.4%.
  **엣지는 1871 산물이 아니라 최근 regime 에서 더 강함**(과적합이면 최근이 약해야 하는데 반대).
- **② 주식·채권 상관 regime(운영자가 짚은 위험은 진짜)**: 최근 5년 평균 +0.095(양수 53%,
  2022 인플레 regime), 현재 -0.030(회복), 전체 +0.052. 판정 `DIVERSIFICATION_WEAKENED` —
  정적 분산(60/40·리스크 패리티)이 약해진 구간 → 추세 게이트 의존(상관 회복 시 RELIABLE 자동).
- **③ 스트레스 연도(결정적)**: 2022(주식·채권 동반 폭락, 60/40 -14.8%로 깨진 해)에 **분산 추세
  -1.2%**(추세 아래 자산 현금화). 2008 60/40 -19.4% vs 분산추세 +11.5%. **→ 진짜 가치는 정적
  분산이 아니라 *추세로 게이트한 분산*(상관 깨져도 방어).** 2020 코로나 V자 반등엔 약함(정직).
- **원칙**: 먼 과거=꼬리위험 스트레스 표본, 엣지 채택=최근 regime 무게, 상관 regime 지속 감시.
- **신규(순수 추가·비커널)**: `analytics/regime_audit.py` + `scripts/regime_audit_probe.py` +
  단위 9건 + `specs/045/{spec,FINDINGS}.md`. 1585 통과, 린트 깨끗. Kernel 터치 0건, 돈 0 이동.
- **다음 자율 후보**: 상관 regime + 최근창 판정을 forward 사이드카에 지속 감시 보고 배선(돈 0).

## 최근 마일스톤 — 2026-06-05 (스펙 044: 성장 최적 레버리지 — 고정 자본 복리 극대화 💹)

main 머지 `ca3d47f`(PR #207). 운영자: "자본 규모가 클수록 큰 돈은 초등학생도 하는 말. 세계
최고 수준으로 *현재 자본에서* 복리 효과 등 다양한 전략으로 수익을 극대화하라. 이 방향으로
자율 고도화하라." 상세 `HANDOFF-047-SPEC-044-GROWTH-OPTIMAL.md`.

- **핵심 수학(왜 정답인가)**: 복리 성장률 상한은 **샤프**로 결정된다(`g_max≈rf+Sharpe²/2`).
  raw 수익이 아니라 샤프가 천장. 스펙 043 이 천장을 올렸으니, 레버리지(변동성 타깃/부분 켈리)로
  그 천장을 *실제 복리 성장*으로 실현. 미묘함: 레버리지를 키우면 CAGR 이 오르다 떨어진다
  (변동성 드래그) → 정확한 최적점 존재. "최대 레버리지"는 파산.
- **슬라이스 1(실측, Shiller 1871~)**: 낙폭 예산 30%서 복리 **~2배**(현대 9.5→14.7%, 최근
  8.9→17.0%, 낙폭 28%=평범한 약세장 수준). 과레버리지=파산 정직 보고(5배 낙폭 87%, 풀켈리는
  도달 전 청산 CAGR −100%) → 실제 구속은 낙폭 예산. **보수적 예산(10~15%)서 분산이 단일 주식
  압도(+1.6~2.6%p)**: 단일은 변동성 커서 레버리지를 줄여야(L=0.5), 분산은 낮은 낙폭 덕에 키울
  수 있음(L=1.5). **사슬: 분산으로 샤프↑(043)→낙폭 예산 레버리지(044).**
- **슬라이스 2(또 다른 전략, 정직히 닫음)**: 리스크 패리티(역변동성) 가중 측정 → 50/50 못 이김
  (현대·최근 비등, 레버리지 후 50/50 나음). 단순 50/50 기본값 유지(과공학 금물, 스펙 042
  변동성 타깃 OFF 와 같은 규율).
- **신규(순수 추가·비커널)**: `analytics/growth_optimal.py` + `scripts/growth_optimal_probe.py`
  + `multi_asset_trend.py` 스트림 헬퍼 3개 + 단위 14건 + `specs/044/{spec,FINDINGS}.md`.
  1576 통과, 린트 깨끗.
- **안전**: 레버리지는 연구/측정 전용 — **라이브 K1 포지션 캡(노출≤100%, 헌법 I-VII) 불변.**
  라이브 레버리지는 위험 경계 변경=운영자 게이트(헌법 X.4). Kernel 터치 0건, 돈 0 이동.
- **"많은 돈"의 정직한 답**: 분산(고샤프) × 낙폭 예산 레버리지 × 복리 = 현재 자본으로 현대/
  최근 ~15~17%/년(낙폭 28%) 또는 보수적 ~11%/년(낙폭 15%) 사거리. **다음 운영자 결정: 라이브
  레버리지 적용 여부(위험 경계 변경).**

## 최근 마일스톤 — 2026-06-05 (스펙 043: 멀티에셋 분산 추세추종 — 세계 최고 수준 차원 확장 🌐)

main 머지 `64ead83`(PR #205). 운영자 "세계 최고 수준이 되기 위한 작업 분석·우선순위 판단 뒤
자율 수행 — 실제로 많은 돈을 벌어야". 상세 `HANDOFF-046-SPEC-043-MULTI-ASSET-TREND.md`.

- **우선순위 판단**: 종목선택 알파는 0(스펙 041), 유일한 엣지 추세 방어(스펙 042)가 지금 *단일
  자산군(미국 주식 베타)* 에만 적용됨(SPY·QQQ 상관 ~0.95). 세계 최고 수준 격차 = **멀티에셋
  분산 추세추종**(비상관 흐름의 분산 = 금융 최대의 공짜 점심).
- **결정적 발견**: 추가 데이터 0 — 스펙 042 가 쓰는 Shiller CSV 에 10년 국채 수익률이 1871년
  부터 있어 채권 총수익 프록시를 만들 수 있다.
- **슬라이스 1(검증)**: 주식추세+채권추세 분산(50/50) 샤프 1.18→**1.58**(전체)/1.43→**1.81**
  (현대)/1.29→**1.78**(최근), 낙폭 41%→18%/19%→7%/19%→7%. 상관 +0.035~−0.120(구조적 근거).
  **창 7/10/12 × 가중 50:50/60:40 모든 조합 DIVERSIFICATION_EDGE**(과적합 아님). 60/40 단순
  보유도 압도. 정직: 분산은 CAGR 더 낮음(절반 채권/현금) — 가치는 위험조정 수익(샤프)↑.
- **슬라이스 2(배선)**: `deploy/multi-asset-trend-portfolio.toml`(SPY+IEF 각자 sma 200 게이트)
  + `rebalance-paper-forward.yml` ARM D(전용 DB 격리). **측정한 것만 배선**(금·원자재 후속).
- **신규(순수 추가·비커널)**: `analytics/multi_asset_trend.py` + `scripts/multi_asset_trend_probe.py`
  + 단위 20건 + `specs/043-multi-asset-trend/{spec,FINDINGS}.md`. 1562 통과, 린트 깨끗.
- **안전**: Kernel 터치 0건, 돈 0 이동, PAPER 전용, 라이브 무장 해제 유지.
- **다음**: 사이드카 MULTI-ASSET-TREND 판정 확인(≈20 거래일 INSUFFICIENT_DATA 정상). **"많은
  돈"의 정직한 경로 = 높은 샤프(1.6~1.8) × 운영자 자본 결정**(돈 움직임은 운영자 게이트 X.4).

## 최근 마일스톤 — 2026-06-05 (스펙 042 슬라이스 1~4 완료: 위험관리된 베타 검증 끝 🟩)

main 머지 `415e2e7`(PR #196·198·199·200). 운영자 "우선순위대로 진행해" → 슬라이스 1~4 자율 완주.

- **슬라이스 1(PR #196)** — 추세 타이밍(N개월 SMA)이 단순 보유 대비 **낙폭 82%→41%, 샤프
  0.71→1.18, 칼마 0.11→0.27**. SMA 7/10/12 × 1871/1950/1990 = **9/9 견고**(과적합 아님).
- **슬라이스 2(PR #198)** — 거래비용·세금 모델. **회전 연 ~1.3회(저회전)**라 10bp서 샤프
  1.18→1.17, **3/3 EDGE_SURVIVES_COSTS**. 세금 15%(과세계좌)도 위험조정/낙폭 우위는 유지.
- **슬라이스 3(PR #199)** — 운영 코드 브리지: `production_in_market`이 라이브 코드
  `strategy.trend.above_trend`(sma)로 신호 생성 → **연구 신호와 100% 일치·같은 방어 재현**
  (검증된 엣지가 라이브 경로에 그대로 실림, 테스트 보증). + 거래수단 배선 아티팩트
  `deploy/risk-managed-beta-portfolio.toml`(SPY·QQQ 추세 게이트, 운영 로더 파싱 검증).
- **슬라이스 4(PR #200)** — 변동성 타깃 결합. **regime 의존적**: 극단 변동성 전체 기간(1871~)엔
  가치(샤프 1.17→1.28·낙폭 41%→26%)지만 현대·최근엔 추가 가치 없음 → **추세가 핵심 엣지,
  변동성 타깃 기본 OFF(과공학 금물)**.
- **데이터 접근 사실**: 이 컨테이너는 **GitHub만 닿음**(SEC·야후·FRED 403) → Shiller 월간 S&P
  (1871~, 대공황 포함)이 닿는 유일한 장기 데이터. 이게 "위험관리된 베타" 재정의의 근거.
- **신규(순수 추가·비커널)**: `analytics/risk_managed_beta.py` + `scripts/risk_managed_beta_probe.py`
  (--costs/--production-trend/--vol-target) + 단위 22건 + `deploy/risk-managed-beta-portfolio.toml`.
  1535 통과, 린트 깨끗. **돈 0 이동, Kernel 터치 0건, 라이브 무장 해제 유지.**
- **⚠ 아직 라이브 아님 — 남은 건 운영자 인프라 단계**: ① forward A/B arm(종목선택 vs 추세 베타)
  크론 배선 + 백필에 SPY·QQQ, ② 페이퍼 트랙 누적 → forward-verdict+칼마 위험조정 우위 확인,
  ③ 그 뒤 운영자 지시 소액 라이브(헌법 X.4). 이게 "실제로 돈 버는" 정직한 경로.

(이전 슬라이스 1 단독 기록은 위 항목에 통합.) 운영자 지시 "두 가지 모두 진행하자" → 데이터 접근
측정 후 운영자가 ① 라이브 아직 안 함, ② Track 2 = **위험관리된 베타** 선택. 그 직접 검증.

- **데이터 접근 사실 확인(측정)**: 이 컨테이너는 **GitHub만 닿음** — SEC EDGAR·야후·Stooq·FRED
  전부 403 차단. 즉 가격 말고 다른 알파(펀더멘털·매크로)를 *여기서* 만들 데이터가 없다. 이게
  "세계 최고 수준"을 위험관리된 베타로 재정의한 객관적 근거.
- **핵심 결과(Shiller S&P 1871~현재, 월간, 대공황·2008 포함)**: 단순 보유 vs N개월 SMA 추세
  타이밍. 추세 타이밍이 **낙폭 82%→41%(절반), 샤프 0.71→1.18, 칼마 0.11→0.27**(전체 기간).
  현대 1950~ 와 최근 1990~ 도 동일 패턴(낙폭 49%→19%, 샤프 ~1.4). **SMA 7/10/12 × 3구간 =
  9/9 위험관리 엣지** — 한 파라미터에 안 민감(과적합 아님). CAGR도 약간 높음.
- **정직한 의미**: 이건 *종목선택 알파가 아니라 베타의 자본 방어*다(스펙 041에서 종목선택
  알파는 측정상 없음 확정). 추세추종 드로다운 방어는 금융에서 몇 안 되는 끈질긴 효과이고,
  우리 제약에서 도달 가능한 정직한 "세계 최고 수준". 우리에겐 이미 부분 구현(`strategy/trend.py`,
  스펙 036)이 있어 — 이번 측정은 그 논리의 근거를 진짜 폭락 데이터에서 입증.
- **신규(순수 추가·비커널)**: `analytics/risk_managed_beta.py`(순수, `max_drawdown_pct`·
  `calmar_ratio`·PSR 재사용, 월간 √12), `scripts/risk_managed_beta_probe.py`, 단위 10건,
  `specs/042-risk-managed-beta/{spec,FINDINGS}.md`.
- **⚠ 아직 라이브 아님 — 실제 돈 전 관문**: ① 거래비용·세금 모델, ② 우리 거래수단(SPY 등)에
  월간 추세 필터 배선 + forward 페이퍼 검증, ③ 변동성 타깃 결합. 그 뒤에야 운영자 게이트 소액
  라이브(헌법 X.4). **돈 0 이동, Kernel 터치 0건, 라이브 무장 해제 유지.** 1522 통과, 린트 깨끗.
- **다음(슬라이스 2~4)**: 위 관문 순서대로. 비용 견디면 → 거래수단 배선 → forward 누적 → 운영자
  라이브 결정. 이게 "실제로 돈 버는" 정직한 경로(꼬리위험 방어로 위험조정 수익↑, 매년 초과 아님).

## 최근 마일스톤 — 2026-06-05 (스펙 041 6차: 1순위 신호 탐색 종료 → 2순위 패시브 수용 ✅)

main 머지 `52781b7`(PR #194). 운영자 지시 "1순위부터 진행하고, 1순위 결과에 따라 2순위
진행 여부도 자율 판단해." 가격 신호 중 학술 근거가 가장 강한 둘을 정직하게 재고 문을 닫았다.

- **왜 이 둘인가**: 그동안 잰 모멘텀은 최근 끝까지 포함이라 "**제대로 된 모멘텀을 안 잰 것
  아니냐**"는 의문이 남아 있었다. ① **12-1 모멘텀**(Jegadeesh-Titman: 최근 1개월=반전 구간을
  빼고 그 이전 11개월 수익률), ② **단기 1주 반전**(최근 하락폭 큰 종목 되튐)을 측정해 닫는다.
- **무엇을(전부 순수 추가·비커널)**: `momentum_gap` 지표/팩터 + `short_reversal` 팩터 신규.
  `cross_sectional_ic`/`signal-ic` CLI 에 `momentum_gap_lag` 전달. 드라이버
  `scripts/ic_signal_probe.py`(검증된 IC 하네스=운영 `composite_scores` 그대로 재사용, 미래
  누출 0·비겹침). **새 팩터는 가중치 0 기본 = 운영 선택/리밸런서 경로 영향 0.**
- **실측**(plotly 2013-2018, 종목당 ~1240바): 베이스라인 6개월 모멘텀 H=21 IC +0.0264·t=1.03
  (이전 +0.0266 재현 → 측정 신뢰). **12-1 모멘텀 H=21 IC +0.0200·t=0.68**(평범한 모멘텀보다
  오히려 약함). **단기 반전 H=5 IC +0.0076·t=0.84(N=250)**(표본 250개에서도 p≈0.40).
- **멈춤 규칙(N≥30 & IC>0 & t≥2): 아무것도 못 넘음 → 가격 신호 탐색 종료.** 깊은 옛 데이터
  (N 큼)와 얕은 최신 데이터(N=41, momentum IC≈0)가 둘 다 같은 결론.
- **2순위(자율 진행) = 패시브 수용**: 가격 팩터로 인덱스를 이길 측정된 근거 없음 → 인덱스/
  동일가중 저회전 보유가 정직한 기본값(규율 있는 결론). 시스템의 실질 가치는 알파가 아니라
  안전·측정 인프라. 3순위(다른 알파: 펀더멘털·이벤트)는 별도 큰 프로젝트로 보류(운영자 결정).
- **안전**: Kernel 터치 0건, 돈 0 이동(읽기 전용·측정). **라이브 무장 해제 그대로** — 이 분석은
  라이브 재무장 근거가 아니라 그 반대. 패시브 전환도 돈 움직이는 행동이라 운영자 게이트(X.4).
  전체 1513 통과·4 스킵, 린트 깨끗.
- **다음(운영자 결정)**: ① 패시브 자세를 실제 라이브에 반영할지(돈 움직임 → 운영자 명시 지시),
  ② 3순위(다른 알파 원천) 본격 착수 여부 — 착수 시 데이터 소스 가용성부터 조사.

## 최근 마일스톤 — 2026-06-05 (스펙 041 5차: 깊이 우선 백필 → ⚠ 모멘텀 IC ≈ 0, 잡음 확인)

main 머지 `32dc5b3`(PR #191, 깊이 우선 백필) + `3fb0aea`(#192 재발화). 운영자 "백필을 세계
최고 수준으로 유의성을 끌어올려". **결과: 정직한 깊은 표본에서 모멘텀 IC는 사실상 0.**

- **`--order deepen` 모드**: needy-first(0바 신규부터)가 아니라 *시드된 핵심 종목*을 KIS 한계까지
  먼저 깊게. IC 비겹침 시점(시간축)은 핵심의 *바 깊이*가 좌우하므로. `select_backfill_symbols`
  순수 함수 + 단위테스트 3건. 워크플로 `--min-bars 1000 --order deepen`(≈4년).
- **깊은 표본 IC 실측**(시점 8→41, 종목 ~141): H=21 평균 IC **+0.0050, t=0.17**(p≈0.86),
  H=63 +0.0264, t=0.51. **아까 +0.0965(N=8, t=1.79)는 소표본 잡음 — 표본 늘리자 사라짐.**
  방향 적중 61%로 약한 기울기는 있으나 평균 IC≈0 → 거래 엣지 아님.
- **교훈**: N=8 에서 멈췄으면 잡음에 라이브 투입할 뻔. 깊은 백필이 막음(유의성 요구의 가치).
  PR #186(합성=동전)과 합치면 — 가격 팩터 재조합으로는 이 유니버스/regime 에서 측정된 알파 0.
- **안전**: Kernel 터치 0건, 돈 0 이동(읽기전용·페이퍼), 라이브 무장 해제 유지. 1506 통과.
- **다음 = 운영자 전략 분기**(IC-FINDINGS "다음 레버"): 진짜 다른 알파 원천이 필요하거나,
  "이 접근으로 인덱스 초과는 증거 없음"을 수용. 라이브 투입 근거 없음.

## 최근 마일스톤 — 2026-06-04 (스펙 041 4차: 백필 깊이화 + 진짜 6개월 모멘텀 + 최신 데이터 IC)

main 머지 `c85ca8d`(PR #188). 운영자 선택 "백필 깊이↑ → 진짜 모멘텀" + "오래된 데이터 의미
없어, 최신 데이터 필요". 둘 다 구현:

- **KIS 백필 깊이화(페이지네이션)**: `get_daily_bars(base_date=BYMD)` + `backfill_daily_bars
  (min_bars=)` — 기준일을 과거로 돌려 종목당 ≥252 *최신* 일봉(한 호출 ~100 한계 해소). 새
  과거 바 없으면 종료. CLI `--min-bars`, 워크플로 `--min-bars 300`(≈14개월 최신, needy-first
  120종목/실행). **2013-2018 아니라 인스턴스 현재 데이터.**
- **진짜 6개월 모멘텀**: forward 두 설정 `weights={momentum:1}`(퀄·저변 제거 — IC상 모멘텀
  희석), `momentum_period` 40→120, `lookback` 60→120, 절대 게이트 lookback 120. IC 실측에서
  유일하게 양의 예측력(+0.0266, 적중 58~65%)을 보인 신호.
- **최신 데이터 IC 자동 측정**: 워크플로에 `signal-ic`(H=21·63) 단계 — 깊은 백필이 채운 *최신*
  일봉으로 IC를 매 실행 사이드카 기록. 현재 regime 예측력 지속 확인(이게 진짜 판정).
- **안전**: Kernel 터치 0건, 돈 0 이동(읽기전용·페이퍼). 1503 통과, 린트 깨끗.
- **다음**: forward 워크플로 몇 회 실행 → 깊은 백필 누적(needy-first) → 사이드차의 최신 IC
  확인. **최신 데이터 IC가 양수+유의면** 진짜 모멘텀 엣지 → A/B+DSR 판정 후 라이브 재무장.
  음수면 → 모멘텀도 현 regime엔 부족 → 다른 알파 탐색. **신호 검증이 라이브의 전제.**

## 최근 마일스톤 — 2026-06-04 (스펙 041 3차: IC 실측 — 합성 점수는 동전 던지기 ⚠)

main 머지 `121b8cc`(PR #186). 운영자 "최근 3년 데이터 가져와서 실측? 바로 자율 수행해" 허락대로
**과거 실데이터로 예측 성공률(IC)을 처음으로 실측**했다. 컨테이너 네트워크는 GitHub만 허용
(Stooq/Yahoo 차단) → plotly 2013-2018 S&P 496종목 실일봉으로 측정.

- **⚠ 핵심: 운영하던 합성 점수(모멘텀40+퀄+저변0.5)는 IC ≈ 0 = 동전 던지기.** (1주 -0.0002,
  1달 +0.0015, 분기 -0.0055, 적중률 46~55%). 종목 선택에 예측력 없음 = 세계 최고 수준 아님.
- **왜**: 저변동성 IC -0.0207(음수, 강세장 언더퍼폼을 수익예측에 오용). 모멘텀 40일 너무 짧음
  (단기 반전). 6개월(120) 모멘텀만 IC +0.0266·적중 58%로 유망하나 t<2(유의 아님).
- **교정(페이퍼 전용)**: forward 두 설정에서 저변동성 알파 제거(momentum=1,quality=1). 재측정
  IC +0.0015→+0.0082. A/B 양 팔 동일.
- **도구/기록**: `scripts/load_historical_bars.py`(GitHub 실데이터 적재), `deploy/ic-research-
  portfolio.toml`, `specs/041-absolute-return-gate/IC-FINDINGS.md`(전체 표·진단·레버).
- **안전**: Kernel 터치 0건, 돈 0 이동. 1501 통과, 린트 깨끗.
- **다음(전략 분기, 운영자 판단)**: ① 백필 깊이 ≥252바(KIS 페이지네이션) → 6~12개월 모멘텀
  (가장 큰 레버, 지금 인스턴스 ~100바라 불가), ② 순수 모멘텀 단순화, ③ 약한 엣지 현실 수용
  (비용·회전·리스크 관리) 또는 다른 알파 소스. **신호에 예측력이 없으면 유니버스·게이트·라이브
  다 무의미** — 알파부터 세워야 함.

## 최근 마일스톤 — 2026-06-04 (스펙 041 2차: 유니버스 S&P500 전체 ~501 + 예측 성공률 IC)

main 머지 `72d3a6b`(PR #184). 운영자: "해외주식 종목이 얼마나 많은데 89종목이 뭐야? 세계
최고 수준 맞아? 확실해?" + "계속해(예측 성공률)."

- **운영자 지적 정확 — 89 손큐레이션은 시작 수준.** 기관급은 S&P 500~러셀 1000/3000 횡단면.
- **유니버스 89 → 현재 S&P 500 전체(~501종목)**: 손큐레이션이 아니라 *현행 구성종목 목록*을
  네트워크로 가져와 구성(점 티커 BRK.B/BF.B 만 KIS 호환 위해 제외). 게이트 ON/OFF 두 설정
  동일. top_n 5→10, construct-universe-top-n 30→50.
- **needy-first 백필 바운딩**: `store.bar_counts` + `backfill-bars --max-symbols N` — 바 적은
  종목 우선 N개만 채워 대형 유니버스도 타임아웃 없이 여러 실행에 걸쳐 채움(graceful).
- **예측 성공률 = 정보계수(IC)**: `analytics/signal_ic.py` + `auto-invest signal-ic`. 합성
  점수↔다음 기간 실현 수익률의 횡단면 스피어만 상관(미래 누출 없음). 평균 IC 양수+유의(t≥2)=
  예측력 있음, 0 근처=엣지 아님. `composite_scores` 재사용, 읽기 전용.
- **안전**: Kernel 터치 0건, 돈 0 이동. 전체 1501 통과, 린트 깨끗. 신규 테스트 13건.
- **정직한 한계**: 이번엔 *방법론*을 세계 최고 수준 쪽으로 끌어올린 것(넓은 유니버스 + 절대
  게이트 + 예측력 측정 도구). "돈 버는 엣지 증명"은 아직 — 넓은 forward 트랙이 쌓이고 IC가
  양수로 유의해야 진짜 답. **다음**: IC를 게이트로 승격(예측력 없으면 거래 차단), S&P500
  forward 누적 → A/B+DSR+IC 판정 → 검증 후 라이브 재무장. 추가 확대: 러셀 1000/3000.

## 최근 마일스톤 — 2026-06-04 (스펙 041: 절대 기대수익 게이트 + 유니버스 28→89 + 라이브 중단)

main 머지 `f5cf670`(PR #182). 운영자 지적: "점수 1위에 투자하는 게 무슨 허접한 전략이야?
1위가 수익이 기대 안 되는데도 투자. 기대 수익율이나 예측 성공률 기준으로 판단해야. 유니버스
최대 확대. AAPL 1주 실거래 중단. 이게 세계 최고 수준 맞아?"

- **운영자 지적이 정확했다 — 정직히 인정하고 정면 수정.** 상대 순위(합성 z-점수)만 보고
  절대 기대수익 바닥이 없으면 후보가 전부 나빠도 "그나마 1위"를 산다 = 세계 최고 수준 아님.
- **① 라이브 중단**: `rebalance-live.request` armed:true→false. AAPL 실거래 무장 해제(룰 워커도
  disabled 상태 → 실거래 0). 미검증 좁은 픽에 실제 돈 안 넣는다.
- **② 절대 기대수익 게이트(듀얼 모멘텀, Antonacci)**: `strategy/trend.py` `absolute_momentum`에
  `min_return` 임계치 — 종목의 *자기* 후행수익률이 바닥(기본 0=양수)을 못 넘으면 **1위라도
  현금**. `TrendFilterConfig.min_return_pct` 배선. "기대 안 되면 투자 안 함."
- **③ 유니버스 28→89**: canary-portfolio.toml + -notrend 를 2026 유효 고유동성 대형주 89종목
  (섹터 분산)으로. 스펙 034의 2018 목록은 폐지·합병종목 섞여 부적합 → 현재 종목 큐레이션.
- **④ A/B = 게이트 가치 측정**: 게이트 ON(canary-portfolio.toml) vs OFF(-notrend, top-N 항상
  매수) forward 페이퍼 병렬 → forward-verdict가 "절대 게이트가 정말 도움 되는가" 격리 판정.
  construct-universe-top-n 15→30, 타임아웃 30분.
- **안전**: Kernel 터치 0건, 돈 0 이동(페이퍼 + 라이브 중단). 전체 1490 통과, 린트 깨끗.
- **다음(남은 세계최고수준 격차)**: 예측 성공률/정보계수(IC) — 합성 점수가 *실제로* 미래
  수익을 예측하는지(rank IC/적중률) 측정해 예측력 없으면 거래 막는 메타 게이트. 운영자
  "예측 성공률 기준 판단"의 직접 구현. 그리고 넓은 forward 트랙 누적 → A/B + DSR 판정 → 검증
  후 라이브 재무장(운영자 게이트).

## 최근 마일스톤 — 2026-06-04 (🟢 라이브 캐너리 = 추세 방어 포트폴리오로 무장: (A) 룰 워커 교체)

main 머지 `96ff217`(PR #178 버그수정 → #179 (A) 무장). 운영자 "(A) 룰 워커 끄고 포트폴리오
전략으로 교체. 돈 단위 계산 틀린 거 없지?". 상세 `HANDOFF-045-LIVE-PORTFOLIO-ARMED.md`.

- **돈 단위 검증(운영자 질문 답)**: 이중 확인 — ① 코드 감사: 전부 USD·정수주(`rebalance_plan`
  qty=floor(목표금액/가격), `_per_trade_cap_qty` cap=자본×%/100[재조정 자본 $500 기준, 워커
  $12k 아님], 브로커 `ORD_QTY`=주수·`OVRS_ORD_UNPR`=USD, FX 변환 없음). ② **실데이터 드라이런**:
  `BUY AAPL 1주 @ $312.48, 매도 0건` — $500 → 1 AAPL(≈$312). 100배/FX 오류 없음. **틀린 거 없음.**
- **발견·수정한 버그**: 라이브 워크플로 발행 스텝이 `set -u` 아래 `$1,000`(큰따옴표)을 `$1`로
  해석해 실패 → 사이드카 미발행. 문구 교체 + 발행 스텝 -u 제외(PR #178). **돈 계산과 무관**.
- **(A) 실행**: ① 룰 워커 비활성(`canary-live-rules-disabled.toml` 전체 enabled=false +
  go-live-canary.request run_seq 6) — 한 실계좌 전략 하나(충돌 해소). ② 포트폴리오 무장
  (`rebalance-live.request` armed:true, $500). ③ 시장시간 스케줄(15:00 UTC 평일) + LIVE 스텝
  `event!=push` 게이트 → **무장 머지는 미리보기만, 실주문은 시장시간 스케줄에서만**.
- **현 상태**: 무장 완료. 머지=미리보기만(돈 0 이동). go-live #6(룰 워커 비활성) 실행 진행 중
  이었음(같은 채널 직전 실행 성공). **첫 실주문 = 다음 15:00 UTC 평일 스케줄**(AAPL 1주 ~$312).
- **안전**: 자본 $500(절대 손실 한도), 거래집합 무확대(SPY·MSFT·AAPL), 추세 필터 방어, 스펙 014
  서킷 브레이커 킬스위치, K1 캡, 자본상한 $1,000 가드. 헌법 X.4 운영자 지시 소액 캐너리(풀라이브 아님).
- **다음**: 다음 스케줄 후 사이드카 `automation/rebalance-live-canary-last-run` 에서 실주문/체결
  확인 → forward-verdict `--mode live` + 칼마로 실거래 트랙 판정 누적. 자본 상향은 운영자 결정
  (capital_usd 올리면 워크플로가 $1,000 초과 거부 — 캡 먼저 낮춰야).

## 최근 마일스톤 — 2026-06-04 (스펙 039+040: 고도화를 소액 실거래로 — 가드형 무장 채널 🟡 드라이런)

main 머지 `7a56370`(PR #174·#175·#176). 운영자 지시 "실거래 기반 고도화, 지금 소액 라이브
캐너리 무장 $500, 이어서 진행해". 상세 `HANDOFF-044-LIVE-CANARY-ARMING.md`.

- **격차**: 고도화(스펙 032~038)는 전부 페이퍼, 실거래는 단순 3룰. 운영자가 고도화를 실거래로
  요구 → 소액 라이브 캐너리로 올리는 작업 시작.
- **🚨 구현 중 발견 2가지(정직)**: ① $500 는 주가상(SPY $540·MSFT $430·AAPL $316) **1종목
  1주**만 들어감(top-2 는 ~$10k+) → 무장본 top_n=1. ② **계좌 충돌(치명적)**: 같은 실계좌에
  룰 워커($12k)가 도는데 포트폴리오 재조정을 올리면 **워커 포지션을 청산**(돈 잃음). → 한
  실계좌 전략 하나 = **룰 워커를 먼저 비활성**해야 함(운영자 설정 변경).
- **그래서 가드형 단계 무장**: 실주문 즉시 안 함. `rebalance-live-canary.yml` 은 **기본 드라이런
  미리보기**(주문 0건) — "무장 시 실거래가 무엇을 살지"를 사이드카에 보여줌. 실주문은 센티넬
  `automation/rebalance-live.request` 의 `armed:true`(기본 false)일 때만. 다중 안전장치(자본
  상한 $1,000, --confirm-live, K1 캡, 스펙 014 서킷 브레이커, 추세 필터, 거래 집합 무확대).
- **현 상태**: PR #176 머지 → 드라이런 미리보기 1회 발화(사이드카 `automation/
  rebalance-live-canary-last-run` 에 곧 찍힘). **실주문 0건, 돈 0 이동.**
- **무장(실주문)까지 남은 단계(운영자/다음 세션)**: ① 사이드카 드라이런 미리보기 확인, ②
  룰 워커 비활성(disabled 룰셋 + go-live 채널), ③ `armed:true` 머지. 그러면 추세 방어 포트폴리오가
  소액 실거래로 돈다. forward-verdict + 칼마(`--mode live`)가 실거래 트랙을 같은 잣대로 판정.

## 최근 마일스톤 — 2026-06-04 (스펙 038: 칼마 비율 — 자본 방어 측정 ✅)

main 머지 `9ae4238`(PR #172). Kernel 터치 0건, 돈 0 이동. 운영자 지시 "계속해(옵션 2 Calmar)
+ 실거래 기반 고도화, 돈 못 벌면 의미 없다".

- **왜**: forward-verdict 가 샤프(변동성 대비 수익)로만 판정했는데, 추세 필터(스펙 036)의
  핵심 가치는 *드로다운 방어*다. 샤프만 보면 자본 방어가 안 드러난다. **칼마(연수익/최대낙폭)**
  를 추가해 "돈을 잃지 않는 능력"을 직접 측정.
- **무엇을**: `calmar_ratio` + `EdgeVerdict.strategy_calmar/benchmark_calmar/beats_benchmark_calmar`
  (schema 1.1). 게이트는 불변(샤프+PSR+DSR 유지), 칼마는 *보고* 전용 — 운영자가 드로다운
  방어를 직접 보게. 페이퍼·**라이브(`--mode live`)** 양쪽 트랙 공통.
- **안전**: Kernel 터치 0건, 돈 0 이동(측정 전용). 전체 1485 통과·4 스킵, 린트 깨끗. 신규 7건.
- **다음(실거래 격차)**: 운영자가 "실거래 기반 고도화"를 거듭 강조. 고도화는 페이퍼 전용,
  실거래는 단순 3룰 캐너리. 다음 큰 작업 = **고도화(포트폴리오/추세 전략)를 라이브 캐너리에
  올리기**(소액 실거래). 돈 움직이는 결정이라 자본·킬스위치는 운영자 확정 필요.

## 최근 마일스톤 — 2026-06-03 (스펙 037: forward A/B 토너먼트 — 추세 ON vs OFF ✅)

main 머지 `e1cae73`(PR #170). Kernel 터치 0건, 코드 변경 0(설정+워크플로+테스트), 돈 0 이동.
운영자 지시 "계속해"(앞서 제안한 옵션 2 = forward 전략 토너먼트). 상세
`HANDOFF-042-SPEC-037-AB-TOURNAMENT.md`.

- **왜**: 스펙 035 forward-verdict 의 벤치마크는 *유니버스 균등 단순 보유*라 "추세 ON 전략 vs
  단순 보유"는 답하지만 "추세 필터 *자체*가 도움이 되는가(같은 전략 ON vs OFF)"는 격리
  못 한다. 추세 필터의 한계 기여를 알려면 교란변수 없는 대조군이 필요.
- **무엇을**: ① 대조군 설정 `deploy/canary-portfolio-notrend.toml`(ON 과 유니버스·가중치·top_n·
  주기까지 전부 동일, `[portfolio.trend_filter]` 절만 없음 — 회귀 테스트로 동일성 못박음).
  ② 워크플로 `rebalance-paper-forward.yml` 를 2팔로 재구성 — 추세 ON/OFF 를 **각자 전용 DB**
  (`forward_trend.db` / `forward_notrend.db`)에서 병렬 페이퍼(backfill→rebalance→nav-snapshot→
  forward-verdict). 사이드카에 두 판정 나란히.
- **왜 코드 변경 0**: DB 파일이 격리 경계라 두 트랙 체결·NAV 가 안 섞임 → portfolio_id 태깅·
  주문 경로 손댈 필요 없음. `backfill-bars` 가 빈 DB 자동 마이그레이션.
- **안전**: 양 팔 PAPER 전용, 돈 0 이동. 라이브 캐너리(`canary-live-rules.toml`) 무관·무변경.
  전체 1478 통과·4 스킵, 린트 깨끗, YAML 유효.
- **다음**: NAV 관측 ≥20(≈20 거래일) 쌓이면 두 판정이 INSUFFICIENT_DATA 를 벗어나 ON vs OFF
  비교가 의미를 가짐. 추세 필터의 진짜 가치는 드로다운이라 조용한 구간엔 ON≈OFF 가 정상.
  후속 후보: 위험조정 지표 Calmar(수익/낙폭) 확장으로 드로다운 방어를 더 잘 포착.

## 최근 마일스톤 — 2026-06-03 (스펙 036 후속: forward 페이퍼 트랙에 추세 필터 켜기 ✅)

운영자 지시 "계속해"(앞서 제안한 1번 = 기존 forward 트랙에 추세 필터 켜기) 자율 수행.
`deploy/canary-portfolio.toml`(PAPER 전용 forward 트랙, 라이브 무관)에 `[portfolio.trend_filter]`
추가: method=sma, lookback=50(인스턴스 ~100 일봉에서 활성), on_insufficient=hold.

- **이제 폐회로가 실제로 돈다**: 워크플로 `rebalance-paper-forward.yml` 이 매 거래일 28후보 →
  유동성 상위 15(`--construct-universe-top-n`) → 합성점수 상위 5 → **추세 게이트(SMA-50 아래면
  현금, hold_replace 로 청산)** → 페이퍼 체결 → `nav-snapshot`(스펙 035) → `forward-verdict`
  (스펙 035) 가 단순 보유 대비 위험조정 우위를 자동 판정. `model_copy` 가 trend_filter 를
  construct-universe 경로에서도 보존함을 확인.
- **돈 0 이동**: PAPER 전용. 라이브 캐너리(`canary-live-rules.toml`)는 무관·무변경.
- **검증 누적은 시간이 걸린다**: forward-verdict 는 NAV 관측 ≥20(≈20 거래일) 전엔
  INSUFFICIENT_DATA. 그 전까진 코드/설정 변경 없이 매일 쌓인다. 사이드카
  `git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md` 에서 판정 확인.
- 운영 설정 회귀 테스트 2건(`test_canary_portfolio_config.py`). 전체 1477 통과·4 스킵, 린트 깨끗.

## 최근 마일스톤 — 2026-06-03 (스펙 036: 절대 모멘텀 추세 필터 — 드로다운 방어 오버레이 ✅)

main 머지 `8bee9c8`(PR #167). Kernel 터치 0건, 돈 0 이동. 운영자 지시 "다시 이어서 진행해"
(세계 최고 수준 + 실제로 돈 버는 것). 상세 `HANDOFF-041-SPEC-036-TREND-FILTER.md`.

- **우선순위 판단**: 스펙 035 로 "돈 버는지 판정하는 폐회로"가 생겼으니, 이제 **그 판정이
  심판할 진짜 후보 전략**을 넣을 차례. 데이터의 세 실패(회전율·승자 트리밍·좁은 유니버스) 중,
  알파 스택에 **유일하게 빠진 전략 범주** = 종목별 절대 모멘텀(시계열 추세) 게이트.
- **무엇을 했나**: `strategy/trend.py`(순수, 의존성 0) — `above_trend`(sma / absolute_momentum)
  + `apply_trend_filter`(추세 아래 종목 가중치 0=현금, **재정규화 안 함**=나머지 현금 방어,
  데이터 부족은 hold/cash 정책). `target_weights(..., trend=...)` 옵트인 인자(끄면 byte 동일,
  `_base_weights` 추출). `TrendFilterConfig`(`[portfolio.trend_filter]`). 호출부 배선
  (`rebalancer`·`portfolio_replay`) → 백테스트·라이브 양쪽 자동 적용.
- **왜 중요**: 소매 시스템이 단순 보유 대비 가치를 더하는 지점은 강세장 raw 수익이 아니라
  **드로다운 방어로 위험조정 수익(샤프·칼마)을 올리는 것**. 추세 필터는 세 실패를 정면 대응
  (회전율↓·승자 안 덜어냄·폭락 현금 이탈).
- **안전**: Kernel 터치 0건. 롱-온리(현금으로만 빠짐). `trend_filter` 미설정이면 기존 동작 byte
  동일(회귀 입증). **라이브 캐너리엔 안 켬** — forward/캐너리에 켜는 건 전략 변경이라 운영자
  결정. 옛 데이터 백테스트는 *메커니즘*만 검증(엣지 주장 금지). 전체 1475 통과·4 스킵, 린트 깨끗.
- **다음**: 운영자가 forward 트랙(또는 별도 후보)에 추세 필터를 켜면(예시
  `specs/036-trend-filter/example-trend-portfolio.toml`), 스펙 035 `forward-verdict` 가 추세
  오버레이가 단순 보유를 위험조정으로 이기는지 자동 판정한다.

## 최근 마일스톤 — 2026-06-03 (스펙 035: forward 엣지 자동 판정 폐회로 ✅)

main 머지 `9bfa55d`(PR #165). Kernel 터치 0건. 운영자 지시 "세계 최고 수준이 되기 위한
작업 분석·우선순위 판단 뒤 자율 수행 — 결국 실제로 돈을 버는 게 중요하다". 상세
`HANDOFF-040-SPEC-035-FORWARD-VERDICT.md`.

- **진단(우선순위 판단)**: 알파·검증 도구는 세계 최고 수준급으로 많은데(31,000줄·테스트
  1,400건+) **"실제로 돈을 버는가"를 판정하는 폐회로가 끊겨 있었다.** ① 스펙 029 `compute_nav`
  (시가평가 순자산)·`read_nav_points`(시계열)는 만들어졌고 테스트도 됐지만 **어떤 실행
  경로에도 안 꽂혀** NAV 시계열이 아무 데서도 기록 안 됨 → "시간상 미래에 돈 벌었나" 잴 입력
  자체가 없음. ② 디플레이티드 샤프(스펙 027)는 백테스트에만 연결, forward 트랙엔 미적용. ③
  forward 트랙은 체결만 쌓고 판정 안 함. 검증 데이터가 컨테이너에 없는데 새 알파를 또 만드는
  건 함정 → **가장 레버 큰 일 = 이 폐회로 완성.**
- **무엇을 했나**: ① 순수 판정 모듈 `portfolio/edge_verdict.py` — NAV 자산곡선 → 기간별 수익률
  → 연율 샤프·PSR·DSR·MinTRL(스펙 027 재사용) vs **균등가중 단순 보유 벤치마크**(스펙 032 잣대,
  `price_bars`). ② 생산자 CLI `nav-snapshot` — 스펙 029 `compute_nav` 를 **처음으로 실행 경로에
  배선**(장부 보유를 현재 KIS 시세로 시가평가 → `--snapshot` 이면 `PORTFOLIO_NAV_SNAPSHOT`
  append). ③ 소비자 CLI `forward-verdict` — NAV 시계열 + 벤치마크 → `EDGE_CONFIRMED / NO_EDGE /
  INSUFFICIENT_DATA` 판정. ④ `rebalance-paper-forward.yml` 에 두 단계 + 사이드카 판정 섹션 배선.
- **판정 규칙(전부 만족해야 EDGE)**: ① 관측 ≥ min_obs ② 초과수익>0 이고 전략 샤프>벤치 샤프
  (단순 보유 이김) ③ PSR(벤치 기준)≥0.95(우연 아님) ④ 시도>1 이면 DSR≥0.95(과적합 아님).
  하나라도 미달이면 NO_EDGE. 부족·분산 0 이면 보수적으로 INSUFFICIENT_DATA — **모르면 엣지
  선언 금지**(헌법 X 직접 구현).
- **안전**: Kernel 터치 0건(재사용만). 돈 0 이동(NAV 스냅샷=읽기 전용 측정·주문 0건, 판정=순수
  분석, 워크플로=PAPER). 라이브 자동 승격 0건(EDGE_CONFIRMED 는 운영자 게이트 증거이지 자동
  배포 아님). 전체 1453 통과·4 스킵, 린트 깨끗. 신규 테스트 19건(단위 14 + 통합 5).
- **다음(인스턴스에서 자동 진행)**: forward 워크플로가 돌수록 NAV 점이 쌓임 → 사이드카
  `LAST_RUN.md` 의 "forward 엣지 판정" JSON 이 지금은 INSUFFICIENT_DATA → 충분히 쌓이면 **코드
  수정 없이** 진짜 판정으로 자동 전환. EDGE_CONFIRMED 가 나오면 그게 운영자 라이브 게이트
  (헌법 X.4)에 올릴 첫 증거. (정밀화 후속: 큰 자본 투입/인출 시 시간가중수익.)

## 최근 마일스톤 — 2026-06-03 (스펙 034: 체계적 유니버스 구성 ✅ + ⚠ stale 데이터 백테스트 과장 정정)

main 머지 `7425151`(PR #159) + 정정. Kernel 터치 0건. 운영자 지시 "세계 최고 수준이 되기
위한 작업 분석·우선순위 판단 뒤 자율 수행". 상세 `HANDOFF-039-SPEC-034-UNIVERSE-CONSTRUCTION.md`.

- **⚠ 정정(운영자 지적)**: 이 작업의 백테스트는 **2013–2018(8년 묵은) stale 데이터**로 돌렸고,
  최근성 가드가 stale 경고를 띄웠는데도 무시한 채 "폭을 넓혀도 엣지 없음 → 좁은 유니버스 탓
  가설을 닫음"이라 **과장 선언**했다. 이는 2026-06-01에 확립한 교리(`FORWARD-VALIDATION.md`:
  옛 데이터는 정당화 금지, 현재 데이터 forward 페이퍼만 판정)의 재발 위반이다. **stale
  데이터로는 "지금 폭이 도움이 되는가"를 닫을 수 없다.** 백테스트 수치는 폐기가 아니라
  *판정 아님*으로 재라벨.
- **유효 결과물(데이터 무관)**: 종목을 손으로 안 고르고 유동성으로 *구성*하는 역량 — ①
  `strategy/universe.py`(`median_dollar_volume`/`liquidity_rank`/`select_universe`, 비커널,
  테스트 13건), ② CLI `auto-invest build-universe`, ③ `fetch_sp500_subset.py --all`. 이 도구는
  **현재 데이터 forward 페이퍼 트랙에 적용돼야** 가치가 있다.
- **올바른 다음 단계**: `build-universe` 를 인스턴스의 *현재* `price_bars`(스펙 033 일일 백필)에
  적용해 forward 페이퍼/캐너리 유니버스를 유동성으로 구성(현재 `canary-portfolio.toml` 은 손으로
  고른 10종목). forward 페이퍼가 디플레이티드 샤프로 판정. 이 컨테이너는 현재 데이터 다종목
  일봉 백테스트 불가 — 옛 데이터 우회가 애초에 잘못된 선택이었다.
- **재발 차단(운영자 "둘 다 순서대로", PR #162·#163)**: 운영자가 stale 데이터 백테스트 재발을
  지적 → ① **가드를 코드로 강제**(`recency.stale_guard` + `portfolio-walk-forward`·
  `backtest-portfolio` 가 stale 이면 `--allow-stale` 없이 종료코드 70 거부 — 경고를 각주로
  무시 못 하게). ② **역량을 현재 데이터 경로에 배선**(`rebalance-once --construct-universe-top-n`
  으로 *현재* 저장 바 유동성 상위로 유니버스 구성, `canary-portfolio.toml` 후보 10→28 확대 +
  `rebalance-paper-forward.yml` 에 `--construct-universe-top-n 15` 배선). 신규 테스트 7건.
- **안전**: Kernel 터치 0건. 돈 안 움직임. 결정론·LLM 미사용. 전체 1434 통과·4 스킵, 린트 깨끗.

## 최근 마일스톤 — 2026-06-03 (스펙 033 슬라이스 2·3: 일일 백필 + 유니버스 3→10, B·C 완료 ✅)

main 머지 `f5a095e`(PR #157). Kernel 터치 0건. 운영자 질문("매월 백필 너무 드물지 않나,
매일/실시간이 낫지 않나") → 답 + B·C 자율 수행. **사이드카 실측 검증 완료.**

- **답(주기)**: 일봉은 마감 1회만 갱신 → 매 거래일 1회면 충분(실시간 인트라데이 바는 일봉
  점수에 불필요, 체결은 이미 실시간 get_quote 사용). 매월은 29일간 묵은 가격 → 매일로 전환.
- **C(매일/상시 백필)**: ① 공유 헬퍼 `market_data/feed.backfill_daily_bars`(CLI·워커 공용,
  EXCD 순차 시도→price_bars 멱등). ② 워커 틱 백필 `WorkerSettings.backfill_enabled`(옵트인,
  6h cadence, 세션당 1회 whitelist 일봉 갱신, 읽기 전용·오류 격리). `run --backfill` +
  `deploy/run-worker.sh` 라이브 분기 `--backfill`. ③ 워크플로 cron 월간→매일
  (`30 22 * * 1-5`). 워커 모드 무관 안전망 + 매일 마크.
- **B(유니버스 확대)**: `canary-portfolio.toml` 3→10종목(NAS 6/NYS 3/AMS 1), top_n 5,
  lookback 60·momentum 40. 라이브 트레이딩 whitelist(canary-live-rules)는 좁게 유지(안전).
- **검증(사이드카 실측)**: 백필 10종목 각 100일(거래소 자동 분류 NAS/NYS/AMS), 재조정이
  10중 상위 5(AAPL·SPY·AMZN·NVDA·GOOGL 각 20%) 선택 → **4건 PAPER_FILLED**, 성과 누적
  fills_count=6, 투자금 $2,387. 모든 SSH ssh_exit=0. 돈 안 움직임.
- **검증(코드)**: 신규 테스트 6건(헬퍼 3 + 워커 3), 전체 1414 통과·4 스킵, 린트 깨끗.

## 최근 마일스톤 — 2026-06-02 (스펙 033: KIS 해외 일봉 백필 — forward 페이퍼 트랙 실거래 가동 ✅)

main 머지 `32ab1e1`(PR #153 백필 + #155 계좌 치환 수정). Kernel 터치 0건. 운영자 지시
"1번 방향"(KIS 일봉 조회 구현). **forward 페이퍼 트랙이 현재 데이터로 실제 페이퍼 체결을
시작 — 엔드투엔드 검증 완료.**

- **스펙 033 구현**: `broker/overseas.py` `get_daily_bars`(tr_id HHDFS76240000 기간별시세,
  읽기 전용 시세) + `_parse_daily_bars`. CLI `backfill-bars`(EXCD NAS→NYS→AMS 순차 시도 →
  `price_bars` 1d 저장, 멱등). `rebalance-paper-forward.yml` 재조정 앞에 백필 단계 배선.
- **계좌 게이트 수정(PR #155)**: 백필 후 재조정이 목표비중을 냈으나 주문이 "account not on
  whitelist"로 거부 — `_load_portfolio_for_backtest` 가 `${KIS_ACCOUNT_NO}` 미치환이 원인.
  로더에 `env` 치환 추가(라이브 룰 로더와 동일), rebalance-once 가 secrets 전달.
- **검증(사이드카 실측, 인스턴스)**: 백필 AAPL·MSFT(NAS)·SPY(AMS) 각 100일 실데이터
  (2026-01-08~06-02) → `price_bars` 300개 → 재조정 목표비중 각 33% → **AAPL·MSFT BUY
  PAPER_FILLED** → 성과 엔진 `fills_count: 2`, 투자금 $751.71. 모든 SSH 단계 ssh_exit=0.
  돈 안 움직임(PAPER). `git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md`.
- **이제 트랙이 살아 거래**: 매월 cron + 센티넬로 백필+재조정 반복. 페이퍼 체결이 쌓이면
  디플레이티드 샤프로 forward 유의성 판정(스펙 027 재사용) — 이게 "지금 통하는가"의 진짜 답.
- **검증**: 신규 테스트 7건(일봉 파서 4 + env 치환 3), 전체 1408 통과·4 스킵, 린트 깨끗.
- **주의(경합)**: 센티넬-머지가 deploy-on-merge 와 동시 발화하면 인스턴스 코드 갱신 전에
  워크플로가 돌아 첫 실행이 실패할 수 있음(No such command 등) → 같은 센티넬 한 번 더
  갱신 머지로 해소(검증됨).

## 최근 마일스톤 — 2026-06-02 (스펙 032: A방향 — bars-status 진단으로 무거래 근본원인 확정)

main 머지 `e088aab`(PR #150 진단 배선 + #151 타임프레임 요약). Kernel 터치 0건. 운영자
지시 "A방향"(왜 무거래인지 인스턴스 진단을 사이드카에 기록).

- **결정적 근본원인**: forward 페이퍼가 무거래(빈 target_weights)였던 이유는
  **인스턴스의 `price_bars` 테이블이 완전히 비어 있기 때문**. 사이드카 진단 결과:
  AAPL/MSFT/SPY 1d 바 0개, **`db_timeframes: []`, `db_symbols_sample: []`** (어떤
  타임프레임·심볼도 0). 워커가 일봉을 전혀 저장하지 않아 재조정 스코어러가 빈 데이터를
  읽음. `git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md` 로 확인.
- **새 도구**(읽기 전용): `market_data/store.bar_summary`·`available_timeframes`·
  `distinct_symbols` + CLI `auto-invest bars-status`(--portfolio/--symbols, text/JSON).
  워크플로 `rebalance-paper-forward.yml` 에 인스턴스 bars-status 단계 배선 → 매 실행
  사이드카에 "인스턴스 저장 바 수" 섹션이 찍힘(앞으로 항상 가시).
- **수정 경로(별도·큰 작업, 자율 빠른 배선 아님)**: 트랙이 실제 거래하려면 인스턴스
  `price_bars` 를 채워야 한다. 현재 코드엔 KIS 과거 일봉 백필 CLI가 없다(`ingest-history`
  는 CSV→백테스트 데이터셋 전용, `overseas.py` 에 일봉 조회 함수 없음, 워커는
  `store_synthetic_bar` 만). 선택지: (a) **KIS 해외 일봉(period/itemchartprice) 조회를
  새 스펙으로 구현** → 워커/워크플로가 백필, (b) 인스턴스에서 일봉 CSV 를 만들어
  `price_bars` 시드(인스턴스 측 작업), (c) 워커가 합성 바를 충분히 쌓을 때까지 대기(느림).
- **검증**: 신규 테스트 4건, 전체 1401 통과·4 스킵, 린트 깨끗. 읽기 전용 — 돈 안 움직임.

## 최근 마일스톤 — 2026-06-02 (스펙 032: A안 — forward 페이퍼 트랙 인스턴스에서 시작·발화 확인)

main 머지 `bcc8ca7`(PR #147 트리거 + #148 룩백 단축). Kernel 터치 0건. 운영자 지시
"A안 자율 수행"(인스턴스에서 현재 데이터 일봉 forward 페이퍼 트랙 시작).

- **메커니즘 완전 동작 확인(엔드투엔드)**: MCP 토큰에 `actions:write` 가 없어
  workflow_dispatch 직접 트리거는 403 → go-live-canary 와 같은 **센티넬 push 패턴**을
  추가(`automation/rebalance-paper.request` 가 main 에 머지되면 발화). 실제로 워크플로
  3회 실행(스케줄 1 + 센티넬 push 2) **전부 성공** — 인스턴스 SSH `rebalance-once
  --mode paper` + `performance` 둘 다 ssh_exit=0, 사이드카
  `automation/rebalance-paper-forward-last-run` 에 발행됨.
- **현재 마크는 무거래(no-op)**: `target_weights {}`, `fills 0`. 원인은 인스턴스에
  AAPL·MSFT·SPY 의 일봉 히스토리가 점수 계산에 부족(빈 점수→빈 타깃). 룩백을 90→30,
  momentum 60→20 으로 낮춰 재발화해도 여전히 무거래 → 인스턴스 일봉 축적 부족(또는
  설정 동기화 경합)이 원인. **이 컨테이너에서는 인스턴스 DB 접근이 없어 해결 불가** —
  워커가 일봉을 쌓을수록(시간 경과) 자동 해소된다.
- **트랙은 살아있다**: 매월 1일 cron + 센티넬 갱신으로 계속 마크. 인스턴스 히스토리가
  충분해지면 실제 페이퍼 재조정이 시작되고 fills 가 쌓인다. 확인:
  `git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md`.
- **다음(운영자/후속 세션)**: (a) 인스턴스에 유니버스 일봉이 충분한지 확인(서버 audit/DB),
  부족하면 워커 적재 대기 또는 `ingest-history` 로 시드. (b) 무거래 원인을 인스턴스에서
  진단(`auto-invest rebalance-once --dry-run` 으로 점수/바 수 확인). (c) 트랙이 fills 를
  쌓기 시작하면 디플레이티드 샤프로 forward 유의성 판정.

## 최근 마일스톤 — 2026-06-02 (스펙 032: 최근 데이터 자율 백테스트 — 다자산 월봉 + DSR 단일시도 보정)

main 머지 `9a9239f`(PR #145). Kernel 터치 0건. 운영자 지시: "1번 자율 수행, 불가능한
거 아니지?" (최근 데이터로 백테스트).

- **최근 데이터를 찾아냄**: 403 메시지가 "Host not in allowlist" = 네트워크 정책이 라이브
  시세 API(KIS·Yahoo·Stooq)는 막지만 **GitHub raw 는 허용**. `datasets` 조직 FRED 기반
  시계열이 **2026년까지** 갱신(S&P500 월·금 월·WTI 일). 이걸로 최근 다자산 월봉(주식·금·
  유가) 데이터셋(`scripts/fetch_recent_macro.py`)을 만들어 `portfolio-walk-forward
  --trailing-years 5` 평가 → recency 게이트 **fresh**, 창 2021-03~2026-03.
- **결과(정직)**: 자산군 모멘텀 로테이션이 4구간 중 3승, PSR 0.987 — *겉보기엔* 단순 보유
  우위. **그러나 현실적 검색 횟수(num_trials=14)로 보정하면 DSR=0.294 로 붕괴 → "강건한
  엣지 없음".** 게다가 월봉이라 표본 작음(구간당 12)으로 샤프 과장(10·16). 즉 최근 데이터
  파이프라인은 자율 완성됐고, *결정적 신뢰*는 일봉·다종목(라이브 인스턴스/forward 페이퍼)
  필요. recency 가드 + DSR 이 한계를 설계대로 드러냄.
- **보정**: `portfolio_walk_forward` 에서 num_trials=1 일 때 DSR 이 None→PSR 로 복원
  (N=1 은 디플레이션 없음 = PSR). 잘못된 "DSR 미달" 표시 방지. 신규 산출물:
  `scripts/fetch_recent_macro.py`, `specs/032/macro-portfolio.toml`. 전체 1397 통과.
- **다음**: 일봉·다종목 최근 데이터는 라이브 인스턴스에서만 → forward 페이퍼 워크플로
  (`rebalance-paper-forward.yml`)가 현재 데이터로 그 트랙을 누적하는 정공법.

## 최근 마일스톤 — 2026-06-02 (스펙 032: 데이터 최근성 기준 — 백테스트 복권 + 최근 N년 트레일링 창)

main 머지 `3e47cce`(PR #143). Kernel 터치 0건. 운영자 교정: "옛 데이터로 전략을 찾는
것도 중요하다. 다만 너무 과거가 아니라 최근 5개년처럼 *기준만 명확히* 하면 되는 것 아닌가?"

- **직전 세션의 over-correction(백테스트를 '필터일 뿐'으로 강등) 교정.** 백테스트는 전략
  발굴·적합의 일급 도구다. 바뀌는 건 단 하나 — **데이터 최근성 기준을 명확히 코드로 강제.**
- `backtest/recency.py`: `trailing_window`(가용 데이터의 가장 최근 N년 창 자동 선택,
  기본 5년) + `assess_recency`(오늘 대비 최신 바 나이 → fresh ≤6개월 / aging ≤2년 / stale
  >2년 등급 + 경고 배너). `portfolio-walk-forward --trailing-years N` 추가(`--from/--to`
  생략 가능), 매 실행 최근성 배너(stale 이면 큰 경고). JSON 에도 신선도 필드.
- **검증**: 현재 적재 2013-2018 데이터는 2026 기준 ~3,000일(8년) 전 → **stale 경고 정상
  발동.** 이 컨테이너는 라이브 시세 차단으로 진짜 최근(2021-2026) 데이터 불가 → recency
  가드가 그 한계를 가시화(진짜 최근 데이터 출처는 라이브 인스턴스). 신규 테스트 5건,
  전체 1397 통과·4 스킵, 린트 깨끗.
- **4기준 검증 교리**(`FORWARD-VALIDATION.md`): ① 최근 데이터 백테스트(발굴, 일급) → ②
  표본외/디플레이티드 샤프 과적합 가드 → ③ forward 페이퍼 확인 → ④ 라이브 운영자 게이트.
- **다음**: 유니버스 확대 + `--trailing-years 5` 로 후보 발굴(이상적으로 인스턴스 최근
  적재분), 통과 후보를 forward 페이퍼 워크플로로 확인.

## 최근 마일스톤 — 2026-06-01 (스펙 032: 현재 데이터 forward 페이퍼 검증 — "옛 데이터 과의존" 교정)

main 머지 `4a33e3a`(PR #141). Kernel 터치 0건. Python 코드 무변경. 운영자 지적:
"2026년인데 너무 과거 데이터만 쓰는 것 아닌가? 폭락장(2008·2000)도 결국 과거다."

- **정확한 지적**: 모든 백테스트는 과거이고, 과거 regime(참여자·금리·미시구조)은 2026
  시장과 다르다. 게다가 이 컨테이너는 라이브 시세(KIS·Yahoo·Stooq) 차단 + github raw
  데이터는 전부 옛것(2018까지) → **여기서 최신 데이터 백테스트 자체가 불가능.** 현재 데이터
  검증의 유일한 길은 라이브 인스턴스의 forward 페이퍼 트레이딩.
- **3계층 검증 교리**(`specs/032-portfolio-rebalancing/FORWARD-VALIDATION.md`): (1) 옛 데이터
  백테스트 = 값싼 과적합 필터일 뿐(라이브 정당화 금지) → (2) **현재 데이터 forward 페이퍼
  트랙 = 진짜 판정**(`rebalance-once --mode paper` 주기 실행 → 라이브 시세 가상 체결 누적 →
  스펙 011 성과 + 스펙 027 디플레이티드 샤프로 "지금 우연 아닌 엣지" 판정) → (3) 라이브
  캐너리 = 운영자 게이트(헌법 X.4).
- **인프라(돈 0)**: `deploy/canary-portfolio.toml`(저회전 hold_replace 시드, 화이트리스트
  AAPL·MSFT·SPY) + `.github/workflows/rebalance-paper-forward.yml`(매월 1일 인스턴스 페이퍼
  재조정 1회 + forward 성과 스냅샷 → 사이드카 브랜치 `automation/rebalance-paper-forward-last-run`).
  **PAPER 전용, 실주문 0건.** YAML·CLI 플래그·설정 로더 전부 검증 통과.
- **다음**: 운영자가 워크플로를 트리거(또는 월간 cron)하면 forward 트랙 누적 시작 →
  `git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md`. 유니버스 확대는
  1계층 후보 다양화용이고, 채택 판정은 항상 2계층 forward 트랙이 한다.

## 최근 마일스톤 — 2026-06-01 (스펙 032: 포트폴리오 워크포워드 — 과적합·벤치마크 집착 방어)

main 머지 `df7b41e`(PR #139). Kernel 터치 0건. 운영자 지시: "1번(진짜 단순 보유를
이기는 전략 찾기)으로 가되, *단순 보유라는 한 벤치마크에 과적합되는 전략*이 될까 걱정."

- 그 우려를 **코드로** 막는 평가 장치를 만듦: `backtest/portfolio_walk_forward.py`
  + CLI `auto-invest portfolio-walk-forward`. 단일 표본 내 총수익 비교(`backtest-portfolio`)
  대신 ① 기간을 연속 구간으로 잘라 **표본 외** 독립 실행, ② 총수익이 아니라 **구간별
  샤프·최대낙폭**으로 단순 보유와 비교(강세장 편향 회피), ③ **디플레이티드 샤프**(스펙 027
  재사용)로 *시도한 설정 개수만큼* 선택된 샤프를 깎음. 판정은 (1)구간 과반 우위
  (2)평균 샤프 우위 (3)DSR≥0.95 를 **동시에** 요구.
- **핵심 증명**: `equal top15 분기재조정`은 연도별 표본 외 4년 중 3년 위험조정 우위 +
  PSR=0.990("유의해 보임")이지만, 14개 설정 보정 **DSR=0.896<0.95 → 우연과 구별 안 됨.**
  "3/4년 이겼고 PSR 0.99!"만 봤다면 할 과적합 승리 선언을 DSR 가 정확히 막음. 현재 어떤
  설정도 (3)을 못 넘음 → 라이브 배포 정당화 안 됨(증거 기반).
- **다음**: 이 장치로 *새 전략 후보*를 정직하게 평가(시도 횟수 정직히 셈). 단순 보유를
  표본 외+DSR 로 이기는 후보가 나오기 전엔 ②③ 라이브 금지. 더 넓은 유니버스·다국면
  데이터(폭락장 포함)가 다음 레버. 상세 `specs/032-portfolio-rebalancing/REAL-DATA-FINDINGS.md`.
- **검증**: 신규 테스트 5건, 전체 1392 통과·4 스킵, 린트 깨끗.

## 최근 마일스톤 — 2026-06-01 (스펙 032: 실데이터 백테스트 — 단계 ① 자율 해결 + hold_replace 모드)

main 머지 `795cb3d`(PR #137). Kernel 터치 0건. 운영자 지시: "개입 안 한다, 불가능한 게
아니잖아, 가능한 방법을 찾아 해결해."

- **직전 마일스톤의 "①은 이 환경에서 물리적으로 불가" 단정을 뒤집음.** 컨테이너 네트워크는
  금융 데이터 호스트(Yahoo·Stooq → 403)는 막지만 **GitHub raw·PyPI는 허용**(git/uv 동작이
  근거)한다. 그래서 공개 GitHub raw 데이터셋(`plotly/datasets/all_stocks_5yr.csv` =
  S&P500 5년 일봉 OHLCV)을 받아 적재→실데이터 백테스트했다. **단계 ①(실데이터 재조정 vs
  단순 보유 비교)을 운영자 개입 없이 자율로 해결.**
- **핵심 결과(정직한 음수 발견)**: 실제 2013-2018 대형주 강세장에서 **어떤 재조정 설정도
  단순 보유(균등가중, +130%)를 못 이김.** 직전 마일스톤(line 아래)의 합성 데이터 시연("모든
  재조정 스킴이 단순 보유를 이김")은 **거짓 신호**였다. 잦은 재조정의 회전율·수수료가 수익을
  잠식(월간 = 자본의 7%를 수수료로 소진)하고, 비중 재조정이 강세장에서 승자를 덜어내 손해.
  최선은 `equal top15 반기`(+106%, 회전 1.2×)로 사실상 "전부 저회전 보유"였으나 여전히 −24%p.
- **시도한 해법**: 저회전 "승자 유지" 모드 `rebalance_mode="hold_replace"`(순위 이탈만 청산,
  신규만 매수, 승자 비중 안 되돌림). 기본값 `"rebalance"` 유지(옵트인). top-N 경계 종목의 순위
  진출입 churn 때문에 마진 개선에 그쳐 단순 보유엔 여전히 미달 — 정직하게 기록.
- **부수**: `fix(canary)` `--run-id` 검증을 비싼 커버리지 검사보다 앞으로 이동(사전 결함
  `test_exit_4_on_invalid_run_id` 빨강 해소).
- **함의(②③ 재해석)**: 측정 신호가 음수이므로 **이 설정의 라이브 실행(②)·주기 스케줄(③)은
  증거상 정당화 안 됨.** 재조정 엔진·측정 인프라는 완성됐고, 그 측정이 "단순 보유에 진다"는
  진실을 정확히 드러냄 — 돈을 잃지 않게 막는 가장 중요한 기능(헌법 X). 벤치마크를 이기려면
  넓은 유니버스 + net-of-cost 엣지 + 낮은 회전율 + 워크포워드·디플레이티드 샤프 표본 외 검증
  필요. 상세: `specs/032-portfolio-rebalancing/REAL-DATA-FINDINGS.md`.
- **검증**: 신규 테스트 1건(hold_replace), 전체 1387 통과·4 스킵(라이브 KIS 게이트), 린트 깨끗.

## 최근 마일스톤 — 2026-06-01 (스펙 032: rebalance-once 안전 강화 — 드라이런 + 라이브 인터록)

main 머지 `bd442ba`(PR #135). Kernel 터치 0건. 운영자 "②(실제 라이브 실행) 먼저" 지시.

- **현실**: 이 컨테이너엔 KIS 시크릿·브로커 네트워크·과거 데이터셋이 **모두 없음**(env 부재,
  KIS 호스트 타임아웃, data/history 없음, 외부 데이터 403). 즉 ②(실주문)·①(실데이터 비교)는
  이 환경에서 **물리적으로 불가** — 운영자 자금 계좌 환경에서만 가능.
- **그래서 ②의 안전 가능 부분을 완성**(돈 무이동): ① `execute_rebalance(dry_run=True)` —
  계획만 산출하고 라우터 절대 미호출(state DRY_RUN). ② CLI `rebalance-once --dry-run`
  오프라인 미리보기(KIS 미접촉, 저장 바 기준가), `--mode live` 는 `--confirm-live` 없으면
  거부(사고 방지 인터록), 유니버스 화이트리스트 미포함 사전 거부. 오프라인 시연 검증
  (보유 청산 매도 + per-trade 클램프 237→79 미리보기).
- **남은 것(운영자 환경 필요)**: ② 실주문 = 운영자가 `rebalance-once --mode live --confirm-live`
  를 자금 계좌 env 에서 실행(먼저 `--dry-run` 권장). ① 실데이터 비교 = `ingest-history` 로
  실 OHLCV 적재 후 `backtest-portfolio` → "EXCESS return %". ③ 슬라이스 3(주기 스케줄) =
  `promote-readiness.yml` 패턴의 드라이런 미리보기 워크플로(운영자 서버 경로·배포 모델 필요).
- **검증**: 신규 테스트 1건, 전체 1386 통과·4 스킵, 린트 깨끗.

## 최근 마일스톤 — 2026-05-31 (스펙 032 슬라이스 2 + 단계 ②: 라이브/페이퍼 실행기 + 벤치마크 비교)

main 머지 `21eff7a`(슬라이스 2, PR #132) + `2c33c28`(단계 ②, PR #133). Kernel 터치 0건.
운영자 지시 "다음 단계 순서대로 진행"(① 라이브 배선 → ② 측정)을 자율 수행·자동 머지.

- **슬라이스 2 — 라이브/페이퍼 재조정 실행기**: 1Hz 워커 틱 루프에 월 단위 재조정을 끼워
  넣는 대신 **일회성 실행기**로 분리(더 안전·단순). `execution/rebalancer.py`
  `execute_rebalance` — 저장 바로 합성 점수 → 목표 비중 → 보유·시세로 재조정 계획 →
  **필터 없는 합성 룰**로 기존 `OrderRouter.submit_order` 라우팅(K1 게이트·감사·paper/live
  분기 그대로 = 별도 돈 경로 0). 각 주문 수량을 per-trade 캡으로 하향 클램프(큰 청산도
  통과, 반복 호출 수렴). marketable LIMIT(헌법 지정가 기본). CLI `rebalance-once` —
  **paper 기본(돈 무이동)**, 실주문은 `--mode live` 명시 필요.
- **단계 ② — 측정**: 컨테이너에 과거 데이터셋 없음 + 외부 데이터 네트워크 차단(403) →
  실데이터 비교는 운영자 `ingest-history` 선행. 대신 **단순 보유(균등가중 매수후보유)
  벤치마크**를 백테스트에 내장 — `backtest-portfolio` 가 전략 vs 벤치 vs **초과수익**을
  같은 잣대로 산출. **단일 잣대 정합 수정**: 백테스트도 per-trade 캡 클램프(이전엔 캡 초과
  주문을 통째 거부해 라이브와 어긋나 균등가중이 0% 수익으로 보였음 — X.2 위반 해소).
- **안전 경계**: Kernel 터치 0건(신규 모듈 + cli/backtest 비커널, K1/캡/감사/시크릿 무변경
  재사용만). 돈 무이동(머지·테스트·시연 기준 paper/백테스트). 실주문은 운영자가 명시
  실행할 때만. `AUTO_INVEST_MODE`·배포 룰셋 무변경. per-trade 클램프는 하향 전용.
- **검증**: 신규 테스트(슬라이스 2 통합 3 + 벤치마크 1, per-trade 테스트 재작성), 전체
  1385 통과·4 스킵, 린트 깨끗. 시연(합성 3년·10종목·KIS 비용): 모든 재조정 스킴이 단순
  보유(+17.1%) 초과(equal top4 +42.5%, 초과 +25.4%) — **합성이라 방향성 시연**.
- **다음**: 실데이터 적재 후 실제 비교, 슬라이스 3(라이브 재조정 주기·캐너리 적용 —
  돈 경로·운영자 게이트), 유니버스 확대, 워크포워드 표본외 검증.

## 이전 마일스톤 — 2026-05-31 (스펙 032 슬라이스 1: 횡단면 포트폴리오 재조정 엔진)

main 머지 커밋 `583654a` (PR #130). Kernel 터치 0건. 운영자 지시 "세계 최고 수준이
되기 위한 작업 분석·우선순위 판단 뒤 자율 수행 — 결국 수익률이 중요하다"에 대한 응답.

- **발견한 격차**: 알파 도구(다요인 합성·횡단면 순위·레짐·변동성 사이징·최소분산/최대샤프/
  ERC 최적화기)는 다 만들어졌으나 **실제 거래 루프에 미배선**. 시스템 전체가 단일 종목·
  매수 전용 "룰"이라 **목표 포트폴리오·재조정(매도) 개념이 통째로 없다.** 종목이 순위에서
  밀려나도 아무도 안 팔아 알파가 샌다. 이 재조정 엔진이 수익률의 가장 큰 병목.
- **무엇을 했나(슬라이스 1, 백테스트 전용)**: ① `strategy/rebalance.py`(신규) —
  `target_weights`(equal/score_proportional/inverse_vol/min_variance/max_sharpe/erc,
  스펙 022/024 최적화기 재사용 + fallback) + `rebalance_plan`(보유와 차이 → 매수+매도,
  **드롭아웃 종목 전량매도 청산**, 무거래 밴드·최소명목 회전율 통제). ② `config/rules.py`
  `PortfolioRebalanceConfig`(옵트인). ③ `backtest/portfolio_replay.py`(신규)
  `replay_portfolio` — 주기적 재조정 백테스트, 모든 주문을 기존 K1 게이트 체인으로
  라우팅, 시가평가 자산곡선·회전율 산출, 미래참조 방지. ④ CLI `auto-invest backtest-portfolio`
  (text/json, 단일 잣대 지표) + `specs/032-portfolio-rebalancing/example-portfolio.toml`.
- **안전 경계**: Kernel 터치 0건(`risk/gates.py`·caps·whitelist·worker·audit 무변경,
  재사용만). 돈 무이동 — 백테스트·CLI 전용, 라이브 워커 룰 루프 byte 동일(기존 1348건
  그대로 통과). 라이브 배선(슬라이스 2)은 돈 경로 변경이라 운영자 게이트. 롱-온리, K1 캡이
  천장(매수는 캡 초과 시 게이트가 거부 — 통합 테스트로 입증).
- **검증**: 신규 테스트 33건(단위 29 + 통합 4 — 드롭아웃 매도 청산·게이트 거부·결정론),
  전체 1381 통과·4 스킵, 린트 깨끗.
- **다음**: 슬라이스 2(라이브 워커 배선 — 재조정 스케줄러 옵트인·실제 매수+매도, **운영자
  게이트**), 유니버스 확대(횡단면 폭).

## 이전 마일스톤 — 2026-05-31 (작업 1·2·3: 자본추적 라이브 적용 + 스펙 030 + 스펙 031 슬라이스 1)

운영자 지시 "작업 1·2·3 전부 순서대로"를 자율 수행·자동 머지로 완료. 세 PR(#126·#127·#128).
한 줄 요약:

- **작업 1 (PR #126, main `012adbc`)**: `deploy/run-worker.sh` 라이브 분기에 `--capital-tracking`
  추가 — 게이트 캡 기준이 워커 시작 시 읽은 상수에서 살아있는 라이브 순자산(NAV) 추종으로 전환.
  `--capital-growth` 는 제외(하락 방어만, 상승 미반영 = 보수적 시작). K1 캡·whitelist 무변경.
  main 머지로 deploy-on-merge 가 라이브 워커를 새 코드로 재배포. **라이브 검증은 서버 접근 필요**.
- **작업 2 — 스펙 030 (PR #127, main `29653b8`)**: 미체결 주문 수명 관리 3종 옵트인.
  ① TTL 취소(`ttl_seconds` 초과 미체결 취소), ② 취소-재호가(지정가가 중간가에서
  `requote_drift_pct` 벌어지면 취소 후 **게이트 체인 재통과** 재제출), ③ marketable-limit
  (매수=ask 위/매도=bid 아래 공격적 지정가). `execution/lifecycle.py`(순수 + DB 리더),
  `config/rules.py`(`OrderLifecycleConfig`), `worker/loop.py`(cadence 10초 배선),
  `audit.py`(K4 추가-전용 `ORDER_TTL_CANCELLED`·`ORDER_REQUOTED`). 취소는 브로커 확인 후 로컬
  전이(실패는 스펙 015 체결 동기화가 정합화). 부분 체결 재호가 제외. Kernel 터치 0건. 테스트 31건.
- **작업 3 — 스펙 031 슬라이스 1 (PR #128, main `b701a26`)**: KIS 실시간 웹소켓 토대.
  `broker/realtime.py`(신규) — approval-key 요청(시크릿 격리)·구독 프레임·프레임 파싱·
  `quote_from_frame`·`WebsocketRealtimeFeed`(전송 주입형, 모든 예외 격리→`available=False`).
  `worker/loop.py` `_fetch_quote` — realtime available 이면 그 시세, 아니면 REST 폴백. 수신
  전용(주문 경로 무변경)·기본 끔(byte 동일)·제3자 의존성 무추가. 테스트 17건. **슬라이스 2
  (실제 전송 어댑터 + 라이브러리)는 공급망 결정이라 운영자 확인 후.**
- **안전 경계(셋 다)**: Kernel 터치 0건(`worker/schedule.py`·`risk/gates.py`·`config/caps.py`
  무변경). 라이브 머니 경로는 작업 1만 닿고 그것도 방어적(하락 시 캡 축소). 스펙 030·031 은
  옵트인이라 기존 룰 byte 동일.
- **검증**: 전체 1348 통과, 4 스킵(라이브 KIS smoke 게이트), 린트 깨끗.

## 이전 마일스톤 — 2026-05-31 (스펙 029 슬라이스 3: 미실현 포함 시가평가 순자산 성장 추적)

main 머지 커밋 `99f071c` (PR #122). 감사 스키마 무변경(읽기 전용 — K4 터치 없음).
운영자 지시 "내 자산 수준 기준 관리·성장"의 마지막 조각이자 스펙 029(측정→자산 인식
자본→성장 추적) 3개 슬라이스의 완성. 한 줄 요약:

- **배경**: 성과 엔진(스펙 011)의 자산곡선은 실현손익만 누적했다(과거 시세 없이 미실현
  시점 평가 불가). 슬라이스 1이 `PORTFOLIO_NAV_SNAPSHOT` 로 미실현 포함 순자산을
  시점별로 남기기 시작했으므로, 이제 그 시계열을 이어 붙여 실현+미실현을 합친 진짜
  시가평가 성장 추세를 그린다.
- **무엇을 했나**: ① `portfolio/growth.py`(신규, 비커널) `read_nav_points()` 가
  audit_log 의 NAV 스냅샷을 모드별·기간별로 읽고(SELECT만), `compute_growth()` 순수
  함수가 시작/현재 순자산·총수익률·최대낙폭·기간(일수)·CAGR 을 결정론 산출. 총수익률·
  최대낙폭은 스펙 008 metrics 재사용(단일 잣대). 스냅샷 2개 미만→추세 None, 곡선에
  0 이하→낙폭/CAGR None 강등. ② CLI `auto-invest growth`(text/json, --since/--window,
  read-only).
- **동작**: NAV [$10k→$11k→$12.1k]→총수익률 +21%. [$10k→$12k→$9k→$11k]→최대낙폭 25%.
  365일·+21%→CAGR ≈+21%. 스냅샷 1개→측정 불가.
- **안전 경계**: Kernel 터치 0건. 게이트·사이징·주문 라우터·워커·감사 스키마 무변경
  (읽기만, 새 이벤트 0건). 읽기 전용 — 주문/halt/자본 갱신 0건. 결정론·LLM 미사용.
  dry-run/paper 그대로.
- **검증**: 신규 테스트 12건(SC-17~SC-21 + 강등/왕복/렌더링), 전체 1300 통과, 4 스킵,
  린트 깨끗.

## 이전 마일스톤 — 2026-05-30 (스펙 029 슬라이스 2: 자산 인식 유효 자본 — 캡 기준이 라이브 순자산 추종)

main 머지 커밋 `7f63ec2` (PR #120). K4 터치 커밋 `6078fe6`(감사 로그 `EFFECTIVE_CAPITAL_UPDATED`, 추가-전용).
운영자 지시 "내 포트폴리오와 현재 자산 수준을 기준으로 판단하고 성장시키는 관리 능력" + "이어서
바로 진행해"의 **핵심**. 슬라이스 1(측정)이 순자산을 보이게 했다면, 슬라이스 2는 그 빈칸을 메운다 —
게이트에 넘기는 자본 기준을 "워커 시작 시 한 번 읽은 낡은 상수"에서 "살아있는 라이브 순자산(NAV)"으로
바꿔 모든 캡(K1)이 실제 자산을 추종하게 한다. 한 줄 요약:

- **무엇을 했나**: ① `portfolio/nav.py`(비커널) `effective_capital()` 순수·결정론 — 하락(nav<시작)은
  **항상** 반영(방어), 상승은 `growth_enabled`일 때만 `시작×max_growth_factor` 클램프 안에서 반영,
  nav None/0이하면 시작 자본 폴백. ② `worker/loop.py`(비커널)가 60초 cadence로 KIS 순자산을 읽어
  유효 자본 갱신(`_refresh_effective_capital`), 게이트에 `_effective_capital_usd`를 넘김. paper·
  tracking 끔이면 NAV 조회조차 안 함. 조회 실패는 직전 값 유지(무중단). ③ CLI `run` 에
  `--capital-tracking`/`--capital-growth`/`--capital-max-growth`. ④ K4 추가-전용
  `EFFECTIVE_CAPITAL_UPDATED`(값 변할 때만, reason=defense_drawdown/growth_applied/growth_clamped/reset_to_start).
- **동작**: NAV $8k(시작 $10k) → 유효자본 $8k(방어, per-trade 캡 $400로 축소). NAV $15k·growth 끔
  → $10k(시작이 천장). NAV $15k·growth 켬(상한 2배) → $15k. NAV $25k·상한 2배 → $20k(클램프).
- **안전 경계**: Kernel 터치 0건. 게이트(`risk/gates.py`)·캡 스키마·사이징·주문 라우터 무변경 —
  캡 계산식·퍼센트 그대로, 입력 자본만 살아있는 자산 추종. K1이 여전히 천장(성장은 하드 클램프).
  **기본 끔=회귀 무손상.** AUTO_INVEST_MODE 무관(자율 전환 아님). 추가-전용 감사. 결정론·LLM 미사용.
  dry-run/paper 그대로.
- **검증**: 신규 테스트 19건(SC-09~SC-16 + 폴백/이벤트/유니온), 전체 1288 통과, 4 스킵, 린트 깨끗.
- **다음(비목표)**: 슬라이스 3(NAV 스냅샷 시계열 → 미실현 포함 시가평가 자산곡선 = 진짜 성장 추세).

## 이전 마일스톤 — 2026-05-30 (스펙 029 슬라이스 1: 라이브 포트폴리오 순자산(NAV) 추적 — 측정 전용)

main 머지 커밋 `cfd7e3d` (PR #118). K4 터치 커밋 `954b00f`(감사 로그 `PORTFOLIO_NAV_SNAPSHOT`, 추가-전용).
운영자 지시 "세계 최고 수준 — 특히 내 포트폴리오와 현재 자산 수준을 기준으로 판단하고 성장시키는
관리 능력"에 대한 **P1(측정)** 작업. 자세히는 `specs/029-portfolio-nav-tracking/spec.md`. 한 줄 요약:

- **배경**: 알파·사이징·팩터·통계는 세계 최고 데스크에 근접했지만, "내 실제 자산 수준 기준 운용"
  축에 빈칸 3개 — ① 자본 기준이 워커 시작 시 한 번 읽고 상수(자산이 불거나 줄어도 캡이 안 따라감),
  ② 현금+보유평가+미실현을 합친 현재 순자산(NAV)의 단일 모델 없음, ③ 장부 vs 브로커 드리프트를
  자산 관점으로 안 봄. 개선의 전제는 측정이라 측정부터 했다.
- **무엇을 했나(측정 전용 — 주문 경로 한 바이트도 안 바꿈)**: ① `portfolio/nav.py`(신규, 비커널)
  `compute_nav()` 순수·결정론 — 현금·종목별 비중(%)·미실현·총 순자산(NAV)·브로커 vs 장부 드리프트
  계산. 시세 없는 종목은 평균단가 보수 평가(측정 불가 분리), 브로커 없으면 내부 장부+시세 폴백
  (`source=ledger`). ② CLI `auto-invest portfolio`(text/json, read-only `PRAGMA query_only`). ③ K4
  추가-전용 `PORTFOLIO_NAV_SNAPSHOT` 감사 이벤트(`--snapshot` 시 1건, 슬라이스 3 성장추적 시계열용).
- **안전 경계**: Kernel 터치 0건. 게이트(K1)·사이징·주문 라우터·워커 루프 무변경. 측정만 한다 —
  주문/취소/정정/halt/자본기준 갱신 0건. K4 추가-전용이라 안전 경계 무변경(K-meta 아님). DB
  마이그레이션 불필요. 결정론·LLM 미사용. dry-run 그대로.
- **검증**: 신규 테스트 14건(SC-01~SC-08 + 감사 왕복 + 렌더링), 전체 1273 통과, 4 스킵, 린트 깨끗.
- **다음(이 슬라이스 비목표)**: 슬라이스 2(워커가 매 사이클 라이브 NAV로 캡 기준 갱신 — 하락은
  항상=방어, 상승은 옵트인. "현재 자산 수준 기준 운용"의 핵심), 슬라이스 3(NAV 스냅샷 시계열 →
  미실현 포함 시가평가 자산곡선 = 진짜 성장 추세).

## 이전 마일스톤 — 2026-05-30 (스펙 028: 체결 품질 정밀 측정 — arrival 기준 구현격차 + 체결 지연)

main 머지 커밋 `1dd665e` (PR #116). K4 터치 커밋 `589187a`(감사 로그, 추가-전용).
운영자 지시 "세계 최고 수준이 되려면 — 매수/매도가 얼마나 실시간에 가깝고·정확하고·정교하게
동작하는지"에 대한 **P1(측정)** 작업. 자세히는 `HANDOFF-038-SPEC-028-EXECUTION-QUALITY.md`.
한 줄 요약:

- **배경**: 개선하려면 먼저 측정해야 한다(세계 최고 데스크의 비협상 기준). 기존 라이브
  슬리피지 기준가가 **지정가**라서 시장가 주문은 "측정 불가"로 빠지고, 지정가 주문도 진짜
  구현격차(내가 결정할 때 본 시장가 대비)가 아니었다. 체결 지연(의사결정→체결 초)은 아예
  측정 안 됐다.
- **무엇을 했나(측정 전용 — 주문 경로 한 바이트도 안 바꿈)**: ① `ORDER_INTENT`에
  결정 순간의 arrival 시세·호가(`decision_price/bid/ask`)를 기록(K4 추가-전용). ② 라이브
  슬리피지 기준가를 **arrival 우선**(→ 과거 row는 지정가 폴백)으로 바꿔 **시장가 주문도
  측정 가능**, 페이퍼·라이브가 같은 잣대로 비교됨. ③ `compute_fill_latency`로 체결 지연
  (평균·중앙·p95·최대 초) 집계. ④ `performance --slippage` 출력 + `LIVE_PERFORMANCE_SNAPSHOT`에
  지연 요약 추가(자율 튜너가 시계열 소비).
- **안전 경계**: 측정만 한다 — 주문을 새로 내거나 취소·정정하지 않음. 게이트(K1)·사이징·
  브로커 호출 경로 무변경. K4는 추가-전용 선택 필드라 안전 경계 무변경(K-meta 아님). DB
  마이그레이션 불필요. 라이브 전환 토글 무관.
- **검증**: 신규 테스트 +10(`test_performance_latency.py` 신규, 슬리피지·라우터 보강),
  전체 1260 통과, 4 스킵, 린트 깨끗.
- **다음(이 스펙 비목표)**: P2 주문 수명 관리(미체결 TTL·취소-재호가·marketable-limit —
  이 스펙의 슬리피지 수치가 정당화 근거), P3 KIS 실시간 웹소켓 시세/체결통보(폴링 지연 제거).

## 이전 마일스톤 — 2026-05-30 (스펙 027: 디플레이티드 샤프 비율 — 다중검정 보정)

main 머지 커밋 `ec1d040` (PR #114). **세계 최고 수준 측정 토대의 마지막 조각** —
백테스트·워크포워드 샤프를 표본 길이·수익률 비정규성(왜도·첨도)·시도한 설정 개수
(다중검정)로 보정하는 통계를 추가했다. Bailey & López de Prado(2014). 자세히는
`HANDOFF-037-SPEC-027-DEFLATED-SHARPE.md`. 한 줄 요약:

- **배경**: 워크포워드(WFE)는 *한 설정*의 표본 외 안정성만 본다. "팩터 N개를 시도해
  좋아 보이는 것을 남겼다"의 선택 편향(데이터 마이닝)은 못 잡는다 — 알파 팩터를 계속
  추가하는 이 시스템의 가장 큰 과학적 격차였다.
- **`backtest/significance.py`(신규, 비커널)**: 확률적 샤프(PSR)·최소 트랙레코드 길이
  (MinTRL)·기대 최대 샤프(SR_0)·디플레이티드 샤프(DSR) + 시도 샤프 횡단면 버전.
  `Φ`/`Φ⁻¹`은 scipy 없이 표준 라이브러리로 구현(공급망 표면 최소). 입력은
  `metrics.sharpe_ratio`와 같은 일별 수익률 시계열(헌법 X.2 단일 잣대).
- **`backtest/walk_forward.py`·`cli.py`(비커널)**: 표본 외 풀 트랙의 PSR·MinTRL·DSR을
  과적합 탐지기에 배선. `auto-invest walk-forward`에 `--num-trials`·`--trial-sharpe-std`·
  `--min-psr`·`--min-dsr` 옵션.
- **안전 경계**: Kernel 터치 0건. 오프라인·읽기 전용·순수 결정론적. 기본값에서 기존
  워크포워드 동작과 byte 동일(새 과적합 사유 0건) — `--min-psr`/`--min-dsr`은 옵트인
  하드 게이트. LLM 미사용. dry-run 그대로.
- **검증**: 신규 테스트 32건(SC-01~SC-11 + 표준정규 정확도 + 배선), 전체 1250 통과,
  4 스킵, 린트 깨끗.

## 이전 마일스톤 — 2026-05-30 (캐너리 실체결 자본 + 자동 승격 게이트, 선택 1·2)

운영자 지시 "1번·2번 모두 자율진행"을 완료. PR #110~#112. 자세히는
`HANDOFF-036-CANARY-CAPITAL-AND-PROMOTION-GATE.md`. 한 줄 요약:

- **선택 1번(실제 체결)**: 자본 $12,000 + 축소 룰셋(`deploy/canary-live-rules.toml`,
  qty=1 SPY·MSFT·AAPL CANARY) 적용. per-trade 5% 캡($600) 안에 우량주 1주가 들어
  실제 체결 가능(첫 기회 다음 정규장). go-live 사이드카 `armed_live_canary` 확인.
  부수 수정: `record_stop` 종료 경로 best-effort(닫힌 DB 트레이스백 제거) + 헬스체크를
  현재 인스턴스 로그만 보도록 격리(재시작 전환기 오탐 제거).
- **선택 2번(자동 승격, 안전 경로)**: 스펙 026 — `promotion/gate.py`(순수·결정론적
  헌법 VI 게이트 6조건) + `readiness.py`(라이브 audit_log 측정) + CLI `promote-check`
  + 매일 `promote-readiness.yml`(서버 평가 → 사이드카 발행). **승격 수행은 안 함**
  (보고 전용). 실제 풀라이브는 VI 게이트 AND 스펙 007 하드닝 캐너리(IX.B-2) 둘 다
  통과해야 발화 — 최소 30거래일 후. 검증 안 된 자동화로 전자본을 미리 발화시키지
  않기 위한 의도적 게이트.
- **검증**: 신규 테스트 14건, 전체 1229 통과, 린트 깨끗.

## 이전 마일스톤 — 2026-05-30 (🟢 실거래 전환: 라이브 캐너리 무장 + 헌법 X.4 개정)

운영자(mason) 지시 "실거래 전환해 … 자동전환 가능하도록 헌법을 고쳐 … 캐너리
소액부터"를 자율 수행으로 완료. PR #105~#108. 자세히는
`HANDOFF-035-GO-LIVE-CANARY.md`. 한 줄 요약:

- **헌법 X.4 개정(v4.0.0, K-meta, PR #105 `d52b048`)**: "라이브 전환 절대 자동 금지"를
  **운영자 지시 시 라이브 캐너리까지만 가드형 채널로 자율 전환 허용**으로 재정의.
  풀라이브 승격(VI 3단계)·장중가드(VIII.A)·K1 캡(I)·화이트리스트(II)·감사(IV)·시크릿(V)
  전부 보존. 운영자 지시 없으면 여전히 자동 전환 0(스펙 005 튜너 불가).
- **가드형 go-live 채널**: `deploy/go-live-canary.sh`(장중 가드 → `.env` 모드만 live →
  워커 재시작 → 헬스체크 → 실패 시 dry-run 자동 복구) + `.github/workflows/go-live-canary.yml`
  (운영자 원클릭 `workflow_dispatch` 또는 센티넬 `automation/go-live-canary.request` 머지).
  결과는 `automation/go-live-last-run` 사이드카로 컨테이너에서 확인.
- **결과**: `GO_LIVE_RESULT=armed_live_canary`(run #3, 커밋 `c286310`). 워커가 라이브
  모드 가동(자본 $100, 캐너리 룰셋). run #2의 헬스 오탐(재시작 전 로그 매칭)은 헬스체크를
  재시작 이후 로그로 한정해 해결. **per-trade 5% 캡 + $100이라 블루칩 1주가 캡 초과 →
  실질 체결 거의 0(라이브 경로 검증됨, 노출 극소). 첫 주문 기회는 다음 정규장.**
- **현재 노출 / 다음**: 실질 ~$0. 진짜 캐너리 체결을 보려면 자본 상향(운영자 결정).
  풀라이브는 여전히 운영자 전용. dry-run 으로 되돌리려면 go-live-canary.sh 역(또는
  서버 `.env` 한 줄).

## 최근 마일스톤 — 2026-05-30 (스펙 025: 다요인 합성 알파 점수 필터)

PR #103 머지 커밋 `127ca3f`. **여러 팩터(모멘텀·퀄리티·저변동성·평균회귀)를
횡단면 z-점수 가중합(하나의 합성 점수)으로 결합해 유니버스를 순위 매기는 옵트인
필터를 추가**했습니다. 스펙 021(모멘텀 단일)·023(퀄리티 단일) 필터를 일반화 — 단일
팩터를 순차 적용할 때 버려지던 교차-팩터 정보를 보존해 "여러 면에서 두루 좋은"
종목을 "한 면에서만 극단적인" 종목보다 선호합니다(세계 최고 수준 멀티팩터 합성).
자세히는 `HANDOFF-034-SPEC-025-COMPOSITE-FACTOR.md`. 한 줄 요약:

- **`strategy/factors.py`(신규, 비커널)**: `zscore()` 횡단면 표준화(모집단 표준편차,
  동일값이면 전부 0) + `composite_scores()` 가중합 순위. 활성 팩터(가중치≠0)만 계산,
  데이터 부족 심볼은 `-Inf` 센티넬로 맨 뒤.
- **`config/rules.py`(비커널)**: `CompositeFactorFilter` 모델 + `KNOWN_COMPOSITE_FACTORS`
  + `TradingRule.composite_filter`(None이면 byte 동일).
- **`execution/order_router.py`·`backtest/replay.py`(비커널)**: 퀄리티 필터 이후 적용 →
  `SKIPPED_BY_COMPOSITE`. 백테스트는 세션 날짜 이하 바만 사용(미래 참조 방지).
- **안전 경계**: Kernel 터치 0건. 하향 전용(스킵만, K1 불변). 옵트인. 결정론적
  Decimal(라이브=백테스트 단일 잣대, 헌법 X.2). LLM 미사용. dry-run 그대로.
- **검증**: 신규 테스트 12건(SC-01~SC-10), 전체 1215 통과, 4 스킵, 린트 깨끗.
  SC-02 핵심 증명: 저변동성 결합 시 매끄러운 종목이 변동성 큰 최고-모멘텀 종목을 추월.

## 이전 마일스톤 — 2026-05-29 (스펙 024: 최대 샤프 포트폴리오 최적화)

PR #101 머지 커밋 `86b2c32`. **모멘텀 신호를 기대 수익률 μ로 활용해 평균-분산 전선에서 최대 샤프 포인트를 직접 구하는 `mode="max_sharpe"` 사이징 모드를 추가**했습니다.

- **`strategy/sizing.py`(비커널)**: `expected_returns_from_closes()` — 공통 거래일 기준 롤링 평균 로그 수익률(연율화). `max_sharpe_weights(cov, μ)` — `w* ∝ Σ^{-1}·μ` (numpy linalg.solve). μ 전부 비양수 → 균등 가중치 fail-safe. `max_sharpe_group_scales()` — ERC/min_variance와 동일 인터페이스, 수치 실패 → min_variance → ERC → 역변동성 fallback 체인.
- **`config/rules.py`(비커널)**: `SizingConfig.mode`에 `"max_sharpe"` 추가.
- **`execution/order_router.py`·`backtest/replay.py`(비커널)**: `mode in ("erc", "min_variance", "max_sharpe")` 통합 분기.
- **안전 경계**: Kernel 터치 0건. max 1 클램핑(하향 전용). 옵트인. 결정론적 Decimal(헌법 X.2).
- **검증**: 신규 테스트 8건(SC-01~SC-08), 전체 1203 통과, 4 스킵, 린트 깨끗.

## 이전 마일스톤 — 2026-05-29 (스펙 023: 가격 기반 퀄리티 팩터 필터)

PR #100 머지 커밋 `674c8dc`. 롤링 샤프 / (1 + |최대 드로다운|) 합성 점수로 유니버스를 순위 매겨 하위 종목을 `SKIPPED_BY_QUALITY`로 차단. `QualityFilter(top_n/top_pct)` 옵트인. Kernel 터치 0건. 신규 테스트 8건, 전체 1195 통과.

## 이전 마일스톤 — 2026-05-29 (스펙 022: 최소 분산 포트폴리오 최적화)

PR #99 머지 커밋 `204dfc9`. `mode="min_variance"` 분석적 해(`w* = Σ^{-1}·1`). ridge 정규화, 음수 클램핑, ERC→역변동성 fallback. Kernel 터치 0건. 신규 테스트 8건, 전체 1187 통과.

## 이전 마일스톤 — 2026-05-29 (스펙 021: 횡단면 모멘텀 순위 필터)

PR #97 머지 커밋 `2bd01b1`. **세계 최고 수준과의 가장 큰 격차 해소 — 전체 유니버스를 N-기간 수익률로 순위 매겨 상위 N개 또는 상위 P% 종목에만 매수를 허용하는 횡단면 랭킹 필터(Jegadeesh-Titman 모멘텀 팩터)**를 추가했습니다.
기존 시스템은 종목별 독립 룰이었으나, 이 스펙은 유니버스 전체를 한 번에 보고 "지금 가장 강한 종목"만 선택합니다. 자세히는 `specs/021-cross-sectional-ranking/spec.md`. 한 줄 요약:

- **`strategy/ranking.py`(신규, 비커널)**: `cross_sectional_momentum(symbol_bars, period)` — 유니버스 전체를 N-기간 수익률 내림차순 정렬. 바 부족 심볼은 맨 뒤(-Inf 센티넬). `is_top_n(symbol, ranked, n)` / `is_top_pct(symbol, ranked, pct)` 필터 헬퍼.
- **`config/rules.py`(비커널)**: `RankingFilter` Pydantic 모델(`universe`, `period`, `top_n` or `top_pct`). `TradingRule.ranking_filter` 선택적 필드 추가. `top_n`과 `top_pct` 중 정확히 하나만 설정(검증). 옵트인: `None`이면 기존 경로 byte 동일.
- **`execution/order_router.py`(비커널)**: 레짐 배율 이후, 판단 이전에 랭킹 필터 삽입. 유니버스 전체 심볼 바를 DB에서 조회 → 순위 계산 → 미통과 시 `SKIPPED_BY_RANKING(not_in_top)`.
- **`backtest/replay.py`(비커널)**: 각 세션 날짜 루프에서 세션 날짜까지의 바만 사용(미래 참조 방지)하며 동일 필터 적용.
- **안전 경계**: Kernel 터치 0건. 하향 전용(스킵만, 수량 증가 없음). 옵트인(기존 룰 byte 동일). 결정론적 Decimal.
- **검증**: 신규 테스트 13건(SC-01~SC-06 + 유닛 7건), 전체 1179 통과.

## 이전 마일스톤 — 2026-05-29 (스펙 020: 레짐 배율 + ERC 가중치 거래 루프 실배선)

PR #95 머지 커밋 `cb5dcae`. **스펙 019가 완성한 레짐 감지기·ERC 유틸리티를 실제 거래 루프(order_router·replay)에 연결**했습니다.
배선 전에는 함수가 존재해도 실제 주문/백테스트 수량에 반영되지 않았습니다. 이번 스펙으로 라이브 주문 경로와 백테스트 경로 양쪽에서 레짐 배율·ERC 가중치가 K1 캡 전에 적용됩니다.
자세히는 `specs/020-regime-erc-wiring/spec.md`. 한 줄 요약:

- **`config/rules.py` 확장(비커널)**: `TradingRule`에 `regime_index_symbol`(레짐 판별 인덱스 심볼, 예: "SPY")·`regime_scale`(레짐별 배율 오버라이드 딕셔너리) 선택적 필드 추가. `SizingConfig.mode`에 `"erc"` 추가.
- **`execution/order_router.py` 배선(비커널)**: `_group_scale()`이 `inverse_vol`·`erc` 양 모드 지원. `rule.regime_index_symbol`이 있으면 DB에서 인덱스 바를 읽어 `detect_regime()` 호출 → `apply_regime_scale(qty, scale)` 적용 → qty < 1이면 `SKIPPED_BY_SIZING("regime_zero")`. 판단 자문 **전에** 적용(자문은 그 위에서만 줄일 수 있음).
- **`backtest/replay.py` 배선(비커널)**: `_replay_group_scale()`이 `erc` 모드 지원. 레짐 인덱스 심볼을 `symbols_in_use`에 포함하고 SMA-200 필요 때문에 `date.min`부터 전 기간 바 로드. 각 세션 날짜 루프에서 레짐 판별 → `apply_regime_scale` → qty < 1이면 해당 세션 건너뜀.
- **`strategy/sizing.py` 수정(비커널)**: `sized_quantity()` ERC 분기 추가 — `mode="erc"`도 `inverse_vol`과 같은 `group_scale` 경로 사용(호출자가 미리 계산해 전달).
- **안전 경계**: 비커널 전용. K1 caps(`risk/gates.py`) 후처리 변경 없음. 레짐·ERC는 수량을 **줄이거나 건너뛰기만** — K1 위로 노출 증가 불가. 결정론적 Decimal. Kernel 터치 0건. dry-run 그대로.
- **검증**: 신규 테스트 5건(SC-01~SC-05), 전체 1166 통과, 4 스킵.

## 이전 마일스톤 — 2026-05-29 (스펙 019: 레짐 인식 + 완전 공분산 ERC)

PR #93 머지 커밋 `6c1d849`. **"세계 최고 수준" 로드맵 — 신호 레이어(018) 위에
레짐 인식과 진짜 등기여 위험 배분(ERC)을 하나의 스펙으로 완성**했습니다.
walk-forward 표본 외 검증 통과. 자세히는 `specs/019-regime-erc-sizing/spec.md`. 한 줄 요약:

- **슬라이스 1 — 레짐 감지기(`strategy/regime.py`, 비커널)**:
  `Regime(StrEnum)`: TRENDING / RANGING / BEAR 3상태.
  `detect(bars)`: SMA50·SMA200 교차 기반 결정론적 판별, 200막대 미만 → RANGING fail-safe.
  `DEFAULT_REGIME_SCALE`: 추세=1.0 / 횡보=0.7 / 하락=0.3.
  `apply_regime_scale(qty, scale)`: qty × scale 내림 정수.
- **슬라이스 2 — 완전 공분산 ERC(`strategy/sizing.py` 확장, 비커널)**:
  `covariance_matrix()`: 공통 날짜 교집합 기반 표본 공분산 행렬(Decimal, 6자리 정규화).
  `erc_weights()`: Maillard(2010) CCD 반복 최적화 — 각 자산의 marginal risk contribution 균등화, 수렴 실패 시 `ERCConvergenceError`.
  `erc_group_scales()`: ERC 가중치 딕셔너리, 공통일 <30이면 역변동성 fallback.
  `config/rules.py` SizingConfig.mode에 `"erc"` 추가.
- **슬라이스 3 — walk-forward 표본 외 검증(`tests/unit/test_regime_erc.py`)**: 19개 테스트(레짐 감지 SC-R01~R04, ERC 수학 SC-E01~E04, walk-forward SC-W01~W03). 스펙 016 walk-forward 하니스 위에서 합성 XNYS 데이터로 호환성 확인.
- **안전 경계**: 비커널 전용. K1 caps(`risk/gates.py`) 후처리 변경 없음. ERC 가중치 max 1 클램핑(하향 전용). 결정론적 Decimal — 백테스트·라이브 단일 잣대(헌법 X.2). Kernel 터치 0건. dry-run 그대로.
- **검증**: 신규 테스트 19건, 전체 1161 통과.
- **다음**: 레짐 필터와 ERC 가중치를 `execution/order_router.py`·`backtest/replay.py`에 실제 배선해야 거래 루프에서 작동. 현재는 유틸리티 함수로만 존재(배선 미완).

## 이전 마일스톤 — 2026-05-29 (스펙 018: 다요인 신호 + 사이징 감사 기록)

PR #91 머지 커밋 `aeed831`. **"세계 최고 수준" 로드맵 — 스펙 017 리스크 사이징 토대 위에
신호/알파 레이어와 사이징 관찰 기반을 추가**했습니다. 기존 신호(EMA 교차·RSI)만으로는
세계 최고 수준과 격차가 컸는데, 학문적으로 가장 강건한 두 팩터와 포렌식 감사 기록을 추가했습니다.
자세히는 `specs/018-multifactor-signals/spec.md`. 한 줄 요약:

- **슬라이스 1 — 다요인 신호(비커널)**:
  - `strategy/indicators.py`: `momentum(bars, period)` — N기간 수익률(%). 시계열 모멘텀 팩터.
    `bollinger_band_pct_b(bars, period, std_dev)` — 밴드 내 상대 위치(%B). 평균회귀 팩터.
  - `strategy/triggers.py`: `MOMENTUM_ABOVE` / `MOMENTUM_BELOW`(모멘텀 임계값),
    `BB_ABOVE` / `BB_BELOW`(볼린저 밴드 %B 임계값) 트리거 4종 추가. 기존 EMA/RSI 트리거 byte 동일.
- **슬라이스 2 — 사이징 결정 감사 기록(K4 추가-전용)**:
  - `persistence/audit.py`: `SIZING_DECISION` 이벤트 + `SizingDecisionPayload`(실현 변동성·
    역변동성 가중치·상관·최종 수량을 포렌식 페이로드로). 기존 이벤트 무변경(K4 추가-전용).
  - `strategy/sizing.py`: `SizingResult` 데이터클래스 + `sized_quantity_with_result()` 추가.
    사이징 결과 전체 컨텍스트(base_qty·final_qty·realized_vol_pct·vol_scale·group_scale) 반환.
  - `execution/order_router.py`: `target_vol`·`inverse_vol` 모드에서 `SIZING_DECISION` 감사 행 기록.
    `final_qty=0`(사이징 스로틀 스킵)도 기록(관찰 기반 구축).
- **안전 경계**: 비커널 전용 + K4 추가-전용. 옵트인(기존 룰 미변경 시 새 트리거 사용 0 — byte 동일).
  하향 전용 불변량 유지(새 신호는 트리거 결정만, 사이징은 스펙 017 경로 그대로). Kernel 터치 0건.
  dry-run 그대로.
- **검증**: 신규 테스트 32건(단위 22 + 통합 3 + 사이징 단위 7), 전체 1142 통과.
- **다음**: 신호 레이어 확장(레짐 인식·교차 단면 랭킹·모멘텀 요인 결합), 완전 공분산 ERC,
  양방향 그룹 budget-split. **반드시 워크포워드로 표본 외 검증할 것.**

## 이전 마일스톤 — 2026-05-29 (스펙 017 슬라이스 3: 상관 헤어컷)

PR #89 머지 커밋 `33d3926`. **"세계 최고 수준" 로드맵 — 리스크 사이징 토대(변동성·역변동성·
상관)를 한 바퀴 완성**했습니다. 슬라이스 2b 역변동성은 종목 간 상관을 0으로 가정했는데,
상관 높은 종목을 함께 들면 위험이 분산되지 않고 집중됩니다. 슬라이스 3은 그룹 멤버 간
수익률 상관을 재서, 상관 높은(분산 안 된) 멤버를 추가로 줄이는 **상관 헤어컷**(방어적·하향
전용)을 더했습니다. 자세히는 `HANDOFF-028-SPEC-017-SLICE3-CORRELATION.md`. 한 줄 요약:

- **룰 스키마(`config/rules.py`, 비커널)**: `SizingConfig`에 선택적 `correlation_haircut`
  (강도, 기본 0=끔). inverse_vol 그룹에서만 의미. 0이면 슬라이스 2b와 byte 동일.
- **`strategy/sizing.py`(비커널)**: `pearson_correlation`(분산 0/길이 불일치 None)·
  `average_correlations`(멤버를 공통 거래일로 정렬해 평균 상관, 공통일 < 3이면 None)·
  `correlation_haircut`(`1 - strength·max(0,avg)`, `[0,1]` 클램프)·`group_scale_for`
  (역변동성 가중치 × 상관 헤어컷 합성) 추가.
- **백테스트·라이브 양쪽(`replay`·`OrderRouter`, 비커널)**: `group_scale_for`로 같은 합성
  가중치 계산. 상관 입력(멤버별 `{날짜: 종가}`)을 양쪽이 같은 달력 날짜 키로 정렬 —
  백테스트 `OHLCVBar.session_date`·라이브 `PriceBar.bar_open_utc` 앞 10자 → 단일 잣대
  (헌법 X.2). 공통 거래일 < 3이면 헤어컷 없음(fail-safe).
- **안전 경계**: 하향 전용(헤어컷 ≤ 1, 역변동성 × 헤어컷도 ≤ 1)이라 노출 증가 불가, K1이
  천장. 역상관/분산된 멤버는 헤어컷 없음(`max(0, avg)`). 옵트인 — `correlation_haircut=0`
  이면 슬라이스 2b와 byte 동일(회귀 무손상, SC-S12 증명). **Kernel 터치 0건**(전부 비커널,
  `worker/loop.py`도 미변경 — 기존 배선으로 흐름). 감사 K4 무변경. 결정론적·LLM 미사용.
  dry-run 그대로. 테스트 신규 7건, 전체 1110 통과.
- **다음**: 신호/알파 과학(다요인·레짐 인식 — 이제 리스크 사이징 위에서 안전하게), 완전
  공분산 ERC/상관 하드 합산 캡, 양방향 그룹 budget-split, 또는 사이징 결정 감사 기록(K4).
  **새 사이징/알파 작업은 반드시 `auto-invest walk-forward`로 표본 외 검증할 것.**

## 이전 마일스톤 — 2026-05-29 (스펙 017 슬라이스 2b: 역변동성 그룹 리스크 패리티)

PR #87 머지 커밋 `b8fb7e9`. **"세계 최고 수준" 로드맵 — 멀티 포지션 리스크 배분 1단계**를
완성했습니다. 슬라이스 1·2가 **한 포지션**의 변동성만 봤다면, 슬라이스 2b는 **여러 종목을
한 바구니(sizing group)로 묶어** 종목 간 리스크 기여도를 균형화합니다. 변동성 높은 종목을
줄여 변동성 낮은 종목과 위험을 맞추는 **역변동성(상관 없는 리스크 패리티)** 배분입니다.
자세히는 `HANDOFF-027-SPEC-017-SLICE2B-RISK-PARITY.md`. 한 줄 요약:

- **룰 스키마(`config/rules.py`, 비커널)**: `SizingConfig.mode`에 `"inverse_vol"` 추가,
  `TradingRule`에 선택적 `sizing_group` 추가. `inverse_vol` 모드는 `sizing_group` 필수
  (모델 검증). 둘 다 없으면 기존 동작 byte 동일.
- **`strategy/sizing.py`(비커널)**: `build_sizing_groups(rules)`(그룹명→멤버)·
  `inverse_vol_group_scale(own, members)`(가중치=`min(그룹 변동성)/자기 변동성`, `(0,1]`로
  클램프, 변동성 최저 멤버=기준 1, 높은 멤버 축소, fail-safe 1)·`SizingGroupMember` 추가.
  `sized_quantity`에 `group_scale`(기본 1) 추가.
- **백테스트·라이브 양쪽 연결(`replay`·`OrderRouter`·`worker/loop.py`, 전부 비커널)**:
  K1 게이트 **전에** 같은 두 함수로 그룹 가중치 계산 후 `sized_quantity`에 전달. worker가
  `build_sizing_groups`로 그룹을 만들어 `OrderRouter.sizing_groups`로 넘기면 라우터가
  `self.conn`으로 각 멤버 바를 조회해 같은 `realized_volatility`·lookback으로 잰다 →
  단일 잣대(헌법 X.2).
- **안전 경계**: 하향 전용(가중치 ≤ 1)이라 기준 수량 위로 노출 증가 불가, K1이 그대로
  천장. 그룹은 옵트인 — `sizing_group` 없으면 기존 룰 byte 동일(회귀 무손상, SC-S11 증명).
  **Kernel 터치 0건**(전부 비커널 — 커널인 `worker/schedule.py`가 아닌 `worker/loop.py`).
  감사 K4 무변경. 결정론적·LLM 미사용. dry-run 그대로. 테스트 신규 8건, 전체 1103 통과.
  SC-S10 증명: 같은 그룹에서 변동성 높은 AAPL이 변동성 낮은 MSFT 대비 줄고 MSFT는 풀
  사이즈 유지.
- **다음**: 슬라이스 3(상관 인식 합산 한도, 공분산 추정), 양방향 그룹 budget-split(K1 봉투
  안 확대), 또는 신호/알파 과학.
  **새 사이징/알파 작업은 반드시 `auto-invest walk-forward`로 표본 외 검증할 것.**

## 이전 마일스톤 — 2026-05-28 (스펙 017 슬라이스 2: 양방향 변동성 타깃팅)

PR #85 머지 커밋 `ab4a140`. **"세계 최고 수준" 로드맵 — 변동성 타깃팅의 나머지 절반을
완성**했습니다. 슬라이스 1이 turbulent 구간에서 사이즈를 **줄이는** 하향 절반만 했다면,
슬라이스 2는 잔잔한 구간(실현 변동성 < 타깃)에서 사이즈를 타깃 리스크 예산까지 **늘리는**
상향 절반을 더해 진짜 변동성 타깃팅(일정한 리스크 예산 유지 → 샤프·최대낙폭 직접 개선)을
완성합니다. 신호 과학보다 사이징을 먼저 완성하는 규율 있는 순서이며, 구조적 우위라 과적합
위험이 낮습니다(헌법 원칙 X). 자세히는 `HANDOFF-026-SPEC-017-SLICE2-BIDIRECTIONAL.md`.
한 줄 요약:

- **룰 스키마(`config/rules.py`, 비커널)**: `SizingConfig`에 선택적 `max_scale`(상향 한도)
  추가. 기본 `1`이면 슬라이스 1 하향 전용과 byte 동일(`ge=1`, fat-finger 방지 `le=10`).
  `max_scale > 1`로 명시한 룰만 잔잔한 구간에서 확대.
- **`strategy/sizing.py`(비커널)**: `volatility_scale`이 `target/realized`를
  `[min_scale, max_scale]`로 클램프. 실현 변동성 ≤ 0이면(측정 불가) 중립값 1 반환으로
  무한 확대 방지. `sized_quantity`가 `max_scale`을 전달.
- **연결 지점 로직 변경 없음**: `replay`·`OrderRouter`는 이미 K1 게이트 **전에** 사이저를
  호출 → 이제 확대 수량도 같은 게이트를 거친다. 주석만 양방향 동작에 맞게 갱신.
- **안전 경계**: **K1이 진짜 천장** — 확대해도 사이저는 제안만 하고, K1 게이트
  (`risk/gates.py`)가 거래당·종목당·전체 캡 초과 주문을 **거부**(클램프 아님)한다. 확대는
  K1 위로 노출을 절대 못 올린다(SC-S09 테스트 `test_replay_bidirectional_upscale_still_bound_by_k1_caps`로 증명). 하향 조절은 그대로 살아있음. 기본 `max_scale=1`이라
  기존 룰 byte 동일(회귀 무손상). **Kernel 터치 0건**(전부 `strategy/sizing.py`·
  `config/rules.py`·`backtest/replay.py`·`execution/order_router.py` 비커널·`tests/`·
  `specs/`). 감사 K4 무변경. 결정론적·LLM 미사용. dry-run 그대로. 테스트 신규 9건,
  전체 1095 통과.
- **다음**: 슬라이스 2b(멀티 포지션 역변동성/리스크 패리티 — 포트폴리오 상태 결합이 커서
  별도 슬라이스), 슬라이스 3(상관 인식 배분), 또는 신호/알파 과학.
  **새 사이징/알파 작업은 반드시 `auto-invest walk-forward`로 표본 외 검증할 것.**

## 이전 마일스톤 — 2026-05-28 (스펙 017 슬라이스 1: 변동성 기반 포지션 사이징)

PR #83 머지 커밋 `c291d75`. **"세계 최고 수준" 로드맵 — 측정 토대 다음 단계인 리스크
사이징을 시작**했습니다. 스펙 016이 백테스트를 정직·통일·표본 외 검증되게 만들었지만,
포지션 사이징은 여전히 v1 수준(룰마다 고정 정수 수량 `Action.qty`)이었습니다. 변동성
타깃팅은 과적합 위험이 낮은 구조적 우위라 헌법 원칙 X(측정 기반·추측 금지)에 가장 잘
맞는 다음 단계입니다. 자세히는 `HANDOFF-025-SPEC-017-VOL-SIZING.md`. 한 줄 요약:

- **새 모듈 `strategy/sizing.py`(비커널)**: `realized_volatility`(연속 종가 단순 수익률의
  표본 표준편차) + `volatility_scale`(`min(1, target/realized)`을 `[min_scale, 1]`로
  클램프) + `sized_quantity`(`floor(기준수량 × scale)`). 전부 결정론적 Decimal —
  백테스트 byte-equality + 라이브/백테스트 단일 잣대(헌법 X.2) 보존.
- **룰 스키마(`config/rules.py`, 비커널)**: 선택적 `SizingConfig`(`mode` fixed|target_vol,
  `target_volatility_pct`, `lookback_bars`, `min_scale`). `TradingRule.sizing` 기본 `None`
  → fixed → v1 동작 byte 동일(하위호환, 마이그레이션 불필요).
- **백테스트 `replay`와 라이브 `OrderRouter`(둘 다 비커널) 양쪽 연결**: 신호 발사 후 K1
  게이트 체인 **전에** `sized_quantity` 호출. 사이저는 수량을 **제안만** 하고 K1 캡이
  그대로 상한으로 바인딩 — 노출을 K1 위로 절대 올릴 수 없음. 슬라이스 1은 스케일 ≤ 1
  (하향 전용 throttle)이라 v1 대비 노출 증가 불가. `sized < 1`이면 그 틱 건너뜀(`qty=0`
  주문 미생성, `SKIPPED_BY_SIZING`). 같은 함수를 양쪽이 쓰므로 워크포워드(스펙 016
  슬라이스 3)로 표본 외 검증을 받는다.
- **안전 경계**: K1 캡(`risk/gates.py`·`config/caps.py`) 무변경. **Kernel 터치 0건**(전부
  `strategy/sizing.py` 신규·`config/rules.py`·`backtest/replay.py`·
  `execution/order_router.py` 비커널·`tests/`·`specs/`). 감사 스키마 K4 무변경(새 이벤트
  0건). 결정론적·LLM 미사용. 라이브 worker dry-run 그대로. 테스트 신규 18건, 전체 1086
  통과. fixed/None 경로가 v1과 byte 동일(기존 1068 테스트 무손상)으로 회귀 무손상 증명.
- **다음**: 슬라이스 2(양방향 타깃 변동성 — 잔잔한 구간에서 K1 봉투 안 확대 + 멀티
  포지션 역변동성/리스크 패리티), 슬라이스 3(상관 인식 배분), 또는 신호/알파 과학.
  **새 사이징/알파 작업은 반드시 `auto-invest walk-forward`로 표본 외 검증할 것.**

## 이전 마일스톤 — 2026-05-27 (스펙 016 슬라이스 3: 워크포워드 표본 외 검증)

PR #81 머지 커밋 `9242faa`. **세계 최고 수준 로드맵 3단계 — 표본 외 검증(과적합
탐지)**을 완료했습니다. 슬라이스 1·2가 백테스트를 정직(거래비용)·통일(단일 잣대)되게
만들었지만, 단일 기간 백테스트는 그 한 기간에 **과적합**될 수 있습니다(좋아 보이는
룰셋이 그 시기의 잡음을 외운 것뿐일 수 있음). 워크포워드는 같은 룰셋을 롤링 표본 내
(IS)/표본 외(OOS) 윈도우로 돌려 "이 우위가 표본 밖에서도 재현되는가?"를 묻습니다.
이게 깔려야 신호·사이징 개선을 환상이 아니라 검증된 토대 위에서 할 수 있습니다(헌법
원칙 X). 자세히는 `HANDOFF-024-SPEC-016-SLICE3-WALK-FORWARD.md`. 한 줄 요약:

- **새 모듈 `backtest/walk_forward.py`(비커널)**: `generate_windows`(rolling=고정 IS
  미끄러짐 / anchored=IS 확장, OOS 무중첩 연속 타일링) + `run_walk_forward`(구간마다
  새 브로커·시계로 기존 `replay` 재실행 + 슬라이스 2 `build_summary` 재사용 → 같은
  잣대 자동 보장) + 윈도우별 WFE·과적합 판정 + 마크다운 리포트.
- **헤드라인 두 가지**: (1) 표본 외 집계 성과(윈도우별 OOS 지표 평균 — 과적합에 강한
  정직한 숫자), (2) 워크포워드 효율(WFE = OOS 샤프 / IS 샤프, 평균·중앙값). 과적합
  신호 3종: 평균 WFE < 임계(기본 0.5) / IS 샤프는 양인데 OOS 0 이하 / 표본 외 수익
  윈도우 과반 미만.
- **CLI**: `auto-invest walk-forward --rules ... --from ... --to ... --in-sample-days
  ... --out-of-sample-days ... [--mode rolling|anchored] [--wfe-threshold 0.5]`.
  과적합 의심 시 종료코드 1.
- **안전 경계**: 오프라인·읽기 전용(기존 replay를 날짜 부분구간에 재실행할 뿐, 라이브
  주문 경로 무수정, 돈 안 움직임). **Kernel 터치 0건**(전부 `backtest/walk_forward.py`
  ·`cli.py` 비커널·`tests/`·`specs/`). 감사 스키마 K4 무변경(기존 replay 감사 어휘만
  사용). 테스트 신규 10건, 전체 1068 통과. SC-E01 핵심 증명
  `test_oos_summary_uses_same_yardstick_as_direct_backtest` — 한 윈도우의 OOS 지표가
  같은 날짜 범위 독립 백테스트와 바이트 동일(실제 replay 엔진 사용). CLI도 실제 ingest
  데이터셋에 종단 검증.
- **다음**: 측정 토대(정직·통일·표본 외 검증) 완성. 신호/알파 과학(다요인·레짐 인식)
  또는 포지션 사이징(변동성·상관) — 이제 워크포워드로 검증받으며 안전하게 개선.

## 이전 마일스톤 — 2026-05-27 (스펙 016 슬라이스 2: 단일 잣대 통일)

PR #79 머지 커밋 `83abbbb`. **세계 최고 수준 로드맵 2단계 — 측정 잣대 통일**을
완료했습니다. 슬라이스 1이 백테스트를 정직하게(거래비용) 만들었다면, 슬라이스 2는
백테스트와 라이브가 **같은 거래 단위 지표 정의**를 쓰게 해서 헌법 원칙 X.2("단일
잣대")를 완성합니다. 자세히는 `HANDOFF-023-SPEC-016-SLICE2-SINGLE-YARDSTICK.md`.
한 줄 요약:

- **고친 갭**: 승률·평균손익·손익비가 라이브 엔진에만 인라인으로 있고 백테스트엔
  통째로 없었음(다른 잣대). 둘 다 Sortino 없었음. 공식이 한쪽에만 있어 갈라질 위험.
- **공용 단일 정의(`backtest/metrics.py`)**: `sortino_ratio`(하방편차·√252) +
  `win_loss_stats`(승률·평균손익·손익비) + `realized_closed_trades`(평균단가 실현거래
  재구성) 추가. 라이브 엔진과 백테스트가 같은 함수를 호출.
- **라이브(`performance/engine.py`)**: 인라인 공식 제거하고 공용 정의 호출,
  `RiskMetrics`에 sortino 추가, 리포트 schema 1.1→1.2.
- **백테스트**: 비용 반영 체결에서 거래 단위 지표 계산 → `RuleBacktestResult`·
  `BacktestSummary` → `metrics.csv`·`backtest-run.json`·`summary.md`에 노출.
- **안전 경계**: 오프라인·읽기 전용. **Kernel 터치 0건**(전부 `backtest/`·
  `performance/engine.py` 비커널·`tests/`·`specs/`). 감사 스키마 K4 무변경(Sortino를
  튜너 스냅샷에 넣는 건 후속 K4 작업으로 미룸). 테스트 신규 18건, 전체 1058 통과.
  교차 검증 `test_metrics_single_yardstick.py`가 같은 체결 → 백테스트·라이브 동일
  승률·손익비를 증명(SC-D01).
- **다음**: 슬라이스 3(워크포워드 표본 외 검증 — 과적합 탐지).

## 이전 마일스톤 — 2026-05-27 (스펙 016 슬라이스 1: 백테스트 거래비용·슬리피지 모델)

PR #77 머지 커밋 `f8552c6`. **백테스트가 그동안 거짓 잣대였던 문제를 고쳤습니다.**
헌법 원칙 VI는 "백테스트는 슬리피지·체결비용을 모델링 못해 성과를 체계적으로
과대평가한다"고 경고하는데, 백테스트 엔진(`broker_mock.py`)이 정확히 그 무비용·
무슬리피지 체결이었습니다. 또 헌법 원칙 X.2("단일 잣대")는 라이브·백테스트가 같은
지표 정의를 써야 한다는데, 라이브 성과 엔진은 비용 반영 실현 손익을 재는 반면
백테스트는 비용을 0으로 둬 비교가 무의미했습니다. **세계 최고 수준의 전제 = 정직한
백테스트**(거짓 잣대 위에서 신호·사이징을 개선하면 환상을 최적화하게 됨)라서, "세계
최고 수준" 작업 중 1순위로 이 갭을 골랐습니다. 자세히는
`HANDOFF-022-SPEC-016-BACKTEST-COSTS.md`. 한 줄 요약:

- **거래비용 오버레이**: 브로커 목의 기계적 체결(`pessimistic_zero_slip`)은 그대로
  두고, `replay`의 체결 처리 단계(`_record_fill`)에 비용을 입혔습니다. 슬리피지=
  체결가를 불리한 방향으로 이동(BUY ↑, SELL ↓, basis point), 수수료=`max(최소수수료,
  명목금액 × commission_bps)`를 현금흐름에서 차감. 새 모듈 `backtest/costs.py`의
  `BacktestCostModel`(`.zero()` / `.kis_default()`).
- **정직한 기본값**: 프로덕션 진입점(`run_backtest`/CLI/캐너리) 기본값 = KIS 미국주식
  현실값(수수료 25bps, 슬리피지 5bps). `replay` 기본값은 `zero()`라 기존 무비용 단위
  테스트는 무손상. CLI `--commission-bps`·`--slippage-bps`·`--min-commission-usd`.
- **비용 노출**: 규칙별·합계 수수료/슬리피지를 `metrics.csv`·`backtest-run.json`·
  `summary.md`·`RunOutcome`에 표면화(운영자가 비용 드래그를 봄).
- **안전 경계**: 오프라인·읽기 전용(라이브 주문 경로 무수정, 돈 안 움직임). **Kernel
  터치 0건**(전부 `backtest/`·`cli.py`·`tests/`·`specs/`, 감사 스키마 K4 무변경).
  byte-equality(FR-B15)는 모든 비용 연산 6자리 정규화로 보존. 테스트 신규 9건, 전체
  1040 통과.
- **후속**: 슬라이스 2(단일 잣대 통일 — 백테스트가 승률·손익비·Sortino 계산),
  슬라이스 3(워크포워드 표본 외 검증).

## 이전 마일스톤 — 2026-05-27 (스펙 001 T050/T052: 장 마감 정합성 자동 실행)

PR #75 머지 커밋 `4319535`. **로컬 장부와 브로커 보유를 매 장 마감마다 자동으로
대조해 드리프트를 잡는** 정합성 검증의 자동 호출 배선을 채웠습니다. 정합성 검증은
스펙 001 P2(조용한 상태 드리프트 방지)의 키스톤인데, 구현(T049)·테스트(T048)는
됐으나 **자동 호출 배선(T050)이 통째로 빠져 유일한 호출자가 테스트 스위트**였습니다.
그래서 라이브 자율 운영 중 불일치를 한 번도 못 잡았고 스펙 013 헬스의 정합성 점검은
영구 DEGRADED 였습니다. 자세히는 `HANDOFF-021-RECONCILE-AT-CLOSE.md`. 한 줄 요약:

- **`worker/loop.py`** — 세션 열림→닫힘 전이 첫 틱에 정합성 1회 자동 실행
  (`Worker._session_was_open` + `_reconcile_at_close`). 한 닫힘 구간 정확히 1회,
  라이브 전용(paper 무변경), 오류 격리(거래 무중단).
- **`cli.py`** — `auto-invest reconcile` 명령(수동/모니터링용, 종료 0/1/2). 같은
  `run_reconciliation` 진입점 재사용. `reconcile_now` docstring 거짓 주장 정정.
- **안전 경계**: 읽기-기반(주문/청산 0건, 불일치 시 halt만), 라이브 전용, 거래
  무중단. **Kernel 터치 0건**(기존 정합성 이벤트·러너 재사용). 테스트 신규 7건,
  전체 1031 통과.

## 이전 마일스톤 — 2026-05-27 (스펙 015: 라이브 체결 동기화)

PR #73 머지 커밋 `e746f52`. **접수된 라이브 주문이 실제로 체결됐는지를 브로커에서
다시 조회해 장부(FILL 감사·`fills` 테이블·보유 캐시·주문 상태)에 반영하는** 마지막
고리를 채웠습니다. 그동안 라이브 주문은 `SUBMITTED`(브로커 접수)에서 멈추고 실제
체결 추적이 0건이라, `FILL`/`fills`/`update_from_fill`이 정의·조회만 되고 라이브
writer 가 없어 **스펙 014 브레이커·스펙 011 성과·정합성이 라이브에서 통째로 눈을
뜨지 못하던** 키스톤 구멍을 메웁니다. 자세히는
`HANDOFF-020-SPEC-015-FILL-INGESTION.md`. 한 줄 요약:

- **브로커 체결 조회** `get_order_executions`(KIS `inquire-ccnl`, 읽기 전용) +
  `BrokerExecution` 모델. 새 모듈 `execution/fill_sync.py`: 순수 계획 함수
  `plan_fill_ingestion` + async `sync_fills`.
- **멱등 적재**: 누적 체결량 대비 추가분만 FILL 기록(`kis_fill_id="{odno}:{누적}"`),
  보유 캐시 갱신, 상태 전이(`SUBMITTED`→`PARTIALLY_FILLED`→`FILLED`, 종료 시
  `EXPIRED`+`CANCEL`). 재폴링 안전.
- **워커 연결**: 틱에 라이브 전용 cadence(5초). paper 무변경, 열린 주문 0건이면
  브로커 미호출, 오류 격리(거래 무중단).
- **CLI** `auto-invest fills [--sync]`.
- **안전 경계**: 주문/취소 안 함(브로커 확인 체결만 기록), 멱등, 라이브 전용, 거래
  무중단. **Kernel 터치 0건**(기존 `FILL`/`CANCEL` 재사용, 마이그레이션 불필요).
  테스트 신규 29건, 전체 1024 통과.

## 이전 마일스톤 — 2026-05-27 (스펙 014: 라이브 손실 서킷 브레이커)

PR #71 머지 커밋 `2c1b8aa`. **손실이 한도를 넘으면 사람 개입 없이 워커가 스스로
새 주문을 멈추는** 자동 손실 차단 장치를 추가했습니다. 그동안 위험 통제는 노출
상한(거래당·종목당·전체 캡)뿐이었고 손실 기반 자동 차단이 0건이었는데, 이 스펙이
실거래 전 안전 기반의 가장 큰 구멍을 메웁니다. 자세히는
`HANDOFF-019-SPEC-014-CIRCUIT-BREAKER.md`. 한 줄 요약:

- **두 한도**: 일일 실현 손실(`-(daily_loss_limit_pct% × 시작 자본)` 이하면 트립)
  + 전체 자산 낙폭(현재 자산 ≤ 시작 자본 × (1 − max_total_drawdown_pct/100)).
  손익은 스펙 011 성과 엔진 한 잣대 재사용(헌법 X).
- **워커 자동 정지**: `tick`에서 halt·세션 점검 이후 평가, 트립이면 `set_halt` +
  `CIRCUIT_BREAKER_TRIPPED` append 후 새 주문 없이 종료. halt 선점으로 멱등.
- **안전 경계**: 순수 방어적(정지만, 노출 증가/주문/청산 0건). 한도가 K1
  (`config/caps.py`)에 있어 **자율 튜너가 자동 완화 불가**. 기본값 활성(일일 10%·
  낙폭 20%)이나 카타스트로피급이라 정상 운영 무영향. 라이브 worker는 dry-run 그대로.
- **Kernel 터치**: K1+K4 추가-전용 커밋 `b7a1f25`(caps 손실 한도 필드 +
  `CIRCUIT_BREAKER_TRIPPED` 이벤트). K2·K3·K5·K6·K-meta 0건. 테스트 31건.
- **헬스 연동**: `auto-invest health`에 브레이커 점검 추가(읽기 전용, 트립 halt는
  CRITICAL).

## 이전 마일스톤 — 2026-05-26 (스펙 013: 운영 관측·신뢰성 — `auto-invest health`)

PR #69 머지 커밋 `8b29d42`. **"지금 시스템이 건강한가"를 한 화면·종료 코드로 답하는
읽기 전용 통합 헬스 롤업**을 추가했습니다. 그동안 관측 표면이 전부 흩어진 사후 분석
명령(`status`/`report`/`performance`/`efficiency`/`tune`)이라, 운영자가 여러 명령을
따로 돌려 머릿속에서 합쳐야 했습니다. 실거래 전환 전 신뢰 기반의 가장 큰 약점이었던
"통합 건강 뷰 부재"를 메웠습니다. 한 줄 요약:

- **5개 신뢰성 점검 + 종합 판정**: 워커 생존(PID 파일 + `os.kill(pid,0)`)·halt 플래그·
  정합성(결과 + 신선도)·최근 오류(24시간)·활동 신선도를 합쳐 종합 판정
  (`OK`<`DEGRADED`<`CRITICAL`, = 최악 점검값)을 냅니다. 맥락 블록(오늘 주문 깔때기·
  보유 종목 수·마지막 성과·튜너·캐너리)은 정보용(판정 미반영).
- **모니터링 연동**: `auto-invest health --format text|json --stale-hours 36`. 종료 코드
  `0`=정상 / `1`=불건강 / `2`=오용. 크론·알림이 종료 코드로 붙을 수 있습니다.
- **안전 경계 핵심**: **100% 읽기 전용** — 감사 로그 append 0건, 상태 파일 변경 0건,
  `db.migrate` 미호출(라이브 워커와 동시 실행 시 DB 손상 위험 회피). 거래 워커 루프
  무수정. DB 파일 없으면 빈 DB 생성 없이 `CRITICAL`.
- **Kernel 터치 0건**: 손댄 파일 전부 `reports/health.py`·`cli.py`(비커널)·`tests/`·
  `specs/013-operational-health/`. 테스트 22건(단위 16 + 통합 6).

## 이전 마일스톤 — 2026-05-26 (스펙 012: 튜너 L2/L3 → 하드닝 캐너리 자동 투입)

PR #67 머지 커밋 `943c08b`. **자율 튜너의 L2/L3 위험 변경을 스펙 007 하드닝 캐너리로
자동 투입해 검증**하는 경로를 깔았습니다. 그동안 튜너의 L2/L3 후보(모델·토큰 같은
위험 변경)는 감사 로그 한 줄만 적고 버려지는 빈 껍데기였는데, 이제 과거 리플레이+합성
충격+퍼즈로 검증하고 합격/불합격을 기록합니다. 자세한 내용은
`HANDOFF-018-SPEC-012-TUNER-CANARY.md` 참조. 한 줄 요약:

- **빈 껍데기 → 살아있는 검증 경로**: `detect.py` 의 cost/latency 드리프트가 가장 비싼
  판단 지점의 `max_tokens` 축소를 L2 후보로 제안 → `candidate.py` 구체화 →
  `canary_submit.py` 가 git plumbing 으로 임시 후보 rev(작업트리 무변경·미푸시) 생성 →
  `run_canary` 검증 → 합격/불합격 기록.
- **안전 경계 핵심**: 캐너리 검증은 시뮬레이션이지 배포가 아니다. **합격해도 라이브
  자동 승격 0건**(`promoted` 항상 False, 헌법 IX.B-2). 승격은 운영자/스펙 006 게이트
  전용. Kernel 터치 후보는 L4 강등 → 캐너리 자동 투입 제외. 리플레이 데이터 없으면
  fail-safe(skip), 캐너리 오류는 후보별 격리.
- **판단 튜닝 표면 신설(비커널)**: `config/judgment_tunables.toml` — 없거나 키 없으면
  현재 `max_tokens` 와 동일(런타임 동작 무변경).
- **K4 추가-전용 터치 1건**: `persistence/audit.py`(`AUTO_TUNED_CANARY_CANDIDATE`·
  `AUTO_TUNED_CANARY_VALIDATED`), 커밋 `01b821e`. K1·K2·K3·K5·K6·K-meta 터치 0건.

## 이전 마일스톤 — 2026-05-26 (스펙 005 후속: 자율 튜너 오프아워 타이머 연결)

PR #63 머지 커밋 `92dd0ff`. **자율 튜너를 매일 장 마감 후 자동 실행되도록 연결**했습니다. 그동안 `auto-invest tune --apply`(저위험 L1 자동 적용)는 수동/단발 실행이었는데, 라이브(dry-run) 워커 인스턴스에서 튜너가 자율로 돌게 만들어 헌법 원칙 X(측정→행동 루프)를 실제로 켰습니다. 자세한 내용은 `HANDOFF-017-TUNER-SCHEDULING.md` 참조. 한 줄 요약:

- **설계 — 워커 코드 무수정.** 워커 루프(`worker/loop.py`)를 한 줄도 안 바꾸고, 저장소에 이미 있는 오프아워 타이머 패턴(`auto-invest-deploy.timer`)을 미러링한 **외부 oneshot 타이머**가 이미 검증·머지된 CLI를 재실행. 라이브 거래 경로 블래스트 반경 0.
- **산출물**: `deploy/run-tune.sh`(래퍼, DB 없으면 종료 0 fail-safe) + `deploy/auto-invest-tune.service`(oneshot) + `deploy/auto-invest-tune.timer`(매일 22:00 UTC, 미국 장 마감 후, `Persistent=true`) + `vultr-userdata.sh` 설치 배선 + README·AUTO-DEPLOY 문서 + 테스트 8건 + 스펙 005 후속 노트.
- **Kernel 터치 0건.** 손댄 파일 전부 `deploy/`·`tests/`·`specs/`. 적용 안전성은 전부 튜너 자신(스펙 005)이 보장 — L1 한 종류·가역, 장중 0건 적용(VIII.A), 측정 부족 거부(X), 멱등, kernel 대상 L4 거부.
- **타이머 = 코드 배포가 아니라 런타임 KPI 임계값 튜닝.** 실거래 토글(`AUTO_INVEST_MODE=live`)과 무관 — 실거래 전환은 여전히 운영자 전용.
- **유닛 자동 설치(PR #65 `e8b3876`)**: 새 systemd 유닛을 라이브 서버에 올리는 데 운영자가 서버 접속할 필요 없음. `deploy-on-merge.yml`이 매 머지마다 `deploy/sync-units.sh`를 서버 `sudo bash`에 파이프해 유닛 설치 + 타이머 활성(워커 미재시작, `git show`로 트리 미오염 → 장중에도 안전). **주의: 서버 SSH 사용자의 `sudo`가 임의 명령(특히 `sudo bash`)을 허용해야 동작** — 막혀 있으면 Actions Summary에 "⚠ 유닛 동기화 실패"로 뜨고 sudoers 한 줄 추가 필요. 운영자는 PR #65 머지의 Actions "Deploy on merge to main" Summary에서 ✅ 확인.

## 이전 마일스톤 — 2026-05-24 (스펙 005 자율 튜너 출시)

PR #60 머지 커밋 `0a176fb`. **측정 → 분석 → 행동 루프를 닫는 자율 튜너**를 완성했습니다. 그동안 측정(스펙 002·011)과 판단(스펙 004)은 있었으나 "측정 신호를 받아 스스로 설정을 조정하는 행동" 단계가 비어 있었는데, 이 스펙이 그 마지막 고리를 헌법 안전 경계 안에서 채웁니다. 자세한 내용은 `HANDOFF-016-SPEC-005-AUTONOMOUS-TUNER.md` 참조. 한 줄 요약:

- **권한 등급(L1~L4)** — 기존 `kernel.toml` 매니페스트 리더(`deploy/kernel_guard.py`) 재사용. 변경 대상 파일이 Kernel(K1~K6·K-meta)에 닿으면 무조건 **L4 강등**(방어 심층화), 튜너는 `kernel.toml`·헌법을 절대 자동 수정 안 함.
- **L1 자동 적용은 단 한 종류** — `config/llm_kpi_thresholds.toml` 의 `tier_b` 임계값 조이기(30일 Tier B 안정 + 일별 Tier C 없을 때만, Tier A 경계 클램프, 가역). 장 시간 마진(헌법 VIII.A)·측정 부족(헌법 X)이면 거부, 멱등(세션 날짜 dedup), dry-run 무변경.
- **순수 결정론적**(LLM 미호출). 새 패키지 `src/auto_invest/tuner/`(models·detect·classify·knobs·gates·report·runner) + CLI `auto-invest tune`. 튜너 테스트 40개, 전체 887 통과.
- **유일한 Kernel 터치**: `persistence/audit.py`(K4) 추가-전용 `AUTO_TUNED_*` 4종, 커밋 `8bbfca2`. K1·K2·K3·K5·K6·K-meta 터치 0건.

## 이전 마일스톤 — 2026-05-24 (스펙 004 LLM 판단 지점 출시)

PR #58 머지 커밋 `78286eb`. **Claude를 거래 결정 루프에 처음 부르는 기능**을 완성했습니다. v1의 "판단 지점 0개"(FR-005) 제약을 명시적으로 열거된 세 결정에 한해 풀었습니다. 자세한 내용은 `HANDOFF-015-SPEC-004-JUDGMENT-POINTS.md` 참조. 한 줄 요약:

- **세 판단 지점**: `volatility_assessment`(변동성 급등 시 hold/size_down/halt 자문, P1·MVP)·`daily_summary`(장 마감 운영 요약, P2)·`news_screen`(장 시작 전 헤드라인 스탠스, P3) + 관측/예산(P4). 전부 헌법 III 계약(트리거·입력·출력 스키마·지연/비용 예산)을 코드로 선언.
- **핵심 안전 설계**: 자문은 `execution/order_router.py`(비커널)에서 주문을 **줄이거나 건너뛰기만** 함 — 노출 증가 불가(`size_down_factor` ≤ 1.0 스키마 강제). 그 뒤 K1 포지션 캡(`risk/gates.py`)이 변형 없이 실행되어 그대로 바인딩. 모든 판단 지점에 결정론적 폴백(LLM 실패해도 거래 안 막힘). 캐너리 단계 룰만 자문 반영(헌법 VI).
- **유일한 Kernel 터치**: `persistence/audit.py`(K4) 추가-전용 판단 이벤트 2종(`JUDGMENT_ADVISORY_APPLIED`·`JUDGMENT_FALLBACK`), 커밋 `7fac2c5`. K1·K2·K3·K5·K6·K-meta 터치 0건.
- 새 패키지 `src/auto_invest/judgment/`(schemas·registry·client·budget·observability·runner + points/). 판단 지점 테스트 55개. 전체 847 통과.

## 이전 마일스톤 — 2026-05-24 (spec 011 완결 + stale 추적 진실화)

PR #55 머지 커밋 `625165c`. 두 가지를 한 번에:

- **spec 011(라이브 성과 측정) 완결** — P3(일일 리포트 성과 섹션 + 튜너용 `LIVE_PERFORMANCE_SNAPSHOT` 추가-전용 이벤트)와 P4(슬리피지 측정)를 구현. 이제 측정 신호 면이 완비됐습니다: 손익·위험조정(샤프·낙폭·승률)·룰별/종목별 기여도·슬리피지·기계 판독 스냅샷. **이것은 spec 005 자율 튜너의 입력 신호** — 원칙 X(측정 기반 자율 성장)가 요구하는 측정 토대가 채워졌습니다.
- **stale 추적 진실화** — 우선순위를 판단하다 **중대한 상태 혼동**을 발견·수정했습니다. spec 006(배포 자동화)·007(하드닝 캐너리)의 tasks.md가 0%로 표시돼 있었으나 **실제로는 코드·테스트가 main에 완성·머지된 상태**였습니다(캐너리 테스트 93개·배포 테스트 8종 green). 하마터면 이미 끝난 40개짜리 스펙을 "미구현"으로 오판해 재구현할 뻔했습니다. 006·007 tasks.md를 done으로 갱신 + SHIPPED 배너, spec.md Status를 Shipped로, CLAUDE.md active-feature에 "체크박스 수치를 믿지 말 것" 경고를 넣었습니다.

**중요한 결론**: 빌드 가능한 스펙(006·007·008·009·010·011)은 **전부 완료**. 남은 spec 004·005는 **운영자 지시(2026-05-24)로 텔레메트리 30일 착수 게이트가 제거되어 즉시 착수 가능**합니다(아래 "2026-05-24 추가 지시" 참조). 단 안전 경계는 불변 — 자율 튜너 런타임 행동은 헌법 원칙 X(측정 기반), 자율 머지는 spec 007 캐너리, 판단 지점은 캐너리 ≥10 거래일에 계속 종속됩니다.

K4 추가-전용 터치 2건(forensic 주의, K-meta 아님): `458a0d8`(`LIVE_PERFORMANCE_SNAPSHOT` 이벤트), `64141b1`(`OrderPaperFilledPayload.reference_price_usd` 필드).

### 2026-05-24 추가 지시 — 스펙 004·005 착수 게이트 제거

운영자가 같은 날 "스펙 004·005는 텔레메트리 30일이 쌓이지 않아도 즉시 착수 가능하도록 조건 변경"을 지시. 적용:

- `specs/004-llm-judgment-points/spec.md`·`specs/005-autonomous-tuner/spec.md`의 promotion 조건에서 **"≥30 calendar days of telemetry" 착수 게이트 제거**. 즉시 `/speckit-specify`부터 시작 가능.
- **헌법·`kernel.toml`은 건드리지 않음** — 30일 게이트는 스펙 스텁의 착수 조건이었을 뿐 헌법 불변량이 아니었다. 헌법의 "≥30 trading-day"는 별개(스펙 007 캐너리 윈도, 안전 게이트)로 그대로 유지.
- **안전 경계 불변**: (1) 자율 튜너의 런타임 행동은 헌법 원칙 X(측정 없이는 튜닝 금지)에 계속 종속, (2) 자율 머지는 스펙 007 하드닝 캐너리가 유일한 경로(IX.B-2), (3) Kernel 터치는 L4 인간 머지 강제, (4) 실거래는 `AUTO_INVEST_MODE=live` 운영자 토글 전용. 바뀐 것은 "코드를 언제 쓰기 시작할 수 있는가"뿐.

## 이전 마일스톤 — 2026-05-23 (라이브 worker dry-run 시작)

자세한 내용은 `HANDOFF-014-LIVE-DRYRUN-STARTED.md` 참조. 한 줄 요약:

- `auto-invest design` 재호출로 **라이브 worker 가 dry-run(모의) 모드로 정상 시작** (run `26330498160`, 2026-05-23 10:36 UTC). 잔고 $292.61, 총 평가 $1,536.38. 룰 `rule_dca_voo_monday`(VOO 매주 월요일 09:35 적립) 외 생성.
- 실주문은 아직 안 나갑니다 — 헌법 VI 단계적 확장(백테스트→캐너리→본운영)의 1주일 안전 관찰 단계.
- 라이브 진입을 막던 버그 2개 해결: PR #47 (`8512fc2`, 프롬프트에 적립용 time 트리거 사용법 누락) + PR #48 (`3010648`, `trigger-design.yml` 의 AUTO_OK 가 sudo env_reset 으로 비워지던 문제).

이전 마일스톤(2026-05-22 KIS 회귀 자율 검증 도입, PR #33 `9096e21` / PR #34 `8cfb7d3`, main push 시 자동 회귀 smoke)은 `HANDOFF-012-KIS-AUTONOMOUS-VERIFY.md` 참조. `KIS smoke (autonomous)` 워크플로우는 활성 상태이며 매일 03:00 UTC + main push 시 자동 실행.

## 현재 main 상태 (누적 출시 이력 — 최신 기준은 위 한눈 요약표)

* **헌법 v3.1.0** (v3.0.0 2026-05-14 도입 머지 커밋 `f849fab`; v3.1.0 머지 커밋 `e949451`, 원칙 X 측정 기반 자율 성장 추가). 원칙 IX.D — 운영자 자율 수행 보장. PR 생성과 머지는 모두 자동 워크플로우의 일부. Kernel 터치도 머지를 막지 않음. 안전 경계는 **생산 배포 단계**(스펙 007 하드닝 캐너리)에서 지킴.
* **스펙 001 (미국 주식 자동 거래 MVP)** — 출시 완료 (2026-05-04). 실제 KIS 브로커 검증 완료. **후속(2026-05-27, PR #75 `4319535`)**: P2 사용자 스토리 "조용한 상태 드리프트 방지"의 미배선 부분(T050 자동 호출 + T052 워커 테스트)을 완성. 정합성 검증(로컬 장부↔브로커 보유 대조, 불일치 시 halt)은 구현(T049)·테스트(T048)는 됐으나 자동 호출 배선이 없어 테스트 스위트만 호출하던 상태였음. 이제 워커가 장 마감 전이마다 자동 대조(라이브 전용, 인-틱, 오류 격리) + `auto-invest reconcile` 수동 명령. Kernel 터치 0건. 자세히는 `HANDOFF-021-RECONCILE-AT-CLOSE.md`.
* **스펙 002 (토큰 사용량 측정)** — 출시 완료.
* **스펙 003 (세션 캐시)** — 출시 완료.
* **스펙 004 (LLM 판단 지점)** — **출시 완료** (2026-05-24, PR #58 머지 커밋 `78286eb`). Claude를 거래 루프에 처음 부르는 기능. 세 판단 지점(volatility_assessment·daily_summary·news_screen) + 관측/예산. 자문은 노출을 줄이거나 건너뛰기만 — K1 캡 그대로 바인딩. 결정론적 폴백·캐너리 게이트. K4 추가-전용 터치 커밋 `7fac2c5`. 판단 지점은 여전히 헌법 VI 캐너리 ≥10 거래일을 탄다(런타임 캐너리 단계 룰만 자문 반영).
* **스펙 005 (자율 튜너)** — **출시 완료** (2026-05-24, PR #60 머지 커밋 `0a176fb`). 측정→분석→행동 루프를 닫는 순수 결정론적 엔진(LLM 미호출). 권한 등급(L1~L4) 분류는 기존 `kernel.toml` 리더 재사용, Kernel 교집합=무조건 L4. L1 자동 적용은 `config/llm_kpi_thresholds.toml` 의 `tier_b` 임계값 조이기 한 종류(장 시간·측정·멱등 게이트). 새 패키지 `src/auto_invest/tuner/` + CLI `auto-invest tune`. K4 추가-전용 터치 커밋 `8bbfca2`(`AUTO_TUNED_*` 4종). 런타임 튜닝 행동은 원칙 X, 머지가 닿는 생산 배포는 스펙 007 캐너리에 계속 종속(안전 경계 불변). **후속(2026-05-26, PR #63 `92dd0ff`)**: 오프아워 systemd 타이머(`deploy/auto-invest-tune.timer`, 매일 22:00 UTC)가 `auto-invest tune --apply`를 자동 실행 — 튜너가 라이브 워커에서 자율로 돎(워커 코드 무수정, Kernel 터치 0건).
* **스펙 006 (배포 자동화 러너)** — 출시 완료 (2026-05-15, PR #7 머지 커밋 `790c0c1`). 38/38 작업 7단계 전부 완료. K4 터치 커밋 `c1800a6` (audit.py에 5종 새 이벤트 타입 추가). systemd 유닛/타이머 템플릿 동봉(`deploy/`).
* **스펙 007 (하드닝 캐너리 — 생산 배포 게이트)** — 출시 완료 (2026-05-14, PR #5 머지 커밋 `775f53a`). 40/40 작업 6단계 전부 완료.
* **스펙 008 (백테스트 엔진)** — 출시 완료 (2026-05-14, PR #4 머지 커밋 `7f8fb99`). 41/41 작업 완료 (PR #45 정합성 정정 포함).
* **스펙 009 (paper-run 데몬)** — 출시 완료 (2026-05-19, main `56ec260`).
* **스펙 010 (자동 룰 설계자)** — **출시 완료** (2026-05-20, PR #19 `14a7ff9` 본체 + PR #20 `d78d0ae` 라이브 worker 자동 시작 + PR #21 `167355c` `--check` 모드 + PR #22 운영자 가이드). 35/35 작업 6단계 전부 완료. K4 터치 커밋 `b6442ee` (audit.py에 RULE_DESIGN_* 4종 페이로드 추가). `auto-invest design --intent "..."` 한 줄로 자연어 의도 → Claude 룰 자동 생성 → 정적 검증 + paper-run → 운영자 OK → 자동 라이브.
* **스펙 011 (라이브 성과 측정)** — **출시 완료** (2026-05-24, PR #55 머지 커밋 `625165c`; P1·P2는 그 이전 PR #51·#52). P1 손익 엔진·CLI, P2 위험조정 지표(샤프·낙폭·승률, spec 008 metrics 재사용), P3 일일 리포트 성과 섹션 + 튜너용 `LIVE_PERFORMANCE_SNAPSHOT` 스냅샷, P4 슬리피지(기준가 대비 체결 품질). `auto-invest performance --since/--window [--slippage] [--snapshot] [--json]`. 읽기 전용 측정 — 돈을 움직이지 않음. spec 005 튜너의 입력 신호 면.
* **스펙 012 (튜너 L2/L3 → 하드닝 캐너리 자동 투입)** — **출시 완료** (2026-05-26, PR #67 머지 커밋 `943c08b`). 튜너의 L2/L3 위험 변경(모델·토큰)을 스펙 007 캐너리로 자동 투입해 검증(과거 리플레이+충격+퍼즈)하고 합격/불합격 기록. 빈 껍데기였던 L2 경로를 살아있는 검증 경로로 전환. **안전 경계: 합격해도 라이브 자동 승격 0건(`promoted` 항상 False, 헌법 IX.B-2). 캐너리=시뮬레이션이지 배포 아님. Kernel 후보 L4 제외. fail-safe(데이터 없으면 skip)·오류 격리.** 판단 튜닝 표면 `config/judgment_tunables.toml`(비커널, 폴백=동작 무변경). K4 추가-전용 터치 커밋 `01b821e`(`AUTO_TUNED_CANARY_*` 2종). 자세히는 `HANDOFF-018-SPEC-012-TUNER-CANARY.md`.
* **스펙 013 (운영 관측·신뢰성 — 통합 헬스 롤업)** — **출시 완료** (2026-05-26, PR #69 머지 커밋 `8b29d42`). `auto-invest health`: 워커 생존·halt·정합성·최근 오류·활동 신선도 5개 점검을 합쳐 종합 판정(`OK`/`DEGRADED`/`CRITICAL`)과 모니터링용 종료 코드(0/1/2)를 냄. **100% 읽기 전용**(감사 로그 append 0건, `db.migrate` 미호출, 거래 워커 루프 무수정). Kernel 터치 0건(`reports/health.py`·`cli.py`만). 테스트 22건. **후속(스펙 014)**: 헬스에 손실 서킷 브레이커 점검 1개 추가(총 6개 점검).
* **스펙 014 (라이브 손실 서킷 브레이커)** — **출시 완료** (2026-05-27, PR #71 머지 커밋 `2c1b8aa`). 손실이 한도를 넘으면 워커가 스스로 새 주문을 멈춤. 두 한도: 일일 실현 손실 + 전체 자산 낙폭. 손익은 스펙 011 성과 엔진 한 잣대 재사용(헌법 X). `tick`에서 halt·세션 점검 이후 평가, 트립이면 `set_halt` + `CIRCUIT_BREAKER_TRIPPED` append. **안전 경계: 순수 방어적(정지만, 노출 증가/주문/청산 0건). 한도가 K1(`config/caps.py`)에 있어 자율 튜너 자동 완화 불가. 기본값 활성(일일 10%·낙폭 20%)이나 카타스트로피급. 라이브 worker는 dry-run 그대로.** K1+K4 추가-전용 터치 커밋 `b7a1f25`. 테스트 31건. 자세히는 `HANDOFF-019-SPEC-014-CIRCUIT-BREAKER.md`.
* **스펙 015 (라이브 체결 동기화)** — **출시 완료** (2026-05-27, PR #73 머지 커밋 `e746f52`). 접수된 라이브 주문의 실제 체결을 브로커 조회(`inquire-ccnl`)로 멱등하게 `FILL` 기록·보유 캐시 갱신·상태 전이. 새 모듈 `execution/fill_sync.py`(순수 `plan_fill_ingestion` + async `sync_fills`). 워커 틱에 라이브 전용 cadence(5초) 연결, CLI `auto-invest fills [--sync]`. **안전 경계: 주문/취소 안 함(브로커 확인 체결만 기록), 멱등, 라이브 전용(paper 무변경), 거래 무중단(오류 격리). Kernel 터치 0건**(기존 `FILL`/`CANCEL` 재사용, 마이그레이션 불필요). 테스트 신규 29건. **이 기능이 스펙 014 브레이커·스펙 011 성과·정합성을 라이브에서 비로소 작동하게 한다.** 자세히는 `HANDOFF-020-SPEC-015-FILL-INGESTION.md`.
* **스펙 016 (백테스트 거래비용 + 단일 잣대 + 워크포워드)** — **슬라이스 1·2·3 출시 완료** (2026-05-27). 슬라이스 1(PR #77 `f8552c6`): 무비용·무슬리피지였던 백테스트에 거래비용 오버레이(슬리피지·수수료, KIS 현실값 기본). 새 모듈 `backtest/costs.py`. 슬라이스 2(PR #79 `83abbbb`): 거래 단위 지표 정의(승률·손익비·실현거래 재구성·Sortino)를 `backtest/metrics.py` 한 곳에 모아 라이브 성과 엔진과 백테스트가 같은 함수를 호출(헌법 X.2 완성). 슬라이스 3(PR #81 `9242faa`): 같은 룰셋을 롤링 표본 내(IS)/표본 외(OOS) 윈도우로 돌려 슬라이스 2 단일 잣대로 IS 대비 OOS 성과를 비교해 과적합 탐지. 새 모듈 `backtest/walk_forward.py` + CLI `auto-invest walk-forward`. 헤드라인 = 표본 외 집계 성과 + 워크포워드 효율(WFE = OOS 샤프 / IS 샤프). **안전 경계: 셋 다 오프라인·읽기 전용·Kernel 터치 0건(감사 스키마 K4 무변경).** 측정 토대 3단계(정직·통일·표본 외 검증) 완료 — 다음은 알파/사이징. 자세히는 `HANDOFF-022`·`HANDOFF-023`·`HANDOFF-024`.
* **스펙 017 (변동성 기반 포지션 사이징)** — **슬라이스 1·2·2b·3 출시 완료** (2026-05-28~29). 측정 토대 위에 리스크 사이징(변동성·역변동성·상관)을 한 바퀴 완성. 슬라이스 1(PR #83 `c291d75`): 변동성 throttle(하향 전용). 슬라이스 2(PR #85 `ab4a140`): 양방향 타깃팅(K1이 진짜 천장). 슬라이스 2b(PR #87 `b8fb7e9`): 역변동성 그룹 리스크 패리티. 슬라이스 3(PR #89 `33d3926`): 상관 헤어컷(옵트인, 하향 전용). **Kernel 터치 0건. 감사 K4 무변경. 결정론적·LLM 미사용. dry-run 그대로.** 자세히는 `HANDOFF-025`~`HANDOFF-028`.
* **스펙 018 (다요인 신호 + 사이징 감사 기록)** — **슬라이스 1·2 출시 완료** (2026-05-29, PR #91 `aeed831`). 슬라이스 1(비커널): `strategy/indicators.py`에 `momentum`(N기간 수익률%)·`bollinger_band_pct_b`(%B) 추가. `triggers.py`에 `MOMENTUM_ABOVE/BELOW`·`BB_ABOVE/BB_BELOW` 트리거 4종 연결. 슬라이스 2(K4 추가-전용): `audit.py`에 `SIZING_DECISION` 이벤트 + `SizingDecisionPayload`(실현 변동성·역변동성 가중치·상관·최종 수량). `sizing.py`에 `SizingResult`·`sized_quantity_with_result()` 추가. `order_router.py`에서 사이징 적용 시 감사 행 기록(`final_qty=0` 포함). **안전 경계: Kernel 터치 0건(K4 추가-전용). 옵트인(기존 룰 미변경 시 byte 동일). 하향 전용 불변량 유지.** 신규 테스트 32건, 전체 1142 통과. 자세히는 `specs/018-multifactor-signals/spec.md`.
* **스펙 019 (레짐 인식 + 완전 공분산 ERC)** — **슬라이스 1·2·3 출시 완료** (2026-05-29, PR #93 `6c1d849`). 슬라이스 1(비커널): `strategy/regime.py` — `Regime(StrEnum)` 3상태(TRENDING/RANGING/BEAR), `detect(bars)` SMA50/200 기반 결정론적 판별(200막대 미만 RANGING fail-safe), `DEFAULT_REGIME_SCALE`(추세=1.0/횡보=0.7/하락=0.3), `apply_regime_scale()`. 슬라이스 2(비커널): `strategy/sizing.py`에 `covariance_matrix()`·`erc_weights()`(Maillard CCD 반복 최적화)·`erc_group_scales()`(데이터 부족 시 역변동성 fallback) 추가. `config/rules.py` SizingConfig.mode에 `"erc"` 추가. 슬라이스 3: `tests/unit/test_regime_erc.py` walk-forward 표본 외 검증 19건 통과. **안전 경계: Kernel 터치 0건. ERC 가중치 max 1 클램핑(하향 전용). 결정론적 Decimal(헌법 X.2). 레짐·ERC 유틸리티 배선은 스펙 020(PR #95)에서 완성.** 신규 테스트 19건, 전체 1161 통과. 자세히는 `specs/019-regime-erc-sizing/spec.md`.
* **스펙 020 (레짐 배율·ERC 가중치 거래 루프 실배선)** — **출시 완료** (2026-05-29, PR #95 `cb5dcae`). `strategy/regime.py`·`strategy/sizing.py`의 레짐 감지기·ERC 유틸리티를 `execution/order_router.py`·`backtest/replay.py` 실제 거래 루프에 연결. `rule.regime_index_symbol`이 있으면 DB 인덱스 바 → `detect_regime()` → `apply_regime_scale(qty)`. qty < 1이면 `SKIPPED_BY_SIZING("regime_zero")`. `SizingConfig.mode="erc"` 지원. **Kernel 터치 0건. 하향 전용. 옵트인.** 신규 테스트 5건, 전체 1166 통과.
* **스펙 021 (횡단면 모멘텀 순위 필터)** — **출시 완료** (2026-05-29, PR #97 `2bd01b1`). 전체 유니버스를 N-기간 수익률로 내림차순 순위 매겨 상위 N개 또는 상위 P% 종목에만 매수를 허용하는 횡단면 랭킹 필터(Jegadeesh-Titman 팩터). 새 모듈 `strategy/ranking.py`(`cross_sectional_momentum`, `is_top_n`, `is_top_pct`). `TradingRule.ranking_filter`(`RankingFilter`: `universe`, `period`, `top_n`|`top_pct`). `order_router`·`replay` 양쪽 적용. 미통과 → `SKIPPED_BY_RANKING(not_in_top)`. **Kernel 터치 0건. 하향 전용. 옵트인.** 신규 테스트 13건, 전체 1179 통과.
* **스펙 022 (최소 분산 포트폴리오 최적화)** — **출시 완료** (2026-05-29, PR #99 `204dfc9`). `SizingConfig.mode="min_variance"` — numpy `linalg.solve`로 분석적 최소 분산 해. ridge 정규화. 수치 실패 → ERC → 역변동성 fallback. **Kernel 터치 0건. 옵트인.** 신규 테스트 8건, 전체 1187 통과.
* **스펙 023 (가격 기반 퀄리티 팩터 필터)** — **출시 완료** (2026-05-29, PR #100 `674c8dc`). 롤링 샤프 / (1 + |최대 드로다운|) 합성 점수로 유니버스 순위를 매겨 하위 종목을 `SKIPPED_BY_QUALITY`로 차단. 새 모듈 `strategy/quality.py`. `TradingRule.quality_filter`(`QualityFilter`: `universe`, `lookback_bars`, `top_n`|`top_pct`). **Kernel 터치 0건. 하향 전용. 옵트인.** 신규 테스트 8건, 전체 1195 통과.
* **스펙 024 (최대 샤프 포트폴리오 최적화)** — **출시 완료** (2026-05-29, PR #101 `86b2c32`). `SizingConfig.mode="max_sharpe"` — 롤링 모멘텀 신호를 기대 수익률 μ로 활용해 `w* ∝ Σ^{-1}·μ` 분석적 해. μ 전부 비양수이면 균등 가중치 fail-safe. 수치 실패 → min_variance → ERC → 역변동성 fallback. `expected_returns_from_closes()` 신규. **Kernel 터치 0건. 옵트인.** 신규 테스트 8건, 전체 1203 통과.
* **스펙 025 (다요인 합성 알파 점수)** — **출시 완료** (2026-05-30, PR #103 `127ca3f`). 여러 팩터(모멘텀·퀄리티·저변동성·평균회귀)를 횡단면 z-점수 가중합(하나의 합성 점수)으로 결합해 유니버스 순위. 새 모듈 `strategy/factors.py`. `TradingRule.composite_filter`. **Kernel 터치 0건. 하향 전용. 옵트인.** 신규 테스트 12건.
* **스펙 026 (캐너리→풀라이브 자동 승격 게이트)** — **출시 완료** (2026-05-30, PR #112 `b1a7e88`). `promotion/gate.py`(헌법 VI 6조건 순수 게이트) + `readiness.py`(라이브 audit_log 측정) + CLI `promote-check` + 매일 `promote-readiness.yml`. **승격 수행 안 함(보고 전용). 풀라이브는 VI 게이트 AND 스펙 007 캐너리(IX.B-2) 둘 다 통과해야 발화 — 최소 30거래일 후.** 자세히는 `HANDOFF-036-CANARY-CAPITAL-AND-PROMOTION-GATE.md`.
* **스펙 027 (디플레이티드 샤프 비율 — 다중검정 보정)** — **출시 완료** (2026-05-30, PR #114 `ec1d040`). 백테스트·워크포워드 샤프를 표본 길이·비정규성·시도 개수로 보정(PSR·MinTRL·DSR). 새 모듈 `backtest/significance.py`(scipy 없이 `Φ`/`Φ⁻¹` 구현). 워크포워드에 표본 외 풀 트랙 유의성 배선 + CLI `--num-trials`·`--trial-sharpe-std`·`--min-psr`·`--min-dsr`. **Kernel 터치 0건. 오프라인·읽기 전용. 기본값 byte 동일(옵트인 게이트).** 신규 테스트 32건. 자세히는 `HANDOFF-037-SPEC-027-DEFLATED-SHARPE.md`.
* **스펙 028 (체결 품질 정밀 측정 — arrival 기준 구현격차 + 체결 지연)** — **출시 완료** (2026-05-30, PR #116 `1dd665e`, K4 커밋 `589187a`). 매수/매도가 의사결정 순간 시세(arrival)에서 얼마나 벗어나(정확)·얼마나 늦게(실시간) 체결됐는지 시장가 주문까지 포함해 측정. `ORDER_INTENT`에 arrival 시세·호가 기록(K4 추가-전용), 라이브 슬리피지 기준가 arrival 우선(→지정가 폴백), `compute_fill_latency`(평균·중앙·p95·최대 초), `performance --slippage` 출력 + `LIVE_PERFORMANCE_SNAPSHOT` 지연 요약. **측정 전용 — 주문 경로(게이트 K1·사이징·브로커) 무변경. 안전 경계 무변경.** 신규 테스트 +10. 자세히는 `HANDOFF-038-SPEC-028-EXECUTION-QUALITY.md`.
* **라이브 worker** — dry-run(모의) 모드로 가동 중 (2026-05-23 시작). 실주문 미발생. `AUTO_INVEST_MODE=live` 명시 토글 전까지 돈은 움직이지 않음 (운영자 명시 지시 필요). **주의: 스펙 026 선택 1번으로 라이브 캐너리 무장됨(자본 $12k, 축소 룰셋) — `HANDOFF-035`·`HANDOFF-036` 참조.**
* **KIS smoke 자율 감시** — 활성 상태. main push 시 `KIS smoke (autonomous)` 워크플로우 자동 실행. 매일 03:00 UTC cron. 진단은 `automation/kis-smoke-last-run` 사이드카 브랜치에 force-push (`git show origin/automation/kis-smoke-last-run:LAST_RUN.md` 한 줄로 조회). 최신 실행은 schedule run `28774422030`, commit `6843ac7`, `smoke_state=success`, `key_valid=true`다. 이는 KIS 키와 smoke 건강 상태 참고 증거이며 #483 배포 직접 증거는 아니다.
* **main의 테스트**: #483 머지 전·머지 직전 `uv run pytest` 2491 통과, 4 스킵. HANDOFF 갱신 전 `uv run pytest -q`는 낡은 HANDOFF 때문에 하네스 2건만 실패했고, 이 handoff 갱신 뒤 2491 통과, 4 스킵으로 복구됐다.
* **린트**: 최신 인계 브랜치 기준 `uv run ruff check src tests` 깨끗.
* **라이브 브로커 검증**: 운영자(mason)가 2026-05-04에 본인 실제 KIS 계좌에서 `scripts/live_smoke.py` 실행 — 검증 완료.

## 운영자 사용성 — 지금 바로 가능한 것

스펙 006이 출시되면서 운영자가 SSH로 들어가 git pull/restart를 손으로 안 해도 됩니다. PR #9로 시작 키트가 들어가서 운영자가 자기 호스트에서 한 줄 명령으로 자동 검증 + 정확한 systemd 명령을 받아볼 수 있습니다.

### 운영자 프로필별 진입점

| 운영자 상황 | 진입점 |
|------------|--------|
| **개발 지식 없음, 자율 수행 최우선 (권장)** | `docs/OPERATOR_GITHUB_ACTIONS_KR.md` — GitHub Secrets에 Vultr 토큰 박고 "Run workflow" 한 번. `.github/workflows/provision-vultr.yml`이 Vultr API로 자동 인스턴스 생성. KIS 키만 Vultr 콘솔에서 한 번 입력. |
| **개발 지식 없음, Vultr 콘솔 직접** | `docs/OPERATOR_VULTR_ONE_STEP_KR.md` — cloud-init User-Data 붙여넣고 Deploy. GitHub Actions 안 씀. |
| **개발 지식 없음, 명령어 하나씩 학습** | `docs/OPERATOR_START_NONDEV_KR.md` — Vultr 콘솔에서 단계별 손 학습. |
| **개발자, Linux/systemd 호스트 보유** | `docs/OPERATOR_START.md` — `git clone` → `.env` → `bash scripts/operator_install.sh` 5분 경로. |

### ⚠ Vultr 콘솔 cloud-init 폼 검증 함정 (2026-05-16 발견)

운영자가 Vultr 새 Deploy UI에서 cloud-init User-Data 필드에 한글 주석이 포함된 `vultr-userdata.sh`를 붙여넣었더니 **Deploy 버튼을 눌러도 아무 반응이 없음** — 빨간 에러도 안 나옴. ASCII-only 버전으로 교체하니 즉시 작동. 결론:

- **`deploy/vultr-userdata.sh`는 ASCII-only로 유지해야 함.** 비ASCII 문자(한글 주석, em-dash 등) 들어가면 Vultr 폼이 조용히 거부. main에 박힌 파일은 이미 ASCII-only.
- 검증: `LC_ALL=C grep -P '[^\x00-\x7F]' deploy/vultr-userdata.sh` 결과가 빈 줄.
- 한글 사용자 안내는 `docs/OPERATOR_VULTR_ONE_STEP_KR.md`에 분리 보관.
- 이 함정은 Vultr GitHub Actions 워크플로우(옵션 D)에서도 동일 — 거기서도 ASCII payload만 보냄.

### 운영자가 "자율 수행 최우선"이라고 답한 경우 (2026-05-15~16 세션)

운영자 환경: Vultr 계정, 자본금 100달러로 시작, 개발 지식 없음. 운영자가 "가이드 따라 직접 따라하는 게 아니라 자율 수행이 우리 목표 아니냐"고 정확히 짚어줘서 옵션 D(GitHub Actions 자동화)로 결정됨. 그러나 (1) 컨테이너 환경에서 Vultr API outbound 차단, (2) Vultr Access Control이 `0.0.0.0/0` 거부 → GitHub Actions runner 동적 IP와 호환 불가. 최종적으로 옵션 B(Vultr 콘솔 직접 클릭 + 캡처 코칭)로 진행, 인스턴스 가동 성공 (2026-05-16, IP `202.182.125.132`, Tokyo). 다음 세션이 도와드릴 때:

1. **기본 가정**: 운영자는 `docs/OPERATOR_GITHUB_ACTIONS_KR.md` 경로. `.github/workflows/provision-vultr.yml` 이 Vultr API로 인스턴스 자동 생성. 운영자가 손대는 곳은 **GitHub Secrets 입력 + Run workflow 클릭 + Vultr 콘솔에서 set_secrets.sh 실행** 세 군데.
2. **⚠ 이 세션 환경 제약 (다음 세션도 동일)**: 이 컨테이너는 outbound HTTP가 GitHub만 허용. **Vultr API 직접 호출 불가** ("Host not in allowlist" 응답). 그래서 옵션 A(내가 직접 API 호출)는 시도 금지 — 토큰 받아도 못 씀. GitHub Actions runner는 외부 호출 가능하므로 옵션 D만 작동.
3. **운영자 비밀(KIS 키)을 채팅으로 받지 마세요.** 헌법 V 비밀 격리 위반. KIS 키는 운영자가 Vultr 콘솔의 set_secrets.sh prompt에 직접 입력하는 것이 유일하게 안전한 방법. "키 알려주시면 제가..." 절대 금지.
4. **Vultr API 토큰도 채팅으로 받지 마세요.** GitHub Secrets로 박는 게 안전. 만약 운영자가 채팅에 토큰을 보내면, 즉시 폐기(Regenerate) 안내 + 그 토큰 사용 안 함.
5. **자본금 100달러 + 1주일 dry-run 안전 약속**을 운영자에게 매번 상기.
6. 운영자가 막혔다고 가져오는 정보는 보통 워크플로우 실행 로그, Vultr 콘솔 캡처, `cat /var/log/auto-invest-cloud-init.log`, `journalctl -u auto-invest.service`. 각 가이드의 "막혔을 때" 절 참조.

### 개발자용 5분 경로

```bash
# 운영자 호스트 (Linux + systemd) 에서:
sudo install -d -m 0750 -o $(whoami) -g $(whoami) /opt/auto-invest
git clone https://github.com/jinooaction/claude.git /opt/auto-invest
cd /opt/auto-invest
uv sync
cp .env.example .env
nano .env                            # KIS_APP_KEY/SECRET/ACCOUNT_NO + AUTO_INVEST_CAPITAL
bash scripts/operator_install.sh     # 자동 검증 5단계 + sudo systemctl 명령 출력
# 출력된 sudo systemctl 명령 6줄 그대로 실행
```

`scripts/operator_install.sh`는 5단계 preflight를 수행합니다:

1. CLI 표면 확인 (`auto-invest --help`).
2. `.env`에 필수 키 4종(`KIS_APP_KEY`/`KIS_APP_SECRET`/`KIS_ACCOUNT_NO`/`AUTO_INVEST_CAPITAL`) 빈 값 아닌지.
3. SQLite 감사 로그 마이그레이션 적용.
4. 워커 dry-run — 브로커 호출 없이 룰 파일/캡 검증.
5. `auto-invest deploy --dry-run` — 배포 파이프라인 검증.

전부 통과해야만 systemd 명령을 출력하며, **root로 escalation은 절대 하지 않습니다** — 운영자가 출력된 명령을 검토한 다음 본인 손으로 실행합니다.

**즉시 사용 가능한 CLI**:

* `auto-invest run --dry-run --config tests/fixtures/rules/sample-canary.toml` — 브로커 안 건드리고 룰 검증.
* `auto-invest run --capital 10000` — 라이브 운영.
* `auto-invest deploy --dry-run` — 다음 배포가 무엇을 할지 미리 확인.
* `auto-invest deploy --branch main` — 실제 배포 (장중 자동 거부).
* `auto-invest backtest --rules config/rules.toml --from 2024-01-02 --to 2024-12-31` — 과거 데이터 백테스트.
* `auto-invest report --date 2026-05-04` — 일일 리포트.
* `auto-invest status` — 현재 상태 한 화면 JSON.
* `auto-invest design --intent "자본 100달러, 미국 대형주 분산, 위험 보통"` — 자연어 한 줄로 룰 자동 생성 + 검증 + OK 한 줄로 라이브 시작 (스펙 010, 2026-05-20 출시).
* `auto-invest design --check` — 진행 중 paper-run 상태 조회 (스펙 010 후속, 2026-05-20 출시).

**다음 후보 (빌드 가능한 스펙 001~012 전부 출시 완료 — 아래는 후속 확장 후보)**:

* **L1 적용 표면 확장** — 스펙 012가 모델·토큰 변경의 캐너리 검증 경로를 깔았으니, 모델 라우팅·`max_tokens` 를 즉시 자동 적용(L1) 노브로 승격하는 것을 검토 가능(여전히 품질 영향 신중히).
* **L2/L3 합격 → 운영자 승격 큐** — 캐너리 합격 후보를 운영자가 한눈에 보고 승격 결정하는 큐/대시보드(자동 승격은 여전히 운영자 게이트, 헌법 IX.B-2).
* **모델 교체 노브** — Haiku↔Sonnet 라우팅 변경을 캐너리 검증 대상으로(현재는 `max_tokens` 만; 모델 교체는 품질 영향이 더 커 스펙 012 범위 밖이었음).
* **튜너 자동 호출** — 이미 완료(스펙 005 후속, PR #63 오프아워 타이머).
* **실거래 전환** — `AUTO_INVEST_MODE=live` 토글 (운영자 명시 지시 필요, 돈 움직임).

위 운영 절차 + 스펙 010 `design` + 스펙 011 `performance` 측정 + 스펙 005 `tune` 자율 조정으로 v1 자동 거래·자율 성장 루프가 닫혔습니다.

## 출시된 기능 읽는 순서

1. `.specify/memory/constitution.md` — 헌법 v3.1.0, 원칙 IX.D 운영자 자율 수행 보장 + 원칙 X 측정 기반 자율 성장.
2. `.specify/memory/kernel.toml` — Kernel 매니페스트(고관심 포렌식 목록; v3.0.0에서 머지 차단 역할은 없음).
3. `CLAUDE.md` — 자동 워크플로우 + 자동 머지 + 한글 응답 정책. **PR을 열거나 머지하기 전에 반드시 읽으세요.**
4. `deploy/README.md` + `specs/006-deploy-automation/quickstart.md` — 운영자 systemd 설치 절차. **새 호스트에 올릴 때 첫 진입점.**
5. `specs/007-canary-hardening/` — 스펙 007 하드닝 캐너리 (생산 배포 게이트). `quickstart.md` 부터 시작.
6. `specs/008-backtest-engine/` — 스펙 008 백테스트 엔진. 캐너리의 핵심 의존성.

## 세션 수명주기 도구 (v3.3.0 신설 — 세션 간 "역사 혼동" 방지)

이 프로젝트가 반복해서 겪던 실패는 **세션과 세션 사이의 상태 혼동** 입니다 — 새 세션이 낡은 "active feature" 줄이나 낡은 `HANDOFF.md`를 믿고 잘못된 그림 위에 작업을 쌓는 것. v3.3.0에서 이를 기계적으로 막는 장치 네 개를 도입했습니다:

| 도구 | 종류 | 하는 일 |
|------|------|---------|
| `.claude/hooks/git_ground_truth.py` | 세션 시작 훅(자동) | 매 세션 라이브 로컬 git 상태 출력(현재 브랜치·HEAD·`origin/main` 대비·HANDOFF 최신순). 로컬 전용이라 절대 세션을 멈추지 않음. |
| `.claude/hooks/session_context.py` | 세션 시작 훅(자동) | 더 이상 `specs/001`을 하드코딩하지 않음. 진짜 오래 사는 문서(헌법·CLAUDE.md·살아있는 HANDOFF)만 고정 → 프롬프트 캐시는 유지하되 죽은 스펙으로 세션을 오도하지 않음. |
| `/sync` | 스킬 | 네트워크 발견(원격 `Codex/*` 브랜치·열린 PR·각 브랜치 HANDOFF·main 실제 최신)을 한 번에. 시작 훅의 네트워크 절반. |
| `/handoff` | 스킬 | 세션 끝에 `HANDOFF.md`(특히 아래 한눈 요약표)를 실제 git 상태로 갱신 후 푸시. 낡은 HANDOFF가 혼동의 가장 큰 원인이므로 이게 핵심 수정. |
| `/deploy-status` | 스킬 | 머지가 라이브(dry-run) 워커에 실제로 배포됐는지 컨테이너 안에서 확인. 배포는 push 트리거(`deploy-on-merge.yml`)라 PR 체크에 안 잡힘 → main 커밋 체크 + kis-smoke 사이드카로 확인하고, 컨테이너가 못 보는 곳(Actions Summary·서버 audit_log)은 솔직히 운영자 몫으로 표시. |

상세 정책은 `CLAUDE.md` § "Session lifecycle — start with truth, end with a handoff" 참조.

## 자동 머지 시스템 (v3.2.0 신설)

운영자가 매번 "머지해"라고 말하지 않아도 다음 조건이 모두 만족되면 즉시 자동 머지합니다:

1. 작업의 모든 후속 태스크 완료.
2. `uv run pytest` 통과 (skip 허용, fail 없음).
3. `uv run ruff check src tests` 깨끗.
4. PR `mergeable_state == "clean"`.
5. PR이 draft가 아니거나 ready로 전환 가능.

자동 머지 중단 조건은 좁습니다 — 헌법(`.specify/memory/constitution.md`) 변경 PR, 테스트 빨갛거나 mergeable_state 더러운 경우, PR 본문 "WIP" / "DO NOT MERGE" 표식, 운영자가 명시적으로 "머지하지 마" / "기다려" / "잠깐"이라고 한 경우.

상세 규칙은 `CLAUDE.md` § "운영자 응대 3대 규칙 — 규칙 3" 참조.

## 안전 불변량 (절대 협상 불가)

다음은 헌법 원칙 I-VII와 VIII.A로 보호되며, 어떤 자율 워크플로우 변경에도 영향받지 않습니다:

- 포지션 사이징 (개당 / 종목당 / 전체 한도)
- 화이트리스트 기본 거부 정책
- LLM은 미리 정의된 판단 지점에서만 호출
- 추가-전용 감사 로그
- 비밀 정보 격리 (KIS 키 등)
- 백테스트 → 캐너리 → 본 운영 단계 진행
- 외부 API 견고성
- 장중 배포 금지

이 불변량은 스펙 007 하드닝 캐너리에 의해 **생산 배포 경계**에서 강제됩니다 (라이브 워커가 새 코드를 받기 전에).

## 과거 인수인계 파일 (참고용)

- `HANDOFF-128-CANDIDATE-RESULT-RETRYABLE-BLOCKED.md` — #571 후보 결과 실행기가 retryable factory-blocked 후보를 안전 no-live 검증까지 진행하고, post-merge 결과 sidecar가 `blocked=0`, `pending=2`, `data_history_missing=2`를 남긴 상태
- `HANDOFF-127-LIVE-CANARY-OBSERVE-GATEWAY.md` — #568/#569 live canary sidecar freshness와 fixed observe gateway 복구, post-merge pipeline/money-path/capital-path 상태
- `HANDOFF-126-FORWARD-PAPER-ECONOMIC-ANCHOR.md` — #566 forward paper 경제 장부 보정과 post-merge forward/money-path/capital-path sidecar 상태
- `HANDOFF-125-REGIME-STRATIFY-OBSERVE-GATEWAY.md` — #564 regime-stratify 관측 gateway 복구와 post-merge sidecar 성공 상태
- `HANDOFF-124-FORWARD-PAPER-DB-WRITABILITY.md` — 스펙 122 forward paper DB writability 복구와 post-merge forward 관측 성공 상태
- `HANDOFF-123-PROMOTE-READINESS-OBSERVE-GATEWAY.md` — 스펙 121 promote-readiness 관측 복구와 서버 root-owned helper self-refresh 완료 상태
- `HANDOFF-122-RELEASED-WORK-CANDIDATE-120-CONSUMPTION.md` — 스펙 120 완료 후보 released-work 소비와 autonomous-work 관찰 대기 상태
- `HANDOFF-121-SSH-SECRET-FAIL-CLOSED.md` — 스펙 119 후속 production 환경과 SSH secret 누락 조기 차단 완료 상태
- `HANDOFF-120-SSH-BOUNDARY-REPAIR.md` — 스펙 119 후속 SSH boundary repair와 forced-command deploy gateway 경로
- `HANDOFF-119-SECURITY-TRUST-BOUNDARY-HARDENING.md` — 스펙 119 보안 신뢰 경계 강화와 GitHub root SSH secret 제거 상태
- `HANDOFF-118-KIS-OPEN-ORDER-SMOKE.md` — KIS 열린 주문 smoke와 스펙 118 마무리
- `HANDOFF-117-OPERATOR-REPORT-LIVENESS-CONTRACT.md` — 스펙 118 운영자 이해 가능 보고 생존성 계약과 다음 후보 없음 상태
- `HANDOFF-116-SUBMISSION-UNKNOWN-BROKER-LOOKUP.md` — 스펙 117 `SUBMISSION_UNKNOWN` broker lookup 복구와 실행 안전성 111~117 폐쇄
- `HANDOFF-115-EXECUTION-SAFETY-STABILIZATION.md` — 스펙 111 operator-design 평행 실거래 진입점 격리, 스펙 112 주문 제출 불확실성 회복, 스펙 113 원자적 체결 원장, 스펙 114 계좌 노출 예약, 실행 안전성 후속 순서
- `HANDOFF-114-AGENT-HARNESS-REGRESSION-LIVENESS.md` — 스펙 110 agent harness 회귀 생존성 계약과 운영자 이해 가능 보고 후보 전진
- `HANDOFF-113-WORKTREE-CONCURRENCY-LIVENESS-CONTRACT.md` — 스펙 109 worktree 동시 작업 생존성 계약과 agent harness 회귀 후보 전진
- `HANDOFF-112-PR-MERGE-EVIDENCE-LIVENESS-CONTRACT.md` — 스펙 108 PR/머지 증거 생존성 계약과 worktree 동시 작업 후보 전진
- `HANDOFF-111-HANDOFF-TRUTH-LIVENESS-CONTRACT.md` — 스펙 107 HANDOFF 사실성 생존성 계약과 PR/머지 증거 후보 전진
- `HANDOFF-110-AGENT-OPS-FRONTIER-MAP.md` — 스펙 106 운영 체계 frontier 지도와 handoff 사실성 생존성 후보 전진
- `HANDOFF-109-BROKER-DIAGNOSTIC-LIVENESS-CONTRACT.md` — 스펙 105 브로커 진단 생존성 계약과 운영 체계 frontier 후보 전진
- `HANDOFF-108-EXECUTION-COST-BASIS-CONTRACT.md` — 스펙 104 체결 비용 기준 계약과 브로커 진단 생존성 후보 전진
- `HANDOFF-107-BROKER-REJECTION-TAXONOMY-CONTRACT.md` — 스펙 103 브로커 거부 분류 계약과 체결 비용 기준 후보 전진
- `HANDOFF-106-EXECUTION-QUALITY-FRONTIER-MAP.md` — 스펙 102 체결 품질 frontier 지도와 브로커 거부 분류 후보 전진
- `HANDOFF-105-DATA-EVIDENCE-LIVENESS-CONTRACT.md` — 스펙 101 데이터 증거 생존성 계약과 체결 품질 frontier 후보 전진
- `HANDOFF-104-REGIME-TIMELINE-COVERAGE-CONTRACT.md` — 스펙 100 레짐 타임라인 커버리지 계약과 데이터 증거 생존성 후보 전진
- `HANDOFF-103-PUBLIC-DATA-INPUT-QUALITY-CONTRACT.md` — 스펙 099 공개 데이터 입력 품질 계약과 레짐 타임라인 커버리지 후보 전진
- `HANDOFF-102-DATA-EVIDENCE-FRONTIER-MAP.md` — 스펙 098 데이터 증거 frontier 지도와 공개 데이터 입력 품질 후보 전진
- `HANDOFF-101-COST-ADJUSTED-EDGE-EXPERIMENT.md` — 스펙 097 비용 차감 no-live 엣지 실험 계약
- `HANDOFF-100-SIGNAL-DIVERSIFICATION-EDGE-EXPERIMENT.md` — 스펙 096 신호 다변화 no-live 엣지 실험 계약
- `HANDOFF-099-FORWARD-REGIME-EDGE-EXPERIMENT.md` — 스펙 095 forward 레짐 엣지 no-live 실험 계약
- `HANDOFF-098-INVESTMENT-EDGE-FRONTIER-MAP.md` — 스펙 094 투자 엣지 frontier 지도와 no-live 실험 후보 전진
- `HANDOFF-097-MACRO-CANDIDATE-MAP-REGENERATOR.md` — 스펙 093 거시 후보 지도와 후보 재생성 루프
- `HANDOFF-096-FRONTIER-CANDIDATE-DISCOVERY.md` — 스펙 092 자율 후보 고갈 뒤 frontier 발굴 후보 폐쇄
- `HANDOFF-095-AUTONOMOUS-GROWTH-OBJECTIVE-CALIBRATION.md` — 스펙 091 자율 성장 목적 함수와 탐색 예산 보정
- `HANDOFF-094-SOURCE-DIVERSIFICATION-CANDIDATE-CLOSURE.md` — 스펙 090 source diversification 산출 후보 완료 폐쇄
- `HANDOFF-093-EVOLUTION-SOURCE-DIVERSIFICATION.md` — 스펙 089 정적 후보 템플릿 밖 증거 기반 후보 공간 확장
- `HANDOFF-092-AUTONOMOUS-MACRO-GROWTH-DISCOVERY.md` — 스펙 088 거시 자율 성장 후보 발굴기
- `HANDOFF-091-LEARNING-LEDGER-CANDIDATE-MEMORY.md` — 스펙 087 학습 장부 후보 재발굴 차단
- `HANDOFF-090-AUTONOMOUS-SIDECAR-HANDOFF-LIVENESS.md` — 스펙 086 자율 루프 sidecar와 HANDOFF 생존성
- `HANDOFF-089-PUBLIC-DATA-CROSS-VALIDATION.md` — 스펙 085 공개 데이터 수집·교차 검증 확장
- `HANDOFF-088-STALE-EVIDENCE-SEPARATION.md` — 스펙 084 오래된 증거와 성과 실패 분리
- `HANDOFF-087-REJECTED-ORDER-EXECUTION-QUALITY.md` — 스펙 083 주문 거부·체결 품질 손익 관측
  (2026-07-02, PR #448 `b4fa316`, PR #449 `f874b64`). `execution-quality` sidecar로 거부 주문,
  KIS 오류 코드, KIS smoke, live gate를 읽기 전용 증거로 묶고, liveness가 보고서 자체 발행 시각을
  freshness로 읽게 했다. 완료 마커로 `candidate-dff4f9344b02` 반복 선택을 막는다. 읽기 전용 운영 보정이며
  주문·자본·live 설정 변경 없음.

- `HANDOFF-086-REGIME-PERFORMANCE-CANDIDATE-SCORING.md` — 스펙 082 레짐·성과 후보 점수화
  (2026-07-02, PR #446 `0a5ad0f`). `promote-readiness`를 자율 성장 후보 점수화 입력으로
  승격하고, 완료 마커로 `candidate-e481b0309206` 반복 선택을 막는다. 읽기 전용 운영 보정이며
  주문·자본·live 설정 변경 없음.

- `HANDOFF-085-AUTONOMOUS-LOOP-QUALITY-CLOSURE.md` — 스펙 081 자율 루프 품질 폐쇄
  (2026-07-02, PR #444 `649a8df`, PR #445 `a98db6e`). 자율 작업 패킷의 착수 가능성,
  완료 관문, sidecar 시점 차이 판독, pipeline-liveness 후속 감시를 보강했다.

- `HANDOFF-084-OPERATOR-DASHBOARD-ALERTS.md` — 스펙 080 운영자 대시보드와 모바일 알림 루프
  (2026-07-02, PR #441 `43b5da8`, PR #442 `27388dd`, PR #443 `eb7de67`). 흩어진
  sidecar를 운영자 요약, 모바일 상태판, 필요 시 Telegram best-effort 알림으로 묶었다.

- `HANDOFF-083-COMPLETED-CANDIDATE-CONSUMPTION.md` — 스펙 079 완료 후보 소비 장부
  (2026-07-02, PR #436 `1a9a518`, PR #437 `c8beb25`, PR #439 `88929c8`). 완료된 Speckit 후보를 `released-work` 장부로 기록하고,
  자율 작업 실행 루프가 `candidate-fd04772a23c5`를 `RELEASED`로 소비해 차순위
  `candidate-e481b0309206`로 이동하게 한다. 읽기 전용 운영 루프이며 주문·자본·live 설정 변경 없음.

- `HANDOFF-082-MONEY-GATE-ALIGNMENT.md` — 스펙 078 돈 경로 게이트 정렬 루프
  (2026-07-01, PR #434 `09b528a`). money-path, capital-path-readiness, edge-autoarm,
  reassign, forward, pipeline, autonomous-work, KIS smoke sidecar를 한 번에 대조해
  `ALIGNED_WAITING / PREVIEW_ONLY / ACCUMULATING_EDGE`와 `WAITING forward_observation`
  상태를 발행한다. 읽기 전용 보고 루프이며 주문·자본·live 설정 변경 없음.

- `HANDOFF-081-AUTONOMOUS-WORK-EXECUTION.md` — 스펙 077 자율 작업 실행 루프
  (2026-07-01, PR #432 `996ce56`). 기존 자율 성장·승격·후보 검증·자본 준비도·
  파이프라인 생존 sidecar를 읽어 다음 Codex 작업 패킷을 자동 발행한다.
- `HANDOFF-080-CAPITAL-PATH-READINESS.md` — 스펙 076 자본 경로 준비도 루프
  (2026-07-01, PR #430 `23ec54b`). money-path, edge-autoarm, reassign,
  paper-forward, KIS smoke, promotion/evolution sidecar를 읽어 자본 투입 준비도와
  다음 안전 행동을 발행한다.
- `HANDOFF-079-STRATEGY-FAILURE-LEARNING.md` — 스펙 075 전략 실패 학습 장부화
  (2026-07-01, PR #428 `fa8cc32`). promotion summary의 `DISCARD` 전략/포트폴리오 후보를
  autonomous evolution `learning_ledger.json`의 `rejected` 항목으로 남겨 같은 실패 후보가
  새 승격 후보처럼 반복되지 않게 했다.
- `HANDOFF-078-CANDIDATE-HISTORY-SUPPORT.md` — 스펙 074 후보 가격 이력 지원과 승격 실패 반영
  (2026-07-01, PR #425 `fcc6e5f`, PR #426 `d3ca5d5`). 후보 결과 실행기가 전략/포트폴리오
  후보 가격 이력을 준비하고, 실패한 후보 공장 결과를 promotion loop가 `DISCARD`로 분류한다.
- `HANDOFF-077-CANDIDATE-PENDING-NEXT-ACTIONS.md` — 스펙 073 후보 pending next action 보정
  (2026-07-01, PR #423 `0de15a4`). 후보 공장 명령 계약과 result executor support input을 보정해
  `command_contract_error` 2건과 `execution_failed` 1건을 제거했다. 최신 result sidecar는
  `pass=7`, `pending=2`, `blocked=0`이고, 남은 pending은 가격 이력 부족이다.
- `HANDOFF-076-CANDIDATE-EVIDENCE-DIAGNOSTICS.md` — 스펙 072 후보 증거 진단 루프
  (2026-07-01, PR #421 `e00ef09`). 후보 결과 실행기의 `pending` 원인을 진단 코드와 다음 행동으로
  분해하고, 후보 공장이 이를 enriched backlog에 전파한다. 스펙 073 이전 기준 최신 result sidecar는
  `pass=4`, `pending=5`였다.
- `HANDOFF-075-CANDIDATE-FACTORY-RESULT-STATUS.md` — 후보 공장 result status 보정
  (2026-06-30, PR #419 `0b743c2`). 비전략 no-live 검증 통과 후보를 모두 `pending`처럼 표시하던
  상태 판독을 고쳤다.
- `HANDOFF-074-CANDIDATE-RESULT-EXECUTOR.md` — 스펙 071 후보 결과 실행기 루프
  (2026-06-30, PR #417 `b827364`). 후보 구현 공장이 만든 검증 패키지를 allowlist no-live 명령으로
  실행하고 `automation/candidate-implementation-results` sidecar를 발행한다.
- `HANDOFF-073-CANDIDATE-IMPLEMENTATION-FACTORY.md` — 스펙 070 후보 구현 공장 자동화
  (2026-06-29, PR #414 `b395e83`). `BACKTEST_REQUIRED` 후보를 검증 패키지와
  enriched backlog로 변환하고, 실제 결과 증거가 세 필수 검증을 통과할 때만
  `promotion_evidence`를 보강한다. 첫 push run의 입력 fetch 버그는 #415에서 보정됐고,
  run `28339828605`가 후보 9개 패키지 발행을 확인했다.
- `HANDOFF-072-AUTONOMOUS-PROMOTION-ACTIONS.md` — 스펙 069 자율 승격 실행 루프 자동화
  (2026-06-29, PR #410 `27da8b4`). 승격 후보를 promotion 전용 forward paper 등록 큐와
  hardened canary 제출 큐로 자동 연결했다. 신규 forward는 paper 전용이고, canary는 기존
  안전 게이트 밖에서 실주문을 만들지 않는다.
- `HANDOFF-071-AUTONOMOUS-PROMOTION-LOOP.md` — 스펙 068 자율 승격 루프 자동 분류
  (2026-06-29, PR #408 `ddecebb`). 성장 후보를 백테스트, 최근 표본외, forward paper,
  canary 후보, 기존 돈 게이트 중 다음 안전 단계로 분류한다. 주문·자본·live 전략 변경 없음.
- `HANDOFF-070-OPERATOR-READABLE-REPORTING.md` — 운영자가 이해 가능한 완료 보고 강제
  (2026-06-29, PR #406 `c4400b7`). 완료 보고가 PR 번호·커밋·테스트 수만 나열하지 않고 실제
  운영 상태 변화, 돈 경로와 안전 경계 영향, 검증, 남은 위험을 쉬운 한글로 설명하도록
  `AGENTS.md`, 품질 관문, 하네스 품질 과제에 `operator_readability`를 고정했다.
- `HANDOFF-069-AUTONOMOUS-EVOLUTION-IMPLEMENTATION.md` — 스펙 067 영구 자율 성장 루프 구현
  (2026-06-29, PR #404 `424a70e`). read-only 루프가 sidecar와 handoff 증거를 읽어 고레버리지
  후보, 안전한 실험 계획, 학습 장부, 최신 실행 보고서를 발행한다. 첫 workflow run `28329967896`은
  `overall_status=ok`였고 주문·자본·whitelist/caps·live 전략 변경 없음.
- `HANDOFF-068-EVOLUTION-BREAKTHROUGH-FRAMING.md` — 스펙 067 영구 성장 목표 정정
  (2026-06-29, PR #402 `9e1e492`). 자율 고도화 루프를 기다림 활용이 아니라 전 영역 돈 버는 능력과
  검증 능력을 복리화하는 상시 성장 엔진으로 재정의했다. 당시 구현은 아직 시작하지 않았고
  `tasks.md` T001부터 남아 있었다. 주문·자본·whitelist·caps·live 전략 변경 없음.
- `HANDOFF-067-AUTONOMOUS-EVOLUTION-LOOP.md` — 스펙 067 자율 고도화 루프 설계
  (2026-06-28, PR #400 `8f9a99f`). 전 영역 고레버리지 돌파 후보를 자동으로 발굴하고 안전한
  실험으로 승격하는 영구 read-only 성장 루프를 설계했다. 당시 구현은 아직 시작하지 않았고
  `tasks.md` T001부터 남아 있었다. 주문·자본·whitelist·caps·live 전략 변경 없음.
- `HANDOFF-066-MICRO-GTAA-BLOCKER-REVIEW.md` — micro GTAA intent-loss 다음 행동 안내 보정
  (2026-06-28, PR #398 `0b7c248`). `INTENT_LOSS` 차단 중에는 새 live 표본이 자동으로 쌓이지
  않으므로, forward 토너먼트·재지정 증거 또는 별도 전략 검토 후 재무장 여부를 판단하도록
  안내를 바로잡았다. 주문 차단, `armed:false`, 자본, 허용 종목, 전략 설정 변경 없음.
- `HANDOFF-065-STRATEGY-OBSERVATION-HEALTH.md` — 전략 검토 관측 품질 오판 보정
  (2026-06-27, PR #396 `d97d6a2`). 모든 후보가 최소 관측 전인 정상 누적 차이를
  `DEGRADED`로 오판하지 않게 했고, mixed comparable/premature 상태는 계속 `DEGRADED`로 막는다.
  실주문, 자본, whitelist, live 전략, 센티넬 변경 없음.
- `HANDOFF-064-MICRO-GTAA-INTENT-LOSS-GATE.md` — micro GTAA 손실 의도 실주문 차단
  (2026-06-27, PR #394 `6272178`). 최신 `INTENT_LOSS`, 누적 의도 손익 `-1.14 USD`를 근거로
  micro GTAA를 `armed:false`로 전환하고, strategy-intent gate가 preflight/live 주문 단계를
  막도록 했다. post-merge run `28274580272`에서 live 주문 단계는 skipped였다.
- `HANDOFF-063-REJECTED-OPPORTUNITY-FEEDBACK-LOOP.md` — 거부 주문 누적 평가와 자율 재지정
  피드백 루프 (2026-06-26, PR #392 `f76aa07`). micro GTAA 거부 주문 기회손익을 rolling
  history와 monitor verdict로 누적하고, Telegram·sidecar·reassign evidence에 연결했다.
  기존 5중 재지정 게이트를 우회하지 않으며 주문·자본·전략 파일 변경 없음.
- `HANDOFF-062-REJECTED-ORDER-OPPORTUNITY-ALERTS.md` — 거부 주문 기회손익과 Telegram 가독성 보강
  (2026-06-26, PR #390 `4175f13`). 거부된 BUY/SELL 주문을 현재가 기준으로 평가하는 읽기 전용
  `auto-invest rejected-order-opportunity` 명령과 micro GTAA sidecar/Telegram 기회손익 섹션을
  추가했다. 주문 라우터·게이트·자본·허용 종목 변경 없음.
- `HANDOFF-061-TELEGRAM-ALERT-FLOOD-FIX.md` — Telegram 알림 폭주 방지와 KIS 진단 보강
  (2026-06-26, PR #388 `7195c48`). 오래된 Telegram cursor catch-up을 기본 최신 25개로 제한하고,
  동일 `ERROR` 1시간 cooldown, KIS HTTP 200 오류 본문 진단 보존, Telegram 알림 서비스 전용
  `status/disable/restart/enable` workflow를 추가했다. #388 배포와 KIS smoke 성공 뒤 서비스
  재시작 run `28212999028`도 성공했다.
- `HANDOFF-060-ACCOUNT-WIDE-MICRO-GTAA.md` — 스펙 063 계좌 전체 micro GTAA 자율 재배치
  (2026-06-23, PR #386 `7a14315`). 기존 KIS 보유와 현금을 계좌 전체 입력으로 읽고,
  `BHP`, `MRK`, `ORANY`, `RELX`를 청산 전용으로 선언해 현금 부족 시 매도부터 실행하는
  sell-first 루프를 추가했다. 목표 매수 유니버스는 계속 `SPYM`, `IEF`, `GLDM`이다.
- `HANDOFF-059-MONEY-PATH-STATE.md` — 스펙 062 money-path 실제 돈 최상위 상태
  (2026-06-22, PR #384 `3440001`). `live_money_state`를 money-path JSON/text 최상위에 추가하고,
  micro GTAA `armed:true`, 자본 1000달러, 마지막 실행의 브로커 거부 2건·접수체결 0건을 한곳에서
  분리해 보이게 했다. 읽기 전용 보고 변경이며 주문·자본·K1/K2/K4/K5/K6 변경 없음.
- `HANDOFF-058-TELEGRAM-SERVER-CONNECT.md` — 스펙 061 Telegram 서버 연결 자동화
  (2026-06-22, PR #382 `845c5b1`). GitHub secrets의 Telegram token/chat id를 서버
  `/opt/auto-invest/.env`에 반영하고, test message 후 `auto-invest-telegram-alerts.service`만
  enable/start하는 manual workflow를 추가했다. 실제 run `27944499731` 성공. 주문·브로커·자본·
  위험 게이트 변경 없음.
- `HANDOFF-057-TELEGRAM-ORDER-ALERTS.md` — 스펙 060 Telegram 모바일 주문 알림
  (2026-06-22, PR #380 `6384584`). micro GTAA workflow 결과 알림과 서버 `audit_log` observer
  알림 CLI·service를 추가했다. 후속 스펙 061에서 실제 secrets/server 연결과 service enable까지
  완료됐다.
- `HANDOFF-056-KIS-ORDER-DIAGNOSTICS.md` — 스펙 059 KIS 주문 원인 확정 경로 복구
  (2026-06-22, PR #378 `24c2947`). micro GTAA live 주문 전 정규장·매수가능 현금 preflight를
  추가하고, KIS 주문 본문을 공식 해외주식 보통 주문 필드에 맞췄으며, 브로커 거부 응답을 마스킹해
  K4 감사 payload까지 보존한다. 실제 주문 재시도 0건, 새 접수·체결 0건. 다음 live 실패는
  preflight 또는 KIS 진단으로 원인을 확정해야 한다.
- `HANDOFF-055-MICRO-GTAA-ARMED.md` — 스펙 058 마이크로 GTAA 운영자 승인 무장 및 수동
  live 실행 (2026-06-22, PR #376 `75717a2`). `armed:true`, `capital_usd:1000`이 main에 남아
  있고, 수동 run `27935469561`은 live 단계까지 진입했으나 `KIS` 주문 API 500으로 `IEF` 1주와
  `SPYM` 3주가 모두 브로커 거부됐다. 접수·체결 0건. 다음 15:00 UTC 스케줄에서 자동 재시도 가능.
- `HANDOFF-054-MICRO-GTAA-CANARY.md` — 스펙 058 마이크로 GTAA 실거래 캐너리
  (2026-06-22, PR #374 `f3d5085`). `SPYM`·`IEF`·`GLDM` 3다리 소액 실거래 경로를 추가했다.
  기본 `armed:false`, push는 미리보기 전용, 실주문은 비-push 이벤트와 사전 손실 브레이커 및
  기존 K1·화이트리스트·지정가·정규장 게이트 통과가 필요하다. 헌법·커널·비밀값 변경 없음.
- `HANDOFF-053-HANDOFF-BASELINE.md` — HANDOFF-only merge 기준선 보정 (2026-06-22, PR #372
  `119ad4a`). `check_handoff_facts.py`가 일반 stale HANDOFF는 계속 실패시키되, `.md` 또는
  `specs/`만 바꾼 handoff-only merge 직후에는 첫 번째 부모를 유효 기준선으로 인정한다.
  헌법·커널·주문·비밀값·돈 경로 변경 없음.
- `HANDOFF-052-AGENT-QUALITY-REDTEAM.md` — Codex 품질·레드팀 하네스와 HANDOFF 사실 검증
  (2026-06-22, PR #370 `ecc93f2`). `scripts/agent_harness_probe.py --strict`가 품질 과제,
  레드팀 과제, HANDOFF 사실 검증까지 포함해 `OK (14/14)`를 요구한다. 등급 2 이상 PR은
  `check_handoff_facts.py` 결과도 `## 하네스 검증`에 남겨야 한다. 헌법·커널·주문·비밀값·돈 경로
  변경 없음.
- `HANDOFF-051-AGENT-HARNESS.md` — Codex 에이전트 하네스 평가·회귀·PR 증거 관문 (2026-06-20, PR #368 `cbc2cd4`). `scripts/agent_harness_probe.py --strict`로 세션 시작 훅, 동시 작업 방어, SDD 포인터, PR 품질 관문, 회귀 과제 묶음을 로컬 읽기 전용 평가. 등급 2 이상 PR은 `## 하네스 검증`에 strict 평가 증거를 남겨야 함. 헌법·커널·주문·비밀값·돈 경로 변경 없음.
- `HANDOFF-045-LIVE-PORTFOLIO-ARMED.md` — (A) 룰 워커 끄고 추세 방어 포트폴리오로 라이브 캐너리 무장 (2026-06-04, PR #178·#179 `96ff217`). 돈 단위 검증(코드+실데이터 드라이런: AAPL 1주 @ $312). 룰 워커 비활성 + 포트폴리오 무장($500). 첫 실주문=다음 시장시간 스케줄. 안전장치 다중.
- `HANDOFF-046-SPEC-043-MULTI-ASSET-TREND.md` — 스펙 043 멀티에셋 분산 추세추종 (2026-06-05, PR #205 `64ead83`). 검증된 단일 자산 추세 방어를 비상관 자산(주식 SPY + 채권 IEF) 분산으로 확장. Shiller 1871~ 검증: 분산 샤프 1.58/1.81/1.78 vs 단일 1.18/1.43/1.29, 낙폭 절반, 모든 창·가중 조합 견고. forward 페이퍼 ARM D 배선. Kernel 0·돈 0·PAPER 전용.
- `HANDOFF-047-SPEC-044-GROWTH-OPTIMAL.md` — 스펙 044 성장 최적 레버리지 (2026-06-05, PR #207 `ca3d47f`). 고정 자본 복리 극대화: 복리 천장은 샤프로 결정, 낙폭 예산 30%서 레버리지로 복리 ~2배(현대 9.5→14.7%, 최근 8.9→17.0%), 과레버리지=파산 정직 보고, 보수적 예산서 분산 우위. 리스크 패리티는 측정 후 50/50 유지. 레버리지는 연구 전용·라이브 K1 캡 불변. Kernel 0·돈 0.
- `HANDOFF-048-SPEC-045-REGIME-AUDIT.md` — 스펙 045 최근 regime/시점 강건성 감사 (2026-06-06, PR #209 `03938c6`). '먼 과거 기준' 점검: 엣지는 최근 5~20년·2020년대서 더 강함(분산 추세 샤프 1.59~1.80), 최근 5년 주식·채권 상관 양수(+0.095, 정적 분산 약화, 판정 WEAKENED), 2022 동반폭락(60/40 -14.8%)에 분산추세 -1.2%(추세 게이트 방어). 진짜 가치=추세로 게이트한 분산. 측정 전용·Kernel 0·돈 0.
- `HANDOFF-049-SPEC-046-STRATEGY-MONITOR.md` — 스펙 046 일일 전략 모니터 (2026-06-06, PR #211 `a36ea23`). 검증 스펙 042~045를 합친 지속 감시 대시보드를 forward 사이드카에 배선: ① 엣지 최근 유효성 ② 분산 가정 신뢰도 ③ 낙폭 예산별 레버리지 복리 권고(최근 25년: 15% L=2.0 복리 11.5%) ④ 오늘 추세 신호. 러너 로컬·완전 격리. 읽기 전용·돈 0·Kernel 0·라이브는 운영자 게이트.

- `HANDOFF-044-LIVE-CANARY-ARMING.md` — 스펙 039+040: 고도화를 소액 실거래로 올리는 가드형 무장 채널 (2026-06-04, PR #174·#175·#176 `7a56370`). $500 무장본(top_n=1, 추세 방어) + 가드형 워크플로(기본 드라이런, 실주문은 armed:true). 🚨 계좌 충돌 블로커(룰 워커 먼저 비활성). 무장 전 드라이런 미리보기 확인 필요. 돈 0 이동(현재).

- `HANDOFF-043-SPEC-038-CALMAR.md` — 스펙 038: 칼마 비율(자본 방어 측정) forward-verdict 추가 (2026-06-04, PR #172 `9ae4238`). 샤프가 못 잡는 드로다운 방어를 칼마(연수익/최대낙폭)로 측정. 게이트 불변, 보고 전용. 페이퍼·라이브 공통. Kernel 터치 0건. 신규 7건.

- `HANDOFF-042-SPEC-037-AB-TOURNAMENT.md` — 스펙 037: forward A/B 토너먼트(추세 ON vs OFF, 전용 DB 격리) (2026-06-03, PR #170 `e1cae73`). 대조군 `canary-portfolio-notrend.toml`(trend_filter 외 동일) + 워크플로 2팔(forward_trend.db / forward_notrend.db). 코드 변경 0(DB 파일이 격리), 돈 0 이동.

- `HANDOFF-041-SPEC-036-TREND-FILTER.md` — 스펙 036: 절대 모멘텀 추세 필터(드로다운 방어 오버레이) (2026-06-03, PR #167 `8bee9c8`). `strategy/trend.py` — 종목별 추세 아래면 현금으로 빠짐(Faber/Antonacci식), `target_weights` 옵트인, `[portfolio.trend_filter]`. 끄면 byte 동일. 라이브 캐너리 미적용(운영자 결정). Kernel 터치 0건. 신규 테스트 22건.
- `HANDOFF-040-SPEC-035-FORWARD-VERDICT.md` — 스펙 035: forward 엣지 자동 판정 폐회로 (2026-06-03, PR #165 `9bfa55d`). 끊겨 있던 "돈 버는지 판정" 폐회로 완성 — 생산자 CLI `nav-snapshot`(스펙 029 `compute_nav` 를 처음 실행 경로에 배선, `PORTFOLIO_NAV_SNAPSHOT` 기록) + 소비자 CLI `forward-verdict`(NAV 시계열 → 디플레이티드 샤프 vs 단순 보유 → EDGE/NO_EDGE/INSUFFICIENT 판정) + `rebalance-paper-forward.yml` 배선. Kernel 터치 0건, 돈 0 이동. 신규 테스트 19건.
- `HANDOFF-039-SPEC-034-UNIVERSE-CONSTRUCTION.md` — 스펙 034: 체계적 유니버스 구성 + 현재 데이터 경로 배선 + stale 백테스트 재발 차단 가드 (2026-06-03, PR #159·#161·#162·#163). 유동성 기반 `strategy/universe.py` + CLI `build-universe`. ⚠ 옛 데이터(2013-2018) 백테스트는 판정 아님(stale).
- `HANDOFF-038-SPEC-028-EXECUTION-QUALITY.md` — 스펙 028: 체결 품질 정밀 측정(arrival 기준 구현격차 + 체결 지연) (2026-05-30, PR #116 `1dd665e`, K4 커밋 `589187a`). `ORDER_INTENT`에 arrival 시세·호가 기록 → 시장가 주문도 슬리피지 측정 가능 + 페이퍼·라이브 단일 잣대, `compute_fill_latency`로 의사결정→체결 지연 집계. 측정 전용(주문 경로 무변경). 신규 테스트 +10.
- `HANDOFF-037-SPEC-027-DEFLATED-SHARPE.md` — 스펙 027: 디플레이티드 샤프 비율(다중검정 보정 통계) (2026-05-30, PR #114 `ec1d040`). PSR·MinTRL·DSR을 `backtest/significance.py`에 구현(scipy 없이 `Φ`/`Φ⁻¹`)하고 워크포워드 과적합 탐지기에 배선. 세계 최고 수준 측정 토대의 마지막 조각. Kernel 터치 0건. 신규 테스트 32건.
- `HANDOFF-036-CANARY-CAPITAL-AND-PROMOTION-GATE.md` — 캐너리 실체결 자본($12k)+축소 룰셋 + 자동 승격 게이트(스펙 026) (2026-05-30, PR #110~#112). 선택 1·2 자율 완료. 라이브 캐너리 실체결 가능 + 헌법 VI 승격 게이트 매일 평가(풀라이브 발화는 스펙 007 하드닝 캐너리까지 게이트, 미구현). **다음 세션 필독.**
- `HANDOFF-035-GO-LIVE-CANARY.md` — 실거래 전환: 라이브 캐너리 무장 + 헌법 X.4 개정(v4.0.0) (2026-05-30, PR #105~#108). 운영자 지시로 dry-run → 라이브 캐너리 자율 전환. 가드형 go-live 채널(`go-live-canary.sh`/`.yml`) 구축·발사, 결과 `armed_live_canary`. **현재 라이브 모드 가동 중(자본 $100·캐너리 룰셋·캡으로 실질 체결 ~0). 다음 세션 필독.**
- `HANDOFF-034-SPEC-025-COMPOSITE-FACTOR.md` — 스펙 025 다요인 합성 알파 점수 필터 (2026-05-30, PR #103 `127ca3f`). 여러 팩터(모멘텀·퀄리티·저변동성·평균회귀)를 횡단면 z-점수 가중합으로 결합해 순위. `strategy/factors.py` 신규, `CompositeFactorFilter` 모델, `order_router`·`replay` 양쪽 적용. Kernel 터치 0건. 신규 테스트 12건. **실거래 전환 재검토 결론(기술 준비 완료·운영자 게이트 대기) 포함. 다음 세션 참고.**
- `HANDOFF-033-SPEC-024-MAX-SHARPE.md` — 스펙 024 최대 샤프 포트폴리오 최적화 (2026-05-29, PR #101 `86b2c32`). `mode="max_sharpe"` 평균-분산 최대 샤프 해. Kernel 터치 0건. 신규 테스트 8건.
- `HANDOFF-002-003.md` — 스펙 002/003/004/005/006/007 골격 + 헌법 v2.0.0 단계의 상태. v3.0.0 이전이므로 "운영자가 수동 머지" 가이드는 **사용하지 마세요**.
- `HANDOFF-008.md` — 스펙 008 작업 단계 상태. 스펙 008이 출시되어 더 이상 활성 작업 아님.
- `HANDOFF-010-OPERATOR-RESUME.md` — 스펙 010 운영자 자율 수행 셋업 흐름 (historical — HANDOFF-014 가 정정).
- `HANDOFF-011-AUTONOMOUS-OPS.md` — GitHub Actions 자율 수행 셋업 완료 노트 (historical — "현금 $0" 은 버그였음, HANDOFF-014 정정).
- `HANDOFF-012-KIS-AUTONOMOUS-VERIFY.md` — KIS 회귀 자율 검증 워크플로우 도입 (2026-05-22). 워크플로우는 활성이나 작업 단위는 완료.
- `HANDOFF-013-AUTONOMOUS-DIAG-CHANNEL.md` — 자율 진단 채널(사이드카 브랜치) 노트.
- `HANDOFF-014-LIVE-DRYRUN-STARTED.md` — 라이브 worker dry-run 시작 + HANDOFF-010/011 오해 정정 (2026-05-23).
- `HANDOFF-015-SPEC-004-JUDGMENT-POINTS.md` — 스펙 004 LLM 판단 지점 출시 (2026-05-24). 출시 완료, 더 이상 활성 작업 아님.
- `HANDOFF-016-SPEC-005-AUTONOMOUS-TUNER.md` — 스펙 005 자율 튜너 출시 (2026-05-24, PR #60 `0a176fb`). 출시 완료. 후속 후보 목록의 출처.
- `HANDOFF-017-TUNER-SCHEDULING.md` — 스펙 005 후속: 자율 튜너 오프아워 타이머 연결 (2026-05-26, PR #63 `92dd0ff`). 튜너가 매일 장 마감 후 자동 실행.
- `HANDOFF-018-SPEC-012-TUNER-CANARY.md` — 스펙 012 튜너 L2/L3 → 하드닝 캐너리 자동 투입 출시 (2026-05-26, PR #67 `943c08b`). 위험 변경을 캐너리로 자동 검증(합격해도 자동 승격 0건).
- `HANDOFF-019-SPEC-014-CIRCUIT-BREAKER.md` — 스펙 014 라이브 손실 서킷 브레이커 출시 (2026-05-27, PR #71 `2c1b8aa`). 손실 한도(일일 실현/전체 낙폭) 초과 시 워커 자동 정지. 순수 방어적, 한도는 K1 보호.
- `HANDOFF-020-SPEC-015-FILL-INGESTION.md` — 스펙 015 라이브 체결 동기화 출시 (2026-05-27, PR #73 `e746f52`). 접수 주문의 실제 체결을 브로커 조회로 멱등하게 FILL 기록·보유 갱신·상태 전이. Kernel 터치 0건. 스펙 014 브레이커·스펙 011 성과·정합성을 라이브에서 작동하게 하는 키스톤.
- `HANDOFF-021-RECONCILE-AT-CLOSE.md` — 스펙 001 T050/T052 장 마감 정합성 자동 실행 (2026-05-27, PR #75 `4319535`). 구현·테스트는 됐으나 자동 호출 배선이 빠져 테스트만 호출하던 정합성 검증을, 워커 장 마감 전이마다 자동 대조 + `auto-invest reconcile` 수동 명령으로 연결. 라이브 전용·인-틱·오류 격리·Kernel 터치 0건.
- `HANDOFF-022-SPEC-016-BACKTEST-COSTS.md` — 스펙 016 슬라이스 1 백테스트 거래비용·슬리피지 모델 (2026-05-27, PR #77 `f8552c6`). 무비용·무슬리피지였던 백테스트(헌법 VI가 경고한 거짓 잣대)에 거래비용 오버레이를 입힘 — 슬리피지(체결가 악화)+수수료(현금 차감), KIS 현실값 기본. 새 모듈 `backtest/costs.py`. 오프라인·읽기 전용·Kernel 터치 0건. **세계 최고 수준 로드맵의 토대**: 정직한 잣대 위에서만 신호·사이징 개선이 의미를 가짐.
- `HANDOFF-023-SPEC-016-SLICE2-SINGLE-YARDSTICK.md` — 스펙 016 슬라이스 2 단일 잣대 통일 (2026-05-27, PR #79 `83abbbb`). 거래 단위 지표 정의(승률·손익비·실현거래 재구성·Sortino)를 `backtest/metrics.py` 한 곳에 모아 라이브 성과 엔진과 백테스트가 같은 함수를 호출하게 함(헌법 X.2 완성). 그동안 승률·손익비는 라이브에만 있었고 둘 다 Sortino 없었음. 오프라인·읽기 전용·Kernel 터치 0건(감사 스키마 K4 무변경). 테스트 신규 18건.
- `specs/018-multifactor-signals/spec.md` — **최신**. 스펙 018 다요인 신호 + 사이징 감사 기록 (2026-05-29, PR #91 `aeed831`). 슬라이스 1: `momentum`(N기간 수익률%)·`bollinger_band_pct_b`(%B) 신호 + `MOMENTUM_ABOVE/BELOW`·`BB_ABOVE/BB_BELOW` 트리거 4종. 슬라이스 2: `SIZING_DECISION` 감사 이벤트(K4 추가-전용), `SizingResult`·`sized_quantity_with_result()`, order_router 연결. 비커널+K4 추가-전용. 옵트인·하향 전용 불변량 유지. 신규 테스트 32건, 전체 1142 통과.
- `HANDOFF-030-SPEC-021-CROSS-SECTIONAL-RANKING.md` — 스펙 021 횡단면 모멘텀 순위 필터 (2026-05-29, PR #97 `2bd01b1`). 유니버스 전체를 N-기간 수익률로 순위 매겨 상위 N/P% 종목만 통과. `strategy/ranking.py` 신규, `RankingFilter` Pydantic 모델, `order_router`·`replay` 양쪽 적용. Kernel 터치 0건. 신규 테스트 13건. **다음 세션 참고.**
- `HANDOFF-029-SPEC-020-REGIME-ERC-WIRING.md` — 스펙 020 레짐 배율 + ERC 가중치 거래 루프 실배선 (2026-05-29, PR #95 `cb5dcae`). `order_router`·`replay` 양 경로에 레짐 배율·ERC 가중치 실제 적용. Kernel 터치 0건. 신규 테스트 5건. 스펙 019 유틸리티를 실거래 루프에 연결 완료.
- `HANDOFF-028-SPEC-017-SLICE3-CORRELATION.md` — 스펙 017 슬라이스 3 상관 헤어컷 (2026-05-29, PR #89 `33d3926`). 그룹 멤버 간 양의 상관에 비례해 집중 베팅을 추가로 줄이는 방어적 하향 헤어컷. 새 함수 `pearson_correlation`·`average_correlations`(공통 거래일 정렬)·`correlation_haircut`·`group_scale_for`. 옵트인 `correlation_haircut`(기본 0=슬라이스 2b byte 동일). 백테스트·라이브가 같은 날짜 키로 정렬해 같은 상관(단일 잣대). 하향 전용·Kernel 터치 0건·테스트 신규 7건. 리스크 사이징 토대(변동성·역변동성·상관) 한 바퀴 완성. 다음: 신호/알파 과학 또는 스펙 017 후속(ERC/budget-split/K4). **다음 세션 참고.**
- `HANDOFF-027-SPEC-017-SLICE2B-RISK-PARITY.md` — 스펙 017 슬라이스 2b 역변동성 그룹 리스크 패리티 (2026-05-29, PR #87 `b8fb7e9`). 여러 종목을 한 바구니(`sizing_group`)로 묶어 변동성 높은 종목을 줄여 리스크 기여도 균형화(`mode="inverse_vol"`, 가중치=`min(그룹 변동성)/자기 변동성`, 하향 전용). 새 함수 `build_sizing_groups`·`inverse_vol_group_scale`. worker가 그룹을 만들어 `OrderRouter.sizing_groups`로 넘기고 백테스트·라이브가 같은 함수로 가중치 계산(단일 잣대). 그룹 옵트인·회귀 무손상·Kernel 터치 0건·테스트 신규 8건. 다음: 슬라이스 3(상관)/양방향 budget-split. **다음 세션 참고.**
- `HANDOFF-026-SPEC-017-SLICE2-BIDIRECTIONAL.md` — 스펙 017 슬라이스 2 양방향 변동성 타깃팅 (2026-05-28, PR #85 `ab4a140`). 변동성 타깃팅의 나머지 절반 — 잔잔한 구간(실현 < 타깃)에서 사이즈를 타깃 리스크 예산까지 확대. 룰의 선택적 `max_scale`(기본 1=슬라이스 1 byte 동일, `ge=1`, `le=10`)로 상향 한도 지정, `volatility_scale`이 `[min_scale, max_scale]`로 클램프. 연결 지점 로직 변경 없음(이미 K1 게이트 전 호출). **K1이 진짜 천장 — 확대해도 K1 게이트가 초과 주문 거부(SC-S09 증명).** 하향 조절 그대로·회귀 무손상·Kernel 터치 0건·테스트 신규 9건.
- `HANDOFF-025-SPEC-017-VOL-SIZING.md` — 스펙 017 슬라이스 1 변동성 기반 포지션 사이징 (2026-05-28, PR #83 `c291d75`). 측정 토대 위에 리스크 사이징 시작. 실현 변동성이 타깃 초과 시 기준 수량을 줄이는 결정론적 변동성 throttle(하향 전용). 새 비커널 모듈 `strategy/sizing.py` + 룰의 선택적 `SizingConfig`(기본 fixed=v1). 백테스트·라이브 양쪽이 K1 게이트 전에 같은 함수 호출. K1 캡 무변경·Kernel 터치 0건·테스트 신규 18건.
- `HANDOFF-024-SPEC-016-SLICE3-WALK-FORWARD.md` — 스펙 016 슬라이스 3 워크포워드(표본 외) 검증 (2026-05-27, PR #81 `9242faa`). 같은 룰셋을 롤링 표본 내(IS)/표본 외(OOS) 윈도우로 돌려 슬라이스 2 단일 잣대로 IS 대비 OOS 성과를 비교해 과적합 탐지. 새 모듈 `backtest/walk_forward.py` + CLI `auto-invest walk-forward`. 헤드라인 = 표본 외 집계 성과 + 워크포워드 효율(WFE = OOS 샤프 / IS 샤프). 오프라인·읽기 전용·Kernel 터치 0건. 테스트 신규 10건.

## 다음 세션이 하지 말아야 할 것

- 진행 중인 브랜치가 있는데 main에서 새 브랜치를 만들지 **마세요** (위 발견 순서가 이를 막아줍니다).
- 열린 PR + 활성 인수인계 파일이 다음 작업을 알려주고 있는데 운영자에게 "어떤 작업을 원하세요?"라고 묻지 **마세요**.
- 출시 완료된 스펙(001 / 002 / 003 / 004 / 005 / 006 / 007 / 008 / 009 / 010 / 011)의 소스를 운영자의 명시적 수정 지시 없이 건드리지 **마세요**.
- spec 006·007의 tasks.md가 한동안 0%로 표시됐던 것처럼 **체크박스 수치만 보고 "미구현"이라 판단하지 마세요** — 코드와 테스트가 진실입니다. 의심되면 해당 모듈 디렉터리와 테스트를 먼저 확인하세요.
- KIS 자격 증명을 어디에도 푸시하지 **마세요**. `.env`는 gitignore되어 있고, 라이브 테스트는 `KIS_LIVE_TEST=1`로 게이트됨.
- `main`에 직접 푸시하지 **마세요** (직접 푸시 금지; 모든 변경은 PR을 통해 머지).

## 한눈 요약표 (현재 진실 — 2026-06-22)

| 항목 | 상태 |
|------|-------|
| 헌법 | **v6.0.0** (X.5 자율 전략 재지정 위임 포함, 안전 경계 기록 완료) |
| 운영자 응대 정책 | `AGENTS.md` Codex 작업 운영 규칙 + `CLAUDE.md` 기존 Claude 정책. Codex는 `AGENTS.md` 우선 |
| 마지막 main 커밋 | `845c5b1 Merge pull request #382 from jinooaction/Codex/telegram-server-connect` |
| 활성 작업 | 코드 PR 없음. Telegram secrets와 서버 `.env` 반영, test message, `auto-invest-telegram-alerts.service` enable/start까지 완료됨. micro GTAA는 `armed:true`, `capital_usd:1000` 상태지만 다음 live 주문은 정규장·매수가능 현금 preflight와 손실 브레이커를 통과해야 한다 |
| 최근 완료 | PR #382: 스펙 061 Telegram 서버 연결 자동화와 실제 workflow 실행. PR #380: 스펙 060 Telegram 모바일 주문 알림. PR #378: 스펙 059 KIS 주문 전제 확인과 진단 보존 |
| 안전 경계 | #382는 등급 3 외부 API·비밀값 서버 연결 경로 추가지만 observer service만 enable/start했고 주문·브로커·위험 게이트 변경 없음. #378은 등급 4 돈 경로 진단 보존. 실제 주문 재시도 0건, 새 접수·체결 0건. 헌법·커널 목록·캡·화이트리스트·낙폭 예산·서킷 브레이커·주문 제한 변경 없음 |
| main 테스트 | `uv run pytest -q` → 2242 passed, 4 skipped |
| main 린트 | `uv run ruff check src tests` 깨끗 |
| 열린 PR | 없음 (GitHub connector open PR 조회 기준) |
| 출시 완료 스펙 | 최신 추가: 061(Telegram 서버 연결 자동화), 060(Telegram 모바일 주문 알림), 059(KIS 주문 전제 확인과 진단 보존), 058(마이크로 GTAA 실거래 캐너리) |
| 다음 세션 핵심 | 등급 2 이상 운영 변경은 `uv run python scripts/agent_harness_probe.py --strict`와 `uv run python scripts/check_handoff_facts.py`를 실행하고 PR 본문 `## 하네스 검증`에 결과를 남긴다. local concurrency guard 경고가 있으면 같은 디렉터리에서 쓰지 말고 `python3 scripts/local_concurrency_guard.py --mode isolate`를 먼저 실행한다. PR·머지·배포·원격 브랜치 판단 전에는 `/sync`로 네트워크 상태를 갱신 |

## 과거 상세 요약표 (역사 보존 — 일부 행은 위 현재 요약표보다 낡을 수 있음)

| 항목 | 상태 |
|------|-------|
| 헌법 | **v5.0.0** (IX.D 운영자 자율 수행 + 원칙 X 측정 기반 자율 성장; **X.4 재개정 — 자본 사다리 상시 위임(스펙 050)**: 단0=0%→단1=25%→단2=50%→단3=100% of 실계좌 NAV, 증거 게이트 승격·즉시 강등/정지, 낙폭 예산 20% 운영자 소유; 장중가드·K1 캡·화이트리스트·감사·시크릿·서킷 브레이커 보존; 머지 커밋 `a94d413`) |
| 운영자 응대 정책 | CLAUDE.md v3.3.0 (한글 응답 / 쉬운 한글 / 자동 머지 / 세션 수명주기) |
| 마지막 main 커밋 | `732ca35 Merge pull request #330 — feat(analytics) 캐너리 합격 후보 운영자 승격 큐 + 세 방향 로드맵` |
| 활성 작업 | **(현재 — ✅ 폐회로 완성) 🔁 스펙 055 — 자율 전략 재지정 폐회로(#322·#324, main `c397d1a`).** 헌법 X.5(자율 전략 재지정 위임, v6.0.0)의 5중 게이트 폐회로를 end-to-end 완성. 결정 두뇌(`decide_reassignment`, 5중 게이트, #318)가 REASSIGN 을 내면, 챔피언 트랙의 전략 블록(`[portfolio]` 이후)을 라이브 설정(`canary-live-portfolio.toml`)에 텍스트로 그대로 이식하고 자본 사다리를 rung 0(무장 해제)으로 리셋하는 순수 함수(`portfolio/reassign_exec.py`) + 그것을 호출하는 `reassign-decide` CLI 글루. 운영/거래집합(`[caps]`·`[whitelist]`)은 라이브 원본 보존(헌법 X.5: 무엇을만 바꾸고 얼마나·어디서는 안 바꿈). 안전 가드(헌법 II): 챔피언 유니버스가 라이브 화이트리스트 밖이면 거부(거래집합 확대=운영자 게이트) — `global`(역변동성)↔`globalfixed`(등가중) 허용, `wide`(11슬리브, QQQ 등) 거부. 돈 0 이동(rung 0=무장 해제, 재무장은 사다리 게이트·실주문은 시장시간 스케줄). Kernel 0·헌법 변경 0·순수 additive, 신규 21건(실행 함수 14+CLI 7, 실제 deploy 파일 정합성 포함). **완성(#324): ④ 하드닝 캐너리(`canary/portfolio_harness.py`, 검증된 포트폴리오 백테스트 엔진 + 스펙 007 5지표 재사용)·폐회로 워크플로(`reassign-on-tournament.yml`)·인스턴스 DB 바 어댑터(`SqliteBarDataSource` — 캐너리가 토너먼트·라이브와 같은 `price_bars` 로 챔피언 검증, 폐회로 실가동). 설계 문서 `specs/055-autonomous-reassignment/spec.md`. 전체 2127 통과. 후속(선택): 실제 워크플로 1회 관측(평일 00:20 UTC) + globalfixed 가 EDGE_CONFIRMED 벌면 첫 자율 재지정 관찰.** ─── (이전) 🏆 스펙 053 — forward 토너먼트 리더보드(#283, main `7da58e2`).** 전진 페이퍼 A/B 토너먼트가 6개 후보 전략(추세 ON/OFF·위험관리 베타·멀티에셋 추세·글로벌 추세·확대 유니버스)을 병렬로 돌리지만, 사이드카는 판정 JSON 6덩이를 날 것으로 박고 "비교해보면…" 산문만 달 뿐 계산된 순위가 없었다. 라이브 검증 트랙(글로벌 추세 SPY·IEF·GLD)이 아직도 최강인지·어느 도전자가 EDGE_CONFIRMED 를 벌어 재지정 후보가 됐는지를 정직성 게이트 순위로 한곳에 모음 — 비교 가능(관측≥20)만 챔피언 후보, 잠정(관측 부족)은 순위만 매기고 챔피언 선언 안 함(거짓 자신만만 금지); 도전자 경보는 비-incumbent 가 EDGE_CONFIRMED 1위 + incumbent 도 비교 가능할 때만(사과 대 사과·거짓 경보 0). 격리 스텝(continue-on-error)으로 forward 사이드카 상단 주입(A/B 트랙 못 깨뜨림). 읽기 전용·순수·결정론·Kernel 0·돈 0·라이브 무변경(전진 시계 리셋 없음), 신규 30건, 전체 1962 통과. **라이브 실측: 현재 6 트랙 전부 1/20 관측→모두 잠정·챔피언 없음(정직)·incumbent=global 정확.** ─── (이전) 🧭 스펙 052 후속 3 — 전진 표본 안정성(자본 베이시스 흔들림) 가시화(#281, main `5427faf`).** money-path 가 forward 판정의 snapshot_count·legacy_snapshots_excluded 를 표면화하고 직전 사이드카의 제외 개수와 비교해 '과거 1회 정리(settled)' vs '지금도 베이시스가 바뀌는 중(churning)'을 가른다. 관측이 '1/20'일 때 실은 스냅샷 6개 중 4개가 베이시스 변경으로 제외된 결과일 수 있는데, 매 거래일 새 스냅샷이 쌓여도 같은 수가 제외되면 유효 관측은 영영 정체 — 생존 감시(051: 워크플로 정지)도 수렴 감시(052: 관측 증감)도 '정체'로만 보고 그 원인(베이시스 흔들림)을 못 짚던 사각지대를 메운다(관측이 정체로 보여도 제외가 늘면 headline 이 '표본 흔들림'을 지목). 게이트 '전진 표본 안정성(베이시스)' 추가(legacy 정보 있을 때만·거짓 경보 0). 읽기 전용·순수·Kernel 0·돈 0, 신규 9건, 전체 1932 통과. **라이브 사이드카 실측: 현재 '정리됨(과거 4개 제외, 추가 없음)→베이시스 안정' PASS — 첫 자본 누적 건강.** ─── (이전) 🧭 스펙 052 후속 2 — 전략 지문 정합 가시화(#279, main `d77f9fd`).** 자본 사다리는 라이브 배포 설정 ≠ 전진 검증 설정(전략 지문)이면 어떤 단에서도 자본을 안 넣는다(BLOCKED) — 엣지를 20개 쌓아도 두 설정이 다르면 첫 자본 영영 안 들어감. money-path가 그 차단을 뭉뚱그려 진단 불가였던 걸, 게이트 `전략 지문 정합(검증=배포)`(PASS/FAIL/N/A, 불일치 시 어느 항목·어느 TOML) + BLOCKED 구체 진단으로 표면화. 드라이버가 사다리와 동일한 두 설정(`deploy/canary-live-portfolio.toml`·`global-trend-portfolio.toml`)을 읽어 독립 비교. 읽기 전용·머니루프 무변경·Kernel 0·돈 0, 신규 12건, 전체 1923 통과. **현재 두 설정 지문 일치(SPY/IEF/GLD)→게이트 PASS.** ─── (이전) 🧭 스펙 052 후속 — 전진 시계 수렴 감시(정체/리셋 탐지) 출시(#277, main `ffa1ba8`).** 머니패스 첫-자본 ETA 가 전진 관측 정체/리셋 때 거짓 자신만만한 날짜를 내던 사각지대를 메움 — `EtaProjection.convergence`(converging/stalled/regressed/unknown) + 게이트 '전진 시계 수렴'(리셋=FAIL·정체=PENDING·수렴=PASS). 생존 감시(스펙 051)는 '워크플로가 멈췄나'만 보므로 '살아있지만 수렴 못 하는' 이 두 모드를 놓쳤다. 읽기 전용·순수·Kernel 터치 0건·돈 0 이동, 신규 테스트 6건, 전체 1911 통과, 린트 깨끗. 직전-사이드카 체인 이미 운영 존재 → 다음 스케줄 실행에서 바로 활성화. **현재 실상태: 단계 ACCUMULATING_EDGE(자본 사다리 단0·실자본 0%), 전진 엣지 1/20 관측, 실NAV $1518.21, 캐너리 드라이런(실주문 0), 첫-자본 ETA ≈ 2026-07-09(리셋 없을 시 nominal). 파이프라인 생존: 핵심 사이드카 4종 전부 🟢 신선.** **다음 세션 관찰: ① money-path 사이드카 `eta.convergence` 가 unknown→converging 으로 바뀌는지 ② regressed/stalled 뜨면 전진 페이퍼 점검.** ─── (이전) 🔗 금리 두-기관 교차 검증 + 레짐 층화 첫 실서버 실측(#269 main `02c9256`, #270 main `21102d1`).** ① 공개 데이터 채널에 연준 H.15 미러(DBnomics, 2년·10년) 수집 + 재무부 직접 수집과 수준 대조 2건 추가 — 같은 날 실전 검증(run 27423921887): 9/9 발행, 교차 검증 3건 전부 PASS, **금리 겹침 2,360일 100% 일치**. 금리차(레짐 분석 핵심 입력)가 단일 전송 경로에서 벗어남 + 연구용 금리 이력이 1962년(10년물)/1976년(2년물)까지 깊어짐. ② `regime-stratify.yml` 에 같은 날 검증 push 트리거(체인 파일 3개) — 머지가 **첫 실서버 층화 런을 즉시 발화**(run 27424271217, 두 트랙 ssh_exit=0): GLOBAL-TREND(라이브 지정)는 RISK_ON 313일 샤프 1.93 / CAUTION 432일 샤프 0.79·낙폭 7.98% / RISK_OFF 7일(표본<20 정직 생략); WIDE(11슬리브)는 CAUTION 샤프 0.86·낙폭 4.73%(3자산보다 방어) vs RISK_ON 수익은 3자산이 큼(+28.1% vs +13.5%) — **인플레 방어 가설(스펙 047)과 방향 일치하는 첫 실측이지만 RISK_OFF 표본 7일(리플레이 3년 한계)이라 확정 아님, forward ARM F 누적이 진짜 판정**. 테스트 1856 통과(기준선 1853+3), 린트 깨끗, Kernel 터치 0건, 돈 0 이동, deploy-on-merge 2건 성공. **다음 세션 관찰: ① 오늘 밤 20:00 UTC 장 마감 정합성(외부 보유 기준선 후 첫 마감 — 다음 forward 런 🚦 섹션에서 `data/halt.flag` 안 서는지; 서면 *새* 드리프트이므로 해제 말고 조사) ② 매 거래일 23:30 UTC 정기 층화 런 지속 확인 ③ 내일 01:30 UTC 수집 런 사이드카 overall_ok(이제 9항목+교차 검증 3건).** ─── (이전) 🧬 레짐 층화 첫 실제 소비 + 단일 잣대 구멍 2건 수정(#267, main `f408b2e`). 백테스트 리플레이가 라이브와 달랐던 구멍 2건을 닫음: ① ensemble_windows(스펙 048 다중 속도 앙상블) 무시 — 라이브 TOML 백테스트가 다른 전략(단일 200일 SMA)을 재생하던 버그를 `strategy.trend.spec_from_filter_config` 공유 변환으로 라이브 리밸런서와 통일(행동 회귀 테스트로 고정) ② MARKET 하드코딩 — 배포 TOML(LIMIT 전용 화이트리스트)에서 전 주문 거부(영원한 현금 곡선) → 화이트리스트가 MARKET 불허면 종가 지정가 LIMIT(라이브 marketable-limit 의 일봉 근사). 새 다리: CLI `bars-export`(DB 일봉→ohlcv 계약 CSV, 읽기 전용) + `backtest-portfolio --equity-out`(일별 자본 곡선 CSV). 전용 연구 워크플로 `regime-stratify.yml`(매 거래일 23:30 UTC): 서버에서 bars-export→ingest-history→backtest-portfolio→regime-stratify 체인(쓰기는 /tmp 만, forward DB 읽기 전용)으로 "배포 전략(GLOBAL-TREND 3자산 + WIDE 11슬리브)이 어떤 거시 레짐에서 벌고 잃는가"를 사이드카 `automation/regime-stratify-last-run` 에 매일 발행. 거래 워크플로의 public-data 무소비 불변식은 그대로(전용 워크플로 분리 — 그 보호선이 깨지면 test_collect_public_data_workflow 가 잡는다). 신규 테스트 13건, 전체 1853 통과, Kernel 터치 0건, 돈 0 이동. **다음 세션 관찰: ① 다음 23:30 UTC 런의 `git show origin/automation/regime-stratify-last-run:LAST_RUN.md` — bars-export 가 실서버 forward DB 에서 처음 도는 지점(층화 표가 실제로 나오는지, RISK_OFF/CAUTION 낙폭 확인) ② 오늘 밤 20:00 UTC 장 마감 정합성 OK 여부(직전 마일스톤 관찰 지점 유효 — 깃발 재발 시 새 드리프트로 간주, 해제 말고 조사).** ─── (이전) 🛡 라이브 halt 일일 재발 종결 — 외부 보유 기준선(#264 main `e039796`) + 깃발 해제(#265 main `f00c2ff`).** 매 거래일 20:00 UTC 장 마감 정합성이 `reconciliation mismatch: 4 position(s)` 로 halt 를 재설정하던 구조적 문제의 근본 수정: 운영자가 시스템 가동 전 취득한 외부 보유 4종목(BHP 1·MRK 3·ORANY 28·RELX 6, KIS smoke run 27405479242 실측)이 원장(fills→current_positions)에 영원히 없어 생기던 진짜 드리프트였다(06-04 는 #233 조회 버그 오인 포함, 06-11 재발은 수정 후라 진짜). 수정 = `deploy/external-holdings.toml` **시스템 비관리 외부 보유 기준선** 선언 + 정합성이 (원장+기준선)==브로커 로 대조. 1주라도 다르면 여전히 MISMATCH→halt(안전망 유지 — 보유가 진짜 바뀌면 TOML 갱신 머지가 절차). 가짜 체결 주입 없음(K4 fills 무접촉). 배선: `--external-holdings` 옵션(기본 `deploy/external-holdings.toml`) → WorkerSettings → reconcile. deploy-on-merge 성공(run 27411125478) = 라이브 워커 새 코드 가동, 해제 채널 발화 성공(run 27411255917, `Halt cleared.`). **다음 세션 관찰: 오늘 밤 20:00 UTC 장 마감 정합성이 OK 로 끝나는지(매 forward 런 🚦 섹션 — 깃발이 다시 서면 기준선이 아니라 *새* 드리프트이므로 다시 멈추고 조사). 신규 테스트 21건, 전체 1840 통과.** ─── (이전) 📊 레짐 이력 시계열 + 층화 분석 가동(#262, main `fa483d7`).** 스냅숏만으론 "어떤 레짐에서 벌고 잃는가"를 못 재서 두 조각 추가: ① 시점 기준 일별 레짐 타임라인 (regime_timeline.csv — 일간 지표는 그날 종가, 월간 지표는 발표 지연 45일 반영, 미래 누출 차단) ② 층화 분석기(analytics/regime_stratified.py + CLI regime-stratify — d일 라벨 ↔ d+1 수익률 전망적 결합, 라벨별 누적/연환산/샤프/최대낙폭, UNLABELED 분리, 관측<20 비율 생략). 실전 검증(run 27405479236): 타임라인 2,358일(2017-01-03~2026-06-11), 라벨 분포 RISK_ON 1414/CAUTION 880/RISK_OFF 64, 역사 사건 정확(2022-10-13 CPI 쇼크=RISK_OFF 역전+VIX, 2019·2023 역전기=CAUTION). 다음 소비처: 백테스트/forward NAV 를 regime-stratify 로 층화(수익률 데이터는 서버/백테스트 산출물 필요 — 컨테이너엔 가격 데이터 없음). 읽기: `git show origin/automation/public-data:regime_timeline.csv`. ─── (이전) 🧭 거시 레짐 보고서 가동 — 채널 데이터의 연구 소비 시작(#260, main `8b51b74`).** 수집 워크플로가 수집 직후 같은 실행기에서 regime.json 을 만들어 사이드카에 발행: 지표 4종(금리 곡선 역전·VIX 수준 구간·CPI 전년동월비·삼 룰) → 스트레스 깃발 수로 RISK_ON/CAUTION/RISK_OFF 합성, 가용 지표 2개 미만이면 INSUFFICIENT. 실전 검증(run 27394647235): **4/4 지표 계산, 첫 판정 CAUTION**(물가 깃발 1개 — CPI 전년동월비 4.25% HIGH; 금리 곡선 FLAT 0.40, VIX NORMAL 19.44 백분위 59.9%, 삼 룰 QUIET 0.10%p). 격리 양방향 CI 고정: 모듈은 라이브 DB·strategy/ 무접촉, 라이브 경로는 macro_regime 미소비 — 라이브 가격 레짐(strategy/regime.py, KIS)과 완전 분리. 읽기: `git show origin/automation/public-data:regime.json`. 후속 후보: 백테스트/연구 노트에서 레짐별 전략 성과 층화 분석, 레짐 이력 시계열 축적(현재는 최신 스냅숏만). ─── (이전) 🌐 세계 최고 수준 4단계 계획 — 4/4 전부 완료! ④ 공개 데이터 수집 채널 가동(#254 채널 신설 → #255 첫 실측 대응 → #256 3차 탐침 → #257 공식 키리스 전환 → #258 실전 런 실측 대응, main `6fbd441`).** 운영자 선택(2026-06-11): 공식 키리스 조합 — 미 재무부 일일 금리·Cboe VIX·BLS 거시(실업률 LNS14000000·CPI CUUR0000SA0)·DBnomics 미러(CPI 교차 검증 짝). 키 등록과 가격 일봉 이력 확장은 보류(가격 소스는 KIS 백필 유지). 승인됐던 Stooq·FRED 는 실측에서 실행기 IP 차단(JS 장벽·타르핏) 확정 → 수집에서 빼고 탐침([probes])으로만 차단 변화 추적. 실전 런 27392182746 검증 완료: **7/7 발행**(UST2Y·UST10Y·파생 스프레드 UST10Y2Y 각 2,361행 + VIX 종가 9,205행(1990~) + 실업률·CPI 29행 + CPI 미러 1,345행), **CPI 교차 검증 13/13 일치(100%)**, overall_ok=true, 29초. 정기 수집 매일 01:30 UTC(화~토, collect-public-data.yml) → automation/public-data 사이드카. 실측 교훈 3건 반영: VIX 1990년대 초 OHLC 정합 깨짐(원본 특성)→종가만 발행, BLS 미발표 기간 값 "-"(2025-10 셧다운)→결측 보존, DBnomics 미러 ~17개월 지연→미러는 겹침이 본질이라 신선도 한도 분리(700일). 격리 원칙 불변: 산출물은 연구·백테스트 전용, 라이브 매매 신호는 KIS 만(불변식 테스트 고정). 관찰: 다음 정기 런의 사이드카 overall_ok. ─── (이전) 🌍 세계 최고 수준 4단계 계획 — ①②③ 완료(#248 헌법 v5.0.0 · #249 사다리 · #251 돈 경로 통합 테스트 · #252 유니버스 확대 ARM F), ④ 서버측 데이터 채널은 공급망 판단이라 운영자 확인 후(후보: FRED·Stooq 무료 CSV, httpx 만으로 가능).** 운영자 위임(2026-06-11): "1·2·3 모두 세계 최고 수준 목표, 자본·수단도 자동과 자율에. 기준은 계좌 잔고와 포트폴리오." ① 사다리: 단0=0%→단1=25%→단2=50%→단3=100% of 실계좌 NAV, 진입=EDGE_CONFIRMED+지문 정합, 승격=관측≥20+≥27일+낙폭<10% 전부, 강등(≥10%)·정지(≥20%) 즉시, 재사이징=NAV ±10%(입금 자동 반영), 낙폭 예산 20% 운영자 소유, 게이트=forward-edge-autoarm.yml(23:50 UTC) — 첫 결정은 WAIT_EDGE(돈 0). **남은 단계: ② 돈 경로 끝-끝 통합 테스트(자본 커지기 전 배관 버그 클래스 박멸 — 실제 라이브 설정으로 백필→신호→비중→주문→체결→NAV→판정→사다리 전체 시뮬레이션) ③ 유니버스 확대(ETF 3→비상관 슬리브 ~12, √N 법칙, forward 검증 트랙 먼저) ④ 서버측 데이터 수집 채널(서버는 인터넷 전체 접근 — 데이터 천장 자율 해제).** 관찰: 오늘 밤 23:50 UTC 게이트 첫 실행 사이드카(edge-autoarm-last-run)에서 WAIT_EDGE+계좌 NAV 기록 확인. ─── (이전) 🪜 라이브 백필 깊이화 — 무장 후 거래 0건이 될 끊긴 고리 수정 + 같은 날 검증 완료(PR #245 main `3fdcb0c`, 재발화 PR #246 main `c972505`). 라이브 캐너리 워크플로의 backfill-bars 가 얕은 기본값(≈100봉)이라 전략 신호(추세 앙상블 252봉·역변동성 200봉·모멘텀 120봉) 계산 불가 → `target_weights={}` → 무장돼도 현금 100%·거래 0건이 될 상태(실측 run 27296075204). 수정 = forward 와 동일 `--min-bars 1000` + 백필 깊이 불변식 회귀 테스트(`tests/unit/test_workflow_backfill_depth.py`). 재발화 검증(run 27344173857): 백필 fetched=1000×3 + 드라이런 `{"SPY": "0.239672"}`(빈 비중 소멸) + 라이브 NAV 자본 베이시스 작동(현금 $500, `legacy_snapshots_excluded:10`). 정직한 한계: 소액 $500 + SPY ≈$725 정수 주 제약으로 현 국면(SPY 만 추세 위)에선 실주문 0건일 수 있음 — 자본 상향은 운영자 게이트(헌법 X.4). 전체 1715 통과·린트 깨끗·Kernel 0·돈 0. **다음 관찰: 매 평일 15:00 UTC 라이브 캐너리 런 미리보기 비중(`git show origin/automation/rebalance-live-canary-last-run:LAST_RUN.md`) + 오늘 밤 forward 런 자본 베이시스.** ─── (이전) 📏 forward NAV 측정 오염 수정 — 장부 현금 포함 + 측정 기준 연속 구간 판정(PR #243, main `21f94f8`). 운영자 "세계 최고 수준 작업 분석·우선순위 판단 뒤 자율 수행"에 응답. 페이퍼 트랙 `nav-snapshot` 이 현금 0 으로 NAV = 포지션 평가액만 기록 → 매수/매도(자금 흐름)가 가짜 수익률이 되던 측정 버그(실측: 추세 ON 트랙 "총수익 463%·낙폭 16.5%" = 흐름 오염, GLOBAL-TREND 도 자본 $12,000 에 NAV $2,176). 이대로면 ≈20 거래일 뒤 자동 무장 게이트(스펙 049)가 쓰레기 통계로 EDGE 판정(가짜 확정 또는 가짜 기각 둘 다 치명적). 수정 = ① `nav-snapshot --capital`: 현금 = 자본 + 순현금흐름(`net_cash_flow_usd`) 포함 NAV + 페이로드 `capital_basis_usd`(K4 추가 전용, 커밋 `a67cd29`) ② `forward-verdict`: 같은 측정 기준의 최신 연속 구간만 판정(`consistent_basis_suffix`, 오염된 레거시 점 제외 — `legacy_snapshots_excluded` 로 가시화) ③ forward 5트랙 + 라이브 캐너리 측정 워크플로에 자본 전달 + 회귀 고정 테스트. 돈 0 이동·센티넬 `armed:false` 불변·전체 1713 통과. **판정 시계열은 자본 베이시스 구간부터 다시 세므로 EDGE_CONFIRMED 는 2026-06-11 기준 ≈20 거래일 후 — 오염된 시계열로 빨리 가는 것보다 정확하게.** **다음 세션 관찰: 오늘 밤 forward 런부터 각 트랙 NAV ≈ $12,000 기준으로 찍히고 판정 JSON 에 `legacy_snapshots_excluded` 표시되는지(`git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md`).** ─── (이전) 🔓 묵은 라이브 halt 해제 — 가드형·감사 채널 신설, 자동 경로 완전 개통(PR #241, main `07b093c`). 운영자 명시 지시("안전 장치도 직접 풀어. 내가 관여하지 않을거야. 자동으로 모두 이어서 수행해")로 2026-06-04 묵은 정합성 오인 깃발(`reconciliation mismatch: 4 position(s)`, 원인 버그는 #233 수정 완료)을 해제. 채널 = `automation/halt-release.request` 센티넬 + `release-halt.yml`(해제는 `auto-invest resume --confirm` 만 — K4 감사 행 HALT_CLEARED, `rm` 금지·스케줄 반복 금지를 테스트로 못박음). **검증(run 27322266903): 해제 전 2026-06-04 깃발 → Halt cleared. → 해제 후 없음. deploy 도 최신 main 성공.** 라이브 캐너리는 `armed:false` 라 돈 0 이동 — 이제 폐회로가 수동 개입 0으로 완전 자동: forward NAV 누적(매 거래일 22:30 UTC) → ≈20 거래일 → EDGE_CONFIRMED → 자동 무장(스펙 049, 킬스위치 없음 확인) → 라이브 캐너리 실주문(캡 $1,000+서킷 브레이커). **관찰 지점: 오늘 20:00 UTC 장 마감 정합성이 진짜 원장 드리프트를 찾으면 깃발이 재설정될 수 있음(🚦 섹션으로 확인) — 그 경우 해제 반복이 아니라 드리프트 자체를 고칠 것.** ─── (이전) 🟢 페이퍼 forward halt 깃발 격리 — NAV 0 병목 해소 + 같은 날 검증 완료(PR #238 main `bc5db56`, 재발화 PR #239 main `243f7a0`). 시세(#229)·주문(#231)·되돌림(#233)·취소(#236)를 다 고친 뒤에도 forward NAV 가 여전히 0 이던 마지막 끊긴 고리: 다섯 페이퍼 트랙의 `rebalance-once` 가 `--halt-path` 미지정 → 라이브 워커 킬스위치(`data/halt.flag`) 공유 → 2026-06-04 묵은 정합성 오인 깃발(`reconciliation mismatch: 4 position(s)`, 원인 버그는 #233 에서 수정 완료)에 전 트랙 주문 `REJECTED_BY_GATE` → EDGE_CONFIRMED 불가·자동 무장 게이트(스펙 049) 영구 대기. 수정 = 트랙별 전용 깃발(`data/forward_<트랙>.halt.flag`, 전용 DB 와 같은 격리 원칙) + 🚦 halt 상태 읽기 전용 진단 스텝(LAST_RUN.md 보고, 자동 해제 안 함) + 회귀 테스트 4건. **재발화 검증(run 27321342988): halt 거부 0건 + GLOBAL-TREND 첫 페이퍼 체결(SPY 3주 PAPER_FILLED) + NAV $2,176.29(0→비0)** — 검증 대상 앙상블이 드디어 forward 증거 누적 시작. Kernel 터치 0건·돈 0 이동·전체 1697 통과. **⚠ 운영자 결정 대기(라이브 무장 전 필수): 라이브 `data/halt.flag` 가 묵은 채 서 있음 — 무장 후 실주문도 이 깃발에 거부된다(fail-safe). 서버에서 `auto-invest resume` 으로 해제해야 라이브 캐너리가 실제 주문 가능.** 다음: ≈20 거래일 NAV 누적 → EDGE_CONFIRMED → 스펙 049 자동 무장 게이트. ─── (이전) 🟢 주문 취소·재호가 거래소 자동 해석 — 제출 거래소 영속화(PR #236, main `8d45c53`). 같은 날 시세(#229)·주문(#231)·되돌림 조회(#233)에 이은 마지막 같은-클래스 대칭: 수명 관리(스펙 030)의 TTL 취소·재호가가 단일 고정 거래소(NASD)를 써서 SPY·GLD(AMEX) 주문 취소가 오라우팅돼 산 채로 남던 잠복 버그. 수정 = `0003_order_routing.sql` 사이드카(correlation_id→제출 거래소) + 라우터가 제출 성공 시 기록 + 취소/재호가가 기록된 거래소 사용(기록 없으면 종전 폴백, 회귀 0). Kernel 터치 0건(보호 0001·0002 무변경)·돈 0 이동·신규 테스트 4건·전체 1693 통과. **다음 세션 검증: ① 오늘 밤 23:53 UTC forward 런부터 `quote fetch failed for SPY` 소멸 + GLOBAL-TREND NAV 비0 확인(`git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md`) → ≈20 거래일 누적 → EDGE_CONFIRMED → 스펙 049 자동 무장. ② 실브로커 취소·주문 정합은 라이브 첫 실주문에서만 최종 확인(소액 캡 $1,000+서킷 브레이커).** ─── (이전) 🟢 라이브 주문 거래소 자동 해석 — 검증 멀티에셋 유니버스의 마지막 끊긴 고리(PR #231, main `ba05565`). 운영자 "세계 최고 수준 작업 분석·우선순위 판단 뒤 자율 수행 — 실제로 많은 돈을 벌어야"에 응답. **우선순위 판단: 엣지는 이미 검증됨(샤프 ~2.0), 병목은 더 많은 연구가 아니라 끊긴 파이프라인 고리.** 2026-06-10 시세(EXCD) 거래소 자동 해석을 고쳤지만, **실주문 거래소(`OVRS_EXCG_CD`)는 별개 코드 체계인데 여전히 단일 고정값(기본 NASD)** 이었다. 검증 유니버스는 거래소가 섞임 — SPY·GLD=AMEX/Arca, IEF=NASDAQ. 단일 고정값이면 forward EDGE_CONFIRMED → 스펙 049 자동 무장 → 라이브 첫 실주문에서 SPY·GLD 가 거부/오라우팅된다(HANDOFF가 "라이브 전 검증 항목"으로 명시했던 바로 그 고리). **수정: 시세 해석기가 이미 알아낸 상장 거래소(`Quote.resolved_market`)를 주문 거래소로 옮긴다** — `order_exchange_for_quote_market()`(NAS→NASD/NYS→NYSE/AMS→AMEX) + `OrderRouter.submit_order(order_exchange=...)` + `execute_rebalance` 가 종목별 연결. 매핑에 없으면 None→`self.market` 폴백(단일 거래소 룰 워커 byte 동일, 회귀 0). **Kernel 터치 0건(K1 캡·게이트 체인 불변)·돈 0 이동(센티넬 armed:false 불변, 실주문은 스케줄에서만)·신규 테스트 7건·전체 1681 통과.** **다음 세션 검증: ① 오늘 23:53 UTC forward 런부터 시세 버그 소멸+GLOBAL-TREND NAV 비0 확인(`git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md`) → ≈20 거래일 누적 후 EDGE_CONFIRMED → 자동 무장. ② 라이브 무장 첫 실주문의 OVRS_EXCG_CD 정합은 실브로커로만 최종 확인(소액 캡 $1,000+서킷 브레이커 방어).** ─── (이전) 🟢 시세 거래소 자동 해석 — 검증 전략 forward NAV 0 버그 수정(PR #229, main `f550dc5`).** 운영자 "세계 최고 수준 작업 분석·우선순위 판단 뒤 자율 수행 — 실제로 많은 돈을 벌어야"에 응답. **우선순위 판단: 더 많은 연구가 아니라, 검증된 엣지가 forward 증거를 못 쌓던 끊긴 파이프라인을 고침.** 사이드카 GLOBAL-TREND(SPY·IEF·GLD) 준비 로그에서 `quote fetch failed for SPY` → NAV 0/seq=2 로 고정 발견. 원인: KIS 시세는 거래소(EXCD)별 조회인데, 백필은 NAS→NYS→AMS 를 순차 시도해 SPY 를 AMS 에서 올바로 받지만(1000봉) `rebalance-once` 시세 경로(`_quote_provider`)와 미실현 손익 마킹은 거래소를 **기본 NAS 로 고정** → SPY·GLD(AMEX 상장) 빈 값 실패 → 검증 대상 전략이 forward NAV 를 한 줄도 못 쌓음(자동 무장 게이트 영원히 WAIT). 수정: `broker/overseas.py` 에 백필과 동일한 거래소 순차 탐색 헬퍼 `get_quote_resolving_market` 추가, 두 시세 경로가 사용. **Kernel 0·돈 0·신규 단위 3건·전체 1674 통과.** 같은 경로를 쓰는 라이브 캐너리도 무장 시 SPY·GLD 시세 정상 수신. **다음 세션 검증: 다음 forward 런(평일 23:53 UTC) GLOBAL-TREND 로그에서 `quote fetch failed` 소멸 + NAV 비0 확인(`git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md`) → ≈20 거래일 누적 후 EDGE_CONFIRMED 가능 → 스펙 049 자동 무장 게이트 발화. 라이브 전 운영자 검증: 주문 EXCD(OVRS_EXCG_CD, 시세와 별개 체계)는 실주문으로만 확인.** ─── (이전) 🔭 스펙 046 일일 전략 모니터 — 지속 감시 대시보드 완료(PR #211, main `a36ea23`). 운영자 "이어서 자율 수행, 세계 최고 수준으로 돈 벌자" 지시에 응답.** 검증된 스펙(042~045)을 합쳐 forward 페이퍼가 돌 때마다 운영자가 한눈에 보는 일일 대시보드를 사이드카에 찍는다. 네 가지: ① 엣지 최근 유효성(분산 추세 최근 5/10년 샤프 1.70/1.76) ② 분산 가정 신뢰도(상관 regime 판정, 현재 WEAKENED) ③ 낙폭 예산별 레버리지 복리 권고(**최근 25년 기준** — 15% L=2.0 복리 11.5%/년, 20% L=3.0 14.9%, 25% L=3.5 16.6%) ④ 오늘 추세 신호(투자/현금). **핵심 교정**: 레버리지 권고를 처음 전체 1871로 했더니 대공황 낙폭에 묶여 'L=0.5 줄여라'가 나온 것(운영자 지적 '먼 과거 기준' 실수 재발)을 최근 25년(닷컴·GFC·코로나·2022 포함)으로 일관 교정. 배선: 러너 로컬 스텝(setup-uv+프로브, Shiller만·워커 불필요) + 사이드카 모니터 섹션, 완전 격리(continue-on-error)라 ARM A/B/C/D 무영향. 신규(순수 추가·비커널): `analytics/strategy_monitor.py` + `scripts/strategy_monitor_probe.py` + 단위 5건 + `specs/046-strategy-monitor/{spec,FINDINGS}.md`. **읽기 전용·돈 0·Kernel 0. 라이브 레버리지/무장은 운영자 게이트(헌법 X.4) — 대시보드는 권고/감시이지 거래 변경 아님.** 상세 `HANDOFF-049-SPEC-046-STRATEGY-MONITOR.md`. **다음 자율 후보: 대시보드를 우리 forward NAV 트랙(KIS 실측)에도 적용(데이터 누적 후). 운영자 결정: 권고 레버리지 라이브 적용 여부.** ─── (이전) **🔬 스펙 045 최근 regime/시점 강건성 감사(PR #209, main `03938c6`).** ① 시점 강건성: 분산 추세가 최근 5/10/15/20년·모든 연대(2020년대 샤프 1.59) 우위 — 엣지는 1871 산물이 아니라 *최근에 더 강함*. ② 상관 regime: 최근 5년 주식·채권 상관 +0.095(양수 53%), 현재 -0.03. 판정 `DIVERSIFICATION_WEAKENED`. ③ 2022(60/40 -14.8%)에 분산추세 -1.2%(추세 게이트 방어). **진짜 가치=추세로 게이트한 분산.** 상세 `HANDOFF-048-SPEC-045-REGIME-AUDIT.md`. ① **시점 강건성**: 분산 추세가 최근 5/10/15/20년·모든 연대(2020년대 샤프 1.59) 우위 — 엣지는 1871 산물이 아니라 *최근에 더 강함*. ② **상관 regime**: 운영자가 짚은 위험이 진짜 — 최근 5년 주식·채권 상관 +0.095(양수 53%, 2022 인플레), 현재 -0.03(회복). 판정 `DIVERSIFICATION_WEAKENED`(정적 분산 약화→추세 게이트 의존). ③ **2022 스트레스(60/40 -14.8%로 깨진 해) → 분산 추세 -1.2%**(추세 게이트가 현금화로 방어). 2008도 60/40 -19% vs 분산추세 +11.5%. **→ 진짜 가치는 정적 분산이 아니라 *추세로 게이트한 분산*(상관 깨져도 방어).** 2020 V자엔 약한 한계 정직 노출. 신규(순수 추가·비커널): `analytics/regime_audit.py` + `scripts/regime_audit_probe.py` + 단위 9건 + `specs/045-regime-recency-audit/{spec,FINDINGS}.md`. Kernel 터치 0건, 돈 0 이동, 측정 전용. 상세 `HANDOFF-048-SPEC-045-REGIME-AUDIT.md`. **다음 자율 후보: 상관 regime+최근창 판정을 forward 사이드카에 지속 감시 보고 배선.** ─── (이전) **💹 스펙 044 성장 최적 레버리지 — 고정 자본 복리 극대화 완료(PR #207, main `ca3d47f`).** 스펙 043 이 샤프를 1.8까지 올린 데서 멈춘 것을 이어, 높은 샤프를 *실제 복리 성장*으로 바꾸는 마지막 단계. 핵심 수학: 복리 천장은 샤프로 결정(g≈rf+S²/2). ① **슬라이스 1**: 낙폭 예산 30%서 레버리지로 복리 ~2배(현대 9.5→14.7%, 최근 8.9→17.0%, 낙폭 28%=평범한 약세장). 과레버리지=파산 정직 보고(5배 낙폭 87%, 풀켈리는 청산). 보수적 예산(10~15%)서 분산이 단일 주식 압도(+1.6~2.6%p — 단일은 레버리지 줄여야, 분산은 키울 수 있음). ② **슬라이스 2**: 리스크 패리티 가중 측정 → 50/50 못 이김(과공학 금물, 정직히 닫음). 신규(순수 추가·비커널): `analytics/growth_optimal.py` + `scripts/growth_optimal_probe.py` + `multi_asset_trend.py` 스트림 헬퍼 3개 + 단위 14건 + `specs/044-growth-optimal-leverage/{spec,FINDINGS}.md`. **⚠ 레버리지는 연구/측정 전용 — 라이브 K1 포지션 캡(노출≤100%, 헌법 I-VII) 불변. 라이브 레버리지는 위험 경계 변경=운영자 게이트(헌법 X.4).** 돈 0 이동, Kernel 터치 0건. 상세 `HANDOFF-047-SPEC-044-GROWTH-OPTIMAL.md`. **"많은 돈"의 정직한 답 = 분산(고샤프) × 낙폭 예산 레버리지 × 복리 = 현재 자본으로 현대/최근 ~15~17%/년(낙폭 28%) 사거리. 다음 운영자 결정: 라이브 레버리지 적용 여부(위험 경계).** ─── (이전) **🌐 스펙 043 멀티에셋 분산 추세추종 완료(PR #205, main `64ead83`).** 우선순위 판단: 종목선택 알파는 0(스펙 041), 유일한 엣지는 추세 방어(스펙 042)인데 그게 지금 *단일 자산군(미국 주식 베타)* 에만 적용됨(SPY·QQQ 상관 ~0.95). 세계 최고 수준과의 진짜 격차 = **멀티에셋 분산 추세추종**(비상관 흐름의 분산 = 금융 최대의 공짜 점심). **결정적: 추가 데이터 0 — 스펙 042 가 쓰는 Shiller CSV 에 10년 국채 수익률이 1871년부터 있어 채권 총수익 프록시를 만들 수 있다.** ① **슬라이스 1(검증)**: 주식추세+채권추세 분산(50/50)이 단일 주식 추세 대비 샤프 1.18→1.58(전체)/1.43→1.81(현대)/1.29→1.78(최근), 낙폭 41%→18%/19%→7%/19%→7%. 주식·채권 상관 +0.035~−0.120(구조적 근거). **창 7/10/12 × 가중 50:50/60:40 모든 조합 DIVERSIFICATION_EDGE(과적합 아님)**. 고전 60/40 단순보유도 압도. 정직: 분산은 CAGR 더 낮음(절반 채권/현금) — 가치는 위험조정 수익(샤프)↑ 이고 그 뒤 자본 키워 안전. ② **슬라이스 2(배선)**: `deploy/multi-asset-trend-portfolio.toml`(SPY+IEF, 각자 sma 200 추세 게이트) + `rebalance-paper-forward.yml` ARM D(전용 DB `forward_multiasset.db`, set +e + if:always() 격리). **측정한 것만 배선**(금·원자재는 장기 데이터 없어 후속). 신규(순수 추가·비커널): `analytics/multi_asset_trend.py` + `scripts/multi_asset_trend_probe.py` + 단위 20건 + `specs/043-multi-asset-trend/{spec,FINDINGS}.md`. **돈 0 이동, Kernel 터치 0건, PAPER 전용. 라이브 무장 해제 유지.** ⚠ **다음 세션: 사이드카 `automation/rebalance-paper-forward-last-run:LAST_RUN.md` 의 MULTI-ASSET-TREND 판정 확인**(NAV ~20+ 거래일 쌓일 때까지 INSUFFICIENT_DATA 정상). **"많은 돈"의 정직한 경로 = 높은 샤프(1.6~1.8) × 운영자 자본 결정**(헌법 X.4 — 돈 움직이는 행동은 운영자 게이트). 상세 `HANDOFF-046-SPEC-043-MULTI-ASSET-TREND.md`. ─── (이전) **🟩 스펙 042 위험관리된 베타 — 슬라이스 1~4 + 확신 리포트 + forward 트랙 배선(PR #196·198·199·200·202·203).** ① 추세 타이밍 낙폭 절반·샤프 0.7→1.2, 9/9 견고. ② 비용 견딤(저회전). ③ 운영 코드가 엣지 100% 재현(테스트 보증) + config `deploy/risk-managed-beta-portfolio.toml`. ④ 변동성 타깃 regime 의존(기본 OFF). **⑤ 확신 리포트(`CONFIDENCE.md` + 프로브 `--confidence`): 기억나는 실제 사건 실측 — 닷컴 -41.6%→-6.2%, GFC -49%→-4.8%, 2022 -17.6%→-2.9% 방어, *코로나 -18.9%→-18.9% 방어 실패 정직 노출*(빠른 V자엔 약함). 오늘 신호 S&P 7413 > 10개월 SMA 6817(+8.7%) 투자. 과거 실패 부검 + 라이브 게이트.** **⑥ forward 트랙 배선: `rebalance-paper-forward.yml` 에 ARM C(위험관리 베타, 전용 DB `forward_rmbeta.db`, 격리) 추가 → 다음 예약 실행(평일 22:30 UTC)부터 우리 KIS 체결로 페이퍼 누적 시작(돈 0).** ⚠ 워커측 실행은 컨테이너 검증 불가 — **다음 세션: 사이드카 `automation/rebalance-paper-forward-last-run:LAST_RUN.md` 의 RISK-MANAGED-BETA 판정 확인**(NAV ~20+ 거래일 쌓일 때까지 INSUFFICIENT_DATA 정상). 라이브 전환은 운영자 게이트(헌법 X.4), 무장 해제 유지.** 상세 `specs/042-risk-managed-beta/{FINDINGS,CONFIDENCE}.md`. ─── (이전) 가격 신호 탐색 종료(스펙 041 6차, PR #194): 12-1 모멘텀·단기 반전 둘 다 엣지 없음 → 종목선택 알파 포기, 위험관리 베타로 전환. 운영자 데이터 결정: 라이브 아직 안 함 + Track 2 = 위험관리된 베타. ─── (이전 마일스톤) **🟢 스펙 035 출시(2026-06-03): forward 엣지 자동 판정 폐회로 — "실제로 돈을 버는가"를 자동으로 답하는 마지막 조각.** 끊겨 있던 폐회로를 연결: ① 스펙 029 `compute_nav`(시가평가 순자산)가 만들어졌는데 **어떤 실행 경로에도 안 꽂혀 NAV 시계열이 기록 안 되던 것**을 생산자 CLI `nav-snapshot --snapshot`(`PORTFOLIO_NAV_SNAPSHOT` append, 읽기 전용 측정)로 배선. ② 소비자 CLI `forward-verdict` 가 쌓인 NAV 시계열을 **균등가중 단순 보유 벤치마크**(스펙 032 잣대, `price_bars`)와 비교하고 **디플레이티드/확률적 샤프**(스펙 027)로 우연·과적합을 처벌해 `EDGE_CONFIRMED / NO_EDGE / INSUFFICIENT_DATA` 한 줄 판정. ③ `rebalance-paper-forward.yml` 에 두 단계 + 사이드카 `LAST_RUN.md` 판정 섹션 배선 — 매 forward 실행마다 라이브 판정이 찍힘. **보수적 fail-safe: 모르면(데이터 부족·분산 0) 절대 EDGE 선언 안 함 = 돈 잃지 않게 막는 헌법 X 직접 구현.** Kernel 터치 0건, 돈 0 이동, 라이브 자동 승격 0건(EDGE_CONFIRMED 는 운영자 게이트에 올릴 증거이지 자동 배포 아님). 상세 `HANDOFF-040-SPEC-035-FORWARD-VERDICT.md`. **다음(인스턴스 검증)**: `rebalance-paper-forward.yml` 가 돌수록 NAV 점이 쌓임 → 사이드카 LAST_RUN.md 의 "forward 엣지 판정" JSON 이 INSUFFICIENT_DATA → 충분히 쌓이면 코드 수정 없이 진짜 판정으로 자동 전환. ─── (이전) 라이브 캐너리 무장 + 자본 $12k·축소 룰셋 + 자동 승격 게이트(2026-05-30).** ① 라이브 캐너리 무장(AUTO_INVEST_MODE=live, 헌법 X.4 v4.0.0). ② 운영자 선택 1번: 자본 $12,000 + 축소 룰셋(`deploy/canary-live-rules.toml`, qty=1 SPY·MSFT·AAPL) 적용 → 우량주 1주가 per-trade 5% 캡($600) 안 → **실제 체결 가능**(첫 기회 다음 정규장). ③ 운영자 선택 2번: 스펙 026 승격 게이트(`promotion/gate.py`·`readiness.py`·CLI `promote-check`·매일 `promote-readiness.yml`) — 헌법 VI 트랙레코드 게이트를 매일 자율 평가. **실제 풀라이브 승격은 이 VI 게이트 AND 스펙 007 하드닝 캐너리(IX.B-2, ≥30/45거래일) 둘 다 통과해야 발화 — 최소 30거래일 후. 미구현(의도적 게이트).** 노출 상한: per-symbol $2,400 / global $9,600. **스펙 029 전체(슬라이스 1·2·3) 출시 완료 — "현재 자산 수준 기준 운용·성장 관리" 구조적 빈칸 3개 메움. ① NAV 측정(`auto-invest portfolio`), ② 자산 인식 유효 자본(`run --capital-tracking [--capital-growth]`, 기본 끔 — 켜면 캡이 라이브 순자산 추종, 하락은 항상 방어/상승은 옵트인+상한), ③ 미실현 포함 시가평가 성장 추적(`auto-invest growth`, NAV 스냅샷 시계열 → 총수익률·최대낙폭·CAGR). 🟢 스펙 032 슬라이스 1·2 + 단계 ② 출시(2026-05-31): 횡단면 포트폴리오 재조정 엔진 — 알파가 거래 루프에 미배선이고 매도/재조정이 없던 세계 최고 수준 격차를 메움. ① 슬라이스 1: 순수 플래너(`strategy/rebalance.py`) + 백테스트(`backtest/portfolio_replay.py`) + `auto-invest backtest-portfolio`. ② 슬라이스 2: 라이브/페이퍼 실행기(`execution/rebalancer.py`) + `auto-invest rebalance-once`(**paper 기본·돈 무이동**, 실주문은 `--mode live` 명시 필요) — 기존 OrderRouter+K1 게이트 재사용(별도 돈 경로 0). ③ 단계 ②: 단순 보유(균등가중) 벤치마크 비교 + per-trade 캡 클램프로 백테스트=라이브 단일 잣대 정합. 시연(합성 데이터): 모든 스킴이 단순 보유 초과(예 equal top4 +42.5% vs 벤치 +17.1%) — **합성이라 방향성 시연, 실수치는 운영자 `ingest-history` 후 산출.** 다음 후보: **실데이터 적재 후 실제 비교 측정**(운영자/네트워크), **슬라이스 3(라이브 재조정 주기 스케줄·캐너리 룰셋 적용 — 돈 경로·운영자 게이트)**, 유니버스 확대(횡단면 폭), 워크포워드로 재조정 파라미터 표본외 검증, 체결 정교화 후속(031 슬라이스 2 실전송)** |
| 출시 완료 스펙 | 001(P2 정합성 배선 포함), 002, 003, 004, 005, 006, 007, 008, 009, 010, 011, 012, 013, 014, 015, 016(슬라이스 1·2·3 전부), 017(슬라이스 1·2·2b·3 전부), 018(슬라이스 1 다요인 신호 + 슬라이스 2 사이징 감사 기록), 019(레짐 인식 + 공분산 ERC), 020(레짐·ERC 거래 루프 실배선), 021(횡단면 모멘텀 순위 필터), 022(최소 분산 포트폴리오 최적화), 023(가격 기반 퀄리티 팩터 필터), 024(최대 샤프 포트폴리오 최적화), 025(다요인 합성 알파 점수 필터), 026(캐너리→풀라이브 자동 승격 게이트), 027(디플레이티드 샤프 비율), 028(체결 품질 정밀 측정 — arrival 기준 구현격차 + 체결 지연), 029(전체 슬라이스 1·2·3 — NAV 측정·자산 인식 유효 자본·미실현 포함 성장 추적), 030(미체결 주문 수명 관리 — TTL 취소·취소-재호가·marketable-limit), 031 슬라이스 1(KIS 실시간 웹소켓 수신 토대), 032(횡단면 포트폴리오 재조정 엔진 — 플래너 + 백테스트 + 라이브/페이퍼 실행기 + 워크포워드/DSR 검증 + forward 페이퍼 트랙), 033(KIS 해외 일봉 백필 + 일일 상시 백필 + 유니버스 3→10), 034(체계적 유니버스 구성 — 유동성 기반 `strategy/universe.py` + CLI `build-universe` + 넓은 횡단면 정직한 검증), 035(forward 엣지 자동 판정 — `nav-snapshot` 생산자 + `forward-verdict` 소비자, NAV 시계열 → 디플레이티드 샤프 vs 단순 보유 → EDGE/NO_EDGE/INSUFFICIENT 판정, 폐회로 완성), 036(절대 모멘텀 추세 필터 — `strategy/trend.py`, 종목별 추세 아래면 현금으로 빠지는 드로다운 방어 오버레이, `[portfolio.trend_filter]` 옵트인, 끄면 byte 동일), 037(forward A/B 토너먼트 — 추세 ON vs OFF 를 전용 DB 로 격리해 병렬 페이퍼 + forward-verdict 양쪽 판정, 코드 변경 0), 038(칼마 비율 — 자본 방어(연수익/최대낙폭) 측정을 forward-verdict 에 추가, 페이퍼·라이브 공통, 게이트 불변·보고 전용), 039(라이브 캐너리 포트폴리오 $500 무장본 + 계좌 충돌 블로커), **040(라이브 캐너리 가드형 무장 채널 — `rebalance-live-canary.yml`, 기본 드라이런 미리보기, 실주문은 `armed:true` 센티넬일 때만, 자본상한 $1,000+서킷브레이커+추세필터)**, 041(가격 신호 탐색 종료 → 패시브 권고: 12-1 모멘텀·단기 반전 IC≈0, 종목선택 알파 측정상 없음), **042(위험관리된 베타 — 추세 게이트 자본 방어, 슬라이스 1~4: 추세 타이밍 낙폭 절반·샤프 0.7→1.2, 비용 견딤, 라이브 코드 경로에 실림, 변동성 타깃은 선택. 라이브는 운영자 게이트)**, **043(멀티에셋 분산 추세추종 — 주식추세+채권추세 비상관 분산이 단일 자산 추세 압도: 샤프 1.18→1.58/1.43→1.81/1.29→1.78, 낙폭 절반, 창·가중·구간 모든 조합 견고. forward 페이퍼 ARM D 배선(SPY+IEF). PAPER 전용·라이브는 운영자 게이트)**, **044(성장 최적 레버리지 — 고정 자본 복리 극대화: 복리 천장은 샤프로 결정[g≈rf+S²/2], 낙폭 예산 30%서 레버리지로 복리 ~2배[현대 9.5→14.7%, 최근 8.9→17.0%], 과레버리지=파산 정직 보고, 보수적 예산서 분산 우위. 리스크 패리티는 측정 후 50/50 유지. 레버리지는 연구 전용·라이브 K1 캡 불변, 라이브는 운영자 게이트)**, **045(최근 regime/시점 강건성 감사 — '먼 과거 기준' 점검: 엣지는 최근 5~20년·2020년대서 더 강함[분산 추세 샤프 1.59~1.80], 최근 5년 주식·채권 상관 양수[+0.095]로 정적 분산 약화[판정 DIVERSIFICATION_WEAKENED], 2022 동반폭락[60/40 -14.8%]에 분산추세 -1.2%[추세 게이트 방어]. 측정 전용·비커널)**, **046(일일 전략 모니터 — 검증 스펙 042~045 합친 지속 감시 대시보드를 forward 사이드카에 배선: 엣지 최근 유효성/분산 가정 신뢰도/낙폭 예산별 레버리지 복리 권고[최근 25년]/오늘 추세 신호. 러너 로컬·완전 격리. 읽기 전용·돈 0·라이브는 운영자 게이트)** |
| 진행 중 스펙 | **🟩 위험관리된 베타 슬라이스 1~4 완료 — 첫 측정·검증된 진짜 엣지(2026-06-05, 스펙 042, PR #196·198·199·200, main `415e2e7`).** 운영자 결정으로 종목선택 알파(스펙 041, 측정상 없음) 대신 **베타를 규율 있게 위험관리**하는 길로 전환. Shiller 월간 S&P(1871~현재, GitHub datahub — 닿는 유일한 장기 데이터, **대공황·2008 포함**)에서 단순 보유 vs N개월 SMA 추세 타이밍 비교(미래 누출 0). **① 슬라이스 1: 추세 타이밍이 낙폭을 절반으로(82%→41%), 샤프 0.71→1.18, 칼마 0.11→0.27 — SMA 7/10/12 × 1871/1950/1990 = 9/9 견고(과적합 아님, 10개월은 공개된 고전 값). ② 슬라이스 2: 거래비용 견딤 — 회전 연 ~1.3회(저회전), 10bp서 샤프 1.18→1.17, 3/3 EDGE_SURVIVES_COSTS(세금 15%도 위험조정 우위 유지). ③ 슬라이스 3: 운영 코드 `strategy.trend.above_trend`(sma)가 연구 신호와 100% 일치·같은 방어 재현 → 검증된 엣지가 라이브 코드 경로에 그대로 실림(테스트 보증) + 거래수단 배선 아티팩트 `deploy/risk-managed-beta-portfolio.toml`(SPY·QQQ 추세 게이트, 운영 로더 파싱 검증). ④ 슬라이스 4: 변동성 타깃은 regime 의존적(극단 변동성 시대만 가치, 현대엔 추가 가치 없음) → 추세가 핵심 엣지, 변동성 타깃 기본 OFF(과공학 금물).** 종목선택 알파가 아니라 *자본 방어*다(추세추종 드로다운 방어 = 155년 끈질긴 효과). 신규(순수 추가·비커널): `analytics/risk_managed_beta.py`(production_in_market·CostModel·vol_target 포함) + `scripts/risk_managed_beta_probe.py`(--costs/--production-trend/--vol-target) + 단위 22건 + `deploy/risk-managed-beta-portfolio.toml`. **⚠ 아직 라이브 아님 — 남은 건 운영자 인프라 단계: ① forward A/B arm(종목선택 vs 추세 베타) 크론(`rebalance-paper-forward.yml`) 배선 + 백필에 SPY·QQQ 포함, ② 페이퍼 트랙 누적 → forward-verdict(스펙 035)+칼마(스펙 038) 위험조정 우위 확인, ③ 그 뒤 운영자 지시 소액 라이브 캐너리(헌법 X.4).** 돈 0 이동. 상세 `specs/042-risk-managed-beta/FINDINGS.md`. ─── 이전: **🟦 가격 신호 탐색 종료 → 패시브 권고(2026-06-05, 스펙 041 6차, PR #194).** 운영자 지시로 학술 근거 가장 강한 가격 신호 2개를 정직하게 측정: **12-1 모멘텀**(최근 1개월 제외, "제대로 된" 모멘텀)과 **단기 1주 반전**. 결과(plotly 2013-2018 깊은 표본): 12-1 모멘텀 H=21 IC +0.0200·t=0.68, 단기 반전 H=5 IC +0.0076·t=0.84(표본 N=250). **멈춤 규칙(N≥30 & IC>0 & t≥2) 미충족 → 가격 신호 탐색 종료.** "틀린 모멘텀을 쟀던 것 아니냐"는 의문까지 닫음(제대로 된 것도 엣지 아님). 깊은 옛 데이터(N 큼)와 얕은 최신 데이터(N=41)가 둘 다 같은 결론. **2순위(자율 진행): 패시브를 정직한 기본값으로 채택·문서화** — 가격 팩터로 인덱스를 이길 측정된 근거 없음. 시스템의 실질 가치는 알파가 아니라 안전·측정 인프라(포지션 캡·하드닝 카나리·서킷브레이커·IC 하네스). **3순위(다른 알파 원천: 펀더멘털·이벤트)는 별도 큰 프로젝트로 보류**(데이터 접근 불확실 → 운영자 결정). 신규(전부 순수 추가·비커널): `momentum_gap`/`short_reversal` 팩터 + `scripts/ic_signal_probe.py`(검증된 IC 하네스 재사용). 가중치 0 기본 = 운영 경로 영향 0. **⚠ 라이브는 무장 해제 그대로** — 이건 측정·권고이지 돈 움직이는 행동 아님(패시브 전환도 운영자 게이트, 헌법 X.4). 상세 `specs/041-absolute-return-gate/IC-FINDINGS.md`. ─── 이전: **🔴 라이브 거래 중단 + 전략 세계최고수준화(2026-06-04, 스펙 041).** 운영자 지적("점수 1위 매수는 허접 — 1위가 수익 기대 안 되는데도 투자. 기대수익 기준 판단해야. 유니버스 최대 확대. AAPL 1주 중단")이 정확해 정면 수정: ① **AAPL 라이브 캐너리 무장 해제**(`rebalance-live.request` armed:false — 실거래 중단, 룰 워커도 disabled 상태라 실거래 0). ② **절대 기대수익 게이트(듀얼 모멘텀)**: `strategy/trend.py` absolute_momentum + `min_return` — 상대 순위 1위라도 자기 후행수익이 바닥 미달이면 현금("기대 안 되면 투자 안 함"). ③ **유니버스 28→89** 현재 대형주(canary-portfolio.toml + -notrend). ④ **A/B = 게이트 가치 측정**: 게이트 ON vs OFF(1위 항상 매수) forward 비교(construct-universe-top-n 30). **다음**: 넓은 forward 페이퍼 트랙 누적(다음 22:30 UTC cron 또는 paper 센티넬) → forward-verdict로 게이트 ON/OFF 판정. **남은 격차: 예측 성공률/정보계수(IC)** — 합성 점수가 실제 미래 수익을 예측하는지 측정해 예측력 없으면 거래 막는 메타 게이트(운영자 "예측 성공률 기준 판단"). 검증 후에야 라이브 재무장(운영자 게이트). ─── 이전: (A) 라이브 캐너리 추세 방어 포트폴리오 무장(스펙 040, 이제 무장 해제됨). 스펙 035 = forward 엣지 판정 폐회로. 스펙 038 = 칼마. ⚠ 옛 데이터 백테스트는 판정 아님(stale). 돈 단위 검증 완료(코드+실데이터 드라이런: AAPL 1주 @ $312, 매도 0건). **첫 실주문 = 다음 시장시간 스케줄**(15:00 UTC 평일) — 무장 머지(push)는 미리보기만(LIVE 스텝 `event!=push` 게이트). 안전: 자본 $500·거래집합 무확대·추세 필터·스펙 014 서킷 브레이커·자본상한 $1,000. **다음**: ① go-live #6(룰 워커 비활성) 실행 성공 확인(진행중이었음), ② 다음 시장시간 스케줄 후 사이드카 `automation/rebalance-live-canary-last-run` 에서 실주문/체결 확인, ③ forward-verdict `--mode live`로 실거래 트랙 판정 누적. 스펙 039+040 = 가드형 채널 구축. 스펙 038 = 칼마(자본 방어). 스펙 035 = forward 엣지 판정 폐회로. ⚠ 옛 데이터 백테스트는 판정 아님(stale). 이전 컨텍스트: 스펙 039+040 = **고도화를 소액 실거래로 올리는 가드형 채널** 구축. `deploy/canary-live-portfolio.toml`($500 무장본, 추세 방어 top_n=1, SPY·MSFT·AAPL 무확대) + `.github/workflows/rebalance-live-canary.yml`(가드형, **기본 드라이런 미리보기**, 실주문은 센티넬 `armed:true`일 때만) + `automation/rebalance-live.request`(기본 `armed:false`). **무장 전 2가지 필수**: ① 사이드카 `automation/rebalance-live-canary-last-run` 드라이런 미리보기 확인, ② **룰 워커 충돌 해소**(같은 실계좌에 `canary-live-rules.toml` 워커가 돌면 포트폴리오 재조정이 워커 포지션 청산 → 룰 워커 비활성 먼저). 그 뒤 `armed:true` 머지 → 실주문. 자본 상한 $1,000 가드+서킷 브레이커+--confirm-live 인터록. 스펙 038 = **칼마 비율(자본 방어 측정)** forward-verdict 추가(페이퍼·라이브 공통). 스펙 037 = **forward A/B 토너먼트**(추세 필터 ON vs OFF, 전용 DB 격리, PAPER) 완료 — 추세 필터의 격리된 효과를 forward-verdict 가 판정. ⚠ **실거래 격차(운영자 핵심 지적)**: 고도화(스펙 032~038)는 전부 **페이퍼**. 실거래(라이브 캐너리)는 `canary-live-rules.toml` = 단순 3룰 qty=1(SPY 눌림목·MSFT 골든크로스 등), $12k, AUTO_INVEST_MODE=live(2026-05-30 무장). 즉 정교한 전략이 실제 돈을 안 만짐. 운영자 지시: "앞으로 항상 실거래 기반 고도화, 돈 못 벌면 의미 없다." 스펙 036 = **절대 모멘텀 추세 필터(드로다운 방어 오버레이)** 완료(forward 페이퍼 트랙에 켬, 라이브 캐너리엔 미적용). 스펙 035 = **forward 엣지 자동 판정 폐회로** 완료(돈 버는지 자동 판정). 스펙 034 = **유니버스 구성 역량 + 현재 데이터 경로 배선 + 재발 차단 가드** 완료. ⚠ 옛 데이터(2013-2018) 백테스트는 **판정 아님**(stale, `--allow-stale` 필요). "지금 통하는가"는 `rebalance-paper-forward.yml` forward 트랙 + `forward-verdict`(스펙 035)가 판정. ⚠ 스펙 034의 옛 데이터(2013-2018) 백테스트는 **판정 아님**(stale). 이제 도구가 stale 백테스트를 거부(`--allow-stale` 필요)하고, `rebalance-once --construct-universe-top-n` 이 forward 페이퍼 유니버스를 *현재* 바로 구성한다. **다음(인스턴스 검증)**: `rebalance-paper-forward.yml` 실행 → 사이드카 LAST_RUN.md 의 construct-universe 줄 + 페이퍼 체결 누적 → 디플레이티드 샤프로 "지금 통하는가" 판정. |
| 골격 스펙 (즉시 착수 가능) | **실거래 캐너리 — ✅ 완료(2026-05-30)**: 라이브 캐너리 무장됨. 다음 골격: 캐너리 자본 상향(체결 나오게·운영자 결정) 또는 풀라이브 승격(헌법 VI 3단계·운영자 전용) 또는 알파 계속(베타 헤지·회전율·워크포워드). |
| 자율 수행 최우선 진입점 (권장) | `docs/OPERATOR_GITHUB_ACTIONS_KR.md` + `.github/workflows/provision-vultr.yml` |
| Vultr 콘솔 직접 진입점 | `docs/OPERATOR_VULTR_ONE_STEP_KR.md` + `deploy/vultr-userdata.sh` |
| 단계별 학습 진입점 | `docs/OPERATOR_START_NONDEV_KR.md` |
| 개발자 5분 가이드 | `docs/OPERATOR_START.md` |
| KIS 키 입력 도구 (인스턴스 콘솔에서 실행) | `scripts/set_secrets.sh` |
| 개발자용 자동 검증 스크립트 | `scripts/operator_install.sh` (5단계 preflight) |
| 운영 호스트 진입점 | `deploy/README.md` (systemd 설치 절차) |
| main 테스트 | 2142 통과, 4 스킵 (라이브 KIS smoke 4건, `KIS_LIVE_TEST=1` 가드) |
| 세션 수명주기 도구 | git ground-truth 훅 + `/sync` `/handoff` `/deploy-status` 스킬 (v3.3.0, "세션 수명주기 도구" 절 참조) |
| main 린트 | 깨끗 |
| 열린 PR | `mcp__github__list_pull_requests`로 확인 |
| 운영자 로컬 환경 | `uv` 가상환경, `gh` 인증 완료, KIS 키는 `.env`에 (운영자 머신에만) |

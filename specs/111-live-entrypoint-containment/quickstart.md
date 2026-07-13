# Quickstart: Live Entrypoint Containment

## Goal

코덱스가 기존 위험 경로를 실제 돈이나 외부 서비스를 건드리지 않고 재현하고, 테스트를 먼저 추가한 뒤 proposal-only 경계로 바꾸는 절차다.

## 1. Branch and Ground Truth

```bash
git fetch origin
git checkout Codex/111-live-entrypoint-containment
git pull --ff-only

git status -sb
git log -5 --oneline
```

먼저 읽는다.

```bash
sed -n '1,240p' AGENTS.md
sed -n '1,280p' HANDOFF-115-EXECUTION-SAFETY-STABILIZATION.md
sed -n '1,260p' specs/111-live-entrypoint-containment/spec.md
sed -n '1,320p' specs/111-live-entrypoint-containment/plan.md
sed -n '1,260p' specs/111-live-entrypoint-containment/tasks.md
```

작업 트리에 기존 변경이 있으면 덮어쓰지 않는다.

## 2. Read-Only Baseline Search

```bash
rg -n "operator-design|AUTO_OK|auto_ok|prompt_operator_ok|start_live_worker|verify_rules|RULE_DESIGN_DEPLOYED" \
  .github scripts src tests docs
```

다음 질문에 답을 기록한다.

1. `operator-design` 예약 실행은 어디서 정의되는가
2. 자동 `OK`는 어디서 주입되는가
3. `design` CLI에서 `start_live_worker`까지 호출 순서는 무엇인가
4. verifier는 백테스트와 paper를 실제로 호출하는가
5. 기존 테스트 중 direct-live 동작을 요구하는 것은 무엇인가
6. `design` command policy는 어떤 권한을 선언하는가

## 3. Safety Snapshot Before Editing

주요 sentinel이 작업 전후 동일한지 해시를 기록한다.

```bash
sha256sum \
  automation/rebalance-live.request \
  automation/rebalance-micro-gtaa.request \
  automation/go-live-canary.request \
  .specify/memory/constitution.md \
  .specify/memory/kernel.toml \
  src/auto_invest/config/caps.py \
  src/auto_invest/config/whitelist.py \
  > /tmp/spec111-protected-before.sha256
```

macOS에서는 `shasum -a 256`을 사용한다.

## 4. Baseline Tests

관련 테스트 이름을 먼저 확인한다.

```bash
rg -n "design|operator_design|start_live_worker|command_policy\(\"design\"" tests
```

기존 focused tests를 실행한다. 파일명이 다르면 검색 결과에 맞춘다.

```bash
uv run pytest \
  tests/unit/test_design_deploy.py \
  tests/integration/test_design_cli.py \
  tests/unit/test_safety_command_registry.py
```

현재 unsafe behavior를 직접 실행하지 않는다. 테스트 더블과 source assertion으로만 재현한다.

## 5. Add Failing Tests First

최소 테스트 묶음:

```text
workflow source
- schedule 없음
- auto_ok 기본 true 없음
- raw intent shell interpolation 없음

shell helper
- AUTO_OK 분기 없음
- 자동 OK 주입 없음
- special-character intent 보존

verifier
- backtest unavailable -> ok false
- paper unavailable -> ok false
- skipped/stubbed -> ok false
- fingerprint mismatch -> ok false
- all actual evidence pass -> ok true

CLI
- candidate generated
- live worker not started
- broker order not called
- PROPOSAL_ONLY output

command registry
- design=A2 proposal
- live/order flags false
```

테스트가 기존 코드에서 의도대로 실패하는지 확인한 뒤 구현한다.

## 6. Implementation Order

### A. Workflow

```text
.github/workflows/operator-design.yml
```

- `schedule` 제거
- `auto_ok` 제거 또는 무권한 호환 입력으로 변경
- intent를 stdin/file/base64 중 하나로 안전 전달
- Summary 문구를 proposal-only로 변경
- 원격 종료 코드 정확히 전파

### B. Shell helper

```text
scripts/operator_design.sh
```

- `AUTO_OK`와 `echo "OK" |` 제거
- stdin 또는 파일에서 intent 읽기
- design proposal 실행
- live worker 상태 확인 문구 제거

### C. Verifier

```text
src/auto_invest/design/verifier.py
```

- stage result 모델 추가
- 실제 callable 실행
- 실행 증거 없는 경우 WAIT/FAIL
- aggregate fail closed

동적 validator 연결이 큰 경우 이번 PR에서 `ok=false` proposal 상태로 남긴다. 성공을 가장하지 않는다.

### D. CLI and deploy helper

```text
src/auto_invest/cli.py
src/auto_invest/design/deploy.py
```

- design command의 direct live startup 제거
- 후보 파일과 결과만 출력
- `start_live_worker` caller 0건 증명
- 필요 시 helper 삭제 또는 명시적 boundary error

### E. Command policy

```text
src/auto_invest/safety/command_registry.py
```

- `design`을 A2 proposal로 변경
- live/order capability false

## 7. Intent Transport Test Payload

아래 문자열을 fixture로 사용한다.

```text
자본 100달러, John's "low-risk" portfolio
$(touch /tmp/spec111-must-not-exist); echo hacked
`uname -a`
두 번째 줄: 금·채권·주식
🙂
```

검증:

```bash
test ! -e /tmp/spec111-must-not-exist
```

테스트는 실제 SSH를 사용하지 않는다. runner-side command construction과 remote-script stdin parsing을 함수 또는 subprocess fixture로 검증한다.

## 8. Focused Verification

```bash
uv run pytest \
  tests/unit/test_design_verifier.py \
  tests/unit/test_design_deploy.py \
  tests/integration/test_design_cli.py \
  tests/unit/test_safety_command_registry.py
```

추가한 workflow/shell 테스트 파일을 포함한다.

```bash
uv run ruff check src tests
git diff --check
```

## 9. Static Boundary Check

```bash
rg -n "AUTO_OK|auto_ok|start_live_worker|echo .*OK|schedule:" \
  .github/workflows/operator-design.yml \
  scripts/operator_design.sh \
  src/auto_invest/design \
  src/auto_invest/cli.py
```

남은 hit마다 다음 중 하나로 분류한다.

- 테스트가 금지 동작 부재를 검사하는 문자열
- 역사 문서
- 즉시 boundary error를 내는 deprecated compatibility shell
- 제거 누락

production 실행 hit는 0이어야 한다.

## 10. Protected Surface Check

작업 후:

```bash
sha256sum -c /tmp/spec111-protected-before.sha256
```

또는 macOS에서 대응 명령을 사용한다.

다음 파일이 diff에 있으면 범위 위반으로 중단한다.

```bash
git diff --name-only origin/main...HEAD | grep -E \
'^(automation/(rebalance-live|rebalance-micro-gtaa|go-live-canary)\.request|\.specify/memory/(constitution\.md|kernel\.toml)|src/auto_invest/config/(caps|whitelist)\.py)$' \
&& exit 1 || true
```

## 11. Full Gates

```bash
uv run pytest
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```

PR 본문을 `/tmp/pr-body-111.md`에 저장한 뒤:

```bash
python3 scripts/check_pr_quality_gate.py /tmp/pr-body-111.md
```

## 12. Final Manual Review

코드 diff를 네 관점으로 읽는다.

- 구현자: proposal-only가 실제로 작동하는가
- 검토자: 다른 direct-live caller가 남았는가
- 안전 담당자: live sentinel, caps, whitelist, loss budget이 그대로인가
- 인계 담당자: 다음 세션이 제거된 경로와 대체 경로를 이해하는가

## 13. Do Not Run

이번 스펙에서 아래 명령을 실제 환경에 실행하지 않는다.

```text
auto-invest run --capital ...
auto-invest rebalance-once --mode live --confirm-live
systemctl start auto-invest.service
auto-invest resume --confirm
GitHub Actions go-live / live rebalance dispatch
```

## 14. Completion Report Template

```markdown
## 핵심 결론

## 제거한 실거래 경로

## 유지한 설계 기능과 대체 승격 경로

## 검증 결과

## 안전 경계와 돈 경로 영향

## 실제 환경에서 실행하지 않은 항목

## 다음 스펙
```

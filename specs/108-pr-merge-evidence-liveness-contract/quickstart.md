# Quickstart: PR/Merge Evidence Liveness Contract

## Local probe with explicit fixtures

```bash
tmpdir="$(mktemp -d)"
cat > "$tmpdir/pr_body.md" <<'EOF'
# 변경 요약

- PR/머지 증거 생존성 계약 추가.

## 위험 등급

- [ ] 등급 0: 설명, 조사, 단순 문서 오탈자처럼 실행 동작이 바뀌지 않음
- [ ] 등급 1: 일반 코드나 테스트 변경. 안전 경계, 배포, 돈 경로, 자동화 흐름은 바꾸지 않음
- [x] 등급 2: 운영 체계 변경. 훅, 설정, 워크플로, `AGENTS.md`, `CLAUDE.md`, `HANDOFF.md`, 스킬, 인계, 머지 흐름을 바꿈
- [ ] 등급 3: 안전 경계 변경. 헌법, 커널 목록, 위험 게이트, 주문 제한, 감사 로그, 비밀값, 배포 제한, 외부 API 안전장치를 바꿈
- [ ] 등급 4: 돈 경로 변경. 실제 주문, 실거래 전환, 자본 배분, 계좌 노출, 라이브 전략 교체, 운영자 비용 발생 가능성이 있음

## 문제 정의

- 요청: 다음 자율 후보를 완료한다.
- 실제 목표: PR/머지 증거 생존성을 재현 가능하게 만든다.
- 비목표: 돈 경로 변경 없음.
- 위험: 완료 증거 누락.
- 완료 기준: 테스트와 하네스 통과.

## 탐색 근거

- 읽은 파일: HANDOFF.md, PR 템플릿.
- 확인한 실행 경로: probe.
- 제거하거나 줄인 기능: 없음.
- 남긴 기능 또는 대체 수단: 기존 PR 품질 관문.

## 변경 내용

- 읽기 전용 보고서 추가.

## 검증

- [x] `uv run pytest`
- [x] `uv run ruff check src tests`
- [x] 문서·설정 변경에 맞는 형식 검증: `git diff --check`
- [x] 등급 2 이상 실제 적용 경로 확인: focused probe

## 하네스 검증

- 하네스 평가: `uv run python scripts/agent_harness_probe.py --strict` OK.
- HANDOFF 검증: `uv run python scripts/check_handoff_facts.py` OK.

## 안전 경계

- Kernel 터치: 없음
- 안전 경계 변경: 없음
- 돈 경로 변경: 없음
- 감사 로그·비밀값·주문 제한 영향: 없음

## 인계

- 다음 세션이 알아야 할 상태: 보고서가 완료 증거를 분리한다.
- 남은 위험: post-merge deploy 관측 대기 가능.
- 실행하지 못한 검증: 없음

## 자동 머지 준비

- [x] 작업 완료
- [x] 테스트 통과
- [x] 린트 깨끗함
- [x] PR 머지 가능 상태 확인
- [x] `WIP` 또는 `DO NOT MERGE` 표식 없음
- [x] Kernel 터치 커밋 해시를 본문에 명시함, 또는 Kernel 터치 없음
EOF

cat > "$tmpdir/released_work.json" <<'EOF'
{"released_work":[{"candidate_id":"candidate-pr-merge-evidence-liveness-contract","status":"released"}]}
EOF

cat > "$tmpdir/deploy_status.md" <<'EOF'
대상 main 커밋: abc123 Merge pull request #999 from branch
Deploy on merge to main: success
kis-smoke sidecar: success
서버 audit_log는 운영자 전용 표면이다.
EOF

uv run python scripts/pr_merge_evidence_liveness_probe.py \
  --repo-root . \
  --pr-body "$tmpdir/pr_body.md" \
  --released-work "$tmpdir/released_work.json" \
  --deploy-status "$tmpdir/deploy_status.md" \
  --format json
```

Expected: JSON includes `overall_status=CONTRACT_READY`, `completed_candidate_id=candidate-pr-merge-evidence-liveness-contract`, and `next_candidate_id=candidate-worktree-concurrency-liveness-contract`.

## Autonomous-work transition

```bash
uv run pytest tests/unit/test_pr_merge_evidence_liveness.py \
  tests/integration/test_pr_merge_evidence_liveness_probe.py \
  tests/unit/test_autonomous_work_execution.py -q
```

Expected: released PR/merge evidence advances selected work to `candidate-worktree-concurrency-liveness-contract`.

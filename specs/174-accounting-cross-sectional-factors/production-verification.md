# 생산 검증: 회계 기반 횡단면 다요인 전략

## 기준 봉인

- 사전등록·계획·계약 커밋: `c172dbb`, `cfd5a3b`
- 작업 순서 커밋: `fbbd468`
- 공식 자료 열람 전 구현·시험·워크플로 커밋:
  `5b73792d59d70f69642e428ba74108e35fc81ee3`
- 위 커밋 뒤에만 공식 보관본과 최신본을 내려받았다.

## 실행과 결과

```bash
uv run python scripts/edge_gate_calibration_probe.py \
  --seed 60000 --repetitions 500 \
  --code-commit 5b73792d59d70f69642e428ba74108e35fc81ee3 \
  --timestamp-utc 2026-08-31T00:00:00Z \
  --json-out /tmp/spec174_edge_gate_calibration.json

uv run python scripts/accounting_factor_factory_probe.py \
  --prior-factory-json /tmp/spec174_prior_factory.json \
  --calibration-json /tmp/spec174_edge_gate_calibration.json \
  --result-schema specs/174-accounting-cross-sectional-factors/contracts/accounting-factor-result.schema.json \
  --code-commit 5b73792d59d70f69642e428ba74108e35fc81ee3 \
  --timestamp-utc 2026-08-31T00:00:00Z \
  --json-out /tmp/accounting_factor_factory.json \
  --summary-out /tmp/accounting_factor_factory.md
```

- 결과: `NO_FACTORY_EDGE`
- 공식 자료 파싱·날짜·필수열·결측 검증: 통과
- 16개 후보·800행·20가족·오합격 상한 0.20: 통과
- JSON 결과 계약: 통과
- 역사 성과 관문: 7개 실패
- 주문·자본·라이브 변경: 0건/없음/없음

## 결정론과 독립 소비자

- 동일 명령을 다시 실행해 `/tmp/accounting_factor_factory_repeat.json`과 Markdown을 만들었다.
- `cmp`로 첫 실행과 재실행 JSON·Markdown이 모두 동일함을 확인했다.
- 두 전체 JSON의 SHA-256은 모두
  `2cc1c738a1f6075cebbc255d905352711b52337bcd66f7644896a33f0b460e37`이다.
- `scripts/factory_evidence_gate.py`가 800행·20가족·0.20을 독립 재계산했다.
- 소비자 종료코드는 예상한 부적격 코드 `3`이었다. 통계 탈락 외에도 point-in-time 종목,
  실행 동등성, 연구 캐너리, 배포 설정이 없으므로 실패 폐쇄했다.

## 관련 회귀시험

```bash
uv run pytest -q \
  tests/unit/test_accounting_factor_factory.py \
  tests/unit/test_turn_of_month_equity_factory.py \
  tests/unit/test_research_family_audit.py \
  tests/unit/test_factory_evidence.py \
  tests/integration/test_accounting_factor_factory_probe.py \
  tests/integration/test_turn_of_month_equity_factory_probe.py \
  tests/integration/test_strategy_factory_workflow.py \
  tests/integration/test_factory_evidence_gate.py
```

공식 자료 열람 전 관련 시험 48개가 통과했다. 오래된 옵션 워크플로 시험의 784행 기대값을
새 최종 800행 상태로 갱신한 뒤 전체 저장소를 다시 검증했다.

- `uv run pytest -q`: 3,167개 통과, 6개 조건부 건너뜀, 실패 0개
- 건너뜀 6개: `KIS_LIVE_TEST=1`이 필요한 기존 실계좌 연동 시험
- `uv run ruff check src tests`: 통과
- `uv run ruff check scripts/accounting_factor_factory_probe.py`: 통과
- `uv run python scripts/agent_harness_probe.py --strict`: 14/14 통과
- `uv run python scripts/check_handoff_facts.py`: 통과
- `uv run python scripts/check_pr_quality_gate.py --template .github/pull_request_template.md`: 통과

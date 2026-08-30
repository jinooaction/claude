# Quickstart: PEAD와 21가족 프로그램 관문

## 1. 사전등록과 교정 확인

```bash
uv run python scripts/edge_gate_calibration_probe.py --output /tmp/edge-calibration.json
uv run python scripts/pead_factory_probe.py \
  --prior-evidence /tmp/accounting-factor-factory.json \
  --preregistration specs/175-pead-program-gate/contracts/pead-preregistration.json \
  --output /tmp/pead-factory.json \
  --summary /tmp/PEAD_LAST_RUN.md
```

PEAD 탐침은 공개자료를 읽으며 이전 sidecar가 800후보·20가족인지 먼저 확인한다. 실제 계좌나
브로커 자격증명은 필요하지 않다.

## 2. 독립 증거 판정

```bash
uv run python scripts/pead_evidence_gate.py \
  --evidence /tmp/pead-factory.json \
  --preregistration specs/175-pead-program-gate/contracts/pead-preregistration.json
```

종료 코드 0은 “발행된 연구 판정의 동일성과 안전 경계가 유효하다”는 뜻이다.
`PUBLISHED_EDGE`라도 실자본 적격이나 주문 승인이 아니다.

기존 돈 경로 소비자가 새 진단 전용 계약을 거부하는지도 확인한다.

```bash
uv run python scripts/factory_evidence_gate.py --evidence /tmp/pead-factory.json
```

이 명령은 `3.2`를 자본 진입 증거로 인정하지 않고 실패 폐쇄해야 정상이다.

## 3. 검증

```bash
uv run pytest tests/unit/test_pead_factory.py tests/unit/test_pead_factory_evidence.py
uv run pytest tests/integration/test_pead_factory_probe.py tests/integration/test_pead_evidence_gate.py
uv run pytest
uv run ruff check src tests
uv run python scripts/agent_harness_probe.py --strict
uv run python scripts/check_handoff_facts.py
```

## 4. 결과 읽는 법

- `PUBLISHED_EDGE`: 공개 역사자료 관문 통과. 현재 계좌나 라이브 자본에는 아직 부적격.
- `PAPER_CHALLENGER`: 과거 신호는 있지만 최근성 또는 엄격 관문 부족.
- `NO_FACTORY_EDGE`: 공개 복제자료에서도 최소 경제 근거 부족.
- `research_canary_eligible=false`, `promotion_allowed=false`, `orders_submitted=0`은 모든 판정에서
  반드시 유지된다.


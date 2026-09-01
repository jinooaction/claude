# 빠른 실행: 비용 현실형 장중매매 페이퍼 챌린저

## 1. 입력 준비

`contracts/intraday-bars.md`에 맞춰 한 디렉터리에 `SPY.csv`, `QQQ.csv`, `IWM.csv`,
`TLT.csv`, `GLD.csv`와 `manifest.json`을 둔다. 각 CSV는 같은 공급자·같은 조정 정책의 5분
정규장 봉이어야 한다.

## 2. 연구 배치 실행

```bash
uv run python scripts/intraday_paper_challenger_probe.py \
  --bars-dir /path/to/intraday-bars \
  --manifest /path/to/intraday-bars/manifest.json \
  --preregistration specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json \
  --code-commit "$(git rev-parse HEAD)" \
  --json-out /tmp/intraday-paper-result.json \
  --ledger-out /tmp/intraday-paper-ledger.jsonl \
  --summary-out /tmp/INTRADAY_PAPER_LAST_RUN.md
```

자료가 756세션보다 짧으면 종료 실패가 아니라 기계 판독 가능한
`INSUFFICIENT_EVIDENCE`가 발행된다. 파일 손상·지문 불일치는 입력 오류 종료 코드 2다.

## 3. 독립 증거 판정

```bash
uv run python scripts/intraday_paper_evidence_gate.py \
  --evidence /tmp/intraday-paper-result.json \
  --ledger /tmp/intraday-paper-ledger.jsonl \
  --preregistration specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json
```

종료 코드 0은 결과의 동일성·판정·안전 필드가 유효하다는 뜻이다.
`PAPER_CHALLENGER`라도 실주문이나 자본 승인을 뜻하지 않는다.

## 4. 검증

```bash
uv run pytest tests/unit/test_intraday_paper_challenger.py
uv run pytest tests/unit/test_intraday_paper_challenger_evidence.py
uv run pytest tests/integration/test_intraday_paper_challenger_probe.py
uv run pytest
uv run ruff check src tests
uv run python scripts/agent_harness_probe.py --strict
uv run python scripts/check_handoff_facts.py
```

## 5. 결과 읽는 법

- `INSUFFICIENT_EVIDENCE`: 기간·세션·거래·자료가 부족해 아직 판단할 수 없음.
- `NO_INTRADAY_EDGE`: 자료는 충분하지만 KIS 비용·강건성 관문 뒤 남는 후보가 없음.
- `PAPER_CHALLENGER`: 모든 역사 관문 통과. 자본 0으로 최소 60세션 전진 관찰만 가능.

모든 상태에서 실제 주문 0건, 자본 0%, 라이브 설정 변경 0건이어야 한다.

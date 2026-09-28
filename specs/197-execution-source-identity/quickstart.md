# 검증 순서

1. 신규 identity 반례로 기존 네 누락의 실패를 확인한다.
2. 목록과 경로/내용 지문 구현 후 identity/selection/qualification 검사를 실행한다.
3. 삭제·읽기 실패·변경 중·문서 변경·기존 지문 자격을 검사한다.
4. 외부 접속 없는 사용자self-test의 실제주문0/live_eligible=false를 확인한다.
5. 전체pytest/ruff·하네스·인계·PR 품질 검사와 배포를 확인한다.

권한을 발급하거나 자동 변경하지 않는다. 전체 단타 전략 관문은 별도로 유지한다.

저장소 루트에서 아래 명령으로 구현된 검사를 재현한다. 기존 전체 검사 프로세스가 실행 중이면 새로 시작하지 말고 해당 실행의 종료 결과를 먼저 확인한다.

```sh
uv run pytest tests/unit/test_intraday_identity.py tests/unit/test_intraday_selection.py tests/unit/test_intraday_qualification.py tests/unit/test_intraday_registration.py -q
uv run python scripts/intraday_operator.py self-test
uv run ruff check src tests
uv run python scripts/agent_harness_probe.py --strict
uv run python scripts/check_handoff_facts.py
uv run pytest -q
```

소스 읽기 비용은 같은 저장소 루트에서 다음과 같이 측정한다. 서버 최악 지연이나 전략 승인 근거로 사용하지 않는다.

```sh
uv run python - <<'PY'
from statistics import mean
from time import perf_counter
from auto_invest.execution.intraday_identity import source_identity

samples = []
for _ in range(100):
    start = perf_counter()
    source_identity()
    samples.append((perf_counter() - start) * 1000)
print({"mean_ms": mean(samples), "p95_ms": sorted(samples)[94], "max_ms": max(samples)})
PY
```

과거 네 반례의 실패는 기준 커밋 `37829096639c7ef60c3df43bf899fce516667fc4`에서 재현했다. 현재 버전에서 실패해야 한다는 뜻이 아니다. 현재 자료의 절대 경로나 사용자 작업 트리를 되돌려 기준 버전을 만들지 않는다.

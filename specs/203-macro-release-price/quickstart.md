# Quickstart: 발표일 진단

1. [계약](contracts/preregistration.json)의 모든 SHA-256을 실제 원본과
   비교한다. HF 달력·ALFRED 두 목록은
   `/Users/mason/Projects/claude-data-research/20261002-macro-calendar/`,
   가격 목록·CSV는 `20260921-hf-raw/research-input/`에 있다.
2. 날짜·시각·휴장·중복 입력만 감사하고 개발 가격을 열기 전에 계약
   커밋을 기록한다. 2차 달력의 `status`가 공식 날짜를 덮지 않는다.
3. 관련 단위/통합 반례를 실행한 뒤 개발 구간만 재생한다. 출력은
   저장소 밖 새 파일로 기록하고 SHA-256을 남긴다.
4. 비용 후 결과가 음수면 차단/최종 수익을 열지 않는다. 양수라도
   Spec 177의 정식 후보 선별과 Spec 181 T014~T016은 별도다.

재생 명령은 다음과 같다. 출력 파일이 이미 있으면 실패한다.

```sh
nice -n 10 uv run python scripts/macro_release_price_diagnostic.py \
  --calendar-dir /Users/mason/Projects/claude-data-research/20261002-macro-calendar \
  --bars-dir /Users/mason/Projects/claude-data-research/20260921-hf-raw/research-input \
  --output /Users/mason/Projects/claude-data-research/20261002-macro-calendar/macro-release-price-203-development-v2.json
```

이 단계에서 브로커 비밀값·주문은 사용하지 않는다. 실제 결과는
[results.md](results.md)에 기록했다.

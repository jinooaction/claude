# 단타 프로그램 실행 안내

## 서버 수집 증명을 남기는 모의 운용

서버에 `/etc/auto-invest/intraday-market-data.key`가 준비된 경우 다음 옵션으로
직접 수집한 봉과 수신 시각을 서명해 보존합니다. 키는32바이트 일반 파일, root 소유,
서비스 계정에 읽기만 허용하는0640 이하 권한이어야 합니다. 링크와 공개 키 파일은
거절합니다. 연구 고정용 intraday-forward.key와 별도이며 이번 작업에서 설치하지 않았습니다.

```sh
uv run python scripts/intraday_operator.py run --root data/intraday-attested --attest-market-data
```

기존 KIS 인증 환경을 사용합니다. 사용자 봉 파일을 서명하는 기능은 없고 프로그램이
직접 조회한5종목 봉만 처리합니다. 새 런타임 소스 지문에 맞는 별도 장부를 사용하며
이전 장부는 보존합니다. 키·시계·수집 코드를 신뢰하는 서버 증명이지 증권사의 전자서명은
아닙니다. 증명 없는 진단 기록이나 과거 수집일을 정식 전진 실적으로 바꾸지 않습니다.
출처 증명과 구간 거래량 통과도 전체 계좌 인증·연구 모델 동등성·운영 승인과는 별개입니다.

## 지금부터 계좌 원본 기록

서버의 기존 인증 환경에서 다음 명령으로 조회 원본을 비공개 장부에 추가할 수 있습니다.
부모 폴더는 미리 존재해야 합니다. 같은 명령을 다시 실행하면 이전 관측 뒤에 이어 쓰며
과거 전체 거래내역 파일은 필요하지 않습니다. 자동 주기 실행이나 서버 설치를 뜻하지 않습니다.

```sh
uv run python scripts/intraday_balance_check.py --history-db data/account-observations.db --execution-db data/auto_invest.db
```

기존 실행 장부는 읽기만 합니다. 새 관측 장부는0600 권한으로 만들며 원본 금액·종목이
포함되므로 공개하지 않습니다. 조회 실패 기록도 보존하지만 검증된 시작 잔고로 쓰지 않습니다.
조회 성공은 현재 전체 순현금의 검증이나 실주문 허용을 의미하지 않습니다.

현재 실행 가능한 것은 **KIS 시세를 이용한 모의 자동 운용, 실제 체결시각이 있는 시세 조회,
종목·지정가별 구매가능 상한 조회**입니다. 실주문 자동 운용 완성본은 아닙니다.
실행 시작 명령은 연결됐지만 전체 계좌 계산·체결 동등성 검증이 미완료라 현재 생산
시작은 차단됩니다. 아래 명령의 존재를 실거래 준비 완료로 해석하지 않습니다.

프로젝트 폴더에서 `uv sync --locked`로 설치합니다. Alpaca 계정은 사용하지 않습니다.
사용 계좌는 기존 한국투자 계좌로 확정했습니다. 새 계좌를 만들 필요가 없습니다.
기존 보유는 단타 매매분과 구분합니다. 실행 엔진의 기준표 연동과 소유 분리 검사는 통과했으며,
최종 계좌 검증과 적격 조건의 연결은 아직 남아 있습니다.
기존 운영 환경의 `KIS_APP_KEY`, `KIS_APP_SECRET`를 사용합니다. 구매력 조회에는
`KIS_ACCOUNT_NO`도 필요합니다. 비밀값을 명령 인수·채팅·저장소에 적지 마세요.
이 명령은 `.env`를 자동 검색하지 않습니다. 기존 비밀값 관리 환경에서 실행합니다.
이미 준비한 `.env`를 사용하려면 `uv run --env-file .env python scripts/intraday_operator.py run`으로
실행할 수 있습니다. 시세와 구매력 명령에도 같은 `--env-file` 옵션을 적용할 수 있습니다.

## 시작, 확인, 중지

설치 후 계좌 키 없이 프로그램 자체 시험을 실행할 수 있습니다.

```sh
uv run python scripts/intraday_operator.py self-test
```

`SELF_TEST_PASSED`는 시험용 증권사 응답으로 부분 체결·늦은 체결·재시작·중지 정리가
통과했다는 뜻입니다. 실제 계좌나 네트워크에 연결하지 않으며 사용자 장부를 받지 않습니다.
실제 거래 자격이나 실계좌 검증 통과를 뜻하지 않습니다. 실패하면 종료 코드2와 실패 항목을
표시합니다. 아래 `run`은 기존 모의 운용을 시작하는 별도 명령입니다.

```sh
uv run python scripts/intraday_operator.py run
```

정규장에는 매분 자료를 읽고 사전 등록한 18개 모의 전략의 장부를 갱신합니다.
장 밖에서는 기다립니다. 화면의 모의 자산은 전략 비교용 가상 자산이며 확정한
600달러 실거래 준비 한도나 실제 계좌 잔액이 아닙니다.

다른 창에서 상태 확인과 중지 요청을 할 수 있습니다.

```sh
uv run python scripts/intraday_operator.py status
uv run python scripts/intraday_operator.py stop
```

중지 요청은 현재 수집·장부 반영을 끝낸 뒤 적용됩니다. 대기 중에는 1초 안에 반영됩니다.
다시 `run`을 실행하면 같은 `data/intraday-operator/paper.db` 장부를 이어 씁니다.
중지는 모의 보유의 청산이나 실제 주문 취소가 아닙니다. 강제 종료 흔적은 `INTERRUPTED`,
연속 세 번의 수집 실패는 `FAILED`로 표시합니다. 기록은 `events.jsonl`에 추가됩니다.

## 시세와 구매가능 상한

```sh
uv run python scripts/intraday_operator.py quotes --seconds 30
uv run python scripts/intraday_operator.py buying-power --symbol SPY --limit-price 100.00
```

100.00은 요청 형식 예시이며 매수 추천 가격이 아닙니다. 본인이 확인하려는 지정가로
바꿉니다. 구매가능 금액·수량은 해당 조회의 외화 상한이며 현금 잔액·총자산·매수 승인이 아닙니다.
시세 결과의 `source_at`은 증권사 체결 발생시각, `received_at`은 도착시각입니다.
장전·장후, 30초 초과, 구독하지 않은 종목, 시간대가 맞지 않는 가격은 받아들이지 않습니다.
30초 안에 모든 종목의 유효 시세가 없으면 종료 코드2로 미완전 상태를 알립니다.

## 주문 엔진의 상태와 중지 요청

`execution-start`는 같은 장부를 이용한 시작/재개 명령입니다. 다음 경로는 모두 예시입니다.
이미 사용하는 장부·설정·기준표와 검증 자료를 지정하며, 없는 장부를 자동 생성하지 않습니다.
이 안내에서 실제 실행을 수행한 것은 아닙니다.

```sh
uv run python scripts/intraday_operator.py execution-start \
  --db /path/to/trading.db --rules /path/to/rules.toml \
  --archives /path/to/archives --forward-db /path/to/forward.db \
  --registration /path/to/freeze.json --external-holdings /path/to/holdings.toml \
  --halt-path /path/to/halt.flag --token-cache /path/to/token.json
```

시작에는 기존 세 가지 KIS 환경값이 모두 필요합니다. 자격 실패는 외부 접속 전에
종료 코드2로 거절합니다. 현재 체결 동등성 검사가 미구현이므로 실제 자료가 충분해져도
`QUALIFICATION_PARITY_NOT_VERIFIED`를 승인 파일로 덮을 수 없습니다.
서버 운영 승인은 장부·중지 파일·위험 설정·보유 기준표 지문에도 묶입니다.
`Ctrl+C`나 종료 신호는 정리 요청이며, 같은 명령으로 재시작하면 기존 기록을 이어갑니다.
정리 완료가 확인된 `STOPPED`만 정상 종료 코드0입니다. 오류 후 주문 결과가 불확실하면
`order_outcome_verified=false`를 표시하며 주문0으로 단정하지 않습니다.

실제 주문 엔진을 호출하는 운용 모듈에 상태 확인과 중지 요청을 추가했습니다.
아래 명령은 그 운용 모듈이 사용하는 공용 거래 DB의 정확한 경로를 지정해야 합니다.
`/path/to/trading.db`는 예시이며 새 장부를 만들라는 뜻이 아닙니다.

```sh
uv run python scripts/intraday_operator.py execution-status --db /path/to/trading.db
uv run python scripts/intraday_operator.py execution-stop --db /path/to/trading.db
```

중지 요청은 신규 진입을 막고 미체결 취소와 단타 보유분 정리를 이어갑니다.
기존 보유분은 청산하지 않습니다. `STOP_REQUESTED`는 요청 저장이며,
`STOPPED`는 증권사 대조 후 단타 보유와 미체결이 모두 없음을 확인한 상태입니다.
시세·계좌 조회가 실패하면 정리를 완료했다고 표시하지 않습니다.
강제 종료 후에는 `INTERRUPTED`로 표시하고 다음 실행에서 저장된 중지 요청을 이어갑니다.
주문 운용 모듈을 이전 버전으로 바꾸려면 먼저 `STOPPED`를 확인해야 합니다.
정리가 남았으면 같은 버전과 장부를 유지하여 조회·권한 문제를 복구한 뒤 정리를 이어갑니다.

이 제어 기능은 기존 주문 엔진을 사용하는 통합 시험에서 검증했습니다.
실계좌 관측·적격 권한을 갖춘 엔진을 생성하는 생산 연결은 아직 없으므로,
현재 사용자가 실주문을 시작할 명령은 제공하지 않습니다. 위의 `run`은 모의 운용입니다.

## 현재 적용과 복구

실제 서버의 기존 모의 타이머를 자동 교체하지 않습니다. 별도 실행 폴더가 필요하면
모든 `run/status/stop` 명령에 동일한 `--root`를 지정합니다. 같은 폴더의 중복 실행은 거절합니다.
기존 서버 장부를 이동하거나 지우지 않습니다. 새 실행기를 중지하면 이전 실행 명령으로
돌아갈 수 있습니다. 실주문 스위치·자금 배정·실제 주문은 이 명령이 변경하지 않습니다.
# 날짜별 보관 자료로 전략 검증 실행

거래/수수료 원본의 읽기 점검은 기존 잔고 점검 명령에 두 날짜 옵션을 함께 지정한다.
아래 날짜는 조회 예시이며 **등록일** 기준이다. 공개 결과는 건수만 보여주고 금액·종목은
출력하지 않는다. 기존 계좌 인증을 쓰는 GET 조회이며 실제 주문은 보내지 않는다.
부분 조회는 실패한다. 이 명령의 성공은 현금이나 개별 체결 비용 검증 완료가 아니다.
transactions.settlement_audit는 거래금액·보고 수수료·정산금액의 산술 일치 여부다.
MATCH도 계좌 현금이나 실제 주문별 비용 승인이 아니며, MISMATCH/NO_TRANSACTIONS는
검증된 합계를 만들지 않는다. 통화별 상세 합계와 원본 금액은 공개 출력에서 제외한다.

같은 명령에 `--execution-db /path/to/existing-execution.db`를 더하면 기존 장부를
읽기 전용으로 대조한다. 두 날짜 옵션이 모두 필요하며 없는 DB를 만들지 않는다.
같은 인증의 주문체결 GET 조회를 추가하고 주문번호별 장부 수량/금액→명세 합계를 비교한다.
ledger_comparison의 MATCH는 제공된 조회들 사이의 일치다. 등록일과 주문일의 전체
거래 범위나 장부 계좌 소속을 인증하지 않으며 개별 주문 수수료·현금·실거래 승인이 아니다.

```sh
uv run python scripts/intraday_balance_check.py --transactions-from 20260901 --transactions-through 20260910
```

이미 보관된 자료를 결합해 기존 연구 검증기로 넘길 수 있습니다. `--archives`는
YYYY-MM-DD 폴더들이 들어 있는 sessions 폴더이고 `--out`은 아직 없는 새 폴더입니다.
다음 경로는 예시이며 실제 보관 위치로 바꿉니다. 계좌 키나 새 계정은 필요하지 않습니다.

```sh
uv run python scripts/intraday_operator.py history-review --archives /path/to/sessions --out /path/to/new-review
```

review.json에서 실제 완결 거래일 수와 부족분을 확인합니다. research.json은 기존177
전략 검사 결과이고 ledger.csv는 연구용 모의 체결입니다. 원본 보관 파일은 바뀌지 않습니다.
원본 지문·가격 파일 불일치, 완료 날짜의 자료 누락, 다른 공급자 혼합은 실패합니다.
기존 수집기의 임시 보관 폴더는 별도 개수로 표시하며 검증 일수에는 더하지 않습니다.
중간 거래일이 빠져도 자료 부족으로 남깁니다. 이 명령은 실주문이나 정식 전진 검증을 시작하지 않습니다.

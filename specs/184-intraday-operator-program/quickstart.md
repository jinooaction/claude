# 단타 프로그램 실행 안내

현재 실행 가능한 것은 **KIS 시세를 이용한 모의 자동 운용, 실제 체결시각이 있는 시세 조회,
종목·지정가별 구매가능 상한 조회**입니다. 실주문 자동 운용 완성본은 아닙니다.
실주문 엔진은 있지만 전체 계좌 관측·전략 적격성·운용 권한과의 연결이 남아 있습니다.

프로젝트 폴더에서 `uv sync --locked`로 설치합니다. Alpaca 계정은 사용하지 않습니다.
기존 운영 환경의 `KIS_APP_KEY`, `KIS_APP_SECRET`를 사용합니다. 구매력 조회에는
`KIS_ACCOUNT_NO`도 필요합니다. 비밀값을 명령 인수·채팅·저장소에 적지 마세요.
이 명령은 `.env`를 자동 검색하지 않습니다. 기존 비밀값 관리 환경에서 실행합니다.
이미 준비한 `.env`를 사용하려면 `uv run --env-file .env python scripts/intraday_operator.py run`으로
실행할 수 있습니다. 시세와 구매력 명령에도 같은 `--env-file` 옵션을 적용할 수 있습니다.

## 시작, 확인, 중지

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

## 현재 적용과 복구

실제 서버의 기존 모의 타이머를 자동 교체하지 않습니다. 별도 실행 폴더가 필요하면
모든 `run/status/stop` 명령에 동일한 `--root`를 지정합니다. 같은 폴더의 중복 실행은 거절합니다.
기존 서버 장부를 이동하거나 지우지 않습니다. 새 실행기를 중지하면 이전 실행 명령으로
돌아갈 수 있습니다. 실주문 스위치·자금 배정·실제 주문은 이 명령이 변경하지 않습니다.

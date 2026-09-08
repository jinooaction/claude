# 구현 계획: 단타 실행 프로그램

## 기술 환경

Python 3.11+, httpx, SQLite, asyncio, websockets 15~17의 asyncio 전송.
기존 `scripts/intraday_runtime.py`와 `PaperRuntime` 장부를 재사용한다.
새 시세 입력은 기존 기본 비활성 `realtime.py`와 분리해 기존 워커 동작을 바꾸지 않는다.

## 헌법 점검

등급 3. 허용 종목, 현금·계좌 검증, 주문 권한, 단계별 자본, 공용 거래 DB와
계좌 잠금, 감사 로그, 장중 배포 금지는 그대로 유지한다. 공식 시세 접속과
외화 구매력 GET만 새로 실행 가능하다. 모의 장부는 실거래 공용 장부와 구분한다.
전체 계좌 NAV를 임의로 만들거나 사용자 기준선을 브로커 검증값으로 승격하지 않는다.

## 조사 및 결정

계획 기술의 독립 조사 두 건(operator_runtime_research, kis_inputs_research)을 수행했다.
결과와 공식 출처는 research.md에 기록한다. 주입형 시세 코드에는 실제 전송·발생시각이
없었고, 고정 AAPL/1 구매력 조회는 주문별 상한으로 사용할 수 없었다.
전체 NAV 입력과 실제 단타 권한은 미완료이며 시세 연결 성공으로 완료 처리하지 않는다.

## 구조

- src/auto_invest/broker/intraday_inputs.py: 엄격한 체결 파서, 실제 전송, 외화 구매력.
- scripts/intraday_operator.py: run/status/stop/quotes/buying-power의 단일 진입점.
- tests/unit/test_intraday_inputs.py: 프로토콜·수량·시각·비밀 오류 경계.
- tests/integration/test_intraday_operator.py: 실제 로컬 전송, 수명주기, 명령 연결.

## 순서와 검증

1. 명세·입력 계약·작업 목록을 작성한다.
2. 순수 파서와 외화 구매력 조회를 구현하고 반례 테스트한다.
3. 실제 웹소켓 전송·해지·연결 종료와 캐시 무효화를 검증한다.
4. 기존 모의 실행기를 단일 명령의 지속 운용·상태·중지로 연결한다.
5. 문서 명령을 실제 실행하고 관련 주문 엔진 회귀, 전체 테스트, 린트, 하네스를 확인한다.
6. 사용자 전체 목표의 미완료 실주문 연결은 숨기지 않고 초안 PR에 남긴다.

## 복구

신규 모의 프로세스를 협조적으로 중지하고 기존 실행 명령으로 돌아갈 수 있다.
기존 장부·봉 자료·감사 기록을 삭제하거나 재작성하지 않는다. 실거래 배포·가동은 하지 않는다.

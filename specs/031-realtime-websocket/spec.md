# 스펙 031 — 체결 정교화 P3: KIS 실시간 웹소켓 (슬라이스 1)

## 배경 / 문제

현재 워커는 시세를 `get_quote` **REST 폴링**으로, 체결을 `sync_fills` **REST 폴링**으로
받는다(스펙 015). 폴링은 본질적으로 지연이 있다 — 틱 간격(1Hz)·cadence(체결 5초)만큼
시세·체결 반영이 늦는다. 세계 최고 수준 데스크는 거래소 실시간 푸시(웹소켓)로 이 지연을
없앤다. KIS 는 실시간 웹소켓으로 시세(체결가)·체결통보를 푸시한다.

## 목표

- **G1 — 실시간 시세 수신**: KIS 웹소켓으로 시세를 받아 워커가 폴링 대신 푸시된 최신
  시세로 룰을 평가한다(지연 제거).
- **G2 — 폴백 보장**: 웹소켓이 끊기거나 실패하면 **기존 REST 폴링으로 자동 폴백**한다 —
  거래는 한순간도 멈추지 않는다(헌법 외부 API 강건성).
- **G3 — 수신 전용**: 웹소켓은 시세/체결 사실만 받는다. 주문 제출·취소 경로를 한 바이트도
  바꾸지 않는다.

## 슬라이스 경계

이 스펙은 **라이브 거래 인프라**라 보수적으로 슬라이스한다:

- **슬라이스 1(이 문서)** — 의존성 없는 **프로토콜 계층 + 폴백 + 워커 연동(전송 주입형)**.
  KIS approval-key 요청·구독 프레임 생성·실시간 프레임 파싱·폴백 로직·워커 시세 소스 폴백을
  전부 구현하고, **가짜 전송(fake transport)** 으로 연결·구독·파싱·폴백을 테스트한다.
  제3자 웹소켓 라이브러리 의존을 추가하지 않는다(공급망 표면 최소, 헌법). 기본 끔이라
  라이브 워커 동작은 byte 동일.
- **슬라이스 2(후속)** — 실제 웹소켓 **전송 어댑터**(`websockets` 등 라이브러리) 주입 +
  run-live 부트스트랩에서 백그라운드 수신 태스크 기동. 라이브러리 추가는 **공급망 결정**이라
  운영자 확인 후 진행한다(라이브 머니 시스템 의존성 확장).

## 안전 경계 (비협상)

- **Kernel 터치 0건** — 커널(`worker/schedule.py`·`risk/gates.py`·`config/caps.py`) 무변경.
- **수신 전용** — 웹소켓은 주문을 내거나 취소하지 않는다. 시세/체결 사실만 받는다.
- **폴백 보장** — 연결·구독·수신 중 **어떤 예외도 격리**되어 feed 를 `available=False` 로
  내리고, 워커는 기존 REST `get_quote` 로 자동 폴백한다(거래 무중단).
- **기본 끔(옵트인)** — `WorkerSettings.realtime_feed` 가 `None`(기본)이면 워커는 REST 만
  쓴다(byte 동일, 회귀 무손상).
- **시크릿 격리** — approval-key 는 받는 즉시 `register_secret` 로 로그에서 가린다. `.env`
  의 app_key/app_secret 로만 발급.
- **dry-run/paper 그대로** — 시세 소스만 바뀔 뿐 주문 경로 무변경.

## 기능 요구사항

- **FR-031-01** — `request_approval_key(client, *, base_url, app_key, app_secret)`: KIS
  `/oauth2/Approval` 로 웹소켓 approval-key 를 발급받고 즉시 `register_secret`.
- **FR-031-02** — `build_subscribe_frame(approval_key, *, tr_id, tr_key, subscribe)`: KIS
  실시간 구독/해지 JSON 프레임(header.tr_type "1"=구독/"2"=해지 + body.input.tr_id/tr_key).
- **FR-031-03** — `parse_realtime_frame(raw)`: 실시간 프레임 파서(순수). JSON 제어 프레임
  (PINGPONG/구독응답)과 파이프 구분 데이터 프레임(`0|TR_ID|cnt|f1^f2^...`)을 구분해
  `RealtimeFrame(tr_id, fields, is_pingpong)` 반환. 형식 불량은 `None`.
- **FR-031-04** — `quote_from_frame(frame, field_map)`: 해외 실시간체결가 필드에서 종목·
  현재가·매수/매도호가를 추출(문서화된 인덱스 맵, 비양수/부족은 `None`).
- **FR-031-05** — `RealtimeTransport` 프로토콜(`send`/`recv`/`close`) + `WebsocketRealtimeFeed`:
  전송을 주입받아 연결→구독→수신 루프에서 시세 캐시를 갱신. `available`/`latest_quote(symbol)`
  노출. PINGPONG 은 에코. **모든 예외 격리 → `available=False`(폴백 신호)**.
- **FR-031-06** — 워커 연동(`worker/loop.py`): `_fetch_quote(symbol)` 가 realtime feed 가
  주입됐고 `available` 이며 캐시에 시세가 있으면 그것을, 아니면 REST `get_quote` 를 쓴다.
  `realtime_feed=None`(기본)이면 항상 REST(byte 동일).

## 합격 지표

- **SC-031-01** — approval-key 요청이 `/oauth2/Approval` 에 POST 하고 응답의 `approval_key`
  를 돌려준다(respx 목).
- **SC-031-02** — 구독 프레임 JSON 이 approval_key·tr_type·tr_id·tr_key 를 담는다. 해지는
  tr_type "2".
- **SC-031-03** — 데이터 프레임 `0|HDFSCNT0|001|AAPL^...^...` → `RealtimeFrame(tr_id=HDFSCNT0,
  fields=[...])`. PINGPONG JSON → `is_pingpong=True`. 형식 불량 → None.
- **SC-031-04** — `quote_from_frame` 가 해외 필드에서 last/bid/ask 추출. 필드 부족·비양수 →
  None.
- **SC-031-05** — feed.run() 이 가짜 전송으로 연결·구독 프레임 전송 후, 수신 프레임을
  파싱해 `latest_quote(symbol)` 캐시를 채운다. PINGPONG 은 에코.
- **SC-031-06** — 전송이 수신 중 예외를 던지면 feed 가 `available=False` 로 내려간다(폴백).
- **SC-031-07** — 워커: realtime feed 가 available + 캐시 시세 있으면 그 시세로 룰 평가,
  unavailable 이거나 캐시 없으면 REST 폴백. `realtime_feed=None` 이면 REST 만(byte 동일).

## 비목표

- 실제 웹소켓 전송 어댑터(라이브러리 의존)와 라이브 부트스트랩 기동 — **슬라이스 2**.
- 실시간 체결통보(H0 체결) → `sync_fills` 대체 — 슬라이스 2 이후(이 슬라이스는 시세 우선).
- 웹소켓 다중 세션·구독 한도 관리(KIS 41건 한도) 최적화 — 후속.

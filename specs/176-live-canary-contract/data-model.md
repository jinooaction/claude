# 데이터 모델: 증거 수렴형 실거래 검증 캐너리

## OperationalCanaryEvidence

장기 성과가 있는 기존 정확 배포 전략을 10% 운영 검증에 넣기 위한 불변 증거다.

| 필드 | 의미 |
|---|---|
| `schema_version` | 운영 증거 계약 버전 |
| `role` | 항상 `operational_canary_entry` |
| `route` | 항상 `historical-operational-canary-v1` |
| `code_commit` | 증거를 만든 40자리 Git 커밋 |
| `generated_at_utc` | 생성 시각 |
| `candidate_id` | 정확 배포 후보 ID |
| `strategy_fingerprint` | 라이브 설정의 SHA-256 |
| `data_fingerprint` | 원시 입력과 분할의 SHA-256 |
| `split` | 개발·홀드아웃 월 수와 겹침 수 |
| `cost_model` | 기본 50bp 이상과 진단 100/150bp |
| `holdout` | 월 목록, 후보·기준 원시 월별 요인, 재현 성과 |
| `checks` | 시간 분리·성과·지문·강화·대리·구현성 판정 |
| `diagnostics` | 초과수익 PSR과 비용 민감도, `alpha_confirmed:false` |
| `decision` | 운영 자격, 10% 자본, 최대 단 1, 20% 승격 불가 |
| `safety` | 주문 0건, 자본 변경 없음, 라이브 설정 변경 없음 |

## OperationalCanaryAssessment

자본 판정기가 증거를 독립 검증한 결과다.

- `checks`: 계약·역할·신선도·계보·지문·원시 숫자·위험 게이트별 불리언
- `recomputed`: 원시 요인에서 다시 계산한 CAGR·샤프·낙폭·PSR·비용 민감도
- `eligible`: 모든 운영 검증 조건의 논리곱
- `alpha_confirmed`: 항상 거짓
- `capital_fraction`: 자격 참이면 0.10, 아니면 0
- `max_rung`: 자격 참이어도 1
- `reasons`: 실패 폐쇄 원인 목록

## CapitalLadderSentinel

```text
DISARMED (rung 0, entry_route none)
  ├─ operational evidence ready ─> OPERATIONAL_CANARY (rung 1, 10%)
  ├─ factory research eligible ──> RESEARCH_CANARY (rung 1, 10%)
  └─ calibrated exploration ─────> EXPLORATION (rung 2, 20%)

OPERATIONAL_CANARY
  ├─ clean forward alpha gate ───> EXPLORATION (rung 2, 20%)
  ├─ safety failure ─────────────> DISARMED (rung 0)
  └─ live time alone ────────────> OPERATIONAL_CANARY (rung 1 유지)
```

추가 필드 `entry_route`는 `operational_canary`, `factory_research`, `exploration` 중 하나이며,
단수와 함께 자본 진입 근거를 보존한다.

## FirstOrderRevalidation

첫 실제 매수 직전에 만드는 판정이다.

- 증거 역할·신선도·커밋 계보
- 정확 후보 ID·전략 지문·데이터 지문
- 강화 검사와 체결 대리 등가성
- 최신 NAV 10% 정수 주 구현성
- 센티넬 단 1·`entry_route=operational_canary`
- KIS 계좌 정합·halt·킬스위치·정규장
- 기존 체결이 있으면 위험 축소 주문을 막지 않는 별도 분기

## WholeShareFundabilityEvidence v1.1

최신 목표와 실제 주문 계획을 같은 입력으로 재계산하는 첫 자본 상향 증거다.

- `active_target_count`, `funded_target_count`, `funded_target_ratio`: 모든 양의 목표의 진단 수와 비율
- `whole_share_eligible_target_count`: 목표금액이 현재 시세 한 주 이상인 양의 목표 수
- `funded_whole_share_target_count`: 표현 가능 목표 중 주문 뒤 1주 이상인 목표 수
- `funded_whole_share_target_ratio`: 표현 가능 목표의 자금 배치 비율, 최소 0.66
- `whole_share_ineligible_targets`: 목표금액이 한 주보다 작은 목표와 목표금액·시세 진단
- `projected_quantities`, `projected_weights`: 주문 뒤 정수 수량과 자본 대비 비중
- `l1_weight_error`, `max_leg_weight_error`: 모든 양의 목표를 포함한 25%·15% 상한
- `checks`: 양의 시세 100%, 표현 가능 목표 1개 이상, 표현 가능 목표 66%, 오차·노출 한도
- 이전 `1.0` 증거는 새 의미로 추론하지 않고 첫 자본 판정에서 실패 폐쇄한다.

## LiveExecutionEvidence

한 예약 실행의 주문·체결·정합·감사를 연결한다.

- `run_id`, `code_commit`, `started_at_utc`, `market_session`
- `sentinel`, `capital_limit`, `account_nav`
- 정화된 주문 요청과 브로커 응답
- 체결 ID·수량·가격·수수료·시각
- 주문 전후 관리 포지션과 비관리 외부 보유
- 전략 장부 동기화 결과
- 계좌 정합 결과와 불일치 사유
- 감사 장부 위치와 sidecar 실행 ID

## LiveOrderSessionGate

실주문 진입점이 실제 실행 시각으로 만드는 일회성 판정이다.

- `mode`, `dry_run`: 실제 돈을 움직이는 호출인지 구분
- `checked_at_utc`: 서버가 검사한 현재 UTC 시각
- `XNYS regular session open`: 거래소 정규장 여부
- `next_open_utc`: 닫힌 장에서 운영 진단에 남길 다음 개장 시각
- 시작부터 닫힌 장의 결과: 주문·브로커 조회·DB 마이그레이션 0건, 종료 코드 75
- 도중 마감 결과: 다음 중개사 쓰기 0건, `market_hours_gate` 거부 감사, 종료 코드 75
- `check_scope`: CLI 시작 전 검사와 실행 권한 잠금 뒤 각 실제 중개사 쓰기 직전 검사
- 종이매매·미리보기: 판정 대상이 아니므로 기존 동작 유지

## LiveOrderSessionClaim

같은 뉴욕 거래일의 GitHub 예약과 server timer를 실제 주문 한 번으로 축약하는 production 서버 장부다.

- 입력 예약: 뉴욕 현지 10:17~13:53의 GitHub 후보와 10:35~15:35의 root systemd fallback 후보
- `market_session`: XNYS가 실제로 열린 서버 현재 시각의 뉴욕 현지 날짜
- `run_id`, `source`, `code_commit`, `claimed_at_utc`: 최초 선점 실행의 신원·출처와 시각
- `source`: `github_schedule` 또는 `server_timer`만 허용
- 저장: production 비밀 경계 안의 추가 전용 파일, 파일 잠금 아래 원자 확인·추가
- 최초 실행: `LIVE_ORDER_SESSION_CLAIMED` 뒤 기존 `rebalance-once` 호출
- 중복 실행: `LIVE_ORDER_SESSION_ALREADY_CLAIMED`와 최초 run ID를 반환하고 브로커 호출 0건
- 장외·휴장: 선점하지 않고 종료 코드 75, 다음 정상 예약 기회를 소모하지 않음

## LiveOrderRetryIncidentManifest

명시적 zero-acceptance 서버 사고와 검토된 보정을 배포 코드 안에서 연결하는 닫힌 선언이다.

- `schema_version`, `incident_id`, `enabled`
- `market_session`, `first_run_id`, `first_source=server_timer`
- `first_code_commit`, `remediation_commit`
- `broker_rejection_signatures`: 종목별 닫힌 `kis_rt_cd`, `kis_msg_cd`, HTTP, 예외,
  TR ID, 거래소, 주문 구분
- 유효성: exact key 집합·형식, tracked regular file, 최초·보정 커밋이 실제 배포 코드의 조상,
  서로 다른 최초·배포 코드
- 금지: 환경 override, 임의 경로, 자유문 reason, 계좌·가격·주문 ID·비밀값, GitHub/수동 출처

## LiveOrderSessionRetryClaim

원래 거래일 선점을 보존하면서 같은 세션 복구를 최대 한 번으로 제한하는 root 추가 전용 장부다.

- `market_session`, `first_run_id`, `first_source`, `first_code_commit`
- `retry_run_id`, `deployed_code_commit`, `manifest_sha256`, `claimed_at_utc`
- 저장: root 소유 일반 파일, 배타 잠금 아래 기존 세션 행 확인 후 broker command 전에 한 줄 추가
- 상태 전이: 없음 → `RETRY_CLAIMED` → 불변. 성공·실패 모두 되돌림 없음
- 중복: 기존 행의 최초·복구 run 신원을 반환하고 broker write·fill sync·측정·정합 0건

## ScheduledLiveCanaryEvidence

GitHub와 독립된 server timer 최초 실행이 남기는 정화된 추가 전용 증거다.

- `schema_version=1.1`, `run_id`, `source=server_timer`, `market_session`
- `started_at_utc`, `finished_at_utc`, `code_commit`(현재 main),
  `deployed_code_commit`(실제 실행 HEAD), `operational_equivalent=true`, `capital_usd`
- `entry_state`, `entry_allowed`, `claim_status`
- `order_exit`, `orders_submitted`, `fills_exit`, `measurement_exit`, `reconciliation_exit`
- `result`: 거래일 선점을 얻은 실행에 대해 `completed` 또는 `partial` 중 하나. 선점 전 차단과
  중복은 journal에만 남기고 최신 성공·부분 실행 포인터를 덮어쓰지 않음
- `attempt_kind=initial|same_session_retry`, `first_run_id`, 선택적 `retry_run_id`:
  최초와 복구 실행을 구분하며 다른 출처가 broker 단계 없이 동일 신원을 관측하게 함
- 저장: `/var/lib/auto-invest-live-order/scheduled-runs/<run_id>/summary.json`
- 최신 포인터: root 소유 고정 파일에 run ID만 원자 교체하며 임의 경로나 심볼릭 링크를 따르지 않음
- 관측: SSH forced-command의 고정 `live-canary-scheduled-status [14자리 run_id]`만 최신 또는
  지정 요약을 읽음
- 금지: 비밀값, 환경 전체, 임의 로그 경로, 임의 파일 읽기, 주문 명령 노출

## OperationalRevision

server fallback이 공유 거래일 선점 전에 두 번 확인하는 실행 코드 정합 판정이다.

- `main_commit`: 검사 시점 `origin/main`의 40자리 SHA이며 첫 진입 증거와 내부 주문 요청의 기준
- `deployed_code_commit`: production 작업 트리 `HEAD`의 40자리 SHA이며 배포 감사의 기준
- `deployed_is_main_ancestor`: 배포 커밋이 현재 main의 조상인지 여부
- `changed_paths`: 두 커밋 사이의 모든 변경 경로
- `allowed_non_runtime_paths`: `*.md`, `specs/**`, `.verify/**`, `.trigger/**` 고정 목록
- `operational_equivalent`: 두 SHA가 같거나 조상 관계와 모든 경로 허용이 함께 참일 때만 참
- 실패: fetch, commit 조회, merge-base, diff, 경로 분류, 현재 main 재확인 중 하나라도 실패하면 거짓
- 감사 연결: `DEPLOY_COMPLETED`는 `deployed_code_commit`에 있어야 하며 현재 main으로 대신하지 않음

## LiveCanaryRuntimeStatus

성공·부분 실행 요약이 없을 때 독립 server timer의 발화와 조기 실패를 구분하는 읽기 전용 진단이다.

- `schema_version=1.0`, `source=server_timer_runtime`, `observed_at_utc`
- `timer`: `load_state`, `active_state`, `last_trigger_utc`, `next_elapse_utc`
- `service`: `load_state`, `active_state`, `result`, 숫자 `exec_main_status`,
  `started_at_utc`, `finished_at_utc`
- `journal_readable`: 고정 journal 읽기 성공 여부
- `recent_events`: 최근 24시간 저널 원문을 비밀값 없는 고정 사건 코드로 바꾼 최대 20개 항목
- 호출: 인자 없는 SSH forced-command `live-canary-runtime-status`
- 금지: 임의 unit·기간·필터·경로, 환경 전체, journal 전체, 주문·서비스·timer 제어
- 의미: 실패 원인 진단이며 `ScheduledLiveCanaryEvidence`나 실제 체결 증거를 대체하지 않음

## LiveCanaryOrderDiagnostics

유효한 server timer 실행이 주문 0건으로 끝났을 때 같은 실행의 결과를 정화해 읽는 진단이다.

- `schema_version=1.2`, `source=server_timer_order_diagnostics`, 14자리 `run_id`
- `planned_order_count`, `result_count`, `withheld_order_count`: 각각 0~20의 정수 건수
- `outcomes`: 허용 형식의 종목, `BUY|SELL`, 요청·라우팅 정수 수량, 닫힌 결과 상태, 안전한 gate
- `broker_rejections`: 거부 종목별 `kis_rt_cd`, `kis_msg_cd`, HTTP 상태, 예외 종류,
  `TTTT1002U|TTTT1006U`, `NASD|NYSE|AMEX`, `00|01` 또는 `null`인 고정 진단과
  `account|service_registration|trading_permission|exchange|symbol|market_session|price|quantity|buying_power|currency|order_type|other|unavailable`
  중 중복 없는 `message_topics`
- `withheld_reason_codes`: 비관리 보유·현금 부족·방향 필터·기타 보류의 고정 코드
- 입력: 최신 고정 포인터 또는 명시된 14자리 run ID의 root 전용 일반 파일
- 금지: 원문 reason·`msg1`·부분 문자열·길이·해시·응답 본문, 가격·현금·계좌·주문·상관 ID,
  임의 경로·파일·로그,
  주문·재시도·서비스 제어
- 의미: 주문 0건의 원인 분류이며 주문·체결·감사·대사 성공 증거를 대체하지 않음

## KisRestRequestProtocol

KIS production REST 호출이 공식 현재 래퍼와 공유하는 고정 요청 헤더 계약이다.

- `custtype=P`: 개인 고객 유형. 공유 헤더 빌더가 고정하며 호출자가 덮어쓰지 않음
- `tr_cont=""`: 연속 조회가 아닌 요청도 헤더를 생략하지 않고 명시적 빈 문자열로 전송
- 주문 고유 필드: 기존 `tr_id=TTTT1002U|TTTT1006U`, endpoint, `OVRS_EXCG_CD`,
  `ORD_DVSN=00`, 지정가 본문을 그대로 유지
- 적용 범위: 공유 KIS REST 헤더를 사용하는 시세·잔고·주문 호출. 주문별 우회 헤더를 만들지 않음
- production live rebalancer pacing: `rate_per_sec=5.0`, `capacity=1.0`; 첫 요청 뒤 모든
  REST 요청 시작 사이 최소 0.2초, 초기 burst 1건
- 주문 재전송: `retry_transient=false`; 5xx·전송 오류·`EGW00201`에도 같은 주문을 자동 반복하지 않음
- 로컬 증거: 모의 주문 요청의 실제 헤더와 본문을 캡처해 두 고정값과 기존 주문 계약을 함께 검증
- production 증거: 다음 자동 정규장 실행의 신규 브로커 접수·체결·추가 전용 감사·계좌 대사
- 금지: `APBK1672` 자유문 의미 추측, 원문 응답 공개, 수동 주문, 기존 거래일 선점 삭제,
  시장가·다른 거래소·hashkey의 근거 없는 추가

## KisAccountServiceRegistrationGate

정화 진단이 코드 바깥의 계좌 서비스 신청을 지목할 때 사용하는 운영자 외부 관문이다.

- production 근거: observer run `33892995912`의 IAUM·SCHX
  `message_topics=[account, service_registration]`
- 코드 건강성 근거: exact-main KIS smoke run `33893241198` 6/6, 주문 없는 preflight run
  `33893825580`의 `ENTRY_READY`, 측정 `CLEAR`, 대사 `OK`, 증거 `VALID`, 주문 제출 0건
- 운영자 확인 항목: KIS `해외증권 거래신청`, 해외 ETF용 `해외ETP 거래신청`
- 시스템 권한: 신청 상태를 정화된 주제로 진단하고 다음 자동 실행을 관찰할 수 있음
- 시스템 비권한: 본인 인증, 금융 약관 동의, 계좌 서비스 임의 활성화, 수동 주문
- 해제 증거: 다음 유효 자동 scheduler의 신규 주문 접수·실제 체결·전략 감사·같은 실행 계좌 대사

## DeployAuditObservation

exact-main 배포 여부를 서버의 추가 전용 감사 장부에서 읽는 비변경 관측 결과다.

- 입력: 없거나 8~64자리 16진수인 `correlation_id`
- 호출: SSH forced-command gateway의 `deploy-audit [correlation_id]` 고정 명령
- 이중 검증: GitHub 워크플로와 root 소유 서버 helper가 입력 형식을 각각 검증
- 읽기 경계: `/opt/auto-invest/data/auto_invest.db`를 `sqlite3 -readonly`로만 조회
- 출력: `AUDIT_STATUS`, `AUDIT_CORRELATION_ID`, `AUDIT_ROW_COUNT`, `AUDIT_TERMINAL_EVENT`
- 성공: 최신 또는 지정 감사 사슬의 마지막 이벤트가 `DEPLOY_COMPLETED`
- 금지: 원격 셸·표준 입력 스크립트·환경 접두사·DB 쓰기·systemd·git·주문 명령

## QuoteMarketResolution

미국 종목의 KIS 시세 거래소와 주문 거래소를 실제 응답으로 연결하는 읽기 판정이다.

- 후보 시세 거래소: `NAS`, `NYS`, `AMS`
- 성공: 양의 `last`를 반환한 첫 거래소와 시세를 `Quote.resolved_market`에 기록
- 미상장 표현: 빈·비숫자 시세 또는 해당 거래소 조회의 5xx는 다음 후보를 계속 조회
- 실패 폐쇄: 모든 후보 실패 중 5xx가 있으면 마지막 5xx를 전파, 모두 빈 시세면 `QuoteUnavailable`
- 인증·요청 오류: 4xx는 다른 거래소로 숨기지 않고 즉시 전파
- 주문 연결: 성공한 시세 거래소만 `NAS→NASD`, `NYS→NYSE`, `AMS→AMEX`로 변환

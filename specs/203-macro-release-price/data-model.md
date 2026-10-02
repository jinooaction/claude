# Data Model: 발표일 가격 진단

## Announcement

`family`는 `CPI` 또는 `EMPLOYMENT`, `date_et`는 동부 날짜,
`clock_et`는 `08:30:00`, `calendar_id`는 2차 달력의 출처 식별자다.
ALFRED 날짜 목록에 포함되고 정확한 미국 증시 정규장 세션일 때만
선택한다. 한 가족·날짜가 중복되면 실패한다. `status`와
`first_announced_at`은 판정 입력이 아니다.

## Observation

발표·종목·세션, 직전 세션 마지막 봉 종가, 09:45 시작 봉 종가,
09:55 진입 참조 시가, 15:55 청산 참조 시가, 세 봉의 거래량을 가진다.
정확한 직전 세션 끝 봉이 아니거나 관측/거래량이 없으면 상태와 이유만
기록한다. 음수/0 가격과 중복 타임스탬프는 실패한다.

## DiagnosticResult

입력/계약 SHA-256, 선택·제외 건수, 가족별·연도별 표본, 관측 상태,
가격쌍별 비용 전/기준/가혹 수익, 동일 가중 평균을 가진다.
`orders_submitted=0`, `actual_capital_fraction=0`, `live_eligible=false`,
`promotion_allowed=false`를 항상 기록한다. 200개 미만 참조 거래는
자료 부족, 비용 후 평균 음수는 개발 가설 탈락이다. 어느 경우에도
정식 전략 합격을 내지 않는다.

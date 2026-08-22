# Research: 라이브 증거 오염과 저회전 후보

## 확인된 원인

- `nav-snapshot --mode live`는 브로커 NAV가 아니라 전체 live 체결 장부와 `--capital`로 전략 NAV를 구성한다.
- 2026-06-23의 BHP·MRK·RELX 매도는 시스템 시작 전 외부 보유 청산이지만 live 체결로 저장되어 `$293` 전략 자본에 매도대금이 더해졌다.
- ORANY는 시작 포지션 성과에는 포함되지만 NAV 장부에는 없어 성과와 NAV의 범위가 달라졌다.
- 기존 `external-holdings.toml`은 현재 수량 정합성에는 유효하지만 이미 청산된 역사 외부 보유를 설명하지 못한다. 역사 기준은 `live-opening-positions.toml`에 남아 있다.

## 선택

- 현재 수량 정합성은 `external-holdings.toml`, 역사적 전략 제외 범위는 `live-opening-positions.toml`을 사용한다.
- live 전략 성과와 NAV는 역사 제외 종목의 체결을 제외한다.
- 측정 계약 지문은 제외 종목과 전략 범위 규칙을 해시해 생성한다.
- 과거 계약의 NAV는 새 계약의 forward·growth 표본에 섞지 않는다.

## 저회전 AI

- 기존 모델의 누수 방지·워크포워드 구조는 유지한다.
- 미세 예측 차이는 거래하지 않는 no-trade threshold를 둔다.
- 최소 보유기간 동안은 위험 비상 조건 외 교체를 금지한다.
- 배분 점수에서 예상 거래비용을 차감해 비용보다 작은 신호를 0으로 만든다.
- 새 후보도 기존보다 못하면 `NO_EDGE`가 정답이다.

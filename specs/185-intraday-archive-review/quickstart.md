# 보관 자료로 연구 검증하기

날짜별 보관 폴더가 있는 sessions와 아직 없는 출력 폴더를 지정합니다. 아래는 예시 경로입니다.

```sh
uv run python -m auto_invest.analytics.intraday_archive --archives /path/to/sessions --out /path/to/new-review
```

review.json에서 실제 완결 거래일 수와 부족분, research.json에서 기존 전략 검증 결과를
확인합니다. ledger.csv는 연구용 모의 체결이며 실제 주문 기록이 아닙니다.
원본은 바뀌지 않습니다. 기존 계좌·수집기·실주문 설정도 변경하지 않습니다.
이 명령은 정식 전진 관찰이나 실제 주문을 시작하지 않습니다.

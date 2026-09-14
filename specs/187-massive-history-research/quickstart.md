# 장기 자료 연구

개인 연구용 Massive Stocks Starter 권한과 MASSIVE_API_KEY를 안전한 실행 환경에
연결한 뒤 사용한다. 키를 채팅·명령 인수·저장소에 적지 않는다. 기존 한국투자 키는 사용하지 않는다.

```sh
uv run python scripts/massive_history_review.py --start 2023-09-07 --end 2026-09-11 --out data/massive-history-20260914
```

지정 범위의 실제 달력 일수를 검사한다. 정상 재실행은 검증한 원본 캐시를 재사용한다.
자료 수집·분석 성공과 전략 합격은 다르다. 연구 결과는 실제 KIS 운영 승인으로 쓰지 않는다.
수집 실패 시 권한 부족·손상·부분 자료 이유를 확인하고, 원본을 삭제하거나 가격을 채우지 않는다.

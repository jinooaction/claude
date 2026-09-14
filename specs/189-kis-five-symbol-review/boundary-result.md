# 한국투자 과거 분봉 경계 재확인

## 새로 확인한 공식 근거

공식 저장소의 최신 개별 함수 설명만 읽었을 때 보관 기간을 찾지 못했다.
같은 저장소의 legacy/rest/get_ovsstk_chart_price.py 첫 줄에는 해외주식 분봉이
최대 약1개월이라고 명시돼 있다. 과거 샘플 설명이므로 모든 현재 서비스의 절대
한도로 일반화하지 않지만, 실제5종목의 약1개월 반환 결과와 일치한다.

- 공식 저장소 조사 HEAD: b4e6249714418aa57833d1cbbbced39cbcc5b125.
- 기간 설명: https://github.com/koreainvestment/open-trading-api/blob/b4e6249714418aa57833d1cbbbced39cbcc5b125/legacy/rest/get_ovsstk_chart_price.py#L1
- 커서 근거: https://github.com/koreainvestment/open-trading-api/blob/b4e6249714418aa57833d1cbbbced39cbcc5b125/examples_llm/overseas_stock/inquire_time_itemchartprice/inquire_time_itemchartprice.py#L54
- dailyprice는 일/주/월 자료이고 inquire_time_indexchartprice는 지수/환율 자료다.
  고정5종목의5분 가격/거래량을 대체하지 않는다. 분 간격을 늘린 OHLC로 잃어버린
  5분 경로를 복원하지 않는다. 새 공급자/가입/비용은 추가하지 않았다.

## 보정과 실제 결과

PR832/main da57dded9236ba82bc389f15541e6d797001087f,
실행3a0cb59048ba94ba28e3a6a5458c4cf299bb23ba.
기존5분 전 커서로 빈 응답을 받으면 마지막 봉의1분 전 커서를 한 번 확인한다.
80페이지 예산, 허용 GET/종목, 비공개 원본 보존, 중복/충돌 검증을 유지했다.
관련14 passed(1.53초), 전체4769 passed/13 skipped(808.63초), 린트/하네스 통과.
전체 로그 /tmp/claude-189-boundary-full.log.13skip은12실제 인증과1가동 전 전용 검사.

실제34857636042:12 passed(114.62초). 모든 종목이 경계 대안1회 시도 후 EMPTY_PAGE.
SPY/QQQ/IWM/TLT/GLD 페이지 수는35/35/33/35/35이며80회 한도 도달이 아니다.
모두 최초2026-08-14T08:00:00Z, 정규장 최초13:30Z로 유지됐다.
공통 완결2026-08-14~09-11: 예상20/완전20/누락0.756일 중736일 부족 유지.
오늘9월14일 미완결 자료는 제외했다. 공식 연구 INSUFFICIENT_EVIDENCE,
독립 증거 검사 통과, 별도 단기36회 REPLAYED/승격 불가. 개별 손익은 조회하지 않았다.
GitHub가 QQQ 원본 개수/일부 해시를 마스킹하므로 원본 총개수를 추정하지 않았다.

서버 원본/연구/장부:
/opt/auto-invest/data/kis-history-reviews/review-1129a519dd10419eb8bbc4b7234ed7f6
로컬 요약 로그: /tmp/claude-189-boundary-live.log.
기존 일별 보관도 재검사:9월4/8/9/10/11일5일로 위20일과 겹친다.
서버에 존재하지 않는 과거 관측 자료를 만들어 채우지 않는다.

배포34857634053은 장중 연기, 다음 허용2026-09-14T20:00Z.
운영 워커 교체를 완료했다고 주장하지 않는다. 실제 읽기 검사는 새 코드 임시 공간에서 완료.
배포 로그 /tmp/claude-189-boundary-deploy.log. 실제 주문/자금 배정/승인 발급 없음.

## 결론과 남은 범위

이 경계 보정과 재검사는 완료됐다. 장기 분봉 확보와 통과 전략은 완료되지 않았다.
KIS만 반복 호출하면736일을 채울 수 있다는 근거는 없다. 한국투자 전체 서비스에서
절대로 불가능하다고 단정하지 않는다. 다른 기간 자료나 일봉을 쓰는 연구는 별도 설계와
검증이 필요한 대안이며 현재5분 전략을 통과시킨 것처럼 바꾸지 않는다.

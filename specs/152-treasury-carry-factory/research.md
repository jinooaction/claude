# Research: Independent Treasury Carry Factory

## Decision 1 - 공식 CMT 금리곡선 사용

**Decision**: 3개월·2년·5년·10년·30년 미국 국채 constant maturity yield를 사용한다.

**Rationale**: 미국 재무부는 이 금리를 최근 발행 국채의 장외시장 마감 매수호가에서 만든 일별
par yield curve의 고정 만기점이라고 설명한다. 공식 XML은 1990년부터 제공되므로 개발 구간과
2007년 이후 홀드아웃을 나눌 수 있다.

**Sources**:
- https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve
- https://home.treasury.gov/treasury-daily-interest-rate-xml-feed
- https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics/treasury-yield-curve-methodology

**Alternatives considered**:
- ETF 가격 웹 수집: 공급자 조정주가와 이용 조건에 의존하고 긴 이력의 단일 공식 원천이 아니다.
- KIS 일봉만 사용: 실거래 표현은 좋지만 현재 저장 이력으로 120개월 개발과 120개월 홀드아웃을 동시에 만들 수 없다.
- 유료 채권 총수익 데이터: 운영자가 승인하지 않은 비용과 공급자 종속성을 만든다.

## Decision 2 - rolling-par 수익의 보수적 근사

**Decision**: 월수익을 전월 수익률의 캐리와 수정 듀레이션 곱하기 금리 변화의 가격효과로 계산한다.
3개월은 이자 수익만 사용한다. 2년 이상은 장기일수록 같은 금리 변화에 더 크게 움직인다.

**Rationale**: 재무부는 bills가 1년 이하 할인증권이고 notes/bonds가 반기 이자를 지급하며,
시장 수익률이 쿠폰보다 높아지면 가격이 액면 아래로 내려간다고 설명한다. 이 관계를 레버리지
없이 재현하는 투명한 근사이며, 실제 ETF 총수익과 동일하다고 주장하지 않는다.

**Source**: https://www.treasurydirect.gov/marketable-securities/understanding-pricing/

**Alternatives considered**:
- 단순 금리/12: 장기채의 가격 변동을 빠뜨려 거짓으로 안정적인 결과를 만든다.
- 정확한 개별 CUSIP 재투자: 쿠폰, 발행, 경과이자, 교체 종목 전체 자료가 필요해 이번 공식 공개 곡선 범위를 넘는다.

## Decision 3 - 30년 공백 보존

**Decision**: 2002-02-18부터 2006-02-08까지 30년 CMT 공백을 메우지 않는다. 후보가 그 기간에
30년을 요구하면 나머지 유효 만기만 사용한다.

**Rationale**: 재무부가 30년 시리즈 중단과 재개를 명시한다. 10년이나 장기평균으로 대체하면
당시 존재하지 않은 입력을 같은 만기처럼 취급한다.

**Source**: https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve

## Decision 4 - 후보 문법과 누적 벌점

**Decision**: 첫 실행 전에 네 전략군과 다섯 이진 선택을 고정해 64개만 평가한다. 이전 공장의
256+192+64=512회를 전부 받아 총 576회 DSR/PBO에 사용한다.

**Rationale**: 결과를 본 뒤 후보를 추가하거나 실패한 탐색을 지우면 선택 편향이 커진다. 현재
문법은 자산 노출, 기간, 선택 폭, 신호 강도를 제한해 자동화 장점을 살리면서 탐색 폭주를 막는다.

**Alternatives considered**:
- 승자가 나올 때까지 무제한 검색: 우연한 승자를 거의 보장하므로 거부한다.
- 이전 512회 삭제: 실제 연구 이력을 숨겨 통계 확률을 부풀리므로 거부한다.

## Decision 5 - 이중 대조군

**Decision**: 후보는 같은 만기의 균등 국채 사다리보다 나아야 하고, 기존 주식·중기채·금
포트폴리오에 20% 섞었을 때 샤프가 0.05 이상 오르며 낙폭이 악화되지 않아야 한다.

**Rationale**: 첫 비교는 만기 선택 자체의 엣지를 분리하고, 두 번째 비교는 계좌 전체에 실제로
쓸 가치가 있는 독립 수익원인지 검사한다.

## Decision 6 - 실거래 표현과 별도 승격

**Decision**: 연구 슬리브는 `SGOV`, `SHY`, `IEI`, `IEF`, `TLT`로 표현 가능하게 설계하지만,
현재 live whitelist는 바꾸지 않는다. 완전한 승자가 생긴 뒤에만 현재가, 거래소, 정수주,
추적오차, 계좌 캡을 확인하는 기존 캐너리 절차로 넘긴다.

**Rationale**: 금리곡선 근사는 전략 가설을 시험하지만 ETF의 비용·듀레이션·추적오차를 완전히
대신하지 못한다. 연구 합격과 실제 자본 투입을 같은 사건으로 취급하면 안 된다.

# 가입 없는 외부 분봉 조사 — 2026-09-20

운영자는 한국투자 거래 계좌를 유지하고 외부 과거 자료를 먼저 조사하도록 승인했다.
조회만 했으며 가입/결제/주문/자본 배분은 하지 않았다. 프로그램의 공급자 허용 목록과
756세션 기준도 바꾸지 않았다. 이번 변경은 조사 기록이며 실행 코드 변경이 아니다.

## 실제 확보한 자료

Hugging Face ggaddam/OHLCV-1m의 공개 월별 파일에서5종목만 추출했다.
출처: https://huggingface.co/datasets/ggaddam/OHLCV-1m
고정 원본 버전: ef1551b11d8ee3e35c7521cf36deee155b43e77d.
파일: data/ohlcv_2025-07.parquet (389,718,680바이트,29,325,940행).
전체 저장소는403월 파일/84,447,702,480바이트로, README의52MB 메타데이터와 다르다.
인증 없이 HTTP206 범위 읽기가 가능했다. 범위/길이를 확인하고 종목 열부터 읽어
33요청/69,515,887바이트로 필요한5개 행 그룹만 추출했다. 실패했던 이전 실행은
80MB 검사 예산으로 중단됐으며, 이후 열 우선 조회로 정상 완료했다.

로컬 산출물: /Users/mason/Projects/claude-data-research/20260920-public-minutes/
- acquire_sample.py: 재현용 수집 코드. 공급자 코드를 실행하지 않고 Parquet만 읽음.
- 2025-07-targets.parquet:79,510행. UTC2025-07-01~07-31, 장외 포함.
- sample-audit.json: URL/버전/행수/해시/다운로드량/종목별 기간.
- quality-audit.json: 뉴욕 거래 달력과 비교한 종목별 누락/중복/OHLC 검사.
- 파일 SHA256:0555fa709333c235e83acc5aa2df6333600d3edee29fa8123e16a9c540b3b8df.

## 실제 품질 결과

거래 달력상22세션이며7월3일 조기 마감도 반영했다. 시각은UTC로 읽고 뉴욕 정규장만
분리해 비교했다. 아래 중복은 전체 시간대에서 동일 시각이 반복된 횟수다.

| 종목 | 원본 행 | 정규장 누락1분 | 중복 | 1분 시각이 모두 있는 세션 |
|---|---:|---:|---:|---:|
| SPY |17554|0|0|22|
| QQQ |18209|0|2|22|
| IWM |16020|0|1|22|
| TLT |15753|18|0|9|
| GLD |11974|3|1|20|

가격 순서 오류/0이하 가격/음수 거래량/소수 거래량/결측값은 표본에서 없었다.
다만 중복4건은 완전 동일행이 아니라 OHLCV가 서로 달랐다. 특히 IWM의
2025-07-31T18:29Z는 정규장 안에서 거래량693과62,320의 두 행이 충돌한다.
나머지 GLD/QQQ 충돌은 장외다. TLT7월1일에는18:22/18:23/18:31Z가 없다.
거래 없는 분인지 수집 누락인지는 원본만으로 확정할 수 없다. 빈 분을 만들어 넣거나
충돌행 하나를 임의 채택하지 않았다. 단순5분 집계만으로 이 불확실성은 해결되지 않는다.

업로더는 Finnhub 원천이라고 설명하지만 원천 응답/수집 시각/수정 정책은 미확인이다.
원본으로 지목한 mito0o852/OHLCV-1m과 복제본 모두 공개 API에서 gated=false이지만
license 필드와 라이선스 파일이 없다. 공개 다운로드 가능성과 이용 허용/품질 검증을
같은 의미로 해석하지 않는다. 현재 연구용 격리 표본이며 프로그램 적격 자료에 미산입.

## 다른 후보의 확인 결과

- fabhaus/equities_5m_stockprices: 공개 설명상2024-01~2026-03의27개월이며
  단독으로756세션에 부족하다. 원천은Various sources로 설명되고 별도 허용 조건
  확정이 필요하다. 전체 파일 다운로드/정규장 품질 검증은 미수행.
  https://huggingface.co/datasets/fabhaus/equities_5m_stockprices
- paperswithbacktest/Stocks-1Min-Price: API의gated=manual, 내려받기 승인에 구독이
  필요하다고 명시돼 가입 없는 경로에서 제외했다. 인증을 우회하지 않았다.
  https://huggingface.co/datasets/paperswithbacktest/Stocks-1Min-Price
- FirstRate Data: 공개 안내의 무료 분봉 표본은2주다. 장기 대체 자료가 아니다.
  https://firstratedata.com/free-tick-data
- Kibot: 무료분봉 IBM/OIH3개월, 대상5종목의756세션 자료가 아니다.
  https://www.kibot.com/buy.html
- MarketParquet: 가격표상 무료는일봉, 분봉은유료다. 구매하지 않았다.
  https://marketparquet.com/

## 다음 판단

이번 조사로 가입 없는 외부 실제 분봉 취득 경로를 확인했다. 그러나 장기 자료 확보와
전략 검증 완료는 아니다. 이 표본을 기존KIS20일에 단순 합산하지 않는다.
다음 작업은 원천/이용 조건/충돌행 수정 근거를 확인하거나 다른 추적 가능한 원본을
확보하는 것이다. 라이선스와 품질이 미확인인84GB 전체 다운로드를 먼저 하지 않는다.
공식 공급자 자료나 다른 무료 원천을 계속 탐색하되 새 결제/가입을 실행하지 않는다.

## 2026-09-20 원천 추적 후속

원본 mito0o852 최신776328445b7ac6e7815ef3a483e9c8ded1eb6d56과 복제본의
2025-07 Parquet는 동일 크기389,718,680과 동일LFS SHA256
90971731bcc3fe9ad465b82f3fc33b481a25f632b6f65f996b7ae91f0d0c9e29다.
원본에서 다시 내려받아도 해당 파일의 충돌을 해결하지 못한다. 원본은2026-03까지
늘었지만 정정 정책/허용 근거가 생긴 것은 아니다. 로컬upstream-comparison.json 보존.
공개 토론4에서 소유자는 분할 조정 자료를 향후 다른 저장소로 제공할 가능성을
언급했으나 현재 표본의 조정 완료 근거는 아니다. 가격 급락을 분할로 임의 추정하지 않는다.
https://huggingface.co/datasets/mito0o852/OHLCV-1m/discussions/4
Finnhub 약관은 제3자 재배포에 서면 승인을 요구한다. 업로더의 승인을 확인하지 못했으며
불법이라고 단정하지도 않는다. 운영 검증 채택은 계속 보류한다.
https://finnhub.io/terms-of-service

새 후보 HF Data Library를 발견했다. Hugging Face와 별개의 사이트다.
https://hfdatalibrary.com/pages/license 는편집물/문서/2022년이전 부분의CC BY4.0과
이후IEX 원천 조건을 명시한다. https://hfdatalibrary.com/pages/docs 는2022년3월 전
PiTrading 통합시세, 이후IEX 단일 거래소, split/dividend 조정을 설명한다. Clean버전은
중앙50봉 필터를 포함하므로 시점 당시 재현 가능성이 필요한 검증에 바로 쓰지 않는다.
Raw판과 출처 구간 분리/가격 조정 검증이 필요하다. KIS 거래량과 바로 등치하지 않는다.

접근 확인: 홈페이지는기본다운로드가입불필요라고 하나,다운로드화면/현재API문서는
무료계정/키를 안내한다. 실제공개symbol5종목과SPY raw 요청 모두HTTP403/error1010.
이 응답만으로 가입이 거절 원인이라고 단정하지 않는다. 로그인/키 생성/결제는 미수행.
https://hfdatalibrary.com/pages/api
Zenodo19501605는API200이나파일은5,135바이트README1개이며데이터파일은없다.
설명서도실제자료는별도사이트라고밝힌다. DOI가있다는이유로원본확보로간주하지않는다.
https://zenodo.org/records/19501605
실제응답목록은로컬hf-library-access.json에보존했다.

이번후속에서추가분봉확보/장기전략검증은없다. 무료계정연결후취득가능성과
Raw자료품질을확인하는대안은생겼지만,계정만만들면충분하다고보장할수없다.

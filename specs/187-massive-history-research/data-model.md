# 자료

plan.json: schema/provider/symbols/start/end/timeframe/adjusted. 캐시를 다른 범위에 재사용하지 않는다.
pages/*.json: 요청 신원, 조회시각, 원 응답과 그 SHA256. 인증 헤더를 기록하지 않는다.
dataset/: source.json, 종목별CSV, manifest.json. 공급자·미조정 정책을 명시한다.
research/: 기존 연구 JSON·모의 체결CSV·한국어 요약·독립 증거 판정.
완료 표식은 전체 수집/검증/연구 후 작성한다. 원본은 재실행으로 덮지 않는다.

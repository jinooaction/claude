# 명령 계약

`filing_observations.py collect --config FILE --store DIR --run-id ID`
실행 환경 SEC_USER_AGENT 필수. 임의 URL/시각/접수일 덮어쓰기 인자 없음.
기존 store 검증 후 새run을 추가. 응답/재시도 한도·실패·미시도 범위를 보고한다.
수집 코드는 커밋된 상태여야 하며 실행 중 다른 작성자는 파일잠금으로 거부한다.

`filing_observations.py collect-issuer --config deploy/issuer-filings.json --store DIR --run-id ID`
고정Microsoft보도자료RSS와최대3개선택본문만수집한다. SEC_USER_AGENT를읽거나전송하지않으며
고정된개인정보없는식별자를쓴다. 임의주소인자없음. SEC기록이있는저장소는요청전에거부한다.
selection.unselected는일반보도자료,selection.limit_skipped는선택대상의상한초과다.
반환0은선택대상의실패/상한초과없음을뜻하며전체역사성공은아니다. 출처의전체성은unknown이다.
발행사본문도export가능하지만195의검토시각과사건주장은자동으로생성하지않는다.

`filing_observations.py verify --store DIR`
모든 완료run의 계약·지문·이전연결·원문을 검증한다. 불완전/변조를 성공으로 만들지 않는다.

`filing_observations.py query --store DIR --as-of UTC --output NEW_FILE`
읽기 전용. 완료manifest와 각 verified_at 모두 기준 이하여야 노출한다. 기존 출력 덮어쓰기 금지.
없는 저장소를 생성하지 않으며, query/export 출력은 저장소 밖의 새 경로여야 한다.

`filing_observations.py export --store DIR --observation ID --output NEW_DIR`
검증된 원문과195 입력 작성에 필요한 출처/지문을 제공한다. 검토된 사건 입력은 자동 작성하지 않는다.

반환0=명령 성공,2=계약/저장 거부,3=수집 실패 또는 일부 범위 미관측.
HTTP 실패여도 유효한 실패run 저장을 시도한다. 저장 실패면 증거가 없음을 명시하고 성공하지 않는다.
stderr에는 비밀 헤더/원문/개인 연락 정보를 출력하지 않는다.

`filing_observations.py recover --store DIR --artifact DIR --run-id NEW_ID`
발행 실패 산출물의 원본 지문과 기존store를 검증해 새복구run으로 연결한다.
원래 관측/실패는 그대로 유지하며 복구결과 이용 가능 시각은 복구 완료 이전으로 소급하지 않는다.

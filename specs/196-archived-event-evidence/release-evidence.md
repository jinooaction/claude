# 구현 및 실제 자료 검사 근거

2026-09-25: 구현·관련·전체 회귀·병합·배포 확인 완료. 전체 단타 목표는 미완료다.

## 검증 범위

- 단위·실제 CLI 검사: 62 passed. 압축 손상/다중 멤버/크기 제한, 길이·지문·식별자 불일치, 중복 JSON/WARC 필드, 잘못된 시각·프로필·인용·회사 필드, 스크립트/외부 iframe 문구, UTF-8 BOM, 초·연도 경계, 뒤로 가는 로컬 시계, 출력 덮어쓰기 거부를 확인했다.
- `uv run ruff check src tests scripts/archived_event_evidence.py`: 통과.
- `uv run python scripts/agent_harness_probe.py --strict`: OK 14/14.
- `uv run python scripts/check_handoff_facts.py`: OK.
- 전체 `uv run pytest -q`: 코드1b02509 기준 4989 passed/13 skipped, 793.89초. 실행 핸들75776 종료 코드0 확인. 결과 로그 `/tmp/auto-invest-196-pytest.log`. 검사 중 후속 변경은 근거 및 HANDOFF 문서뿐이다. 생략은 실제 KIS 접속 검사12개와 가동 전 상태 전용 검사1개이며 실거래 검증 통과로 해석하지 않는다. 종료 뒤 전체 ruff도 다시 통과했다.

## 실제 월마트 보관 자료

공통 경로: `/Users/mason/Projects/claude-data-research/20260921-hf-raw/event-source-pilot-v1/issuer-source-pilot-v1/`.

`spec196-integration-v1/manifest.json`과 `report.json`을 실제 CLI로 검사해 종료 0을 확인했다.
응답은 `company-commoncrawl-v1/WMT.record.warc.gz` 그대로다. metadata는 `WMT-adjacent.range.gz`, warcinfo는 `crawler-timing-v1/prefix.range.gz`에서 CRC 검사를 마친 첫 gzip 멤버의 정확한 압축 바이트만 추출했다. 재압축·본문 수정 없이 새 폴더에 저장했고 원본은 보존했다.

| 파일 | SHA-256 |
|---|---|
| manifest.json | `7e0a16beb2b377f6dc5d6b2135384a513ffbc1559d5006b0124726830427463d` |
| report.json | `e41567212c084bd50ae233725be23735323e507027952ecef824476df65f2b45` |
| response.warc.gz | `313022909d1a2b25345231b1471574e6c0c6fdd2365b6ac887dcb2acc21cbc07` |
| metadata.warc.gz | `28f70e3f980f762415b5f511967796f2d8a87e36bec2ff5cf0c40937ba1cc891` |
| warcinfo.warc.gz | `31834172a60ff627f3a2606a42ea37d840eddbd5b6bd21ba4b54b058b5cbead8` |

본문 SHA-256: `ba7b63811d1fc5756587b918f9941f0a4fca5330d12da51de2da9748469e824a`.
색인의 SHA1 `ZVUELDW5VRI4JED72DLZEQFFI6IB77DY`, URI, 시각, 세 기록의 연결 ID가 모두 일치했다.
두 인용문(매출 및 회사 출처)이 스크립트를 제외한 본문에 존재했다.

실물 반례도 확인했다. `spec196-integration-v1/wrong-link-case-v1/`에서 실제 metadata의 Concurrent-To UUID 마지막 한 글자만 바꾸고 압축 파일 SHA-256도 새 사본에 맞게 갱신했다. CLI는 파일 지문 검사를 통과한 뒤 잘못된 응답 연결을 거부해 종료 2를 반환했고 `report.json`은 생성되지 않았다. 원본 파일 다섯 개의 지문은 전후 동일했다. `audit.json`에 결과를 보존했다. 변조 사본의 SHA-256은 `0607e35b9fbfbe9d46d4cdd59c81ba22edfdc773e02f0095963aceded05a9029`다.

공급자 기록은 `2014-03-10T00:43:42Z`; 조건부 수신 후 구간은 `[00:43:42, 00:43:43)`이고 기준점은 `00:43:43Z`이다. `fetchTimeMs=1470`은 보존하되 더하지 않았다.
현재 검사 시각은 `2026-09-25T01:44:30.728409+00:00`~`2026-09-25T01:44:30.755727+00:00`로 별도 기록됐다.

실물 검사에서 발견한 형식 차이 두 가지를 고쳤다. warc-fields 본문은 마지막 CRLF 1회 또는 추가 빈 줄을 허용하되 WARC Content-Length와 외부 기록 경계는 정확히 검사한다. HTTP Set-Cookie의 정상 반복은 오프라인 검사에서 제외하고 Content-Length 및 WARC 식별자 중복은 계속 거부한다. 각각 회귀 테스트를 추가했다.

## 병합 및 배포 확인

- PR853을 최종12f4c3e에서 merge 방식으로 병합했다. main은 `dda232fbe07638a39b46a5d93d9593ec93c00bfd`다. 원격 품질 검사36084406292 성공.
- 배포 실행36084456885 성공. 이번 배포 상관키 `0279dd91abe3af75fda78723d8aa9382`를 지정한 읽기 전용 감사36084571623도 성공했다.
- 서버 시작19372(`2026-09-25T02:01:08.874Z`)와 완료19377(`02:01:14.272Z`)가 같은 상관키와 대상 `dda232fbe076`을 가리킨다. terminal_event는 DEPLOY_COMPLETED, 기존 모드는 live다. 이번 검사 도구가 단타 실거래를 활성화한 것이 아니다.
- 최신 KIS smoke 기록은 이전main9c3acd0의2026-09-24 실행이다. 이번 커밋의 신규 브로커 검사 증거로 쓰지 않는다. 브로커 코드 변경은 없다.

## 전체 목표 잔여 조건

`WARC-Truncated: length`를 보존한다. 원문 전체 완전성, 실제 배포 커밋, 공급자 시계 정확성, 사건 처리 지연, 회사·사건 의미, 종목 연결은 미인증이다. 이 검사 결과로 기존195 기록을 소급하거나 전략을 채택하지 않는다. `strategy_admitted=false`, `live_eligible=false`다.

196 T001~T011은 완료했다. 전체181의 전략 통과·전진 관찰·단타 주문/청산 경로·실제 체결 대사는 이 입력 검사로 대체되지 않는다. 최종 보류 가격 자료는 열지 않았다. 제거 기능과 주문·자본·안전 관문 변경은 없다. 후속 작업은 지원 범위의 과거 사건 자료를 확보하고 처리 지연·종목 연결·전체 자료 범위를 명시한 연구 입력으로 연결하는 것이다. 현재23개 사건의 로컬 관측을 과거로 바꾸거나 WMT3월 보관본을2월 발표 직후 매매에 쓰지 않는다.

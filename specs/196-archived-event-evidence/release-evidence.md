# 구현 및 실제 자료 검사 근거

2026-09-25: 구현·관련 검사 완료, 전체 회귀 검사 진행 중. 미병합·미배포 상태이며 전체 단타 목표는 미완료다.

## 검증 범위

- 단위·실제 CLI 검사: 62 passed. 압축 손상/다중 멤버/크기 제한, 길이·지문·식별자 불일치, 중복 JSON/WARC 필드, 잘못된 시각·프로필·인용·회사 필드, 스크립트/외부 iframe 문구, UTF-8 BOM, 초·연도 경계, 뒤로 가는 로컬 시계, 출력 덮어쓰기 거부를 확인했다.
- `uv run ruff check src tests scripts/archived_event_evidence.py`: 통과.
- `uv run python scripts/agent_harness_probe.py --strict`: OK 14/14.
- `uv run python scripts/check_handoff_facts.py`: OK.
- 전체 `uv run pytest -q`: 실행 중. 결과 로그 `/tmp/auto-invest-196-pytest.log`; 완료 판정 전 프로세스와 최종 종료 코드를 확인한다.

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

## 판단 한계와 다음 단계

`WARC-Truncated: length`를 보존한다. 원문 전체 완전성, 실제 배포 커밋, 공급자 시계 정확성, 사건 처리 지연, 회사·사건 의미, 종목 연결은 미인증이다. 이 검사 결과로 기존195 기록을 소급하거나 전략을 채택하지 않는다. `strategy_admitted=false`, `live_eligible=false`다.

T010 전체 회귀 완료 및 T011 PR 검토·병합·배포/인계가 남는다. 전체181의 전략 통과·전진 관찰·단타 주문/청산 경로·실제 체결 대사는 이 입력 검사로 대체되지 않는다. 최종 보류 가격 자료는 열지 않았다. 제거 기능과 주문·자본·안전 관문 변경은 없다.

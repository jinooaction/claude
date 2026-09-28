# Implementation Plan: 최초 관측 원문 누적 수집

**Branch**: `codex/199-first-observed-filings` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

## Summary

SEC 회사별 submissions 목록과 지정 공시 본문을 읽기 전용으로 받아 원문·관측 구간을
누적한다. 기존195의 로컬 읽기와 의미 검토는 유지하며 수집 성공을 실적 사건으로 승격하지 않는다.
기존 공개자료 스냅샷 발행은 과거 버전을 덮어쓰므로 이 저장 방식에는 사용하지 않는다.

## Technical Context

- Python3.11, 기존 httpx·표준 라이브러리, 새 런타임 의존성 없음.
- 원격 Linux GitHub Actions에서 수집/전체 검사. Mac은 가벼운 편집·표적 시험만.
- 저장: `blobs/<sha256>`, `observations/<uuid>.json`, `runs/<run_id>.json`. 원본/관측은 불변.
- 원격 보존: 전용 `automation/filing-observations` 브랜치의 일반 추가 커밋. force-push 금지.
- 초기 CIK `0000789019`(Microsoft), form `8-K`, `8-K/A`. CIK는 현재 공식 응답으로 재확인한다.
- 1초 최소 요청 간격, 요청20초, 응답8MiB, 실행180초, 1회 최대5개 신규/변경 본문.
- 네트워크/5xx/429 최대2회 재시도, 지수 지연. 403 즉시 차단, 연속3실패 후15분 냉각을 다음 실행에도 유지.
- 첫 실행은 목록의 최근5개 대상만 수집하며 나머지는 미관측 개수/범위로 표시한다. 역사는 복원하지 않는다.
- 조건부 요청 최적화는 초기 버전에서 제외한다. 동일 바이트는 blob만 공유하고 새 관측은 남긴다.
- pytest 가짜 HTTP·가짜 시계 반례, CLI 오프라인 회귀, 원격 실제 수집2회·재조회 확인.

## Constitution Check

- I/II: 계좌·주문·거래 종목 허용 목록 무접촉. 관측 회사 목록은 매매 허용 목록이 아니다.
- III: 런타임 LLM 호출 없음.
- IV: 기존 거래 감사 로그 무접촉. 연구 관측도 기존 기록 수정/삭제 없이 추가한다.
- V: KIS 비밀값 사용 없음. SEC 요청 식별자는 실행 환경에서만 받으며 원문/로그에 출력하지 않는다.
- VI/IX/X: 후보·자격·자본 승격 없음. 수익성 실패32회 및181 미완료 유지.
- VII: 속도 제한·제한 재시도·지수 지연·지속 차단·냉각 적용. 인증 없는 조회라 토큰 갱신 해당 없음.
- VIII.A: 운영 서버 배포 제한/SSH 경계 무접촉. GitHub 연구 자동화와 기존 배포를 구분한다.
- 등급3 전체 SDD. 새 외부 API의 요청 제한·차단·재시도 경계를 구현하므로 높은 등급을 적용한다.
  기존 거래 경계는 유지한다. 되돌림은 수집 workflow 중단/명세 포인터 복원, 기록은 보존한다.
- 설계 후 재점검: 거래·안전 커널 변경 필요 없음. 새 임의 네트워크 주소 입력은 제공하지 않는다.

## Project Structure

- `src/auto_invest/analytics/filing_observations.py`: 계약·불변 저장·검증·기준시각 조회.
- `src/auto_invest/market_data/filing_collector.py`: 고정 SEC URL 생성·HTTP 제한·수신 영수증.
- `scripts/filing_observations.py`: collect/verify/query/export 명령.
- `deploy/filing-observations.json`: 초기 회사/문서/한도. 연락 정보 없음.
- `.github/workflows/collect-filing-observations.yml`: 원격 수집, 영구 보존, 진단.
- `.github/workflows/filing-observation-checks.yml`: PR 정확한 커밋 전체 검사.
- `tests/unit/test_filing_observations.py`, `tests/unit/test_filing_collector.py`,
  `tests/integration/test_filing_observations_cli.py`, `tests/unit/test_filing_observation_workflow.py`.

## Delivery and rollback

저장·조회 반례를 먼저 고정하고 HTTP를 연결한다. 쓰기 없는 수집 작업과 발행 작업을 분리한다.
원격 발행 전 이전 브랜치의 파일 제거/변경이 없는지 검사하고 non-fast-forward는 실패로 남긴다.
발행 전 원격artifact에 새 자료를90일 보존한다. 발행 실패 시 run요약에 복구 위치/기한을 남긴다.
복구는 원본artifact 지문과 기존store를 검사하고 새로운 복구run으로 게시하며 원래 관측시각을
보존한다. 기존 실패run 수정이나 이전연결 강제변경은 하지 않는다. 공개branch의 관측시각은
수집기 로컬 검증 완료의 증거이며 다른 시스템이 원격게시물을 읽은 시각을 증명하지 않는다.
자동 실행 간격은15분이며 지연/누락이 있을 수 있음을 보고한다. 실시간 SLA나 연속 관측은 주장하지 않는다.
연구 원문·관측에 계좌 정보는 없다. 기존 SEC 공개 문서만 보존하며 개인 연락 헤더는 배제한다.
원격2회 수집·검증·195 내보내기 연결을 확인한 뒤 정기 실행을 활성화한다.
PR858 인계 변경은 현재 브랜치의 부모에 있으며 병합 전 origin/main과 다시 정합한다.

## Complexity Tracking

새 저장 구조는 최신 스냅샷 교체로는 과거 관측 불변을 보장할 수 없어 필요하다.
기존195/196의 검토/보관 증거 기능, 공개 거시자료 collector, 실거래 권한 경로는 유지한다.

## 발행사 대안 구현

- 새고정출처 issuer_listing/issuer_primary를추가한다. MicrosoftCIK와URL경로를폐쇄검증하고,
  issuer_primary의accession필드는SEC번호가아닌URL의SHA256으로명시한다.
- RSS구문/제목선택·본문제목검증을독립모듈로분리한다. 원문파일과pubDate는공급자주장이다.
- SEC의한도있는HTTP처리는공유하되기본SEC연락정보검증을유지하고발행사전용고정User-Agent를쓴다.
- 별도 collect-issuer 명령·설정·누적브랜치를연결한다. SEC와각자의실패/냉각기록을이어간다.
- 위험등급3의기존전체SDD후속이며거래커널·실주문·자본변경은없다. 되돌림은발행사실행중단,
  기존두출처의자료는보존한다. 대안이SEC모든자료를대체한다는주장은하지않는다.
- 실제두실행과195연결이검증된Microsoft만15분정기수집대상으로설정한다.
  정기이벤트에는사용자입력이없으므로출처·브랜치·연락헤더세곳에서명시적으로분기한다.
  SEC는수동선택만허용하고정기실행에연락비밀값을주입하지않는다.
  일정은기본브랜치병합후에만효력이생긴다. 첫실제정기실행확인전에는가동완료를주장하지않는다.

## 누적 보존 전달 보완

실제3회 자료는10개원문/1,468,677바이트다. 매번전체누적artifact를90일보관하는방식은
중복저장량이증가한다. 복구artifact를기준목록지문·최종목록지문·새파일만담는증분으로전환한다.
기준은원격추가전용브랜치의기존파일전체이며동일파일삭제/변조는허용하지않는다.
복구에는그기준과증분이모두필요함을명시한다. 독립전체스냅샷복구기능은기존명령에남긴다.
적용은임시사본에서전체RunStore검증을끝낸후기존stage로추가한다. 다른기준/변조/누락/
알수없는파일/경로/심볼릭링크는원격게시전에거부한다. 증분상한64MiB를적용한다.
누적원문파일상한512MiB/100000개를적용하며HTTP전64MiB/32파일의다음실행여유를확인한다.
Git이력·요금의총량보증은아니며원문영역의상한이다. 도달시삭제대신명시적중단한다.
수집직전고정회사한도(SEC목록+최대5본문,발행사목록+최대3본문)의최대응답과영수증을위해예약한다.
되돌림은정기실행중단후기존전체artifact경로사용이며기존원문은보존한다.

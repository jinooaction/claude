# 무료 역사 공시 원문·접속 기록 표본

2026-09-21. 195 전체 검사 중 진행한 자료 타당성 조사다. 195의 로컬 관측 계약을
역사 공개 증거 계약으로 바꾸지 않았고 새 성과 계산·후보 선택·495일 확인 자료 조회는 없다.
고정 개발 기간 이전인 2014-01-23 Microsoft 사례 하나만 확인했다.

## 공식 근거와 실제 접근

- [SEC 공개 자료 안내](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)는
  Oldloads를 날짜별 공개 제출 원문과 헤더의 보관 묶음으로 설명한다.
  이후 삭제는 이전 일별/feed/oldload 목록에 반영되지 않지만 분기 목록은 다시 작성될 수 있다.
- [접속 기록 설명](https://www.sec.gov/data-research/sec-markets-data/edgar-log-file-data-sets)은
  2003-01-01~2017-06-30 및 2020-05-19~2025-06-30 자료를 제공하고 중간 구간은 없다고 명시한다.
  누락·추출 오류 가능성이 있어 무응답/기록 없음은 미공개 증거가 아니다.
- [변수 정의](https://www.sec.gov/files/variables-edgar-log-file-data-sets.pdf)는
  시각·시간대·CIK·공시 식별자·문서명·HTTP 상태를 설명한다.
- 명령줄의 공식 daily index GET와 로그 ZIP HEAD는403이었다. 반복 요청이나 신원 위장 없이
  Chrome의 일반 공개 다운로드로 ZIP과 Oldloads GZ를 각각 확보했다. 가입·비용 발생 없음.

## 확보한 원본

| 원본 | 바이트 | SHA256 |
|---|---:|---|
| [log20140123.zip](https://www.sec.gov/dera/data/Public-EDGAR-log-file-data/2014/Qtr1/log20140123.zip) | 133918444 | 18a8ddf85c78da7a9afd2a31ac505f5d2492d22604a4f1de375c7a7dafbaa1c1 |
| [20140123.gz](https://www.sec.gov/Archives/edgar/Oldloads/2014/QTR1/20140123.gz) | 215090485 | 34f3185b8615747421b762414ec5f17714e80b5dec17edf41688b7f73e48c5d3 |

저장소 밖 event-source-pilot-v1에 원본과 감사 스크립트를 보존했다.
접속 원본은8348343행 전체를 읽었고 ZIP 스트림 CRC 검증을 거쳤다.
Oldloads는2254570051바이트를 끝까지 읽어 gzip 무결성을 확인했다.
원본의 접속자 주소는 별도 보고서나 저장소에 내보내지 않았다.

## 일치한 사건

공시 식별자 `0001193125-14-018629`는 Oldloads에서 정확히1건이었다.
CIK `0000789019`, 회사 MICROSOFT CORP, 8-K, Items2.02/9.01, 제출일20140123을 확인했다.
보존한 전체 제출 레코드225351바이트의 SHA256은
`c8af4a4972ef1ca36969b1df6190d3b8423f00135948e4de74783e42bbb70ced`다.
문서에는 8-K `d661449d8k.htm`와 EX-99.1 `d661449dex991.htm`가 포함된다.
본문의2013-12-31 보고 기간도 확인했다. 현재 SEC 8-K 설명과 같은 사건이다.

접속 기록에는 해당 식별자354행이 있었다. 상태200은334행,404는2행,301은4행,
0은3행,304는11행이었다. index=0인 EX-99.1의200응답은87행이며 첫 원시 time은
`21:07:18`, zone은 `0.0`이다. 8-K의200응답은45행, 첫 time은 `21:07:16`이다.
원본 헤더는 설명 문서의 doc와 달리 `extention`이라는 열 이름을 사용한다.
v1조사는 이 차이로 문서명 필드가null이었고, v2에서 원본 열 이름을 보존해 바로잡았다.
동일 문서에서도 size 값이 여러 개이므로 byte 수만으로 전달 본문의 동일성을 인증하지 않는다.

## 시각 의미와 남은 검증

[2014 PDS 기술 명세 2.1절](https://www.sec.gov/info/edgar/specifications/pds-dissemination-spec030314.pdf)의
256바이트 제어 블록 정의에 따라 원문 접수일/수락일20140123, 수락시각160607,
생성시각160608을 읽었다. 수락/생성은 공개·다운로드 완료 시각과 구분한다.
같은 명세의 TIMESTAMP 태그는 접수 후 정정 배포용이며 모든 일반 공시의 공개 초가 아니다.

이번 표본은 과거 문서의 날짜별 보관과 해당 문서 요청 성공이 함께 존재함을 보여준다.
그러나 접속 로그 시간대 표현·요청 시작/완료 의미, 정정/재전송 처리, 보관본과 실제 전달
본문 연결, 전체 회사·기간 누락 범위는 아직 검증하지 않았다. point_in_time_eligible=false다.
정확한 최초 공개 시각을 추정하거나 임의 지연을 붙여195 import의 과거 관측으로 넣지 않는다.

후속 판단은 이 표본을 바탕으로 독립적인 역사 공개 근거 계약이 가능한지 확인하는 것이다.
일별 자료는 커서 단순히 전 기간을 받기보다 고정 회사·사건 목록을 먼저 확정해야 한다.
출처 범위나 비용을 이유로 합격 기준을 바꾸지 않는다.

## 재현 파일

로컬 기준 폴더: `/Users/mason/Projects/claude-data-research/20260921-hf-raw/event-source-pilot-v1/`.

- audit_sec_log.py → log20140123-audit-v2.json. v1은문서명 누락 진단으로 보존.
- audit_sec_oldload.py → oldload20140123-audit-v1.json 및 msft-20140123-oldload-submission.bin.
- 기존 원문·출력은 덮어쓰지 않는다. 두 감사 실행은 종료 코드0으로 완료됐으며 재다운로드는 불필요하다.

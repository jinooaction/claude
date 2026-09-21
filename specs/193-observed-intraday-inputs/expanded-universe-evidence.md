# 당시 종목 목록과 추가 원본 확보 근거

2026-09-21, 전략 수익률 조회 없이 자료 확보·품질만 검사했다.
로컬 근거 폴더: `/Users/mason/Projects/claude-data-research/20260921-hf-raw/`.

## 공개일

SEC 공식 분기 목록 `https://www.sec.gov/Archives/edgar/full-index/2014/QTR1/master.idx`
에서 accession0001193125-14-065112의 공개일2014-02-24를 확인했다.
문서 작성일2014-02-20과 구분한다. 목록 원본 SHA256은
`c2b7e77c5a94caf676b059cae5c7859e42777e2c7067d126e0db92eb2198e984`.
근거는 sec-2014-q1-master.idx 및 historical-universe-publication-evidence-v1.json.
historical-universe-inventory-v2.json은 이 확인을 반영하며 v1을 보존한다.

## 취득 및 검사

다운로드4152는 exit0/28_MEMBER_DOWNLOADS_COMPLETED로 종료했다.
기존 DD/RTX와 합쳐30개 후보 파일,1,253,569,246바이트,69,042,717행.
감사6950 exit0:전체 파일을 실제로 열고 원본 SHA를 확인·보존했으며
비정상 값0,중복 시각0,미확보 파일0이다.
원본 스키마에는 회사 식별자가 없어 이 결과만으로 역사적 회사 연결을 인증하지 않는다.
UTX의 후보 파일은 RTX이며 mapping_accepted=false를 유지한다.

달력 검사40206 exit0:PiTrading만2014-03-01~2020-03-06을 점검했다.
30파일 모두1515거래일에 정규장 관측이 있고 통째로 누락된 날은 없다.
누락 분봉 합계19262개, 모든 종목의 공통 완전 거래일48일,
최장 연속4일(2020-03-02~2020-03-05)이다. 날짜를 삭제하거나 가격을 채우지 않았다.
이는 완전일만 골라 연구하면 표본이 크게 줄어든다는 자료 품질 근거다.

재현 자료와 명령:
- audit_available_members.py → available-members-audit-20260921T025454Z.json.
- audit_identity_calendar.py --manifest 위파일 --output 새로운파일.
- 결과 all-30-calendar-audit-v1.json. 기존 출력은 덮어쓰지 않는다.
- 실행 환경은 저장소 uv 환경에 --with pyarrow를 추가했다.

## 남은 작업

회사 변경 전후 가격 연결, 새 전략의 사전 계약과 평가가 남았다.
입력 자료 확보는 전략 합격, 실계좌 수익률, 체결 동등성의 증거가 아니다.
기존29후보 실패와 추가 거래량 가설 실패를 보존하며 최종확인495일 성과는 미개봉이다.
기존 주문 권한·자본·허용종목은 변경하지 않았다.

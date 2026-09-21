# CLI 계약

replay --manifest PATH --output NEW_DIR:봉인후보와30원본목록/지문/기간검사,
기준/가혹 비용 재생,manifest/code/contract지문,결정/관측/현금장부 출력.
verify --result DIR:원본결과를수정하지않고별도산술로잔고·보유·결제·손익을검사.
exit0은계산/검사성공,exit2는입력오류. 전략탈락은정상결과다.
기존출력거부,네트워크·주문·비밀값조회없음. 명령은구현전이다.

입력 manifest는193의필드(schema_version,symbols,start,end,calendar,files)를
유지하되schema_version=2다. 각파일에original_sha256,file_symbol을추가한다.
provider=hfdatalibrary-pitrading,adjustment=source-split-dividend-adjusted,
issuer_lineage_status=unverified를고정한다. original_sha256은봉인원본해시,
sha256은변환CSV해시다. CSV는동일193칼럼이며symbol은원래구성종목명이다.
UTX파일의file_symbol은RTX이고,이는회사연결인증을뜻하지않는다.
입력을디스크스냅샷으로복제하며해시확인후날짜별관측으로읽는다.
성과실행전변환CSV manifest지문도결과의입력증거로보존한다.

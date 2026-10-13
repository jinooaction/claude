# 자료 구조
기대 JSON 정확 필드: schema=1, scope=EXPECTED_INSTALLED_TREE, entries(1..16384).
디렉터리: path/kind=directory/mode. 파일: path/kind=file/mode/size/sha256.
정규 상대 POSIX path는 구성별 ASCII 영문/숫자/점/밑줄/더하기/하이픈만 지원한다. 공백/제어문자/상위경로/빈 구성 금지. 중복·대소문자 별칭 금지, 모든 부모 디렉터리를 명시한다.
mode0..0777 정수/size0..256MiB 정수/sha256 소문자64hex/합계1GiB 이내. 빈 디렉터리도 비교하며 루트 권한은 비교 범위 밖이다.
두 관측은 전체 항목·dev/inode/mode/size/mtime_ns/ctime_ns를 비교한다. 파일 전문 출력0.
결과 schema1/scopeLOCAL_INSTALLED_TREE_COMPARISON/statusMATCHED|MISMATCH|UNAVAILABLE/reason 코드/compared_entries·bytes/declared_tree_files_compared.
항상 declaration_authenticated/runtime_closure_verified/continuous_immutability_verified/registration_verified/live_eligible/promotion_allowed=false,
program_readinessNOT_ASSESSED/orders_submitted0.

# 자료 구조

ExpectedContext(schema1/scopeEXPECTED_LOCAL_FROZEN_CONTEXT): commit40자리/tree40자리/lock_sha25664자리/python_version 정확패치버전,
modules[{name,relative_path,sha256}] 최대16, dependencies[{name,version}] 최대32. 키 집합은 폐쇄형, 이름 중복/비정규 경로/중복 JSON키 거절.
RuntimeObservation: sys.prefix/Python버전/검색되는 최상위 모듈 origin/설치 메타데이터 버전·위치. 명령줄 호출은 자동 조회하며 임의 관측파일을 받아들일 옵션은 없다.
ContextResult: scopeLOCAL_FROZEN_CONTEXT_PREFLIGHT, statusMATCHED/MISMATCH/UNAVAILABLE, 제한된issues,
expected_sha256/검사boolean/authorityfalse/orders0/readinessNOT_ASSESSED. 절대경로·값 전문을 출력하지 않는다.
Git HEAD/tree/dirty/untracked/detached와 lock/모듈 파일 지문을 전후 재비교하며 변경은MISMATCH다. 단일 관측이며 지속 잠금은 아니다.

# 진단 상태 범위 보정 검증

## 확인한 오류와 범위

기준main d05b3b7764e3d61cf5774e9edf7cc71ea3370ef1과 서버 관측36980403386은
모의timer active·service success·10월1일원본 COMPLETE를 확인했다. 그러나
1.0 보고서의고정BLOCKERS는 HISTORY_756_SESSIONS_REQUIRED와
LIVE_ADAPTER_NOT_IMPLEMENTED를 포함했다.189의1645세션확보와182/184실행
엔진 존재를 직접 읽어,진단 서비스가 전체 프로그램을 판정한 것처럼 보이는 오류를
확인했다. 진단qualified_forward_sessions=0·실주문0은 그 서비스의 값이며
실거래 준비가 됐다는 증거는 없다. 전체181 T013~T016은미완료다.

## 구현과 작은 반례

기존181 명세FR015~018·계획·작업의보정이며 위험등급2다. 신규거래기능/새승격
경로를 만들지 않고 기존 전체회귀workflow의빠진 상태/시험/관측 경로만 등록한다.
상태1.1은scope=DIAGNOSTIC_PAPER_SERVICE,
program_readiness=NOT_ASSESSED와진단전용·미평가BLOCKERS를고정한다.
정확한옛1.0은메모리상보기로만변환하고source_schema_version=1.0을명시한다.
옛파일원문은수정하지않으며미확인버전·범위·필드·권한은INVALID_STATUS다.

수정전실제시험은7 failed/14 passed/3 deselected(3.18초)였고,보정후
관련21 passed/3 deselected(1.88초),전체src/tests린트·git diff --check·
하네스14/14·HANDOFF사실·두workflow YAML 검사가통과했다. 반례는
새/옛CLI의원본바이트보존·위조된실행범위/READY/60세션/실주문/승격거절·
미래/오래된상태·비밀값차단·새코드epoch의옛paper.db/원본보존을포함한다.
코드지문변경으로새진단디렉터리를쓰는기존FR013은유지한다. 실제서버옛
디렉터리의모든파일을조회한것이아니며생산보존전체를직접확인했다고주장하지않는다.

## 원격 전체 검사와 출시

정확한최종코드의원격전체pytest/ruff·병합·서버배포감사·새1.1원본생산자
현장관측은후속대기다. 새관측은1.0의보기변환만으로성공하지않으며현재코드
지문과원본생산자1.1·범위/미평가값·실주문/승격거짓·자격세션0을대조한다.
되돌림시이전읽기는1.1을거절하다가이전코드의다음예약이1.0을발행하면복구한다.
실제주문·자본·전략·수집제한·Kernel·실거래권한변경0건,무거운로컬검사0건이다.

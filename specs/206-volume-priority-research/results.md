# 현재 검증 기록

## 성과 조회 전 봉인

사전등록 커밋 `39dc9de601c244cd633b4af353bb42991c436294`를 원격 브랜치에
푸시하고 PR877을 초안으로 만들었다. 계약 지문은
`0eb8c1b04bacb8e347f0fc1708d7b392cb37b8526ffe6b18a57d388716546a85`다.
194 계약·inventory·실제 입력 manifest의 지문을 다시 대조했다. 첫 봉인 시점에는
새 가격 재생·새 성과 계산·최종 확인 구간 조회·연구 키 발급·자료 암호문 생성이 없었다.

## 핵심 순서 구현

새 모듈 부재의 시험 수집 실패를 먼저 확인했다(0.91초). 구현 뒤 최초 관련51개는
9.06초에 통과했다. 시험의 lambda 할당 린트 지적은 def로 보정했다. 기존194 공개
실행을 실제로 호출해 내부 원래 순서 실행과 결과·장부 전체가 같음을 추가 검사했다.
계약 변조·공개 실행에 우선순위 옵션 추가 거부·부분 매수 반례 뒤 최종 관련
**54 passed/9.03초**, 전체src/tests 린트와git diff --check가 통과했다.

```sh
nice -n 19 uv run pytest -q tests/unit/test_volume_priority_research.py tests/unit/test_sparse_opening_research.py tests/integration/test_sparse_opening_research_cli.py
nice -n 19 uv run ruff check src tests
```

같은 시각5개 합성 신호와최대4보유의 실제 연구 예약/참조 체결/청산/미결제 장부에서
기존은 AAA/BBB/CCC/DDD, 새 순서는 EEE/DDD/CCC/BBB를 선택했다. 두 비용31/40bp,
1주만 부분 매수 가능한 조건에서도 예약을 해제하고 현금 음수 없이4거래를 청산했다.
같은 후보의 재현이고 새로운 실자료 성과가 아니다. 미래/과거 시각 혼입·상대거래량
NaN/무한대/잘못된 형식·중복 종목·다른 원본 정체성은거부했다.

명세/계획/작업 포인터와엄격 하네스14/14·HANDOFF 사실·PR 본문 품질 검사는
봉인 시점에통과했다. 원격PR 품질 검사37040968670도39dc9de6에서성공했다.
이 검사는 전체 회귀·전략 수익·비밀 전달 경계의 구현 완료를증명하지 않는다.

## 현금·암호문·명령 구현과 실제 원본 준비

기존194 실행과새 순서 양비용의현금 부족·미체결 예약 반환 뒤시도권 재사용 금지·
부분 청산 중 신규 진입 차단·누락분봉 수량0을확인했다. 작은 합성 CSV에서 실제
CLI 재생·현금 산술·전체 원본 재계산을 수행했고, 지문/현금 장부를 일관되게 위조한
결과도 원본 재생 비교가 거부했다. 합성 자료의결과는전략합격 근거가 아니다.
잘못된키·인증 태그/AAD·중복nonce/JSON·원본집합·크기/압축팽창·최종/중간
심볼릭링크·일반파일아닌FIFO·완료영수증누락·덮어쓰기·비밀/연락처비출력도검사했다.
macOS의시스템/var별칭은 새로만든개인 임시폴더에서만 정규경로로 바꾸고,
신뢰하지않는입력 경로는각디렉터리의O_NOFOLLOW 검사로우회하지않는다.

```sh
nice -n 19 uv run --with-requirements scripts/volume-priority-requirements.txt pytest -q tests/unit/test_volume_priority_research.py tests/integration/test_volume_priority_research_cli.py tests/unit/test_sparse_opening_research.py tests/integration/test_sparse_opening_research_cli.py
nice -n 19 uv run ruff check src tests scripts/volume_priority_research.py
```

최종 관련87개/10.01초와린트가통과했다. 이중새암호문/CLI 반례29개는고정연구
실행환경에서생략없이실행했다. 전체pytest는원격에서아직실행전이다.

원본은30종목1070241004바이트, 최대파일41442955바이트다. 입력manifest의
고정지문3ec002d68f0b62af9d9c0379eb829f4a5e22376b2993a701d134db2e5fb6046c와
각CSV지문을 대조한뒤낮은우선순위·1MiB당0.05초쉼으로gzip/AES-256-GCM 준비했다.
암호문244235959바이트,목록지문839ff5bb0a9de5f4ccad085b44a17ee9fe8cc89714e991756439d081d8e4bc88.
별도 [연구 자산](https://github.com/jinooaction/claude/releases/tag/research-206-input-v1)은
34개/244260329바이트이며34개모두원격업로드SHA-256/크기와로컬지문이일치한다.
가격없는4영수증만Git에보존했다. 연구키는0600개인파일과새전용비밀설정에만보관했고,
2026-10-02 18:07:45UTC 등록을확인했다.SEC/계좌/증권사키를연구작업에주입하지않는다.
실제 원본 준비는가격성과를계산하거나최종확인구간을읽지않는다.

새workflow는동일저장소·등록실행주체·운영자가정한정확한검토SHA가일치할때만
연구키를사용한다. 일반전체검사는키없이고정연구의존성과암호화반례미생략을확인한다.
YAML구조·읽기전용권한·키사용단계1곳·SEC/증권사키미주입을검사했다.
엄격하네스14/14·HANDOFF사실·본문품질도통과했다. 실제 원격결과는아직없다.

## 미완료 범위

T013~T016의 원격 실제 재생/독립 재계산·전체검증/인계는 미완료다.
초안은 병합하지 않았다. 구현된 연구 도구와자료 준비만으로전체181
T013~T016·통과 전략·60세션 전진·실주문·자본 배정을 완료하지 않는다.
기존205 PR876과원본/결과는 보존한다. 연구 소프트웨어출시와후보 통과는별개다.

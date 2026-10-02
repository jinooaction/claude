# 검증 순서

1. `contracts/preregistration.json` 커밋 지문을 성과 확인 전에 고정한다.
2. 작은 합성 반례로 순서·동률·미래 정보·194 보존을 검사한다. 합성 결과는 전략 합격 근거가 아니다.
3. 원본 manifest와194의 모든 입력 지문을 대조하고 낮은 우선순위·속도 제한으로 새 암호문을 준비한다.
4. 원격의 정확한 검토 코드에서 복호화·입력 검증·두 비용 재생·독립 장부 재계산을 수행한다.
5. 원격 전체 pytest/ruff·엄격 하네스·HANDOFF 사실·PR 품질을 확인한다.
6. 실제 결과와 코드·계약·장부 지문을 보존한다. 후보 탈락이면 그대로 기록한다.

명령줄은 다음과 같으며 키는 `SPARSE_RESEARCH_INPUT_KEY` 비밀 환경에서만 받는다.
`uv run --with-requirements scripts/volume-priority-requirements.txt python scripts/volume_priority_research.py stage --manifest <원본_manifest> --output <새_암호문_경로>`
`uv run --with-requirements scripts/volume-priority-requirements.txt python scripts/volume_priority_research.py replay --fixture <검증된_암호문_경로> --output <새_결과_경로>`
`uv run --with-requirements scripts/volume-priority-requirements.txt python scripts/volume_priority_research.py verify --fixture <검증된_암호문_경로> --evidence <결과_경로>`
마지막 명령은 현금 장부를 독립 계산하고 원본 전체를 다시 재생해 결과/장부 지문을 비교한다.
키를 채팅이나 코드에 붙여 넣지 않는다. 실제 원격 개발 재생/전체 원본 재계산은
e1566818의37046328250에서 완료했고 후보는 DEVELOPMENT_REJECTED다.
최종58e4d423의37052020849도5278 passed/13 skipped·암호화/명령29개 무생략과
린트를 통과했다. 원래 장부와 최종 XML은 각각 별도 결과/검사 자산에 보존했다.
새 실제 재생을 불필요하게 반복하지 말고 results.md와 evidence/의 지문을 확인한다.
기존194/205·원본·결과는 유지하며 최종 확인495세션과 전체181 관문은 별도다.

# HANDOFF 018 — 스펙 012 튜너 L2/L3 → 하드닝 캐너리 자동 투입 출시 (2026-05-26)

PR #67 머지 커밋 `943c08b`. 자율 튜너(스펙 005)의 측정→분석→행동 루프에서
"위험한 변경을 안전 게이트로 검증하는 팔"을 닫았습니다.

## 한 줄 요약

그동안 튜너의 L2/L3 후보(모델·토큰 같은 위험 변경)는 `runner.py`에서 감사 로그 한
줄만 적고 버려지는 **빈 껍데기**였습니다. 비용·지연 드리프트의 수정 지점인 모델
라우팅(`judgment/registry.py`)은 분류기가 올바르게 L2로 강등하는데, 그 L2 경로가
죽어 있어 감지된 개선이 갈 곳 없이 사라졌습니다. 스펙 012는 그 후보를 **스펙 007
하드닝 캐너리로 자동 투입해 검증**(과거 리플레이+합성 충격+퍼즈)하고 합격/불합격을
기록합니다.

## 무엇을 만들었나

- **판단 튜닝 표면 신설(비커널)**: `config/judgment_tunables.toml` + `registry.py`
  폴백 로더. 파일/키 없으면 현재 하드코딩 `max_tokens` 와 동일 → **런타임 동작
  무변경**(안전). 바닥값 클램프(JUDGMENT_MAX_TOKENS_FLOOR=32).
- **후보 구체화**: `tuner/candidate.py` `build_canary_candidate` — L2/L3·비커널·
  `max_tokens_reduce` 후보만 `CanaryCandidate`로 구체화(결정론, 권장 tier/window).
- **드리프트→노브**: `detect.py` 의 `cost_drift`·`latency_degradation` 가 가장 비싼
  판단 지점의 `max_tokens` 축소를 제안(L2 캐너리 대상). `cache_miss` 는 노브 없어
  proposal_only 유지.
- **캐너리 자동 투입**: `tuner/canary_submit.py` — git plumbing(`commit-tree`)으로
  임시 후보 rev 생성(작업트리·인덱스·HEAD·브랜치 미변경, ref 미생성, **origin
  미푸시**, 임시 인덱스 정리) → `run_canary` 호출 → 합격/불합격 기록. 리플레이 데이터
  없으면 skip(fail-safe), 캐너리 예외/내부오류는 internal_error 로 격리(미전파).
- **감사(K4 추가-전용)**: `AUTO_TUNED_CANARY_CANDIDATE`·`AUTO_TUNED_CANARY_VALIDATED`
  2종. 커밋 `01b821e`. 기존 이벤트·마이그레이션 무수정.
- **리포트·CLI**: 튜너 리포트에 `canary_candidates`·`canary_validations` 섹션(schema
  1.1) + "라이브 미승격(운영자/스펙 006 게이트)" 표식. `auto-invest tune` 사람용
  요약 줄 추가.

## 안전 경계 (불변)

- **캐너리 검증 = 시뮬레이션**(과거/합성 데이터)이지 실거래·실배포가 아니다.
- **합격해도 라이브 자동 승격 0건** — `CanaryValidationResult.promoted` 는 코드 경로상
  항상 False(감사에 박힘). 라이브 승격은 운영자/스펙 006 배포 게이트 전용(헌법 IX.B-2).
- Kernel 터치 후보는 기존대로 L4 강등 → 캐너리 자동 투입 제외.
- **K4 추가-전용 1건(`01b821e`)** 외 Kernel(K1·K2·K3·K5·K6·K-meta) 터치 0건.

## 테스트

전체 942 통과·4 스킵(라이브 KIS, `KIS_LIVE_TEST=1` 게이트), 린트 깨끗. 신규: 후보
구체화·max_tokens 노브·config 폴백·git plumbing(작업트리 무변경·dangling·정리)·
fail-safe/오류격리/결과매핑·파이프라인 통합(passed/failed/skipped + 멱등)·승격 0건
불변·결정론.

## 다음 후보 (스펙 012 이후)

- **L1 적용 표면 확장**: 스펙 012가 캐너리 검증 경로를 깔았으니, 모델 라우팅·max_tokens
  를 즉시 자동 적용(L1) 노브로 승격하는 것을 검토 가능(여전히 신중히 — 품질 영향).
- **L2/L3 합격 → 운영자 승격 큐**: 캐너리 합격 후보를 운영자가 한눈에 보고 승격 결정할
  수 있는 큐/대시보드(자동 승격은 여전히 운영자 게이트, 헌법 IX.B-2).
- **모델 교체 노브**: Haiku↔Sonnet 라우팅 변경을 캐너리 검증 대상으로(현재는 max_tokens
  만; 모델 교체는 품질 영향이 더 커 v1 범위 밖이었음).
- **실거래 전환**: `AUTO_INVEST_MODE=live` (운영자 명시 지시 필요, 돈 움직이는 행동).

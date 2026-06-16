# 스펙 051 — 자율 파이프라인 생존 감시 (사이드카 정지 watchdog)

## 한 줄 요약

자율 시스템을 굴리는 여러 스케줄 워크플로(전진 페이퍼·자본 사다리 게이트·KIS smoke·
라이브 캐너리·수집·층화·승격)의 사이드카 `timestamp_utc` 를 한 곳에서 읽어, 어느 하나가
기대 주기보다 오래 멈췄으면(STALE/MISSING) 빨갛게 실패(loud)시키는 단일 감시자. 읽기
전용·돈 0 이동.

## 동기 (운영자 상시 지시)

운영자(2026-06-13): "세계 최고 수준의 사람 개입 없는 완벽한 자동 시스템 + 세계 최고
수준의 안정성." 그런데 지금까지 **"전체 파이프라인이 살아있나"를 보는 단일 감시자가
없었다.** 각 워크플로는 *자기* 사이드카에 *자기* 타임스탬프만 찍을 뿐이다.

이게 위험한 이유 — 침묵 정지: 예컨대 전진 페이퍼(`rebalance-paper-forward`)가 조용히
멈추면(시크릿 만료·서버 SSH 단절·GitHub 60일 비활동 스케줄 정지) 전진 엣지가
*얼어붙는데*, 자본 사다리 게이트는 계속 `WAIT_EDGE`(단 0, 자본 0%)만 보고한다. 그래서
"정상 누적 중"과 "2주 전 죽어서 정지"가 겉보기로 **구분되지 않는다.** 이 프로젝트가
반복적으로 물렸던 "침묵 실패"(스펙 X.2 단일 잣대 구멍 ①②의 조용한 현금 곡선과 같은
부류)다.

## 매 실행마다 답하는 것

각 핵심 사이드카에 대해:

1. **마지막으로 언제 갱신됐나** — 사이드카 본문의 `timestamp_utc` 를 읽어 나이(h) 계산.
2. **그 나이가 정상 범위인가** — 사이드카별 `max_age_hours`(평일 스케줄은 주말 갭을
   견디는 80h, 매일 스케줄은 한 번 미스 허용 30h)에 비춰 등급:
   - OK: 한계 이내 · LATE: 1~2주기 지연 · STALE: 2주기 초과(정지 의심) · MISSING: 없음.
3. **종합 판정** — 최악값. *핵심* 사이드카가 STALE/MISSING → CRITICAL(워크플로 빨강).
   연구/보고 트랙은 저하(DEGRADED)로만(거짓 경보 최소화).

## 범위

- `src/auto_invest/analytics/pipeline_liveness.py` — 순수 코어. `SidecarSpec`(명세),
  `assess_liveness(specs, observations, now) → LivenessReport`, `parse_timestamp_utc`,
  `default_specs()`(레지스트리). 결정론·비커널.
- `scripts/pipeline_liveness_probe.py` — 드라이버. 워크플로가 git show 로 모은 사이드카
  디렉터리를 읽어 판정·출력(text/json). `--manifest`(레지스트리 단일 출처) / `--strict`
  (CRITICAL 시 비정상 종료) / `--now`(테스트용) 지원.
- `.github/workflows/pipeline-liveness.yml` — 매일 07:30 UTC(밤 배치·smoke·수집 이후).
  automation/* ref 를 fetch → 사이드카 git show → 판정 → 사이드카
  `automation/pipeline-liveness-last-run` 발행 → **CRITICAL 이면 빨갛게 실패.**
- 단위 + 통합 테스트. FINDINGS.

## 핵심/비핵심 구분 (레지스트리)

- **핵심(critical=True, STALE→CRITICAL→빨강)**: 자율 머니루프의 직접 경로 —
  `rebalance-paper-forward`(전진 엣지 관측 생산), `edge-autoarm`(자본 사다리 게이트),
  `kis-smoke`(브로커 생존), `rebalance-live-canary`(라이브 NAV 스냅샷 = 무장 시 드로다운
  감지의 눈).
- **비핵심(critical=False, STALE→DEGRADED, 빨강 아님)**: 연구/보고 + fail-safe 결정 루프 —
  `collect-public-data`, `regime-stratify`, `promote-readiness`, `money-path`, `reassign`.
  멈춰도 돈 경로 무관. 특히 `reassign`(스펙 055 자율 전략 재지정, 평일 00:20 UTC)은
  정지하면 검증된 incumbent 전략이 그대로 라이브로 남는 fail-safe 라 비핵심이지만,
  *가장 최신 자율 루프이므로* 침묵 정지가 반드시 드러나야 해서 감시 대상에는 넣는다
  (저하로만 — 거짓 빨강 금지).

### 레지스트리 감사 (스케줄 루프 vs 감시 대상)

생존 감시는 *스케줄(cron)* 루프만 본다 — 멈춤=비정상이 의미를 갖는 건 정기 실행 루프뿐이기
때문이다. `go-live-canary`·`forward-anchored-verdict`·`release-halt` 는 수동/이벤트 트리거라
평소 idle 이 정상이므로 일부러 제외한다(넣으면 거짓 경보). 스펙 055 머지 시점 기준, 스케줄
루프 중 감시 사각지대는 `reassign` 하나였고 위에서 메웠다.

## 비목표 (안전 경계)

- **읽기 전용·측정 전용** — 주문 0건, 돈 0 이동, Kernel 터치 0건. 거래·자본·전략 변경
  없음(라이브는 운영자 게이트, 헌법 X.4).
- **돈을 지키는 게 아니라 정지를 드러내는 것**. 얼어붙은 엣지는 자본 측면에서 이미
  fail-safe(EDGE_CONFIRMED 를 못 만들어 절대 승격 안 함). 돈은 자본 사다리 게이트의
  fail-closed + 스펙 014 서킷 브레이커가 지킨다. 이 감시자는 가시성 계층이다.
- **감시자가 무언가를 자동으로 끄지 않는다** — AUTOARM 비활성화 같은 머니루프 개입은
  하지 않는다(자체가 footgun). 탐지·보고·빨간 실행까지가 이 스펙의 고도.

## 감시자의 backstop (누가 감시자를 감시하나)

감시자 자신이 죽으면 빨간 실행이 안 뜬다. 그래서 사이드카
`automation/pipeline-liveness-last-run` 의 신선도 자체가 backstop이다 — `/sync` 또는
컨테이너 세션이 이 사이드카가 오래됐는지 보면 감시자의 정지를 잡는다. 또한 이 워크플로는
의존성이 가볍고(git + python, SSH·외부 시크릿 불필요) SSH 기반 워크플로들보다 실패
모드가 훨씬 적어, 살아남을 확률이 가장 높다.

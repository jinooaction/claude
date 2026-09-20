# 실행

깨끗하고 커밋된 코드에서 기존1645일 개발 입력만 사용한다.

```bash
uv run python scripts/shock_recovery_probe.py develop --bars-dir /path/research-input --manifest /path/research-input/manifest.json --output-dir /path/shock-recovery-development-v1
uv run python scripts/shock_recovery_probe.py verify --bars-dir /path/research-input --manifest /path/research-input/manifest.json --evidence /path/shock-recovery-development-v1
```

기존 출력은 덮어쓰지 않는다. 입력 오류·변조·코드 미커밋은 exit2.
검증 성공 exit0은 연구 재현 성공이며 전략 합격/실거래 허용이 아니다.
이 명령에는 확인495일을 읽거나 실제 주문하는 기능이 없다.

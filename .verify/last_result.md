# 운영자 셋업 검증 결과 ❌

- 종합: `ssh_failed`
- Secrets: 4개 등록됨, 키 형식=full_marker
- SSH exit: `255`
- 시각: 2026-05-20T14:05:32Z
- run id: 26167807594

## SSH 출력 (인스턴스 상태)

```
Warning: Permanently added '202.182.125.132' (ED25519) to the list of known hosts.
Load key "/home/runner/.ssh/id_ed25519": error in libcrypto
root@202.182.125.132: Permission denied (publickey,password).
```

## 키 진단 (3가지 복구 시도 모두 실패한 경우만)

```
=== 키 파일 진단 ===
파일 크기: 422 바이트
줄 수: 7
첫 줄: -----BEGIN OPENSSH PRIVATE KEY-----
마지막 줄: -----END OPENSSH PRIVATE KEY-----
ssh-keygen 에러: Load key "/home/runner/.ssh/id_ed25519": error in libcrypto
=== base64 magic bytes 검증 ===
base64 본문 길이: 347
디코드된 첫 14 바이트: openssh-key-v1
→ OpenSSH 키 형식 OK (그런데 ssh-keygen 이 거부 — 본문 손상)
```

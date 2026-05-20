# 운영자 셋업 검증 결과 ❌

- 종합: `ssh_failed`
- Secrets: 4개 등록됨, 키 형식=body_only_auto_wrapped
- SSH exit: `255`
- 시각: 2026-05-20T14:15:26Z
- run id: 26168384758

## SSH 출력 (인스턴스 상태)

```
Warning: Permanently added '202.182.125.132' (ED25519) to the list of known hosts.
Load key "/home/runner/.ssh/id_ed25519": error in libcrypto
root@202.182.125.132: Permission denied (publickey,password).
```

## 키 진단 (3가지 복구 시도 모두 실패한 경우만)

```
=== 키 파일 진단 ===
파일 크기: 679 바이트
줄 수: 11
첫 줄: -----BEGIN OPENSSH PRIVATE KEY-----
마지막 줄: -----END OPENSSH PRIVATE KEY-----
ssh-keygen 에러: Load key "/home/runner/.ssh/id_ed25519": error in libcrypto
=== base64 magic bytes 검증 ===
base64 본문 길이: 600
디코드된 첫 14 바이트: -----BEGIN OPE
→ 알 수 없는 형식: '-----BEGIN OPE'
```

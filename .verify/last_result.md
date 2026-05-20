# 운영자 셋업 검증 결과 ❌

- 종합: `ssh_failed`
- Secrets: 4개 등록됨, 키 형식=body_only_auto_wrapped
- SSH exit: `255`
- 시각: 2026-05-20T14:18:33Z
- run id: 26168564355

## SSH 출력 (인스턴스 상태)

```
Warning: Permanently added '202.182.125.132' (ED25519) to the list of known hosts.
Load key "/home/runner/.ssh/id_ed25519": error in libcrypto
root@202.182.125.132: Permission denied (publickey,password).
```

## 키 진단 (3가지 복구 시도 모두 실패한 경우만)

```
=== KEY 원본 분석 ===
원본 길이: 600
원본 첫 50자: LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYm
원본 마지막 50자: nI1SlpQUXRCUFVEV0U1TklJRkJTU1ZaQlZFVWdTMFZLU0tLS0K
공백 + 일반 base64 문자만 남긴 길이: 600
순수 base64 문자만 남긴 길이: 600
→ 차이 (0 글자) = 공백 + 특수문자
=== 시도 3 (순수 base64 디코드) 결과 ===
base64 -d 성공
  디코드 크기: 450
  디코드 첫 줄: -----BEGIN OPENSSH PRIVATE KEY-----
  디코드 마지막 줄: YcCR=yBKPLZzCP3j3hh25fpXK8KhgNN2f5tWZSS38PPR�]�]��֍��(pPPPP]�̙���^S�^�PPPP�NXK�T���S��$�ŧ��6�6��$�ecK���t��&SUSWU3�p�TF�v�eEUv��$崽���-���M��I��)]9����]���ّ��) �%��ѹ5��A�!�Ĭ)���ܝܸ5�������uS�������e�šd�I�����E%	5��)iAE�	AU]�9%%	MMYi	YU�L�Y-M---
  디코드 줄 수: 3
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@         WARNING: UNPROTECTED PRIVATE KEY FILE!          @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
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

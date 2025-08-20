# 그룹 삭제 기능 API 테스트 가이드

이 문서는 새로 구현된 그룹 삭제 기능의 API 테스트 방법을 상세히 설명합니다.

## 📋 구현된 기능 개요

### 1. 새로 추가된 API 엔드포인트
- `DELETE /family/my-group` - 그룹 리더가 자신의 그룹 삭제
- `DELETE /admin/groups/{group_id}` - 관리자가 특정 그룹 삭제  
- `DELETE /admin/members/{member_id}` - 관리자가 특정 멤버 삭제

### 2. 새로 추가된 서비스
- `SubscriptionAdminService` - 구독 취소 및 삭제 전담 서비스

## 🔧 테스트 환경 설정

### 필요한 환경 변수
```bash
# KakaoPay 설정 (결제 취소 테스트용)
KAKAO_PAY_SECRET_KEY=your_secret_key
KAKAO_PAY_CID=your_cid
KAKAO_PAY_API_HOST=https://open-api.kakaopay.com

# 관리자 이메일 설정
ADMIN_EMAILS=admin@example.com,admin2@example.com
```

### 테스트 데이터베이스 설정
```sql
-- 테스트용 활성 구독 데이터 생성
INSERT INTO subscriptions (id, group_id, user_id, status, start_date, amount, payment_method)
VALUES (uuid_generate_v4(), 'test_group_id', 'test_user_id', 'ACTIVE', CURRENT_DATE, 6900, 'kakao_pay');

-- 테스트용 결제 데이터 생성
INSERT INTO payments (id, subscription_id, transaction_id, pg_tid, amount, status, payment_method)
VALUES (uuid_generate_v4(), 'subscription_id', 'test_aid', 'test_tid', 6900, 'SUCCESS', 'kakao_pay');
```

## 🧪 API 테스트 시나리오

### 1. 그룹 리더 삭제 기능 테스트

#### 1-1. 정상적인 그룹 삭제 (구독 없음)
```bash
curl -X DELETE "http://localhost:8000/family/my-group" \
  -H "Authorization: Bearer {leader_jwt_token}" \
  -H "Content-Type: application/json"
```

**예상 응답:**
```json
{
  "message": "가족 그룹이 완전히 삭제되었습니다",
  "subscription_cancel": {
    "cancelled": false,
    "reason": "no_active_subscription"
  },
  "subscription_deleted": false,
  "pending_books_count": 0
}
```

#### 1-2. 활성 구독이 있는 그룹 삭제
```bash
curl -X DELETE "http://localhost:8000/family/my-group" \
  -H "Authorization: Bearer {leader_jwt_token}" \
  -H "Content-Type: application/json"
```

**예상 응답:**
```json
{
  "message": "가족 그룹이 완전히 삭제되었습니다",
  "subscription_cancel": {
    "cancelled": true,
    "subscription_id": "uuid-here",
    "payment_cancel_status": "success",
    "refund_amount": 6900
  },
  "subscription_deleted": true,
  "pending_books_count": 0
}
```

#### 1-3. 배송/제작 진행 중 그룹 삭제 시도
```bash
curl -X DELETE "http://localhost:8000/family/my-group?force=false" \
  -H "Authorization: Bearer {leader_jwt_token}" \
  -H "Content-Type: application/json"
```

**예상 응답 (400 Bad Request):**
```json
{
  "detail": "배송/제작 진행 중인 책자가 있어 삭제할 수 없습니다. force=true로 강제 삭제 가능합니다."
}
```

#### 1-4. 강제 삭제
```bash
curl -X DELETE "http://localhost:8000/family/my-group?force=true" \
  -H "Authorization: Bearer {leader_jwt_token}" \
  -H "Content-Type: application/json"
```

#### 1-5. 권한 없음 (일반 멤버)
```bash
curl -X DELETE "http://localhost:8000/family/my-group" \
  -H "Authorization: Bearer {member_jwt_token}" \
  -H "Content-Type: application/json"
```

**예상 응답 (403 Forbidden):**
```json
{
  "detail": "그룹 리더만 그룹을 삭제할 수 있습니다"
}
```

### 2. 관리자 그룹 삭제 기능 테스트

#### 2-1. 관리자 권한으로 그룹 삭제
```bash
curl -X DELETE "http://localhost:8000/admin/groups/{group_id}" \
  -H "Authorization: Bearer {admin_jwt_token}" \
  -H "Content-Type: application/json"
```

**예상 응답:**
```json
{
  "message": "그룹이 관리자에 의해 삭제되었습니다 (ID: group_id)",
  "group_name": "테스트 가족",
  "subscription_cancel": {
    "cancelled": true,
    "payment_cancel_status": "success",
    "refund_amount": 6900
  },
  "subscription_deleted": true,
  "pending_books_count": 2,
  "admin_email": "admin@example.com"
}
```

#### 2-2. 존재하지 않는 그룹 삭제 시도
```bash
curl -X DELETE "http://localhost:8000/admin/groups/non-existent-id" \
  -H "Authorization: Bearer {admin_jwt_token}" \
  -H "Content-Type: application/json"
```

**예상 응답 (404 Not Found):**
```json
{
  "detail": "그룹을 찾을 수 없습니다"
}
```

#### 2-3. 관리자 권한 없음
```bash
curl -X DELETE "http://localhost:8000/admin/groups/{group_id}" \
  -H "Authorization: Bearer {normal_user_jwt_token}" \
  -H "Content-Type: application/json"
```

**예상 응답 (403 Forbidden):**
```json
{
  "detail": "관리자 권한이 필요합니다"
}
```

### 3. 관리자 멤버 삭제 기능 테스트

#### 3-1. 일반 멤버 삭제
```bash
curl -X DELETE "http://localhost:8000/admin/members/{member_id}" \
  -H "Authorization: Bearer {admin_jwt_token}" \
  -H "Content-Type: application/json"
```

**예상 응답:**
```json
{
  "message": "멤버가 관리자에 의해 삭제되었습니다",
  "member_id": "member_id",
  "group_name": "테스트 가족",
  "admin_email": "admin@example.com"
}
```

#### 3-2. 리더 멤버 삭제 시도 (차단)
```bash
curl -X DELETE "http://localhost:8000/admin/members/{leader_member_id}" \
  -H "Authorization: Bearer {admin_jwt_token}" \
  -H "Content-Type: application/json"
```

**예상 응답 (400 Bad Request):**
```json
{
  "detail": "리더 멤버는 관리자 권한으로도 삭제할 수 없습니다. 그룹 삭제를 사용해주세요. (그룹: 테스트 가족)"
}
```

#### 3-3. 존재하지 않는 멤버 삭제 시도
```bash
curl -X DELETE "http://localhost:8000/admin/members/non-existent-id" \
  -H "Authorization: Bearer {admin_jwt_token}" \
  -H "Content-Type: application/json"
```

**예상 응답 (404 Not Found):**
```json
{
  "detail": "멤버를 찾을 수 없습니다"
}
```

## 🔍 테스트 케이스별 검증 포인트

### A. 그룹 삭제 후 데이터 확인
```sql
-- 1. 그룹 삭제 확인
SELECT * FROM family_groups WHERE id = '{deleted_group_id}';
-- 결과: 0 rows (삭제됨)

-- 2. 연관 데이터 cascade 삭제 확인
SELECT * FROM family_members WHERE group_id = '{deleted_group_id}';
SELECT * FROM recipients WHERE group_id = '{deleted_group_id}';
SELECT * FROM issues WHERE group_id = '{deleted_group_id}';
-- 결과: 모두 0 rows (cascade로 삭제됨)

-- 3. 구독 데이터 삭제 확인
SELECT * FROM subscriptions WHERE group_id = '{deleted_group_id}';
SELECT * FROM payments WHERE subscription_id IN (
    SELECT id FROM subscriptions WHERE group_id = '{deleted_group_id}'
);
-- 결과: 모두 0 rows (물리적 삭제됨)
```

### B. 결제 취소 로그 확인
```sql
-- 애플리케이션 로그에서 다음 패턴 확인
-- "카카오페이 취소 요청: tid=xxx, amount=6900"
-- "결제 취소 성공: tid=xxx"
-- "구독 삭제 완료: subscription_id=xxx, group_id=xxx"
```

### C. 오류 상황 테스트
#### C-1. KakaoPay API 오류 시뮬레이션
```bash
# 잘못된 TID로 취소 시도하여 -721 에러 발생
# 애플리케이션이 "already_cancelled" 상태로 처리하는지 확인
```

#### C-2. 동시성 테스트
```bash
# 두 개의 요청을 동시에 실행
curl -X DELETE "http://localhost:8000/family/my-group" & 
curl -X DELETE "http://localhost:8000/family/my-group" &

# 하나는 성공, 하나는 404 에러가 나와야 함
```

## 📊 성능 및 모니터링

### 성능 측정 포인트
1. **그룹 삭제 완료 시간**: 구독 취소 → 데이터 삭제 → 완료 응답
2. **카카오페이 취소 API 응답 시간**: 보통 1-3초
3. **DB 트랜잭션 처리 시간**: cascade 삭제 포함

### 로그 모니터링
```bash
# 애플리케이션 로그에서 다음 키워드 모니터링
grep -i "그룹 삭제" app.log
grep -i "결제 취소" app.log
grep -i "subscription_admin_service" app.log
grep -i "ERROR.*delete.*group" app.log
```

## 🚨 주의사항 및 제한사항

### 1. 안전장치
- **배송 중인 책자**: force=true 없이는 삭제 불가
- **제작 중인 책자**: force=true 없이는 삭제 불가
- **리더 멤버**: 관리자도 직접 삭제 불가

### 2. 복구 불가
- **물리적 삭제**: 모든 데이터가 완전히 제거됨
- **결제 내역**: 구독과 함께 삭제됨 (회계 데이터 유지 필요시 정책 변경 필요)

### 3. 트랜잭션 경계
- **결제 취소**: 별도 커밋 (PG 취소 실패해도 그룹 삭제는 진행)
- **구독 삭제**: 별도 커밋
- **그룹 삭제**: 최종 커밋

## 🔄 롤백 및 복구 절차

### 1. 실수로 삭제한 경우
```sql
-- 백업에서 복구해야 함 (물리적 삭제로 인한 데이터 손실)
-- 자동 복구 불가능
```

### 2. 부분 실패 시나리오
- **결제 취소만 실패**: 그룹은 삭제되지만 환불 수동 처리 필요
- **구독 삭제 실패**: HTTP 500 에러, 트랜잭션 롤백
- **그룹 삭제 실패**: HTTP 500 에러, 전체 롤백

## 📋 체크리스트

### 배포 전 확인사항
- [ ] 환경변수 설정 완료 (KAKAO_PAY_*, ADMIN_EMAILS)
- [ ] 데이터베이스 cascade 관계 확인
- [ ] 백업 시스템 구축
- [ ] 로그 모니터링 설정
- [ ] 관리자 계정 권한 확인

### 테스트 시나리오 실행 체크리스트
- [ ] 정상 그룹 삭제 (구독 없음)
- [ ] 활성 구독 그룹 삭제
- [ ] 배송/제작 중 그룹 삭제 차단
- [ ] 강제 삭제 동작
- [ ] 권한 검증 (리더, 관리자)
- [ ] 리더 멤버 삭제 차단
- [ ] 존재하지 않는 엔티티 처리
- [ ] 동시성 테스트
- [ ] 오류 복구 테스트

이상으로 그룹 삭제 기능의 API 테스트 가이드를 완료했습니다. 모든 시나리오를 순차적으로 테스트하여 안정성을 확인하시기 바랍니다.
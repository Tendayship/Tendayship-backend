# CRUD 작업 매트릭스

## 1. 사용자 도메인 (User Domain)

| 작업 | 메서드 | 엔드포인트 | 권한 | PostgreSQL | Azure Blob |
|------|--------|------------|------|------------|------------|
| 카카오 로그인 | POST | `/auth/kakao/callback` | Public | users 조회/생성 | - |
| 프로필 등록 | POST | `/auth/profile` | Auth | users 업데이트 | profile 이미지 업로드 |
| 프로필 조회 | GET | `/profile/me` | Auth | users 조회 | - |
| 프로필 수정 | PUT | `/profile/me` | Auth | users 업데이트 | profile 이미지 교체 |
| 회원 탈퇴 | DELETE | `/profile/me` | Auth | users 소프트 삭제 | - |

## 2. 가족 그룹 도메인 (Family Group Domain)

| 작업 | 메서드 | 엔드포인트 | 권한 | PostgreSQL | Azure Blob |
|------|--------|------------|------|------------|------------|
| 그룹 생성 | POST | `/family/create` | Auth | family_groups 생성 | - |
| 받는 분 등록 | POST | `/family/{group_id}/recipient` | Leader | recipients 생성 | recipient 프로필 업로드 |
| 초대 코드 생성 | POST | `/family/{group_id}/invite` | Leader | family_groups 업데이트 | - |
| 초대 코드 검증 | POST | `/family/join` | Auth | family_groups 조회 | - |
| 멤버 가입 | POST | `/family/{group_id}/members` | Auth | family_members 생성 | - |
| 멤버 목록 조회 | GET | `/family/{group_id}/members` | Member | family_members 조회 | - |
| 멤버 권한 변경 | PUT | `/family/{group_id}/members/{member_id}` | Leader | family_members 업데이트 | - |
| 멤버 제거 | DELETE | `/family/{group_id}/members/{member_id}` | Leader | family_members 삭제 | - |
| 받는 분 정보 수정 | PUT | `/family/{group_id}/recipient` | Leader | recipients 업데이트 | recipient 프로필 교체 |

## 3. 소식 도메인 (Post Domain)

| 작업 | 메서드 | 엔드포인트 | 권한 | PostgreSQL | Azure Blob |
|------|--------|------------|------|------------|------------|
| 소식 작성 | POST | `/posts` | Member | posts 생성 | 이미지 업로드 (최대 4장) |
| 소식 목록 조회 | GET | `/posts` | Member | posts, issues 조회 | - |
| 소식 상세 조회 | GET | `/posts/{post_id}` | Member | posts 조회 | - |
| 소식 수정 | PUT | `/posts/{post_id}` | Author | posts 업데이트 | 이미지 교체 |
| 소식 삭제 | DELETE | `/posts/{post_id}` | Author | posts 삭제 | 이미지 삭제 |
| 이미지 업로드 | POST | `/posts/{post_id}/images` | Author | posts.image_urls 업데이트 | 이미지 저장 |
| 이미지 삭제 | DELETE | `/posts/{post_id}/images/{image_id}` | Author | posts.image_urls 업데이트 | 이미지 삭제 |

## 4. 회차 도메인 (Issue Domain)

| 작업 | 메서드 | 엔드포인트 | 권한 | PostgreSQL | Azure Blob |
|------|--------|------------|------|------------|------------|
| 현재 회차 조회 | GET | `/issues/current` | Member | issues 조회 | - |
| 회차 목록 조회 | GET | `/issues` | Member | issues 조회 | - |
| 회차 마감 | POST | `/issues/{issue_id}/close` | System | issues 업데이트 | - |
| 새 회차 생성 | POST | `/issues` | System | issues 생성 | - |
| 회차별 소식 조회 | GET | `/issues/{issue_id}/posts` | Member | posts 조회 | - |

## 5. 책자 도메인 (Book Domain)

| 작업 | 메서드 | 엔드포인트 | 권한 | PostgreSQL | Azure Blob |
|------|--------|------------|------|------------|------------|
| 책자 생성 요청 | POST | `/books/generate` | Admin | books 생성 | - |
| PDF 업로드 | POST | `/books/{book_id}/pdf` | Admin | books.pdf_url 업데이트 | PDF 업로드 |
| 책자 목록 조회 | GET | `/books` | Member | books 조회 | - |
| 책자 다운로드 | GET | `/books/{book_id}/download` | Member | books 조회 | SAS URL 생성 |
| 배송 상태 업데이트 | PUT | `/books/{book_id}/delivery` | Admin | books 업데이트 | - |

## 6. 구독 도메인 (Subscription Domain)

| 작업 | 메서드 | 엔드포인트 | 권한 | PostgreSQL | Azure Blob |
|------|--------|------------|------|------------|------------|
| 구독 생성 | POST | `/subscriptions` | Leader | subscriptions 생성 | - |
| 결제 처리 | POST | `/payments/process` | Leader | payments 생성 | - |
| 구독 상태 조회 | GET | `/subscriptions/{group_id}` | Member | subscriptions 조회 | - |
| 결제 수단 변경 | PUT | `/subscriptions/{sub_id}/payment-method` | Leader | subscriptions 업데이트 | - |
| 구독 취소 | DELETE | `/subscriptions/{sub_id}` | Leader | subscriptions 업데이트 | - |
| 결제 내역 조회 | GET | `/payments` | Leader | payments 조회 | - |

## 권한 레벨 정의

- **Public**: 인증 불필요
- **Auth**: 로그인 필요 (오디가의 `require_auth` 패턴 사용)
- **Member**: 그룹 멤버 권한 필요
- **Leader**: 그룹 리더 권한 필요
- **Author**: 콘텐츠 작성자 본인
- **Admin**: 관리자 권한
- **System**: 시스템 자동 처리 (크론잡, 워커)

## 데이터베이스 트랜잭션 패턴

```python
# 기본 트랜잭션 패턴
async def create_entity(db: AsyncSession, entity_data: EntityCreate):
    try:
        # 1. 권한 검증
        await verify_permissions(...)
        
        # 2. PostgreSQL 트랜잭션
        db_entity = Entity(**entity_data.dict())
        db.add(db_entity)
        
        # 3. Azure Blob Storage 작업 (필요시)
        if has_files:
            file_url = await upload_to_blob(...)
            db_entity.file_url = file_url
        
        # 4. 커밋
        await db.commit()
        await db.refresh(db_entity)
        
        return db_entity
        
    except Exception as e:
        await db.rollback()
        # Blob Storage 롤백 (필요시)
        if uploaded_file:
            await delete_from_blob(...)
        raise
```

## Azure Blob Storage 경로 구조

```
family-news/
├── {group_id}/
│   ├── profiles/
│   │   ├── recipient_{recipient_id}.jpg
│   │   └── member_{user_id}.jpg
│   │
│   ├── issues/
│   │   └── {issue_id}/
│   │       ├── posts/
│   │       │   └── {post_id}/
│   │       │       ├── image1.jpg
│   │       │       ├── image2.jpg
│   │       │       ├── image3.jpg
│   │       │       └── image4.jpg
│   │       │
│   │       └── books/
│   │           ├── book_{timestamp}.pdf
│   │           └── book_{timestamp}_cover.jpg
│   │
│   └── temp/
│       └── upload_{session_id}/
```

## 캐싱 전략

자주 조회되는 데이터에 대한 캐싱 전략:

1. **Redis 캐싱 대상**
   - 현재 회차 정보 (TTL: 1시간)
   - 그룹 멤버 목록 (TTL: 10분)
   - 사용자 프로필 (TTL: 30분)
   
2. **CDN 캐싱 (Azure Blob)**
   - 프로필 이미지 (Cache-Control: 7일)
   - 게시글 이미지 (Cache-Control: 30일)
   - PDF 파일 (Cache-Control: 영구)
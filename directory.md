# 가족 소식 서비스 프로젝트 구조

```
family-news-service/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── dependencies.py         # 인증, 권한 검증 의존성
│   │   │   ├── middleware.py           # CORS, 세션 미들웨어
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       ├── auth.py             # 카카오 로그인/회원가입
│   │   │       ├── family.py           # 가족 그룹 생성/관리
│   │   │       ├── members.py          # 멤버 초대/가입
│   │   │       ├── posts.py            # 소식 작성/조회
│   │   │       ├── issues.py           # 회차 관리
│   │   │       ├── books.py            # 책자 생성/조회
│   │   │       ├── subscription.py     # 구독/결제 관리
│   │   │       ├── profile.py          # 프로필 관리
│   │   │       └── admin.py            # 어드민 기능
│   │   │
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py               # 환경변수 및 설정
│   │   │   ├── security.py             # 보안 관련 유틸리티
│   │   │   └── exceptions.py           # 커스텀 예외 클래스
│   │   │
│   │   ├── crud/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # 기본 CRUD 클래스
│   │   │   ├── user_crud.py            # 사용자 CRUD
│   │   │   ├── family_crud.py          # 가족 그룹 CRUD
│   │   │   ├── member_crud.py          # 멤버 CRUD
│   │   │   ├── recipient_crud.py       # 받는 분 CRUD
│   │   │   ├── post_crud.py            # 소식 CRUD
│   │   │   ├── issue_crud.py           # 회차 CRUD
│   │   │   ├── book_crud.py            # 책자 CRUD
│   │   │   └── subscription_crud.py    # 구독 CRUD
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # SQLAlchemy Base
│   │   │   ├── user.py                 # User 모델
│   │   │   ├── family.py               # FamilyGroup, FamilyMember 모델
│   │   │   ├── recipient.py            # Recipient 모델
│   │   │   ├── post.py                 # Post 모델
│   │   │   ├── issue.py                # Issue 모델
│   │   │   ├── book.py                 # Book 모델
│   │   │   └── subscription.py         # Subscription, Payment 모델
│   │   │
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── user.py                 # User 관련 Pydantic 스키마
│   │   │   ├── family.py               # Family 관련 스키마
│   │   │   ├── recipient.py            # Recipient 스키마
│   │   │   ├── post.py                 # Post 스키마
│   │   │   ├── issue.py                # Issue 스키마
│   │   │   ├── book.py                 # Book 스키마
│   │   │   └── subscription.py         # Subscription 스키마
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py         # 카카오 OAuth 서비스
│   │   │   ├── storage_service.py      # Azure Blob Storage 서비스
│   │   │   ├── pdf_service.py          # PDF 생성 서비스
│   │   │   ├── payment_service.py      # 결제 처리 서비스
│   │   │   ├── notification_service.py # 알림 서비스
│   │   │   └── deadline_service.py     # 마감일 처리 서비스
│   │   │
│   │   ├── utils/
│   │   │   ├── __init__.py
│   │   │   ├── azure_utils.py          # Azure Blob Storage 유틸리티
│   │   │   ├── image_utils.py          # 이미지 처리 유틸리티
│   │   │   ├── pdf_utils.py            # PDF 생성 유틸리티
│   │   │   ├── invite_utils.py         # 초대 코드 생성
│   │   │   └── validators.py           # 데이터 검증 유틸리티
│   │   │
│   │   ├── workers/
│   │   │   ├── __init__.py
│   │   │   ├── deadline_worker.py      # 마감일 체크 워커
│   │   │   ├── pdf_worker.py           # PDF 생성 백그라운드 워커
│   │   │   └── notification_worker.py  # 알림 발송 워커
│   │   │
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── session.py              # 데이터베이스 세션 관리
│   │   │   └── migrations/             # Alembic 마이그레이션
│   │   │       └── versions/
│   │   │
│   │   └── main.py                     # FastAPI 앱 진입점
│   │
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py                 # pytest 설정
│   │   ├── test_auth.py
│   │   ├── test_family.py
│   │   ├── test_posts.py
│   │   └── test_storage.py
│   │
│   ├── alembic.ini                     # Alembic 설정
│   ├── requirements.txt                # Python 의존성
│   ├── .env.example                    # 환경변수 예제
│   └── Dockerfile                      # Docker 이미지 빌드
│
├── frontend/                            # Next.js 프론트엔드
│   ├── src/
│   │   ├── app/                        # App Router 페이지
│   │   ├── components/                 # React 컴포넌트
│   │   ├── lib/                        # 유틸리티 함수
│   │   ├── hooks/                      # 커스텀 훅
│   │   └── styles/                     # 스타일 파일
│   │
│   ├── public/                         # 정적 파일
│   ├── package.json
│   └── next.config.js
│
├── infrastructure/
│   ├── terraform/                      # Terraform IaC
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   │
│   └── docker-compose.yml              # 로컬 개발 환경
│
└── docs/
    ├── api/                            # API 문서
    ├── architecture/                   # 아키텍처 문서
    └── deployment/                     # 배포 가이드
```

## 디렉토리 구조 설명

### 1. **api/routes/** - API 엔드포인트
각 도메인별로 라우터를 분리하여 관리합니다. 오디가 프로젝트처럼 기능별로 명확히 구분된 파일로 구성했습니다.

### 2. **models/** - 데이터베이스 모델
SQLAlchemy ORM 모델을 도메인별로 분리했습니다. 각 모델은 PostgreSQL 테이블과 1:1 매핑됩니다.

### 3. **schemas/** - 데이터 검증 스키마
Pydantic을 사용한 요청/응답 데이터 검증 스키마입니다. 모델과 동일한 구조로 구성하여 일관성을 유지합니다.

### 4. **services/** - 비즈니스 로직
복잡한 비즈니스 로직을 처리하는 서비스 레이어입니다. Azure Blob Storage 연동, PDF 생성, 결제 처리 등의 외부 서비스 연동을 담당합니다.

### 5. **crud/** - 데이터베이스 작업
순수한 데이터베이스 CRUD 작업만을 담당합니다. 오디가 프로젝트의 crud.py를 도메인별로 세분화했습니다.

### 6. **utils/** - 유틸리티 함수
재사용 가능한 유틸리티 함수들입니다. 특히 `azure_utils.py`는 오디가 프로젝트의 구조를 참고하여 Blob Storage 작업을 처리합니다.

### 7. **workers/** - 백그라운드 작업
비동기로 처리해야 하는 작업들입니다. 마감일 체크, PDF 생성, 알림 발송 등을 백그라운드에서 처리합니다.

## 주요 설계 원칙

1. **도메인 중심 설계**: 각 도메인(family, post, issue 등)별로 모델, 스키마, CRUD를 분리
2. **계층 분리**: API 라우터 → 서비스 레이어 → CRUD 레이어 → 데이터베이스
3. **관심사 분리**: PostgreSQL(구조적 데이터)과 Azure Blob Storage(파일)를 명확히 분리
4. **테스트 가능성**: 각 레이어가 독립적으로 테스트 가능하도록 설계
5. **확장성**: 새로운 기능 추가 시 기존 구조를 변경하지 않고 확장 가능
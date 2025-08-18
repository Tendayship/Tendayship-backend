from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """
    애플리케이션 전체 설정을 관리하는 클래스
    환경 변수를 자동으로 읽어와 검증하고 타입을 보장합니다.
    """
    # 기본 애플리케이션 설정
    APP_NAME: str = "Family News Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # API 설정
    API_PREFIX: str = "/api"
    ALLOWED_HOSTS: List[str] = Field(
        default=[
            "localhost", 
            "127.0.0.1", 
            "tendayapp-f0a0drg2b6avh8g3.koreacentral-01.azurewebsites.net"
        ],
        description="허용된 호스트 목록"
    )

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    SECRET_KEY: str

    # 저장소 타입 설정 추가
    STORAGE_TYPE: str = Field(
        default="azure",
        description="저장소 타입: 'local' 또는 'azure'"
    )

    # Azure PostgreSQL 설정
    POSTGRES_SERVER: str = Field(
        ...,
        description="Azure PostgreSQL 서버 주소"
    )
    POSTGRES_USER: str = Field(
        ...,
        description="PostgreSQL 사용자명"
    )
    POSTGRES_PASSWORD: str = Field(
        ...,
        description="PostgreSQL 비밀번호"
    )
    POSTGRES_DB: str = Field(
        default="family_news_db",
        description="데이터베이스 이름"
    )
    POSTGRES_PORT: int = Field(
        default=5432,
        description="PostgreSQL 포트 번호"
    )
    POSTGRES_SSL_MODE: str = Field(
        default="require",
        description="SSL 연결 모드"
    )

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            f"?ssl={self.POSTGRES_SSL_MODE}"
        )

    # Azure Blob Storage 설정
    AZURE_STORAGE_CONNECTION_STRING: str = Field(
        ...,
        description="Azure Storage 연결 문자열"
    )
    AZURE_STORAGE_ACCOUNT_NAME: str = Field(
        ...,
        description="Storage Account 이름"
    )
    AZURE_STORAGE_ACCOUNT_KEY: str = Field(
        ...,
        description="Storage Account 액세스 키"
    )
    AZURE_STORAGE_CONTAINER_NAME: str = Field(
        default="family-news",
        description="메인 컨테이너 이름"
    )

    # Azure Content Safety API 설정
    CONTENT_SAFETY_ENDPOINT: Optional[str] = Field(
        default=None,
        description="Azure Content Safety API 엔드포인트"
    )
    CONTENT_SAFETY_KEY: Optional[str] = Field(
        default=None,
        description="Content Safety API 키"
    )

    # 세션 및 보안 설정
    SECRET_KEY: str = Field(
        ...,
        min_length=32,
        description="세션 암호화용 비밀 키"
    )
    SESSION_EXPIRE_MINUTES: int = Field(
        default=1440,
        description="세션 만료 시간"
    )

    # 카카오 OAuth 설정
    KAKAO_CLIENT_ID: str = Field(
        ...,
        description="카카오 앱 REST API 키"
    )
    KAKAO_CLIENT_SECRET: Optional[str] = Field(
        default=None,
        description="카카오 앱 시크릿"
    )
    KAKAO_REDIRECT_URI: str = Field(
        ...,
        description="카카오 로그인 리다이렉트 URI"
    )

    # 카카오페이 설정
    KAKAO_PAY_SECRET_KEY: str = Field(
        default="",
        env="KAKAO_PAY_SECRET_KEY",
        description="카카오페이 시크릿 키"
    )
    KAKAO_PAY_CID: str = Field(
        default="TC0ONETIME",
        env="KAKAO_PAY_CID",
        description="카카오페이 가맹점 코드"
    )
    KAKAO_PAY_CID_SUBSCRIPTION: str = Field(
        default="TCSUBSCRIP",
        env="KAKAO_PAY_CID_SUBSCRIPTION",
        description="카카오페이 정기결제용 가맹점 코드"
    )
    KAKAO_PAY_API_HOST: str = Field(
        default="https://open-api.kakaopay.com",
        env="KAKAO_PAY_API_HOST",
        description="카카오페이 API 호스트"
    )

    PAYMENT_SUCCESS_URL: str = Field(
        default="https://tendayapp-f0a0drg2b6avh8g3.koreacentral-01.azurewebsites.net/api/subscription/approve",
        env="PAYMENT_SUCCESS_URL"
    )
    PAYMENT_CANCEL_URL: str = Field(
        default="https://tendayapp-f0a0drg2b6avh8g3.koreacentral-01.azurewebsites.net/api/subscription/cancel",
        env="PAYMENT_CANCEL_URL"
    )
    PAYMENT_FAIL_URL: str = Field(
        default="https://tendayapp-f0a0drg2b6avh8g3.koreacentral-01.azurewebsites.net/api/subscription/fail",
        env="PAYMENT_FAIL_URL"
    )

    # 결제 모드
    PAYMENT_MODE: str = Field(
        default="TEST",
        env="PAYMENT_MODE",
        description="TEST or PRODUCTION"
    )

    # 결제 설정
    PAYMENT_MONTHLY_AMOUNT: int = Field(
        default=6900,
        description="월 구독료"
    )

    # 프론트엔드 URL
    FRONTEND_URL: str = Field(
        default="http://localhost:3000",
        env="FRONTEND_URL",
        description="프론트엔드 URL"
    )

    # 파일 업로드 제한
    MAX_UPLOAD_SIZE: int = Field(
        default=10 * 1024 * 1024,
        description="최대 업로드 파일 크기"
    )
    MAX_IMAGES_PER_POST: int = Field(
        default=4,
        description="게시글당 최대 이미지 수"
    )
    
    # 게시글 제한 추가
    MAX_POSTS_PER_MONTH: int = Field(
        default=20,
        description="월 최대 게시글 수"
    )

    # 텍스트 제한
    POST_MIN_LENGTH: int = Field(
        default=50,
        description="게시글 최소 글자 수"
    )
    POST_MAX_LENGTH: int = Field(
        default=100,
        description="게시글 최대 글자 수"
    )

    # 초대 코드 설정
    INVITE_CODE_LENGTH: int = Field(
        default=8,
        description="초대 코드 길이"
    )
    INVITE_CODE_EXPIRE_DAYS: int = Field(
        default=7,
        description="초대 코드 유효 기간"
    )

    # 회차 및 마감일 설정
    ISSUE_DEADLINE_OPTIONS: List[str] = Field(
        default=["second_sunday", "fourth_sunday"],
        description="마감일 옵션"
    )

    # Redis 설정
    REDIS_URL: Optional[str] = Field(
        default=None,
        description="Redis 연결 URL"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @validator("SECRET_KEY")
    def validate_secret_key(cls, v):
        if len(v) < 32:
            raise ValueError("SECRET_KEY는 최소 32자 이상이어야 합니다")
        return v

    @validator("KAKAO_PAY_SECRET_KEY")
    def validate_kakao_pay_key(cls, v, values):
        if values.get("PAYMENT_MODE") == "PRODUCTION" and not v:
            raise ValueError("Production 모드에서는 KAKAO_PAY_SECRET_KEY가 필수입니다")
        return v

    @validator("ALLOWED_HOSTS", pre=True)
    def parse_allowed_hosts(cls, v):
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v


settings = Settings()



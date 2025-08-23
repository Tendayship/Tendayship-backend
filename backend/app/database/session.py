from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy import text
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
import logging

from ..core.config import settings

# 로깅 설정
logger = logging.getLogger(__name__)

# SQLAlchemy Base 클래스 생성
Base = declarative_base()

# 비동기 엔진 생성
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # 디버그 모드에서 SQL 쿼리 출력
    pool_pre_ping=True,  # 연결 상태를 미리 확인 (Azure 연결 안정성 향상)
    pool_size=5,  # 기본 연결 풀 크기
    max_overflow=10,  # 최대 추가 연결 수
    pool_timeout=30,  # 연결 대기 시간 (초)
    pool_recycle=3600,  # 연결 재활용 시간 (1시간)
    connect_args={
        # Azure PostgreSQL SSL 연결 설정
        "server_settings": {
            "application_name": settings.APP_NAME,
            "jit": "off"  # Azure PostgreSQL 성능 최적화
        },
        "command_timeout": 60,
        "ssl": settings.POSTGRES_SSL_MODE
    }
)

# 비동기 세션 팩토리 생성
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async_session_maker = AsyncSessionLocal

async def get_db() -> AsyncSession: # type: ignore
    """
    FastAPI 의존성 주입용 데이터베이스 세션 제공 함수
    트랜잭션 제어(commit, rollback)는 API 라우터/서비스 레이어에서 수행합니다.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session  # 세션을 라우터 함수에 제공
        except Exception as e:
            await session.rollback() # 예외 발생 시 롤백
            logger.error(f"Database session error occurred, rolling back: {e}")
            raise
        finally:
            await session.close() # 세션 종료


async def init_db():
    """
    데이터베이스 초기화 함수
    테이블을 생성하고 초기 데이터를 설정합니다.
    """
    try:
        async with engine.begin() as conn:
            # PostgreSQL UUID 확장 활성화 (UUID 필드 사용을 위해 필요)
            try:
                await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
                logger.info("UUID extension enabled successfully")
            except Exception as ext_error:
                logger.warning(f"Could not enable UUID extension (might already exist): {ext_error}")
            
            # 모든 테이블 생성
            # 주의: 프로덕션에서는 Alembic 마이그레이션을 사용하세요
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
            
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        logger.error("This might be due to:")
        logger.error("1. Database connection issues")
        logger.error("2. Missing permissions to create extensions/tables")
        logger.error("3. UUID extension not available")
        logger.error("4. Table conflicts or constraint violations")
        raise


async def close_db():
    """
    데이터베이스 연결 종료 함수
    애플리케이션 종료 시 호출됩니다.
    """
    await engine.dispose()
    logger.info("Database connections closed")


async def check_db_connection():
    """
    데이터베이스 연결 상태를 확인하는 헬스체크 함수
    """
    try:
        async with AsyncSessionLocal() as session:
            # 간단한 쿼리로 연결 확인
            result = await session.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


async def validate_db_setup():
    """
    데이터베이스 설정 및 필수 확장 유효성 검사
    """
    try:
        async with AsyncSessionLocal() as session:
            # 1. 기본 연결 테스트
            await session.execute(text("SELECT 1"))
            logger.info("✓ Database connection successful")
            
            # 2. UUID 확장 확인
            try:
                result = await session.execute(text("SELECT uuid_generate_v4()"))
                uuid_test = result.scalar()
                if uuid_test:
                    logger.info("✓ UUID extension is working")
            except Exception as uuid_error:
                logger.error(f"✗ UUID extension test failed: {uuid_error}")
                raise
                
            # 3. 데이터베이스 권한 확인 (테이블 생성 권한)
            try:
                await session.execute(text("CREATE TABLE IF NOT EXISTS _test_permissions_check (id INTEGER)"))
                await session.execute(text("DROP TABLE IF EXISTS _test_permissions_check"))
                logger.info("✓ Database permissions are sufficient")
            except Exception as perm_error:
                logger.error(f"✗ Insufficient database permissions: {perm_error}")
                raise
                
            await session.commit()
            return True
            
    except Exception as e:
        logger.error(f"Database setup validation failed: {e}")
        return False
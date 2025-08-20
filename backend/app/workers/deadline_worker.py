import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager

from ..core.config import settings
from ..services.deadline_service import DeadlineService

logger = logging.getLogger(__name__)

@asynccontextmanager
async def get_worker_db():
    """
    워커를 위한 새로운 데이터베이스 세션을 생성합니다.
    """
    engine = create_async_engine(settings.ASYNC_DATABASE_URL, pool_pre_ping=True)
    AsyncSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
    )
    
    db = AsyncSessionLocal()
    try:
        yield db
    finally:
        await db.close()

async def process_deadlines_job():
    """
    마감일을 처리하고 다음 회차를 생성하는 스케줄링 작업입니다.
    """
    logger.info("마감일 처리 스케줄러 시작...")
    async with get_worker_db() as db:
        try:
            deadline_service = DeadlineService(db)
            closed_count, new_issue_count = await deadline_service.process_all_group_deadlines()
            logger.info(
                f"마감일 처리 완료: "
                f"{closed_count}개 회차 마감, {new_issue_count}개 신규 회차 생성"
            )
        except Exception as e:
            logger.error(f"마감일 처리 스케줄러 실행 중 오류: {str(e)}")


scheduler = AsyncIOScheduler(timezone="Asia/Seoul")

# 매일 새벽 1시에 마감일 처리 작업을 실행하도록 등록합니다.
scheduler.add_job(process_deadlines_job, 'cron', hour=1, minute=0)

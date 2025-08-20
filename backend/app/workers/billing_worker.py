import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager

from ..core.config import settings
from ..crud.subscription_crud import subscription_crud
from ..services.payment_service import payment_service

logger = logging.getLogger(__name__)

# --- 수정된 부분 ---

@asynccontextmanager
async def get_worker_db():
    """
    워커를 위한 새로운 데이터베이스 세션을 생성합니다.
    settings 객체가 완전히 로드된 후 engine이 생성되도록 이 함수 안으로 옮겼습니다.
    """
    # engine과 session 생성을 함수 내부로 이동
    engine = create_async_engine(settings.ASYNC_DATABASE_URL, pool_pre_ping=True)
    AsyncSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
    )
    
    db = AsyncSessionLocal()
    try:
        yield db
    finally:
        await db.close()

# --- 수정된 부분 끝 ---

async def process_recurring_payments():
    """ 정기결제 처리 로직 """
    logger.info("정기결제 스케줄러 시작...")
    async with get_worker_db() as db:
        try:
            due_subscriptions = await subscription_crud.get_due_subscriptions(db)
            if not due_subscriptions:
                logger.info("결제 대상 구독이 없습니다.")
                return

            logger.info(f"총 {len(due_subscriptions)}개의 구독에 대한 정기결제를 시도합니다.")
            for sub in due_subscriptions:
                try:
                    logger.info(f"구독 ID: {sub.id} 결제 시도...")
                    await payment_service.charge_recurring_payment(db, sub)
                    logger.info(f"구독 ID: {sub.id} 결제 성공.")
                except Exception as e:
                    logger.error(f"구독 ID: {sub.id} 결제 처리 중 오류 발생: {str(e)}")
                    continue
        except Exception as e:
            logger.error(f"정기결제 스케줄러 실행 중 오류: {str(e)}")


scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
# 매일 0시 5분에 실행 (서버 시작 시 약간의 딜레이를 감안)
scheduler.add_job(process_recurring_payments, 'cron', hour=0, minute=5)
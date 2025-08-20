# app/workers/billing_worker.py
import logging
from typing import Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from ..core.config import settings
from ..crud.subscription_crud import subscription_crud
from ..services.payment_service import payment_service

logger = logging.getLogger(__name__)

# 전역 스케줄러 인스턴스 (지연 로딩)
_scheduler = None

def init_scheduler():
    """
    스케줄러를 초기화합니다. APScheduler가 설치되어 있지 않으면 None을 반환합니다.
    """
    global _scheduler
    
    if _scheduler is not None:
        return _scheduler
        
    try:
        # 지연 임포트: 패키지 없으면 여기서만 실패
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.jobstores.memory import MemoryJobStore
        from apscheduler.executors.asyncio import AsyncIOExecutor
        
        # 스케줄러 설정
        jobstores = {"default": MemoryJobStore()}
        executors = {"default": AsyncIOExecutor()}
        job_defaults = {"coalesce": False, "max_instances": 1}
        
        _scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors, 
            job_defaults=job_defaults,
            timezone="Asia/Seoul"
        )
        
        # 정기결제 작업 등록 - 매일 0시 5분에 실행
        _scheduler.add_job(
            process_recurring_payments, 
            'cron', 
            hour=0, 
            minute=5,
            id='recurring_payments_job'
        )
        
        logger.info("정기결제 스케줄러가 초기화되었습니다.")
        return _scheduler
        
    except ModuleNotFoundError as e:
        logger.warning(
            "APScheduler가 설치되지 않았습니다. 정기결제 스케줄러 기능이 비활성화됩니다. "
            f"설치하려면 'pip install APScheduler>=3.10.4' 를 실행하세요. 오류: {str(e)}"
        )
        _scheduler = None
        return None
    except Exception as e:
        logger.error(f"스케줄러 초기화 중 예외가 발생했습니다: {str(e)}")
        _scheduler = None
        return None

@asynccontextmanager
async def get_worker_db():
    """
    워커를 위한 새로운 데이터베이스 세션을 생성합니다.
    settings 객체가 완전히 로드된 후 engine이 생성되도록 이 함수 안으로 옮겼습니다.
    """
    # engine과 session 생성을 함수 내부로 이동
    engine = create_async_engine(
        settings.DATABASE_URL,  # ASYNC_DATABASE_URL -> DATABASE_URL로 수정 (기존 설정에 맞춤)
        pool_pre_ping=True,
        pool_size=2,  # 워커용이므로 작은 풀 사이즈 사용
        max_overflow=5
    )
    
    AsyncSessionLocal = sessionmaker(
        autocommit=False, 
        autoflush=False, 
        bind=engine, 
        class_=AsyncSession
    )
    
    db = AsyncSessionLocal()
    try:
        yield db
    finally:
        await db.close()
        await engine.dispose()

async def process_recurring_payments():
    """정기결제 처리 로직"""
    logger.info("정기결제 스케줄러 시작...")
    
    try:
        async with get_worker_db() as db:
            due_subscriptions = await subscription_crud.get_due_subscriptions(db)
            
            if not due_subscriptions:
                logger.info("결제 대상 구독이 없습니다.")
                return
                
            logger.info(f"총 {len(due_subscriptions)}개의 구독에 대한 정기결제를 시도합니다.")
            
            success_count = 0
            fail_count = 0
            
            for sub in due_subscriptions:
                try:
                    logger.info(f"구독 ID: {sub.id} 결제 시도...")
                    await payment_service.charge_recurring_payment(db, sub)
                    logger.info(f"구독 ID: {sub.id} 결제 성공.")
                    success_count += 1
                except Exception as e:
                    logger.error(f"구독 ID: {sub.id} 결제 처리 중 오류 발생: {str(e)}")
                    fail_count += 1
                    continue
            
            logger.info(f"정기결제 처리 완료 - 성공: {success_count}건, 실패: {fail_count}건")
                    
    except Exception as e:
        logger.error(f"정기결제 스케줄러 실행 중 치명적 오류: {str(e)}")

def get_scheduler() -> Optional[object]:
    """현재 스케줄러 인스턴스를 반환합니다."""
    return _scheduler

# 하위 호환성을 위한 별칭 (기존 코드에서 scheduler를 직접 참조할 수 있도록)
def get_scheduler_instance():
    """스케줄러 인스턴스를 가져옵니다. 없으면 None을 반환합니다."""
    return init_scheduler()

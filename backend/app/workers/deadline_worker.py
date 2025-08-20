import logging
from typing import Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from ..core.config import settings

logger = logging.getLogger(__name__)

# 전역 스케줄러 인스턴스 (지연 로딩)
_deadline_scheduler = None

def init_scheduler():
    """
    마감일 처리 스케줄러를 초기화합니다. APScheduler가 설치되어 있지 않으면 None을 반환합니다.
    """
    global _deadline_scheduler
    
    if _deadline_scheduler is not None:
        return _deadline_scheduler
        
    try:
        # 지연 임포트: 패키지 없으면 여기서만 실패
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.jobstores.memory import MemoryJobStore
        from apscheduler.executors.asyncio import AsyncIOExecutor
        
        # 스케줄러 설정
        jobstores = {"default": MemoryJobStore()}
        executors = {"default": AsyncIOExecutor()}
        job_defaults = {"coalesce": False, "max_instances": 1}
        
        _deadline_scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone="Asia/Seoul"
        )
        
        # 마감일 처리 작업 등록 - 매일 새벽 1시에 실행
        _deadline_scheduler.add_job(
            process_deadlines_job,
            'cron', 
            hour=1, 
            minute=0,
            id='deadline_processing_job'
        )
        
        logger.info("마감일 처리 스케줄러가 초기화되었습니다.")
        return _deadline_scheduler
        
    except ModuleNotFoundError as e:
        logger.warning(
            "APScheduler가 설치되지 않았습니다. 마감일 처리 스케줄러 기능이 비활성화됩니다. "
            f"설치하려면 'pip install APScheduler>=3.10.4' 를 실행하세요. 오류: {str(e)}"
        )
        _deadline_scheduler = None
        return None
    except Exception as e:
        logger.error(f"마감일 처리 스케줄러 초기화 중 예외가 발생했습니다: {str(e)}")
        _deadline_scheduler = None
        return None

@asynccontextmanager
async def get_worker_db():
    """
    워커를 위한 새로운 데이터베이스 세션을 생성합니다.
    """
    engine = create_async_engine(
        settings.DATABASE_URL,
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

async def process_deadlines_job():
    """
    마감일을 처리하고 다음 회차를 생성하는 스케줄링 작업입니다.
    """
    logger.info("마감일 처리 스케줄러 시작...")
    
    try:
        async with get_worker_db() as db:
            # DeadlineService 임포트를 함수 내부로 이동 (순환 임포트 방지)
            try:
                from ..services.deadline_service import DeadlineService
                
                deadline_service = DeadlineService(db)
                closed_count, new_issue_count = await deadline_service.process_all_group_deadlines()
                
                logger.info(
                    f"마감일 처리 완료: "
                    f"{closed_count}개 회차 마감, {new_issue_count}개 신규 회차 생성"
                )
                
            except ImportError as ie:
                logger.warning(f"DeadlineService 모듈을 찾을 수 없습니다: {str(ie)}")
            except AttributeError as ae:
                logger.warning(f"DeadlineService 클래스 또는 메서드를 찾을 수 없습니다: {str(ae)}")
                
    except Exception as e:
        logger.error(f"마감일 처리 스케줄러 실행 중 치명적 오류: {str(e)}")

def get_scheduler() -> Optional[object]:
    """현재 마감일 처리 스케줄러 인스턴스를 반환합니다."""
    return _deadline_scheduler

# 하위 호환성을 위한 별칭
def get_scheduler_instance():
    """마감일 처리 스케줄러 인스턴스를 가져옵니다. 없으면 None을 반환합니다."""
    return init_scheduler()

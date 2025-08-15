import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.session import async_session_maker
from ..crud.family_crud import family_group_crud
from ..crud.issue_crud import issue_crud
from ..services.deadline_service import deadline_service
from ..models.issue import IssueStatus

logger = logging.getLogger(__name__)

class DeadlineWorker:
    """마감일 체크 및 회차 전환 워커"""
    
    def __init__(self):
        self.is_running = False
    
    async def check_deadlines(self):
        """모든 그룹의 마감일 체크"""
        async with async_session_maker() as db:
            try:
                # 활성 그룹들 조회
                groups = await family_group_crud.get_active_groups(db)
                
                for group in groups:
                    await self._process_group_deadline(db, group)
                    
            except Exception as e:
                logger.error(f"마감일 체크 중 오류: {e}")
    
    async def _process_group_deadline(self, db: AsyncSession, group):
        """개별 그룹의 마감일 처리"""
        try:
            # 현재 활성 회차 조회
            current_issue = await issue_crud.get_current_issue(db, group.id)
            
            if current_issue and deadline_service.is_deadline_passed(current_issue.deadline_date):
                # 회차 마감 처리
                await issue_crud.close_issue(db, current_issue.id)
                logger.info(f"회차 마감 처리: group_id={group.id}, issue_id={current_issue.id}")
                
                # 새 회차 생성
                next_deadline = deadline_service.calculate_next_deadline(group.deadline_type)
                new_issue_data = {
                    "group_id": group.id,
                    "issue_number": current_issue.issue_number + 1,
                    "deadline_date": next_deadline,
                    "status": IssueStatus.OPEN
                }
                await issue_crud.create(db, new_issue_data)
                logger.info(f"새 회차 생성: group_id={group.id}, deadline={next_deadline}")
                
        except Exception as e:
            logger.error(f"그룹 마감일 처리 오류: group_id={group.id}, error={e}")
    
    async def start_worker(self, interval_minutes: int = 60):
        """워커 시작 (1시간마다 실행)"""
        self.is_running = True
        logger.info("마감일 체크 워커 시작")
        
        while self.is_running:
            try:
                await self.check_deadlines()
                await asyncio.sleep(interval_minutes * 60)  # 분을 초로 변환
                
            except Exception as e:
                logger.error(f"워커 실행 중 오류: {e}")
                await asyncio.sleep(300)  # 오류 시 5분 대기
    
    def stop_worker(self):
        """워커 중지"""
        self.is_running = False
        logger.info("마감일 체크 워커 중지")

# 싱글톤 인스턴스
deadline_worker = DeadlineWorker()

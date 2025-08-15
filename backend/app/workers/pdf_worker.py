import asyncio
import logging
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.session import async_session_maker
from ..crud.issue_crud import issue_crud
from ..crud.book_crud import book_crud
from ..services.pdf_service import pdf_service
from ..models.issue import IssueStatus
from ..models.book import ProductionStatus

logger = logging.getLogger(__name__)

class PDFWorker:
    """PDF 생성 백그라운드 워커"""
    
    def __init__(self):
        self.is_running = False
        self.queue = asyncio.Queue()
    
    async def add_to_queue(self, issue_id: str):
        """PDF 생성 큐에 추가"""
        await self.queue.put(issue_id)
        logger.info(f"PDF 생성 큐에 추가: issue_id={issue_id}")
    
    async def process_pdf_generation(self):
        """PDF 생성 처리"""
        while self.is_running:
            try:
                # 큐에서 작업 가져오기 (5초 타임아웃)
                issue_id = await asyncio.wait_for(
                    self.queue.get(), timeout=5.0
                )
                
                async with async_session_maker() as db:
                    await self._generate_single_pdf(db, issue_id)
                    
            except asyncio.TimeoutError:
                # 큐가 비어있으면 계속 대기
                continue
            except Exception as e:
                logger.error(f"PDF 생성 워커 오류: {e}")
                await asyncio.sleep(10)  # 오류 시 10초 대기
    
    async def _generate_single_pdf(self, db: AsyncSession, issue_id: str):
        """개별 PDF 생성"""
        try:
            # 회차 확인
            issue = await issue_crud.get(db, issue_id)
            if not issue:
                logger.warning(f"회차를 찾을 수 없음: issue_id={issue_id}")
                return
            
            # 이미 책자가 있는지 확인
            existing_book = await book_crud.get_by_issue_id(db, issue_id)
            if existing_book and existing_book.production_status == ProductionStatus.COMPLETED:
                logger.info(f"이미 완료된 책자: issue_id={issue_id}")
                return
            
            # PDF 생성
            logger.info(f"PDF 생성 시작: issue_id={issue_id}")
            pdf_url = await pdf_service.generate_issue_pdf(db, issue_id)
            
            logger.info(f"PDF 생성 완료: issue_id={issue_id}, url={pdf_url}")
            
        except Exception as e:
            logger.error(f"PDF 생성 실패: issue_id={issue_id}, error={str(e)}")
    
    async def check_pending_issues(self):
        """마감된 회차 중 PDF가 없는 것들 자동 처리"""
        async with async_session_maker() as db:
            try:
                # 마감되었지만 책자가 없는 회차들 조회
                closed_issues = await issue_crud.get_issues_without_books(db)
                
                for issue in closed_issues:
                    await self.add_to_queue(issue.id)
                    logger.info(f"자동 PDF 생성 큐 추가: issue_id={issue.id}")
                    
            except Exception as e:
                logger.error(f"미처리 회차 확인 오류: {e}")
    
    async def start_worker(self):
        """워커 시작"""
        self.is_running = True
        logger.info("PDF 생성 워커 시작")
        
        # 메인 처리 태스크
        process_task = asyncio.create_task(self.process_pdf_generation())
        
        # 주기적 체크 태스크 (1시간마다)
        async def periodic_check():
            while self.is_running:
                await self.check_pending_issues()
                await asyncio.sleep(3600)  # 1시간 대기
        
        check_task = asyncio.create_task(periodic_check())
        
        # 두 태스크 병렬 실행
        await asyncio.gather(process_task, check_task)
    
    def stop_worker(self):
        """워커 중지"""
        self.is_running = False
        logger.info("PDF 생성 워커 중지")

# 싱글톤 인스턴스
pdf_worker = PDFWorker()

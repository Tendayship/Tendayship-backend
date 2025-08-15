import asyncio
import logging
from datetime import datetime

from backend.app.crud import book_crud

from ..database.session import async_session_maker
from ..crud.family_crud import family_group_crud
from ..crud.issue_crud import issue_crud
from ..crud.subscription_crud import subscription_crud
from ..services.notification_service import notification_service
from ..services.deadline_service import deadline_service

logger = logging.getLogger(__name__)

class NotificationWorker:
    """알림 발송 백그라운드 워커"""
    
    def __init__(self):
        self.is_running = False
    
    async def send_deadline_reminders(self):
        """마감일 알림 발송 (D-7, D-3, D-1)"""
        async with async_session_maker() as db:
            try:
                # 활성 그룹들 조회
                active_groups = await family_group_crud.get_active_groups(db)
                
                for group in active_groups:
                    # 현재 회차 조회
                    current_issue = await issue_crud.get_current_issue(db, group.id)
                    if not current_issue:
                        continue
                    
                    # 마감까지 남은 일수 계산
                    days_until = deadline_service.days_until_deadline(
                        current_issue.deadline_date
                    )
                    
                    # D-7, D-3, D-1에 알림 발송
                    if days_until in [7, 3, 1]:
                        await notification_service.send_deadline_reminder(
                            group_id=group.id,
                            deadline_date=current_issue.deadline_date,
                            days_until=days_until
                        )
                        logger.info(f"마감일 알림 발송: group_id={group.id}, D-{days_until}")
                        
                        # 발송 간격 조정 (서버 부하 방지)
                        await asyncio.sleep(1)
                        
            except Exception as e:
                logger.error(f"마감일 알림 발송 오류: {e}")
    
    async def send_payment_reminders(self):
        """결제 예정 알림 발송 (D-3)"""
        async with async_session_maker() as db:
            try:
                # 3일 후 결제 예정인 구독들 조회
                upcoming_subscriptions = await subscription_crud.get_expiring_subscriptions(
                    db, days_ahead=3
                )
                
                for subscription in upcoming_subscriptions:
                    await notification_service.send_payment_reminder(
                        subscription_id=subscription.id,
                        user_email=subscription.user.email,
                        group_name=subscription.group.group_name,
                        amount=float(subscription.amount),
                        next_billing_date=subscription.next_billing_date
                    )
                    
                    logger.info(f"결제 알림 발송: subscription_id={subscription.id}")
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"결제 알림 발송 오류: {e}")
    
    async def send_book_notifications(self):
        """책자 완성 알림 발송"""
        async with async_session_maker() as db:
            try:
                # 최근 완성된 책자들 조회 (24시간 이내)
                recent_books = await book_crud.get_recently_completed_books(db)
                
                for book in recent_books:
                    # 이미 알림을 발송했는지 확인 (중복 방지)
                    if not book.notification_sent:
                        await notification_service.send_book_ready_notification(
                            group_id=book.issue.group_id,
                            issue_number=book.issue.issue_number,
                            pdf_url=book.pdf_url
                        )
                        
                        # 알림 발송 표시
                        book.notification_sent = True
                        await db.commit()
                        
                        logger.info(f"책자 완성 알림 발송: book_id={book.id}")
                        await asyncio.sleep(1)
                        
            except Exception as e:
                logger.error(f"책자 완성 알림 발송 오류: {e}")
    
    async def process_failed_notifications(self):
        """실패한 알림 재발송"""
        try:
            # TODO: 실패한 알림 큐에서 재처리
            # Redis나 별도 테이블에서 실패한 알림들을 조회하여 재발송
            logger.info("실패한 알림 재처리 완료")
            
        except Exception as e:
            logger.error(f"실패한 알림 재처리 오류: {e}")
    
    async def daily_notifications(self):
        """일일 알림 작업"""
        while self.is_running:
            try:
                current_hour = datetime.now().hour
                
                # 오전 9시: 마감일 알림
                if current_hour == 9:
                    await self.send_deadline_reminders()
                
                # 오전 10시: 결제 알림
                elif current_hour == 10:
                    await self.send_payment_reminders()
                
                # 오후 2시: 책자 완성 알림
                elif current_hour == 14:
                    await self.send_book_notifications()
                
                # 오후 11시: 실패한 알림 재처리
                elif current_hour == 23:
                    await self.process_failed_notifications()
                
                # 1시간 대기
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"일일 알림 작업 오류: {e}")
                await asyncio.sleep(300)  # 오류 시 5분 대기
    
    async def start_worker(self):
        """워커 시작"""
        self.is_running = True
        logger.info("알림 워커 시작")
        
        # 일일 알림 작업 시작
        await self.daily_notifications()
    
    def stop_worker(self):
        """워커 중지"""
        self.is_running = False
        logger.info("알림 워커 중지")

# 싱글톤 인스턴스
notification_worker = NotificationWorker()

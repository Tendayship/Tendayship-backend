import smtplib
import logging
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from ..core.config import settings
from ..crud.family_crud import family_group_crud
from ..crud.member_crud import family_member_crud
from ..crud.subscription_crud import subscription_crud

logger = logging.getLogger(__name__)

class NotificationService:
    """알림 서비스 - 이메일, 푸시 알림 등"""
    
    def __init__(self):
        # 이메일 설정 (향후 SendGrid, AWS SES 등으로 확장 가능)
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.FROM_EMAIL
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """이메일 발송"""
        try:
            # MIME 메시지 생성
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            # 텍스트 내용
            if text_content:
                text_part = MIMEText(text_content, 'plain', 'utf-8')
                msg.attach(text_part)
            
            # HTML 내용
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # SMTP 발송
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"이메일 발송 성공: {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"이메일 발송 실패: {to_email}, 오류: {str(e)}")
            return False
    
    async def send_deadline_reminder(
        self,
        group_id: str,
        deadline_date: datetime,
        days_until: int
    ):
        """마감일 알림 발송"""
        try:
            # 그룹 멤버들 조회
            members = await family_member_crud.get_group_members(None, group_id)  # db 세션 필요
            
            if not members:
                return
            
            # 알림 내용 생성
            subject = f"📅 가족 소식 마감 D-{days_until} 알림"
            
            html_content = f"""
            <div style="font-family: 'Malgun Gothic', sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #018941, #4CAF50); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="margin: 0; font-size: 24px;">🏡 가족 소식 서비스</h1>
                </div>
                
                <div style="background: white; padding: 30px; border: 1px solid #e0e0e0; border-top: none;">
                    <h2 style="color: #018941; margin-top: 0;">마감일이 다가오고 있어요!</h2>
                    
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <p style="margin: 0; font-size: 18px; font-weight: bold; color: #d32f2f;">
                            ⏰ 마감까지 <span style="font-size: 24px;">{days_until}일</span> 남았습니다
                        </p>
                        <p style="margin: 10px 0 0 0; color: #666;">
                            마감일: {deadline_date.strftime('%Y년 %m월 %d일 %H시')}
                        </p>
                    </div>
                    
                    <p>아직 이번 달 소식을 올리지 않으셨다면, 지금 바로 가족들과 소중한 순간을 공유해보세요! 📸✍️</p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{settings.FRONTEND_URL}/posts/create" 
                           style="background: #018941; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                            소식 작성하기
                        </a>
                    </div>
                    
                    <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 30px 0;">
                    
                    <p style="color: #666; font-size: 14px; text-align: center;">
                        가족 소식 서비스 | 매달 전해지는 따뜻한 마음 💝
                    </p>
                </div>
            </div>
            """
            
            # 각 멤버에게 발송
            for member in members:
                if member.user.email:
                    await self.send_email(
                        to_email=member.user.email,
                        subject=subject,
                        html_content=html_content
                    )
                    
        except Exception as e:
            logger.error(f"마감일 알림 발송 실패: group_id={group_id}, 오류: {str(e)}")
    
    async def send_book_ready_notification(
        self,
        group_id: str,
        issue_number: int,
        pdf_url: str
    ):
        """책자 제작 완료 알림"""
        try:
            # 그룹 멤버들 조회
            members = await family_member_crud.get_group_members(None, group_id)
            
            if not members:
                return
            
            subject = f"📖 제{issue_number}호 가족 소식책자가 완성되었어요!"
            
            html_content = f"""
            <div style="font-family: 'Malgun Gothic', sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #018941, #4CAF50); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="margin: 0; font-size: 24px;">🏡 가족 소식 서비스</h1>
                </div>
                
                <div style="background: white; padding: 30px; border: 1px solid #e0e0e0; border-top: none;">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <div style="background: #018941; color: white; width: 80px; height: 80px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 36px; margin-bottom: 20px;">
                            📖
                        </div>
                        <h2 style="color: #018941; margin: 0;">책자 제작이 완료되었습니다!</h2>
                    </div>
                    
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center;">
                        <p style="margin: 0; font-size: 18px; font-weight: bold; color: #018941;">
                            제 {issue_number}호 가족 소식책자
                        </p>
                        <p style="margin: 10px 0 0 0; color: #666;">
                            온 가족이 함께 만든 소중한 추억들이 한 권의 책으로 완성되었어요! 💝
                        </p>
                    </div>
                    
                    <p>이제 앱에서 책자를 미리 보실 수 있으며, 곧 받는 분께 실물 책자가 배송될 예정입니다.</p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{settings.FRONTEND_URL}/books" 
                           style="background: #018941; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; margin-right: 10px;">
                            책자 보기
                        </a>
                        <a href="{pdf_url}" 
                           style="background: #fff; color: #018941; border: 2px solid #018941; padding: 13px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                            PDF 다운로드
                        </a>
                    </div>
                    
                    <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 30px 0;">
                    
                    <p style="color: #666; font-size: 14px; text-align: center;">
                        가족 소식 서비스 | 매달 전해지는 따뜻한 마음 💝
                    </p>
                </div>
            </div>
            """
            
            # 각 멤버에게 발송
            for member in members:
                if member.user.email:
                    await self.send_email(
                        to_email=member.user.email,
                        subject=subject,
                        html_content=html_content
                    )
                    
        except Exception as e:
            logger.error(f"책자 완성 알림 발송 실패: group_id={group_id}, 오류: {str(e)}")
    
    async def send_payment_reminder(
        self,
        subscription_id: str,
        user_email: str,
        group_name: str,
        amount: float,
        next_billing_date: datetime
    ):
        """결제 예정 알림"""
        try:
            subject = "💳 가족 소식 서비스 결제 예정 안내"
            
            html_content = f"""
            <div style="font-family: 'Malgun Gothic', sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #018941, #4CAF50); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="margin: 0; font-size: 24px;">🏡 가족 소식 서비스</h1>
                </div>
                
                <div style="background: white; padding: 30px; border: 1px solid #e0e0e0; border-top: none;">
                    <h2 style="color: #018941; margin-top: 0;">결제 예정 안내</h2>
                    
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <p style="margin: 0 0 10px 0; font-weight: bold;">📅 결제 예정일</p>
                        <p style="margin: 0; font-size: 18px; color: #018941;">
                            {next_billing_date.strftime('%Y년 %m월 %d일')}
                        </p>
                    </div>
                    
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <p style="margin: 0 0 10px 0; font-weight: bold;">💰 결제 금액</p>
                        <p style="margin: 0; font-size: 18px; color: #d32f2f;">
                            {amount:,.0f}원
                        </p>
                    </div>
                    
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <p style="margin: 0 0 10px 0; font-weight: bold;">👨‍👩‍👧‍👦 가족 그룹</p>
                        <p style="margin: 0; font-size: 16px;">
                            {group_name}
                        </p>
                    </div>
                    
                    <p>등록하신 결제 수단으로 자동 결제가 진행됩니다. 결제 수단을 변경하시려면 아래 버튼을 클릭해주세요.</p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{settings.FRONTEND_URL}/subscription/{subscription_id}" 
                           style="background: #018941; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                            구독 관리
                        </a>
                    </div>
                    
                    <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 30px 0;">
                    
                    <p style="color: #666; font-size: 14px; text-align: center;">
                        가족 소식 서비스 | 매달 전해지는 따뜻한 마음 💝
                    </p>
                </div>
            </div>
            """
            
            await self.send_email(
                to_email=user_email,
                subject=subject,
                html_content=html_content
            )
            
        except Exception as e:
            logger.error(f"결제 알림 발송 실패: subscription_id={subscription_id}, 오류: {str(e)}")

# 싱글톤 인스턴스
notification_service = NotificationService()

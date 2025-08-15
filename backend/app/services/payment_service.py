import requests
import uuid
from typing import Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta

from ..core.config import settings
from ..crud.subscription_crud import subscription_crud
from ..models.subscription import SubscriptionStatus

class PaymentService:
    """결제 처리 서비스 (카카오페이/PG사 연동)"""
    
    def __init__(self):
        # TODO: 실제 PG사 설정으로 변경
        self.kakao_pay_admin_key = settings.KAKAO_PAY_ADMIN_KEY
        self.pg_merchant_id = settings.PG_MERCHANT_ID
        self.pg_secret_key = settings.PG_SECRET_KEY
    
    async def create_subscription_payment(
        self,
        user_id: str,
        group_id: str,
        amount: Decimal = Decimal("6900"),
        payment_method: str = "kakao_pay"
    ) -> Dict[str, Any]:
        """구독 결제 생성"""
        
        if payment_method == "kakao_pay":
            return await self._create_kakao_pay_subscription(
                user_id, group_id, amount
            )
        else:
            return await self._create_pg_payment(
                user_id, group_id, amount, payment_method
            )
    
    async def _create_kakao_pay_subscription(
        self,
        user_id: str,
        group_id: str,
        amount: Decimal
    ) -> Dict[str, Any]:
        """카카오페이 정기결제 생성"""
        
        # 카카오페이 정기결제 API 호출
        headers = {
            "Authorization": f"KakaoAK {self.kakao_pay_admin_key}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "cid": "TCSUBSCRIP",  # 정기결제용 가맹점 코드
            "partner_order_id": f"sub_{group_id}_{int(datetime.now().timestamp())}",
            "partner_user_id": user_id,
            "item_name": "가족 소식 서비스 정기구독",
            "quantity": 1,
            "total_amount": int(amount),
            "vat_amount": int(amount / 11),  # 부가세 10%
            "tax_free_amount": 0,
            "approval_url": f"{settings.FRONTEND_URL}/payment/success",
            "fail_url": f"{settings.FRONTEND_URL}/payment/fail",
            "cancel_url": f"{settings.FRONTEND_URL}/payment/cancel"
        }
        
        try:
            response = requests.post(
                "https://kapi.kakao.com/v1/payment/ready",
                headers=headers,
                data=data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "payment_method": "kakao_pay",
                    "tid": result.get("tid"),
                    "next_redirect_pc_url": result.get("next_redirect_pc_url"),
                    "next_redirect_mobile_url": result.get("next_redirect_mobile_url"),
                    "partner_order_id": data["partner_order_id"]
                }
            else:
                raise Exception(f"카카오페이 API 오류: {response.text}")
                
        except Exception as e:
            raise Exception(f"결제 생성 실패: {str(e)}")
    
    async def approve_subscription_payment(
        self,
        tid: str,
        pg_token: str,
        partner_order_id: str
    ) -> Dict[str, Any]:
        """카카오페이 결제 승인"""
        
        headers = {
            "Authorization": f"KakaoAK {self.kakao_pay_admin_key}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "cid": "TCSUBSCRIP",
            "tid": tid,
            "partner_order_id": partner_order_id,
            "partner_user_id": partner_order_id.split("_")[1],  # user_id 추출
            "pg_token": pg_token
        }
        
        try:
            response = requests.post(
                "https://kapi.kakao.com/v1/payment/approve",
                headers=headers,
                data=data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "aid": result.get("aid"),
                    "sid": result.get("sid"),  # 정기결제용 SID
                    "amount": result.get("amount"),
                    "approved_at": result.get("approved_at")
                }
            else:
                raise Exception(f"결제 승인 실패: {response.text}")
                
        except Exception as e:
            raise Exception(f"결제 승인 오류: {str(e)}")
    
    async def process_monthly_billing(
        self,
        subscription_id: str,
        sid: str,
        amount: Decimal
    ) -> Dict[str, Any]:
        """월 정기결제 처리"""
        
        headers = {
            "Authorization": f"KakaoAK {self.kakao_pay_admin_key}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "cid": "TCSUBSCRIP",
            "sid": sid,
            "partner_order_id": f"monthly_{subscription_id}_{int(datetime.now().timestamp())}",
            "partner_user_id": subscription_id,
            "item_name": "가족 소식 서비스 월 정기결제",
            "quantity": 1,
            "total_amount": int(amount),
            "vat_amount": int(amount / 11),
            "tax_free_amount": 0
        }
        
        try:
            response = requests.post(
                "https://kapi.kakao.com/v1/payment/subscription",
                headers=headers,
                data=data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "aid": result.get("aid"),
                    "amount": result.get("amount"),
                    "approved_at": result.get("approved_at"),
                    "status": "success"
                }
            else:
                return {
                    "status": "failed",
                    "error": response.text
                }
                
        except Exception as e:
            return {
                "status": "failed", 
                "error": str(e)
            }
    
    async def cancel_subscription(
        self,
        sid: str,
        reason: str = "사용자 요청"
    ) -> Dict[str, Any]:
        """정기결제 해지"""
        
        headers = {
            "Authorization": f"KakaoAK {self.kakao_pay_admin_key}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "cid": "TCSUBSCRIP",
            "sid": sid
        }
        
        try:
            response = requests.post(
                "https://kapi.kakao.com/v1/payment/manage/subscription/inactive",
                headers=headers,
                data=data,
                timeout=10
            )
            
            if response.status_code == 200:
                return {"status": "cancelled", "cancelled_at": datetime.now()}
            else:
                raise Exception(f"구독 해지 실패: {response.text}")
                
        except Exception as e:
            raise Exception(f"구독 해지 오류: {str(e)}")

# 싱글톤 인스턴스
payment_service = PaymentService()

import logging
from typing import Dict, Any
from decimal import Decimal
from datetime import datetime
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..crud.subscription_crud import subscription_crud, payment_crud
from ..models.subscription import SubscriptionStatus, PaymentStatus

logger = logging.getLogger(__name__)

class KakaoPayService:
    """카카오페이 결제 서비스 (main.py 로직 기반)"""
    
    def __init__(self):
        self.secret_key = settings.KAKAO_PAY_SECRET_KEY
        self.cid = settings.KAKAO_PAY_CID  # 단건 결제용
        self.cid_subscription = settings.KAKAO_PAY_CID_SUBSCRIPTION  # 정기 결제용
        self.api_host = settings.KAKAO_PAY_API_HOST
        self.is_test_mode = settings.PAYMENT_MODE == "TEST"
        
        # 임시 저장소 (실제는 Redis 사용 권장)
        self._payment_cache: Dict[str, Dict] = {}
    
    def _get_headers(self) -> Dict[str, str]:
        """카카오페이 API 헤더"""
        if not self.secret_key:
            raise ValueError("카카오페이 시크릿 키가 설정되지 않았습니다. KAKAO_PAY_SECRET_KEY 환경변수를 확인하세요.")
        
        # 카카오페이 2024 업데이트된 형식 사용
        return {
            "Authorization": f"SECRET_KEY {self.secret_key}",
            "Content-Type": "application/json;charset=UTF-8",
        }
    
    async def create_single_payment(
        self,
        user_id: str,
        group_id: str,
        amount: Decimal = Decimal("6900")
    ) -> Dict[str, Any]:
        """
        단건 결제 준비 (main.py의 ready_payment 로직 적용)
        
        Returns:
            {
                "tid": "결제 고유번호",
                "next_redirect_pc_url": "PC 결제 URL",
                "next_redirect_mobile_url": "모바일 결제 URL",
                "partner_order_id": "주문번호",
                "partner_user_id": "사용자ID"
            }
        """
        try:
            # 주문 ID 생성
            partner_order_id = f"FNS_{group_id[:8]}_{int(datetime.now().timestamp())}"
            partner_user_id = str(user_id)
            
            headers = self._get_headers()
            
            payload = {
                "cid": self.cid,
                "partner_order_id": partner_order_id,
                "partner_user_id": partner_user_id,
                "item_name": "가족 소식 서비스 월 구독",
                "quantity": 1,
                "total_amount": int(amount),
                "tax_free_amount": 0,
                "approval_url": settings.PAYMENT_SUCCESS_URL,
                "cancel_url": settings.PAYMENT_CANCEL_URL,
                "fail_url": settings.PAYMENT_FAIL_URL,
            }
            
            url = f"{self.api_host}/online/v1/payment/ready"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code != 200:
                    error_data = response.json() if response.text else {}
                    logger.error(f"카카오페이 ready 실패: {response.status_code} - {error_data}")
                    raise Exception(f"결제 준비 실패: {error_data.get('msg', '알 수 없는 오류')}")
                
                result = response.json()
                tid = result.get("tid")
                
                # 결제 정보 캐시 저장 (approve 시 필요)
                self._payment_cache[tid] = {
                    "partner_order_id": partner_order_id,
                    "partner_user_id": partner_user_id,
                    "user_id": user_id,
                    "group_id": group_id,
                    "amount": amount,
                    "created_at": datetime.now()
                }
                
                logger.info(f"결제 준비 성공: tid={tid}, order_id={partner_order_id}")
                
                return {
                    "tid": tid,
                    "next_redirect_pc_url": result.get("next_redirect_pc_url"),
                    "next_redirect_mobile_url": result.get("next_redirect_mobile_url"),
                    "partner_order_id": partner_order_id,
                    "partner_user_id": partner_user_id
                }
                
        except httpx.RequestError as e:
            logger.error(f"카카오페이 API 요청 실패: {str(e)}")
            raise Exception(f"결제 서비스 연결 실패: {str(e)}")
        except Exception as e:
            logger.error(f"결제 준비 중 오류: {str(e)}")
            raise
    
    async def approve_payment(
        self,
        tid: str,
        pg_token: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        결제 승인 (main.py의 approve_payment 로직 적용)
        
        Returns:
            {
                "aid": "승인 번호",
                "tid": "결제 고유번호",
                "payment_method_type": "결제 수단",
                "amount": {...},
                "subscription_id": "구독 ID (DB)",
                "payment_id": "결제 ID (DB)"
            }
        """
        try:
            # 캐시에서 결제 정보 조회
            payment_info = self._payment_cache.get(tid)
            if not payment_info:
                raise ValueError(f"결제 정보를 찾을 수 없습니다: tid={tid}")
            
            headers = self._get_headers()
            
            payload = {
                "cid": self.cid,
                "tid": tid,
                "partner_order_id": payment_info["partner_order_id"],
                "partner_user_id": payment_info["partner_user_id"],
                "pg_token": pg_token,
            }
            
            url = f"{self.api_host}/online/v1/payment/approve"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code != 200:
                    error_data = response.json() if response.text else {}
                    logger.error(f"카카오페이 approve 실패: {response.status_code} - {error_data}")
                    raise Exception(f"결제 승인 실패: {error_data.get('msg', '알 수 없는 오류')}")
                
                result = response.json()
                aid = result.get("aid")
                
                # DB에 구독 및 결제 정보 저장
                subscription = await subscription_crud.create_subscription(
                    db=db,
                    group_id=payment_info["group_id"],
                    user_id=payment_info["user_id"],
                    billing_key=None,  # 단건 결제는 빌링키 없음
                    amount=payment_info["amount"]
                )
                
                payment = await payment_crud.create_payment(
                    db=db,
                    subscription_id=subscription.id,
                    transaction_id=aid,
                    amount=payment_info["amount"],
                    payment_method="kakao_pay",
                    status=PaymentStatus.SUCCESS
                )
                
                # 캐시 정리
                del self._payment_cache[tid]
                
                logger.info(f"결제 승인 성공: aid={aid}, subscription_id={subscription.id}")
                
                return {
                    "aid": aid,
                    "tid": tid,
                    "payment_method_type": result.get("payment_method_type"),
                    "amount": result.get("amount"),
                    "subscription_id": str(subscription.id),
                    "payment_id": str(payment.id),
                    "approved_at": result.get("approved_at")
                }
                
        except Exception as e:
            logger.error(f"결제 승인 중 오류: {str(e)}")
            # 실패 시 캐시 정리
            if tid in self._payment_cache:
                del self._payment_cache[tid]
            raise
    
    async def cancel_payment(
        self,
        tid: str,
        cancel_amount: int,
        cancel_reason: str = "사용자 요청"
    ) -> Dict[str, Any]:
        """결제 취소"""
        try:
            headers = self._get_headers()
            
            payload = {
                "cid": self.cid,
                "tid": tid,
                "cancel_amount": cancel_amount,
                "cancel_tax_free_amount": 0,
                "cancel_reason": cancel_reason
            }
            
            url = f"{self.api_host}/online/v1/payment/cancel"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code != 200:
                    error_data = response.json() if response.text else {}
                    raise Exception(f"결제 취소 실패: {error_data.get('msg', '알 수 없는 오류')}")
                
                result = response.json()
                logger.info(f"결제 취소 성공: tid={tid}")
                
                return result
                
        except Exception as e:
            logger.error(f"결제 취소 중 오류: {str(e)}")
            raise
    

# 싱글톤 인스턴스
payment_service = KakaoPayService()
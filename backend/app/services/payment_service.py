import logging
from typing import Dict, Any
from decimal import Decimal
from datetime import datetime
import httpx
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..crud.subscription_crud import subscription_crud, payment_crud
from ..models.subscription import  PaymentStatus

logger = logging.getLogger(__name__)

class KakaoPayService:
    """카카오페이 결제 서비스 (main.py 로직 기반)"""
    
    def __init__(self):
        self.secret_key = settings.KAKAO_PAY_SECRET_KEY
        self.cid = settings.KAKAO_PAY_CID  
        self.cid_subscription = settings.KAKAO_PAY_CID_SUBSCRIPTION 
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
        try:
            partner_order_id = f"FNS_{group_id[:8]}_{int(datetime.now().timestamp())}"
            partner_user_id = str(user_id)
            headers = self._get_headers()
            
            temp_payment_id = str(uuid.uuid4())
            

            approval_url_with_id = f"{settings.PAYMENT_SUCCESS_URL}?temp_id={temp_payment_id}"
            cancel_url_with_id = f"{settings.PAYMENT_CANCEL_URL}?temp_id={temp_payment_id}"
            fail_url_with_id = f"{settings.PAYMENT_FAIL_URL}?temp_id={temp_payment_id}"
            
            payload = {
                "cid": self.cid,
                "partner_order_id": partner_order_id,
                "partner_user_id": partner_user_id,
                "item_name": "가족 소식 서비스 월 구독",
                "quantity": 1,
                "total_amount": int(amount),
                "tax_free_amount": 0,
                "approval_url": approval_url_with_id,
                "cancel_url": cancel_url_with_id,
                "fail_url": fail_url_with_id,
            }

            url = f"{self.api_host}/online/v1/payment/ready"
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code != 200:
                    try:
                        error_data = response.json()
                        error_message = error_data.get('error_message', error_data.get('msg', '알 수 없는 오류'))
                    except Exception:
                        error_message = response.text if response.text else f"HTTP {response.status_code} 오류"
                    
                    logger.error(f"카카오페이 ready 실패: {response.status_code} - {error_message}")
                    raise Exception(f"결제 준비 실패: {error_message}")

                result = response.json()
                tid = result.get("tid")
                
                if not tid:
                    raise Exception("결제 TID를 받지 못했습니다.")
                
                payment_info = {
                    "tid": tid,
                    "partner_order_id": partner_order_id,
                    "partner_user_id": partner_user_id,
                    "user_id": user_id,
                    "group_id": group_id,
                    "amount": amount,
                    "created_at": datetime.now()
                }
                
                # temp_id와 tid 모두를 키로 저장
                self._payment_cache[temp_payment_id] = payment_info
                self._payment_cache[tid] = payment_info

                logger.info(f"결제 준비 성공: tid={tid}, temp_id={temp_payment_id}")
                
                return {
                    "tid": tid,
                    "next_redirect_pc_url": result.get("next_redirect_pc_url"),
                    "next_redirect_mobile_url": result.get("next_redirect_mobile_url"),
                    "partner_order_id": partner_order_id,
                    "partner_user_id": partner_user_id
                }

        except Exception as e:
            logger.error(f"결제 준비 중 오류: {str(e)}")
            raise
    
    async def approve_payment(
        self,
        tid: str,
        pg_token: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """결제 승인 - tid를 통한 안전한 검증"""
        try:
            # 1. 캐시에서 결제 정보 조회
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
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code != 200:
                    try:
                        error_data = response.json()
                        error_message = error_data.get('error_message', error_data.get('msg', '알 수 없는 오류'))
                    except Exception:
                        error_message = response.text if response.text else f"HTTP {response.status_code} 오류"
                    
                    logger.error(f"카카오페이 approve 실패: {response.status_code} - {error_message}")
                    raise Exception(f"결제 승인 실패: {error_message}")

                result = response.json()
                aid = result.get("aid")

  
                try:
                    # 구독 생성
                    subscription = await subscription_crud.create_subscription(
                        db=db,
                        group_id=payment_info["group_id"],
                        user_id=payment_info["user_id"],
                        amount=payment_info["amount"]
                    )


                    await db.flush()           # DB에 반영하여 ID 할당
                    await db.refresh(subscription)  # 할당된 ID를 객체에 로드

                    # 이제 subscription.id가 정상적으로 할당됨
                    payment = await payment_crud.create_payment(
                        db=db,
                        subscription_id=subscription.id,  
                        transaction_id=aid,
                        amount=payment_info["amount"],
                        payment_method="kakao_pay",
                        status=PaymentStatus.SUCCESS
                    )

                    # 트랜잭션 커밋
                    await db.commit()
                    
                    # 3. 캐시 정리
                    del self._payment_cache[tid]
                    
                    logger.info(f"결제 승인 성공: aid={aid}, subscription_id={subscription.id}")
                    
                    return {
                        "aid": aid,
                        "tid": tid,
                        "payment_method_type": result.get("payment_method_type"),
                        "amount": result.get("amount"),
                        "subscription_id": str(subscription.id),
                        "payment_id": str(payment.id),
                        "user_id": payment_info["user_id"],
                        "approved_at": result.get("approved_at")
                    }

                except Exception as db_error:
                    await db.rollback()
                    logger.error(f"DB 저장 실패: {str(db_error)}")
                    raise Exception(f"결제는 성공했으나 DB 저장 실패: {str(db_error)}")

        except Exception as e:
            logger.error(f"결제 승인 중 오류: {str(e)}")
            # 실패 시 캐시 정리
            if tid in self._payment_cache:
                del self._payment_cache[tid]
    
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

            logger.info(f"카카오페이 취소 요청: tid={tid}, amount={cancel_amount}, cid={self.cid}")

            url = f"{self.api_host}/online/v1/payment/cancel"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code != 200:
                    try:
                        error_data = response.json()
                        error_code = error_data.get('error_code', 'UNKNOWN')
                        error_message = error_data.get('error_message', error_data.get('msg', '알 수 없는 오류'))
                        
                        logger.error(f"카카오페이 취소 실패: code={error_code}, message={error_message}")
                        logger.error(f"요청 파라미터: {payload}")
                        
                        # 🔥 특정 에러 코드에 대한 명확한 메시지
                        if error_code == -721:
                            raise Exception(f"유효하지 않은 결제 ID이거나 이미 취소된 결제입니다 ({error_code}): {error_message}")
                        elif error_code == -780:
                            raise Exception(f"이미 취소된 결제입니다 ({error_code}): {error_message}")
                        else:
                            raise Exception(f"결제 취소 실패 ({error_code}): {error_message}")
                            
                    except Exception as parse_error:
                        if "결제 취소 실패" in str(parse_error):
                            raise parse_error
                        
                        error_text = response.text
                        logger.error(f"카카오페이 응답 파싱 실패: {str(parse_error)}, response_text={error_text}")
                        raise Exception(f"결제 취소 실패: HTTP {response.status_code} - {error_text}")

                result = response.json()
                logger.info(f"결제 취소 성공: tid={tid}")
                return result

        except Exception as e:
            logger.error(f"결제 취소 중 오류: {str(e)}")
            raise
    

# 싱글톤 인스턴스
payment_service = KakaoPayService()
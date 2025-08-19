import logging
from typing import Dict, Any
from decimal import Decimal
from datetime import datetime
import httpx
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.config import settings
from ..crud.subscription_crud import subscription_crud, payment_crud
from ..models.subscription import PaymentStatus

logger = logging.getLogger(__name__)

class KakaoPayService:
    
    def __init__(self):
        self.secret_key = settings.KAKAO_PAY_SECRET_KEY
        self.cid = settings.KAKAO_PAY_CID
        self.cid_subscription = settings.KAKAO_PAY_CID_SUBSCRIPTION
        self.api_host = settings.KAKAO_PAY_API_HOST
        self.is_test_mode = settings.PAYMENT_MODE == "TEST"
        self._payment_cache: Dict[str, Dict] = {}

    def _get_headers(self) -> Dict[str, str]:
        if not self.secret_key:
            raise ValueError("카카오페이 시크릿 키가 설정되지 않았습니다. KAKAO_PAY_SECRET_KEY 환경변수를 확인하세요.")
        return {
            "Authorization": f"SECRET_KEY {self.secret_key}",
            "Content-Type": "application/json;charset=UTF-8",
        }

    async def create_single_payment(self, user_id: str, group_id: str, amount: Decimal = Decimal("6900")) -> Dict[str, Any]:
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

    async def approve_payment(self, tid: str, pg_token: str, db: AsyncSession) -> Dict[str, Any]:
        try:
            payment_info = self._payment_cache.get(tid)
            if not payment_info:
                raise ValueError(f"결제 정보를 찾을 수 없습니다: tid={tid}")

            existing_subscription = await subscription_crud.get_by_group_id_simple(db, payment_info["group_id"])
            if existing_subscription:
                if tid in self._payment_cache:
                    del self._payment_cache[tid]
                raise Exception("이미 활성 구독이 존재합니다. 중복 구독은 허용되지 않습니다.")

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
                    recheck = await subscription_crud.get_by_group_id(db, payment_info["group_id"])
                    if recheck:
                        try:
                            await self.cancel_payment(tid=tid, cancel_amount=int(payment_info["amount"]), cancel_reason="중복 구독 방지")
                        except Exception as cp_e:
                            logger.error(f"중복 감지 후 결제 취소 실패(관리자 확인 필요): {str(cp_e)}")
                        if tid in self._payment_cache:
                            del self._payment_cache[tid]
                        raise Exception("이미 활성 구독이 존재합니다. 결제가 원복되었습니다.")

                    subscription = await subscription_crud.upsert_activate_subscription(
                        db=db,
                        group_id=payment_info["group_id"],
                        user_id=payment_info["user_id"],
                        amount=payment_info["amount"],
                    )
                    await db.flush()
                    await db.refresh(subscription)

                    payment = await payment_crud.create_payment(
                        db=db,
                        subscription_id=subscription.id,
                        transaction_id=aid,
                        amount=payment_info["amount"],
                        payment_method="kakao_pay",
                        status=PaymentStatus.SUCCESS,
                        pg_tid=tid,
                        pg_response=result,
                    )

                    await db.commit()
                    if tid in self._payment_cache:
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
                        "approved_at": result.get("approved_at"),
                    }

                except Exception as db_error:
                    await db.rollback()
                    logger.error(f"DB 저장 실패: {str(db_error)}")
                    try:
                        await self.cancel_payment(tid=tid, cancel_amount=int(payment_info["amount"]), cancel_reason="DB 저장 실패 원복")
                    except Exception as cp_e:
                        logger.error(f"DB 실패 후 결제 취소(원복)도 실패(관리자 확인 필요): {str(cp_e)}")
                    if tid in self._payment_cache:
                        del self._payment_cache[tid]
                    if "unique" in str(db_error).lower() and "group_id" in str(db_error).lower():
                        raise Exception("이미 활성 구독이 존재합니다. 결제가 원복되었습니다.")
                    raise Exception(f"결제 승인 후 내부 저장 실패로 결제를 원복했습니다: {str(db_error)}")

        except Exception as e:
            logger.error(f"결제 승인 중 오류: {str(e)}")
            if tid in self._payment_cache:
                del self._payment_cache[tid]
            raise

    async def cancel_payment(self, tid: str, cancel_amount: int, cancel_reason: str = "사용자 요청") -> Dict[str, Any]:
        try:
            headers = self._get_headers()
            payload = {
                "cid": self.cid,
                "tid": tid,
                "cancel_amount": cancel_amount,
                "cancel_tax_free_amount": 0,
                "cancel_reason": cancel_reason,
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

payment_service = KakaoPayService()

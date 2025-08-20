import logging
from sqlalchemy.ext.asyncio import AsyncSession
from ..crud.subscription_crud import subscription_crud, payment_crud
from ..models.subscription import SubscriptionStatus, PaymentStatus
from ..services.payment_service import payment_service

logger = logging.getLogger(__name__)

class SubscriptionAdminService:
    """구독 관리 전용 서비스 - 관리자/리더 그룹 삭제에서 사용"""
    
    async def cancel_active_subscription_if_any(self, db: AsyncSession, group_id: str) -> dict:
        """
        활성 구독이 있다면 취소 처리
        - 최근 결제 환불 시도
        - 구독 상태를 CANCELLED로 변경
        """
        # 활성 구독 조회
        sub = await subscription_crud.get_by_group_id_simple(db, group_id)
        if not sub:
            return {"cancelled": False, "reason": "no_active_subscription"}
        
        # 최근 결제 환불 시도
        recent = await payment_crud.get_recent_payment(db, str(sub.id))
        payment_cancel_status = "no_payment"
        refund_amount = 0
        
        if recent:
            # PG TID 확인 (pg_tid 우선, 없으면 pg_response에서 tid 추출)
            tid_for_cancel = recent.pg_tid or (
                recent.pg_response.get("tid") if getattr(recent, "pg_response", None) else None
            )
            
            if tid_for_cancel:
                try:
                    # 카카오페이 결제 취소 시도
                    await payment_service.cancel_payment(
                        tid=tid_for_cancel, 
                        cancel_amount=int(recent.amount), 
                        cancel_reason="group_delete"
                    )
                    refund_amount = recent.amount
                    payment_cancel_status = "success"
                    # 결제 레코드를 REFUNDED 상태로 변경
                    await payment_crud.mark_refunded(db, recent.id)
                    
                except Exception as e:
                    error_str = str(e)
                    # 카카오페이 특정 에러 코드 처리
                    if "invalid" in error_str.lower() or "-721" in error_str or "-780" in error_str:
                        payment_cancel_status = "already_cancelled"
                        refund_amount = recent.amount
                        logger.warning(f"이미 취소된 결제 감지: {error_str}")
                    else:
                        payment_cancel_status = "failed"
                        logger.error(f"결제 취소 실패: {error_str}")
        
        # 구독 취소 처리
        await subscription_crud.cancel_subscription(db, str(sub.id), reason="group_delete")
        
        # 커밋은 호출자에서 처리
        return {
            "cancelled": True,
            "subscription_id": str(sub.id),
            "payment_cancel_status": payment_cancel_status,
            "refund_amount": refund_amount
        }
    
    async def hard_delete_subscription_by_group(self, db: AsyncSession, group_id: str) -> int:
        """
        그룹의 구독 완전 삭제
        - cascade 설정으로 결제/이력도 함께 삭제됨
        """
        # 그룹의 구독 조회 (취소된 것 포함)
        sub = await subscription_crud.get_any_by_group_id(db, group_id)
        if not sub:
            return 0
        
        # 구독 삭제 (cascade로 결제/이력도 삭제)
        await db.delete(sub)
        logger.info(f"구독 삭제 완료: subscription_id={sub.id}, group_id={group_id}")
        
        # 커밋은 호출자에서 처리
        return 1

# 싱글톤 인스턴스
subscription_admin_service = SubscriptionAdminService()
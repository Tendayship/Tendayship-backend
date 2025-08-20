from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal
import logging

from ...core.config import settings
from ...database.session import get_db
from ...api.dependencies import get_current_user
from ...models.user import User
from ...models.subscription import SubscriptionStatus
from ...crud.subscription_crud import subscription_crud, payment_crud
from ...crud.member_crud import family_member_crud
from ...services.payment_service import payment_service
from ...schemas.subscription import (
    SubscriptionHistoryResponse,
    SubscriptionResponse,
    PaymentReadyResponse,
)
from ...core.constants import ROLE_LEADER

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscription", tags=["subscription"])

@router.post("/payment/ready", response_model=PaymentReadyResponse)
async def ready_payment(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    새로운 정기결제 구독을 위한 첫 결제를 준비합니다.
    """
    membership = await family_member_crud.check_user_membership(db, current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="가족 그룹에 속해있지 않습니다."
        )

    role_value = membership.role.value if hasattr(membership.role, 'value') else str(membership.role)
    if role_value != ROLE_LEADER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="그룹 리더만 구독을 생성할 수 있습니다."
        )

    existing_subscription = await subscription_crud.get_by_group_id_simple(db, membership.group_id)
    if existing_subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이 그룹에는 이미 활성 구독이 존재합니다."
        )

    try:
        # 정기결제 흐름을 시작하기 위해 is_subscription=True 플래그를 전달합니다.
        payment_result = await payment_service.create_payment_ready(
            user_id=str(current_user.id),
            group_id=str(membership.group_id),
            amount=Decimal("6900"),
            is_subscription=True
        )

        return PaymentReadyResponse(
            tid=payment_result["tid"],
            next_redirect_pc_url=payment_result["next_redirect_pc_url"],
            next_redirect_mobile_url=payment_result["next_redirect_mobile_url"],
            partner_order_id=payment_result["partner_order_id"],
        )
    except Exception as e:
        logger.error(f"결제 준비 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"결제 준비에 실패했습니다: {str(e)}"
        )

@router.get("/approve")
async def approve_payment(
    pg_token: str,
    temp_id: str = Query(..., description="임시 결제 ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    사용자가 카카오페이 인증 후 결제를 승인합니다.
    """
    try:
        payment_info = payment_service._payment_cache.get(temp_id)
        if not payment_info:
            raise Exception(f"임시 ID({temp_id})에 해당하는 결제 정보를 찾을 수 없습니다.")

        actual_tid = payment_info.get("tid")
        if not actual_tid:
            raise Exception("캐시된 정보에서 결제 TID를 찾을 수 없습니다.")

        approval_result = await payment_service.approve_payment(
            tid=actual_tid,
            pg_token=pg_token,
            db=db,
        )

        # 캐시 정리
        if temp_id in payment_service._payment_cache:
            del payment_service._payment_cache[temp_id]
        if actual_tid in payment_service._payment_cache:
            del payment_service._payment_cache[actual_tid]

        frontend_url = f"{settings.FRONTEND_URL}/subscription/success"
        return RedirectResponse(
            url=f"{frontend_url}?subscription_id={approval_result['subscription_id']}"
        )
    except Exception as e:
        logger.error(f"결제 승인 실패: {str(e)}")
        if temp_id in payment_service._payment_cache:
            del payment_service._payment_cache[temp_id]
        frontend_url = f"{settings.FRONTEND_URL}/subscription/fail"
        return RedirectResponse(url=f"{frontend_url}?error={str(e)}")

@router.get("/cancel")
async def cancel_payment():
    """사용자를 프론트엔드의 결제 취소 페이지로 리디렉션합니다."""
    frontend_url = f"{settings.FRONTEND_URL}/subscription/cancel"
    return RedirectResponse(url=frontend_url)

@router.get("/fail")
async def fail_payment():
    """사용자를 프론트엔드의 결제 실패 페이지로 리디렉션합니다."""
    frontend_url = f"{settings.FRONTEND_URL}/subscription/fail"
    return RedirectResponse(url=frontend_url)

@router.get("/my", response_model=List[SubscriptionResponse])
async def get_my_subscriptions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(None, description="상태 필터: 'all'은 전체, 그 외에는 'active'만 조회"),
):
    """현재 사용자의 구독 목록을 조회합니다."""
    normalized_filter = (status_filter or "").strip().lower()
    all_subs = await subscription_crud.get_by_user_id(db, current_user.id)

    if normalized_filter == "all":
        target_subs = all_subs
    else:
        target_subs = [sub for sub in all_subs if sub.status == SubscriptionStatus.ACTIVE]

    return [SubscriptionResponse.from_orm(sub) for sub in target_subs]


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription_detail(
    subscription_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """특정 구독의 상세 정보를 조회합니다."""
    subscription = await subscription_crud.get(db, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="구독을 찾을 수 없습니다.",
        )

    # 사용자가 구독 소유자이거나 구독 그룹의 멤버인지 확인
    if subscription.user_id != current_user.id:
        membership = await family_member_crud.get_by_user_and_group(
            db, current_user.id, subscription.group_id
        )
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="이 구독 정보에 접근할 권한이 없습니다.",
            )

    return SubscriptionResponse.from_orm(subscription)

@router.post("/{subscription_id}/cancel")
async def cancel_subscription(
    subscription_id: str,
    reason: str = "사용자 요청",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사용자의 활성 구독을 취소합니다."""
    subscription = await subscription_crud.get(db, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="구독을 찾을 수 없습니다.",
        )

    if subscription.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 구독만 취소할 수 있습니다.",
        )

    if subscription.status == SubscriptionStatus.CANCELLED:
        return {
            "message": "이미 취소된 구독입니다.",
            "cancelled_at": subscription.end_date,
        }

    try:
        # 최근 결제에 대한 환불 시도 로직
        recent_payment = await payment_crud.get_recent_payment(db, subscription_id)
        refund_amount = 0
        payment_cancel_status = "환불할 결제 내역 없음"

        if recent_payment and recent_payment.pg_tid:
            try:
                await payment_service.cancel_payment(
                    tid=recent_payment.pg_tid,
                    cancel_amount=int(recent_payment.amount),
                    cancel_reason=reason,
                )
                refund_amount = recent_payment.amount
                payment_cancel_status = "환불 성공"
                await payment_crud.mark_refunded(db, recent_payment.id)
                logger.info(f"구독 ID {subscription_id}에 대한 결제 환불에 성공했습니다.")
            except Exception as payment_error:
                error_str = str(payment_error)
                logger.warning(f"환불은 실패했지만 구독 취소는 진행합니다: {error_str}")
                payment_cancel_status = "환불 실패"

        # 환불 상태와 관계없이 데이터베이스에서 구독 취소 처리
        cancelled_subscription = await subscription_crud.cancel_subscription(db, subscription_id, reason)
        await db.commit()

        return {
            "message": "구독이 성공적으로 취소되었습니다.",
            "cancelled_at": cancelled_subscription.end_date,
            "refund_amount": refund_amount,
            "payment_cancel_status": payment_cancel_status,
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"구독 취소 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"구독 취소 중 오류가 발생했습니다: {str(e)}",
        )

@router.get("/my/history", response_model=List[SubscriptionHistoryResponse])
async def get_subscription_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """현재 사용자의 모든 구독 이력을 조회합니다."""
    subscriptions = await subscription_crud.get_by_user_id(db, current_user.id)
    
    all_history = []
    for sub in subscriptions:
        for hist in sub.history:
            all_history.append(SubscriptionHistoryResponse.from_orm(hist))
    
    return sorted(all_history, key=lambda x: x.created_at, reverse=True)

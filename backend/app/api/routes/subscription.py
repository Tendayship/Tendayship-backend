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
    membership = await family_member_crud.check_user_membership(db, current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="가족 그룹에 속해있지 않습니다"
        )

    role_value = membership.role.value if hasattr(membership.role, 'value') else str(membership.role)
    if role_value != ROLE_LEADER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="그룹 리더만 구독을 생성할 수 있습니다"
        )

    existing_subscription = await subscription_crud.get_by_group_id_simple(db, membership.group_id)
    if existing_subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 활성 구독이 존재합니다"
        )

    try:
        payment_result = await payment_service.create_single_payment(
            user_id=str(current_user.id),
            group_id=str(membership.group_id),
            amount=Decimal("6900"),
        )

        return PaymentReadyResponse(
            tid=payment_result["tid"],
            next_redirect_pc_url=payment_result["next_redirect_pc_url"],
            next_redirect_mobile_url=payment_result["next_redirect_mobile_url"],
            partner_order_id=payment_result["partner_order_id"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"결제 준비 중 오류: {str(e)}"
        )

@router.get("/approve")
async def approve_payment(
    pg_token: str,
    temp_id: str = Query(..., description="임시 결제 ID"),
    db: AsyncSession = Depends(get_db),
):
    try:
        payment_info = payment_service._payment_cache.get(temp_id)
        if not payment_info:
            raise Exception(f"결제 정보를 찾을 수 없습니다: temp_id={temp_id}")

        actual_tid = payment_info.get("tid")
        if not actual_tid:
            raise Exception("결제 TID를 찾을 수 없습니다")

        approval_result = await payment_service.approve_payment(
            tid=actual_tid,
            pg_token=pg_token,
            db=db,
        )

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
    frontend_url = f"{settings.FRONTEND_URL}/subscription/cancel"
    return RedirectResponse(url=frontend_url)

@router.get("/fail")
async def fail_payment():
    frontend_url = f"{settings.FRONTEND_URL}/subscription/fail"
    return RedirectResponse(url=frontend_url)

@router.get("/my", response_model=List[SubscriptionResponse])
async def get_my_subscriptions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(None, description="all이면 전체, 기본(None)은 활성만"),
):
    normalized = (status_filter or "").strip().lower()
    all_subs = await subscription_crud.get_by_user_id(db, current_user.id)

    if normalized == "all":
        target = all_subs
    else:
        target = [sub for sub in all_subs if sub.status == SubscriptionStatus.ACTIVE]

    return [
        SubscriptionResponse(
            id=str(sub.id),
            group_id=str(sub.group_id),
            user_id=str(sub.user_id),
            status=sub.status,
            start_date=sub.start_date,
            end_date=sub.end_date,
            next_billing_date=sub.next_billing_date,
            amount=sub.amount,
            created_at=sub.created_at,
            updated_at=sub.updated_at,
        )
        for sub in target
    ]

@router.get("/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription_detail(
    subscription_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    subscription = await subscription_crud.get(db, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="구독을 찾을 수 없습니다",
        )

    if subscription.user_id != current_user.id:
        membership = await family_member_crud.get_by_user_and_group(
            db, current_user.id, subscription.group_id
        )
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="이 구독 정보에 접근할 권한이 없습니다",
            )

    return SubscriptionResponse(
        id=str(subscription.id),
        group_id=str(subscription.group_id),
        user_id=str(subscription.user_id),
        status=subscription.status,
        start_date=subscription.start_date,
        end_date=subscription.end_date,
        next_billing_date=subscription.next_billing_date,
        amount=subscription.amount,
        created_at=subscription.created_at,
        updated_at=subscription.updated_at,
    )

@router.post("/{subscription_id}/cancel")
async def cancel_subscription(
    subscription_id: str,
    reason: str = "사용자 요청",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    subscription = await subscription_crud.get(db, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="구독을 찾을 수 없습니다",
        )

    if subscription.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 구독만 취소할 수 있습니다",
        )

    if subscription.status == SubscriptionStatus.CANCELLED:
        return {
            "message": "이미 취소된 구독입니다",
            "cancelled_at": subscription.end_date,
            "refund_amount": 0,
        }

    try:
        recent_payment = await payment_crud.get_recent_payment(db, subscription_id)
        refund_amount = 0
        payment_cancel_status = "no_payment"

        if recent_payment:
            tid_for_cancel = None
            
            if getattr(recent_payment, "pg_tid", None):
                tid_for_cancel = recent_payment.pg_tid
            elif getattr(recent_payment, "pg_response", None) and recent_payment.pg_response.get("tid"):
                tid_for_cancel = recent_payment.pg_response.get("tid")

            if tid_for_cancel:
                try:
                    await payment_service.cancel_payment(
                        tid=tid_for_cancel,
                        cancel_amount=int(recent_payment.amount),
                        cancel_reason=reason,
                    )
                    refund_amount = recent_payment.amount
                    payment_cancel_status = "success"
                    await payment_crud.mark_refunded(db, recent_payment.id)
                    logger.info(f"결제 취소 성공: subscription_id={subscription_id}")
                except Exception as payment_error:
                    error_str = str(payment_error)
                    logger.warning(f"결제 취소 실패하지만 구독은 취소 처리: {error_str}")
                    if "invalid tid" in error_str or "-721" in error_str or "-780" in error_str:
                        payment_cancel_status = "already_cancelled"
                        refund_amount = recent_payment.amount
                    else:
                        payment_cancel_status = "failed"
            else:
                payment_cancel_status = "failed"

        cancelled_subscription = await subscription_crud.cancel_subscription(db, subscription_id, reason)
        await db.commit()

        return {
            "message": "구독이 취소되었습니다",
            "cancelled_at": cancelled_subscription.end_date,
            "refund_amount": refund_amount,
            "payment_cancel_status": payment_cancel_status,
            "details": {
                "success": payment_cancel_status == "success",
                "already_cancelled": payment_cancel_status == "already_cancelled",
                "payment_failed": payment_cancel_status == "failed",
            },
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"구독 취소 중 오류: {str(e)}",
        )

    
@router.get("/my/history", response_model=List[SubscriptionHistoryResponse])
async def get_subscription_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """구독 이력 조회 (취소/재활성화 포함)"""
    subscriptions = await subscription_crud.get_by_user_id(db, current_user.id)
    
    all_history = []
    for sub in subscriptions:
        for hist in sub.history:
            all_history.append(SubscriptionHistoryResponse(
                id=str(hist.id),
                subscription_id=str(hist.subscription_id),
                action=hist.action,
                status=hist.status,
                start_date=hist.start_date,
                end_date=hist.end_date,
                cancel_reason=hist.cancel_reason,
                amount=hist.amount,
                created_at=hist.created_at
            ))
    
    return sorted(all_history, key=lambda x: x.created_at, reverse=True)
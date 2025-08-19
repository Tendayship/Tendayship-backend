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
    SubscriptionResponse,
    PaymentReadyResponse,
)
from ...core.constants import ROLE_LEADER

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscription", tags=["subscription"])

# ===== 단건 결제 플로우 =====

@router.post("/payment/ready", response_model=PaymentReadyResponse)
async def ready_payment(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 1. 사용자의 그룹 멤버십 확인
    membership = await family_member_crud.check_user_membership(db, current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="가족 그룹에 속해있지 않습니다"
        )

    # 2. 그룹 리더인지 확인
    role_value = membership.role.value if hasattr(membership.role, 'value') else str(membership.role)
    if role_value != ROLE_LEADER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="그룹 리더만 구독을 생성할 수 있습니다"
        )

    # 3. 기존 활성 구독 확인 - 개선된 메서드 사용
    existing_subscription = await subscription_crud.get_by_group_id_simple(db, membership.group_id)
    if existing_subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 활성 구독이 존재합니다"
        )

    try:
        # 4. 카카오페이 결제 준비
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
    """
    결제 승인 - 카카오페이 리다이렉트 후 처리
    1) temp_id로 캐시에서 tid 조회
    2) tid + pg_token으로 카카오페이 승인
    3) 구독/결제 기록 DB 저장
    4) 성공 페이지로 리다이렉트
    """
    try:
        # temp_id로 결제 정보 조회
        payment_info = payment_service._payment_cache.get(temp_id)
        if not payment_info:
            raise Exception(f"결제 정보를 찾을 수 없습니다: temp_id={temp_id}")

        actual_tid = payment_info.get("tid")
        if not actual_tid:
            raise Exception("결제 TID를 찾을 수 없습니다")

        # 결제 승인 처리
        approval_result = await payment_service.approve_payment(
            tid=actual_tid,
            pg_token=pg_token,
            db=db,
        )

        # 성공 시 캐시 정리
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
        # 실패 시에도 캐시 정리
        if temp_id in payment_service._payment_cache:
            del payment_service._payment_cache[temp_id]
        frontend_url = f"{settings.FRONTEND_URL}/subscription/fail"
        return RedirectResponse(url=f"{frontend_url}?error={str(e)}")

@router.get("/cancel")
async def cancel_payment():
    """결제 취소 - 사용자가 결제창에서 취소"""
    frontend_url = f"{settings.FRONTEND_URL}/subscription/cancel"
    return RedirectResponse(url=frontend_url)

@router.get("/fail")
async def fail_payment():
    """결제 실패"""
    frontend_url = f"{settings.FRONTEND_URL}/subscription/fail"
    return RedirectResponse(url=frontend_url)

# ===== 구독 관리 API =====

@router.get("/my", response_model=List[SubscriptionResponse])
async def get_my_subscriptions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(None, description="all이면 전체, 기본(None)은 활성만"),
):
    """
    내 구독 목록 조회
    - 기본: 활성만
    - status_filter=all: 전체(취소/만료 포함)
    """
    # 파라미터 정규화
    normalized = (status_filter or "").strip().lower()
    all_subs = await subscription_crud.get_by_user_id(db, current_user.id)

    if normalized == "all":
        target = all_subs
    else:
        # 🔥 핵심 수정: Enum 객체와 직접 비교
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
    """구독 상세 정보"""
    subscription = await subscription_crud.get(db, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="구독을 찾을 수 없습니다",
        )

    # 권한 확인
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
    """구독 취소 (환불)"""
    subscription = await subscription_crud.get(db, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="구독을 찾을 수 없습니다",
        )

    # 권한 확인
    if subscription.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 구독만 취소할 수 있습니다",
        )

    # 이미 취소된 구독
    if subscription.status == SubscriptionStatus.CANCELLED:
        return {
            "message": "이미 취소된 구독입니다",
            "cancelled_at": subscription.end_date,
            "refund_amount": 0,
        }

    try:
        # 최근 결제 내역 조회
        recent_payment = await payment_crud.get_recent_payment(db, subscription_id)
        refund_amount = 0
        payment_cancel_status = "no_payment"

        # 결제 취소 시도 (실패해도 구독 취소는 진행)
        if recent_payment and recent_payment.transaction_id:
            try:
                await payment_service.cancel_payment(
                    tid=recent_payment.transaction_id,
                    cancel_amount=int(recent_payment.amount),
                    cancel_reason=reason,
                )
                refund_amount = recent_payment.amount
                payment_cancel_status = "success"
                logger.info(f"결제 취소 성공: subscription_id={subscription_id}")
            except Exception as payment_error:
                logger.warning(f"결제 취소 실패하지만 구독은 취소 처리: {str(payment_error)}")
                error_str = str(payment_error)
                if "invalid tid" in error_str or "-721" in error_str:
                    payment_cancel_status = "already_cancelled"
                else:
                    payment_cancel_status = "failed"

        # 구독 상태 변경 (결제 취소 성공 여부와 관계없이 진행)
        cancelled_subscription = await subscription_crud.cancel_subscription(
            db, subscription_id, reason
        )

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

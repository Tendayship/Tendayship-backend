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
from ...crud.subscription_crud import subscription_crud, payment_crud
from ...crud.member_crud import family_member_crud
from ...services.payment_service import payment_service
from ...schemas.subscription import (
    SubscriptionCreate, 
    SubscriptionResponse, 
    PaymentResponse,
    PaymentReadyResponse,  # 새로 추가
    PaymentApproveRequest   # 새로 추가
)
from ...core.constants import ROLE_LEADER

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/subscription", tags=["subscription"])

# ===== 단건 결제 플로우 (우선 구현) =====

@router.post("/payment/ready", response_model=PaymentReadyResponse)
async def ready_payment(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 1. 사용자의 그룹 멤버십 확인
    membership = await family_member_crud.check_user_membership(db, current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="가족 그룹에 속해있지 않습니다"
        )

    # 2. 그룹 리더인지 확인 (Enum 처리)
    role_value = membership.role.value if hasattr(membership.role, 'value') else str(membership.role)
    if role_value != ROLE_LEADER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="그룹 리더만 구독을 생성할 수 있습니다"
        )
    
    # 3. 기존 활성 구독 확인
    existing_subscription = await subscription_crud.get_by_group_id(
        db, membership.group_id
    )
    if existing_subscription and existing_subscription.status == "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 활성 구독이 존재합니다"
        )
    
    try:
        # 4. 카카오페이 결제 준비
        payment_result = await payment_service.create_single_payment(
            user_id=str(current_user.id),
            group_id=str(membership.group_id),
            amount=Decimal("6900")
        )
        
        return PaymentReadyResponse(
            tid=payment_result["tid"],
            next_redirect_pc_url=payment_result["next_redirect_pc_url"],
            next_redirect_mobile_url=payment_result["next_redirect_mobile_url"],
            partner_order_id=payment_result["partner_order_id"]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"결제 준비 중 오류: {str(e)}"
        )

@router.get("/approve")
async def approve_payment(
    pg_token: str,
    tid: str = Query(..., description="결제 고유번호"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    결제 승인 - 카카오페이에서 리다이렉트 후 처리
    
    1. pg_token과 tid로 결제 승인
    2. 구독 정보 DB 저장
    3. 결제 내역 DB 저장
    4. 성공 페이지로 리다이렉트
    """
    
    try:
        # 결제 승인 처리
        approval_result = await payment_service.approve_payment(
            tid=tid,
            pg_token=pg_token,
            db=db
        )
        
        # 프론트엔드 성공 페이지로 리다이렉트
        frontend_url = f"{settings.FRONTEND_URL}/subscription/success"
        return RedirectResponse(
            url=f"{frontend_url}?subscription_id={approval_result['subscription_id']}"
        )
        
    except Exception as e:
        logger.error(f"결제 승인 실패: {str(e)}")
        # 실패 페이지로 리다이렉트
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

# ===== 기존 구독 관리 API =====

@router.get("/my", response_model=List[SubscriptionResponse])
async def get_my_subscriptions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """내 구독 목록 조회"""
    subscriptions = await subscription_crud.get_by_user_id(db, current_user.id)
    return subscriptions

@router.get("/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription_detail(
    subscription_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """구독 상세 정보"""
    subscription = await subscription_crud.get(db, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="구독을 찾을 수 없습니다"
        )
    
    # 권한 확인
    if subscription.user_id != current_user.id:
        membership = await family_member_crud.get_by_user_and_group(
            db, current_user.id, subscription.group_id
        )
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="이 구독 정보에 접근할 권한이 없습니다"
            )
    
    return subscription

@router.post("/{subscription_id}/cancel")
async def cancel_subscription(
    subscription_id: str,
    reason: str = "사용자 요청",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """구독 취소 (환불)"""
    
    subscription = await subscription_crud.get(db, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="구독을 찾을 수 없습니다"
        )
    
    # 권한 확인
    if subscription.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 구독만 취소할 수 있습니다"
        )
    
    try:
        # 최근 결제 내역 조회
        recent_payment = await payment_crud.get_recent_payment(db, subscription_id)
        if recent_payment and recent_payment.transaction_id:
            # 카카오페이 결제 취소
            await payment_service.cancel_payment(
                tid=recent_payment.transaction_id,
                cancel_amount=int(recent_payment.amount),
                cancel_reason=reason
            )
        
        # 구독 상태 변경
        cancelled_subscription = await subscription_crud.cancel_subscription(
            db, subscription_id, reason
        )
        
        return {
            "message": "구독이 취소되었습니다",
            "cancelled_at": cancelled_subscription.end_date,
            "refund_amount": recent_payment.amount if recent_payment else 0
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"구독 취소 중 오류: {str(e)}"
        )
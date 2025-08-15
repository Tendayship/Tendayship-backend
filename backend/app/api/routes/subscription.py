from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from ...database.session import get_db
from ...api.dependencies import get_current_user
from ...models.user import User
from ...crud.subscription_crud import subscription_crud, payment_crud
from ...crud.member_crud import family_member_crud
from ...services.payment_service import payment_service
from ...schemas.subscription import (
    SubscriptionCreate, 
    SubscriptionResponse, 
    PaymentRequest,
    PaymentResponse
)

router = APIRouter(prefix="/subscription", tags=["subscription"])

@router.post("/", response_model=SubscriptionResponse)
async def create_subscription(
    subscription_data: SubscriptionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    구독 생성 (그룹 리더만 가능)
    카카오페이/PG사 결제 연동 포함
    """
    
    # 1. 그룹 리더 권한 확인
    membership = await family_member_crud.get_by_user_and_group(
        db, current_user.id, subscription_data.group_id
    )
    if not membership or membership.role != "leader":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="그룹 리더만 구독을 생성할 수 있습니다"
        )
    
    # 2. 기존 활성 구독 확인
    existing_subscription = await subscription_crud.get_by_group_id(
        db, subscription_data.group_id
    )
    if existing_subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 활성 구독이 존재합니다"
        )
    
    try:
        # 3. 결제 생성 (카카오페이/PG사)
        payment_result = await payment_service.create_subscription_payment(
            user_id=current_user.id,
            group_id=subscription_data.group_id,
            payment_method=subscription_data.payment_method
        )
        
        return {
            "payment_info": payment_result,
            "redirect_url": payment_result.get("next_redirect_pc_url"),
            "mobile_url": payment_result.get("next_redirect_mobile_url")
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"구독 생성 중 오류: {str(e)}"
        )

@router.post("/approve")
async def approve_payment(
    tid: str,
    pg_token: str,
    partner_order_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """카카오페이 결제 승인"""
    
    try:
        # 1. 결제 승인 처리
        approval_result = await payment_service.approve_subscription_payment(
            tid=tid,
            pg_token=pg_token,
            partner_order_id=partner_order_id
        )
        
        # 2. 구독 생성
        group_id = partner_order_id.split("_")[1]  # partner_order_id에서 추출
        subscription = await subscription_crud.create_subscription(
            db=db,
            group_id=group_id,
            user_id=current_user.id,
            billing_key=approval_result.get("sid"),  # 정기결제용 SID
            amount=Decimal("6900")
        )
        
        # 3. 첫 결제 기록 생성
        await payment_crud.create_payment(
            db=db,
            subscription_id=subscription.id,
            transaction_id=approval_result.get("aid"),
            amount=subscription.amount,
            payment_method="kakao_pay",
            status="success"
        )
        
        return {
            "message": "구독이 성공적으로 생성되었습니다",
            "subscription_id": subscription.id,
            "next_billing_date": subscription.next_billing_date
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"결제 승인 중 오류: {str(e)}"
        )

@router.get("/my", response_model=List[SubscriptionResponse])
async def get_my_subscriptions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """내 구독 목록 조회"""
    
    subscriptions = await subscription_crud.get_by_user_id(
        db, current_user.id
    )
    
    return subscriptions

@router.get("/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription_detail(
    subscription_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """구독 상세 정보 조회"""
    
    subscription = await subscription_crud.get(db, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="구독을 찾을 수 없습니다"
        )
    
    # 권한 확인 - 구독자 본인 또는 그룹 멤버
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

@router.delete("/{subscription_id}")
async def cancel_subscription(
    subscription_id: str,
    reason: Optional[str] = "사용자 요청",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """구독 취소"""
    
    subscription = await subscription_crud.get(db, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="구독을 찾을 수 없습니다"
        )
    
    # 권한 확인 - 구독자 본인만 가능
    if subscription.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 구독만 취소할 수 있습니다"
        )
    
    try:
        # 1. PG사 정기결제 해지
        if subscription.billing_key:
            await payment_service.cancel_subscription(
                sid=subscription.billing_key,
                reason=reason
            )
        
        # 2. 구독 상태 변경
        cancelled_subscription = await subscription_crud.cancel_subscription(
            db, subscription_id, reason
        )
        
        return {
            "message": "구독이 성공적으로 취소되었습니다",
            "cancelled_at": cancelled_subscription.end_date
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"구독 취소 중 오류: {str(e)}"
        )

@router.get("/{subscription_id}/payments", response_model=List[PaymentResponse])
async def get_payment_history(
    subscription_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """결제 내역 조회"""
    
    # 구독 권한 확인
    subscription = await subscription_crud.get(db, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="구독을 찾을 수 없습니다"
        )
    
    if subscription.user_id != current_user.id:
        membership = await family_member_crud.get_by_user_and_group(
            db, current_user.id, subscription.group_id
        )
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="결제 내역에 접근할 권한이 없습니다"
            )
    
    # 결제 내역 조회
    payments = await payment_crud.get_by_subscription(
        db, subscription_id, limit
    )
    
    return payments

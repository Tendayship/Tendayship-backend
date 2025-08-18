from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, and_, desc, or_
from sqlalchemy.orm import selectinload, joinedload
from datetime import date, datetime, timedelta
from decimal import Decimal

from .base import BaseCRUD
from ..models.subscription import Subscription, Payment, SubscriptionStatus, PaymentStatus
from ..schemas.subscription import SubscriptionCreate

class SubscriptionCRUD(BaseCRUD[Subscription, SubscriptionCreate, dict]):
    
    async def get_by_group_id(
        self,
        db: AsyncSession,
        group_id: str
    ) -> Optional[Subscription]:
        """그룹의 활성 구독 조회"""
        result = await db.execute(
            select(Subscription)
            .where(
                and_(
                    Subscription.group_id == group_id,
                    Subscription.status == SubscriptionStatus.ACTIVE
                )
            )
            .options(
                selectinload(Subscription.payments),
                joinedload(Subscription.payer),
                joinedload(Subscription.group)
            )
        )
        return result.scalars().first()
    
    async def get_by_user_id(
        self,
        db: AsyncSession,
        user_id: str
    ) -> List[Subscription]:
        """사용자의 모든 구독 조회"""
        result = await db.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .options(
                selectinload(Subscription.payments),
                joinedload(Subscription.group)
            )
            .order_by(desc(Subscription.created_at))
        )
        return result.scalars().all()
    
    async def get_expiring_subscriptions(
        self,
        db: AsyncSession,
        days_ahead: int = 3
    ) -> List[Subscription]:
        """곧 만료될 구독 조회 (자동 결제용)"""
        target_date = date.today() + timedelta(days=days_ahead)
        
        result = await db.execute(
            select(Subscription)
            .where(
                and_(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.next_billing_date <= target_date
                )
            )
            .options(
                joinedload(Subscription.user),
                joinedload(Subscription.group).joinedload(Subscription.group.recipient)
            )
        )
        return result.scalars().all()
    
    async def get_failed_payments(
        self,
        db: AsyncSession,
        retry_limit: int = 3
    ) -> List[Subscription]:
        """결제 실패한 구독 조회 (재시도용)"""
        result = await db.execute(
            select(Subscription)
            .join(Payment)
            .where(
                and_(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Payment.status == PaymentStatus.FAILED,
                    Payment.created_at >= datetime.now() - timedelta(days=7)  # 최근 7일 내
                )
            )
            .group_by(Subscription.id)
            .having(func.count(Payment.id) < retry_limit)
            .options(
                selectinload(Subscription.payments),
                joinedload(Subscription.payer)
            )
        )
        return result.scalars().all()
    
    async def create_subscription(
        self,
        db: AsyncSession,
        group_id: str,
        user_id: str,
        billing_key: str,
        amount: Decimal = Decimal("6900")
    ) -> Subscription:
        """새 구독 생성"""
        # 기존 활성 구독 확인
        existing = await self.get_by_group_id(db, group_id)
        if existing:
            raise ValueError("이미 활성 구독이 존재합니다")
        
        # 다음 결제일 계산 (30일 후)
        next_billing_date = date.today() + timedelta(days=30)
        
        subscription = Subscription(
            group_id=group_id,
            user_id=user_id,
            status=SubscriptionStatus.ACTIVE,
            start_date=date.today(),
            next_billing_date=next_billing_date,
            amount=amount,
            billing_key=billing_key
        )
        
        db.add(subscription)
        # Transaction management moved to upper layer
        return subscription
    
    async def cancel_subscription(
        self,
        db: AsyncSession,
        subscription_id: str,
        reason: str = "사용자 요청"
    ) -> Subscription:
        """구독 취소"""
        subscription = await self.get(db, subscription_id)
        if not subscription:
            raise ValueError("구독을 찾을 수 없습니다")
        
        subscription.status = SubscriptionStatus.CANCELLED
        subscription.end_date = date.today()
        subscription.cancel_reason = reason
        
        # Transaction management moved to upper layer
        return subscription

class PaymentCRUD(BaseCRUD[Payment, dict, dict]):
    
    async def create_payment(
        self,
        db: AsyncSession,
        subscription_id: str,
        transaction_id: str,
        amount: Decimal,
        payment_method: str,
        status: PaymentStatus = PaymentStatus.PENDING
    ) -> Payment:
        """결제 기록 생성"""
        payment = Payment(
            subscription_id=subscription_id,
            transaction_id=transaction_id,
            amount=amount,
            payment_method=payment_method,
            status=status
        )
        
        if status == PaymentStatus.SUCCESS:
            payment.paid_at = datetime.now()
        
        db.add(payment)
        # Transaction management moved to upper layer
        # Note: Subscription update should be handled in service layer
        return payment
    
    async def get_by_subscription(
        self,
        db: AsyncSession,
        subscription_id: str,
        limit: int = 10
    ) -> List[Payment]:
        """구독의 결제 내역 조회"""
        result = await db.execute(
            select(Payment)
            .where(Payment.subscription_id == subscription_id)
            .order_by(desc(Payment.created_at))
            .limit(limit)
        )
        return result.scalars().all()

# 싱글톤 인스턴스  
subscription_crud = SubscriptionCRUD(Subscription)
payment_crud = PaymentCRUD(Payment)

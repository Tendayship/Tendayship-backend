from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, and_, desc, update
from sqlalchemy.orm import selectinload, joinedload
from datetime import date, datetime, timedelta
from decimal import Decimal
from .base import BaseCRUD
from ..models.subscription import Subscription, Payment, SubscriptionStatus, PaymentStatus
from ..schemas.subscription import SubscriptionCreate

class SubscriptionCRUD(BaseCRUD[Subscription, SubscriptionCreate, dict]):
    
    async def get_by_group_id_simple(self, db: AsyncSession, group_id: str) -> Optional[Subscription]:
        result = await db.execute(
            select(Subscription).where(
                and_(Subscription.group_id == group_id, Subscription.status == SubscriptionStatus.ACTIVE)
            )
        )
        return result.scalars().first()

    async def get_by_group_id(self, db: AsyncSession, group_id: str) -> Optional[Subscription]:
        result = await db.execute(
            select(Subscription).where(
                and_(Subscription.group_id == group_id, Subscription.status == SubscriptionStatus.ACTIVE)
            ).options(
                selectinload(Subscription.payments),
                joinedload(Subscription.payer),
                joinedload(Subscription.group)
            )
        )
        return result.scalars().first()

    async def get_any_by_group_id(self, db: AsyncSession, group_id: str) -> Optional[Subscription]:
        result = await db.execute(
            select(Subscription).where(Subscription.group_id == group_id).order_by(desc(Subscription.created_at))
        )
        return result.scalars().first()

    async def get_by_user_id(self, db: AsyncSession, user_id: str) -> List[Subscription]:
        result = await db.execute(
            select(Subscription).where(Subscription.user_id == user_id).options(
                selectinload(Subscription.payments),
                joinedload(Subscription.group)
            ).order_by(desc(Subscription.created_at))
        )
        return result.scalars().all()

    async def upsert_activate_subscription(self, db: AsyncSession, group_id: str, user_id: str, amount: Decimal = Decimal("6900"), pg_customer_key: Optional[str] = None) -> Subscription:
        existing = await self.get_any_by_group_id(db, group_id)
        if existing:
            existing.user_id = user_id
            existing.status = SubscriptionStatus.ACTIVE
            existing.start_date = date.today()
            existing.end_date = None
            existing.next_billing_date = date.today() + timedelta(days=30)
            existing.amount = amount
            existing.payment_method = "kakao_pay_subscription" if pg_customer_key else "kakao_pay"
            if pg_customer_key:
                existing.pg_customer_key = pg_customer_key
            existing.cancel_reason = None
            return existing
        else:
            next_billing_date = date.today() + timedelta(days=30)
            subscription = Subscription(
                group_id=group_id,
                user_id=user_id,
                status=SubscriptionStatus.ACTIVE,
                start_date=date.today(),
                next_billing_date=next_billing_date,
                amount=amount,
                payment_method="kakao_pay_subscription" if pg_customer_key else "kakao_pay",
                pg_customer_key=pg_customer_key
            )
            db.add(subscription)
            return subscription

    async def cancel_subscription(self, db: AsyncSession, subscription_id: str, reason: str = "사용자 요청") -> Subscription:
        subscription = await self.get(db, subscription_id)
        if not subscription:
            raise ValueError("구독을 찾을 수 없습니다")
        subscription.status = SubscriptionStatus.CANCELLED
        subscription.end_date = date.today()
        subscription.cancel_reason = reason
        subscription.pg_customer_key = None # 정기결제 키 해제
        return subscription
        
    async def expire_subscription(self, db: AsyncSession, subscription_id: str, reason: str) -> None:
        stmt = update(Subscription).where(Subscription.id == subscription_id).values(
            status=SubscriptionStatus.EXPIRED,
            end_date=date.today(),
            cancel_reason=reason
        )
        await db.execute(stmt)

    async def get_due_subscriptions(self, db: AsyncSession) -> List[Subscription]:
        """ 결제일이 오늘이거나 지난 구독 목록을 가져옵니다. """
        result = await db.execute(
            select(Subscription).where(
                and_(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.next_billing_date <= date.today(),
                    Subscription.pg_customer_key.isnot(None)
                )
            )
        )
        return result.scalars().all()
        
    async def update_next_billing_date(self, db: AsyncSession, subscription_id: str) -> None:
        """ 다음 결제일을 한 달 뒤로 업데이트합니다. """
        next_date = date.today() + timedelta(days=30)
        stmt = update(Subscription).where(Subscription.id == subscription_id).values(
            next_billing_date=next_date
        )
        await db.execute(stmt)

class PaymentCRUD(BaseCRUD[Payment, dict, dict]):
    
    async def create_payment(self, db: AsyncSession, subscription_id: str, transaction_id: str, amount: Decimal, payment_method: str, status: PaymentStatus = PaymentStatus.PENDING, pg_tid: str = None, pg_response: dict = None) -> Payment:
        payment = Payment(
            subscription_id=subscription_id,
            transaction_id=transaction_id,
            pg_tid=pg_tid,
            amount=amount,
            payment_method=payment_method,
            status=status,
            pg_response=pg_response
        )
        if status == PaymentStatus.SUCCESS:
            payment.paid_at = datetime.now()
        db.add(payment)
        await db.flush() # ID를 즉시 얻기 위해 flush
        return payment

    async def get_by_subscription(self, db: AsyncSession, subscription_id: str, limit: int = 10) -> List[Payment]:
        result = await db.execute(
            select(Payment).where(Payment.subscription_id == subscription_id).order_by(desc(Payment.created_at)).limit(limit)
        )
        return result.scalars().all()

    async def get_recent_payment(self, db: AsyncSession, subscription_id: str) -> Optional[Payment]:
        result = await db.execute(
            select(Payment).where(Payment.subscription_id == subscription_id).order_by(desc(Payment.created_at)).limit(1)
        )
        return result.scalars().first()

    async def mark_refunded(self, db: AsyncSession, payment_id: str) -> Payment:
        payment = await self.get(db, payment_id)
        if not payment:
            raise ValueError("결제 레코드를 찾을 수 없습니다")
        payment.status = PaymentStatus.REFUNDED
        return payment

subscription_crud = SubscriptionCRUD(Subscription)
payment_crud = PaymentCRUD(Payment)
from sqlalchemy import Column, String, ForeignKey, Enum, Numeric, Date, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import enum

from .base import Base, TimestampMixin, UUIDMixin
from .user import User


class SubscriptionStatus(enum.Enum):
    """구독 상태"""
    ACTIVE = "active"      # 활성
    CANCELLED = "cancelled"  # 취소됨
    EXPIRED = "expired"    # 만료됨
    PENDING = "pending"    # 대기 중


class PaymentStatus(enum.Enum):
    """결제 상태"""
    SUCCESS = "success"  # 성공
    FAILED = "failed"    # 실패
    PENDING = "pending"  # 대기 중
    REFUNDED = "refunded"  # 환불됨


class Subscription(Base, UUIDMixin, TimestampMixin):
    """구독 모델"""
    __tablename__ = "subscriptions"
    __table_args__ = {"comment": "구독 정보"}
    
    # 관계 정보
    group_id = Column(UUID(as_uuid=True), ForeignKey("family_groups.id"), nullable=False, unique=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, comment="결제자 ID")
    
    # 구독 정보
    status = Column(
        Enum(SubscriptionStatus),
        nullable=False,
        default=SubscriptionStatus.PENDING,
        comment="구독 상태"
    )
    start_date = Column(Date, nullable=False, comment="시작일")
    end_date = Column(Date, nullable=True, comment="종료일")
    next_billing_date = Column(Date, nullable=True, comment="다음 결제일")
    
    # 금액
    amount = Column(Numeric(10, 0), nullable=False, comment="구독료 (원)")
    
    # 결제 정보
    payment_method = Column(String(50), nullable=True, comment="결제 수단")
    pg_customer_key = Column(String(200), nullable=True, comment="PG사 고객 키")
    
    # 관계
    group = relationship("FamilyGroup", back_populates="subscription")
    payer = relationship("User", back_populates="subscriptions")
    payments = relationship("Payment", back_populates="subscription", cascade="all, delete-orphan")


class Payment(Base, UUIDMixin, TimestampMixin):
    """결제 모델"""
    __tablename__ = "payments"
    __table_args__ = {"comment": "결제 내역"}
    
    # 관계 정보
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False)
    
    # 결제 정보
    transaction_id = Column(String(200), unique=True, nullable=False, comment="PG 거래 ID")
    amount = Column(Numeric(10, 0), nullable=False, comment="결제 금액 (원)")
    
    # 상태
    status = Column(
        Enum(PaymentStatus),
        nullable=False,
        default=PaymentStatus.PENDING,
        comment="결제 상태"
    )
    
    # 결제 상세
    payment_method = Column(String(50), nullable=False, comment="결제 수단")
    pg_response = Column(JSONB, nullable=True, comment="PG사 응답 (JSON)")
    
    # 타임스탬프
    paid_at = Column(DateTime(timezone=True), nullable=True, comment="결제일시")
    failed_reason = Column(Text, nullable=True, comment="실패 사유")
    
    # 관계
    subscription = relationship("Subscription", back_populates="payments")
from sqlalchemy import Column, String, ForeignKey, Enum, Numeric, Date, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import enum
from sqlalchemy.types import TypeDecorator, CHAR
import uuid
from .base import Base, TimestampMixin, UUIDMixin

class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(value))
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            return value

class SubscriptionStatus(enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PENDING = "pending"

class PaymentStatus(enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    REFUNDED = "refunded"

class Subscription(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "subscriptions"
    __table_args__ = {"comment": "구독 정보"}

    group_id = Column(UUID(as_uuid=True), ForeignKey("family_groups.id"), nullable=False, unique=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, comment="결제자 ID")
    status = Column(Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.PENDING, comment="구독 상태")
    start_date = Column(Date, nullable=False, comment="시작일")
    end_date = Column(Date, nullable=True, comment="종료일")
    next_billing_date = Column(Date, nullable=True, comment="다음 결제일")
    cancel_reason = Column(Text, nullable=True, comment="취소 사유")
    amount = Column(Numeric(10, 0), nullable=False, comment="구독료 (원)")
    payment_method = Column(String(50), nullable=True, comment="결제 수단")
    pg_customer_key = Column(String(200), nullable=True, comment="PG사 고객 키")
    history = relationship("SubscriptionHistory", back_populates="subscription", cascade="all, delete-orphan")
    group = relationship("FamilyGroup", back_populates="subscription")
    payer = relationship("User", back_populates="subscriptions")
    payments = relationship("Payment", back_populates="subscription", cascade="all, delete-orphan")


class SubscriptionHistory(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "subscription_history"
    
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False)
    action = Column(String(20), nullable=False)  # CREATED, CANCELLED, REACTIVATED
    status = Column(String(20), nullable=False)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True) 
    cancel_reason = Column(Text, nullable=True)
    amount = Column(Numeric(10, 0), nullable=True)
    
    subscription = relationship("Subscription", back_populates="history")

# Subscription 모델에 추가
history = relationship("SubscriptionHistory", back_populates="subscription", cascade="all, delete-orphan")

class Payment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = {"comment": "결제 내역"}

    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False)
    transaction_id = Column(String(200), unique=True, nullable=False, comment="PG 거래 ID (AID)")
    pg_tid = Column(String(200), nullable=True, comment="PG 결제 TID (환불용)")
    amount = Column(Numeric(10, 0), nullable=False, comment="결제 금액 (원)")
    status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING, comment="결제 상태")
    payment_method = Column(String(50), nullable=False, comment="결제 수단")
    pg_response = Column(JSONB, nullable=True, comment="PG사 응답 (JSON)")
    paid_at = Column(DateTime(timezone=True), nullable=True, comment="결제일시")
    failed_reason = Column(Text, nullable=True, comment="실패 사유")

    subscription = relationship("Subscription", back_populates="payments")

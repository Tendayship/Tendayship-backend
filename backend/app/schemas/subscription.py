from typing import Optional
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, field_serializer
from enum import Enum


class SubscriptionStatusEnum(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    SUSPENDED = "suspended"

class PaymentStatusEnum(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    REFUNDED = "refunded"

class PaymentMethodEnum(str, Enum):
    CARD = "card"
    KAKAO_PAY = "kakao_pay"
    BANK_TRANSFER = "bank_transfer"

# 구독 생성 요청
class SubscriptionCreate(BaseModel):
    group_id: str = Field(..., description="가족 그룹 ID")
    payment_method: PaymentMethodEnum = Field(..., description="결제 수단")
    billing_key: Optional[str] = Field(None, description="자동 결제용 빌링키")

# 구독 응답
class SubscriptionResponse(BaseModel):
    id: str
    group_id: str
    user_id: str
    status: SubscriptionStatusEnum
    start_date: date
    end_date: Optional[date] = None
    next_billing_date: date
    amount: Decimal
    created_at: datetime
    updated_at: datetime
    
    @field_serializer('id', 'group_id', 'user_id')
    def serialize_uuid_fields(self, value: UUID) -> str:
        return str(value)
    
    class Config:
        from_attributes = True

# 결제 요청
class PaymentRequest(BaseModel):
    subscription_id: str = Field(..., description="구독 ID")
    amount: Decimal = Field(..., description="결제 금액")
    payment_method: PaymentMethodEnum = Field(..., description="결제 수단")

class PaymentReadyResponse(BaseModel):
    """결제 준비 응답"""
    tid: str = Field(..., description="결제 고유번호")
    next_redirect_pc_url: str = Field(..., description="PC 결제 페이지 URL")
    next_redirect_mobile_url: str = Field(..., description="모바일 결제 페이지 URL")
    partner_order_id: str = Field(..., description="가맹점 주문번호")

class PaymentApproveRequest(BaseModel):
    """결제 승인 요청"""
    tid: str = Field(..., description="결제 고유번호")
    pg_token: str = Field(..., description="결제 승인 토큰")

class PaymentCancelRequest(BaseModel):
    """결제 취소 요청"""
    tid: str = Field(..., description="결제 고유번호")
    cancel_amount: int = Field(..., description="취소 금액")
    cancel_reason: str = Field(default="사용자 요청", description="취소 사유")


# 결제 응답
class PaymentResponse(BaseModel):
    id: str
    subscription_id: str
    transaction_id: str
    amount: Decimal
    status: PaymentStatusEnum
    payment_method: PaymentMethodEnum
    paid_at: Optional[datetime] = None
    
    @field_serializer('id', 'subscription_id')
    def serialize_uuid_fields(self, value: UUID) -> str:
        return str(value)
    
    class Config:
        from_attributes = True

from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field
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
    
    class Config:
        from_attributes = True

# 결제 요청
class PaymentRequest(BaseModel):
    subscription_id: str = Field(..., description="구독 ID")
    amount: Decimal = Field(..., description="결제 금액")
    payment_method: PaymentMethodEnum = Field(..., description="결제 수단")
    
# 결제 응답
class PaymentResponse(BaseModel):
    id: str
    subscription_id: str
    transaction_id: str
    amount: Decimal
    status: PaymentStatusEnum
    payment_method: PaymentMethodEnum
    paid_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

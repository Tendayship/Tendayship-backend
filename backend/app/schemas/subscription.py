from typing import Optional, Any, List
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, field_serializer, ConfigDict, validator
from enum import Enum

# --- Enums (열거형) ---
# 데이터베이스 모델과 값을 일치시킵니다.
class SubscriptionStatusEnum(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PENDING = "pending"

class PaymentStatusEnum(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    REFUNDED = "refunded"

class PaymentMethodEnum(str, Enum):
    CARD = "card"
    KAKAO_PAY = "kakao_pay"
    BANK_TRANSFER = "bank_transfer"

# --- 구독 관련 스키마 ---
class SubscriptionCreate(BaseModel):
    """구독 생성 요청 (현재 프로젝트에서는 사용되지 않음)"""
    group_id: str = Field(..., description="가족 그룹 ID")
    payment_method: PaymentMethodEnum = Field(..., description="결제 수단")
    billing_key: Optional[str] = Field(None, description="자동 결제용 빌링키")

class SubscriptionResponse(BaseModel):
    """구독 정보 응답"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    group_id: UUID
    user_id: UUID
    status: SubscriptionStatusEnum
    start_date: date
    end_date: Optional[date] = None
    next_billing_date: Optional[date] = None # DB 모델에 맞춰 Optional로 변경
    amount: Decimal
    created_at: datetime
    updated_at: datetime

    @field_serializer('id', 'group_id', 'user_id')
    def serialize_uuid_to_str(self, value: UUID) -> str:
        """UUID 객체를 문자열로 변환"""
        return str(value)

    @validator('status', pre=True)
    def validate_status_enum(cls, v):
        """DB에서 온 값이 문자열일 경우 Enum으로 변환"""
        if hasattr(v, 'value'): # SQLAlchemy Enum 객체 처리
            return SubscriptionStatusEnum(v.value)
        if isinstance(v, str):
            return SubscriptionStatusEnum(v.lower())
        return v

class SubscriptionHistoryResponse(BaseModel):
    """구독 이력 응답"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subscription_id: UUID
    action: str
    status: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    cancel_reason: Optional[str] = None
    amount: Optional[Decimal] = None
    created_at: datetime

    @field_serializer('id', 'subscription_id')
    def serialize_uuid_to_str(self, value: UUID) -> str:
        return str(value)

# --- 결제 관련 스키마 ---
class PaymentReadyResponse(BaseModel):
    """결제 준비 응답"""
    tid: str = Field(..., description="결제 고유번호")
    next_redirect_pc_url: str = Field(..., description="PC 결제 페이지 URL")
    next_redirect_mobile_url: str = Field(..., description="모바일 결제 페이지 URL")
    partner_order_id: str = Field(..., description="가맹점 주문번호")

class PaymentApproveRequest(BaseModel):
    """결제 승인 요청 (API 라우트에서 직접 처리)"""
    tid: str = Field(..., description="결제 고유번호")
    pg_token: str = Field(..., description="결제 승인 토큰")

class PaymentCancelRequest(BaseModel):
    """결제 취소 요청 (서비스 레이어에서 사용)"""
    tid: str = Field(..., description="결제 고유번호")
    cancel_amount: int = Field(..., description="취소 금액")
    cancel_reason: str = Field(default="사용자 요청", description="취소 사유")

class PaymentResponse(BaseModel):
    """결제 정보 응답"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subscription_id: UUID
    transaction_id: str
    amount: Decimal
    status: PaymentStatusEnum
    payment_method: str # DB 모델의 String 타입과 일치
    paid_at: Optional[datetime] = None

    @field_serializer('id', 'subscription_id')
    def serialize_uuid_to_str(self, value: UUID) -> str:
        return str(value)
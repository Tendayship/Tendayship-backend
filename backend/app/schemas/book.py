from typing import Optional, List, Union
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_serializer, field_validator
from enum import Enum

class ProductionStatusEnum(str, Enum):
    PENDING = "pending"        # 제작 대기
    IN_PROGRESS = "in_progress"  # 제작 중
    COMPLETED = "completed"    # 제작 완료

class DeliveryStatusEnum(str, Enum):
    PENDING = "pending"        # 배송 대기
    SHIPPING = "shipping"      # 배송 중
    DELIVERED = "delivered"    # 배송 완료

# 책자 생성 요청 (관리자용)
class BookCreate(BaseModel):
    issue_id: str = Field(..., description="회차 ID")
    template_type: str = Field(default="standard", description="템플릿 타입")

# 책자 상태 업데이트 (관리자용)
class BookStatusUpdate(BaseModel):
    production_status: Optional[ProductionStatusEnum] = None
    delivery_status: Optional[DeliveryStatusEnum] = None
    tracking_number: Optional[str] = Field(None, description="운송장 번호")
    notes: Optional[str] = Field(None, description="배송 메모")

# 책자 응답
class BookResponse(BaseModel):
    id: Union[str, UUID]
    issue_id: Union[str, UUID]
    pdf_url: Optional[str] = None
    production_status: ProductionStatusEnum
    delivery_status: DeliveryStatusEnum
    tracking_number: Optional[str] = None
    produced_at: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    # 회차 정보 포함
    issue_number: Optional[int] = None
    issue_deadline: Optional[datetime] = None
    post_count: Optional[int] = None
    
    @field_validator('id', 'issue_id', mode='before')
    @classmethod
    def validate_uuid_fields(cls, value):
        """UUID나 문자열을 문자열로 변환"""
        if isinstance(value, UUID):
            return str(value)
        return value
    
    @field_serializer('id', 'issue_id')
    def serialize_uuid_fields(self, value) -> str:
        return str(value)
    
    class Config:
        from_attributes = True

# PDF 생성 요청 (내부용)
class PDFGenerationRequest(BaseModel):
    issue_id: str
    group_id: str
    recipient_name: str
    issue_number: int
    posts: List[dict]  # 소식 데이터
    template_settings: dict = Field(default_factory=dict)

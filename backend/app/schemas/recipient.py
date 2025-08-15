from typing import Optional
from datetime import date, datetime
from pydantic import BaseModel, Field, validator

class RecipientBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="받는 분 이름")
    birth_date: Optional[date] = Field(None, description="생년월일")
    phone: Optional[str] = Field(None, description="전화번호")
    address: str = Field(..., min_length=1, max_length=500, description="주소")
    address_detail: Optional[str] = Field(None, max_length=200, description="상세주소")
    postal_code: str = Field(..., description="우편번호")

    @validator('phone')
    def validate_phone(cls, v):
        if v and not v.replace('-', '').replace(' ', '').isdigit():
            raise ValueError('올바른 전화번호 형식이 아닙니다')
        return v

    @validator('postal_code')
    def validate_postal_code(cls, v):
        if not v.isdigit() or len(v) != 5:
            raise ValueError('우편번호는 5자리 숫자여야 합니다')
        return v

class RecipientCreate(RecipientBase):
    profile_image_url: Optional[str] = Field(None, description="프로필 이미지 URL")

class RecipientUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    birth_date: Optional[date] = None
    phone: Optional[str] = None
    address: Optional[str] = Field(None, min_length=1, max_length=500)
    address_detail: Optional[str] = Field(None, max_length=200)
    postal_code: Optional[str] = None
    profile_image_url: Optional[str] = None

class RecipientResponse(RecipientBase):
    id: str
    group_id: str
    profile_image_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

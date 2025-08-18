from typing import Optional
from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, field_serializer

class RecipientBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="받는 분 이름")
    birth_date: Optional[date] = Field(None, description="생년월일")
    phone: Optional[str] = Field(None, description="전화번호")
    address: str = Field(..., min_length=1, max_length=500, description="주소")
    address_detail: Optional[str] = Field(None, max_length=200, description="상세주소")
    postal_code: str = Field(..., description="우편번호")
    

    road_address: Optional[str] = Field(None, max_length=500, description="도로명주소")
    jibun_address: Optional[str] = Field(None, max_length=500, description="지번주소")
    address_type: Optional[str] = Field(None, description="주소 타입 (ROAD/JIBUN)")
    latitude: Optional[float] = Field(None, description="위도")
    longitude: Optional[float] = Field(None, description="경도")
    region_1depth: Optional[str] = Field(None, max_length=50, description="시/도")
    region_2depth: Optional[str] = Field(None, max_length=50, description="구/군")
    region_3depth: Optional[str] = Field(None, max_length=50, description="동/면")

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        if v and not v.replace('-', '').replace(' ', '').isdigit():
            raise ValueError('올바른 전화번호 형식이 아닙니다')
        return v

    @field_validator('postal_code')
    @classmethod
    def validate_postal_code(cls, v):
        if not v.isdigit() or len(v) != 5:
            raise ValueError('우편번호는 5자리 숫자여야 합니다')
        return v

class RecipientCreate(RecipientBase):
    profile_image_url: Optional[str] = Field(None, description="프로필 이미지 URL")
    group_id: Optional[str] = Field(None, description="가족 그룹 ID")

class RecipientUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    birth_date: Optional[date] = None
    phone: Optional[str] = None
    address: Optional[str] = Field(None, min_length=1, max_length=500)
    address_detail: Optional[str] = Field(None, max_length=200)
    postal_code: Optional[str] = None
    profile_image_url: Optional[str] = None
    road_address: Optional[str] = None
    jibun_address: Optional[str] = None
    address_type: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    region_1depth: Optional[str] = None
    region_2depth: Optional[str] = None
    region_3depth: Optional[str] = None

class RecipientResponse(RecipientBase):
    id: str
    group_id: str
    profile_image_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_serializer('id', 'group_id')
    def serialize_uuid_fields(self, value: UUID) -> str:
        return str(value)

    class Config:
        from_attributes = True

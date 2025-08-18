from typing import Optional, Union
from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, field_serializer, field_validator, Field


class UserBase(BaseModel):
    email: EmailStr
    name: str
    phone: Optional[str] = None
    birth_date: Optional[date] = None


class UserCreate(UserBase):
    kakao_id: Optional[str] = None
    profile_image_url: Optional[str] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    birth_date: Optional[date] = None
    profile_image_url: Optional[str] = None


class UserProfileUpdate(BaseModel):
    """사용자 프로필 업데이트 전용 스키마"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="사용자 이름")
    phone: Optional[str] = Field(None, pattern=r"^01[0-9]-\d{3,4}-\d{4}$", description="전화번호 (010-1234-5678 형식)")
    birth_date: Optional[date] = Field(None, description="생년월일")
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        """전화번호 형식 검증"""
        if v and not v.startswith('01'):
            raise ValueError('전화번호는 01로 시작해야 합니다')
        return v


class UserResponse(UserBase):
    id: Union[str, UUID]
    profile_image_url: Optional[str] = None
    kakao_id: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    
    @field_validator('id', mode='before')
    @classmethod
    def validate_id(cls, value):
        """UUID나 문자열을 문자열로 변환"""
        if isinstance(value, UUID):
            return str(value)
        return value
    
    @field_serializer('id')
    def serialize_id(self, value) -> str:
        """UUID를 문자열로 직렬화"""
        return str(value)
    
    class Config:
        from_attributes = True


class SocialLogin(BaseModel):
    code: str


class KakaoLoginResponse(BaseModel):
    user: UserResponse
    is_new_user: bool
    access_token: str


class UserProfileResponse(BaseModel):
    """사용자 프로필 조회 응답"""
    id: str
    email: str
    name: str
    phone: Optional[str] = None
    birth_date: Optional[date] = None
    profile_image_url: Optional[str] = None
    kakao_id: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class FamilyGroupSetup(BaseModel):
    """가족 그룹 초기 설정"""
    group_name: str = Field(..., min_length=1, max_length=100, description="가족 그룹명")
    deadline_type: str = Field(..., description="마감일 타입 (SECOND_SUNDAY, FOURTH_SUNDAY)")
    leader_relationship: str = Field(..., description="리더와 받는 분의 관계")
    recipient_name: str = Field(..., min_length=1, max_length=100, description="받는 분 이름")
    recipient_address: str = Field(..., min_length=3, max_length=500, description="받는 분 주소")
    recipient_address_detail: Optional[str] = Field(None, max_length=200, description="받는 분 상세주소")
    recipient_postal_code: Optional[str] = Field(None, description="우편번호")
    recipient_phone: Optional[str] = Field(None, description="받는 분 전화번호")

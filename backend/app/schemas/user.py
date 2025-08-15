from typing import Optional
from datetime import date, datetime
from pydantic import BaseModel, EmailStr


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


class UserResponse(UserBase):
    id: str
    profile_image_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SocialLogin(BaseModel):
    code: str


class KakaoLoginResponse(BaseModel):
    user: UserResponse
    is_new_user: bool
    access_token: str

from typing import List, Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, validator, field_serializer, model_validator

class PostCreate(BaseModel):
    content: str = Field(..., min_length=10, max_length=1000, description="소식 내용")
    image_urls: List[str] = Field(default=[], max_items=4, description="이미지 URL 목록")

    @validator('image_urls')
    def validate_image_urls(cls, v):
        if len(v) > 4:
            raise ValueError('최대 4개의 이미지만 업로드 가능합니다')
        return v
    
    @validator('content')
    def validate_content(cls, v):
        if not v or len(v.strip()) < 10:
            raise ValueError('소식 내용은 최소 10자 이상이어야 합니다')
        if len(v) > 1000:
            raise ValueError('소식 내용은 최대 1000자까지 가능합니다')
        return v.strip()

class PostUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=50, max_length=100)
    image_urls: Optional[List[str]] = Field(None, min_items=1, max_items=4)

class PostResponse(BaseModel):
    id: str
    issue_id: str
    author_id: str
    content: str
    image_urls: List[str]
    created_at: datetime
    updated_at: datetime
    
    author_name: Optional[str] = None
    author_relationship: Optional[str] = None
    author_profile_image: Optional[str] = None

    class Config:
        from_attributes = True

class ImageUploadResponse(BaseModel):
    image_urls: List[str]
    collage_layout: Optional[str] = None

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum

# 소식 작성 요청
class PostCreate(BaseModel):
    content: str = Field(..., min_length=50, max_length=100, description="소식 내용")
    images: List[str] = Field(..., min_items=1, max_items=4, description="이미지 URL 목록")

    @validator('images')
    def validate_images(cls, v):
        if len(v) < 1:
            raise ValueError('최소 1개의 이미지가 필요합니다')
        if len(v) > 4:
            raise ValueError('최대 4개의 이미지만 업로드 가능합니다')
        return v

# 소식 수정 요청
class PostUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=50, max_length=100)
    images: Optional[List[str]] = Field(None, min_items=1, max_items=4)

# 소식 응답
class PostResponse(BaseModel):
    id: str
    issue_id: str
    author_id: str
    content: str
    image_urls: List[str]
    created_at: datetime
    updated_at: datetime
    
    # 작성자 정보 포함 (JOIN)
    author_name: Optional[str] = None
    author_relationship: Optional[str] = None
    author_profile_image: Optional[str] = None
    
    class Config:
        from_attributes = True

# 이미지 업로드 요청
class ImageUploadRequest(BaseModel):
    post_id: Optional[str] = None
    images: List[bytes] = Field(..., description="이미지 바이너리 데이터")

# 이미지 업로드 응답
class ImageUploadResponse(BaseModel):
    image_urls: List[str]
    collage_layout: str  # "1x1", "2x1", "2x2" 등

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator, model_validator

class PostCreate(BaseModel):
    content: Optional[str] = Field(None, min_length=50, max_length=100, description="소식 내용 (선택)")
    image_urls: List[str] = Field(..., min_items=1, max_items=4, description="이미지 URL 목록 (필수)")

    @validator('content')
    def validate_content(cls, v):
        if v is None:
            return v
        v = v.strip()
        if len(v) < 50:
            raise ValueError('소식 내용은 최소 50자 이상이어야 합니다')
        if len(v) > 100:
            raise ValueError('소식 내용은 최대 100자까지 가능합니다')
        return v
    
    @validator('image_urls')
    def validate_image_urls(cls, v):
        if not v or len(v) == 0:
            raise ValueError('최소 1장의 이미지가 필요합니다')
        if len(v) > 4:
            raise ValueError('최대 4개의 이미지만 업로드 가능합니다')
        return v

class PostCreateWithImages(BaseModel):
    content: Optional[str] = Field(None, min_length=50, max_length=100, description="소식 내용 (선택)")
    image_urls: List[str] = Field(..., min_items=1, max_items=4, description="이미지 URL 목록 (필수)")
    image_blob_keys: List[str] = Field(..., min_items=1, max_items=4, description="이미지 블롭 키 목록 (필수)")

    @validator('content')
    def validate_content(cls, v):
        if v is None:
            return v
        v = v.strip()
        if len(v) < 50:
            raise ValueError('소식 내용은 최소 50자 이상이어야 합니다')
        if len(v) > 100:
            raise ValueError('소식 내용은 최대 100자까지 가능합니다')
        return v

    @validator('image_urls')
    def validate_image_urls(cls, v):
        if not v or len(v) == 0:
            raise ValueError('최소 1장의 이미지가 필요합니다')
        if len(v) > 4:
            raise ValueError('최대 4개의 이미지만 업로드 가능합니다')
        return v

    @validator('image_blob_keys')
    def validate_image_blob_keys(cls, v):
        if not v or len(v) == 0:
            raise ValueError('최소 1개의 이미지 블롭 키가 필요합니다')
        if len(v) > 4:
            raise ValueError('최대 4개의 이미지 블롭 키만 가능합니다')
        return v

    @model_validator(mode='after')
    def validate_image_consistency(cls, values):
        image_urls = values.image_urls or []
        image_blob_keys = values.image_blob_keys or []
        
        if len(image_urls) != len(image_blob_keys):
            raise ValueError('이미지 URL과 블롭 키 개수가 일치하지 않습니다')
        
        return values

class PostUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=50, max_length=100)
    image_urls: Optional[List[str]] = Field(None, min_items=1, max_items=4)

class PostResponse(BaseModel):
    id: str
    issue_id: str
    author_id: str
    content: Optional[str]  # Optional로 변경
    image_urls: List[str]
    created_at: datetime
    updated_at: datetime
    
    author_name: Optional[str] = None
    author_relationship: Optional[str] = None
    author_profile_image: Optional[str] = None  # 사용하지 않지만 호환성 유지

    class Config:
        from_attributes = True

class ImageUploadResponse(BaseModel):
    image_urls: List[str]
    blob_keys: List[str]
    collage_layout: Optional[str] = None
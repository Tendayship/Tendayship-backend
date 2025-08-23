from sqlalchemy import Column, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from .base import Base, TimestampMixin, UUIDMixin

class Post(Base, UUIDMixin, TimestampMixin):
    """소식 게시글 모델"""
    __tablename__ = "posts"
    __table_args__ = {"comment": "소식 게시글"}
    
    # 소속 정보
    issue_id = Column(UUID(as_uuid=True), ForeignKey("issues.id"), nullable=False)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 내용 (선택사항으로 변경)
    content = Column(Text, nullable=True, comment="게시글 내용 (선택, 최대 100자)")
    
    # 이미지 정보 (필수, JSON 배열로 저장)
    # 최소 1장, 최대 4장 필수
    image_urls = Column(JSONB, nullable=False, default=list, comment="이미지 URL 배열 (필수, 1-4장)")
    
    # 이미지 블롭 키 저장 (정확한 삭제를 위해)
    image_blob_keys = Column(JSONB, nullable=True, default=list, comment="Azure Blob Storage 키 배열")
    
    # 관계
    issue = relationship("Issue", back_populates="posts")
    author = relationship("User", back_populates="posts")
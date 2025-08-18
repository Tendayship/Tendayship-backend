from sqlalchemy import Column, Text, ForeignKey, Date, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from .base import Base, TimestampMixin, UUIDMixin
from .user import User
from .issue import Issue



class Post(Base, UUIDMixin, TimestampMixin):
    """소식 게시글 모델"""
    __tablename__ = "posts"
    __table_args__ = {"comment": "소식 게시글"}
    
    # 소속 정보
    issue_id = Column(UUID(as_uuid=True), ForeignKey("issues.id"), nullable=False)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 내용
    content = Column(Text, nullable=False, comment="게시글 내용 (50-100자)")
    
    # 이미지 정보 (JSON 배열로 저장)
    # 예: ["image1.jpg", "image2.jpg", "image3.jpg", "image4.jpg"]
    image_urls = Column(JSONB, nullable=True, default=list, comment="이미지 URL 배열")
    
    # 이미지 블롭 키 저장 (정확한 삭제를 위해)
    # 예: ["group/issue/post/image1.jpg", "group/issue/post/image2.jpg"]
    image_blob_keys = Column(JSONB, nullable=True, default=list, comment="Azure Blob Storage 키 배열")
    
    # 관계
    issue = relationship("Issue", back_populates="posts")
    author = relationship("User", back_populates="posts")
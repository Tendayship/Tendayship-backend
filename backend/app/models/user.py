from sqlalchemy import Column, String, Date, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import Base, TimestampMixin, UUIDMixin


class User(Base, UUIDMixin, TimestampMixin):
    """사용자 모델"""
    __tablename__ = "users"
    __table_args__ = {"comment": "사용자 정보"}
    
    # 기본 정보
    email = Column(String(255), unique=True, nullable=False, index=True, comment="이메일 (카카오 로그인)")
    name = Column(String(100), nullable=False, comment="이름")
    phone = Column(String(20), nullable=True, comment="전화번호")
    birth_date = Column(Date, nullable=True, comment="생년월일")
    
    # 프로필
    profile_image_url = Column(Text, nullable=True, comment="프로필 이미지 URL (Blob Storage)")
    
    # 카카오 연동
    kakao_id = Column(String(100), unique=True, nullable=True, index=True, comment="카카오 고유 ID")
    kakao_refresh_token = Column(Text, nullable=True, comment="카카오 리프레시 토큰")
    
    # 상태
    is_active = Column(Boolean, default=True, nullable=False, comment="활성 상태")
    is_deleted = Column(Boolean, default=False, nullable=False, comment="삭제 여부 (소프트 삭제)")
    
    # 관계
    family_members = relationship("FamilyMember", back_populates="user", cascade="all, delete-orphan")
    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="payer", cascade="all, delete-orphan")
    led_groups = relationship("FamilyGroup", back_populates="leader")
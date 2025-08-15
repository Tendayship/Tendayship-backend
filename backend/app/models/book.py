from sqlalchemy import Column, String, ForeignKey, Enum, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import enum

from .base import Base, TimestampMixin, UUIDMixin


class ProductionStatus(enum.Enum):
    """제작 상태"""
    PENDING = "pending"    # 대기 중
    IN_PROGRESS = "in_progress"  # 제작 중
    COMPLETED = "completed"  # 완료됨
    FAILED = "failed"      # 실패


class DeliveryStatus(enum.Enum):
    """배송 상태"""
    PENDING = "pending"    # 대기 중
    PREPARING = "preparing"  # 준비 중
    SHIPPING = "shipping"   # 배송 중
    DELIVERED = "delivered"  # 배송 완료
    RETURNED = "returned"   # 반송됨


class Book(Base, UUIDMixin, TimestampMixin):
    """책자 모델"""
    __tablename__ = "books"
    __table_args__ = {"comment": "책자 정보"}
    
    # 관계 정보
    issue_id = Column(UUID(as_uuid=True), ForeignKey("issues.id"), nullable=False, unique=True)
    
    # 파일 정보
    pdf_url = Column(Text, nullable=True, comment="PDF 파일 URL (Blob Storage)")
    cover_image_url = Column(Text, nullable=True, comment="표지 이미지 URL")
    
    # 제작 상태
    production_status = Column(
        Enum(ProductionStatus),
        nullable=False,
        default=ProductionStatus.PENDING,
        comment="제작 상태"
    )
    
    # 배송 상태
    delivery_status = Column(
        Enum(DeliveryStatus),
        nullable=False,
        default=DeliveryStatus.PENDING,
        comment="배송 상태"
    )
    
    # 배송 정보
    tracking_number = Column(String(100), nullable=True, comment="운송장 번호")
    delivery_company = Column(String(50), nullable=True, comment="택배사")
    
    # 타임스탬프
    produced_at = Column(DateTime(timezone=True), nullable=True, comment="제작 완료일시")
    shipped_at = Column(DateTime(timezone=True), nullable=True, comment="발송일시")
    delivered_at = Column(DateTime(timezone=True), nullable=True, comment="배송 완료일시")
    
    # 관계
    issue = relationship("Issue", back_populates="book")
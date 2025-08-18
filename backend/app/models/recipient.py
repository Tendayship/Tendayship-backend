from sqlalchemy import Column, String, ForeignKey, Date, Text, Float
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import Base, TimestampMixin, UUIDMixin

class Recipient(Base, UUIDMixin, TimestampMixin):
    """받는 분 정보 모델"""

    __tablename__ = "recipients"
    __table_args__ = {"comment": "받는 분 정보"}

    # 소속 그룹
    group_id = Column(UUID(as_uuid=True), ForeignKey("family_groups.id"), nullable=False, unique=True)

    # 개인 정보
    name = Column(String(100), nullable=False, comment="이름")
    birth_date = Column(Date, nullable=True, comment="생년월일")
    phone = Column(String(20), nullable=True, comment="전화번호")
    profile_image_url = Column(Text, nullable=True, comment="프로필 이미지 URL")

    # 주소 정보 (기존)
    address = Column(String(500), nullable=False, comment="주소")
    address_detail = Column(String(200), nullable=True, comment="상세주소")
    postal_code = Column(String(10), nullable=False, comment="우편번호")

    # 🆕 추가된 주소 관련 필드들
    road_address = Column(String(500), nullable=True, comment="도로명주소")
    jibun_address = Column(String(500), nullable=True, comment="지번주소")
    address_type = Column(String(10), nullable=True, comment="주소타입(ROAD/JIBUN)")
    
    # 좌표 정보 (배송 최적화용)
    latitude = Column(Float, nullable=True, comment="위도")
    longitude = Column(Float, nullable=True, comment="경도")
    
    # 지역 정보
    region_1depth = Column(String(50), nullable=True, comment="시/도")
    region_2depth = Column(String(50), nullable=True, comment="구/군")
    region_3depth = Column(String(50), nullable=True, comment="동/면")

    # 관계
    group = relationship("FamilyGroup", back_populates="recipient")
    family_members = relationship("FamilyMember", back_populates="recipient")

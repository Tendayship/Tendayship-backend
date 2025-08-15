from sqlalchemy import Column, String, ForeignKey, Enum, UniqueConstraint, Text, Date, DateTime, func
from sqlalchemy.orm import relationship
from sqlalchemy.types import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
import enum

from .base import Base, TimestampMixin, UUIDMixin


class DeadlineType(enum.Enum):
    """마감일 타입"""
    SECOND_SUNDAY = "SECOND_SUNDAY" 
    FOURTH_SUNDAY = "FOURTH_SUNDAY"

class GroupStatus(enum.Enum):
    """그룹 상태"""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"

class RelationshipType(enum.Enum):
    """가족 관계 타입"""
    DAUGHTER = "DAUGHTER"                   
    SON = "SON"                             
    DAUGHTER_IN_LAW = "DAUGHTER_IN_LAW"    
    SON_IN_LAW = "SON_IN_LAW"            
    GRANDCHILD = "GRANDCHILD"               
    OTHER = "OTHER"

class MemberRole(enum.Enum):
    """멤버 역할"""
    LEADER = "LEADER"                     
    MEMBER = "MEMBER"  

class FamilyGroup(Base, UUIDMixin, TimestampMixin):
    """가족 그룹 모델"""
    
    __tablename__ = "family_groups"
    __table_args__ = {"comment": "가족 그룹 정보"}

    # 기본 정보
    group_name = Column(String(100), nullable=False, comment="그룹명")
    leader_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, comment="리더 ID")

    # 초대 코드
    invite_code = Column(String(20), unique=True, nullable=False, index=True, comment="초대 코드")
    invite_code_expires_at = Column(DateTime(timezone=True), nullable=True, comment="초대 코드 만료일시")

    # 설정 
    deadline_type = Column(
    SAEnum(DeadlineType, native_enum=False, values_callable=lambda x: [e.value for e in x]),
    nullable=False,
    default=DeadlineType.SECOND_SUNDAY,
    comment="마감일 타입"
    )

    status = Column(
        SAEnum(GroupStatus, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=GroupStatus.ACTIVE,
        comment="그룹 상태"
    )

    # SQLAlchemy 관계 정의 (문자열 참조 사용)
    leader = relationship("User", back_populates="led_groups")
    members = relationship("FamilyMember", back_populates="group", cascade="all, delete-orphan")
    recipient = relationship("Recipient", back_populates="group", uselist=False, cascade="all, delete-orphan")
    issues = relationship("Issue", back_populates="group", cascade="all, delete-orphan")
    subscription = relationship("Subscription", back_populates="group", uselist=False)

class FamilyMember(Base, UUIDMixin, TimestampMixin):
    """가족 구성원 모델 (조인 테이블)"""
    
    __tablename__ = "family_members"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_user"),
        {"comment": "가족 구성원 정보"}
    )

    # Foreign Key 관계
    group_id = Column(UUID(as_uuid=True), ForeignKey("family_groups.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    recipient_id = Column(UUID(as_uuid=True), ForeignKey("recipients.id"), nullable=False)

    # 멤버 정보
    member_relationship = Column(
        Enum(RelationshipType),
        nullable=False,
        comment="받는 분과의 관계"
    )

    role = Column(
        Enum(MemberRole),
        nullable=False,
        default=MemberRole.MEMBER,
        comment="그룹 내 역할"
    )

    # 가입 정보
    joined_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="가입일시"
    )

    # SQLAlchemy 관계 정의
    group = relationship("FamilyGroup", back_populates="members")
    user = relationship("User", back_populates="family_members")
    recipient = relationship("Recipient", back_populates="family_members")
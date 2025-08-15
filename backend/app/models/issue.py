from sqlalchemy import Column, Integer, ForeignKey, Enum, Date, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import enum

from .base import Base, TimestampMixin, UUIDMixin

class IssueStatus(enum.Enum):
    """회차 상태"""
    OPEN = "open" # 진행 중
    CLOSED = "closed" # 마감됨
    PUBLISHED = "published" # 발행됨

class Issue(Base, UUIDMixin, TimestampMixin):
    """회차 모델"""

    __tablename__ = "issues"
    __table_args__ = {"comment": "회차 정보"}

    # 소속 그룹
    group_id = Column(UUID(as_uuid=True), ForeignKey("family_groups.id"), nullable=False)

    # 회차 정보
    issue_number = Column(Integer, nullable=False, comment="회차 번호")
    deadline_date = Column(Date, nullable=False, comment="마감일")

    # 상태
    status = Column(
        Enum(IssueStatus),
        nullable=False,
        default=IssueStatus.OPEN,
        comment="회차 상태"
    )

    # 타임스탬프
    closed_at = Column(DateTime(timezone=True), nullable=True, comment="마감일시")
    published_at = Column(DateTime(timezone=True), nullable=True, comment="발행일시")

    # 관계
    group = relationship("FamilyGroup", back_populates="issues")
    posts = relationship("Post", back_populates="issue", cascade="all, delete-orphan")
    book = relationship("Book", back_populates="issue", uselist=False, cascade="all, delete-orphan")
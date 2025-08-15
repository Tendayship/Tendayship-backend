from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declared_attr
import uuid

from ..database.session import Base


class TimestampMixin:
    """
    생성일시와 수정일시를 자동 관리하는 믹스인
    모든 모델에서 이 믹스인을 상속받아 타임스탬프를 자동 관리합니다.
    """
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="생성일시"
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="수정일시"
    )


class UUIDMixin:
    """
    UUID 기본 키를 제공하는 믹스인
    정수 ID 대신 UUID를 사용하여 보안성과 확장성을 향상시킵니다.
    """
    @declared_attr
    def id(cls):
        return Column(
            UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
            nullable=False,
            comment=f"{cls.__name__} 고유 ID"
        )
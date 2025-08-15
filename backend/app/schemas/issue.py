from typing import Optional, List
from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_serializer
from enum import Enum

class IssueStatusEnum(str, Enum):
    OPEN = "open"      # 진행 중
    CLOSED = "closed"  # 마감됨
    PUBLISHED = "published"  # 발행됨

class DeadlineTypeEnum(str, Enum):
    SECOND_WEEK = "second_week"  # 매월 둘째 주 일요일
    FOURTH_WEEK = "fourth_week"  # 매월 넷째 주 일요일

class IssueCreate(BaseModel):
    group_id: str = Field(..., description="가족 그룹 ID")
    issue_number: int = Field(..., description="회차 번호")
    deadline_date: date = Field(..., description="마감일")
    status: IssueStatusEnum = Field(default=IssueStatusEnum.OPEN, description="회차 상태")
    
# 현재 회차 응답
class CurrentIssueResponse(BaseModel):
    id: str
    group_id: str
    issue_number: int
    deadline_date: date
    status: IssueStatusEnum
    days_until_deadline: int
    post_count: int
    max_posts: int = 20
    created_at: datetime
    
    @field_serializer('id', 'group_id')
    def serialize_uuid_fields(self, value: UUID) -> str:
        return str(value)
    
    class Config:
        from_attributes = True

# 회차 목록 응답
class IssueListResponse(BaseModel):
    id: str
    issue_number: int
    deadline_date: date
    status: IssueStatusEnum
    post_count: int
    published_at: Optional[datetime] = None
    
    @field_serializer('id')
    def serialize_uuid_fields(self, value: UUID) -> str:
        return str(value)
    
    class Config:
        from_attributes = True

# 회차 마감 처리 (시스템 내부용)
class IssueCloseRequest(BaseModel):
    issue_id: str
    close_reason: Optional[str] = "정기 마감"

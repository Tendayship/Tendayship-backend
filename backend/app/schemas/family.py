from typing import Optional, List, Union
from datetime import datetime, date
from uuid import UUID
from pydantic import BaseModel, Field, field_serializer, field_validator
from enum import Enum
from .recipient import RecipientCreate

class DeadlineTypeEnum(str, Enum):
    SECOND_SUNDAY = "SECOND_SUNDAY"  # 매월 둘째 주 일요일
    FOURTH_SUNDAY = "FOURTH_SUNDAY"  # 매월 넷째 주 일요일

class GroupStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

class RelationshipTypeEnum(str, Enum):
    DAUGHTER = "DAUGHTER"
    SON = "SON"
    DAUGHTER_IN_LAW = "DAUGHTER_IN_LAW"
    SON_IN_LAW = "SON_IN_LAW"

class MemberRoleEnum(str, Enum):
    LEADER = "LEADER"
    MEMBER = "MEMBER"

# 가족 그룹 생성 요청 (MVP 기준)
class FamilyGroupCreate(BaseModel):
    group_name: str = Field(..., min_length=1, max_length=100, description="가족 그룹명")
    deadline_type: DeadlineTypeEnum = Field(..., description="마감일 타입")
    leader_relationship: RelationshipTypeEnum = Field(..., description="리더와 받는 분의 관계")
    recipient_info: RecipientCreate = Field(..., description="받는 분 정보")

# 가족 그룹 응답
class FamilyGroupResponse(BaseModel):
    id: Union[str, UUID]
    group_name: str
    leader_id: Union[str, UUID]
    invite_code: str
    deadline_type: DeadlineTypeEnum
    status: GroupStatusEnum
    created_at: datetime
    updated_at: datetime
    
    @field_validator('id', 'leader_id', mode='before')
    @classmethod
    def validate_uuid_fields(cls, value):
        """UUID나 문자열을 문자열로 변환"""
        if isinstance(value, UUID):
            return str(value)
        return value
    
    @field_serializer('id', 'leader_id')
    def serialize_uuid_fields(self, value) -> str:
        return str(value)
    
    class Config:
        from_attributes = True

# 멤버 가입 요청
class MemberJoinRequest(BaseModel):
    invite_code: str = Field(..., min_length=8, max_length=8, description="초대 코드")
    relationship: RelationshipTypeEnum = Field(..., description="받는 분과의 관계")

# 가족 멤버 응답
class FamilyMemberResponse(BaseModel):
    id: Union[str, UUID]
    group_id: Union[str, UUID]
    user_id: Union[str, UUID]
    recipient_id: Union[str, UUID]
    member_relationship: RelationshipTypeEnum
    role: MemberRoleEnum
    joined_at: datetime
    
    # 사용자 정보 포함
    user_name: Optional[str] = None
    user_profile_image: Optional[str] = None
    
    @field_validator('id', 'group_id', 'user_id', 'recipient_id', mode='before')
    @classmethod
    def validate_uuid_fields(cls, value):
        """UUID나 문자열을 문자열로 변환"""
        if isinstance(value, UUID):
            return str(value)
        return value
    
    @field_serializer('id', 'group_id', 'user_id', 'recipient_id')
    def serialize_uuid_fields(self, value) -> str:
        return str(value)
    
    class Config:
        from_attributes = True

# 초대 코드 검증 응답
class InviteCodeValidation(BaseModel):
    valid: bool
    group_name: Optional[str] = None
    current_member_count: Optional[int] = None
    max_members: int = 20
    recipient_name: Optional[str] = None

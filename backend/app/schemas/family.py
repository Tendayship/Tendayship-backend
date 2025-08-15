from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, Field
from enum import Enum

class DeadlineTypeEnum(str, Enum):
    SECOND_WEEK = "second_week"  # 매월 둘째 주 일요일
    FOURTH_WEEK = "fourth_week"  # 매월 넷째 주 일요일

class GroupStatusEnum(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

class RelationshipTypeEnum(str, Enum):
    DAUGHTER = "daughter"
    SON = "son"
    DAUGHTER_IN_LAW = "daughter_in_law"
    SON_IN_LAW = "son_in_law"

class MemberRoleEnum(str, Enum):
    LEADER = "leader"
    MEMBER = "member"

# 가족 그룹 생성 요청 (MVP 기준)
class FamilyGroupCreate(BaseModel):
    group_name: str = Field(..., min_length=1, max_length=100, description="가족 그룹명")
    deadline_type: DeadlineTypeEnum = Field(..., description="마감일 타입")
    leader_relationship: RelationshipTypeEnum = Field(..., description="리더와 받는 분의 관계")

# 가족 그룹 응답
class FamilyGroupResponse(BaseModel):
    id: str
    group_name: str
    leader_id: str
    invite_code: str
    deadline_type: DeadlineTypeEnum
    status: GroupStatusEnum
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# 멤버 가입 요청
class MemberJoinRequest(BaseModel):
    invite_code: str = Field(..., min_length=8, max_length=8, description="초대 코드")
    relationship: RelationshipTypeEnum = Field(..., description="받는 분과의 관계")

# 가족 멤버 응답
class FamilyMemberResponse(BaseModel):
    id: str
    group_id: str
    user_id: str
    recipient_id: str
    member_relationship: RelationshipTypeEnum
    role: MemberRoleEnum
    joined_at: datetime
    
    # 사용자 정보 포함
    user_name: Optional[str] = None
    user_profile_image: Optional[str] = None
    
    class Config:
        from_attributes = True

# 초대 코드 검증 응답
class InviteCodeValidation(BaseModel):
    valid: bool
    group_name: Optional[str] = None
    current_member_count: Optional[int] = None
    max_members: int = 20
    recipient_name: Optional[str] = None

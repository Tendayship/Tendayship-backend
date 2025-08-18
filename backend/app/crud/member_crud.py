from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from .base import BaseCRUD
from ..models.family import FamilyMember
from ..schemas.family import MemberJoinRequest
from ..core.constants import ROLE_MEMBER

class FamilyMemberCRUD(BaseCRUD[FamilyMember, dict, dict]):
    
    async def create_member(
        self,
        db: AsyncSession,
        user_id: str,
        group_id: str,
        recipient_id: str,
        relationship: str,
        role: str = ROLE_MEMBER
    ) -> FamilyMember:
        """새 멤버 생성"""
        member_data = {
            "user_id": user_id,
            "group_id": group_id,
            "recipient_id": recipient_id,
            "member_relationship": relationship,
            "role": role
        }
        
        db_member = FamilyMember(**member_data)
        db.add(db_member)
        # Transaction management moved to upper layer
        return db_member
    
    async def get_by_user_and_group(
        self,
        db: AsyncSession,
        user_id: str,
        group_id: str
    ) -> Optional[FamilyMember]:
        """사용자와 그룹으로 멤버 조회"""
        result = await db.execute(
            select(FamilyMember)
            .where(
                and_(
                    FamilyMember.user_id == user_id,
                    FamilyMember.group_id == group_id
                )
            )
        )
        return result.scalars().first()
    
    async def get_group_members(
        self,
        db: AsyncSession,
        group_id: str
    ) -> List[FamilyMember]:
        """그룹의 모든 멤버 조회"""
        result = await db.execute(
            select(FamilyMember)
            .where(FamilyMember.group_id == group_id)
            .options(selectinload(FamilyMember.user))
        )
        return result.scalars().all()
    
    async def check_user_membership(
        self,
        db: AsyncSession,
        user_id: str
    ) -> Optional[FamilyMember]:
        """사용자가 어떤 그룹에 속해있는지 확인"""
        result = await db.execute(
            select(FamilyMember)
            .where(FamilyMember.user_id == user_id)
            .limit(1)
        )
        return result.scalars().first()

# 싱글톤 인스턴스
family_member_crud = FamilyMemberCRUD(FamilyMember)

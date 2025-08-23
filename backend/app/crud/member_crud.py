from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from .base import BaseCRUD
from ..models.family import FamilyMember, RelationshipType, MemberRole
from ..schemas.family import MemberJoinRequest
from ..core.constants import ROLE_MEMBER

class FamilyMemberCRUD(BaseCRUD[FamilyMember, dict, dict]):

    async def create_member(
        self,
        db: AsyncSession,
        user_id: str,
        group_id: str,
        recipient_id: str,
        relationship,
        role = ROLE_MEMBER
    ) -> FamilyMember:
        if recipient_id is None:
            raise ValueError("recipient_id is required to create FamilyMember")
        
        if isinstance(relationship, str):
            relationship = RelationshipType(relationship)
        elif hasattr(relationship, 'value'):
            relationship = RelationshipType(relationship.value)
            
        if isinstance(role, str):
            if role == ROLE_MEMBER:
                role = MemberRole.MEMBER
            else:
                role = MemberRole(role)
        elif hasattr(role, 'value'):
            role = MemberRole(role.value)

        db_member = FamilyMember(
            user_id=user_id,
            group_id=group_id,
            recipient_id=recipient_id,
            member_relationship=relationship,
            role=role
        )
        
        db.add(db_member)
        await db.flush()
        await db.refresh(db_member)
        return db_member

    async def get_by_user_and_group(
        self,
        db: AsyncSession,
        user_id: str,
        group_id: str
    ) -> Optional[FamilyMember]:
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
        result = await db.execute(
            select(FamilyMember)
            .where(FamilyMember.user_id == user_id)
            .limit(1)
        )
        return result.scalars().first()

family_member_crud = FamilyMemberCRUD(FamilyMember)

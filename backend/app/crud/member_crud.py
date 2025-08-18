from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from .base import BaseCRUD
from ..models.family import FamilyMember
from ..schemas.family import MemberJoinRequest

class FamilyMemberCRUD(BaseCRUD[FamilyMember, dict, dict]):
    
    async def create_member(
        self,
        db: AsyncSession,
        user_id: str,
        group_id: str,
        recipient_id: str,
        relationship: str,
        role: str = "member"
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
        await db.commit()
        await db.refresh(db_member)
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
        """사용자가 어떤 그룹에 속해있는지 확인 - 안전한 버전"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info(f"멤버십 확인 시작: user_id={user_id}")
            
            result = await db.execute(
                select(FamilyMember)
                .where(FamilyMember.user_id == user_id)
                .limit(1)
            )
            member = result.scalars().first()
            
            if member:
                logger.info(f"멤버십 확인 완료: group_id={member.group_id}, role={member.role}")
            else:
                logger.info(f"멤버십 없음: user_id={user_id}")
                
            return member
            
        except Exception as e:
            logger.error(f"멤버십 확인 중 오류: {str(e)}")
            return None

# 싱글톤 인스턴스
family_member_crud = FamilyMemberCRUD(FamilyMember)

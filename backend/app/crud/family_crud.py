from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
import secrets
import string

from .base import BaseCRUD
from ..models.family import FamilyGroup, FamilyMember
from ..schemas.family import FamilyGroupCreate

class FamilyGroupCRUD(BaseCRUD[FamilyGroup, dict, dict]):
    
    async def create_with_leader(
        self, 
        db: AsyncSession, 
        group_data: dict, 
        leader_id: str
    ) -> FamilyGroup: 
        """리더와 함께 가족 그룹 생성"""
        
        # 초대 코드 생성
        invite_code = self._generate_invite_code()
        
        # 가족 그룹 생성
        db_group = FamilyGroup(
            group_name=group_data["group_name"],
            leader_id=leader_id,
            invite_code=invite_code,
            deadline_type=group_data["deadline_type"],
            status="ACTIVE"
        )
        
        db.add(db_group)
        await db.commit()  
        await db.refresh(db_group)  
        
        return db_group 
    
    async def get_by_invite_code(
        self, 
        db: AsyncSession, 
        invite_code: str
    ) -> Optional[FamilyGroup]:
        """초대 코드로 활성 그룹 조회"""
        result = await db.execute(
            select(FamilyGroup)
            .where(
                and_(
                    FamilyGroup.invite_code == invite_code,
                    FamilyGroup.status == "ACTIVE"
                )
            )
            .options(selectinload(FamilyGroup.recipient))
        )
        return result.scalars().first()
    
    async def get_by_user_id(
        self, 
        db: AsyncSession, 
        user_id: str
    ) -> Optional[FamilyGroup]:
        """사용자가 속한 그룹 조회"""
        result = await db.execute(
            select(FamilyGroup)
            .join(FamilyMember)
            .where(FamilyMember.user_id == user_id)
            .options(
                selectinload(FamilyGroup.members),
                selectinload(FamilyGroup.recipient)
            )
        )
        return result.scalars().first()
    
    def _generate_invite_code(self) -> str:
        """8자리 초대 코드 생성 (대문자+숫자)"""
        return ''.join(secrets.choice(string.ascii_uppercase + string.digits) 
                      for _ in range(8))

# 싱글톤 인스턴스
family_group_crud = FamilyGroupCRUD(FamilyGroup)

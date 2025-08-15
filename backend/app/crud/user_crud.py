from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from .base import BaseCRUD
from ..models.user import User
from ..schemas.user import UserCreate, UserUpdate, UserProfileUpdate


class UserCRUD(BaseCRUD[User, UserCreate, UserUpdate]):
    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """이메일로 사용자 조회"""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalars().first()
    
    async def get_by_kakao_id(self, db: AsyncSession, kakao_id: str) -> Optional[User]:
        """카카오 ID로 사용자 조회"""
        result = await db.execute(select(User).where(User.kakao_id == kakao_id))
        return result.scalars().first()
    
    async def get_by_id(self, db: AsyncSession, user_id: UUID) -> Optional[User]:
        """ID로 사용자 조회"""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalars().first()
    
    async def update_profile(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        profile_data: UserProfileUpdate
    ) -> User:
        """사용자 프로필 정보 업데이트"""
        user = await self.get_by_id(db, user_id)
        if not user:
            raise ValueError("사용자를 찾을 수 없습니다")
        
        # 업데이트할 필드만 수정
        update_data = profile_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        
        await db.commit()
        await db.refresh(user)
        return user
    
    async def deactivate_user(self, db: AsyncSession, user_id: UUID) -> bool:
        """사용자 비활성화 (소프트 삭제)"""
        user = await self.get_by_id(db, user_id)
        if not user:
            return False
        
        user.is_active = False
        user.is_deleted = True
        await db.commit()
        return True


# 싱글톤 인스턴스
user_crud = UserCRUD(User)

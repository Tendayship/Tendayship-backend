from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .base import BaseCRUD
from ..models.user import User
from ..schemas.user import UserCreate, UserUpdate


class UserCRUD(BaseCRUD[User, UserCreate, UserUpdate]):
    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """이메일로 사용자 조회"""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalars().first()
    
    async def get_by_kakao_id(self, db: AsyncSession, kakao_id: str) -> Optional[User]:
        """카카오 ID로 사용자 조회"""
        result = await db.execute(select(User).where(User.kakao_id == kakao_id))
        return result.scalars().first()


# 싱글톤 인스턴스
user_crud = UserCRUD(User)

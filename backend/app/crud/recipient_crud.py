from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .base import BaseCRUD
from ..models.recipient import Recipient
from ..schemas.recipient import RecipientCreate, RecipientUpdate

class RecipientCRUD(BaseCRUD[Recipient, RecipientCreate, RecipientUpdate]):
    
    async def get_by_group_id(
        self,
        db: AsyncSession,
        group_id: str
    ) -> Optional[Recipient]:
        """그룹 ID로 받는 분 정보 조회"""
        result = await db.execute(
            select(Recipient).where(Recipient.group_id == group_id)
        )
        return result.scalars().first()
    
    async def create_with_group(
        self,
        db: AsyncSession,
        recipient_data: RecipientCreate,
        group_id: str
    ) -> Recipient:
        """그룹 ID와 함께 받는 분 생성"""
        db_recipient = Recipient(
            **recipient_data.dict(),
            group_id=group_id
        )
        
        db.add(db_recipient)
        await db.commit()
        await db.refresh(db_recipient)
        
        return db_recipient

# 싱글톤 인스턴스 생성
recipient_crud = RecipientCRUD(Recipient)
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .base import BaseCRUD
from ..models.recipient import Recipient
from ..schemas.recipient import RecipientCreate, RecipientUpdate

class RecipientCRUD(BaseCRUD[Recipient, RecipientCreate, RecipientUpdate]):
    
    async def create(self, db: AsyncSession, obj_in):
        if hasattr(obj_in, "dict"):
            create_data = obj_in.dict()
        else:
            create_data = obj_in
            
        db_obj = Recipient(**create_data)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def get_by_group_id(
        self,
        db: AsyncSession,
        group_id: str
    ) -> Optional[Recipient]:
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
        db_recipient = Recipient(
            **recipient_data.dict(),
            group_id=group_id
        )
        db.add(db_recipient)
        await db.flush()
        await db.refresh(db_recipient)
        return db_recipient

recipient_crud = RecipientCRUD(Recipient)

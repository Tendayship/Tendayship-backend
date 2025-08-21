from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from datetime import datetime, timedelta
import uuid

from ..models.refresh_token import RefreshToken
from .base import BaseCRUD


class RefreshTokenCRUD(BaseCRUD[RefreshToken, dict, dict]):
    
    async def create_token(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> RefreshToken:
        """새 리프레시 토큰 생성"""
        token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            device_info=device_info,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.add(token)
        await db.flush()  # 상태 변경 반영, commit 없이
        await db.refresh(token)
        return token
    
    async def get_by_token_hash(
        self,
        db: AsyncSession,
        token_hash: str
    ) -> Optional[RefreshToken]:
        """토큰 해시로 리프레시 토큰 조회"""
        stmt = select(RefreshToken).where(
            and_(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked == False
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_valid_token(
        self,
        db: AsyncSession,
        token_hash: str
    ) -> Optional[RefreshToken]:
        """유효한 리프레시 토큰 조회 (만료되지 않고 폐기되지 않음)"""
        stmt = select(RefreshToken).where(
            and_(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked == False,
                RefreshToken.expires_at > datetime.utcnow()
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def revoke_token(
        self,
        db: AsyncSession,
        token_hash: str
    ) -> bool:
        """토큰 폐기"""
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await db.execute(stmt)
        token = result.scalar_one_or_none()
        
        if token:
            token.revoked = True
            await db.flush()  # 상태 변경만 반영
            return True
        return False
    
    async def revoke_all_user_tokens(
        self,
        db: AsyncSession,
        user_id: uuid.UUID
    ) -> int:
        """사용자의 모든 토큰 폐기"""
        stmt = select(RefreshToken).where(
            and_(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked == False
            )
        )
        result = await db.execute(stmt)
        tokens = result.scalars().all()
        
        revoked_count = 0
        for token in tokens:
            token.revoked = True
            revoked_count += 1
        
        if revoked_count > 0:
            await db.flush()  # 상태 변경만 반영
        
        return revoked_count
    
    async def get_user_tokens(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        include_revoked: bool = False
    ) -> List[RefreshToken]:
        """사용자의 리프레시 토큰 목록 조회"""
        conditions = [RefreshToken.user_id == user_id]
        
        if not include_revoked:
            conditions.append(RefreshToken.revoked == False)
        
        stmt = select(RefreshToken).where(and_(*conditions)).order_by(RefreshToken.issued_at.desc())
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def cleanup_expired_tokens(
        self,
        db: AsyncSession,
        before_date: Optional[datetime] = None
    ) -> int:
        """만료된 토큰 정리"""
        if before_date is None:
            before_date = datetime.utcnow()
        
        stmt = select(RefreshToken).where(
            or_(
                RefreshToken.expires_at < before_date,
                RefreshToken.revoked == True
            )
        )
        result = await db.execute(stmt)
        tokens_to_delete = result.scalars().all()
        
        for token in tokens_to_delete:
            await db.delete(token)
        
        if tokens_to_delete:
            await db.flush()  # 삭제 작업만 반영, commit은 상위에서
        
        return len(tokens_to_delete)
    
    async def get_token_with_user(
        self,
        db: AsyncSession,
        token_hash: str
    ) -> Optional[RefreshToken]:
        """토큰과 사용자 정보를 함께 조회"""
        from ..models.user import User
        
        stmt = select(RefreshToken).join(User).where(
            and_(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked == False,
                RefreshToken.expires_at > datetime.utcnow()
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


# 인스턴스 생성
refresh_token_crud = RefreshTokenCRUD(RefreshToken)
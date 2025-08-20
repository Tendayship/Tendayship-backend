from typing import Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError

from ..crud.member_crud import family_member_crud
from ..database.session import get_db
from ..core.security import verify_token
from ..crud.user_crud import user_crud
from ..models.user import User

security = HTTPBearer(auto_error=False)  # auto_error=False로 설정

# 쿠키 이름 상수
COOKIE_NAME = "access_token"

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 정보가 없습니다",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # 1. 쿠키에서 토큰 우선 확인
    token = request.cookies.get(COOKIE_NAME)
    
    # 2. 쿠키에 없으면 Authorization 헤더에서 확인 (fallback)
    if not token and credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    
    if not token:
        raise credentials_exception
    
    try:
        payload = verify_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    except Exception:
        raise credentials_exception
    
    user = await user_crud.get(db, id=user_id)
    if user is None:
        raise credentials_exception
    
    return user

async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    try:
        return await get_current_user(request, db, credentials)
    except HTTPException:
        return None

async def require_auth(
    request: Request,
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> User:
    return await get_current_user(request, db, credentials)

async def get_current_member(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    membership = await family_member_crud.check_user_membership(db, current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="가족 그룹에 속해있지 않습니다"
        )
    
    return membership
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import timedelta, datetime
import secrets
import hashlib

from ...database.session import get_db
from ...services.auth_service import kakao_oauth_service
from ...schemas.user import SocialLogin, UserProfileUpdate
from ...core.security import create_access_token
from ...api.dependencies import get_current_user
from ...models.user import User
from ...crud.user_crud import user_crud
from ...crud.refresh_token_crud import refresh_token_crud
from ...core.config import settings

import logging
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

# 쿠키 설정 상수
ACCESS_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"

def _cookie_common_kwargs() -> dict:
    return {
        "httponly": True,
        "secure": not settings.DEBUG,
        "samesite": "Lax",
    }

def set_access_cookie(response, token: str):
    kwargs = _cookie_common_kwargs()
    kwargs.update({
        "max_age": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "path": settings.ACCESS_TOKEN_PATH or "/",
    })
    if settings.TOKEN_COOKIE_DOMAIN:
        kwargs["domain"] = settings.TOKEN_COOKIE_DOMAIN
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=token,
        **kwargs
    )

def set_refresh_cookie(response, token: str):
    kwargs = _cookie_common_kwargs()
    kwargs.update({
        "max_age": settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        "path": settings.REFRESH_TOKEN_PATH or "/api/auth/refresh",
    })
    if settings.TOKEN_COOKIE_DOMAIN:
        kwargs["domain"] = settings.TOKEN_COOKIE_DOMAIN
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        **kwargs
    )

def clear_auth_cookies(response):
    # 쿠키 삭제 시 path/domain 동일해야 함
    kw = {
        "path": settings.ACCESS_TOKEN_PATH or "/",
    }
    if settings.TOKEN_COOKIE_DOMAIN:
        kw["domain"] = settings.TOKEN_COOKIE_DOMAIN
    response.delete_cookie(ACCESS_COOKIE_NAME, **kw)
    
    kw = {
        "path": settings.REFRESH_TOKEN_PATH or "/api/auth/refresh",
    }
    if settings.TOKEN_COOKIE_DOMAIN:
        kw["domain"] = settings.TOKEN_COOKIE_DOMAIN
    response.delete_cookie(REFRESH_COOKIE_NAME, **kw)

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

async def save_refresh_token(db: AsyncSession, user_id: str, rt_hash: str, expires_at: datetime, request: Optional[Request] = None):
    """DB에 리프레시 토큰 저장"""
    device_info = None
    ip_address = None
    user_agent = None
    
    if request:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")
    
    return await refresh_token_crud.create_token(
        db=db,
        user_id=uuid.UUID(user_id),
        token_hash=rt_hash,
        expires_at=expires_at,
        device_info=device_info,
        ip_address=ip_address,
        user_agent=user_agent
    )

async def get_refresh_token_record(db: AsyncSession, rt_hash: str):
    """DB에서 리프레시 토큰 조회"""
    return await refresh_token_crud.get_valid_token(db, rt_hash)

async def revoke_refresh_token(db: AsyncSession, rt_hash: str):
    """DB에서 리프레시 토큰 폐기"""
    return await refresh_token_crud.revoke_token(db, rt_hash)

async def revoke_all_refresh_tokens_for_user(db: AsyncSession, user_id: str):
    """DB에서 사용자의 모든 리프레시 토큰 폐기"""
    return await refresh_token_crud.revoke_all_user_tokens(db, uuid.UUID(user_id))


@router.get("/kakao/callback")
async def kakao_oauth_callback(
    request: Request,
    code: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """카카오 OAuth 콜백 처리 - 프론트 콜백 페이지로 리다이렉트"""
    
    # 에러 처리
    if error:
        error_msg = error_description or error
        logger.error(f"OAuth error received: {error} - {error_description}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback/fail?reason={error}",
            status_code=302
        )
    
    if not code:
        logger.error("No authorization code received")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback/fail?reason=no_code",
            status_code=302
        )
    
    try:
        logger.info(f"Starting OAuth callback with code: {code[:20]}...")
        
        # OAuth 처리
        access_token = await kakao_oauth_service.get_access_token(code)
        kakao_user_info = await kakao_oauth_service.get_user_info(access_token)
        
        if not await kakao_oauth_service.verify_kakao_account(kakao_user_info):
            logger.warning("Account verification failed")
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/auth/callback/fail?reason=invalid_account",
                status_code=302
            )
        
        user = await kakao_oauth_service.login_or_create_user(kakao_user_info, db)
        access_jwt = create_access_token(data={"sub": str(user.id)}, expires_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        # Refresh Token 생성(opaque string)
        refresh_token = secrets.token_urlsafe(64)
        rt_expires = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        await save_refresh_token(db, str(user.id), hash_token(refresh_token), rt_expires, request)
        
        # 모든 토큰 작업 완료 후 단일 커밋
        await db.commit()
        
        response = RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback/success",
            status_code=302
        )
        set_access_cookie(response, access_jwt)
        set_refresh_cookie(response, refresh_token)
        return response
        
    except Exception as e:
        logger.error(f"OAuth callback failed: {str(e)}", exc_info=True)
        await db.rollback()  # 예외 시 롤백으로 일관성 보장
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback/fail?reason=server_error",
            status_code=302
        )

@router.post("/kakao")
async def kakao_login(
    request: Request,
    login_data: SocialLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    카카오 OAuth 로그인 (API 엔드포인트) - 쿠키 기반 JWT 설정
    1. 인가 코드로 액세스 토큰 받기
    2. 액세스 토큰으로 사용자 정보 받기
    3. 카카오 계정 검증
    4. 사용자 생성 또는 기존 사용자 반환
    5. JWT 토큰 발급 (쿠키로 설정)
    """
    try:
        # 1. 액세스 토큰 받기
        access_token = await kakao_oauth_service.get_access_token(login_data.code)
        
        # 2. 사용자 정보 받기
        kakao_user_info = await kakao_oauth_service.get_user_info(access_token)
        
        # 3. 카카오 계정 검증
        if not await kakao_oauth_service.verify_kakao_account(kakao_user_info):
            raise HTTPException(status_code=400, detail="유효하지 않은 카카오 계정입니다")
        
        # 4. 로그인 또는 회원가입
        user = await kakao_oauth_service.login_or_create_user(kakao_user_info, db)
        
        # 5. JWT 토큰 생성
        access_jwt = create_access_token(data={"sub": str(user.id)}, expires_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        # Refresh Token 생성(opaque string)
        refresh_token = secrets.token_urlsafe(64)
        rt_expires = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        await save_refresh_token(db, str(user.id), hash_token(refresh_token), rt_expires, request)
        
        # 모든 토큰 작업 완료 후 단일 커밋
        await db.commit()
        
        response = JSONResponse(content={
            "success": True,
            "user": {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
                "profile_image_url": user.profile_image_url,
                "is_new_user": user.created_at == user.updated_at
            }
        })
        set_access_cookie(response, access_jwt)
        set_refresh_cookie(response, refresh_token)
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()  # 예외 시 롤백으로 일관성 보장
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/kakao/url")
async def get_kakao_login_url():
    """카카오 로그인 URL 생성"""
    # 카카오 OAuth 스코프는 앱 설정에서 활성화되어야 함
    # account_email 스코프가 앱에서 비활성화된 경우 기본 정보만 요청
    kakao_login_url = (
        f"https://kauth.kakao.com/oauth/authorize"
        f"?client_id={kakao_oauth_service.client_id}"
        f"&redirect_uri={kakao_oauth_service.redirect_uri}"
        f"&response_type=code"
        f"&state=random_state_string"  # CSRF 방지
    )
    
    return {"login_url": kakao_login_url}

@router.get("/me", response_model=dict)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """현재 로그인한 사용자 정보 조회"""
    user = await user_crud.get_by_id(db, current_user.id)
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "phone": user.phone,
        "birth_date": user.birth_date.isoformat() if user.birth_date else None,
        "profile_image_url": user.profile_image_url,
        "kakao_id": user.kakao_id,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat()
    }

@router.put("/profile", response_model=dict)
async def update_user_profile(
    profile_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """사용자 프로필 정보 수정"""
    updated_user = await user_crud.update_profile(db, current_user.id, profile_data)
    return {
        "message": "프로필이 성공적으로 업데이트되었습니다",
        "user": {
            "id": str(updated_user.id),
            "name": updated_user.name,
            "phone": updated_user.phone,
            "birth_date": updated_user.birth_date.isoformat() if updated_user.birth_date else None,
            "updated_at": updated_user.updated_at.isoformat()
        }
    }

@router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    """로그아웃 - RT 폐기 및 쿠키 삭제"""
    try:
        rt = request.cookies.get(REFRESH_COOKIE_NAME)
        
        # AT는 서버 저장 필요 없음, RT만 폐기
        if rt:
            rt_h = hash_token(rt)
            await revoke_refresh_token(db, rt_h)
            # RT 폐기 완료 후 커밋
            await db.commit()
        
        response = JSONResponse(content={"message": "로그아웃되었습니다."})
        clear_auth_cookies(response)
        return response
        
    except Exception as e:
        await db.rollback()  # 예외 시 롤백
        # 로그아웃은 클라이언트 쿠키 삭제가 주 목적이므로 DB 실패해도 성공 반환
        response = JSONResponse(content={"message": "로그아웃되었습니다."})
        clear_auth_cookies(response)
        return response

@router.post("/refresh")
async def refresh_token(request: Request, db: AsyncSession = Depends(get_db)):
    """리프레시 토큰으로 새 액세스 토큰 발급"""
    try:
        rt = request.cookies.get(REFRESH_COOKIE_NAME)
        if not rt:
            raise HTTPException(status_code=401, detail="Missing refresh token")
        
        # 현재 사용자 식별은 RT 기록으로 역추적
        rt_h = hash_token(rt)
        record = await get_refresh_token_record(db, rt_h)
        if not record:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        # 트랜잭션 안전성을 위한 순서: 새 RT 생성 → 이전 RT 폐기 → 커밋
        user_id = str(record.user_id)
        new_access = create_access_token(data={"sub": user_id}, expires_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        new_refresh = secrets.token_urlsafe(64)
        new_rt_hash = hash_token(new_refresh)
        new_expires = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        # 1. 새 RT 생성 (실패 시 이전 RT 유지됨)
        await save_refresh_token(db, user_id, new_rt_hash, new_expires, request)
        
        # 2. 새 RT 생성 성공 후 이전 RT 폐기
        await revoke_refresh_token(db, rt_h)
        
        # 3. 모든 작업 완료 후 단일 커밋
        await db.commit()
        
        resp = JSONResponse(content={"success": True})
        set_access_cookie(resp, new_access)
        set_refresh_cookie(resp, new_refresh)
        return resp
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()  # 예외 시 롤백으로 이전 RT 보존
        raise HTTPException(status_code=500, detail="Token refresh failed")

@router.get("/verify")
async def verify_token(
    current_user: User = Depends(get_current_user)
):
    """토큰 유효성 검증"""
    return {
        "valid": True,
        "user_id": str(current_user.id),
        "email": current_user.email,
        "name": current_user.name
    }
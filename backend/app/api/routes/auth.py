from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from ...database.session import get_db
from ...services.auth_service import kakao_oauth_service
from ...schemas.user import SocialLogin, KakaoLoginResponse, UserProfileUpdate
from ...core.security import create_access_token
from ...api.dependencies import get_current_user
from ...models.user import User
from ...crud.user_crud import user_crud
import secrets

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/kakao/callback")
async def kakao_oauth_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    카카오 OAuth 콜백 처리
    
    1. 인가 코드로 액세스 토큰 받기
    2. 액세스 토큰으로 사용자 정보 받기
    3. 카카오 계정 검증 (실제 카카오 계정인지 확인)
    4. 사용자 생성 또는 기존 사용자 반환
    5. JWT 토큰 발급 및 리다이렉트
    """
    if error:
        error_msg = error_description or error
        print(f"DEBUG: OAuth error received: {error} - {error_description}")
        return RedirectResponse(
            url=f"{kakao_oauth_service.frontend_url}/login?error={error}&message={error_msg}",
            status_code=302
        )
    
    if not code:
        print("DEBUG: No authorization code received")
        return RedirectResponse(
            url=f"{kakao_oauth_service.frontend_url}/login?error=no_code",
            status_code=302
        )
    
    try:
        print(f"DEBUG: Starting OAuth callback with code: {code[:20]}...")
        
        # 1. 액세스 토큰 받기
        print("DEBUG: Step 1 - Getting access token...")
        access_token = await kakao_oauth_service.get_access_token(code)
        print(f"DEBUG: Got access token: {access_token[:20] if access_token else 'None'}...")
        
        # 2. 사용자 정보 받기
        print("DEBUG: Step 2 - Getting user info...")
        kakao_user_info = await kakao_oauth_service.get_user_info(access_token)
        print(f"DEBUG: Got user info: {kakao_user_info.get('id') if kakao_user_info else 'None'}")
        
        # 3. 카카오 계정 검증 (실제 카카오 계정인지 확인)
        print("DEBUG: Step 3 - Verifying account...")
        if not await kakao_oauth_service.verify_kakao_account(kakao_user_info):
            print("DEBUG: Account verification failed")
            return RedirectResponse(
                url=f"{kakao_oauth_service.frontend_url}/login?error=invalid_kakao_account",
                status_code=302
            )
        print("DEBUG: Account verification passed")
        
        # 4. 로그인 또는 회원가입
        print("DEBUG: Step 4 - Login or create user...")
        user = await kakao_oauth_service.login_or_create_user(kakao_user_info, db)
        print(f"DEBUG: User: {user.id if user else 'None'}")
        
        # 5. JWT 토큰 생성
        print("DEBUG: Step 5 - Creating JWT token...")
        jwt_token = create_access_token(data={"sub": str(user.id)})
        print(f"DEBUG: JWT token created: {jwt_token[:20] if jwt_token else 'None'}...")
        
        # 6. 프론트엔드로 리다이렉트 (토큰 포함)
        redirect_url = f"{kakao_oauth_service.frontend_url}/auth/callback?token={jwt_token}&user_id={user.id}"
        print(f"DEBUG: Redirecting to: {redirect_url}")
        return RedirectResponse(url=redirect_url, status_code=302)
        
    except Exception as e:
        print(f"ERROR: OAuth callback failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return RedirectResponse(
            url=f"{kakao_oauth_service.frontend_url}/login?error=auth_failed",
            status_code=302
        )


@router.post("/kakao", response_model=KakaoLoginResponse)
async def kakao_login(
    login_data: SocialLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    카카오 OAuth 로그인 (API 엔드포인트)
    
    1. 인가 코드로 액세스 토큰 받기
    2. 액세스 토큰으로 사용자 정보 받기
    3. 카카오 계정 검증
    4. 사용자 생성 또는 기존 사용자 반환
    5. JWT 토큰 발급
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
        jwt_token = create_access_token(data={"sub": str(user.id)})
        
        return KakaoLoginResponse(
            user=user,
            is_new_user=user.created_at == user.updated_at,
            access_token=jwt_token
        )
        
    except Exception as e:
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
async def logout():
    """로그아웃 (클라이언트에서 토큰 삭제)"""
    return {"message": "로그아웃되었습니다. 클라이언트에서 토큰을 삭제해주세요."}


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

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...database.session import get_db
from ...services.auth_service import kakao_oauth_service
from ...schemas.user import SocialLogin, KakaoLoginResponse
from ...core.security import create_access_token

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/kakao", response_model=KakaoLoginResponse)
async def kakao_login(
    login_data: SocialLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    카카오 OAuth 로그인
    
    1. 인가 코드로 액세스 토큰 받기
    2. 액세스 토큰으로 사용자 정보 받기
    3. 사용자 생성 또는 기존 사용자 반환
    4. JWT 토큰 발급
    """
    try:
        # 1. 액세스 토큰 받기
        access_token = await kakao_oauth_service.get_access_token(login_data.code)
        
        # 2. 사용자 정보 받기
        kakao_user_info = await kakao_oauth_service.get_user_info(access_token)
        
        # 3. 로그인 또는 회원가입
        user = await kakao_oauth_service.login_or_create_user(kakao_user_info, db)
        
        # 4. JWT 토큰 생성
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
    kakao_login_url = (
        f"https://kauth.kakao.com/oauth/authorize"
        f"?client_id={kakao_oauth_service.client_id}"
        f"&redirect_uri={kakao_oauth_service.redirect_uri}"
        f"&response_type=code"
    )
    
    return {"login_url": kakao_login_url}

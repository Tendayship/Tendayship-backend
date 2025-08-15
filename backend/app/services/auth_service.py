from typing import Dict, Any
import requests
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.user import User
from ..crud.user_crud import UserCRUD


class KakaoOAuthService:
    """카카오 OAuth 인증 서비스"""
    
    def __init__(self):
        self.client_id = settings.KAKAO_CLIENT_ID
        self.redirect_uri = settings.KAKAO_REDIRECT_URI
        self.token_url = "https://kauth.kakao.com/oauth/token"
        self.user_info_url = "https://kapi.kakao.com/v2/user/me"
    
    async def get_access_token(self, code: str) -> str:
        """인가 코드로 액세스 토큰 받기"""
        try:
            token_response = requests.post(
                self.token_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "redirect_uri": self.redirect_uri,
                    "code": code,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
            )
            
            if token_response.status_code != 200:
                raise HTTPException(status_code=400, detail="카카오 토큰 요청 실패")
                
            token_data = token_response.json()
            return token_data.get("access_token")
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"카카오 OAuth 오류: {str(e)}")
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """액세스 토큰으로 사용자 정보 받기"""
        try:
            user_response = requests.post(
                self.user_info_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"
                }
            )
            
            if user_response.status_code != 200:
                raise HTTPException(status_code=400, detail="카카오 사용자 정보 요청 실패")
                
            return user_response.json()
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"카카오 사용자 정보 오류: {str(e)}")
    
    async def login_or_create_user(
        self, 
        kakao_user_info: Dict[str, Any], 
        db: AsyncSession
    ) -> User:
        """카카오 사용자 정보로 로그인 또는 회원가입"""
        kakao_account = kakao_user_info.get("kakao_account", {})
        profile = kakao_account.get("profile", {})
        
        email = kakao_account.get("email")
        name = profile.get("nickname", "")
        kakao_id = str(kakao_user_info.get("id"))
        
        # 기존 사용자 확인
        user_crud = UserCRUD()
        existing_user = await user_crud.get_by_email(db, email)
        
        if existing_user:
            # 기존 사용자 업데이트
            if not existing_user.kakao_id:
                existing_user.kakao_id = kakao_id
                await db.commit()
            return existing_user
        else:
            # 새 사용자 생성
            user_data = {
                "email": email,
                "name": name,
                "kakao_id": kakao_id,
                "profile_image_url": profile.get("profile_image_url")
            }
            return await user_crud.create(db, user_data)


# 싱글톤 인스턴스
kakao_oauth_service = KakaoOAuthService()

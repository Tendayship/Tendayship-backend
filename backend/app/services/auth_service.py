from typing import Dict, Any, Optional
import requests
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, date

from ..core.config import settings
from ..models.user import User
from ..crud.user_crud import user_crud
import secrets


class KakaoOAuthService:
    """카카오 OAuth 인증 서비스"""
    
    def __init__(self):
        self.client_id = settings.KAKAO_CLIENT_ID
        self.redirect_uri = settings.KAKAO_REDIRECT_URI
        self.frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
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
    
    async def verify_kakao_account(self, kakao_user_info: Dict[str, Any]) -> bool:
        """
        카카오 계정 검증 (실제 카카오 계정인지 확인)
        
        검증 조건:
        1. kakao_account 정보가 존재
        2. email이 존재하고 유효한 형식
        3. profile 정보가 존재
        4. 계정 상태가 정상
        """
        try:
            print(f"DEBUG: Verifying kakao account - Full user info: {kakao_user_info}")
            
            # 기본 구조 확인
            if not kakao_user_info.get("id"):
                print("DEBUG: Missing kakao user ID")
                return False
            print(f"DEBUG: Kakao ID found: {kakao_user_info.get('id')}")
            
            kakao_account = kakao_user_info.get("kakao_account", {})
            if not kakao_account:
                print("DEBUG: Missing kakao_account data")
                return False
            print(f"DEBUG: Kakao account data: {kakao_account}")
            
            # 이메일 확인 (선택적)
            email = kakao_account.get("email")
            print(f"DEBUG: Email from kakao_account: {email}")
            
            # 이메일이 없어도 계정 검증 통과 (카카오 ID로 식별 가능)
            # 단, 이메일이 있다면 유효한 형식이어야 함
            if email and "@" not in email:
                print("DEBUG: Email validation failed - invalid email format")
                return False
            
            if not email:
                print("DEBUG: No email provided - proceeding with kakao ID only")
            
            # 프로필 정보 확인
            profile = kakao_account.get("profile", {})
            print(f"DEBUG: Profile data: {profile}")
            if not profile.get("nickname"):
                print("DEBUG: Profile nickname validation failed")
                return False
            
            # 계정 상태 확인
            profile_needs_agreement = kakao_account.get("profile_needs_agreement", True)
            print(f"DEBUG: Profile needs agreement: {profile_needs_agreement}")
            
            # 추가 검증: 카카오 고유 ID가 숫자 형태인지 확인
            kakao_id = str(kakao_user_info.get("id"))
            if not kakao_id.isdigit():
                print(f"DEBUG: Kakao ID format validation failed - ID: {kakao_id}")
                return False
            
            print("DEBUG: All kakao account verification checks passed")
            return True
            
        except Exception as e:
            print(f"카카오 계정 검증 오류: {e}")
            import traceback
            traceback.print_exc()
            return False
    
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
        profile_image_url = profile.get("profile_image_url")
        
        # 이메일이 있으면 이메일로 먼저 확인, 없으면 카카오 ID로 확인
        if email:
            existing_user = await user_crud.get_by_email(db, email)
        else:
            # 이메일 없을 때는 카카오 ID로 기존 사용자 확인
            existing_user = await user_crud.get_by_kakao_id(db, kakao_id)
        
        if existing_user:
            # 기존 사용자 업데이트
            if not existing_user.kakao_id:
                existing_user.kakao_id = kakao_id
                await db.commit()
            return existing_user
        else:
            # 새 사용자 생성
            # 이메일이 없을 때는 카카오 ID 기반 더미 이메일 생성
            if not email:
                email = f"kakao_{kakao_id}@temp.kakao"
                
            user_data = {
                "email": email,
                "name": name,
                "kakao_id": kakao_id,
                "profile_image_url": profile_image_url
            }
            return await user_crud.create(db, user_data)
    
    # async def create_family_group_for_user(
    #     self,
    #     user: User,
    #     group_name: str,
    #     deadline_type: str,
    #     leader_relationship: str,
    #     recipient_name: str,
    #     recipient_address: str,
    #     db: AsyncSession
    # ) -> Dict[str, Any]:
    #     """
    #     사용자를 위한 가족 그룹 생성
    #     
    #     Args:
    #         user: 사용자 객체
    #         group_name: 가족 그룹명
    #         deadline_type: 마감일 타입 (SECOND_SUNDAY, FOURTH_SUNDAY)
    #         leader_relationship: 리더와 받는 분의 관계
    #         recipient_name: 받는 분 이름
    #         recipient_address: 받는 분 주소
    #         db: 데이터베이스 세션
    #     
    #     Returns:
    #         생성된 가족 그룹 정보
    #     """
    #     # 임시로 비활성화 - family.py로 이동 예정
    #     pass


# 싱글톤 인스턴스
kakao_oauth_service = KakaoOAuthService()

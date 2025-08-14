import os

import requests

from oauth.social_schema import SocialMember, PROVIDER_ENUM


KAKAO_CLIENT_ID = os.getenv("KAKAO_CLIENT_ID")
KAKAO_SECRET = os.getenv("KAKAO_SECRET")
KAKAO_CALLBACK_URL = "http://127.0.0.1:8000/"  # 실제 콜백 URL로 변경해야 합니다.

def auth_kakao(code: str):
    try:
        # kakao에 access token 요청
        token_url = f"https://kauth.kakao.com/oauth/token?client_id={KAKAO_CLIENT_ID}&client_secret={KAKAO_SECRET}&code={code}&grant_type=authorization_code&redirect_uri={KAKAO_CALLBACK_URL}"
        headers = {"Content-type": "application/x-www-form-urlencoded;charset=utf-8"}
        token_response = requests.post(token_url, headers=headers)
        if token_response.status_code != 200:
            raise Exception

        # kakao에 회원 정보 요청
        access_token = token_response.json()['access_token']
        user_info = f"https://kapi.kakao.com/v2/user/me"
        headers = {"Authorization": "Bearer " + access_token,
                   "Content-type": "application/x-www-form-urlencoded;charset=utf-8"}
        user_response = requests.post(user_info, headers=headers)
        if user_response.status_code != 200:
            raise Exception
    except:
        raise Exception("kakao oauth error")

    info = user_response.json()['kakao_account']
    name = info.get('name') if info.get('name') else info.get('profile').get('nickname')
    return SocialMember(
        name=name,
        email=info.get('email'),
        provider=PROVIDER_ENUM.KAKAO.name
    )
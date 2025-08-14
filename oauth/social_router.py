from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from starlette import status
from starlette.responses import JSONResponse

from oauth import social_handler
from oauth.social_schema import SocialLogin, PROVIDER_ENUM

app = APIRouter(
    prefix="/oauth",
)

@app.post(path="/{provider}", description="소셜 로그인 / 회원가입")
async def social_auth(provider: str, form: SocialLogin):
    # 나중에 다른 로그인 방법 추가 가능
    provider = PROVIDER_ENUM.from_str(provider.lower())
    if not provider:
        raise HTTPException(status_code=404)



    user_data = social_handler.auth_naver(form.code)

    
    response_body = {"message": "oauth register successful", "name": user_data.email}
    return JSONResponse(status_code=status.HTTP_200_OK, content=response_body)
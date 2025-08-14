from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel

# 로그인 상태 설정 / 추가 가능
class PROVIDER_ENUM(Enum):
    KAKAO = ('kakao')

    def __init__(self, title):
        self.title = title

    @classmethod
    def from_str(cls, name: str):
        for enum in cls:
            if enum.value == name:
                return enum


class SocialLogin(BaseModel):
    code: str


class SocialMember(BaseModel):
    email: Optional[str]
    name: Optional[str] = None
    provider: Union[str, PROVIDER_ENUM]
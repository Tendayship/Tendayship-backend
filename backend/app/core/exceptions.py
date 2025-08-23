from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

logger = logging.getLogger(__name__)

# CORS 헬퍼 함수 - main.py와 동일한 로직
def _get_allowed_origins_set() -> set[str]:
    """허용된 오리진 목록을 집합으로 반환"""
    from .config import settings
    origins = set()
    try:
        origins.update([
            "https://kind-sky-0070e521e.2.azurestaticapps.net"
        ])
        if getattr(settings, "FRONTEND_URL", None):
            origins.add(settings.FRONTEND_URL)
    except Exception:
        pass
    return origins

ALLOWED_ORIGINS_SET = _get_allowed_origins_set()

def _conditionally_set_cors_headers(request: Request, response: JSONResponse):
    """요청 Origin이 허용 목록에 있을 때만 CORS 헤더 설정"""
    origin = request.headers.get("origin")
    if origin and origin in ALLOWED_ORIGINS_SET:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Credentials"] = "true"

class FamilyNewsException(Exception):
    """애플리케이션 기본 예외 클래스"""
    def __init__(self, message: str, code: str = None):
        self.message = message
        self.code = code
        super().__init__(self.message)

class UserAlreadyExistsException(FamilyNewsException):
    """사용자가 이미 존재하는 경우"""
    pass

class GroupNotFoundException(FamilyNewsException):
    """그룹을 찾을 수 없는 경우"""
    pass

class InvalidInviteCodeException(FamilyNewsException):
    """유효하지 않은 초대 코드"""
    pass

class InsufficientPermissionException(FamilyNewsException):
    """권한이 부족한 경우"""
    pass

# 전역 예외 처리기
async def family_news_exception_handler(request: Request, exc: FamilyNewsException):
    logger.error(f"Application error: {exc.message}")
    response = JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "code": exc.code
        }
    )
    _conditionally_set_cors_headers(request, response)
    return response

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Validation error: {exc.errors()}")
    response = JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "message": "입력 데이터가 올바르지 않습니다",
            "details": exc.errors()
        }
    )
    _conditionally_set_cors_headers(request, response)
    return response

async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTP error: {exc.status_code} - {exc.detail}")
    response = JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTPException",
            "message": exc.detail
        }
    )
    _conditionally_set_cors_headers(request, response)
    return response

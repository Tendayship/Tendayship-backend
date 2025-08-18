from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time
import logging

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    """요청/응답 로깅 미들웨어"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # 요청 로깅
        logger.info(f"Request: {request.method} {request.url}")
        
        response = await call_next(request)
        
        # 응답 로깅
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        logger.info(
            f"Response: {response.status_code} "
            f"({process_time:.3f}s) "
            f"{request.method} {request.url}"
        )
        
        return response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """보안 헤더 추가 미들웨어"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # 기존 보안 헤더
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Azure 배포용 추가 보안 헤더
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
            "https://kind-sky-0070e521e.2.azurestaticapps.net "
            "https://cdn.jsdelivr.net; "  
            "style-src 'self' 'unsafe-inline' "
            "https://kind-sky-0070e521e.2.azurestaticapps.net "
            "https://cdn.jsdelivr.net; "  
            "img-src 'self' data: https: blob:; "
            "connect-src 'self' https://tendayapp-f0a0drg2b6avh8g3.koreacentral-01.azurewebsites.net"
        )
        
        return response


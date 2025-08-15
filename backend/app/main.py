# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
from datetime import datetime

# 내부 모듈 import
from .core.config import settings
from .core.exceptions import (
    FamilyNewsException,
    family_news_exception_handler,
    validation_exception_handler,
    http_exception_handler
)
from .api.middleware import LoggingMiddleware, SecurityHeadersMiddleware
from .database.session import init_db

# 라우터 import
from .api.routes import (
    auth,
    family, 
    members, 
    posts, 
    issues, 
    books, 
    subscription, 
    profile, 
    admin
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성 (API 문서 항상 활성화)
app = FastAPI(
    title=settings.APP_NAME if hasattr(settings, 'APP_NAME') else "Family News Service",
    version=settings.APP_VERSION if hasattr(settings, 'APP_VERSION') else "1.0.0",
    debug=getattr(settings, 'DEBUG', True),
    description="가족 소식 서비스 - 가족의 소식을 책자로 만들어 전달하는 서비스",
    docs_url="/docs",      # 항상 활성화
    redoc_url="/redoc",    # 항상 활성화
    openapi_url="/openapi.json"
)

# CORS 미들웨어 설정
allowed_origins = getattr(settings, 'ALLOWED_HOSTS', ["*"])
if allowed_origins == ["*"] or "localhost" in str(allowed_origins):
    allowed_origins = [
        "http://localhost:3000",  # React 개발 서버
        "http://localhost:8000",  # FastAPI 서버
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Trusted Host 미들웨어 (개발 환경에서는 느슨하게 설정)
if hasattr(settings, 'ALLOWED_HOSTS') and settings.ALLOWED_HOSTS != ["*"]:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS
    )

# 커스텀 미들웨어 추가
app.add_middleware(LoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# 예외 처리기 등록
app.add_exception_handler(FamilyNewsException, family_news_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)

# 기본 라우트
@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "Family News Service API",
        "version": getattr(settings, 'APP_VERSION', '1.0.0'),
        "description": "가족 소식지 서비스 API",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "api_prefix": getattr(settings, 'API_PREFIX', '/api/v1'),
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    try:
        # 데이터베이스 연결 확인 (선택적)
        from .database.session import AsyncSessionLocal
        from sqlalchemy import text
        
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "app": getattr(settings, 'APP_NAME', 'Family News Service'),
        "version": getattr(settings, 'APP_VERSION', '1.0.0'),
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/status")
async def api_status():
    """API 상태 및 엔드포인트 정보"""
    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            routes.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": getattr(route, 'name', 'unknown')
            })
    
    return {
        "total_routes": len(routes),
        "api_prefix": getattr(settings, 'API_PREFIX', '/api/v1'),
        "available_routes": routes[:10],  # 처음 10개만 표시
        "docs": {
            "swagger": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json"
        }
    }

# API 라우터 등록
api_prefix = getattr(settings, 'API_PREFIX', '/api/v1')

# 인증 라우터
app.include_router(
    auth.router, 
    prefix=api_prefix, 
    tags=["authentication"]
)

# 프로필 라우터
app.include_router(
    profile.router, 
    prefix=api_prefix, 
    tags=["profile"]
)

# 가족 관리 라우터
app.include_router(
    family.router, 
    prefix=api_prefix, 
    tags=["family"]
)

# 멤버 관리 라우터
app.include_router(
    members.router, 
    prefix=api_prefix, 
    tags=["members"]
)

# 소식 관리 라우터
app.include_router(
    posts.router, 
    prefix=api_prefix, 
    tags=["posts"]
)

# 회차 관리 라우터
app.include_router(
    issues.router, 
    prefix=api_prefix, 
    tags=["issues"]
)

# 책자 관리 라우터
app.include_router(
    books.router, 
    prefix=api_prefix, 
    tags=["books"]
)

# 구독 관리 라우터
app.include_router(
    subscription.router, 
    prefix=api_prefix, 
    tags=["subscription"]
)

# 관리자 라우터
app.include_router(
    admin.router, 
    prefix=api_prefix, 
    tags=["admin"]
)

# 이벤트 핸들러
@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 실행"""
    logger.info("Starting Family News Service...")
    
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        # 개발 환경에서는 계속 진행, 프로덕션에서는 중단 고려
    
    logger.info("=== Family News Service Started ===")
    logger.info(f"Version: {getattr(settings, 'APP_VERSION', '1.0.0')}")
    logger.info(f"Debug Mode: {getattr(settings, 'DEBUG', True)}")
    logger.info(f"API Documentation: /docs")
    logger.info(f"Alternative Documentation: /redoc")

@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 실행"""
    logger.info("Shutting down Family News Service...")
    
    # 정리 작업 (데이터베이스 연결 종료, 캐시 정리 등)
    try:
        # 필요시 여기에 정리 로직 추가
        pass
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
    
    logger.info("Family News Service stopped")

# 개발 환경용 디버그 라우트
if getattr(settings, 'DEBUG', True):
    @app.get("/debug/routes")
    async def debug_routes():
        """등록된 모든 라우트 확인 (개발용)"""
        routes = []
        for route in app.routes:
            if hasattr(route, 'path'):
                route_info = {
                    "path": route.path,
                    "name": getattr(route, 'name', 'unknown'),
                    "methods": list(getattr(route, 'methods', [])) if hasattr(route, 'methods') else []
                }
                routes.append(route_info)
        
        return {
            "total_routes": len(routes),
            "routes": sorted(routes, key=lambda x: x['path'])
        }
    
    @app.get("/debug/config")
    async def debug_config():
        """현재 설정 확인 (개발용)"""
        config_info = {}
        for attr in dir(settings):
            if not attr.startswith('_'):
                try:
                    value = getattr(settings, attr)
                    # 민감한 정보는 마스킹
                    if any(sensitive in attr.lower() for sensitive in ['password', 'secret', 'key', 'token']):
                        config_info[attr] = "*****"
                    else:
                        config_info[attr] = value
                except:
                    config_info[attr] = "Error reading value"
        
        return {
            "config": config_info,
            "app_info": {
                "title": app.title,
                "version": app.version,
                "debug": app.debug,
                "docs_url": app.docs_url,
                "redoc_url": app.redoc_url
            }
        }

# 에러 페이지 (404 등)
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return {
        "detail": "Not Found",
        "message": f"The path '{request.url.path}' was not found",
        "available_endpoints": {
            "docs": "/docs",
            "redoc": "/redoc", 
            "health": "/health",
            "api_status": "/api/status"
        }
    }

# 앱 정보 출력 (서버 시작 시)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

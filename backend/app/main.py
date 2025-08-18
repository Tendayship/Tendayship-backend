from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
from datetime import datetime

from dotenv import load_dotenv
import os

load_dotenv()

from .core.config import settings
from .core.exceptions import (
    FamilyNewsException,
    family_news_exception_handler,
    validation_exception_handler,
    http_exception_handler
)
from .api.middleware import LoggingMiddleware, SecurityHeadersMiddleware
from .database.session import init_db
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    description="가족 소식 서비스",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS 미들웨어
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://kind-sky-0070e521e.2.azurestaticapps.net",
        "http://localhost:3000",  # 개발용 유지
        "http://127.0.0.1:3000",  # 개발용 유지
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# TrustedHost 미들웨어
if hasattr(settings, 'ALLOWED_HOSTS') and settings.ALLOWED_HOSTS != ["*"]:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS
    )

app.add_middleware(LoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# 전역 예외 핸들러
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"전역 예외: {type(exc).__name__}: {str(exc)}")
    response = JSONResponse(
        status_code=500,
        content={
            "detail": "Internal Server Error",
            "message": "서버 내부 오류가 발생했습니다"
        }
    )
    # 환경에 따른 동적 CORS 설정
    frontend_url = settings.FRONTEND_URL
    response.headers["Access-Control-Allow-Origin"] = frontend_url
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    response = JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )
    # 환경에 따른 동적 CORS 설정
    frontend_url = settings.FRONTEND_URL
    response.headers["Access-Control-Allow-Origin"] = frontend_url
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

# 기본 예외 핸들러
app.add_exception_handler(FamilyNewsException, family_news_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)

@app.get("/")
async def root():
    return {
        "message": "Family News Service API",
        "version": settings.APP_VERSION,
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    try:
        from .database.session import AsyncSessionLocal
        from sqlalchemy import text
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "error"

    try:
        from .utils.azure_storage import get_storage_service
        storage_service = get_storage_service()
        storage_service._ensure_initialized()
        storage_status = "connected"
    except Exception:
        storage_status = "error"

    return {
        "status": "healthy",
        "database": db_status,
        "storage": storage_status,
        "timestamp": datetime.now().isoformat()
    }

# API 라우터 등록
api_prefix = settings.API_PREFIX
app.include_router(auth.router, prefix=api_prefix, tags=["authentication"])
app.include_router(profile.router, prefix=api_prefix, tags=["profile"])
app.include_router(family.router, prefix=api_prefix, tags=["family"])
app.include_router(members.router, prefix=api_prefix, tags=["members"])
app.include_router(posts.router, prefix=api_prefix, tags=["posts"])
app.include_router(issues.router, prefix=api_prefix, tags=["issues"])
app.include_router(books.router, prefix=api_prefix, tags=["books"])
app.include_router(subscription.router, prefix=api_prefix, tags=["subscription"])
app.include_router(admin.router, prefix=api_prefix, tags=["admin"])

@app.on_event("startup")
async def startup_event():
    logger.info("Starting Family News Service...")
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")

    try:
        from .utils.azure_storage import get_storage_service
        storage_service = get_storage_service()
        storage_service._ensure_initialized()
        logger.info("Azure Storage initialized successfully")
    except Exception as e:
        logger.error(f"Azure Storage initialization failed: {str(e)}")

    logger.info("Family News Service started")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Family News Service stopped")

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    response = JSONResponse(
        status_code=404,
        content={
            "detail": "Not Found",
            "message": f"The path '{request.url.path}' was not found"
        }
    )
    # 환경에 따른 동적 CORS 설정
    frontend_url = settings.FRONTEND_URL
    response.headers["Access-Control-Allow-Origin"] = frontend_url
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

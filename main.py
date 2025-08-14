from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware
from oauth import social_router

app = FastAPI()

app.include_router(social_router.app , tags=['oauth'])

app.add_middleware(
    TrustedHostMiddleware,
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allowed_hosts=["*"]  # 또는 특정 도메인만
)

class EchoReq(BaseModel):
    message: str

@app.get("/ping")
async def ping():
    return {"status": "ok"}

@app.post("/echo")
async def echo(body: EchoReq):
    return {"echo": body.message}

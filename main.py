from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.trustedhost import TrustedHostMiddleware

app = FastAPI()

app.add_middleware(
    TrustedHostMiddleware, 
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

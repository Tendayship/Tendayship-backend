from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class EchoReq(BaseModel):
    message: str

@app.get("/ping")
async def ping():
    return {"status": "ok"}

@app.post("/echo")
async def echo(body: EchoReq):
    return {"echo": body.message}

FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    POETRY_VERSION=0

WORKDIR /app

# 필수 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# FastAPI + Uvicorn 실행 (80 포트)
ENV PORT=80
EXPOSE 80
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
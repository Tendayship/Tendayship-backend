FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=/app
PIP_NO_CACHE_DIR=1
PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y
gcc
g++
libpq-dev
libffi-dev
libssl-dev
curl
&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip &&
pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3
CMD curl -f http://localhost:80/health || exit 1

RUN groupadd -r appuser && useradd -r -g appuser appuser &&
chown -R appuser:appuser /app
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]
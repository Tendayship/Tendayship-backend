# FastAPI 백엔드 API 명세서

## 기본 정보

**API 이름:** FastAPI Echo Service
**버전:** v1
**기본 URL:** `https://<SWA_DOMAIN>/api` (정적 웹앱을 통한 접근)
**직접 URL:** `https://<APP_SERVICE_NAME>.azurewebsites.net` (App Service 직접 접근)

## 인증

**인증 방식:** 없음 (현재 익명 접근)
**헤더:** 추가 인증 헤더 불필요

## 엔드포인트

### **GET /ping**

**설명:** 서버 상태 확인용 헬스 체크
**요청 파라미터:** 없음
**응답 예시:**

```json
{
  "status": "ok"
}
```

**상태 코드:**

- 200 OK

### **POST /echo**

**설명:** 클라이언트가 전송한 메시지를 그대로 반환
**요청 헤더:**

- Content-Type: application/json

**요청 본문:**

```json
{
  "message": "Hello World"
}
```

**응답 예시:**

```json
{
  "echo": "Hello World"
}
```

**상태 코드:**

- 200 OK
- 422 Validation Error


## 오류 처리

### **422 Validation Error:**

필수 필드 누락 또는 데이터 형식 오류

```json
{
  "detail": [
    {
      "loc": ["body", "message"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```


### **404 Not Found:**

존재하지 않는 엔드포인트 접근

```json
{
  "detail": "Not Found"
}
```


## 데이터 모델

### EchoRequest

```json
{
  "message": "string" // 필수 필드
}
```


### EchoResponse

```json
{
  "echo": "string"
}
```


### HealthResponse

```json
{
  "status": "ok"
}
```


## 추가 정보

**자동 생성 문서:**

- Swagger UI: `https://<APP_SERVICE_NAME>.azurewebsites.net/docs`
- ReDoc: `https://<APP_SERVICE_NAME>.azurewebsites.net/redoc`
- OpenAPI JSON: `https://<APP_SERVICE_NAME>.azurewebsites.net/openapi.json`

**주의사항:**

- 정적 웹앱에서 호출 시 반드시 `/api` 접두사 사용
- CORS 설정은 정적 웹앱에서 자동 처리
- 현재 Rate Limiting 미구현

<div style="text-align: center">⁂</div>
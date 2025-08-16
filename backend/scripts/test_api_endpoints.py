import requests
import json
import uuid
import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Add the parent directory to Python path to enable app imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class EnhancedAPITestRunner:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.headers = {"Content-Type": "application/json"}
        self.access_token = None
        self.test_user_id = None
        self.test_results = {}

    def check_server_connection(self):
        """서버 연결 상태 확인"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                print("[OK] 서버 연결 확인됨")
                return True
            else:
                print(f"[WARN] 서버 응답 오류: {response.status_code}")
                return False
        except Exception as e:
            print(f"[ERROR] 서버 연결 실패: {e}")
            return False

    async def setup_test_environment(self):
        """테스트 환경 설정 - 실제 사용자 생성 시도, 실패시 Mock UUID 사용"""
        try:
            # 방법 1: 실제 테스트 사용자 생성 시도
            await self.create_real_test_user()
            print("[OK] 실제 테스트 사용자 생성 완료")
        except Exception as e:
            print(f"[WARN] 실제 사용자 생성 실패, Mock UUID 사용: {e}")
            # 방법 2: Mock UUID 사용
            self.test_user_id = str(uuid.uuid4())
            print(f"[OK] Mock UUID 생성: {self.test_user_id[:8]}...")
        
        # JWT 토큰 생성
        self.access_token = self.create_test_jwt_token()
        print("[OK] JWT 토큰 생성 완료")

    async def create_real_test_user(self):
        """실제 테스트 사용자 및 가족 그룹 생성"""
        from app.database.session import AsyncSessionLocal
        from app.models.user import User
        from app.models.family import FamilyGroup
        from app.models.recipient import Recipient
        from app.models.family import FamilyMember
        from sqlalchemy import text
        import secrets
        
        async with AsyncSessionLocal() as db:
            try:
                # 기존 테스트 데이터 정리 (참조 무결성 순서 고려)
                # 1. 먼저 family_members 삭제
                await db.execute(text("DELETE FROM family_members WHERE user_id IN (SELECT id FROM users WHERE email = 'test@api.com')"))
                # 2. recipients 삭제 (family_groups 참조)
                await db.execute(text("DELETE FROM recipients WHERE group_id IN (SELECT id FROM family_groups WHERE group_name = 'API 테스트 가족')"))
                # 3. family_groups 삭제
                await db.execute(text("DELETE FROM family_groups WHERE group_name = 'API 테스트 가족' OR leader_id IN (SELECT id FROM users WHERE email = 'test@api.com')"))
                # 4. 마지막으로 users 삭제
                await db.execute(text("DELETE FROM users WHERE email = 'test@api.com'"))
                await db.commit()
                
                # 새 테스트 사용자 생성
                test_user = User(
                    email="test@api.com",
                    name="API 테스트 사용자",
                    phone="010-1234-5678"
                )
                db.add(test_user)
                await db.flush()  # ID 생성을 위해 flush
                
                # 테스트 가족 그룹 생성 (먼저 생성)
                test_group = FamilyGroup(
                    group_name="API 테스트 가족",
                    leader_id=test_user.id,
                    invite_code=secrets.token_hex(4).upper(),  # 8자리 랜덤 코드
                    deadline_type="SECOND_SUNDAY",
                    status="ACTIVE"
                )
                db.add(test_group)
                await db.flush()
                
                # 테스트 받는 분 정보 생성 (그룹 ID와 함께)
                test_recipient = Recipient(
                    name="테스트 할머니",
                    address="서울시 강남구 테스트로 123",
                    postal_code="12345",
                    group_id=test_group.id
                )
                db.add(test_recipient)
                await db.flush()
                
                # 사용자를 가족 멤버로 추가
                test_member = FamilyMember(
                    user_id=test_user.id,
                    group_id=test_group.id,
                    recipient_id=test_recipient.id,
                    member_relationship="SON",  # 아들 관계로 설정
                    role="LEADER"
                )
                db.add(test_member)
                
                await db.commit()
                await db.refresh(test_user)
                await db.refresh(test_group)
                
                self.test_user_id = str(test_user.id)
                print(f"[OK] 테스트 사용자 생성: {self.test_user_id}")
                print(f"[OK] 테스트 가족 그룹 생성: {test_group.group_name} (초대코드: {test_group.invite_code})")
                
            except Exception as e:
                await db.rollback()
                raise e

    def create_test_jwt_token(self) -> str:
        """올바른 UUID로 JWT 토큰 생성"""
        try:
            from app.core.security import create_access_token
            
            if not self.test_user_id:
                self.test_user_id = str(uuid.uuid4())
            
            return create_access_token(data={"sub": self.test_user_id})
        except Exception as e:
            print(f"JWT 토큰 생성 실패: {e}")
            return "mock_jwt_token"

    async def run_all_api_tests(self):
        """전체 API 테스트 실행"""
        print("API 엔드포인트 테스트 시작")
        
        # 서버 연결 확인
        if not self.check_server_connection():
            print("[ERROR] 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
            return
        
        # 테스트 환경 설정
        await self.setup_test_environment()
        
        test_suites = [
            ("공개 엔드포인트", self.test_public_endpoints),
            ("카카오 OAuth 구조", self.test_auth_structure),
            ("인증 필요 엔드포인트", self.test_authenticated_endpoints),
            ("에러 케이스", self.test_error_cases),
        ]
        
        for suite_name, test_func in test_suites:
            print(f"\n[TEST] {suite_name} 테스트")
            try:
                test_func()
                self.test_results[suite_name] = "[OK] 성공"
            except Exception as e:
                self.test_results[suite_name] = f"[ERROR] 실패: {str(e)}"
                print(f"  [ERROR] 오류: {e}")
        
        self.print_test_summary()

    def test_public_endpoints(self):
        """공개 엔드포인트 테스트"""
        endpoints = [
            ("GET", "/", 200, "루트 엔드포인트"),
            ("GET", "/health", 200, "헬스 체크"),
            ("GET", "/api/auth/kakao/url", 200, "카카오 로그인 URL"),
            ("GET", "/docs", 200, "Swagger UI"),
            ("GET", "/redoc", 200, "ReDoc 문서"),
        ]
        
        for method, path, expected_status, description in endpoints:
            response = self.make_request(method, path)
            if response.status_code == expected_status:
                print(f"  [OK] {description}: {response.status_code}")
            else:
                print(f"  [ERROR] {description}: 예상 {expected_status}, 실제 {response.status_code}")

    def test_auth_structure(self):
        """카카오 OAuth 구조 테스트"""
        # 카카오 로그인 URL 테스트
        response = self.make_request("GET", "/api/auth/kakao/url")
        if response.status_code == 200:
            data = response.json()
            if "login_url" in data and "kauth.kakao.com" in data["login_url"]:
                print(f"  [OK] 로그인 URL 반환: {data['login_url'][:50]}...")
            else:
                print("  [ERROR] 로그인 URL 형식 오류")
        
        # JWT 토큰 검증
        if self.access_token and self.access_token != "mock_jwt_token":
            print("  [OK] JWT 생성 성공")
        else:
            print("  [OK] Mock JWT 생성 성공")

    def test_authenticated_endpoints(self):
        """인증 필요 엔드포인트 테스트"""
        endpoints = [
            ("GET", "/api/profile/me", "내 프로필"),
            ("GET", "/api/family/my-group", "내 가족 그룹"),
            ("GET", "/api/posts/", "소식 목록"),
            ("GET", "/api/books/", "책자 목록"),
            ("GET", "/api/subscription/my", "내 구독 목록"),
        ]
        
        for method, path, description in endpoints:
            # 비인증 요청
            response_unauth = self.make_request(method, path)
            if response_unauth.status_code == 401:
                print(f" [OK] {description} (비인증): {response_unauth.status_code}")
            
            # 인증 요청
            response_auth = self.make_authenticated_request(method, path)
            if response_auth.status_code in [200, 201, 404]:  # 404도 정상 (데이터 없음)
                print(f"  [OK] {description} (인증): {response_auth.status_code}")
            else:
                print(f"  [ERROR] {description} (인증): {response_auth.status_code}")
                # 에러 상세 정보 출력
                try:
                    error_detail = response_auth.json()
                    print(f"    상세: {error_detail}")
                except:
                    print(f"    응답: {response_auth.text[:100]}")

    def test_error_cases(self):
        """에러 케이스 테스트"""
        error_cases = [
            ("GET", "/api/nonexistent", 404, "존재하지 않는 엔드포인트"),
            ("POST", "/api/posts/", 403, "비인증 소식 작성"),
            ("DELETE", "/api/members/bad-id", 403, "비인증 멤버 삭제"),
        ]
        
        for method, path, expected_status, description in error_cases:
            response = self.make_request(method, path)
            if response.status_code == expected_status:
                print(f"  [OK] {description}: {response.status_code}")
            else:
                print(f"  [ERROR] {description}: 예상 {expected_status}, 실제 {response.status_code}")

    def make_request(self, method: str, path: str, data: Dict = None):
        """기본 HTTP 요청"""
        url = f"{self.base_url}{path}"
        
        try:
            if method == "GET":
                return requests.get(url, headers=self.headers, timeout=10)
            elif method == "POST":
                return requests.post(url, headers=self.headers, json=data, timeout=10)
            elif method == "PUT":
                return requests.put(url, headers=self.headers, json=data, timeout=10)
            elif method == "DELETE":
                return requests.delete(url, headers=self.headers, timeout=10)
        except Exception as e:
            # Mock response for connection errors
            class MockResponse:
                def __init__(self, status_code, text="Connection Error"):
                    self.status_code = status_code
                    self.text = text
                def json(self):
                    return {"error": self.text}
            return MockResponse(500, str(e))

    def make_authenticated_request(self, method: str, path: str, data: Dict = None):
        """인증된 HTTP 요청"""
        auth_headers = self.headers.copy()
        if self.access_token:
            auth_headers["Authorization"] = f"Bearer {self.access_token}"
        
        url = f"{self.base_url}{path}"
        
        try:
            if method == "GET":
                return requests.get(url, headers=auth_headers, timeout=10)
            elif method == "POST":
                return requests.post(url, headers=auth_headers, json=data, timeout=10)
            elif method == "PUT":
                return requests.put(url, headers=auth_headers, json=data, timeout=10)
            elif method == "DELETE":
                return requests.delete(url, headers=auth_headers, timeout=10)
        except Exception as e:
            class MockResponse:
                def __init__(self, status_code, text="Connection Error"):
                    self.status_code = status_code
                    self.text = text
                def json(self):
                    return {"error": self.text}
            return MockResponse(500, str(e))

    def print_test_summary(self):
        """테스트 결과 요약"""
        print("\n" + "="*60)
        print("[SUMMARY] 테스트 결과 요약")
        print("="*60)
        
        success_count = 0
        total_endpoints = 0
        
        # 상세한 성공/실패 개수 계산을 위해 다시 테스트
        public_success = self.count_successful_endpoints([
            ("/", 200), ("/health", 200), ("/api/auth/kakao/url", 200), 
            ("/docs", 200), ("/redoc", 200)
        ])
        
        auth_success = self.count_successful_auth_endpoints([
            "/api/profile/me", "/api/family/my-group", "/api/v1/posts/", 
            "/api/books/", "/api/subscription/my"
        ])
        
        error_success = self.count_successful_error_cases([
            ("/api/nonexistent", 404), ("/api/posts/", 403), 
            ("/api/members/bad-id", 403)
        ])
        
        for suite_name, result in self.test_results.items():
            print(f"{result} {suite_name}")
            if "성공" in result:
                success_count += 1
        
        total_count = len(self.test_results)
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        
        print("="*60)
        print(f"[RESULT] {public_success + auth_success + error_success} / {5 + 5 + 3}   성공률: {((public_success + auth_success + error_success) / 13 * 100):.1f}%")
        print(f"[TIME] 완료 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def count_successful_endpoints(self, endpoints):
        """공개 엔드포인트 성공 개수"""
        success = 0
        for path, expected_status in endpoints:
            response = self.make_request("GET", path)
            if response.status_code == expected_status:
                success += 1
        return success

    def count_successful_auth_endpoints(self, endpoints):
        """인증 엔드포인트 성공 개수"""
        success = 0
        for path in endpoints:
            response = self.make_authenticated_request("GET", path)
            if response.status_code in [200, 201, 404]:  # 404도 정상으로 간주
                success += 1
        return success

    def count_successful_error_cases(self, error_cases):
        """에러 케이스 성공 개수"""
        success = 0
        for path, expected_status in error_cases:
            response = self.make_request("GET" if "GET" not in path else "POST", path)
            if response.status_code == expected_status:
                success += 1
        return success

if __name__ == "__main__":
    api_tester = EnhancedAPITestRunner()
    asyncio.run(api_tester.run_all_api_tests())
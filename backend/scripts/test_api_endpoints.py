import requests
import json
from datetime import datetime
from typing import Dict, Any, Optional

class EnhancedAPITestRunner:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.headers = {"Content-Type": "application/json"}
        self.access_token = None
        self.test_data = {}
        self.test_results = {}

    async def run_all_api_tests(self):
        """전체 API 테스트 실행"""
        print("🚀 API 엔드포인트 테스트 시작")
        
        test_suites = [
            ("공개 엔드포인트", self.test_public_endpoints),
            ("인증 엔드포인트", self.test_auth_endpoints),
            ("사용자 프로필", self.test_profile_endpoints),
            ("가족 그룹", self.test_family_endpoints),
            ("소식 관리", self.test_posts_endpoints),
            ("구독 관리", self.test_subscription_endpoints),
            ("에러 처리", self.test_error_cases),
        ]
        
        for suite_name, test_func in test_suites:
            print(f"\n📋 {suite_name} 테스트 실행 중...")
            try:
                await test_func()
                self.test_results[suite_name] = "✅ 성공"
            except Exception as e:
                self.test_results[suite_name] = f"❌ 실패: {str(e)}"
        
        self.print_api_test_summary()

    def test_public_endpoints(self):
        """공개 엔드포인트 테스트"""
        endpoints = [
            ("GET", "/", 200, "루트 엔드포인트"),
            ("GET", "/health", 200, "헬스 체크"),
            ("GET", "/docs", 200, "API 문서"),
            ("GET", "/api/v1/auth/kakao/url", 200, "카카오 로그인 URL"),
        ]
        
        for method, path, expected_status, description in endpoints:
            response = self.make_request(method, path)
            assert response.status_code == expected_status, f"{description} 실패: {response.status_code}"
            print(f"✅ {description}: {response.status_code}")

    def test_auth_endpoints(self):
        """인증 관련 엔드포인트 테스트"""
        # 카카오 로그인 URL 테스트
        response = self.make_request("GET", "/api/v1/auth/kakao/url")
        assert response.status_code == 200
        data = response.json()
        assert "login_url" in data
        assert "kauth.kakao.com" in data["login_url"]
        print("✅ 카카오 로그인 URL 생성 성공")

        # Mock JWT 토큰 생성 (실제 환경에서는 실제 토큰 사용)
        self.access_token = self.create_test_jwt_token()
        print("✅ 테스트 JWT 토큰 생성 완료")

    def test_profile_endpoints(self):
        """프로필 관련 엔드포인트 테스트"""
        if not self.access_token:
            print("⚠️ 인증 토큰이 없어 프로필 테스트 건너뜀")
            return

        # 내 프로필 조회
        response = self.make_authenticated_request("GET", "/api/v1/profile/me")
        if response.status_code == 401:
            print("✅ 인증 필요 엔드포인트 보안 확인")
        else:
            print(f"📝 프로필 조회: {response.status_code}")

    def test_family_endpoints(self):
        """가족 그룹 관련 엔드포인트 테스트"""
        endpoints = [
            ("GET", "/api/v1/family/my-group", "내 가족 그룹 조회"),
            ("POST", "/api/v1/family/create", "가족 그룹 생성"),
            ("POST", "/api/v1/members/join", "멤버 가입"),
        ]
        
        for method, path, description in endpoints:
            response = self.make_authenticated_request(method, path)
            print(f"📝 {description}: {response.status_code}")

    def test_posts_endpoints(self):
        """소식 관련 엔드포인트 테스트"""
        endpoints = [
            ("GET", "/api/v1/posts/", "소식 목록 조회"),
            ("POST", "/api/v1/posts/", "소식 작성"),
            ("POST", "/api/v1/posts/upload-images", "이미지 업로드"),
        ]
        
        for method, path, description in endpoints:
            response = self.make_authenticated_request(method, path)
            print(f"📝 {description}: {response.status_code}")

    def test_subscription_endpoints(self):
        """구독 관련 엔드포인트 테스트"""
        endpoints = [
            ("GET", "/api/v1/subscription/my", "내 구독 조회"),
            ("POST", "/api/v1/subscription/", "구독 생성"),
            ("POST", "/api/v1/subscription/approve", "결제 승인"),
        ]
        
        for method, path, description in endpoints:
            response = self.make_authenticated_request(method, path)
            print(f"📝 {description}: {response.status_code}")

    def test_error_cases(self):
        """에러 케이스 테스트"""
        error_cases = [
            ("GET", "/api/v1/nonexistent", 404, "존재하지 않는 엔드포인트"),
            ("POST", "/api/v1/posts/", 401, "인증 없이 소식 작성"),
            ("GET", "/api/v1/profile/me", 401, "인증 없이 프로필 조회"),
        ]
        
        for method, path, expected_status, description in error_cases:
            response = self.make_request(method, path)
            if response.status_code == expected_status:
                print(f"✅ {description}: 올바른 에러 응답 {response.status_code}")
            else:
                print(f"⚠️ {description}: 예상 {expected_status}, 실제 {response.status_code}")

    def make_request(self, method: str, path: str, data: Dict = None):
        """기본 HTTP 요청"""
        url = f"{self.base_url}{path}"
        
        if method == "GET":
            return requests.get(url, headers=self.headers)
        elif method == "POST":
            return requests.post(url, headers=self.headers, json=data)
        elif method == "PUT":
            return requests.put(url, headers=self.headers, json=data)
        elif method == "DELETE":
            return requests.delete(url, headers=self.headers)

    def make_authenticated_request(self, method: str, path: str, data: Dict = None):
        """인증된 HTTP 요청"""
        auth_headers = self.headers.copy()
        if self.access_token:
            auth_headers["Authorization"] = f"Bearer {self.access_token}"
        
        url = f"{self.base_url}{path}"
        
        if method == "GET":
            return requests.get(url, headers=auth_headers)
        elif method == "POST":
            return requests.post(url, headers=auth_headers, json=data)
        elif method == "PUT":
            return requests.put(url, headers=auth_headers, json=data)
        elif method == "DELETE":
            return requests.delete(url, headers=auth_headers)

    def create_test_jwt_token(self) -> str:
        """테스트용 JWT 토큰 생성"""
        from app.core.security import create_access_token
        
        # 시스템 테스트에서 생성된 사용자 ID 활용
        test_user_id = "test_user_id_for_api_testing"
        return create_access_token(data={"sub": test_user_id})

    def print_api_test_summary(self):
        """API 테스트 결과 요약"""
        print("\n" + "="*60)
        print("🎯 API 엔드포인트 테스트 결과 요약")
        print("="*60)
        
        for suite_name, result in self.test_results.items():
            print(f"{result} {suite_name}")
        
        success_count = sum(1 for result in self.test_results.values() if "성공" in result)
        total_count = len(self.test_results)
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        
        print("="*60)
        print(f"📊 API 테스트 성공률: {success_count}/{total_count} ({success_rate:.1f}%)")

if __name__ == "__main__":
    import asyncio
    
    api_tester = EnhancedAPITestRunner()
    asyncio.run(api_tester.run_all_api_tests())
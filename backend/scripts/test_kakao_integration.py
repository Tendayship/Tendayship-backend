#!/usr/bin/env python3
"""
실제 카카오 계정 로그인 통합 테스트 스크립트

이 스크립트는 실제 카카오 계정을 사용하여 다음 기능들을 테스트합니다:
1. 카카오 OAuth 로그인
2. 계정 생성 및 검증
3. 프로필 관리
4. 가족 그룹 생성
5. API 엔드포인트 테스트

사용법:
1. .env 파일에 카카오 OAuth 설정 추가
2. 카카오 개발자 콘솔에서 앱 설정
3. 스크립트 실행
"""

import asyncio
import requests
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Add the parent directory to Python path to enable app imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class KakaoIntegrationTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.headers = {"Content-Type": "application/json"}
        self.access_token = None
        self.user_id = None
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
    
    def get_kakao_login_url(self):
        """카카오 로그인 URL 획득"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/auth/kakao/url")
            if response.status_code == 200:
                data = response.json()
                login_url = data.get("login_url")
                print(f"[OK] 카카오 로그인 URL 생성: {login_url[:50]}...")
                return login_url
            else:
                print(f"[ERROR] 카카오 로그인 URL 생성 실패: {response.status_code}")
                return None
        except Exception as e:
            print(f"[ERROR] 카카오 로그인 URL 요청 실패: {e}")
            return None
    
    def simulate_kakao_callback(self, auth_code: str):
        """카카오 OAuth 콜백 시뮬레이션"""
        try:
            # 실제로는 브라우저에서 카카오 로그인 후 리다이렉트되는 과정
            # 여기서는 API 엔드포인트를 직접 호출하여 테스트
            response = requests.post(
                f"{self.base_url}/api/v1/auth/kakao",
                json={"code": auth_code},
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                self.user_id = data.get("user", {}).get("id")
                is_new_user = data.get("is_new_user", False)
                
                print(f"[OK] 카카오 로그인 성공")
                print(f"  - 사용자 ID: {self.user_id}")
                print(f"  - 새 사용자: {is_new_user}")
                print(f"  - 액세스 토큰: {self.access_token[:20]}...")
                
                # 헤더에 토큰 추가
                self.headers["Authorization"] = f"Bearer {self.access_token}"
                return True
            else:
                print(f"[ERROR] 카카오 로그인 실패: {response.status_code}")
                print(f"  - 응답: {response.text}")
                return False
                
        except Exception as e:
            print(f"[ERROR] 카카오 로그인 처리 실패: {e}")
            return False
    
    def test_user_profile(self):
        """사용자 프로필 테스트"""
        print("\n[TEST] 사용자 프로필 테스트")
        
        # 1. 현재 사용자 정보 조회
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/auth/me",
                headers=self.headers
            )
            
            if response.status_code == 200:
                user_data = response.json()
                print(f"  [OK] 사용자 정보 조회: {user_data.get('name')} ({user_data.get('email')})")
                
                # 2. 프로필 업데이트
                update_data = {
                    "name": f"테스트 사용자 {datetime.now().strftime('%H%M')}",
                    "phone": "010-1234-5678"
                }
                
                update_response = requests.put(
                    f"{self.base_url}/api/v1/auth/profile",
                    json=update_data,
                    headers=self.headers
                )
                
                if update_response.status_code == 200:
                    print(f"  [OK] 프로필 업데이트 성공")
                    self.test_results["프로필 관리"] = "[OK] 성공"
                else:
                    print(f"  [ERROR] 프로필 업데이트 실패: {update_response.status_code}")
                    self.test_results["프로필 관리"] = f"[ERROR] 실패: {update_response.status_code}"
                    
            else:
                print(f"  [ERROR] 사용자 정보 조회 실패: {response.status_code}")
                self.test_results["프로필 관리"] = f"[ERROR] 실패: {response.status_code}"
                
        except Exception as e:
            print(f"  [ERROR] 프로필 테스트 오류: {e}")
            self.test_results["프로필 관리"] = f"[ERROR] 실패: {str(e)}"
    
    def test_family_group_setup(self):
        """가족 그룹 설정 테스트"""
        print("\n[TEST] 가족 그룹 설정 테스트")
        
        try:
            # 가족 그룹 초기 설정
            setup_data = {
                "group_name": f"테스트 가족 {datetime.now().strftime('%H%M')}",
                "deadline_type": "SECOND_SUNDAY",
                "leader_relationship": "SON",
                "recipient_name": "테스트 할머니",
                "recipient_address": "서울시 강남구 테스트로 123, 456동 789호",
                "recipient_postal_code": "12345",
                "recipient_phone": "010-9876-5432"
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/family/setup",
                json=setup_data,
                headers=self.headers
            )
            
            if response.status_code == 200:
                result = response.json()
                group_info = result.get("group", {})
                recipient_info = result.get("recipient", {})
                
                print(f"  [OK] 가족 그룹 생성 성공")
                print(f"    - 그룹명: {group_info.get('group_name')}")
                print(f"    - 초대코드: {group_info.get('invite_code')}")
                print(f"    - 받는 분: {recipient_info.get('name')}")
                print(f"    - 주소: {recipient_info.get('address')}")
                
                self.test_results["가족 그룹 설정"] = "[OK] 성공"
                
            else:
                print(f"  [ERROR] 가족 그룹 생성 실패: {response.status_code}")
                print(f"    - 응답: {response.text}")
                self.test_results["가족 그룹 설정"] = f"[ERROR] 실패: {response.status_code}"
                
        except Exception as e:
            print(f"  [ERROR] 가족 그룹 설정 테스트 오류: {e}")
            self.test_results["가족 그룹 설정"] = f"[ERROR] 실패: {str(e)}"
    
    def test_family_group_management(self):
        """가족 그룹 관리 테스트"""
        print("\n[TEST] 가족 그룹 관리 테스트")
        
        try:
            # 내 가족 그룹 조회
            response = requests.get(
                f"{self.base_url}/api/v1/family/my-group",
                headers=self.headers
            )
            
            if response.status_code == 200:
                group_data = response.json()
                print(f"  [OK] 가족 그룹 조회 성공")
                print(f"    - 그룹명: {group_data.get('group_name')}")
                print(f"    - 상태: {group_data.get('status')}")
                print(f"    - 마감일 타입: {group_data.get('deadline_type')}")
                
                self.test_results["가족 그룹 관리"] = "[OK] 성공"
                
            else:
                print(f"  [ERROR] 가족 그룹 조회 실패: {response.status_code}")
                self.test_results["가족 그룹 관리"] = f"[ERROR] 실패: {response.status_code}"
                
        except Exception as e:
            print(f"  [ERROR] 가족 그룹 관리 테스트 오류: {e}")
            self.test_results["가족 그룹 관리"] = f"[ERROR] 실패: {str(e)}"
    
    def test_token_verification(self):
        """토큰 검증 테스트"""
        print("\n[TEST] 토큰 검증 테스트")
        
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/auth/verify",
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"  [OK] 토큰 검증 성공")
                print(f"    - 유효성: {data.get('valid')}")
                print(f"    - 사용자: {data.get('name')} ({data.get('email')})")
                
                self.test_results["토큰 검증"] = "[OK] 성공"
                
            else:
                print(f"  [ERROR] 토큰 검증 실패: {response.status_code}")
                self.test_results["토큰 검증"] = f"[ERROR] 실패: {response.status_code}"
                
        except Exception as e:
            print(f"  [ERROR] 토큰 검증 테스트 오류: {e}")
            self.test_results["토큰 검증"] = f"[ERROR] 실패: {str(e)}"
    
    async def run_integration_test(self):
        """통합 테스트 실행"""
        print("=" * 60)
        print("카카오 계정 로그인 통합 테스트 시작")
        print("=" * 60)
        
        # 1. 서버 연결 확인
        if not self.check_server_connection():
            print("[ERROR] 서버에 연결할 수 없습니다.")
            return
        
        # 2. 카카오 로그인 URL 생성
        login_url = self.get_kakao_login_url()
        if not login_url:
            print("[ERROR] 카카오 로그인 URL을 생성할 수 없습니다.")
            return
        
        print(f"\n[INFO] 다음 URL에서 카카오 로그인을 진행하세요:")
        print(f"  {login_url}")
        print(f"\n[INFO] 로그인 후 받은 인가 코드를 입력하세요:")
        
        # 3. 사용자로부터 인가 코드 입력 받기
        auth_code = input("인가 코드: ").strip()
        
        if not auth_code:
            print("[ERROR] 인가 코드가 입력되지 않았습니다.")
            return
        
        # 4. 카카오 로그인 처리
        if not self.simulate_kakao_callback(auth_code):
            print("[ERROR] 카카오 로그인에 실패했습니다.")
            return
        
        # 5. 각종 기능 테스트
        self.test_user_profile()
        self.test_family_group_setup()
        self.test_family_group_management()
        self.test_token_verification()
        
        # 6. 테스트 결과 요약
        self.print_test_summary()
    
    def print_test_summary(self):
        """테스트 결과 요약 출력"""
        print("\n" + "=" * 60)
        print("테스트 결과 요약")
        print("=" * 60)
        
        success_count = 0
        total_count = len(self.test_results)
        
        for test_name, result in self.test_results.items():
            print(f"{test_name}: {result}")
            if "[OK]" in result:
                success_count += 1
        
        print("-" * 60)
        print(f"성공: {success_count}/{total_count}")
        print(f"성공률: {(success_count/total_count*100):.1f}%")
        print(f"완료 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)


def main():
    """메인 함수"""
    print("카카오 계정 로그인 통합 테스트")
    print("이 테스트는 실제 카카오 계정이 필요합니다.")
    print("계속하시겠습니까? (y/N): ", end="")
    
    confirm = input().strip().lower()
    if confirm not in ['y', 'yes']:
        print("테스트를 취소합니다.")
        return
    
    tester = KakaoIntegrationTester()
    asyncio.run(tester.run_integration_test())


if __name__ == "__main__":
    main()

import asyncio
import httpx
from datetime import datetime
from typing import Dict, Any
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class PaymentIntegrationTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_prefix = "/api"
        self.headers = {"Content-Type": "application/json"}
        self.access_token = None
        self.test_user_id = None  # 추가
        self.test_results = {}
    
    async def setup_test_user_and_group(self):
        """테스트용 사용자 및 가족 그룹 생성 (실제 DB에 저장)"""
        try:
            # 실제 테스트 사용자 생성
            await self.create_real_test_user()
            print(f"✅ 실제 테스트 사용자 생성 완료: {self.test_user_id[:8]}...")
        except Exception as e:
            print(f"❌ 테스트 사용자 생성 실패: {e}")
            raise

        # JWT 토큰 생성 (실제 사용자 ID 사용)
        from app.core.security import create_access_token
        self.access_token = create_access_token(data={"sub": self.test_user_id})
        self.headers["Authorization"] = f"Bearer {self.access_token}"
        
    async def create_real_test_user(self):
        """실제 테스트 사용자 및 가족 그룹 생성"""
        from app.database.session import AsyncSessionLocal
        from app.models.user import User
        from app.models.family import FamilyGroup, FamilyMember
        from app.models.recipient import Recipient
        from sqlalchemy import text
        import secrets

        async with AsyncSessionLocal() as db:
            try:
                # 기존 테스트 데이터 정리
                await db.execute(text("DELETE FROM family_members WHERE user_id IN (SELECT id FROM users WHERE email = 'payment_test@api.com')"))
                await db.execute(text("DELETE FROM recipients WHERE group_id IN (SELECT id FROM family_groups WHERE group_name = '결제 테스트 가족')"))
                await db.execute(text("DELETE FROM family_groups WHERE group_name = '결제 테스트 가족'"))
                await db.execute(text("DELETE FROM users WHERE email = 'payment_test@api.com'"))
                await db.commit()

                # 새 테스트 사용자 생성
                test_user = User(
                    email="payment_test@api.com",
                    name="결제 테스트 사용자",
                    phone="010-9999-8888"
                )
                db.add(test_user)
                await db.flush()  # ID 생성을 위한 flush
                
                # 테스트 가족 그룹 생성
                test_group = FamilyGroup(
                    group_name="결제 테스트 가족",
                    leader_id=test_user.id,  # 중요: leader_id 설정
                    invite_code=secrets.token_hex(4).upper(),
                    deadline_type="SECOND_SUNDAY",
                    status="ACTIVE"
                )
                db.add(test_group)
                await db.flush()

                # 테스트 받는 분 정보 생성
                test_recipient = Recipient(
                    name="테스트 할머니",
                    address="서울시 강남구 테스트로 123",
                    postal_code="12345",
                    group_id=test_group.id
                )
                db.add(test_recipient)
                await db.flush()

                # 사용자를 가족 멤버로 추가 (리더 권한)
                test_member = FamilyMember(
                    user_id=test_user.id,
                    group_id=test_group.id,
                    recipient_id=test_recipient.id,
                    member_relationship="SON",
                    role="LEADER"  # 명시적으로 LEADER 설정
                )
                db.add(test_member)
                
                # 중요: 커밋 전에 모든 객체를 확실히 저장
                await db.commit()
                
                # 저장 후 새로고침하여 실제 DB 상태 확인
                await db.refresh(test_user)
                await db.refresh(test_group) 
                await db.refresh(test_member)
                
                self.test_user_id = str(test_user.id)
                
                # 디버깅: 실제 저장된 값 확인
                print(f"✅ 사용자 생성: {test_user.email} (ID: {test_user.id})")
                print(f"✅ 그룹 생성: {test_group.group_name} (리더: {test_group.leader_id})")
                print(f"✅ 멤버 생성: Role={test_member.role}, User={test_member.user_id}")
                
            except Exception as e:
                await db.rollback()
                print(f"❌ 데이터베이스 오류: {e}")
                raise e
        
    async def test_payment_ready(self) -> Dict[str, Any]:
        """결제 준비 테스트"""
        print("\n[TEST] 결제 준비 API 테스트")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}{self.api_prefix}/subscription/payment/ready",
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 결제 준비 성공")
                print(f"  - TID: {data['tid']}")
                print(f"  - PC URL: {data['next_redirect_pc_url'][:50]}...")
                print(f"  - Mobile URL: {data['next_redirect_mobile_url'][:50]}...")
                
                self.test_results["payment_ready"] = "성공"
                return data
            else:
                print(f"❌ 결제 준비 실패: {response.status_code}")
                print(f"  - 응답: {response.text}")
                self.test_results["payment_ready"] = f"실패: {response.status_code}"
                return {}
    
    async def test_payment_approve(self, tid: str, pg_token: str = "test_token"):
        """결제 승인 테스트"""
        print("\n[TEST] 결제 승인 API 테스트")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}{self.api_prefix}/subscription/approve",
                params={"tid": tid, "pg_token": pg_token},
                headers=self.headers,
                follow_redirects=False
            )
            
            if response.status_code in [302, 307]:  # 리다이렉트
                print(f"✅ 결제 승인 처리 (리다이렉트)")
                print(f"  - Location: {response.headers.get('location')}")
                self.test_results["payment_approve"] = "성공"
            else:
                print(f"❌ 결제 승인 실패: {response.status_code}")
                self.test_results["payment_approve"] = f"실패: {response.status_code}"
    
    async def test_subscription_list(self):
        """구독 목록 조회 테스트"""
        print("\n[TEST] 구독 목록 조회")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}{self.api_prefix}/subscription/my",
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 구독 목록 조회 성공: {len(data)}개")
                self.test_results["subscription_list"] = "성공"
            else:
                print(f"❌ 구독 목록 조회 실패: {response.status_code}")
                self.test_results["subscription_list"] = f"실패: {response.status_code}"
    
    async def run_all_tests(self):
        """전체 테스트 실행"""
        print("="*60)
        print("🧪 결제 시스템 통합 테스트 시작")
        print("="*60)
        
        # 1. 테스트 환경 설정
        await self.setup_test_user_and_group()
        
        # 2. 결제 준비
        payment_data = await self.test_payment_ready()
        
        # 3. 결제 승인 (실제로는 브라우저에서 결제 후)
        if payment_data.get("tid"):
            print("\n⚠️  브라우저에서 결제를 진행하세요:")
            print(f"URL: {payment_data['next_redirect_pc_url']}")
            print("\n결제 완료 후 받은 pg_token을 입력하세요:")
            
        # 4. 구독 목록 확인
        await self.test_subscription_list()
        
        # 5. 결과 요약
        self.print_summary()
    
    def print_summary(self):
        """테스트 결과 요약"""
        print("\n" + "="*60)
        print("📊 테스트 결과 요약")
        print("="*60)
        
        success_count = sum(1 for r in self.test_results.values() if "성공" in r)
        total_count = len(self.test_results)
        
        for test_name, result in self.test_results.items():
            status = "✅" if "성공" in result else "❌"
            print(f"{status} {test_name}: {result}")
        
        print("-"*60)
        print(f"성공: {success_count}/{total_count}")
        print(f"성공률: {(success_count/total_count*100):.1f}%")
        print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 실행
async def main():
    tester = PaymentIntegrationTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_profile_endpoint():
    """직접 프로필 엔드포인트 로직 테스트"""
    try:
        from app.database.session import AsyncSessionLocal
        from app.models.user import User
        from app.crud.user_crud import user_crud
        from app.schemas.user import UserResponse
        from app.core.security import create_access_token, verify_token
        
        # 테스트 사용자 ID (최신 테스트에서 생성된 ID)
        test_user_id = "9ce3f993-9cf8-4efa-a81c-c4bb0d9e8cfc"
        
        # JWT 토큰 생성
        token = create_access_token(data={"sub": test_user_id})
        print(f"[OK] JWT 토큰 생성: {token[:50]}...")
        
        # 토큰 검증
        payload = verify_token(token)
        print(f"[OK] 토큰 검증 성공: {payload}")
        
        # 데이터베이스에서 사용자 조회
        async with AsyncSessionLocal() as db:
            user = await user_crud.get(db, id=test_user_id)
            if user:
                print(f"[OK] 사용자 조회 성공: {user.email}")
                print(f"   - ID: {user.id}")
                print(f"   - Name: {user.name}")
                print(f"   - Created: {user.created_at}")
                
                # UserResponse 스키마 직렬화 테스트
                try:
                    user_response = UserResponse.from_orm(user)
                    print(f"[OK] UserResponse 직렬화 성공")
                    print(f"   - Response ID: {user_response.id}")
                    print(f"   - Response Name: {user_response.name}")
                    return True
                except Exception as e:
                    print(f"[ERROR] UserResponse 직렬화 실패: {e}")
                    print(f"   - 에러 타입: {type(e)}")
                    import traceback
                    traceback.print_exc()
                    return False
            else:
                print(f"[ERROR] 사용자를 찾을 수 없음: {test_user_id}")
                return False
                
    except Exception as e:
        print(f"[ERROR] 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_profile_endpoint())
    print(f"\n{'='*50}")
    print(f"테스트 결과: {'성공' if success else '실패'}")
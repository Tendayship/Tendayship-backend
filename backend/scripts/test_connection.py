import asyncio
from app.database.session import check_db_connection, init_db
from app.core.config import print_settings

async def test_database():
    print("데이터베이스 연결 테스트 시작...")
    
    # 설정 확인
    print_settings()
    
    # 연결 테스트
    if await check_db_connection():
        print("✅ 데이터베이스 연결 성공!")
        
        # 테이블 생성
        await init_db()
        print("✅ 테이블 생성 완료!")
    else:
        print("❌ 데이터베이스 연결 실패. 설정을 확인해주세요.")

if __name__ == "__main__":
    asyncio.run(test_database())
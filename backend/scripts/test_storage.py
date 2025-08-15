import asyncio
from app.utils.azure_storage import storage_service

async def test_storage():
    print("Blob Storage 연결 테스트 시작...")
    
    # 테스트 데이터
    test_data = b"Hello, Azure Blob Storage!"
    test_path = "test/connection_test.txt"
    
    try:
        # 업로드 테스트
        blob_client = storage_service.blob_service_client.get_blob_client(
            container=storage_service.container_name,
            blob=test_path
        )
        blob_client.upload_blob(test_data, overwrite=True)
        print("✅ 업로드 성공!")
        
        # 다운로드 테스트
        downloaded = await storage_service.download_blob(test_path)
        assert downloaded == test_data
        print("✅ 다운로드 성공!")
        
        # 정리
        await storage_service.delete_blob(test_path)
        print("✅ 삭제 성공!")
        
    except Exception as e:
        print(f"❌ Storage 테스트 실패: {e}")

if __name__ == "__main__":
    asyncio.run(test_storage())
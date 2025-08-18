from typing import List
from fastapi import UploadFile, HTTPException
from ..utils.azure_storage import get_storage_service
from ..core.config import settings

class PostStorageService:
    """소식 관련 파일 저장 서비스"""

    def __init__(self):
        self.max_file_size = getattr(settings, 'MAX_UPLOAD_SIZE', 10 * 1024 * 1024)
        self.allowed_types = ["image/jpeg", "image/png", "image/webp", "image/jpg"]

    async def upload_post_images(
        self,
        group_id: str,
        issue_id: str,
        post_id: str,
        files: List[UploadFile]
    ) -> tuple[List[str], List[str]]:
        """소식 이미지들을 Azure Blob Storage에 업로드"""
        max_images = getattr(settings, 'MAX_IMAGES_PER_POST', 4)
        
        if len(files) > max_images:
            raise HTTPException(
                status_code=400,
                detail=f"최대 {max_images}개의 이미지만 업로드 가능합니다"
            )

        uploaded_urls = []
        blob_keys = []
        
        for i, file in enumerate(files):
            # 파일 검증
            await self._validate_image_file(file)
            
            # Azure Blob Storage에 업로드
            try:
                storage_service = get_storage_service()
                image_url, blob_key = storage_service.upload_post_image(
                    group_id=group_id,
                    issue_id=issue_id,
                    post_id=post_id,
                    file=file,
                    image_index=i
                )
                uploaded_urls.append(image_url)
                blob_keys.append(blob_key)
                
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"이미지 업로드 실패: {str(e)}"
                )

        return uploaded_urls, blob_keys

    async def upload_profile_image(self, user_id: str, file: UploadFile) -> str:
        """프로필 이미지 업로드"""
        await self._validate_image_file(file)
        
        try:
            storage_service = get_storage_service()
            return storage_service.upload_profile_image(user_id, file)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"프로필 이미지 업로드 실패: {str(e)}"
            )

    async def _validate_image_file(self, file: UploadFile):
        """이미지 파일 유효성 검증"""
        if file.content_type not in self.allowed_types:
            raise HTTPException(
                status_code=400,
                detail="지원하지 않는 이미지 형식입니다. JPEG, PNG, WebP만 가능합니다."
            )

        # 파일 크기 확인
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)
        
        if size > self.max_file_size:
            raise HTTPException(
                status_code=400,
                detail=f"파일 크기가 너무 큽니다. 최대 {self.max_file_size//1024//1024}MB까지 가능합니다."
            )

# 싱글톤 인스턴스
post_storage_service = PostStorageService()

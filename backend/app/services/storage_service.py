from typing import List, Tuple
from fastapi import UploadFile, HTTPException
import uuid
from datetime import datetime

from ..utils.azure_storage import storage_service
from ..utils.image_utils import ImageProcessor
from ..core.config import settings

class PostStorageService:
    """소식 관련 파일 저장 서비스"""
    
    def __init__(self):
        self.image_processor = ImageProcessor()
        self.max_file_size = settings.MAX_UPLOAD_SIZE  # 10MB
        self.allowed_types = ["image/jpeg", "image/png", "image/webp"]
    
    async def upload_post_images(
        self,
        group_id: str,
        issue_id: str,
        post_id: str,
        files: List[UploadFile]
    ) -> Tuple[List[str], str]:
        """
        소식 이미지 업로드 및 콜라주 레이아웃 결정
        
        Returns:
            Tuple[List[str], str]: (업로드된 이미지 URLs, 레이아웃 타입)
        """
        if len(files) > settings.MAX_IMAGES_PER_POST:
            raise HTTPException(
                status_code=400,
                detail=f"최대 {settings.MAX_IMAGES_PER_POST}개의 이미지만 업로드 가능합니다"
            )
        
        uploaded_urls = []
        
        for i, file in enumerate(files):
            # 파일 검증
            await self._validate_image_file(file)
            
            # 이미지 처리 (리사이즈, 회전 보정)
            processed_image = await self.image_processor.process_for_collage(
                file, len(files), i
            )
            
            # Azure Blob Storage에 업로드
            blob_path = f"{group_id}/issues/{issue_id}/posts/{post_id}/image_{i+1}.jpg"
            image_url = await storage_service.upload_processed_image(
                blob_path, processed_image
            )
            
            uploaded_urls.append(image_url)
        
        # 콜라주 레이아웃 결정
        layout = self._determine_layout(len(files))
        
        return uploaded_urls, layout
    
    async def _validate_image_file(self, file: UploadFile):
        """이미지 파일 유효성 검증"""
        if file.content_type not in self.allowed_types:
            raise HTTPException(
                status_code=400,
                detail="지원하지 않는 이미지 형식입니다. JPEG, PNG, WebP만 가능합니다."
            )
        
        # 파일 크기 확인
        file.file.seek(0, 2)  # 파일 끝으로 이동
        size = file.file.tell()
        file.file.seek(0)  # 파일 시작으로 되돌리기
        
        if size > self.max_file_size:
            raise HTTPException(
                status_code=400,
                detail=f"파일 크기가 너무 큽니다. 최대 {self.max_file_size//1024//1024}MB까지 가능합니다."
            )
    
    def _determine_layout(self, image_count: int) -> str:
        """이미지 개수에 따른 콜라주 레이아웃 결정"""
        layout_map = {
            1: "1x1",
            2: "2x1", 
            3: "2x2_with_3",
            4: "2x2"
        }
        return layout_map.get(image_count, "1x1")

# 싱글톤 인스턴스
post_storage_service = PostStorageService()

import os
import io
import mimetypes
from typing import Optional, List, Tuple
from datetime import datetime, timedelta, timezone
from pathlib import Path
import logging

from azure.storage.blob import (
    BlobServiceClient,
    BlobClient,
    ContainerClient,
    generate_blob_sas,
    BlobSasPermissions,
    ContentSettings
)
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
from PIL import Image, ImageOps

from ..core.config import settings

logger = logging.getLogger(__name__)


class AzureStorageService:
    """
    Azure Blob Storage 서비스 클래스
    싱글톤 패턴으로 구현하여 연결을 재사용합니다.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """서비스 초기화"""
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(
                settings.AZURE_STORAGE_CONNECTION_STRING
            )
            self.container_name = settings.AZURE_STORAGE_CONTAINER_NAME
            self._ensure_container_exists()
            logger.info(f"Azure Storage Service initialized for container: {self.container_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Azure Storage Service: {e}")
            raise
    
    def _ensure_container_exists(self):
        """컨테이너가 없으면 생성합니다"""
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            container_client.get_container_properties()
        except ResourceNotFoundError:
            # 컨테이너가 없으면 생성
            container_client = self.blob_service_client.create_container(
                self.container_name,
                public_access=None  # 비공개 컨테이너
            )
            logger.info(f"Created container: {self.container_name}")
    
    def _build_blob_path(self, group_id: str, category: str, *parts: str) -> str:
        """
        Blob 경로를 생성합니다.
        예: group_id/category/subfolder/filename.ext
        """
        path_parts = [group_id, category] + list(parts)
        return "/".join(path_parts)
    
    def _get_safe_filename(self, filename: str) -> str:
        """
        파일명을 안전하게 변환합니다.
        특수문자 제거, 공백을 언더스코어로 변경
        """
        # 파일명과 확장자 분리
        name, ext = os.path.splitext(filename)
        # 안전한 문자만 남기기
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        # 타임스탬프 추가로 유니크성 보장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{safe_name}_{timestamp}{ext}"
    
    async def upload_profile_image(
        self,
        group_id: str,
        user_id: str,
        image_data: bytes,
        filename: str = "profile.jpg"
    ) -> str:
        """
        프로필 이미지를 업로드합니다.
        이미지는 자동으로 리사이즈되고 최적화됩니다.
        
        Args:
            group_id: 그룹 ID
            user_id: 사용자 ID  
            image_data: 이미지 바이너리 데이터
            filename: 파일명
            
        Returns:
            업로드된 이미지의 URL
        """
        try:
            # 이미지 처리 (리사이즈, 최적화)
            processed_image = self._process_profile_image(image_data)
            
            # Blob 경로 생성
            safe_filename = self._get_safe_filename(filename)
            blob_path = self._build_blob_path(group_id, "profiles", user_id, safe_filename)
            
            # 업로드
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            
            blob_client.upload_blob(
                processed_image,
                overwrite=True,
                content_settings=ContentSettings(
                    content_type="image/jpeg",
                    cache_control="max-age=604800"  # 7일 캐시
                )
            )
            
            # SAS URL 생성 (1년 유효)
            sas_url = self.generate_sas_url(blob_path, expiry_hours=8760)
            logger.info(f"Profile image uploaded: {blob_path}")
            return sas_url
            
        except Exception as e:
            logger.error(f"Failed to upload profile image: {e}")
            raise
    
    def _process_profile_image(self, image_data: bytes) -> bytes:
        """
        프로필 이미지를 처리합니다.
        - EXIF 회전 적용
        - 정사각형으로 크롭
        - 500x500으로 리사이즈
        - JPEG로 최적화
        """
        # 이미지 열기
        img = Image.open(io.BytesIO(image_data))
        
        # EXIF 회전 적용
        img = ImageOps.exif_transpose(img)
        
        # 정사각형으로 크롭 (중앙 기준)
        width, height = img.size
        size = min(width, height)
        left = (width - size) // 2
        top = (height - size) // 2
        right = left + size
        bottom = top + size
        img = img.crop((left, top, right, bottom))
        
        # 500x500으로 리사이즈
        img = img.resize((500, 500), Image.Resampling.LANCZOS)
        
        # RGB로 변환 (JPEG는 RGBA 지원 안함)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 바이트로 변환
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        return output.getvalue()
    
    async def upload_post_images(
        self,
        group_id: str,
        issue_id: str,
        post_id: str,
        images: List[Tuple[str, bytes]]
    ) -> List[str]:
        """
        게시글 이미지들을 업로드합니다.
        최대 4장까지 업로드 가능합니다.
        
        Args:
            group_id: 그룹 ID
            issue_id: 회차 ID
            post_id: 게시글 ID
            images: [(filename, data), ...] 형태의 이미지 리스트
            
        Returns:
            업로드된 이미지 URL 리스트
        """
        if len(images) > settings.MAX_IMAGES_PER_POST:
            raise ValueError(f"최대 {settings.MAX_IMAGES_PER_POST}장까지 업로드 가능합니다")
        
        uploaded_urls = []
        
        for idx, (filename, image_data) in enumerate(images, 1):
            try:
                # 이미지 처리 (리사이즈, 최적화)
                processed_image = self._process_post_image(image_data)
                
                # 파일명 생성 (image1.jpg, image2.jpg, ...)
                ext = Path(filename).suffix or '.jpg'
                new_filename = f"image{idx}{ext}"
                
                # Blob 경로 생성
                blob_path = self._build_blob_path(
                    group_id, "issues", issue_id, "posts", post_id, new_filename
                )
                
                # 업로드
                blob_client = self.blob_service_client.get_blob_client(
                    container=self.container_name,
                    blob=blob_path
                )
                
                blob_client.upload_blob(
                    processed_image,
                    overwrite=True,
                    content_settings=ContentSettings(
                        content_type=mimetypes.guess_type(filename)[0] or "image/jpeg",
                        cache_control="max-age=2592000"  # 30일 캐시
                    )
                )
                
                # SAS URL 생성
                sas_url = self.generate_sas_url(blob_path, expiry_hours=8760)  # 1년
                uploaded_urls.append(sas_url)
                
            except Exception as e:
                logger.error(f"Failed to upload image {idx}: {e}")
                # 실패한 이미지들 롤백
                for url in uploaded_urls:
                    try:
                        await self.delete_from_url(url)
                    except:
                        pass
                raise
        
        logger.info(f"Uploaded {len(uploaded_urls)} images for post {post_id}")
        return uploaded_urls
    
    def _process_post_image(self, image_data: bytes) -> bytes:
        """
        게시글 이미지를 처리합니다.
        - EXIF 회전 적용
        - 최대 1920px로 리사이즈 (비율 유지)
        - JPEG로 최적화
        """
        img = Image.open(io.BytesIO(image_data))
        
        # EXIF 회전 적용
        img = ImageOps.exif_transpose(img)
        
        # 최대 크기로 리사이즈 (비율 유지)
        max_size = 1920
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        # RGB로 변환
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 바이트로 변환
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=90, optimize=True)
        return output.getvalue()
    
    async def upload_book_pdf(
        self,
        group_id: str,
        issue_id: str,
        pdf_data: bytes,
        filename: Optional[str] = None
    ) -> str:
        """
        책자 PDF를 업로드합니다.
        Args:
            group_id: 그룹 ID
            issue_id: 회차 ID
            pdf_data: PDF 바이너리 데이터
            filename: 파일명 (없으면 자동 생성)
        Returns:
            업로드된 PDF의 URL
        """
        try:
            # 파일명 생성
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"book_{issue_id}_{timestamp}.pdf"

            # Blob 경로 생성 (수정된 부분)
            blob_path = self._build_blob_path(
                group_id, "issues", issue_id, "books", filename
            )

            # 업로드
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            blob_client.upload_blob(
                pdf_data,
                overwrite=True,
                content_settings=ContentSettings(
                    content_type="application/pdf",
                    content_disposition=f'inline; filename="{filename}"'
                )
            )

            # SAS URL 생성 (다운로드용, 30일 유효)
            sas_url = self.generate_sas_url(blob_path, expiry_hours=720, download=True)
            logger.info(f"Book PDF uploaded: {blob_path}")
            return sas_url
        except Exception as e:
            logger.error(f"Failed to upload book PDF: {e}")
            raise
    
    def generate_sas_url(
        self,
        blob_path: str,
        expiry_hours: int = 24,
        download: bool = False
    ) -> str:
        """
        Blob에 대한 SAS URL을 생성합니다.
        
        Args:
            blob_path: Blob 경로
            expiry_hours: 유효 시간 (시간 단위)
            download: 다운로드 권한 포함 여부
            
        Returns:
            SAS URL
        """
        permissions = BlobSasPermissions(read=True)
        if download:
            permissions.add = True
            permissions.create = True
            permissions.write = True
        
        sas_token = generate_blob_sas(
            account_name=settings.AZURE_STORAGE_ACCOUNT_NAME,
            container_name=self.container_name,
            blob_name=blob_path,
            account_key=settings.AZURE_STORAGE_ACCOUNT_KEY,
            permission=permissions,
            expiry=datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
        )
        
        return f"https://{settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{self.container_name}/{blob_path}?{sas_token}"
    
    async def delete_blob(self, blob_path: str):
        """
        Blob을 삭제합니다.
        
        Args:
            blob_path: 삭제할 Blob 경로
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            blob_client.delete_blob()
            logger.info(f"Blob deleted: {blob_path}")
        except ResourceNotFoundError:
            logger.warning(f"Blob not found for deletion: {blob_path}")
        except Exception as e:
            logger.error(f"Failed to delete blob: {e}")
            raise
    
    async def delete_from_url(self, url: str):
        """
        URL에서 Blob 경로를 추출하여 삭제합니다.
        
        Args:
            url: Blob URL
        """
        try:
            # URL에서 Blob 경로 추출
            # 예: https://account.blob.core.windows.net/container/path/to/file.jpg?sas
            parts = url.split(f"{self.container_name}/", 1)
            if len(parts) > 1:
                blob_path = parts[1].split("?")[0]  # SAS 토큰 제거
                await self.delete_blob(blob_path)
        except Exception as e:
            logger.error(f"Failed to delete from URL: {e}")
    
    async def list_blobs(self, prefix: str) -> List[str]:
        """
        특정 프리픽스로 시작하는 모든 Blob을 나열합니다.
        
        Args:
            prefix: 검색할 프리픽스
            
        Returns:
            Blob 이름 리스트
        """
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            blobs = container_client.list_blobs(name_starts_with=prefix)
            return [blob.name for blob in blobs]
        except Exception as e:
            logger.error(f"Failed to list blobs: {e}")
            return []
    
    async def download_blob(self, blob_path: str) -> bytes:
        """
        Blob을 다운로드합니다.
        
        Args:
            blob_path: 다운로드할 Blob 경로
            
        Returns:
            파일 데이터
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            return blob_client.download_blob().readall()
        except Exception as e:
            logger.error(f"Failed to download blob: {e}")
            raise
    
    def get_blob_url(self, blob_path: str) -> str:
        """
        Blob의 기본 URL을 반환합니다 (SAS 없음).
        CDN 사용 시 이 URL을 사용합니다.
        
        Args:
            blob_path: Blob 경로
            
        Returns:
            Blob URL
        """
        return f"https://{settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{self.container_name}/{blob_path}"


# 싱글톤 인스턴스 생성
storage_service = AzureStorageService()


# 편의 함수들 (직접 임포트해서 사용 가능)
async def upload_profile_image(group_id: str, user_id: str, image_data: bytes, filename: str = "profile.jpg") -> str:
    """프로필 이미지 업로드"""
    return await storage_service.upload_profile_image(group_id, user_id, image_data, filename)

async def upload_post_images(group_id: str, issue_id: str, post_id: str, images: List[Tuple[str, bytes]]) -> List[str]:
    """게시글 이미지 업로드"""
    return await storage_service.upload_post_images(group_id, issue_id, post_id, images)

async def upload_book_pdf(group_id: str, issue_id: str, pdf_data: bytes, filename: Optional[str] = None) -> str:
    """책자 PDF 업로드"""
    return await storage_service.upload_book_pdf(group_id, issue_id, pdf_data, filename)

async def delete_blob(blob_path: str):
    """Blob 삭제"""
    await storage_service.delete_blob(blob_path)

def generate_sas_url(blob_path: str, expiry_hours: int = 24, download: bool = False) -> str:
    """SAS URL 생성"""
    return storage_service.generate_sas_url(blob_path, expiry_hours, download)
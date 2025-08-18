import os
from datetime import datetime, timedelta
from typing import Optional
from azure.storage.blob import BlobServiceClient, ContentSettings, generate_blob_sas, BlobSasPermissions
from azure.core.exceptions import ResourceNotFoundError
from fastapi import HTTPException, UploadFile
import logging

logger = logging.getLogger(__name__)

class FamilyNewsStorageService:
    def __init__(self):
        # 초기화는 실제 사용 시점에서만 수행
        self._initialized = False
        self.blob_service_client = None
        self.container_client = None
        self.container_name = None

    def _ensure_initialized(self):
        """실제 사용 시점에서만 Azure Storage 연결"""
        if self._initialized:
            return

        try:
            # 환경 변수 로드 확인
            print("DEBUG: Azure Storage 초기화 시작...")
            
            connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
            print(f"DEBUG: Connection string exists: {bool(connection_string)}")

            if not connection_string:
                # 개별 구성 요소로 연결 문자열 구성
                account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
                account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
                
                print(f"DEBUG: Account name: {account_name}")
                print(f"DEBUG: Account key exists: {bool(account_key)}")

                if account_name and account_key:
                    connection_string = (
                        f"DefaultEndpointsProtocol=https;"
                        f"AccountName={account_name};"
                        f"AccountKey={account_key};"
                        f"EndpointSuffix=core.windows.net"
                    )
                    print("DEBUG: Connection string created from components")
                else:
                    raise ValueError(
                        "Azure Storage 연결 정보를 찾을 수 없습니다. "
                        "다음 환경변수 중 하나를 설정하세요:\n"
                        "1. AZURE_STORAGE_CONNECTION_STRING\n"
                        "2. AZURE_STORAGE_ACCOUNT_NAME + AZURE_STORAGE_ACCOUNT_KEY\n"
                        f"현재 상태:\n"
                        f"- AZURE_STORAGE_CONNECTION_STRING: {bool(os.getenv('AZURE_STORAGE_CONNECTION_STRING'))}\n"
                        f"- AZURE_STORAGE_ACCOUNT_NAME: {bool(account_name)}\n"
                        f"- AZURE_STORAGE_ACCOUNT_KEY: {bool(account_key)}"
                    )

            self.container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "family-news")
            print(f"DEBUG: Container name: {self.container_name}")

            # Azure Storage 클라이언트 초기화
            print("DEBUG: BlobServiceClient 초기화 중...")
            self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            self.container_client = self.blob_service_client.get_container_client(self.container_name)

            # 컨테이너 존재 확인 및 생성
            try:
                properties = self.container_client.get_container_properties()
                print(f"DEBUG: Container '{self.container_name}' exists")
            except ResourceNotFoundError:
                print(f"DEBUG: Container '{self.container_name}' not found, creating...")
                self.container_client.create_container()
                print(f"DEBUG: Container '{self.container_name}' created")

            self._initialized = True
            print("DEBUG: Azure Storage 초기화 완료")

        except Exception as e:
            error_msg = f"Azure Storage 초기화 실패: {str(e)}"
            logger.error(error_msg)
            print(f"DEBUG ERROR: {error_msg}")
            raise ValueError(error_msg)

    def upload_post_image(
        self,
        group_id: str,
        issue_id: str,
        post_id: str,
        file: UploadFile,
        image_index: int = 0
    ) -> tuple[str, str]:
        """소식 이미지 업로드"""
        self._ensure_initialized()

        try:
            # 파일 내용 읽기
            content = file.file.read()
            file.file.seek(0)  # 파일 포인터 리셋

            if len(content) == 0:
                raise ValueError(f"파일 '{file.filename}'의 내용이 비어있습니다")

            # 파일 확장자 추출
            file_extension = 'jpg'
            if file.filename and '.' in file.filename:
                file_extension = file.filename.split('.')[-1].lower()
                if file_extension not in ['jpg', 'jpeg', 'png', 'webp']:
                    file_extension = 'jpg'

            # Blob 경로 생성
            blob_name = f"{group_id}/issues/{issue_id}/posts/{post_id}/image_{image_index + 1}.{file_extension}"
            print(f"DEBUG: Uploading to blob path: {blob_name}")

            # Content-Type 설정
            content_settings = ContentSettings(content_type=file.content_type or "image/jpeg")

            # Blob 업로드
            blob_client = self.container_client.get_blob_client(blob_name)
            blob_client.upload_blob(
                content,
                overwrite=True,
                content_settings=content_settings
            )

            blob_url = blob_client.url
            print(f"DEBUG: Successfully uploaded: {blob_url}")
            # Return both URL and blob key for deletion purposes
            return blob_url, blob_name

        except Exception as e:
            error_msg = f"이미지 업로드 실패: {str(e)}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

    def upload_profile_image(self, user_id: str, file: UploadFile) -> str:
        """프로필 이미지 업로드"""
        self._ensure_initialized()

        try:
            content = file.file.read()
            file.file.seek(0)

            if len(content) == 0:
                raise ValueError("파일 내용이 비어있습니다")

            file_extension = 'jpg'
            if file.filename and '.' in file.filename:
                file_extension = file.filename.split('.')[-1].lower()
                if file_extension not in ['jpg', 'jpeg', 'png', 'webp']:
                    file_extension = 'jpg'

            blob_name = f"profiles/{user_id}/avatar.{file_extension}"
            content_settings = ContentSettings(content_type=file.content_type or "image/jpeg")

            blob_client = self.container_client.get_blob_client(blob_name)
            blob_client.upload_blob(
                content,
                overwrite=True,
                content_settings=content_settings
            )

            return blob_client.url

        except Exception as e:
            error_msg = f"프로필 이미지 업로드 실패: {str(e)}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

    def upload_book_pdf(
        self,
        group_id: str,
        issue_id: str,
        pdf_content: bytes,
        filename: str
    ) -> str:
        """책자 PDF 업로드"""
        self._ensure_initialized()

        try:
            blob_name = f"{group_id}/issues/{issue_id}/books/{filename}"
            content_settings = ContentSettings(content_type="application/pdf")

            blob_client = self.container_client.get_blob_client(blob_name)
            blob_client.upload_blob(
                pdf_content,
                overwrite=True,
                content_settings=content_settings
            )

            return blob_client.url

        except Exception as e:
            error_msg = f"PDF 업로드 실패: {str(e)}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

    def delete_post_images_by_keys(self, blob_keys: list[str]):
        """저장된 블롭 키로 이미지 삭제 (DB 에서 가져온 정확한 키 사용)"""
        self._ensure_initialized()

        deleted_count = 0
        errors = []
        
        for blob_key in blob_keys:
            try:
                blob_client = self.container_client.get_blob_client(blob_key)
                blob_client.delete_blob()
                deleted_count += 1
                print(f"DEBUG: Deleted blob: {blob_key}")
            except Exception as e:
                error_msg = f"Failed to delete blob {blob_key}: {str(e)}"
                logger.warning(error_msg)
                errors.append(error_msg)

        print(f"DEBUG: Deleted {deleted_count}/{len(blob_keys)} images")
        if errors:
            logger.warning(f"Deletion errors: {errors}")
        
        return deleted_count, errors
    
    def delete_post_images(self, group_id: str, issue_id: str, post_id: str):
        """소식의 모든 이미지 삭제 (레거시 메서드 - 경로 재구성 사용)"""
        self._ensure_initialized()

        try:
            prefix = f"{group_id}/issues/{issue_id}/posts/{post_id}/"
            blobs = self.container_client.list_blobs(name_starts_with=prefix)

            deleted_count = 0
            for blob in blobs:
                blob_client = self.container_client.get_blob_client(blob.name)
                blob_client.delete_blob()
                deleted_count += 1

            print(f"DEBUG: Deleted {deleted_count} images for post {post_id}")

        except Exception as e:
            error_msg = f"이미지 삭제 실패: {str(e)}"
            logger.error(error_msg)

    def generate_sas_url(self, blob_name: str, expiry_minutes: int = 60) -> str:
        """SAS URL 생성"""
        self._ensure_initialized()

        try:
            sas_token = generate_blob_sas(
                account_name=self.blob_service_client.account_name,
                container_name=self.container_name,
                blob_name=blob_name,
                account_key=self.blob_service_client.credential.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(minutes=expiry_minutes)
            )

            return f"https://{self.blob_service_client.account_name}.blob.core.windows.net/{self.container_name}/{blob_name}?{sas_token}"

        except Exception as e:
            error_msg = f"SAS URL 생성 실패: {str(e)}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

# 전역 인스턴스 (단순한 방식)
_storage_instance: Optional[FamilyNewsStorageService] = None

def get_storage_service() -> FamilyNewsStorageService:
    """Storage 서비스 인스턴스 반환 (지연 초기화)"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = FamilyNewsStorageService()
    return _storage_instance

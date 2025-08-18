from typing import List
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import traceback

from ...services.storage_service import post_storage_service
from ...database.session import get_db
from ...api.dependencies import get_current_user
from ...models.user import User
from ...crud.post_crud import post_crud
from ...crud.issue_crud import issue_crud
from ...crud.member_crud import family_member_crud
from ...schemas.post import PostCreate, PostResponse, PostCreateWithImages
from ...core.config import settings
from ...core.constants import MAX_POSTS_PER_ISSUE

router = APIRouter(prefix="/posts", tags=["posts"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=PostResponse)
async def create_post(
    post_data: PostCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """소식 작성 - Azure Blob Storage 사용"""
    logger.info(f"소식 작성 요청 시작: user_id={current_user.id}")

    try:
        # 1. 멤버십 확인
        membership = await family_member_crud.check_user_membership(db, current_user.id)
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="가족 그룹에 속해있지 않습니다"
            )

        # 2. 현재 회차 확인
        current_issue = await issue_crud.get_current_issue(db, membership.group_id)
        if not current_issue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="현재 열린 회차가 없습니다"
            )

        # 3. 소식 개수 확인
        current_post_count = await post_crud.count_posts_by_issue(db, current_issue.id)
        if current_post_count >= MAX_POSTS_PER_ISSUE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"월 최대 소식 개수({MAX_POSTS_PER_ISSUE}개)에 도달했습니다"
            )

        # 4. 소식 생성
        new_post = await post_crud.create_post(
            db, post_data, current_user.id, current_issue.id
        )

        # 5. PostResponse 생성
        post_response_data = {
            "id": str(new_post.id),
            "issue_id": str(new_post.issue_id),
            "author_id": str(new_post.author_id),
            "content": new_post.content,
            "image_urls": new_post.image_urls or [],
            "created_at": new_post.created_at,
            "updated_at": new_post.updated_at,
            "author_name": None,
            "author_relationship": None,
            "author_profile_image": None
        }

        return PostResponse(**post_response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"소식 작성 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="소식 작성 중 오류가 발생했습니다"
        )

@router.post("/with-images", response_model=PostResponse)
async def create_post_with_images(
    post_data: PostCreateWithImages,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """이미지와 함께 소식 작성 - 블롭 키 저장"""
    logger.info(f"이미지와 함께 소식 작성 요청: user_id={current_user.id}")

    try:
        # 1. 멤버십 확인
        membership = await family_member_crud.check_user_membership(db, current_user.id)
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="가족 그룹에 속해있지 않습니다"
            )

        # 2. 현재 회차 확인
        current_issue = await issue_crud.get_current_issue(db, membership.group_id)
        if not current_issue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="현재 열린 회차가 없습니다"
            )

        # 3. 소식 개수 확인
        current_post_count = await post_crud.count_posts_by_issue(db, current_issue.id)
        if current_post_count >= MAX_POSTS_PER_ISSUE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"월 최대 소식 개수({MAX_POSTS_PER_ISSUE}개)에 도달했습니다"
            )

        # 4. 소식 생성 (이미지 URL과 블롭 키 포함)
        new_post = await post_crud.create_post(
            db=db,
            post_data=post_data,
            author_id=current_user.id,
            issue_id=current_issue.id,
            image_urls=post_data.image_urls,
            image_blob_keys=post_data.image_blob_keys
        )

        # 5. 데이터베이스 커밋
        await db.commit()
        await db.refresh(new_post)

        # 6. PostResponse 생성
        post_response_data = {
            "id": str(new_post.id),
            "issue_id": str(new_post.issue_id),
            "author_id": str(new_post.author_id),
            "content": new_post.content,
            "image_urls": new_post.image_urls or [],
            "created_at": new_post.created_at,
            "updated_at": new_post.updated_at,
            "author_name": None,
            "author_relationship": None,
            "author_profile_image": None
        }

        logger.info(f"이미지와 함께 소식 작성 완료: post_id={new_post.id}")
        return PostResponse(**post_response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"이미지와 함께 소식 작성 중 오류: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="소식 작성 중 오류가 발생했습니다"
        )

@router.get("/", response_model=List[PostResponse])
async def get_current_posts(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """현재 회차의 소식 목록 조회"""
    try:
        # 1. 멤버십 확인
        membership = await family_member_crud.check_user_membership(db, current_user.id)
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="가족 그룹에 속해있지 않습니다"
            )

        # 2. 현재 회차 확인
        current_issue = await issue_crud.get_current_issue(db, membership.group_id)
        if not current_issue:
            return []

        # 3. 소식 목록 조회
        posts = await post_crud.get_posts_by_issue(db, current_issue.id, skip, limit)

        # 4. PostResponse 변환
        post_responses = []
        for post in posts:
            post_response_data = {
                "id": str(post.id),
                "issue_id": str(post.issue_id),
                "author_id": str(post.author_id),
                "content": post.content,
                "image_urls": post.image_urls or [],
                "created_at": post.created_at,
                "updated_at": post.updated_at,
                "author_name": getattr(post.author, 'name', None) if hasattr(post, 'author') and post.author else None,
                "author_relationship": None,
                "author_profile_image": getattr(post.author, 'profile_image_url', None) if hasattr(post, 'author') and post.author else None
            }
            post_responses.append(PostResponse(**post_response_data))

        return post_responses

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"소식 목록 조회 중 오류: {str(e)}")
        return []

@router.post("/upload-images")
async def upload_post_images(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """소식 작성용 이미지 업로드 - Azure Blob Storage 사용"""
    
    try:
        # 1. 멤버십 확인
        membership = await family_member_crud.check_user_membership(db, current_user.id)
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="가족 그룹에 속해있지 않습니다"
            )

        # 2. 현재 회차 확인
        current_issue = await issue_crud.get_current_issue(db, membership.group_id)
        if not current_issue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="현재 열린 회차가 없습니다"
            )

        # 3. 임시 post_id 생성
        temp_post_id = str(uuid.uuid4())

        # 4. Azure Blob Storage에 이미지 업로드
        image_urls, blob_keys = await post_storage_service.upload_post_images(
            group_id=str(membership.group_id),
            issue_id=str(current_issue.id),
            post_id=temp_post_id,
            files=files
        )

        return {
            "image_urls": image_urls,
            "blob_keys": blob_keys,
            "temp_post_id": temp_post_id,
            "storage_type": "Azure Blob Storage",
            "message": f"{len(image_urls)}개 이미지 업로드 완료"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"이미지 업로드 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="이미지 업로드 중 오류가 발생했습니다"
        )

@router.delete("/{post_id}")
async def delete_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """소식 삭제"""
    
    try:
        # 1. 소식 존재 확인 및 권한 확인
        post = await post_crud.get(db, post_id)
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="소식을 찾을 수 없습니다"
            )

        if str(post.author_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="자신이 작성한 소식만 삭제할 수 있습니다"
            )

        # 2. 이미지 삭제 (Azure Blob Storage)
        if post.image_blob_keys:
            try:
                from ...utils.azure_storage import get_storage_service
                storage_service = get_storage_service()
                deleted_count, errors = storage_service.delete_post_images_by_keys(post.image_blob_keys)
                logger.info(f"Azure Blob Storage에서 {deleted_count}개 이미지 삭제 완료: post_id={post_id}")
                if errors:
                    logger.warning(f"일부 이미지 삭제 실패: {errors}")
            except Exception as e:
                logger.error(f"이미지 삭제 중 오류 (계속 진행): {str(e)}")
        elif post.image_urls:
            # Fallback for old posts without blob keys (레거시 지원)
            try:
                # 멤버십 확인
                membership = await family_member_crud.check_user_membership(db, current_user.id)
                if membership:
                    # 현재 회차 확인
                    current_issue = await issue_crud.get_current_issue(db, membership.group_id)
                    if current_issue:
                        from ...utils.azure_storage import get_storage_service
                        storage_service = get_storage_service()
                        storage_service.delete_post_images(
                            str(membership.group_id),
                            str(current_issue.id),
                            str(post.id)
                        )
                        logger.info(f"Azure Blob Storage에서 레거시 방식으로 이미지 삭제: post_id={post_id}")
            except Exception as e:
                logger.error(f"레거시 이미지 삭제 중 오류 (계속 진행): {str(e)}")

        # 3. 소식 삭제
        await post_crud.delete(db, post_id)

        return {"message": "소식이 성공적으로 삭제되었습니다"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"소식 삭제 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"소식 삭제 중 오류: {str(e)}"
        )

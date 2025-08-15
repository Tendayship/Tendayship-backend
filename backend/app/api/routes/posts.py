from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime


from ...database.session import get_db
from ...api.dependencies import get_current_user
from ...models.user import User
from ...crud.post_crud import post_crud
from ...crud.issue_crud import issue_crud
from ...crud.member_crud import family_member_crud
from ...schemas.post import PostCreate, PostResponse, ImageUploadResponse
from ...services.storage_service import post_storage_service
from ...core.config import settings

router = APIRouter(prefix="/posts", tags=["posts"])

@router.post("/", response_model=PostResponse)
async def create_post(
    post_data: PostCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    소식 작성 (MVP 핵심 기능)
    - 텍스트 50-100자
    - 이미지 1-4장 필수
    - 현재 열린 회차에만 작성 가능
    """
    
    # 1. 사용자의 그룹 멤버십 확인
    membership = await family_member_crud.check_user_membership(
        db, current_user.id
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="가족 그룹에 속해있지 않습니다"
        )
    
    # 2. 현재 열린 회차 확인
    current_issue = await issue_crud.get_current_issue(
        db, membership.group_id
    )
    if not current_issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="현재 열린 회차가 없습니다"
        )
    
    # 3. 월 최대 소식 개수 확인 (20개 제한)
    current_post_count = await post_crud.count_posts_by_issue(
        db, current_issue.id
    )
    if current_post_count >= settings.MAX_POSTS_PER_MONTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"월 최대 소식 개수({settings.MAX_POSTS_PER_MONTH}개)에 도달했습니다"
        )
    
    # 4. 소식 작성
    try:
        new_post = await post_crud.create_post(
            db, post_data, current_user.id, current_issue.id
        )
        return new_post
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"소식 작성 중 오류: {str(e)}"
        )

@router.post("/upload-images", response_model=ImageUploadResponse)
async def upload_post_images(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    소식 이미지 업로드
    - 최대 4장, 10MB 제한
    - 자동 리사이즈 및 콜라주 레이아웃
    """
    
    membership = await family_member_crud.check_user_membership(
        db, current_user.id
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="가족 그룹에 속해있지 않습니다"
        )
    
    current_issue = await issue_crud.get_current_issue(
        db, membership.group_id
    )
    if not current_issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="현재 열린 회차가 없습니다"
        )
    
    try:
        # 임시 post_id 생성 (실제 소식 작성 전 이미지 업로드)
        temp_post_id = f"temp_{current_user.id}_{int(datetime.now().timestamp())}"
        
        image_urls, layout = await post_storage_service.upload_post_images(
            group_id=membership.group_id,
            issue_id=current_issue.id,
            post_id=temp_post_id,
            files=files
        )
        
        return ImageUploadResponse(
            image_urls=image_urls,
            collage_layout=layout
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"이미지 업로드 중 오류: {str(e)}"
        )

@router.get("/", response_model=List[PostResponse])
async def get_current_posts(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """현재 회차의 소식 목록 조회 (피드)"""
    
    membership = await family_member_crud.check_user_membership(
        db, current_user.id
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="가족 그룹에 속해있지 않습니다"
        )
    
    current_issue = await issue_crud.get_current_issue(
        db, membership.group_id
    )
    if not current_issue:
        return []  # 현재 회차가 없으면 빈 목록 반환
    
    posts = await post_crud.get_posts_by_issue(
        db, current_issue.id, skip, limit
    )
    
    return posts

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from ...database.session import get_db
from ...api.dependencies import get_current_user
from ...models.user import User
from ...crud.user_crud import user_crud
from ...services.storage_service import post_storage_service
from ...schemas.user import UserUpdate, UserResponse

router = APIRouter(prefix="/profile", tags=["profile"])

@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user)
):
    """현재 사용자 프로필 조회"""
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_my_profile(
    profile_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """사용자 프로필 수정"""
    
    try:
        updated_user = await user_crud.update(
            db, db_obj=current_user, obj_in=profile_data
        )
        return updated_user
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"프로필 수정 중 오류: {str(e)}"
        )

@router.post("/me/avatar")
async def upload_profile_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """프로필 이미지 업로드"""
    
    try:
        # 이미지 업로드 및 URL 반환
        image_url = await post_storage_service.upload_profile_image(
            user_id=current_user.id,
            file=file
        )
        
        # 사용자 프로필 이미지 URL 업데이트
        current_user.profile_image_url = image_url
        await db.commit()
        
        return {"profile_image_url": image_url}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"프로필 이미지 업로드 중 오류: {str(e)}"
        )

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database.session import get_db
from ...api.dependencies import get_current_user
from ...models.user import User
from ...crud.family_crud import family_group_crud
from ...crud.member_crud import family_member_crud
from ...crud.recipient_crud import recipient_crud
from ...schemas.family import (
    FamilyGroupCreate, 
    FamilyGroupResponse
)

router = APIRouter(prefix="/family", tags=["family"])

@router.post("/create", response_model=FamilyGroupResponse)
async def create_family_group(
    group_data: FamilyGroupCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    가족 그룹 생성 (리더만 가능)
    
    1. 사용자가 이미 다른 그룹에 속해있는지 확인
    2. 받는 분 정보 생성
    3. 가족 그룹 생성
    4. 리더를 첫 번째 멤버로 추가
    """
    
    # 1. 기존 그룹 멤버십 확인
    existing_membership = await family_member_crud.check_user_membership(
        db, current_user.id
    )
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 다른 가족 그룹에 속해있습니다"
        )
    
    try:
        # 2. 받는 분 정보 생성 (임시로, 그룹 생성 후 실제 ID로 업데이트)
        db_recipient = await recipient_crud.create(
            db, group_data.recipient_info
        )
        
        # 3. 가족 그룹 생성
        db_group = await family_group_crud.create_with_leader(
            db, group_data, current_user.id
        )
        
        # 받는 분에 그룹 ID 설정
        db_recipient.group_id = db_group.id
        
        # 4. 리더를 첫 번째 멤버로 추가
        await family_member_crud.create_member(
            db=db,
            user_id=current_user.id,
            group_id=db_group.id,
            recipient_id=db_recipient.id,
            relationship=group_data.leader_relationship,
            role="leader"
        )
        
        await db.commit()
        await db.refresh(db_group)
        
        return db_group
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"가족 그룹 생성 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/my-group", response_model=FamilyGroupResponse)
async def get_my_family_group(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """현재 사용자가 속한 가족 그룹 조회"""
    
    group = await family_group_crud.get_by_user_id(db, current_user.id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="속한 가족 그룹이 없습니다"
        )
    
    return group

@router.post("/{group_id}/regenerate-invite")
async def regenerate_invite_code(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """초대 코드 재생성 (리더만 가능)"""
    
    # 그룹 조회 및 리더 권한 확인
    member = await family_member_crud.get_by_user_and_group(
        db, current_user.id, group_id
    )
    
    if not member or member.role != "leader":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="그룹 리더만 초대 코드를 재생성할 수 있습니다"
        )
    
    # 새 초대 코드 생성
    new_invite_code = family_group_crud._generate_invite_code()
    group = await family_group_crud.get(db, group_id)
    group.invite_code = new_invite_code
    
    await db.commit()
    
    return {"invite_code": new_invite_code}

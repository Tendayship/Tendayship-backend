from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database.session import get_db
from ...api.dependencies import get_current_user
from ...models.user import User
from ...crud.family_crud import family_group_crud
from ...crud.member_crud import family_member_crud
from ...schemas.family import (
    MemberJoinRequest,
    FamilyMemberResponse
)
from ...core.constants import ROLE_LEADER, ROLE_MEMBER, MAX_GROUP_MEMBERS

router = APIRouter(prefix="/members", tags=["members"])

@router.post("/join", response_model=FamilyMemberResponse)
async def join_family_group(
    join_data: MemberJoinRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    초대 코드로 가족 그룹 가입
    
    1. 초대 코드 유효성 확인
    2. 사용자의 기존 멤버십 확인
    3. 그룹 멤버 수 제한 확인 (최대 20명)
    4. 멤버로 추가
    """
    
    # 1. 초대 코드로 그룹 조회
    group = await family_group_crud.get_by_invite_code(
        db, join_data.invite_code
    )
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="유효하지 않은 초대 코드입니다"
        )
    
    # 2. 기존 멤버십 확인
    existing_membership = await family_member_crud.check_user_membership(
        db, current_user.id
    )
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 다른 가족 그룹에 속해있습니다"
        )
    
    # 3. 그룹 멤버 수 제한 확인
    current_members = await family_member_crud.get_group_members(
        db, group.id
    )
    if len(current_members) >= MAX_GROUP_MEMBERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"가족 그룹 멤버 수가 최대 제한({MAX_GROUP_MEMBERS}명)에 도달했습니다"
        )
    
    # 4. 멤버로 추가
    try:
        new_member = await family_member_crud.create_member(
            db=db,
            user_id=current_user.id,
            group_id=group.id,
            recipient_id=group.recipient.id,
            relationship=join_data.relationship,
            role=ROLE_MEMBER
        )
        
        return new_member
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"그룹 가입 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/validate-invite/{invite_code}")
async def validate_invite_code(invite_code: str, db: AsyncSession = Depends(get_db)):
    """초대 코드 유효성 검증"""
    
    group = await family_group_crud.get_by_invite_code(db, invite_code)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="유효하지 않은 초대 코드입니다"
        )
    
    # 멤버 수 확인
    current_members = await family_member_crud.get_group_members(db, group.id)
    
    return {
        "valid": True,
        "group_name": group.group_name,
        "current_member_count": len(current_members),
        "max_members": MAX_GROUP_MEMBERS,
        "recipient_name": group.recipient.name
    }

@router.get("/my-group/members", response_model=List[FamilyMemberResponse])
async def get_my_group_members(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """현재 사용자가 속한 그룹의 멤버 목록 조회"""
    
    # 사용자의 멤버십 확인
    membership = await family_member_crud.check_user_membership(
        db, current_user.id
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="속한 가족 그룹이 없습니다"
        )
    
    # 그룹 멤버 목록 조회
    members = await family_member_crud.get_group_members(
        db, membership.group_id
    )
    
    return members

@router.delete("/{member_id}")
async def remove_member(
    member_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """멤버 제거 (리더만 가능, 본인 제거 불가)"""
    
    # 제거할 멤버 조회
    target_member = await family_member_crud.get(db, member_id)
    if not target_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="멤버를 찾을 수 없습니다"
        )
    
    # 현재 사용자의 멤버십 및 권한 확인
    current_membership = await family_member_crud.get_by_user_and_group(
        db, current_user.id, target_member.group_id
    )
    
    if not current_membership or current_membership.role != ROLE_LEADER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="그룹 리더만 멤버를 제거할 수 있습니다"
        )
    
    # 본인 제거 방지
    if target_member.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="자신을 그룹에서 제거할 수 없습니다"
        )
    
    # 멤버 제거
    await family_member_crud.remove(db, id=member_id)
    
    return {"message": "멤버가 성공적으로 제거되었습니다"}

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database.session import get_db
from ...api.dependencies import get_current_user
from ...models.user import User
from ...crud.family_crud import family_group_crud
from ...crud.member_crud import family_member_crud
from ...crud.recipient_crud import recipient_crud
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
    group = await family_group_crud.get_by_invite_code(
        db, join_data.invite_code
    )

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="유효하지 않은 초대 코드입니다"
        )

    existing_membership = await family_member_crud.check_user_membership(
        db, current_user.id
    )

    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 다른 가족 그룹에 속해있습니다"
        )

    current_members = await family_member_crud.get_group_members(
        db, group.id
    )

    if len(current_members) >= MAX_GROUP_MEMBERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"가족 그룹 멤버 수가 최대 제한({MAX_GROUP_MEMBERS}명)에 도달했습니다"
        )

    recipient = await recipient_crud.get_by_group_id(db, group.id)
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="그룹에 받는 분 정보가 설정되지 않았습니다"
        )

    try:
        new_member = await family_member_crud.create_member(
            db=db,
            user_id=current_user.id,
            group_id=group.id,
            recipient_id=recipient.id,
            relationship=join_data.relationship,
            role=ROLE_MEMBER
        )

        await db.commit()
        await db.refresh(new_member)
        return new_member

    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"그룹 가입 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/validate-invite/{invite_code}")
async def validate_invite_code(invite_code: str, db: AsyncSession = Depends(get_db)):
    group = await family_group_crud.get_by_invite_code(db, invite_code)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="유효하지 않은 초대 코드입니다"
        )

    current_members = await family_member_crud.get_group_members(db, group.id)
    return {
        "valid": True,
        "group_name": group.group_name,
        "current_member_count": len(current_members),
        "max_members": MAX_GROUP_MEMBERS,
        "recipient_name": group.recipient.name if group.recipient else None
    }

@router.get("/my-group/members", response_model=List[FamilyMemberResponse])
async def get_my_group_members(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    membership = await family_member_crud.check_user_membership(
        db, current_user.id
    )

    if not membership:
        return []

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
    target_member = await family_member_crud.get(db, member_id)
    if not target_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="멤버를 찾을 수 없습니다"
        )

    current_membership = await family_member_crud.get_by_user_and_group(
        db, current_user.id, target_member.group_id
    )

    if not current_membership or current_membership.role.value != ROLE_LEADER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="그룹 리더만 멤버를 제거할 수 있습니다"
        )

    if target_member.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="자신을 그룹에서 제거할 수 없습니다"
        )

    try:
        await family_member_crud.remove(db, id=member_id)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"멤버 삭제 중 오류가 발생했습니다: {str(e)}"
        )

    return {"message": "멤버가 성공적으로 제거되었습니다"}

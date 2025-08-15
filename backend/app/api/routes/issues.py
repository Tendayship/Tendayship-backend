from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_current_user
from app.crud import issue_crud
from app.crud.member_crud import family_member_crud
from app.schemas.issue import CurrentIssueResponse as IssueOut
from app.models.user import User

router = APIRouter(prefix="/issues", tags=["Issues"])

@router.get("/current", response_model=IssueOut)
async def get_current_issue_for_group(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    ### 현재 사용자가 속한 그룹의 '진행 중'인 회차 정보를 조회합니다.
    """
    # 사용자의 멤버십 확인
    membership = await family_member_crud.check_user_membership(db, current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="가족 그룹에 속해있지 않습니다"
        )
    
    issue = await issue_crud.get_current_issue(db, group_id=membership.group_id)
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="현재 진행 중인 회차가 없습니다"
        )

    return issue
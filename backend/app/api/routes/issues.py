from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.dependencies import get_db, get_current_user
from ...crud.issue_crud import issue_crud
from ...crud.member_crud import family_member_crud
from ...schemas.issue import CurrentIssueResponse as IssueOut
from ...models.user import User
from ...core.constants import ROLE_LEADER

router = APIRouter(prefix="/issues", tags=["Issues"])

@router.get("/current", response_model=dict)
async def get_current_issue_for_group(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """현재 사용자가 속한 그룹의 '진행 중'인 회차 정보를 조회합니다 - 안전한 버전"""
    
    membership = await family_member_crud.check_user_membership(db, current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="가족 그룹에 속해있지 않습니다"
        )

    issue = await issue_crud.get_current_issue(db, group_id=membership.group_id)
    if not issue:
        return {
            "message": "현재 진행 중인 회차가 없습니다",
            "current_issue": None,
            "group_id": str(membership.group_id)
        }
    
    from datetime import datetime
    days_until_deadline = (issue.deadline_date - datetime.now().date()).days if issue.deadline_date else 0
    
    return {
        "current_issue": {
            "id": str(issue.id),
            "issue_number": issue.issue_number,
            "deadline_date": issue.deadline_date.isoformat() if issue.deadline_date else None,
            "status": issue.status.value if hasattr(issue.status, 'value') else str(issue.status),
            "days_until_deadline": max(0, days_until_deadline),
            "created_at": issue.created_at.isoformat() if hasattr(issue, 'created_at') else None
        },
        "group_id": str(membership.group_id)
    }

@router.post("/create", response_model=dict)
async def create_new_issue(
    issue_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """새 회차 생성 (리더만 가능)"""
    
    membership = await family_member_crud.check_user_membership(db, current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="가족 그룹에 속해있지 않습니다"
        )

    role_value = membership.role.value if hasattr(membership.role, 'value') else str(membership.role)
    if role_value != ROLE_LEADER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="그룹 리더만 회차를 생성할 수 있습니다"
        )

    try:
        new_issue = await issue_crud.create(db, issue_data)
        
        return {
            "message": "새 회차가 생성되었습니다",
            "issue": {
                "id": str(new_issue.id),
                "issue_number": new_issue.issue_number,
                "deadline_date": new_issue.deadline_date.isoformat(),
                "status": new_issue.status.value
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"회차 생성 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/", response_model=list)
async def get_group_issues(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """그룹의 모든 회차 목록 조회"""
    
    membership = await family_member_crud.check_user_membership(db, current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="가족 그룹에 속해있지 않습니다"
        )

    try:
        issues = await issue_crud.get_issues_by_group(db, group_id=membership.group_id)
        return issues
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"회차 목록 조회 중 오류가 발생했습니다: {str(e)}"
        )

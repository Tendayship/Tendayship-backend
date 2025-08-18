from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import logging

from ...database.session import get_db
from ...api.dependencies import get_current_user
from ...models.user import User
from ...crud.family_crud import family_group_crud
from ...crud.member_crud import family_member_crud
from ...crud.recipient_crud import recipient_crud
from ...crud.issue_crud import issue_crud
from ...schemas.family import FamilyGroupCreate, FamilyGroupResponse
from ...schemas.user import FamilyGroupSetup
from ...core.constants import ROLE_LEADER

router = APIRouter(prefix="/family", tags=["family"])
logger = logging.getLogger(__name__)

# 마감일 계산 함수
def calculate_deadline_date(deadline_type: str) -> datetime:
    """다음 달의 해당 일요일 계산"""
    now = datetime.now()
    if now.month == 12:
        next_month = now.replace(year=now.year + 1, month=1, day=1)
    else:
        next_month = now.replace(month=now.month + 1, day=1)
    first_sunday = next_month
    while first_sunday.weekday() != 6:  # 일요일 = 6
        first_sunday += timedelta(days=1)
    if deadline_type == "SECOND_SUNDAY":
        return first_sunday + timedelta(days=7)   # 둘째 주 일요일
    else:  # FOURTH_SUNDAY
        return first_sunday + timedelta(days=21)  # 넷째 주 일요일

@router.post("/setup", response_model=dict)
async def setup_family_group(
    setup_data: FamilyGroupSetup,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    가족 그룹 초기 설정 (새 사용자용)
    1) 기존 멤버십 확인
    2) 그룹 생성
    3) 받는 분 생성
    4) 첫 회차 생성
    5) 리더 멤버 추가
    """
    existing_membership = await family_member_crud.check_user_membership(db, current_user.id)
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 다른 가족 그룹에 속해있습니다"
        )

    try:
        # 2. 그룹 생성
        group_data = {
            "group_name": setup_data.group_name,
            "leader_id": current_user.id,
            "deadline_type": setup_data.deadline_type,
            "leader_relationship": setup_data.leader_relationship
        }
        db_group = await family_group_crud.create_with_leader(db, group_data, current_user.id)

        # 3. 받는 분 생성 (group_id 포함)
        recipient_data = {
            "name": setup_data.recipient_name,
            "address": setup_data.recipient_address,
            "address_detail": setup_data.recipient_address_detail,
            "postal_code": setup_data.recipient_postal_code or "00000",
            "phone": setup_data.recipient_phone or current_user.phone,
            "group_id": db_group.id
        }
        db_recipient = await recipient_crud.create(db, recipient_data)

        # 4. 첫 회차 생성
        deadline_date = calculate_deadline_date(setup_data.deadline_type)
        issue_data = {
            "group_id": str(db_group.id),
            "issue_number": 1,
            "deadline_date": deadline_date.date(),
            "status": "OPEN"
        }
        db_issue = await issue_crud.create(db, issue_data)

        # 5. 리더 멤버 추가
        await family_member_crud.create_member(
            db=db,
            user_id=current_user.id,
            group_id=db_group.id,
            recipient_id=db_recipient.id,
            relationship=setup_data.leader_relationship,
            role=ROLE_LEADER
        )

        await db.commit()
        await db.refresh(db_group)

        return {
            "message": "가족 그룹이 성공적으로 생성되었습니다",
            "group": {
                "id": str(db_group.id),
                "group_name": db_group.group_name,
                "invite_code": db_group.invite_code,
                "deadline_type": db_group.deadline_type,
                "status": db_group.status
            },
            "recipient": {
                "id": str(db_recipient.id),
                "name": db_recipient.name,
                "address": db_recipient.address,
                "postal_code": db_recipient.postal_code
            },
            "issue": {
                "id": str(db_issue.id),
                "issue_number": db_issue.issue_number,
                "deadline_date": db_issue.deadline_date.isoformat(),
                "status": db_issue.status
            }
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"가족 그룹 설정 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/recipient", response_model=dict)
async def get_my_recipient(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """현재 사용자가 속한 그룹의 받는 분 정보 조회"""
    membership = await family_member_crud.check_user_membership(db, current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="속한 가족 그룹이 없습니다"
        )

    group = await family_group_crud.get(db, membership.group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="가족 그룹을 찾을 수 없습니다"
        )

    recipient = await recipient_crud.get_by_group_id(db, membership.group_id)
    if not recipient:
        return {
            "error": "받는 분 정보 없음",
            "message": "받는 분 정보가 설정되지 않았습니다",
            "group_id": str(membership.group_id)
        }

    return {
        "id": str(recipient.id),
        "name": recipient.name,
        "address": recipient.address,
        "address_detail": getattr(recipient, 'address_detail', None),
        "postal_code": getattr(recipient, 'postal_code', None),
        "phone": getattr(recipient, 'phone', None),
        "road_address": getattr(recipient, 'road_address', None),
        "jibun_address": getattr(recipient, 'jibun_address', None),
        "address_type": getattr(recipient, 'address_type', None),
        "latitude": getattr(recipient, 'latitude', None),
        "longitude": getattr(recipient, 'longitude', None),
        "region_1depth": getattr(recipient, 'region_1depth', None),
        "region_2depth": getattr(recipient, 'region_2depth', None),
        "region_3depth": getattr(recipient, 'region_3depth', None),
        "created_at": recipient.created_at.isoformat() if hasattr(recipient, 'created_at') else None,
        "updated_at": recipient.updated_at.isoformat() if hasattr(recipient, 'updated_at') else None
    }

@router.post("/create", response_model=FamilyGroupResponse)
async def create_family_group(
    group_data: FamilyGroupCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """가족 그룹 생성 (리더만 가능)"""
    existing_membership = await family_member_crud.check_user_membership(db, current_user.id)
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 다른 가족 그룹에 속해있습니다"
        )

    try:
        # 받는 분 생성
        db_recipient = await recipient_crud.create(db, group_data.recipient_info)

        # 그룹 생성
        db_group = await family_group_crud.create_with_leader(db, group_data, current_user.id)

        # 받는 분에 group_id 설정
        db_recipient.group_id = db_group.id

        # 리더 멤버 추가
        await family_member_crud.create_member(
            db=db,
            user_id=current_user.id,
            group_id=db_group.id,
            recipient_id=db_recipient.id,
            relationship=group_data.leader_relationship,
            role=ROLE_LEADER
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
    member = await family_member_crud.get_by_user_and_group(db, current_user.id, group_id)
    if not member or getattr(member, "role", None) != ROLE_LEADER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="그룹 리더만 초대 코드를 재생성할 수 있습니다"
        )

    new_invite_code = family_group_crud._generate_invite_code()
    group = await family_group_crud.get(db, group_id)
    group.invite_code = new_invite_code
    await db.commit()
    return {"invite_code": new_invite_code}

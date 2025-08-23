from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import logging
from typing import Union
import enum

from ...models.issue import IssueStatus
from ...database.session import get_db
from ...api.dependencies import get_current_user
from ...models.user import User
from ...crud.family_crud import family_group_crud
from ...crud.member_crud import family_member_crud
from ...crud.recipient_crud import recipient_crud
from ...crud.issue_crud import issue_crud
from ...crud.book_crud import book_crud
from ...schemas.family import FamilyGroupCreate, FamilyGroupResponse, MyGroupOut, RecipientOut
from ...schemas.user import FamilyGroupSetup
from ...core.constants import ROLE_LEADER
from ...models.book import DeliveryStatus, ProductionStatus
from ...services.subscription_admin_service import subscription_admin_service
from ...schemas.recipient import RecipientCreate
from ...models.family import RelationshipType, MemberRole

router = APIRouter(prefix="/family", tags=["family"])
logger = logging.getLogger(__name__)

def enum_to_str(value: Union[str, enum.Enum]) -> str:
    return value.value if hasattr(value, "value") else str(value)

def to_relationship_enum(value: Union[str, enum.Enum]) -> RelationshipType:
    if isinstance(value, RelationshipType):
        return value
    str_value = value.value if hasattr(value, "value") else str(value)
    return RelationshipType(str_value)

def safe_enum_value(value):
    return value.value if hasattr(value, "value") else str(value)

def calculate_deadline_date(deadline_type: str) -> datetime:
    now = datetime.now()
    if now.month == 12:
        next_month = now.replace(year=now.year + 1, month=1, day=1)
    else:
        next_month = now.replace(month=now.month + 1, day=1)
    
    first_sunday = next_month
    while first_sunday.weekday() != 6:
        first_sunday += timedelta(days=1)
    
    if deadline_type == "SECOND_SUNDAY":
        return first_sunday + timedelta(days=7)
    else:
        return first_sunday + timedelta(days=21)

@router.post("/setup", response_model=dict)
async def setup_family_group(
    setup_data: FamilyGroupSetup,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    existing_membership = await family_member_crud.check_user_membership(db, current_user.id)
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 다른 가족 그룹에 속해있습니다"
        )

    try:
        recipient_info = RecipientCreate(
            name=setup_data.recipient_name,
            address=setup_data.recipient_address,
            address_detail=setup_data.recipient_address_detail,
            postal_code=setup_data.recipient_postal_code or "00000",
            phone=setup_data.recipient_phone or current_user.phone
        )

        group_create_data = FamilyGroupCreate(
            group_name=setup_data.group_name,
            deadline_type=setup_data.deadline_type,
            leader_relationship=setup_data.leader_relationship,
            recipient_info=recipient_info
        )

        db_group = await family_group_crud.create_with_leader(db, group_create_data, current_user.id)
        
        recipient_data = {
            "name": recipient_info.name,
            "address": recipient_info.address,
            "address_detail": recipient_info.address_detail,
            "postal_code": recipient_info.postal_code,
            "phone": recipient_info.phone,
            "group_id": db_group.id
        }
        db_recipient = await recipient_crud.create(db, recipient_data)

        if not db_recipient.id:
            raise ValueError("Recipient ID가 생성되지 않았습니다")

        deadline_str = enum_to_str(setup_data.deadline_type)
        deadline_date = calculate_deadline_date(deadline_str)
        issue_data = {
            "group_id": db_group.id,
            "issue_number": 1,
            "deadline_date": deadline_date.date(),
            "status": IssueStatus.OPEN
        }
        db_issue = await issue_crud.create(db, issue_data)

        relationship_enum = to_relationship_enum(setup_data.leader_relationship)
        
        logger.info(
            "create_member args - group_id=%s user_id=%s recipient_id=%s relationship=%s role=LEADER",
            db_group.id, current_user.id, db_recipient.id, relationship_enum
        )

        try:
            leader_member = await family_member_crud.create_member(
                db=db,
                user_id=current_user.id,
                group_id=db_group.id,
                recipient_id=db_recipient.id,
                relationship=relationship_enum,
                role=MemberRole.LEADER
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        await db.commit()
        await db.refresh(db_group)

        return {
            "message": "가족 그룹이 성공적으로 생성되었습니다",
            "group": {
                "id": str(db_group.id),
                "group_name": db_group.group_name,
                "invite_code": db_group.invite_code,
                "deadline_type": safe_enum_value(db_group.deadline_type),
                "status": safe_enum_value(db_group.status)
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
                "status": safe_enum_value(db_issue.status)
            }
        }

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"가족 그룹 설정 중 오류가 발생했습니다: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"가족 그룹 설정 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/recipient", response_model=RecipientOut)
async def get_my_recipient(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    membership = await family_member_crud.check_user_membership(db, current_user.id)
    if not membership:
        return {"recipient": None, "group_id": None, "message": "속한 가족 그룹이 없습니다"}

    group = await family_group_crud.get(db, membership.group_id)
    if not group:
        return {"recipient": None, "group_id": str(membership.group_id), "message": "가족 그룹을 찾을 수 없습니다"}

    recipient = await recipient_crud.get_by_group_id(db, membership.group_id)
    if not recipient:
        return {"recipient": None, "group_id": str(membership.group_id), "message": "받는 분 정보가 설정되지 않았습니다"}

    recipient_data = {
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

    return {"recipient": recipient_data, "group_id": str(membership.group_id)}

@router.post("/create", response_model=FamilyGroupResponse)
async def create_family_group(
    group_data: FamilyGroupCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    existing_membership = await family_member_crud.check_user_membership(db, current_user.id)
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 다른 가족 그룹에 속해있습니다"
        )

    try:
        db_group = await family_group_crud.create_with_leader(db, group_data, current_user.id)
        
        recipient_data = {
            "name": group_data.recipient_info.name,
            "address": group_data.recipient_info.address,
            "address_detail": group_data.recipient_info.address_detail,
            "postal_code": group_data.recipient_info.postal_code,
            "phone": group_data.recipient_info.phone,
            "group_id": db_group.id
        }
        db_recipient = await recipient_crud.create(db, recipient_data)
        
        if not db_recipient.id:
            raise ValueError("Recipient ID가 생성되지 않았습니다")

        relationship_enum = to_relationship_enum(group_data.leader_relationship)
        
        try:
            leader_member = await family_member_crud.create_member(
                db=db,
                user_id=current_user.id,
                group_id=db_group.id,
                recipient_id=db_recipient.id,
                relationship=relationship_enum,
                role=MemberRole.LEADER
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        await db.commit()
        await db.refresh(db_group)

        return db_group

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"가족 그룹 생성 중 오류가 발생했습니다: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"가족 그룹 생성 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/my-group", response_model=MyGroupOut)
async def get_my_family_group(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    group = await family_group_crud.get_by_user_id(db, current_user.id)
    if not group:
        return {"group": None, "message": "속한 가족 그룹이 없습니다"}
    return {"group": group}

@router.post("/{group_id}/regenerate-invite")
async def regenerate_invite_code(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    member = await family_member_crud.get_by_user_and_group(db, current_user.id, group_id)
    if not member or safe_enum_value(getattr(member, "role", None)) != ROLE_LEADER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="그룹 리더만 초대 코드를 재생성할 수 있습니다"
        )

    new_invite_code = family_group_crud._generate_invite_code()
    group = await family_group_crud.get(db, group_id)
    group.invite_code = new_invite_code
    await db.commit()
    return {"invite_code": new_invite_code}

@router.delete("/my-group")
async def delete_my_family_group(
    force: bool = Query(False, description="배송/제작 진행 중이어도 강제 삭제"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    membership = await family_member_crud.check_user_membership(db, current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="속한 가족 그룹이 없습니다"
        )

    group_id = str(membership.group_id)
    role_value = safe_enum_value(membership.role)
    if role_value != ROLE_LEADER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="그룹 리더만 그룹을 삭제할 수 있습니다"
        )

    pending_books = await book_crud.get_pending_books_by_group(db, group_id)
    has_shipping_or_inprogress = any(
        (b.delivery_status == DeliveryStatus.SHIPPING or b.production_status == ProductionStatus.IN_PROGRESS)
        for b in pending_books
    )

    if has_shipping_or_inprogress and not force:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="배송/제작 진행 중인 책자가 있어 삭제할 수 없습니다. force=true로 강제 삭제 가능합니다."
        )

    try:
        cancel_info = await subscription_admin_service.cancel_active_subscription_if_any(db, group_id)
        await db.commit()

        deleted_subscriptions = await subscription_admin_service.hard_delete_subscription_by_group(db, group_id)
        await db.commit()

        removed = await family_group_crud.remove(db, id=group_id)
        if not removed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="그룹을 찾을 수 없습니다"
            )

        await db.commit()
        logger.info(f"그룹 삭제 완료 - group_id: {group_id}, user_id: {current_user.id}")

        return {
            "message": "가족 그룹이 완전히 삭제되었습니다",
            "subscription_cancel": cancel_info,
            "subscription_deleted": bool(deleted_subscriptions),
            "pending_books_count": len(pending_books)
        }

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"그룹 삭제 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"그룹 삭제 중 오류가 발생했습니다: {str(e)}"
        )
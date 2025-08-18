from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

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
from ...schemas.user import FamilyGroupSetup
from ...services.auth_service import kakao_oauth_service

router = APIRouter(prefix="/family", tags=["family"])

@router.post("/setup", response_model=dict)
async def setup_family_group(
    setup_data: FamilyGroupSetup,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    가족 그룹 초기 설정 (새 사용자용)
    1. 사용자가 이미 다른 그룹에 속해있는지 확인
    2. 가족 그룹 생성 (먼저)
    3. 받는 분 정보 생성 (group_id 포함)
    4. 첫 번째 회차 자동 생성
    5. 리더를 첫 번째 멤버로 추가
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
        # 🔧 2. 가족 그룹 먼저 생성
        group_data = {
            "group_name": setup_data.group_name,
            "leader_id": current_user.id,
            "deadline_type": setup_data.deadline_type,
            "leader_relationship": setup_data.leader_relationship
        }

        db_group = await family_group_crud.create_with_leader(
            db, group_data, current_user.id
        )

        # 🔧 3. 받는 분 정보 생성 (group_id 포함)
        recipient_data = {
            "name": setup_data.recipient_name,
            "address": setup_data.recipient_address,
            "address_detail": setup_data.recipient_address_detail,
            "postal_code": setup_data.recipient_postal_code or "00000",
            "phone": setup_data.recipient_phone or current_user.phone,
            "group_id": db_group.id  # 🔧 group_id 포함해서 생성
        }

        db_recipient = await recipient_crud.create(db, recipient_data)
        
        existing_open_issue = await issue_crud.get_current_issue(db, str(db_group.id))
        if not existing_open_issue:
            deadline_date = calculate_deadline_date(setup_data.deadline_type)
            
            issue_data = {
                "group_id": str(db_group.id),
                "issue_number": 1,
                "deadline_date": deadline_date.date(),
                "status": "OPEN"
            }
            
            db_issue = await issue_crud.create(db, issue_data)
        else:
            db_issue = existing_open_issue

        # 🆕 4. 첫 번째 회차 자동 생성
        from ...crud.issue_crud import issue_crud
        
        # 마감일 계산 함수
        def calculate_deadline_date(deadline_type: str) -> datetime:
            """다음 달의 해당 일요일 계산"""
            now = datetime.now()
            # 다음 달 첫째 날
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.replace(month=now.month + 1, day=1)
            
            # 첫 번째 일요일 찾기
            first_sunday = next_month
            while first_sunday.weekday() != 6:  # 일요일 = 6
                first_sunday += timedelta(days=1)
            
            if deadline_type == "SECOND_SUNDAY":
                return first_sunday + timedelta(days=7)  # 둘째 주 일요일
            else:  # FOURTH_SUNDAY
                return first_sunday + timedelta(days=21)  # 넷째 주 일요일
        
        deadline_date = calculate_deadline_date(setup_data.deadline_type)
        
        # 첫 번째 회차 생성
        issue_data = {
            "group_id": str(db_group.id),
            "issue_number": 1,
            "deadline_date": deadline_date.date(),
            "status": "OPEN"
        }
        
        db_issue = await issue_crud.create(db, issue_data)

        # 5. 리더를 첫 번째 멤버로 추가
        await family_member_crud.create_member(
            db=db,
            user_id=current_user.id,
            group_id=db_group.id,
            recipient_id=db_recipient.id,
            relationship=setup_data.leader_relationship,
            role="LEADER"
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
            "issue": {  # 🆕 생성된 회차 정보 포함
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

# 🆕 받는 분 정보 조회 엔드포인트 - 강화된 오류 처리
@router.get("/recipient", response_model=dict)
async def get_my_recipient(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """현재 사용자가 속한 그룹의 받는 분 정보 조회 - 강화된 오류 처리"""
    
    import logging
    import traceback
    logger = logging.getLogger(__name__)
    
    logger.info(f"받는 분 정보 조회 시작: user_id={current_user.id}")
    
    try:
        # 1단계: 멤버십 확인
        logger.info("1단계: 사용자 멤버십 확인 중...")
        try:
            membership = await family_member_crud.check_user_membership(db, current_user.id)
            if not membership:
                logger.warning(f"멤버십 없음: user_id={current_user.id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="속한 가족 그룹이 없습니다"
                )
            logger.info(f"멤버십 확인 완료: group_id={membership.group_id}")
        except Exception as e:
            logger.error(f"멤버십 확인 중 오류: {str(e)}")
            # 멤버십 확인 실패 시 빈 응답 반환
            return {
                "error": "멤버십 확인 실패",
                "message": "가족 그룹 정보를 확인할 수 없습니다"
            }

        # 2단계: 그룹 정보 조회
        logger.info("2단계: 그룹 정보 조회 중...")
        try:
            group = await family_group_crud.get(db, membership.group_id)
            if not group:
                logger.warning(f"그룹 없음: group_id={membership.group_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="가족 그룹을 찾을 수 없습니다"
                )
            logger.info(f"그룹 확인 완료: group_name={group.group_name}")
        except Exception as e:
            logger.error(f"그룹 조회 중 오류: {str(e)}")
            return {
                "error": "그룹 조회 실패",
                "message": "가족 그룹 정보를 불러올 수 없습니다"
            }

        # 3단계: 받는 분 정보 조회
        logger.info("3단계: 받는 분 정보 조회 중...")
        try:
            # 직접 recipient_crud 사용
            recipient = await recipient_crud.get_by_group_id(db, membership.group_id)
            
            if not recipient:
                logger.warning(f"받는 분 정보 없음: group_id={membership.group_id}")
                return {
                    "error": "받는 분 정보 없음",
                    "message": "받는 분 정보가 설정되지 않았습니다",
                    "group_id": str(membership.group_id)
                }
                
            logger.info(f"받는 분 정보 확인 완료: name={recipient.name}")
            
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
            
        except Exception as e:
            logger.error(f"받는 분 정보 조회 중 오류: {str(e)}")
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return {
                "error": "받는 분 조회 실패",
                "message": f"받는 분 정보 조회 중 오류: {str(e)}",
                "group_id": str(membership.group_id)
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"전체 프로세스 실패: {str(e)}")
        logger.error(f"전체 스택 트레이스: {traceback.format_exc()}")
        
        # 안전한 폴백 응답
        return {
            "error": "시스템 오류",
            "message": "받는 분 정보를 불러오는 중 시스템 오류가 발생했습니다",
            "details": str(e)
        }

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

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from ...database.session import get_db
from ...api.dependencies import get_current_user
from ...models.user import User
from ...crud.family_crud import family_group_crud
from ...crud.issue_crud import issue_crud
from ...crud.book_crud import book_crud
from ...crud.post_crud import post_crud
from ...crud.member_crud import family_member_crud
from ...services.pdf_service import pdf_service
from ...services.subscription_admin_service import subscription_admin_service
from ...schemas.book import BookStatusUpdate
from ...models.book import DeliveryStatus, ProductionStatus
from ...core.config import settings
from ...core.constants import ROLE_LEADER

router = APIRouter(prefix="/admin", tags=["admin"])

async def verify_admin_user(current_user: User = Depends(get_current_user)):
    """관리자 권한 확인"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 사용자입니다"
        )
    
    # 환경변수에서 가져온 관리자 이메일 목록 사용
    if current_user.email not in settings.ADMIN_EMAILS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다"
        )
    
    return current_user

@router.get("/groups")
async def get_all_family_groups(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    _admin_user: User = Depends(verify_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """모든 가족 그룹 목록 조회 (관리자용) - N+1 최적화"""
    result = await family_group_crud.get_all_groups_with_stats(db, skip=skip, limit=limit)
    return result

@router.get("/groups/{group_id}/feed")
async def get_group_feed(
    group_id: str,
    issue_id: Optional[str] = None,
    _admin_user: User = Depends(verify_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """특정 그룹의 피드 조회 (관리자용)"""
    group = await family_group_crud.get_with_relations(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="그룹을 찾을 수 없습니다"
        )

    if not issue_id:
        current_issue = await issue_crud.get_current_issue(db, group_id)
        if not current_issue:
            return {"posts": [], "issue": None}
        issue_id = current_issue.id

    posts = await post_crud.get_posts_by_issue_with_author(db, issue_id)

    return {
        "group_info": {
            "id": group.id,
            "name": group.group_name,
            "recipient_name": group.recipient.name if group.recipient else None
        },
        "issue_id": issue_id,
        "posts": posts
    }

@router.post("/books/generate/{issue_id}")
async def generate_book_pdf(
    issue_id: str,
    _admin_user: User = Depends(verify_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """회차의 책자 PDF 생성 (관리자용)"""
    try:
        pdf_url = await pdf_service.generate_issue_pdf(db, issue_id)
        return {
            "message": "책자 PDF 생성 완료",
            "pdf_url": pdf_url,
            "issue_id": issue_id
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF 생성 중 오류: {str(e)}"
        )

@router.get("/books/pending")
async def get_pending_books(
    _admin_user: User = Depends(verify_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """제작/배송 대기 중인 책자 목록 (관리자용)"""
    pending_books = await book_crud.get_all_pending_books(db)
    return pending_books

@router.put("/books/{book_id}/status")
async def update_book_status(
    book_id: str,
    status_update: BookStatusUpdate,
    _admin_user: User = Depends(verify_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """책자 상태 업데이트 (관리자용)"""
    book = await book_crud.get(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="책자를 찾을 수 없습니다"
        )

    update_data = status_update.dict(exclude_unset=True)
    if status_update.delivery_status == "shipping" and "shipped_at" not in update_data:
        update_data["shipped_at"] = datetime.now()
    elif status_update.delivery_status == "delivered" and "delivered_at" not in update_data:
        update_data["delivered_at"] = datetime.now()

    updated_book = await book_crud.update(db, db_obj=book, obj_in=update_data)
    return updated_book

@router.delete("/groups/{group_id}")
async def admin_delete_group(
    group_id: str,
    force: bool = Query(True, description="배송/제작 진행 중이어도 강제 삭제 (관리자 기본값)"),
    _admin_user: User = Depends(verify_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    관리자용 그룹 삭제
    - 활성 구독 취소 및 환불 시도
    - 구독 데이터 완전 삭제
    - 그룹 및 모든 연관 데이터 삭제
    """
    # 그룹 존재 확인
    group = await family_group_crud.get(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="그룹을 찾을 수 없습니다"
        )

    # 배송/제작 진행 체크 (관리자는 기본 force=True)
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
        # 활성 구독 취소 시도
        cancel_info = await subscription_admin_service.cancel_active_subscription_if_any(db, group_id)
        await db.commit()

        # 구독 물리 삭제
        deleted_subscriptions = await subscription_admin_service.hard_delete_subscription_by_group(db, group_id)
        await db.commit()

        # 그룹 삭제
        removed = await family_group_crud.remove(db, id=group_id)
        if not removed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="그룹 삭제 실패 (이미 삭제되었을 수 있음)"
            )
        await db.commit()

        return {
            "message": f"그룹이 관리자에 의해 삭제되었습니다 (ID: {group_id})",
            "group_name": group.group_name,
            "subscription_cancel": cancel_info,
            "subscription_deleted": bool(deleted_subscriptions),
            "pending_books_count": len(pending_books),
            "admin_email": _admin_user.email
        }
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"관리자 그룹 삭제 중 오류: {str(e)}"
        )

@router.delete("/members/{member_id}")
async def admin_remove_member(
    member_id: str,
    _admin_user: User = Depends(verify_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    관리자용 멤버 삭제
    - 리더 삭제는 정책상 차단 (그룹이 리더 없는 상태가 되는 것을 방지)
    - 일반 멤버는 삭제 허용
    """
    # 멤버 존재 확인
    target_member = await family_member_crud.get(db, member_id)
    if not target_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="멤버를 찾을 수 없습니다"
        )

    # 멤버 정보 조회 (그룹 정보 포함)
    group = await family_group_crud.get(db, target_member.group_id)
    member_role = getattr(target_member, "role", None)
    
    # 리더 삭제 정책상 차단
    if member_role == ROLE_LEADER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"리더 멤버는 관리자 권한으로도 삭제할 수 없습니다. 그룹 삭제를 사용해주세요. (그룹: {group.group_name if group else 'Unknown'})"
        )

    try:
        # 멤버 삭제
        removed = await family_member_crud.remove(db, id=member_id)
        if not removed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="멤버 삭제 실패"
            )
        await db.commit()
        
        return {
            "message": "멤버가 관리자에 의해 삭제되었습니다",
            "member_id": member_id,
            "group_name": group.group_name if group else "Unknown",
            "admin_email": _admin_user.email
        }
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"관리자 멤버 삭제 중 오류: {str(e)}"
        )

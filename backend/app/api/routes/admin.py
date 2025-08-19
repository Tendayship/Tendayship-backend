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
from ...services.pdf_service import pdf_service
from ...schemas.book import BookResponse, BookStatusUpdate
from ...core.constants import ADMIN_EMAILS

router = APIRouter(prefix="/admin", tags=["admin"])

async def verify_admin_user(current_user: User = Depends(get_current_user)):
    """관리자 권한 확인 - 활성화 상태 및 관리자 이메일 체크"""
    
    # 1. 사용자 활성화 상태 체크
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 사용자입니다"
        )
    
    # 2. 사용자 삭제 상태 체크 (is_deleted가 있다면)
    if hasattr(current_user, 'is_deleted') and current_user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="삭제된 사용자입니다"
        )
    
    # 3. 관리자 권한 체크
    if current_user.email not in ADMIN_EMAILS:
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

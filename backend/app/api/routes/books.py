from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...database.session import get_db
from ...api.dependencies import get_current_user
from ...models.user import User
from ...crud.book_crud import book_crud
from ...crud.member_crud import family_member_crud
from ...services.pdf_service import pdf_service
from ...schemas.book import BookResponse
from ...core.constants import ROLE_LEADER
from ...core.config import settings

router = APIRouter(prefix="/books", tags=["books"])

@router.get("/", response_model=List[BookResponse])
async def get_my_books(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """내가 속한 그룹의 책자 목록 조회"""
    
    # 사용자의 그룹 멤버십 확인
    membership = await family_member_crud.check_user_membership(
        db, current_user.id
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="속한 가족 그룹이 없습니다"
        )
    
    # 그룹의 책자 목록 조회
    books = await book_crud.get_books_by_group(db, membership.group_id)
    
    # 응답 데이터에 추가 정보 포함
    result = []
    for book in books:
        issue = getattr(book, "issue", None)
        post_count = len(issue.posts) if issue and issue.posts else 0
        book_data = {
            "id": book.id,
            "issue_id": book.issue_id,
            "pdf_url": book.pdf_url,
            "production_status": book.production_status,
            "delivery_status": book.delivery_status,
            "created_at": book.created_at,
            "updated_at": book.updated_at,
            "issue_number": issue.issue_number if issue else None,
            "issue_deadline": issue.deadline_date if issue else None,
            "post_count": post_count,
        }
        result.append(BookResponse(**book_data))
    
    return result

@router.get("/{book_id}", response_model=BookResponse)
async def get_book_detail(
    book_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """책자 상세 정보 조회"""
    
    book = await book_crud.get_with_issue(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="책자를 찾을 수 없습니다"
        )
    
    issue = getattr(book, "issue", None)
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="책자에 연결된 회차 정보가 없습니다"
        )
    
    # 권한 확인 - 해당 그룹 멤버인지 확인
    membership = await family_member_crud.get_by_user_and_group(
        db, current_user.id, issue.group_id
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 책자에 접근할 권한이 없습니다"
        )
    
    book_data = {
        "id": book.id,
        "issue_id": book.issue_id,
        "pdf_url": book.pdf_url,
        "production_status": book.production_status,
        "delivery_status": book.delivery_status,
        "created_at": book.created_at,
        "updated_at": book.updated_at,
        "issue_number": issue.issue_number,
        "issue_deadline": issue.deadline_date,
        "post_count": len(issue.posts) if issue.posts else 0,
    }
    
    return BookResponse(**book_data)

@router.get("/{book_id}/download")
async def download_book_pdf(
    book_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """책자 PDF 다운로드 (SAS URL 리다이렉트)"""
    
    book = await book_crud.get_with_issue(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="책자를 찾을 수 없습니다"
        )
    
    if not book.pdf_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="아직 제작되지 않은 책자입니다"
        )
    
    issue = getattr(book, "issue", None)
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="책자에 연결된 회차 정보가 없습니다"
        )
    
    # 권한 확인
    membership = await family_member_crud.get_by_user_and_group(
        db, current_user.id, issue.group_id
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 책자에 접근할 권한이 없습니다"
        )
    
    # URL 스킴 검증
    url = book.pdf_url
    if not (str(url).startswith("http://") or str(url).startswith("https://")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 PDF URL입니다"
        )
    
    # Azure Blob Storage SAS URL로 리다이렉트
    return RedirectResponse(url=str(url))

@router.post("/{book_id}/regenerate")
async def regenerate_book_pdf(
    book_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """책자 PDF 재생성 (관리자 또는 그룹 리더만 가능)"""
    
    book = await book_crud.get_with_issue(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="책자를 찾을 수 없습니다"
        )
    
    issue = getattr(book, "issue", None)
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="책자에 연결된 회차 정보가 없습니다"
        )
    
    # 권한 확인 - 그룹 리더 또는 관리자
    membership = await family_member_crud.get_by_user_and_group(
        db, current_user.id, issue.group_id
    )
    is_leader = bool(membership and (getattr(membership.role, "value", str(membership.role)) == ROLE_LEADER))
    is_admin = current_user.email in settings.ADMIN_EMAILS
    
    if not (is_leader or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="그룹 리더 또는 관리자만 책자를 재생성할 수 있습니다"
        )
    
    try:
        new_pdf_url = await pdf_service.regenerate_pdf(db, book_id)
        await db.commit()
        return {
            "message": "책자 PDF 재생성 완료",
            "pdf_url": new_pdf_url
        }
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF 재생성 중 오류: {str(e)}"
        )

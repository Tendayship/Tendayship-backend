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
        book_data = {
            "id": book.id,
            "issue_id": book.issue_id,
            "pdf_url": book.pdf_url,
            "status": book.status,
            "delivery_status": book.delivery_status,
            "created_at": book.created_at,
            "updated_at": book.updated_at,
            "issue_number": book.issue.issue_number,
            "issue_deadline": book.issue.deadline_date,
            "post_count": len(book.issue.posts) if book.issue.posts else 0
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
    
    book = await book_crud.get(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="책자를 찾을 수 없습니다"
        )
    
    # 권한 확인 - 해당 그룹 멤버인지 확인
    membership = await family_member_crud.get_by_user_and_group(
        db, current_user.id, book.issue.group_id
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
        "status": book.status,
        "delivery_status": book.delivery_status,
        "created_at": book.created_at,
        "updated_at": book.updated_at,
        "issue_number": book.issue.issue_number,
        "issue_deadline": book.issue.deadline_date,
        "post_count": len(book.issue.posts) if book.issue.posts else 0
    }
    
    return BookResponse(**book_data)

@router.get("/{book_id}/download")
async def download_book_pdf(
    book_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """책자 PDF 다운로드 (SAS URL 리다이렉트)"""
    
    book = await book_crud.get(db, book_id)
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
    
    # 권한 확인
    membership = await family_member_crud.get_by_user_and_group(
        db, current_user.id, book.issue.group_id
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 책자에 접근할 권한이 없습니다"
        )
    
    # Azure Blob Storage SAS URL로 리다이렉트
    return RedirectResponse(url=book.pdf_url)

@router.post("/{book_id}/regenerate")
async def regenerate_book_pdf(
    book_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """책자 PDF 재생성 (관리자 또는 그룹 리더만 가능)"""
    
    book = await book_crud.get(db, book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="책자를 찾을 수 없습니다"
        )
    
    # 권한 확인 - 그룹 리더 또는 관리자
    membership = await family_member_crud.get_by_user_and_group(
        db, current_user.id, book.issue.group_id
    )
    if not membership or membership.role != ROLE_LEADER:
        # TODO: 관리자 권한도 확인
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="그룹 리더만 책자를 재생성할 수 있습니다"
        )
    
    try:
        new_pdf_url = await pdf_service.regenerate_pdf(db, book_id)
        return {
            "message": "책자 PDF 재생성 완료",
            "pdf_url": new_pdf_url
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF 재생성 중 오류: {str(e)}"
        )

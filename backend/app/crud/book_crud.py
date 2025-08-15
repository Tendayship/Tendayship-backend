from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload, joinedload
from datetime import datetime

from .base import BaseCRUD
from ..models.book import Book, ProductionStatus, DeliveryStatus
from ..models.issue import Issue
from ..schemas.book import BookCreate, BookStatusUpdate

class BookCRUD(BaseCRUD[Book, BookCreate, dict]):
    
    async def get_by_issue_id(
        self,
        db: AsyncSession,
        issue_id: str
    ) -> Optional[Book]:
        """회차 ID로 책자 조회"""
        result = await db.execute(
            select(Book)
            .where(Book.issue_id == issue_id)
            .options(
                joinedload(Book.issue).joinedload(Issue.group),
                joinedload(Book.issue).joinedload(Issue.posts)
            )
        )
        return result.scalars().first()
    
    async def get_books_by_group(
        self,
        db: AsyncSession,
        group_id: str,
        limit: int = 10
    ) -> List[Book]:
        """그룹의 책자 목록 조회"""
        result = await db.execute(
            select(Book)
            .join(Issue)
            .where(Issue.group_id == group_id)
            .options(
                selectinload(Book.issue).selectinload(Issue.posts)
            )
            .order_by(Book.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_pending_books_by_group(
        self,
        db: AsyncSession,
        group_id: str
    ) -> List[Book]:
        """그룹의 미완료 책자 조회"""
        result = await db.execute(
            select(Book)
            .join(Issue)
            .where(
                and_(
                    Issue.group_id == group_id,
                    or_(
                        Book.production_status != ProductionStatus.COMPLETED,
                        Book.delivery_status != DeliveryStatus.DELIVERED
                    )
                )
            )
            .options(joinedload(Book.issue))
        )
        return result.scalars().all()
    
    async def get_all_pending_books(
        self,
        db: AsyncSession
    ) -> List[Book]:
        """전체 미완료 책자 조회 (관리자용)"""
        result = await db.execute(
            select(Book)
            .where(
                or_(
                    Book.production_status != ProductionStatus.COMPLETED,
                    Book.delivery_status != DeliveryStatus.DELIVERED
                )
            )
            .options(
                joinedload(Book.issue).joinedload(Issue.group).joinedload(Issue.group.recipient)
            )
            .order_by(Book.created_at.desc())
        )
        return result.scalars().all()
    
    async def update_production_status(
        self,
        db: AsyncSession,
        book_id: str,
        status: ProductionStatus,
        pdf_url: Optional[str] = None
    ) -> Book:
        """제작 상태 업데이트"""
        book = await self.get(db, book_id)
        if book:
            book.production_status = status
            if pdf_url:
                book.pdf_url = pdf_url
            if status == ProductionStatus.COMPLETED:
                book.produced_at = datetime.now()
            await db.commit()
            await db.refresh(book)
        return book

# 싱글톤 인스턴스
book_crud = BookCRUD(Book)

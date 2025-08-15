from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload
from datetime import datetime

from .base import BaseCRUD
from ..models.issue import Issue, IssueStatus
from ..schemas.issue import IssueCreate

class IssueCRUD(BaseCRUD[Issue, dict, dict]):
    
    async def get_current_issue(
        self,
        db: AsyncSession,
        group_id: str
    ) -> Optional[Issue]:
        """현재 활성 회차 조회"""
        result = await db.execute(
            select(Issue)
            .where(
                and_(
                    Issue.group_id == group_id,
                    Issue.status == IssueStatus.OPEN
                )
            )
            .options(selectinload(Issue.posts))
            .order_by(desc(Issue.created_at))
        )
        return result.scalars().first()
    
    async def get_by_group(
        self,
        db: AsyncSession,
        group_id: str,
        limit: int = 10
    ) -> List[Issue]:
        """그룹의 회차 목록 조회"""
        result = await db.execute(
            select(Issue)
            .where(Issue.group_id == group_id)
            .order_by(desc(Issue.created_at))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def close_issue(
        self,
        db: AsyncSession,
        issue_id: str
    ) -> Issue:
        """회차 마감 처리"""
        issue = await self.get(db, issue_id)
        if issue:
            issue.status = IssueStatus.CLOSED
            issue.closed_at = datetime.now()
            await db.commit()
        return issue

# 싱글톤 인스턴스
issue_crud = IssueCRUD(Issue)

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from datetime import datetime, date
from ..models.issue import Issue, IssueStatus

class IssueCRUD:
    """회차 관련 CRUD 작업"""

    async def create(self, db: AsyncSession, obj_in: dict) -> Issue:
        """새 회차 생성"""
        try:
            db_obj = Issue(
                group_id=obj_in["group_id"],
                issue_number=obj_in["issue_number"],
                deadline_date=datetime.strptime(obj_in["deadline_date"], "%Y-%m-%d").date() if isinstance(obj_in["deadline_date"], str) else obj_in["deadline_date"],
                status=IssueStatus.OPEN,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            return db_obj
            
        except Exception as e:
            await db.rollback()
            raise e

    async def get(self, db: AsyncSession, id: str) -> Optional[Issue]:
        """ID로 회차 조회"""
        try:
            result = await db.execute(
                select(Issue).where(Issue.id == id)
            )
            return result.scalars().first()
            
        except Exception as e:
            return None

    async def get_current_issue(self, db: AsyncSession, group_id: str) -> Optional[Issue]:
        """그룹의 현재 진행 중인 회차 조회 (안전한 버전)"""
        try:
            result = await db.execute(
                select(Issue)
                .where(
                    and_(
                        Issue.group_id == group_id,
                        Issue.status == IssueStatus.OPEN
                    )
                )
                .order_by(desc(Issue.created_at))
                .limit(1)
            )
            return result.scalars().first()
            
        except Exception as e:
            print(f"현재 회차 조회 오류: {str(e)}")
            return None

    async def get_issues_by_group(self, db: AsyncSession, group_id: str, skip: int = 0, limit: int = 100) -> List[Issue]:
        """그룹의 모든 회차 목록 조회"""
        try:
            result = await db.execute(
                select(Issue)
                .where(Issue.group_id == group_id)
                .order_by(desc(Issue.issue_number))
                .offset(skip)
                .limit(limit)
            )
            return result.scalars().all()
            
        except Exception as e:
            return []

    async def update(self, db: AsyncSession, db_obj: Issue, obj_in: dict) -> Issue:
        """회차 정보 업데이트"""
        try:
            update_data = obj_in if isinstance(obj_in, dict) else obj_in.dict(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)
            db_obj.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(db_obj)
            return db_obj
            
        except Exception as e:
            await db.rollback()
            raise e

    async def close_issue(self, db: AsyncSession, issue_id: str) -> Issue:
        """회차 마감"""
        try:
            issue = await self.get(db, issue_id)
            if not issue:
                raise ValueError(f"Issue with id {issue_id} not found")
            issue.status = IssueStatus.CLOSED
            issue.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(issue)
            return issue
            
        except Exception as e:
            await db.rollback()
            raise e

    async def delete(self, db: AsyncSession, id: str) -> bool:
        """회차 삭제"""
        try:
            issue = await self.get(db, id)
            if not issue:
                return False
            await db.delete(issue)
            await db.commit()
            return True
            
        except Exception as e:
            await db.rollback()
            raise e

    async def count_posts_by_issue(self, db: AsyncSession, issue_id: str) -> int:
        """회차별 소식 개수 조회"""
        try:
            from ..models.post import Post
            result = await db.execute(
                select(Post).where(Post.issue_id == issue_id)
            )
            posts = result.scalars().all()
            return len(posts)
            
        except Exception as e:
            return 0

# 싱글톤 인스턴스 생성
issue_crud = IssueCRUD()

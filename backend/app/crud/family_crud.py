from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, case
from sqlalchemy.orm import selectinload, joinedload
import secrets
import string

from .base import BaseCRUD
from ..models.family import FamilyGroup, FamilyMember
from ..models.issue import Issue, IssueStatus
from ..models.book import Book, ProductionStatus, DeliveryStatus
from ..models.post import Post
from ..schemas.family import FamilyGroupCreate
from ..core.constants import GROUP_STATUS_ACTIVE

class FamilyGroupCRUD(BaseCRUD[FamilyGroup, dict, dict]):
    
    async def create_with_leader(
        self, 
        db: AsyncSession, 
        group_data: dict, 
        leader_id: str
    ) -> FamilyGroup: 
        """리더와 함께 가족 그룹 생성"""
        
        # 초대 코드 생성
        invite_code = self._generate_invite_code()
        
        # 가족 그룹 생성
        db_group = FamilyGroup(
            group_name=group_data["group_name"],
            leader_id=leader_id,
            invite_code=invite_code,
            deadline_type=group_data["deadline_type"],
            status=GROUP_STATUS_ACTIVE
        )
        
        db.add(db_group)
        # Transaction management moved to upper layer
        return db_group 
    
    async def get_by_invite_code(
        self, 
        db: AsyncSession, 
        invite_code: str
    ) -> Optional[FamilyGroup]:
        """초대 코드로 활성 그룹 조회"""
        result = await db.execute(
            select(FamilyGroup)
            .where(
                and_(
                    FamilyGroup.invite_code == invite_code,
                    FamilyGroup.status == GROUP_STATUS_ACTIVE
                )
            )
            .options(selectinload(FamilyGroup.recipient))
        )
        return result.scalars().first()
    
    async def get_by_user_id(
        self, 
        db: AsyncSession, 
        user_id: str
    ) -> Optional[FamilyGroup]:
        """사용자가 속한 그룹 조회"""
        result = await db.execute(
            select(FamilyGroup)
            .join(FamilyMember)
            .where(FamilyMember.user_id == user_id)
            .options(
                selectinload(FamilyGroup.members),
                selectinload(FamilyGroup.recipient)
            )
        )
        return result.scalars().first()
    
    async def get_all_groups_with_stats(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 20
    ) -> List[dict]:
        """모든 가족 그룹을 통계 정보와 함께 조회 (N+1 최적화)"""
        
        # 1. 기본 그룹 정보 조회 (joinedload 사용)
        groups_query = (
            select(FamilyGroup)
            .options(
                joinedload(FamilyGroup.leader),
                joinedload(FamilyGroup.recipient),
                selectinload(FamilyGroup.members)
            )
            .offset(skip)
            .limit(limit)
        )
        
        result = await db.execute(groups_query)
        groups = result.scalars().unique().all()
        
        if not groups:
            return []
        
        group_ids = [str(group.id) for group in groups]
        
        # 2. 현재 활성 회차 조회 (한 번의 쿼리로 모든 그룹)
        current_issues_query = (
            select(Issue)
            .where(
                and_(
                    Issue.group_id.in_(group_ids),
                    Issue.status == IssueStatus.OPEN
                )
            )
        )
        current_issues_result = await db.execute(current_issues_query)
        current_issues = {str(issue.group_id): issue for issue in current_issues_result.scalars().all()}
        
        # 3. 회차별 포스트 수 집계 (현재 활성 회차만)
        issue_ids = [issue.id for issue in current_issues.values()]
        posts_count = {}
        if issue_ids:
            posts_count_query = (
                select(
                    Post.issue_id,
                    func.count(Post.id).label('post_count')
                )
                .where(Post.issue_id.in_([str(issue_id) for issue_id in issue_ids]))
                .group_by(Post.issue_id)
            )
            posts_count_result = await db.execute(posts_count_query)
            posts_count = {str(row.issue_id): row.post_count for row in posts_count_result.fetchall()}
        
        # 4. 그룹별 미완료 책자 수 집계 (한 번의 쿼리로 모든 그룹)
        pending_books_query = (
            select(
                Issue.group_id,
                func.count(Book.id).label('pending_books_count')
            )
            .select_from(Book)
            .join(Issue, Book.issue_id == Issue.id)
            .where(
                and_(
                    Issue.group_id.in_(group_ids),
                    Book.status != ProductionStatus.COMPLETED,
                    Book.delivery_status != DeliveryStatus.DELIVERED
                )
            )
            .group_by(Issue.group_id)
        )
        pending_books_result = await db.execute(pending_books_query)
        pending_books_count = {str(row.group_id): row.pending_books_count for row in pending_books_result.fetchall()}
        
        # 5. 결과 조합
        groups_data = []
        for group in groups:
            group_id_str = str(group.id)
            current_issue = current_issues.get(group_id_str)
            current_issue_posts = 0
            if current_issue:
                current_issue_posts = posts_count.get(str(current_issue.id), 0)
            
            groups_data.append({
                "id": group.id,
                "group_name": group.group_name,
                "leader_name": group.leader.name if group.leader else None,
                "member_count": len(group.members) if group.members else 0,
                "recipient_name": group.recipient.name if group.recipient else None,
                "current_issue_id": current_issue.id if current_issue else None,
                "current_issue_posts": current_issue_posts,
                "pending_books_count": pending_books_count.get(group_id_str, 0),
                "created_at": group.created_at,
                "status": group.status
            })
        
        return groups_data

    def _generate_invite_code(self) -> str:
        """8자리 초대 코드 생성 (대문자+숫자)"""
        return ''.join(secrets.choice(string.ascii_uppercase + string.digits) 
                      for _ in range(8))

# 싱글톤 인스턴스
family_group_crud = FamilyGroupCRUD(FamilyGroup)

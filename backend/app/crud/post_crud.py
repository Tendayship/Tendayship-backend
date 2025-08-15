from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import selectinload, joinedload

from .base import BaseCRUD
from ..models.post import Post
from ..models.user import User
from ..schemas.post import PostCreate, PostUpdate

class PostCRUD(BaseCRUD[Post, PostCreate, PostUpdate]):
    
    async def create_post(
        self,
        db: AsyncSession,
        post_data: PostCreate,
        author_id: str,
        issue_id: str
    ) -> Post:
        """새 소식 작성"""
        db_post = Post(
            issue_id=issue_id,
            author_id=author_id,
            content=post_data.content,
            image_urls=post_data.images
        )
        
        db.add(db_post)
        await db.commit()
        await db.refresh(db_post)
        return db_post
    
    async def get_posts_by_issue(
        self,
        db: AsyncSession,
        issue_id: str,
        skip: int = 0,
        limit: int = 20
    ) -> List[Post]:
        """회차별 소식 목록 조회 (작성자 정보 포함)"""
        result = await db.execute(
            select(Post)
            .where(Post.issue_id == issue_id)
            .options(
                selectinload(Post.author).selectinload(User.family_members)
            )
            .order_by(desc(Post.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_posts_by_group(
        self,
        db: AsyncSession,
        group_id: str,
        issue_ids: List[str],
        skip: int = 0,
        limit: int = 20
    ) -> List[Post]:
        """그룹의 여러 회차 소식 조회"""
        result = await db.execute(
            select(Post)
            .where(Post.issue_id.in_(issue_ids))
            .options(
                joinedload(Post.author),
                selectinload(Post.author).selectinload(User.family_members)
            )
            .order_by(desc(Post.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def count_posts_by_issue(
        self,
        db: AsyncSession,
        issue_id: str
    ) -> int:
        """회차별 소식 개수"""
        result = await db.execute(
            select(func.count(Post.id))
            .where(Post.issue_id == issue_id)
        )
        return result.scalar()
    
    async def get_user_posts_in_issue(
        self,
        db: AsyncSession,
        issue_id: str,
        author_id: str
    ) -> List[Post]:
        """특정 사용자의 회차내 소식 목록"""
        result = await db.execute(
            select(Post)
            .where(
                and_(
                    Post.issue_id == issue_id,
                    Post.author_id == author_id
                )
            )
            .order_by(desc(Post.created_at))
        )
        return result.scalars().all()

# 싱글톤 인스턴스
post_crud = PostCRUD(Post)

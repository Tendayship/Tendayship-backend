from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import joinedload

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
        try:
            # 🔧 안전한 image_urls 접근
            image_urls = getattr(post_data, 'image_urls', [])
            if image_urls is None:
                image_urls = []
            
            db_post = Post(
                issue_id=issue_id,
                author_id=author_id,
                content=post_data.content,
                image_urls=image_urls
            )
            
            db.add(db_post)
            await db.commit()
            await db.refresh(db_post)
            return db_post
            
        except Exception as e:
            await db.rollback()
            print(f"소식 작성 오류: {str(e)}")
            raise e

    async def get_posts_by_issue(
        self,
        db: AsyncSession,
        issue_id: str,
        skip: int = 0,
        limit: int = 20
    ) -> List[Post]:
        """회차별 소식 목록 조회"""
        try:
            result = await db.execute(
                select(Post)
                .where(Post.issue_id == issue_id)
                .options(joinedload(Post.author))
                .order_by(desc(Post.created_at))
                .offset(skip)
                .limit(limit)
                .distinct()
            )
            return result.scalars().unique().all()
            
        except Exception as e:
            print(f"소식 목록 조회 오류: {str(e)}")
            return []

    async def count_posts_by_issue(
        self,
        db: AsyncSession,
        issue_id: str
    ) -> int:
        """회차별 소식 개수"""
        try:
            result = await db.execute(
                select(func.count(Post.id.distinct()))
                .where(Post.issue_id == issue_id)
            )
            return result.scalar() or 0
            
        except Exception as e:
            print(f"소식 개수 조회 오류: {str(e)}")
            return 0

    async def get_posts_by_group(
        self,
        db: AsyncSession,
        group_id: str,
        issue_ids: List[str],
        skip: int = 0,
        limit: int = 20
    ) -> List[Post]:
        """그룹의 여러 회차 소식 조회"""
        try:
            result = await db.execute(
                select(Post)
                .where(Post.issue_id.in_(issue_ids))
                .options(joinedload(Post.author))
                .order_by(desc(Post.created_at))
                .offset(skip)
                .limit(limit)
            )
            return result.scalars().unique().all()
            
        except Exception as e:
            return []

    async def get_user_posts_in_issue(
        self,
        db: AsyncSession,
        issue_id: str,
        author_id: str
    ) -> List[Post]:
        """특정 사용자의 회차내 소식 목록"""
        try:
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
            
        except Exception as e:
            return []

# 싱글톤 인스턴스
post_crud = PostCRUD(Post)

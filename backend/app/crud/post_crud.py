import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import joinedload

from .base import BaseCRUD
from ..models.post import Post
from ..schemas.post import PostCreate, PostUpdate
from ..models.issue import Issue

logger = logging.getLogger(__name__)

class PostCRUD(BaseCRUD[Post, PostCreate, PostUpdate]):
 
    async def create_post(
        self,
        db: AsyncSession,
        post_data: PostCreate,
        author_id: str,
        issue_id: str,
        image_urls: List[str] = None,
        image_blob_keys: List[str] = None
    ) -> Post:
        """새 소식 작성 (텍스트 선택, 이미지 필수)"""
        
        # 이미지 URL 처리 (필수)
        if image_urls is None:
            image_urls = getattr(post_data, 'image_urls', [])
        
        if not image_urls:
            raise ValueError("최소 1장의 이미지가 필요합니다")
        
        # 이미지 blob keys 처리
        if image_blob_keys is None:
            image_blob_keys = getattr(post_data, 'image_blob_keys', [])
            if image_blob_keys is None:
                image_blob_keys = []
        
        # 텍스트 내용 처리 (선택)
        content = getattr(post_data, 'content', None)
        if content:
            content = content.strip()
            # 최대 100자 검증 (스키마에서 이미 처리되지만 추가 확인)
            if len(content) > 100:
                raise ValueError(f"소식 내용은 최대 100자까지 가능합니다 (현재: {len(content)}자)")
        
        # Post 생성
        db_post = Post(
            issue_id=issue_id,
            author_id=author_id,
            content=content,  # None일 수 있음
            image_urls=image_urls,
            image_blob_keys=image_blob_keys
        )
        
        db.add(db_post)
        # Transaction management moved to upper layer
        logger.info(f"소식 생성: author_id={author_id}, issue_id={issue_id}, has_content={bool(content)}, image_count={len(image_urls)}")
        
        return db_post

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
            posts = result.scalars().unique().all()
            
            # 로깅 추가
            for post in posts:
                logger.debug(f"Post {post.id}: content={'있음' if post.content else '없음'}, images={len(post.image_urls or [])}")
            
            return posts
            
        except Exception as e:
            logger.error(f"회차별 소식 조회 실패: {str(e)}")
            raise e

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
            logger.error(f"소식 개수 조회 실패: {str(e)}")
            raise e

    async def validate_post_content(
        self,
        content: Optional[str],
        image_urls: List[str]
    ) -> tuple[bool, Optional[str]]:
        """소식 내용 검증 (새 요구사항)"""
        
        # 이미지 필수 검증
        if not image_urls or len(image_urls) == 0:
            return False, "최소 1장의 이미지가 필요합니다"
        
        if len(image_urls) > 4:
            return False, "최대 4장의 이미지만 업로드 가능합니다"
        
        # 텍스트 선택 검증
        if content is not None:
            content = content.strip()
            if len(content) > 100:
                return False, f"소식 내용은 최대 100자까지 가능합니다 (현재: {len(content)}자)"
        
        return True, None

    async def get_posts_by_group(
        self,
        db: AsyncSession,
        group_id: str,
        issue_ids: List[str],
        skip: int = 0,
        limit: int = 20
    ) -> List[Post]:
        """그룹의 여러 회차 소식 조회 - 보안 검증 포함"""
        try:
            # 1. issue_ids가 해당 group_id에 속하는지 검증
            if issue_ids:
                verification_result = await db.execute(
                    select(Issue.id)
                    .where(
                        and_(
                            Issue.id.in_(issue_ids),
                            Issue.group_id == group_id
                        )
                    )
                )
                verified_issue_ids = [str(issue_id) for issue_id in verification_result.scalars().all()]
                
                # 검증 실패 시 빈 리스트 반환
                if not verified_issue_ids:
                    logger.warning(f"그룹 {group_id}에 속하지 않는 회차 ID가 포함되어 있습니다")
                    return []
                
                # 검증된 issue_ids만 사용
                final_issue_ids = verified_issue_ids
            else:
                # issue_ids가 비어있으면 해당 그룹의 모든 이슈 조회
                group_issues_result = await db.execute(
                    select(Issue.id)
                    .where(Issue.group_id == group_id)
                    .order_by(desc(Issue.created_at))
                )
                final_issue_ids = [str(issue_id) for issue_id in group_issues_result.scalars().all()]
                
                if not final_issue_ids:
                    return []

            # 2. 검증된 issue_ids로 포스트 조회
            result = await db.execute(
                select(Post)
                .where(Post.issue_id.in_(final_issue_ids))
                .options(joinedload(Post.author))
                .order_by(desc(Post.created_at))
                .offset(skip)
                .limit(limit)
            )
            return result.scalars().unique().all()
            
        except Exception as e:
            logger.error(f"get_posts_by_group 오류: {str(e)}")
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
            logger.error(f"사용자 소식 조회 실패: {str(e)}")
            return []
    
    async def delete(self, db: AsyncSession, post_id: str):
        """게시글(Post) DB에서 삭제"""
        post = await db.get(Post, post_id)
        if post is None:
            return False
        
        logger.info(f"소식 삭제: post_id={post_id}, had_content={bool(post.content)}, image_count={len(post.image_urls or [])}")
        
        await db.delete(post)
        await db.commit()
        return True
    
    async def get_posts_by_issue_with_author(self, db: AsyncSession, issue_id: str, limit: int = 20, offset: int = 0):
        """이슈의 포스트를 작성자 정보와 함께 조회 (관리자용 피드에서 사용)"""
        result = await db.execute(
            select(Post)
            .where(Post.issue_id == issue_id)
            .options(joinedload(Post.author))
            .order_by(Post.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        posts = result.scalars().all()
        
        # 디버깅 정보
        for post in posts:
            logger.debug(f"Admin view - Post {post.id}: content={'있음' if post.content else '없음'}, images={len(post.image_urls or [])}")
        
        return posts

# 싱글톤 인스턴스
post_crud = PostCRUD(Post)
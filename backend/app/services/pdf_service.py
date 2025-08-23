from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from datetime import datetime
import logging

from ..utils.pdf_utils import pdf_generator
from ..utils.azure_storage import get_storage_service
from ..crud.book_crud import book_crud
from ..models.book import ProductionStatus
from ..models.issue import Issue
from ..models.post import Post
from ..models.family import FamilyGroup
from ..models.user import User

logger = logging.getLogger(__name__)

class PDFGenerationService:
    """PDF 생성 서비스"""

    async def generate_issue_pdf(
        self,
        db: AsyncSession,
        issue_id: str
    ) -> str:
        """회차별 소식을 PDF로 생성하고 업로드"""
        try:
            # 1. 회차 정보 + 그룹 + 받는 분 recipient 미리 로드
            issue_result = await db.execute(
                select(Issue)
                .where(Issue.id == issue_id)
                .options(
                    joinedload(Issue.group).joinedload(FamilyGroup.recipient)
                )
            )
            issue = issue_result.scalars().first()
            if not issue:
                raise ValueError(f"회차를 찾을 수 없습니다: {issue_id}")

            # 2. 회차의 모든 소식 + 작성자 + 작성자의 가족 멤버(관계) 미리 로드
            posts_result = await db.execute(
                select(Post)
                .where(Post.issue_id == issue_id)
                .options(
                    joinedload(Post.author)
                    .selectinload(User.family_members)  # 작성자의 가족 멤버 목록
                )
                .order_by(Post.created_at.desc())
            )
            posts = posts_result.scalars().unique().all()
            
            # 소식이 없어도 진행 (빈 책자 생성 가능)
            logger.info(f"회차 {issue_id}에 {len(posts)}개의 소식이 있습니다.")

            # 3. 받는 분 검증 (이미 eager load 되었음)
            recipient = issue.group.recipient if issue.group else None
            if not recipient:
                raise ValueError(f"받는 분 정보가 없습니다: {issue.group_id}")

            # 4. 소식 데이터 준비 (DB IO 없이 메모리 접근만)
            post_data = []
            for post in posts:
                # 작성자의 그룹 내 관계 추출 (이미 author.family_members 로드됨)
                author_member = None
                if post.author and getattr(post.author, "family_members", None):
                    author_member = next(
                        (m for m in post.author.family_members if str(m.group_id) == str(issue.group_id)),
                        None
                    )

                # 관계 정보 추출
                relationship = "가족"
                if author_member:
                    if hasattr(author_member, "member_relationship"):
                        rel = author_member.member_relationship
                        if hasattr(rel, "value"):
                            relationship = rel.value
                        else:
                            relationship = str(rel)

                # 작성자 이름 추출
                author_name = "작성자"
                if post.author:
                    author_name = getattr(post.author, "name", "작성자")

                # 게시물 데이터 구성 (프로필 이미지 제외)
                post_item = {
                    'content': post.content,  # None일 수 있음 (텍스트 선택)
                    'image_urls': post.image_urls or [],  # 최소 1장은 보장됨
                    'created_at': post.created_at,
                    'author_name': author_name,
                    'author_relationship': relationship
                    # 'author_profile_image' 제외
                }
                post_data.append(post_item)

            # 5. PDF 생성
            if not post_data:
                # 소식이 없는 경우 빈 페이지 생성
                logger.warning(f"회차 {issue_id}에 소식이 없습니다. 빈 PDF를 생성합니다.")
                post_data = [{
                    'content': '이번 회차에는 아직 소식이 없습니다.',
                    'image_urls': [],
                    'created_at': datetime.now(),
                    'author_name': '시스템',
                    'author_relationship': '관리자'
                }]

            pdf_bytes = pdf_generator.generate_pdf(
                recipient_name=recipient.name,
                issue_number=issue.issue_number,
                deadline_date=issue.deadline_date,
                posts=post_data
            )

            # 6. Azure Blob Storage에 업로드
            storage_service = get_storage_service()
            pdf_url = storage_service.upload_book_pdf(
                str(issue.group_id),
                str(issue_id),
                pdf_bytes,
                f"book_{issue.issue_number}.pdf"
            )

            # 7. 책자 레코드 생성/업데이트
            existing_book = await book_crud.get_by_issue_id(db, issue_id)
            if existing_book:
                # 기존 책자 업데이트
                existing_book.pdf_url = pdf_url
                existing_book.production_status = ProductionStatus.COMPLETED
                existing_book.produced_at = datetime.now()
                await db.commit()
                book_id = existing_book.id
                logger.info(f"기존 책자 업데이트: book_id={book_id}")
            else:
                # 새 책자 생성
                book_data = {
                    'issue_id': issue_id,
                    'pdf_url': pdf_url,
                    'production_status': ProductionStatus.COMPLETED,
                    'produced_at': datetime.now()
                }
                new_book = await book_crud.create(db, book_data)
                await db.commit()
                book_id = new_book.id
                logger.info(f"새 책자 생성: book_id={book_id}")

            logger.info(f"PDF 생성 완료: issue_id={issue_id}, book_id={book_id}, url={pdf_url}")
            return pdf_url

        except Exception as e:
            logger.error(f"PDF 생성 실패: issue_id={issue_id}, error={str(e)}")
            raise

    async def regenerate_pdf(
        self,
        db: AsyncSession,
        book_id: str
    ) -> str:
        """기존 책자 PDF 재생성"""
        book = await book_crud.get(db, book_id)
        if not book:
            raise ValueError(f"책자를 찾을 수 없습니다: {book_id}")
        
        logger.info(f"PDF 재생성 시작: book_id={book_id}, issue_id={book.issue_id}")
        return await self.generate_issue_pdf(db, book.issue_id)

# 싱글톤 인스턴스
pdf_service = PDFGenerationService()
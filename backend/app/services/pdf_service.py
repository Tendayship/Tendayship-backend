from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging

from ..utils.pdf_utils import pdf_generator
from ..utils.azure_storage import get_storage_service
from ..crud.book_crud import book_crud
from ..crud.post_crud import post_crud
from ..crud.issue_crud import issue_crud
from ..models.book import ProductionStatus

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
            # 1. 회차 정보 조회
            issue = await issue_crud.get(db, issue_id)
            if not issue:
                raise ValueError(f"회차를 찾을 수 없습니다: {issue_id}")

            # 2. 회차의 모든 소식 조회
            posts = await post_crud.get_posts_by_issue(db, issue_id)
            if not posts:
                raise ValueError(f"회차에 소식이 없습니다: {issue_id}")

            # 3. 받는 분 정보 조회
            recipient = issue.group.recipient
            if not recipient:
                raise ValueError(f"받는 분 정보가 없습니다: {issue.group_id}")

            # 4. 소식 데이터 준비
            post_data = []
            for post in posts:
                # 작성자의 관계 정보 조회
                author_member = next(
                    (member for member in post.author.family_members
                     if member.group_id == issue.group_id),
                    None
                )

                post_data.append({
                    'content': post.content,
                    'image_urls': post.image_urls,
                    'created_at': post.created_at,
                    'author_name': post.author.name,
                    'author_relationship': author_member.relationship.value if author_member else '가족'
                })

            # 5. PDF 생성
            pdf_bytes = pdf_generator.generate_pdf(
                recipient_name=recipient.name,
                issue_number=issue.issue_number,
                deadline_date=issue.deadline_date,
                posts=post_data
            )

            # 6. Azure Blob Storage에 업로드 (수정됨)
            storage_service = get_storage_service()  # 함수 호출
            pdf_url = storage_service.upload_book_pdf(
                issue.group_id,
                issue_id,
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
            else:
                # 새 책자 생성
                book_data = {
                    'issue_id': issue_id,
                    'pdf_url': pdf_url,
                    'production_status': ProductionStatus.COMPLETED,
                    'produced_at': datetime.now()
                }
                new_book = await book_crud.create(db, book_data)
                book_id = new_book.id

            logger.info(f"PDF 생성 완료: issue_id={issue_id}, book_id={book_id}")
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
        return await self.generate_issue_pdf(db, book.issue_id)

# 싱글톤 인스턴스
pdf_service = PDFGenerationService()

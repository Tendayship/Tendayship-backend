from typing import List
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import traceback

from ...services.storage_service import post_storage_service
from ...database.session import get_db
from ...api.dependencies import get_current_user
from ...models.user import User
from ...crud.post_crud import post_crud
from ...crud.issue_crud import issue_crud
from ...crud.member_crud import family_member_crud
from ...schemas.post import PostCreate, PostResponse
from ...core.config import settings

router = APIRouter(prefix="/posts", tags=["posts"])
logger = logging.getLogger(__name__)

@router.get("/debug/test", response_model=dict)
async def debug_posts_without_auth(
    db: AsyncSession = Depends(get_db)
):
    """인증 없이 포스트 시스템 테스트"""
    logger.info("인증 없는 포스트 테스트 시작")
    try:
        from sqlalchemy import text
        result = await db.execute(text("SELECT 1 as test"))
        db_test = result.scalar()

        tables_result = await db.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name IN ('posts', 'issues', 'family_groups', 'users', 'family_members')
            ORDER BY table_name
        """))
        tables = [row[0] for row in tables_result.fetchall()]

        post_columns_result = await db.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'posts' AND table_schema = 'public'
            ORDER BY ordinal_position
        """))
        post_columns = [{"name": row[0], "type": row[1], "nullable": row[2]} for row in post_columns_result.fetchall()]

        post_count = 0
        if 'posts' in tables:
            count_result = await db.execute(text("SELECT COUNT(*) FROM posts"))
            post_count = count_result.scalar()

        return {
            "database_connection": "OK" if db_test == 1 else "FAILED",
            "tables_found": tables,
            "post_table_columns": post_columns,
            "total_posts": post_count,
            "storage_type": settings.STORAGE_TYPE,
            "status": "debug_success",
            "message": "포스트 시스템 기본 테스트 완료"
        }
    except Exception as e:
        logger.error(f"디버그 테스트 실패: {str(e)}")
        return {
            "error": str(e),
            "status": "debug_failed",
            "message": "포스트 시스템 테스트 중 오류 발생"
        }

@router.get("/debug/storage-test")
async def test_storage_connection():
    """Storage 연결 테스트 (디버깅용)"""
    try:
        from ...utils.azure_storage import get_storage_service
        storage_service = get_storage_service()
        storage_service._ensure_initialized()
        
        import os
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
        container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
        
        return {
            "status": "success",
            "storage_type": "Azure Blob Storage",
            "connection_string_exists": bool(connection_string),
            "account_name": account_name,
            "container_name": container_name,
            "storage_service_created": storage_service is not None,
            "storage_initialized": storage_service._initialized
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }

@router.post("/", response_model=PostResponse)
async def create_post(
    post_data: PostCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """소식 작성 - Azure Blob Storage 사용"""
    logger.info(f"소식 작성 요청 시작: user_id={current_user.id}")
    logger.info(f"요청 데이터: content_length={len(post_data.content)}, images={len(post_data.image_urls) if hasattr(post_data, 'image_urls') else 0}")

    try:
        # 1. 멤버십 확인
        logger.info("1단계: 멤버십 확인 중...")
        membership = await family_member_crud.check_user_membership(db, current_user.id)
        if not membership:
            logger.warning(f"멤버십 없음: user_id={current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="가족 그룹에 속해있지 않습니다"
            )

        logger.info(f"멤버십 확인 완료: group_id={membership.group_id}")

        # 2. 현재 회차 확인
        logger.info("2단계: 현재 회차 확인 중...")
        current_issue = await issue_crud.get_current_issue(db, membership.group_id)
        if not current_issue:
            logger.warning(f"현재 회차 없음: group_id={membership.group_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="현재 열린 회차가 없습니다"
            )

        logger.info(f"현재 회차 확인 완료: issue_id={current_issue.id}")

        # 3. 소식 개수 확인
        logger.info("3단계: 소식 개수 확인 중...")
        try:
            current_post_count = await post_crud.count_posts_by_issue(db, current_issue.id)
            max_posts = getattr(settings, 'MAX_POSTS_PER_MONTH', 20)
            logger.info(f"현재 소식 개수: {current_post_count}/{max_posts}")
            
            if current_post_count >= max_posts:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"월 최대 소식 개수({max_posts}개)에 도달했습니다"
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"소식 개수 확인 중 오류: {str(e)}")

        # 4. 소식 생성
        logger.info("4단계: 소식 생성 중...")
        new_post = await post_crud.create_post(
            db, post_data, current_user.id, current_issue.id
        )

        logger.info(f"소식 생성 성공: post_id={new_post.id}")

        # 5. PostResponse 생성
        post_response_data = {
            "id": str(new_post.id),
            "issue_id": str(new_post.issue_id),
            "author_id": str(new_post.author_id),
            "content": new_post.content,
            "image_urls": new_post.image_urls or [],
            "created_at": new_post.created_at,
            "updated_at": new_post.updated_at,
            "author_name": None,
            "author_relationship": None,
            "author_profile_image": None
        }

        return PostResponse(**post_response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"소식 작성 중 예상치 못한 오류: {str(e)}")
        logger.error(f"전체 스택 트레이스: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"소식 작성 중 시스템 오류: {str(e)}"
        )

@router.get("/", response_model=List[PostResponse])
async def get_current_posts(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """현재 회차의 소식 목록 조회"""
    logger.info(f"소식 목록 조회 요청: user_id={current_user.id}, skip={skip}, limit={limit}")
    
    try:
        # 1. 멤버십 확인
        logger.info("1단계: 멤버십 확인 중...")
        membership = await family_member_crud.check_user_membership(db, current_user.id)
        if not membership:
            logger.warning(f"멤버십 없음: user_id={current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="가족 그룹에 속해있지 않습니다"
            )

        logger.info(f"멤버십 확인 완료: group_id={membership.group_id}")

        # 2. 현재 회차 확인
        logger.info("2단계: 현재 회차 확인 중...")
        current_issue = await issue_crud.get_current_issue(db, membership.group_id)
        if not current_issue:
            logger.info(f"현재 회차 없음: group_id={membership.group_id}")
            return []

        logger.info(f"현재 회차 확인 완료: issue_id={current_issue.id}")

        # 3. 소식 목록 조회
        logger.info("3단계: 소식 목록 조회 중...")
        posts = await post_crud.get_posts_by_issue(db, current_issue.id, skip, limit)
        logger.info(f"소식 조회 완료: {len(posts)}개 조회됨")

        # 4. PostResponse 변환
        post_responses = []
        for post in posts:
            post_response_data = {
                "id": str(post.id),
                "issue_id": str(post.issue_id),
                "author_id": str(post.author_id),
                "content": post.content,
                "image_urls": post.image_urls or [],
                "created_at": post.created_at,
                "updated_at": post.updated_at,
                "author_name": getattr(post.author, 'name', None) if hasattr(post, 'author') and post.author else None,
                "author_relationship": None,
                "author_profile_image": getattr(post.author, 'profile_image_url', None) if hasattr(post, 'author') and post.author else None
            }
            post_responses.append(PostResponse(**post_response_data))

        return post_responses

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"소식 목록 조회 중 예상치 못한 오류: {str(e)}")
        logger.error(f"상세 오류: {traceback.format_exc()}")
        return []

@router.post("/upload-images")
async def upload_post_images(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """소식 작성용 이미지 업로드 - Azure Blob Storage 사용"""
    logger.info(f"이미지 업로드 요청: user_id={current_user.id}, files={len(files)}")
    
    try:
        # 1. 멤버십 확인
        membership = await family_member_crud.check_user_membership(db, current_user.id)
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="가족 그룹에 속해있지 않습니다"
            )

        # 2. 현재 회차 확인
        current_issue = await issue_crud.get_current_issue(db, membership.group_id)
        if not current_issue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="현재 열린 회차가 없습니다"
            )

        # 3. 임시 post_id 생성
        temp_post_id = str(uuid.uuid4())

        # 4. Azure Blob Storage에 이미지 업로드
        logger.info("Azure Blob Storage에 이미지 업로드 시작...")
        image_urls = await post_storage_service.upload_post_images(
            group_id=str(membership.group_id),
            issue_id=str(current_issue.id),
            post_id=temp_post_id,
            files=files
        )

        logger.info(f"이미지 업로드 완료: {len(image_urls)}개")

        return {
            "image_urls": image_urls,
            "temp_post_id": temp_post_id,
            "storage_type": "Azure Blob Storage",
            "message": f"{len(image_urls)}개 이미지 업로드 완료"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"이미지 업로드 중 오류: {str(e)}")
        logger.error(f"스택 트레이스: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"이미지 업로드 중 오류: {str(e)}"
        )

@router.delete("/{post_id}")
async def delete_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """소식 삭제"""
    logger.info(f"소식 삭제 요청: post_id={post_id}, user_id={current_user.id}")
    
    try:
        # 1. 소식 존재 확인 및 권한 확인
        post = await post_crud.get(db, post_id)
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="소식을 찾을 수 없습니다"
            )

        if str(post.author_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="자신이 작성한 소식만 삭제할 수 있습니다"
            )

        # 2. 이미지 삭제 (Azure Blob Storage)
        if post.image_urls:
            try:
                # 멤버십 확인
                membership = await family_member_crud.check_user_membership(db, current_user.id)
                if membership:
                    # 현재 회차 확인
                    current_issue = await issue_crud.get_current_issue(db, membership.group_id)
                    if current_issue:
                        from ...utils.azure_storage import get_storage_service
                        storage_service = get_storage_service()
                        storage_service.delete_post_images(
                            str(membership.group_id),
                            str(current_issue.id),
                            str(post.id)
                        )
                        logger.info(f"Azure Blob Storage에서 이미지 삭제 완료: post_id={post_id}")
            except Exception as e:
                logger.error(f"이미지 삭제 중 오류 (계속 진행): {str(e)}")

        # 3. 소식 삭제
        await post_crud.delete(db, post_id)
        logger.info(f"소식 삭제 완료: post_id={post_id}")

        return {"message": "소식이 성공적으로 삭제되었습니다"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"소식 삭제 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"소식 삭제 중 오류: {str(e)}"
        )

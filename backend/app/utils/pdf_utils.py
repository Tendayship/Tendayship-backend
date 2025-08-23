from typing import List, Dict, Any, Optional, Tuple
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm, mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from datetime import datetime
import io
from PIL import Image as PILImage
import requests
import os
import logging

logger = logging.getLogger(__name__)

class ImageMeta:
    """이미지 메타데이터"""
    def __init__(self, data: io.BytesIO, width: int, height: int, url: str):
        self.data = data
        self.width = width
        self.height = height
        self.url = url
        self.aspect_ratio = width / height if height else 1.0

class LayoutOption:
    """레이아웃 옵션"""
    def __init__(self, layout_type: str, cells: List[Tuple[float, float, float, float]]):
        self.layout_type = layout_type
        self.cells = cells  # [(x, y, width, height), ...]
        self.score = 0.0

class FamilyNewsPDFGenerator:
    """가족 소식 PDF 생성기 - 한글 폰트 안정화 버전"""

    def __init__(self):
        self.page_width = A4[0]
        self.page_height = A4[1]
        self.margin = 2 * cm
        
        # 폰트 등록 및 스타일 설정
        self._register_fonts()
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _register_fonts(self):
        """
        폰트 등록 우선순위:
        1) 번들 폰트(NotoSansKR Regular/Bold) - 최우선
        2) 폴백 CID 폰트(HYSMyeongJo-Medium) - 최후 폴백
        """
        # 1) 번들 폰트 등록 시도
        try:
            # 현재 파일 기준으로 fonts 디렉토리 경로 계산
            base_dir = os.path.dirname(os.path.abspath(__file__))
            fonts_dir = os.path.join(base_dir, "..", "fonts")
            regular_path = os.path.join(fonts_dir, "NotoSansCJKkr-Regular.ttf")
            bold_path = os.path.join(fonts_dir, "NotoSansCJKkr-Bold.ttf")

            if os.path.exists(regular_path) and os.path.exists(bold_path):
                pdfmetrics.registerFont(TTFont("NotoSansKR", regular_path))
                pdfmetrics.registerFont(TTFont("NotoSansKR-Bold", bold_path))
                logger.info(f"번들 폰트 등록 성공: NotoSansKR (경로: {fonts_dir})")
                return
            else:
                logger.warning(f"번들 폰트 파일을 찾을 수 없습니다: {fonts_dir}")
        except Exception as e:
            logger.warning(f"번들 폰트 등록 실패: {e}")

        # 2) 폴백 CID 폰트 등록
        try:
            pdfmetrics.registerFont(UnicodeCIDFont('HYSMyeongJo-Medium'))
            logger.info("CID 폴백 폰트 등록 성공: HYSMyeongJo-Medium")
        except Exception as e:
            logger.error(f"CID 폴백 폰트 등록 실패: {e}")
            logger.error("한글이 깨질 수 있습니다 - 최종 폴백으로 Helvetica 사용")

    def _choose_font_names(self):
        """
        등록된 폰트 중 우선순위대로 사용할 패밀리명을 선택.
        반환: (font_name, font_bold)
        """
        registered = set(pdfmetrics.getRegisteredFontNames())
        
        # 1) 번들 폰트 우선
        if "NotoSansKR" in registered and "NotoSansKR-Bold" in registered:
            return ("NotoSansKR", "NotoSansKR-Bold")
        
        # 2) CID 폴백 (볼드는 동일 폰트 사용)
        if "HYSMyeongJo-Medium" in registered:
            return ("HYSMyeongJo-Medium", "HYSMyeongJo-Medium")
        
        # 3) 최후 폴백 (한글 미지원)
        logger.warning("한글 지원 폰트가 없습니다. Helvetica로 폴백")
        return ("Helvetica", "Helvetica-Bold")

    def _setup_custom_styles(self):
        """커스텀 스타일 설정 - 선택된 폰트 적용"""
        font_name, font_bold = self._choose_font_names()
        logger.info(f"PDF 폰트 선택됨: normal={font_name}, bold={font_bold}")

        # 제목 스타일
        self.styles.add(ParagraphStyle(
            name='FamilyTitle',
            parent=self.styles['Title'],
            fontName=font_bold,
            fontSize=28,
            alignment=TA_CENTER,
            spaceAfter=30,
            leading=36
        ))

        # 회차 제목
        self.styles.add(ParagraphStyle(
            name='IssueTitle',
            parent=self.styles['Heading1'],
            fontName=font_bold,
            fontSize=20,
            alignment=TA_CENTER,
            spaceAfter=20,
            leading=28
        ))

        # 작성자 정보
        self.styles.add(ParagraphStyle(
            name='AuthorInfo',
            parent=self.styles['Normal'],
            fontName=font_name,
            fontSize=11,
            alignment=TA_LEFT,
            spaceBefore=6,
            spaceAfter=6
        ))

        # 소식 내용
        self.styles.add(ParagraphStyle(
            name='PostContent',
            parent=self.styles['Normal'],
            fontName=font_name,
            fontSize=13,
            alignment=TA_JUSTIFY,
            leftIndent=12,
            rightIndent=12,
            spaceBefore=12,
            spaceAfter=12,
            leading=20,
            wordWrap='CJK'  # 한중일 줄바꿈 개선
        ))

        # 페이지 번호
        self.styles.add(ParagraphStyle(
            name='PageNumber',
            parent=self.styles['Normal'],
            fontName=font_name,
            fontSize=10,
            alignment=TA_CENTER
        ))

        # 날짜 스타일
        self.styles.add(ParagraphStyle(
            name='DateStyle',
            parent=self.styles['Normal'],
            fontName=font_name,
            fontSize=10,
            alignment=TA_LEFT
        ))

    def generate_pdf(
        self,
        recipient_name: str,
        issue_number: int,
        deadline_date: Any,
        posts: List[Dict[str, Any]]
    ) -> bytes:
        """PDF 생성 메인 함수"""
        try:
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=self.margin,
                leftMargin=self.margin,
                topMargin=self.margin,
                bottomMargin=self.margin
            )

            story = []

            # 표지 생성
            story.extend(self._create_cover_page(recipient_name, issue_number, deadline_date))
            story.append(PageBreak())

            # 소식 페이지들 생성
            for i, post in enumerate(posts):
                post_elements = self._create_post_page(post, i + 1, len(posts))
                # KeepTogether로 페이지 분할 방지 (가능한 경우)
                if len(post_elements) > 0:
                    story.append(KeepTogether(post_elements))
                if i < len(posts) - 1:
                    story.append(PageBreak())

            # PDF 빌드
            doc.build(story)
            buffer.seek(0)
            pdf_bytes = buffer.getvalue()
            
            logger.info(f"PDF 생성 완료: {len(pdf_bytes)} bytes")
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"PDF 생성 중 오류: {e}")
            raise

    def _create_cover_page(
        self,
        recipient_name: str,
        issue_number: int,
        deadline_date: Any
    ) -> List:
        """표지 페이지 생성"""
        elements = []

        # 상단 여백
        elements.append(Spacer(1, 2*inch))

        # 서비스 제목
        title = Paragraph("가족 소식", self.styles['FamilyTitle'])
        elements.append(title)
        elements.append(Spacer(1, 0.8*inch))

        # 받는 분
        recipient_title = Paragraph(
            f"{recipient_name}님께",
            self.styles['IssueTitle']
        )
        elements.append(recipient_title)
        elements.append(Spacer(1, 0.5*inch))

        # 회차 정보
        if hasattr(deadline_date, 'strftime'):
            date_str = deadline_date.strftime('%Y년 %m월')
        else:
            date_str = str(deadline_date)

        issue_info = Paragraph(
            f"제 {issue_number}호",
            self.styles['IssueTitle']
        )
        elements.append(issue_info)
        
        date_info = Paragraph(
            f"({date_str})",
            self.styles['DateStyle']
        )
        elements.append(date_info)

        # 하단 여백
        elements.append(Spacer(1, 2.5*inch))

        # 발행 정보
        publish_info = Paragraph(
            f"발행일: {datetime.now().strftime('%Y년 %m월 %d일')}<br/>"
            f"발행처: 가족 소식 서비스",
            self.styles['DateStyle']
        )
        elements.append(publish_info)

        return elements

    def _create_post_page(
        self,
        post: Dict[str, Any],
        current_page: int,
        total_pages: int
    ) -> List:
        """개별 소식 페이지 생성 - 개선된 레이아웃"""
        elements = []

        # 페이지 헤더
        header = Paragraph(
            f"소식 {current_page} / {total_pages}",
            self.styles['PageNumber']
        )
        elements.append(header)
        elements.append(Spacer(1, 0.15*inch))

        # 구분선
        elements.append(self._create_divider())
        elements.append(Spacer(1, 0.15*inch))

        # 작성자 정보 (프로필 이미지 제외)
        author_name = post.get('author_name', '작성자')
        relationship = post.get('author_relationship', '가족')
        created_at = post.get('created_at')
        
        date_str = ""
        if created_at:
            if hasattr(created_at, 'strftime'):
                date_str = created_at.strftime('%Y년 %m월 %d일')
            else:
                date_str = str(created_at)

        author_text = f"{author_name} ({relationship})"
        if date_str:
            author_text += f" | {date_str}"

        author_info = Paragraph(author_text, self.styles['AuthorInfo'])
        elements.append(author_info)
        elements.append(Spacer(1, 0.2*inch))

        # 이미지 처리
        images = post.get('image_urls', [])
        if images:
            # 이미지 개수에 따라 반절/전체 페이지 결정
            use_half_page = len(images) <= 2
            image_elements = self._create_adaptive_image_layout(images, use_half_page)
            elements.extend(image_elements)
            
            # 텍스트가 있으면 이미지 후 간격 추가
            if post.get('content'):
                elements.append(Spacer(1, 0.3*inch))

        # 소식 내용 (선택사항)
        if post.get('content'):
            content_text = post['content'].replace('\n', '<br/>')
            content = Paragraph(content_text, self.styles['PostContent'])
            
            # 내용을 박스로 감싸기
            content_table = Table([[content]], colWidths=[self.page_width - 2*self.margin])
            content_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 12),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ]))
            elements.append(content_table)

        return elements

    def _create_divider(self) -> Table:
        """구분선 생성"""
        line = Table([[""]], colWidths=[self.page_width - 2*self.margin])
        line.setStyle(TableStyle([
            ('LINEABOVE', (0, 0), (-1, 0), 0.5, colors.black),
        ]))
        return line

    def _create_adaptive_image_layout(self, image_urls: List[str], use_half_page: bool) -> List:
        """적응형 이미지 레이아웃 생성"""
        elements = []

        # 이미지 메타데이터 수집
        image_metas = []
        for url in image_urls[:4]:
            meta = self._get_image_meta(url)
            if meta:
                image_metas.append(meta)

        if not image_metas:
            return elements

        # 사용 가능한 영역 계산
        available_width = self.page_width - 2 * self.margin
        if use_half_page:
            # 1~2장: A4 반절 사용
            available_height = (self.page_height - 2 * self.margin) * 0.4
        else:
            # 3~4장: 전체 페이지 사용
            available_height = (self.page_height - 2 * self.margin) * 0.7

        # 이미지 개수별 레이아웃 생성
        layout_elements = self._generate_layout(image_metas, available_width, available_height)
        elements.extend(layout_elements)

        return elements

    def _generate_layout(self, image_metas: List[ImageMeta], width: float, height: float) -> List:
        """이미지 개수와 비율에 따른 최적 레이아웃 생성"""
        elements = []
        count = len(image_metas)

        if count == 1:
            # 1장: 중앙 정렬, 비율 유지
            img_meta = image_metas[0]
            img_width, img_height = self._calculate_fit_size(
                img_meta.aspect_ratio, width * 0.8, height * 0.9
            )
            img = Image(img_meta.data, width=img_width, height=img_height)
            
            # 중앙 정렬을 위한 테이블
            table = Table([[img]], colWidths=[width])
            table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(table)

        elif count == 2:
            # 2장: 가로 배치 또는 세로 배치 (비율에 따라)
            avg_ratio = sum(m.aspect_ratio for m in image_metas) / 2

            if avg_ratio > 1.2:  # 가로가 긴 이미지들 - 세로 배치
                table_data = []
                for img_meta in image_metas:
                    img_width, img_height = self._calculate_fit_size(
                        img_meta.aspect_ratio, width * 0.9, height * 0.4
                    )
                    table_data.append([Image(img_meta.data, width=img_width, height=img_height)])
                
                table = Table(table_data, colWidths=[width])
                table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ]))
            else:  # 세로가 긴 이미지들 - 가로 배치
                images = []
                for img_meta in image_metas:
                    img_width, img_height = self._calculate_fit_size(
                        img_meta.aspect_ratio, width * 0.45, height * 0.8
                    )
                    images.append(Image(img_meta.data, width=img_width, height=img_height))

                table = Table([images], colWidths=[width/2, width/2])
                table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
            elements.append(table)

        elif count == 3:
            # 3장: 1+2 또는 2+1 레이아웃
            if image_metas[0].aspect_ratio > 1.5:  # 첫 이미지가 가로로 긴 경우
                # 상단에 1장, 하단에 2장
                img_width, img_height = self._calculate_fit_size(
                    image_metas[0].aspect_ratio, width * 0.9, height * 0.4
                )
                first_img = Image(image_metas[0].data, width=img_width, height=img_height)

                # 하단 2장
                bottom_images = []
                for img_meta in image_metas[1:]:
                    img_width, img_height = self._calculate_fit_size(
                        img_meta.aspect_ratio, width * 0.43, height * 0.4
                    )
                    bottom_images.append(Image(img_meta.data, width=img_width, height=img_height))

                table_data = [
                    [first_img],
                    bottom_images
                ]
                table = Table(table_data, colWidths=[width])
            else:  # 상단에 2장, 하단에 1장
                # 상단 2장
                top_images = []
                for img_meta in image_metas[:2]:
                    img_width, img_height = self._calculate_fit_size(
                        img_meta.aspect_ratio, width * 0.43, height * 0.4
                    )
                    top_images.append(Image(img_meta.data, width=img_width, height=img_height))

                # 하단 1장
                img_width, img_height = self._calculate_fit_size(
                    image_metas[2].aspect_ratio, width * 0.9, height * 0.4
                )
                bottom_img = Image(image_metas[2].data, width=img_width, height=img_height)

                table_data = [
                    top_images,
                    [bottom_img]
                ]
                table = Table(table_data, colWidths=[width/2, width/2])

            table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(table)

        else:  # count == 4
            # 4장: 2x2 그리드
            cell_width = width * 0.43
            cell_height = height * 0.43

            table_data = []
            for i in range(0, 4, 2):
                row = []
                for j in range(2):
                    if i + j < len(image_metas):
                        img_meta = image_metas[i + j]
                        img_width, img_height = self._calculate_fit_size(
                            img_meta.aspect_ratio, cell_width, cell_height
                        )
                        row.append(Image(img_meta.data, width=img_width, height=img_height))
                    else:
                        row.append("")
                table_data.append(row)

            table = Table(table_data, colWidths=[width/2, width/2])
            table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(table)

        return elements

    def _calculate_fit_size(self, aspect_ratio: float, max_width: float, max_height: float) -> Tuple[float, float]:
        """비율을 유지하면서 영역에 맞는 크기 계산"""
        if aspect_ratio > max_width / max_height:
            # 가로가 더 긴 경우
            width = max_width
            height = max_width / aspect_ratio
        else:
            # 세로가 더 긴 경우
            height = max_height
            width = max_height * aspect_ratio
        return width, height

    def _get_image_meta(self, image_url: str) -> Optional[ImageMeta]:
        """이미지 메타데이터 추출"""
        try:
            # URL 유효성 간단 체크
            if not image_url.startswith(('http://', 'https://')):
                logger.error(f"유효하지 않은 이미지 URL 스킴: {image_url}")
                return None

            response = requests.get(image_url, timeout=20)  # 타임아웃 증가
            response.raise_for_status()
            image = PILImage.open(io.BytesIO(response.content))

            # EXIF 회전 정보 적용
            if hasattr(image, '_getexif'):
                exif = image._getexif()
                if exif is not None:
                    for tag, value in exif.items():
                        if tag == 274:  # Orientation tag
                            if value == 3:
                                image = image.rotate(180, expand=True)
                            elif value == 6:
                                image = image.rotate(270, expand=True)
                            elif value == 8:
                                image = image.rotate(90, expand=True)

            # RGB 변환
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # 원본 크기 저장
            original_width, original_height = image.size

            # 적절한 크기로 리사이즈 (메모리 절약)
            max_size = (1200, 900)
            image.thumbnail(max_size, PILImage.Resampling.LANCZOS)

            # BytesIO로 변환
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=90)
            output.seek(0)

            return ImageMeta(output, original_width, original_height, image_url)

        except Exception as e:
            logger.error(f"이미지 처리 실패: {image_url}, 오류: {e}")
            return None

# 싱글톤 인스턴스
pdf_generator = FamilyNewsPDFGenerator()

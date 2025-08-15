from typing import List, Dict, Any
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime
import io
from PIL import Image as PILImage
import requests
from typing import Optional

class FamilyNewsPDFGenerator:
    """가족 소식 PDF 생성기"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()
    
    def setup_custom_styles(self):
        """커스텀 스타일 설정"""
        # 제목 스타일
        self.styles.add(ParagraphStyle(
            name='FamilyTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#018941'),  # 서비스 메인 컬러
            alignment=TA_CENTER,
            spaceAfter=20
        ))
        
        # 소제목 스타일
        self.styles.add(ParagraphStyle(
            name='IssueTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#018941'),
            alignment=TA_CENTER,
            spaceAfter=15
        ))
        
        # 작성자 정보 스타일
        self.styles.add(ParagraphStyle(
            name='AuthorInfo',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.grey,
            alignment=TA_LEFT,
            spaceBefore=5
        ))
        
        # 소식 내용 스타일
        self.styles.add(ParagraphStyle(
            name='PostContent',
            parent=self.styles['Normal'],
            fontSize=12,
            alignment=TA_LEFT,
            leftIndent=10,
            rightIndent=10,
            spaceBefore=10,
            spaceAfter=10
        ))
    
    def generate_pdf(
        self, 
        recipient_name: str,
        issue_number: int,
        deadline_date: datetime,
        posts: List[Dict[str, Any]]
    ) -> bytes:
        """PDF 생성 메인 함수"""
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        # 스토리(페이지 내용) 구성
        story = []
        
        # 표지 생성
        story.extend(self._create_cover_page(recipient_name, issue_number, deadline_date))
        story.append(PageBreak())
        
        # 소식 페이지들 생성
        for i, post in enumerate(posts):
            story.extend(self._create_post_page(post, i + 1, len(posts)))
            if i < len(posts) - 1:  # 마지막 페이지가 아니면 페이지 브레이크
                story.append(PageBreak())
        
        # PDF 빌드
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
    
    def _create_cover_page(
        self, 
        recipient_name: str, 
        issue_number: int, 
        deadline_date: datetime
    ) -> List:
        """표지 페이지 생성"""
        elements = []
        
        # 서비스 로고/제목
        title = Paragraph("가족 소식", self.styles['FamilyTitle'])
        elements.append(title)
        elements.append(Spacer(1, 1*inch))
        
        # 받는 분 이름
        recipient_title = Paragraph(
            f"{recipient_name}님께", 
            self.styles['IssueTitle']
        )
        elements.append(recipient_title)
        elements.append(Spacer(1, 0.5*inch))
        
        # 회차 정보
        issue_info = Paragraph(
            f"제 {issue_number}호 ({deadline_date.strftime('%Y년 %m월')})", 
            self.styles['Normal']
        )
        elements.append(issue_info)
        elements.append(Spacer(1, 2*inch))
        
        # 발행 정보
        publish_info = Paragraph(
            f"발행일: {datetime.now().strftime('%Y년 %m월 %d일')}<br/>"
            f"발행처: 가족 소식 서비스",
            self.styles['Normal']
        )
        elements.append(publish_info)
        
        return elements
    
    def _create_post_page(
        self, 
        post: Dict[str, Any], 
        current_page: int, 
        total_pages: int
    ) -> List:
        """개별 소식 페이지 생성"""
        elements = []
        
        # 페이지 헤더
        header = Paragraph(
            f"소식 {current_page} / {total_pages}",
            self.styles['AuthorInfo']
        )
        elements.append(header)
        elements.append(Spacer(1, 0.3*inch))
        
        # 작성자 정보
        author_info = Paragraph(
            f"{post.get('author_name', '')} ({post.get('author_relationship', '')}) | "
            f"{post.get('created_at', '').strftime('%m월 %d일') if post.get('created_at') else ''}",
            self.styles['AuthorInfo']
        )
        elements.append(author_info)
        elements.append(Spacer(1, 0.2*inch))
        
        # 이미지 처리 (최대 4장)
        images = post.get('image_urls', [])
        if images:
            elements.extend(self._create_image_layout(images))
            elements.append(Spacer(1, 0.3*inch))
        
        # 소식 내용
        if post.get('content'):
            content = Paragraph(post['content'], self.styles['PostContent'])
            elements.append(content)
        
        return elements
    
    def _create_image_layout(self, image_urls: List[str]) -> List:
        """이미지 레이아웃 생성 (콜라주 형태)"""
        elements = []
        image_count = len(image_urls)
        
        # 이미지 다운로드 및 처리
        processed_images = []
        for url in image_urls[:4]:  # 최대 4장
            try:
                image_data = self._download_and_resize_image(url)
                if image_data:
                    processed_images.append(image_data)
            except Exception as e:
                print(f"이미지 처리 실패: {url}, 오류: {e}")
                continue
        
        if not processed_images:
            return elements
        
        # 이미지 개수에 따른 레이아웃
        if image_count == 1:
            # 1장: 중앙 정렬, 큰 크기
            img = Image(processed_images[0], width=4*inch, height=3*inch)
            elements.append(img)
        
        elif image_count == 2:
            # 2장: 나란히 배치
            table_data = [[
                Image(processed_images[0], width=2.5*inch, height=2*inch),
                Image(processed_images[1], width=2.5*inch, height=2*inch)
            ]]
            table = Table(table_data, colWidths=[2.7*inch, 2.7*inch])
            table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(table)
        
        elif image_count >= 3:
            # 3-4장: 2x2 그리드
            if image_count == 3:
                processed_images.append(None)  # 빈 셀용
            
            table_data = [
                [
                    Image(processed_images[0], width=2*inch, height=1.5*inch),
                    Image(processed_images[1], width=2*inch, height=1.5*inch)
                ],
                [
                    Image(processed_images[2], width=2*inch, height=1.5*inch) if processed_images[2] else "",
                    Image(processed_images[3], width=2*inch, height=1.5*inch) if len(processed_images) > 3 and processed_images[3] else ""
                ]
            ]
            
            table = Table(table_data, colWidths=[2.2*inch, 2.2*inch])
            table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ]))
            elements.append(table)
        
        return elements
    
    def _download_and_resize_image(self, image_url: str) -> Optional[io.BytesIO]:
        """이미지 다운로드 및 리사이즈"""
        try:
            # URL에서 이미지 다운로드
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            
            # PIL로 이미지 처리
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
            
            # RGB 변환 (PDF에 적합)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # 적절한 크기로 리사이즈
            max_size = (800, 600)
            image.thumbnail(max_size, PILImage.Resampling.LANCZOS)
            
            # BytesIO로 변환
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=85)
            output.seek(0)
            
            return output
            
        except Exception as e:
            print(f"이미지 처리 실패: {image_url}, 오류: {e}")
            return None

# 싱글톤 인스턴스
pdf_generator = FamilyNewsPDFGenerator()

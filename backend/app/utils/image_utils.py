from PIL import Image, ExifTags
from typing import Tuple
import io

class ImageProcessor:
    """이미지 처리 유틸리티"""
    
    @staticmethod
    def resize_image(
        image: Image.Image, 
        max_size: Tuple[int, int] = (800, 600)
    ) -> Image.Image:
        """이미지 리사이즈"""
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        return image
    
    @staticmethod
    def fix_orientation(image: Image.Image) -> Image.Image:
        """EXIF 회전 정보 적용"""
        try:
            if hasattr(image, '_getexif'):
                exif = image._getexif()
                if exif is not None:
                    for tag, value in exif.items():
                        if tag in ExifTags.TAGS and ExifTags.TAGS[tag] == 'Orientation':
                            if value == 3:
                                image = image.rotate(180, expand=True)
                            elif value == 6:
                                image = image.rotate(270, expand=True)
                            elif value == 8:
                                image = image.rotate(90, expand=True)
                            break
        except (AttributeError, KeyError, TypeError):
            pass
        return image
    
    @staticmethod
    def convert_to_rgb(image: Image.Image) -> Image.Image:
        """RGB 포맷으로 변환"""
        if image.mode != 'RGB':
            return image.convert('RGB')
        return image
    
    async def process_for_collage(
        self, 
        file_data: bytes, 
        total_images: int, 
        index: int
    ) -> bytes:
        """콜라주용 이미지 처리"""
        # PIL 이미지로 변환
        image = Image.open(io.BytesIO(file_data))
        
        # EXIF 회전 적용
        image = self.fix_orientation(image)
        
        # RGB 변환
        image = self.convert_to_rgb(image)
        
        # 콜라주 타입에 따른 크기 조정
        if total_images == 1:
            max_size = (800, 600)
        elif total_images == 2:
            max_size = (400, 300)
        else:  # 3-4장
            max_size = (300, 225)
        
        image = self.resize_image(image, max_size)
        
        # BytesIO로 변환
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=85)
        output.seek(0)
        
        return output.getvalue()

import re
from typing import Optional, List
from datetime import date
from decimal import Decimal

def validate_email(email: str) -> bool:
    """이메일 형식 검증"""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email))

def validate_phone(phone: str) -> bool:
    """한국 휴대폰 번호 검증"""
    # 010-1234-5678, 01012345678 형식 지원
    phone_clean = re.sub(r'[-\s]', '', phone)
    phone_pattern = r'^010\d{8}$'
    return bool(re.match(phone_pattern, phone_clean))

def validate_postal_code(postal_code: str) -> bool:
    """우편번호 검증 (5자리 숫자)"""
    return bool(re.match(r'^\d{5}$', postal_code))

def validate_invite_code(invite_code: str) -> bool:
    """초대 코드 검증 (8자리 대문자+숫자)"""
    return bool(re.match(r'^[A-Z0-9]{8}$', invite_code))

def validate_post_content(content: str) -> tuple[bool, Optional[str]]:
    """소식 내용 검증"""
    if not content or not content.strip():
        return False, "내용을 입력해주세요"
    
    content_length = len(content.strip())
    if content_length < 50:
        return False, f"내용은 최소 50자 이상 입력해주세요 (현재: {content_length}자)"
    
    if content_length > 100:
        return False, f"내용은 최대 100자까지 입력 가능합니다 (현재: {content_length}자)"
    
    return True, None

def validate_image_urls(image_urls: List[str]) -> tuple[bool, Optional[str]]:
    """이미지 URL 목록 검증"""
    if not image_urls:
        return False, "최소 1장의 이미지가 필요합니다"
    
    if len(image_urls) > 4:
        return False, "최대 4장의 이미지만 업로드 가능합니다"
    
    # URL 형식 검증
    url_pattern = r'^https?://.+\.(jpg|jpeg|png|webp)(\?.*)?$'
    for url in image_urls:
        if not re.match(url_pattern, url, re.IGNORECASE):
            return False, f"올바른 이미지 URL 형식이 아닙니다: {url}"
    
    return True, None

def validate_payment_amount(amount: Decimal) -> tuple[bool, Optional[str]]:
    """결제 금액 검증"""
    if amount <= 0:
        return False, "결제 금액은 0보다 커야 합니다"
    
    if amount != Decimal("6900"):
        return False, "현재 지원하는 구독 금액은 6,900원입니다"
    
    return True, None

def validate_birth_date(birth_date: date) -> tuple[bool, Optional[str]]:
    """생년월일 검증"""
    today = date.today()
    
    if birth_date > today:
        return False, "생년월일은 현재 날짜보다 이전이어야 합니다"
    
    # 150세 초과 제한
    age_limit = today.replace(year=today.year - 150)
    if birth_date < age_limit:
        return False, "올바른 생년월일을 입력해주세요"
    
    return True, None

def validate_group_name(group_name: str) -> tuple[bool, Optional[str]]:
    """그룹명 검증"""
    if not group_name or not group_name.strip():
        return False, "그룹명을 입력해주세요"
    
    group_name = group_name.strip()
    if len(group_name) < 2:
        return False, "그룹명은 2자 이상 입력해주세요"
    
    if len(group_name) > 20:
        return False, "그룹명은 20자 이하로 입력해주세요"
    
    # 특수문자 제한 (일부만 허용)
    allowed_pattern = r'^[가-힣a-zA-Z0-9\s\-_()]+$'
    if not re.match(allowed_pattern, group_name):
        return False, "그룹명에는 한글, 영문, 숫자, 공백, 하이픈(-), 언더스코어(_), 괄호()만 사용 가능합니다"
    
    return True, None

class ValidationError(Exception):
    """검증 오류 커스텀 예외"""
    def __init__(self, message: str, field: Optional[str] = None):
        self.message = message
        self.field = field
        super().__init__(self.message)

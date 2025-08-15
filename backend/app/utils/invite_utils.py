import random
import string

def generate_invite_code(length: int = 8) -> str:
    """지정된 길이의 랜덤 영숫자 초대 코드를 생성합니다."""
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))
import asyncio
from app.utils.pdf_utils import pdf_generator
from datetime import datetime

async def test_pdf_generation():
    """PDF 생성 테스트"""
    print("PDF 생성 테스트 시작...")
    
    # 테스트 데이터
    test_posts = [
        {
            'content': '오늘 아침에 맛있는 김치찌개를 끓여서 온 가족이 함께 먹었어요. 할머니가 좋아하실 것 같아서 사진으로 남겨뒀어요.',
            'image_urls': [],
            'created_at': datetime.now(),
            'author_name': '김영희',
            'author_relationship': '딸'
        },
        {
            'content': '주말에 아이들과 공원에 나들이를 갔어요. 날씨가 너무 좋아서 기분이 상쾌했습니다.',
            'image_urls': [],
            'created_at': datetime.now(),
            'author_name': '박철수',
            'author_relationship': '아들'
        }
    ]
    
    try:
        pdf_bytes = pdf_generator.generate_pdf(
            recipient_name="김할머니",
            issue_number=1,
            deadline_date=datetime.now(),
            posts=test_posts
        )
        
        # 파일로 저장
        with open("test_book.pdf", "wb") as f:
            f.write(pdf_bytes)
        
        print("✅ PDF 생성 성공!")
        print(f"파일 크기: {len(pdf_bytes)} bytes")
        
    except Exception as e:
        print(f"❌ PDF 생성 실패: {e}")

if __name__ == "__main__":
    asyncio.run(test_pdf_generation())

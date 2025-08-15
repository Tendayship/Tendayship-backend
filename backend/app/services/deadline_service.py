from datetime import date, datetime, timedelta
from typing import Tuple, Optional
from calendar import monthrange

from ..models.family import DeadlineType

class DeadlineService:
    """마감일 계산 및 관리 서비스"""
    
    @staticmethod
    def calculate_next_deadline(
        deadline_type: DeadlineType,
        reference_date: Optional[date] = None
    ) -> date:
        """다음 마감일 계산"""
        if reference_date is None:
            reference_date = date.today()
        
        if deadline_type == DeadlineType.SECOND_WEEK:
            return DeadlineService._get_nth_sunday_of_month(reference_date, 2)
        elif deadline_type == DeadlineType.FOURTH_WEEK:
            return DeadlineService._get_nth_sunday_of_month(reference_date, 4)
        else:
            raise ValueError(f"지원하지 않는 마감일 타입: {deadline_type}")
    
    @staticmethod
    def _get_nth_sunday_of_month(reference_date: date, week_number: int) -> date:
        """해당 월의 N번째 일요일 구하기"""
        year = reference_date.year
        month = reference_date.month
        
        # 해당 월 1일
        first_day = date(year, month, 1)
        
        # 1일이 무슨 요일인지 확인 (0=월요일, 6=일요일)
        first_weekday = first_day.weekday()
        
        # 첫 번째 일요일까지의 날짜 차이
        days_to_first_sunday = (6 - first_weekday) % 7
        first_sunday = first_day + timedelta(days=days_to_first_sunday)
        
        # N번째 일요일
        nth_sunday = first_sunday + timedelta(weeks=week_number - 1)
        
        # 만약 N번째 일요일이 해당 월을 벗어나면, 다음 월로
        if nth_sunday.month != month:
            next_month = month + 1 if month < 12 else 1
            next_year = year if month < 12 else year + 1
            return DeadlineService._get_nth_sunday_of_month(
                date(next_year, next_month, 1), week_number
            )
        
        # 이미 지난 마감일이면 다음 달로
        if nth_sunday <= reference_date:
            next_month = month + 1 if month < 12 else 1
            next_year = year if month < 12 else year + 1
            return DeadlineService._get_nth_sunday_of_month(
                date(next_year, next_month, 1), week_number
            )
        
        return nth_sunday
    
    @staticmethod
    def days_until_deadline(deadline_date: date) -> int:
        """마감일까지 남은 일수"""
        today = date.today()
        return (deadline_date - today).days
    
    @staticmethod
    def is_deadline_passed(deadline_date: date) -> bool:
        """마감일이 지났는지 확인"""
        return date.today() > deadline_date

# 싱글톤 인스턴스
deadline_service = DeadlineService()

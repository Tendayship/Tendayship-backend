from datetime import date, timedelta
from app.models import DeadlineType

def get_next_sunday(d: date, weekday_index: int) -> date:
    """주어진 날짜 이후의 특정 요일(일요일=6)을 찾습니다."""
    days_ahead = weekday_index - d.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return d + timedelta(days_ahead)

def calculate_next_deadline(start_date: date, deadline_type: DeadlineType) -> date:
    """다음 마감일을 계산합니다 (둘째/넷째 주 일요일)."""
    # 이번 달 1일
    first_day_of_month = start_date.replace(day=1)
    
    # 첫째 주 일요일
    first_sunday = get_next_sunday(first_day_of_month, 6)
    
    # 둘째, 넷째 주 일요일 계산
    second_sunday = first_sunday + timedelta(weeks=1)
    fourth_sunday = first_sunday + timedelta(weeks=3)

    if deadline_type == DeadlineType.SECOND_SUNDAY:
        # 이미 둘째 주 일요일이 지났다면 다음 달을 기준으로 계산
        if start_date > second_sunday:
            next_month_first_day = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
            first_sunday_next_month = get_next_sunday(next_month_first_day, 6)
            return first_sunday_next_month + timedelta(weeks=1)
        return second_sunday
    
    elif deadline_type == DeadlineType.FOURTH_SUNDAY:
        if start_date > fourth_sunday:
            next_month_first_day = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
            first_sunday_next_month = get_next_sunday(next_month_first_day, 6)
            return first_sunday_next_month + timedelta(weeks=3)
        return fourth_sunday
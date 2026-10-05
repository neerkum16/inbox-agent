"""
Date and datetime utility functions for the Bank Database.
"""

from datetime import date, datetime, time, timedelta
from typing import Callable, Union

DateLike = Union[date, datetime]


class DateUtils:
    """Static helpers for deterministic generator date operations."""

    @staticmethod
    def today() -> date:
        return date.today()

    @staticmethod
    def now() -> datetime:
        return datetime.now().replace(microsecond=0)

    @staticmethod
    def parse_date(value: Union[str, date, datetime]) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Date value cannot be blank.")
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise ValueError(f"Invalid ISO date: {value!r}") from exc

    @staticmethod
    def parse_datetime(value: Union[str, date, datetime]) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, time.min)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Datetime value cannot be blank.")
        try:
            return datetime.fromisoformat(value.strip())
        except ValueError as exc:
            raise ValueError(f"Invalid ISO datetime: {value!r}") from exc

    @staticmethod
    def random_date(
        start_date: DateLike,
        end_date: DateLike,
        rng: Callable[[], float] = None,
    ) -> date:
        start = DateUtils.parse_date(start_date)
        end = DateUtils.parse_date(end_date)

        if start > end:
            raise ValueError("start_date cannot be later than end_date.")

        if rng is None:
            import random
            offset = random.randint(0, (end - start).days)
        else:
            offset = int(rng() * ((end - start).days + 1))
            offset = min(offset, (end - start).days)

        return start + timedelta(days=offset)

    @staticmethod
    def random_datetime(
        start_date: DateLike,
        end_date: DateLike,
        rng: Callable[[], float] = None,
    ) -> datetime:
        start = DateUtils.parse_date(start_date)
        end = DateUtils.parse_date(end_date)

        if start > end:
            raise ValueError("start_date cannot be later than end_date.")

        start_dt = datetime.combine(start, time.min)
        end_dt = datetime.combine(end, time.max)

        if start == end:
            return start_dt

        total_seconds = int((end_dt - start_dt).total_seconds())
        if rng is None:
            import random
            seconds = random.randint(0, total_seconds)
        else:
            seconds = int(rng() * (total_seconds + 1))
            seconds = min(seconds, total_seconds)

        return (start_dt + timedelta(seconds=seconds)).replace(microsecond=0)

    @staticmethod
    def add_days(input_date: DateLike, days: int) -> DateLike:
        """
        Add days while preserving the input type.
    
        datetime input -> datetime output
        date input     -> date output
        """
        if isinstance(input_date, datetime):
            return input_date + timedelta(days=days)
    
        return DateUtils.parse_date(input_date) + timedelta(days=days)

    @staticmethod
    def add_years(input_date: DateLike, years: int) -> date:
        value = DateUtils.parse_date(input_date)
        try:
            return value.replace(year=value.year + years)
        except ValueError:
            return value.replace(year=value.year + years, month=2, day=28)

    @staticmethod
    def years_ago(years: int) -> date:
        if years < 0:
            raise ValueError("years cannot be negative.")
        return DateUtils.add_years(DateUtils.today(), -years)

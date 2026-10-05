"""
Validation utilities for the Bank Database synthetic data pipeline.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from numbers import Number
from typing import Iterable, Mapping, Optional


class Validation:
    """Static validation helpers for values, identifiers, records, and CSV schemas."""

    @staticmethod
    def not_blank(value) -> bool:
        return isinstance(value, str) and bool(value.strip())

    @staticmethod
    def positive_number(value) -> bool:
        try:
            return isinstance(value, Number) and not isinstance(value, bool) and value > 0
        except TypeError:
            return False

    @staticmethod
    def non_negative_number(value) -> bool:
        try:
            return isinstance(value, Number) and not isinstance(value, bool) and value >= 0
        except TypeError:
            return False

    @staticmethod
    def positive_decimal(value) -> bool:
        decimal_value = Validation._to_decimal(value)
        return decimal_value is not None and decimal_value > Decimal("0")

    @staticmethod
    def non_negative_decimal(value) -> bool:
        decimal_value = Validation._to_decimal(value)
        return decimal_value is not None and decimal_value >= Decimal("0")

    @staticmethod
    def valid_sort_code(sort_code) -> bool:
        return Validation._fixed_digits(sort_code, 6)

    @staticmethod
    def valid_customer_number(customer_number) -> bool:
        return Validation._fixed_digits(customer_number, 10)

    @staticmethod
    def valid_account_number(account_number) -> bool:
        return Validation._fixed_digits(account_number, 8)

    @staticmethod
    def valid_status(value, allowed_statuses: Iterable[str]) -> bool:
        return isinstance(value, str) and value in set(allowed_statuses)

    @staticmethod
    def require_columns(
        fieldnames: Optional[Iterable[str]],
        required_columns: Iterable[str],
        source_name: str = "Input",
    ) -> None:
        if not fieldnames:
            raise ValueError(f"{source_name} is empty or missing a header.")

        missing = set(required_columns) - set(fieldnames)
        if missing:
            raise ValueError(
                f"{source_name} missing required columns: {', '.join(sorted(missing))}"
            )

    @staticmethod
    def validate_record(
        record: Mapping,
        required_fields: Iterable[str],
        source_name: str = "Record",
    ) -> None:
        missing = [
            field for field in required_fields
            if field not in record or record[field] is None or record[field] == ""
        ]
        if missing:
            raise ValueError(
                f"{source_name} missing required values: {', '.join(sorted(missing))}"
            )

    @staticmethod
    def date_not_before(
        earlier: Optional[date],
        later: Optional[date],
        field_name: str = "date",
    ) -> bool:
        if earlier is None or later is None:
            return True
        return earlier >= later

    @staticmethod
    def parse_decimal(value) -> Decimal:
        decimal_value = Validation._to_decimal(value)
        if decimal_value is None:
            raise ValueError(f"Invalid decimal value: {value!r}")
        return decimal_value

    @staticmethod
    def _fixed_digits(value, length: int) -> bool:
        return isinstance(value, str) and value.isdigit() and len(value) == length

    @staticmethod
    def _to_decimal(value):
        if isinstance(value, bool):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None

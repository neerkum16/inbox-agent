"""
Generate REASON_CODE reference data from BANKDB configuration.
"""

import csv
from pathlib import Path


class ReasonCodeGenerator:
    """Generate static REASON_CODE reference records."""

    HEADER = [
        "reason_code",
        "applies_to",
        "description",
        "customer_facing_text",
    ]

    VALID_APPLIES_TO = {
        "ACCOUNT_STATUS",
        "CUSTOMER_STATUS",
        "TRANSACTION",
    }

    REQUIRED_FIELDS = {
        "reason_code",
        "applies_to",
        "description",
        "customer_facing_text",
    }

    def __init__(self, config: dict):
        self.config = config
        self.reason_codes = config.get("reason_codes", [])
        self._validate_configuration()

    def generate_reason_codes(self, output_file: str) -> dict:
        """Write configured reason codes to CSV."""

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=self.HEADER,
            )
            writer.writeheader()
            writer.writerows(self.reason_codes)

        return {
            "reason_codes_generated": len(self.reason_codes),
            "output_file": str(output_path),
        }

    def _validate_configuration(self) -> None:
        """Validate reason-code definitions before generation."""

        if not isinstance(self.reason_codes, list) or not self.reason_codes:
            raise ValueError("reason_codes must contain at least one definition.")

        seen_codes = set()

        for record in self.reason_codes:
            if not isinstance(record, dict):
                raise ValueError(
                    "Each reason code definition must be a dictionary."
                )

            missing_fields = self.REQUIRED_FIELDS - set(record)
            if missing_fields:
                missing = ", ".join(sorted(missing_fields))
                raise ValueError(
                    f"Reason code definition is missing fields: {missing}"
                )

            reason_code = str(record["reason_code"]).strip()
            applies_to = str(record["applies_to"]).strip()

            if not reason_code:
                raise ValueError("reason_code cannot be blank.")

            if reason_code in seen_codes:
                raise ValueError(
                    f"Duplicate reason_code configured: {reason_code}"
                )

            if applies_to not in self.VALID_APPLIES_TO:
                valid = ", ".join(sorted(self.VALID_APPLIES_TO))
                raise ValueError(
                    f"Invalid applies_to '{applies_to}' for "
                    f"reason_code '{reason_code}'. Expected one of: {valid}"
                )

            seen_codes.add(reason_code)

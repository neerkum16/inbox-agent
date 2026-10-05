"""
Generate CONTROL records summarising generated CUSTOMER and ACCOUNT datasets.
"""

import csv
from collections import Counter
from pathlib import Path

from utils.date_utils import DateUtils


class ControlGenerator:
    HEADER = ["control_key", "control_value", "description", "created_at", "updated_at"]

    def __init__(self, config: dict):
        self.config = config

    def generate_control(self, customer_file: str, account_file: str, output_file: str) -> dict:
        customers = self._read_statistics(Path(customer_file), "customer_number", "customer_status")
        accounts = self._read_statistics(Path(account_file), "account_number", "account_status")

        records = [
            ("LAST_CUSTOMER_NUMBER", customers["last_number"], "Last generated customer number"),
            ("LAST_ACCOUNT_NUMBER", accounts["last_number"], "Last generated account number"),
            ("CUSTOMER_COUNT", str(customers["count"]), "Total customers generated"),
            ("ACCOUNT_COUNT", str(accounts["count"]), "Total accounts generated"),
        ]

        for status, count in sorted(customers["statuses"].items()):
            records.append((f"CUSTOMER_STATUS_{status}_COUNT", str(count), f"Customers with {status} status"))
        for status, count in sorted(accounts["statuses"].items()):
            records.append((f"ACCOUNT_STATUS_{status}_COUNT", str(count), f"Accounts with {status} status"))

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = DateUtils.now().isoformat(sep=" ")

        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(self.HEADER)
            for key, value, description in records:
                writer.writerow([key, value, description, timestamp, timestamp])

        return {
            "control_records_generated": len(records),
            "customers": customers["count"],
            "accounts": accounts["count"],
            "output_file": str(output_path),
        }

    @staticmethod
    def _read_statistics(path: Path, number_column: str, status_column: str) -> dict:
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")

        count = 0
        last_number = ""
        statuses = Counter()
        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            required = {number_column, status_column}
            if not reader.fieldnames or required - set(reader.fieldnames):
                raise ValueError(f"{path.name} missing required control columns.")
            for row in reader:
                count += 1
                last_number = row[number_column]
                statuses[row[status_column]] += 1

        return {"count": count, "last_number": last_number, "statuses": statuses}

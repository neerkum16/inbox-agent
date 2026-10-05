"""
Generate Transaction_History financial and lifecycle events aligned with the final schema.

Customer lifecycle events OCC/ODC require CUSTOMER input.
Account lifecycle events OFA/OSC are generated from ACCOUNT input.
Financial events are generated per account subject to account status rules.
"""

import csv
from decimal import Decimal
from pathlib import Path

from utils.date_utils import DateUtils
from utils.random_utils import RandomUtils


class TranHistGenerator:
    HEADER = [
        "sort_code", "account_number", "customer_number", "transaction_timestamp",
        "transaction_type", "transaction_amount", "transaction_description",
        "status_code", "status_reason", "created_at",
    ]

    def __init__(self, config: dict):
        self.config = config
        self.random = RandomUtils(config["random"]["seed"] + 2)
        tx = config["transactions"]
        self.minimum = tx["minimum_per_account"]
        self.maximum = tx["maximum_per_account"]
        self.financial_types = tx["financial_transaction_types"]
        self.definitions = tx["transaction_definitions"]
        self.failure_mapping = tx.get("failure_reason_mapping", {})
        self.frozen_declined_rate = tx.get("frozen_declined_rate", 0.2)
        self.dormant_cap_days = tx.get("dormant_cap_days", 365)

        self.amount_ranges = tx.get("transaction_amount_ranges", {})
        missing_ranges = set(self.financial_types) - set(self.amount_ranges)
        if missing_ranges:
            raise ValueError(
                "Missing transaction_amount_ranges configuration for "
                f"financial transaction type(s): {', '.join(sorted(missing_ranges))}"
            )

    def generate_transactions(self, account_file: str, output_file: str, customer_file: str | None = None) -> dict:
        account_path = Path(account_file)
        if not account_path.exists():
            raise FileNotFoundError(f"Account input file not found: {account_path}")

        events = []
        with account_path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            self._validate_account_columns(reader.fieldnames)
            for account in reader:
                events.extend(self._generate_account_events(account))

        if customer_file:
            events.extend(self._generate_customer_events(Path(customer_file)))

        events.sort(key=lambda item: item["transaction_timestamp"])
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.HEADER)
            writer.writeheader()
            for event in events:
                writer.writerow({
                    **event,
                    "account_number": event["account_number"] or "",
                    "transaction_timestamp": event["transaction_timestamp"].isoformat(sep=" "),
                    "created_at": event["created_at"].isoformat(sep=" "),
                })

        return {"transactions_generated": len(events), "output_file": str(output_path)}

    def _generate_account_events(self, account: dict) -> list:
        opened = DateUtils.parse_date(account["opened_date"])
        status = account["account_status"]
        events = [self._event(account, "OFA", opened)]

        if status != "ACTIVE":
            events.append(self._event(
                account, "OSC",
                DateUtils.parse_datetime(account["status_changed_at"]) if account.get("status_changed_at")
                else DateUtils.random_datetime(opened, DateUtils.today(), self.random.probability)
            ))

        if status == "CLOSED":
            end = DateUtils.parse_date(account["closed_date"])
        elif status == "DORMANT":
            end = DateUtils.add_days(DateUtils.today(), -self.dormant_cap_days)
            end = max(end, opened)
        elif status == "PENDING_CLOSE":
            # Closure has been requested — no further financial activity
            # is generated past that point, same reasoning as CLOSED/DORMANT.
            # Previously this fell through to the "else" branch below and
            # was treated identically to ACTIVE, generating activity right
            # up to today despite the pending closure.
            end = DateUtils.parse_datetime(account["status_changed_at"]).date()
            end = max(end, opened)
        else:
            end = DateUtils.today()

        if status != "CLOSED" or end >= opened:
            count = self.random.randint(self.minimum, self.maximum)
            for _ in range(count):
                events.append(self._financial_event(account, opened, end, status))

        return events

    def _generate_customer_events(self, customer_path: Path) -> list:
        if not customer_path.exists():
            raise FileNotFoundError(f"Customer input file not found: {customer_path}")

        events = []
        with customer_path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            required = {"sort_code", "customer_number", "customer_status", "created_at", "status_changed_at"}
            if not reader.fieldnames or required - set(reader.fieldnames):
                raise ValueError("CUSTOMER CSV missing columns required for lifecycle events.")

            for customer in reader:
                created = DateUtils.parse_datetime(customer["created_at"])
                events.append(self._customer_event(
                    customer["sort_code"], customer["customer_number"], "OCC", created
                ))
                if customer["customer_status"] == "DELETED":
                    changed = DateUtils.parse_datetime(customer["status_changed_at"])
                    events.append(self._customer_event(
                        customer["sort_code"], customer["customer_number"], "ODC", changed
                    ))
        return events

    def _financial_event(self, account: dict, start, end, account_status: str) -> dict:
        tx_type = self.random.choice(self.financial_types)
        timestamp = DateUtils.random_datetime(start, end, self.random.probability)
        status_code = "SUCCESS"
        reason = ""

        if account_status == "FROZEN" and self.random.probability() < self.frozen_declined_rate:
            status_code = "DECLINED"
            reason = self.random.choice(self.failure_mapping.get("DECLINED", ["ACCOUNT_FROZEN"]))
        elif account_status == "CLOSED":
            status_code = "REJECTED"
            reason = self.random.choice(self.failure_mapping.get("REJECTED", ["ACCOUNT_CLOSED"]))

        return {
            "sort_code": account["sort_code"],
            "account_number": account["account_number"],
            "customer_number": account["customer_number"],
            "transaction_timestamp": timestamp,
            "transaction_type": tx_type,
            "transaction_amount": self._amount(tx_type),
            "transaction_description": self.definitions[tx_type]["description"],
            "status_code": status_code,
            "status_reason": reason,
            "created_at": DateUtils.now(),
        }

    def _event(self, account: dict, tx_type: str, event_date) -> dict:
        timestamp = DateUtils.random_datetime(event_date, event_date, self.random.probability)
        return {
            "sort_code": account["sort_code"],
            "account_number": account["account_number"],
            "customer_number": account["customer_number"],
            "transaction_timestamp": timestamp,
            "transaction_type": tx_type,
            "transaction_amount": Decimal("0.00"),
            "transaction_description": self.definitions[tx_type]["description"],
            "status_code": "SUCCESS",
            "status_reason": "",
            "created_at": DateUtils.now(),
        }

    def _customer_event(self, sort_code: str, customer_number: str, tx_type: str, timestamp) -> dict:
        return {
            "sort_code": sort_code,
            "account_number": None,
            "customer_number": customer_number,
            "transaction_timestamp": timestamp,
            "transaction_type": tx_type,
            "transaction_amount": Decimal("0.00"),
            "transaction_description": self.definitions[tx_type]["description"],
            "status_code": "SUCCESS",
            "status_reason": "",
            "created_at": DateUtils.now(),
        }

    def _amount(self, tx_type: str):
        rule = self.amount_ranges[tx_type]
        return self.random.decimal(float(rule["minimum"]), float(rule["maximum"]))

    @staticmethod
    def _validate_account_columns(fieldnames):
        required = {
            "sort_code", "account_number", "customer_number", "opened_date",
            "account_status", "closed_date", "status_changed_at",
        }
        if not fieldnames or required - set(fieldnames):
            raise ValueError("ACCOUNT CSV missing columns required for Transaction_History generation.")

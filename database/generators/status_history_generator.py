"""
Generate STATUS_HISTORY records from final CUSTOMER and ACCOUNT states.

The generator synthesizes plausible transitions because source generators emit
final entity state rather than event-by-event history.
"""

import csv
from pathlib import Path

from utils.date_utils import DateUtils
from utils.random_utils import RandomUtils


class StatusHistoryGenerator:
    HEADER = [
        "entity_type", "sort_code", "entity_number", "previous_status",
        "status_reason", "new_status", "changed_at",
    ]

    def __init__(self, config: dict):
        self.config = config
        self.random = RandomUtils(config["random"]["seed"] + 3)
        settings = config.get("status_history", {})
        self.enabled = settings.get("enabled", True)
        self.max_entries = settings.get("max_entries_per_entity", 3)

    def generate_status_history(self, customer_file: str, account_file: str, output_file: str) -> dict:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.enabled:
            self._write(output_path, [])
            return {"history_entries_generated": 0, "enabled": False, "output_file": str(output_path)}

        entries = []
        entries.extend(self._customer_history(Path(customer_file)))
        entries.extend(self._account_history(Path(account_file)))
        entries.sort(key=lambda item: item["changed_at"])
        self._write(output_path, entries)

        return {
            "history_entries_generated": len(entries),
            "customer_history_entries": sum(e["entity_type"] == "CUSTOMER" for e in entries),
            "account_history_entries": sum(e["entity_type"] == "ACCOUNT" for e in entries),
            "enabled": True,
            "output_file": str(output_path),
        }

    def _customer_history(self, path: Path) -> list:
        entries = []
        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                status = row["customer_status"]
                # PENDING is the initial state a customer is created in —
                # not a state reached by transitioning from ACTIVE. There
                # is no prior state to log, so it gets no history entry,
                # same as ACTIVE.
                if status in ("ACTIVE", "PENDING"):
                    continue
                final_time = DateUtils.parse_datetime(row["status_changed_at"])
                if status == "DELETED":
                    pending_time = DateUtils.add_days(final_time, -self.random.randint(7, 30))
                    entries.extend([
                        self._entry("CUSTOMER", row, "ACTIVE", "", "PENDING_DELETE", pending_time),
                        self._entry("CUSTOMER", row, "PENDING_DELETE", row["status_reason"], "DELETED", final_time),
                    ])
                else:
                    entries.append(self._entry(
                        "CUSTOMER", row, "ACTIVE", row["status_reason"], status, final_time
                    ))
        return self._cap(entries)

    def _account_history(self, path: Path) -> list:
        entries = []
        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                status = row["account_status"]
                if status == "ACTIVE":
                    continue
                final_time = DateUtils.parse_datetime(row["status_changed_at"])
                if status == "CLOSED":
                    pending_time = DateUtils.add_days(final_time, -self.random.randint(1, 14))
                    entries.extend([
                        self._entry("ACCOUNT", row, "ACTIVE", "", "PENDING_CLOSE", pending_time),
                        self._entry("ACCOUNT", row, "PENDING_CLOSE", row["status_reason"], "CLOSED", final_time),
                    ])
                else:
                    entries.append(self._entry(
                        "ACCOUNT", row, "ACTIVE", row["status_reason"], status, final_time
                    ))
        return self._cap(entries)

    def _entry(self, entity_type, row, previous, reason, new, changed_at):
        number_key = "customer_number" if entity_type == "CUSTOMER" else "account_number"
        return {
            "entity_type": entity_type,
            "sort_code": row["sort_code"],
            "entity_number": row[number_key],
            "previous_status": previous,
            "status_reason": reason or "",
            "new_status": new,
            "changed_at": changed_at,
        }

    def _cap(self, entries: list) -> list:
        grouped = {}
        for entry in entries:
            key = (entry["entity_type"], entry["sort_code"], entry["entity_number"])
            grouped.setdefault(key, []).append(entry)

        capped = []
        for group in grouped.values():
            group.sort(key=lambda item: item["changed_at"])
            capped.extend(group[:self.max_entries])
        return capped

    def _write(self, output_path: Path, entries: list):
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.HEADER)
            writer.writeheader()
            for entry in entries:
                row = dict(entry)
                row["changed_at"] = row["changed_at"].isoformat(sep=" ")
                writer.writerow(row)

"""
FIXTURE MESSAGE ADAPTER
=======================

Phase 0 stores test messages in JSON. Each JSON item has two separate parts:
the email-shaped message and ground_truth used only to score the agent later.
This adapter converts only the message part into InboundMessage. Keeping the
ground truth separate prevents it from influencing classification or routing.
"""

# json is Python's standard library reader for JSON files.
import json

# datetime converts the fixture's existing text date into a date/time object.
from datetime import datetime

# Path is a readable way to build paths without manually joining slash text.
from pathlib import Path

# Any documents that a fixture can contain values of several possible types.
from typing import Any

# This import supports both normal package imports in tests and the existing
# command-line scripts that run from inside the agent directory.
try:
    from agent.contracts import InboundMessage
except ImportError:
    from contracts import InboundMessage


# ---------------------------------------------------------------------------
# FILE LOCATION
# ---------------------------------------------------------------------------

# __file__ is this module's location. Resolving it first means this default
# works regardless of the current terminal directory.
DEFAULT_FIXTURES_FILE = Path(__file__).resolve().parents[1] / "output" / "test_messages.json"


# ---------------------------------------------------------------------------
# SMALL CONVERSION HELPERS
# ---------------------------------------------------------------------------

def parse_fixture_date(date_text: str | None) -> datetime | None:
    """Convert the fixture's YYYY-MM-DD HH:MM:SS text into datetime.

    A missing date is represented as None because the shared contract allows
    sources that do not supply a received time.
    """

    if not date_text:
        return None

    return datetime.strptime(date_text, "%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# FIXTURE NORMALIZATION
# ---------------------------------------------------------------------------

def normalize_fixture_message(fixture: dict[str, Any]) -> InboundMessage:
    """Convert one fixture's message block into the production contract."""

    # The fixture's top level also contains ground_truth. Reading only this
    # nested message dictionary is the important separation in Phase 4A.
    fixture_message = fixture["message"]

    # The fixture has one "to" string while the contract supports many
    # recipients, so wrap the string in a list when it is present.
    recipient_addresses = []
    if fixture_message.get("to"):
        recipient_addresses.append(fixture_message["to"])

    return InboundMessage(
        source="fixture",
        source_message_id=fixture_message["id"],
        source_thread_id=fixture_message.get("threadId"),
        from_address=fixture_message.get("from"),
        to_addresses=recipient_addresses,
        subject=fixture_message.get("subject", ""),
        body_text=fixture_message.get("body", ""),
        received_at=parse_fixture_date(fixture_message.get("date")),
        rfc_message_id=None,
        headers=None,
    )


def load_fixture_messages(path: Path = DEFAULT_FIXTURES_FILE) -> list[tuple[InboundMessage, dict[str, Any]]]:
    """Load messages plus separate ground truth for fixture evaluation only."""

    # UTF-8 is the standard text encoding for this project's JSON files.
    with path.open("r", encoding="utf-8") as input_handle:
        fixture_records = json.load(input_handle)

    normalized_records = []
    for fixture_record in fixture_records:
        normalized_message = normalize_fixture_message(fixture_record)

        # Ground truth remains outside the InboundMessage object. Evaluation
        # callers may use it after processing has completed.
        ground_truth = fixture_record.get("ground_truth", {})
        normalized_records.append((normalized_message, ground_truth))

    return normalized_records

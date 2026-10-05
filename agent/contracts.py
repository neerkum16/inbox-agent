"""
INBOUND MESSAGE CONTRACT
========================

Every inbox source needs to give the agent the same simple description of an
incoming message. Test fixtures already contain email-like dictionaries, and a
future Gmail adapter will receive Gmail API dictionaries. The rest of the
agent should not need to know which source produced a message.

This module defines that shared description. It intentionally does NOT contain
fixture ground truth. Ground truth is useful for scoring a test, but including
it here could accidentally let production business logic use the known answer.
"""

# dataclasses is part of Python's standard library. @dataclass creates the
# usual __init__ method for us from the fields below, while keeping the class
# easier for a beginner to read than a hand-written constructor.
from dataclasses import dataclass

# datetime is also part of the standard library. It represents a real point in
# time, rather than storing every received date as an ambiguous text string.
from datetime import datetime

# Literal is a typing helper. It documents that source is limited to the two
# source names currently supported by the application contract.
from typing import Literal


# ---------------------------------------------------------------------------
# NORMALIZED INBOUND MESSAGE
# ---------------------------------------------------------------------------

@dataclass
class InboundMessage:
    """One inbound email after an adapter has converted it to application data.

    Adapters may keep source-specific information in headers, but all business
    logic uses the common fields below. The type annotations document the
    intended kind of each value; Python still creates the normal constructor.
    """

    # The adapter that supplied the message. A future Gmail adapter will use
    # "gmail"; fixture evaluation uses "fixture".
    source: Literal["fixture", "gmail"]

    # The provider's unique ID for this individual message.
    source_message_id: str

    # The provider's conversation/thread ID. Some systems may not have one.
    source_thread_id: str | None

    # The sender's mailbox address after adapter-level extraction, if known.
    from_address: str | None

    # A list is used because a message can have more than one recipient.
    to_addresses: list[str]

    # The human-readable subject and plain text body supplied to the pipeline.
    subject: str
    body_text: str

    # The adapter converts a known received date into datetime, or uses None
    # when the source did not provide a trustworthy date.
    received_at: datetime | None

    # This is the RFC Message-ID email header, not a Gmail API message ID.
    rfc_message_id: str | None

    # Optional source-specific header values. Ground truth must never go here.
    headers: dict | None

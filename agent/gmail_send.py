"""
PHASE 5C - GMAIL AUTONOMOUS SEND SUPPORT
=========================================

This module contains only Gmail transport operations needed to safely send an
already-created reply draft.

The banking pipeline remains responsible for identity, live facts, drafting,
and routing. This module does not decide whether a message is safe to send.

Phase 5C deliberately sends an existing Gmail draft with drafts.send rather
than calling messages.send directly. This keeps the generated draft as the
single persisted outbound artifact and allows the delivery-state table to
correlate one source message to one Gmail draft.
"""

import hashlib



# =============================================================================
# DETERMINISTIC OUTBOUND MESSAGE ID
# =============================================================================


def build_outbound_message_id(source, source_message_id):
    """
    Build a deterministic RFC Message-ID for one source message.

    The value is stable across retries and is used to detect a send that may
    have succeeded even when the API response was lost.
    """

    digest = hashlib.sha256(
        (str(source) + ":" + str(source_message_id)).encode("utf-8")
    ).hexdigest()[:32]

    return "<inbox-agent-" + digest + "@gmail-agent.local>"


# =============================================================================
# GMAIL RESOURCE LOOKUPS
# =============================================================================


def find_draft_by_rfc_message_id(service, user_id, rfc_message_id):
    """
    Find an existing Gmail draft containing the specified RFC Message-ID.

    Returns the first matching draft resource or None.
    """

    if not rfc_message_id:
        return None

    query = "rfc822msgid:" + rfc_message_id

    response = (
        service.users()
        .drafts()
        .list(
            userId=user_id,
            q=query,
            maxResults=10,
        )
        .execute()
    )

    drafts = response.get("drafts") or []
    return drafts[0] if drafts else None


def get_draft(service, user_id, draft_id):
    """Get a Gmail draft resource by ID."""

    try:
        return (
            service.users()
            .drafts()
            .get(
                userId=user_id,
                id=draft_id,
            )
            .execute()
        )
    except Exception as error:
        response = getattr(error, "resp", None)
        if response is not None and getattr(response, "status", None) == 404:
            return None
        raise


def find_sent_message_by_rfc_message_id(service, user_id, rfc_message_id):
    """
    Find a sent message by its deterministic RFC Message-ID.

    This is used after an ambiguous send failure. If the message is already
    present in Sent, the agent records the send as successful and does not send
    again.
    """

    if not rfc_message_id:
        return None

    query = "in:sent rfc822msgid:" + rfc_message_id

    response = (
        service.users()
        .messages()
        .list(
            userId=user_id,
            q=query,
            maxResults=10,
        )
        .execute()
    )

    messages = response.get("messages") or []
    return messages[0] if messages else None


# =============================================================================
# GMAIL SEND
# =============================================================================


def send_gmail_draft(service, user_id, draft_id):
    """
    Send an existing Gmail draft.

    Gmail deletes the draft and creates the resulting SENT message. The Gmail
    API returns that sent Message resource on success.
    """

    if not draft_id:
        raise ValueError("Cannot send Gmail draft without a draft ID.")

    return (
        service.users()
        .drafts()
        .send(
            userId=user_id,
            body={"id": draft_id},
        )
        .execute()
    )

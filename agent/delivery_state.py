"""
DURABLE GMAIL DELIVERY STATE

Persists autonomous outbound-delivery state in PostgreSQL.

Delivery lifecycle:

    PREPARED
        |
        v
    SENDING
       / \
      /   \
     v     v
   SENT   UNKNOWN
            |
            v
         SENDING

FAILED is also retryable.

Delivery idempotency is keyed by:

    (source, source_message_id)

This module manages PostgreSQL delivery state only.
It does not perform Gmail operations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from psycopg2.extras import Json


def _row_to_dict(cursor, row) -> Optional[dict[str, Any]]:
    """Convert a psycopg2 row into a normal dictionary."""

    if row is None:
        return None

    if isinstance(row, dict):
        return dict(row)

    columns = [description[0] for description in cursor.description]
    return dict(zip(columns, row))


def get_delivery_state(
    connection,
    source: str,
    source_message_id: str,
) -> Optional[dict[str, Any]]:
    """
    Retrieve the durable delivery state for an inbound message.
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                source,
                source_message_id,
                source_thread_id,
                status,
                outbound_message_id,
                gmail_draft_id,
                gmail_draft_message_id,
                gmail_sent_message_id,
                attempt_count,
                first_prepared_at,
                sending_started_at,
                sent_at,
                updated_at,
                last_error,
                processing_result
            FROM message_delivery
            WHERE source = %s
              AND source_message_id = %s
            """,
            (
                source,
                source_message_id,
            ),
        )

        return _row_to_dict(cursor, cursor.fetchone())


def prepare_delivery(
    connection,
    source: str,
    source_message_id: str,
    source_thread_id: Optional[str],
    outbound_message_id: str,
    processing_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Create the durable delivery record.

    If a record already exists, return it unchanged.

    This guarantees that a retry does not replace the original
    processing result with a newly generated result.
    """

    existing = get_delivery_state(
        connection,
        source,
        source_message_id,
    )

    if existing is not None:
        return existing

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO message_delivery
            (
                source,
                source_message_id,
                source_thread_id,
                status,
                outbound_message_id,
                attempt_count,
                first_prepared_at,
                processing_result
            )
            VALUES
            (
                %s,
                %s,
                %s,
                'PREPARED',
                %s,
                0,
                CURRENT_TIMESTAMP,
                %s
            )
            RETURNING
                source,
                source_message_id,
                source_thread_id,
                status,
                outbound_message_id,
                gmail_draft_id,
                gmail_draft_message_id,
                gmail_sent_message_id,
                attempt_count,
                first_prepared_at,
                sending_started_at,
                sent_at,
                updated_at,
                last_error,
                processing_result
            """,
            (
                source,
                source_message_id,
                source_thread_id,
                outbound_message_id,
                Json(processing_result),
            ),
        )

        state = _row_to_dict(cursor, cursor.fetchone())

    connection.commit()

    return state


def attach_draft(
    connection,
    source: str,
    source_message_id: str,
    gmail_draft_id: str,
    gmail_draft_message_id: str,
) -> dict[str, Any]:
    """
    Persist Gmail draft ID and Gmail draft message ID.

    This is done before sending so a retry can reuse the same draft.
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE message_delivery
            SET
                gmail_draft_id = %s,
                gmail_draft_message_id = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE source = %s
              AND source_message_id = %s
            RETURNING
                source,
                source_message_id,
                source_thread_id,
                status,
                outbound_message_id,
                gmail_draft_id,
                gmail_draft_message_id,
                gmail_sent_message_id,
                attempt_count,
                first_prepared_at,
                sending_started_at,
                sent_at,
                updated_at,
                last_error,
                processing_result
            """,
            (
                gmail_draft_id,
                gmail_draft_message_id,
                source,
                source_message_id,
            ),
        )

        state = _row_to_dict(cursor, cursor.fetchone())

    if state is None:
        connection.rollback()
        raise RuntimeError(
            "Cannot attach Gmail draft: delivery state does not exist"
        )

    connection.commit()

    return state


def mark_sending(
    connection,
    source: str,
    source_message_id: str,
) -> int:
    """
    Transition delivery to SENDING.

    Increments attempt_count and returns the new attempt number.
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE message_delivery
            SET
                status = 'SENDING',
                attempt_count = attempt_count + 1,
                sending_started_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP,
                last_error = NULL
            WHERE source = %s
              AND source_message_id = %s
              AND status IN
                  (
                      'PREPARED',
                      'UNKNOWN',
                      'FAILED',
                      'SENDING'
                  )
            RETURNING attempt_count
            """,
            (
                source,
                source_message_id,
            ),
        )

        row = cursor.fetchone()

    if row is None:
        connection.rollback()
        raise RuntimeError(
            "Cannot mark delivery SENDING: "
            "delivery state does not exist or is not retryable"
        )

    if isinstance(row, dict):
        attempts = row["attempt_count"]
    else:
        attempts = row[0]

    connection.commit()

    return attempts


def mark_sent(
    connection,
    source: str,
    source_message_id: str,
    gmail_sent_message_id: str,
) -> dict[str, Any]:
    """
    Mark delivery as SENT and persist the Gmail sent-message ID.

    SENT is the terminal delivery state.
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE message_delivery
            SET
                status = 'SENT',
                gmail_sent_message_id = %s,
                sent_at = COALESCE(sent_at, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP,
                last_error = NULL
            WHERE source = %s
              AND source_message_id = %s
            RETURNING
                source,
                source_message_id,
                source_thread_id,
                status,
                outbound_message_id,
                gmail_draft_id,
                gmail_draft_message_id,
                gmail_sent_message_id,
                attempt_count,
                first_prepared_at,
                sending_started_at,
                sent_at,
                updated_at,
                last_error,
                processing_result
            """,
            (
                gmail_sent_message_id,
                source,
                source_message_id,
            ),
        )

        state = _row_to_dict(cursor, cursor.fetchone())

    if state is None:
        connection.rollback()
        raise RuntimeError(
            "Cannot mark delivery SENT: delivery state does not exist"
        )

    connection.commit()

    return state


def mark_unknown(
    connection,
    source: str,
    source_message_id: str,
    error: str,
) -> dict[str, Any]:
    """
    Mark delivery outcome as UNKNOWN.

    UNKNOWN means the application cannot prove whether Gmail accepted
    the send.

    The existing Gmail draft is deliberately preserved.
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE message_delivery
            SET
                status = 'UNKNOWN',
                last_error = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE source = %s
              AND source_message_id = %s
            RETURNING
                source,
                source_message_id,
                source_thread_id,
                status,
                outbound_message_id,
                gmail_draft_id,
                gmail_draft_message_id,
                gmail_sent_message_id,
                attempt_count,
                first_prepared_at,
                sending_started_at,
                sent_at,
                updated_at,
                last_error,
                processing_result
            """,
            (
                error,
                source,
                source_message_id,
            ),
        )

        state = _row_to_dict(cursor, cursor.fetchone())

    if state is None:
        connection.rollback()
        raise RuntimeError(
            "Cannot mark delivery UNKNOWN: delivery state does not exist"
        )

    connection.commit()

    return state


def mark_failed(
    connection,
    source: str,
    source_message_id: str,
    error: str,
) -> dict[str, Any]:
    """
    Mark delivery as FAILED.

    FAILED means the application knows that the send did not happen
    and the delivery can safely be retried.
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE message_delivery
            SET
                status = 'FAILED',
                last_error = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE source = %s
              AND source_message_id = %s
            RETURNING
                source,
                source_message_id,
                source_thread_id,
                status,
                outbound_message_id,
                gmail_draft_id,
                gmail_draft_message_id,
                gmail_sent_message_id,
                attempt_count,
                first_prepared_at,
                sending_started_at,
                sent_at,
                updated_at,
                last_error,
                processing_result
            """,
            (
                error,
                source,
                source_message_id,
            ),
        )

        state = _row_to_dict(cursor, cursor.fetchone())

    if state is None:
        connection.rollback()
        raise RuntimeError(
            "Cannot mark delivery FAILED: delivery state does not exist"
        )

    connection.commit()

    return state


def serialize_delivery_state(
    state: Optional[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """
    Convert a delivery-state dictionary into JSON-safe data.
    """

    if state is None:
        return None

    result = dict(state)

    for key, value in result.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()

    return result
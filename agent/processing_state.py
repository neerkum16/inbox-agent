"""
PROCESSING STATE / IDEMPOTENCY
==============================

This module stores durable processing state for inbound messages.

The key idea is simple:
    (source, source_message_id)

uniquely identifies one message within the application.  The database keeps
that identity across application restarts, so the same Gmail message is not
processed repeatedly.

This module does not know anything about Gmail, classification, drafting, or
routing.  It only manages durable processing state.
"""

import json

import psycopg2.extras


DEFAULT_STALE_AFTER_MINUTES = 30


def claim_message(
    connection,
    source,
    source_message_id,
    source_thread_id=None,
    stale_after_minutes=DEFAULT_STALE_AFTER_MINUTES,
):
    """
    Atomically claim a message for processing.

    Returns a dictionary containing:

        claimed=True
            The caller owns the message and may process it.

        claimed=False
            Another completed/freshly-processing record already owns it, so
            the caller should skip the message.

    FAILED messages can be retried.  A PROCESSING message can also be
    reclaimed when it has been stuck longer than stale_after_minutes.
    """

    if not source or not source_message_id:
        raise ValueError("source and source_message_id are required")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO message_processing
            (
                source,
                source_message_id,
                source_thread_id,
                status,
                processing_started_at,
                last_error,
                processing_result
            )
            VALUES
            (
                %s,
                %s,
                %s,
                'PROCESSING',
                CURRENT_TIMESTAMP,
                NULL,
                NULL
            )
            ON CONFLICT (source, source_message_id) DO NOTHING
            RETURNING source, source_message_id, status;
            """,
            (source, source_message_id, source_thread_id),
        )
        inserted_row = cursor.fetchone()

        if inserted_row is not None:
            connection.commit()
            return {
                "claimed": True,
                "status": "PROCESSING",
                "reason": "new_message",
                "processing_result": None,
            }

        # A previous attempt exists.  FAILED messages are safe to retry.
        # A stale PROCESSING record is also retryable because the previous
        # application instance may have crashed after claiming it.
        cursor.execute(
            """
            UPDATE message_processing
            SET
                status = 'PROCESSING',
                source_thread_id = COALESCE(%s, source_thread_id),
                processing_started_at = CURRENT_TIMESTAMP,
                processing_completed_at = NULL,
                last_error = NULL,
                processing_result = NULL
            WHERE source = %s
              AND source_message_id = %s
              AND
              (
                  status = 'FAILED'
                  OR status = 'RECEIVED'
                  OR
                  (
                      status = 'PROCESSING'
                      AND processing_started_at <
                          CURRENT_TIMESTAMP - (%s * INTERVAL '1 minute')
                  )
              )
            RETURNING source, source_message_id, status;
            """,
            (
                source_thread_id,
                source,
                source_message_id,
                stale_after_minutes,
            ),
        )
        reclaimed_row = cursor.fetchone()

        if reclaimed_row is not None:
            connection.commit()
            return {
                "claimed": True,
                "status": "PROCESSING",
                "reason": "retry_or_stale_reclaim",
                "processing_result": None,
            }

        # The existing record is either COMPLETED or currently being handled
        # by another process.  Read its state so the caller can explain why it
        # skipped the message and, for COMPLETED, reuse the stored result.
        cursor.execute(
            """
            SELECT status, processing_result, last_error
            FROM message_processing
            WHERE source = %s
              AND source_message_id = %s;
            """,
            (source, source_message_id),
        )
        existing_row = cursor.fetchone()

    connection.commit()

    if existing_row is None:
        # This should be extremely unlikely because the INSERT and SELECT are
        # protected by the primary key.  Treat it as a safe skip rather than
        # accidentally processing an unknown state.
        return {
            "claimed": False,
            "status": "UNKNOWN",
            "reason": "processing_record_not_found",
            "processing_result": None,
        }

    return {
        "claimed": False,
        "status": existing_row["status"],
        "reason": "already_processed_or_in_progress",
        "processing_result": existing_row["processing_result"],
        "last_error": existing_row["last_error"],
    }


def mark_completed(connection, source, source_message_id, processing_result):
    """Mark a claimed message as successfully completed and store its result."""

    serializable_result = json.loads(
        json.dumps(processing_result, default=str)
    )

    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE message_processing
            SET
                status = 'COMPLETED',
                processing_completed_at = CURRENT_TIMESTAMP,
                last_error = NULL,
                processing_result = %s
            WHERE source = %s
              AND source_message_id = %s
              AND status = 'PROCESSING';
            """,
            (
                psycopg2.extras.Json(serializable_result),
                source,
                source_message_id,
            ),
        )

        if cursor.rowcount != 1:
            connection.rollback()
            raise RuntimeError(
                "Could not mark message as COMPLETED: "
                + str(source)
                + "/"
                + str(source_message_id)
            )

    connection.commit()


def mark_failed(connection, source, source_message_id, error):
    """Mark a claimed message as failed so a later run can retry it."""

    error_text = str(error)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE message_processing
            SET
                status = 'FAILED',
                processing_completed_at = NULL,
                last_error = %s
            WHERE source = %s
              AND source_message_id = %s
              AND status = 'PROCESSING';
            """,
            (error_text, source, source_message_id),
        )

        if cursor.rowcount != 1:
            connection.rollback()
            raise RuntimeError(
                "Could not mark message as FAILED: "
                + str(source)
                + "/"
                + str(source_message_id)
            )

    connection.commit()

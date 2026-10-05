"""
PHASE 4E - PROCESSING STATE / IDEMPOTENCY TESTS

These are integration tests against the real PostgreSQL bankdb.
They use temporary unique message IDs and clean their rows up afterward.

Run after applying phase4e_message_processing.sql:

    python test_processing_state.py
"""

import os
import uuid

import psycopg2
import psycopg2.extras

from agent.processing_state import claim_message, mark_completed, mark_failed


SOURCE = "phase4e_test"


def connect_to_database():
    password = os.environ.get("PGPASSWORD")
    if not password:
        raise RuntimeError("PGPASSWORD environment variable is not set.")

    return psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="bankdb",
        user="postgres",
        password=password,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def assert_equal(actual, expected, description):
    if actual != expected:
        raise AssertionError(
            description
            + ": expected "
            + repr(expected)
            + ", got "
            + repr(actual)
        )


def main():
    connection = connect_to_database()
    message_ids = []

    try:
        # ---------------------------------------------------------------------
        # TEST 1 - FIRST CLAIM SUCCEEDS
        # ---------------------------------------------------------------------
        message_id = "first-" + uuid.uuid4().hex
        message_ids.append(message_id)

        result = claim_message(
            connection,
            SOURCE,
            message_id,
            "thread-1",
        )
        assert_equal(result["claimed"], True, "first claim should succeed")
        assert_equal(result["status"], "PROCESSING", "first claim status")

        # ---------------------------------------------------------------------
        # TEST 2 - SAME MESSAGE CANNOT BE CLAIMED TWICE WHILE PROCESSING
        # ---------------------------------------------------------------------
        result = claim_message(
            connection,
            SOURCE,
            message_id,
            "thread-1",
        )
        assert_equal(result["claimed"], False, "fresh processing record should skip")
        assert_equal(result["status"], "PROCESSING", "fresh duplicate status")

        # ---------------------------------------------------------------------
        # TEST 3 - COMPLETED MESSAGE IS SKIPPED
        # ---------------------------------------------------------------------
        stored_result = {
            "classification": {"extracted_category": "balance_inquiry"},
            "draft": {"draft_reply": "test"},
            "routing": {"tier": "autonomous"},
        }
        mark_completed(connection, SOURCE, message_id, stored_result)

        result = claim_message(
            connection,
            SOURCE,
            message_id,
            "thread-1",
        )
        assert_equal(result["claimed"], False, "completed message should skip")
        assert_equal(result["status"], "COMPLETED", "completed duplicate status")
        assert_equal(
            result["processing_result"]["routing"]["tier"],
            "autonomous",
            "stored completed result should be returned",
        )

        # ---------------------------------------------------------------------
        # TEST 4 - FAILED MESSAGE CAN BE RETRIED
        # ---------------------------------------------------------------------
        failed_message_id = "failed-" + uuid.uuid4().hex
        message_ids.append(failed_message_id)

        result = claim_message(
            connection,
            SOURCE,
            failed_message_id,
        )
        assert_equal(result["claimed"], True, "failed-test initial claim")

        mark_failed(
            connection,
            SOURCE,
            failed_message_id,
            "simulated processing failure",
        )

        result = claim_message(
            connection,
            SOURCE,
            failed_message_id,
        )
        assert_equal(result["claimed"], True, "failed message should be retryable")
        assert_equal(result["status"], "PROCESSING", "retry status")

        # ---------------------------------------------------------------------
        # TEST 5 - STALE PROCESSING RECORD CAN BE RECLAIMED
        # ---------------------------------------------------------------------
        stale_message_id = "stale-" + uuid.uuid4().hex
        message_ids.append(stale_message_id)

        result = claim_message(
            connection,
            SOURCE,
            stale_message_id,
        )
        assert_equal(result["claimed"], True, "stale-test initial claim")

        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE message_processing
                SET processing_started_at = CURRENT_TIMESTAMP - INTERVAL '31 minutes'
                WHERE source = %s AND source_message_id = %s;
                """,
                (SOURCE, stale_message_id),
            )
        connection.commit()

        result = claim_message(
            connection,
            SOURCE,
            stale_message_id,
            stale_after_minutes=30,
        )
        assert_equal(result["claimed"], True, "stale processing record should be reclaimed")

        # ---------------------------------------------------------------------
        # TEST 6 - DIFFERENT SOURCE CAN REUSE THE SAME MESSAGE ID
        # ---------------------------------------------------------------------
        shared_message_id = "shared-" + uuid.uuid4().hex
        message_ids.append(shared_message_id)

        gmail_result = claim_message(
            connection,
            "gmail",
            shared_message_id,
        )
        fixture_result = claim_message(
            connection,
            "fixture",
            shared_message_id,
        )
        assert_equal(gmail_result["claimed"], True, "gmail source claim")
        assert_equal(fixture_result["claimed"], True, "fixture source claim")

        print("PASS: first claim")
        print("PASS: duplicate PROCESSING message is skipped")
        print("PASS: COMPLETED message is skipped and stored result is available")
        print("PASS: FAILED message can be retried")
        print("PASS: stale PROCESSING message can be reclaimed")
        print("PASS: source + message ID form the idempotency key")
        print("")
        print("All Phase 4E processing-state tests passed.")

    finally:
        # The tests intentionally leave no processing records behind.
        with connection.cursor() as cursor:
            for message_id in message_ids:
                cursor.execute(
                    "DELETE FROM message_processing WHERE source = %s AND source_message_id = %s;",
                    (SOURCE, message_id),
                )
                cursor.execute(
                    "DELETE FROM message_processing WHERE source = 'gmail' AND source_message_id = %s;",
                    (message_id,),
                )
                cursor.execute(
                    "DELETE FROM message_processing WHERE source = 'fixture' AND source_message_id = %s;",
                    (message_id,),
                )
        connection.commit()
        connection.close()


if __name__ == "__main__":
    main()

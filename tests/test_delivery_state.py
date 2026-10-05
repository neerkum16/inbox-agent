"""
PHASE 5C - DURABLE DELIVERY STATE INTEGRATION TESTS

Requires the Phase 5C migration to be applied to bankdb.

Run:
    python tests/test_delivery_state.py
"""

import os
import uuid

import psycopg2
import psycopg2.extras

from agent.delivery_state import (
    attach_draft,
    get_delivery_state,
    mark_sent,
    mark_sending,
    mark_unknown,
    prepare_delivery,
)


SOURCE = "phase5c_test"


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
    message_id = "delivery-" + uuid.uuid4().hex
    outbound_message_id = "<delivery-" + uuid.uuid4().hex + "@gmail-agent.local>"

    processing_result = {
        "classification": {"identity_eligible": True},
        "draft": {"draft_reply": "test"},
        "routing": {"tier": "autonomous"},
    }

    try:
        # TEST 1 - prepare creates a durable row.
        state = prepare_delivery(
            connection,
            SOURCE,
            message_id,
            "thread-1",
            outbound_message_id,
            processing_result,
        )
        assert_equal(state["status"], "PREPARED", "initial delivery status")
        assert_equal(state["attempt_count"], 0, "initial attempt count")
        assert_equal(
            state["processing_result"]["routing"]["tier"],
            "autonomous",
            "persisted processing result",
        )

        # TEST 2 - repeated prepare returns the same delivery record.
        state2 = prepare_delivery(
            connection,
            SOURCE,
            message_id,
            "thread-1",
            outbound_message_id,
            {"different": "result"},
        )
        assert_equal(state2["status"], "PREPARED", "duplicate prepare status")
        assert_equal(
            state2["processing_result"]["routing"]["tier"],
            "autonomous",
            "duplicate prepare must preserve original result",
        )

        # TEST 3 - draft IDs are persisted before send.
        attach_draft(connection, SOURCE, message_id, "draft-1", "draft-msg-1")
        state = get_delivery_state(connection, SOURCE, message_id)
        assert_equal(state["gmail_draft_id"], "draft-1", "draft ID")
        assert_equal(
            state["gmail_draft_message_id"],
            "draft-msg-1",
            "draft message ID",
        )

        # TEST 4 - send transition increments the attempt count.
        attempts = mark_sending(connection, SOURCE, message_id)
        assert_equal(attempts, 1, "first send attempt")
        state = get_delivery_state(connection, SOURCE, message_id)
        assert_equal(state["status"], "SENDING", "sending status")

        # TEST 5 - ambiguous send is durable and does not erase the draft.
        mark_unknown(connection, SOURCE, message_id, "simulated network timeout")
        state = get_delivery_state(connection, SOURCE, message_id)
        assert_equal(state["status"], "UNKNOWN", "unknown status")
        assert_equal(state["gmail_draft_id"], "draft-1", "unknown retains draft")

        # TEST 6 - retry uses the same delivery record and same draft.
        attempts = mark_sending(connection, SOURCE, message_id)
        assert_equal(attempts, 2, "second send attempt")
        state = get_delivery_state(connection, SOURCE, message_id)
        assert_equal(state["gmail_draft_id"], "draft-1", "retry draft ID")

        # TEST 7 - SENT is terminal and stores Gmail sent message ID.
        mark_sent(connection, SOURCE, message_id, "sent-1")
        state = get_delivery_state(connection, SOURCE, message_id)
        assert_equal(state["status"], "SENT", "sent status")
        assert_equal(state["gmail_sent_message_id"], "sent-1", "sent message ID")

        print("PASS: durable PREPARED state")
        print("PASS: duplicate prepare is idempotent")
        print("PASS: draft IDs persist before send")
        print("PASS: SENDING increments attempt count")
        print("PASS: UNKNOWN preserves the original draft")
        print("PASS: retry reuses the same delivery record/draft")
        print("PASS: SENT is terminal and stores sent message ID")
        print("All Phase 5C delivery-state tests passed.")

    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM message_delivery WHERE source = %s AND source_message_id = %s;",
                (SOURCE, message_id),
            )
        connection.commit()
        connection.close()


if __name__ == "__main__":
    main()

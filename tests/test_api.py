"""
test_api.py

Purpose
-------
A small command-line test harness for the banking inbox pipeline.

This script does NOT connect to Gmail.

Instead, it lets you simulate one inbound banking email by providing:
    - the sender's email address
    - a customer number that exists in bankdb
    - the customer's request

The simulated message is converted directly into the common
InboundMessage contract and then passed to:

    agent.pipeline.process_message()

This means we can test the real classification -> identity ->
live facts -> RAG -> draft -> routing flow without involving Gmail.
"""

# =============================================================================
# SECTION 1 - IMPORTS
# =============================================================================

import argparse
import json
import os
from datetime import datetime, timezone

# PostgreSQL database driver.
import psycopg2
import psycopg2.extras

# The common message contract used by the pipeline.
from agent.contracts import InboundMessage

# The single application pipeline.
from agent.pipeline import process_message

# These helpers already exist in gmail_agent.py.
#
# Reusing them means this test uses the same:
#   - model configuration
#   - API key configuration
#   - embedding model
# as the Gmail entry point.
from gmail_agent import create_model_client
from gmail_agent import load_embedding_model


# =============================================================================
# SECTION 2 - COMMAND-LINE ARGUMENTS
# =============================================================================

def parse_arguments():
    """
    Read the test inputs from the command line.

    Example:

        python test_api.py ^
            --email customer@example.com ^
            --customer-number 123456789 ^
            --request "Tell me the balance of my accounts."

    The request is optional. If omitted, a simple balance enquiry is used.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Test the banking pipeline using an email address and "
            "customer number from bankdb, without using Gmail."
        )
    )

    parser.add_argument(
        "--email",
        required=True,
        help="Customer email address as stored in bankdb.",
    )

    parser.add_argument(
        "--customer-number",
        required=True,
        help="Customer number as stored in bankdb.",
    )

    parser.add_argument(
        "--request",
        default="Please tell me the balance of my accounts.",
        help=(
            "The banking request to put into the simulated email body."
        ),
    )

    parser.add_argument(
        "--account-number",
        default=None,
        help=(
            "Optional account number to include in the simulated request."
        ),
    )

    return parser.parse_args()


# =============================================================================
# SECTION 3 - VERIFY TEST CUSTOMER EXISTS
# =============================================================================

def verify_customer_exists(connection, email_address, customer_number):
    """
    Check that the supplied email/customer-number combination exists
    in bankdb.

    This is only a test-input check.

    The actual identity decision is still made by the application's
    classification and identity-resolution logic inside process_message().
    """

    query = """
        SELECT
            sort_code,
            customer_number,
            customer_email
        FROM customer
        WHERE LOWER(customer_email) = LOWER(%s)
          AND customer_number = %s
        ORDER BY sort_code;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (
                email_address,
                customer_number,
            ),
        )

        rows = cursor.fetchall()

    return rows


# =============================================================================
# SECTION 4 - BUILD SIMULATED INBOUND MESSAGE
# =============================================================================

def build_test_message(email_address, customer_number, request, account_number):
    """
    Build an InboundMessage that looks like an email received by the
    banking application.

    Important:
        customer_number is deliberately placed in the BODY.

    The pipeline should extract it from the message just as it would
    extract it from a real Gmail message.

    The sender email becomes from_address.

    No identity information is injected directly into the pipeline.
    """

    if account_number:
        body = (
            "Hi,\n\n"
            "My customer number is "
            + customer_number
            + ".\n"
            "My account number is "
            + account_number
            + ".\n\n"
            + request
            + "\n\n"
            "Thanks."
        )
    else:
        body = (
            "Hi,\n\n"
            "My customer number is "
            + customer_number
            + ".\n\n"
            + request
            + "\n\n"
            "Thanks."
        )

    message = InboundMessage(
        source="test_api",
        source_message_id="test-api-" + datetime.now(
            timezone.utc
        ).strftime("%Y%m%d%H%M%S%f"),
        source_thread_id=None,
        from_address=email_address,
        to_addresses=["support@examplebank.com"],
        subject="Test Banking Enquiry",
        body_text=body,
        received_at=datetime.now(timezone.utc),
        rfc_message_id=None,
        headers={
            "from": email_address,
            "subject": "Test Banking Enquiry",
        },
    )

    return message


# =============================================================================
# SECTION 5 - PRINT RESULT
# =============================================================================

def print_result(result):
    """
    Print the most useful fields returned by the pipeline.

    The complete result is also printed as formatted JSON at the end.
    """

    print("")
    print("=" * 80)
    print("PIPELINE RESULT")
    print("=" * 80)

    if not isinstance(result, dict):
        print(result)
        return

    important_keys = [
        "message_id",
        "resolved_sort_code",
        "resolved_customer_number",
        "identity_status",
        "identity_eligible",
        "extracted_category",
        "extracted_priority",
        "extracted_entities",
        "validation_result",
        "live_facts",
        "draft_reply",
        "cited_rule_ids",
        "tier",
        "escalation_reason",
        "audit_log_id",
        "processing_status",
        "error",
    ]

    for key in important_keys:
        if key in result:
            print("")
            print(key + ":")
            print(result[key])

    print("")
    print("-" * 80)
    print("COMPLETE RESULT")
    print("-" * 80)

    print(
        json.dumps(
            result,
            indent=2,
            default=str,
        )
    )

    print("=" * 80)


# =============================================================================
# SECTION 6 - MAIN
# =============================================================================

def main():
    """
    Execute one complete simulated inbound-email request.
    """

    arguments = parse_arguments()

    connection = None

    try:
        # ---------------------------------------------------------------------
        # STEP 1 - CONNECT TO BANKDB
        # ---------------------------------------------------------------------

        print("")
        print("Connecting to bankdb...")

        connection = psycopg2.connect(
           host="localhost",
           port=5432,
           dbname="bankdb",
           user="postgres",
           password=os.environ["PGPASSWORD"],
           cursor_factory=psycopg2.extras.RealDictCursor,
       )

        print("Database connection successful.")

        # ---------------------------------------------------------------------
        # STEP 2 - VERIFY TEST INPUT
        # ---------------------------------------------------------------------

        print("")
        print("Checking email/customer number in bankdb...")

        customer_rows = verify_customer_exists(
            connection,
            arguments.email,
            arguments.customer_number,
        )

        if not customer_rows:
            print("")
            print("ERROR")
            print(
                "The supplied email/customer-number combination "
                "was not found in bankdb."
            )
            print("")
            print("Email:", arguments.email)
            print("Customer number:", arguments.customer_number)
            return

        print("")
        print("Matching customer record(s) found:", len(customer_rows))

        for row in customer_rows:
            print(
                "  Sort code:",
                row["sort_code"],
                "| Customer number:",
                row["customer_number"],
                "| Email:",
                row["customer_email"],
            )

        # ---------------------------------------------------------------------
        # STEP 3 - CREATE MODEL CLIENT
        # ---------------------------------------------------------------------

        print("")
        print("Creating model client...")

        client = create_model_client()

        print("Model client created.")

        # ---------------------------------------------------------------------
        # STEP 4 - LOAD EMBEDDING MODEL
        # ---------------------------------------------------------------------

        embedding_model = load_embedding_model()

        # ---------------------------------------------------------------------
        # STEP 5 - BUILD SIMULATED EMAIL
        # ---------------------------------------------------------------------

        message = build_test_message(
            email_address=arguments.email,
            customer_number=arguments.customer_number,
            request=arguments.request,
            account_number=arguments.account_number,
        )

        print("")
        print("=" * 80)
        print("SIMULATED INBOUND MESSAGE")
        print("=" * 80)

        print("Source:", message.source)
        print("Message ID:", message.source_message_id)
        print("From:", message.from_address)
        print("Subject:", message.subject)

        print("")
        print("BODY:")
        print(message.body_text)

        # ---------------------------------------------------------------------
        # STEP 6 - RUN THE REAL APPLICATION PIPELINE
        # ---------------------------------------------------------------------

        print("")
        print("=" * 80)
        print("RUNNING BANKING PIPELINE")
        print("=" * 80)

        result = process_message(
            message,
            client,
            connection,
            embedding_model,
        )

        # ---------------------------------------------------------------------
        # STEP 7 - DISPLAY RESULT
        # ---------------------------------------------------------------------

        print_result(result)

    finally:
        if connection is not None:
            connection.close()
            print("")
            print("Database connection closed.")


if __name__ == "__main__":
    main()

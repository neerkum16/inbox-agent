"""
test_api_enhanced.py

Purpose
-------
A command-line test harness for the banking inbox pipeline.

Unlike the original test_api.py, this version supports both POSITIVE and
NEGATIVE identity/security scenarios.

The script still uses the REAL:
    - PostgreSQL bankdb
    - LLM classification
    - identity-resolution logic
    - live account lookup
    - RAG/drafting
    - escalation/routing

It does NOT connect to Gmail and does NOT modify Gmail.

Examples
--------
Positive happy path:

    python test_api_enhanced.py --scenario positive

Correct email + account only:

    python test_api_enhanced.py --scenario account-only

Wrong customer number:

    python test_api_enhanced.py --scenario wrong-customer

Account belongs to another customer:

    python test_api_enhanced.py --scenario account-not-owned

Unregistered sender:

    python test_api_enhanced.py --scenario unregistered-email

Multiple customers using the same email, with no identifier:

    python test_api_enhanced.py --scenario ambiguous-email
"""

# =============================================================================
# SECTION 1 - IMPORTS
# =============================================================================

import argparse
import json
import os
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from agent.contracts import InboundMessage
from agent.pipeline import process_message

from gmail_agent import create_model_client
from gmail_agent import load_embedding_model


# =============================================================================
# SECTION 2 - COMMAND-LINE ARGUMENTS
# =============================================================================

SCENARIOS = [
    "positive",
    "account-only",
    "wrong-customer",
    "account-not-owned",
    "unregistered-email",
    "ambiguous-email",
]


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Run positive and negative tests against the banking pipeline."
    )

    parser.add_argument(
        "--scenario",
        choices=SCENARIOS,
        default="positive",
        help="Test scenario to execute.",
    )

    parser.add_argument(
        "--request",
        default="What is the balance of this account?",
        help="Banking request to place into the simulated email.",
    )

    return parser.parse_args()


# =============================================================================
# SECTION 3 - DATABASE CONNECTION
# =============================================================================

def connect_to_database():
    """
    Create the PostgreSQL connection.

    agent.bankdb contains lookup functions, but the current application
    architecture creates the connection at the entry point and passes it
    into the pipeline.
    """

    password = os.environ.get("PGPASSWORD")

    if not password:
        raise RuntimeError(
            "PGPASSWORD environment variable is not set."
        )

    return psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="bankdb",
        user="postgres",
        password=password,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


# =============================================================================
# SECTION 4 - TEST DATA DISCOVERY
# =============================================================================

def get_customer_with_account(connection):
    """
    Find one real customer with an email and at least one account.

    This makes the positive test independent of hard-coded test data.
    """

    query = """
        SELECT
            c.sort_code,
            c.customer_number,
            c.customer_email,
            a.account_number
        FROM customer c
        JOIN account a
            ON a.sort_code = c.sort_code
           AND a.customer_number = c.customer_number
        WHERE c.customer_email IS NOT NULL
          AND c.customer_email <> ''
        ORDER BY c.customer_number, a.account_number
        LIMIT 1;
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchone()


def get_second_customer_account(connection, customer_number, sort_code):
    """
    Find an account belonging to a different customer.

    Used by the account-not-owned negative test.
    """

    query = """
        SELECT
            c.sort_code,
            c.customer_number,
            c.customer_email,
            a.account_number
        FROM customer c
        JOIN account a
            ON a.sort_code = c.sort_code
           AND a.customer_number = c.customer_number
        WHERE NOT (
            c.sort_code = %s
            AND c.customer_number = %s
        )
        ORDER BY c.customer_number, a.account_number
        LIMIT 1;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (sort_code, customer_number),
        )
        return cursor.fetchone()


def get_multiple_customer_email(connection):
    """
    Find an email address associated with more than one DISTINCT customer.

    This is needed for the ambiguous-email scenario.
    """

    query = """
        SELECT
            customer_email
        FROM customer
        WHERE customer_email IS NOT NULL
          AND customer_email <> ''
        GROUP BY customer_email
        HAVING COUNT(DISTINCT customer_number) > 1
        ORDER BY customer_email
        LIMIT 1;
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        row = cursor.fetchone()

    return row["customer_email"] if row else None


def get_nonexistent_email(connection):
    """
    Generate an email address that should not exist in bankdb.
    """

    candidate = "test.unregistered.999999@examplebank.com"

    query = """
        SELECT 1
        FROM customer
        WHERE LOWER(customer_email) = LOWER(%s)
        LIMIT 1;
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (candidate,))
        exists = cursor.fetchone()

    if not exists:
        return candidate

    return "definitely.not.registered.987654321@examplebank.com"


# =============================================================================
# SECTION 5 - BUILD SIMULATED EMAIL
# =============================================================================

def build_test_message(
    email_address,
    customer_number,
    account_number,
    request,
):
    """
    Build the same InboundMessage type that the real Gmail adapter produces.

    None means that the identifier is intentionally omitted.

    This is important for negative tests: we want to test the real
    identity-resolution logic rather than inject identity information
    directly into the pipeline.
    """

    body_lines = [
        "Hi,",
        "",
    ]

    if customer_number:
        body_lines.append(
            "My customer number is " + str(customer_number) + "."
        )

    if account_number:
        body_lines.append(
            "My account number is " + str(account_number) + "."
        )

    body_lines.extend(
        [
            "",
            request,
            "",
            "Thanks.",
        ]
    )

    body = "\n".join(body_lines)

    return InboundMessage(
        source="test_api",
        source_message_id=(
            "test-api-"
            + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        ),
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


# =============================================================================
# SECTION 6 - BUILD TEST SCENARIO
# =============================================================================

def build_scenario(connection, scenario, request):
    """
    Create the email/customer/account combination for the selected test.

    The values are discovered from bankdb wherever possible.
    """

    primary = get_customer_with_account(connection)

    if not primary:
        raise RuntimeError(
            "Could not find a customer with an email address and account."
        )

    email = primary["customer_email"]
    customer_number = primary["customer_number"]
    sort_code = primary["sort_code"]
    account_number = primary["account_number"]

    if scenario == "positive":
        return {
            "email": email,
            "customer_number": customer_number,
            "account_number": account_number,
            "expected": {
                "identity_eligible": True,
                "identity_status": "customer_number_match",
            },
        }

    if scenario == "account-only":
        return {
            "email": email,
            "customer_number": None,
            "account_number": account_number,
            "expected": {
                "identity_eligible": True,
                "identity_status": "verified_single_customer",
            },
        }

    if scenario == "wrong-customer":
        wrong_customer_number = str(customer_number) + "999"

        return {
            "email": email,
            "customer_number": wrong_customer_number,
            "account_number": account_number,
            "expected": {
                "identity_eligible": False,
                "identity_status": "customer_number_mismatch",
            },
        }

    if scenario == "account-not-owned":
        other = get_second_customer_account(
            connection,
            customer_number,
            sort_code,
        )

        if not other:
            raise RuntimeError(
                "Could not find a second customer account for the "
                "account-not-owned test."
            )

        return {
            "email": email,
            "customer_number": None,
            "account_number": other["account_number"],
            "expected": {
                "identity_eligible": False,
                "identity_status": "account_number_not_owned",
            },
            "note": (
                "The sender email belongs to one customer, but the "
                "account belongs to another customer."
            ),
        }

    if scenario == "unregistered-email":
        return {
            "email": get_nonexistent_email(connection),
            "customer_number": customer_number,
            "account_number": account_number,
            "expected": {
                "identity_eligible": False,
                "identity_status": "email_not_registered",
            },
        }

    if scenario == "ambiguous-email":
        ambiguous_email = get_multiple_customer_email(connection)

        if not ambiguous_email:
            raise RuntimeError(
                "No email address associated with multiple distinct "
                "customers was found in bankdb."
            )

        return {
            "email": ambiguous_email,
            "customer_number": None,
            "account_number": None,
            "expected": {
                "identity_eligible": False,
                "identity_status": "multiple_customers_identifier_missing",
            },
        }

    raise ValueError("Unknown scenario: " + scenario)


# =============================================================================
# SECTION 7 - ASSERT EXPECTED RESULT
# =============================================================================

def evaluate_result(result, expected):
    """
    Compare the pipeline's actual identity result with the expected result.

    Returns:
        True  -> test passed
        False -> test failed
    """

    classification = result.get("classification", {})

    actual_eligible = classification.get("identity_eligible")
    actual_status = classification.get("identity_status")

    expected_eligible = expected["identity_eligible"]
    expected_status = expected["identity_status"]

    eligible_ok = actual_eligible == expected_eligible
    status_ok = actual_status == expected_status

    print("")
    print("=" * 80)
    print("TEST ASSERTION")
    print("=" * 80)

    print(
        "identity_eligible:",
        "PASS" if eligible_ok else "FAIL",
        "| expected:",
        expected_eligible,
        "| actual:",
        actual_eligible,
    )

    print(
        "identity_status:",
        "PASS" if status_ok else "FAIL",
        "| expected:",
        expected_status,
        "| actual:",
        actual_status,
    )

    # For blocked identity tests, the pipeline should not route the
    # message to autonomous processing.
    if expected_eligible is False:
        routing = result.get("routing")

        routing_ok = routing is None

        print(
            "routing blocked:",
            "PASS" if routing_ok else "FAIL",
            "| expected: None",
            "| actual:",
            routing,
        )
    else:
        routing = result.get("routing", {})
        routing_ok = routing.get("tier") == "autonomous"

        print(
            "routing:",
            "PASS" if routing_ok else "FAIL",
            "| expected: autonomous",
            "| actual:",
            routing.get("tier"),
        )

    passed = eligible_ok and status_ok and routing_ok

    print("")
    print("OVERALL:", "PASS" if passed else "FAIL")
    print("=" * 80)

    return passed


# =============================================================================
# SECTION 8 - PRINT RESULT
# =============================================================================

def print_result(result):
    print("")
    print("=" * 80)
    print("COMPLETE PIPELINE RESULT")
    print("=" * 80)

    print(
        json.dumps(
            result,
            indent=2,
            default=str,
        )
    )

    print("=" * 80)


# =============================================================================
# SECTION 9 - MAIN
# =============================================================================

def main():
    arguments = parse_arguments()

    connection = None

    try:
        print("")
        print("=" * 80)
        print("BANKING PIPELINE TEST")
        print("=" * 80)
        print("Scenario:", arguments.scenario)

        # ---------------------------------------------------------------------
        # STEP 1 - CONNECT TO DATABASE
        # ---------------------------------------------------------------------

        print("")
        print("Connecting to bankdb...")

        connection = connect_to_database()

        print("Database connection successful.")

        # ---------------------------------------------------------------------
        # STEP 2 - DISCOVER TEST DATA
        # ---------------------------------------------------------------------

        print("")
        print("Building test scenario from bankdb...")

        scenario = build_scenario(
            connection,
            arguments.scenario,
            arguments.request,
        )

        print("Test email:", scenario["email"])
        print("Test customer number:", scenario["customer_number"])
        print("Test account number:", scenario["account_number"])

        if "note" in scenario:
            print("Note:", scenario["note"])

        print("Expected identity status:", scenario["expected"]["identity_status"])
        print("Expected identity eligible:", scenario["expected"]["identity_eligible"])

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

        print("")
        print("Loading knowledge-base embedding model...")

        embedding_model = load_embedding_model()

        print("Embedding model loaded.")

        # ---------------------------------------------------------------------
        # STEP 5 - BUILD SIMULATED MESSAGE
        # ---------------------------------------------------------------------

        message = build_test_message(
            email_address=scenario["email"],
            customer_number=scenario["customer_number"],
            account_number=scenario["account_number"],
            request=arguments.request,
        )

        print("")
        print("=" * 80)
        print("SIMULATED INBOUND MESSAGE")
        print("=" * 80)

        print("From:", message.from_address)
        print("Subject:", message.subject)

        print("")
        print("BODY:")
        print(message.body_text)

        # ---------------------------------------------------------------------
        # STEP 6 - RUN REAL PIPELINE
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
        # STEP 7 - PRINT RESULT
        # ---------------------------------------------------------------------

        print_result(result)

        # ---------------------------------------------------------------------
        # STEP 8 - ASSERT EXPECTED RESULT
        # ---------------------------------------------------------------------

        passed = evaluate_result(
            result,
            scenario["expected"],
        )

        if not passed:
            raise SystemExit(1)

    finally:
        if connection is not None:
            connection.close()
            print("")
            print("Database connection closed.")


if __name__ == "__main__":
    main()

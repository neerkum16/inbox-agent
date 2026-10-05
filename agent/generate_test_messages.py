"""
GENERATE TEST MESSAGES
===========================

WHAT THIS PROGRAM DOES
------------------------
Before we can build (or test) the inbox agent, we need realistic
customer emails to test it against — messages like "why was my
transfer declined?" or "why is my account frozen?". We could type
these by hand, but hand-written examples aren't tied to anything
real, and we'd have no reliable way to check whether the agent
answered correctly.

This program instead reaches into the REAL bankdb database — the same
one built earlier, with real customers, accounts, and transactions —
and picks specific, real rows to build messages around. Because each
test message is built from a real row, we always know exactly what the
CORRECT answer should have been, since it's sitting right there in the
same database row the message was generated from.

Each test message this program produces has two parts:
  1. The message itself — shaped like a Gmail API message, so the
     agent's ingestion code can be swapped later from "read this test
     file" to "read real Gmail" without changing its shape.
  2. A "ground truth" block — the category, priority, which tier the
     agent should route it to (answer automatically, draft for human
     review, or escalate), and which entities (account numbers,
     amounts, dates) should be extracted. Nothing in the ground truth
     is a guess — it's read directly from the same database row.

CATEGORIES THIS PROGRAM GENERATES, AND WHY EACH ONE IS INCLUDED
--------------------------------------------------------------------
  balance_inquiry            - routine question, safe to auto-answer
  declined_transaction       - "why was my payment declined" (dispute)
  account_status_inquiry     - "why is my account frozen/closed"
  fraud_report                - self-reported fraud; ALWAYS escalates,
                                 regardless of the account's real state
  application_status_inquiry - a still-PENDING customer asking about
                                 their application
  new_account_request        - a customer asking to open another
                                 account (tests that a SUSPENDED
                                 customer's request escalates, while
                                 an ACTIVE customer's doesn't)
  invalid_account_reference  - a message quoting an account number
                                 that doesn't exist at all, to test
                                 that the agent can safely say so
                                 rather than guessing

HOW THE "GROUND TRUTH" TIER IS DECIDED
-------------------------------------------
Some categories always escalate (fraud_report). For the others, the
tier depends on the REASON behind whatever the customer is asking
about, which we read from the real account/reason_code data — for
example, an account frozen for FRAUD_SUSPECTED escalates, but one
frozen at the CUSTOMER'S OWN request does not. This mirrors the
same reasoning used when the bankdb data itself was designed.
"""

# ---------------------------------------------------------------------------
# SECTION 1: IMPORTS
# ---------------------------------------------------------------------------

import json
# Writing the finished test messages out as a JSON file.

import os
# Reading the database password from an environment variable.

import random
# Python's built-in randomness library. random.Random(seed) creates
# our OWN private random number generator, separate from Python's
# shared global one. Using our own, seeded copy means: run this
# program twice with the same database contents, get the exact same
# test messages both times — the same deterministic principle the bankdb
# generator itself was built on.

from pathlib import Path
# Same as every earlier program: representing file locations.

from datetime import datetime
# Used to format dates and timestamps into the message text and into
# the Gmail-shaped fields, in a consistent, readable way.

import psycopg2
import psycopg2.extras
# psycopg2: talking to Postgres, same as load_rules_into_vector_store.py.
# psycopg2.extras gives us RealDictCursor, below, which we use so
# database rows come back as dictionaries (row["account_number"])
# instead of plain, unlabeled tuples (row[3]) — much easier to read
# and far less error-prone when a table has many columns.


# ---------------------------------------------------------------------------
# SECTION 2: SETTINGS
# ---------------------------------------------------------------------------

DATABASE_HOST = "localhost"
DATABASE_PORT = 5432
DATABASE_NAME = "bankdb"
DATABASE_USER = "postgres"
DATABASE_PASSWORD = os.environ["PGPASSWORD"]
# Same bankdb connection details used throughout this project.

OUTPUT_FILE = Path("output/test_messages.json")

RANDOM_SEED = 123
# This program's own seed. It has no need to match bankdb's own seed
# (42) — the two programs' randomness are entirely independent of one
# another. What matters is that THIS seed stays fixed, so this
# program's own output is reproducible.

MESSAGES_PER_CATEGORY = 5
# How many messages to generate for each category, when enough real
# candidate rows exist in the database to support that many. If fewer
# real rows exist for a category, this program uses however many are
# actually available rather than inventing extras.

BUSINESS_INBOX_ADDRESS = "support@examplebank.com"
# The "to" address on every generated message — standing in for the
# bank's monitored support inbox.

# Reason codes serious enough that whatever they're attached to should
# always be routed to a human, regardless of which category the
# message falls under. Everything else defaults to "autonomous".
ESCALATION_REASON_CODES = {"FRAUD_SUSPECTED", "COURT_ORDER"}

# Customer relationship states serious enough that a NEW request from
# that customer (like asking to open another account) should not be
# handled automatically.
ESCALATION_CUSTOMER_STATUSES = {"SUSPENDED", "PENDING_DELETE", "DELETED", "DECEASED"}


# ---------------------------------------------------------------------------
# SECTION 3: DATABASE CONNECTION AND QUERIES
# ---------------------------------------------------------------------------

def connect_to_database():
    """Open a connection to bankdb, with rows returned as dictionaries."""

    connection = psycopg2.connect(
        host=DATABASE_HOST,
        port=DATABASE_PORT,
        dbname=DATABASE_NAME,
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )

    return connection


def run_query(connection, sql_text):
    """
    Run a SELECT query and return every matching row as a list of
    dictionaries. Small helper so the query functions below don't each
    have to repeat the same three lines of cursor handling.
    """

    cursor = connection.cursor()
    cursor.execute(sql_text)
    rows = cursor.fetchall()
    cursor.close()

    # RealDictCursor rows behave like dictionaries already, but they
    # are technically a special psycopg2 type. dict(row) converts each
    # one into a genuinely ordinary Python dictionary, which is simpler
    # to reason about in the rest of this program.
    plain_rows = []
    for row in rows:
        plain_rows.append(dict(row))

    return plain_rows


def fetch_active_accounts(connection):
    """Real ACTIVE accounts, for balance_inquiry test messages."""

    return run_query(connection, """
        SELECT a.sort_code, a.account_number, a.account_type,
               a.available_balance, a.actual_balance,
               c.customer_number, c.customer_name, c.customer_email
        FROM account a
        JOIN customer c
            ON a.sort_code = c.sort_code
           AND a.customer_number = c.customer_number
        WHERE a.account_status = 'ACTIVE'
    """)


def fetch_declined_transactions(connection):
    """Real non-SUCCESS transactions, for declined_transaction test messages."""

    return run_query(connection, """
        SELECT t.transaction_timestamp, t.transaction_amount,
               t.status_reason, a.account_number, a.account_type,
               a.status_reason AS account_status_reason,
               c.customer_number, c.customer_name, c.customer_email
        FROM transaction_history t
        JOIN account a
            ON t.sort_code = a.sort_code
           AND t.account_number = a.account_number
        JOIN customer c
            ON a.sort_code = c.sort_code
           AND a.customer_number = c.customer_number
        WHERE t.status_code <> 'SUCCESS'
    """)


def fetch_non_active_accounts(connection):
    """Real FROZEN/CLOSED/PENDING_CLOSE/DORMANT accounts, for account_status_inquiry."""

    return run_query(connection, """
        SELECT a.account_number, a.account_status, a.status_reason,
               c.customer_number, c.customer_name, c.customer_email
        FROM account a
        JOIN customer c
            ON a.sort_code = c.sort_code
           AND a.customer_number = c.customer_number
        WHERE a.account_status IN ('FROZEN', 'CLOSED', 'PENDING_CLOSE', 'DORMANT')
    """)


def fetch_pending_customers(connection):
    """Real PENDING customers, for application_status_inquiry."""

    return run_query(connection, """
        SELECT customer_number, customer_name, customer_email
        FROM customer
        WHERE customer_status = 'PENDING'
    """)


def fetch_customers_for_new_account_request(connection):
    """
    Real customers of any status, for new_account_request. We
    deliberately do NOT filter to only ACTIVE customers here — including
    a SUSPENDED or similar customer is what lets this category test
    that such a request correctly escalates instead of being
    auto-approved.
    """

    return run_query(connection, """
        SELECT customer_number, customer_name, customer_email, customer_status
        FROM customer
    """)


def fetch_one_real_customer(connection):
    """
    One real, ACTIVE customer, used as the sender for the
    invalid_account_reference test message — the CUSTOMER is real, only the
    account number they mention is fabricated.
    """

    rows = run_query(connection, """
        SELECT customer_number, customer_name, customer_email
        FROM customer
        WHERE customer_status = 'ACTIVE'
        LIMIT 1
    """)

    if len(rows) == 0:
        return None

    return rows[0]


# ---------------------------------------------------------------------------
# SECTION 4: SMALL HELPERS SHARED BY SEVERAL CATEGORIES
# ---------------------------------------------------------------------------

def tier_for_reason_code(reason_code):
    """
    Decide the routing tier for a reason code. Escalation-worthy codes
    are the exception; everything else defaults to "autonomous".
    """

    if reason_code in ESCALATION_REASON_CODES:
        return "escalate"

    return "autonomous"


def format_money(amount):
    """Format a number as a plain British-pound amount, e.g. 45.2 -> '£45.20'."""

    return "£" + format(amount, ".2f")


def format_date(timestamp_value):
    """
    Format a database timestamp as a plain date a customer would
    write, e.g. '15 August 2026'.

    We build this from two separate pieces rather than one strftime
    call. strftime has a "%-d" flag on Linux/Mac that drops a date's
    leading zero (turning "05" into "5"), but Windows's version of
    strftime does not understand that flag and raises an error on it.
    Reading .day directly as a plain number, and using strftime only
    for the month/year part (which IS portable everywhere), gives the
    exact same result on every operating system.
    """

    day_number = timestamp_value.day
    month_and_year_text = timestamp_value.strftime("%B %Y")

    return str(day_number) + " " + month_and_year_text


# ---------------------------------------------------------------------------
# SECTION 5: ONE "MAKE A MESSAGE" FUNCTION PER CATEGORY
# ---------------------------------------------------------------------------
# Each function below takes one real database row (a dictionary) and
# our shared random generator, and returns a dictionary with three
# things: the email subject, the email body, and the ground truth.
# Several categories offer a couple of differently-worded templates
# and pick one at random, so the test messages don't all read identically.

def make_balance_inquiry_message(row, rng):
    templates = [
        "Hi, could you tell me the current balance on my account {account_number}?",
        "What's the balance on account {account_number} at the moment? Thanks.",
    ]
    body = rng.choice(templates).format(account_number=row["account_number"])

    return {
        "subject": "Balance enquiry",
        "body": body,
        "from_email": row["customer_email"],
        "ground_truth": {
            "category": "balance_inquiry",
            "priority": "low",
            "tier": "autonomous",
            # customer_number is deliberately NOT here. A real customer
            # never states their own internal customer number in an
            # email — it appears nowhere in the message text above for
            # a model to extract. Identifying the customer is a lookup
            # against WHO SENT the email (from_email), not a text-
            # extraction task, so it's tracked separately here instead.
            "expected_customer_number": row["customer_number"],
            "entities": {
                "account_number": row["account_number"],
            },
        },
    }


def make_declined_transaction_message(row, rng):
    templates = [
        "I tried to make a payment of {amount} on {date} from account {account_number} and it didn't go through. Can you tell me why?",
        "A transaction for {amount} on {date} was declined on my account {account_number}. What happened?",
    ]
    amount_text = format_money(row["transaction_amount"])
    date_text = format_date(row["transaction_timestamp"])
    body = rng.choice(templates).format(
        amount=amount_text,
        date=date_text,
        account_number=row["account_number"],
    )

    # ACCOUNT_FROZEN is a generic transaction-level code meaning "this
    # payment failed because the account happens to be frozen" — it
    # doesn't say WHY the account is frozen. For escalation purposes,
    # what actually matters is the account's own reason (FRAUD_SUSPECTED
    # escalates, CUSTOMER_REQUESTED doesn't) — so for this one specific
    # transaction reason, we look at the account's status_reason
    # instead. Every other transaction reason (INSUFFICIENT_FUNDS,
    # ACCOUNT_CLOSED) is self-explanatory and doesn't need that lookup.
    if row["status_reason"] == "ACCOUNT_FROZEN":
        tier = tier_for_reason_code(row["account_status_reason"])
    else:
        tier = tier_for_reason_code(row["status_reason"])

    return {
        "subject": "Declined transaction",
        "body": body,
        "from_email": row["customer_email"],
        "ground_truth": {
            "category": "declined_transaction",
            "priority": "medium",
            "tier": tier,
            "expected_customer_number": row["customer_number"],
            "entities": {
                "account_number": row["account_number"],
                "transaction_date": row["transaction_timestamp"].strftime("%Y-%m-%d"),
                "amount": str(row["transaction_amount"]),
            },
            "expected_reason_code": row["status_reason"],
        },
    }


def make_account_status_message(row, rng):
    status_word = row["account_status"].replace("_", " ").lower()
    templates = [
        "Why is my account {account_number} showing as {status}? Can you explain?",
        "I noticed my account {account_number} is {status}. What does that mean for me?",
    ]
    body = rng.choice(templates).format(
        account_number=row["account_number"],
        status=status_word,
    )

    # A question about your own account's status is reasonably
    # medium priority to the customer even when the underlying cause
    # is routine and safe to auto-answer — their account access is
    # affected, which is a step up from a purely informational
    # question like a balance check. Only a genuinely escalation-
    # worthy reason (fraud, legal) pushes this to high.
    if row["status_reason"] in ESCALATION_REASON_CODES:
        priority = "high"
    else:
        priority = "medium"

    return {
        "subject": "Question about my account status",
        "body": body,
        "from_email": row["customer_email"],
        "ground_truth": {
            "category": "account_status_inquiry",
            "priority": priority,
            "tier": tier_for_reason_code(row["status_reason"]),
            "expected_customer_number": row["customer_number"],
            "entities": {
                "account_number": row["account_number"],
            },
            "expected_reason_code": row["status_reason"],
        },
    }


def make_fraud_report_message(row, rng):
    templates = [
        "I think someone has made an unauthorised transaction on my account {account_number}. Please help urgently.",
        "There's a payment on my account {account_number} that I did not make. I believe this is fraud.",
    ]
    body = rng.choice(templates).format(account_number=row["account_number"])

    return {
        "subject": "Possible fraud on my account",
        "body": body,
        "from_email": row["customer_email"],
        "ground_truth": {
            # fraud_report ALWAYS escalates. This is a hard trigger
            # based on what the customer is SAYING, not on the
            # account's actual current status_reason — even if this
            # particular account turns out to be fine, a self-reported
            # fraud claim always goes to a human.
            "category": "fraud_report",
            "priority": "high",
            "tier": "escalate",
            "expected_customer_number": row["customer_number"],
            "entities": {
                "account_number": row["account_number"],
            },
        },
    }


def make_application_status_message(row, rng):
    templates = [
        "Hi, I applied for an account a little while ago. Could you tell me the status of my application?",
        "I'm still waiting to hear back about my new account application. Any update?",
    ]
    body = rng.choice(templates)

    return {
        "subject": "Application status",
        "body": body,
        "from_email": row["customer_email"],
        "ground_truth": {
            "category": "application_status_inquiry",
            # A customer waiting on their application is reasonably
            # invested in a timely answer, even though the answer
            # itself (KYC still pending) is routine and safe to give
            # automatically — same reasoning as account_status_inquiry.
            "priority": "medium",
            "tier": "autonomous",
            "expected_customer_number": row["customer_number"],
            "entities": {},
            "expected_reason_code": "KYC_INCOMPLETE",
        },
    }


def make_new_account_request_message(row, rng):
    account_type = rng.choice(["SAVINGS", "ISA", "CURRENT"])
    templates = [
        "I'd like to open a new {account_type} account, please.",
        "Could you help me set up an additional {account_type} account?",
    ]
    body = rng.choice(templates).format(account_type=account_type.title())

    if row["customer_status"] in ESCALATION_CUSTOMER_STATUSES:
        tier = "escalate"
        priority = "medium"
    else:
        tier = "autonomous"
        priority = "low"

    return {
        "subject": "New account request",
        "body": body,
        "from_email": row["customer_email"],
        "ground_truth": {
            "category": "new_account_request",
            "priority": priority,
            "tier": tier,
            "expected_customer_number": row["customer_number"],
            "entities": {
                "requested_account_type": account_type,
            },
        },
    }


def make_invalid_account_message(row, rng):
    # A deliberately fake account number, well outside the real
    # numbering range, so it cannot coincidentally match a real
    # account.
    fake_account_number = "99999999"

    body = (
        "I'm trying to check my account " + fake_account_number
        + " but I can't see it anywhere. Can you look into this?"
    )

    return {
        "subject": "Can't find my account",
        "body": body,
        "from_email": row["customer_email"],
        "ground_truth": {
            "category": "invalid_account_reference",
            # A customer who can't find their own account is at least
            # mildly concerned, even though the correct response (a
            # clear "we can't find that account number") is routine
            # and safe to give automatically.
            "priority": "medium",
            "tier": "autonomous",
            "expected_customer_number": row["customer_number"],
            "entities": {
                "account_number": fake_account_number,
            },
            "expected_reason_code": "ACCOUNT_NOT_FOUND",
        },
    }


# ---------------------------------------------------------------------------
# SECTION 6: SHAPING A GENERATED MESSAGE INTO GMAIL FORMAT
# ---------------------------------------------------------------------------

def wrap_as_gmail_message(message_id, from_email, subject, body):
    """
    Wrap a subject/body pair into a simplified structure shaped like a
    Gmail API message — id, thread ID, sender, recipient, subject,
    body, and a date. This is a simplified stand-in, not a byte-for-byte
    copy of the real Gmail API's format (which nests the body as
    base64-encoded MIME content) — the point is that swapping this
    file's output for a real Gmail API response later should mean
    changing how the agent reads a message, not changing what a
    "message" means to the rest of the program.
    """

    return {
        "id": message_id,
        "threadId": message_id,
        "from": from_email,
        "to": BUSINESS_INBOX_ADDRESS,
        "subject": subject,
        "body": body,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ---------------------------------------------------------------------------
# SECTION 7: BUILDING ALL TEST MESSAGES FOR ONE CATEGORY
# ---------------------------------------------------------------------------

def build_messages_for_category(category_name, candidate_rows, make_message_function, rng, next_message_number):
    """
    Pick up to MESSAGES_PER_CATEGORY rows at random from candidate_rows,
    turn each into a test message using make_message_function, and return
    the finished list together with the next unused test message number (so
    numbering carries on smoothly across categories, e.g.
    msg_0001, msg_0002, and so on, regardless of which
    category each one came from).
    """

    if len(candidate_rows) == 0:
        print("  No real rows found for category '" + category_name + "' — skipping it.")
        return [], next_message_number

    how_many = min(MESSAGES_PER_CATEGORY, len(candidate_rows))
    if how_many < MESSAGES_PER_CATEGORY:
        print(
            "  Only " + str(how_many) + " real row(s) available for '"
            + category_name + "' (wanted " + str(MESSAGES_PER_CATEGORY) + ")."
        )

    chosen_rows = rng.sample(candidate_rows, how_many)

    messages_for_this_category = []
    for one_row in chosen_rows:
        built = make_message_function(one_row, rng)

        message_id = "msg_" + str(next_message_number).zfill(4)
        next_message_number = next_message_number + 1

        message = wrap_as_gmail_message(
            message_id,
            built["from_email"],
            built["subject"],
            built["body"],
        )

        messages_for_this_category.append({
            "message": message,
            "ground_truth": built["ground_truth"],
        })

    print("  Generated " + str(len(messages_for_this_category)) + " test message(s) for '" + category_name + "'.")

    return messages_for_this_category, next_message_number


# ---------------------------------------------------------------------------
# SECTION 8: THE MAIN PROGRAM
# ---------------------------------------------------------------------------

def main():

    rng = random.Random(RANDOM_SEED)

    connection = connect_to_database()

    all_messages = []
    next_message_number = 1

    category_plan = [
        ("balance_inquiry", fetch_active_accounts(connection), make_balance_inquiry_message),
        ("declined_transaction", fetch_declined_transactions(connection), make_declined_transaction_message),
        ("account_status_inquiry", fetch_non_active_accounts(connection), make_account_status_message),
        ("fraud_report", fetch_active_accounts(connection), make_fraud_report_message),
        ("application_status_inquiry", fetch_pending_customers(connection), make_application_status_message),
        ("new_account_request", fetch_customers_for_new_account_request(connection), make_new_account_request_message),
    ]

    print("Generating test messages from real bankdb data...")
    for category_name, candidate_rows, make_message_function in category_plan:
        messages_for_this_category, next_message_number = build_messages_for_category(
            category_name, candidate_rows, make_message_function, rng, next_message_number
        )
        all_messages.extend(messages_for_this_category)

    # invalid_account_reference needs only ONE real customer to serve
    # as the sender, so it's handled separately from the category_plan
    # loop above rather than forcing it through the same
    # "pick several rows" shape as every other category.
    one_customer = fetch_one_real_customer(connection)
    if one_customer is not None:
        built = make_invalid_account_message(one_customer, rng)
        message_id = "msg_" + str(next_message_number).zfill(4)
        next_message_number = next_message_number + 1
        message = wrap_as_gmail_message(message_id, built["from_email"], built["subject"], built["body"])
        all_messages.append({"message": message, "ground_truth": built["ground_truth"]})
        print("  Generated 1 test message(s) for 'invalid_account_reference'.")
    else:
        print("  No ACTIVE customer found for 'invalid_account_reference' — skipping it.")

    connection.close()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as output_handle:
        json.dump(all_messages, output_handle, indent=2)

    print("")
    print("Done. Wrote " + str(len(all_messages)) + " test messages to " + str(OUTPUT_FILE))


if __name__ == "__main__":
    main()

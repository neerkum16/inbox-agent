"""
CLASSIFY AND EXTRACT
======================

WHAT THIS PROGRAM DOES
-------------------------
This is the first real piece of the inbox agent itself — everything
before this point (bankdb, the knowledge base, the test messages) was
groundwork for THIS program to be testable.

For each test message, this program:

  1. Sends the message to an AI model (Claude or Kimi — a toggle,
     just like synthesize_rule_text.py) and asks it to read the
     message and answer three questions: what CATEGORY is this
     (a balance question? a fraud report?), how URGENT is it, and
     what specific details (account numbers, amounts, dates) does it
     mention?
  2. Checks those extracted details against the REAL bankdb database —
     does that account number actually exist? Does it belong to that
     customer? This is the difference between an agent that merely
     reads a number out of an email, and one that has actually
     confirmed the number means something real.
  3. Writes down exactly what happened — the message, what the model
     said, what the database check found — into a permanent audit log
     table, so every decision this program ever makes can be reviewed
     later.
  4. Compares its own answer against the test message's ground truth (which
     we already know is correct, since the test messages were built FROM
     real database rows) and reports how often it got things right.

WHAT THIS PROGRAM DELIBERATELY DOES NOT DO YET
---------------------------------------------------
It does not draft a reply. It does not decide whether to escalate to
a human. Those come later, once we know classification and extraction
are actually reliable — there's no point building an escalation
policy on top of a classifier we haven't checked works.
"""

# ---------------------------------------------------------------------------
# SECTION 1: IMPORTS
# ---------------------------------------------------------------------------

import json
import os
import time
from pathlib import Path

import anthropic
import psycopg2
import psycopg2.extras
# InboundMessage is the Phase 4A application contract. The try/except keeps
# this file usable both as part of the agent package and as the original script.
try:
    from .contracts import InboundMessage
    from .adapters.fixtures import normalize_fixture_message
except ImportError:  # Supports the existing `python agent/...py` CLI invocation.
    from contracts import InboundMessage
    from adapters.fixtures import normalize_fixture_message
# All four of these are used the same way, and for the same reasons,
# as in synthesize_rule_text.py and load_rules_into_vector_store.py —
# json for reading/writing files and parsing the model's replies,
# os for environment variables, anthropic for talking to Claude or
# Kimi, and psycopg2 for talking to Postgres.


# ---------------------------------------------------------------------------
# SECTION 2: SETTINGS
# ---------------------------------------------------------------------------

TEST_MESSAGES_FILE = Path("output/test_messages.json")
# This program reads the test messages produced by
# generate_test_messages.py, which live in the same folder — the same
# pattern this program's own output follows for whatever reads it next.

OUTPUT_FILE = Path("output/classification_results.json")

DATABASE_HOST = "localhost"
DATABASE_PORT = 5432
DATABASE_NAME = "bankdb"
DATABASE_USER = "postgres"
DATABASE_PASSWORD = os.environ["PGPASSWORD"]

MODEL_PROVIDER = "kimi"
# Toggle: "claude" or "kimi" — same idea as synthesize_rule_text.py.
# Change this one line to switch providers; nothing else in this file
# needs to change either way.

if MODEL_PROVIDER == "kimi":
    MODEL_NAME = "kimi-k2.6"
else:
    MODEL_NAME = "claude-sonnet-5"

# Kimi's account tier used here earlier allowed only 3 requests per
# minute. This program makes one request per test message, so
# we pace requests the same way synthesize_rule_text.py learned to.
KIMI_REQUEST_DELAY_SECONDS = 21
MAX_RATE_LIMIT_RETRIES = 5
RATE_LIMIT_RETRY_WAIT_SECONDS = 25

VALID_CATEGORIES = [
    "balance_inquiry",
    "declined_transaction",
    "account_status_inquiry",
    "fraud_report",
    "application_status_inquiry",
    "new_account_request",
    "invalid_account_reference",
    "other",
]
# "other" is included on purpose, as an honest fallback — we would
# rather the model say "I don't recognise this" than force a message
# into a category it doesn't really belong to.

VALID_PRIORITIES = ["low", "medium", "high"]


# ---------------------------------------------------------------------------
# SECTION 3: DATABASE CONNECTION AND LOOKUPS
# ---------------------------------------------------------------------------

def connect_to_database():
    """Open a connection to bankdb, with rows returned as dictionaries."""

    return psycopg2.connect(
        host=DATABASE_HOST,
        port=DATABASE_PORT,
        dbname=DATABASE_NAME,
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def look_up_customer(connection, customer_number):
    """Return True if a customer number exists in bankdb."""

    cursor = connection.cursor()
    cursor.execute(
        "SELECT 1 FROM customer WHERE customer_number = %s LIMIT 1;",
        (customer_number,),
    )
    found = cursor.fetchone() is not None
    cursor.close()

    return found


def look_up_customer_by_email(connection, from_email):
    """Return every customer identity associated with the sender email."""

    if from_email is None:
        return []

    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT sort_code, customer_number
        FROM customer
        WHERE customer_email = %s;
        """,
        (from_email,),
    )
    rows = cursor.fetchall()
    cursor.close()

    return [dict(row) for row in rows]


def resolve_customer_identity(
    customer_records,
    claimed_customer_number=None,
    account_records=None,
    claimed_account_number=None,
):
    """Resolve customer identity using sender email and claimed identifiers.

    Customer identity is established from the sender email and then verified
    against any identifiers supplied in the message.

    Rules:
      1. An unregistered email is never eligible.
      2. If customer number is supplied, it must match an email-linked customer.
      3. If an account number is also supplied, that account must belong to
         the resolved customer.
      4. If no customer number is supplied, an account number may identify the
         email-linked customer, but ownership must be verified.
      5. If neither identifier is supplied, a single email-linked customer is
         sufficient.
    """

    if account_records is None:
        account_records = []

    # ------------------------------------------------------------------
    # 1. Sender email must be registered.
    # ------------------------------------------------------------------
    if len(customer_records) == 0:
        return {
            "identity_status": "email_not_registered",
            "identity_eligible": False,
            "resolved_sort_code": None,
            "resolved_customer_number": None,
        }

    # ------------------------------------------------------------------
    # 2. Customer number, if supplied, takes precedence.
    #
    # We establish the customer from the email + customer number first.
    # However, we MUST still validate the account number if one was also
    # supplied.
    # ------------------------------------------------------------------
    if claimed_customer_number is not None:
        matching_records = []

        for record in customer_records:
            if (
                str(record["customer_number"]).strip()
                == str(claimed_customer_number).strip()
            ):
                matching_records.append(record)

        if len(matching_records) == 0:
            return {
                "identity_status": "customer_number_mismatch",
                "identity_eligible": False,
                "resolved_sort_code": None,
                "resolved_customer_number": None,
            }

        if len(matching_records) > 1:
            return {
                "identity_status": "multiple_matching_customer_records",
                "identity_eligible": False,
                "resolved_sort_code": None,
                "resolved_customer_number": None,
            }

        resolved_record = matching_records[0]
        resolved_sort_code = resolved_record["sort_code"]
        resolved_customer_number = resolved_record["customer_number"]

        # --------------------------------------------------------------
        # Customer number is valid.
        #
        # If an account number was also supplied, verify ownership
        # BEFORE granting identity eligibility.
        # --------------------------------------------------------------
        if claimed_account_number is not None:
            matching_accounts = []

            for account in account_records:
                if (
                    str(account["account_number"]).strip()
                    == str(claimed_account_number).strip()
                ):
                    matching_accounts.append(account)

            if len(matching_accounts) == 0:
                return {
                    "identity_status": "account_number_not_found",
                    "identity_eligible": False,
                    "resolved_sort_code": None,
                    "resolved_customer_number": None,
                }

            linked_accounts = []

            for account in matching_accounts:
                same_customer = (
                    str(account["customer_number"]).strip()
                    == str(resolved_customer_number).strip()
                    and str(account["sort_code"]).strip()
                    == str(resolved_sort_code).strip()
                )

                if same_customer:
                    linked_accounts.append(account)

            if len(linked_accounts) == 0:
                return {
                    "identity_status": "account_number_not_owned",
                    "identity_eligible": False,
                    "resolved_sort_code": None,
                    "resolved_customer_number": None,
                }

            if len(linked_accounts) > 1:
                return {
                    "identity_status": "multiple_customers_match_account",
                    "identity_eligible": False,
                    "resolved_sort_code": None,
                    "resolved_customer_number": None,
                }

        # Customer number matched and, if supplied, account ownership matched.
        return {
            "identity_status": "customer_number_match",
            "identity_eligible": True,
            "resolved_sort_code": resolved_sort_code,
            "resolved_customer_number": resolved_customer_number,
        }

    # ------------------------------------------------------------------
    # 3. No customer number.
    #
    # An account number may identify which email-linked customer owns the
    # account. Ownership must be explicitly verified.
    # ------------------------------------------------------------------
    if claimed_account_number is not None:
        matching_accounts = []

        for account in account_records:
            if (
                str(account["account_number"]).strip()
                == str(claimed_account_number).strip()
            ):
                matching_accounts.append(account)

        if len(matching_accounts) == 0:
            return {
                "identity_status": "account_number_not_found",
                "identity_eligible": False,
                "resolved_sort_code": None,
                "resolved_customer_number": None,
            }

        linked_matches = []

        for account in matching_accounts:
            for customer in customer_records:
                same_customer = (
                    str(account["customer_number"]).strip()
                    == str(customer["customer_number"]).strip()
                    and str(account["sort_code"]).strip()
                    == str(customer["sort_code"]).strip()
                )

                if same_customer:
                    linked_matches.append(customer)

        if len(linked_matches) == 1:
            record = linked_matches[0]

            return {
                "identity_status": "verified_single_customer",
                "identity_eligible": True,
                "resolved_sort_code": record["sort_code"],
                "resolved_customer_number": record["customer_number"],
            }

        if len(linked_matches) > 1:
            return {
                "identity_status": "multiple_customers_match_account",
                "identity_eligible": False,
                "resolved_sort_code": None,
                "resolved_customer_number": None,
            }

        return {
            "identity_status": "account_number_not_owned",
            "identity_eligible": False,
            "resolved_sort_code": None,
            "resolved_customer_number": None,
        }

    # ------------------------------------------------------------------
    # 4. No customer number and no account number.
    # ------------------------------------------------------------------
    if len(customer_records) == 1:
        record = customer_records[0]

        return {
            "identity_status": "verified_single_customer",
            "identity_eligible": True,
            "resolved_sort_code": record["sort_code"],
            "resolved_customer_number": record["customer_number"],
        }

    return {
        "identity_status": "multiple_customers_identifier_missing",
        "identity_eligible": False,
        "resolved_sort_code": None,
        "resolved_customer_number": None,
    }


def look_up_account(connection, account_number):
    """
    Return a dictionary describing what bankdb knows about an account
    number: whether it exists at all, and if so, which customer number
    owns it.
    """

    cursor = connection.cursor()
    cursor.execute(
        "SELECT customer_number FROM account WHERE account_number = %s LIMIT 1;",
        (account_number,),
    )
    row = cursor.fetchone()
    cursor.close()

    if row is None:
        return {"exists": False, "owning_customer_number": None}

    return {"exists": True, "owning_customer_number": row["customer_number"]}


def validate_entities(connection, entities, resolved_customer_number):
    """
    Check whatever entities the model extracted against the real
    database, and return a dictionary describing what was found. A
    value of None means that particular check didn't apply — either
    the entity wasn't extracted, or (for account_matches_customer) the
    sender's email didn't resolve to a known customer at all.

    resolved_customer_number comes from look_up_customer_by_email(),
    NOT from anything the model extracted — customer identity is
    established by who sent the email, not by text extraction.
    """

    result = {
        "account_number_exists": None,
        "account_matches_customer": None,
    }

    account_number = entities.get("account_number")

    if account_number:
        account_info = look_up_account(connection, account_number)
        result["account_number_exists"] = account_info["exists"]

        if account_info["exists"] and resolved_customer_number:
            result["account_matches_customer"] = (
                account_info["owning_customer_number"] == resolved_customer_number
            )

    return result


# ---------------------------------------------------------------------------
# SECTION 4: BUILDING THE PROMPT AND CALLING THE MODEL
# ---------------------------------------------------------------------------

def build_classification_prompt(message: InboundMessage):
    """Build the existing classification prompt for one normalized message."""

    prompt_lines = []
    prompt_lines.append("You are the first stage of a bank's customer support inbox agent.")
    prompt_lines.append("Read the email below and answer three questions about it.")
    prompt_lines.append("")
    prompt_lines.append("1. category — choose exactly one from this list:")
    prompt_lines.append("   " + ", ".join(VALID_CATEGORIES))
    prompt_lines.append("2. priority — choose exactly one from: " + ", ".join(VALID_PRIORITIES))
    prompt_lines.append("3. entities — any of the following that are actually mentioned in the")
    prompt_lines.append("   email: customer_number, account_number, transaction_date (as YYYY-MM-DD),")
    prompt_lines.append("   amount (numbers only, no currency symbol), requested_account_type.")
    prompt_lines.append("   Leave out any entity that is not mentioned — do not guess or invent one.")
    prompt_lines.append("   customer_number is the number the sender CLAIMS is theirs. It is untrusted")
    prompt_lines.append("   input and will be checked separately against the sender's email address.")
    prompt_lines.append("")
    prompt_lines.append("Reply with ONLY a JSON object shaped exactly like this, and nothing else:")
    prompt_lines.append('{"category": "...", "priority": "...", "entities": {"account_number": "..."}}')
    prompt_lines.append("")
    prompt_lines.append("Subject: " + message.subject)
    prompt_lines.append("Body: " + message.body_text)

    return "\n".join(prompt_lines)


def ask_model(prompt_text, client):
    """
    Send one prompt to the model and return its reply as plain text,
    retrying automatically if the API's rate limit is hit.
    """

    extra_arguments = {}
    if MODEL_PROVIDER == "kimi":
        # Same reasoning as synthesize_rule_text.py: this task doesn't
        # need step-by-step reasoning, and leaving thinking on risks
        # burning the whole reply budget on reasoning alone.
        extra_arguments["thinking"] = {"type": "disabled"}

    attempt_number = 0
    while attempt_number < MAX_RATE_LIMIT_RETRIES:
        attempt_number = attempt_number + 1
        try:
            response = client.messages.create(
                model=MODEL_NAME,
                max_tokens=500,
                messages=[
                    {"role": "user", "content": prompt_text}
                ],
                **extra_arguments,
            )
            break
        except anthropic.RateLimitError:
            print(
                "  Hit the API's rate limit. Waiting "
                + str(RATE_LIMIT_RETRY_WAIT_SECONDS)
                + " seconds before trying again (attempt "
                + str(attempt_number) + " of " + str(MAX_RATE_LIMIT_RETRIES) + ")."
            )
            time.sleep(RATE_LIMIT_RETRY_WAIT_SECONDS)
    else:
        # This "else" belongs to the "while" loop above, not to the
        # "try" — in Python, a while/for loop's "else" block runs only
        # if the loop finished normally, WITHOUT ever hitting "break".
        # Here, that means every retry attempt failed.
        print("  Gave up after repeated rate-limit errors.")
        return None

    reply_text = None
    for one_block in response.content:
        if one_block.type == "text":
            reply_text = one_block.text

    return reply_text


# ---------------------------------------------------------------------------
# SECTION 5: PROCESSING ONE TEST MESSAGE
# ---------------------------------------------------------------------------

def strip_code_fence(text):
    """Remove a surrounding ```json ... ``` fence, if the reply has one."""

    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline_index = cleaned.find("\n")
        if first_newline_index != -1:
            cleaned = cleaned[first_newline_index + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    return cleaned


def values_match(expected_value, actual_value):
    """
    Compare two entity values the way a human checking the answer
    would — ignoring letter case and surrounding whitespace, so
    "SAVINGS" and "Savings" count as the same answer rather than a
    scoring failure over a formatting difference that doesn't matter.
    """

    if actual_value is None:
        return False

    return str(expected_value).strip().lower() == str(actual_value).strip().lower()


def classify_message(message: InboundMessage, client, connection):
    """Classify, extract, and validate one normalized message.

    This production function intentionally has no dependency on fixture ground
    truth. Sender-to-customer resolution remains the existing Phase 1 rule.
    """

    # The sender email is used to find every customer record associated with it.
    # The customer number extracted from the email is only a claim; Python
    # validates that claim against these database records after model extraction.
    customer_records = look_up_customer_by_email(connection, message.from_address)
    result = {
        "message_id": message.source_message_id,
        "message_body": message.body_text,
        "from_email": message.from_address,
        "customer_records_for_email": customer_records,
        "resolved_sort_code": None,
        "resolved_customer_number": None,
        "identity_status": None,
        "identity_eligible": False,
    }

    # Reuse the exact existing prompt, now using normalized message fields.
    prompt_text = build_classification_prompt(message)
    reply_text = ask_model(prompt_text, client)

    if reply_text is None:
        result["error"] = "no_reply_text"
        return result

    cleaned_reply_text = strip_code_fence(reply_text)
    try:
        parsed_reply = json.loads(cleaned_reply_text)
    except json.JSONDecodeError:
        result["error"] = "invalid_json"
        result["raw_model_output"] = reply_text
        return result

    # get supplies an empty dictionary if the model did not include entities.
    extracted_entities = parsed_reply.get("entities", {})
    result["raw_model_output"] = reply_text
    result["extracted_category"] = parsed_reply.get("category")
    result["extracted_priority"] = parsed_reply.get("priority")
    result["extracted_entities"] = extracted_entities

    claimed_customer_number = extracted_entities.get("customer_number")
    claimed_account_number = extracted_entities.get("account_number")

    account_records = []
    if claimed_account_number is not None:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT sort_code, account_number, customer_number
            FROM account
            WHERE account_number = %s;
            """,
            (claimed_account_number,),
        )
        account_records = [dict(row) for row in cursor.fetchall()]
        cursor.close()

    identity_result = resolve_customer_identity(
        customer_records,
        claimed_customer_number,
        account_records,
        claimed_account_number,
    )
    result.update(identity_result)

    result["validation_result"] = validate_entities(
        connection, extracted_entities, result["resolved_customer_number"]
    )
    return result


def process_one_message(test_message, client, connection):
    """
    Run the full pipeline — identify the customer, classify, extract,
    validate, compare to ground truth — for a single test message, and
    return one result record.
    """

    # This wrapper is fixture evaluation only. The production function above
    # receives only InboundMessage and cannot see this ground truth.
    ground_truth = test_message["ground_truth"]
    message = normalize_fixture_message(test_message)
    expected_customer_number = ground_truth.get("expected_customer_number")

    result = classify_message(message, client, connection)
    result.update({
        "ground_truth_category": ground_truth["category"],
        "ground_truth_priority": ground_truth["priority"],
        "expected_customer_number": expected_customer_number,
        "customer_identified_correctly": (
            result["resolved_customer_number"] == expected_customer_number
        ),
    })

    if "error" in result:
        return result

    # Compare every entity the TEST MESSAGE expected against what the model
    # actually extracted, one field at a time.
    entity_matches = {}
    for expected_key in ground_truth.get("entities", {}):
        expected_value = ground_truth["entities"][expected_key]
        actual_value = result["extracted_entities"].get(expected_key)
        entity_matches[expected_key] = values_match(expected_value, actual_value)

    result["entity_matches"] = entity_matches
    result["category_correct"] = (result["extracted_category"] == ground_truth["category"])
    result["priority_correct"] = (result["extracted_priority"] == ground_truth["priority"])

    return result


def save_to_audit_log(connection, result):
    """Write one test message's result into the permanent audit log table."""

    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO agent_audit_log
            (message_id, message_body, model_provider, raw_model_output,
             extracted_category, extracted_priority, extracted_entities,
             validation_result, ground_truth_category, ground_truth_priority,
             category_correct, priority_correct)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s)
        """,
        (
            result["message_id"],
            result["message_body"],
            MODEL_PROVIDER,
            result.get("raw_model_output"),
            result.get("extracted_category"),
            result.get("extracted_priority"),
            json.dumps(result.get("extracted_entities")),
            json.dumps(result.get("validation_result")),
            result["ground_truth_category"],
            result["ground_truth_priority"],
            result.get("category_correct"),
            result.get("priority_correct"),
        ),
    )
    connection.commit()
    cursor.close()


# ---------------------------------------------------------------------------
# SECTION 6: SCORING
# ---------------------------------------------------------------------------

def print_accuracy_report(results):
    """Print how often the model got category, priority, and entities right."""

    total_count = len(results)
    error_count = 0
    category_correct_count = 0
    priority_correct_count = 0

    for one_result in results:
        if "error" in one_result:
            error_count = error_count + 1
            continue
        if one_result["category_correct"]:
            category_correct_count = category_correct_count + 1
        if one_result["priority_correct"]:
            priority_correct_count = priority_correct_count + 1

    scored_count = total_count - error_count

    print("")
    print("=" * 60)
    print("ACCURACY REPORT")
    print("=" * 60)
    print("Total test messages:", total_count)
    print("Failed to get a usable reply:", error_count)
    if scored_count > 0:
        print(
            "Category accuracy:",
            category_correct_count, "/", scored_count,
            "(" + str(round(100 * category_correct_count / scored_count, 1)) + "%)",
        )
        print(
            "Priority accuracy:",
            priority_correct_count, "/", scored_count,
            "(" + str(round(100 * priority_correct_count / scored_count, 1)) + "%)",
        )

    print("")
    print("Per-message results where the category was WRONG:")
    for one_result in results:
        if "error" in one_result:
            print("  " + one_result["message_id"] + ": ERROR (" + one_result["error"] + ")")
        elif not one_result["category_correct"]:
            print(
                "  " + one_result["message_id"] + ": expected '"
                + one_result["ground_truth_category"] + "', got '"
                + str(one_result.get("extracted_category")) + "'"
            )


# ---------------------------------------------------------------------------
# SECTION 7: THE MAIN PROGRAM
# ---------------------------------------------------------------------------

def main():

    with open(TEST_MESSAGES_FILE, "r", encoding="utf-8") as input_handle:
        test_messages = json.load(input_handle)

    print("Loaded", len(test_messages), "test messages from", TEST_MESSAGES_FILE)

    if MODEL_PROVIDER == "kimi":
        client = anthropic.Anthropic(
            api_key=os.environ["MOONSHOT_API_KEY"],
            base_url="https://api.moonshot.ai/anthropic",
        )
    else:
        client = anthropic.Anthropic()

    connection = connect_to_database()

    all_results = []
    for index_number in range(len(test_messages)):
        one_test_message = test_messages[index_number]
        print(
            "Processing test message "
            + str(index_number + 1) + " of " + str(len(test_messages))
            + ": " + one_test_message["message"]["id"]
        )

        result = process_one_message(one_test_message, client, connection)
        save_to_audit_log(connection, result)
        all_results.append(result)

        if MODEL_PROVIDER == "kimi":
            time.sleep(KIMI_REQUEST_DELAY_SECONDS)
        else:
            time.sleep(1)

    connection.close()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as output_handle:
        json.dump(all_results, output_handle, indent=2)

    print_accuracy_report(all_results)
    print("")
    print("Full results saved to", OUTPUT_FILE)
    print("Every decision also logged to the 'agent_audit_log' table in bankdb.")


if __name__ == "__main__":
    main()

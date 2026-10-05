"""
APPLY ESCALATION RULES
========================

WHAT THIS PROGRAM DOES
-------------------------
Phase 1 told us WHAT a message is about. Phase 2 drafted a reply for
it. Neither of those steps decided who's allowed to see that draft go
out WITHOUT a human checking it first. That's this program's only
job: read everything the earlier phases already found out, and apply
a set of fixed, explicit rules to decide one of two things for every
message:

  autonomous — safe to send the draft as-is, no human needed
  escalate   — a human must review this before anything is sent

WHY THIS IS RULES, NOT ANOTHER MODEL CALL
----------------------------------------------
Every earlier step in this pipeline that needed judgement (what
category is this? what should the reply say?) used an AI model,
because those are genuinely open-ended language tasks. Escalation is
different: whether a fraud report should go to a human isn't a close
call that benefits from a model's judgement — it should ALWAYS be
yes, every single time, with zero exceptions and zero risk of an
inconsistent answer on a slow day. A fixed rule is more reliable than
a model call for exactly this kind of decision, and it costs nothing
to run.

WHAT "GROUND TRUTH" MEANS HERE
------------------------------------
Back when the test messages were generated, each one was already
labelled with the correct tier it SHOULD receive (autonomous or
escalate) — worked out from the real bankdb data at the time. This
program never looks at that label while making its own decision (that
would be cheating — a real incoming email has no such label attached).
It only checks its own answer against that label afterward, to report
how often the rules actually got it right.
"""

# ---------------------------------------------------------------------------
# SECTION 1: IMPORTS
# ---------------------------------------------------------------------------

import json
import os
from pathlib import Path

import psycopg2
import psycopg2.extras
# Both drafting and routing read the same customer status fields. This shared
# helper avoids maintaining two copies of that database query.
try:
    from .bankdb import fetch_customer_status_details
except ImportError:
    from bankdb import fetch_customer_status_details
# No AI library is imported here at all — this program makes no model
# calls. Every decision comes from plain Python if/else logic below,
# checked against real data already sitting in bankdb.


# ---------------------------------------------------------------------------
# SECTION 2: SETTINGS
# ---------------------------------------------------------------------------

CLASSIFICATION_RESULTS_FILE = Path("output/classification_results.json")
DRAFT_REVIEW_QUEUE_FILE = Path("output/draft_review_queue.json")
TEST_MESSAGES_FILE = Path("output/test_messages.json")
# We read all three earlier outputs: classification for the category
# and extracted entities, the draft queue for the live facts Phase 2
# already looked up, and the original test messages purely to recover
# the ground truth tier for scoring at the end.

OUTPUT_FILE = Path("output/routed_messages.json")

DATABASE_HOST = "localhost"
DATABASE_PORT = 5432
DATABASE_NAME = "bankdb"
DATABASE_USER = "postgres"
DATABASE_PASSWORD = os.environ["PGPASSWORD"]

# Reason codes serious enough to always require a human, wherever they
# turn up. Identical to the rule generate_test_messages.py used when
# it invented the ground truth in the first place — this program is
# now the real version of that same rule.
ESCALATION_REASON_CODES = {"FRAUD_SUSPECTED", "COURT_ORDER"}

# Customer relationship states serious enough that a NEW request from
# that customer should not be handled automatically.
ESCALATION_CUSTOMER_STATUSES = {"SUSPENDED", "PENDING_DELETE", "DELETED", "DECEASED"}

# Categories that escalate every single time, regardless of what the
# account data says. A self-reported fraud claim isn't something a
# rule should ever wave through automatically, even if the account
# itself turns out to be perfectly fine.
ALWAYS_ESCALATE_CATEGORIES = {"fraud_report"}


# ---------------------------------------------------------------------------
# SECTION 3: DATABASE LOOKUPS
# ---------------------------------------------------------------------------

def connect_to_database():
    return psycopg2.connect(
        host=DATABASE_HOST,
        port=DATABASE_PORT,
        dbname=DATABASE_NAME,
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def fetch_account_status_reason(connection, account_number):
    """
    Look up an account's OWN reason for its current status. Used when
    a declined transaction's reason is the generic ACCOUNT_FROZEN code,
    which only tells us the account is frozen, not WHY — and why is
    what actually decides whether this escalates.
    """

    if account_number is None:
        return None

    cursor = connection.cursor()
    cursor.execute(
        "SELECT status_reason FROM account WHERE account_number = %s LIMIT 1;",
        (account_number,),
    )
    row = cursor.fetchone()
    cursor.close()

    if row is None:
        return None

    return row["status_reason"]


def fetch_customer_status(connection, sort_code, customer_number):
    """Look up a customer's real current relationship status."""
    customer = fetch_customer_status_details(connection, sort_code, customer_number)
    return None if customer is None else customer["customer_status"]


# ---------------------------------------------------------------------------
# SECTION 4: THE RULES ENGINE
# ---------------------------------------------------------------------------

def decide_tier(category, entities, live_facts, resolved_sort_code, resolved_customer_number, connection):
    """
    The actual escalation gate. Returns two things: the tier
    ("autonomous" or "escalate"), and a short, human-readable reason
    for that decision — so a reviewer can see WHY the gate decided
    what it did, not just the raw answer.

    Every branch below is a plain, explicit rule. There is
    deliberately no "if unsure, ask a model" fallback anywhere in this
    function — an unrecognised or ambiguous case defaults to
    escalate, on the principle that failing safe (a human looks at
    it) is always better than failing open (it gets sent automatically
    and turns out to be wrong).
    """

    if category in ALWAYS_ESCALATE_CATEGORIES:
        return "escalate", category + " always escalates, regardless of account data"

    if category == "invalid_account_reference":
        return "autonomous", "a clear 'account not found' reply is safe to send automatically"

    if category == "balance_inquiry":
        return "autonomous", "balance inquiries are informational and safe to answer directly"

    if category == "application_status_inquiry":
        return "autonomous", "a routine KYC-pending status is safe to explain automatically"

    if category == "declined_transaction":
        transaction = live_facts.get("transaction")
        if transaction is None:
            return "escalate", "no matching transaction was found — needs human review"

        reason = transaction.get("status_reason")

        if reason == "ACCOUNT_FROZEN":
            # The transaction's own reason only says the account is
            # frozen, not why. The WHY is what actually matters here.
            account_number = entities.get("account_number")
            account_reason = fetch_account_status_reason(connection, account_number)
            if account_reason in ESCALATION_REASON_CODES:
                return "escalate", "account frozen for " + str(account_reason)
            return "autonomous", "account frozen for a routine reason (" + str(account_reason) + ")"

        if reason in ESCALATION_REASON_CODES:
            return "escalate", "transaction declined for " + str(reason)

        return "autonomous", "transaction declined for a routine reason (" + str(reason) + ")"

    if category == "account_status_inquiry":
        account = live_facts.get("account")
        if account is None:
            return "escalate", "the account could not be found — needs human review"

        reason = account.get("status_reason")
        if reason in ESCALATION_REASON_CODES:
            return "escalate", "account status reason is " + str(reason)

        return "autonomous", "account status reason is routine (" + str(reason) + ")"

    if category == "new_account_request":
        # This is the branch that used to crash: it referenced
        # resolved_sort_code without that value ever being passed in.
        # customer_status is a composite-key lookup (sort_code +
        # customer_number together identify one customer row), so both
        # pieces have to arrive here, not just the customer number.
        customer_status = fetch_customer_status(
            connection, resolved_sort_code, resolved_customer_number
        )
        if customer_status in ESCALATION_CUSTOMER_STATUSES:
            return "escalate", "customer relationship status is " + str(customer_status)
        return "autonomous", "customer relationship is in good standing"

    # Any category this program doesn't recognise at all falls here —
    # failing safe rather than guessing.
    return "escalate", "unrecognised category '" + str(category) + "' — defaulting to human review"


def route_message(classification_result, draft_result, connection):
    """Apply the unchanged Phase 3 escalation policy to one production result."""

    # Read the values decide_tier already expects from the earlier-stage
    # results. Defaulting entities/live facts to {} preserves prior behavior.
    category = classification_result.get("extracted_category")
    entities = classification_result.get("extracted_entities") or {}
    live_facts = draft_result.get("live_facts") or {}
    tier, tier_reason = decide_tier(
        category,
        entities,
        live_facts,
        classification_result.get("resolved_sort_code"),
        classification_result.get("resolved_customer_number"),
        connection,
    )
    # Return the same routing fields the existing JSON review queue uses. This
    # function only prepares a decision; it does not send or alter email.
    return {
        "message_id": classification_result["message_id"],
        "message_body": classification_result["message_body"],
        "category": category,
        "draft_reply": draft_result.get("draft_reply"),
        "cited_rule_ids": draft_result.get("cited_rule_ids"),
        "tier": tier,
        "tier_reason": tier_reason,
    }


# ---------------------------------------------------------------------------
# SECTION 5: SCORING AGAINST GROUND TRUTH
# ---------------------------------------------------------------------------

def build_ground_truth_lookup(test_messages):
    """
    Build a dictionary mapping message_id -> ground truth tier, so we
    can look up the correct answer for each message quickly while
    scoring.
    """

    lookup = {}
    for one_test_message in test_messages:
        message_id = one_test_message["message"]["id"]
        lookup[message_id] = one_test_message["ground_truth"].get("tier")

    return lookup


def print_accuracy_report(routed_messages):
    """Print how often the escalation gate's decision matched the ground truth tier."""

    total_count = len(routed_messages)
    correct_count = 0
    mismatches = []

    for one_routed_message in routed_messages:
        if one_routed_message["tier"] == one_routed_message["ground_truth_tier"]:
            correct_count = correct_count + 1
        else:
            mismatches.append(one_routed_message)

    print("")
    print("=" * 60)
    print("ESCALATION GATE ACCURACY REPORT")
    print("=" * 60)
    print("Total messages:", total_count)
    if total_count > 0:
        print(
            "Tier accuracy:", correct_count, "/", total_count,
            "(" + str(round(100 * correct_count / total_count, 1)) + "%)",
        )

    if mismatches:
        print("")
        print("Messages where the gate's decision did NOT match ground truth:")
        for one_mismatch in mismatches:
            print(
                "  " + one_mismatch["message_id"] + ": expected '"
                + str(one_mismatch["ground_truth_tier"]) + "', gate decided '"
                + str(one_mismatch["tier"]) + "' (" + one_mismatch["tier_reason"] + ")"
            )


# ---------------------------------------------------------------------------
# SECTION 6: THE MAIN PROGRAM
# ---------------------------------------------------------------------------

def main():

    with open(CLASSIFICATION_RESULTS_FILE, "r", encoding="utf-8") as f:
        classification_results = json.load(f)

    with open(DRAFT_REVIEW_QUEUE_FILE, "r", encoding="utf-8") as f:
        draft_review_queue = json.load(f)

    with open(TEST_MESSAGES_FILE, "r", encoding="utf-8") as f:
        test_messages = json.load(f)

    print("Loaded", len(classification_results), "classification results")
    print("Loaded", len(draft_review_queue), "drafted replies")

    drafts_by_message_id = {}
    for one_draft in draft_review_queue:
        drafts_by_message_id[one_draft["message_id"]] = one_draft

    ground_truth_lookup = build_ground_truth_lookup(test_messages)

    connection = connect_to_database()

    routed_messages = []
    for one_result in classification_results:
        if "error" in one_result:
            continue

        message_id = one_result["message_id"]
        matching_draft = drafts_by_message_id.get(message_id)

        if matching_draft is None:
            print("No draft found for " + message_id + " — skipping.")
            continue

        routed = route_message(one_result, matching_draft, connection)
        routed["ground_truth_tier"] = ground_truth_lookup.get(message_id)
        routed_messages.append(routed)

    connection.close()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(routed_messages, f, indent=2, default=str)

    print_accuracy_report(routed_messages)
    print("")
    print("Done. Wrote", len(routed_messages), "routed messages to", OUTPUT_FILE)
    print("Messages routed 'autonomous' are still not being sent by this program —")
    print("that action belongs to the live email integration, not built yet.")


if __name__ == "__main__":
    main()

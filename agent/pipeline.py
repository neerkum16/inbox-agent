"""
PHASE 0-4 MESSAGE PROCESSING PIPELINE
======================================

This module joins the existing business stages into one reusable function.
Adapters supply an InboundMessage; the pipeline classifies it, validates its
entities against bankdb, enforces the identity gate, gathers live facts and
knowledge-base rules, writes a draft, then applies the unchanged escalation
policy.

It does not connect to Gmail, send email, create drafts, add labels, or change
any mailbox. Those responsibilities remain outside this processing core.
"""

from .classify_and_extract import classify_message
from .contracts import InboundMessage
from .generate_draft_response import draft_response
from .apply_escalation_rules import route_message


# ---------------------------------------------------------------------------
# IDENTITY-FAILURE RESPONSES
# ---------------------------------------------------------------------------

def build_identity_failure_reply(classification_result):
    """Build a deterministic, non-sensitive reply when identity fails.

    Every branch here is deliberately vague about WHY verification failed.
    Two security properties matter more than being maximally helpful:

    1. A wrong guess must never be corrected into a right one. Confirming or
       revealing a specific correct value on a failed attempt turns this
       into an oracle an attacker can query repeatedly.
    2. Different failure causes that a legitimate customer can't tell apart
       anyway (an account that doesn't exist vs. one that exists but isn't
       theirs) must produce IDENTICAL external text, or the wording itself
       becomes a side channel for enumerating real account numbers.
    """

    status = classification_result.get("identity_status")

    if status == "email_not_registered":
        return (
            "We could not verify your identity because this email address is "
            "not registered with us. Please contact us using your registered "
            "email address."
        )

    if status == "customer_number_mismatch":
        # Deliberately does not reveal the correct customer number, or even
        # confirm that a record exists for this email at all. The previous
        # version returned the correct value outright when exactly one
        # record was found — that defeats the point of asking for a
        # customer number as a verification factor in the first place.
        return (
            "The customer number provided could not be verified. Please "
            "check the customer number and try again, or provide your "
            "account number instead."
        )

    if status == "multiple_customers_identifier_missing":
        return (
            "We found multiple customer records associated with this email "
            "address. Please provide your customer number or account number "
            "so we can identify the correct account."
        )

    if status in ("account_number_not_found", "account_number_not_owned"):
        # Same external text for both states, on purpose. identity_status
        # still distinguishes them internally for audit logging — only the
        # customer-facing wording is unified, so the response itself can't
        # be used to test whether an account number exists in our system.
        return (
            "We could not verify the account number provided. Please check "
            "the account number and try again."
        )

    if status == "multiple_customers_match_account":
        return (
            "We could not uniquely verify the account provided. Please "
            "contact us using the correct registered email address or provide "
            "your customer number."
        )

    if status == "multiple_matching_customer_records":
        return (
            "We could not uniquely verify the customer number provided. "
            "Please provide your account number or contact us using the "
            "correct registered email address."
        )

    return (
        "We could not verify your identity for this request. Please provide "
        "your customer number or account number."
    )


def build_identity_failure_result(classification_result):
    """Return the safe pipeline result used when the identity gate blocks."""

    return {
        "message_id": classification_result.get("message_id"),
        "message_body": classification_result.get("message_body"),
        "category": classification_result.get("extracted_category"),
        "priority": classification_result.get("extracted_priority"),
        "draft_reply": build_identity_failure_reply(classification_result),
        "live_facts": {},
        "retrieved_rule_ids": [],
        "cited_rule_ids": [],
        "identity_gate_blocked": True,
        "identity_status": classification_result.get("identity_status"),
    }


# ---------------------------------------------------------------------------
# PIPELINE ORCHESTRATION
# ---------------------------------------------------------------------------

def process_message(message: InboundMessage, client, connection, embedding_model):
    """Process one normalized message through every existing business stage."""

    # Phase 1 identifies the sender, asks the model for category/entities, and
    # validates those entities against bankdb.
    classification_result = classify_message(message, client, connection)

    if "error" in classification_result:
        return {
            "classification": classification_result,
            "draft": None,
            "routing": None,
        }

    # The identity gate is deliberately before live-fact lookup and routing.
    # A sender must not receive customer-specific banking data unless the
    # deterministic identity resolver has verified the sender/identifier
    # relationship.
    if not classification_result.get("identity_eligible", False):
        return {
            "classification": classification_result,
            "draft": build_identity_failure_result(classification_result),
            "routing": None,
        }

    # Phase 2 gathers bankdb facts, retrieves vector-store rules, and asks the
    # model for a grounded response. No email action occurs here.
    draft_result = draft_response(
        classification_result,
        client,
        connection,
        embedding_model,
    )

    if "error" in draft_result:
        return {
            "classification": classification_result,
            "draft": draft_result,
            "routing": None,
        }

    # Phase 3 is deterministic Python policy. The existing routing policy is
    # intentionally unchanged by the identity gate.
    routing_result = route_message(classification_result, draft_result, connection)

    return {
        "classification": classification_result,
        "draft": draft_result,
        "routing": routing_result,
    }

"""
PHASE 4A UNIT TESTS
===================

These tests exercise the normalized-message contract and the extracted
per-message functions without calling a real LLM, Postgres, or Gmail. Mocking
lets a test replace an external dependency with a predictable answer.
"""

# unittest is Python's built-in test framework. It supplies test case classes
# and assertion methods such as assertEqual.
import unittest
from datetime import datetime
# patch temporarily replaces an imported function while one test runs.
from unittest.mock import patch

from agent.adapters.fixtures import normalize_fixture_message
from agent.apply_escalation_rules import route_message
from agent.classify_and_extract import classify_message
from agent.contracts import InboundMessage
from agent.generate_draft_response import draft_response


class FakeClient:
    """A tiny stand-in so tests can pass a client object without an API call."""

    def __init__(self, reply):
        self.reply = reply


class Phase4ATests(unittest.TestCase):
    """Tests for the Phase 4A contract and reusable production functions."""

    def make_message(self):
        """Build one ordinary normalized fixture message for several tests."""
        return InboundMessage(
            source="fixture",
            source_message_id="msg_1",
            source_thread_id="thread_1",
            from_address="customer@examplebank.com",
            to_addresses=["support@examplebank.com"],
            subject="Balance enquiry",
            body_text="What is my balance for account 10000001?",
            received_at=datetime(2026, 9, 9, 9, 10, 49),
            rfc_message_id=None,
            headers=None,
        )

    def test_inbound_message_construction(self):
        """The dataclass should store the message values supplied to it."""
        message = self.make_message()
        self.assertEqual(message.source, "fixture")
        self.assertEqual(message.to_addresses, ["support@examplebank.com"])

    def test_fixture_normalization_keeps_ground_truth_out_of_message(self):
        """Fixture scoring data must not become production message data."""
        fixture = {
            "message": {
                "id": "msg_1", "threadId": "thread_1", "from": "customer@examplebank.com",
                "to": "support@examplebank.com", "subject": "Subject", "body": "Body",
                "date": "2026-09-09 09:10:49",
            },
            "ground_truth": {"category": "fraud_report"},
        }
        message = normalize_fixture_message(fixture)
        self.assertEqual(message.source_message_id, "msg_1")
        self.assertFalse(hasattr(message, "ground_truth"))

    @patch("agent.classify_and_extract.ask_model")
    @patch("agent.classify_and_extract.validate_entities")
    @patch("agent.classify_and_extract.look_up_customer_by_email", return_value="1000000001")
    def test_production_classification_has_no_ground_truth_dependency(self, lookup, validate, ask):
        """Classification uses adapter data, model output, and validation only."""
        ask.return_value = '{"category":"balance_inquiry","priority":"low","entities":{"account_number":"10000001"}}'
        validate.return_value = {"account_number_exists": True, "account_matches_customer": True}
        connection = object()
        result = classify_message(self.make_message(), FakeClient("unused"), connection)
        self.assertEqual(result["message_id"], "msg_1")
        self.assertEqual(result["extracted_category"], "balance_inquiry")
        self.assertNotIn("ground_truth_category", result)
        lookup.assert_called_once_with(connection, "customer@examplebank.com")

    @patch("agent.generate_draft_response.ask_model")
    @patch("agent.generate_draft_response.retrieve_relevant_rules", return_value=[])
    @patch("agent.generate_draft_response.build_retrieval_query", return_value=None)
    @patch("agent.generate_draft_response.look_up_live_facts", return_value={"account": {"available_balance": "10.00"}})
    def test_production_drafting(self, facts, query, retrieval, ask):
        """Drafting uses classification output and mocked grounding dependencies."""
        ask.return_value = '{"draft_reply":"Your balance is £10.00.","cited_rule_ids":[]}'
        result = draft_response({
            "message_id": "msg_1", "message_body": "Balance?", "extracted_category": "balance_inquiry",
            "extracted_priority": "low", "extracted_entities": {}, "validation_result": {},
            "resolved_customer_number": "1000000001",
        }, FakeClient("unused"), object(), object())
        self.assertEqual(result["draft_reply"], "Your balance is £10.00.")
        self.assertNotIn("ground_truth_tier", result)

    def test_production_routing_unknown_category_fails_safe(self):
        """The unchanged fallback tier remains escalate for an unknown category."""
        result = route_message(
            {"message_id": "msg_1", "message_body": "Unknown", "extracted_category": "other",
             "extracted_entities": {}, "resolved_customer_number": None},
            {"live_facts": {}, "draft_reply": "", "cited_rule_ids": []}, object(),
        )
        self.assertEqual(result["tier"], "escalate")

    def test_production_routing_missing_entity_escalates_for_account_status(self):
        """An account-status request with no matched account keeps its old route."""
        result = route_message(
            {"message_id": "msg_1", "message_body": "Why frozen?", "extracted_category": "account_status_inquiry",
             "extracted_entities": {}, "resolved_customer_number": None},
            {"live_facts": {}, "draft_reply": "", "cited_rule_ids": []}, object(),
        )
        self.assertEqual(result["tier"], "escalate")

    def test_production_routing_invalid_account_preserves_existing_policy(self):
        """This explicitly verifies the existing invalid-account policy is unchanged."""
        result = route_message(
            {"message_id": "msg_1", "message_body": "Account missing", "extracted_category": "invalid_account_reference",
             "extracted_entities": {"account_number": "00000000"}, "resolved_customer_number": None},
            {"live_facts": {}, "draft_reply": "", "cited_rule_ids": []}, object(),
        )
        self.assertEqual(result["tier"], "autonomous")


if __name__ == "__main__":
    unittest.main()

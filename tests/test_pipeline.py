"""
PIPELINE TESTS — IDENTITY FAILURE REPLIES AND ORCHESTRATION FLOW
===================================================================

This file replaces test_pipeline_identity_gate.py and test_pipeline_flow.py,
which tested different concerns of the same two functions in pipeline.py via
the same AST-isolation technique. Splitting them into two files never bought
any real independence — both extracted build_identity_failure_reply and
build_identity_failure_result from the same source file the same way.

Two things are tested here, as two classes:

    TestIdentityFailureReplies   -- does each identity_status produce the
                                     right WORDING, and nothing it shouldn't?
    TestPipelineOrchestration    -- does process_message call classify/draft/
                                     route in the right order, and stop early
                                     when identity fails?
"""

import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).parent.parent / "agent" / "pipeline.py"
tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
selected = []
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in {
        "build_identity_failure_reply",
        "build_identity_failure_result",
        "process_message",
    }:
        selected.append(node)
module = ast.Module(body=selected, type_ignores=[])
ast.fix_missing_locations(module)


# ---------------------------------------------------------------------------
# TestIdentityFailureReplies — reply wording, no orchestration involved
# ---------------------------------------------------------------------------

reply_namespace = {"InboundMessage": object}
exec(compile(module, str(SOURCE), "exec"), reply_namespace)


class TestIdentityFailureReplies(unittest.TestCase):

    def call(self, status, records=None):
        result = {
            "message_id": "m1",
            "message_body": "test",
            "identity_status": status,
            "customer_records_for_email": records or [],
            "extracted_category": "balance_inquiry",
            "extracted_priority": "low",
        }
        return reply_namespace["build_identity_failure_result"](result)

    def test_unregistered_email_does_not_contain_customer_data(self):
        result = self.call("email_not_registered")
        self.assertIn("not registered", result["draft_reply"])
        self.assertEqual(result["live_facts"], {})
        self.assertEqual(result["retrieved_rule_ids"], [])
        self.assertTrue(result["identity_gate_blocked"])

    def test_customer_number_mismatch_does_not_disclose_correct_number(self):
        # This replaces a test that asserted the OPPOSITE of this on
        # purpose — the previous version of pipeline.py revealed the
        # correct customer number here, and the previous version of this
        # test treated that disclosure as correct behavior. It wasn't:
        # confirming or correcting a wrong guess defeats using the
        # customer number as a verification factor at all. This test now
        # asserts the fixed, safe behavior instead.
        result = self.call(
            "customer_number_mismatch",
            [{"sort_code": "123456", "customer_number": "100000001"}],
        )
        self.assertNotIn("100000001", result["draft_reply"])

    def test_account_not_found_and_not_owned_produce_identical_text(self):
        # Different wording for these two states would let someone tell
        # "this account doesn't exist" apart from "this account exists
        # but isn't yours" without ever proving ownership of either —
        # an account-number enumeration oracle. Both must read the same.
        not_found = self.call("account_number_not_found")
        not_owned = self.call("account_number_not_owned")
        self.assertEqual(not_found["draft_reply"], not_owned["draft_reply"])

    def test_multiple_customers_without_identifier_asks_for_identifier(self):
        result = self.call(
            "multiple_customers_identifier_missing",
            [
                {"sort_code": "123456", "customer_number": "100000001"},
                {"sort_code": "654321", "customer_number": "100000002"},
            ],
        )
        self.assertIn("customer number or account number", result["draft_reply"])


# ---------------------------------------------------------------------------
# TestPipelineOrchestration — does process_message call things in order?
# ---------------------------------------------------------------------------
# This needs its own namespace with fake classify/draft/route functions
# injected, so it exercises real orchestration logic without touching a
# real LLM, Postgres, or Gmail.

calls = []


def fake_classify(message, client, connection):
    calls.append("classify")
    return fake_classify.result


def fake_draft(classification, client, connection, embedding_model):
    calls.append("draft")
    return {"draft_reply": "normal", "live_facts": {}}


def fake_route(classification, draft, connection):
    calls.append("route")
    return {"tier": "autonomous"}


orchestration_namespace = {
    "InboundMessage": object,
    "classify_message": fake_classify,
    "draft_response": fake_draft,
    "route_message": fake_route,
}
exec(compile(module, str(SOURCE), "exec"), orchestration_namespace)


class TestPipelineOrchestration(unittest.TestCase):

    def test_identity_failure_stops_before_draft_and_route(self):
        calls.clear()
        fake_classify.result = {
            "message_id": "m1",
            "message_body": "balance please",
            "identity_status": "email_not_registered",
            "identity_eligible": False,
            "customer_records_for_email": [],
            "extracted_category": "balance_inquiry",
            "extracted_priority": "low",
        }

        result = orchestration_namespace["process_message"]("message", None, None, None)

        self.assertEqual(calls, ["classify"])
        self.assertIsNone(result["routing"])
        self.assertTrue(result["draft"]["identity_gate_blocked"])
        self.assertEqual(result["draft"]["live_facts"], {})

    def test_verified_identity_continues_existing_pipeline(self):
        calls.clear()
        fake_classify.result = {
            "message_id": "m2",
            "message_body": "balance please",
            "identity_status": "customer_number_match",
            "identity_eligible": True,
            "resolved_sort_code": "123456",
            "resolved_customer_number": "100000001",
            "extracted_category": "balance_inquiry",
            "extracted_priority": "low",
            "extracted_entities": {},
        }

        result = orchestration_namespace["process_message"]("message", None, None, None)

        self.assertEqual(calls, ["classify", "draft", "route"])
        self.assertEqual(result["routing"]["tier"], "autonomous")


if __name__ == "__main__":
    unittest.main()

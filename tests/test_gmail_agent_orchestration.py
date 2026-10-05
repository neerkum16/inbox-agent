"""
GMAIL AGENT ORCHESTRATION TESTS
==================================

process_one_gmail_message and resume_autonomous_delivery had no test
coverage at all before this file. Every individual module they call
(processing_state, delivery_state, send_policy, pipeline) is well tested
in isolation -- but the wiring between them, in gmail_agent.py itself, was
untested. That gap is exactly where the resolved_sort_code bug lived: a
defect in how two well-tested pieces are connected, not a defect inside
either piece.

Both functions are extracted from gmail_agent.py via the same AST-isolation
technique already used elsewhere in this test suite (test_identity.py,
test_pipeline.py), rather than importing the module directly -- gmail_agent.py
imports the Gmail/Google auth libraries at module level, which this test
suite should not need installed just to check this orchestration logic.

Every external dependency (claim_message, delivery-state functions, Gmail
transport functions, the banking pipeline itself) is replaced with a small
recording fake. Each fake remembers what it was called with and returns
whatever the test configures -- the same pattern already used for
fake_classify/fake_draft/fake_route in test_pipeline.py.
"""

import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).parent.parent / "gmail_agent.py"
tree = ast.parse(SOURCE.read_text(encoding="utf-8"))

# Two SEPARATE AST modules, not one. resume_autonomous_delivery needs to be
# fakeable while testing process_one_gmail_message's orchestration -- but if
# both functions were compiled into the same exec() namespace, the real
# resume_autonomous_delivery definition would silently overwrite whatever
# fake was placed in that namespace beforehand, since exec() defines names
# in the dict it's given, unconditionally. Keeping them in separate modules,
# each compiled into its own fresh namespace, avoids that collision.
#
# Duplicated-name note: _processing_error, _mark_processing_failed, and
# _mark_processing_completed are each defined TWICE in gmail_agent.py. Only
# the LAST definition of each survives when Python compiles the module body
# in order -- exactly as it would on a real import -- so pulling every
# matching node (not just the first) deliberately mirrors real behavior.
HELPER_NAMES = {"_processing_error", "_mark_processing_failed", "_mark_processing_completed"}

process_selected = [
    node for node in tree.body
    if isinstance(node, ast.FunctionDef)
    and node.name in HELPER_NAMES | {"process_one_gmail_message"}
]
process_module = ast.Module(body=process_selected, type_ignores=[])
ast.fix_missing_locations(process_module)

resume_selected = [
    node for node in tree.body
    if isinstance(node, ast.FunctionDef)
    and node.name in HELPER_NAMES | {"resume_autonomous_delivery"}
]
resume_module = ast.Module(body=resume_selected, type_ignores=[])
ast.fix_missing_locations(resume_module)


class FakeMessage:
    """Stands in for one InboundMessage without needing the real dataclass."""

    def __init__(self, source="gmail", source_message_id="msg-1", source_thread_id="thread-1",
                 from_address="customer@example.com", subject="Balance please"):
        self.source = source
        self.source_message_id = source_message_id
        self.source_thread_id = source_thread_id
        self.from_address = from_address
        self.subject = subject


class RecordingFake:
    """
    A callable that records every call it receives and returns a
    preconfigured value (or raises a preconfigured exception). Building one
    generic fake, rather than a bespoke one per dependency, keeps this file
    from needing ~15 nearly-identical small classes.
    """

    def __init__(self, return_value=None, side_effect=None):
        self.calls = []
        self.return_value = return_value
        self.side_effect = side_effect

    def __call__(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        if self.side_effect is not None:
            raise self.side_effect
        return self.return_value

    @property
    def call_count(self):
        return len(self.calls)


def build_namespace(target, **overrides):
    """
    Build a fresh namespace with a recording fake for every name the target
    function references, then apply per-test overrides on top, then compile
    ONLY the requested module ("process" or "resume") into it. GMAIL_USER_ID
    is a plain constant these functions read, not a function.
    """

    namespace = {
        "GMAIL_USER_ID": "me",
        "claim_message": RecordingFake(),
        "get_delivery_state": RecordingFake(return_value=None),
        "mark_failed": RecordingFake(),
        "mark_delivery_failed": RecordingFake(),
        "is_autonomous_send_candidate": RecordingFake(return_value=False),
        "process_message": RecordingFake(return_value={}),
        "create_draft_from_processing_result": RecordingFake(return_value={"id": "draft-x", "message": {"id": "msg-x"}}),
        "resume_autonomous_delivery": RecordingFake(return_value={"processing_status": "COMPLETED"}),
        "prepare_delivery": RecordingFake(),
        "find_sent_message_by_rfc_message_id": RecordingFake(return_value=None),
        "get_draft": RecordingFake(return_value=None),
        "find_draft_by_rfc_message_id": RecordingFake(return_value=None),
        "attach_draft": RecordingFake(),
        "mark_sending": RecordingFake(),
        "send_gmail_draft": RecordingFake(return_value={"id": "sent-1"}),
        "mark_sent": RecordingFake(),
        "mark_unknown": RecordingFake(),
        "build_outbound_message_id": RecordingFake(return_value="<out-1@gmail-agent.local>"),
        "mark_completed": RecordingFake(),
    }
    namespace.update(overrides)
    module_to_run = process_module if target == "process" else resume_module
    exec(compile(module_to_run, str(SOURCE), "exec"), namespace)
    return namespace


# ---------------------------------------------------------------------------
# process_one_gmail_message
# ---------------------------------------------------------------------------

class TestProcessOneGmailMessage(unittest.TestCase):

    def test_already_claimed_elsewhere_is_skipped_without_running_pipeline(self):
        namespace = build_namespace("process",
            claim_message=RecordingFake(return_value={
                "claimed": False, "status": "PROCESSING", "reason": "already_processed_or_in_progress",
                "processing_result": None,
            }),
        )
        result = namespace["process_one_gmail_message"](
            {"message": FakeMessage()}, None, None, None, None,
        )
        self.assertEqual(result["processing_status"], "SKIPPED")
        self.assertEqual(namespace["process_message"].call_count, 0)

    def test_existing_sent_delivery_short_circuits_before_the_llm_pipeline_runs(self):
        # This is the most important idempotency property in the whole
        # file: if delivery already reached SENT on an earlier run, the LLM
        # pipeline must never run again for this message, under any
        # circumstance -- rerunning it risks a second autonomous reply.
        namespace = build_namespace("process",
            claim_message=RecordingFake(return_value={"claimed": True, "reason": "new_message"}),
            get_delivery_state=RecordingFake(return_value={
                "status": "SENT", "gmail_sent_message_id": "sent-1", "processing_result": {},
            }),
        )
        result = namespace["process_one_gmail_message"](
            {"message": FakeMessage()}, None, None, None, None,
        )
        self.assertEqual(namespace["process_message"].call_count, 0)
        self.assertEqual(namespace["mark_completed"].call_count, 1)

    def test_resumable_prepared_delivery_skips_the_llm_and_resumes_send(self):
        stored_result = {
            "classification": {"identity_eligible": True},
            "draft": {"draft_reply": "reply"},
            "routing": {"tier": "autonomous"},
        }
        namespace = build_namespace("process",
            claim_message=RecordingFake(return_value={"claimed": True, "reason": "retry_or_stale_reclaim"}),
            get_delivery_state=RecordingFake(return_value={
                "status": "PREPARED", "processing_result": stored_result,
            }),
            is_autonomous_send_candidate=RecordingFake(return_value=True),
        )
        namespace["process_one_gmail_message"](
            {"message": FakeMessage()}, None, None, None, None,
        )
        self.assertEqual(namespace["process_message"].call_count, 0)
        self.assertEqual(namespace["resume_autonomous_delivery"].call_count, 1)

    def test_resumable_delivery_that_fails_the_send_gate_is_marked_failed(self):
        # A PREPARED/SENDING/UNKNOWN record that no longer passes the send
        # gate (e.g. policy tightened between runs) must not be resumed --
        # it must fail loudly, not be silently sent anyway.
        stored_result = {"classification": {}, "draft": {}, "routing": {"tier": "autonomous"}}
        namespace = build_namespace("process",
            claim_message=RecordingFake(return_value={"claimed": True, "reason": "retry_or_stale_reclaim"}),
            get_delivery_state=RecordingFake(return_value={
                "status": "UNKNOWN", "processing_result": stored_result,
            }),
            is_autonomous_send_candidate=RecordingFake(return_value=False),
        )
        with self.assertRaises(RuntimeError):
            namespace["process_one_gmail_message"](
                {"message": FakeMessage()}, None, None, None, None,
            )
        self.assertEqual(namespace["mark_delivery_failed"].call_count, 1)
        self.assertEqual(namespace["resume_autonomous_delivery"].call_count, 0)

    def test_fresh_autonomous_result_is_routed_to_resume_delivery_not_a_draft(self):
        namespace = build_namespace("process",
            claim_message=RecordingFake(return_value={"claimed": True, "reason": "new_message"}),
            process_message=RecordingFake(return_value={
                "classification": {"identity_eligible": True},
                "draft": {"draft_reply": "reply"},
                "routing": {"tier": "autonomous"},
            }),
            is_autonomous_send_candidate=RecordingFake(return_value=True),
        )
        namespace["process_one_gmail_message"](
            {"message": FakeMessage()}, None, None, None, None,
        )
        self.assertEqual(namespace["resume_autonomous_delivery"].call_count, 1)
        self.assertEqual(namespace["create_draft_from_processing_result"].call_count, 0)

    def test_fresh_non_autonomous_result_creates_a_review_draft(self):
        namespace = build_namespace("process",
            claim_message=RecordingFake(return_value={"claimed": True, "reason": "new_message"}),
            process_message=RecordingFake(return_value={
                "classification": {"identity_eligible": True},
                "draft": {"draft_reply": "reply"},
                "routing": {"tier": "human_review"},
            }),
            is_autonomous_send_candidate=RecordingFake(return_value=False),
        )
        namespace["process_one_gmail_message"](
            {"message": FakeMessage()}, None, None, None, None,
        )
        self.assertEqual(namespace["create_draft_from_processing_result"].call_count, 1)
        self.assertEqual(namespace["resume_autonomous_delivery"].call_count, 0)
        self.assertEqual(namespace["mark_completed"].call_count, 1)

    def test_pipeline_error_is_marked_failed_not_completed(self):
        namespace = build_namespace("process",
            claim_message=RecordingFake(return_value={"claimed": True, "reason": "new_message"}),
            process_message=RecordingFake(return_value={
                "classification": {"error": "model call failed"}, "draft": None, "routing": None,
            }),
        )
        namespace["process_one_gmail_message"](
            {"message": FakeMessage()}, None, None, None, None,
        )
        self.assertEqual(namespace["mark_failed"].call_count, 1)
        self.assertEqual(namespace["mark_completed"].call_count, 0)

    def test_exception_after_delivery_already_sent_is_not_overwritten_as_failed(self):
        # The except-block re-check: if delivery already reached SENT before
        # the exception was raised, do not clobber that with FAILED.
        namespace = build_namespace("process",
            claim_message=RecordingFake(return_value={"claimed": True, "reason": "new_message"}),
            process_message=RecordingFake(side_effect=RuntimeError("boom")),
            get_delivery_state=RecordingFake(return_value={
                "status": "SENT", "gmail_sent_message_id": "sent-1", "processing_result": {},
            }),
        )
        namespace["process_one_gmail_message"](
            {"message": FakeMessage()}, None, None, None, None,
        )
        self.assertEqual(namespace["mark_failed"].call_count, 0)
        self.assertEqual(namespace["mark_completed"].call_count, 1)

    def test_exception_without_a_sent_delivery_marks_failed_and_reraises(self):
        namespace = build_namespace("process",
            claim_message=RecordingFake(return_value={"claimed": True, "reason": "new_message"}),
            process_message=RecordingFake(side_effect=RuntimeError("boom")),
            get_delivery_state=RecordingFake(return_value=None),
        )
        with self.assertRaises(RuntimeError):
            namespace["process_one_gmail_message"](
                {"message": FakeMessage()}, None, None, None, None,
            )
        self.assertEqual(namespace["mark_failed"].call_count, 1)


# ---------------------------------------------------------------------------
# resume_autonomous_delivery
# ---------------------------------------------------------------------------

class TestResumeAutonomousDelivery(unittest.TestCase):

    def test_already_sent_state_short_circuits_with_no_gmail_calls(self):
        namespace = build_namespace("resume",
            prepare_delivery=RecordingFake(return_value={
                "status": "SENT", "outbound_message_id": "<x@y>", "gmail_draft_id": None,
            }),
        )
        namespace["resume_autonomous_delivery"](
            service=None, connection=None, message=FakeMessage(), processing_result={},
        )
        self.assertEqual(namespace["send_gmail_draft"].call_count, 0)
        self.assertEqual(namespace["mark_completed"].call_count, 1)

    def test_ambiguous_state_resolved_by_finding_it_already_in_sent(self):
        namespace = build_namespace("resume",
            prepare_delivery=RecordingFake(return_value={
                "status": "UNKNOWN", "outbound_message_id": "<x@y>", "gmail_draft_id": "draft-1",
            }),
            find_sent_message_by_rfc_message_id=RecordingFake(return_value={"id": "sent-99"}),
        )
        namespace["resume_autonomous_delivery"](
            service=None, connection=None, message=FakeMessage(), processing_result={},
        )
        self.assertEqual(namespace["mark_sent"].call_count, 1)
        self.assertEqual(namespace["send_gmail_draft"].call_count, 0)

    def test_existing_draft_is_reused_rather_than_recreated(self):
        namespace = build_namespace("resume",
            prepare_delivery=RecordingFake(return_value={
                "status": "PREPARED", "outbound_message_id": "<x@y>", "gmail_draft_id": "draft-1",
            }),
            get_draft=RecordingFake(return_value={"id": "draft-1", "message": {"id": "msg-1"}}),
        )
        namespace["resume_autonomous_delivery"](
            service=None, connection=None, message=FakeMessage(), processing_result={},
        )
        self.assertEqual(namespace["create_draft_from_processing_result"].call_count, 0)
        self.assertEqual(namespace["send_gmail_draft"].call_count, 1)
        self.assertEqual(namespace["mark_sent"].call_count, 1)

    def test_orphaned_draft_found_by_message_id_is_reattached_not_recreated(self):
        namespace = build_namespace("resume",
            prepare_delivery=RecordingFake(return_value={
                "status": "PREPARED", "outbound_message_id": "<x@y>", "gmail_draft_id": None,
            }),
            find_draft_by_rfc_message_id=RecordingFake(return_value={"id": "draft-2", "message": {"id": "msg-2"}}),
            get_delivery_state=RecordingFake(return_value={
                "status": "PREPARED", "outbound_message_id": "<x@y>", "gmail_draft_id": "draft-2",
            }),
        )
        namespace["resume_autonomous_delivery"](
            service=None, connection=None, message=FakeMessage(), processing_result={},
        )
        self.assertEqual(namespace["attach_draft"].call_count, 1)
        self.assertEqual(namespace["create_draft_from_processing_result"].call_count, 0)

    def test_no_draft_anywhere_creates_exactly_one_new_draft(self):
        namespace = build_namespace("resume",
            prepare_delivery=RecordingFake(return_value={
                "status": "PREPARED", "outbound_message_id": "<x@y>", "gmail_draft_id": None,
            }),
            get_delivery_state=RecordingFake(return_value={
                "status": "PREPARED", "outbound_message_id": "<x@y>", "gmail_draft_id": "draft-new",
            }),
        )
        namespace["resume_autonomous_delivery"](
            service=None, connection=None, message=FakeMessage(), processing_result={},
        )
        self.assertEqual(namespace["create_draft_from_processing_result"].call_count, 1)
        self.assertEqual(namespace["attach_draft"].call_count, 1)

    def test_neither_draft_nor_sent_message_found_raises_and_never_recreates(self):
        # The critical duplicate-send protection: if we can't find the draft
        # OR the sent message, never invent a replacement email.
        namespace = build_namespace("resume",
            prepare_delivery=RecordingFake(return_value={
                "status": "SENDING", "outbound_message_id": "<x@y>", "gmail_draft_id": "draft-gone",
            }),
            get_draft=RecordingFake(return_value=None),
        )
        with self.assertRaises(RuntimeError):
            namespace["resume_autonomous_delivery"](
                service=None, connection=None, message=FakeMessage(), processing_result={},
            )
        self.assertEqual(namespace["mark_unknown"].call_count, 1)
        self.assertEqual(namespace["create_draft_from_processing_result"].call_count, 0)

    def test_send_exception_confirmed_sent_afterward_is_treated_as_success(self):
        namespace = build_namespace("resume",
            prepare_delivery=RecordingFake(return_value={
                "status": "PREPARED", "outbound_message_id": "<x@y>", "gmail_draft_id": "draft-1",
            }),
            get_draft=RecordingFake(return_value={"id": "draft-1", "message": {"id": "msg-1"}}),
            send_gmail_draft=RecordingFake(side_effect=ConnectionError("timeout")),
            find_sent_message_by_rfc_message_id=RecordingFake(return_value=None),
        )
        # First call (before send) returns None so it doesn't short-circuit;
        # the second call, inside the except block, must confirm the send.
        calls_so_far = {"n": 0}
        def sequenced(*args, **kwargs):
            calls_so_far["n"] += 1
            namespace["find_sent_message_by_rfc_message_id"].calls.append({"args": args, "kwargs": kwargs})
            return None if calls_so_far["n"] == 1 else {"id": "sent-after-error"}
        original_fake = namespace["find_sent_message_by_rfc_message_id"]
        namespace["find_sent_message_by_rfc_message_id"] = sequenced
        namespace["find_sent_message_by_rfc_message_id"].calls = original_fake.calls

        namespace["resume_autonomous_delivery"](
            service=None, connection=None, message=FakeMessage(), processing_result={},
        )
        self.assertEqual(namespace["mark_sent"].call_count, 1)

    def test_send_exception_not_in_sent_but_draft_survives_says_retry_can_resume(self):
        namespace = build_namespace("resume",
            prepare_delivery=RecordingFake(return_value={
                "status": "PREPARED", "outbound_message_id": "<x@y>", "gmail_draft_id": "draft-1",
            }),
            get_draft=RecordingFake(return_value={"id": "draft-1", "message": {"id": "msg-1"}}),
            send_gmail_draft=RecordingFake(side_effect=ConnectionError("timeout")),
            find_sent_message_by_rfc_message_id=RecordingFake(return_value=None),
        )
        with self.assertRaises(RuntimeError) as raised:
            namespace["resume_autonomous_delivery"](
                service=None, connection=None, message=FakeMessage(), processing_result={},
            )
        self.assertIn("retry can", str(raised.exception))
        self.assertEqual(namespace["mark_unknown"].call_count, 1)

    def test_send_exception_and_draft_also_gone_says_manual_reconciliation(self):
        namespace = build_namespace("resume",
            prepare_delivery=RecordingFake(return_value={
                "status": "PREPARED", "outbound_message_id": "<x@y>", "gmail_draft_id": "draft-1",
            }),
            get_draft=RecordingFake(return_value=None),
            send_gmail_draft=RecordingFake(side_effect=ConnectionError("timeout")),
            find_sent_message_by_rfc_message_id=RecordingFake(return_value=None),
        )
        # First get_draft call (before send) must find the draft so we reach
        # send at all; only the SECOND call (inside except) reports it gone.
        first_get_draft_result = {"id": "draft-1", "message": {"id": "msg-1"}}
        calls_so_far = {"n": 0}
        def sequenced_get_draft(*args, **kwargs):
            calls_so_far["n"] += 1
            return first_get_draft_result if calls_so_far["n"] == 1 else None
        namespace["get_draft"] = sequenced_get_draft

        with self.assertRaises(RuntimeError) as raised:
            namespace["resume_autonomous_delivery"](
                service=None, connection=None, message=FakeMessage(), processing_result={},
            )
        self.assertIn("manual reconciliation", str(raised.exception))


if __name__ == "__main__":
    unittest.main()

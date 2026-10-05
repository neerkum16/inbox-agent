"""
PHASE 5C - DETERMINISTIC OUTBOUND SEND POLICY
==============================================

This module is deliberately independent of Gmail and the LLM. It is the
authorization boundary for autonomous outbound responses.
"""


def extract_draft_reply(processing_result):
    """Return the generated reply from a normal or identity-blocked result.

    Both shapes nest draft_reply under "draft" -- pipeline.process_message
    always returns {"classification": ..., "draft": {...}, "routing": ...},
    whether the draft came from generate_draft_response.draft_response or
    from pipeline.build_identity_failure_result. There is no code path where
    processing_result itself carries a top-level draft_reply, so a second
    fallback lookup at that level was dead code that could never fire --
    removed rather than kept as unreachable defensive code.
    """

    if not isinstance(processing_result, dict):
        return None

    draft_result = processing_result.get("draft") or {}
    draft_reply = draft_result.get("draft_reply")

    if not draft_reply or not str(draft_reply).strip():
        return None

    return str(draft_reply).strip()


def is_autonomous_send_candidate(processing_result):
    """
    Return True only when the deterministic pipeline explicitly authorizes send.

    Required conditions:
      1. routing tier is exactly autonomous;
      2. identity eligibility is exactly True;
      3. identity gate did not block the draft;
      4. a non-empty response exists.

    The LLM cannot grant or override this authorization.
    """

    if not isinstance(processing_result, dict):
        return False

    classification = processing_result.get("classification") or {}
    draft = processing_result.get("draft") or {}
    routing = processing_result.get("routing") or {}

    return (
        routing.get("tier") == "autonomous"
        and classification.get("identity_eligible") is True
        and draft.get("identity_gate_blocked") is not True
        and bool(extract_draft_reply(processing_result))
    )

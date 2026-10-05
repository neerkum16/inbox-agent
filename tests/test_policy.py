"""Unit tests for the Phase 5C deterministic autonomous-send gate."""

from agent.send_policy import extract_draft_reply, is_autonomous_send_candidate


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def assert_false(value, message):
    if value:
        raise AssertionError(message)


def main():
    base = {
        "classification": {"identity_eligible": True},
        "draft": {"draft_reply": "Approved reply."},
        "routing": {"tier": "autonomous"},
    }

    assert_true(
        is_autonomous_send_candidate(base),
        "normal autonomous result must be sendable",
    )

    blocked = {
        "classification": {"identity_eligible": False},
        "draft": {
            "draft_reply": "Identity failure reply.",
            "identity_gate_blocked": True,
        },
        "routing": None,
    }
    assert_false(
        is_autonomous_send_candidate(blocked),
        "identity-blocked result must never be sendable",
    )

    human_review = {
        "classification": {"identity_eligible": True},
        "draft": {"draft_reply": "Needs review."},
        "routing": {"tier": "human_review"},
    }
    assert_false(
        is_autonomous_send_candidate(human_review),
        "human-review result must not be sent autonomously",
    )

    no_identity = {
        "classification": {},
        "draft": {"draft_reply": "Reply."},
        "routing": {"tier": "autonomous"},
    }
    assert_false(
        is_autonomous_send_candidate(no_identity),
        "missing identity eligibility must fail closed",
    )

    empty_reply = {
        "classification": {"identity_eligible": True},
        "draft": {"draft_reply": "   "},
        "routing": {"tier": "autonomous"},
    }
    assert_false(
        is_autonomous_send_candidate(empty_reply),
        "empty response must fail closed",
    )

    conflicting = {
        "classification": {"identity_eligible": True},
        "draft": {
            "draft_reply": "Reply.",
            "identity_gate_blocked": True,
        },
        "routing": {"tier": "autonomous"},
    }
    assert_false(
        is_autonomous_send_candidate(conflicting),
        "identity_gate_blocked must override autonomous routing",
    )

    assert_true(
        extract_draft_reply({"draft": {"draft_reply": "  hello  "}}) == "hello",
        "draft reply extraction should trim whitespace",
    )
    # The previous assertion here checked extract_draft_reply({"draft_reply":
    # "fallback"}) -- a shape with draft_reply at the top level rather than
    # nested under "draft". That fallback lookup was dead code: every real
    # pipeline result (normal or identity-blocked) always nests draft_reply
    # under "draft", so this path never fired in practice and was removed
    # from send_policy.py. Removed here to match.

    print("PASS: autonomous eligible result")
    print("PASS: identity-blocked result")
    print("PASS: human-review result")
    print("PASS: missing identity eligibility")
    print("PASS: empty response")
    print("PASS: identity gate overrides routing")
    print("PASS: draft reply extraction")
    print("All Phase 5C send-policy tests passed.")


if __name__ == "__main__":
    main()

"""Unit tests for Gmail draft-send transport helpers using a fake Gmail service."""

from types import SimpleNamespace

from agent.gmail_send import (
    build_outbound_message_id,
    find_draft_by_rfc_message_id,
    find_sent_message_by_rfc_message_id,
    send_gmail_draft,
)
from agent.gmail_drafts import build_reply_message


class FakeExecute:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


class FakeDrafts:
    def __init__(self):
        self.send_calls = []
        self.list_queries = []
        self.drafts = [
            {"id": "draft-123", "message": {"id": "draft-msg-123"}}
        ]

    def list(self, **kwargs):
        self.list_queries.append(kwargs)
        return FakeExecute({"drafts": self.drafts})

    def send(self, **kwargs):
        self.send_calls.append(kwargs)
        return FakeExecute({"id": "sent-123", "threadId": "thread-1"})


class FakeMessages:
    def __init__(self):
        self.list_queries = []

    def list(self, **kwargs):
        self.list_queries.append(kwargs)
        return FakeExecute({"messages": [{"id": "sent-123"}]})


class FakeUsers:
    def __init__(self):
        self.drafts_api = FakeDrafts()
        self.messages_api = FakeMessages()

    def drafts(self):
        return self.drafts_api

    def messages(self):
        return self.messages_api


class FakeService:
    def __init__(self):
        self.users_api = FakeUsers()

    def users(self):
        return self.users_api


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(
            message + ": expected " + repr(expected) + ", got " + repr(actual)
        )


def main():
    first = build_outbound_message_id("gmail", "message-1")
    second = build_outbound_message_id("gmail", "message-1")
    other = build_outbound_message_id("gmail", "message-2")

    assert_equal(first, second, "outbound message ID must be deterministic")
    if first == other:
        raise AssertionError("different source messages must have different IDs")

    service = FakeService()

    draft = find_draft_by_rfc_message_id(service, "me", first)
    assert_equal(draft["id"], "draft-123", "draft lookup")
    assert_equal(
        service.users_api.drafts_api.list_queries[0]["q"],
        "rfc822msgid:" + first,
        "draft lookup query",
    )

    sent = find_sent_message_by_rfc_message_id(service, "me", first)
    assert_equal(sent["id"], "sent-123", "sent lookup")
    assert_equal(
        service.users_api.messages_api.list_queries[0]["q"],
        "in:sent rfc822msgid:" + first,
        "sent lookup query",
    )

    sent_resource = send_gmail_draft(service, "me", "draft-123")
    assert_equal(sent_resource["id"], "sent-123", "send response")
    assert_equal(
        service.users_api.drafts_api.send_calls[0],
        {"userId": "me", "body": {"id": "draft-123"}},
        "draft send call",
    )

    mime = build_reply_message(
        from_address="customer@examplebank.com",
        original_subject="Balance Enquiry",
        draft_reply="Your balance is £10.00.",
        rfc_message_id="<incoming@examplebank.com>",
        outbound_message_id=first,
    )

    assert_equal(mime["To"], "customer@examplebank.com", "reply recipient")
    assert_equal(mime["Subject"], "Re: Balance Enquiry", "reply subject")
    assert_equal(mime["Message-ID"], first, "outbound Message-ID")
    assert_equal(
        mime["In-Reply-To"],
        "<incoming@examplebank.com>",
        "reply threading header",
    )

    print("PASS: deterministic outbound Message-ID")
    print("PASS: draft lookup")
    print("PASS: sent-message lookup")
    print("PASS: drafts.send invocation")
    print("PASS: outbound MIME headers")
    print("All Gmail send unit tests passed.")


if __name__ == "__main__":
    main()

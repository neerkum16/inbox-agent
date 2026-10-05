"""
Phase 5A unit tests for Gmail draft construction.

These tests do not contact Gmail. They verify the MIME message and the exact
Gmail API operation requested by the draft module.
"""

import base64
import unittest

from agent.gmail_drafts import build_reply_message, create_gmail_draft


class FakeExecute:
    def __init__(self, response):
        self.response = response

    def execute(self):
        return self.response


class FakeDrafts:
    def __init__(self):
        self.calls = []

    def create(self, userId, body):
        self.calls.append((userId, body))
        return FakeExecute(
            {
                "id": "draft-123",
                "message": {"id": "message-456"},
            }
        )


class FakeUsers:
    def __init__(self, drafts):
        self._drafts = drafts

    def drafts(self):
        return self._drafts


class FakeService:
    def __init__(self):
        self.drafts_api = FakeDrafts()

    def users(self):
        return FakeUsers(self.drafts_api)


class FakeInboundMessage:
    from_address = "customer@example.com"
    subject = "Balance Enquiry"
    rfc_message_id = "<original@example.com>"
    source_thread_id = "thread-123"
    headers = {"References": "<older@example.com>"}


class TestGmailDrafts(unittest.TestCase):

    def test_reply_headers_and_body(self):
        message = build_reply_message(
            from_address="customer@example.com",
            original_subject="Balance Enquiry",
            draft_reply="Your requested response.",
            rfc_message_id="<original@example.com>",
            references="<older@example.com>",
        )

        self.assertEqual(message["To"], "customer@example.com")
        self.assertEqual(message["Subject"], "Re: Balance Enquiry")
        self.assertEqual(message["In-Reply-To"], "<original@example.com>")
        self.assertEqual(
            message["References"],
            "<older@example.com> <original@example.com>",
        )
        self.assertIn("Your requested response.", message.get_content())

    def test_existing_re_subject_is_not_doubled(self):
        message = build_reply_message(
            from_address="customer@example.com",
            original_subject="Re: Balance Enquiry",
            draft_reply="Response.",
        )

        self.assertEqual(message["Subject"], "Re: Balance Enquiry")

    def test_gmail_draft_api_call(self):
        service = FakeService()

        result = create_gmail_draft(
            service=service,
            user_id="me",
            message=FakeInboundMessage(),
            draft_reply="Your requested response.",
        )

        self.assertEqual(result["id"], "draft-123")
        self.assertEqual(len(service.drafts_api.calls), 1)

        user_id, body = service.drafts_api.calls[0]
        self.assertEqual(user_id, "me")
        self.assertEqual(body["message"]["threadId"], "thread-123")

        raw_message = base64.urlsafe_b64decode(
            body["message"]["raw"]
        ).decode("utf-8")

        self.assertIn("To: customer@example.com", raw_message)
        self.assertIn("Subject: Re: Balance Enquiry", raw_message)
        self.assertIn("In-Reply-To: <original@example.com>", raw_message)
        self.assertIn("Your requested response.", raw_message)

    def test_empty_reply_is_rejected(self):
        with self.assertRaises(ValueError):
            build_reply_message(
                from_address="customer@example.com",
                original_subject="Balance Enquiry",
                draft_reply="",
            )

    def test_missing_sender_is_rejected(self):
        with self.assertRaises(ValueError):
            build_reply_message(
                from_address=None,
                original_subject="Balance Enquiry",
                draft_reply="Response.",
            )


if __name__ == "__main__":
    unittest.main()

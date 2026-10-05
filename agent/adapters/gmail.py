"""
Gmail Adapter 

Purpose:
    Convert raw Gmail API messages into the application's InboundMessage
    contract.

This module only reads and normalizes Gmail messages. It does not:
    - call an LLM
    - query BankDB
    - generate replies
    - send email
    - modify Gmail messages
    - download attachments

Data flow:

    Gmail API
        |
        v
    Gmail adapter
        |
        v
    InboundMessage
        |
        v
    Pipeline 

Required packages:
    pip install beautifulsoup4 google-api-python-client
"""

# =============================================================================
# IMPORTS
# =============================================================================

# Python's standard Base64 library. Gmail body data is Base64URL encoded.
import base64

# Used to convert Gmail's millisecond timestamp into a Python datetime.
from datetime import datetime, timezone

# Python's standard email utilities. parseaddr() understands formats such as:
#     Neeraj Kumar <kneeraj16@gmail.com>
from email.utils import parseaddr

# BeautifulSoup parses HTML email and lets us turn it into readable text.
# Install it with: pip install beautifulsoup4
from bs4 import BeautifulSoup

# This is the common message contract.
from agent.contracts import InboundMessage


# =============================================================================
# 1. HEADER EXTRACTION
# =============================================================================

def extract_headers(payload):
    """
    Extract the headers needed by the application.

    Gmail stores headers as a list such as:
        {"name": "From", "value": "Neeraj <neeraj@example.com>"}

    Header names are case-insensitive, so we store them using lowercase
    names. Missing headers receive an empty string instead of causing
    a KeyError.
    """

    # Define the headers we currently care about.
    extracted_headers = {
        "from": "",
        "to": "",
        "cc": "",
        "subject": "",
        "date": "",
        "message-id": "",
    }

    # payload may not contain "headers", so .get() safely gives us [].
    header_list = payload.get("headers", [])

    # Examine every header returned by Gmail.
    for header in header_list:
        # Lowercase makes From, FROM, and from equivalent.
        header_name = header.get("name", "").lower()

        # Read the actual header value.
        header_value = header.get("value", "")

        # Only keep headers required by this adapter.
        if header_name in extracted_headers:
            extracted_headers[header_name] = header_value

    return extracted_headers


# =============================================================================
# 2. SENDER AND RECIPIENT PARSING
# =============================================================================

def parse_sender(from_header):
    """
    Extract only the sender's email address.

    Example:
        "Neeraj Kumar <kneeraj16@gmail.com>"
        becomes:
        "kneeraj16@gmail.com"

    parseaddr() is preferable to manually splitting on '<' and '>'.
    """

    # parseaddr() returns:
    #     (display_name, email_address)
    display_name, email_address = parseaddr(from_header)

    # We need the mailbox address for later identity lookup.
    return email_address.strip()


def parse_recipient_addresses(header_value):
    """
    Convert a To or Cc header into a list of email addresses.

    Example:
        "A <a@example.com>, B <b@example.com>"
    becomes:
        ["a@example.com", "b@example.com"]
    """

    if not header_value:
        return []

    # This handles the common comma-separated address format.
    address_parts = header_value.split(",")

    email_addresses = []

    for address_part in address_parts:
        display_name, email_address = parseaddr(address_part)

        if email_address:
            email_addresses.append(email_address.strip())

    return email_addresses


# =============================================================================
# 3. GMAIL BASE64URL DECODING
# =============================================================================

def decode_gmail_body(data):
    """
    Decode Gmail's URL-safe Base64 body data into UTF-8 text.

    Gmail can omit '=' padding from Base64URL data. We add the required
    padding before decoding.

    errors="replace" means a malformed UTF-8 byte will be replaced rather
    than crashing the entire email-ingestion process.
    """

    if not data:
        return ""

    try:
        # Base64 represents data in groups of four characters.
        # Add '=' characters when Gmail omitted padding.
        missing_padding = len(data) % 4

        if missing_padding:
            data = data + ("=" * (4 - missing_padding))

        # Gmail uses the URL-safe Base64 alphabet.
        decoded_bytes = base64.urlsafe_b64decode(data)

        # Convert bytes to normal Python text.
        return decoded_bytes.decode("utf-8", errors="replace")

    except Exception as error:
        # Give callers a clear application-level error.
        raise ValueError(
            "Unable to decode Gmail Base64URL body data."
        ) from error


# =============================================================================
# 4. HTML TO TEXT
# =============================================================================

def html_to_text(html):
    """
    Convert an HTML email body into readable plain text.

    The important rule is that HTML formatting tags such as <b> must
    not create unwanted line breaks.

    Example:

        <p>Hello <b>Neeraj</b>.</p>

    becomes:

        Hello Neeraj.
    """

    soup = BeautifulSoup(html, "html.parser")

    # Remove content that should never become part of the email text.
    for tag in soup.find_all(["script", "style", "head", "img"]):
        tag.decompose()

    # Preserve meaningful links.
    for link in soup.find_all("a"):
        link_text = link.get_text(" ", strip=True)
        href = link.get("href")

        if link_text and href:
            link.replace_with(
                link_text + " (" + href + ")"
            )
        elif href:
            link.replace_with(href)

    # Extract text using a space between HTML elements.
    #
    # This is important:
    #
    #     <b>Neeraj</b>.
    #
    # will be treated as:
    #
    #     Neeraj .
    #
    # rather than:
    #
    #     Neeraj
    #     .
    #
    # We clean the space before punctuation below.
    raw_text = soup.get_text(" ")

    # Normalize all whitespace.
    cleaned_text = " ".join(raw_text.split())

    # Remove spaces accidentally placed before punctuation.
    punctuation = [".", ",", "!", "?", ":", ";", "%"]

    for character in punctuation:
        cleaned_text = cleaned_text.replace(
            " " + character,
            character,
        )

    return cleaned_text


# =============================================================================
# 5. ATTACHMENT DETECTION
# =============================================================================

def is_attachment(part):
    """
    Determine whether a MIME part looks like an attachment.

    We detect attachments but deliberately do not download them.
    """

    # Gmail commonly supplies a filename for an attachment.
    filename = part.get("filename", "")

    if filename:
        return True

    # Gmail may instead provide an attachmentId.
    body = part.get("body", {})
    attachment_id = body.get("attachmentId")

    if attachment_id:
        return True

    return False


def find_attachments(payload):
    """
    Recursively find attachment metadata.

    Example result:
        [
            {
                "filename": "statement.pdf",
                "mime_type": "application/pdf"
            }
        ]

    The actual file contents are never downloaded.
    """

    attachments = []

    if is_attachment(payload):
        attachments.append(
            {
                "filename": payload.get("filename", ""),
                "mime_type": payload.get("mimeType", ""),
            }
        )

    # MIME messages can contain nested parts.
    for part in payload.get("parts", []):
        attachments.extend(find_attachments(part))

    return attachments


# =============================================================================
# 6. MIME BODY EXTRACTION
# =============================================================================

def extract_body(payload):
    """
    Extract readable text from a Gmail MIME payload.

    Conceptually:

        if payload is text/plain:
            decode and return it

        if payload is multipart:
            recursively inspect parts
            prefer text/plain
            otherwise use text/html

        return ""

    Why recursion?

    Email can have structures such as:

        multipart/mixed
            |
            +-- multipart/alternative
            |       |
            |       +-- text/plain
            |       +-- text/html
            |
            +-- application/pdf

    Therefore, we cannot assume the body is at one fixed JSON path.
    """

    mime_type = payload.get("mimeType", "").lower()

    # -------------------------------------------------------------------------
    # Case 1: Plain text
    # -------------------------------------------------------------------------

    if mime_type == "text/plain":
        body = payload.get("body", {})
        encoded_data = body.get("data", "")

        if encoded_data:
            return decode_gmail_body(encoded_data)

        return ""

    # -------------------------------------------------------------------------
    # Case 2: HTML
    # -------------------------------------------------------------------------

    if mime_type == "text/html":
        body = payload.get("body", {})
        encoded_data = body.get("data", "")

        if encoded_data:
            html = decode_gmail_body(encoded_data)
            return html_to_text(html)

        return ""

    # -------------------------------------------------------------------------
    # Case 3: Multipart
    # -------------------------------------------------------------------------

    parts = payload.get("parts", [])

    if not parts:
        return ""

    html_body = ""

    # First pass: inspect children in their original order.
    for part in parts:
        # Do not treat attachments as customer message body.
        if is_attachment(part):
            continue

        part_mime_type = part.get("mimeType", "").lower()

        # Plain text has highest priority.
        if part_mime_type == "text/plain":
            plain_text = extract_body(part)

            if plain_text:
                return plain_text

        # HTML is saved as a fallback.
        elif part_mime_type == "text/html":
            body = part.get("body", {})
            encoded_data = body.get("data", "")

            if encoded_data and not html_body:
                html_body = decode_gmail_body(encoded_data)

        # A multipart child may contain more multipart children.
        elif part.get("parts"):
            nested_body = extract_body(part)

            if nested_body:
                return nested_body

    # No plain-text version was found, so use HTML.
    if html_body:
        return html_to_text(html_body)

    return ""


# =============================================================================
# 7. GMAIL TIMESTAMP
# =============================================================================

def convert_internal_date(internal_date):
    """
    Convert Gmail's internalDate from milliseconds since Unix epoch
    into a timezone-aware Python datetime.
    """

    if not internal_date:
        return None

    try:
        milliseconds = int(internal_date)

        # Gmail uses milliseconds; datetime.fromtimestamp() uses seconds.
        seconds = milliseconds / 1000

        return datetime.fromtimestamp(seconds, tz=timezone.utc)

    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(
            "Gmail internalDate is not a valid millisecond timestamp."
        ) from error


# =============================================================================
# 8. NORMALIZE ONE GMAIL MESSAGE
# =============================================================================

def normalize_gmail_message(gmail_message):
    """
    Convert one raw Gmail API message into an InboundMessage.

    Important distinction:

        gmail_message["id"]
            = ID of this individual message

        gmail_message["threadId"]
            = ID of the conversation/thread

    These must never be treated as the same value.

    Returns:
        (InboundMessage, attachment_metadata, cc_addresses)
    """

    # -------------------------------------------------------------------------
    # Message and thread IDs
    # -------------------------------------------------------------------------

    source_message_id = gmail_message.get("id", "")
    source_thread_id = gmail_message.get("threadId")

    if not source_message_id:
        raise ValueError("Gmail message does not contain a message ID.")

    # We intentionally preserve threadId separately.
    # Multiple messages can have different message IDs but share one thread ID.

    # -------------------------------------------------------------------------
    # Payload and headers
    # -------------------------------------------------------------------------

    payload = gmail_message.get("payload", {})
    headers = extract_headers(payload)

    # -------------------------------------------------------------------------
    # Sender
    # -------------------------------------------------------------------------

    from_address = parse_sender(headers["from"])

    # -------------------------------------------------------------------------
    # Recipients
    # -------------------------------------------------------------------------

    to_addresses = parse_recipient_addresses(headers["to"])
    cc_addresses = parse_recipient_addresses(headers["cc"])

    # -------------------------------------------------------------------------
    # Body
    # -------------------------------------------------------------------------

    body_text = extract_body(payload)

    # -------------------------------------------------------------------------
    # Attachments
    # -------------------------------------------------------------------------

    attachment_metadata = find_attachments(payload)

    # -------------------------------------------------------------------------
    # Received timestamp
    # -------------------------------------------------------------------------

    received_at = convert_internal_date(
        gmail_message.get("internalDate")
    )

    # -------------------------------------------------------------------------
    # Build the common application contract
    # -------------------------------------------------------------------------

    inbound_message = InboundMessage(
        source="gmail",
        source_message_id=source_message_id,
        source_thread_id=source_thread_id,
        from_address=from_address,
        to_addresses=to_addresses,
        subject=headers["subject"],
        body_text=body_text,
        received_at=received_at,
        rfc_message_id=headers["message-id"],
        headers=headers,
    )

    return inbound_message, attachment_metadata, cc_addresses


# =============================================================================
# 9. GMAIL PAGINATION
# =============================================================================

def iter_gmail_messages(service, user_id="me", query=""):
    """
    Read Gmail messages page by page.

    Gmail's list API returns one page at a time.

        list()
          |
          v
        messages
          |
          v
        nextPageToken?
          |
          +-- yes --> request another page
          |
          +-- no ---> finished

    The function yields complete Gmail messages one at a time.

    A generator is used here because it naturally represents a stream
    of messages. The caller does not need to load every message into
    memory first.
    """

    next_page_token = None

    while True:

        # These are the parameters required by Gmail's list endpoint.
        request_parameters = {
            "userId": user_id,
        }

        # The caller controls the Gmail search query.
        # We do not hard-code "is:unread" inside the adapter.
        if query:
            request_parameters["q"] = query

        # For the first request there is no page token.
        # For later requests Gmail gives us one.
        if next_page_token:
            request_parameters["pageToken"] = next_page_token

        # Request one page from Gmail.
        response = (
            service.users()
            .messages()
            .list(**request_parameters)
            .execute()
        )

        # The list endpoint normally returns message IDs and thread IDs.
        messages = response.get("messages", [])

        for message in messages:
            message_id = message.get("id")

            if not message_id:
                continue

            # Fetch the full message because the list response does not
            # contain the complete MIME payload and headers.
            full_message = (
                service.users()
                .messages()
                .get(
                    userId=user_id,
                    id=message_id,
                    format="full",
                )
                .execute()
            )

            yield full_message

        # If this value exists, Gmail has another page.
        next_page_token = response.get("nextPageToken")

        # No token means the current page was the final page.
        if not next_page_token:
            break


# =============================================================================
# 10. PAGINATED, NORMALIZED GMAIL MESSAGES
# =============================================================================

def iter_normalized_gmail_messages(service, user_id="me", query=""):
    """
    Read Gmail messages and immediately normalize them.

    Data flow:

        Gmail list
            |
            v
        Gmail get
            |
            v
        normalize_gmail_message()
            |
            v
        InboundMessage
    """

    for gmail_message in iter_gmail_messages(
        service=service,
        user_id=user_id,
        query=query,
    ):
        inbound_message, attachments, cc_addresses = (
            normalize_gmail_message(gmail_message)
        )

        yield {
            "message": inbound_message,
            "attachments": attachments,
            "cc_addresses": cc_addresses,
        }


# =============================================================================
# 11. SIMPLE DISPLAY HELPER
# =============================================================================

def print_normalized_message(normalized_result):
    """
    Print a normalized message for manual testing.

    This function only prints information. It does not modify Gmail.
    """

    message = normalized_result["message"]
    attachments = normalized_result["attachments"]
    cc_addresses = normalized_result["cc_addresses"]

    print("=" * 70)
    print("SOURCE:", message.source)
    print("MESSAGE ID:", message.source_message_id)
    print("THREAD ID:", message.source_thread_id)
    print("FROM:", message.from_address)
    print("TO:", message.to_addresses)
    print("CC:", cc_addresses)
    print("SUBJECT:", message.subject)
    print("RECEIVED AT:", message.received_at)
    print("RFC MESSAGE-ID:", message.rfc_message_id)

    print("\nBODY:")
    print(message.body_text)

    print("\nATTACHMENTS:")

    if attachments:
        for attachment in attachments:
            print(
                "  -",
                attachment["filename"],
                "(" + attachment["mime_type"] + ")",
            )
    else:
        print("  None")

    print("=" * 70)


# =============================================================================
# AUTHENTICATION NOTE
# =============================================================================

# Authentication intentionally does not live here.
#
# Existing gmail_agent.py already handles OAuth authentication and
# creates the Gmail API service object.
#
# Keeping authentication separate means this adapter can be unit-tested
# with fake Gmail API responses without needing a real Gmail login.
#
# The intended relationship is:
#
#     gmail_agent.py
#          |
#          +--> authenticate
#          |
#          +--> create Gmail service
#          |
#          +--> iter_normalized_gmail_messages(...)
#                         |
#                         v
#                  InboundMessage
#
# Next will connect that InboundMessage to process_message().

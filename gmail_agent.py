"""
Gmail Banking Agent - Phase 5C Autonomous Sending

PURPOSE
-------
This program is the Gmail entry point for the banking inbox agent. Phase 5C adds deterministic autonomous sending while retaining draft-only handling for non-autonomous cases.

It connects the real Gmail inbox to the existing application pipeline:

    Gmail
      |
      v
    Gmail authentication
      |
      v
    Gmail adapter
      |
      v
    InboundMessage
      |
      v
    process_message()
      |
      +--> classify the email
      |
      +--> resolve customer from sender
      |
      +--> validate account/entity references
      |
      +--> retrieve live banking information
      |
      +--> retrieve relevant knowledge-base rules
      |
      +--> generate a draft response
      |
      +--> apply deterministic escalation rules
      |
      +--> write application audit information
      |
      v
    Print processing result

IMPORTANT
---------
Phase 5C can send only responses that the deterministic routing layer classifies as autonomous and that have passed the identity gate. Non-autonomous and identity-blocked responses remain drafts.

It does NOT:
    - modify the source inbound email
    - mark an email as read
    - archive an email
    - change Gmail labels
    - delete an email
    - download attachments

The Gmail OAuth scopes are gmail.readonly + gmail.compose. Gmail draft creation and drafts.send both use gmail.compose; no broader gmail.modify or mail.google.com scope is requested.

The business logic is deliberately NOT duplicated here. The existing
agent.pipeline.process_message() function owns the banking workflow.
This file is primarily responsible for:

    1. Gmail authentication
    2. creating the model/database/embedding dependencies
    3. reading and normalizing Gmail messages
    4. passing each InboundMessage into process_message()
    5. displaying the result

This separation is important because the same process_message() function
can later be used by fixture input and by other message sources.

-------------------------------------------------------------------------------

PROJECT LOCATION
----------------

Recommended structure:

    inbox-agent/
    |
    +-- gmail_agent.py
    |
    +-- config/
    |   +-- gmail/
    |       +-- credentials.json
    |       +-- token.json
    |
    +-- agent/
    |   +-- pipeline.py
    |   +-- bankdb.py
    |   +-- contracts.py
    |   +-- adapters/
    |       +-- gmail.py
    |
    +-- database/
    +-- knowledge_base/
    +-- tests/

credentials.json is the OAuth client configuration downloaded from Google.

token.json is created by this program after the first OAuth login.

Both files are secrets and should be excluded from Git.

-------------------------------------------------------------------------------

REQUIRED ENVIRONMENT VARIABLES
------------------------------

For Kimi:

    MOONSHOT_API_KEY

For PostgreSQL:

    PGPASSWORD

Example in PowerShell:

    $env:MOONSHOT_API_KEY = "your-kimi-key"
    $env:PGPASSWORD = "your-postgres-password"

The actual values are NOT stored in this source file.

-------------------------------------------------------------------------------

RUNNING THE PROGRAM
-------------------

Default: read unread Gmail messages

    python gmail_agent.py

Read a different Gmail query:

    python gmail_agent.py --query "is:unread"

For example:

    python gmail_agent.py --query "from:kneeraj16@gmail.com"

The Gmail query is passed to the Gmail adapter. The adapter performs
pagination and normalization.
"""

# =============================================================================
# SECTION 1 - IMPORTS
# =============================================================================

# argparse is part of Python's standard library.
#
# We use it to accept a Gmail search query from the command line.
import argparse

# os is part of Python's standard library.
#
# We use it to read environment variables such as MOONSHOT_API_KEY and
# PGPASSWORD without putting secrets into this source file.
import os

# Path gives us a clear and safe way to work with filesystem paths.
from pathlib import Path

# Anthropic's Python SDK is used for both Claude and Kimi.
#
# Kimi provides an Anthropic-compatible API endpoint, so the same SDK
# can be used with a different base URL.
import anthropic

# Google API client used to build the Gmail service object.
from googleapiclient.discovery import build

# Google OAuth credentials object.
#
# It represents an already-authorized Gmail identity and access token.
from google.oauth2.credentials import Credentials

# Google OAuth flow used when the application needs the user to authorize
# Gmail access for the first time.
from google_auth_oauthlib.flow import InstalledAppFlow

# Request is used when an expired OAuth access token can be refreshed.
from google.auth.transport.requests import Request

# SentenceTransformer converts a knowledge-base search query into an
# embedding vector. The vector is used to search the pgvector knowledge base.
from sentence_transformers import SentenceTransformer

# The Gmail adapter owns all Gmail-specific parsing and normalization.
#
# It converts a raw Gmail API message into the application's common
# InboundMessage contract.
from agent.adapters.gmail import iter_normalized_gmail_messages

# process_message() owns the banking workflow.
#
# It receives an InboundMessage and performs classification, validation,
# live-data retrieval, drafting, routing, and audit persistence.
from agent.pipeline import process_message
from agent.processing_state import claim_message, mark_completed, mark_failed
from agent.gmail_drafts import create_gmail_draft
from agent.delivery_state import (
    get_delivery_state,
    prepare_delivery,
    attach_draft,
    mark_sending,
    mark_sent,
    mark_unknown,
    mark_failed as mark_delivery_failed,
)
from agent.send_policy import extract_draft_reply, is_autonomous_send_candidate
from agent.gmail_send import (
    build_outbound_message_id,
    find_draft_by_rfc_message_id,
    get_draft,
    find_sent_message_by_rfc_message_id,
    send_gmail_draft,
)

# psycopg2 is the PostgreSQL driver used by the banking application.
#
# The current agent.bankdb.py contains shared bankdb lookup helpers, but it
# does NOT own the database connection function. The Phase 4C entry point
# therefore creates the connection here and passes it into process_message().
import psycopg2
import psycopg2.extras


# =============================================================================
# SECTION 2 - GMAIL SETTINGS
# =============================================================================

# Gmail permission required for draft creation.
#
# Gmail does not provide a narrower OAuth scope that permits creating drafts.
# The application uses drafts.create for review replies and drafts.send only after the deterministic Phase 5C send gate approves an autonomous response.
SCOPES = [
    # Read inbound Gmail messages.
    "https://www.googleapis.com/auth/gmail.readonly",
    # Create and send drafts. Gmail's drafts.send endpoint accepts gmail.compose.
    "https://www.googleapis.com/auth/gmail.compose",
]

# PROJECT_ROOT is the directory containing this script.
#
# If the script is:
#
#     C:\Users\Neeraj\Projects\inbox-agent\gmail_agent.py
#
# PROJECT_ROOT becomes:
#
#     C:\Users\Neeraj\Projects\inbox-agent
PROJECT_ROOT = Path(__file__).resolve().parent

# OAuth files are kept outside the Python source code.
GMAIL_CONFIG_DIRECTORY = PROJECT_ROOT / "config" / "gmail"

# Google OAuth client configuration.
CREDENTIALS_FILE = GMAIL_CONFIG_DIRECTORY / "credentials.json"

# Token generated after the user completes OAuth authorization.
TOKEN_FILE = GMAIL_CONFIG_DIRECTORY / "token.json"

# Gmail API uses the special user ID "me" to mean:
#
#     the Gmail account represented by the current OAuth credentials
#
# It is NOT a hard-coded email address.
GMAIL_USER_ID = "me"

# The normal query.
DEFAULT_GMAIL_QUERY = "is:unread"


# =============================================================================
# SECTION 3 - MODEL SETTINGS
# =============================================================================

# Change this value to switch between the two supported providers.
#
#     "kimi"  -> Moonshot's Anthropic-compatible endpoint
#     "claude" -> Anthropic's normal endpoint
MODEL_PROVIDER = "kimi"

# Kimi model currently used by the project.
KIMI_MODEL_NAME = "kimi-k2.6"

# Claude model currently used by the project.
CLAUDE_MODEL_NAME = "claude-sonnet-5"

# Moonshot's Anthropic-compatible endpoint.
KIMI_BASE_URL = "https://api.moonshot.ai/anthropic"

# The embedding model must match the model used when the knowledge-base
# rules were inserted into pgvector.
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# =============================================================================
# SECTION 4A - DATABASE SETTINGS
# =============================================================================

# These settings are the PostgreSQL connection settings used by this entry
# point to create the connection that is passed into process_message().
#
# PGPASSWORD remains an environment variable so the database password is
# never stored in this source file.
DATABASE_HOST = "localhost"
DATABASE_PORT = 5432
DATABASE_NAME = "bankdb"
DATABASE_USER = "postgres"


def connect_to_database():
    """
    Open a PostgreSQL connection to bankdb.

    The current agent.bankdb.py contains shared database lookup helpers and
    expects callers to provide an already-open connection. Therefore this
    Gmail entry point creates the connection and passes it into the common
    processing pipeline.

    RealDictCursor is used because the existing banking code expects database
    rows to behave like dictionaries with column names.
    """

    database_password = os.environ.get("PGPASSWORD")

    if not database_password:
        raise RuntimeError(
            "PGPASSWORD environment variable is not set."
        )

    connection = psycopg2.connect(
        host=DATABASE_HOST,
        port=DATABASE_PORT,
        dbname=DATABASE_NAME,
        user=DATABASE_USER,
        password=database_password,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )

    return connection



# =============================================================================
# SECTION 4 - CREATE THE MODEL CLIENT
# =============================================================================

def create_model_client():
    """
    Create the LLM client used by the classification and drafting stages.

    Why is this function here?

    The pipeline needs an LLM client, but it should not need to know how
    the application obtained that client.

    For Claude:
        Anthropic's normal endpoint is used.

    For Kimi:
        The Anthropic Python SDK is pointed at Moonshot's compatible endpoint.
    """

    if MODEL_PROVIDER == "kimi":
        api_key = os.environ.get("MOONSHOT_API_KEY")

        if not api_key:
            raise RuntimeError(
                "MOONSHOT_API_KEY environment variable is not set."
            )

        client = anthropic.Anthropic(
            api_key=api_key,
            base_url=KIMI_BASE_URL,
        )

        return client

    if MODEL_PROVIDER == "claude":
        api_key = os.environ.get("ANTHROPIC_API_KEY")

        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY environment variable is not set."
            )

        client = anthropic.Anthropic(
            api_key=api_key
        )

        return client

    raise ValueError(
        "Invalid MODEL_PROVIDER: "
        + MODEL_PROVIDER
        + ". Use 'kimi' or 'claude'."
    )


def get_model_name():
    """
    Return the model name corresponding to MODEL_PROVIDER.

    Keeping this in one small function prevents the rest of the program
    from repeatedly checking which provider is active.
    """

    if MODEL_PROVIDER == "kimi":
        return KIMI_MODEL_NAME

    if MODEL_PROVIDER == "claude":
        return CLAUDE_MODEL_NAME

    raise ValueError(
        "Invalid MODEL_PROVIDER: "
        + MODEL_PROVIDER
    )


# =============================================================================
# SECTION 5 - LOAD THE EMBEDDING MODEL
# =============================================================================

def load_embedding_model():
    """
    Load the SentenceTransformer used by the knowledge-base retrieval stage.

    Why does the Gmail entry point need this?

    The draft-generation stage may need to search the banking knowledge base.
    That search requires converting a text query into an embedding vector.

    The model must be the same model that was used when the knowledge base
    was originally embedded.
    """

    print("Loading knowledge-base embedding model...")

    embedding_model = SentenceTransformer(
        EMBEDDING_MODEL_NAME
    )

    print(
        "Embedding model loaded:",
        EMBEDDING_MODEL_NAME,
    )

    return embedding_model


# =============================================================================
# SECTION 6 - GMAIL FILE PATH HELPERS
# =============================================================================

def get_credentials_file():
    """
    Return the Google OAuth client configuration path.

    The default is:

        config/gmail/credentials.json

    An environment variable can override this location.
    """

    configured_path = os.environ.get(
        "GMAIL_CREDENTIALS_FILE"
    )

    if configured_path:
        return Path(configured_path)

    return CREDENTIALS_FILE


def get_token_file():
    """
    Return the Google OAuth token path.

    The default is:

        config/gmail/token.json

    An environment variable can override this location.
    """

    configured_path = os.environ.get(
        "GMAIL_TOKEN_FILE"
    )

    if configured_path:
        return Path(configured_path)

    return TOKEN_FILE


# =============================================================================
# SECTION 7 - GMAIL AUTHENTICATION
# =============================================================================

def authenticate_with_gmail():
    """
    Authenticate with Gmail and return a Gmail API service object.

    There are three normal cases.

    CASE 1 - No token exists
    ------------------------

        credentials.json
              |
              v
        Google OAuth login
              |
              v
           token.json
              |
              v
        Gmail service


    CASE 2 - Token exists and is still valid
    -----------------------------------------

        token.json
              |
              v
        Gmail service


    CASE 3 - Access token expired but refresh token exists
    -------------------------------------------------------

        token.json
              |
              v
        refresh access token
              |
              v
        Gmail service

    The OAuth token represents the Gmail account that the user authorized.
    The program does not hard-code a personal email address.
    """

    credentials_file = get_credentials_file()
    token_file = get_token_file()

    print("Authenticating with Gmail...")

    # The credentials file is required only when starting a new OAuth flow.
    if not credentials_file.exists():
        raise FileNotFoundError(
            "Google OAuth credentials file was not found:\n"
            + str(credentials_file)
            + "\n\n"
            "Place credentials.json in config/gmail/ "
            "or set GMAIL_CREDENTIALS_FILE."
        )

    credentials = None

    # If token.json exists, try to use the saved authorization first.
    if token_file.exists():
        print("Loading existing Gmail OAuth token...")

        try:
            credentials = Credentials.from_authorized_user_file(
                str(token_file),
                SCOPES,
            )
        except Exception:
            # A corrupted or incompatible token should not be silently used.
            # Setting credentials to None causes a clean new OAuth flow below.
            print("Saved Gmail OAuth token could not be loaded.")
            credentials = None

    # The token must contain every scope required by Phase 5C. A Phase 5A
    # compose-only token cannot read the inbox, while a Phase 4E readonly-only
    # token cannot create/send drafts. Force a new OAuth authorization when the
    # saved token is missing either scope.
    if credentials is not None:
        granted_scopes = set(credentials.scopes or [])
        required_scopes = set(SCOPES)

        if not required_scopes.issubset(granted_scopes):
            print("Saved Gmail OAuth token does not include all Phase 5C scopes.")
            print("Starting a new OAuth authorization for Gmail read + compose access...")
            credentials = None

    # If credentials exist but the access token is expired, try refreshing it.
    if credentials is not None and credentials.expired:
        if credentials.refresh_token:
            print("Gmail OAuth token has expired. Refreshing it...")

            try:
                credentials.refresh(Request())
            except Exception as error:
                print(
                    "The saved Gmail OAuth token could not be refreshed."
                )
                print("Reason:", error)
                credentials = None
        else:
            print(
                "The saved Gmail OAuth token has no refresh token."
            )
            credentials = None

    # If there is no usable credential, start a new browser-based OAuth flow.
    if credentials is None or not credentials.valid:
        print("No usable Gmail OAuth token found.")
        print("Starting Google OAuth authorization...")

        flow = InstalledAppFlow.from_client_secrets_file(
            str(credentials_file),
            SCOPES,
        )

        credentials = flow.run_local_server(
            port=0,
            prompt="consent",
        )

        # Make sure the directory exists before saving token.json.
        token_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with open(
            token_file,
            "w",
            encoding="utf-8",
        ) as token_handle:
            token_handle.write(
                credentials.to_json()
            )

        print("Gmail OAuth token saved to:")
        print("  " + str(token_file))

    # Build the Gmail API service object.
    #
    # The service object is our Python interface to Gmail's REST API.
    service = build(
        "gmail",
        "v1",
        credentials=credentials,
    )

    print("Authentication successful.")

    return service


# =============================================================================
# SECTION 8 - IDENTIFY THE AUTHENTICATED GMAIL ACCOUNT
# =============================================================================

def get_authenticated_email(service):
    """
    Ask Gmail which mailbox is represented by the current OAuth credentials.

    This is useful because:

        userId="me"

    does not tell us the actual email address.

    Gmail provides the mailbox address through its profile endpoint.
    """

    profile = (
        service.users()
        .getProfile(userId=GMAIL_USER_ID)
        .execute()
    )

    email_address = profile.get("emailAddress")

    if not email_address:
        return "unknown"

    return email_address


# =============================================================================
# SECTION 9 - PROCESSING / DRAFT HELPERS
# =============================================================================

def create_draft_from_processing_result(
    service,
    normalized_result,
    processing_result,
    outbound_message_id=None,
):
    """
    Convert the pipeline's draft response into a Gmail draft.

    The pipeline owns the response content. This function performs only the
    Gmail-specific draft operation and never sends or modifies the source
    message.

    ``outbound_message_id`` is supplied only for autonomous Phase 5C delivery.
    It provides the deterministic RFC Message-ID used for send/retry
    correlation.
    """

    if not isinstance(processing_result, dict):
        raise ValueError("Processing result must be a dictionary.")

    draft_result = processing_result.get("draft") or {}
    draft_reply = draft_result.get("draft_reply")

    # Identity-gate failures use a deterministic top-level draft reply.
    if not draft_reply:
        draft_reply = processing_result.get("draft_reply")

    if not draft_reply or not str(draft_reply).strip():
        raise RuntimeError(
            "Cannot create Gmail draft because the processing result does not "
            "contain a draft reply."
        )

    message = normalized_result["message"]

    print("")
    print("Creating Gmail draft...")

    draft_resource = create_gmail_draft(
        service=service,
        user_id=GMAIL_USER_ID,
        message=message,
        draft_reply=draft_reply,
        outbound_message_id=outbound_message_id,
    )

    print("Gmail draft created.")
    print("Gmail draft ID:", draft_resource.get("id"))

    return draft_resource


def print_processing_result(normalized_result, processing_result):
    """Print a concise, useful view of the processing outcome."""

    message = normalized_result["message"]
    attachments = normalized_result.get("attachments") or []

    # A skipped message may contain the previously persisted result under
    # ``stored_processing_result``. Display that result rather than only the
    # wrapper returned by claim_message().
    display_result = processing_result
    if isinstance(processing_result, dict):
        stored_result = processing_result.get("stored_processing_result")
        if stored_result is not None:
            display_result = stored_result

    print("")
    print("=" * 70)
    print("MESSAGE PROCESSING RESULT")
    print("=" * 70)
    print("SOURCE:", message.source)
    print("MESSAGE ID:", message.source_message_id)
    print("THREAD ID:", message.source_thread_id)
    print("FROM:", message.from_address)
    print("TO:", message.to_addresses)
    print("SUBJECT:", message.subject)
    print("RECEIVED AT:", message.received_at)

    print("ATTACHMENTS:")
    if attachments:
        for attachment in attachments:
            print(
                "  -",
                attachment.get("filename", "unknown"),
                "(" + attachment.get("mime_type", "unknown") + ")",
            )
    else:
        print("  None")

    print("")
    print("PIPELINE RESULT:")

    if display_result is None:
        print("  No processing result was returned.")
    elif isinstance(display_result, dict):
        important_keys = [
            "message_id",
            "resolved_customer_number",
            "extracted_category",
            "extracted_priority",
            "extracted_entities",
            "validation_result",
            "identity_status",
            "identity_gate_blocked",
            "live_facts",
            "draft_reply",
            "cited_rule_ids",
            "tier",
            "escalation_reason",
            "audit_log_id",
            "gmail_draft_id",
            "gmail_draft_message_id",
            "gmail_sent_message_id",
            "delivery_status",
            "processing_status",
            "processing_error",
            "error",
        ]

        printed_any_key = False
        for key in important_keys:
            if key in display_result:
                print("  " + key + ":", display_result[key])
                printed_any_key = True

        if not printed_any_key:
            print("  " + str(display_result))
    else:
        print("  " + str(display_result))

    # Always expose the outer processing status when this was a skipped message.
    if isinstance(processing_result, dict) and processing_result.get("processing_status") == "SKIPPED":
        print("")
        print("PROCESSING STATUS: SKIPPED")
        print("SKIP REASON:", processing_result.get("processing_skip_reason"))
        print("ORIGINAL STATUS:", processing_result.get("original_processing_status"))

    print("=" * 70)



def _processing_error(processing_result):
    """Return a short error description if the pipeline result contains one, otherwise None."""

    if not isinstance(processing_result, dict):
        return "pipeline returned a non-dictionary result"

    classification_result = processing_result.get("classification") or {}
    draft_result = processing_result.get("draft") or {}
    routing_result = processing_result.get("routing") or {}

    if "error" in classification_result:
        return "classification: " + str(classification_result["error"])

    if "error" in draft_result:
        return "draft: " + str(draft_result["error"])

    if "error" in routing_result:
        return "routing: " + str(routing_result["error"])

    return None


def _mark_processing_failed(connection, message, processing_result, error):
    """Persist a FAILED processing_state row and return a safe result dict."""

    if not isinstance(processing_result, dict):
        processing_result = {}

    mark_failed(
        connection,
        message.source,
        message.source_message_id,
        error,
    )
    processing_result["processing_status"] = "FAILED"
    processing_result["processing_error"] = str(error)
    return processing_result


def _mark_processing_completed(connection, message, processing_result):
    """Persist a COMPLETED processing_state row and return the result dict."""

    mark_completed(
        connection,
        message.source,
        message.source_message_id,
        processing_result,
    )
    processing_result["processing_status"] = "COMPLETED"
    return processing_result

def resume_autonomous_delivery(
    service,
    connection,
    message,
    processing_result,
):
    """
    Create/reuse one durable draft and send it exactly through that draft.

    A pre-existing delivery record is always resumed before a new draft is
    created. After an ambiguous send exception, Sent is checked first. If the
    original draft still exists, it can safely be retried. If both the Sent
    message and draft are absent, the outcome is deliberately left UNKNOWN and
    no replacement message is created.
    """

    outbound_message_id = build_outbound_message_id(
        message.source,
        message.source_message_id,
    )

    state = prepare_delivery(
        connection=connection,
        source=message.source,
        source_message_id=message.source_message_id,
        source_thread_id=message.source_thread_id,
        outbound_message_id=outbound_message_id,
        processing_result=processing_result,
    )

    processing_result["delivery"] = state

    # If an earlier attempt already confirmed the send, never call Gmail send
    # again. This also repairs message_processing after a crash between Gmail
    # success and mark_completed().
    if state["status"] == "SENT":
        print("Delivery state is already SENT; no Gmail send will be repeated.")
        return _mark_processing_completed(connection, message, processing_result)

    # First, resolve an ambiguous state against Sent. This check happens before
    # touching the draft because a successful send deletes the draft.
    sent_message = find_sent_message_by_rfc_message_id(
        service,
        GMAIL_USER_ID,
        state["outbound_message_id"],
    )

    if sent_message is not None:
        mark_sent(
            connection,
            message.source,
            message.source_message_id,
            sent_message.get("id"),
        )
        processing_result["gmail_sent_message_id"] = sent_message.get("id")
        processing_result["delivery_status"] = "SENT"
        return _mark_processing_completed(connection, message, processing_result)

    draft_resource = None

    # Reuse the persisted draft if one exists.
    if state.get("gmail_draft_id"):
        draft_resource = get_draft(
            service,
            GMAIL_USER_ID,
            state["gmail_draft_id"],
        )

    # If the draft ID was not persisted because of a crash immediately after
    # draft creation, locate the draft by its deterministic RFC Message-ID.
    if draft_resource is None and state["status"] == "PREPARED":
        draft_resource = find_draft_by_rfc_message_id(
            service,
            GMAIL_USER_ID,
            state["outbound_message_id"],
        )

        if draft_resource is not None:
            attach_draft(
                connection,
                message.source,
                message.source_message_id,
                draft_resource.get("id"),
                (draft_resource.get("message") or {}).get("id"),
            )
            state = get_delivery_state(
                connection,
                message.source,
                message.source_message_id,
            )

    # A PREPARED record may legitimately have no draft yet. Create exactly one.
    if draft_resource is None and state["status"] == "PREPARED":
        draft_resource = create_draft_from_processing_result(
            service=service,
            normalized_result={"message": message},
            processing_result=processing_result,
            outbound_message_id=state["outbound_message_id"],
        )

        if draft_resource is None:
            raise RuntimeError("Autonomous response did not contain a sendable draft.")

        attach_draft(
            connection,
            message.source,
            message.source_message_id,
            draft_resource.get("id"),
            (draft_resource.get("message") or {}).get("id"),
        )

        state = get_delivery_state(
            connection,
            message.source,
            message.source_message_id,
        )

    # If the draft is gone but the message is not found in Sent, never invent a
    # replacement. This is the critical duplicate-send protection.
    if draft_resource is None:
        mark_unknown(
            connection,
            message.source,
            message.source_message_id,
            "Neither the existing Gmail draft nor its sent message could be found; "
            "manual delivery reconciliation is required.",
        )
        raise RuntimeError(
            "Autonomous delivery outcome is UNKNOWN: existing draft is absent "
            "and no sent message was found. No replacement email was created."
        )

    processing_result["gmail_draft_id"] = draft_resource.get("id")
    processing_result["gmail_draft_message_id"] = (
        (draft_resource.get("message") or {}).get("id")
    )

    mark_sending(
        connection,
        message.source,
        message.source_message_id,
    )

    try:
        print("")
        print("AUTONOMOUS SEND GATE: APPROVED")
        print("Routing tier: autonomous")
        print("Identity eligible: True")
        print("Sending Gmail draft:", draft_resource.get("id"))

        sent_resource = send_gmail_draft(
            service=service,
            user_id=GMAIL_USER_ID,
            draft_id=draft_resource.get("id"),
        )

        sent_message_id = sent_resource.get("id")

        mark_sent(
            connection,
            message.source,
            message.source_message_id,
            sent_message_id,
        )

        processing_result["gmail_sent_message_id"] = sent_message_id
        processing_result["delivery_status"] = "SENT"

        print("Gmail autonomous send confirmed.")
        print("Gmail sent message ID:", sent_message_id)

        return _mark_processing_completed(connection, message, processing_result)

    except Exception as send_error:
        # A transport exception after the API call may mean Gmail actually sent
        # the message. Check Sent before deciding that the operation failed.
        confirmed_sent = find_sent_message_by_rfc_message_id(
            service,
            GMAIL_USER_ID,
            state["outbound_message_id"],
        )

        if confirmed_sent is not None:
            mark_sent(
                connection,
                message.source,
                message.source_message_id,
                confirmed_sent.get("id"),
            )
            processing_result["gmail_sent_message_id"] = confirmed_sent.get("id")
            processing_result["delivery_status"] = "SENT"
            print("Send raised an exception, but Sent confirms delivery.")
            return _mark_processing_completed(connection, message, processing_result)

        existing_draft = get_draft(
            service,
            GMAIL_USER_ID,
            draft_resource.get("id"),
        )

        mark_unknown(
            connection,
            message.source,
            message.source_message_id,
            send_error,
        )
        processing_result["delivery_status"] = "UNKNOWN"

        if existing_draft is not None:
            raise RuntimeError(
                "Gmail send failed or returned an ambiguous result. The original "
                "draft still exists, so no replacement was created; retry can "
                "resume the same draft. Original error: " + str(send_error)
            )

        raise RuntimeError(
            "Gmail send outcome is ambiguous and the original draft is gone. "
            "No replacement email was created; manual reconciliation is required. "
            "Original error: " + str(send_error)
        )

def process_one_gmail_message(
    normalized_result,
    client,
    connection,
    embedding_model,
    service,
):
    """
    Process one Gmail message and apply the Phase 5C outbound policy.

    Idempotency is checked before any LLM work. Autonomous deliveries have a
    second durable state machine so a restart at the Gmail send boundary can
    resume the existing draft rather than generate a duplicate response.
    """

    message = normalized_result["message"]

    print("")
    print("=" * 70)
    print("PROCESSING MESSAGE")
    print("=" * 70)
    print("Message ID:", message.source_message_id)
    print("Thread ID:", message.source_thread_id)
    print("From:", message.from_address)
    print("Subject:", message.subject)

    claim_result = claim_message(
        connection=connection,
        source=message.source,
        source_message_id=message.source_message_id,
        source_thread_id=message.source_thread_id,
    )

    if not claim_result["claimed"]:
        print("")
        print("IDEMPOTENCY CHECK: MESSAGE SKIPPED")
        print("Processing status:", claim_result["status"])
        print("Reason:", claim_result["reason"])

        stored_result = claim_result.get("processing_result")
        if stored_result is not None:
            return {
                "processing_status": "SKIPPED",
                "processing_skip_reason": claim_result["reason"],
                "original_processing_status": claim_result["status"],
                "stored_processing_result": stored_result,
            }

        return {
            "processing_status": "SKIPPED",
            "processing_skip_reason": claim_result["reason"],
            "original_processing_status": claim_result["status"],
        }

    print("")
    print("IDEMPOTENCY CHECK: MESSAGE CLAIMED")
    print("Claim reason:", claim_result["reason"])

    try:
        # If a previous run crossed the autonomous delivery boundary, resume
        # that exact delivery before invoking the LLM again.
        delivery_state = get_delivery_state(
            connection,
            message.source,
            message.source_message_id,
        )

        if delivery_state is not None:
            print("Existing delivery state:", delivery_state["status"])

            if delivery_state["status"] == "SENT":
                processing_result = delivery_state.get("processing_result") or {}
                processing_result["delivery_status"] = "SENT"
                processing_result["gmail_sent_message_id"] = delivery_state.get(
                    "gmail_sent_message_id"
                )
                return _mark_processing_completed(
                    connection,
                    message,
                    processing_result,
                )

            processing_result = delivery_state.get("processing_result") or {}

            if processing_result and delivery_state["status"] in {
                "PREPARED",
                "SENDING",
                "UNKNOWN",
            }:
                if not is_autonomous_send_candidate(processing_result):
                    mark_delivery_failed(
                        connection,
                        message.source,
                        message.source_message_id,
                        "Persisted delivery state is not eligible for autonomous sending.",
                    )
                    raise RuntimeError(
                        "Persisted autonomous delivery record failed the send gate."
                    )

                print("Resuming durable autonomous delivery; LLM pipeline will not rerun.")
                return resume_autonomous_delivery(
                    service=service,
                    connection=connection,
                    message=message,
                    processing_result=processing_result,
                )

        print("")
        print("Running banking pipeline...")

        processing_result = process_message(
            message,
            client,
            connection,
            embedding_model,
        )

        processing_error = _processing_error(processing_result)

        if processing_error is not None:
            return _mark_processing_failed(
                connection,
                message,
                processing_result,
                processing_error,
            )

        # Only the deterministic routing layer can authorize autonomous send.
        # Identity failures have routing=None and therefore cannot reach this
        # branch even if an LLM happened to produce a plausible reply.
        if is_autonomous_send_candidate(processing_result):
            print("")
            print("Routing decision: AUTONOMOUS")
            return resume_autonomous_delivery(
                service=service,
                connection=connection,
                message=message,
                processing_result=processing_result,
            )

        # Non-autonomous and identity-blocked responses remain drafts. This is
        # the Phase 5B-style human review path retained inside Phase 5C.
        print("")
        print("Routing decision: HUMAN REVIEW / BLOCKED")

        draft_resource = create_draft_from_processing_result(
            service=service,
            normalized_result=normalized_result,
            processing_result=processing_result,
        )

        if draft_resource is not None:
            processing_result["gmail_draft_id"] = draft_resource.get("id")
            processing_result["gmail_draft_message_id"] = (
                (draft_resource.get("message") or {}).get("id")
            )

        return _mark_processing_completed(
            connection,
            message,
            processing_result,
        )

    except Exception as error:
        # If the delivery layer already recorded SENT, do not overwrite it with
        # a FAILED inbound-processing state.
        delivery_state = get_delivery_state(
            connection,
            message.source,
            message.source_message_id,
        )

        if delivery_state is not None and delivery_state["status"] == "SENT":
            processing_result = delivery_state.get("processing_result") or {}
            processing_result["delivery_status"] = "SENT"
            processing_result["gmail_sent_message_id"] = delivery_state.get(
                "gmail_sent_message_id"
            )
            return _mark_processing_completed(
                connection,
                message,
                processing_result,
            )

        # Do not call delivery_state.mark_failed here for UNKNOWN/PREPARED
        # records; those states are deliberately retryable. message_processing
        # is marked FAILED so the next Gmail poll can reclaim the message and
        # resume the same delivery state without creating a new outbound draft.
        mark_failed(
            connection,
            message.source,
            message.source_message_id,
            error,
        )
        raise


# =============================================================================
# SECTION 11 - COMMAND-LINE ARGUMENTS
# =============================================================================

def parse_arguments():
    """
    Read command-line options.

    The only application-specific option currently needed is the Gmail query.

    Examples:

        python gmail_agent.py

        python gmail_agent.py --query "is:unread"

        python gmail_agent.py --query "from:someone@example.com"
    """

    parser = argparse.ArgumentParser(
        description=(
            "Read Gmail messages and process them through the banking support pipeline "
            "with deterministic autonomous-send controls."
        )
    )

    parser.add_argument(
        "--query",
        default=DEFAULT_GMAIL_QUERY,
        help=(
            "Gmail search query. "
            "Default: is:unread"
        ),
    )

    return parser.parse_args()


# =============================================================================
# SECTION 12 - MAIN PROGRAM
# =============================================================================

def main():
    """
    Run the complete Phase 5C workflow.

    High-level flow:

        1. Parse Gmail query
        2. Authenticate with Gmail
        3. Identify authenticated mailbox
        4. Create LLM client
        5. Load embedding model
        6. Connect to bankdb
        7. Read and normalize Gmail messages
        8. Process each message through process_message()
        9. Create a draft or send an autonomous response
        10. Persist processing/delivery state
        11. Print results
        12. Close the database connection

    The source inbound Gmail message is never modified. Autonomous replies are
    sent only through the deterministic send gate.
    """

    arguments = parse_arguments()

    service = None
    connection = None

    try:
        # ---------------------------------------------------------------------
        # STEP 1 - AUTHENTICATE WITH GMAIL
        # ---------------------------------------------------------------------

        service = authenticate_with_gmail()

        authenticated_email = get_authenticated_email(
            service
        )

        print(
            "Authenticated Gmail account:",
            authenticated_email,
        )

        print(
            "Gmail query:",
            arguments.query,
        )

        # ---------------------------------------------------------------------
        # STEP 2 - CREATE THE LLM CLIENT
        # ---------------------------------------------------------------------

        print("")
        print("Creating model client...")

        client = create_model_client()

        print(
            "Model provider:",
            MODEL_PROVIDER,
        )
        print(
            "Model:",
            get_model_name(),
        )

        # ---------------------------------------------------------------------
        # STEP 3 - LOAD THE EMBEDDING MODEL
        # ---------------------------------------------------------------------

        embedding_model = load_embedding_model()

        # ---------------------------------------------------------------------
        # STEP 4 - CONNECT TO BANKDB
        # ---------------------------------------------------------------------

        print("")
        print("Connecting to bankdb...")

        connection = connect_to_database()

        print("Database connection successful.")

        # ---------------------------------------------------------------------
        # STEP 5 - READ, NORMALIZE, AND PROCESS GMAIL
        # ---------------------------------------------------------------------

        print("")
        print("Reading Gmail messages...")
        print("")

        messages_read = 0
        messages_processed = 0
        messages_failed = 0
        messages_skipped = 0

        # iter_normalized_gmail_messages() handles:
        #
        #     Gmail list
        #       -> Gmail get
        #       -> MIME parsing
        #       -> header parsing
        #       -> HTML conversion
        #       -> InboundMessage
        #
        # The adapter also handles Gmail pagination.
        for normalized_result in iter_normalized_gmail_messages(
            service=service,
            user_id=GMAIL_USER_ID,
            query=arguments.query,
        ):
            messages_read += 1

            try:
                processing_result = process_one_gmail_message(
                    normalized_result,
                    client,
                    connection,
                    embedding_model,
                    service,
                )

                processing_status = (
                    processing_result.get("processing_status")
                    if isinstance(processing_result, dict)
                    else None
                )

                if processing_status == "SKIPPED":
                    messages_skipped += 1
                elif processing_status == "FAILED":
                    messages_failed += 1
                else:
                    messages_processed += 1

                print_processing_result(
                    normalized_result,
                    processing_result,
                )

            except Exception as error:
                # One bad message should be visible rather than silently
                # disappearing. We continue to the next Gmail message.
                messages_failed += 1

                message = normalized_result["message"]

                print("")
                print("=" * 70)
                print("MESSAGE PROCESSING FAILED")
                print("=" * 70)
                print("Message ID:", message.source_message_id)
                print("Thread ID:", message.source_thread_id)
                print("Error:", error)
                print("=" * 70)

        # ---------------------------------------------------------------------
        # STEP 6 - FINAL SUMMARY
        # ---------------------------------------------------------------------

        print("")
        print("=" * 70)
        print("PHASE 5C SUMMARY")
        print("=" * 70)
        print("Messages read:", messages_read)
        print("Messages processed:", messages_processed)
        print("Messages skipped:", messages_skipped)
        print("Messages failed:", messages_failed)
        print("")
        print("Gmail source messages were READ ONLY.")
        print("Autonomous responses were sent only when the deterministic send gate approved them.")
        print("Non-autonomous and identity-blocked responses remain Gmail drafts for review.")
        print("=" * 70)

    except Exception as error:
        print("")
        print("=" * 70)
        print("GMAIL BANKING AGENT FAILED")
        print("=" * 70)
        print("Error:", error)
        print("=" * 70)

        # Return a non-zero status so PowerShell, CI/CD, or another caller
        # can detect that the program did not complete successfully.
        raise SystemExit(1)

    finally:
        # The database connection is an external resource.
        #
        # Closing it in finally means it is closed even if an exception
        # occurs while processing a message.
        if connection is not None:
            connection.close()
            print("")
            print("Database connection closed.")

        print("Program complete.")


# =============================================================================
# SECTION 13 - PROGRAM ENTRY POINT
# =============================================================================

# This condition is true only when Python runs this file directly:
#
#     python gmail_agent.py
#
# It is false when another Python file imports functions from this file.
#
# That makes the program reusable and also makes it easier to test.
if __name__ == "__main__":
    main()

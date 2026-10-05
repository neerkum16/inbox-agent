"""
GENERATE DRAFTS
=================

WHAT THIS PROGRAM DOES
-------------------------
Phase 1 (classify_and_extract.py) told us WHAT each message is about —
category, priority, which entities it mentions, whether those
entities are real. This program takes that output and actually
drafts a reply — but it does NOT send anything, and it does NOT
decide who gets a human reviewer and who doesn't. Both of those are
later phases. This program's only job is: given everything we now
know about a message, write the best possible draft reply, and show
exactly what that draft is based on.

TWO DIFFERENT KINDS OF "GROUNDING", AND WHY BOTH MATTER
------------------------------------------------------------
It would be a mistake to treat every question as something to look up
in the knowledge base. A knowledge base built from COBOL business
rules can tell you WHY a transaction gets declined in general — but
it cannot tell you a specific customer's CURRENT balance. That's a
fact, not a policy, and it lives in bankdb itself, not in the rule
library. So this program grounds a draft in up to two different
places, depending on the category:

  LIVE DATA — read directly from bankdb. Used for balance inquiries
  (the real number), and to find the REAL reason behind an account's
  status or a declined transaction (rather than trusting whatever the
  customer's email guessed).

  THE KNOWLEDGE BASE — searched by meaning, using the same embedding
  model used to build it. Used to explain WHY a real reason code means
  what it means, in the bank's own terms — not invented by the model.

Some categories (a fraud report, a request to open a new account)
need neither: there's no fact to look up yet, and no policy to
explain, so those get a short, standard acknowledgement instead.

WHY THE RETRIEVAL QUERY ISN'T JUST THE CUSTOMER'S OWN WORDS
------------------------------------------------------------------
A customer might write "why is my account acting weird?" — vague,
unhelpful to search with. But by the time we reach this program, we
often already KNOW the real reason (e.g. FRAUD_SUSPECTED) from the
live data lookup. Searching the knowledge base using that real reason
directly, instead of the customer's vague wording, finds a far more
relevant rule. This program builds its search query from what it has
already confirmed, not from guessing at the customer's phrasing.
"""

# ---------------------------------------------------------------------------
# SECTION 1: IMPORTS
# ---------------------------------------------------------------------------

import json
import os
import time
from pathlib import Path

import anthropic
import psycopg2
import psycopg2.extras
from sentence_transformers import SentenceTransformer
# Same embedding model library used in load_rules_into_vector_store.py.
# We need it again here because searching "by meaning" means turning
# OUR search query into the same kind of number-list the stored rules
# already are — using a different model would produce numbers that
# aren't comparable to the ones already stored.


# ---------------------------------------------------------------------------
# SECTION 2: SETTINGS
# ---------------------------------------------------------------------------

CLASSIFICATION_RESULTS_FILE = Path("output/classification_results.json")
# Phase 1's output — this program's input.

OUTPUT_FILE = Path("output/draft_review_queue.json")

DATABASE_HOST = "localhost"
DATABASE_PORT = 5432
DATABASE_NAME = "bankdb"
DATABASE_USER = "postgres"
DATABASE_PASSWORD = os.environ["PGPASSWORD"]

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
# Must match load_rules_into_vector_store.py exactly — the numbers
# stored in rule_knowledge_base were produced by this exact model, so
# our search query has to come from the same one.

RULES_TO_RETRIEVE = 3
# How many knowledge base rules to pull back per search. A handful is
# enough grounding for one short reply; more risks diluting the draft
# with less relevant material.

MODEL_PROVIDER = "kimi"
# Same toggle as classify_and_extract.py: "claude" or "kimi".

if MODEL_PROVIDER == "kimi":
    MODEL_NAME = "kimi-k2.6"
else:
    MODEL_NAME = "claude-sonnet-5"

KIMI_REQUEST_DELAY_SECONDS = 21
MAX_RATE_LIMIT_RETRIES = 5
RATE_LIMIT_RETRY_WAIT_SECONDS = 25

# Categories where a live database fact is central to a correct
# answer, rather than (or in addition to) a knowledge base rule.
LIVE_LOOKUP_CATEGORIES = {
    "balance_inquiry",
    "declined_transaction",
    "account_status_inquiry",
    "application_status_inquiry",
}

# Categories with no live fact and no policy to explain — these get a
# short, standard acknowledgement instead of a fully grounded draft.
ACKNOWLEDGEMENT_ONLY_CATEGORIES = {
    "fraud_report",
    "new_account_request",
}


# ---------------------------------------------------------------------------
# SECTION 3: DATABASE CONNECTION AND LIVE-DATA LOOKUPS
# ---------------------------------------------------------------------------

def connect_to_database():
    return psycopg2.connect(
        host=DATABASE_HOST,
        port=DATABASE_PORT,
        dbname=DATABASE_NAME,
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def fetch_account_details(connection, account_number):
    """Look up an account's real current state. Returns None if it doesn't exist."""

    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT account_type, available_balance, actual_balance,
               account_status, status_reason
        FROM account
        WHERE account_number = %s
        LIMIT 1
        """,
        (account_number,),
    )
    row = cursor.fetchone()
    cursor.close()

    if row is None:
        return None

    return dict(row)


def fetch_transaction_details(connection, account_number, transaction_date, amount):
    """
    Look up the real transaction behind a decline, matching on account,
    date, and amount together (since none of those alone is a reliable
    match on its own). Returns None if no matching transaction is
    found.
    """

    if account_number is None or transaction_date is None or amount is None:
        return None

    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT status_code, status_reason, transaction_amount, transaction_timestamp
        FROM transaction_history
        WHERE account_number = %s
          AND transaction_timestamp::date = %s
          AND transaction_amount = %s
        LIMIT 1
        """,
        (account_number, transaction_date, amount),
    )
    row = cursor.fetchone()
    cursor.close()

    if row is None:
        return None

    return dict(row)


def fetch_customer_status(connection, customer_number, sort_code=None):
    """Look up a customer's real current status. Returns None if not found."""

    if customer_number is None:
        return None

    cursor = connection.cursor()
    if sort_code is None:
        cursor.execute(
            "SELECT customer_status, status_reason FROM customer WHERE customer_number = %s LIMIT 1;",
            (customer_number,),
        )
    else:
        cursor.execute(
            """
            SELECT customer_status, status_reason
            FROM customer
            WHERE sort_code = %s
              AND customer_number = %s
            LIMIT 1;
            """,
            (sort_code, customer_number),
        )
    row = cursor.fetchone()
    cursor.close()

    if row is None:
        return None

    return dict(row)


def fetch_all_customer_accounts(connection, sort_code, customer_number):
    """Return all accounts belonging to one verified customer identity."""

    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT sort_code, account_number, account_type, available_balance,
               actual_balance, account_status, status_reason
        FROM account
        WHERE sort_code = %s
          AND customer_number = %s
        ORDER BY account_number;
        """,
        (sort_code, customer_number),
    )
    rows = cursor.fetchall()
    cursor.close()

    return [dict(row) for row in rows]


def look_up_live_facts(connection, category, entities, resolved_sort_code, resolved_customer_number):
    """
    Gather whatever real, current facts are relevant to this
    category. Returns a plain dictionary of findings — exactly what
    was found, nothing invented, and missing pieces are simply absent
    rather than guessed at.
    """

    facts = {}

    account_number = entities.get("account_number")

    if category == "balance_inquiry" and account_number:
        facts["account"] = fetch_account_details(connection, account_number)
    elif category == "balance_inquiry" and resolved_sort_code and resolved_customer_number:
        facts["accounts"] = fetch_all_customer_accounts(
            connection, resolved_sort_code, resolved_customer_number
        )

    elif category == "declined_transaction" and account_number:
        facts["transaction"] = fetch_transaction_details(
            connection,
            account_number,
            entities.get("transaction_date"),
            entities.get("amount"),
        )

    elif category == "account_status_inquiry" and account_number:
        facts["account"] = fetch_account_details(connection, account_number)

    elif category == "application_status_inquiry":
        facts["customer"] = fetch_customer_status(
            connection, resolved_customer_number, resolved_sort_code
        )

    return facts


# ---------------------------------------------------------------------------
# SECTION 4: SEARCHING THE KNOWLEDGE BASE
# ---------------------------------------------------------------------------

def build_retrieval_query(category, live_facts):
    """
    Build the text we'll search the knowledge base with. We use the
    REAL reason we've already found in bankdb, not the customer's own
    (often vague) wording — a precise search query finds a precise
    rule.

    Returns None when there's nothing meaningful to search for yet
    (e.g. the account or transaction wasn't found at all).
    """

    if category == "declined_transaction":
        transaction = live_facts.get("transaction")
        if transaction is not None and transaction.get("status_reason"):
            return "transaction declined " + transaction["status_reason"]
        return None

    if category == "account_status_inquiry":
        account = live_facts.get("account")
        if account is not None and account.get("status_reason"):
            return "account " + account["account_status"] + " " + account["status_reason"]
        if account is not None:
            return "account " + account["account_status"]
        return None

    if category == "application_status_inquiry":
        customer = live_facts.get("customer")
        if customer is not None and customer.get("status_reason"):
            return "customer application " + customer["status_reason"]
        return None

    if category == "invalid_account_reference":
        return "account not found"

    return None


def retrieve_relevant_rules(connection, embedding_model, query_text):
    """
    Embed the query text and find the closest matching rules in
    rule_knowledge_base by cosine distance. Returns a list of
    dictionaries, each with the rule's text and enough detail to cite
    it later.
    """

    if query_text is None:
        return []

    query_embedding = embedding_model.encode([query_text])[0].tolist()

    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT id, rule_text, source_file, section, subsection,
               embedding <=> %s::vector AS distance
        FROM rule_knowledge_base
        ORDER BY distance
        LIMIT %s
        """,
        (query_embedding, RULES_TO_RETRIEVE),
    )
    rows = cursor.fetchall()
    cursor.close()

    retrieved = []
    for row in rows:
        retrieved.append(dict(row))

    return retrieved


# ---------------------------------------------------------------------------
# SECTION 5: BUILDING THE DRAFT PROMPT AND CALLING THE MODEL
# ---------------------------------------------------------------------------

def build_draft_prompt(message_body, category, priority, live_facts, retrieved_rules, validation_result):
    """Build the instruction text sent to the model to write one draft reply."""

    prompt_lines = []
    prompt_lines.append("You are drafting a reply from a bank's customer support team.")
    prompt_lines.append("Write a short, clear, professional reply to the customer email below.")
    prompt_lines.append("")
    prompt_lines.append("Only state facts that appear in the LIVE DATA or KNOWLEDGE BASE")
    prompt_lines.append("sections below. Do not invent a balance, a reason, or a policy that")
    prompt_lines.append("isn't given to you here.")
    prompt_lines.append("")
    prompt_lines.append("If a KNOWLEDGE BASE section is provided below, you MUST use it to give")
    prompt_lines.append("a direct, specific answer to the customer's question — do not fall back")
    prompt_lines.append("to a vague 'someone will follow up' reply when you already have enough")
    prompt_lines.append("information to actually answer them.")
    prompt_lines.append("Only write a brief 'a member of the team will follow up' reply when")
    prompt_lines.append("NEITHER LIVE DATA NOR KNOWLEDGE BASE below gives you anything relevant")
    prompt_lines.append("to answer with.")
    prompt_lines.append("")
    prompt_lines.append("This bank operates in the UK. Always write monetary amounts in British")
    prompt_lines.append("pounds using the £ symbol (e.g. £45.20) — never $ or other currencies.")
    prompt_lines.append("")
    prompt_lines.append("Category: " + str(category))
    prompt_lines.append("Priority: " + str(priority))
    prompt_lines.append("")
    prompt_lines.append("Customer email:")
    prompt_lines.append(message_body)
    prompt_lines.append("")

    if validation_result.get("account_number_exists") is False:
        prompt_lines.append("LIVE DATA: The account number the customer mentioned does NOT exist in our system.")

    if live_facts:
        prompt_lines.append("LIVE DATA:")
        prompt_lines.append(json.dumps(live_facts, default=str))

    if retrieved_rules:
        prompt_lines.append("")
        prompt_lines.append("KNOWLEDGE BASE (each rule has an id — cite the ids you actually used):")
        for one_rule in retrieved_rules:
            prompt_lines.append("[id " + str(one_rule["id"]) + "] " + one_rule["rule_text"])

    prompt_lines.append("")
    prompt_lines.append("Reply with ONLY a JSON object shaped exactly like this, and nothing else:")
    prompt_lines.append('{"draft_reply": "...", "cited_rule_ids": [1, 2]}')
    prompt_lines.append("cited_rule_ids should be an empty list if no knowledge base rule was used.")

    return "\n".join(prompt_lines)


def ask_model(prompt_text, client):
    """Send one prompt to the model and return its reply as plain text, retrying on rate limits."""

    extra_arguments = {}
    if MODEL_PROVIDER == "kimi":
        extra_arguments["thinking"] = {"type": "disabled"}

    attempt_number = 0
    while attempt_number < MAX_RATE_LIMIT_RETRIES:
        attempt_number = attempt_number + 1
        try:
            response = client.messages.create(
                model=MODEL_NAME,
                max_tokens=600,
                messages=[{"role": "user", "content": prompt_text}],
                **extra_arguments,
            )
            break
        except anthropic.RateLimitError:
            print(
                "  Hit the API's rate limit. Waiting " + str(RATE_LIMIT_RETRY_WAIT_SECONDS)
                + " seconds before trying again (attempt " + str(attempt_number)
                + " of " + str(MAX_RATE_LIMIT_RETRIES) + ")."
            )
            time.sleep(RATE_LIMIT_RETRY_WAIT_SECONDS)
    else:
        print("  Gave up after repeated rate-limit errors.")
        return None

    reply_text = None
    for one_block in response.content:
        if one_block.type == "text":
            reply_text = one_block.text

    return reply_text


def strip_code_fence(text):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline_index = cleaned.find("\n")
        if first_newline_index != -1:
            cleaned = cleaned[first_newline_index + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
    return cleaned


# ---------------------------------------------------------------------------
# SECTION 6: PROCESSING ONE TEST MESSAGE'S RESULT
# ---------------------------------------------------------------------------

def draft_response(classification_result, client, connection, embedding_model):
    """Look up live facts, retrieve rules if relevant, and draft a reply for one message."""

    category = classification_result.get("extracted_category")
    priority = classification_result.get("extracted_priority")
    entities = classification_result.get("extracted_entities") or {}
    validation_result = classification_result.get("validation_result") or {}
    resolved_sort_code = classification_result.get("resolved_sort_code")
    resolved_customer_number = classification_result.get("resolved_customer_number")

    queue_entry = {
        "message_id": classification_result["message_id"],
        "message_body": classification_result["message_body"],
        "category": category,
        "priority": priority,
    }

    if category in ACKNOWLEDGEMENT_ONLY_CATEGORIES:
        live_facts = {}
        retrieved_rules = []
    else:
        live_facts = look_up_live_facts(
            connection, category, entities, resolved_sort_code, resolved_customer_number
        )
        query_text = build_retrieval_query(category, live_facts)
        retrieved_rules = retrieve_relevant_rules(connection, embedding_model, query_text)

    queue_entry["live_facts"] = live_facts
    queue_entry["retrieved_rule_ids"] = [r["id"] for r in retrieved_rules]

    prompt_text = build_draft_prompt(
        classification_result["message_body"], category, priority,
        live_facts, retrieved_rules, validation_result,
    )
    reply_text = ask_model(prompt_text, client)

    if reply_text is None:
        queue_entry["error"] = "no_reply_text"
        return queue_entry

    cleaned_reply_text = strip_code_fence(reply_text)

    try:
        parsed_reply = json.loads(cleaned_reply_text)
    except json.JSONDecodeError:
        queue_entry["error"] = "invalid_json"
        queue_entry["raw_model_output"] = reply_text
        return queue_entry

    queue_entry["draft_reply"] = parsed_reply.get("draft_reply")
    queue_entry["cited_rule_ids"] = parsed_reply.get("cited_rule_ids", [])

    return queue_entry


# Keep the older function name so existing fixture-oriented callers continue
# to work while the shared pipeline uses the clearer draft_response name.
process_one_result = draft_response


# ---------------------------------------------------------------------------
# SECTION 7: THE MAIN PROGRAM
# ---------------------------------------------------------------------------

def main():

    with open(CLASSIFICATION_RESULTS_FILE, "r", encoding="utf-8") as input_handle:
        classification_results = json.load(input_handle)

    print("Loaded", len(classification_results), "classified messages from", CLASSIFICATION_RESULTS_FILE)

    print("Loading the embedding model...")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    if MODEL_PROVIDER == "kimi":
        client = anthropic.Anthropic(
            api_key=os.environ["MOONSHOT_API_KEY"],
            base_url="https://api.moonshot.ai/anthropic",
        )
    else:
        client = anthropic.Anthropic()

    connection = connect_to_database()

    review_queue = []
    for index_number in range(len(classification_results)):
        one_result = classification_results[index_number]

        if "error" in one_result:
            print(
                "Skipping " + one_result["message_id"]
                + " — Phase 1 never got a usable classification for it."
            )
            continue

        print(
            "Drafting " + str(index_number + 1) + " of " + str(len(classification_results))
            + ": " + one_result["message_id"]
        )

        queue_entry = draft_response(one_result, client, connection, embedding_model)
        review_queue.append(queue_entry)

        if MODEL_PROVIDER == "kimi":
            time.sleep(KIMI_REQUEST_DELAY_SECONDS)
        else:
            time.sleep(1)

    connection.close()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as output_handle:
        # default=str is needed here for the same reason it's needed
        # inside build_draft_prompt(): Postgres NUMERIC columns (like
        # available_balance) come back from psycopg2 as Python Decimal
        # objects, which json.dump() doesn't know how to write out on
        # its own. default=str tells it to fall back to converting
        # anything it doesn't recognise into plain text instead.
        json.dump(review_queue, output_handle, indent=2, default=str)

    print("")
    print("Done. Wrote", len(review_queue), "drafts to", OUTPUT_FILE)
    print("Nothing was sent — every draft is waiting in this file for human review.")


if __name__ == "__main__":
    main()

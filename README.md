# Inbox Agent — AI-Managed Banking Customer Service Inbox

A GenAI portfolio project: an agent that reads incoming customer-service
email for a bank, classifies and verifies the sender's identity, drafts a
reply grounded in real business rules and live account data, and decides
deterministically whether that reply is safe to send automatically or must
go to a human first.

Built independently of the author's mainframe background to demonstrate
end-to-end GenAI engineering: RAG over real extracted business rules,
LLM-based classification and drafting, a deterministic safety gate,
idempotent message processing, and a durable Gmail integration.

---

## 1. Why it's built this way

- **Escalation is plain Python, not another model call.** Whether a message
  is safe to answer automatically is a safety-critical decision. A fixed
  rule set is more auditable and more consistent than an LLM judgment call,
  and it costs nothing to run.
- **Fail closed.** Any category, status, or combination the rules don't
  explicitly recognize defaults to escalate. Guessing and sending
  automatically is never the fallback; a human looking at it is.
- **The knowledge base is real, not synthetic.** The RAG content comes from
  parsing and synthesizing actual COBOL/CICS business-rule analysis
  documents (validations, fail codes, abend codes) for a legacy banking
  application — not invented FAQ text.
- **Identity is a trust boundary, not an authentication claim.** The sender's
  email address (Gmail `From:` header) is the primary signal; customer
  number and account number are secondary verification factors checked
  against bankdb. This system does not independently verify SPF/DKIM/DMARC —
  see Known Limitations.
- **Idempotency and delivery state are tracked durably in Postgres**, not in
  memory, so a crash or restart never produces a duplicate reply.

---

## 2. Project layout

```
inbox-agent/
├── database/            Synthetic banking database (schema + generators + load)
├── knowledge_base/       COBOL rule extraction → embeddings → pgvector
└── agent/                Classification, drafting, routing, Gmail integration, tests
```

### 2.1 `database/`

Synthetic PostgreSQL banking dataset modeled on a legacy CICS/COBOL core
banking system (CUSTOMER / ACCOUNT / CONTROL / PROCTRAN), extended with
status and reason-code lifecycle tracking so the agent has real states to
reason about (frozen accounts, suspended customers, declined transactions).

```
database/
├── bankdb_config.yaml        all generation parameters: seed, sort code,
│                              status weights, reason-code mappings, balance
│                              rules, transaction volumes
├── bankdb_schema.sql         6 tables, check constraints, indexes, triggers
├── generate_data.py          orchestrator (reason_code → customer → account →
│                              status_history → transaction_history → control)
├── load_data.sql              \copy-based CSV loader, dependency-ordered
├── truncate_tables.sql
├── verify_data.sql            12 integrity/business-rule checks, expect 0
│                              invalid_rows on every one
├── setup_bankdb.ps1            one-shot: drop → create → schema → generate →
│                              load → verify
├── generators/
│   ├── customer_generator.py
│   ├── account_generator.py
│   ├── control_generator.py
│   ├── reason_code_generator.py
│   ├── status_history_generator.py
│   └── transaction_history_generator.py
├── utils/
│   ├── date_utils.py
│   ├── random_utils.py
│   └── validation.py
└── output/                    generated CSVs (gitignored)
```

Tables:

| Table | Purpose |
|---|---|
| `customer` | Customer master: identity, contact info, credit score, `customer_status` (PENDING/ACTIVE/SUSPENDED/PENDING_DELETE/DELETED/DECEASED) |
| `account` | One or more accounts per customer: type, balances, `account_status` (ACTIVE/DORMANT/FROZEN/PENDING_CLOSE/CLOSED) |
| `transaction_history` | Immutable ledger: financial events (CREDIT/DEBIT) and lifecycle events (OCC/ODC customer open/close, OFA/OUA/OSC account open/update/status-change) |
| `status_history` | Synthesized status-transition history for customers and accounts |
| `reason_code` | Master list of status/transaction reason codes with customer-facing text |
| `control` | Generation metadata and record counts |

Generation is deterministic (`random.Random(seed=42)`, decorrelated per
generator by offsetting the seed), so the same config always reproduces the
same dataset. All status/reason/balance invariants are enforced both by
Postgres check constraints and by `verify_data.sql`.

Setup:

```powershell
.\venv\Scripts\Activate.ps1
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\database\setup_bankdb.ps1
```

or manually: create the database, run `bankdb_schema.sql`, run
`generate_data.py`, run `load_data.sql`, run `verify_data.sql`.

### 2.2 `knowledge_base/`

Turns the bank's actual legacy-system business-rule documentation into a
retrievable vector store.

```
knowledge_base/
├── parse_analysis_docs.py          parses the 8 *_Analysis.md source docs
│                                    into structured rule rows (validations,
│                                    fail codes, abend codes)
├── synthesize_rule_text.py          LLM pass that turns each structured row
│                                    into natural-language rule text, batched
├── retry_failed_batches.py          re-runs batches the model couldn't parse
├── load_rules_into_vector_store.py  embeds rule text (sentence-transformers
│                                    all-MiniLM-L6-v2, 384-dim) and loads into
│                                    a pgvector table
├── source_docs/                     8 COBOL business-rule analysis documents
│                                    (Create_Account, Create_Customer,
│                                    Credit_Debit_Account,
│                                    Display_Customer_Accounts,
│                                    Display_Delete_Account,
│                                    Display_Update_Delete_Customer,
│                                    Transfer_Funds, Update_Account)
└── output/
    ├── parsed_rules.json
    └── rules_with_text.json
```

Result: 380 embedded business rules in a `rule_knowledge_base` pgvector
table, retrieved by the drafting stage to ground replies in the bank's
actual validation and fail-code logic rather than generic banking
knowledge.

Note: the synthesis step calls an LLM in batches and needs
`thinking: {"type": "disabled"}` set for Kimi specifically — without it,
Kimi can consume its entire token budget on hidden reasoning and return no
usable text for a batch.

### 2.3 `agent/`

The application itself.

```
agent/
├── contracts.py                 InboundMessage — the one shared message
│                                 shape every adapter normalizes into
├── bankdb.py                    shared customer-status/email lookup helpers
│                                 (used by both drafting and routing, so the
│                                 SQL lives in one place)
├── generate_test_messages.py    Phase 0 — synthetic test emails + ground truth
├── classify_and_extract.py      Phase 1 — category/entity extraction +
│                                 deterministic identity-resolution gate
├── generate_draft_response.py   Phase 2 — RAG-grounded draft reply (bankdb
│                                 live facts + knowledge-base retrieval)
├── apply_escalation_rules.py    Phase 3 — deterministic autonomous/escalate
│                                 decision (no LLM call)
├── pipeline.py                  Phase 4 — orchestrates phases 1–3 for one
│                                 InboundMessage; owns the identity-failure
│                                 reply wording
├── processing_state.py          idempotency: claim / mark_completed /
│                                 mark_failed, keyed by (source, message_id)
├── delivery_state.py            durable send-state machine: PREPARED →
│                                 SENDING → SENT / UNKNOWN / FAILED
├── send_policy.py               deterministic authorization gate for
│                                 autonomous sends — the LLM cannot grant this
├── gmail_agent.py                main entry point: polls Gmail, runs the
│                                 pipeline, creates drafts, sends autonomous
│                                 replies, reconciles delivery state on resume
├── gmail_drafts.py               builds the MIME reply and calls
│                                 drafts.create
├── gmail_send.py                  sends an existing draft (drafts.send) and
│                                 finds it/its sent copy by deterministic
│                                 Message-ID for crash recovery
├── adapters/
│   ├── fixtures.py               test_messages.json → InboundMessage
│   └── gmail.py                  Gmail API payload → InboundMessage (MIME
│                                 parsing, multipart handling, attachment
│                                 exclusion)
├── output/                       JSON artifacts between phases
└── tests/                        see §4
```

---

## 3. Pipeline flow

```
InboundMessage
      │
      ▼
Phase 1  classify_and_extract.py
         - look up customer records by sender email
         - ask the model for category + entities
         - validate entities against bankdb
         - resolve_customer_identity(): deterministic identity gate
      │
      ├── identity not eligible ──► pipeline.py builds a safe,
      │                              non-disclosing identity-failure reply
      │                              and STOPS (no live facts, no drafting,
      │                              no routing)
      │
      ▼ identity eligible
Phase 2  generate_draft_response.py
         - fetch live bankdb facts (balances, status, transaction)
         - retrieve relevant knowledge-base rules (pgvector)
         - ask the model for a grounded reply, citing rule IDs
      │
      ▼
Phase 3  apply_escalation_rules.py
         - plain Python rules decide: autonomous | escalate
         - always escalate: fraud_report, FRAUD_SUSPECTED/COURT_ORDER
           reasons, any unrecognized category
      │
      ▼
Phase 5  gmail_agent.py
         - claim the message (processing_state) — idempotent, crash-safe
         - create a Gmail draft
         - if autonomous: send_policy gate re-checks everything
           independently, then delivery_state tracks PREPARED → SENDING →
           SENT, with Gmail's Sent folder checked before ever assuming a
           send failed (prevents duplicate sends)
         - if escalate: draft is left for human review, not sent
```

### Identity resolution (deterministic, security-critical)

`resolve_customer_identity()` in `classify_and_extract.py` combines: the
customer record(s) matching the sender's email, an optional customer number
from the message body, and an optional account number, into one of several
outcomes — `verified_single_customer`, `customer_number_match`,
`customer_number_mismatch`, `multiple_customers_identifier_missing`,
`account_number_match`, `account_number_not_found`,
`account_number_not_owned`, `multiple_customers_match_account`,
`multiple_matching_customer_records`, `email_not_registered`. Only specific
outcomes set `identity_eligible = True`.

Two anti-disclosure properties are enforced in `pipeline.py`'s
`build_identity_failure_reply`:
- A customer-number mismatch never reveals the correct customer number, even
  when exactly one record matched the sender's email.
- `account_number_not_found` and `account_number_not_owned` produce
  byte-identical customer-facing text, so a sender cannot use response
  wording to enumerate which account numbers exist.

---

## 4. Tests

```
agent/tests/
├── test_identity.py                     resolve_customer_identity — every
│                                          identity-state combination
├── test_pipeline.py                      pipeline.py: identity-failure reply
│                                          wording (incl. the two
│                                          anti-disclosure properties above)
│                                          and orchestration call order
├── test_policy.py                        send_policy.py: the autonomous-send
│                                          gate, fail-closed on every missing
│                                          or conflicting condition
├── test_message_processing_pipeline.py   classify/draft/route using real
│                                          production functions with mocked
│                                          model/DB calls
├── test_processing_state.py              claim/complete/fail idempotency,
│                                          integration test against real
│                                          bankdb
├── test_delivery_state.py                PREPARED→SENDING→SENT/UNKNOWN/FAILED
│                                          state machine, integration test
│                                          against real bankdb
├── test_gmail_drafts.py                  MIME construction + drafts.create,
│                                          fake Gmail service
├── test_gmail_send.py                    drafts.send + deterministic
│                                          outbound Message-ID, fake Gmail
│                                          service
├── test_gmail_adapter.py                 Gmail payload → InboundMessage:
│                                          multipart, headers, attachments
└── test_gmail_agent_orchestration.py     process_one_gmail_message and
                                           resume_autonomous_delivery: claim/
                                           skip logic, crash-recovery paths,
                                           the "never recreate a send that
                                           might already have happened" rule
```

Most tests use one of two strategies to avoid needing real Gmail/LLM
credentials: AST-extracting the specific function(s) under test from the
real source file into an isolated namespace, or a `RecordingFake` that
stands in for a dependency and records how it was called. Where real
infrastructure is cheap and safe to use (Postgres), tests run as genuine
integration tests against bankdb with cleanup in a `finally` block.

Known coverage gaps: no concurrency test exercises `claim_message` under
genuinely simultaneous workers (reasoned about, not executed in parallel);
`test_message_processing_pipeline.py` has no case for the
`new_account_request` escalation branch specifically, though it is covered
indirectly elsewhere.

---

## 5. Known limitations

- **Sender trust boundary.** Identity resolution treats the Gmail `From:`
  address as the primary signal. This application does not independently
  verify SPF/DKIM/DMARC; it relies on Gmail's own upstream spam/authentication
  filtering. A spoofed sender address that passes Gmail's filtering and
  matches a real customer's email on file could pass the first identity
  check — customer number / account number verification is the second
  factor that limits what such a message can actually do.
- **A verified customer's balance inquiry lists all of their accounts**
  rather than asking which one. This is a deliberate design choice, not an
  oversight: once a customer's identity is verified, returning their full
  account list is treated as acceptable disclosure for this system's scope.
- **Gmail's own spam/phishing filtering is relied upon** as the first line
  of defense before any message reaches this pipeline.

---

## 6. Running it

```bash
# 1. Database
.\database\setup_bankdb.ps1

# 2. Knowledge base
python knowledge_base/parse_analysis_docs.py
python knowledge_base/synthesize_rule_text.py
python knowledge_base/load_rules_into_vector_store.py

# 3. Generate and classify test messages (no Gmail needed)
python agent/generate_test_messages.py
python agent/classify_and_extract.py
python agent/generate_draft_response.py
python agent/apply_escalation_rules.py

# 4. Live Gmail integration
python agent/gmail_agent.py
```

Required environment variable: `PGPASSWORD` (bankdb connection). Model
provider (Claude or Kimi) is selected via the `MODEL_PROVIDER` constant.

---

## 7. Status

All identified correctness and security defects found during the latest
review round are fixed and verified by execution against real Postgres data
and real source code (not merely reasoned about). See the project's
handoff notes for the itemized list of fixes, remaining test-coverage gaps,
and recommended follow-ups (a concurrency test for `claim_message`,
retiring the redundant `test_api.py`, typed result models to catch
structural mismatches earlier).

-- ============================================================================
-- BANKDB SYNTHETIC BANKING DATASET - FINAL SCHEMA
-- PostgreSQL
-- ============================================================================

-- ============================================================================
-- 1. CUSTOMER
-- ============================================================================

CREATE TABLE customer
(
    sort_code                 VARCHAR(6)   NOT NULL,
    customer_number           VARCHAR(10)  NOT NULL,

    customer_name             VARCHAR(60)  NOT NULL,
    customer_address          VARCHAR(100),
    customer_city             VARCHAR(30),
    customer_state            VARCHAR(30),
    customer_postcode         VARCHAR(10),
    customer_email            VARCHAR(100),
    customer_phone            VARCHAR(20),

    date_of_birth             DATE,
    credit_score              INTEGER,
    credit_score_review_date  DATE,

    -- PENDING, ACTIVE, SUSPENDED, PENDING_DELETE, DELETED, DECEASED
    customer_status           VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
    status_reason             VARCHAR(30),
    status_changed_at         TIMESTAMP,

    created_at                TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_customer
        PRIMARY KEY (sort_code, customer_number),

    CONSTRAINT chk_credit_score
        CHECK (credit_score IS NULL OR credit_score BETWEEN 300 AND 999),

    CONSTRAINT chk_customer_status
        CHECK (customer_status IN
        (
            'PENDING',
            'ACTIVE',
            'SUSPENDED',
            'PENDING_DELETE',
            'DELETED',
            'DECEASED'
        )),

    CONSTRAINT chk_customer_credit_review_date
        CHECK
        (
            credit_score_review_date IS NULL
            OR date_of_birth IS NULL
            OR credit_score_review_date >= date_of_birth
        ),

    -- ACTIVE is the only status that needs no explanation. PENDING
    -- customers are mid-onboarding (e.g. KYC_INCOMPLETE) and now
    -- require a reason just like every other non-normal status.
    CONSTRAINT chk_customer_status_reason
        CHECK
        (
            customer_status = 'ACTIVE'
            OR status_reason IS NOT NULL
        )
);


-- ============================================================================
-- 2. ACCOUNT
-- ============================================================================

CREATE TABLE account
(
    sort_code                 VARCHAR(6)   NOT NULL,
    account_number            VARCHAR(8)   NOT NULL,

    customer_number           VARCHAR(10)  NOT NULL,

    account_type              VARCHAR(20)  NOT NULL,
    interest_rate             NUMERIC(6,3),

    opened_date               DATE,

    -- ACTIVE, DORMANT, FROZEN, PENDING_CLOSE, CLOSED
    account_status            VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
    status_reason             VARCHAR(30),
    status_changed_at         TIMESTAMP,
    closed_date               DATE,

    overdraft_limit           NUMERIC(15,2) NOT NULL DEFAULT 0,

    last_statement_date       DATE,
    next_statement_date       DATE,

    available_balance         NUMERIC(15,2) NOT NULL DEFAULT 0,
    actual_balance             NUMERIC(15,2) NOT NULL DEFAULT 0,

    created_at                TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_account
        PRIMARY KEY (sort_code, account_number),

    CONSTRAINT fk_account_customer
        FOREIGN KEY (sort_code, customer_number)
        REFERENCES customer (sort_code, customer_number),

    CONSTRAINT chk_account_type
        CHECK (account_type IN
        (
            'CURRENT',
            'SAVINGS',
            'ISA',
            'LOAN',
            'MORTGAGE'
        )),

    CONSTRAINT chk_account_status
        CHECK (account_status IN
        (
            'ACTIVE',
            'DORMANT',
            'FROZEN',
            'PENDING_CLOSE',
            'CLOSED'
        )),

    CONSTRAINT chk_non_negative_overdraft
        CHECK (overdraft_limit >= 0),

    CONSTRAINT chk_closed_date_iff_closed
        CHECK
        (
            (account_status = 'CLOSED' AND closed_date IS NOT NULL)
            OR
            (account_status <> 'CLOSED' AND closed_date IS NULL)
        ),

    CONSTRAINT chk_account_dates
        CHECK
        (
            closed_date IS NULL
            OR opened_date IS NULL
            OR closed_date >= opened_date
        ),

    CONSTRAINT chk_statement_dates
        CHECK
        (
            next_statement_date IS NULL
            OR last_statement_date IS NULL
            OR next_statement_date >= last_statement_date
        ),

    CONSTRAINT chk_closed_deposit_zeroed
        CHECK
        (
            NOT
            (
                account_status = 'CLOSED'
                AND account_type IN ('CURRENT', 'SAVINGS', 'ISA')
            )
            OR
            (actual_balance = 0 AND available_balance = 0)
        ),

    CONSTRAINT chk_closed_loan_zeroed
        CHECK
        (
            NOT
            (
                account_status = 'CLOSED'
                AND account_type IN ('LOAN', 'MORTGAGE')
            )
            OR
            (actual_balance = 0 AND available_balance = 0)
        ),

    -- LOAN and MORTGAGE are liability accounts: while not CLOSED, both
    -- balances must be negative or zero. Previously nothing enforced
    -- this at the schema level, so a config error (positive
    -- balance_rules ranges) went uncaught.
    CONSTRAINT chk_loan_balance_sign
        CHECK
        (
            account_type NOT IN ('LOAN', 'MORTGAGE')
            OR account_status = 'CLOSED'
            OR (actual_balance <= 0 AND available_balance <= 0)
        ),

    CONSTRAINT chk_account_status_reason
        CHECK
        (
            account_status IN ('ACTIVE', 'DORMANT')
            OR status_reason IS NOT NULL
        )
);


-- ============================================================================
-- 3. CONTROL
-- ============================================================================

CREATE TABLE control
(
    control_key              VARCHAR(50)   NOT NULL,
    control_value            VARCHAR(100)  NOT NULL,
    description              VARCHAR(100),

    created_at               TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_control PRIMARY KEY (control_key)
);


-- ============================================================================
-- 4. REASON CODE MASTER
-- ============================================================================

CREATE TABLE reason_code
(
    reason_code              VARCHAR(30)   NOT NULL,
    applies_to               VARCHAR(20)   NOT NULL,
    description              VARCHAR(200),
    customer_facing_text     VARCHAR(200),

    CONSTRAINT pk_reason_code
        PRIMARY KEY (reason_code),

    CONSTRAINT chk_reason_code_applies_to
        CHECK (applies_to IN
        (
            'ACCOUNT_STATUS',
            'CUSTOMER_STATUS',
            'TRANSACTION'
        ))
);


-- ============================================================================
-- 5. transaction_history - IMMUTABLE TRANSACTION / LIFECYCLE EVENT LEDGER
-- ============================================================================
-- Financial events:
--   CREDIT, DEBIT
--
-- Customer lifecycle events:
--   OCC = Open/Create Customer
--   ODC = Delete/Close Customer
--
-- Account lifecycle events:
--   OFA = Open/Create Account
--   OUA = Update Account (reserved; no generator currently emits this)
--   OSC = Account Status Change
--
-- customer_number is populated on every event, including account-level
-- ones, so a customer's full lifecycle history can be queried directly
-- without joining through account. This was previously omitted, which
-- made it structurally impossible to verify which customer an OCC/ODC
-- event belonged to (account_number is NULL for those event types, so
-- no join path existed at all).
-- ============================================================================

CREATE TABLE transaction_history
(
    transaction_id           BIGINT
                             GENERATED ALWAYS AS IDENTITY,

    sort_code                VARCHAR(6)   NOT NULL,
    customer_number          VARCHAR(10)  NOT NULL,

    -- Nullable only for customer-level lifecycle events OCC and ODC.
    account_number           VARCHAR(8),

    transaction_timestamp    TIMESTAMP    NOT NULL,
    transaction_type         VARCHAR(20)  NOT NULL,
    transaction_amount       NUMERIC(15,2) NOT NULL,

    transaction_description  VARCHAR(100),

    -- SUCCESS, DECLINED, REJECTED, FAILED
    status_code              VARCHAR(20)  NOT NULL DEFAULT 'SUCCESS',
    status_reason            VARCHAR(30),

    created_at               TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_transaction_history
        PRIMARY KEY (transaction_id),

    CONSTRAINT fk_transaction_history_customer
        FOREIGN KEY (sort_code, customer_number)
        REFERENCES customer (sort_code, customer_number),

    CONSTRAINT fk_transaction_history_account
        FOREIGN KEY (sort_code, account_number)
        REFERENCES account (sort_code, account_number),

    CONSTRAINT chk_transaction_type
        CHECK (transaction_type IN
        (
            'CREDIT',
            'DEBIT',
            'OCC',
            'ODC',
            'OFA',
            'OUA',
            'OSC'
        )),

    CONSTRAINT chk_transaction_amount_non_negative
        CHECK (transaction_amount >= 0),

    -- Financial transactions must carry a genuine positive amount.
    -- Previously only >= 0 was enforced at the schema level, so a
    -- zero-amount CREDIT/DEBIT would have passed silently; only
    -- verify_data.sql caught this, and only after the fact.
    CONSTRAINT chk_financial_transaction_amount_positive
        CHECK
        (
            transaction_type NOT IN ('CREDIT', 'DEBIT')
            OR transaction_amount > 0
        ),

    -- Lifecycle events are audit events and do not carry a monetary amount.
    CONSTRAINT chk_lifecycle_transaction_zero_amount
        CHECK
        (
            transaction_type IN ('CREDIT', 'DEBIT')
            OR transaction_amount = 0
        ),

    -- Financial and account lifecycle events must reference an account.
    -- Customer lifecycle events OCC and ODC must not reference an account.
    CONSTRAINT chk_transaction_account_reference
        CHECK
        (
            (
                transaction_type IN ('CREDIT', 'DEBIT', 'OFA', 'OUA', 'OSC')
                AND account_number IS NOT NULL
            )
            OR
            (
                transaction_type IN ('OCC', 'ODC')
                AND account_number IS NULL
            )
        ),

    CONSTRAINT chk_status_code
        CHECK (status_code IN
        (
            'SUCCESS',
            'DECLINED',
            'REJECTED',
            'FAILED'
        )),

    -- A reason is mandatory for a non-successful transaction.
    CONSTRAINT chk_transaction_status_reason
        CHECK
        (
            status_code = 'SUCCESS'
            OR status_reason IS NOT NULL
        )
);


-- ============================================================================
-- 6. STATUS HISTORY
-- ============================================================================
-- entity_number stores:
--   CUSTOMER -> customer_number
--   ACCOUNT  -> account_number
-- Referential validation is intentionally performed by the generator/application
-- because this is a polymorphic history table.
-- ============================================================================

CREATE TABLE status_history
(
    history_id               BIGINT
                             GENERATED ALWAYS AS IDENTITY,

    entity_type              VARCHAR(20) NOT NULL,
    sort_code                VARCHAR(6)  NOT NULL,
    entity_number            VARCHAR(10) NOT NULL,

    previous_status          VARCHAR(20),
    status_reason            VARCHAR(30),
    new_status                VARCHAR(20) NOT NULL,

    changed_at                TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_status_history
        PRIMARY KEY (history_id),

    CONSTRAINT chk_status_history_entity_type
        CHECK (entity_type IN ('CUSTOMER', 'ACCOUNT')),

    CONSTRAINT chk_status_history_status_change
        CHECK
        (
            previous_status IS NULL
            OR previous_status <> new_status
        )
);


-- ============================================================================
-- 7. AGENT AUDIT LOG
-- ============================================================================
-- This table records what the inbox agent saw and decided for each processed
-- message. Ground-truth fields are populated only by the fixture evaluation
-- pipeline; they remain NULL for future live messages.
--
-- The table belongs in this clean-build schema so a newly created bankdb has
-- the same agent support tables as an existing database upgraded with the
-- Phase 4A additive migration.
-- ============================================================================

CREATE TABLE agent_audit_log
(
    id                              BIGINT GENERATED ALWAYS AS IDENTITY,

    message_id                      VARCHAR(255),
    message_body                    TEXT,

    model_provider                  VARCHAR(20),
    raw_model_output                TEXT,

    extracted_category              VARCHAR(50),
    extracted_priority              VARCHAR(20),
    extracted_entities              JSONB,
    entity_matches                  JSONB,
    validation_result               JSONB,

    expected_customer_number        VARCHAR(20),
    resolved_customer_number        VARCHAR(20),
    customer_identified_correctly   BOOLEAN,

    ground_truth_category           VARCHAR(50),
    ground_truth_priority           VARCHAR(20),
    category_correct                BOOLEAN,
    priority_correct                BOOLEAN,

    created_at                      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_agent_audit_log
        PRIMARY KEY (id)
);


-- ============================================================================
-- 8. AGENT MESSAGE PROCESSING STATE
-- ============================================================================
--
-- Durable idempotency and processing state for inbound messages.
-- The composite key is intentional: different message sources can have
-- different ID namespaces.  A Gmail message ID is therefore unique within
-- the Gmail source, while a fixture can safely reuse the same textual ID.
--
-- This table is separate from agent_audit_log because audit history and
-- operational processing state serve different purposes.  The processing
-- state answers: "Have we already processed this message, and where did we
-- get to?"
-- ============================================================================

CREATE TABLE message_processing
(
    source                       VARCHAR(50)  NOT NULL,
    source_message_id            VARCHAR(255) NOT NULL,
    source_thread_id             VARCHAR(255),

    -- RECEIVED, PROCESSING, COMPLETED, FAILED
    status                       VARCHAR(20)  NOT NULL,

    first_seen_at                TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processing_started_at       TIMESTAMP,
    processing_completed_at     TIMESTAMP,

    last_error                   TEXT,
    processing_result            JSONB,

    CONSTRAINT pk_message_processing
        PRIMARY KEY (source, source_message_id),

    CONSTRAINT chk_message_processing_status
        CHECK (status IN ('RECEIVED', 'PROCESSING', 'COMPLETED', 'FAILED')),

    CONSTRAINT chk_message_processing_completion
        CHECK
        (
            status <> 'COMPLETED'
            OR processing_completed_at IS NOT NULL
        )
);


-- ============================================================================
-- 9. INDEXES
-- ============================================================================

CREATE INDEX idx_customer_name
    ON customer (customer_name);

CREATE INDEX idx_customer_postcode
    ON customer (customer_postcode);

CREATE INDEX idx_customer_status
    ON customer (customer_status);

CREATE INDEX idx_account_customer
    ON account (sort_code, customer_number);

CREATE INDEX idx_account_type
    ON account (account_type);

CREATE INDEX idx_account_status
    ON account (account_status);

CREATE INDEX idx_transaction_history_customer
    ON transaction_history (sort_code, customer_number);

CREATE INDEX idx_transaction_history_account
    ON transaction_history (sort_code, account_number);

CREATE INDEX idx_transaction_history_timestamp
    ON transaction_history (transaction_timestamp);

CREATE INDEX idx_transaction_history_status_code
    ON transaction_history (status_code);

CREATE INDEX idx_status_history_entity
    ON status_history (entity_type, sort_code, entity_number);

CREATE INDEX idx_status_history_changed_at
    ON status_history (changed_at);


-- ============================================================================
-- 10. UPDATED_AT TRIGGER
-- ============================================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_customer_updated_at
BEFORE UPDATE ON customer
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_account_updated_at
BEFORE UPDATE ON account
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_control_updated_at
BEFORE UPDATE ON control
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


-- Index for efficient customer lookup by email.
-- Deliberately non-unique because the application supports
-- the possibility of one email being associated with multiple customers.
CREATE INDEX idx_customer_email_customer
    ON customer (customer_email, customer_number);


-- ============================================================================
-- 11. AGENT OUTBOUND MESSAGE DELIVERY STATE - PHASE 5C
-- ============================================================================
--
-- Durable state for autonomous outbound Gmail delivery. This is deliberately
-- separate from message_processing: inbound processing state answers whether
-- the message was processed; delivery state answers whether the generated
-- outbound response was sent.
--
-- PREPARED -> SENDING -> SENT
--                    \-> UNKNOWN -> later verification/retry
--                    \-> FAILED
--
-- The deterministic outbound_message_id is unique so a retry cannot create
-- a second logical outbound message for the same source message.
-- ============================================================================

CREATE TABLE message_delivery
(
    source                       VARCHAR(50)  NOT NULL,
    source_message_id            VARCHAR(255) NOT NULL,
    source_thread_id             VARCHAR(255),

    status                       VARCHAR(20)  NOT NULL,
    outbound_message_id          VARCHAR(255) NOT NULL,

    gmail_draft_id               VARCHAR(255),
    gmail_draft_message_id       VARCHAR(255),
    gmail_sent_message_id        VARCHAR(255),

    attempt_count                INTEGER      NOT NULL DEFAULT 0,

    first_prepared_at            TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sending_started_at           TIMESTAMP,
    sent_at                      TIMESTAMP,
    updated_at                   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    last_error                   TEXT,
    processing_result            JSONB,

    CONSTRAINT pk_message_delivery
        PRIMARY KEY (source, source_message_id),

    CONSTRAINT uq_message_delivery_outbound_message
        UNIQUE (outbound_message_id),

    CONSTRAINT chk_message_delivery_status
        CHECK (status IN ('PREPARED', 'SENDING', 'SENT', 'UNKNOWN', 'FAILED')),

    CONSTRAINT chk_message_delivery_attempt_count
        CHECK (attempt_count >= 0),

    CONSTRAINT chk_message_delivery_sent_fields
        CHECK
        (
            status <> 'SENT'
            OR
            (
                gmail_sent_message_id IS NOT NULL
                AND sent_at IS NOT NULL
            )
        )
);

CREATE INDEX idx_message_delivery_status
    ON message_delivery (status);

CREATE INDEX idx_message_delivery_updated_at
    ON message_delivery (updated_at);

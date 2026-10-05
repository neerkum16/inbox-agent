-- Additive Phase 4A migration. Run once against an existing bankdb database.
-- It formalizes the table previously created at application runtime.
CREATE TABLE IF NOT EXISTS agent_audit_log (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    message_id VARCHAR(255),
    message_body TEXT,
    model_provider VARCHAR(20),
    raw_model_output TEXT,
    extracted_category VARCHAR(50),
    extracted_priority VARCHAR(20),
    extracted_entities JSONB,
    entity_matches JSONB,
    validation_result JSONB,
    expected_customer_number VARCHAR(20),
    resolved_customer_number VARCHAR(20),
    customer_identified_correctly BOOLEAN,
    ground_truth_category VARCHAR(50),
    ground_truth_priority VARCHAR(20),
    category_correct BOOLEAN,
    priority_correct BOOLEAN,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- BANKDB - TRUNCATE GENERATED DATA
-- ============================================================================
-- Purpose:
--   Remove all generated data from BANKDB tables while preserving:
--   - Tables
--   - Constraints
--   - Indexes
--   - Triggers
--   - Functions
--
-- Use before loading a newly generated CSV dataset.
-- RESTART IDENTITY resets GENERATED ALWAYS AS IDENTITY columns.
-- CASCADE handles foreign-key dependencies safely.
-- ============================================================================

\set ON_ERROR_STOP on

\echo
\echo ============================================================
\echo BANKDB - TRUNCATE DATA
\echo ============================================================
\echo

BEGIN;

TRUNCATE TABLE
    transaction_history,
    status_history,
    account,
    customer,
    reason_code,
    control
RESTART IDENTITY
CASCADE;

COMMIT;

\echo
\echo ============================================================
\echo ALL BANKDB DATA TRUNCATED SUCCESSFULLY
\echo ============================================================
\echo

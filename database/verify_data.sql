-- ============================================================================
-- BANKDB - DATA VERIFICATION
-- ============================================================================
-- Validates data integrity and business rules after CSV load.
--
-- Expected result:
-- All invalid_rows values should be 0.
-- ============================================================================

\set ON_ERROR_STOP on

\echo ''
\echo '============================================================'
\echo 'BANKDB - DATA VERIFICATION'
\echo '============================================================'


-- ============================================================================
-- [1/12] ROW COUNTS
-- ============================================================================

\echo ''
\echo '[1/12] ROW COUNTS'

SELECT
    table_name,
    row_count
FROM (
    SELECT 'account' AS table_name, COUNT(*) AS row_count FROM account
    UNION ALL
    SELECT 'control', COUNT(*) FROM control
    UNION ALL
    SELECT 'customer', COUNT(*) FROM customer
    UNION ALL
    SELECT 'reason_code', COUNT(*) FROM reason_code
    UNION ALL
    SELECT 'status_history', COUNT(*) FROM status_history
    UNION ALL
    SELECT 'transaction_history', COUNT(*) FROM transaction_history
) counts
ORDER BY table_name;


-- ============================================================================
-- [2/12] ORPHAN ACCOUNT CHECK
-- ============================================================================

\echo ''
\echo '[2/12] ORPHAN ACCOUNT CHECK'

SELECT COUNT(*) AS invalid_rows
FROM account a
LEFT JOIN customer c
    ON a.sort_code = c.sort_code
   AND a.customer_number = c.customer_number
WHERE c.customer_number IS NULL;


-- ============================================================================
-- [3/12] CUSTOMER STATUS / REASON CHECK
-- ============================================================================
-- Only ACTIVE customers may omit a reason.
-- Every other customer status must have a valid CUSTOMER_STATUS reason code.
-- ============================================================================

\echo ''
\echo '[3/12] CUSTOMER STATUS / REASON CHECK'

SELECT COUNT(*) AS invalid_rows
FROM customer c
LEFT JOIN reason_code r
    ON c.status_reason = r.reason_code
WHERE
    (
        c.customer_status = 'ACTIVE'
        AND NULLIF(c.status_reason, '') IS NOT NULL
    )
    OR
    (
        c.customer_status <> 'ACTIVE'
        AND (
            NULLIF(c.status_reason, '') IS NULL
            OR r.reason_code IS NULL
            OR r.applies_to <> 'CUSTOMER_STATUS'
        )
    );


-- ============================================================================
-- [4/12] ACCOUNT STATUS / REASON CHECK
-- ============================================================================
-- ACTIVE and DORMANT accounts must not have a reason.
-- Other account statuses must have a valid ACCOUNT_STATUS reason code.
-- ============================================================================

\echo ''
\echo '[4/12] ACCOUNT STATUS / REASON CHECK'

SELECT COUNT(*) AS invalid_rows
FROM account a
LEFT JOIN reason_code r
    ON a.status_reason = r.reason_code
WHERE
    (
        a.account_status IN ('ACTIVE', 'DORMANT')
        AND NULLIF(a.status_reason, '') IS NOT NULL
    )
    OR
    (
        a.account_status NOT IN ('ACTIVE', 'DORMANT')
        AND (
            NULLIF(a.status_reason, '') IS NULL
            OR r.reason_code IS NULL
            OR r.applies_to <> 'ACCOUNT_STATUS'
        )
    );


-- ============================================================================
-- [5/12] CLOSED ACCOUNT BALANCE CHECK
-- ============================================================================
-- Closed accounts must have zero balances.
-- ============================================================================

\echo ''
\echo '[5/12] CLOSED ACCOUNT BALANCE CHECK'

SELECT COUNT(*) AS invalid_rows
FROM account
WHERE account_status = 'CLOSED'
  AND (
      actual_balance <> 0
      OR available_balance <> 0
  );


-- ============================================================================
-- [6/12] ACCOUNT CLOSED DATE CHECK
-- ============================================================================
-- CLOSED accounts require closed_date.
-- Non-CLOSED accounts must not have closed_date.
-- ============================================================================

\echo ''
\echo '[6/12] ACCOUNT CLOSED DATE CHECK'

SELECT COUNT(*) AS invalid_rows
FROM account
WHERE
    (
        account_status = 'CLOSED'
        AND closed_date IS NULL
    )
    OR
    (
        account_status <> 'CLOSED'
        AND closed_date IS NOT NULL
    );


-- ============================================================================
-- [7/12] CUSTOMER LIFECYCLE EVENT CHECK
-- ============================================================================
-- Every customer must have at least one OCC lifecycle transaction.
--
-- Previously this joined transaction_history to account on account_number
-- to reach OCC rows — but OCC rows always have account_number = NULL, and
-- NULL never equals anything in an equijoin, so that join could never
-- match a single OCC row for any customer. This check reported every
-- customer as invalid, silently, since a nonzero invalid_rows count does
-- not itself abort the script. Fixed now that transaction_history carries
-- customer_number directly.
-- ============================================================================

\echo ''
\echo '[7/12] CUSTOMER LIFECYCLE EVENT CHECK'

SELECT COUNT(*) AS invalid_rows
FROM customer c
WHERE NOT EXISTS (
    SELECT 1
    FROM transaction_history t
    WHERE t.sort_code = c.sort_code
      AND t.customer_number = c.customer_number
      AND t.transaction_type = 'OCC'
);


-- ============================================================================
-- [8/12] TRANSACTION AMOUNT RULE CHECK
-- ============================================================================
-- Financial transactions must have a positive amount.
-- Lifecycle events must have zero amount.
-- ============================================================================

\echo ''
\echo '[8/12] TRANSACTION AMOUNT RULE CHECK'

SELECT COUNT(*) AS invalid_rows
FROM transaction_history
WHERE
    (
        transaction_type IN ('CREDIT', 'DEBIT')
        AND transaction_amount <= 0
    )
    OR
    (
        transaction_type NOT IN ('CREDIT', 'DEBIT')
        AND transaction_amount <> 0
    );


-- ============================================================================
-- [9/12] LOAN/MORTGAGE BALANCE SIGN CHECK
-- ============================================================================
-- Non-CLOSED LOAN and MORTGAGE accounts are liabilities and must carry
-- a negative or zero balance.
-- ============================================================================

\echo ''
\echo '[9/12] LOAN/MORTGAGE BALANCE SIGN CHECK'

SELECT COUNT(*) AS invalid_rows
FROM account
WHERE account_type IN ('LOAN', 'MORTGAGE')
  AND account_status <> 'CLOSED'
  AND (
      actual_balance > 0
      OR available_balance > 0
  );


-- ============================================================================
-- [10/12] ACCOUNT OPENED DATE VS CUSTOMER CREATED DATE CHECK
-- ============================================================================
-- An account cannot open before the customer relationship that owns it
-- was created.
-- ============================================================================

\echo ''
\echo '[10/12] ACCOUNT OPENED DATE VS CUSTOMER CREATED DATE CHECK'

SELECT COUNT(*) AS invalid_rows
FROM account a
JOIN customer c
    ON a.sort_code = c.sort_code
   AND a.customer_number = c.customer_number
WHERE a.opened_date < c.created_at::date;


-- ============================================================================
-- [11/12] OCC EVENT ORDERING CHECK
-- ============================================================================
-- A customer's OCC (relationship created) event must precede every other
-- event recorded for that customer, including account-level events on
-- accounts they own.
-- ============================================================================

\echo ''
\echo '[11/12] OCC EVENT ORDERING CHECK'

SELECT COUNT(*) AS invalid_rows
FROM customer c
WHERE EXISTS (
    SELECT 1
    FROM transaction_history t
    WHERE t.sort_code = c.sort_code
      AND t.customer_number = c.customer_number
      AND t.transaction_type <> 'OCC'
      AND t.transaction_timestamp < (
          SELECT MIN(occ.transaction_timestamp)
          FROM transaction_history occ
          WHERE occ.sort_code = c.sort_code
            AND occ.customer_number = c.customer_number
            AND occ.transaction_type = 'OCC'
      )
);


-- ============================================================================
-- [12/12] PENDING CUSTOMER ACCOUNT CHECK
-- ============================================================================
-- PENDING customers have not completed onboarding and must have zero
-- accounts.
-- ============================================================================

\echo ''
\echo '[12/12] PENDING CUSTOMER ACCOUNT CHECK'

SELECT COUNT(*) AS invalid_rows
FROM customer c
WHERE c.customer_status = 'PENDING'
  AND EXISTS (
      SELECT 1
      FROM account a
      WHERE a.sort_code = c.sort_code
        AND a.customer_number = c.customer_number
  );


-- ============================================================================
-- COMPLETION
-- ============================================================================

\echo ''
\echo '============================================================'
\echo 'BANKDB DATA VERIFICATION COMPLETED'
\echo '============================================================'
\echo ''
\echo 'Expected result: all invalid_rows values should be 0.'

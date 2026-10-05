# test_api.py Test Case Matrix

This document contains the recommended manual test cases for the current banking inbox pipeline.

Assumptions from the current bankdb sample data:
- Ruth: email `ruth.griffiths.1000000001@examplebank.com`, customer `1000000001`, account `10000001`
- Ricky: email `ricky.barker.1000000002@examplebank.com`, customer `1000000002`, accounts include `10000002`, `10000003`, `10000004`, `10000005`
- Sort code: `123456`

Run each command from:
`C:\Users\Neeraj\Projects\inbox-agent`

## A. Identity and account-security tests

### TC01 — Correct email + correct customer + correct account
Expected:
- identity: `customer_number_match`
- `identity_eligible`: `true`
- account ownership: `true`
- balance lookup occurs
- routing: `autonomous`

```powershell
python test_api.py --email "ricky.barker.1000000002@examplebank.com" --customer-number "1000000002" --account-number "10000002" --request "What is the balance of this account?"
```

### TC02 — Correct email + correct customer + no account number
Tests the multiple-account customer path.

Expected:
- identity verified
- all verified customer accounts may be used for a balance enquiry
- routing: `autonomous`

```powershell
python test_api.py --email "ricky.barker.1000000002@examplebank.com" --customer-number "1000000002" --request "What is the balance of all my accounts?"
```

### TC03 — Correct email + correct customer + different valid account
Expected:
- identity verified
- account belongs to customer
- balance for account `10000003`
- routing: `autonomous`

```powershell
python test_api.py --email "ricky.barker.1000000002@examplebank.com" --customer-number "1000000002" --account-number "10000003" --request "Please tell me the balance of account 10000003."
```

### TC04 — Correct email + WRONG customer number
Expected:
- `identity_status`: `customer_number_mismatch`
- `identity_eligible`: `false`
- no live facts
- no normal draft generation
- routing: `None`
- deterministic identity-failure reply

```powershell
python test_api.py --email "ricky.barker.1000000002@examplebank.com" --customer-number "1000000001" --account-number "10000002" --request "What is the balance of this account?"
```

### TC05 — Correct email + valid account number + WRONG customer number
This is important because both identifiers are supplied.

Expected:
- customer-number mismatch must not be silently overridden by the valid account number
- identity blocked
- no live banking data disclosed

```powershell
python test_api.py --email "ricky.barker.1000000002@examplebank.com" --customer-number "1000000001" --account-number "10000002" --request "What is the balance of this account?"
```

### TC06 — Correct email + account number, customer number omitted
Expected:
- account number resolves the customer
- identity succeeds
- account ownership succeeds
- balance returned

```powershell
python test_api.py --email "ricky.barker.1000000002@examplebank.com" --account-number "10000002" --request "What is the balance of this account?"
```

Note: the current `test_api.py` requires `--customer-number`, so this case requires making that CLI argument optional. See the change request at the end of this document.

### TC07 — Correct email + account number belonging to another customer
Use Ruth's account with Ricky's email.

Expected:
- account exists
- account is not owned by the email-linked customer
- identity blocked
- no balance disclosed

```powershell
python test_api.py --email "ricky.barker.1000000002@examplebank.com" --customer-number "1000000002" --account-number "10000001" --request "What is the balance of this account?"
```

### TC08 — Correct email + nonexistent account number
Expected:
- identity/account validation blocks the request
- no balance lookup for a nonexistent account
- no fabricated balance

```powershell
python test_api.py --email "ricky.barker.1000000002@examplebank.com" --customer-number "1000000002" --account-number "99999999" --request "What is the balance of this account?"
```

## B. Email-registration tests

### TC09 — Unregistered email + plausible customer number
Expected:
- `identity_status`: `email_not_registered`
- `identity_eligible`: `false`
- no banking data
- no live facts

```powershell
python test_api.py --email "unknown.person@examplebank.com" --customer-number "1000000002" --account-number "10000002" --request "What is the balance of this account?"
```

Important: the current `test_api.py` performs a pre-check requiring the email/customer combination to exist. Therefore TC09 will currently stop in the test harness before reaching the application identity gate. For a true application test, the pre-check must be changed so it does not reject intentionally invalid identity scenarios.

## C. Customer-number tests

### TC10 — Correct email + customer number, no account
Single-customer customer-number verification.

Expected:
- `customer_number_match`
- identity succeeds

```powershell
python test_api.py --email "ruth.griffiths.1000000001@examplebank.com" --customer-number "1000000001" --request "What is my account status?"
```

### TC11 — Correct email + customer number from another customer
Expected:
- mismatch
- identity blocked

```powershell
python test_api.py --email "ruth.griffiths.1000000001@examplebank.com" --customer-number "1000000002" --request "What is my account status?"
```

## D. Balance enquiry tests

### TC12 — Balance of a specific account
Expected:
- live account lookup
- actual/available balance included
- autonomous

```powershell
python test_api.py --email "ricky.barker.1000000002@examplebank.com" --customer-number "1000000002" --account-number "10000002" --request "What is the balance of this account?"
```

### TC13 — Balance of all customer accounts
Expected:
- all accounts belonging to verified customer considered
- autonomous

```powershell
python test_api.py --email "ricky.barker.1000000002@examplebank.com" --customer-number "1000000002" --request "Please tell me the balance of every account I have."
```

### TC14 — Balance request using natural wording
Tests classification robustness.

```powershell
python test_api.py --email "ricky.barker.1000000002@examplebank.com" --customer-number "1000000002" --account-number "10000002" --request "How much money do I currently have in this account?"
```

## E. Account-status / transaction tests

### TC15 — Account status enquiry
Expected:
- classification: `account_status_inquiry`
- live account facts
- routing according to the existing Phase 3 account-status policy

```powershell
python test_api.py --email "ricky.barker.1000000002@examplebank.com" --customer-number "1000000002" --account-number "10000002" --request "Is this account currently active?"
```

### TC16 — Why is my account not working?
Tests whether classification extracts a useful account-related request.

```powershell
python test_api.py --email "ricky.barker.1000000002@examplebank.com" --customer-number "1000000002" --account-number "10000002" --request "Why is my account not working?"
```

### TC17 — Declined transaction
Requires a transaction/account in bankdb that can produce a declined result.

```powershell
python test_api.py --email "ricky.barker.1000000002@examplebank.com" --customer-number "1000000002" --account-number "10000002" --request "Why was my transaction declined?"
```

Expected:
- `declined_transaction`
- live decline reason if available
- routing follows the existing Phase 3 policy

## F. Application tests

### TC18 — Application status
Requires a customer/application record supported by the current bankdb schema.

```powershell
python test_api.py --email "ruth.griffiths.1000000001@examplebank.com" --customer-number "1000000001" --request "What is the status of my application?"
```

Expected:
- `application_status_inquiry`
- verified customer used for live lookup
- autonomous if the existing routing policy permits it

## G. Fraud / escalation tests

### TC19 — Fraud report
Expected:
- classification: `fraud_report`
- identity should be handled according to the current identity policy
- routing should follow the existing fraud escalation rule

```powershell
python test_api.py --email "ricky.barker.1000000002@examplebank.com" --customer-number "1000000002" --request "I think there is a fraudulent transaction on my account."
```

Expected routing: `escalate` under the existing Phase 3 policy.

### TC20 — Unknown / unclear banking request
Tests fallback behavior.

```powershell
python test_api.py --email "ricky.barker.1000000002@examplebank.com" --customer-number "1000000002" --request "I need help with something on my account."
```

Expected:
- classification may be an appropriate known category or `unknown`
- if category is unknown, routing should follow the existing fallback escalation policy

## H. Regression tests for routing policy

### TC21 — Invalid account reference
This is specifically important because the Phase 3 policy says an invalid account reference remains autonomous.

```powershell
python test_api.py --email "ricky.barker.1000000002@examplebank.com" --customer-number "1000000002" --account-number "99999999" --request "I entered the wrong account number. Please tell me what happened."
```

Do not use this case to test an identity failure. The customer identity must be valid so that the existing `invalid_account_reference` routing rule can be exercised.

Expected routing under the existing policy:
- `tier`: `autonomous`

## I. Classification robustness

### TC22 — Customer number in prose
```powershell
python test_api.py --email "ricky.barker.1000000002@examplebank.com" --customer-number "1000000002" --request "My customer number is 1000000002. Can you tell me my account balances?"
```

### TC23 — Account number in prose
```powershell
python test_api.py --email "ricky.barker.1000000002@examplebank.com" --customer-number "1000000002" --request "Could you check account number 10000002 and tell me its current balance?"
```

### TC24 — Both identifiers in prose
```powershell
python test_api.py --email "ricky.barker.1000000002@examplebank.com" --customer-number "1000000002" --account-number "10000002" --request "Customer 1000000002 has asked for the balance of account 10000002."
```

## J. What to record for every test

For each run, record at minimum:

```text
Test case:
Classification:
Extracted customer number:
Extracted account number:
Identity status:
Identity eligible:
Account exists:
Account matches customer:
Live facts:
Draft reply:
Routing tier:
Routing reason:
```

For identity-failure tests, verify especially:

```text
identity_eligible = false
live_facts = {}
routing = None
```

That confirms the security gate stops the pipeline before live banking data is retrieved.

# Important changes needed before the full matrix can run

The current `test_api.py` was deliberately written to require a valid email/customer-number combination before running the pipeline. That is useful for the happy path but prevents negative identity tests such as:
- unregistered email
- wrong customer number
- account-number-only resolution
- account not owned by customer

Also, the current CLI requires `--customer-number`, which prevents testing the supported account-number-only identity path.

Therefore, before running the complete matrix, `test_api.py` should be changed to:

1. Make `--customer-number` optional.
2. Do not pre-reject invalid email/customer combinations.
3. Let `process_message()` be the authority for identity resolution.
4. Keep the database pre-check only as an optional convenience/display check.
5. Allow `--account-number` without `--customer-number`.

The next version of `test_api.py` should therefore be a genuine pipeline test harness rather than a valid-input-only harness.

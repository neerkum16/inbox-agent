# Create Account — Component Analysis
## CICS Banking Sample Application

> **Transaction:** `OCAC` (triggered from `OMEN` Menu Option 4)
> **Components:** `BNK1CAM` (BMS Map) · `BNK1CAC` (Screen Handler) · `CREACC` (Backend) · `INQCUST` (Customer Inquiry) · `INQACCCU` (Account Count)

---

## Table of Contents

1. [BNK1CAM — BMS Map (BNK1CA)](#1-bnk1cam--bms-map-bnk1ca)
2. [BNK1CAC — Create Account Screen Handler](#2-bnk1cac--create-account-screen-handler)
3. [CREACC — Create Account Backend](#3-creacc--create-account-backend)
4. [INQCUST — Inquire Customer](#4-inqcust--inquire-customer)
5. [INQACCCU — Inquire Accounts for Customer](#5-inqacccu--inquire-accounts-for-customer)
6. [Cross-Component Call Chain Summary](#6-cross-component-call-chain-summary)
7. [Fail Code Reference](#7-fail-code-reference)
8. [Key Differences vs Create Customer Flow](#8-key-differences-vs-create-customer-flow)

---

## 1. BNK1CAM — BMS Map (BNK1CA)

**Mapset:** `BNK1CAM` | **Map:** `BNK1CA` | **Source:** `BNK1CAM.bms`

---

### 1.1 Map Identity

| Attribute | Value |
|-----------|-------|
| Mapset Name | `BNK1CAM` |
| Map Name | `BNK1CA` |
| Terminal Type | 3270-2 |
| Mode | INOUT |
| Language | COBOL |
| Storage | AUTO |
| Control | FREEKB |
| Extended Attributes | COLOR, HILIGHT, OUTLINE, PS, SOSI |
| Title | `CICS Banking Sample Application - Create Account.` (Red, Row 1) |
| Instruction | `Please provide the requested information and press Enter.` (Turquoise, Row 3) |

---

### 1.2 Map Fields — Screen Layout

| Row | Field Name | Position | Length | Attributes | Color | Description |
|-----|-----------|----------|--------|-----------|-------|-------------|
| 1 | *(literal)* | (1,1) | 7 | PROT | Blue | Map ID label `BNK1CA` |
| 1 | `COMPANY` | (1,18) | 61 | PROT | Red | Title banner |
| 6 | `CUSTNO` | (6,23) | 10 | NUM, FSET | Green + Underline | **Input:** Customer Number |
| 7 | `ACCTYP` | (7,23) | 8 | UNPROT, FSET | Green + Underline | **Input:** Account Type |
| 8 | `INTRT` | (8,23) | 7 | NUM, UNPROT, FSET | Green + Underline | **Input:** Interest Rate (default `0000.00`) |
| 9 | `OVERDR` | (9,23) | 8 | NUM, UNPROT, FSET | Green + Underline | **Input:** Overdraft Limit (default `0`, right-justified) |
| 13 | `ACCNO` | (13,23) | 8 | PROT, FSET | Neutral | **Output:** Account Number |
| 14 | `SRTCD` | (14,23) | 6 | PROT, FSET | Neutral | **Output:** Sort Code |
| 15 | `OPENDD` | (15,23) | 2 | PROT, FSET | Neutral | **Output:** Opened Date — Day |
| 15 | `OPENMM` | (15,28) | 2 | PROT, FSET | Neutral | **Output:** Opened Date — Month |
| 15 | `OPENYY` | (15,33) | 4 | PROT, FSET | Neutral | **Output:** Opened Date — Year |
| 16 | `LSTMDD` | (16,23) | 2 | PROT, FSET | Neutral | **Output:** Last Stmt Date — Day |
| 16 | `LSTMMM` | (16,28) | 2 | PROT, FSET | Neutral | **Output:** Last Stmt Date — Month |
| 16 | `LSTMYY` | (16,33) | 4 | PROT, FSET | Neutral | **Output:** Last Stmt Date — Year |
| 17 | `NSTMTDD` | (17,23) | 2 | PROT, FSET | Neutral | **Output:** Next Stmt Date — Day |
| 17 | `NSTMTMM` | (17,28) | 2 | PROT, FSET | Neutral | **Output:** Next Stmt Date — Month |
| 17 | `NSTMTYY` | (17,33) | 4 | PROT, FSET | Neutral | **Output:** Next Stmt Date — Year |
| 18 | `AVAIL` | (18,22) | 14 | PROT, FSET | Neutral | **Output:** Available Balance |
| 19 | `ACTBAL` | (19,22) | 14 | PROT, FSET | Neutral | **Output:** Actual Balance |
| 23 | `MESSAGE` | (23,1) | 79 | PROT, BRT | Yellow | **Output:** User/error messages |
| 24 | *(literal)* | (24,1) | 20 | PROT | Blue | `F3=Exit   F12=Cancel` |
| 24 | `DUMMY` | (24,79) | 1 | DRK, PROT, FSET | — | Hidden MDT-forcing field |

**Notes:**
- Input fields span rows 6–9 (top section). Output fields span rows 13–19 (results section). Message at row 23.
- Date fields use `/` separator literals between DD, MM, YYYY positions.
- `CUSTNO` and `INTRT` are NUM-protected on input (numeric-only keyboard shift). `ACCTYP` is alphanumeric.
- `OVERDR` has `JUSTIFY=RIGHT` — amount right-aligns in the field.

**Function Key Legend (Row 24):**

| Key | Action |
|-----|--------|
| F3 | Exit — return to main menu (`OMEN`) |
| F12 | Cancel — send "Session Ended" termination message |

---

## 2. BNK1CAC — Create Account Screen Handler

**Program ID:** `BNK1CAC` | **Transaction ID:** `OCAC`

---

### 2.1 Validations (EDIT-DATA Section)

All checks short-circuit via `GO TO ED999` on failure, setting `VALID-DATA-SW = 'N'` and populating `MESSAGEO`.

| # | Field | Check | Error Message |
|---|-------|-------|---------------|
| 1 | `CUSTNOI` — presence | `BIF DEEDIT` applied; length < 1 or value = `__________` | `Please enter a 10 digit Customer Number` |
| 2 | `CUSTNOI` — numeric | `NOT NUMERIC` check after DEEDIT | `Please enter a numeric Customer number` |
| 3 | `ACCTYPI` — presence | Length < 1 or value = `________` | `Account Type should be ISA,CURRENT,LOAN,SAVING or MORTGAGE` |
| 4 | `ACCTYPI` — value (EVALUATE) | Must be one of: `ISA`, `CURRENT`, `LOAN`, `SAVING`, `MORTGAGE` (case-insensitive; underscore-padded BMS variants handled) | `Account Type should be ISA,CURRENT,LOAN,SAVING or MORTGAGE` |
| 5 | `INTRTI` — presence | Length = 0 | `Please supply a numeric interest rate` |
| 6 | `INTRTI` — character set | Only digits `0–9`, `.`, `-`, `+`, and spaces allowed (tallied via INSPECT) | `Please supply a numeric interest rate` |
| 7 | `INTRTI` — decimal point count | More than one `.` in field | `Use one decimal point for interest rate only` |
| 8 | `INTRTI` — decimal places | More than 2 numeric digits after the decimal point | `Only up to two decimal places are supported` |
| 9 | `INTRTI` — negative | `FUNCTION NUMVAL(INTRTI) < 0` | `Please supply a zero or positive interest rate` |
| 10 | `INTRTI` — upper bound | `FUNCTION NUMVAL(INTRTI) > 9999.99` | `Please supply an interest rate less than 9999.99%` |
| 11 | `OVERDRI` — character set | Trailing spaces trimmed via REVERSE/INSPECT; only digits `0–9` allowed | `Overdraft Limit must be numeric positive int` |
| 12 | `OVERDRI` — numeric (after DEEDIT) | `BIF DEEDIT` applied; `NOT NUMERIC` check | `The Overdraft Limit must be numeric` |
| 13 | `OVERDRI` — optional zero default | Length < 1, `________`, or spaces → silently default to 0 | *(no error — defaults to zero)* |
| 14 | All mandatory fields — catch-all | `CUSTNOL < 1 OR ACCTYPL < 1` | `Missing expected data.` |

**Account Type Normalisation (EVALUATE in EDIT-DATA):**

BMS fills unused field positions with underscores. The EVALUATE normalises all case and underscore variants before passing to CREACC:

| Input Variants Accepted | Normalised Value Stored |
|------------------------|------------------------|
| `ISA_____`, `isa_____`, `ISA     `, `isa     ` | `ISA     ` |
| `CURRENT_`, `current_`, `CURRENT `, `current ` | `CURRENT ` |
| `LOAN____`, `loan____`, `LOAN    `, `loan    ` | `LOAN    ` |
| `SAVING__`, `saving__`, `SAVING  `, `saving  ` | `SAVING  ` |
| `MORTGAGE`, `mortgage` | `MORTGAGE` |

---

### 2.2 Processing

- **First time through (EIBCALEN = 0):** Initialises `BNK1CAO` to LOW-VALUES, sets cursor to `CUSTNO` field (position -1), sends map `BNK1CA` (mapset `BNK1CAM`) with ERASE.

- **ENTER → PROCESS-MAP:**
  1. `RECEIVE-MAP`: Receives map `BNK1CA` into `BNK1CAI`. Non-normal RESP → ABEND via `ABNDPROC`.
  2. `EDIT-DATA`: Runs all 14 validations above.
  3. If `VALID-DATA`, performs `CRE-ACC-DATA`:
     - Initialises `SUBPGM-PARMS`, sets eyecatcher `'ACCT'`, `SUBPGM-SUCCESS = 'N'`.
     - Moves screen fields: `CUSTNOI → SUBPGM-CUSTNO`, `ACCTYPI → SUBPGM-ACC-TYPE`, `OVERDRI → SUBPGM-OVERDR-LIM`.
     - Converts `INTRTI` via `FUNCTION NUMVAL` to COMP-1; moves to `SUBPGM-INT-RT`.
     - Zeros all balance, date, sort code, and account number fields in SUBPGM-PARMS.
     - Issues `EXEC CICS LINK PROGRAM('CREACC') COMMAREA(SUBPGM-PARMS) SYNCONRETURN`.
     - Non-normal LINK RESP → ABEND via `ABNDPROC`.
  4. Inspects `SUBPGM-SUCCESS` on return:
     - Fail codes `1`–`9`, `A` → specific error message (see Section 7).
     - `'Y'` → "The Account has been successfully created." Maps output fields: sort code, account number, opened date (split DD/MM/YYYY), next/last statement dates (split), available balance, actual balance.
  5. Always echoes `CUSTNOO`, `ACCTYPO`, `INTRTO`, `OVERDRO` from SUBPGM-PARMS back to screen.
  6. Sets `SEND-DATAONLY-ALARM`, performs `SEND-MAP`.

- **PF3:** Returns to `OMEN` (main menu) via `EXEC CICS RETURN TRANSID('OMEN') IMMEDIATE`.
- **PF12 / AID:** Sends "Session Ended" text via `SEND-TERMINATION-MSG`; issues plain `EXEC CICS RETURN`.
- **CLEAR:** Issues `EXEC CICS SEND CONTROL ERASE FREEKB`, then plain `EXEC CICS RETURN`.
- **PA1/PA2/PA3:** `CONTINUE` — no action.
- **Any other key:** Sets `MESSAGEO = 'Invalid key pressed.'`, `SEND-DATAONLY-ALARM`.
- **COMMAREA on RETURN TRANSID('OCAC'):** If `EIBCALEN ≠ 0`, copies SUBPGM-PARMS fields back into `WS-COMM-AREA`; otherwise initialises `WS-COMM-AREA`. Returns `LENGTH(32)`.
- **Abend handling:** All CICS failures populate `ABNDINFO-REC` (APPLID, TASKNO, TRANID, date/time via `POPULATE-TIME-DATE`, RESP/RESP2, freeform message), link to `ABNDPROC`, then `EXEC CICS ABEND ABCODE('HBNK') NODUMP`.

---

### 2.3 Files / Database / CICS Storage

| Resource | Type | Usage |
|----------|------|-------|
| `BNK1CA` / `BNK1CAM` | CICS BMS Map | Input (`RECEIVE MAP`) and Output (`SEND MAP`) |
| `DFHCOMMAREA` (32 bytes) | CICS COMMAREA | Input from `OMEN` or prior `OCAC` cycle; fields: `COMM-CUSTNO`, `COMM-ACCTYPE`, `COMM-INTRT`, `COMM-OVERDR` |
| `WS-COMM-AREA` (32 bytes) | CICS COMMAREA | Passed on `RETURN TRANSID('OCAC')` for pseudo-conversational loop |
| `SUBPGM-PARMS` (COPY CREACC) | CICS COMMAREA | Passed to / received from `CREACC` via `EXEC CICS LINK` |
| `ABNDINFO-REC` (COPY ABNDINFO) | CICS COMMAREA | Passed to `ABNDPROC` on any CICS failure |
| No VSAM files or DB2 tables | — | All data access delegated to `CREACC` |

---

### 2.4 Programs Called by BNK1CAC

| Program | Call Method | Purpose |
|---------|-------------|---------|
| `CREACC` | `EXEC CICS LINK … SYNCONRETURN` | Create the account record (backend) |
| `ABNDPROC` | `EXEC CICS LINK … COMMAREA(ABNDINFO-REC)` | Abend handler — logs and terminates on any CICS failure |

---

## 3. CREACC — Create Account Backend

**Program ID:** `CREACC` | **Invocation:** `EXEC CICS LINK` from `BNK1CAC`

---

### 3.1 Validations

| # | Check | Logic | Fail Code |
|---|-------|-------|-----------|
| 1 | **Customer existence** | Links to `INQCUST`; if EIBRESP ≠ NORMAL or `INQCUST-INQ-SUCCESS ≠ 'Y'` | `1` → immediate RETURN |
| 2 | **Account count error** | Links to `INQACCCU`; if CICS LINK fails or `COMM-SUCCESS IN INQACCCU-COMMAREA = 'N'` | `9` → immediate RETURN |
| 3 | **Maximum accounts per customer** | `NUMBER-OF-ACCOUNTS IN INQACCCU-COMMAREA > 9` | `8` → immediate RETURN |
| 4 | **Account type re-validation** | `ACCOUNT-TYPE-CHECK` section; re-validates `COMM-ACC-TYPE` against `ISA`, `MORTGAGE`, `SAVING`, `CURRENT`, `LOAN` | `A` → immediate RETURN |
| 5 | **ENQ failure** | `EXEC CICS ENQ RESOURCE('CBSAACCT' + sortcode)` fails | `3` → immediate RETURN |
| 6 | **DB2 CONTROL SELECT failure** (ACCOUNT-LAST) | `SQLCODE ≠ 0` on `SELECT FROM CONTROL` for last account number | Abend `HNCS` via `ABNDPROC` |
| 7 | **DB2 CONTROL UPDATE failure** (ACCOUNT-LAST) | `SQLCODE ≠ 0` on `UPDATE CONTROL` to increment last account number | Abend `HNCS` via `ABNDPROC` |
| 8 | **DB2 CONTROL SELECT failure** (ACCOUNT-COUNT) | `SQLCODE ≠ 0` on `SELECT FROM CONTROL` for account count | Abend `HNCS` via `ABNDPROC` |
| 9 | **DB2 CONTROL UPDATE failure** (ACCOUNT-COUNT) | `SQLCODE ≠ 0` on `UPDATE CONTROL` to increment account count | Abend `HNCS` via `ABNDPROC` |
| 10 | **DB2 ACCOUNT INSERT failure** | `SQLCODE ≠ 0` on `INSERT INTO ACCOUNT` | `7` → DEQ then RETURN |
| 11 | **DB2 PROCTRAN INSERT failure** | `SQLCODE ≠ 0` on `INSERT INTO PROCTRAN` | DEQ then Abend `HWPT` via `ABNDPROC` |
| 12 | **DEQ failure** | `EXEC CICS DEQ` returns non-normal RESP | `5` → immediate RETURN |

---

### 3.2 Processing

#### Step 1 — Customer Existence Check
```
MOVE COMM-CUSTNO → INQCUST-CUSTNO
EXEC CICS LINK PROGRAM('INQCUST') COMMAREA(INQCUST-COMMAREA)
IF EIBRESP ≠ NORMAL  OR  INQCUST-INQ-SUCCESS ≠ 'Y'
  → COMM-FAIL-CODE = '1'; RETURN
```

#### Step 2 — Account Count Check
```
CUSTOMER-ACCOUNT-COUNT section:
  MOVE COMM-CUSTNO → CUSTOMER-NUMBER IN INQACCCU-COMMAREA
  SET NUMBER-OF-ACCOUNTS = 20 (passed as capacity limit)
  EXEC CICS LINK PROGRAM('INQACCCU') COMMAREA(INQACCCU-COMMAREA) SYNCONRETURN
  IF WS-CICS-RESP ≠ NORMAL  → COMM-FAIL-CODE = '9'; RETURN
  IF COMM-SUCCESS = 'N'     → COMM-FAIL-CODE = '9'; RETURN
  IF NUMBER-OF-ACCOUNTS > 9 → COMM-FAIL-CODE = '8'; RETURN
```

#### Step 3 — Account Type Validation (ACCOUNT-TYPE-CHECK)
```
EVALUATE TRUE
  WHEN COMM-ACC-TYPE(1:3) = 'ISA'      → COMM-SUCCESS = 'Y'
  WHEN COMM-ACC-TYPE(1:8) = 'MORTGAGE' → COMM-SUCCESS = 'Y'
  WHEN COMM-ACC-TYPE(1:6) = 'SAVING'   → COMM-SUCCESS = 'Y'
  WHEN COMM-ACC-TYPE(1:7) = 'CURRENT'  → COMM-SUCCESS = 'Y'
  WHEN COMM-ACC-TYPE(1:4) = 'LOAN'     → COMM-SUCCESS = 'Y'
  WHEN OTHER → COMM-SUCCESS = 'N'; COMM-FAIL-CODE = 'A'; RETURN
```

#### Step 4 — ENQ Named Counter
```
NCS-ACC-NO-NAME = 'CBSAACCT' + SORTCODE + '  '  (16 bytes total)
EXEC CICS ENQ RESOURCE(NCS-ACC-NO-NAME) LENGTH(16)
Failure → COMM-FAIL-CODE = '3'; RETURN
```
Exclusive lock serialises account number assignment under concurrent load.

#### Step 5 — Get Next Account Number (FIND-NEXT-ACCOUNT via DB2 CONTROL table)
```
1. SELECT CONTROL_VALUE_NUM FROM CONTROL
   WHERE CONTROL_NAME = '<sortcode>-ACCOUNT-LAST'
   SQLCODE ≠ 0 → ABEND 'HNCS'

2. ADD 1 → new account number
   Assign to: COMM-NUMBER, ACCOUNT-NUMBER, NCS-ACC-NO-VALUE, HV-CONTROL-VALUE-NUM

3. UPDATE CONTROL SET CONTROL_VALUE_NUM = new value
   WHERE CONTROL_NAME = '<sortcode>-ACCOUNT-LAST'
   SQLCODE ≠ 0 → ABEND 'HNCS'

4. SELECT CONTROL_VALUE_NUM FROM CONTROL
   WHERE CONTROL_NAME = '<sortcode>-ACCOUNT-COUNT'
   SQLCODE ≠ 0 → ABEND 'HNCS'

5. ADD 1 → new account count

6. UPDATE CONTROL SET CONTROL_VALUE_NUM = new count
   WHERE CONTROL_NAME = '<sortcode>-ACCOUNT-COUNT'
   SQLCODE ≠ 0 → ABEND 'HNCS'
```

#### Step 6 — Calculate Dates (CALCULATE-DATES)
Uses `EXEC CICS ASKTIME` and `FORMATTIME DDMMYYYY`:

| Date Field | Value |
|-----------|-------|
| `ACCOUNT-OPENED` | Today's date (DD.MM.YYYY) |
| `ACCOUNT-LAST-STMT-DATE` | Today's date |
| `ACCOUNT-NEXT-STMT-DATE` | Today + 30 days (with leap year logic for February) |

**Leap year logic for February:**
```
Base: today + 28 days
Year divisible by   4? → potential leap year (+1 day)
Year divisible by 100? → century year — NOT a leap year
Year divisible by 400? → IS a leap year (+1 day)
```

#### Step 7 — Write Account Record to DB2 (WRITE-ACCOUNT-DB2)
```sql
INSERT INTO ACCOUNT (
  ACCOUNT_EYECATCHER,         -- 'ACCT'
  ACCOUNT_CUSTOMER_NUMBER,    -- COMM-CUSTNO
  ACCOUNT_SORTCODE,           -- SORTCODE copybook constant
  ACCOUNT_NUMBER,             -- new number from CONTROL table
  ACCOUNT_TYPE,               -- COMM-ACC-TYPE
  ACCOUNT_INTEREST_RATE,      -- COMM-INT-RT
  ACCOUNT_OPENED,             -- today DD.MM.YYYY
  ACCOUNT_OVERDRAFT_LIMIT,    -- COMM-OVERDR-LIM
  ACCOUNT_LAST_STATEMENT,     -- today DD.MM.YYYY
  ACCOUNT_NEXT_STATEMENT,     -- today + 30 days
  ACCOUNT_AVAILABLE_BALANCE,  -- 0 (new account)
  ACCOUNT_ACTUAL_BALANCE      -- 0 (new account)
)
```
`SQLCODE ≠ 0` → `COMM-FAIL-CODE = '7'`; DEQ named counter; RETURN.

#### Step 8 — Write PROCTRAN Audit Record (WRITE-PROCTRAN-DB2)
```sql
INSERT INTO PROCTRAN (
  PROCTRAN_EYECATCHER,   -- 'PRTR'
  PROCTRAN_SORTCODE,     -- sort code
  PROCTRAN_NUMBER,       -- new account number
  PROCTRAN_DATE,         -- today DD.MM.YYYY
  PROCTRAN_TIME,         -- HHMMSS
  PROCTRAN_REF,          -- EIBTASKN (12 digits)
  PROCTRAN_TYPE,         -- 'OCA' (Open Account)
  PROCTRAN_DESC,         -- custno(10) + acctype(8) + last_stmt(8) + next_stmt(8)
  PROCTRAN_AMOUNT        -- 0
)
```
`SQLCODE ≠ 0` → DEQ named counter; Abend `HWPT` via `ABNDPROC`.

#### Step 9 — DEQ and Return
```
EXEC CICS DEQ RESOURCE(NCS-ACC-NO-NAME) LENGTH(16)
  Failure → COMM-FAIL-CODE = '5'; RETURN

Populate return COMMAREA:
  COMM-SORTCODE     ← HV-ACCOUNT-SORTCODE
  COMM-NUMBER       ← HV-ACCOUNT-ACC-NO
  COMM-OPENED       ← opened date (DDMMYYYY packed)
  COMM-LAST-STMT-DT ← last statement date
  COMM-NEXT-STMT-DT ← next statement date
  COMM-EYECATCHER   ← 'ACCT'
  COMM-SUCCESS      ← 'Y'
  COMM-FAIL-CODE    ← ' '
```

---

### 3.3 Files / Database / CICS Storage

| Resource | Type | Mode | Notes |
|----------|------|------|-------|
| `ACCOUNT` (DB2 table) | DB2 Embedded SQL | INSERT | New account record; uses `EXEC SQL INCLUDE ACCDB2` |
| `CONTROL` (DB2 table) | DB2 Embedded SQL | SELECT + UPDATE | Two control rows: `<sortcode>-ACCOUNT-LAST` and `<sortcode>-ACCOUNT-COUNT` |
| `PROCTRAN` (DB2 table) | DB2 Embedded SQL | INSERT | Transaction audit trail — type `OCA`; uses `EXEC SQL INCLUDE PROCDB2` |
| Named Counter `CBSAACCT` + sortcode | CICS ENQ / DEQ | Exclusive lock | 16-byte resource; serialises account number assignment |
| `DFHCOMMAREA` (COPY CREACC) | CICS COMMAREA | Input / Output | From BNK1CAC; returned with account details and success/fail |
| `INQCUST-COMMAREA` (COPY INQCUST) | CICS COMMAREA | Passed to `INQCUST` | Customer existence validation |
| `INQACCCU-COMMAREA` (COPY INQACCCU) | CICS COMMAREA | Passed to `INQACCCU` | Account count for customer |
| `ABNDINFO-REC` (COPY ABNDINFO) | CICS COMMAREA | Output | Passed to `ABNDPROC` on failure |
| `SORTCODE` (COPY SORTCODE) | Working Storage | Read | Bank sort code constant |
| SQLCA | DB2 | Communication area | SQL return code checking |

---

### 3.4 Programs Called by CREACC

| Program | Call Method | Purpose |
|---------|-------------|---------|
| `INQCUST` | `EXEC CICS LINK` | Verify customer exists before creating account |
| `INQACCCU` | `EXEC CICS LINK … SYNCONRETURN` | Count existing accounts — enforces max 9 per customer |
| `ABNDPROC` | `EXEC CICS LINK … COMMAREA(ABNDINFO-REC)` | Abend handler — logs failure and terminates task |

---

## 4. INQCUST — Inquire Customer

**Program ID:** `INQCUST` | **Invocation:** `EXEC CICS LINK` from `CREACC` and `INQACCCU`

**Purpose:** Takes a customer number as input and returns the full customer record from the CUSTOMER VSAM file, or an initialised record if not found. Handles three input modes: specific number, zero (random customer), or all-nines (last customer in file).

---

### 4.1 Validations

| # | Check | Logic | Result |
|---|-------|-------|--------|
| 1 | **Customer number = 0** | Generate a random customer number from NCS range | Random lookup mode |
| 2 | **Customer number = 9999999999** | Retrieve last-used customer number via `GET-LAST-CUSTOMER-VSAM` (STARTBR/READPREV) | Last-in-file lookup |
| 3 | **VSAM NOTFND (random mode)** | Retry up to 1000 times with `GENERATE-RANDOM-CUSTOMER-AGAIN` | Retry or fail code `1` |
| 4 | **VSAM NOTFND (9999999999 mode)** | Re-read last customer via `GET-LAST-CUSTOMER-VSAM`; retry once only | Retry once |
| 5 | **VSAM NOTFND (specific number)** | Customer does not exist | `INQCUST-INQ-SUCCESS = 'N'`, fail code `1` |
| 6 | **VSAM SYSIDERR** | Retry loop up to 100 times, 3-second delay each | Continue or fall through to abend |
| 7 | **VSAM STARTBR failure** | Non-SYSIDERR, or SYSIDERR after 100 retries in `GET-LAST-CUSTOMER-VSAM` | `INQCUST-INQ-SUCCESS = 'N'`, fail code `9` |
| 8 | **VSAM READPREV failure** | Same retry / fail logic | `INQCUST-INQ-SUCCESS = 'N'`, fail code `9` |
| 9 | **VSAM ENDBR failure** | Same retry / fail logic | `INQCUST-INQ-SUCCESS = 'N'`, fail code `9` |
| 10 | **Any other non-normal RESP** | Unexplained VSAM error | ABEND `CVR1` via `ABNDPROC` |
| 11 | **VSAM RLS abends** (`AFCR`, `AFCS`, `AFCT`) | Storm Drain check; `SYNCPOINT ROLLBACK`; return failure | `INQCUST-INQ-SUCCESS = 'N'`, fail code `2` |

---

### 4.2 Processing

#### Main Flow (PREMIERE section)
```
1. Set up abend handler: EXEC CICS HANDLE ABEND LABEL(ABEND-HANDLING)
2. MOVE SORTCODE → REQUIRED-SORT-CODE
3. IF INQCUST-CUSTNO = 0
      PERFORM READ-CUSTOMER-NCS   (get highest number in use)
      PERFORM GENERATE-RANDOM-CUSTOMER
        COMPUTE RANDOM-CUSTOMER = ((NCS-CUST-NO-VALUE - 1) * FUNCTION RANDOM(EIBTASKN)) + 1
   IF INQCUST-CUSTNO = 9999999999
      PERFORM READ-CUSTOMER-NCS   (get highest number in use)
4. PERFORM READ-CUSTOMER-VSAM UNTIL EXIT-VSAM-READ = 'Y'
5. IF INQCUST-INQ-SUCCESS = 'Y'
      Move all CUSTOMER copybook fields to INQCUST COMMAREA:
        INQCUST-EYE, INQCUST-SCODE, INQCUST-CUSTNO,
        INQCUST-NAME, INQCUST-ADDR, INQCUST-DOB,
        INQCUST-CREDIT-SCORE, INQCUST-CS-REVIEW-DT
6. PERFORM GET-ME-OUT-OF-HERE (EXEC CICS RETURN)
```

#### READ-CUSTOMER-VSAM section
```
EXEC CICS READ FILE('CUSTOMER') RIDFLD(CUSTOMER-KY) INTO(OUTPUT-DATA)
  Normal   → EXIT-VSAM-READ = 'Y', INQCUST-INQ-SUCCESS = 'Y'
  SYSIDERR → retry loop (up to 100 × 3-second delays)
  NOTFND + CUSTNO=0      → try GENERATE-RANDOM-CUSTOMER-AGAIN (up to 1000 retries)
  NOTFND + CUSTNO=9s (first time) → GET-LAST-CUSTOMER-VSAM, retry once
  NOTFND (specific)      → EXIT-VSAM-READ='Y', INQCUST-INQ-SUCCESS='N', fail code '1'
  Any other non-normal   → ABEND 'CVR1' via ABNDPROC
```

#### GET-LAST-CUSTOMER-VSAM section (used for 9999999999 and NCS reads)
```
EXEC CICS STARTBR FILE('CUSTOMER') RIDFLD(HIGH-VALUES)  [SYSIDERR retry ×100]
EXEC CICS READPREV FILE('CUSTOMER') RIDFLD(CUSTOMER-KY2) [SYSIDERR retry ×100]
EXEC CICS ENDBR FILE('CUSTOMER')                         [SYSIDERR retry ×100]
  Any failure → INQCUST-INQ-SUCCESS='N', fail code '9'
  Success     → returns last CUSTOMER-NUMBER in OUTPUT-DATA
```

#### ABEND-HANDLING section
```
EXEC CICS ASSIGN ABCODE(MY-ABEND-CODE)
EVALUATE MY-ABEND-CODE
  WHEN 'AFCR' / 'AFCS' / 'AFCT'  (VSAM RLS abends):
    → SYNCPOINT ROLLBACK
    → INQCUST-INQ-SUCCESS='N', fail code '2'
    → EXEC CICS RETURN (graceful return, no abend)
  WHEN OTHER (not storm drain):
    → EXEC CICS ABEND ABCODE(MY-ABEND-CODE) NODUMP
```

---

### 4.3 Files / Database / CICS Storage

| Resource | Type | Mode | Notes |
|----------|------|------|-------|
| `CUSTOMER` (VSAM KSDS) | CICS File | READ | Primary lookup by sort code + customer number key |
| `CUSTOMER` (VSAM KSDS) | CICS File | STARTBR + READPREV + ENDBR | Backward browse to find last/highest customer number |
| `DFHCOMMAREA` (COPY INQCUST) | CICS COMMAREA | Input / Output | `INQCUST-CUSTNO` in; full customer fields + success/fail flags out |
| `SORTCODE` (COPY SORTCODE) | Local Storage | Read | Bank sort code constant (in LOCAL-STORAGE) |
| `OUTPUT-DATA` (COPY CUSTOMER) | Local Storage | Working | Customer record buffer |
| `ABNDINFO-REC` (COPY ABNDINFO) | Working Storage | Output | Passed to `ABNDPROC` on failure |
| No DB2 tables | — | — | Purely VSAM-based |

---

### 4.4 Programs Called by INQCUST

| Program | Call Method | Purpose |
|---------|-------------|---------|
| `ABNDPROC` | `EXEC CICS LINK … COMMAREA(ABNDINFO-REC)` | Abend handler — logs VSAM failure details and terminates |

---

### 4.5 INQCUST Fail Code Reference

| Fail Code | Meaning |
|-----------|---------|
| `0` | Success (default initial value) |
| `1` | Customer not found in VSAM file (or random retry exhausted) |
| `2` | VSAM RLS storm-drain abend handled — returned gracefully |
| `9` | VSAM STARTBR / READPREV / ENDBR failure in `GET-LAST-CUSTOMER-VSAM` |

---

## 5. INQACCCU — Inquire Accounts for Customer

**Program ID:** `INQACCCU` | **Invocation:** `EXEC CICS LINK` from `CREACC`

**Purpose:** Takes a customer number and returns all associated account records from the DB2 ACCOUNT table (up to 20 rows). Also validates the customer exists first by linking to `INQCUST`. Used by `CREACC` specifically to count how many accounts a customer already holds before creating a new one.

---

### 5.1 Validations

| # | Check | Logic | Result |
|---|-------|-------|--------|
| 1 | **Customer number = 0** | Guard in `CUSTOMER-CHECK` — skip INQCUST call | `CUSTOMER-FOUND='N'`, fail code `1`, immediate RETURN |
| 2 | **Customer number = 9999999999** | Same guard | `CUSTOMER-FOUND='N'`, fail code `1`, immediate RETURN |
| 3 | **Customer not found** | `INQCUST-INQ-SUCCESS ≠ 'Y'` after INQCUST link | `CUSTOMER-FOUND='N'`, `COMM-FAIL-CODE='1'`, immediate RETURN |
| 4 | **DB2 cursor OPEN failure** | `SQLCODE ≠ 0` on `OPEN ACC-CURSOR` | `COMM-FAIL-CODE='2'`; SYNCPOINT ROLLBACK; RETURN |
| 5 | **DB2 FETCH failure** | `SQLCODE ≠ 0` (not +100) during FETCH loop | `COMM-FAIL-CODE='3'`; SYNCPOINT ROLLBACK; RETURN |
| 6 | **DB2 cursor CLOSE failure** | `SQLCODE ≠ 0` on `CLOSE ACC-CURSOR` | `COMM-FAIL-CODE='4'`; SYNCPOINT ROLLBACK; RETURN |
| 7 | **DB2 deadlock** (`AD2Z` abend) | Caught in ABEND-HANDLING; SQLCODE and SQLSTATE logged | Diagnostics displayed; abend re-issued |
| 8 | **VSAM RLS abends** (`AFCR`, `AFCS`, `AFCT`) | Storm Drain check; SYNCPOINT ROLLBACK | `COMM-SUCCESS='N'`; RETURN (graceful) |
| 9 | **DB2 Storm Drain** (`SQLCODE=923`) | `CHECK-FOR-STORM-DRAIN-DB2` section | Logged; processing continues with failure path |

---

### 5.2 Processing

#### Main Flow (PREMIERE section)
```
1. MOVE 'N' TO COMM-SUCCESS; MOVE '0' TO COMM-FAIL-CODE
2. Set up abend handler: EXEC CICS HANDLE ABEND LABEL(ABEND-HANDLING)
3. PERFORM CUSTOMER-CHECK
   IF CUSTOMER-FOUND = 'N' → COMM-FAIL-CODE='1'; RETURN
4. PERFORM READ-ACCOUNT-DB2
5. PERFORM GET-ME-OUT-OF-HERE
```

#### CUSTOMER-CHECK section
```
IF CUSTOMER-NUMBER = 0 or 9999999999 → CUSTOMER-FOUND='N'; RETURN
INITIALIZE INQCUST-COMMAREA
MOVE CUSTOMER-NUMBER → INQCUST-CUSTNO
EXEC CICS LINK PROGRAM('INQCUST ') COMMAREA(INQCUST-COMMAREA)
IF INQCUST-INQ-SUCCESS = 'Y' → CUSTOMER-FOUND = 'Y'
ELSE                         → CUSTOMER-FOUND = 'N'; NUMBER-OF-ACCOUNTS = 0
```

#### READ-ACCOUNT-DB2 section
```
MOVE CUSTOMER-NUMBER → HV-ACCOUNT-CUST-NO
MOVE SORTCODE        → HV-ACCOUNT-SORTCODE

EXEC SQL OPEN ACC-CURSOR
  (SELECT all ACCOUNT columns WHERE ACCOUNT_CUSTOMER_NUMBER = :custno
                                AND ACCOUNT_SORTCODE = :sortcode)
  SQLCODE ≠ 0 → CHECK-FOR-STORM-DRAIN-DB2; SYNCPOINT ROLLBACK; RETURN

PERFORM FETCH-DATA
  Loop: EXEC SQL FETCH ACC-CURSOR INTO :host-variables
    SQLCODE = +100 (no more rows) → COMM-SUCCESS='Y'; exit loop
    SQLCODE ≠  0   (error)        → CHECK-FOR-STORM-DRAIN-DB2;
                                    SYNCPOINT ROLLBACK; RETURN
    SQLCODE = 0    (row fetched)  → ADD 1 TO NUMBER-OF-ACCOUNTS
                                    Move all 12 account fields to COMM-EYE(n),
                                    COMM-CUSTNO(n), COMM-SCODE(n), COMM-ACCNO(n),
                                    COMM-ACC-TYPE(n), COMM-INT-RATE(n),
                                    COMM-OPENED(n), COMM-OVERDRAFT(n),
                                    COMM-LAST-STMT-DT(n), COMM-NEXT-STMT-DT(n),
                                    COMM-ACTUAL-BAL(n), COMM-AVAIL-BAL(n)
  Stop when: SQLCODE ≠ 0 OR NUMBER-OF-ACCOUNTS = 20

EXEC SQL CLOSE ACC-CURSOR
  SQLCODE ≠ 0 → COMM-FAIL-CODE='4'; SYNCPOINT ROLLBACK; RETURN

MOVE 'Y' TO COMM-SUCCESS
```

**Date reformatting:** DB2 stores dates as `YYYY-MM-DD`. INQACCCU reformats using `DB2-DATE-REFORMAT` group-level structure, STRING-ing day + month + year into `COMM-OPENED`, `COMM-LAST-STMT-DT`, `COMM-NEXT-STMT-DT` as `DDMMYYYY`.

#### ABEND-HANDLING section
```
EXEC CICS ASSIGN ABCODE(MY-ABEND-CODE)
EVALUATE MY-ABEND-CODE
  WHEN 'AD2Z':   Display DB2 deadlock diagnostics (SQLSTATE, SQLERRMC, SQLERRD); fall through to re-abend
  WHEN 'AFCR' / 'AFCS' / 'AFCT':
    → SYNCPOINT ROLLBACK
    → COMM-SUCCESS='N'
    → EXEC CICS RETURN (graceful — storm drain)
  WHEN OTHER (WS-STORM-DRAIN='N'):
    → EXEC CICS ABEND ABCODE(MY-ABEND-CODE) NODUMP CANCEL
```

---

### 5.3 Files / Database / CICS Storage

| Resource | Type | Mode | Notes |
|----------|------|------|-------|
| `ACCOUNT` (DB2 table) | DB2 Embedded SQL | SELECT (cursor) | Cursor `ACC-CURSOR`: select all accounts for customer+sortcode; up to 20 rows fetched |
| `DFHCOMMAREA` (COPY INQACCCU) | CICS COMMAREA | Input / Output | `CUSTOMER-NUMBER` in; array of up to 20 account records + `NUMBER-OF-ACCOUNTS` + `COMM-SUCCESS` out |
| `INQCUST-COMMAREA` (COPY INQCUST) | Working Storage | Passed to `INQCUST` | Customer existence check |
| `SORTCODE` (COPY SORTCODE) | Working Storage | Read | Bank sort code constant |
| `ABNDINFO-REC` (COPY ABNDINFO) | Working Storage | Output | Passed to `ABNDPROC` on SYNCPOINT ROLLBACK failure |
| SQLCA | DB2 | Communication area | `SQLCODE` and `SQLSTATE` checking |
| No VSAM files | — | — | Purely DB2-based (VSAM access delegated to INQCUST) |

---

### 5.4 Programs Called by INQACCCU

| Program | Call Method | Purpose |
|---------|-------------|---------|
| `INQCUST` | `EXEC CICS LINK PROGRAM('INQCUST ')` | Validate customer exists before fetching accounts |
| `ABNDPROC` | `EXEC CICS LINK … COMMAREA(ABNDINFO-REC)` | Abend handler — logs failure when SYNCPOINT ROLLBACK fails |

---

### 5.5 INQACCCU Fail Code Reference

| Fail Code | Meaning |
|-----------|---------|
| `0` | Initial value (success pending) |
| `1` | Customer not found (INQCUST returned failure, or guard on 0 / 9s) |
| `2` | DB2 cursor OPEN failed |
| `3` | DB2 FETCH failed |
| `4` | DB2 cursor CLOSE failed |

---

## 6. Cross-Component Call Chain Summary

```
BNKMENU  (OMEN)
  │
  └── Option 4 ──► RETURN TRANSID('OCAC')
                       │
                       ▼
                   BNK1CAC  (OCAC)
                       │
                       ├── EXEC CICS RECEIVE MAP 'BNK1CA' (mapset BNK1CAM)
                       │       User enters: CustNo, AccType, IntRate, OverdraftLim
                       │
                       ├── EDIT-DATA (14 screen-level validations)
                       │
                       ├── EXEC CICS LINK ──► CREACC
                       │                          │
                       │                          ├── EXEC CICS LINK ──► INQCUST
                       │                          │      │  (READ FILE 'CUSTOMER')
                       │                          │      └── Returns: customer found Y/N
                       │                          │
                       │                          ├── EXEC CICS LINK ──► INQACCCU
                       │                          │      │
                       │                          │      ├── EXEC CICS LINK ──► INQCUST
                       │                          │      │      (re-validates customer)
                       │                          │      │
                       │                          │      ├── EXEC SQL OPEN ACC-CURSOR
                       │                          │      ├── EXEC SQL FETCH (up to 20 rows)
                       │                          │      └── Returns: NUMBER-OF-ACCOUNTS
                       │                          │
                       │                          ├── ACCOUNT-TYPE-CHECK
                       │                          │
                       │                          ├── EXEC CICS ENQ 'CBSAACCT'+sort
                       │                          │
                       │                          ├── EXEC SQL SELECT/UPDATE CONTROL
                       │                          │      (get & increment ACCOUNT-LAST)
                       │                          │      (get & increment ACCOUNT-COUNT)
                       │                          │
                       │                          ├── EXEC SQL INSERT INTO ACCOUNT
                       │                          │
                       │                          ├── EXEC SQL INSERT INTO PROCTRAN
                       │                          │
                       │                          ├── EXEC CICS DEQ
                       │                          │
                       │                          └── EXEC CICS LINK ──► ABNDPROC
                       │                                 (on any failure)
                       │
                       ├── EXEC CICS SEND MAP 'BNK1CA'
                       │       Result: AccNo, SortCode, Dates, Balances
                       │
                       └── EXEC CICS RETURN TRANSID('OCAC') COMMAREA(WS-COMM-AREA)
                               (pseudo-conversational loop)
```

### CICS COMMAREA Flow

```
BNKMENU   ──(no COMMAREA — EIBCALEN=0)──────────────────────────► BNK1CAC
BNK1CAC   ──(SUBPGM-PARMS)─────────────────────────────────────► CREACC
CREACC    ──(INQCUST-COMMAREA)──────────────────────────────────► INQCUST ──► BNK1CAC (via CREACC)
CREACC    ──(INQACCCU-COMMAREA)─────────────────────────────────► INQACCCU
INQACCCU  ──(INQCUST-COMMAREA, internal copy)───────────────────► INQCUST (2nd call)
CREACC    ──(updated SUBPGM-PARMS with AccNo/Dates/Success)─────► BNK1CAC
BNK1CAC   ──(WS-COMM-AREA, 32 bytes)───────────────────────────► OCAC (self-return, loop)
```

**Note:** `INQCUST` is called **twice** in a single Create Account flow — once directly by `CREACC` (customer existence check) and once by `INQACCCU` (its own internal `CUSTOMER-CHECK` section). Both calls are independent with separate COMMAREAs.

---

## 7. Fail Code Reference

### CREACC Fail Codes (surfaced as error messages in BNK1CAC)

| Fail Code | Set By | Meaning | Message in BNK1CAC |
|-----------|--------|---------|-------------------|
| `1` | CREACC | Customer number does not exist (INQCUST failure) | `The supplied customer number does not exist.` |
| `2` | CREACC | Customer data inaccessible | `The customer data cannot be accessed, unable to create account.` |
| `3` | CREACC | CICS ENQ on ACCOUNT named counter failed | `Account record creation failed. (unable to ENQ ACCOUNT NC).` |
| `4` | CREACC | Unable to increment ACCOUNT named counter | `Account record creation failed, (unable to increment ACCOUNT NC).` |
| `5` | CREACC | CICS DEQ on named counter failed | `Account record creation failed, (unable to restore ACCOUNT NC).` |
| `6` | CREACC | VSAM WRITE to ACCOUNT file failed *(reserved; DB2 path uses `7`)* | `Account record creation failed, (unable to WRITE to ACCOUNT file).` |
| `7` | CREACC | DB2 INSERT INTO ACCOUNT failed | `Account record creation failed, (unable to INSERT into ACCOUNT).` |
| `8` | CREACC | Customer already has 9 accounts (maximum reached) | `Account record creation failed, (too many accounts).` |
| `9` | CREACC | Error counting existing accounts (INQACCCU failure) | `Account record creation failed, unable to count accounts.` |
| `A` | CREACC | Account type not supported (backend type re-validation) | `Account record creation failed, account type unsupported.` |
| Other | CREACC | Unknown failure | `The account was not created.` |

### INQCUST Fail Codes (returned in INQCUST-COMMAREA)

| Fail Code | Meaning |
|-----------|---------|
| `0` | Success |
| `1` | Customer not found in VSAM file (or random retry exhausted at 1000) |
| `2` | VSAM RLS abend (`AFCR`/`AFCS`/`AFCT`) — handled gracefully via storm drain |
| `9` | VSAM browse operation failed (STARTBR / READPREV / ENDBR) |

### INQACCCU Fail Codes (returned in INQACCCU-COMMAREA)

| Fail Code | Meaning |
|-----------|---------|
| `0` | Initial value |
| `1` | Customer not found |
| `2` | DB2 cursor OPEN failed |
| `3` | DB2 FETCH failed |
| `4` | DB2 cursor CLOSE failed |

### Abend Codes Used Across All Programs

| Abend Code | Program | Trigger |
|-----------|---------|---------|
| `HBNK` | BNK1CAC | Any CICS failure (RECEIVE MAP, SEND MAP, RETURN, LINK) |
| `HNCS` | CREACC | DB2 CONTROL table SELECT or UPDATE failure |
| `HWPT` | CREACC | DB2 PROCTRAN INSERT failure |
| `CVR1` | INQCUST | Unexpected non-NOTFND VSAM error on CUSTOMER READ |
| `HROL` | INQCUST / INQACCCU | SYNCPOINT ROLLBACK failure following storm-drain condition |

---

## 8. Key Differences vs Create Customer Flow

| Aspect | Create Customer (`BNK1CCS` / `CRECUST`) | Create Account (`BNK1CAC` / `CREACC`) |
|--------|----------------------------------------|---------------------------------------|
| Customer validation | Not needed — creating the customer | Mandatory: `INQCUST` called by CREACC |
| Async processing | 5 async credit-check child transactions (`OCR1`–`OCR5`) | None |
| VSAM usage | `CUSTOMER` VSAM KSDS (write + control record) | None in CREACC — delegated to INQCUST |
| DB2 usage | `PROCTRAN` INSERT only | `ACCOUNT` INSERT + `CONTROL` SELECT/UPDATE + `PROCTRAN` INSERT |
| Control table type | VSAM control record (key `000000` + `9999999999`) | DB2 `CONTROL` table (two named rows per sort code) |
| Account limit check | N/A | Max 9 per customer — enforced via INQACCCU |
| Terminal UCTRAN | Disabled for mixed-case name/address input | Not needed (numeric / coded fields only) |
| Named counter resource | `CBSACUST` + sortcode | `CBSAACCT` + sortcode |
| PROCTRAN type | `OCC` (Open Customer Create) | `OCA` (Open Account) |
| LE date calls | `CEEDAYS` / `CEELOCT` for DOB validation | Not used — dates calculated via `INTEGER-OF-DATE` / `DATE-OF-INTEGER` |
| Abend codes | `HBNK`, `HWPT` | `HBNK`, `HNCS`, `HWPT`, `CVR1`, `HROL` |
| INQCUST call count | 0 | 2 (once from CREACC, once internally from INQACCCU) |

---

*Analysis updated from source review of `BNK1CAM.bms`, `BNK1CAC.cbl`, `CREACC.cbl`, `INQCUST.cbl`, and `INQACCCU.cbl`.*

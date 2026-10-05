# Credit / Debit Account — Component Analysis
## CICS Banking Sample Application — Menu Option 6

> **Transaction:** `OCRA` (triggered from `OMEN` Menu Option 6)
> **Components:** `BNK1CDM` (BMS Map) · `BNK1CRA` (Screen Handler) · `DBCRFUN` (Debit/Credit Backend)

---

## Table of Contents

1. [BNK1CDM — BMS Map (BNK1CD)](#1-bnk1cdm--bms-map-bnk1cd)
2. [BNK1CRA — Credit/Debit Screen Handler](#2-bnk1cra--creditdebit-screen-handler)
3. [DBCRFUN — Debit/Credit Function Backend](#3-dbcrfun--debitcredit-function-backend)
4. [Cross-Component Call Chain Summary](#4-cross-component-call-chain-summary)
5. [Fail Code Reference](#5-fail-code-reference)
6. [Screen Flow and Key Behaviour](#6-screen-flow-and-key-behaviour)
7. [Key Design Points and Comparisons](#7-key-design-points-and-comparisons)

---

## 1. BNK1CDM — BMS Map (BNK1CD)

**Mapset:** `BNK1CDM` | **Map:** `BNK1CD` | **Source:** `BNK1CDM.bms`

---

### 1.1 Map Identity

| Attribute | Value |
|-----------|-------|
| Mapset Name | `BNK1CDM` |
| Map Name | `BNK1CD` |
| Terminal Type | 3270-2 |
| Mode | INOUT |
| Language | COBOL |
| Storage | AUTO |
| Control | FREEKB |
| Extended Attributes | COLOR, HILIGHT, OUTLINE, PS, SOSI |
| Title | `CICS Banking Sample Application - Credit/Debit Funds.` (Red, Row 1) |
| Instruction | `Provide an ACCOUNT number and an AMOUNT and then press Enter.` (Turquoise, Row 3) |

---

### 1.2 Map Fields — Screen Layout

| Row | Field Name | Position | Length | Attributes | Color | Description |
|-----|-----------|----------|--------|------------|-------|-------------|
| 1 | *(literal)* | (1,1) | 7 | PROT, NORM | Blue | Map ID label `BNK1CD` |
| 1 | `COMPANY` | (1,15) | 61 | NORM, PROT | Red | Title banner |
| 3 | *(literal)* | (3,1) | 61 | NORM, PROT | Turquoise | Instruction text |
| 8 | *(literal)* | (8,1) | 15 | NORM, PROT | Turquoise | Label: `ACCOUNT NUMBER:` |
| 8 | `ACCNO` | (8,17) | 8 | NORM, NUM, IC, FSET | Green + Underline | **Input:** Account Number (numeric keyboard shift; IC cursor; MDT forced via FSET) |
| 8 | *(literal)* | (8,26) | 7 | NORM, PROT, ASKIP | Turquoise | Label: `AMOUNT:` |
| 8 | `SIGN` | (8,35) | 1 | NORM, UNPROT, FSET | Green + Underline | **Input:** Sign (`+` or `-`); initial value `+`; MDT forced via FSET |
| 8 | `AMT` | (8,37) | 13 | NORM, UNPROT, FSET | Green + Underline | **Input:** Amount; initial value `0000000000.00`; MDT forced via FSET |
| 10 | *(literal)* | (10,1) | 16 | NORM, PROT | Turquoise | Label: `Sort Code:` |
| 10 | `SORTC` | (10,21) | 6 | NORM, NUM, PROT | Neutral | **Output:** Sort Code (returned after processing) |
| 11 | *(literal)* | (11,1) | 18 | NORM, PROT | Turquoise | Label: `Available Balance:` |
| 11 | `AVBAL` | (11,20) | 14 | NORM, PROT | Neutral | **Output:** Available Balance (after transaction) |
| 12 | *(literal)* | (12,1) | 16 | NORM, PROT | Turquoise | Label: `Actual Balance:` |
| 12 | `ACTBAL` | (12,20) | 14 | NORM, PROT | Neutral | **Output:** Actual Balance (after transaction) |
| 23 | `MESSAGE` | (23,1) | 79 | BRT, PROT | Yellow | **Output:** User / error messages |
| 24 | *(literal)* | (24,1) | 20 | NORM, PROT | Blue | `F3=Exit   F12=Cancel` |
| 24 | `DUMMY` | (24,79) | 1 | DRK, PROT, FSET | — | Hidden MDT-forcing field |

**Notes on unique map design:**
- All three input fields (`ACCNO`, `SIGN`, `AMT`) are on **the same row (row 8)** — compact single-line entry, unlike the multi-row entry forms in other screens.
- `SIGN` and `AMT` are `UNPROT` (alphanumeric), not `NUM` — required because `AMT` accepts a decimal point and `SIGN` accepts `+` or `-`.
- All three input fields carry **FSET** — the Modified Data Tag is always set so the default values (`+` and `0000000000.00`) are always transmitted back even if unchanged.
- There is **no PF5 delete or PF10 update key** — Enter is the only action key.
- The output section (rows 10–12) is minimal: just sort code and the two updated balances.

**Function Key Legend:**

| Key | Action |
|-----|--------|
| Enter | Submit account number, sign, and amount for processing |
| PF3 | Exit — return to main menu (`OMEN`) |
| PF12 / AID | Cancel — send "Session Ended" termination message |
| CLEAR | Clear screen |
| PA1/PA2/PA3 | Continue — no action |

---

## 2. BNK1CRA — Credit/Debit Screen Handler

**Program ID:** `BNK1CRA` | **Transaction ID:** `OCRA`

This program is the presentation layer for applying a credit or debit to an account. It handles input collection, multi-step amount validation, sign determination, and delegates the actual account update to `DBCRFUN`.

---

### 2.1 Validations

#### EDIT-DATA Section

| # | Field | Check | Error Message |
|---|-------|-------|---------------|
| 1 | `ACCNOI` — numeric | `EXEC CICS BIF DEEDIT` applied; `NOT NUMERIC` check | `Please enter an account number.` |
| 2 | `ACCNOI` — non-zero | `ACCNOI = ZERO` | `Please enter a non zero account number.` |
| 3 | `SIGNI` — valid sign | `SIGNI NOT = '+'` AND `SIGNI NOT = '-'` AND `SIGNL = 1` | `Please enter + or - preceding the amount` |

Then calls `PERFORM VALIDATE-AMOUNT`.

#### VALIDATE-AMOUNT Section (custom multi-step numeric parser)

| # | Check | Logic | Error Message |
|---|-------|-------|---------------|
| 4 | Amount — presence | `AMTL = ZERO` | `The Amount entered must be numeric.` |
| 5 | Amount — pure integer | `AMTI(1:AMTL) IS NUMERIC` — if true, converts via `FUNCTION NUMVAL`; valid | *(no error — success path)* |
| 6 | Amount — entirely spaces | `INSPECT … TALLYING FOR LEADING SPACES = AMTL` | `The Amount entered must be numeric.` |
| 7 | Amount — embedded spaces | After stripping leading/trailing spaces; `WS-NUM-COUNT-SPACE > 0` | `Please supply a numeric amount without embedded spaces.` |
| 8 | Amount — invalid characters | `WS-NUM-COUNT-TOTAL < WS-AMOUNT-UNSTR-L` (non-digit, non-point chars present) | `Please supply a numeric amount.` |
| 9 | Amount — multiple decimal points | `WS-NUM-COUNT-POINT > 1` | `Use one decimal point for amount only.` |
| 10 | Amount — more than 2 decimal places | When 1 decimal point present: count digits after `.`; if `> 2` non-zero digits after 2nd place → error | `Only up to two decimal places are supported.` |
| 11 | Amount — non-zero value | After `FUNCTION NUMVAL` conversion, `WS-AMOUNT-AS-FLOAT = ZERO` | `Please supply a non-zero amount.` |

**Amount validation algorithm summary:**
```
1. If AMTL=0 → error (no entry)
2. If purely numeric (IS NUMERIC) → NUMVAL, set valid, return
3. Strip leading spaces → compute WS-AMOUNT-UNSTR-L
4. Reverse string → strip trailing spaces → adjust WS-AMOUNT-UNSTR-L
5. INSPECT: tally digits 0-9 and '.' → WS-NUM-COUNT-TOTAL
            tally spaces             → WS-NUM-COUNT-SPACE
6. If embedded spaces > 0 → error
7. If total valid chars < effective length → invalid chars → error
8. Count decimal points → if > 1 → error
9. If exactly 1 decimal point → count digits after it:
   if > 2 non-zero digits exist past 2nd decimal place → error
10. COMPUTE WS-AMOUNT-AS-FLOAT = FUNCTION NUMVAL(stripped amount)
11. If result = zero → error (must be a non-zero amount)
```

#### POST-LINK Result Checks (UPD-CRED-DATA after DBCRFUN)

| # | Condition | Error Message |
|---|-----------|---------------|
| 12 | `SUBPGM-SUCCESS = 'N'` AND `SUBPGM-FAIL-CODE = '1'` | `Sorry but the ACCOUNT no was not found for SORTCODE <code>. Amount not applied.` |
| 13 | `SUBPGM-SUCCESS = 'N'` AND `SUBPGM-FAIL-CODE = '2'` | `Sorry but the AMOUNT could not be applied due to an unexpected error.` |
| 14 | `SUBPGM-SUCCESS = 'N'` AND `SUBPGM-FAIL-CODE = '3'` | `Sorry insufficient funds available to process the request.` |
| 15 | `SUBPGM-SUCCESS = 'N'` AND any other code | `Sorry but the AMOUNT could not be applied due to an unexpected error. <code>` |

---

### 2.2 Processing

#### Key Press Routing (PREMIERE SECTION — EVALUATE on EIBAID)

| AID Key | Action |
|---------|--------|
| `EIBCALEN = 0` | First time: `LOW-VALUE` to `BNK1CDO`; cursor on `ACCNO` (`ACCNOL = -1`); SEND-ERASE |
| `DFHPA1/PA2/PA3` | `CONTINUE` — no action |
| `DFHPF3` | `EXEC CICS RETURN TRANSID('OMEN') IMMEDIATE` |
| `DFHAID` / `DFHPF12` | Send "Session Ended"; plain `EXEC CICS RETURN` |
| `DFHCLEAR` | `SEND CONTROL ERASE FREEKB`; plain `EXEC CICS RETURN` |
| `DFHENTER` | `PERFORM PROCESS-MAP` |
| Any other key | `LOW-VALUES` to `BNK1CDO`; "Invalid key pressed."; `ACCNOL = 8`; SEND-DATAONLY-ALARM |

After all paths: if `EIBCALEN ≠ 0`, copies `COMM-ACCNO`, `COMM-SIGN`, `COMM-AMT` from DFHCOMMAREA to `WS-COMM-AREA`.
Issues `EXEC CICS RETURN TRANSID('OCRA') COMMAREA(WS-COMM-AREA) LENGTH(21)`.

#### PROCESS-MAP Section — Detailed Flow

```
PERFORM RECEIVE-MAP
  (RECEIVE MAP 'BNK1CD' INTO BNK1CDI — standard receive, no ASIS)

PERFORM EDIT-DATA
  (ACCNO numeric + non-zero; SIGN '+'/'-'; VALIDATE-AMOUNT 8-step pipeline)

IF VALID-DATA:
  PERFORM UPD-CRED-DATA:
    INITIALIZE SUBPGM-PARMS
    MOVE ACCNOI → SUBPGM-ACCNO; MOVE 0 → SUBPGM-AMT

    IF SIGNI = '-':
      COMPUTE WS-AMOUNT-AS-FLOAT = WS-AMOUNT-AS-FLOAT * -1
    MOVE WS-AMOUNT-AS-FLOAT → SUBPGM-AMT  (signed COMP-2 float)

    EXEC CICS INQUIRE ASSOCIATION(EIBTASKN)
      ODAPPLID        → SUBPGM-APPLID
      ODUSERID        → SUBPGM-USERID
      ODFACILNAME     → SUBPGM-FACILITY-NAME
      ODNETWORKID     → SUBPGM-NETWRK-ID
      ODFACILTYPE     → SUBPGM-FACILTYPE
    (Captures session/origin metadata for facility-type business rules in DBCRFUN)

    EXEC CICS LINK PROGRAM('DBCRFUN') COMMAREA(SUBPGM-PARMS) SYNCONRETURN

    Evaluate SUBPGM-SUCCESS / SUBPGM-FAIL-CODE:
      'N'+'1' → account not found message (includes sort code)
      'N'+'2' → unexpected error message
      'N'+'3' → insufficient funds message
      'N'+other → unexpected error + code
      'Y'     → 'Amount successfully applied to the account.'
                 ACCNOO  ← SUBPGM-ACCNO
                 SORTCO  ← SUBPGM-SORTC
                 ACTBALO ← SUBPGM-ACT-BAL  via ACTUAL-BALANCE-DISPLAY (+9(10).99)
                 AVBALO  ← SUBPGM-AV-BAL   via AVAILABLE-BALANCE-DISPLAY (+9(10).99)

SET SEND-DATAONLY-ALARM TO TRUE
PERFORM SEND-MAP
```

---

### 2.3 Files / Database / CICS Storage

| Resource | Type | Usage |
|----------|------|-------|
| `BNK1CD` / `BNK1CDM` | CICS BMS Map | Input (`RECEIVE MAP`) and Output (`SEND MAP ERASE` / `DATAONLY` / `DATAONLY ALARM`) |
| `DFHCOMMAREA` (21 bytes) | CICS COMMAREA | Input from `OMEN` or prior `OCRA` cycle; `COMM-ACCNO` (8), `COMM-SIGN` (1), `COMM-AMT` (12) |
| `WS-COMM-AREA` (21 bytes) | CICS COMMAREA | Passed on `RETURN TRANSID('OCRA')` — pseudo-conversational loop state |
| `SUBPGM-PARMS` (COPY PAYDBCR) | CICS COMMAREA | Passed to / received from `DBCRFUN` via `EXEC CICS LINK` |
| `ABNDINFO-REC` (COPY ABNDINFO) | CICS COMMAREA | Passed to `ABNDPROC` on any CICS failure |
| CICS ASSOCIATION (`INQUIRE ASSOCIATION`) | CICS System Service | Read — captures APPLID, USERID, FACILITY-NAME, NETWORK-ID, FACILTYPE for current task |
| No VSAM files or DB2 tables | — | All data access delegated to `DBCRFUN` |
| No terminal UCTRAN management | — | Not needed — inputs are numeric/sign characters only |

---

### 2.4 Programs Called by BNK1CRA

| Program | Call Method | Purpose |
|---------|-------------|---------|
| `DBCRFUN` | `EXEC CICS LINK … SYNCONRETURN` | Apply the credit or debit amount to the account in DB2 and write PROCTRAN audit record |
| `ABNDPROC` | `EXEC CICS LINK … COMMAREA(ABNDINFO-REC)` | Abend handler — logs and terminates on any CICS failure |

---

## 3. DBCRFUN — Debit/Credit Function Backend

**Program ID:** `DBCRFUN` | **Invocation:** `EXEC CICS LINK` from `BNK1CRA`

**Purpose:** Applies a signed amount to an account record in the DB2 `ACCOUNT` table using a SELECT then UPDATE pattern. After a successful update, writes a transaction audit record to `PROCTRAN`. Implements channel-aware business rules: MORTGAGE/LOAN restrictions and insufficient-funds checks that apply only to payment-channel calls (non-terminal, `FACILTYPE = 496`), not teller transactions.

---

### 3.1 Validations

| # | Check | Logic | Fail Code |
|---|-------|-------|-----------|
| 1 | **Account not found** | DB2 `SQLCODE = +100` on singleton SELECT | `COMM-SUCCESS = 'N'`; `COMM-FAIL-CODE = '1'`; CHECK-STORM-DRAIN; GO TO UAD999 |
| 2 | **DB2 SELECT failure (other)** | `SQLCODE NOT = 0` and `NOT = +100` | `COMM-SUCCESS = 'N'`; `COMM-FAIL-CODE = '2'`; CHECK-STORM-DRAIN; GO TO UAD999 |
| 3 | **Debit from MORTGAGE/LOAN — payment channel** | `COMM-AMT < 0` AND `ACC-TYPE = 'MORTGAGE'` or `'LOAN    '` AND `FACILTYPE = 496` | `COMM-SUCCESS = 'N'`; `COMM-FAIL-CODE = '4'`; GO TO UAD999 |
| 4 | **Insufficient available funds — payment channel** | `COMM-AMT < 0` AND `(HV-ACCOUNT-AVAIL-BAL + COMM-AMT) < 0` AND `FACILTYPE = 496` | `COMM-SUCCESS = 'N'`; `COMM-FAIL-CODE = '3'`; GO TO UAD999 |
| 5 | **Credit to MORTGAGE/LOAN — payment channel** | `COMM-AMT ≥ 0` AND `ACC-TYPE = 'MORTGAGE'` or `'LOAN    '` AND `FACILTYPE = 496` | `COMM-SUCCESS = 'N'`; `COMM-FAIL-CODE = '4'`; GO TO UAD999 |
| 6 | **DB2 UPDATE failure** | `SQLCODE NOT = 0` after `EXEC SQL UPDATE ACCOUNT` | `COMM-SUCCESS = 'N'`; `COMM-FAIL-CODE = '2'`; CHECK-STORM-DRAIN; GO TO UAD999 |
| 7 | **PROCTRAN INSERT failure** | `SQLCODE NOT = 0` after `EXEC SQL INSERT INTO PROCTRAN` | SYNCPOINT ROLLBACK (undo ACCOUNT UPDATE); if ROLLBACK fails → ABEND `HROL`; else `COMM-FAIL-CODE = '02'`; CHECK-STORM-DRAIN |
| 8 | **VSAM RLS abends** (`AFCR`, `AFCS`, `AFCT`) | Caught in `ABEND-HANDLING` | SYNCPOINT ROLLBACK; `COMM-FAIL-CODE = '2'`; graceful `EXEC CICS RETURN` |
| 9 | **DB2 Storm Drain** (`SQLCODE = 923`) | `CHECK-FOR-STORM-DRAIN-DB2` section | Logged; processing continues with failure path |
| 10 | **DB2 deadlock** (`AD2Z`) | Caught in `ABEND-HANDLING` | SQLSTATE/SQLERRMC/SQLERRD diagnostics displayed; falls through to non-storm-drain re-abend |

**Facility type gate — `COMM-FACILTYPE = 496`:**
Checks 3, 4, and 5 are **only enforced for payment-channel requests** (FACILTYPE = 496 = NONE = non-terminal). Teller transactions (terminal-based, FACILTYPE ≠ 496) bypass all three checks — a teller can credit or debit MORTGAGE/LOAN accounts and is not subject to the insufficient-funds check.

---

### 3.2 Processing

#### Main Flow (PREMIERE section)
```
1. MOVE 'N' → COMM-SUCCESS; '0' → COMM-FAIL-CODE
2. EXEC CICS HANDLE ABEND LABEL(ABEND-HANDLING)
3. MOVE SORTCODE → COMM-SORTC, DESIRED-SORT-CODE
4. PERFORM UPDATE-ACCOUNT-DB2
5. PERFORM GET-ME-OUT-OF-HERE (EXEC CICS RETURN)
```

#### UPDATE-ACCOUNT-DB2 section
```
1. MOVE COMM-ACCNO → DESIRED-ACC-NO
   Set HV-ACCOUNT-SORTCODE, HV-ACCOUNT-ACC-NO

2. EXEC SQL SELECT (12 columns) FROM ACCOUNT
   WHERE ACCOUNT_SORTCODE = :sort AND ACCOUNT_NUMBER = :accno
   (Singleton SELECT — implicit update lock)

   SQLCODE ≠ 0:
     +100 → COMM-FAIL-CODE='1' (not found); CHECK-STORM-DRAIN; return
     other → COMM-FAIL-CODE='2' (unexpected); CHECK-STORM-DRAIN; return

3. Channel-aware business rule checks (payment channel only, FACILTYPE=496):

   IF COMM-AMT < 0 (debit):
     IF ACC-TYPE = MORTGAGE or LOAN → COMM-FAIL-CODE='4'; return
     COMPUTE WS-DIFFERENCE = HV-ACCOUNT-AVAIL-BAL + COMM-AMT
     IF WS-DIFFERENCE < 0 → COMM-FAIL-CODE='3'; return (insufficient funds)

   IF ACC-TYPE = MORTGAGE or LOAN → COMM-FAIL-CODE='4'; return (blocks credits too)

4. Apply amount to both balances:
   COMPUTE HV-ACCOUNT-AVAIL-BAL  = HV-ACCOUNT-AVAIL-BAL  + COMM-AMT
   COMPUTE HV-ACCOUNT-ACTUAL-BAL = HV-ACCOUNT-ACTUAL-BAL + COMM-AMT

5. EXEC SQL UPDATE ACCOUNT
   SET (all 12 columns) = :host-variables
   WHERE ACCOUNT_SORTCODE = :sort AND ACCOUNT_NUMBER = :accno

   Pass updated balances back to caller:
   MOVE HV-ACCOUNT-AVAIL-BAL  → COMM-AV-BAL
   MOVE HV-ACCOUNT-ACTUAL-BAL → COMM-ACT-BAL

   SQLCODE ≠ 0 → COMM-FAIL-CODE='2'; CHECK-STORM-DRAIN; return

6. PERFORM WRITE-TO-PROCTRAN → PERFORM WRITE-TO-PROCTRAN-DB2
```

#### WRITE-TO-PROCTRAN-DB2 section
```
Build HOST-PROCTRAN-ROW:
  EYECATCHER = 'PRTR'
  SORT-CODE  = COMM-SORTC
  ACC-NUMBER = COMM-ACCNO
  REF        = EIBTASKN (padded to 12 digits)
  DATE       = today DD.MM.YYYY  (ASKTIME + FORMATTIME DATESEP('.'))
  TIME       = HHMMSS

Determine TYPE and DESC:
  COMM-AMT < 0 (debit):
    TYPE = 'DEB'; DESC = 'COUNTER WTHDRW'
    IF FACILTYPE = 496: TYPE = 'PDR'; DESC = COMM-ORIGIN(1:14)
  COMM-AMT ≥ 0 (credit):
    TYPE = 'CRE'; DESC = 'COUNTER RECVED'
    IF FACILTYPE = 496: TYPE = 'PCR'; DESC = COMM-ORIGIN(1:14)

AMOUNT = COMM-AMT (signed)

EXEC SQL INSERT INTO PROCTRAN (9 columns)

IF SQLCODE ≠ 0:
  DISPLAY error details
  EXEC CICS SYNCPOINT ROLLBACK   ← undoes the ACCOUNT UPDATE
  If ROLLBACK fails:
    Link to ABNDPROC; ABEND 'HROL'
  Else:
    COMM-SUCCESS='N'; COMM-FAIL-CODE='02'; CHECK-STORM-DRAIN

IF SQLCODE = 0:
  COMM-SUCCESS='Y'; COMM-FAIL-CODE='0'
```

**PROCTRAN Transaction Type Codes:**

| Type | Description | Condition |
|------|-------------|-----------|
| `DEB` | Counter/Teller debit (cash withdrawal over counter) | `COMM-AMT < 0` AND `FACILTYPE ≠ 496` |
| `CRE` | Counter/Teller credit (cash received over counter) | `COMM-AMT ≥ 0` AND `FACILTYPE ≠ 496` |
| `PDR` | Payment debit (automated payment channel) | `COMM-AMT < 0` AND `FACILTYPE = 496` |
| `PCR` | Payment credit (automated payment channel) | `COMM-AMT ≥ 0` AND `FACILTYPE = 496` |

**SYNCPOINT ROLLBACK logic:** If the PROCTRAN INSERT fails after the ACCOUNT UPDATE has already succeeded, DBCRFUN issues `EXEC CICS SYNCPOINT ROLLBACK` to undo the balance change. This ensures ACCOUNT and PROCTRAN remain consistent — a balance change is only committed when its audit record is also committed. If the rollback itself fails, it ABENDs with `HROL`.

#### ABEND-HANDLING section
```
EXEC CICS ASSIGN ABCODE(MY-ABEND-CODE)
EVALUATE MY-ABEND-CODE:
  WHEN 'AD2Z' (DB2 deadlock):
    Display SQLCODE, SQLSTATE, SQLERRMC, SQLERRD diagnostics
    → falls through to WS-STORM-DRAIN='N' re-abend

  WHEN 'AFCR' / 'AFCS' / 'AFCT' (VSAM RLS storm-drain):
    MOVE 'Y' → WS-STORM-DRAIN
    EXEC CICS SYNCPOINT ROLLBACK
    If ROLLBACK fails → ABEND 'HROL' via ABNDPROC
    MOVE 'N' → COMM-SUCCESS; '2' → COMM-FAIL-CODE
    EXEC CICS RETURN  (graceful)

IF WS-STORM-DRAIN = 'N':
  Log to ABNDINFO-REC; EXEC CICS LINK ABNDPROC
  EXEC CICS ABEND ABCODE(MY-ABEND-CODE) NODUMP CANCEL
```

---

### 3.3 Files / Database / CICS Storage

| Resource | Type | Mode | Notes |
|----------|------|------|-------|
| `ACCOUNT` (DB2 table) | DB2 Embedded SQL | SELECT (singleton) | Read with implicit lock: `WHERE ACCOUNT_SORTCODE=:sort AND ACCOUNT_NUMBER=:accno` |
| `ACCOUNT` (DB2 table) | DB2 Embedded SQL | UPDATE | Full 12-column row rewrite; only `AVAILABLE_BALANCE` and `ACTUAL_BALANCE` change in value |
| `PROCTRAN` (DB2 table) | DB2 Embedded SQL | INSERT | Audit record; type `DEB`/`CRE`/`PDR`/`PCR`; amount = signed `COMM-AMT` |
| `DFHCOMMAREA` (COPY PAYDBCR) | CICS COMMAREA | Input / Output | All fields via `COPY PAYDBCR` copybook |
| `SORTCODE` (COPY SORTCODE) | Working Storage | Read | Bank sort code constant |
| `WS-ACC-DATA` (COPY ACCOUNT) | Local Storage | Declared | Account data structure |
| `PROCTRAN-AREA` (COPY PROCTRAN) | Local Storage | Working | PROCTRAN type/desc formatting |
| `ABNDINFO-REC` (COPY ABNDINFO) | Working Storage | Output | Passed to `ABNDPROC` on failure |
| SQLCA | DB2 | Communication area | `SQLCODE`, `SQLSTATE`, `SQLERRMC`, `SQLERRD` checking |
| `EXEC CICS SYNCPOINT ROLLBACK` | CICS Transaction Control | Issued | If PROCTRAN INSERT fails — rolls back ACCOUNT UPDATE to preserve data integrity |
| No VSAM files | — | — | Purely DB2-based |

---

### 3.4 Programs Called by DBCRFUN

| Program | Call Method | Purpose |
|---------|-------------|---------|
| `ABNDPROC` | `EXEC CICS LINK … COMMAREA(ABNDINFO-REC)` | Abend handler — logs DB2/CICS failure details and terminates |

---

### 3.5 DBCRFUN COMMAREA Fields (COPY PAYDBCR inferred)

| Field | Direction | Description |
|-------|-----------|-------------|
| `COMM-ACCNO` | Input | Account number (8 chars) |
| `COMM-AMT` | Input | Signed amount — positive = credit, negative = debit (COMP-2 float) |
| `COMM-SORTC` | Output | Sort code (set from `SORTCODE` constant) |
| `COMM-AV-BAL` | Output | Updated available balance after transaction |
| `COMM-ACT-BAL` | Output | Updated actual balance after transaction |
| `COMM-ORIGIN` | Input | Origin data block (APPLID, USERID, FACILITY-NAME, NETWORK-ID, FACILTYPE) |
| `COMM-FACILTYPE` | Input | Facility type — `496` = NONE (payment API); other values = terminal (teller) |
| `COMM-SUCCESS` | Output | `'Y'` = success; `'N'` = failure |
| `COMM-FAIL-CODE` | Output | Failure reason code (see Section 5) |

---

## 4. Cross-Component Call Chain Summary

```
BNKMENU  (OMEN)
  │
  └── Option 6 ──► RETURN TRANSID('OCRA')
                       │
                       ▼
                   BNK1CRA  (OCRA)
                       │
                       ├── EXEC CICS RECEIVE MAP 'BNK1CD'
                       │       User enters: ACCNO (8 digits)
                       │                    SIGN (+ or -)
                       │                    AMT (decimal amount)
                       │
                       ├── EDIT-DATA + VALIDATE-AMOUNT:
                       │     BIF DEEDIT + numeric check on ACCNO
                       │     Non-zero check on ACCNO
                       │     Sign character check (+ or -)
                       │     8-step custom amount parser:
                       │       presence, pure numeric, spaces, embedded spaces,
                       │       invalid chars, decimal count, decimal places, non-zero
                       │
                       ├── EXEC CICS INQUIRE ASSOCIATION(EIBTASKN)
                       │       Captures: APPLID, USERID, FACILITY-NAME,
                       │                 NETWORK-ID, FACILTYPE
                       │
                       ├── IF SIGNI = '-': negate WS-AMOUNT-AS-FLOAT
                       │
                       ├── EXEC CICS LINK ──► DBCRFUN
                       │       │
                       │       ├── EXEC SQL SELECT FROM ACCOUNT (singleton)
                       │       │     WHERE SORTCODE=:s AND ACCNO=:a
                       │       │
                       │       ├── Business rule checks (FACILTYPE=496 only):
                       │       │     Debit from MORTGAGE/LOAN → fail '4'
                       │       │     Insufficient available funds → fail '3'
                       │       │     Credit to MORTGAGE/LOAN → fail '4'
                       │       │
                       │       ├── COMPUTE new balances:
                       │       │     AVAIL-BAL  = AVAIL-BAL  + COMM-AMT
                       │       │     ACTUAL-BAL = ACTUAL-BAL + COMM-AMT
                       │       │
                       │       ├── EXEC SQL UPDATE ACCOUNT (full 12-column rewrite)
                       │       │     WHERE SORTCODE=:s AND ACCNO=:a
                       │       │
                       │       ├── EXEC SQL INSERT INTO PROCTRAN
                       │       │     TYPE = DEB / CRE / PDR / PCR
                       │       │     AMOUNT = signed COMM-AMT
                       │       │
                       │       ├── IF PROCTRAN INSERT fails:
                       │       │     EXEC CICS SYNCPOINT ROLLBACK
                       │       │     (undoes ACCOUNT UPDATE — data integrity)
                       │       │
                       │       └── Returns: COMM-SUCCESS, COMM-FAIL-CODE,
                       │                    COMM-SORTC, COMM-AV-BAL, COMM-ACT-BAL
                       │
                       ├── On success:
                       │     SORTCO  ← SUBPGM-SORTC
                       │     AVBALO  ← SUBPGM-AV-BAL  (+9(10).99 signed display)
                       │     ACTBALO ← SUBPGM-ACT-BAL (+9(10).99 signed display)
                       │     MESSAGE: 'Amount successfully applied to the account.'
                       │
                       └── EXEC CICS RETURN TRANSID('OCRA') COMMAREA(WS-COMM-AREA) LENGTH(21)
                               (pseudo-conversational loop)
```

### CICS COMMAREA Flow

```
BNKMENU ──(RETURN TRANSID 'OCRA', no COMMAREA)───────────► BNK1CRA (EIBCALEN=0 first pass)
BNK1CRA ──(SUBPGM-PARMS / COPY PAYDBCR, with origin data)► DBCRFUN ──► BNK1CRA
BNK1CRA ──(WS-COMM-AREA, 21 bytes)──────────────────────► OCRA (self-return, loop)
```

---

## 5. Fail Code Reference

### DBCRFUN → BNK1CRA Fail Codes

| Fail Code | Set By | Condition | Message in BNK1CRA |
|-----------|--------|-----------|-------------------|
| `1` | DBCRFUN | Account not found (`SQLCODE +100`) | `Sorry but the ACCOUNT no was not found for SORTCODE <code>. Amount not applied.` |
| `2` | DBCRFUN | DB2 SELECT or UPDATE failure (unexpected error) | `Sorry but the AMOUNT could not be applied due to an unexpected error.` |
| `3` | DBCRFUN | Insufficient available funds (payment channel only) | `Sorry insufficient funds available to process the request.` |
| `4` | DBCRFUN | MORTGAGE or LOAN account transaction via payment channel | *(falls to OTHER handler)* `Sorry but the AMOUNT could not be applied due to an unexpected error. 4` |
| `02` | DBCRFUN | PROCTRAN INSERT failed (after successful ACCOUNT UPDATE rollback) | `Sorry but the AMOUNT could not be applied due to an unexpected error.` |
| Other | DBCRFUN | Unknown failure | `Sorry but the AMOUNT could not be applied due to an unexpected error. <code>` |

### Abend Codes Across All Programs

| Abend Code | Program | Trigger |
|-----------|---------|---------|
| `HBNK` | BNK1CRA | Any CICS failure (RECEIVE MAP, SEND MAP, RETURN TRANSID, LINK) |
| `HROL` | DBCRFUN | SYNCPOINT ROLLBACK failure after PROCTRAN INSERT fails |
| `HROL` | DBCRFUN | SYNCPOINT ROLLBACK failure in ABEND-HANDLING after VSAM RLS abend |

---

## 6. Screen Flow and Key Behaviour

```
┌──────────────────────────────────────────────────────────────────────┐
│  BNK1CD — First Time (EIBCALEN=0)                                   │
│  CICS Banking Sample Application - Credit/Debit Funds.              │
│  Provide an ACCOUNT number and an AMOUNT and then press Enter.      │
│                                                                      │
│  ACCOUNT NUMBER: ________  AMOUNT: +  0000000000.00                │
│                                                                      │
│  Sort Code:                                                         │
│  Available Balance:                                                 │
│  Actual Balance:                                                     │
│  F3=Exit  F12=Cancel                                                │
└──────────────────────┬───────────────────────────────────────────────┘
                       │ User enters: 00000010, +, 100.00 → ENTER
                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  BNK1CD — After Successful Credit (+100.00)                         │
│                                                                      │
│  ACCOUNT NUMBER: 00000010  AMOUNT: +  0000000100.00                │
│                                                                      │
│  Sort Code:        987654                                           │
│  Available Balance: +0000472907.57                                  │
│  Actual Balance:   +0000472907.57                                   │
│                                                                      │
│  MESSAGE: Amount successfully applied to the account.               │
│  F3=Exit  F12=Cancel                                                │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 7. Key Design Points and Comparisons

### Unique Design Features of This Transaction

| Aspect | Detail |
|--------|--------|
| Single-row input | `ACCNO`, `SIGN`, and `AMT` all on row 8 — compact entry unlike the multi-row forms in other screens |
| Separated sign + amount | `SIGN` (1 char) is a separate field from `AMT` (13 chars). The sign is applied as `* -1` in code before being passed as a single signed COMP-2 float to DBCRFUN |
| Custom amount validator | `VALIDATE-AMOUNT` is an 8-step bespoke parser using INSPECT TALLYING — handles decimal points, leading/trailing spaces, embedded spaces, multiple decimal points, and excess decimal places. More sophisticated than the simple `IS NUMERIC` checks used in other programs |
| INQUIRE ASSOCIATION | Unique to this transaction in the suite — BNK1CRA explicitly captures session origin metadata (APPLID, USERID, FACILTYPE) and passes it to DBCRFUN. No other screen program in this application suite does this |
| Facility type business rules | DBCRFUN uses `COMM-FACILTYPE = 496` to distinguish teller (terminal) from payment API. Three restrictions apply to payment channel only: debit from MORTGAGE/LOAN, insufficient funds, credit to MORTGAGE/LOAN |
| Atomic SELECT → UPDATE → INSERT | DBCRFUN's three DB2 operations are treated as an atomic unit. PROCTRAN INSERT failure triggers SYNCPOINT ROLLBACK to undo the ACCOUNT UPDATE. No other program in this suite implements this ROLLBACK compensation |
| Full 12-column UPDATE | The ACCOUNT UPDATE rewrites all 12 columns even though only `AVAILABLE_BALANCE` and `ACTUAL_BALANCE` change. Other fields (type, interest rate, dates, overdraft) are re-written unchanged |
| Signed PROCTRAN amount | Contains the transaction amount (`COMM-AMT`) — positive for credits, negative for debits. Preserves direction in the audit trail |
| FSET on default values | Both `SIGN` (default `+`) and `AMT` (default `0000000000.00`) use FSET so BMS always transmits them back even if unchanged — essential for the default sign to reach the program |

### Comparison with Other CICS Banking Suite Transactions

| Aspect | `OCRA` Credit/Debit | `ODAC` Display/Delete Account | `ODCS` Display/Update/Delete Customer |
|--------|---------------------|------------------------------|--------------------------------------|
| Primary purpose | Balance modification | Account inquiry + optional delete | Customer inquiry + optional update/delete |
| DB2 operation in backend | SELECT + UPDATE + INSERT | SELECT / DELETE + INSERT | VSAM READ / VSAM DELETE / VSAM REWRITE |
| Transaction rollback? | **Yes** — SYNCPOINT ROLLBACK if PROCTRAN INSERT fails | No | No |
| Facility-type business rules | **Yes** — teller vs payment API | No | No |
| COMMAREA size | 21 bytes | 102 bytes | 266 bytes |
| Terminal UCTRAN management | No | No | Yes (mixed-case name/address) |
| Map update mode (field unprotect) | None | None | Yes (PF10) |
| Number of input fields | 3 (`ACCNO`, `SIGN`, `AMT`) | 1 (`ACCNO`) | 1 (`CUSTNO`) |
| Amount validation | Custom 8-step validator | N/A | N/A |
| INQUIRE ASSOCIATION called | **Yes** | No | No |

---

*Analysis generated from source review of `BNK1CDM.bms`, `BNK1CRA.cbl`, and `DBCRFUN.cbl`.*

# Display Customer Accounts — Component Analysis
## CICS Banking Sample Application — Menu Option A

> **Transaction:** `OCCA` (triggered from `OMEN` Menu Option A)
> **Components:** `BNK1ACC` (BMS Map) · `BNK1CCA` (Screen Handler) · `INQACCCU` (Account Inquiry Backend)

---

## Table of Contents

1. [BNK1ACC — BMS Map (BNK1ACC)](#1-bnk1acc--bms-map-bnk1acc)
2. [BNK1CCA — Display Customer Accounts Screen Handler](#2-bnk1cca--display-customer-accounts-screen-handler)
3. [INQACCCU — Inquire Accounts for Customer Backend](#3-inqacccu--inquire-accounts-for-customer-backend)
4. [Cross-Component Call Chain Summary](#4-cross-component-call-chain-summary)
5. [Fail Code Reference](#5-fail-code-reference)
6. [Screen Flow and Key Behaviour](#6-screen-flow-and-key-behaviour)
7. [Key Design Points and Comparisons](#7-key-design-points-and-comparisons)

---

## 1. BNK1ACC — BMS Map (BNK1ACC)

**Mapset:** `BNK1ACC` | **Map:** `BNK1ACC` | **Source:** `BNK1ACC.bms`

> **Note:** This mapset and map share the same name (`BNK1ACC`) — unique in the suite. All other mapsets use different names for mapset vs map (e.g. `BNK1DCM`/`BNK1DC`).

---

### 1.1 Map Identity

| Attribute | Value |
|-----------|-------|
| Mapset Name | `BNK1ACC` |
| Map Name | `BNK1ACC` |
| Terminal Type | 3270-2 |
| Mode | INOUT |
| Language | COBOL |
| Storage | AUTO |
| Control | FREEKB |
| Extended Attributes | COLOR, HILIGHT, OUTLINE, PS, SOSI |
| Title | `CICS Banking Sample Application - Accounts for Customers.` (Red, Row 1) |
| Instruction | `Provide a Customer number. Then press Enter.` (Turquoise, Row 3) |

---

### 1.2 Map Fields — Screen Layout

| Row | Field Name | Position | Length | Attributes | Color | Description |
|-----|-----------|----------|--------|------------|-------|-------------|
| 1 | *(literal)* | (1,1) | 7 | PROT, NORM | Blue | Map ID label `BNK1ACC` |
| 1 | `COMPANY` | (1,14) | 63 | NORM, PROT | Red | Title banner |
| 3 | *(literal)* | (3,1) | 44 | NORM, PROT | Turquoise | Instruction text |
| 5 | *(literal)* | (5,1) | 15 | NORM, PROT | Turquoise | Label: `CUSTOMER NUMBER` |
| 5 | `CUSTNO` | (5,17) | 10 | NORM, NUM, IC | Green + Underline | **Input:** Customer Number (numeric; cursor auto-positioned via IC; **no FSET**) |
| 8 | *(literal)* | (8,1) | 41 | NORM, PROT | Neutral | Column header: `SORT CODE   ACCOUNT NUMBER   ACCOUNT TYPE` |
| 8 | *(literal)* | (8,43) | 33 | NORM, PROT | Neutral | Column header: `   AVAIL BALANCE   ACTUAL BALANCE` |
| 9–18 | `ACCOUNT` | (9,1)–(18,1) | 79 each | NORM, PROT, FSET, ASKIP | Neutral | **Output:** Account rows array — **OCCURS 10** — one 79-char line per account |
| 23 | `MESSAGE` | (23,1) | 79 | BRT, PROT, ASKIP | Yellow | **Output:** User / error messages |
| 24 | *(literal)* | (24,1) | 20 | NORM, PROT, ASKIP | Blue | `F3=Exit   F12=Cancel` |
| 24 | `DUMMY` | (24,79) | 1 | DRK, PROT, ASKIP, FSET | — | Hidden MDT-forcing field |

**Key map design notes:**
- `CUSTNO` has `IC` (Initial Cursor) — cursor positions here automatically.
- `CUSTNO` has the `NUM` attribute (numeric keyboard shift) but **no FSET** — the field is only transmitted when the user explicitly modifies it.
- `ACCOUNT` is an **OCCURS 10** repeating group — 10 identical 79-character protected output lines spanning rows 9–18. Each line holds one full account record formatted inline as a single string.
- The `ACCOUNT` array fields have `FSET` set — they are always transmitted back, preserving previously displayed data between pseudo-conversational cycles.
- There is **no separate field per data element** in the account display — `BNK1CCA` constructs a single formatted string per account and STRINGs it into `ACCOUNTO(n)`. This is a **flat-file style display pattern**, unlike other screens that use named individual output fields.
- The column headers at row 8 define the layout: `SORT CODE` (6), `ACCOUNT NUMBER` (8), `ACCOUNT TYPE` (8), `AVAIL BALANCE` (14), `ACTUAL BALANCE` (14).
- Only `F3=Exit` and `F12=Cancel` are shown in the key legend. There are **no PF5 delete or PF10 update keys** — this is a pure read-only display screen.

**Function Key Legend:**

| Key | Action |
|-----|--------|
| Enter | Look up all accounts for the entered customer number |
| PF3 | Exit — return to main menu (`OMEN`) |
| PF12 / AID | Cancel — send "Session Ended" termination message |
| CLEAR | Clear screen |
| PA1/PA2/PA3 | Continue — no action |

---

## 2. BNK1CCA — Display Customer Accounts Screen Handler

**Program ID:** `BNK1CCA` | **Transaction ID:** `OCCA`

This is the simplest screen-handler program in the suite — it has a single operation (Enter to display accounts) with minimal validation and no update or delete capability. Its primary role is to accept a customer number and orchestrate a call to `INQACCCU`, then format and display up to 10 account records on screen.

---

### 2.1 Validations

#### EDIT-DATA Section

| # | Field | Check | Error Message |
|---|-------|-------|---------------|
| 1 | `CUSTNOI` — numeric | `CUSTNOI NOT NUMERIC` (direct `IS NUMERIC` check — **no BIF DEEDIT applied**) | `Please enter a customer number.` |

**Notable:** This is the only program in the suite that skips `EXEC CICS BIF DEEDIT` before the numeric check. `CUSTNOI` is checked directly with `NOT NUMERIC`. This is simpler but means the field is not stripped of edit characters before the check — since `CUSTNO` carries the `NUM` attribute, only numeric characters should reach the program in any case.

#### POST-LINK Result Checks (GET-CUST-DATA after INQACCCU)

| # | Condition | Error Message |
|---|-----------|---------------|
| 2 | `CUSTOMER-FOUND = 'N'` | `Unable to find customer <number>` (customer number embedded in message) |
| 3 | `NUMBER-OF-ACCOUNTS = ZERO` (after customer found) | `No accounts found for customer` |
| 4 | `COMM-SUCCESS = 'N'` (after customer found, non-zero account count) | `Error accessing accounts for customer <number>.` |

---

### 2.2 Processing

#### Key Press Routing (PREMIERE SECTION — EVALUATE on EIBAID)

| AID Key | Action |
|---------|--------|
| `EIBCALEN = 0` | First time: `LOW-VALUE` to `BNK1ACCO`; cursor on `CUSTNO` (`CUSTNOL = -1`); SEND-ERASE |
| `DFHPA1/PA2/PA3` | `CONTINUE` — no action |
| `DFHPF3` | `EXEC CICS RETURN TRANSID('OMEN') IMMEDIATE` |
| `DFHAID` / `DFHPF12` | Send "Session Ended"; plain `EXEC CICS RETURN` |
| `DFHCLEAR` | `SEND CONTROL ERASE FREEKB`; plain `EXEC CICS RETURN` |
| `DFHENTER` | `PERFORM PROCESS-MAP` |
| Any other key | `LOW-VALUES` to `BNK1ACCO`; "Invalid key pressed."; `CUSTNOL = -1`; SEND-DATAONLY-ALARM |

After all paths: issues `EXEC CICS RETURN TRANSID('OCCA') COMMAREA(WS-COMM-AREA) LENGTH(248)`.

#### PROCESS-MAP Section — Detailed Flow

```
PERFORM RECEIVE-MAP
  (INITIALIZE BNK1ACCI first; then RECEIVE MAP 'BNK1ACC' INTO BNK1ACCI
   Standard receive — no ASIS needed as customer number is numeric only)

PERFORM EDIT-DATA:
  IF CUSTNOI NOT NUMERIC → error message; VALID-DATA-SW='N'

IF VALID-DATA:
  PERFORM GET-CUST-DATA:
    MOVE 20 → NUMBER-OF-ACCOUNTS           (capacity limit passed to INQACCCU)
    MOVE 'N' → COMM-SUCCESS OF INQACCCU-COMMAREA
    MOVE CUSTNOI → CUSTOMER-NUMBER OF INQACCCU-COMMAREA
    SET COMM-PCB-POINTER TO NULL

    EXEC CICS LINK PROGRAM('INQACCCU') COMMAREA(INQACCCU-COMMAREA) SYNCONRETURN

    IF CICS LINK failure → ABEND via ABNDPROC

    IF CUSTOMER-FOUND = 'N':
      Clear all 10 ACCOUNTO(n) array entries to SPACES
      MESSAGE: 'Unable to find customer <CUSTOMER-NUMBER>'
      GO TO GCD999

    Clear all 10 ACCOUNTO(n) array entries to SPACES

    IF NUMBER-OF-ACCOUNTS = ZERO:
      MESSAGE: 'No accounts found for customer'
    ELSE:
      IF COMM-SUCCESS = 'N':
        MESSAGE: 'Error accessing accounts for customer <number>.'
      ELSE:
        Populate NUMBER-OF-ACCOUNTS-DISPLAY (ZZ format)
        MESSAGE: '<n> accounts found'

      PERFORM VARYING WS-INDEX FROM 1 BY 1
      UNTIL WS-INDEX > NUMBER-OF-ACCOUNTS OR WS-INDEX > 10:

        MOVE COMM-SCODE(WS-INDEX) → SCODE-CHAR (X(6))
        MOVE COMM-ACCNO(WS-INDEX) → ACCNO-CHAR (X(8))

        Determine sign for available balance:
          IF COMM-AVAIL-BAL(WS-INDEX) < 0 → WS-AVAIL-BAL-SIGN = '-'
          ELSE                             → WS-AVAIL-BAL-SIGN = '+'

        Determine sign for actual balance:
          IF COMM-ACTUAL-BAL(WS-INDEX) < 0 → WS-ACT-BAL-SIGN = '-'
          ELSE                             → WS-ACT-BAL-SIGN = '+'

        MOVE COMM-AVAIL-BAL(WS-INDEX) → WS-AVAIL-BAL-9
          (overlay via WS-AVAIL-BAL-CONV-X → WS-AVAIL-BAL-X-PND(10) + WS-AVAIL-BAL-X-PNCE(2))

        MOVE COMM-ACTUAL-BAL(WS-INDEX) → WS-ACT-BAL-9
          (overlay via WS-ACT-BAL-CONV-X → WS-ACT-BAL-X-PND(10) + WS-ACT-BAL-X-PNCE(2))

        STRING the following into ACCOUNTO(WS-INDEX) (79 chars):
          SCODE-CHAR        (6)  — Sort code
          '      '          (6)  — spacer
          ACCNO-CHAR        (8)  — Account number
          '         '       (9)  — spacer
          COMM-ACC-TYPE     (8)  — Account type
          '       '         (7)  — spacer
          WS-AVAIL-BAL-SIGN (1)  — + or -
          WS-AVAIL-BAL-X-PND (10) — Integer part of available balance
          '.'               (1)  — decimal point
          WS-AVAIL-BAL-X-PNCE (2) — Pence (cents) of available balance
          '  '              (2)  — spacer
          WS-ACT-BAL-SIGN   (1)  — + or -
          WS-ACT-BAL-X-PND  (10) — Integer part of actual balance
          '.'               (1)  — decimal point
          WS-ACT-BAL-X-PNCE (2)  — Pence (cents) of actual balance

SET SEND-DATAONLY-ALARM TO TRUE
PERFORM SEND-MAP
```

**Balance formatting approach:** BNK1CCA uses a REDEFINES overlay technique rather than a `PIC +9(10).99` edit picture. The signed balance (`S9(10)V99 COMP-3`) from INQACCCU is moved into an unsigned `PIC 9(10)V99` working field (`WS-AVAIL-BAL-9`). A REDEFINES group overlays this as `PIC X(10)` (integer digits) + `PIC X(2)` (pence digits). The sign is determined separately via a `< 0` test and held in a single-char field (`WS-AVAIL-BAL-SIGN`). The components are then STRINGed together. This manual approach avoids the `+` prefix and `COMP-3` to display conversion overhead.

**Display limit — accounts capped at 10:** The INQACCCU COMMAREA supports up to 20 accounts (`NUMBER-OF-ACCOUNTS = 20` as capacity limit). BNK1CCA's loop terminates at `WS-INDEX > 10` — so only the first 10 accounts are displayed on screen even if INQACCCU returns up to 20. The message shows the count from INQACCCU (`n accounts found`), which could be up to 20. A customer with 11–20 accounts would show "15 accounts found" but display only 10.

---

### 2.3 Files / Database / CICS Storage

| Resource | Type | Usage |
|----------|------|-------|
| `BNK1ACC` / `BNK1ACC` | CICS BMS Map | Input (`RECEIVE MAP`) and Output (`SEND MAP ERASE` / `DATAONLY` / `DATAONLY ALARM`) |
| `DFHCOMMAREA` (248 bytes) | CICS COMMAREA | Input from `OMEN` or prior `OCCA` cycle; fields: `COMM-EYE` (4), `COMM-SCODE` (6), `COMM-CUSTNO` (10), `COMM-NAME` (60), `COMM-ADDR` (160), `COMM-DOB` (8) |
| `WS-COMM-AREA` (248 bytes) | CICS COMMAREA | Passed on `RETURN TRANSID('OCCA')` — pseudo-conversational loop state |
| `INQACCCU-COMMAREA` (COPY INQACCCU) | CICS COMMAREA | Passed to / received from `INQACCCU` via `EXEC CICS LINK` |
| `ABNDINFO-REC` (COPY ABNDINFO) | CICS COMMAREA | Passed to `ABNDPROC` on any CICS failure |
| No VSAM files or DB2 tables | — | All data access delegated to `INQACCCU` |
| No terminal UCTRAN management | — | Not needed — customer number is numeric only |

---

### 2.4 Programs Called by BNK1CCA

| Program | Call Method | Purpose |
|---------|-------------|---------|
| `INQACCCU` | `EXEC CICS LINK … SYNCONRETURN` | Retrieve all accounts for the customer from DB2 `ACCOUNT` table |
| `ABNDPROC` | `EXEC CICS LINK … COMMAREA(ABNDINFO-REC)` | Abend handler — logs and terminates on any CICS failure |

---

## 3. INQACCCU — Inquire Accounts for Customer Backend

**Program ID:** `INQACCCU` | **Invocation:** `EXEC CICS LINK` from `BNK1CCA` and other callers (`CREACC`, `DELCUS`)

**Purpose:** Takes an incoming customer number, validates the customer exists (via `INQCUST`), then retrieves all associated account records from the DB2 `ACCOUNT` table using a declared cursor. Returns up to 20 account records in the COMMAREA array. This program is shared across multiple transactions — it is called by `BNK1CCA` (display), `CREACC` (create account — to count existing accounts), and `DELCUS` (delete customer — to list accounts for cascade delete).

---

### 3.1 Validations

| # | Check | Logic | Result |
|---|-------|-------|--------|
| 1 | **Customer number = 0** | `CUSTOMER-NUMBER IN DFHCOMMAREA = ZERO` in `CUSTOMER-CHECK` | `CUSTOMER-FOUND='N'`; `NUMBER-OF-ACCOUNTS=0`; return |
| 2 | **Customer number = 9999999999** | `CUSTOMER-NUMBER IN DFHCOMMAREA = '9999999999'` | `CUSTOMER-FOUND='N'`; `NUMBER-OF-ACCOUNTS=0`; return |
| 3 | **Customer not found (INQCUST)** | `INQCUST-INQ-SUCCESS ≠ 'Y'` after link to `INQCUST` | `CUSTOMER-FOUND='N'`; `COMM-FAIL-CODE='1'`; GOBACK |
| 4 | **DB2 cursor OPEN failure** | `SQLCODE ≠ 0` on `EXEC SQL OPEN ACC-CURSOR` | `COMM-SUCCESS='N'`; `COMM-FAIL-CODE='2'`; SYNCPOINT ROLLBACK; if ROLLBACK fails → ABEND `HROL` |
| 5 | **DB2 FETCH failure** (non-100) | `SQLCODE ≠ 0` and `≠ +100` during FETCH loop | `COMM-SUCCESS='N'`; `COMM-FAIL-CODE='3'`; SYNCPOINT ROLLBACK; if ROLLBACK fails → ABEND `HROL` |
| 6 | **DB2 cursor CLOSE failure** | `SQLCODE ≠ 0` on `EXEC SQL CLOSE ACC-CURSOR` | `COMM-SUCCESS='N'`; `COMM-FAIL-CODE='4'`; SYNCPOINT ROLLBACK; if ROLLBACK fails → ABEND `HROL` |
| 7 | **DB2 Storm Drain** (`SQLCODE = 923`) | `CHECK-FOR-STORM-DRAIN-DB2` section | Logged; processing continues with failure path |
| 8 | **DB2 deadlock** (`AD2Z`) | Caught in `ABEND-HANDLING` | SQLCODE, SQLSTATE, SQLERRMC, SQLERRD(1–6) diagnostics displayed; falls through to re-abend |
| 9 | **VSAM RLS abends** (`AFCR`, `AFCS`, `AFCT`) | Caught in `ABEND-HANDLING` | SYNCPOINT ROLLBACK; `COMM-SUCCESS='N'`; graceful `EXEC CICS RETURN` |

---

### 3.2 Processing

#### Main Flow (PREMIERE section)
```
1. MOVE 'N' → COMM-SUCCESS; '0' → COMM-FAIL-CODE
2. EXEC CICS HANDLE ABEND LABEL(ABEND-HANDLING)
3. MOVE SORTCODE → REQUIRED-SORT-CODE OF CUSTOMER-KY

4. PERFORM CUSTOMER-CHECK
   IF CUSTOMER-FOUND = 'N' → COMM-FAIL-CODE='1'; PERFORM GET-ME-OUT-OF-HERE

5. PERFORM READ-ACCOUNT-DB2

6. PERFORM GET-ME-OUT-OF-HERE (EXEC CICS RETURN)
```

#### CUSTOMER-CHECK section (CC010)
```
IF CUSTOMER-NUMBER = ZERO → CUSTOMER-FOUND='N'; NUMBER-OF-ACCOUNTS=0; return
IF CUSTOMER-NUMBER = 9999999999 → CUSTOMER-FOUND='N'; NUMBER-OF-ACCOUNTS=0; return

INITIALIZE INQCUST-COMMAREA
MOVE CUSTOMER-NUMBER → INQCUST-CUSTNO

EXEC CICS LINK PROGRAM('INQCUST ') COMMAREA(INQCUST-COMMAREA)

IF INQCUST-INQ-SUCCESS = 'Y' → CUSTOMER-FOUND='Y'
ELSE                         → CUSTOMER-FOUND='N'; NUMBER-OF-ACCOUNTS=0
```

#### READ-ACCOUNT-DB2 section (RAD010)
```
MOVE CUSTOMER-NUMBER IN DFHCOMMAREA → HV-ACCOUNT-CUST-NO
MOVE SORTCODE → HV-ACCOUNT-SORTCODE

EXEC SQL OPEN ACC-CURSOR
  (ACC-CURSOR declared as:
   SELECT (12 columns) FROM ACCOUNT
   WHERE ACCOUNT_CUSTOMER_NUMBER = :HV-ACCOUNT-CUST-NO
     AND ACCOUNT_SORTCODE = :HV-ACCOUNT-SORTCODE
   FOR FETCH ONLY)

SQLCODE ≠ 0:
  CHECK-FOR-STORM-DRAIN-DB2
  COMM-SUCCESS='N'; CUSTOMER-FOUND='N'; COMM-FAIL-CODE='2'; NUMBER-OF-ACCOUNTS=0
  EXEC CICS SYNCPOINT ROLLBACK
    If ROLLBACK fails → ABEND 'HROL' via ABNDPROC
  GO TO RAD999

PERFORM FETCH-DATA

EXEC SQL CLOSE ACC-CURSOR
  SQLCODE ≠ 0:
    DISPLAY failure; CHECK-FOR-STORM-DRAIN-DB2
    COMM-SUCCESS='N'; CUSTOMER-FOUND='N'; COMM-FAIL-CODE='4'
    EXEC CICS SYNCPOINT ROLLBACK
      If ROLLBACK fails → ABEND 'HROL' via ABNDPROC
    GO TO RAD999

MOVE 'Y' → COMM-SUCCESS
```

#### FETCH-DATA section (FD010)
```
MOVE ZERO → NUMBER-OF-ACCOUNTS

PERFORM UNTIL SQLCODE ≠ 0 OR NUMBER-OF-ACCOUNTS = 20:

  EXEC SQL FETCH FROM ACC-CURSOR INTO :12 host variables

  IF SQLCODE = +100 (no more rows):
    MOVE 'Y' → COMM-SUCCESS
    GO TO FD999  (normal end of data)

  IF SQLCODE ≠ 0 (unexpected error):
    DISPLAY failure; CHECK-FOR-STORM-DRAIN-DB2
    COMM-SUCCESS='N'; CUSTOMER-FOUND='N'; COMM-FAIL-CODE='3'
    EXEC CICS SYNCPOINT ROLLBACK
      If ROLLBACK fails → ABEND 'HROL' via ABNDPROC
    GO TO FD999

  ADD 1 → NUMBER-OF-ACCOUNTS

  Move all 12 host variable fields to COMM-*(NUMBER-OF-ACCOUNTS):
    HV-ACCOUNT-EYECATCHER  → COMM-EYE
    HV-ACCOUNT-CUST-NO     → COMM-CUSTNO
    HV-ACCOUNT-SORTCODE    → COMM-SCODE
    HV-ACCOUNT-ACC-NO      → COMM-ACCNO
    HV-ACCOUNT-ACC-TYPE    → COMM-ACC-TYPE
    HV-ACCOUNT-INT-RATE    → COMM-INT-RATE
    HV-ACCOUNT-OPENED      → DB2-DATE-REFORMAT (YYYY-MM-DD)
      STRING DAY MM YYYY → COMM-OPENED (DDMMYYYY)
    HV-ACCOUNT-OVERDRAFT-LIM → COMM-OVERDRAFT
    HV-ACCOUNT-LAST-STMT   → DB2-DATE-REFORMAT
      STRING DAY MM YYYY → COMM-LAST-STMT-DT (DDMMYYYY)
    HV-ACCOUNT-NEXT-STMT   → DB2-DATE-REFORMAT
      STRING DAY MM YYYY → COMM-NEXT-STMT-DT (DDMMYYYY)
    HV-ACCOUNT-ACTUAL-BAL  → COMM-ACTUAL-BAL
    HV-ACCOUNT-AVAIL-BAL   → COMM-AVAIL-BAL

END-PERFORM (exits when SQLCODE ≠ 0 or 20 accounts retrieved)
```

**Date reformatting:** DB2 stores dates as `YYYY-MM-DD` (10 chars). INQACCCU uses a group-level `DB2-DATE-REFORMAT` structure to overlay and extract year, month, day parts, then STRINGs them into the COMMAREA date fields in `DDMMYYYY` format (8 digits, no separators). Three date fields per account are reformatted: OPENED, LAST-STMT, NEXT-STMT.

**Maximum accounts cap:** The cursor loop terminates at `NUMBER-OF-ACCOUNTS = 20`. BNK1CCA passes 20 as the capacity parameter but only displays up to 10 — the difference (11–20) is returned in the COMMAREA but silently discarded by BNK1CCA's display loop.

#### ABEND-HANDLING section
```
EXEC CICS ASSIGN ABCODE(MY-ABEND-CODE)
EVALUATE MY-ABEND-CODE:
  WHEN 'AD2Z' (DB2 deadlock):
    Display SQLCODE, SQLSTATE, SQLERRMC, SQLERRD(1-6) diagnostics
    → falls through to WS-STORM-DRAIN='N' re-abend

  WHEN 'AFCR' / 'AFCS' / 'AFCT' (VSAM RLS storm-drain):
    MOVE 'Y' → WS-STORM-DRAIN
    EXEC CICS SYNCPOINT ROLLBACK
    If ROLLBACK fails → ABEND 'HROL' via ABNDPROC
    MOVE 'N' → COMM-SUCCESS
    EXEC CICS RETURN  (graceful — storm drain)

IF WS-STORM-DRAIN = 'N':
  EXEC CICS ABEND ABCODE(MY-ABEND-CODE) NODUMP CANCEL
```

---

### 3.3 Files / Database / CICS Storage

| Resource | Type | Mode | Notes |
|----------|------|------|-------|
| `ACCOUNT` (DB2 table) | DB2 Embedded SQL | SELECT (cursor) | `ACC-CURSOR` declared `FOR FETCH ONLY`: `SELECT (12 columns) FROM ACCOUNT WHERE ACCOUNT_CUSTOMER_NUMBER=:custno AND ACCOUNT_SORTCODE=:sort`. Up to 20 rows fetched |
| `DFHCOMMAREA` (COPY INQACCCU) | CICS COMMAREA | Input / Output | `CUSTOMER-NUMBER` in (10 digits); array of up to 20 account records + `NUMBER-OF-ACCOUNTS` + `COMM-SUCCESS` + `COMM-FAIL-CODE` + `CUSTOMER-FOUND` out |
| `INQCUST-COMMAREA` (COPY INQCUST) | Working Storage | Passed to `INQCUST` | Customer existence validation |
| `SORTCODE` (COPY SORTCODE) | Working Storage | Read | Bank sort code constant |
| `OUTPUT-DATA` (COPY ACCOUNT) | Working Storage | Declared | Account record structure (declared but DB2 host variables used directly) |
| `CUSTOMER-AREA` (COPY CUSTOMER) | Working Storage | Declared | Customer structure (declared; content populated via INQCUST link) |
| `ABNDINFO-REC` (COPY ABNDINFO) | Working Storage | Output | Passed to `ABNDPROC` on failure |
| SQLCA | DB2 | Communication area | `SQLCODE`, `SQLSTATE`, `SQLERRMC`, `SQLERRD` checking |
| `EXEC CICS SYNCPOINT ROLLBACK` | CICS Transaction Control | Multiple points | Issued on cursor OPEN, FETCH, or CLOSE failure to maintain consistency |
| No VSAM files | — | — | Purely DB2-based account data access |

---

### 3.4 Programs Called by INQACCCU

| Program | Call Method | Purpose |
|---------|-------------|---------|
| `INQCUST` | `EXEC CICS LINK PROGRAM('INQCUST ')` | Validate customer exists in VSAM `CUSTOMER` file before fetching accounts |
| `ABNDPROC` | `EXEC CICS LINK … COMMAREA(ABNDINFO-REC)` | Abend handler — logs failure when SYNCPOINT ROLLBACK fails or on unexpected abend |

---

### 3.5 INQACCCU COMMAREA Structure (COPY INQACCCU)

| Field | Occurs | Type | Description |
|-------|--------|------|-------------|
| `CUSTOMER-NUMBER` | 1 | PIC 9(10) | Input: customer number to look up |
| `CUSTOMER-FOUND` | 1 | PIC X | Output: `'Y'` = found; `'N'` = not found |
| `NUMBER-OF-ACCOUNTS` | 1 | PIC 9(4) | Input/Output: capacity (20 in); actual count returned |
| `COMM-SUCCESS` | 1 | PIC X | Output: `'Y'` = DB2 operations successful; `'N'` = failure |
| `COMM-FAIL-CODE` | 1 | PIC X | Output: failure reason code |
| `COMM-PCB-POINTER` | 1 | POINTER | IMS/DLI vestige — set to NULL by callers |
| `COMM-EYE(n)` | 1–20 | PIC X(4) | Eyecatcher `'ACCT'` |
| `COMM-CUSTNO(n)` | 1–20 | PIC X(10) | Customer number |
| `COMM-SCODE(n)` | 1–20 | PIC X(6) | Sort code |
| `COMM-ACCNO(n)` | 1–20 | PIC X(8) | Account number |
| `COMM-ACC-TYPE(n)` | 1–20 | PIC X(8) | Account type |
| `COMM-INT-RATE(n)` | 1–20 | PIC S9(4)V99 | Interest rate |
| `COMM-OPENED(n)` | 1–20 | PIC 9(8) | Date opened (DDMMYYYY) |
| `COMM-OVERDRAFT(n)` | 1–20 | PIC S9(9) COMP | Overdraft limit |
| `COMM-LAST-STMT-DT(n)` | 1–20 | PIC 9(8) | Last statement date (DDMMYYYY) |
| `COMM-NEXT-STMT-DT(n)` | 1–20 | PIC 9(8) | Next statement date (DDMMYYYY) |
| `COMM-AVAIL-BAL(n)` | 1–20 | PIC S9(10)V99 | Available balance |
| `COMM-ACTUAL-BAL(n)` | 1–20 | PIC S9(10)V99 | Actual balance |

---

## 4. Cross-Component Call Chain Summary

```
BNKMENU  (OMEN)
  │
  └── Option A ──► RETURN TRANSID('OCCA')
                       │
                       ▼
                   BNK1CCA  (OCCA)
                       │
                       ├── EXEC CICS RECEIVE MAP 'BNK1ACC'
                       │       User enters: CUSTNO (10 digits)
                       │
                       ├── EDIT-DATA:
                       │     Direct NOT NUMERIC check on CUSTNOI
                       │     (no BIF DEEDIT — unique in the suite)
                       │
                       ├── EXEC CICS LINK ──► INQACCCU
                       │       │
                       │       ├── CUSTOMER-CHECK:
                       │       │     Guard: CUSTNO=0 or 9999999999 → fail
                       │       │     EXEC CICS LINK ──► INQCUST
                       │       │       READ FILE('CUSTOMER') by sort+custno
                       │       │       Returns: INQCUST-INQ-SUCCESS Y/N
                       │       │
                       │       ├── READ-ACCOUNT-DB2:
                       │       │     EXEC SQL OPEN ACC-CURSOR
                       │       │       (SELECT WHERE CUSTNO=:c AND SORT=:s
                       │       │        FOR FETCH ONLY)
                       │       │     PERFORM FETCH-DATA:
                       │       │       Loop: EXEC SQL FETCH (up to 20 rows)
                       │       │         Date reformat: YYYY-MM-DD → DDMMYYYY
                       │       │         SQLCODE=+100 → end of data → COMM-SUCCESS='Y'
                       │       │     EXEC SQL CLOSE ACC-CURSOR
                       │       │
                       │       └── Returns: COMM-SUCCESS, NUMBER-OF-ACCOUNTS,
                       │                    CUSTOMER-FOUND, COMM-*(1..n)
                       │
                       ├── IF CUSTOMER-FOUND='N' → error message; clear screen
                       ├── IF NUMBER-OF-ACCOUNTS=0 → 'No accounts found'
                       ├── ELSE:
                       │     PERFORM WS-INDEX 1 TO MIN(NUMBER-OF-ACCOUNTS, 10):
                       │       Determine +/- sign for each balance
                       │       Convert balances via REDEFINES overlay
                       │       STRING sort+accno+type+avail+actual → ACCOUNTO(n)
                       │     MESSAGE: '<n> accounts found'
                       │
                       └── EXEC CICS RETURN TRANSID('OCCA') COMMAREA(WS-COMM-AREA) LENGTH(248)
                               (pseudo-conversational loop)
```

### CICS COMMAREA Flow

```
BNKMENU  ──(RETURN TRANSID 'OCCA', no COMMAREA)─────────► BNK1CCA (EIBCALEN=0 first pass)
BNK1CCA  ──(INQACCCU-COMMAREA, COPY INQACCCU)───────────► INQACCCU
INQACCCU ──(INQCUST-COMMAREA, COPY INQCUST)─────────────► INQCUST ──► INQACCCU
BNK1CCA  ──(WS-COMM-AREA, 248 bytes)────────────────────► OCCA (self-return, pseudo-conv loop)
```

**Note:** `WS-COMM-AREA` in BNK1CCA has the same structure as `DFHCOMMAREA` (eye, sortcode, custno, name, addr, DOB) — 248 bytes. However, these fields are **never populated** by BNK1CCA itself; the COMMAREA is carried forward as-is from whatever was passed in on entry. The program does not store any retrieved account data in the COMMAREA between pseudo-conversational cycles. All account data is fetched fresh on every Enter press.

---

## 5. Fail Code Reference

### BNK1CCA — INQACCCU Result Handling

| Condition | Source | Message in BNK1CCA |
|-----------|--------|-------------------|
| `CUSTOMER-FOUND = 'N'` | INQACCCU | `Unable to find customer <number>` |
| `NUMBER-OF-ACCOUNTS = ZERO` | INQACCCU | `No accounts found for customer` |
| `COMM-SUCCESS = 'N'` (non-zero count) | INQACCCU | `Error accessing accounts for customer <number>.` |

### INQACCCU Fail Codes

| Fail Code | Meaning | COMM-SUCCESS |
|-----------|---------|-------------|
| `0` | Initial / success | `'N'` initially; set to `'Y'` on success |
| `1` | Customer not found (INQCUST returned failure) | `'N'` |
| `2` | DB2 cursor OPEN failed | `'N'` |
| `3` | DB2 FETCH failed (unexpected error) | `'N'` |
| `4` | DB2 cursor CLOSE failed | `'N'` |

### Abend Codes Across All Programs

| Abend Code | Program | Trigger |
|-----------|---------|---------|
| `HBNK` | BNK1CCA | Any CICS failure (RECEIVE MAP, SEND MAP, RETURN TRANSID, LINK) |
| `HROL` | INQACCCU | SYNCPOINT ROLLBACK failure on cursor OPEN, FETCH, CLOSE, or VSAM RLS abend |

---

## 6. Screen Flow and Key Behaviour

```
┌──────────────────────────────────────────────────────────────────────┐
│  BNK1ACC — First Time (EIBCALEN=0)                                  │
│  CICS Banking Sample Application - Accounts for Customers.          │
│  Provide a Customer number. Then press Enter.                       │
│                                                                      │
│  CUSTOMER NUMBER __________                                         │
│                                                                      │
│  SORT CODE   ACCOUNT NUMBER   ACCOUNT TYPE    AVAIL BALANCE   ACTUAL BALANCE│
│  (blank rows 9–18)                                                  │
│  F3=Exit   F12=Cancel                                               │
└──────────────────────┬───────────────────────────────────────────────┘
                       │ User enters customer number (e.g. 0000000003), ENTER
                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  BNK1ACC — After Successful Lookup                                  │
│  CUSTOMER NUMBER 0000000003                                         │
│                                                                      │
│  SORT CODE   ACCOUNT NUMBER   ACCOUNT TYPE    AVAIL BALANCE   ACTUAL BALANCE│
│  987654      00000010         CURRENT        +0000472807.57  +0000472807.57 │
│  987654      00000025         SAVING         +0000012000.00  +0000012000.00 │
│  ...                                                                │
│  MESSAGE: 2 accounts found                                          │
│  F3=Exit   F12=Cancel                                               │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 7. Key Design Points and Comparisons

### Unique Design Features of This Transaction

| Aspect | Detail |
|--------|--------|
| Single-string account display | Each account row is built as one 79-character STRING and placed into `ACCOUNTO(n)`. No individual named output fields for sortcode, accno, type, balances — unique to this screen in the suite |
| OCCURS 10 array output | `ACCOUNT OCCURS 10` in the BMS map — all 10 display slots are defined as one repeating field. BNK1CCA populates slots via indexed references `ACCOUNTO(WS-INDEX)` |
| No BIF DEEDIT | `EDIT-DATA` uses a direct `NOT NUMERIC` check on `CUSTNOI` without first issuing `EXEC CICS BIF DEEDIT`. Every other numeric input field in the suite uses BIF DEEDIT first |
| Same mapset and map name | Mapset `BNK1ACC` and map `BNK1ACC` share identical names — the only case of this in the suite |
| 20 returned vs 10 displayed | INQACCCU returns up to 20 accounts; BNK1CCA only displays the first 10. The message count (`n accounts found`) reflects the INQACCCU total, which may exceed what is shown |
| COMMAREA never updated | BNK1CCA never writes any retrieved data into `WS-COMM-AREA` before returning. The COMMAREA fields (eye, scode, custno, name, addr, DOB) carry the values from the initial entry — all account data is re-fetched on each Enter press |
| Manual balance sign + overlay | Balances are signed using separate `WS-AVAIL-BAL-SIGN` / `WS-ACT-BAL-SIGN` fields (populated by `< 0` tests), then STRINGed with unsigned integer and pence portions extracted via REDEFINES overlays — a custom approach vs the `PIC +9(10).99` edit pictures used in other programs |
| COMM-PCB-POINTER set to NULL | `BNK1CCA` initialises `SET COMM-PCB-POINTER TO NULL` before linking to `INQACCCU` — a vestige of IMS/DLI support that was available in earlier versions of this program |
| Read-only screen | No PF5 delete, PF10 update, or any modification capability. This is a pure inquiry screen — the simplest in the suite alongside `INQCUST` |

### Comparison with Other Account Display Functions

| Aspect | `OCCA` — Display Customer Accounts (`BNK1CCA`) | `ODAC` — Display Account (`BNK1DAC`) |
|--------|-----------------------------------------------|--------------------------------------|
| Input | Customer number (10 digits) | Account number (8 digits) |
| Output | Up to 10 accounts (array display) | Single account (individual fields) |
| Backend | `INQACCCU` (DB2 cursor — multiple rows) | `INQACC` (DB2 cursor — single row) |
| Customer validation | Yes — via INQCUST inside INQACCCU | No — account is looked up directly |
| Delete capability | No | Yes — PF5 |
| Display fields | Single STRING per row (OCCURS 10) | Individual named map fields |
| BIF DEEDIT used | No | Yes |
| Balance format | Manual sign + REDEFINES overlay | `PIC +9(10).99` edit picture |
| COMMAREA updated on return | No | Yes — INQACC data stored for delete validation |
| COMMAREA size | 248 bytes | 102 bytes |

---

*Analysis generated from source review of `BNK1ACC.bms`, `BNK1CCA.cbl`, and `INQACCCU.cbl`.*

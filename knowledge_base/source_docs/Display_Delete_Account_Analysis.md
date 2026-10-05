# Display / Delete Account — Component Analysis
## CICS Banking Sample Application

> **Transaction:** `ODAC` (triggered from `OMEN` Menu Option 2)
> **Components:** `BNK1DAM` (BMS Map) · `BNK1DAC` (Screen Handler) · `INQACC` (Account Inquiry) · `DELACC` (Account Delete)

---

## Table of Contents

1. [BNK1DAM — BMS Map (BNK1DA)](#1-bnk1dam--bms-map-bnk1da)
2. [BNK1DAC — Display / Delete Account Screen Handler](#2-bnk1dac--display--delete-account-screen-handler)
3. [INQACC — Inquire Account](#3-inqacc--inquire-account)
4. [DELACC — Delete Account](#4-delacc--delete-account)
5. [Cross-Component Call Chain Summary](#5-cross-component-call-chain-summary)
6. [Fail Code Reference](#6-fail-code-reference)
7. [Screen Flow and Key Behaviour](#7-screen-flow-and-key-behaviour)
8. [Key Differences vs Display Customer (ODCS)](#8-key-differences-vs-display-customer-odcs)

---

## 1. BNK1DAM — BMS Map (BNK1DA)

**Mapset:** `BNK1DAM` | **Map:** `BNK1DA` | **Source:** `BNK1DAM.bms`

---

### 1.1 Map Identity

| Attribute | Value |
|-----------|-------|
| Mapset Name | `BNK1DAM` |
| Map Name | `BNK1DA` |
| Terminal Type | 3270-2 |
| Mode | INOUT |
| Language | COBOL |
| Storage | AUTO |
| Control | FREEKB |
| Extended Attributes | COLOR, HILIGHT, OUTLINE, PS, SOSI |
| Title | `CICS Banking Sample Application - Display Account.` (Red, Row 1) |
| Instruction | `Provide an ACCOUNT number. Then press Enter.` (Turquoise, Row 3) |

---

### 1.2 Map Fields — Screen Layout

| Row | Field Name | Position | Length | Attributes | Color | Description |
|-----|-----------|----------|--------|------------|-------|-------------|
| 1 | *(literal)* | (1,1) | 7 | PROT, NORM | Blue | Map ID label `BNK1DA` |
| 1 | `COMPANY` | (1,16) | 55 | NORM, PROT | Red | Title banner |
| 3 | *(literal)* | (3,1) | 44 | NORM, PROT | Turquoise | Instruction text |
| 5 | *(literal)* | (5,1) | 15 | NORM, PROT | Turquoise | Label: `ACCOUNT NUMBER` |
| 5 | `ACCNO` | (5,17) | 8 | NORM, NUM, IC | Green + Underline | **Input:** Account Number (numeric-only; cursor auto-positioned; IC attribute) |
| 7 | `CUSTNO` | (7,20) | 10 | PROT, FSET, ASKIP | Neutral | **Output:** Customer Number |
| 8 | `SORTC` | (8,20) | 6 | PROT, FSET, ASKIP | Neutral | **Output:** Sort Code |
| 9 | `ACCNO2` | (9,20) | 10 | PROT, ASKIP, FSET, NORM | Neutral | **Output:** Confirmed Account Number |
| 10 | `ACTYPE` | (10,20) | 8 | PROT, ASKIP, FSET, NORM | Neutral | **Output:** Account Type |
| 11 | `INTRT` | (11,20) | 7 | PROT, ASKIP, FSET, NORM | Neutral | **Output:** Interest Rate (`PICOUT='9999.99'`) |
| 12 | `OPENDD` | (12,20) | 2 | PROT, ASKIP, FSET | Neutral | **Output:** Account Opened — Day |
| 12 | `OPENMM` | (12,25) | 2 | PROT, ASKIP, FSET | Neutral | **Output:** Account Opened — Month |
| 12 | `OPENYY` | (12,30) | 4 | PROT, FSET, ASKIP | Neutral | **Output:** Account Opened — Year |
| 13 | `OVERDR` | (13,20) | 8 | PROT, FSET, ASKIP | Neutral | **Output:** Overdraft Limit |
| 14 | `LSTMTDD` | (14,20) | 2 | PROT, FSET, ASKIP | Neutral | **Output:** Last Statement Date — Day |
| 14 | `LSTMTMM` | (14,25) | 2 | PROT, FSET, ASKIP | Neutral | **Output:** Last Statement Date — Month |
| 14 | `LSTMTYY` | (14,30) | 4 | PROT, FSET, ASKIP | Neutral | **Output:** Last Statement Date — Year |
| 15 | `NSTMTDD` | (15,20) | 2 | PROT, FSET, ASKIP | Neutral | **Output:** Next Statement Date — Day |
| 15 | `NSTMTMM` | (15,25) | 2 | PROT, FSET, ASKIP | Neutral | **Output:** Next Statement Date — Month |
| 15 | `NSTMTYY` | (15,30) | 4 | PROT, FSET, ASKIP | Neutral | **Output:** Next Statement Date — Year |
| 16 | `AVBAL` | (16,19) | 14 | PROT, FSET, ASKIP | Neutral | **Output:** Available Balance (`+9(10).99` format) |
| 17 | `ACTBAL` | (17,19) | 14 | PROT, FSET, ASKIP | Neutral | **Output:** Actual Balance (`+9(10).99` format) |
| 23 | `MESSAGE` | (23,1) | 79 | BRT, PROT, ASKIP | Yellow | **Output:** User / error messages |
| 24 | *(literal)* | (24,1) | 20 | PROT, ASKIP | Blue | `F3=Exit   F12=Cancel` |
| 24 | `DUMMY` | (24,79) | 1 | DRK, PROT, FSET, ASKIP | — | Hidden MDT-forcing field |

**Notes:**
- `ACCNO` (row 5) is the **only** user-input field. All output fields (rows 7–17) are fully protected.
- `ACCNO` carries the `IC` (Initial Cursor) attribute — cursor is placed here automatically on every map display.
- `ACCNO` has the `NUM` attribute — numeric-only keyboard shift is enforced on 3270 terminals.
- `INTRT` uses `PICOUT='9999.99'` — the BMS output picture automatically formats the integer rate.
- Balance fields use a `+9(10).99` edit picture in the program (`AVAILABLE-BALANCE-DISPLAY` / `ACTUAL-BALANCE-DISPLAY`), displaying signed amounts with a leading `+` or `-`.
- Date separator literals (`/`) appear between DD, MM, YYYY fields on rows 12, 14, and 15 in **green** — visually distinguishing them from the data fields.
- Unlike the Display Customer screen (`BNK1DCM`), there is **no PF10 update key** on this map — account details are read-only. Only PF5 (delete) is supported after a successful lookup.

**Function Key Legend:**

| Key | Action |
|-----|--------|
| Enter | Look up and display account details |
| PF3 | Exit — return to main menu (`OMEN`) |
| PF5 | Delete account (available after successful lookup) |
| PF12 | Cancel — send "Session Ended" termination message |
| CLEAR | Clear screen |
| PA1/PA2/PA3 | Continue — no action |

---

## 2. BNK1DAC — Display / Delete Account Screen Handler

**Program ID:** `BNK1DAC` | **Transaction ID:** `ODAC`

This program handles two operations: displaying an account record (Enter) and deleting it (PF5). Unlike `BNK1DCS`, there is no update path — account fields cannot be modified via this screen.

---

### 2.1 Validations

#### EDIT-DATA Section (used for Enter — account lookup)

| # | Field | Check | Error Message |
|---|-------|-------|---------------|
| 1 | `ACCNOI` — presence | `ACCNOI = LOW-VALUES` or `ACCNOL = 0` | `Please enter an account number.` |
| 2 | `ACCNOI` — numeric | `EXEC CICS BIF DEEDIT` applied; `NOT NUMERIC` check | `Please enter an account number.` |

#### VALIDATE-DATA Section (used for PF5 — delete pre-check)

| # | Field | Check | Error Message |
|---|-------|-------|---------------|
| 3 | `COMM-SCODE` | `= ZEROES` or `= LOW-VALUES` (no sort code in COMMAREA — no prior successful lookup) | `Please enter an account number.` |
| 4 | `COMM-ACCNO` | `= ZEROES` or `= LOW-VALUES` (no account number confirmed in COMMAREA) | `Please enter an account number.` |

#### POST-LINK Result Checks (GET-ACC-DATA after INQACC)

| # | Condition | Error Message |
|---|-----------|---------------|
| 5 | `INQACC-ACC-TYPE = SPACES` AND `INQACC-INT-RATE = 0` AND `INQACC-SUCCESS = 'N'` | `Sorry, but that account number was not found.` |

#### POST-LINK Result Checks (DEL-ACC-DATA after DELACC)

| # | Condition | Error Message |
|---|-----------|---------------|
| 6 | `PARMS-SUBPGM-DEL-SUCCESS = 'N'` AND `PARMS-SUBPGM-DEL-FAIL-CD = '1'` | `Sorry, but that account number was not found. Account NOT deleted.` |
| 7 | `PARMS-SUBPGM-DEL-SUCCESS = 'N'` AND `PARMS-SUBPGM-DEL-FAIL-CD = '2'` | `Sorry, but a datastore error occurred. Account NOT deleted.` |
| 8 | `PARMS-SUBPGM-DEL-SUCCESS = 'N'` AND `PARMS-SUBPGM-DEL-FAIL-CD = '3'` | `Sorry, but a delete error occurred. Account NOT deleted.` |
| 9 | `PARMS-SUBPGM-DEL-SUCCESS = 'N'` (any other) | `Sorry, but a delete error occurred. Account NOT deleted.` |

---

### 2.2 Processing

#### Key Press Routing (PREMIERE SECTION — EVALUATE on EIBAID)

| AID Key | Action |
|---------|--------|
| `EIBCALEN = 0` | First time: initialise map and COMMAREA; send blank map with ERASE; cursor on `ACCNO` |
| `DFHPA1/PA2/PA3` | `CONTINUE` — no action |
| `DFHPF3` | `EXEC CICS RETURN TRANSID('OMEN') IMMEDIATE` — back to main menu |
| `DFHPF5` | `PERFORM PROCESS-MAP` — delete path |
| `DFHPF12` | Send "Session Ended"; plain `EXEC CICS RETURN` |
| `DFHCLEAR` | `SEND CONTROL ERASE FREEKB`; plain `EXEC CICS RETURN` |
| `DFHENTER` | `PERFORM PROCESS-MAP` — account lookup path |
| Any other key | `LOW-VALUES` to `BNK1DAO`; "Invalid key pressed."; alarm; `SEND-MAP` |

After all paths, if `EIBCALEN ≠ 0` and `INQACC-EYE = 'ACCT'` (valid account data in COMMAREA):
copies all `INQACC-*` fields to `WS-COMM-AREA`. Otherwise initialises `WS-COMM-AREA`.

Issues `EXEC CICS RETURN TRANSID('ODAC') COMMAREA(WS-COMM-AREA) LENGTH(102)`.

#### PROCESS-MAP Section — Detailed Flow

```
PERFORM RECEIVE-MAP
  (RECEIVE MAP 'BNK1DA' INTO BNK1DAI — standard receive, no ASIS needed
   as no mixed-case input is required for account number)

IF ENTER:
  PERFORM EDIT-DATA  (account number presence + numeric)
  IF VALID:
    PERFORM GET-ACC-DATA:
      INITIALIZE PARMS-SUBPGM, INQACC-COMMAREA
      SET INQACC-PCB1-POINTER TO NULL
      MOVE ACCNOI → PARMS-SUBPGM-ACCNO, INQACC-ACCNO
      EXEC CICS LINK PROGRAM('INQACC') COMMAREA(INQACC-COMMAREA) SYNCONRETURN
      Check returned data:
        IF INQACC-ACC-TYPE=SPACES AND INQACC-INT-RATE=0 AND INQACC-SUCCESS='N':
          → clear all output fields; MESSAGE: 'Sorry, but that account number was not found.'
        ELSE:
          Populate map output fields:
            SORTCO    ← INQACC-SCODE
            CUSTNOO   ← INQACC-CUSTNO
            ACCNO2O   ← INQACC-ACCNO
            ACTYPEO   ← INQACC-ACC-TYPE
            INTRTO    ← INQACC-INT-RATE (formatted via PICOUT='9999.99')
            OPENDDO/OPENMMO/OPENYYO ← INQACC-OPENED (split via COMM-OPENED-SPLIT)
            OVERDRO   ← INQACC-OVERDRAFT
            LSTMTDDO/LSTMTMMO/LSTMTYYO ← INQACC-LAST-STMT-DT (split)
            NSTMTDDO/NSTMTMMO/NSTMTYYO ← INQACC-NEXT-STMT-DT (split)
            AVBALO    ← INQACC-AVAIL-BAL via AVAILABLE-BALANCE-DISPLAY (+9(10).99)
            ACTBALO   ← INQACC-ACTUAL-BAL via ACTUAL-BALANCE-DISPLAY (+9(10).99)
          MESSAGE: 'If you wish to delete the Account press <PF5>.'
  ELSE (EDIT-DATA failed):
    INITIALIZE PARMS-SUBPGM

IF PF5:
  PERFORM VALIDATE-DATA  (COMM-SCODE and COMM-ACCNO not zero/low-values)
  IF VALID:
    PERFORM DEL-ACC-DATA:
      INITIALIZE PARMS-SUBPGM
      COMPUTE PARMS-SUBPGM-ACCNO = FUNCTION NUMVAL(ACCNO2I)
      SET PARMS-SUBPGM-DEL-PCB1/PCB2/PCB3 TO NULL
      EXEC CICS LINK PROGRAM('DELACC') COMMAREA(PARMS-SUBPGM) SYNCONRETURN
      Evaluate PARMS-SUBPGM-DEL-SUCCESS and PARMS-SUBPGM-DEL-FAIL-CD:
        Fail code '1' → 'Sorry, but that account number was not found. Account NOT deleted.'
        Fail code '2' → 'Sorry, but a datastore error occurred. Account NOT deleted.'
        Fail code '3' → 'Sorry, but a delete error occurred. Account NOT deleted.'
        Any other 'N' → 'Sorry, but a delete error occurred. Account NOT deleted.'
        Success 'Y'   → Clear all output map fields (sort, custno, accno2, actype,
                         intrt, dates, overdraft, balances set to SPACE/ZERO)
                         MESSAGE: 'Account <accno> was successfully deleted.'

SET SEND-DATAONLY-ALARM TO TRUE
PERFORM SEND-MAP
```

**Note on ACCNO2I in delete path:** The delete operation uses `ACCNO2I` (the protected confirmed account number from row 9 of the map), not `ACCNOI` (the user-input field from row 5). This is identical in design to how `BNK1DCS` uses `CUSTNO2I` for deletion — ensuring only a previously confirmed displayed account can be deleted.

**Note on SEND-MAP variants:**
- `SEND-ERASE` (flag `'1'`): Full screen send with ERASE — first time through only.
- `SEND-DATAONLY` (flag `'2'`): Data only, no alarm. If MESSAGE is non-blank and non-low-values, overrides it with `'Account lookup successful.'`
- `SEND-DATAONLY-ALARM` (flag `'3'`): Data only with audible alarm — used after all PROCESS-MAP paths.

---

### 2.3 Files / Database / CICS Storage

| Resource | Type | Usage |
|----------|------|-------|
| `BNK1DA` / `BNK1DAM` | CICS BMS Map | Input (`RECEIVE MAP`) and Output (`SEND MAP ERASE` / `DATAONLY` / `DATAONLY ALARM`) |
| `DFHCOMMAREA` (102 bytes) | CICS COMMAREA | Input from `OMEN` or prior `ODAC` cycle; fields: `COMM-EYE`, `COMM-CUSTNO`, `COMM-SCODE`, `COMM-ACCNO`, `COMM-ACC-TYPE`, `COMM-INT-RATE`, `COMM-OPENED`, `COMM-OVERDRAFT`, `COMM-LAST-STMT-DT`, `COMM-NEXT-STMT-DT`, `COMM-AVAIL-BAL`, `COMM-ACTUAL-BAL`, `COMM-SUCCESS`, `COMM-FAIL-CD`, `COMM-DEL-SUCCESS`, `COMM-DEL-FAIL-CD` |
| `WS-COMM-AREA` (102 bytes) | CICS COMMAREA | Passed on `RETURN TRANSID('ODAC')` — pseudo-conversational loop state |
| `INQACC-COMMAREA` (COPY INQACC) | CICS COMMAREA | Passed to / received from `INQACC` via `EXEC CICS LINK` |
| `PARMS-SUBPGM` | CICS COMMAREA | Passed to / received from `DELACC` via `EXEC CICS LINK` |
| `ABNDINFO-REC` (COPY ABNDINFO) | CICS COMMAREA | Passed to `ABNDPROC` on any CICS failure |
| No VSAM files or DB2 tables | — | All data access delegated to `INQACC` and `DELACC` |
| No terminal UCTRAN management | — | Not needed — account number input is numeric only |

---

### 2.4 Programs Called by BNK1DAC

| Program | Call Method | Purpose |
|---------|-------------|---------|
| `INQACC` | `EXEC CICS LINK … SYNCONRETURN` | Retrieve account record by account number from DB2 |
| `DELACC` | `EXEC CICS LINK … SYNCONRETURN` | Delete the account record from DB2 and write PROCTRAN audit |
| `ABNDPROC` | `EXEC CICS LINK … COMMAREA(ABNDINFO-REC)` | Abend handler — logs and terminates on any CICS failure |

---

## 3. INQACC — Inquire Account

**Program ID:** `INQACC` | **Invocation:** `EXEC CICS LINK` from `BNK1DAC`

**Purpose:** Takes an account number as input and retrieves the matching account record from the DB2 `ACCOUNT` table using a declared cursor. Supports two modes: specific account number lookup (normal path) and `99999999` (retrieves the highest-numbered account for the sort code).

---

### 3.1 Validations

| # | Check | Logic | Result |
|---|-------|-------|--------|
| 1 | **Account number = 99999999** | Special value triggers `READ-ACCOUNT-LAST` path (DB2 `ORDER BY ACCOUNT_NUMBER DESC FETCH FIRST 1 ROWS ONLY`) | Last account mode |
| 2 | **DB2 cursor OPEN failure** | `SQLCODE ≠ 0` on `EXEC SQL OPEN ACC-CURSOR` | ABEND `HRAC` via `ABNDPROC`; DISPLAY diagnostic; `CHECK-FOR-STORM-DRAIN-DB2` |
| 3 | **DB2 FETCH — no rows (`SQLCODE = +100`)** | Account not found for given sort code + account number | `INITIALIZE OUTPUT-DATA`; preserve sort code and account number; `INQACC-SUCCESS = 'N'` |
| 4 | **DB2 FETCH — non-zero, non-100 SQLCODE** | Unexpected error during FETCH | `CHECK-FOR-STORM-DRAIN-DB2`; ABEND `HRAC` via `ABNDPROC` |
| 5 | **DB2 cursor CLOSE failure** | `SQLCODE ≠ 0` on `EXEC SQL CLOSE ACC-CURSOR` | ABEND `HRAC` via `ABNDPROC`; `CHECK-FOR-STORM-DRAIN-DB2` |
| 6 | **`ACCOUNT-TYPE` blank after retrieval** | `ACCOUNT-TYPE = SPACES OR LOW-VALUES` — record exists but type is unpopulated | `INQACC-SUCCESS = 'N'` |
| 7 | **`READ-ACCOUNT-LAST` DB2 SELECT failure** | `SQLCODE ≠ 0` on the `ORDER BY … FETCH FIRST 1 ROWS ONLY` SELECT | ABEND `HNCS` via `ABNDPROC`; DISPLAY diagnostic |
| 8 | **DB2 Storm Drain (`SQLCODE = 923`)** | `CHECK-FOR-STORM-DRAIN-DB2` detects connection lost | Logged; processing continues to hard ABEND |
| 9 | **VSAM RLS abends** (`AFCR`, `AFCS`, `AFCT`) | ABEND-HANDLING catches; `SYNCPOINT ROLLBACK` | `INQACC-SUCCESS = 'N'`; `EXEC CICS RETURN` (graceful) |
| 10 | **DB2 deadlock** (`AD2Z`) | ABEND-HANDLING catches | SQLSTATE / SQLERRMC / SQLERRD diagnostics displayed; falls through to `WS-STORM-DRAIN='N'` re-abend |

---

### 3.2 Processing

#### Main Flow (PREMIERE section)
```
1. INITIALIZE OUTPUT-DATA
2. EXEC CICS HANDLE ABEND LABEL(ABEND-HANDLING)
3. MOVE SORTCODE → REQUIRED-SORT-CODE OF ACCOUNT-KY
4. IF INQACC-ACCNO = 99999999:
      PERFORM READ-ACCOUNT-LAST:
        PERFORM GET-LAST-ACCOUNT-DB2:
          EXEC SQL SELECT … FROM ACCOUNT
            WHERE ACCOUNT_SORTCODE = :HV-ACCOUNT-SORTCODE
            ORDER BY ACCOUNT_NUMBER DESC
            FETCH FIRST 1 ROWS ONLY
          Populates OUTPUT-DATA with account fields (date reformatting for OPENED, LAST-STMT, NEXT-STMT)
          SQLCODE ≠ 0 → ABEND 'HNCS'
   ELSE:
      PERFORM READ-ACCOUNT-DB2:
        MOVE INQACC-ACCNO → HV-ACCOUNT-ACC-NO
        MOVE SORTCODE → HV-ACCOUNT-SORTCODE
        EXEC SQL OPEN ACC-CURSOR
          (SELECT all ACCOUNT columns WHERE ACCOUNT_SORTCODE=:sort AND ACCOUNT_NUMBER=:accno)
          SQLCODE ≠ 0 → CHECK-FOR-STORM-DRAIN; ABEND 'HRAC'
        PERFORM FETCH-DATA:
          EXEC SQL FETCH FROM ACC-CURSOR INTO :host-variables
          SQLCODE = +100 → INITIALIZE OUTPUT-DATA; preserve sort+accno; GO TO FD999
          SQLCODE ≠ 0   → CHECK-FOR-STORM-DRAIN; ABEND 'HRAC'
          SQLCODE = 0   → Move all 12 host variables to OUTPUT-DATA fields
                           (Date fields reformatted: DB2 YYYY-MM-DD → DAY/MONTH/YEAR parts)
        EXEC SQL CLOSE ACC-CURSOR
          SQLCODE ≠ 0 → CHECK-FOR-STORM-DRAIN; ABEND 'HRAC'

5. IF ACCOUNT-TYPE OF OUTPUT-DATA = SPACES OR LOW-VALUES:
      MOVE 'N' → INQACC-SUCCESS
   ELSE:
      Move all OUTPUT-DATA fields → INQACC COMMAREA:
        EYE, CUSTNO, SCODE, ACCNO, ACC-TYPE, INT-RATE,
        OPENED, OVERDRAFT, LAST-STMT-DT, NEXT-STMT-DT,
        AVAIL-BAL, ACTUAL-BAL
      MOVE 'Y' → INQACC-SUCCESS

6. EXEC CICS RETURN (via GET-ME-OUT-OF-HERE)
```

#### DB2 Date Reformatting
DB2 stores dates as `YYYY-MM-DD` (10 characters). INQACC uses `DB2-DATE-REFORMAT` group-level structure to reformat all three date fields:

```
DB2-DATE-REFORMAT (overlay):
  DB2-DATE-REF-YR   PIC 9(4)  ← positions 1-4
  FILLER            PIC X     ← position 5 (the '-')
  DB2-DATE-REF-MNTH PIC 99    ← positions 6-7
  FILLER            PIC X     ← position 8 (the '-')
  DB2-DATE-REF-DAY  PIC 99    ← positions 9-10

Applied to: ACCOUNT-OPENED, ACCOUNT-LAST-STMT, ACCOUNT-NEXT-STMT
Results in: ACCOUNT-OPENED-DAY, ACCOUNT-OPENED-MONTH, ACCOUNT-OPENED-YEAR etc. in OUTPUT-DATA
```

#### ABEND-HANDLING Section
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
    MOVE 'N' → INQACC-SUCCESS
    EXEC CICS RETURN  (graceful — storm drain)

IF WS-STORM-DRAIN = 'N':
  Log to ABNDINFO-REC; EXEC CICS LINK ABNDPROC
  EXEC CICS ABEND ABCODE(MY-ABEND-CODE) NODUMP CANCEL
```

---

### 3.3 Files / Database / CICS Storage

| Resource | Type | Mode | Notes |
|----------|------|------|-------|
| `ACCOUNT` (DB2 table) | DB2 Embedded SQL | SELECT (cursor) | `ACC-CURSOR`: `SELECT … WHERE ACCOUNT_SORTCODE=:sort AND ACCOUNT_NUMBER=:accno FOR FETCH ONLY`. One row expected. |
| `ACCOUNT` (DB2 table) | DB2 Embedded SQL | SELECT (singleton) | `GET-LAST-ACCOUNT-DB2`: `SELECT … ORDER BY ACCOUNT_NUMBER DESC FETCH FIRST 1 ROWS ONLY` for the `99999999` lookup mode |
| `DFHCOMMAREA` (COPY INQACC replaces as `DFHCOMMAREA`) | CICS COMMAREA | Input / Output | `INQACC-ACCNO` in; all account fields + `INQACC-SUCCESS` out |
| `OUTPUT-DATA` (COPY ACCOUNT) | Working Storage | Working buffer | Account record populated from DB2 host variables |
| `HOST-ACCOUNT-ROW` | Working Storage | DB2 host variables | Receives all 12 account columns from DB2 FETCH |
| `SORTCODE` (COPY SORTCODE) | Working Storage | Read | Bank sort code constant |
| `ABNDINFO-REC` (COPY ABNDINFO) | Working Storage | Output | Passed to `ABNDPROC` on failure |
| SQLCA | DB2 | Communication area | `SQLCODE`, `SQLSTATE`, `SQLERRMC`, `SQLERRD` checking |
| No VSAM files | — | — | Purely DB2-based account data access |

---

### 3.4 Programs Called by INQACC

| Program | Call Method | Purpose |
|---------|-------------|---------|
| `ABNDPROC` | `EXEC CICS LINK … COMMAREA(ABNDINFO-REC)` | Abend handler — logs DB2 failure details and terminates |

---

### 3.5 INQACC Outcome Reference

| Condition | `INQACC-SUCCESS` | Notes |
|-----------|-----------------|-------|
| Account found and type populated | `'Y'` | All COMMAREA fields populated |
| FETCH returned `SQLCODE +100` (no rows) | `'N'` | COMMAREA account fields blank/zero |
| `ACCOUNT-TYPE = SPACES` after FETCH | `'N'` | Record exists but type field empty |
| VSAM RLS abend caught in ABEND-HANDLING | `'N'` | Graceful return via SYNCPOINT ROLLBACK |
| DB2 errors (OPEN, FETCH, CLOSE failures) | Hard ABEND `HRAC` | No graceful return |
| `READ-ACCOUNT-LAST` SELECT failure | Hard ABEND `HNCS` | No graceful return |

---

## 4. DELACC — Delete Account

**Program ID:** `DELACC` | **Invocation:** `EXEC CICS LINK` from `BNK1DAC` (direct delete) and `DELCUS` (cascade delete)

**Purpose:** Reads an account record from DB2, deletes it, and writes an audit record to the `PROCTRAN` DB2 table. Used both as a standalone delete from the Display Account screen (PF5) and as part of the cascade delete within `DELCUS` when a customer is deleted.

---

### 4.1 Validations

| # | Check | Logic | Fail Code |
|---|-------|-------|-----------|
| 1 | **DB2 SELECT failure (non-100, non-0)** | `SQLCODE NOT = 0 AND SQLCODE NOT = +100` on READ_ACCOUNT_DB2 SELECT | ABEND `HRAC` — hard abend, no fail code returned |
| 2 | **Account not found (`SQLCODE = +100`)** | No row returned for sort code + account number | `DELACC-DEL-SUCCESS = 'N'`; `DELACC-DEL-FAIL-CD = '1'`; immediate return |
| 3 | **DB2 DELETE failure** | `SQLCODE ≠ 0` on `EXEC SQL DELETE FROM ACCOUNT` | `DELACC-DEL-SUCCESS = 'N'`; `DELACC-DEL-FAIL-CD = '3'` |
| 4 | **DB2 PROCTRAN INSERT failure** | `SQLCODE ≠ 0` on `EXEC SQL INSERT INTO PROCTRAN` | ABEND `HWPT` via `ABNDPROC` |

**Note:** There is no `DELACC-DEL-FAIL-CD = '2'` set within DELACC itself. Fail code `'2'` is referenced in `BNK1DAC` error handling for a "datastore error" scenario but is not directly produced by the current DELACC source — it may be reserved for future use or produced by another caller path.

---

### 4.2 Processing

#### Main Flow (PREMIERE section)
```
1. MOVE SORTCODE → REQUIRED-SORT-CODE OF ACCOUNT-KEY-RID

2. PERFORM READ-ACCOUNT-DB2:
   MOVE DELACC-ACCNO → HV-ACCOUNT-ACC-NO
   MOVE SORTCODE → HV-ACCOUNT-SORTCODE
   EXEC SQL SELECT … FROM ACCOUNT
     WHERE ACCOUNT_NUMBER = :HV-ACCOUNT-ACC-NO AND
           ACCOUNT_SORTCODE = :HV-ACCOUNT-SORTCODE
   (Singleton SELECT — no cursor needed for single-row delete)
   
   SQLCODE NOT = 0 AND NOT = +100 → ABEND 'HRAC'
   SQLCODE = +100 (not found):
     INITIALIZE OUTPUT-DATA; preserve sort+accno
     DELACC-DEL-SUCCESS = 'N'; DELACC-DEL-FAIL-CD = '1'
     GO TO RAD999
   SQLCODE = 0 (found):
     Populate OUTPUT-DATA from all 12 host variables
     (Date fields: DB2 YYYY-MM-DD → DAY/MONTH/YEAR parts via DB2-DATE-REFORMAT)
     Copy all account fields to DELACC COMMAREA fields:
       DELACC-EYE, DELACC-CUSTNO, DELACC-SCODE, DELACC-ACCNO,
       DELACC-ACC-TYPE, DELACC-INT-RATE, DELACC-OPENED,
       DELACC-OVERDRAFT, DELACC-LAST-STMT-DT, DELACC-NEXT-STMT-DT,
       DELACC-AVAIL-BAL, DELACC-ACTUAL-BAL
     DELACC-DEL-SUCCESS = 'Y'; DELACC-DEL-FAIL-CD = ' '
     Store ACCOUNT-ACTUAL-BALANCE in ACCOUNT-ACT-BAL-STORE
       (used as PROCTRAN amount)

3. IF DELACC-DEL-SUCCESS = 'Y':
   PERFORM DEL-ACCOUNT-DB2:
     EXEC SQL DELETE FROM ACCOUNT
       WHERE ACCOUNT_SORTCODE = :HV-ACCOUNT-SORTCODE AND
             ACCOUNT_NUMBER = :HV-ACCOUNT-ACC-NO
     SQLCODE ≠ 0:
       DELACC-DEL-SUCCESS = 'N'; DELACC-DEL-FAIL-CD = '3'

4. IF DEL-ACCOUNT-DB2 still shows DELACC-DEL-SUCCESS = 'Y':
   PERFORM WRITE-PROCTRAN → PERFORM WRITE-PROCTRAN-DB2:
     EXEC CICS ASKTIME + FORMATTIME (get date/time)
     Build HOST-PROCTRAN-ROW:
       EYECATCHER = 'PRTR'
       SORT-CODE  = ACCOUNT-SORT-CODE
       ACC-NUMBER = ACCOUNT-NUMBER
       DATE       = today DD.MM.YYYY
       TIME       = HHMMSS
       REF        = EIBTASKN (12 digits)
       TYPE       = PROC-TRAN-TYPE (from PROCTRAN-AREA — 'ODA', branch delete account)
       DESC       = custno(10) + acctype(8) + last-stmt-dd(2) + mm(2) + yyyy(4)
                    + next-stmt-dd(2) + mm(2) + yyyy(4)  [via PROC-DESC-DELACC-* fields]
       AMOUNT     = ACCOUNT-ACT-BAL-STORE (actual balance at time of deletion)
     EXEC SQL INSERT INTO PROCTRAN (…)
     SQLCODE ≠ 0 → ABEND 'HWPT' via ABNDPROC

5. GOBACK (via GET-ME-OUT-OF-HERE)
```

**PROCTRAN type and description detail:** DELACC uses the `PROCTRAN` copybook (`COPY PROCTRAN`) to format the transaction record. It sets `PROC-DESC-DELACC-FLAG` to TRUE and `PROC-TY-BRANCH-DELETE-ACCOUNT` to TRUE — these are condition-name 88-level values in the PROCTRAN copybook that map to the actual type code and description format. The type code resolves to `'ODA'` (Open Delete Account), and the description includes customer number, account type, and last/next statement dates.

---

### 4.3 Files / Database / CICS Storage

| Resource | Type | Mode | Notes |
|----------|------|------|-------|
| `ACCOUNT` (DB2 table) | DB2 Embedded SQL | SELECT (singleton) | Read before delete — `WHERE ACCOUNT_NUMBER=:accno AND ACCOUNT_SORTCODE=:sort` |
| `ACCOUNT` (DB2 table) | DB2 Embedded SQL | DELETE | `DELETE FROM ACCOUNT WHERE ACCOUNT_SORTCODE=:sort AND ACCOUNT_NUMBER=:accno` |
| `PROCTRAN` (DB2 table) | DB2 Embedded SQL | INSERT | Audit record per account deletion; type `ODA`; amount = actual balance at deletion time |
| `DFHCOMMAREA` (COPY DELACC replaces as `DFHCOMMAREA`) | CICS COMMAREA | Input / Output | `DELACC-ACCNO` in; all account fields + `DELACC-DEL-SUCCESS` + `DELACC-DEL-FAIL-CD` out |
| `OUTPUT-DATA` (COPY ACCOUNT) | Working Storage | Working buffer | Account record buffer from DB2 SELECT |
| `PROCTRAN-AREA` (COPY PROCTRAN) | Working Storage | Working buffer | Used to format PROCTRAN description fields via condition-name 88 values |
| `ACCOUNT-CONTROL` (COPY ACCTCTRL) | Working Storage | Declared | Account control area (declared but not actively used in the delete path) |
| `SORTCODE` (COPY SORTCODE) | Working Storage | Read | Bank sort code constant |
| `ABNDINFO-REC` (COPY ABNDINFO) | Working Storage | Output | Passed to `ABNDPROC` on failure |
| SQLCA | DB2 | Communication area | `SQLCODE` checking |
| No VSAM files | — | — | Purely DB2-based — unlike `DELCUS` which also uses VSAM for the customer record |

---

### 4.4 Programs Called by DELACC

| Program | Call Method | Purpose |
|---------|-------------|---------|
| `ABNDPROC` | `EXEC CICS LINK … COMMAREA(ABNDINFO-REC)` | Abend handler — logs DB2 failure details and terminates |

---

### 4.5 DELACC Fail Code Reference

| Fail Code | Meaning | Source | Message in BNK1DAC |
|-----------|---------|--------|-------------------|
| `1` | Account not found in DB2 (`SQLCODE +100`) | `READ-ACCOUNT-DB2` | `Sorry, but that account number was not found. Account NOT deleted.` |
| `2` | Datastore error *(reserved — not directly set by current code)* | — | `Sorry, but a datastore error occurred. Account NOT deleted.` |
| `3` | DB2 DELETE failed (`SQLCODE ≠ 0`) | `DEL-ACCOUNT-DB2` | `Sorry, but a delete error occurred. Account NOT deleted.` |

---

## 5. Cross-Component Call Chain Summary

```
BNKMENU  (OMEN)
  │
  └── Option 2 ──► RETURN TRANSID('ODAC')
                       │
                       ▼
                   BNK1DAC  (ODAC)
                       │
                       ├── EXEC CICS RECEIVE MAP 'BNK1DA'
                       │       User enters: ACCOUNT NUMBER (8 digits)
                       │
                       ├──[ENTER — Account Lookup]─────────────────────────────────┐
                       │   EDIT-DATA (accno presence + numeric)                    │
                       │   PERFORM GET-ACC-DATA:                                   │
                       │     EXEC CICS LINK ──► INQACC                            │
                       │       │  EXEC SQL OPEN ACC-CURSOR                         │
                       │       │  EXEC SQL FETCH FROM ACC-CURSOR                   │
                       │       │     (SELECT WHERE SORTCODE=:s AND ACCNO=:a)       │
                       │       │  EXEC SQL CLOSE ACC-CURSOR                        │
                       │       └── Returns: all account fields + SUCCESS flag      │
                       │   Display on BNK1DA map                                  │
                       │   MESSAGE: 'If you wish to delete the Account press       │
                       │            <PF5>.'                                        │
                       │                                                           │
                       └──[PF5 — Delete Account]───────────────────────────────────┘
                           VALIDATE-DATA (COMM-SCODE and COMM-ACCNO not zero)
                           PERFORM DEL-ACC-DATA:
                             EXEC CICS LINK ──► DELACC
                               │  EXEC SQL SELECT FROM ACCOUNT (singleton)
                               │  EXEC SQL DELETE FROM ACCOUNT
                               │     WHERE SORTCODE=:s AND ACCNO=:a
                               │  EXEC SQL INSERT INTO PROCTRAN (type 'ODA')
                               │     Amount = actual balance at deletion
                               └── Returns: DELACC-DEL-SUCCESS, DELACC-DEL-FAIL-CD
                           Clear all output map fields
                           MESSAGE: 'Account <n> was successfully deleted.'

           EXEC CICS RETURN TRANSID('ODAC') COMMAREA(WS-COMM-AREA) LENGTH(102)
               (pseudo-conversational loop)
```

### CICS COMMAREA Flow

```
BNKMENU   ──(RETURN TRANSID 'ODAC', no COMMAREA)────────► BNK1DAC (EIBCALEN=0 first pass)
BNK1DAC   ──(INQACC-COMMAREA, COPY INQACC)──────────────► INQACC ──► BNK1DAC
BNK1DAC   ──(PARMS-SUBPGM)──────────────────────────────► DELACC ──► BNK1DAC
BNK1DAC   ──(WS-COMM-AREA, 102 bytes)───────────────────► ODAC (self-return, pseudo-conv loop)
```

**COMMAREA guard on RETURN:** Only populates `WS-COMM-AREA` from `INQACC-COMMAREA` if `INQACC-EYE = 'ACCT'` — this prevents stale or initialised data from being stored as if it were a valid account lookup result.

---

## 6. Fail Code Reference

### BNK1DAC — DELACC Result Handling

| Fail Code | Source | Meaning | Message Displayed |
|-----------|--------|---------|------------------|
| `1` | DELACC | Account not found | `Sorry, but that account number was not found. Account NOT deleted.` |
| `2` | DELACC *(reserved)* | Datastore error | `Sorry, but a datastore error occurred. Account NOT deleted.` |
| `3` | DELACC | DB2 DELETE failed | `Sorry, but a delete error occurred. Account NOT deleted.` |
| Other | DELACC | Unknown failure | `Sorry, but a delete error occurred. Account NOT deleted.` |

### Abend Codes Across All Programs

| Abend Code | Program | Trigger |
|-----------|---------|---------|
| `HBNK` | BNK1DAC | Any CICS failure (RECEIVE MAP, SEND MAP, RETURN TRANSID, LINK) |
| `HRAC` | INQACC | DB2 cursor OPEN, FETCH, or CLOSE failure |
| `HRAC` | DELACC | DB2 SELECT failure on READ-ACCOUNT-DB2 (non-100, non-0) |
| `HNCS` | INQACC | DB2 SELECT failure in `GET-LAST-ACCOUNT-DB2` (last account path) |
| `HWPT` | DELACC | DB2 INSERT INTO PROCTRAN failure |
| `HROL` | INQACC | SYNCPOINT ROLLBACK failure after VSAM RLS abend |

---

## 7. Screen Flow and Key Behaviour

```
┌──────────────────────────────────────────────────────────────┐
│  BNK1DA (empty) — EIBCALEN = 0                              │
│  ACCOUNT NUMBER: ________                                    │
│  [all output fields blank]                                   │
│  F3=Exit   F12=Cancel                                        │
└──────────────────────┬───────────────────────────────────────┘
                       │ User types account number (e.g. 00000010), presses ENTER
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  BNK1DA (populated) — Display Mode                          │
│  ACCOUNT NUMBER: 00000010                                    │
│  Customer Number: 0000000003                                 │
│  Sort Code      : 987654                                     │
│  Account Number : 00000010                                   │
│  Account Type   : CURRENT                                    │
│  Interest Rate  : 0000.00                                    │
│  Account Opened : 13 / 11 / 1970                            │
│  Overdraft limit: 00000100                                   │
│  Last statement : 01 / 07 / 2014                            │
│  Next statement : 01 / 08 / 2014                            │
│  Available Bal  : +0000472807.57                            │
│  Actual Balance : +0000472807.57                            │
│                                                              │
│  MESSAGE: If you wish to delete the Account press <PF5>.    │
│  F3=Exit   F12=Cancel                                        │
└──────────────────────┬───────────────────────────────────────┘
                       │ User presses PF5
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  BNK1DA (cleared) — After Successful Delete                 │
│  ACCOUNT NUMBER: ________                                    │
│  [all output fields cleared]                                 │
│                                                              │
│  MESSAGE: Account 00000010 was successfully deleted.        │
│  F3=Exit   F12=Cancel                                        │
└──────────────────────────────────────────────────────────────┘
```

---

## 8. Key Differences vs Display Customer (ODCS)

| Aspect | Display Account (`BNK1DAC` / `ODAC`) | Display Customer (`BNK1DCS` / `ODCS`) |
|--------|--------------------------------------|---------------------------------------|
| Operations supported | Display + Delete only | Display + Delete + **Update** |
| Input field | `ACCNO` (8 digits, NUM attribute) | `CUSTNO` (10 digits, no NUM attribute) |
| Confirmed display field | `ACCNO2` (row 9) used in delete | `CUSTNO2` (row 8) used in delete |
| Terminal UCTRAN management | **Not required** — numeric-only input | Required — mixed-case name/address |
| RECEIVE MAP | Standard (no `ASIS`) | `RECEIVE MAP ASIS` to preserve case |
| Dynamic attribute changes | None — display-only, no update mode | Yes — PF10 unprotects name/address fields |
| COMMAREA mode flag | None — no update mode | `COMM-UPD = 'Y'` flag for update mode |
| COMMAREA length | 102 bytes | 266 bytes |
| Primary data store | DB2 (`ACCOUNT` table via cursor in INQACC) | VSAM (`CUSTOMER` file in INQCUST) |
| Delete data store | DB2 (`ACCOUNT` DELETE in DELACC) | VSAM (`CUSTOMER` DELETE in DELCUS) + cascade account deletes |
| Cascade delete? | No — single account only | Yes — all accounts deleted before customer |
| PROCTRAN type | `ODA` (Open Delete Account) in DELACC | `ODC` (Open Delete Customer) in DELCUS |
| PROCTRAN amount | Actual balance at deletion time | Zero |
| Abend handling in screen | `HBNK` only (no ABEND HANDLE registration) | `HBNK` + `HANDLE ABEND LABEL(ABEND-HANDLING)` registered |
| Programs called | `INQACC`, `DELACC`, `ABNDPROC` | `INQCUST`, `DELCUS`, `UPDCUST`, `ABNDPROC` |
| Backend programs called by delete | `DELACC` only | `DELCUS` → `INQCUST`, `INQACCCU`, `DELACC` (×N) |

---

*Analysis generated from source review of `BNK1DAM.bms`, `BNK1DAC.cbl`, `INQACC.cbl`, and `DELACC.cbl`.*
*Screen images: `BMSUser_Opt_2_EMPTY.jpg` (display mode, no data) and `BMSUser_Opt_2_SUCCESS.jpg` (populated after successful account lookup for account `00000010`).*

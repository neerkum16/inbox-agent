# Update Account — Component Analysis
## CICS Banking Sample Application — Menu Option 5

> **Transaction:** `OUAC` (triggered from `OMEN` Menu Option 5)
> **Components:** `BNK1UAM` (BMS Map) · `BNK1UAC` (Screen Handler) · `INQACC` (Account Inquiry) · `UPDACC` (Account Update Backend)

---

## Table of Contents

1. [BNK1UAM — BMS Map (BNK1UA)](#1-bnk1uam--bms-map-bnk1ua)
2. [BNK1UAC — Update Account Screen Handler](#2-bnk1uac--update-account-screen-handler)
3. [INQACC — Inquire Account](#3-inqacc--inquire-account)
4. [UPDACC — Update Account Backend](#4-updacc--update-account-backend)
5. [Cross-Component Call Chain Summary](#5-cross-component-call-chain-summary)
6. [Fail Code Reference](#6-fail-code-reference)
7. [Screen Flow and Key Behaviour](#7-screen-flow-and-key-behaviour)
8. [Key Design Points and Comparisons](#8-key-design-points-and-comparisons)

---

## 1. BNK1UAM — BMS Map (BNK1UA)

**Mapset:** `BNK1UAM` | **Map:** `BNK1UA` | **Source:** `BNK1UAM.bms`

---

### 1.1 Map Identity

| Attribute | Value |
|-----------|-------|
| Mapset Name | `BNK1UAM` |
| Map Name | `BNK1UA` |
| Terminal Type | 3270-2 |
| Mode | INOUT |
| Language | COBOL |
| Storage | AUTO |
| Control | FREEKB |
| Extended Attributes | COLOR, HILIGHT, OUTLINE, PS, SOSI |
| Title | `CICS Banking Sample Application - Update Account.` (Red, Row 1) |
| Instruction | `Please provide an ACCOUNT number.` (Turquoise, Row 3) |

---

### 1.2 Map Fields — Screen Layout

| Row | Field Name | Position | Length | Attributes | Color | Description |
|-----|-----------|----------|--------|------------|-------|-------------|
| 1 | *(literal)* | (1,1) | 7 | PROT, NORM | Blue | Map ID label `BNK1UA ` |
| 1 | `COMPANY` | (1,17) | 55 | NORM, PROT | Red | Title banner |
| 3 | *(literal)* | (3,1) | 34 | NORM, PROT | Turquoise | Instruction text |
| 5 | *(literal)* | (5,1) | 15 | NORM, PROT | Turquoise | Label: `ACCOUNT NUMBER` |
| 5 | `ACCNO` | (5,17) | 8 | NORM, NUM, IC, UNPROT | Green + Underline | **Input:** Account Number (numeric; IC; editable; **no FSET**) |
| 7 | *(literal)* | (7,1) | 18 | NORM, PROT | Neutral | Label: `Customer Number:` |
| 7 | `CUSTNO` | (7,20) | 10 | NORM, PROT, FSET | Turquoise | **Output:** Customer Number (protected; FSET ensures transmission) |
| 8 | *(literal)* | (8,1) | 18 | NORM, PROT | Neutral | Label: `Sort Code      :` |
| 8 | `SORTC` | (8,20) | 6 | NORM, PROT, FSET | Turquoise | **Output:** Sort Code (protected; FSET) |
| 9 | *(literal)* | (9,1) | 18 | NORM, PROT | Neutral | Label: `Account Number :` |
| 9 | `ACCNO2` | (9,20) | 8 | PROT, NORM, FSET | Turquoise | **Output:** Confirmed Account Number (protected; FSET) |
| 10 | *(literal)* | (10,1) | 18 | NORM, PROT | Neutral | Label: `Account Type   :` |
| 10 | `ACTYPE` | (10,20) | 8 | UNPROT, FSET, NORM | Green + Underline | **Input/Update:** Account Type (editable after inquiry; FSET) |
| 11 | *(literal)* | (11,1) | 18 | NORM, PROT | Neutral | Label: `Interest Rate  :` |
| 11 | `INTRT` | (11,20) | 7 | UNPROT, FSET, NORM | Green + Underline | **Input/Update:** Interest Rate (`PICOUT='9999.99'`; FSET) |
| 12 | *(literal)* | (12,1) | 18 | NORM, PROT | Neutral | Label: `Account Opened :` |
| 12 | `OPENDD` | (12,20) | 2 | NORM, PROT, FSET | Turquoise | **Output:** Opened Date — Day (protected) |
| 12 | *(literal)* | (12,23) | 1 | NORM, PROT | Turquoise | `/` date separator |
| 12 | `OPENMM` | (12,25) | 2 | NORM, PROT, FSET | Turquoise | **Output:** Opened Date — Month (protected) |
| 12 | *(literal)* | (12,28) | 1 | NORM, PROT | Turquoise | `/` date separator |
| 12 | `OPENYY` | (12,30) | 4 | NORM, PROT, FSET | Turquoise | **Output:** Opened Date — Year (protected) |
| 13 | *(literal)* | (13,1) | 18 | NORM, PROT | Neutral | Label: `Overdraft limit:` |
| 13 | `OVERDR` | (13,20) | 8 | NORM, UNPROT, FSET | Green + Underline | **Input/Update:** Overdraft Limit (editable; FSET) |
| 14 | *(literal)* | (14,1) | 18 | NORM, PROT | Neutral | Label: `Last statement :` |
| 14 | `LSTMTDD` | (14,20) | 2 | NORM, PROT, FSET | Turquoise | **Output:** Last Stmt Date — Day (protected) |
| 14 | *(literal)* | (14,23) | 1 | NORM, PROT | Turquoise | `/` date separator |
| 14 | `LSTMTMM` | (14,25) | 2 | NORM, PROT, FSET | Turquoise | **Output:** Last Stmt Date — Month (protected) |
| 14 | *(literal)* | (14,28) | 1 | NORM, PROT | Turquoise | `/` date separator |
| 14 | `LSTMTYY` | (14,30) | 4 | NORM, PROT, FSET | Turquoise | **Output:** Last Stmt Date — Year (protected) |
| 15 | *(literal)* | (15,1) | 18 | NORM, PROT | Neutral | Label: `Next statement :` |
| 15 | `NSTMTDD` | (15,20) | 2 | NORM, PROT, FSET | Turquoise | **Output:** Next Stmt Date — Day (protected) |
| 15 | *(literal)* | (15,23) | 1 | NORM, PROT | Neutral | `/` date separator |
| 15 | `NSTMTMM` | (15,25) | 2 | NORM, PROT, FSET | Turquoise | **Output:** Next Stmt Date — Month (protected) |
| 15 | *(literal)* | (15,28) | 1 | NORM, PROT | Neutral | `/` date separator |
| 15 | `NSTMTYY` | (15,30) | 4 | NORM, PROT, FSET | Turquoise | **Output:** Next Stmt Date — Year (protected) |
| 16 | *(literal)* | (16,1) | 17 | NORM, PROT | Neutral | Label: `Available Bal  :` |
| 16 | `AVBAL` | (16,19) | 14 | NORM, PROT, FSET | Turquoise | **Output:** Available Balance (protected; `+9(10).99` format) |
| 17 | *(literal)* | (17,1) | 17 | NORM, PROT | Neutral | Label: `Actual Balance :` |
| 17 | `ACTBAL` | (17,19) | 14 | NORM, PROT, FSET | Turquoise | **Output:** Actual Balance (protected; `+9(10).99` format) |
| 23 | `MESSAGE` | (23,1) | 79 | BRT, PROT | Yellow | **Output:** User / error messages |
| 24 | *(literal)* | (24,1) | 20 | NORM, PROT | Blue | `F3=Exit   F12=Cancel` |
| 24 | `DUMMY` | (24,79) | 1 | DRK, PROT, FSET | — | Hidden MDT-forcing field |

**Key map design notes:**
- `ACCNO` (row 5) is the **only lookup input field** — it is `UNPROT` and `NUM` with `IC` (initial cursor). Uniquely, it has **no FSET** — it is only transmitted when the user modifies it, unlike most other fields.
- `ACTYPE` (row 10), `INTRT` (row 11), and `OVERDR` (row 13) are **`UNPROT` (editable) with `FSET`** — they are always transmitted back and are the three fields the user can modify after an inquiry.
- All other account fields (customer number, sort code, confirmed account number, opened date, statement dates, balances) are **`PROT`** — read-only display fields with `FSET` to ensure round-trip.
- The balance fields `AVBAL` and `ACTBAL` are **protected** — balances cannot be changed on this screen. The source comment in UPDACC explicitly states: *"the balance cannot be amended using this method"*.
- `INTRT` uses `PICOUT='9999.99'` for BMS output formatting of the interest rate.
- Date fields for Account Opened, Last Statement, and Next Statement are split across individual DD, MM, YYYY fields with `/` separator literals.
- Statement dates (`LSTMTDD/MM/YY`, `NSTMTDD/MM/YY`) are displayed as protected fields — they cannot be directly edited by the user via the BMS screen despite being updatable fields in the backend.

**Function Key Legend:**

| Key | Action |
|-----|--------|
| Enter | Look up and display account details |
| PF3 | Exit — return to main menu (`OMEN`) |
| PF5 | Submit the update (apply changes to Account Type, Interest Rate, Overdraft Limit) |
| PF12 / AID | Cancel — send "Session Ended" termination message |
| CLEAR | Clear screen |
| PA1/PA2/PA3 | Continue — no action |

---

## 2. BNK1UAC — Update Account Screen Handler

**Program ID:** `BNK1UAC` | **Transaction ID:** `OUAC`

This program handles two distinct operations via different function keys: Enter performs an account inquiry (populates the screen), and PF5 submits an update. The two operations use separate validation sections and separate backend program calls, making this a dual-purpose screen handler similar in design to `BNK1DCS` (Display/Update/Delete Customer).

---

### 2.1 Validations

#### EDIT-DATA Section (triggered by Enter — account lookup)

| # | Field | Check | Error Message |
|---|-------|-------|---------------|
| 1 | `ACCNOI` — numeric | Direct `ACCNOI NOT NUMERIC` check (**no BIF DEEDIT** applied) | `Please enter an account number.` |

#### VALIDATE-DATA Section (triggered by PF5 — pre-update validation)

| # | Field | Check | Error Message |
|---|-------|-------|---------------|
| 2 | `ACTYPEI` — value | Must be exactly one of: `CURRENT `, `SAVING  `, `LOAN    `, `MORTGAGE`, `ISA     ` (exact 8-char match) | `Account Type must be CURRENT, SAVING, LOAN, MORTGAGE or ISA. Then press PF5.` |
| 3 | `INTRTL` — presence | `INTRTL = ZERO` (field length zero — nothing entered) | `Please supply a numeric interest rate then press PF5.` |
| 4 | `INTRTI` — character set | `IS NOT NUMERIC` triggers INSPECT TALLYING of digits 0–9, `.`, `-`, `+`, spaces. If `WS-NUM-COUNT-TOTAL < INTRTL` (invalid chars present) | `Please supply a numeric interest rate` |
| 5 | `INTRTI` — multiple decimal points | `WS-NUM-COUNT-POINT > 1` | `Use one decimal point for interest rate only` |
| 6 | `INTRTI` — excessive decimal places | 1 decimal point present; more than 2 non-zero digits after 2nd decimal place | `Only up to two decimal places are supported` |
| 7 | `INTRTI` — negative | `FUNCTION NUMVAL(INTRTI) < 0` | `Please supply a zero or positive interest rate` |
| 8 | `INTRTI` — upper bound | `FUNCTION NUMVAL(INTRTI) > 9999.99` | `Please supply an interest rate less than 9999.99%` |
| 9 | `INTRTI` — zero with LOAN/MORTGAGE | `ACTYPEI = 'LOAN    '` AND `INTRTI = '0000.00'`, or `ACTYPEI = 'MORTGAGE'` AND `INTRTI = '0000.00'` | `Interest rate cannot be 0 with this account type. Correct and press PF5.` |
| 10 | `OVERDRI` — numeric | `OVERDRL = ZERO` OR `OVERDRI(1:OVERDRL) IS NOT NUMERIC` | `Overdraft must be numeric. Correct and press PF5.` |
| 11 | `LSTMTDDI/LSTMTMMI/LSTMTYYI` — numeric | Any of the three last statement date parts `NOT NUMERIC` | `Last statement date must be numeric` |
| 12 | `NSTMTDDI/NSTMTMMI/NSTMTYYI` — numeric | Any of the three next statement date parts `NOT NUMERIC` | `Next statement date must be numeric` |
| 13 | Last Statement date — range | `WS-LSTMTDDI > 31` OR `= 0` OR `WS-LSTMTMMI > 12` OR `= 0` | `Incorrect date for LAST STATEMENT.` |
| 14 | Last Statement date — invalid day/month combinations | Day 31 in months 9, 4, 6, 11; OR day > 29 in month 2 | `Incorrect date for LAST STATEMENT.` |
| 15 | Next Statement date — invalid day/month combinations | Day 31 in months 9, 4, 6, 11; OR day > 29 in month 2 | `Incorrect date for NEXT STATEMENT.` |

**Notes on VALIDATE-DATA:**
- Account type comparison uses exact 8-character values — no normalisation or underscore handling. The BMS `ACTYPE` field is 8 chars; users must enter the value space-padded.
- The interest rate validator uses the same multi-step INSPECT pattern as `BNK1CRA` (Credit/Debit) and `BNK1TFN` (Transfer Funds) — tallying valid characters before checking counts.
- Last statement date range check only validates day and month (01–31, 01–12). There is no year validation.
- Next statement date range checks apply the 30-day month and February rules but only check `NSTMTDDI/NSTMTMMI` numeric presence (no explicit 01–31 guard equivalent to check 13 for last statement). The February check caps at day 29, not day 28 — no leap year logic at this level.
- Statement date fields on the map are `PROT` — the user cannot edit them via the BMS screen. However, the validation code checks the transmitted values from those protected fields. The values come back on PF5 because all statement date fields carry `FSET`.

#### POST-LINK Result Checks (INQ-ACC-DATA after INQACC)

| # | Condition | Error Message |
|---|-----------|---------------|
| 16 | `COMM-ACC-TYPE = SPACES AND COMM-LAST-STMT-DT = ZERO` | `This account number could not be found` |

#### POST-LINK Result Checks (UPD-ACC-DATA after UPDACC)

| # | Condition | Error Message |
|---|-----------|---------------|
| 17 | `COMM-SUCCESS = 'N'` | `Update unsuccessful, try again later.` |

---

### 2.2 Processing

#### Key Press Routing (PREMIERE SECTION — EVALUATE on EIBAID)

| AID Key | Action |
|---------|--------|
| `EIBCALEN = 0` | First time: `LOW-VALUE` to `BNK1UAO`; `ACCNOL = -1`; SEND-ERASE; INITIALIZE `WS-COMM-AREA` |
| `DFHPA1/PA2/PA3` | `CONTINUE` — no action |
| `DFHPF3` | `EXEC CICS RETURN TRANSID('OMEN') IMMEDIATE` |
| `DFHAID` / `DFHPF12` | Send "Session Ended"; plain `EXEC CICS RETURN` |
| `DFHCLEAR` | `SEND CONTROL ERASE FREEKB`; plain `EXEC CICS RETURN` |
| `DFHENTER` | `PERFORM PROCESS-MAP` — account inquiry path |
| `DFHPF5` | `PERFORM PROCESS-MAP` — update submit path |
| Any other key | `LOW-VALUES` to `BNK1UAO`; "Invalid key pressed."; `ACCNOL = -1`; SEND-DATAONLY-ALARM |

Both `DFHENTER` and `DFHPF5` route to the same `PROCESS-MAP` section, which then branches internally based on `EIBAID`.

After all paths: if `EIBCALEN ≠ 0`, copies all DFHCOMMAREA fields to `WS-COMM-AREA`. Issues `EXEC CICS RETURN TRANSID('OUAC') COMMAREA(WS-COMM-AREA) LENGTH(99)`.

#### PROCESS-MAP Section — Detailed Flow

```
PERFORM RECEIVE-MAP
  (RECEIVE MAP 'BNK1UA' MAPSET 'BNK1UAM' INTO BNK1UAI)
MOVE 'Y' TO VALID-DATA-SW

IF EIBAID = DFHENTER:
  PERFORM EDIT-DATA  (account number numeric check only)
  IF VALID-DATA:
    PERFORM INQ-ACC-DATA:
      INITIALIZE DFHCOMMAREA
      MOVE ACCNOI → COMM-ACCNO
      SET COMM-PCB1-POINTER TO NULL
      EXEC CICS LINK PROGRAM('INQACC') COMMAREA(DFHCOMMAREA) SYNCONRETURN
      On CICS failure → ABEND via ABNDPROC

      IF COMM-ACC-TYPE = SPACES AND COMM-LAST-STMT-DT = ZERO:
        VALID-DATA-SW = 'N'
        MESSAGE: 'This account number could not be found'
        ACCNOL = -1
      ELSE:
        Populate all map output fields:
          ACCNO2O  ← COMM-ACCNO
          CUSTNOO  ← COMM-CUSTNO
          SORTCO   ← COMM-SCODE
          ACTYPEO  ← COMM-ACC-TYPE
          INTRTO   ← COMM-INT-RATE (via INTRT-PIC9 conversion 9(4)V99 → PIC9999.99)
          OPENDDO/OPENMMO/OPENYYO ← COMM-OPENED (split via WS-DATE-SPLIT DDMMYYYY)
          LSTMTDDO/LSTMTMMO/LSTMTYYO ← COMM-LAST-STMT-DT (split)
          NSTMTDDO/NSTMTMMO/NSTMTYYO ← COMM-NEXT-STMT-DT (split)
          OVERDRO  ← COMM-OVERDRAFT
          AVBALO   ← COMM-AVAIL-BAL via AVAILABLE-BALANCE-DISPLAY (+9(10).99)
          ACTBALO  ← COMM-ACTUAL-BAL via ACTUAL-BALANCE-DISPLAY (+9(10).99)
        ACCNOL = -1
        MESSAGE: 'Please amend fields and hit <pf5> to apply changes'

IF EIBAID = DFHPF5:
  PERFORM VALIDATE-DATA  (15 checks on type, rate, overdraft, dates)
  IF VALID-DATA:
    PERFORM UPD-ACC-DATA:
      INITIALIZE DFHCOMMAREA
      — Account number:
        IF ACCNOI = 99999999 → use ACCNO2I (confirmed displayed number)
        ELSE                 → use ACCNOI  (direct input)
      MOVE CUSTNOI → COMM-CUSTNO
      MOVE SORTCI  → COMM-SCODE
      MOVE ACTYPEI → COMM-ACC-TYPE
      COMPUTE INTRTI-COMP-1 = FUNCTION NUMVAL(INTRTI)
      MOVE INTRTI-COMP-1 → INT-RT-9 (via REDEFINES overlay)
      MOVE INT-RT-9 → COMM-INT-RATE
      — Date packing: assemble DD/MM/YY parts into WS-DATE-SPLIT then COMM-OPENED/LAST/NEXT
      COMPUTE COMM-OVERDRAFT = FUNCTION NUMVAL(OVERDRI(1:OVERDRL))
      — Balance conversion (AVBALI/ACTBALI):
        MOVE field → WS-CONVERT-PICX (overlay: SIGN(1) + DEC(10) + POINT(1) + REMAIN(2))
        COMPUTE pence portion = WS-CONVERT-REMAIN / 100
        COMPUTE integer portion = WS-CONVERT-DEC
        COMPUTE combined = pence + integer
        Apply sign: IF WS-CONVERT-SIGN='-' → negate; ELSE → positive
        MOVE result → COMM-AVAIL-BAL / COMM-ACTUAL-BAL
      MOVE ' ' → COMM-SUCCESS

      EXEC CICS LINK PROGRAM('UPDACC') COMMAREA(DFHCOMMAREA) SYNCONRETURN
      On CICS failure → ABEND via ABNDPROC

      IF COMM-SUCCESS = 'N':
        MESSAGE: 'Update unsuccessful, try again later.'
      ELSE:
        Populate all map output fields from COMMAREA (same as inquiry path)
        MESSAGE: 'Account update successfully applied.'

SET SEND-DATAONLY-ALARM TO TRUE
PERFORM SEND-MAP
```

**Special ACCNO handling for `99999999`:** In `UPD-ACC-DATA`, if the input account number field (`ACCNOI`) equals `99999999` (the sentinel for "last account"), the program substitutes `ACCNO2I` (the confirmed displayed account number from row 9). This prevents the update COMMAREA from carrying `99999999` as the target account, ensuring the update goes to the correct account already displayed on screen.

**Balance conversion in `UPD-ACC-DATA`:** The available and actual balance fields (`AVBALI`/`ACTBALI`) are protected on the map but still transmitted back via `FSET`. Their displayed format is `+9(10).99` (e.g. `+0000472807.57`). BNK1UAC parses these back to numeric using a `WS-CONVERT-PICX` REDEFINES overlay that splits the 14-character string into sign(1), integer(10), decimal point(1), and pence(2). This reconstructed balance is passed to UPDACC via COMMAREA, though UPDACC does not actually update the balances (they are preserved from the DB2 SELECT result).

---

### 2.3 Files / Database / CICS Storage

| Resource | Type | Usage |
|----------|------|-------|
| `BNK1UA` / `BNK1UAM` | CICS BMS Map | Input (`RECEIVE MAP`) and Output (`SEND MAP ERASE CURSOR` / `DATAONLY CURSOR` / `DATAONLY ALARM CURSOR`) |
| `DFHCOMMAREA` (99 bytes) | CICS COMMAREA | Dual-purpose: input from prior `OUAC` cycle AND passed directly to `INQACC`/`UPDACC` via `EXEC CICS LINK`. Fields: `COMM-EYE`, `COMM-CUSTNO`, `COMM-SCODE`, `COMM-ACCNO`, `COMM-ACC-TYPE`, `COMM-INT-RATE`, `COMM-OPENED`, `COMM-OVERDRAFT`, `COMM-LAST-STMT-DT`, `COMM-NEXT-STMT-DT`, `COMM-AVAIL-BAL`, `COMM-ACTUAL-BAL`, `COMM-SUCCESS`, `COMM-PCB1-POINTER` |
| `WS-COMM-AREA` (99 bytes) | CICS COMMAREA | Passed on `RETURN TRANSID('OUAC')` — pseudo-conversational loop state |
| `ABNDINFO-REC` (COPY ABNDINFO) | CICS COMMAREA | Passed to `ABNDPROC` on any CICS failure |
| No VSAM files or DB2 tables | — | All data access delegated to `INQACC` and `UPDACC` |
| No terminal UCTRAN management | — | Not needed — inputs are coded values (account type, numeric interest rate, numeric overdraft) |

**Note:** Unlike most other programs in the suite which use a separate `WS-COMM-AREA` and copy fields from `DFHCOMMAREA`, BNK1UAC uses `DFHCOMMAREA` directly as the COMMAREA passed to both `INQACC` and `UPDACC` (`COMMAREA(DFHCOMMAREA)`). The `DFHCOMMAREA` is first `INITIALIZE`d in `INQ-ACC-DATA` and `UPD-ACC-DATA` before being populated — which clears any prior cycle values.

---

### 2.4 Programs Called by BNK1UAC

| Program | Call Method | Purpose |
|---------|-------------|---------|
| `INQACC` | `EXEC CICS LINK … SYNCONRETURN` | Retrieve account record from DB2 by account number |
| `UPDACC` | `EXEC CICS LINK … SYNCONRETURN` | Update account type, interest rate, and overdraft limit in DB2 |
| `ABNDPROC` | `EXEC CICS LINK … COMMAREA(ABNDINFO-REC)` | Abend handler — logs and terminates on any CICS failure |

---

## 3. INQACC — Inquire Account

**Program ID:** `INQACC` | **Invocation:** `EXEC CICS LINK` from `BNK1UAC` (and `BNK1DAC` — shared program)

**Purpose:** Takes an account number, retrieves the matching account record from the DB2 `ACCOUNT` table using a declared cursor, and returns all 12 account fields. Supports two modes: specific account number and `99999999` (last/highest-numbered account in the sort code). This program is shared across `BNK1UAC` (Update Account) and `BNK1DAC` (Display Account) — the same `INQACC` is used by both transactions.

---

### 3.1 Validations

| # | Check | Logic | Result |
|---|-------|-------|--------|
| 1 | **Account number = `99999999`** | Special value triggers `READ-ACCOUNT-LAST` path (DB2 `SELECT … ORDER BY ACCOUNT_NUMBER DESC FETCH FIRST 1 ROWS ONLY`) | Last account mode |
| 2 | **DB2 cursor OPEN failure** | `SQLCODE ≠ 0` on `EXEC SQL OPEN ACC-CURSOR` | ABEND `HRAC` via `ABNDPROC`; CHECK-FOR-STORM-DRAIN-DB2 |
| 3 | **DB2 FETCH — no rows** (`SQLCODE = +100`) | No account found for sort code + account number | `INITIALIZE OUTPUT-DATA`; preserve sort + accno; `INQACC-SUCCESS = 'N'` |
| 4 | **DB2 FETCH — other failure** | `SQLCODE ≠ 0` and `≠ +100` | CHECK-FOR-STORM-DRAIN-DB2; ABEND `HRAC` |
| 5 | **DB2 cursor CLOSE failure** | `SQLCODE ≠ 0` on `EXEC SQL CLOSE ACC-CURSOR` | ABEND `HRAC`; CHECK-FOR-STORM-DRAIN-DB2 |
| 6 | **`ACCOUNT-TYPE` blank after retrieval** | `ACCOUNT-TYPE = SPACES OR LOW-VALUES` | `INQACC-SUCCESS = 'N'` |
| 7 | **`READ-ACCOUNT-LAST` SELECT failure** | `SQLCODE ≠ 0` on `ORDER BY DESC FETCH FIRST 1 ROWS ONLY` | ABEND `HNCS` via `ABNDPROC` |
| 8 | **DB2 Storm Drain** (`SQLCODE = 923`) | `CHECK-FOR-STORM-DRAIN-DB2` | Logged; processing continues with failure path |
| 9 | **VSAM RLS abends** (`AFCR`, `AFCS`, `AFCT`) | Caught in `ABEND-HANDLING` | SYNCPOINT ROLLBACK; `INQACC-SUCCESS = 'N'`; graceful `EXEC CICS RETURN` |
| 10 | **DB2 deadlock** (`AD2Z`) | Caught in `ABEND-HANDLING` | SQLSTATE/SQLERRMC/SQLERRD diagnostics displayed; falls through to re-abend |

---

### 3.2 Processing

#### Main Flow (PREMIERE section)
```
1. INITIALIZE OUTPUT-DATA
2. EXEC CICS HANDLE ABEND LABEL(ABEND-HANDLING)
3. MOVE SORTCODE → REQUIRED-SORT-CODE

4. IF INQACC-ACCNO = 99999999:
     PERFORM READ-ACCOUNT-LAST:
       PERFORM GET-LAST-ACCOUNT-DB2:
         EXEC SQL SELECT (12 columns) FROM ACCOUNT
           WHERE ACCOUNT_SORTCODE = :sort
           ORDER BY ACCOUNT_NUMBER DESC
           FETCH FIRST 1 ROWS ONLY
         Populates OUTPUT-DATA with date reformatting (YYYY-MM-DD → DAY/MONTH/YEAR)
         SQLCODE ≠ 0 → ABEND 'HNCS'
   ELSE:
     PERFORM READ-ACCOUNT-DB2:
       MOVE INQACC-ACCNO → HV-ACCOUNT-ACC-NO
       MOVE SORTCODE → HV-ACCOUNT-SORTCODE
       EXEC SQL OPEN ACC-CURSOR
         (SELECT 12 columns FROM ACCOUNT
          WHERE ACCOUNT_SORTCODE=:sort AND ACCOUNT_NUMBER=:accno
          FOR FETCH ONLY)
         SQLCODE ≠ 0 → CHECK-STORM-DRAIN; ABEND 'HRAC'
       PERFORM FETCH-DATA:
         EXEC SQL FETCH FROM ACC-CURSOR INTO :host-variables
         SQLCODE = +100 → INITIALIZE OUTPUT-DATA; preserve sort+accno; GO TO FD999
         SQLCODE ≠ 0   → CHECK-STORM-DRAIN; ABEND 'HRAC'
         SQLCODE = 0   → Move all 12 fields; date reformat YYYY-MM-DD → parts
       EXEC SQL CLOSE ACC-CURSOR
         SQLCODE ≠ 0 → CHECK-STORM-DRAIN; ABEND 'HRAC'

5. IF ACCOUNT-TYPE = SPACES OR LOW-VALUES:
     MOVE 'N' → INQACC-SUCCESS
   ELSE:
     Move all OUTPUT-DATA fields → INQACC COMMAREA
     MOVE 'Y' → INQACC-SUCCESS

6. EXEC CICS RETURN
```

#### DB2 Date Reformatting
DB2 stores dates as `YYYY-MM-DD`. INQACC uses a `DB2-DATE-REFORMAT` group overlay to extract year, month, day parts:
```
DB2-DATE-REF-YR   PIC 9(4)  ← positions 1-4
FILLER            PIC X      ← '-'
DB2-DATE-REF-MNTH PIC 99    ← positions 6-7
FILLER            PIC X      ← '-'
DB2-DATE-REF-DAY  PIC 99    ← positions 9-10
```
Applied to `ACCOUNT-OPENED`, `ACCOUNT-LAST-STMT`, `ACCOUNT-NEXT-STMT`. Results stored in separate `ACCOUNT-OPENED-DAY`, `ACCOUNT-OPENED-MONTH`, `ACCOUNT-OPENED-YEAR` etc. fields in `OUTPUT-DATA`.

#### ABEND-HANDLING section
```
EXEC CICS ASSIGN ABCODE(MY-ABEND-CODE)
EVALUATE MY-ABEND-CODE:
  WHEN 'AD2Z': Display DB2 deadlock diagnostics → re-abend
  WHEN 'AFCR' / 'AFCS' / 'AFCT' (VSAM RLS storm-drain):
    SYNCPOINT ROLLBACK
    If ROLLBACK fails → ABEND 'HROL' via ABNDPROC
    MOVE 'N' → INQACC-SUCCESS
    EXEC CICS RETURN (graceful)
IF WS-STORM-DRAIN = 'N':
  EXEC CICS ABEND ABCODE(MY-ABEND-CODE) NODUMP CANCEL
```

---

### 3.3 Files / Database / CICS Storage

| Resource | Type | Mode | Notes |
|----------|------|------|-------|
| `ACCOUNT` (DB2 table) | DB2 Embedded SQL | SELECT (cursor) | `ACC-CURSOR`: `SELECT 12 cols FROM ACCOUNT WHERE SORTCODE=:s AND ACCOUNT_NUMBER=:a FOR FETCH ONLY` |
| `ACCOUNT` (DB2 table) | DB2 Embedded SQL | SELECT (singleton) | `GET-LAST-ACCOUNT-DB2`: `SELECT … ORDER BY ACCOUNT_NUMBER DESC FETCH FIRST 1 ROWS ONLY` for `99999999` mode |
| `DFHCOMMAREA` (COPY INQACC as `DFHCOMMAREA`) | CICS COMMAREA | Input / Output | `INQACC-ACCNO` in; all 12 account fields + `INQACC-SUCCESS` out |
| `OUTPUT-DATA` (COPY ACCOUNT) | Working Storage | Working buffer | Account record populated from DB2 host variables |
| `SORTCODE` (COPY SORTCODE) | Working Storage | Read | Bank sort code constant |
| `ABNDINFO-REC` (COPY ABNDINFO) | Working Storage | Output | Passed to `ABNDPROC` on failure |
| SQLCA | DB2 | Communication area | `SQLCODE`, `SQLSTATE`, `SQLERRMC`, `SQLERRD` checking |
| No VSAM files | — | — | Purely DB2-based |

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
| FETCH returned `SQLCODE +100` (not found) | `'N'` | Fields blank/zero |
| `ACCOUNT-TYPE = SPACES` after FETCH | `'N'` | Record structurally invalid |
| VSAM RLS abend caught gracefully | `'N'` | SYNCPOINT ROLLBACK issued |
| DB2 errors (OPEN/FETCH/CLOSE) | Hard ABEND `HRAC` | No graceful return |
| `READ-ACCOUNT-LAST` SELECT failure | Hard ABEND `HNCS` | No graceful return |

---

## 4. UPDACC — Update Account Backend

**Program ID:** `UPDACC` | **Invocation:** `EXEC CICS LINK` from `BNK1UAC`

**Purpose:** Updates the `ACCOUNT_TYPE`, `ACCOUNT_INTEREST_RATE`, and `ACCOUNT_OVERDRAFT_LIMIT` columns of the DB2 `ACCOUNT` table. First SELECTs the current record to verify the account exists, then issues a targeted UPDATE of only those three mutable columns. Balances (`AVAILABLE_BALANCE`, `ACTUAL_BALANCE`) and dates are explicitly **not updated**. No `PROCTRAN` record is written — the source comment notes: *"because it is only permissible to change a limited number of fields, and it is NOT possible to amend the balance, no record needs to be written to PROCTRAN"*.

---

### 4.1 Validations

| # | Check | Logic | Result |
|---|-------|-------|--------|
| 1 | **Account not found** | `SQLCODE ≠ 0` on initial SELECT (including `SQLCODE = +100`) | `COMM-SUCCESS = 'N'`; DISPLAY error; GO TO UAD999 |
| 2 | **Account type blank or leading space** | `COMM-ACC-TYPE = SPACES` OR `COMM-ACC-TYPE(1:1) = ' '` | `COMM-SUCCESS = 'N'`; DISPLAY error; GO TO UAD999 |
| 3 | **DB2 UPDATE failure** | `SQLCODE ≠ 0` on `EXEC SQL UPDATE ACCOUNT` | `COMM-SUCCESS = 'N'`; DISPLAY `SQLCODE`; GO TO UAD999 |

**Note on validation philosophy:** UPDACC's source comment explicitly states: *"The presentation layer is responsible for ensuring that the fields are validated."* The account type blank check (check 2) is the only backend business-rule validation beyond confirming the record exists — it is the API-caller guard to prevent accidental zeroing of account type when not supplied.

---

### 4.2 Processing

#### Main Flow (PREMIERE section)
```
1. MOVE SORTCODE → COMM-SCODE, DESIRED-SORT-CODE
2. PERFORM UPDATE-ACCOUNT-DB2
3. PERFORM GET-ME-OUT-OF-HERE (EXEC CICS RETURN)
```

#### UPDATE-ACCOUNT-DB2 section (UAD010)
```
1. MOVE COMM-ACCNO → DESIRED-ACC-NO
   Set HV-ACCOUNT-SORTCODE, HV-ACCOUNT-ACC-NO

2. EXEC SQL SELECT (all 12 columns) FROM ACCOUNT
   WHERE ACCOUNT_SORTCODE=:sort AND ACCOUNT_NUMBER=:accno
   INTO :host-variables

   SQLCODE ≠ 0:
     COMM-SUCCESS = 'N'; DISPLAY error; GO TO UAD999

3. Account type guard:
   IF COMM-ACC-TYPE = SPACES OR COMM-ACC-TYPE(1:1) = ' ':
     COMM-SUCCESS = 'N'; DISPLAY error; GO TO UAD999

4. Apply only the three mutable fields from COMMAREA:
   MOVE COMM-ACC-TYPE  → HV-ACCOUNT-ACC-TYPE
   MOVE COMM-OVERDRAFT → HV-ACCOUNT-OVERDRAFT-LIM
   MOVE COMM-INT-RATE  → HV-ACCOUNT-INT-RATE

5. EXEC SQL UPDATE ACCOUNT
   SET ACCOUNT_TYPE = :HV-ACCOUNT-ACC-TYPE,
       ACCOUNT_INTEREST_RATE = :HV-ACCOUNT-INT-RATE,
       ACCOUNT_OVERDRAFT_LIMIT = :HV-ACCOUNT-OVERDRAFT-LIM
   WHERE (ACCOUNT_SORTCODE = :sort AND ACCOUNT_NUMBER = :accno)
   (Note: only 3 columns SET — NOT a full 12-column rewrite)

   SQLCODE ≠ 0:
     COMM-SUCCESS = 'N'; DISPLAY SQLCODE; GO TO UAD999

6. On success — populate COMMAREA from SELECT results (not UPDATE):
   COMM-EYE       ← HV-ACCOUNT-EYECATCHER
   COMM-CUSTNO    ← HV-ACCOUNT-CUST-NO
   COMM-SCODE     ← HV-ACCOUNT-SORTCODE
   COMM-ACCNO     ← HV-ACCOUNT-ACC-NO
   COMM-ACC-TYPE  ← HV-ACCOUNT-ACC-TYPE  (from MOVE above)
   COMM-INT-RATE  ← HV-ACCOUNT-INT-RATE  (from MOVE above)
   COMM-OPENED → DB2-DATE-REFORMAT:
     COMM-OPENED-YEAR/MONTH/DAY ← DB2-DATE-REF-YR/MNTH/DAY
   COMM-OVERDRAFT ← HV-ACCOUNT-OVERDRAFT-LIM (from MOVE above)
   COMM-LAST-STMT → DB2-DATE-REFORMAT:
     COMM-LASTST-YEAR/MONTH/DAY ← DB2-DATE-REF-YR/MNTH/DAY
   COMM-NEXT-STMT → DB2-DATE-REFORMAT:
     COMM-NEXTST-YEAR/MONTH/DAY ← DB2-DATE-REF-YR/MNTH/DAY
   COMM-AVAIL-BAL  ← HV-ACCOUNT-AVAIL-BAL  (from SELECT — unchanged)
   COMM-ACTUAL-BAL ← HV-ACCOUNT-ACTUAL-BAL (from SELECT — unchanged)
   MOVE 'Y' → COMM-SUCCESS
```

**Three-column selective UPDATE:** Unlike `DBCRFUN` (Credit/Debit) and `XFRFUN` (Transfer) which rewrite all 12 `ACCOUNT` columns, UPDACC uses a targeted `SET` clause with only `ACCOUNT_TYPE`, `ACCOUNT_INTEREST_RATE`, and `ACCOUNT_OVERDRAFT_LIMIT`. Dates, customer number, sort code, account number, eyecatcher, and both balances are unchanged by the UPDATE.

**Date format returned to COMMAREA:** UPDACC returns dates in a split format (`COMM-OPENED-YEAR`, `COMM-OPENED-MONTH`, `COMM-OPENED-DAY` etc.) using the `COPY UPDACC` COMMAREA copybook's date sub-fields. The `DB2-DATE-REFORMAT` overlay extracts year, month, day from DB2's `YYYY-MM-DD` format. This is different from `INQACC` which returns dates as packed 8-digit `DDMMYYYY` fields via its own `COPY INQACC` copybook structure.

**No PROCTRAN record written:** UPDACC explicitly does not write to `PROCTRAN`. This is consistent with the design principle that non-financial changes (type, rate, overdraft) do not require an audit trail at the transaction level, unlike credit/debit/transfer operations.

---

### 4.3 Files / Database / CICS Storage

| Resource | Type | Mode | Notes |
|----------|------|------|-------|
| `ACCOUNT` (DB2 table) | DB2 Embedded SQL | SELECT (singleton) | `SELECT 12 columns WHERE SORTCODE=:s AND ACCNO=:a` — verifies account exists and retrieves current values |
| `ACCOUNT` (DB2 table) | DB2 Embedded SQL | UPDATE (3 columns) | `SET ACCOUNT_TYPE, ACCOUNT_INTEREST_RATE, ACCOUNT_OVERDRAFT_LIMIT WHERE SORTCODE=:s AND ACCNO=:a` — targeted update, not a full-row rewrite |
| `DFHCOMMAREA` (COPY UPDACC) | CICS COMMAREA | Input / Output | All account fields in; `COMM-SUCCESS` + updated account fields out (dates as split year/month/day sub-fields) |
| `WS-ACC-DATA` (COPY ACCOUNT) | Local Storage | Declared | Account data structure |
| `DB2-DATE-REFORMAT` | Local Storage | Working | `YYYY-MM-DD` to year/month/day extraction overlay |
| `SORTCODE` (COPY SORTCODE) | Working Storage | Read | Bank sort code constant |
| `ABNDINFO-REC` (COPY ABNDINFO) | Local Storage | Output | Passed to `ABNDPROC` on failure |
| SQLCA | DB2 | Communication area | `SQLCODE` checking |
| No VSAM files | — | — | Purely DB2-based |
| No PROCTRAN write | — | — | Explicitly excluded by design (non-financial update) |

---

### 4.4 Programs Called by UPDACC

| Program | Call Method | Purpose |
|---------|-------------|---------|
| `ABNDPROC` | `EXEC CICS LINK … COMMAREA(ABNDINFO-REC)` | Abend handler — logs failure (declared but not called in current code path; error paths use DISPLAY + `COMM-SUCCESS='N'` and return gracefully) |

**Note:** Unlike most backend programs in the suite, UPDACC's error paths on SELECT and UPDATE failure set `COMM-SUCCESS='N'` and return gracefully rather than ABENDing. There is no call to `ABNDPROC` in the current code's error handling within `UPDATE-ACCOUNT-DB2` — only within the `ABNDINFO-REC` declaration.

---

## 5. Cross-Component Call Chain Summary

```
BNKMENU  (OMEN)
  │
  └── Option 5 ──► RETURN TRANSID('OUAC')
                       │
                       ▼
                   BNK1UAC  (OUAC)
                       │
                       ├── EXEC CICS RECEIVE MAP 'BNK1UA'
                       │       User enters: ACCNO (8 digits)
                       │
                       ├──[ENTER — Account Inquiry]──────────────────────────────┐
                       │   EDIT-DATA: ACCNOI NOT NUMERIC check                  │
                       │   PERFORM INQ-ACC-DATA:                                │
                       │     INITIALIZE DFHCOMMAREA                             │
                       │     MOVE ACCNOI → COMM-ACCNO                          │
                       │     EXEC CICS LINK ──► INQACC                         │
                       │       │  EXEC SQL OPEN ACC-CURSOR                      │
                       │       │  EXEC SQL FETCH (SELECT WHERE SORT+ACCNO)      │
                       │       │  EXEC SQL CLOSE ACC-CURSOR                     │
                       │       └── Returns: all 12 account fields + SUCCESS     │
                       │     IF COMM-ACC-TYPE=SPACES AND COMM-LAST-STMT-DT=0:  │
                       │       MESSAGE: 'account not found'                     │
                       │     ELSE:                                              │
                       │       Populate all map output fields                   │
                       │       MESSAGE: 'Please amend fields and hit <pf5>'    │
                       │                                                        │
                       └──[PF5 — Submit Update]──────────────────────────────────┘
                           VALIDATE-DATA (15 checks):
                             Account type exact match
                             Interest rate: presence, chars, decimal, negative, max, zero+LOAN/MORTGAGE
                             Overdraft: numeric
                             Last stmt date: numeric, range, day/month combos
                             Next stmt date: numeric, day/month combos
                           PERFORM UPD-ACC-DATA:
                             INITIALIZE DFHCOMMAREA
                             Build COMMAREA from screen fields
                             (if ACCNOI=99999999: use ACCNO2I instead)
                             Balance parse: REDEFINES overlay on +9(10).99 string
                             EXEC CICS LINK ──► UPDACC
                               │  EXEC SQL SELECT FROM ACCOUNT (verify exists)
                               │  Account type blank guard
                               │  EXEC SQL UPDATE ACCOUNT
                               │    SET TYPE, INT_RATE, OVERDRAFT_LIMIT only
                               │  (balances unchanged; no PROCTRAN write)
                               └── Returns: COMM-SUCCESS + updated account data
                             IF COMM-SUCCESS='N': error message
                             ELSE: populate map; MESSAGE: 'update applied'

           EXEC CICS RETURN TRANSID('OUAC') COMMAREA(WS-COMM-AREA) LENGTH(99)
```

### CICS COMMAREA Flow

```
BNKMENU  ──(RETURN TRANSID 'OUAC', no COMMAREA)─────────► BNK1UAC (EIBCALEN=0 first pass)
BNK1UAC  ──(DFHCOMMAREA, COPY INQACC layout)────────────► INQACC ──► BNK1UAC
BNK1UAC  ──(DFHCOMMAREA, COPY UPDACC layout)────────────► UPDACC ──► BNK1UAC
BNK1UAC  ──(WS-COMM-AREA, 99 bytes)─────────────────────► OUAC (self-return, pseudo-conv loop)
```

**Important COMMAREA note:** BNK1UAC passes `DFHCOMMAREA` **directly** (not a separate working storage area) to both `INQACC` and `UPDACC`. The `DFHCOMMAREA` layout differs between the two calls — `INQACC` uses its own `COPY INQACC` copybook, while `UPDACC` uses `COPY UPDACC`. Both copybooks map compatible fields at the same offsets for account number, sort code, customer number, account type, interest rate, overdraft, balances, and the `COMM-SUCCESS` flag.

---

## 6. Fail Code Reference

### BNK1UAC — Result Handling

| Condition | Source | Message in BNK1UAC |
|-----------|--------|-------------------|
| `COMM-ACC-TYPE = SPACES AND COMM-LAST-STMT-DT = ZERO` | INQACC | `This account number could not be found` |
| `COMM-SUCCESS = 'N'` | UPDACC | `Update unsuccessful, try again later.` |
| `COMM-SUCCESS = 'Y'` | UPDACC | `Account update successfully applied.` |

### UPDACC — Internal Outcome Codes

| Outcome | Condition | Logged |
|---------|-----------|--------|
| Account not found / SELECT error | `SQLCODE ≠ 0` on SELECT | DISPLAY `SQLCODE` on sysout |
| Account type blank | `COMM-ACC-TYPE = SPACES` or leading space | DISPLAY message on sysout |
| UPDATE DB2 error | `SQLCODE ≠ 0` on UPDATE | DISPLAY `SQLCODE` on sysout |

### Abend Codes Across All Programs

| Abend Code | Program | Trigger |
|-----------|---------|---------|
| `HBNK` | BNK1UAC | Any CICS failure (RECEIVE MAP, SEND MAP, RETURN TRANSID, LINK) |
| `HRAC` | INQACC | DB2 cursor OPEN, FETCH, or CLOSE failure |
| `HNCS` | INQACC | DB2 SELECT failure in `GET-LAST-ACCOUNT-DB2` (last account mode) |
| `HROL` | INQACC | SYNCPOINT ROLLBACK failure after VSAM RLS abend |

---

## 7. Screen Flow and Key Behaviour

```
┌──────────────────────────────────────────────────────────────────────┐
│  BNK1UA — First Time (EIBCALEN=0)                                   │
│  CICS Banking Sample Application - Update Account.                  │
│  Please provide an ACCOUNT number.                                  │
│                                                                      │
│  ACCOUNT NUMBER ________                                            │
│   Customer Number:                                                  │
│   Sort Code      :                                                  │
│   Account Number :                                                  │
│   Account Type   :                                                  │
│   Interest Rate  :                                                  │
│   Account Opened :    /  /                                          │
│   Overdraft limit:                                                  │
│   Last statement :    /  /                                          │
│   Next statement :    /  /                                          │
│   Available Bal  :                                                  │
│   Actual Balance :                                                  │
│  F3=Exit   F12=Cancel                                               │
└──────────────────────┬───────────────────────────────────────────────┘
                       │ User enters account number (e.g. 00000010), ENTER
                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  BNK1UA — After Successful Inquiry                                  │
│  ACCOUNT NUMBER 00000010                                            │
│   Customer Number: 0000000003                                       │
│   Sort Code      : 987654                                           │
│   Account Number : 00000010                                         │
│   Account Type   : CURRENT   ← editable (green, underline)         │
│   Interest Rate  : 0000.00   ← editable (green, underline)         │
│   Account Opened : 13 / 11 / 1970                                  │
│   Overdraft limit: 00000100  ← editable (green, underline)         │
│   Last statement : 01 / 07 / 2014                                  │
│   Next statement : 01 / 08 / 2014                                  │
│   Available Bal  : +0000472807.57  (protected)                     │
│   Actual Balance : +0000472807.57  (protected)                     │
│                                                                      │
│  MESSAGE: Please amend fields and hit <pf5> to apply changes       │
│  F3=Exit   F12=Cancel                                               │
└──────────────────────┬───────────────────────────────────────────────┘
                       │ User amends Account Type / Interest Rate / Overdraft, presses PF5
                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  BNK1UA — After Successful Update                                   │
│  (same layout as inquiry — reflects confirmed stored values)        │
│  MESSAGE: Account update successfully applied.                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 8. Key Design Points and Comparisons

### Unique Design Features of This Transaction

| Aspect | Detail |
|--------|--------|
| Dual key handler (Enter + PF5) | Both `DFHENTER` and `DFHPF5` route to `PROCESS-MAP`, which then branches on `EIBAID`. Enter = inquiry; PF5 = update. Unlike `BNK1DCS` (PF3/PF5/PF10/Enter), this is a simpler two-key model |
| Three editable fields only | `ACTYPE`, `INTRT`, `OVERDR` are `UNPROT` with `FSET`. All other fields (dates, balances, sort code, customer number) are `PROT` — no dynamic attribute manipulation needed. The screen is pre-wired for edit mode after inquiry |
| No PROCTRAN write | UPDACC deliberately does not write an audit record. Explicitly documented: non-financial metadata changes (type, rate, overdraft) do not warrant a transaction journal entry |
| Three-column selective UPDATE | UPDACC's `EXEC SQL UPDATE` uses `SET` with only 3 of 12 columns — `ACCOUNT_TYPE`, `ACCOUNT_INTEREST_RATE`, `ACCOUNT_OVERDRAFT_LIMIT`. Unlike other backends (DBCRFUN, XFRFUN) which rewrite all 12 columns |
| DFHCOMMAREA passed directly | BNK1UAC passes `DFHCOMMAREA` directly to both `INQACC` and `UPDACC` (after INITIALIZE). No intermediate WS copy area is used for the LINK call — unusual in this suite |
| 99999999 account guard | `UPD-ACC-DATA` replaces `ACCNOI = 99999999` with `ACCNO2I` (confirmed displayed account). Prevents the sentinel value from being used as an update target |
| UPDACC date format difference | UPDACC returns dates split as separate year/month/day sub-fields in its COMMAREA (`COMM-OPENED-YEAR`, etc.) — unlike INQACC which packs dates as 8-digit `DDMMYYYY`. BNK1UAC must handle both layouts |
| Balance reconversion | In `UPD-ACC-DATA`, BNK1UAC parses the transmitted `+9(10).99` balance strings back to signed numeric using a REDEFINES overlay. The reconstructed values are passed to UPDACC but are not actually updated in DB2 — they are preserved from the SELECT result |
| VALIDATE-DATA in screen handler | All field-level validation for the update (15 checks) occurs in `BNK1UAC`'s `VALIDATE-DATA` section, not in `UPDACC`. UPDACC performs only existence and type-blank guards. This is consistent with UPDACC's documented design: *"The presentation layer is responsible for ensuring that the fields are validated"* |

### Comparison with Other Update/Modify Functions

| Aspect | `OUAC` Update Account (`BNK1UAC`/`UPDACC`) | `ODCS` Update Customer (`BNK1DCS`/`UPDCUST`) | `OCRA` Credit/Debit (`BNK1CRA`/`DBCRFUN`) |
|--------|-------------------------------------------|-----------------------------------------------|-------------------------------------------|
| Fields updated | Account Type, Interest Rate, Overdraft Limit | Customer Name, Address | Available Balance, Actual Balance |
| Balances updatable? | No (explicitly excluded) | N/A | Yes (primary purpose) |
| PROCTRAN written? | No | No | Yes (`DEB`/`CRE`/`PDR`/`PCR`) |
| DB2 UPDATE columns | 3 specific columns | N/A (VSAM REWRITE) | 2 balance columns (full 12-col rewrite) |
| Backend validate? | No (presentation layer validates) | Yes (title re-check) | Yes (facility type rules) |
| Dynamic attribute change | No — fields pre-wired as UNPROT | Yes — PF10 unprotects fields | N/A |
| Mode flag in COMMAREA | No | Yes (`COMM-UPD = 'Y'`) | No |
| COMMAREA passed to backend | `DFHCOMMAREA` directly | Separate `UPDCUST-COMMAREA` | `SUBPGM-PARMS` |
| Statement dates | Displayed/protected on screen | N/A | N/A |
| Rollback on partial failure | N/A (single UPDATE, no multi-step) | N/A | Yes (PROCTRAN fail rolls back ACCOUNT UPDATE) |

---

*Analysis generated from source review of `BNK1UAM.bms`, `BNK1UAC.cbl`, `INQACC.cbl`, and `UPDACC.cbl`.*

# Transfer Funds — Component Analysis
## CICS Banking Sample Application — Menu Option 7

> **Transaction:** `OTFN` (triggered from `OMEN` Menu Option 7)
> **Components:** `BNK1TFM` (BMS Map) · `BNK1TFN` (Screen Handler) · `XFRFUN` (Transfer Function Backend)

---

## Table of Contents

1. [BNK1TFM — BMS Map (BNK1TF)](#1-bnk1tfm--bms-map-bnk1tf)
2. [BNK1TFN — Transfer Funds Screen Handler](#2-bnk1tfn--transfer-funds-screen-handler)
3. [XFRFUN — Transfer Function Backend](#3-xfrfun--transfer-function-backend)
4. [Cross-Component Call Chain Summary](#4-cross-component-call-chain-summary)
5. [Fail Code Reference](#5-fail-code-reference)
6. [Screen Flow and Key Behaviour](#6-screen-flow-and-key-behaviour)
7. [Key Design Points and Comparisons](#7-key-design-points-and-comparisons)

---

## 1. BNK1TFM — BMS Map (BNK1TF)

**Mapset:** `BNK1TFM` | **Map:** `BNK1TF` | **Source:** `BNK1TFM.bms`

---

### 1.1 Map Identity

| Attribute | Value |
|-----------|-------|
| Mapset Name | `BNK1TFM` |
| Map Name | `BNK1TF` |
| Terminal Type | 3270-2 |
| Mode | INOUT |
| Language | COBOL |
| Storage | AUTO |
| Control | FREEKB |
| Extended Attributes | COLOR, HILIGHT, OUTLINE, PS, SOSI |
| Title | `CICS Banking Sample Application - Transfer funds.` (Red, Row 1) |
| Instruction | `Provide a FROM account, a TO account and an Amount and press Enter.` (Turquoise, Row 3) |

---

### 1.2 Map Fields — Screen Layout

The map is unique in the suite — it presents a **side-by-side dual-account layout** on rows 11–14, with FROM account data on the left and TO account data on the right.

| Row | Field Name | Position | Length | Attributes | Color | Description |
|-----|-----------|----------|--------|------------|-------|-------------|
| 1 | *(literal)* | (1,1) | 7 | PROT, NORM | Blue | Map ID label `BNK1TF` |
| 1 | `COMPANY` | (1,17) | 61 | NORM, PROT | Red | Title banner |
| 3 | *(literal)* | (3,1) | 70 | NORM, PROT | Turquoise | Instruction text |
| 8 | *(literal)* | (8,1) | 21 | NORM, PROT | Turquoise | Label: `FROM Account Number:` |
| 8 | `FACCNO` | (8,23) | 8 | NORM, NUM, FSET | Green + Underline | **Input:** FROM Account Number (numeric keyboard shift; MDT forced via FSET) |
| 8 | *(literal)* | (8,32) | 19 | NORM, PROT, ASKIP | Turquoise | Label: `TO Account Number:` |
| 8 | `TACCNO` | (8,52) | 8 | NORM, NUM, FSET | Green + Underline | **Input:** TO Account Number (numeric keyboard shift; MDT forced via FSET) |
| 9 | *(literal)* | (9,1) | 7 | NORM, PROT | Turquoise | Label: `AMOUNT:` |
| 9 | `AMT` | (9,23) | 13 | NORM, UNPROT, FSET | Green + Underline | **Input:** Transfer Amount; initial value `0000000000.00`; MDT forced via FSET |
| 11 | *(literal)* | (11,1) | 16 | NORM, PROT | Turquoise | Label: `FROM Account   :` |
| 11 | `FACCNO2` | (11,20) | 8 | NORM, NUM, PROT | Turquoise | **Output:** Confirmed FROM Account Number |
| 11 | *(literal)* | (11,35) | 16 | NORM, PROT | Turquoise | Label: `TO Account     :` |
| 11 | `TACCNO2` | (11,55) | 8 | NORM, PROT | Turquoise | **Output:** Confirmed TO Account Number |
| 12 | *(literal)* | (12,1) | 16 | NORM, PROT | Turquoise | Label: `Sort Code      :` (FROM) |
| 12 | `FSORTC` | (12,20) | 6 | NORM, NUM, PROT | Neutral | **Output:** FROM Sort Code |
| 12 | *(literal)* | (12,35) | 16 | NORM, PROT | Turquoise | Label: `Sort Code      :` (TO) |
| 12 | `TSORTC` | (12,55) | 6 | NORM, NUM, PROT | Neutral | **Output:** TO Sort Code |
| 13 | *(literal)* | (13,1) | 16 | NORM, PROT | Turquoise | Label: `Actual Balance :` (FROM) |
| 13 | `FACTBAL` | (13,19) | 14 | NORM, PROT | Neutral | **Output:** FROM Actual Balance (after transfer) |
| 13 | *(literal)* | (13,35) | 16 | NORM, PROT | Turquoise | Label: `Actual Balance :` (TO) |
| 13 | `TACTBAL` | (13,54) | 14 | NORM, PROT | Neutral | **Output:** TO Actual Balance (after transfer) |
| 14 | *(literal)* | (14,1) | 16 | NORM, PROT | Turquoise | Label: `Avail Balance  :` (FROM) |
| 14 | `FAVBAL` | (14,19) | 14 | NORM, PROT | Neutral | **Output:** FROM Available Balance (after transfer) |
| 14 | *(literal)* | (14,35) | 18 | NORM, PROT | Turquoise | Label: `Avail Balance  :` (TO) |
| 14 | `TAVBAL` | (14,54) | 14 | NORM, PROT | Neutral | **Output:** TO Available Balance (after transfer) |
| 23 | `MESSAGE` | (23,1) | 79 | BRT, PROT | Yellow | **Output:** User / error messages |
| 24 | *(literal)* | (24,1) | 20 | NORM, PROT | Blue | `F3=Exit   F12=Cancel` |
| 24 | `DUMMY` | (24,79) | 1 | DRK, PROT, FSET | — | Hidden MDT-forcing field |

**Key map design notes:**
- `FACCNO` and `TACCNO` are on **the same row (row 8)** — three input fields (`FACCNO`, `TACCNO`, `AMT`) across rows 8–9. No `IC` attribute on either field; cursor positioning is handled by cursor length `-1` on `AMTL` on validation failure.
- No `SIGN` field — unlike the Credit/Debit screen, transfer amounts are **always positive**. Negative amounts are explicitly rejected.
- Both `FACCNO` and `TACCNO` have `NUM` attribute (numeric keyboard shift) and `FSET` (MDT always set).
- `AMT` carries `FSET` with initial value `0000000000.00` to ensure it is always transmitted.
- The dual-column output layout (rows 11–14) shows FROM and TO account data side by side — unique in the application suite.
- No `IC` attribute anywhere — no automatic initial cursor positioning defined in the map.

**Function Key Legend:**

| Key | Action |
|-----|--------|
| Enter | Submit FROM account, TO account, and amount for transfer |
| PF3 | Exit — return to main menu (`OMEN`) |
| PF12 / AID | Cancel — send "Session Ended" termination message |
| CLEAR | Clear screen |
| PA1/PA2/PA3 | Continue — no action |

---

## 2. BNK1TFN — Transfer Funds Screen Handler

**Program ID:** `BNK1TFN` | **Transaction ID:** `OTFN`

This program collects the FROM account, TO account, and transfer amount from the user, validates all three, then delegates the actual transfer to `XFRFUN`. Unlike the Credit/Debit screen, there is no sign field — transfers are always positive amounts from one account to another.

---

### 2.1 Validations

#### EDIT-DATA Section

| # | Field | Check | Error Message |
|---|-------|-------|---------------|
| 1 | `FACCNOI` — numeric | `EXEC CICS BIF DEEDIT` applied; `NOT NUMERIC` check | `Please enter a FROM account no` |
| 2 | `TACCNOI` — numeric | `EXEC CICS BIF DEEDIT` applied; `NOT NUMERIC` check | `Please enter a TO account no` |
| 3 | FROM = TO — same account | `FACCNOI = TACCNOI` | `The FROM & TO account should be different` |
| 4 | Zero account guard | `FACCNOI = '00000000'` OR `TACCNOI = '00000000'` | `Account no 00000000 is not valid` |

Then calls `PERFORM VALIDATE-AMOUNT`.

#### VALIDATE-AMOUNT Section

This is the same multi-step custom numeric validator pattern as `BNK1CRA`, but with an additional check rejecting negative amounts (no `-` sign permitted for transfers).

| # | Check | Logic | Error Message |
|---|-------|-------|---------------|
| 5 | Amount — presence | `AMTL = ZERO` | `The Amount entered must be numeric.` |
| 6 | Amount — pure integer | `AMTI(1:AMTL) IS NUMERIC` — if true, converts via `FUNCTION NUMVAL`; then checks ≤ 0 | `Please supply a positive amount.` |
| 7 | Amount — entirely spaces | `INSPECT … TALLYING FOR LEADING SPACES = AMTL` | `The Amount entered must be numeric.` |
| 8 | Amount — negative sign | `WS-NUM-COUNT-MINUS > 0` — any `-` character present | `Please supply a positive amount.` |
| 9 | Amount — embedded spaces | `WS-NUM-COUNT-SPACE > 0` after trimming | `Please supply a numeric amount without embedded  spaces.` |
| 10 | Amount — invalid characters | `WS-NUM-COUNT-TOTAL < WS-AMOUNT-UNSTR-L` (non-digit, non-point chars) | `Please supply a numeric amount.` |
| 11 | Amount — multiple decimal points | `WS-NUM-COUNT-POINT > 1` | `Use one decimal point for amount only.` |
| 12 | Amount — more than 2 decimal places | If 1 decimal point: count non-zero digits after 2nd decimal place > 2 | `Only up to two decimal places are supported.` |
| 13 | Amount — non-zero | `FUNCTION NUMVAL` result = zero | `Please supply a non-zero amount.` |

**Key difference from BNK1CRA `VALIDATE-AMOUNT`:** Check 8 (WS-NUM-COUNT-MINUS > 0) explicitly tallies and rejects any `-` character. The credit/debit screen uses a separate `SIGN` field; this screen enforces positivity directly in the amount validator.

#### POST-LINK Result Checks (GET-ACC-DATA after XFRFUN)

| # | Condition | Error Message |
|---|-----------|---------------|
| 14 | `SUBPGM-SUCCESS = 'N'` AND `SUBPGM-FAIL-CODE = '1'` | `Sorry the FROM ACCOUNT no was not found. Transfer not applied.` |
| 15 | `SUBPGM-SUCCESS = 'N'` AND `SUBPGM-FAIL-CODE = '2'` | `Sorry the TO ACCOUNT no was not found. Transfer not applied.` |
| 16 | `SUBPGM-SUCCESS = 'N'` AND `SUBPGM-FAIL-CODE = '3'` | `Sorry but the transfer could not be applied due to an unexpected error.` |
| 17 | `SUBPGM-SUCCESS = 'N'` AND `SUBPGM-FAIL-CODE = '4'` | `Please supply an amount greater than zero.` |
| 18 | `SUBPGM-SUCCESS = 'N'` AND any other code | `Sorry but the transfer could not be applied due to an error.` |
| 19 | `SUBPGM-SUCCESS NOT = 'Y'` (catch-all after EVALUATE) | `Sorry but the transfer could not be applied unable to determine success.` |

---

### 2.2 Processing

#### Key Press Routing (PREMIERE SECTION — EVALUATE on EIBAID)

| AID Key | Action |
|---------|--------|
| `EIBCALEN = 0` | First time: `LOW-VALUE` to `BNK1TFO`; SEND-ERASE; `PERFORM SEND-MAP` |
| `DFHPA1/PA2/PA3` | `CONTINUE` — no action |
| `DFHPF3` | `EXEC CICS RETURN TRANSID('OMEN') IMMEDIATE` |
| `DFHAID` / `DFHPF12` | Send "Session Ended"; plain `EXEC CICS RETURN` |
| `DFHCLEAR` | `SEND CONTROL ERASE FREEKB`; plain `EXEC CICS RETURN` |
| `DFHENTER` | `PERFORM PROCESS-MAP` |
| Any other key | `LOW-VALUES` to `BNK1TFO`; "Invalid key pressed."; SEND-DATAONLY-ALARM |

After all paths: issues `EXEC CICS RETURN TRANSID('OTFN') COMMAREA(WS-COMMAREA) LENGTH(29)`.

**Note:** `WS-COMMAREA` (not `DFHCOMMAREA`) is passed on RETURN. `WS-COMMAREA` is only populated from `DFHCOMMAREA` on paths where `EIBCALEN ≠ 0` — which is implicit since there is no explicit `IF EIBCALEN NOT = ZERO` guard in this program for the COMMAREA copy-back. The COMMAREA fields (`WS-COMMAREA-FACCNO`, `WS-COMMAREA-TACCNO`, `WS-COMMAREA-AMT`) are initialised to zero by default and only carry forward values if explicitly set.

#### PROCESS-MAP Section — Detailed Flow

```
PERFORM RECEIVE-MAP
  (RECEIVE MAP 'BNK1TF' INTO BNK1TFI — standard receive, no ASIS)

PERFORM EDIT-DATA:
  1. BIF DEEDIT + numeric check on FACCNOI
  2. BIF DEEDIT + numeric check on TACCNOI
  3. FROM = TO same account check
  4. Zero account number check
  5. PERFORM VALIDATE-AMOUNT (9-step positive-only amount parser)

IF VALID-DATA:
  PERFORM GET-ACC-DATA:
    INITIALIZE SUBPGM-PARMS
    MOVE FACCNOI → SUBPGM-FACCNO
    MOVE TACCNOI → SUBPGM-TACCNO
    MOVE 'N'     → SUBPGM-SUCCESS
    MOVE WS-AMOUNT-AS-FLOAT → SUBPGM-AMT  (always positive COMP-2 float)

    EXEC CICS LINK PROGRAM('XFRFUN') COMMAREA(SUBPGM-PARMS) SYNCONRETURN

    On CICS LINK failure → ABEND via ABNDPROC (abend code 'HBNK')

    Always populate initial output fields (zeroed balances):
      FACCNO2O ← SUBPGM-FACCNO
      FSORTCO  ← SUBPGM-FSCODE
      TACCNO2O ← SUBPGM-TACCNO
      TSORTCO  ← SUBPGM-TSCODE
      FACTBALO, FAVBALO, TACTBALO, TAVBALO ← zero (formatted via display pics)

    Evaluate SUBPGM-SUCCESS / SUBPGM-FAIL-CODE:
      'N'+'1' → FROM account not found message; GO TO GCD999
      'N'+'2' → TO account not found message; GO TO GCD999
      'N'+'3' → unexpected error message (stays on screen)
      'N'+'4' → zero amount message; GO TO GCD999
      'N'+other → generic error; GO TO GCD999

    IF SUBPGM-SUCCESS NOT = 'Y':
      undetermined success message; GO TO GCD999

    IF SUBPGM-SUCCESS = 'Y':
      MESSAGE: 'Transfer successfully applied.'
      Populate confirmed output fields:
        FACCNO2O ← SUBPGM-FACCNO;  FSORTCO  ← SUBPGM-FSCODE
        TACCNO2O ← SUBPGM-TACCNO;  TSORTCO  ← SUBPGM-TSCODE
        FACTBALO ← SUBPGM-FACTBAL  via FROM-ACTUAL-BALANCE-DISPLAY (+9(10).99)
        FAVBALO  ← SUBPGM-FAVBAL   via FROM-AVAILABLE-BALANCE-DISPLAY (+9(10).99)
        TACTBALO ← SUBPGM-TACTBAL  via TO-ACTUAL-BALANCE-DISPLAY (+9(10).99)
        TAVBALO  ← SUBPGM-TAVBAL   via TO-AVAILABLE-BALANCE-DISPLAY (+9(10).99)

SET SEND-DATAONLY-ALARM TO TRUE
PERFORM SEND-MAP
```

**Note on zero-balance initialisation before EVALUATE:** BNK1TFN immediately initialises all four balance output fields to zero (via formatted display pictures) as soon as XFRFUN returns, **before** evaluating success/fail. This ensures no stale balance from a prior transaction is left on screen if the transfer fails. The success path then overwrites with the real post-transfer balances.

---

### 2.3 Files / Database / CICS Storage

| Resource | Type | Usage |
|----------|------|-------|
| `BNK1TF` / `BNK1TFM` | CICS BMS Map | Input (`RECEIVE MAP`) and Output (`SEND MAP ERASE` / `DATAONLY` / `DATAONLY ALARM`) |
| `DFHCOMMAREA` (29 bytes) | CICS COMMAREA | Input from `OMEN` or prior `OTFN` cycle; fields: `COMMAREA-FACCNO` (8), `COMMAREA-TACCNO` (8), `COMMAREA-AMT` (12) |
| `WS-COMMAREA` (29 bytes) | CICS COMMAREA | Passed on `RETURN TRANSID('OTFN')` — pseudo-conversational loop state |
| `SUBPGM-PARMS` | CICS COMMAREA | Passed to / received from `XFRFUN` via `EXEC CICS LINK` |
| `ABNDINFO-REC` (COPY ABNDINFO) | CICS COMMAREA | Passed to `ABNDPROC` on any CICS failure |
| No VSAM files or DB2 tables | — | All data access delegated to `XFRFUN` |
| No terminal UCTRAN management | — | Not needed — inputs are numeric only |

---

### 2.4 Programs Called by BNK1TFN

| Program | Call Method | Purpose |
|---------|-------------|---------|
| `XFRFUN` | `EXEC CICS LINK … SYNCONRETURN` | Perform the account-to-account fund transfer in DB2 and write PROCTRAN audit |
| `ABNDPROC` | `EXEC CICS LINK … COMMAREA(ABNDINFO-REC)` | Abend handler — logs and terminates on any CICS failure |

---

## 3. XFRFUN — Transfer Function Backend

**Program ID:** `XFRFUN` | **Invocation:** `EXEC CICS LINK` from `BNK1TFN`

**Purpose:** Performs a fund transfer between two accounts in the DB2 `ACCOUNT` table. Reads and updates both accounts atomically — if either fails, the entire operation rolls back. Writes a single `PROCTRAN` record for the transfer. Implements **deadlock-aware retry logic** and **strict DB2 locking order** to prevent deadlocks under concurrent load.

---

### 3.1 Validations

| # | Check | Logic | Result |
|---|-------|-------|--------|
| 1 | **Amount ≤ zero** | `COMM-AMT <= ZERO` in PREMIERE | `COMM-SUCCESS='N'`; `COMM-FAIL-CODE='4'`; immediate RETURN |
| 2 | **FROM = TO (same sort code + account)** | `COMM-FACCNO = COMM-TACCNO AND COMM-FSCODE = COMM-TSCODE` in `UPDATE-ACCOUNT-DB2` | ABEND `SAME` via ABNDPROC — treated as a programming error |
| 3 | **FROM account not found** | DB2 `SQLCODE = +100` on FROM SELECT | `COMM-FAIL-CODE='1'`; SYNCPOINT ROLLBACK; return |
| 4 | **FROM account DB2 error (other)** | `SQLCODE ≠ 0` and `≠ +100` on FROM SELECT | `COMM-FAIL-CODE='3'`; CHECK-STORM-DRAIN; return |
| 5 | **FROM account UPDATE failure** | `SQLCODE ≠ 0` on FROM UPDATE | `COMM-FAIL-CODE='3'`; CHECK-STORM-DRAIN; ABEND `FROM` |
| 6 | **TO account not found** | DB2 `SQLCODE = +100` on TO SELECT | `COMM-FAIL-CODE='2'`; immediate SYNCPOINT ROLLBACK (undo FROM update); return |
| 7 | **TO account DB2 deadlock on SELECT** (`SQLCODE = -911`, `SQLERRD(3) = 13172872`) | Retry up to 5 times with 1-second delay then full `UPDATE-ACCOUNT-DB2` restart | Retry loop — up to 5 attempts then ABEND `RUF2` |
| 8 | **TO account timeout on SELECT** (`SQLERRD(3) = 13172894`) | Detected and logged | ABEND `RUF2` via ABNDPROC |
| 9 | **TO account UPDATE deadlock** (`SQLCODE = -911`, `SQLERRD(3) = 13172872`) | Retry up to 5 times with 1-second delay then full restart | Retry loop |
| 10 | **TO account UPDATE failure (other)** | `SQLCODE ≠ 0` on TO UPDATE (non-deadlock) | ABEND `RUF3` via ABNDPROC |
| 11 | **PROCTRAN INSERT failure** | `SQLCODE ≠ 0` on `INSERT INTO PROCTRAN` | ABEND `WPCD` via ABNDPROC (no rollback — data inconsistency logged) |
| 12 | **VSAM RLS abends** (`AFCR`, `AFCS`, `AFCT`) | Caught in `ABEND-HANDLING` | SYNCPOINT ROLLBACK; `COMM-FAIL-CODE='2'`; graceful return |
| 13 | **DB2 deadlock abend** (`AD2Z`) | Caught in `ABEND-HANDLING` | SQLSTATE/SQLERRMC/SQLERRD diagnostics displayed; falls through to re-abend |
| 14 | **DB2 Storm Drain** (`SQLCODE = 923`) | `CHECK-FOR-STORM-DRAIN-DB2` | Logged; processing continues with failure path |

---

### 3.2 Processing

#### Main Flow (PREMIERE section)
```
1. EXEC CICS HANDLE ABEND LABEL(ABEND-HANDLING)
2. Initialise host variables and deadlock retry counter
3. MOVE SORTCODE → COMM-FSCODE, COMM-TSCODE, DESIRED-SORT-CODE
4. IF COMM-AMT <= ZERO → COMM-FAIL-CODE='4'; RETURN

5. PERFORM UPDATE-ACCOUNT-DB2
6. PERFORM GET-ME-OUT-OF-HERE (EXEC CICS RETURN)
```

#### UPDATE-ACCOUNT-DB2 section — Deadlock-Prevention Locking Order

This is the most architecturally significant section. DB2 row-level locking requires a consistent lock acquisition order to prevent deadlocks. XFRFUN implements this by always locking the **lower-numbered account first**:

```
IF COMM-FACCNO = COMM-TACCNO AND COMM-FSCODE = COMM-TSCODE:
  → ABEND 'SAME' (same account — programming error)

IF COMM-FACCNO < COMM-TACCNO  (FROM account number is lower):
  Sequence: FROM first → TO second
    PERFORM UPDATE-ACCOUNT-DB2-FROM
    IF success → PERFORM UPDATE-ACCOUNT-DB2-TO
      If TO fails (fail code '2'):
        SYNCPOINT ROLLBACK (undo FROM update)
        If ROLLBACK fails → ABEND 'HROL'
        GO TO UAD999
      If TO fails (other code) → ABEND 'TO  '
    If FROM fails (fail code '1'):
      SYNCPOINT ROLLBACK; if ROLLBACK fails → ABEND 'HROL'
      GO TO UAD999
    If FROM fails (other code) → ABEND 'FROM'

ELSE (COMM-TACCNO ≤ COMM-FACCNO — TO account number is lower or equal):
  Sequence: TO first → FROM second
    PERFORM UPDATE-ACCOUNT-DB2-TO
    IF success → PERFORM UPDATE-ACCOUNT-DB2-FROM
      If FROM fails (fail code '1'):
        SYNCPOINT ROLLBACK; if ROLLBACK fails → ABEND 'HROL'
        GO TO UAD999
      If FROM fails (other code) → ABEND 'FROM'
    If TO fails (fail code '2'):
      SYNCPOINT ROLLBACK; if ROLLBACK fails → ABEND 'HROL'
      GO TO UAD999
    If TO fails (other code) → ABEND 'TO  '

PERFORM WRITE-TO-PROCTRAN
MOVE 'Y' → COMM-SUCCESS
```

**Locking order rationale:** By always acquiring the DB2 row lock on the lower-numbered account first (regardless of whether it is the FROM or TO account), XFRFUN ensures that two concurrent transfers between the same pair of accounts cannot form a deadlock cycle (circular wait). This is the classic database deadlock prevention technique: total ordering of resource acquisition.

#### UPDATE-ACCOUNT-DB2-FROM section (UADF010)
```
MOVE COMM-FACCNO → DESIRED-ACC-NO
MOVE COMM-FSCODE → DESIRED-SORT-CODE
Set HV-ACCOUNT-SORTCODE, HV-ACCOUNT-ACC-NO

EXEC SQL SELECT (12 columns) FROM ACCOUNT
  WHERE ACCOUNT_SORTCODE=:sort AND ACCOUNT_NUMBER=:faccno

SQLCODE ≠ 0:
  +100 → COMM-FAIL-CODE='1' (FROM not found); CHECK-STORM-DRAIN; return
  other → COMM-FAIL-CODE='3' (unexpected); CHECK-STORM-DRAIN; return

Debit FROM account:
  COMPUTE HV-ACCOUNT-AVAIL-BAL  = HV-ACCOUNT-AVAIL-BAL  - COMM-AMT
  COMPUTE HV-ACCOUNT-ACTUAL-BAL = HV-ACCOUNT-ACTUAL-BAL - COMM-AMT

EXEC SQL UPDATE ACCOUNT SET (all 12 columns)
  WHERE ACCOUNT_SORTCODE=:sort AND ACCOUNT_NUMBER=:faccno

SQLCODE ≠ 0 → COMM-FAIL-CODE='3'; CHECK-STORM-DRAIN; return

Store updated FROM balances:
  MOVE HV-ACCOUNT-AVAIL-BAL  → COMM-FAVBAL
  MOVE HV-ACCOUNT-ACTUAL-BAL → COMM-FACTBAL
MOVE 'Y' → COMM-SUCCESS
```

#### UPDATE-ACCOUNT-DB2-TO section (UADT010)

The TO section is significantly more complex due to deadlock retry handling:

```
INITIALIZE HOST-ACCOUNT-ROW
MOVE COMM-TACCNO → DESIRED-ACC-NO
MOVE COMM-TSCODE → DESIRED-SORT-CODE

EXEC SQL SELECT (12 columns) FROM ACCOUNT
  WHERE ACCOUNT_SORTCODE=:sort AND ACCOUNT_NUMBER=:taccno

SQLCODE ≠ 0:
  +100 → COMM-FAIL-CODE='2' (TO not found)
    Immediate SYNCPOINT ROLLBACK (undo FROM update for data consistency)
    If ROLLBACK fails → ABEND 'HROL'
    GO TO UADT999

  -911 with SQLERRD(3)=13172872 (DB2 deadlock):
    ADD 1 TO DB2-DEADLOCK-RETRY
    IF DB2-DEADLOCK-RETRY < 6:
      EXEC CICS SYNCPOINT ROLLBACK (reset both updates)
      EXEC CICS DELAY FOR SECONDS(1)  ← 1-second back-off
      GO TO UPDATE-ACCOUNT-DB2        ← restart entire transfer from top
    IF 6 retries exhausted → ABEND 'RUF2'

  -911 with SQLERRD(3)=13172894 (timeout):
    DISPLAY 'TIMEOUT DETECTED!'; ABEND 'RUF2'

  Other failure → COMM-FAIL-CODE='3'; DISPLAY diagnostics; ABEND 'RUF2'

Credit TO account:
  COMPUTE HV-ACCOUNT-AVAIL-BAL  = HV-ACCOUNT-AVAIL-BAL  + COMM-AMT
  COMPUTE HV-ACCOUNT-ACTUAL-BAL = HV-ACCOUNT-ACTUAL-BAL + COMM-AMT

EXEC SQL UPDATE ACCOUNT SET (all 12 columns)
  WHERE ACCOUNT_SORTCODE=:sort AND ACCOUNT_NUMBER=:taccno

SQLCODE ≠ 0:
  -911 with SQLERRD(3)=13172872 (deadlock on UPDATE):
    ADD 1 TO DB2-DEADLOCK-RETRY
    IF DB2-DEADLOCK-RETRY < 6:
      SYNCPOINT ROLLBACK; DELAY 1 SECOND; GO TO UPDATE-ACCOUNT-DB2 (restart)
    If ROLLBACK fails → ABEND 'HROL'
    ABEND 'RUF2' after retry exhaustion

  Other failure → ABEND 'RUF3'

Store updated TO balances:
  MOVE HV-ACCOUNT-AVAIL-BAL  → COMM-TAVBAL
  MOVE HV-ACCOUNT-ACTUAL-BAL → COMM-TACTBAL
MOVE 'Y' → COMM-SUCCESS
```

#### WRITE-TO-PROCTRAN-DB2 section (WTPD010)
```
Build HOST-PROCTRAN-ROW:
  EYECATCHER = 'PRTR'
  SORT-CODE  = COMM-FSCODE       (FROM sort code)
  ACC-NUMBER = COMM-FACCNO       (FROM account — the debit side)
  REF        = EIBTASKN (padded to 12 digits)
  DATE       = today DD.MM.YYYY  (ASKTIME + FORMATTIME DATESEP('.'))
  TIME       = HHMMSS

Determine TYPE using PROCTRAN copybook:
  SET PROC-TY-TRANSFER IN PROCTRAN-AREA TO TRUE
  (resolves to type code 'TFR' — transfer)

Build DESC using PROCTRAN copybook:
  SET PROC-TRAN-DESC-XFR-FLAG TO TRUE
  PROC-TRAN-DESC-XFR-SORTCODE ← COMM-TSCODE
  PROC-TRAN-DESC-XFR-ACCOUNT  ← COMM-TACCNO
  (Description identifies the TO account as the transfer destination)

AMOUNT = COMM-AMT (positive — the transfer amount)

EXEC SQL INSERT INTO PROCTRAN (9 columns)

SQLCODE ≠ 0:
  Log ABNDINFO-REC; EXEC CICS LINK ABNDPROC
  CHECK-FOR-STORM-DRAIN-DB2
  EXEC CICS ABEND ABCODE('WPCD')
  (NOTE: No SYNCPOINT ROLLBACK is issued here — the two ACCOUNT
   UPDATEs are already committed. PROCTRAN INSERT failure leaves
   the accounts in an inconsistent audit state. This is the
   deliberate trade-off: data integrity of balances > audit completeness)
```

**Critical design note — PROCTRAN INSERT failure:** Unlike `DBCRFUN` (Credit/Debit), `XFRFUN` does **not** issue a SYNCPOINT ROLLBACK if the PROCTRAN INSERT fails after both ACCOUNT UPDATEs succeed. Instead it ABENDs with code `WPCD` and logs a "data inconsistency" warning. The ABND-FREEFORM message explicitly states: `'DATA INCONSISTENCY, DATA UPDATED ON ACCOUNT'`. The design accepts that the account balances are correct and the PROCTRAN audit record is missing, rather than rolling back correct balances.

#### ABEND-HANDLING section
```
EXEC CICS ASSIGN ABCODE(MY-ABEND-CODE)
EVALUATE MY-ABEND-CODE:
  WHEN 'AD2Z' (DB2 deadlock abend):
    Display SQLCODE, SQLSTATE, SQLERRMC, SQLERRD(1-6)
    → falls through to WS-STORM-DRAIN='N' re-abend

  WHEN 'AFCR' / 'AFCS' / 'AFCT' (VSAM RLS storm-drain):
    MOVE 'Y' → WS-STORM-DRAIN
    EXEC CICS SYNCPOINT ROLLBACK
    If ROLLBACK fails → ABEND 'HROL' via ABNDPROC
    MOVE 'N' → COMM-SUCCESS; '2' → COMM-FAIL-CODE
    EXEC CICS RETURN (graceful)

IF WS-STORM-DRAIN = 'N':
  EXEC CICS ABEND ABCODE(MY-ABEND-CODE) NODUMP
```

---

### 3.3 Files / Database / CICS Storage

| Resource | Type | Mode | Notes |
|----------|------|------|-------|
| `ACCOUNT` (DB2 table) | DB2 Embedded SQL | SELECT + UPDATE (FROM account) | Singleton SELECT then full 12-column UPDATE; deducts COMM-AMT from both balances |
| `ACCOUNT` (DB2 table) | DB2 Embedded SQL | SELECT + UPDATE (TO account) | Singleton SELECT then full 12-column UPDATE; adds COMM-AMT to both balances |
| `PROCTRAN` (DB2 table) | DB2 Embedded SQL | INSERT | One audit record per successful transfer; type `TFR`; FROM account number in key; TO account in description; amount = COMM-AMT |
| `DFHCOMMAREA` (COPY XFRFUN) | CICS COMMAREA | Input / Output | All fields via `COPY XFRFUN` copybook |
| `SORTCODE` (COPY SORTCODE) | Working Storage | Read | Bank sort code constant |
| `WS-ACC-DATA` (COPY ACCOUNT) | Local Storage | Declared | FROM account data structure |
| `WS-ACC-DATA2` (COPY ACCOUNT REPLACING) | Local Storage | Declared | TO account data structure (with `ACCOUNT2` prefix to avoid name conflicts) |
| `PROCTRAN-AREA` (COPY PROCTRAN) | Local Storage | Working | PROCTRAN type/desc formatting using 88-level condition names |
| `ABNDINFO-REC` (COPY ABNDINFO) | Working Storage | Output | Passed to `ABNDPROC` on failure |
| SQLCA | DB2 | Communication area | `SQLCODE`, `SQLSTATE`, `SQLERRMC`, `SQLERRD` checking |
| SQLDA | DB2 | Descriptor area | `EXEC SQL INCLUDE SQLDA` declared (used for dynamic SQL capability — not actively used in transfer path) |
| `EXEC CICS SYNCPOINT ROLLBACK` | CICS Transaction Control | Multiple points | Issued when: FROM not found (undo TO), TO not found (undo FROM), deadlock retry, VSAM RLS storm drain |
| `EXEC CICS DELAY FOR SECONDS(1)` | CICS Time Control | Deadlock retry backoff | 1-second pause between deadlock retry attempts (up to 5 retries) |
| `DB2-DEADLOCK-RETRY` | Local Storage | Counter | Tracks deadlock retry attempts; max 5 before hard ABEND |
| No VSAM files | — | — | Purely DB2-based |

---

### 3.4 Programs Called by XFRFUN

| Program | Call Method | Purpose |
|---------|-------------|---------|
| `ABNDPROC` | `EXEC CICS LINK … COMMAREA(ABNDINFO-REC)` | Abend handler — logs DB2/CICS failure details and terminates |

---

### 3.5 XFRFUN COMMAREA Fields (COPY XFRFUN)

| Field | Direction | Description |
|-------|-----------|-------------|
| `COMM-FACCNO` | Input | FROM account number (8 digits) |
| `COMM-FSCODE` | Input/Output | FROM sort code (set from SORTCODE constant) |
| `COMM-TACCNO` | Input | TO account number (8 digits) |
| `COMM-TSCODE` | Input/Output | TO sort code (set from SORTCODE constant) |
| `COMM-AMT` | Input | Transfer amount — always positive (S9(10)V99) |
| `COMM-FAVBAL` | Output | Updated FROM available balance after transfer |
| `COMM-FACTBAL` | Output | Updated FROM actual balance after transfer |
| `COMM-TAVBAL` | Output | Updated TO available balance after transfer |
| `COMM-TACTBAL` | Output | Updated TO actual balance after transfer |
| `COMM-FAIL-CODE` | Output | Failure reason code (see Section 5) |
| `COMM-SUCCESS` | Output | `'Y'` = success; `'N'` = failure |

---

## 4. Cross-Component Call Chain Summary

```
BNKMENU  (OMEN)
  │
  └── Option 7 ──► RETURN TRANSID('OTFN')
                       │
                       ▼
                   BNK1TFN  (OTFN)
                       │
                       ├── EXEC CICS RECEIVE MAP 'BNK1TF'
                       │       User enters: FACCNO (8 digits)
                       │                    TACCNO (8 digits)
                       │                    AMT (positive decimal)
                       │
                       ├── EDIT-DATA:
                       │     BIF DEEDIT + numeric check on FACCNO
                       │     BIF DEEDIT + numeric check on TACCNO
                       │     Same account check (FACCNO ≠ TACCNO)
                       │     Zero account guard (both ≠ '00000000')
                       │     VALIDATE-AMOUNT (9-step positive-only parser,
                       │       including explicit rejection of '-' sign)
                       │
                       ├── EXEC CICS LINK ──► XFRFUN
                       │       │
                       │       ├── Guard: COMM-AMT <= ZERO → fail '4'; RETURN
                       │       │
                       │       ├── UPDATE-ACCOUNT-DB2:
                       │       │     Locking order decision:
                       │       │       IF FACCNO < TACCNO: lock FROM first, then TO
                       │       │       IF TACCNO ≤ FACCNO: lock TO first, then FROM
                       │       │     (prevents deadlock via total locking order)
                       │       │
                       │       ├── UPDATE-ACCOUNT-DB2-FROM:
                       │       │     EXEC SQL SELECT FROM ACCOUNT (singleton)
                       │       │     COMPUTE AVAIL-BAL = AVAIL-BAL - COMM-AMT
                       │       │     COMPUTE ACTUAL-BAL = ACTUAL-BAL - COMM-AMT
                       │       │     EXEC SQL UPDATE ACCOUNT
                       │       │     Store COMM-FAVBAL, COMM-FACTBAL
                       │       │
                       │       ├── UPDATE-ACCOUNT-DB2-TO:
                       │       │     EXEC SQL SELECT FROM ACCOUNT (singleton)
                       │       │       Deadlock retry: SQLCODE=-911 → ROLLBACK;
                       │       │                       DELAY 1s; restart (max 5×)
                       │       │       Not found: ROLLBACK FROM update; fail '2'
                       │       │     COMPUTE AVAIL-BAL = AVAIL-BAL + COMM-AMT
                       │       │     COMPUTE ACTUAL-BAL = ACTUAL-BAL + COMM-AMT
                       │       │     EXEC SQL UPDATE ACCOUNT
                       │       │       Deadlock retry on UPDATE: same retry pattern
                       │       │     Store COMM-TAVBAL, COMM-TACTBAL
                       │       │
                       │       ├── WRITE-TO-PROCTRAN-DB2:
                       │       │     EXEC SQL INSERT INTO PROCTRAN
                       │       │       TYPE = 'TFR'
                       │       │       ACC-NUMBER = COMM-FACCNO (debit side)
                       │       │       DESC = TO sortcode + TO account
                       │       │       AMOUNT = COMM-AMT (positive)
                       │       │     SQLCODE ≠ 0 → ABEND 'WPCD'
                       │       │       (NO ROLLBACK — balances already committed)
                       │       │
                       │       └── Returns: COMM-SUCCESS, COMM-FAIL-CODE,
                       │                    COMM-FAVBAL, COMM-FACTBAL,
                       │                    COMM-TAVBAL, COMM-TACTBAL
                       │
                       ├── Zero all balance output fields (defensive clear)
                       ├── Evaluate SUBPGM-SUCCESS / SUBPGM-FAIL-CODE
                       ├── On success: populate dual balance display
                       │     FACTBALO, FAVBALO (+9(10).99 signed format)
                       │     TACTBALO, TAVBALO (+9(10).99 signed format)
                       │     MESSAGE: 'Transfer successfully applied.'
                       │
                       └── EXEC CICS RETURN TRANSID('OTFN') COMMAREA(WS-COMMAREA) LENGTH(29)
```

### CICS COMMAREA Flow

```
BNKMENU   ──(RETURN TRANSID 'OTFN', no COMMAREA)─────────► BNK1TFN (EIBCALEN=0 first pass)
BNK1TFN   ──(SUBPGM-PARMS / COPY XFRFUN)────────────────► XFRFUN ──► BNK1TFN
BNK1TFN   ──(WS-COMMAREA, 29 bytes)─────────────────────► OTFN (self-return, pseudo-conv loop)
```

---

## 5. Fail Code Reference

### XFRFUN → BNK1TFN Fail Codes

| Fail Code | Set By | Condition | Message in BNK1TFN |
|-----------|--------|-----------|-------------------|
| `1` | XFRFUN | FROM account not found (`SQLCODE +100` on FROM SELECT) | `Sorry the FROM ACCOUNT no was not found. Transfer not applied.` |
| `2` | XFRFUN | TO account not found (`SQLCODE +100` on TO SELECT) | `Sorry the TO ACCOUNT no was not found. Transfer not applied.` |
| `3` | XFRFUN | Unexpected DB2 error on FROM SELECT or FROM/TO UPDATE | `Sorry but the transfer could not be applied due to an unexpected error.` |
| `4` | XFRFUN | Amount ≤ zero (backend guard in PREMIERE) | `Please supply an amount greater than zero.` |
| `2` | XFRFUN | VSAM RLS storm-drain abend handled gracefully | `Sorry but the transfer could not be applied due to an unexpected error.` |
| Other | XFRFUN | Unknown | `Sorry but the transfer could not be applied due to an error.` |

### Abend Codes Across All Programs

| Abend Code | Program | Trigger |
|-----------|---------|---------|
| `HBNK` | BNK1TFN | Any CICS failure (RECEIVE MAP, SEND MAP, RETURN TRANSID, LINK) |
| `SAME` | XFRFUN | FROM and TO are the same account + sort code (programming error guard) |
| `FROM` | XFRFUN | FROM account UPDATE failure with non-`'1'` fail code (unexpected error) |
| `TO  ` | XFRFUN | TO account UPDATE failure with non-`'2'` fail code (unexpected error) |
| `HROL` | XFRFUN | SYNCPOINT ROLLBACK failure at any point |
| `RUF2` | XFRFUN | TO account SELECT deadlock retry exhausted (6 attempts) or timeout |
| `RUF3` | XFRFUN | TO account UPDATE failure (non-deadlock, non-recoverable) |
| `WPCD` | XFRFUN | PROCTRAN INSERT failure after both ACCOUNT UPDATEs committed |

---

## 6. Screen Flow and Key Behaviour

```
┌──────────────────────────────────────────────────────────────────────┐
│  BNK1TF — First Time (EIBCALEN=0)                                   │
│  CICS Banking Sample Application - Transfer funds.                  │
│  Provide a FROM account, a TO account and an Amount and press Enter.│
│                                                                      │
│  FROM Account Number: ________  TO Account Number: ________        │
│  AMOUNT: 0000000000.00                                              │
│                                                                      │
│  FROM Account   :          TO Account     :                        │
│  Sort Code      :          Sort Code      :                        │
│  Actual Balance :          Actual Balance :                        │
│  Avail Balance  :          Avail Balance  :                        │
│  F3=Exit   F12=Cancel                                               │
└──────────────────────┬───────────────────────────────────────────────┘
                       │ User enters: 00000010, 00000020, 500.00 → ENTER
                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  BNK1TF — After Successful Transfer                                 │
│  FROM Account Number: 00000010  TO Account Number: 00000020        │
│  AMOUNT: 0000000500.00                                              │
│                                                                      │
│  FROM Account   : 00000010  TO Account     : 00000020             │
│  Sort Code      : 987654    Sort Code      : 987654               │
│  Actual Balance : +0000472307.57  Actual Balance : +0000001000.00 │
│  Avail Balance  : +0000472307.57  Avail Balance  : +0000001000.00 │
│                                                                      │
│  MESSAGE: Transfer successfully applied.                            │
│  F3=Exit   F12=Cancel                                               │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 7. Key Design Points and Comparisons

### Unique Design Features of This Transaction

| Aspect | Detail |
|--------|--------|
| Dual-account input | `FACCNO` and `TACCNO` on the same row (row 8) — side by side. Unique in the suite |
| No sign field | Transfers are always positive. A `-` in the amount is explicitly rejected by `VALIDATE-AMOUNT` via `WS-NUM-COUNT-MINUS` tallying |
| Side-by-side output layout | Rows 11–14 show FROM (left) and TO (right) account data in parallel columns. Unique in the suite |
| Deadlock-prevention locking order | XFRFUN determines which account to lock first based on account number comparison (`COMM-FACCNO < COMM-TACCNO`). Always locks lower number first. Prevents circular wait deadlocks |
| Deadlock retry with backoff | `UPDATE-ACCOUNT-DB2-TO` detects `SQLCODE=-911 AND SQLERRD(3)=13172872` (deadlock). Rolls back, delays 1 second, then restarts the entire transfer from `UPDATE-ACCOUNT-DB2` top. Up to 5 retries before ABENDing |
| Full restart on deadlock | After a deadlock, `GO TO UPDATE-ACCOUNT-DB2` restarts the entire two-account update sequence, not just the failing step. This ensures locking order consistency is preserved on retry |
| PROCTRAN not rolled back on failure | If PROCTRAN INSERT fails after both ACCOUNT UPDATEs succeed, XFRFUN ABENDs with `WPCD` without rolling back the balance updates. The accounts are correct; the audit record is missing. Deliberate design choice |
| COPY ACCOUNT REPLACING | `WS-ACC-DATA2` uses `COPY ACCOUNT REPLACING "ACCOUNT" BY "ACCOUNT2"` to create a second independent account structure. XFRFUN uses a single shared `HOST-ACCOUNT-ROW` for DB2 host variables however — the two COPY structures are declared but the actual DB2 operations reuse the same host variable area |
| SQLDA declared | `EXEC SQL INCLUDE SQLDA` is declared in WORKING STORAGE, suggesting the program was designed with dynamic SQL capability in mind. Not actively used in the transfer path |
| Single PROCTRAN record | Only one `PROCTRAN` record is written per transfer (for the FROM/debit side). The TO/credit side is captured in the description field, not as a separate row |

### Comparison with DBCRFUN (Credit/Debit — Option 6)

| Aspect | `OTFN` Transfer (`XFRFUN`) | `OCRA` Credit/Debit (`DBCRFUN`) |
|--------|----------------------------|----------------------------------|
| Accounts affected | Two accounts (FROM and TO) | One account |
| DB2 UPDATE operations | Two `EXEC SQL UPDATE ACCOUNT` | One `EXEC SQL UPDATE ACCOUNT` |
| Locking order | Explicit — lower account number first | N/A — single account |
| Deadlock retry | Yes — up to 5 retries with 1-second backoff | No retry logic |
| Amount sign | Always positive; sign rejected at input | Signed float — positive = credit, negative = debit |
| Facility type checks | None — no MORTGAGE/LOAN restrictions | Yes — payment channel only |
| SYNCPOINT ROLLBACK on PROCTRAN fail | No — ABENDs with `WPCD`; balances kept | Yes — rolls back ACCOUNT UPDATE |
| PROCTRAN type | `TFR` (Transfer) | `DEB`/`CRE`/`PDR`/`PCR` (context-dependent) |
| PROCTRAN records written | 1 (FROM side only; TO in description) | 1 (the single affected account) |
| INQUIRE ASSOCIATION | No | Yes — captures APPLID, USERID, FACILTYPE |
| COMMAREA size | 29 bytes | 21 bytes (plus origin fields) |

---

*Analysis generated from source review of `BNK1TFM.bms`, `BNK1TFN.cbl`, and `XFRFUN.cbl`.*

# COBOL Program Analysis
## Banking Application — BMS Suite (IBM Corp. 2023)

> **Programs Analysed:** `BNKMENU` · `BNK1CCS` · `CRECUST`

---

## Table of Contents

1. [BNKMENU — Bank Menu (Transaction Router)](#1-bnkmenu--bank-menu-transaction-router)
2. [BNK1CCS — Create Customer Screen Handler](#2-bnk1ccs--create-customer-screen-handler)
3. [CRECUST — Create Customer Backend](#3-crecust--create-customer-backend)
4. [Cross-Program Call Chain Summary](#4-cross-program-call-chain-summary)

---

## 1. BNKMENU — Bank Menu (Transaction Router)

**Program ID:** `BNKMENU` | **Transaction ID:** `OMEN`

---

### 1.1 Validations

| # | Field / Check | Rule | Error Message |
|---|--------------|------|---------------|
| 1 | AID Key | Only PA1/PA2/PA3, PF3, PF12, CLEAR, ENTER are accepted | `Invalid key pressed.` |
| 2 | ACTION field (EDIT-MENU-DATA) | Must be one of: `1`, `2`, `3`, `4`, `5`, `6`, `7`, or `A` | `You must enter a valid value (1-7 or A).` |
| 3 | RECEIVE MAP response | `MAPFAIL` → map refreshed/erased; any other non-normal RESP → ABEND via `ABNDPROC` | — |
| 4 | RETURN TRANSID response | RESP checked after each of the 8 destination RETURN commands; failure triggers `ABNDPROC` link and task abend | — |

---

### 1.2 Processing

- **First time through (EIBCALEN = 0):** Sends map `BNK1ME` (mapset `BNK1MAI`) with ERASE; cursor positioned on ACTION field.
- **ENTER:** Receives map, validates ACTION field, then routes to the downstream transaction using `EXEC CICS RETURN TRANSID(…) IMMEDIATE`.

| Option | Action | Target TRANSID |
|--------|--------|---------------|
| `1` | Display Customer details | `ODCS` |
| `2` | Display Account details | `ODAC` |
| `3` | Create Customer | `OCCS` |
| `4` | Create Account | `OCAC` |
| `5` | Update Account | `OUAC` |
| `6` | Credit/Debit funds | `OCRA` |
| `7` | Transfer funds | `OTFN` |
| `A` | Accounts for a customer | `OCCA` |

- **PF3 / PF12:** Sends "Session Ended" termination text and returns without TRANSID (ends session).
- **CLEAR:** Issues `EXEC CICS SEND CONTROL ERASE FREEKB` then returns.
- **Abend handling:** All failures link to `ABNDPROC` with full `ABNDINFO-REC` (APPLID, TASKNO, TRANID, timestamp, freeform message, RESP/RESP2) then abend with code `HBNK`.

---

### 1.3 Files / Database / CICS Storage

| Resource | Type | Usage |
|----------|------|-------|
| `BNK1ME` / `BNK1MAI` | CICS BMS Map | Input (`RECEIVE`) and Output (`SEND`) |
| `COMMUNICATION-AREA` (1 byte) | CICS COMMAREA | Passed on `RETURN` to `OMEN` transid |
| `ABNDINFO-REC` (COPY ABNDINFO) | CICS COMMAREA | Passed to `ABNDPROC` on failure |
| No VSAM files or DB2 tables | — | None accessed directly |

---

## 2. BNK1CCS — Create Customer Screen Handler

**Program ID:** `BNK1CCS` | **Transaction ID:** `OCCS`

---

### 2.1 Validations

All checks are in the `EDIT-DATA` section. Each failure short-circuits via `GO TO ED999`, setting `VALID-DATA-SW = 'N'` and populating `MESSAGEO`.

| # | Field | Check | Error Message |
|---|-------|-------|---------------|
| 1 | `CUSTNO2` | If already populated on screen, user must clear first | `Please clear screen before creating new user` |
| 2 | `CUSTTITI` (Title) — presence | Must be populated; not spaces, not LOW-VALUES, length > 0 | Lists valid titles |
| 3 | `CUSTTITI` (Title) — value | Must be one of: `Mr`, `Mrs`, `Miss`, `Ms`, `Dr`, `Drs`, `Professor`, `Lord`, `Sir`, `Lady` (case-insensitive, underscore-padded variants handled) | `Valid titles are: Mr,Mrs,Miss,Ms,Dr,Drs,Professor,Lord,Sir,Lady` |
| 4 | `CHRISTNI` (First Name) | Must not be blank, underscores, or zero-length | `Please supply a valid First Name` |
| 5 | `CUSTSNI` (Surname) | Must not be blank, underscores, or zero-length | `Please supply a valid Surname` |
| 6 | `CUSTAD1I` (Address Line 1) | Must be supplied (not blank, not leading underscore, length > 0) | `Please supply a valid Address Line 1` |
| 7 | `DOBDDI` (DOB Day) — presence | Must be present (length > 0, not `__`) | `Please supply a valid Date of Birth DD` |
| 8 | `DOBMMI` (DOB Month) — presence | Must be present | `Please supply a valid Date of Birth MM` |
| 9 | `DOBYYI` (DOB Year) — presence | Must be present (length ≥ 4, not `____`) | `Please supply a valid Date of Birth YYYY` |
| 10 | `DOBDDI` — numeric | Must be NUMERIC | `Non numeric Date of Birth DD entered` |
| 11 | `DOBMMI` — numeric | Must be NUMERIC | `Non numeric Date of Birth MM entered` |
| 12 | `DOBYYI` — numeric | Must be NUMERIC | `Non numeric Date of Birth YYYY entered` |
| 13 | `DOBDDI` — range | Must be 01–31 | `Please supply a valid Date of Birth (DD)` |
| 14 | `DOBMMI` — range | Must be 01–12 | `Please supply a valid Date of Birth (MM)` |
| 15 | All mandatory fields | Catch-all sweep; cursor set to first missing mandatory field | `Missing expected data.` |

---

### 2.2 Processing

- **Terminal UCTRAN management:** Before every `RECEIVE MAP`, the terminal's uppercase translation (`UCTRANST`) is read via `INQUIRE TERMINAL`, stored, and switched to `NOUCTRAN` so mixed-case names and addresses can be entered. It is restored on all exit paths (normal, PF3, PF12, and all abend paths).

- **First time through (EIBCALEN = 0):** Sends map `BNK1CC` (mapset `BNK1CCM`) with ERASE; cursor on `CUSTTIT` field; stores terminal UCTRAN default.

- **ENTER → PROCESS-MAP:**
  1. Receives map (`RECEIVE MAP ASIS` to preserve case).
  2. Performs `EDIT-DATA` validations.
  3. If valid, preprocesses fields:
     - `INSPECT` replaces all `_` characters with spaces in name and address fields.
     - `STRING` concatenates title + first name + initials + surname → `SUBPGM-NAME`.
     - `STRING` concatenates address lines 1–3 → `SUBPGM-ADDRESS`.
     - DOB components moved to `SUBPGM-BIRTH-DAY/MONTH/YEAR`.
  4. Calls **CRECUST** via `EXEC CICS LINK PROGRAM('CRECUST') COMMAREA(SUBPGM-PARMS) SYNCONRETURN`.
  5. Inspects `SUBPGM-SUCCESS` on return:

| SUBPGM-SUCCESS | SUBPGM-FAIL-CODE | Action |
|---|---|---|
| `N` | `O` | "Sorry, customer is too old. Please check D.O.B." |
| `N` | `Y` | "Sorry, customer D.O.B. is in the future." |
| `N` | `Z` | "Sorry, customer D.O.B. is invalid." |
| `Y` | — | Displays sortcode, customer number, credit score, review date, address. Success message. |

- **PF3:** Restores UCTRAN; returns to `OMEN` (main menu).
- **PF12:** Sends termination text "Session Ended"; restores UCTRAN; returns.
- **CLEAR:** Sends map `MAPONLY ERASE`; restores UCTRAN; returns to `OCCS`.
- **Abend handler:** Registered at startup via `EXEC CICS HANDLE ABEND LABEL(HANDLE-ABEND)`. On abend, restores UCTRAN and re-ABENDs with the original abend code.

---

### 2.3 Files / Database / CICS Storage

| Resource | Type | Usage |
|----------|------|-------|
| `BNK1CC` / `BNK1CCM` | CICS BMS Map | Input (`RECEIVE MAP ASIS`) and Output (`SEND MAP`) |
| `DFHCOMMAREA` (5 bytes) | CICS COMMAREA | Input from `OMEN`; holds `COMM-DATA` and `COMM-TERM` (stored UCTRANS) |
| `WS-COMM-AREA` | CICS COMMAREA | Passed on `RETURN TRANSID('OCCS')`, length 248 |
| `SUBPGM-PARMS` | CICS COMMAREA | Passed to/from `CRECUST` via `EXEC CICS LINK` |
| `ABNDINFO-REC` (COPY ABNDINFO) | CICS COMMAREA | Passed to `ABNDPROC` on failure |
| Terminal `UCTRANST` | CICS Terminal attribute | Read (`INQUIRE`), modified (`SET`), and restored |
| No VSAM files or DB2 tables | — | All data access delegated to `CRECUST` |

---

## 3. CRECUST — Create Customer Backend

**Program ID:** `CRECUST` | **Invocation:** `EXEC CICS LINK` from `BNK1CCS`

---

### 3.1 Validations

| # | Check | Logic | Fail Code |
|---|-------|-------|-----------|
| 1 | **Title re-validation** | UNSTRINGs first word from `COMM-NAME`; checks against: `Professor`, `Mr`, `Mrs`, `Miss`, `Ms`, `Dr`, `Drs`, `Lord`, `Sir`, `Lady`, or spaces | `T` → immediate GOBACK |
| 2 | **DOB — year floor** | Birth year < 1601 is out of range for Lilian date functions | `O` |
| 3 | **DOB — structural validity** | `CEEDAYS` LE call converts DOB to Lilian day number; failure = invalid date | `Z` |
| 4 | **DOB — age > 150 years** | Today's year − birth year > 150 | `O` |
| 5 | **DOB — future date** | DOB Lilian > Today's Lilian | `Y` |
| 6 | **Credit check — no data** | All 5 async credit agencies return no data | `G` → credit score = 0, review date = today |
| 7 | **ENQ failure** | `EXEC CICS ENQ` on named counter resource fails | `3` |
| 8 | **VSAM WRITE failure** | Write to CUSTOMER file fails after up to 100 SYSIDERR retries | `1` → DEQ then return |
| 9 | **Control record read/rewrite failure** | CUSTOMER control record read or rewrite fails | `4` → DEQ then return |
| 10 | **DEQ failure** | `EXEC CICS DEQ` fails | `5` |
| 11 | **DB2 INSERT failure** | `SQLCODE ≠ 0` on PROCTRAN insert | Links to `ABNDPROC`; abends with code `HWPT` |

---

### 3.2 Processing

#### Step 1 — Title Validation
Re-validates the title extracted from `COMM-NAME` (safety check in backend, independent of BNK1CCS).

#### Step 2 — Time/Date Population
`EXEC CICS ASKTIME` + `FORMATTIME` to capture current date (DDMMYYYY) and time.

#### Step 3 — Asynchronous Credit Check (CREDIT-CHECK section)

```
Loop 5 times (WS-CC-CNT = 1 to 5):
  ├── Build TRANSID: 'OCR1' to 'OCR5'
  ├── PUT DFHCOMMAREA into container CIPA–CIPE on channel 'CIPCREDCHANN'
  └── EXEC CICS RUN TRANSID(OCRn) CHANNEL(…) CHILD(token) → async dispatch

EXEC CICS DELAY FOR SECONDS(3)   ← wait for child transactions

PERFORM UNTIL WS-FINISHED-FETCHING = 'Y':
  EXEC CICS FETCH ANY NOSUSPEND COMPSTATUS(…) ABCODE(…)
  ├── NORMAL   → GET CONTAINER(CIPA–CIPE); accumulate credit score
  ├── ABEND    → COMM-FAIL-CODE = 'F'; exit
  ├── SECERROR → COMM-FAIL-CODE = 'G'; exit
  ├── NOTFINISHED (RESP2=52):
  │     ├── WS-RETRIEVED-CNT = 0 → error, exit
  │     └── WS-RETRIEVED-CNT > 0 → compute average, generate review date
  └── NOTFND (RESP2=1):
        ├── WS-RETRIEVED-CNT = 0 → error flag set
        └── WS-RETRIEVED-CNT > 0 → compute average, generate review date

Average credit score = WS-TOTAL-CS-SCR / WS-RETRIEVED-CNT
Review date = random date within next 1–21 days (seeded by EIBTASKN)
```

#### Step 4 — Date of Birth Check
Uses IBM Language Environment (LE) calls:
- `CALL "CEEDAYS"` — converts DOB to Lilian day number.
- `CALL "CEELOCT"` — retrieves today's Lilian day number and Gregorian date.
- Age and future-date checks applied against results.

#### Step 5 — ENQ Named Counter
`EXEC CICS ENQ RESOURCE('CBSACUST' + sortcode)` (16 bytes) — serialises customer number assignment to prevent duplicates under concurrent load.

#### Step 6 — Get Next Customer Number (GET-LAST-CUSTOMER-VSAM)
1. Reads CUSTOMER control record (key = sortcode `000000` + customer number `9999999999`) with `UPDATE` lock.
2. Increments `LAST-CUSTOMER-NUMBER` by 1.
3. REWRITEs the control record.
4. Sets `NCS-CUST-NO-VALUE` and `COMM-NUMBER` to the new number.
5. **SYSIDERR retry loop:** Up to 100 retries, 3-second delay each, on both READ and REWRITE.

#### Step 7 — Write Customer Record (WRITE-CUSTOMER-VSAM)
Builds CUSTOMER record with:

| Field | Source |
|-------|--------|
| Eyecatcher | `'CUST'` |
| Sort Code | `SORTCODE` copybook constant |
| Customer Number | From NCS / control record |
| Name | `COMM-NAME` |
| Address | `COMM-ADDRESS` |
| Date of Birth | `COMM-DATE-OF-BIRTH` |
| Credit Score | From async credit check average |
| CS Review Date | Random date within next 21 days |

Issues `EXEC CICS WRITE FILE('CUSTOMER')` with SYSIDERR retry (up to 100 × 3-second delays). On success, also REWRITEs control record to increment `NUMBER-OF-CUSTOMERS`.

#### Step 8 — Write PROCTRAN Audit Record (WRITE-PROCTRAN-DB2)
Inserts a row into DB2 `PROCTRAN` table:

| Column | Value |
|--------|-------|
| `PROCTRAN_EYECATCHER` | `'PRTR'` |
| `PROCTRAN_SORTCODE` | Sort code |
| `PROCTRAN_NUMBER` | Zeros (not account-specific) |
| `PROCTRAN_DATE` | Current date (DDMMYYYY formatted) |
| `PROCTRAN_TIME` | Current time |
| `PROCTRAN_REF` | EIBTASKN (task number) |
| `PROCTRAN_TYPE` | `'OCC'` (Open Customer Create) |
| `PROCTRAN_DESC` | Sortcode + Customer No + Name + DOB |
| `PROCTRAN_AMOUNT` | Zeros |

`SQLCODE ≠ 0` → links to `ABNDPROC` + ABEND code `HWPT`.

#### Step 9 — DEQ and Return
`EXEC CICS DEQ` releases the named counter lock.
Sets `COMM-SUCCESS = 'Y'`, `COMM-SORTCODE`, `COMM-NUMBER`, `COMM-EYECATCHER = 'CUST'` in COMMAREA and returns to BNK1CCS.

---

### 3.3 Files / Database / CICS Storage

| Resource | Type | Mode | Notes |
|----------|------|------|-------|
| `CUSTOMER` (VSAM KSDS) | CICS File | READ UPDATE, WRITE, REWRITE | New customer records; control record at key `000000` + `9999999999` for sequence tracking |
| `PROCTRAN` (DB2 table) | DB2 Embedded SQL | INSERT | Transaction audit trail; uses `EXEC SQL INCLUDE PROCDB2` copybook and SQLCA |
| `DFHCOMMAREA` (COPY CRECUST) | CICS COMMAREA | Input / Output | Received from BNK1CCS; returned with success/fail flags and customer details |
| Named Counter `CBSACUST` + sortcode | CICS ENQ / DEQ | Exclusive lock | 16-byte resource; serialises customer number assignment |
| Channel `CIPCREDCHANN` | CICS Channel | PUT / RUN / FETCH / GET | Containers `CIPA`–`CIPE`; dispatches 5 async child transactions `OCR1`–`OCR5` for credit checks |
| `SORTCODE` (COPY SORTCODE) | Working Storage | Read | Bank sort code constant |
| `ABNDINFO-REC` (COPY ABNDINFO) | CICS COMMAREA | Output | Passed to `ABNDPROC` on failure |
| LE routines `CEEDAYS`, `CEELOCT` | Language Environment CALL | Call | DOB Lilian date conversion and today's date retrieval |

---

## 4. Cross-Program Call Chain Summary

```
BNKMENU  (OMEN)
  │
  └── Option 3 ──► RETURN TRANSID('OCCS')
                       │
                       ▼
                   BNK1CCS  (OCCS)
                       │
                       ├── EXEC CICS LINK ──► CRECUST
                       │                          │
                       │                          ├── EXEC CICS RUN TRANSID OCR1–OCR5
                       │                          │      (async credit checks, channel-based)
                       │                          │
                       │                          ├── EXEC CICS WRITE FILE('CUSTOMER')
                       │                          │      (VSAM — new customer record)
                       │                          │
                       │                          ├── EXEC SQL INSERT INTO PROCTRAN
                       │                          │      (DB2 — audit trail)
                       │                          │
                       │                          └── EXEC CICS LINK ──► ABNDPROC
                       │                                 (on any failure)
                       │
                       └── Displays result on BNK1CC map
                               │
                               └── RETURN TRANSID('OMEN')
                                       (loops back to menu)
```

### CICS COMMAREA Flow

```
BNKMENU ──(1 byte COMMAREA)──► BNK1CCS
BNK1CCS ──(SUBPGM-PARMS COMMAREA)──► CRECUST ──(same COMMAREA, updated)──► BNK1CCS
BNK1CCS ──(248 byte COMMAREA)──► OMEN (self-return for pseudo-conversational loop)
```

### Fail Code Reference (CRECUST)

| Fail Code | Meaning |
|-----------|---------|
| `T` | Invalid title in customer name |
| `O` | Customer too old (DOB year < 1601 or age > 150) |
| `Y` | DOB is in the future |
| `Z` | DOB is structurally invalid (CEEDAYS failed) |
| `G` | Credit check error / async children returned no data |
| `A` | PUT CONTAINER failed for async credit check |
| `B` | RUN TRANSID failed for async credit check |
| `C` | FETCH ANY returned NOTFINISHED with no data |
| `D` | FETCH ANY returned INVREQ (no children) |
| `E` | GET CONTAINER failed after successful FETCH |
| `F` | Child transaction ABENDed |
| `H` | FETCH ANY returned unknown COMPSTATUS |
| `1` | VSAM WRITE to CUSTOMER file failed |
| `3` | CICS ENQ on named counter failed |
| `4` | VSAM READ/REWRITE of control record failed |
| `5` | CICS DEQ on named counter failed |

---

*Analysis generated from source review of `BNK1CCS.cbl`, `BNKMENU.cbl`, and `CRECUST.cbl`.*

# Display / Update / Delete Customer — Component Analysis
## CICS Banking Sample Application

> **Transaction:** `ODCS` (triggered from `OMEN` Menu Option 1)
> **Components:** `BNK1DCM` (BMS Map) · `BNK1DCS` (Screen Handler) · `INQCUST` (Inquiry) · `DELCUS` (Delete) · `UPDCUST` (Update)

---

## Table of Contents

1. [BNK1DCM — BMS Map (BNK1DC)](#1-bnk1dcm--bms-map-bnk1dc)
2. [BNK1DCS — Display / Update / Delete Customer Screen Handler](#2-bnk1dcs--display--update--delete-customer-screen-handler)
3. [INQCUST — Inquire Customer](#3-inqcust--inquire-customer)
4. [DELCUS — Delete Customer](#4-delcus--delete-customer)
5. [UPDCUST — Update Customer](#5-updcust--update-customer)
6. [Cross-Component Call Chain Summary](#6-cross-component-call-chain-summary)
7. [Fail Code Reference](#7-fail-code-reference)
8. [Screen Flow and Key Behaviour](#8-screen-flow-and-key-behaviour)

---

## 1. BNK1DCM — BMS Map (BNK1DC)

**Mapset:** `BNK1DCM` | **Map:** `BNK1DC` | **Source:** `BNK1DCM.bms`

---

### 1.1 Map Identity

| Attribute | Value |
|-----------|-------|
| Mapset Name | `BNK1DCM` |
| Map Name | `BNK1DC` |
| Terminal Type | 3270-2 |
| Mode | INOUT |
| Language | COBOL |
| Storage | AUTO |
| Control | FREEKB |
| Extended Attributes | COLOR, HILIGHT, OUTLINE, PS, SOSI |
| Title | `CICS Banking Sample Application - Display Customer.` (Red, Row 1) |
| Instruction | `Provide a CUSTOMER number. Then press Enter.` (Turquoise, Row 3) |

---

### 1.2 Map Fields — Screen Layout

| Row | Field Name | Position | Length | Attributes | Color | Description |
|-----|-----------|----------|--------|------------|-------|-------------|
| 1 | *(literal)* | (1,1) | 7 | PROT | Blue | Map ID label `BNK1DC` |
| 1 | `COMPANY` | (1,16) | 55 | PROT | Red | Title banner |
| 3 | *(literal)* | (3,1) | 44 | ASKIP, PROT | Turquoise | Instruction text |
| 5 | *(literal)* | (5,1) | 16 | ASKIP, PROT | Turquoise | Label: `CUSTOMER NUMBER` |
| 5 | `CUSTNO` | (5,17) | 10 | NORM, IC | Green + Underline | **Input:** Customer Number (cursor auto-positioned here; IC attribute) |
| 7 | `SORTC` | (7,18) | 6 | PROT, FSET, ASKIP | Neutral | **Output:** Sort Code |
| 8 | `CUSTNO2` | (8,18) | 10 | PROT, ASKIP, FSET | Neutral | **Output:** Confirmed Customer Number |
| 9 | `CUSTNAM` | (9,18) | 60 | PROT, FSET, ASKIP | Neutral | **Output / Update:** Customer Name (unprotected during update) |
| 10 | `CUSTAD1` | (10,18) | 60 | PROT, FSET, ASKIP | Neutral | **Output / Update:** Customer Address Line 1 |
| 11 | `CUSTAD2` | (11,18) | 60 | PROT, ASKIP, FSET | Neutral | **Output / Update:** Customer Address Line 2 |
| 12 | `CUSTAD3` | (12,18) | 40 | PROT, FSET, ASKIP | Neutral | **Output / Update:** Customer Address Line 3 |
| 13 | `DOBDD` | (13,18) | 2 | PROT, FSET, ASKIP | Neutral | **Output:** Date of Birth — Day |
| 13 | `DOBMM` | (13,23) | 2 | PROT, FSET, ASKIP | Neutral | **Output:** Date of Birth — Month |
| 13 | `DOBYY` | (13,28) | 4 | PROT, FSET, ASKIP | Neutral | **Output:** Date of Birth — Year |
| 14 | `CREDSC` | (14,18) | 3 | PROT, FSET, ASKIP | Neutral | **Output:** Credit Score (3 digits) |
| 15 | `SCRDTDD` | (15,18) | 2 | PROT, FSET, ASKIP | Neutral | **Output:** CS Review Date — Day |
| 15 | `SCRDTMM` | (15,23) | 2 | PROT, FSET, ASKIP | Neutral | **Output:** CS Review Date — Month |
| 15 | `SCRDTYY` | (15,28) | 4 | PROT, FSET, ASKIP | Neutral | **Output:** CS Review Date — Year |
| 23 | `MESSAGE` | (23,1) | 79 | BRT, PROT, ASKIP | Yellow | **Output:** User / error messages |
| 24 | *(literal)* | (24,1) | 20 | PROT, ASKIP | Blue | `F3=Exit   F12=Cancel` |
| 24 | `DUMMY` | (24,79) | 1 | DRK, PROT, FSET, ASKIP | — | Hidden MDT-forcing field |

**Notes:**
- `CUSTNO` has the `IC` (Initial Cursor) attribute — cursor positions here automatically on map display.
- `CUSTNO` is the only user input field in display mode. All other fields are protected output-only.
- During Update mode (PF10 path), `CUSTNAM`, `CUSTAD1`, `CUSTAD2`, `CUSTAD3` are dynamically unprotected by `BNK1DCS` using attribute manipulation (`DFHGREEN`, `DFHUNDLN`, attribute byte `'A'`).
- DOB and Sort Code fields remain protected even during update — these fields cannot be changed.
- Date fields use `/` separator literals between DD, MM, YYYY (rows 13 and 15).

**Function Key Legend:**

| Key | Action |
|-----|--------|
| Enter | Look up customer (first time) OR submit update (update mode) |
| PF3 | Exit — return to main menu (`OMEN`) |
| PF5 | Delete customer and all associated accounts |
| PF10 | Unlock fields for update — transition to update mode |
| PF12 / AID | Cancel — send "Session Ended" termination message |
| CLEAR | Clear screen |
| PA1/PA2/PA3 | Continue — no action |

---

## 2. BNK1DCS — Display / Update / Delete Customer Screen Handler

**Program ID:** `BNK1DCS` | **Transaction ID:** `ODCS`

This is the primary driver for the Display Customer function. It handles **three distinct operations** from a single screen: display, update (via PF10 then Enter), and delete (via PF5). The COMMAREA field `COMM-UPD` acts as a mode flag — `'Y'` indicates the screen is in edit/update mode.

---

### 2.1 Validations

#### EDIT-DATA Section (used for Display, Delete, and PF10 pre-check)

| # | Field | Check | Error Message |
|---|-------|-------|---------------|
| 1 | `CUSTNOI` — presence | `CUSTNOL = ZERO` or `CUSTNOI = LOW-VALUES` | `Please enter a customer number.` |
| 2 | `CUSTNOI` — numeric | `EXEC CICS BIF DEEDIT` applied; `NOT NUMERIC` check | `Please enter a customer number.` |

#### EDIT-DATA2 Section (used for Enter in Update mode — COMM-UPD = 'Y')

| # | Field | Check | Error Message |
|---|-------|-------|---------------|
| 3 | `CUSTNAMI` — title (UNSTRING + EVALUATE) | First word must be one of: `Professor`, `Mr`, `Mrs`, `Miss`, `Ms`, `Dr`, `Drs`, `Lord`, `Sir`, `Lady` | `Valid titles are: Mr,Mrs,Miss,Ms,Dr,Professor,Drs,Lord,Sir,Lady` |
| 4 | Address (all three lines) — not all blank | `CUSTAD1I = SPACES AND CUSTAD2I = SPACES AND CUSTAD3I = SPACES` | `Address must not be all spaces - please reenter` |

#### VALIDATE-DATA Section (additional checks for Delete and PF10 pre-check)

| # | Field | Check | Error Message |
|---|-------|-------|---------------|
| 5 | Sort code | `INQCUST-SCODE = '000000'` — no valid sort code in COMMAREA | `The Sort code / Customer number combination is not VALID.` |
| 6 | `CUSTNOI` — reserved values | `CUSTNOI = ZERO` or `CUSTNOI = '9999999999'` | `The customer number is not VALID.` |

#### POST-LINK Result Checks

| # | Event | Check | Error Message |
|---|-------|-------|---------------|
| 7 | After `INQCUST` | `INQCUST-NAME = SPACES AND INQCUST-ADDR = SPACES` | `Sorry, but that customer number was not found.` |
| 8 | After `DELCUS` fail code `1` | `COMM-DEL-SUCCESS = 'N' AND COMM-DEL-FAIL-CD = '1'` | `Sorry but that Cust no was not found. Customer NOT deleted.` |
| 9 | After `DELCUS` fail code `2` | `COMM-DEL-SUCCESS = 'N' AND COMM-DEL-FAIL-CD = '2'` | `Sorry but a datastore error occurred. Action NOT applied.` |
| 10 | After `DELCUS` fail code `3` | `COMM-DEL-SUCCESS = 'N' AND COMM-DEL-FAIL-CD = '3'` | `Sorry but a delete error occurred. Customer NOT deleted.` |
| 11 | After `DELCUS` any other failure | `COMM-DEL-SUCCESS = 'N'` | `Sorry but an error occurred. Customer NOT deleted.` |
| 12 | After `UPDCUST` fail code `1` | Customer not found | `Sorry but that Cust no was not found. Customer NOT updated.` |
| 13 | After `UPDCUST` fail code `2` | Datastore error | `Sorry but a datastore error occurred. Customer NOT updated.` |
| 14 | After `UPDCUST` fail code `3` | REWRITE error | `Sorry but an update error occurred. Customer NOT updated.` |
| 15 | After `UPDCUST` any other failure | Unknown error | `Sorry but an unknown error occurred. Customer NOT updated.` |

---

### 2.2 Processing

#### Key Press Routing (PREMIERE SECTION — EVALUATE on EIBAID)

| AID Key | Action |
|---------|--------|
| `EIBCALEN = 0` | First time through: send blank map with ERASE; store terminal UCTRANS; initialise COMMAREA |
| `DFHPA1/PA2/PA3` | `CONTINUE` — no action |
| `DFHPF3` | Restore UCTRANS; `RETURN TRANSID('OMEN') IMMEDIATE` |
| `DFHPF5` | `PERFORM PROCESS-MAP` — delete path |
| `DFHPF10` | `PERFORM PROCESS-MAP` — unlock for update path |
| `DFHAID` / `DFHPF12` | Restore UCTRANS; send "Session Ended"; plain `EXEC CICS RETURN` |
| `DFHCLEAR` | Restore UCTRANS; `SEND CONTROL ERASE FREEKB`; plain `EXEC CICS RETURN` |
| `DFHENTER` | `PERFORM PROCESS-MAP` — lookup or update-submit path |
| Any other key | "Invalid key pressed." message with alarm |

After all paths: copies COMMAREA fields back to `WS-COMM-AREA`; issues `EXEC CICS RETURN TRANSID('ODCS') COMMAREA(WS-COMM-AREA) LENGTH(266)`.

#### PROCESS-MAP Section — Detailed Flow

```
PERFORM RECEIVE-MAP
  (Turns off UCTRAN; RECEIVE MAP 'BNK1DC' ASIS; turns on UCTRAN)

IF ENTER AND COMM-UPD ≠ 'Y'  (standard display lookup):
  PERFORM EDIT-DATA
  IF VALID → PERFORM GET-CUST-DATA
    EXEC CICS LINK INQCUST
    IF found → populate all map output fields (sort code, name, address,
                DOB split DD/MM/YYYY, credit score, CS review date)
               MESSAGE: 'Customer lookup successful. <PF5> to Delete. <PF10> to Update.'
    IF not found → clear all output fields; message: 'Sorry, but that customer number was not found.'

IF ENTER AND COMM-UPD = 'Y'  (submit update after PF10):
  PERFORM EDIT-DATA2  (title + address validation)
  IF VALID → PERFORM UPDATE-CUST-DATA
    Build UPDCUST-COMMAREA (scode, custno, name, address STRING'd,
    DOB reassembled from DD/MM/YYYY parts, credit score, CS review date)
    EXEC CICS LINK UPDCUST
    On success → display updated data on map; re-protect all fields;
                 MESSAGE: 'Customer <custno> was updated successfully'
    On failure → display error message per fail code

IF PF5 (delete):
  PERFORM EDIT-DATA  (customer number presence + numeric)
  PERFORM VALIDATE-DATA  (sort code not 000000; custno not 0 or 9s)
  IF VALID → PERFORM DEL-CUST-DATA
    EXEC CICS LINK DELCUS (passes CUSTNO2I — the displayed confirmed number)
    On success → clear all output fields; MESSAGE: 'Customer <custno> and associated accounts were successfully deleted.'
    On failure → display error message per fail code

IF PF10 (initiate update):
  PERFORM EDIT-DATA  (customer number presence + numeric)
  PERFORM VALIDATE-DATA  (sort code not 000000; custno not 0 or 9s)
  IF VALID → PERFORM UNPROT-CUST-DATA:
    Saves all displayed data to DFHCOMMAREA (eye, scode, custno, name, addr, DOB, credit score, review date)
    Sets COMM-UPD = 'Y'  (mode flag for next ENTER)
    Dynamically unprotects CUSTNAM, CUSTAD1/2/3 (green + underline + attr 'A')
    Dynamically protects CUSTNO (DFHBMASK; neutral colour)
    Positions cursor at CUSTNAM
    MESSAGE: 'Amend data then press <ENTER>.'
```

#### Terminal UCTRAN Management

On first pass (`STORE-TERM-DEF`):
- `EXEC CICS INQUIRE TERMINAL UCTRANST(WS-UCTRANS)` — save current setting.
- If `UCTRAN` or `TRANIDONLY`, switch to `NOUCTRAN` to allow mixed-case name/address input.
- Saved value stored in `WS-COMM-TERM` / `COMM-TERM` COMMAREA field.

On `RECEIVE-MAP` (`RECEIVE-MAP` section):
- Same INQUIRE + SET NOUCTRAN before every receive.
- `RECEIVE MAP ASIS` preserves case of name and address.

On exit / PF3 / PF12 / CLEAR / abend (`RESTORE-TERM-DEF`):
- Reads `WS-COMM-TERM` from COMMAREA; issues `SET TERMINAL UCTRANST` to restore original.

#### PROT-CUST-DATA Section (called after successful update)
- Copies updated data back from `UPDCUST-COMMAREA` to screen output fields.
- Re-protects all fields: sets `DFHBMPRF` attributes on CUSTNAM, CUSTAD1/2/3.
- Re-enables and greens the `CUSTNO` field (ready for next lookup).
- Sets `COMM-UPD = 'N'` — resets mode flag.

---

### 2.3 Files / Database / CICS Storage

| Resource | Type | Usage |
|----------|------|-------|
| `BNK1DC` / `BNK1DCM` | CICS BMS Map | Input (`RECEIVE MAP ASIS`) and Output (`SEND MAP ERASE` / `DATAONLY` / `DATAONLY ALARM`) |
| `DFHCOMMAREA` (266 bytes) | CICS COMMAREA | Input from `OMEN` or prior `ODCS` cycle; fields: `COMM-TERM`, `COMM-EYE`, `COMM-SCODE`, `COMM-CUSTNO`, `COMM-NAME`, `COMM-ADDR`, `COMM-DOB`, `COMM-CREDIT-SCORE`, `COMM-CS-REVIEW-DATE`, `COMM-DEL-SUCCESS`, `COMM-DEL-FAIL-CD`, `COMM-UPD` |
| `WS-COMM-AREA` (266 bytes) | CICS COMMAREA | Passed on `RETURN TRANSID('ODCS')` — pseudo-conversational loop |
| `INQCUST-COMMAREA` (COPY INQCUST) | CICS COMMAREA | Passed to / received from `INQCUST` via `EXEC CICS LINK` |
| `DELCUS-COMMAREA` (COPY DELCUS) | CICS COMMAREA | Passed to / received from `DELCUS` via `EXEC CICS LINK` |
| `UPDCUST-COMMAREA` (COPY UPDCUST) | CICS COMMAREA | Passed to / received from `UPDCUST` via `EXEC CICS LINK` |
| `ABNDINFO-REC` (COPY ABNDINFO) | CICS COMMAREA | Passed to `ABNDPROC` on any CICS failure |
| Terminal `UCTRANST` | CICS Terminal attribute | Read (`INQUIRE`), modified (`SET NOUCTRAN`), and restored on all exit paths |
| No VSAM files or DB2 tables | — | All data access delegated to backend programs |

---

### 2.4 Programs Called by BNK1DCS

| Program | Call Method | Purpose |
|---------|-------------|---------|
| `INQCUST` | `EXEC CICS LINK … SYNCONRETURN` | Retrieve customer record by customer number |
| `DELCUS` | `EXEC CICS LINK … SYNCONRETURN` | Delete customer and all associated accounts |
| `UPDCUST` | `EXEC CICS LINK … SYNCONRETURN` | Update customer name and/or address |
| `ABNDPROC` | `EXEC CICS LINK … COMMAREA(ABNDINFO-REC)` | Abend handler — logs and terminates on any CICS failure |

---

## 3. INQCUST — Inquire Customer

**Program ID:** `INQCUST` | **Invocation:** `EXEC CICS LINK` from `BNK1DCS` and `DELCUS`

**Purpose:** Takes a customer number as input, reads the CUSTOMER VSAM file, and returns the complete customer record to the caller. Supports three lookup modes: specific number, zero (random customer), and all-nines (last customer).

---

### 3.1 Validations

| # | Check | Logic | Result |
|---|-------|-------|--------|
| 1 | **Customer number = 0** | Generate random customer number from NCS range | Random lookup mode — `GENERATE-RANDOM-CUSTOMER` using `FUNCTION RANDOM(EIBTASKN)` |
| 2 | **Customer number = 9999999999** | Retrieve last-used customer number via `GET-LAST-CUSTOMER-VSAM` (STARTBR/READPREV/ENDBR) | Last-in-file lookup |
| 3 | **VSAM NOTFND (random mode)** | Retry up to 1000 times with `GENERATE-RANDOM-CUSTOMER-AGAIN` using unseeded `FUNCTION RANDOM` | Retry or fail code `1` after 1000 attempts |
| 4 | **VSAM NOTFND (9999999999, first attempt)** | Re-read last customer via `GET-LAST-CUSTOMER-VSAM`; set `WS-V-RETRIED = 'Y'` | Retry once only |
| 5 | **VSAM NOTFND (specific number)** | Customer does not exist at that key | `INQCUST-INQ-SUCCESS = 'N'`, fail code `1`; spaces set in name/addr |
| 6 | **VSAM SYSIDERR** | Retry loop up to 100 times, 3-second delay each | Continue or fall through to non-normal handling |
| 7 | **VSAM STARTBR failure** (in `GET-LAST-CUSTOMER-VSAM`) | Non-SYSIDERR or SYSIDERR after 100 retries | `INQCUST-INQ-SUCCESS = 'N'`, fail code `9` |
| 8 | **VSAM READPREV failure** | Same retry/fail logic | `INQCUST-INQ-SUCCESS = 'N'`, fail code `9` |
| 9 | **VSAM ENDBR failure** | Same retry/fail logic | `INQCUST-INQ-SUCCESS = 'N'`, fail code `9` |
| 10 | **Any other non-normal VSAM RESP** | Unexplained VSAM error on READ | ABEND `CVR1` via `ABNDPROC` |
| 11 | **VSAM RLS abends** (`AFCR`, `AFCS`, `AFCT`) | Storm Drain check; `SYNCPOINT ROLLBACK` | `INQCUST-INQ-SUCCESS = 'N'`, fail code `2`; graceful return |

---

### 3.2 Processing

#### Main Flow (PREMIERE section)
```
1. HANDLE ABEND LABEL(ABEND-HANDLING)
2. MOVE SORTCODE → REQUIRED-SORT-CODE
3. IF INQCUST-CUSTNO = 0 OR 9999999999:
      PERFORM READ-CUSTOMER-NCS
        (GET-LAST-CUSTOMER-VSAM → STARTBR/READPREV/ENDBR on CUSTOMER)
      Move NCS-CUST-NO-VALUE → REQUIRED-CUST-NUMBER
4. IF INQCUST-CUSTNO = 0:
      PERFORM GENERATE-RANDOM-CUSTOMER
        COMPUTE RANDOM-CUSTOMER = ((NCS-CUST-NO-VALUE - 1) * FUNCTION RANDOM(EIBTASKN)) + 1
5. PERFORM READ-CUSTOMER-VSAM UNTIL EXIT-VSAM-READ = 'Y'
6. IF INQCUST-INQ-SUCCESS = 'Y':
      Move all CUSTOMER fields → INQCUST COMMAREA:
        EYE, SCODE, CUSTNO, NAME, ADDR, DOB, CREDIT-SCORE, CS-REVIEW-DT
7. EXEC CICS RETURN (via GET-ME-OUT-OF-HERE)
```

#### READ-CUSTOMER-VSAM section
```
EXEC CICS READ FILE('CUSTOMER') RIDFLD(CUSTOMER-KY) INTO(OUTPUT-DATA)
  DFHRESP(NORMAL)   → EXIT-VSAM-READ='Y'; INQCUST-INQ-SUCCESS='Y'
  DFHRESP(SYSIDERR) → Retry up to 100 × 3-second delays; re-READ each time
  DFHRESP(NOTFND) + CUSTNO=0       → GENERATE-RANDOM-CUSTOMER-AGAIN (up to 1000 retries)
  DFHRESP(NOTFND) + CUSTNO=9s (first) → GET-LAST-CUSTOMER-VSAM; retry once; WS-V-RETRIED='Y'
  DFHRESP(NOTFND) + specific CUSTNO → EXIT='Y'; SUCCESS='N'; fail code '1'; clear name/addr
  Any other non-normal RESP         → ABEND 'CVR1' via ABNDPROC
```

#### GET-LAST-CUSTOMER-VSAM section
```
EXEC CICS STARTBR FILE('CUSTOMER') RIDFLD(HIGH-VALUES)   [SYSIDERR retry ×100]
EXEC CICS READPREV FILE('CUSTOMER') RIDFLD(CUSTOMER-KY2) [SYSIDERR retry ×100]
EXEC CICS ENDBR FILE('CUSTOMER')                         [SYSIDERR retry ×100]
Any failure at any step → INQCUST-INQ-SUCCESS='N'; fail code '9'
Success → OUTPUT-DATA contains the last customer record
```

#### ABEND-HANDLING section
```
EXEC CICS ASSIGN ABCODE(MY-ABEND-CODE)
EVALUATE MY-ABEND-CODE:
  WHEN 'AFCR' / 'AFCS' / 'AFCT'  (VSAM RLS storm-drain abends):
    → SYNCPOINT ROLLBACK
    → If ROLLBACK fails → ABEND 'HROL' via ABNDPROC
    → INQCUST-INQ-SUCCESS='N'; fail code '2'
    → EXEC CICS RETURN  (graceful — storm drain handling)
  WHEN OTHER (WS-STORM-DRAIN='N'):
    → EXEC CICS ABEND ABCODE(MY-ABEND-CODE) NODUMP
```

---

### 3.3 Files / Database / CICS Storage

| Resource | Type | Mode | Notes |
|----------|------|------|-------|
| `CUSTOMER` (VSAM KSDS) | CICS File | READ | Primary lookup by sort code + customer number composite key |
| `CUSTOMER` (VSAM KSDS) | CICS File | STARTBR + READPREV + ENDBR | Backward browse to find last/highest customer (for all-nines and NCS read) |
| `DFHCOMMAREA` (COPY INQCUST) | CICS COMMAREA | Input / Output | `INQCUST-CUSTNO` in; all customer fields + `INQCUST-INQ-SUCCESS` + `INQCUST-INQ-FAIL-CD` out |
| `SORTCODE` (COPY SORTCODE) | Local Storage | Read | Bank sort code constant |
| `OUTPUT-DATA` (COPY CUSTOMER) | Local Storage | Working buffer | Customer record returned from VSAM |
| `ABNDINFO-REC` (COPY ABNDINFO) | Working Storage | Output | Passed to `ABNDPROC` on failure |
| No DB2 tables | — | — | Purely VSAM-based |

---

### 3.4 Programs Called by INQCUST

| Program | Call Method | Purpose |
|---------|-------------|---------|
| `ABNDPROC` | `EXEC CICS LINK … COMMAREA(ABNDINFO-REC)` | Abend handler — logs VSAM error details and terminates |

---

### 3.5 INQCUST Fail Code Reference

| Fail Code | Meaning |
|-----------|---------|
| `0` | Success (default initial value) |
| `1` | Customer not found in VSAM file (or random retry limit of 1000 exhausted) |
| `2` | VSAM RLS abend — handled gracefully via storm drain; graceful return |
| `9` | VSAM browse operation failed (STARTBR / READPREV / ENDBR) |

---

## 4. DELCUS — Delete Customer

**Program ID:** `DELCUS` | **Invocation:** `EXEC CICS LINK` from `BNK1DCS`

**Purpose:** Deletes a customer and **all associated accounts**. Retrieves account list via `INQACCCU`, deletes each account via `DELACC`, then deletes the CUSTOMER VSAM record and writes a deletion audit record to the DB2 PROCTRAN table.

---

### 4.1 Validations

| # | Check | Logic | Result |
|---|-------|-------|--------|
| 1 | **Customer existence** | Links to `INQCUST`; if `INQCUST-INQ-SUCCESS = 'N'` | `COMM-DEL-SUCCESS='N'`; `COMM-DEL-FAIL-CD = INQCUST-INQ-FAIL-CD`; immediate RETURN |
| 2 | **VSAM READ failure (not NOTFND)** (in `DEL-CUST-VSAM`) | Non-normal RESP on `READ FILE('CUSTOMER') UPDATE` after SYSIDERR retries | ABEND `WPV6` via `ABNDPROC` |
| 3 | **VSAM DELETE failure** (in `DEL-CUST-VSAM`) | Non-normal RESP on `DELETE FILE('CUSTOMER')` after SYSIDERR retries | ABEND `WPV7` via `ABNDPROC` |
| 4 | **VSAM NOTFND on READ** (graceful) | Another process deleted the record between the check and this delete | Silently skip — `GO TO DCV999` (treated as success) |
| 5 | **DB2 PROCTRAN INSERT failure** | `SQLCODE ≠ 0` on `INSERT INTO PROCTRAN` | ABEND `HWPT` via `ABNDPROC` |
| 6 | **VSAM SYSIDERR (READ)** | SYSIDERR on `READ FILE('CUSTOMER') UPDATE` | Retry loop up to 100 × 3-second delays |
| 7 | **VSAM SYSIDERR (DELETE)** | SYSIDERR on `DELETE FILE('CUSTOMER')` | Retry loop up to 100 × 3-second delays |

---

### 4.2 Processing

#### Main Flow (PREMIERE section)
```
1. MOVE SORTCODE → REQUIRED-SORT-CODE, DESIRED-KEY-SORTCODE
2. MOVE COMM-CUSTNO → DESIRED-KEY-CUSTOMER
3. INITIALIZE INQCUST-COMMAREA; MOVE COMM-CUSTNO → INQCUST-CUSTNO
4. EXEC CICS LINK INQCUST
   IF INQCUST-INQ-SUCCESS = 'N' → COMM-DEL-SUCCESS='N';
                                   COMM-DEL-FAIL-CD = fail code; RETURN

5. PERFORM GET-ACCOUNTS:
   MOVE COMM-CUSTNO → CUSTOMER-NUMBER IN INQACCCU-COMMAREA
   MOVE 20 → NUMBER-OF-ACCOUNTS  (capacity limit)
   EXEC CICS LINK INQACCCU SYNCONRETURN
   (Returns array of up to 20 accounts for this customer)

6. IF NUMBER-OF-ACCOUNTS > 0:
   PERFORM DELETE-ACCOUNTS:
     PERFORM VARYING WS-INDEX FROM 1 BY 1
     UNTIL WS-INDEX > NUMBER-OF-ACCOUNTS:
       INITIALIZE DELACC-COMMAREA
       MOVE WS-APPLID → DELACC-COMM-APPLID
       MOVE COMM-ACCNO(WS-INDEX) → DELACC-COMM-ACCNO
       EXEC CICS LINK PROGRAM('DELACC  ') COMMAREA(DELACC-COMMAREA)
     END-PERFORM
   (Each DELACC call deletes one account + writes PROCTRAN account deletion record)

7. PERFORM DEL-CUST-VSAM:
   EXEC CICS READ FILE('CUSTOMER') RIDFLD(DESIRED-KEY) UPDATE TOKEN(WS-TOKEN)
     [SYSIDERR retry ×100 × 3-second delays]
   IF NOTFND → silently skip (already deleted)
   If other non-normal RESP → ABEND 'WPV6'

   Store customer details from record into WS-STOREDC-CUSTOMER and DFHCOMMAREA:
     EYE, SORTCODE, NUMBER, NAME, ADDRESS, DOB (with '/' separators inserted),
     CREDIT-SCORE, CS-REVIEW-DATE (with '/' separators inserted)

   EXEC CICS DELETE FILE('CUSTOMER') TOKEN(WS-TOKEN)
     [SYSIDERR retry ×100 × 3-second delays]
   If non-normal RESP → ABEND 'WPV7'

8. PERFORM WRITE-PROCTRAN-CUST:
   PERFORM WRITE-PROCTRAN-CUST-DB2:
     EXEC CICS ASKTIME + FORMATTIME (get date/time)
     Build HOST-PROCTRAN-ROW:
       EYECATCHER = 'PRTR'
       SORT-CODE  = WS-STOREDC-SORTCODE
       ACC-NUMBER = zeros
       DATE       = today DD.MM.YYYY
       TIME       = HHMMSS
       REF        = EIBTASKN (12 digits)
       TYPE       = 'ODC'  (Open Delete Customer)
       DESC       = sortcode(6) + custno(10) + name(14) + DOB(10)
       AMOUNT     = 0
     EXEC SQL INSERT INTO PROCTRAN (…)
     SQLCODE ≠ 0 → ABEND 'HWPT'

9. MOVE 'Y' → COMM-DEL-SUCCESS; ' ' → COMM-DEL-FAIL-CD
10. GOBACK (via GET-ME-OUT-OF-HERE)
```

---

### 4.3 Files / Database / CICS Storage

| Resource | Type | Mode | Notes |
|----------|------|------|-------|
| `CUSTOMER` (VSAM KSDS) | CICS File | READ UPDATE + DELETE | Reads with UPDATE lock (using TOKEN); then deletes. SYSIDERR retry ×100 on both operations |
| `PROCTRAN` (DB2 table) | DB2 Embedded SQL | INSERT | Audit record per customer deletion; type `ODC`; uses `EXEC SQL INCLUDE PROCDB2` |
| `DFHCOMMAREA` (COPY DELCUS) | CICS COMMAREA | Input / Output | `COMM-CUSTNO` in; `COMM-DEL-SUCCESS`, `COMM-DEL-FAIL-CD`, customer fields out |
| `INQCUST-COMMAREA` (COPY INQCUST) | Working Storage | Passed to `INQCUST` | Customer existence check |
| `INQACCCU-COMMAREA` (COPY INQACCCU) | Working Storage | Passed to `INQACCCU` | Retrieve all accounts for customer (up to 20) |
| `DELACC-COMMAREA` | Working Storage | Passed to `DELACC` | One per account; account number passed; delete result returned |
| `SORTCODE` (COPY SORTCODE) | Working Storage | Read | Bank sort code constant |
| `OUTPUT-CUST-DATA` (COPY CUSTOMER) | Working Storage | Buffer | Customer record read before deletion |
| `OUTPUT-DATA` (COPY ACCOUNT) | Working Storage | Buffer | Account record buffer |
| `ABNDINFO-REC` (COPY ABNDINFO) | Working Storage | Output | Passed to `ABNDPROC` on any failure |
| SQLCA | DB2 | Communication area | SQL return code checking |
| `WS-TOKEN` | Working Storage | VSAM TOKEN | Holds the VSAM update token between READ UPDATE and DELETE |

---

### 4.4 Programs Called by DELCUS

| Program | Call Method | Purpose |
|---------|-------------|---------|
| `INQCUST` | `EXEC CICS LINK` | Verify customer exists before deletion |
| `INQACCCU` | `EXEC CICS LINK … SYNCONRETURN` | Retrieve list of all accounts for the customer (up to 20) |
| `DELACC` | `EXEC CICS LINK` (once per account) | Delete each individual account and write its PROCTRAN record |
| `ABNDPROC` | `EXEC CICS LINK … COMMAREA(ABNDINFO-REC)` | Abend handler — logs failure and terminates |

---

### 4.5 DELCUS Fail Code Reference

| Fail Code | Set By | Meaning | Message in BNK1DCS |
|-----------|--------|---------|-------------------|
| `1` | DELCUS (from INQCUST) | Customer not found | `Sorry but that Cust no was not found. Customer NOT deleted.` |
| `2` | DELCUS | Datastore error | `Sorry but a datastore error occurred. Action NOT applied.` |
| `3` | DELCUS | Delete error | `Sorry but a delete error occurred. Customer NOT deleted.` |
| Other | DELCUS | Unknown error | `Sorry but an error occurred. Customer NOT deleted.` |

---

## 5. UPDCUST — Update Customer

**Program ID:** `UPDCUST` | **Invocation:** `EXEC CICS LINK` from `BNK1DCS`

**Purpose:** Updates a customer record in the CUSTOMER VSAM file. Only **name** and/or **address** can be changed — sort code and DOB are immutable. No PROCTRAN record is written (by design — comment in source: limited field changes do not warrant an audit record).

---

### 5.1 Validations

| # | Check | Logic | Fail Code |
|---|-------|-------|-----------|
| 1 | **Title in COMM-NAME** | UNSTRING first word; EVALUATE against: `Professor`, `Mr`, `Mrs`, `Miss`, `Ms`, `Dr`, `Drs`, `Lord`, `Sir`, `Lady`, spaces | `T` — `COMM-UPD-SUCCESS='N'`; immediate GOBACK |
| 2 | **VSAM READ failure (NOTFND)** | `EXEC CICS READ … UPDATE` returns `DFHRESP(NOTFND)` | `1` — `COMM-UPD-SUCCESS='N'`; return |
| 3 | **VSAM READ failure (other)** | Non-normal, non-NOTFND RESP on READ UPDATE | `2` — `COMM-UPD-SUCCESS='N'`; return |
| 4 | **Both COMM-NAME and COMM-ADDR empty** | Both spaces or both start with space — API guard | `4` — `COMM-UPD-SUCCESS='N'`; return (prevents corruption of backend data via API calls) |
| 5 | **VSAM REWRITE failure** | Non-normal RESP on REWRITE | `3` — `COMM-UPD-SUCCESS='N'`; return |

**Note on updatable fields:** UPDCUST applies selective update logic:
- If only `COMM-NAME` is supplied (ADDR blank) → update name only.
- If only `COMM-ADDR` is supplied (NAME blank) → update address only.
- If both are supplied → update both.
- If both are blank → reject with fail code `4`.

---

### 5.2 Processing

#### Main Flow (PREMIERE section)
```
1. MOVE SORTCODE → COMM-SCODE, DESIRED-SORT-CODE
2. Title validation:
   UNSTRING COMM-NAME DELIMITED BY SPACE INTO WS-UNSTR-TITLE
   EVALUATE WS-UNSTR-TITLE against valid titles list (incl. spaces)
   IF 'N' → COMM-UPD-SUCCESS='N'; COMM-UPD-FAIL-CD='T'; GOBACK
3. PERFORM UPDATE-CUSTOMER-VSAM
4. PERFORM GET-ME-OUT-OF-HERE (EXEC CICS RETURN)
```

#### UPDATE-CUSTOMER-VSAM section
```
MOVE COMM-CUSTNO → DESIRED-CUSTNO
EXEC CICS READ FILE('CUSTOMER') RIDFLD(DESIRED-CUST-KEY) INTO(WS-CUST-DATA) UPDATE
  NOTFND → COMM-UPD-SUCCESS='N'; COMM-UPD-FAIL-CD='1'; GO TO UCV999
  Other non-normal → COMM-UPD-SUCCESS='N'; COMM-UPD-FAIL-CD='2'; GO TO UCV999

Selective update logic:
  IF COMM-NAME blank AND COMM-ADDR blank    → FAIL-CD='4'; GO TO UCV999
  IF COMM-NAME blank AND COMM-ADDR present  → update ADDRESS only
  IF COMM-ADDR blank AND COMM-NAME present  → update NAME only
  IF both present                           → update both NAME and ADDRESS

COMPUTE WS-CUST-REC-LEN = LENGTH OF WS-CUST-DATA
EXEC CICS REWRITE FILE('CUSTOMER') FROM(WS-CUST-DATA) LENGTH(WS-CUST-REC-LEN)
  Non-normal RESP → COMM-UPD-SUCCESS='N'; COMM-UPD-FAIL-CD='3'; GO TO UCV999

On success:
  Move all CUSTOMER fields back to COMMAREA:
    COMM-EYE, COMM-SCODE, COMM-CUSTNO, COMM-NAME, COMM-ADDR,
    COMM-DOB, COMM-CREDIT-SCORE, COMM-CS-REVIEW-DATE
  MOVE 'Y' → COMM-UPD-SUCCESS
```

**Fields that CAN be updated:** `CUSTOMER-NAME`, `CUSTOMER-ADDRESS`

**Fields that CANNOT be updated:** sort code, customer number, DOB, credit score, CS review date (all read-only in the map during update mode)

---

### 5.3 Files / Database / CICS Storage

| Resource | Type | Mode | Notes |
|----------|------|------|-------|
| `CUSTOMER` (VSAM KSDS) | CICS File | READ UPDATE + REWRITE | Read with exclusive UPDATE lock; REWRITE with full record length. No SYSIDERR retry loop (unlike DELCUS) |
| `DFHCOMMAREA` (COPY UPDCUST) | CICS COMMAREA | Input / Output | All customer fields in; updated fields + `COMM-UPD-SUCCESS` + `COMM-UPD-FAIL-CD` out |
| `WS-CUST-DATA` (COPY CUSTOMER) | Local Storage | Working buffer | Customer record buffer for READ/REWRITE |
| `SORTCODE` (COPY SORTCODE) | Working Storage | Read | Bank sort code constant |
| `ABNDINFO-REC` (COPY ABNDINFO) | Working Storage | Output | Passed to `ABNDPROC` on failure |
| No DB2 tables | — | — | No PROCTRAN record written (by design for limited field updates) |

---

### 5.4 Programs Called by UPDCUST

| Program | Call Method | Purpose |
|---------|-------------|---------|
| `ABNDPROC` | `EXEC CICS LINK … COMMAREA(ABNDINFO-REC)` | Abend handler — logs and terminates on CICS failure |

---

### 5.5 UPDCUST Fail Code Reference

| Fail Code | Meaning | Message in BNK1DCS |
|-----------|---------|-------------------|
| `T` | Invalid title in COMM-NAME | *(GOBACK — mapped to generic failure by BNK1DCS)* |
| `1` | Customer not found (VSAM NOTFND) | `Sorry but that Cust no was not found. Customer NOT updated.` |
| `2` | Datastore error (other VSAM failure on READ) | `Sorry but a datastore error occurred. Customer NOT updated.` |
| `3` | REWRITE error | `Sorry but an update error occurred. Customer NOT updated.` |
| `4` | Both name and address blank (API guard) | `Sorry but an unknown error occurred. Customer NOT updated.` |

---

## 6. Cross-Component Call Chain Summary

```
BNKMENU  (OMEN)
  │
  └── Option 1 ──► RETURN TRANSID('ODCS')
                       │
                       ▼
                   BNK1DCS  (ODCS)
                       │
                       ├── EXEC CICS RECEIVE MAP 'BNK1DC' ASIS
                       │       Terminal UCTRAN switched to NOUCTRAN before RECEIVE
                       │
                       ├──[ENTER, normal]──────────────────────────────────────────┐
                       │   EDIT-DATA (custno presence + numeric)                   │
                       │   ├── EXEC CICS LINK ──► INQCUST                          │
                       │   │      EXEC CICS READ FILE('CUSTOMER')                  │
                       │   │      Returns: all customer fields                     │
                       │   └── Display on BNK1DC map                              │
                       │         MESSAGE: 'Customer lookup successful.             │
                       │                  <PF5> to Delete. <PF10> to Update.'     │
                       │                                                           │
                       ├──[PF5 — Delete]───────────────────────────────────────────┤
                       │   EDIT-DATA + VALIDATE-DATA                              │
                       │   ├── EXEC CICS LINK ──► DELCUS                          │
                       │   │      ├── LINK ──► INQCUST (verify customer)           │
                       │   │      ├── LINK ──► INQACCCU (get account list)         │
                       │   │      │      └── LINK ──► INQCUST (re-verify)          │
                       │   │      ├── LINK ──► DELACC (×N, one per account)        │
                       │   │      ├── READ UPDATE + DELETE FILE('CUSTOMER')         │
                       │   │      └── INSERT INTO PROCTRAN (type 'ODC')            │
                       │   └── Clear map fields                                   │
                       │         MESSAGE: 'Customer <n> and associated accounts   │
                       │                  were successfully deleted.'             │
                       │                                                           │
                       ├──[PF10 — Initiate Update]─────────────────────────────────┤
                       │   EDIT-DATA + VALIDATE-DATA                              │
                       │   UNPROT-CUST-DATA:                                      │
                       │     Unprotect CUSTNAM, CUSTAD1/2/3 (green + underline)   │
                       │     Protect CUSTNO (DFHBMASK)                            │
                       │     Set COMM-UPD = 'Y'                                   │
                       │         MESSAGE: 'Amend data then press <ENTER>.'        │
                       │                                                           │
                       └──[ENTER with COMM-UPD='Y' — Submit Update]───────────────┘
                           EDIT-DATA2 (title + address not all blank)
                           ├── EXEC CICS LINK ──► UPDCUST
                           │      Title re-validation (backend)
                           │      EXEC CICS READ FILE('CUSTOMER') UPDATE
                           │      Selective update: name / address / both
                           │      EXEC CICS REWRITE FILE('CUSTOMER')
                           │      Returns: updated customer fields
                           └── PROT-CUST-DATA: re-protect all fields; COMM-UPD='N'
                                 MESSAGE: 'Customer <n> was updated successfully'
```

### CICS COMMAREA Flow

```
BNKMENU   ──(RETURN TRANSID 'ODCS', no COMMAREA)──────► BNK1DCS (EIBCALEN=0 first pass)
BNK1DCS   ──(INQCUST-COMMAREA, COPY INQCUST)──────────► INQCUST ──► BNK1DCS
BNK1DCS   ──(DELCUS-COMMAREA, COPY DELCUS)────────────► DELCUS
  DELCUS  ──(INQCUST-COMMAREA)──────────────────────────► INQCUST
  DELCUS  ──(INQACCCU-COMMAREA, COPY INQACCCU)──────────► INQACCCU
  DELCUS  ──(DELACC-COMMAREA)───────────────────────────► DELACC (×N per account)
BNK1DCS   ──(UPDCUST-COMMAREA, COPY UPDCUST)──────────► UPDCUST ──► BNK1DCS
BNK1DCS   ──(WS-COMM-AREA, 266 bytes)─────────────────► ODCS (self-return, pseudo-conv loop)
```

---

## 7. Fail Code Reference

### BNK1DCS — Response Code Handling

| Fail Code | Source | Meaning | Message Displayed |
|-----------|--------|---------|------------------|
| — | INQCUST | Name and address both blank in returned data | `Sorry, but that customer number was not found.` |
| `1` | DELCUS | Customer not found | `Sorry but that Cust no was not found. Customer NOT deleted.` |
| `2` | DELCUS | Datastore error | `Sorry but a datastore error occurred. Action NOT applied.` |
| `3` | DELCUS | Delete error | `Sorry but a delete error occurred. Customer NOT deleted.` |
| Other | DELCUS | Unknown | `Sorry but an error occurred. Customer NOT deleted.` |
| `1` | UPDCUST | Customer not found | `Sorry but that Cust no was not found. Customer NOT updated.` |
| `2` | UPDCUST | Datastore error | `Sorry but a datastore error occurred. Customer NOT updated.` |
| `3` | UPDCUST | REWRITE error | `Sorry but an update error occurred. Customer NOT updated.` |
| Other | UPDCUST | Unknown | `Sorry but an unknown error occurred. Customer NOT updated.` |

### INQCUST Fail Codes

| Fail Code | Meaning |
|-----------|---------|
| `0` | Success |
| `1` | Customer not found (or random retry limit of 1000 exhausted) |
| `2` | VSAM RLS abend — handled gracefully via storm drain |
| `9` | VSAM browse failure (STARTBR / READPREV / ENDBR) |

### Abend Codes Across All Programs

| Abend Code | Program | Trigger |
|-----------|---------|---------|
| `HBNK` | BNK1DCS | Any CICS failure (RECEIVE MAP, SEND MAP, RETURN, LINK, SET TERMINAL) |
| `CVR1` | INQCUST | Unexpected non-NOTFND VSAM error on CUSTOMER READ |
| `HROL` | INQCUST | SYNCPOINT ROLLBACK failure following VSAM RLS storm-drain abend |
| `WPV6` | DELCUS | VSAM READ UPDATE failure on CUSTOMER (non-NOTFND, non-SYSIDERR) |
| `WPV7` | DELCUS | VSAM DELETE failure on CUSTOMER (non-SYSIDERR after retries) |
| `HWPT` | DELCUS | DB2 INSERT INTO PROCTRAN failure |

---

## 8. Screen Flow and Key Behaviour

```
┌─────────────────────────────────────────────────────────┐
│  BNK1DC (empty) — EIBCALEN = 0                         │
│  CUSTOMER NUMBER: _________                             │
│  [all output fields blank]                              │
└───────────────────┬─────────────────────────────────────┘
                    │ User types customer number, presses ENTER
                    ▼
┌─────────────────────────────────────────────────────────┐
│  BNK1DC (populated) — Display Mode                      │
│  CUSTOMER NUMBER: 0000001234                            │
│  Sort Code:       987654                                │
│  Customer Number: 0000001234                            │
│  Customer Name:   Dr Ulrika W Robinson                  │
│  Customer Address 65 Oak Rise, York...                  │
│  Customer D.O.B.: 16 / 04 / 1953                       │
│  Credit Score:    057                                   │
│  CS Review Date:  26 / 01 / 2021                       │
│                                                         │
│  MESSAGE: Customer lookup successful.                   │
│           <PF5> to Delete. <PF10> to Update.           │
│  F3=Exit  F12=Cancel                                   │
└──────┬──────────────────────┬──────────────────────────-┘
       │PF5 (Delete)          │PF10 (Update)
       ▼                      ▼
┌─────────────────┐  ┌────────────────────────────────────┐
│  DELCUS called  │  │  BNK1DC (Update Mode)              │
│  All accounts   │  │  CUSTNO: protected (white, no UL)  │
│  deleted first  │  │  Customer Name: GREEN + UNDERLINE  │
│  (via DELACC)   │  │  Customer Address: GREEN + UNDERLINE│
│  CUSTOMER VSAM  │  │                                    │
│  record deleted │  │  MESSAGE: Amend data then press    │
│  PROCTRAN (ODC) │  │          <ENTER>.                  │
│  written        │  └──────────────────┬─────────────────┘
│                 │                     │User edits name/addr, presses ENTER
│  Map cleared    │                     ▼
│  MESSAGE:       │         ┌───────────────────────────┐
│  'Customer xxx  │         │  UPDCUST called           │
│  and associated │         │  READ UPDATE + REWRITE    │
│  accounts were  │         │  CUSTOMER VSAM record     │
│  deleted.'      │         │  Fields re-protected      │
│                 │         │  MESSAGE: 'Customer xxx   │
└─────────────────┘         │  was updated successfully'│
                            └───────────────────────────┘
```

### Notable Design Points

| Aspect | Detail |
|--------|--------|
| Dual-purpose CUSTNO field | `CUSTNO` (row 5) is the user-input field; `CUSTNO2` (row 8) is the protected confirmed display field. DELCUS receives `CUSTNO2I` (the confirmed number), not `CUSTNOI`. |
| Mode flag | `COMM-UPD` in the 266-byte COMMAREA persists across pseudo-conversational cycles to distinguish normal Enter (display) from update-submit Enter. |
| Dynamic attribute modification | PF10 path uses `DFHBMASK`, `DFHBMFSE`, `DFHGREEN`, `DFHNEUTR`, `DFHUNDLN`, `DFHBMPRF` constants to change field attributes at runtime — no separate map required for update mode. |
| Cascade delete | DELCUS deletes accounts first (via DELACC one-by-one), then the customer record. If any delete fails mid-process, the program ABENDs to prevent partial data. The only exception is NOTFND on the customer record itself — treated as already deleted. |
| No PROCTRAN for update | UPDCUST intentionally writes no audit record. The source comment states: since only name/address can change, no PROCTRAN record is required. |
| VSAM TOKEN usage | DELCUS uses `TOKEN(WS-TOKEN)` to hold the VSAM update lock between READ UPDATE and DELETE (RLS-style locking). UPDCUST uses standard READ UPDATE without TOKEN. |
| INQCUST called twice in delete | DELCUS calls INQCUST directly (step 1), then INQACCCU calls INQCUST again internally for its own customer check — two independent calls per delete operation. |

---

*Analysis generated from source review of `BNK1DCM.bms`, `BNK1DCS.cbl`, `INQCUST.cbl`, `DELCUS.cbl`, and `UPDCUST.cbl`.*
*Screen images: `BMSUser_Opt_1_EMPTY.jpg` (display mode, no data) and `BMSUser_Opt_1_SUCCESS.jpg` (populated after successful customer lookup).*

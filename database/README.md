# BANKDB Database Setup

## Overview

This directory contains the complete database setup, schema definition, synthetic data generation, data loading, and verification components for the BANKDB application.

The database is implemented in PostgreSQL and populated with deterministic synthetic banking data generated using Python.

The complete setup workflow is:

```text
Configuration
     │
     ▼
Database Schema
     │
     ▼
Synthetic Data Generation
     │
     ▼
CSV Files
     │
     ▼
PostgreSQL Data Load
     │
     ▼
Data Verification
```

---

# Directory Structure

```text
database/
│
├── bankdb_config.yaml
├── bankdb_schema.sql
├── generate_data.py
│
├── load_data.sql
├── truncate_tables.sql
├── verify_data.sql
├── setup_bankdb.ps1
│
├── generators/
│   ├── account_generator.py
│   ├── control_generator.py
│   ├── customer_generator.py
│   ├── reason_code_generator.py
│   ├── status_history_generator.py
│   └── transaction_history_generator.py
│
├── utils/
│   ├── date_utils.py
│   ├── random_utils.py
│   └── validation.py
│
└── output/
    ├── account.csv
    ├── control.csv
    ├── customer.csv
    ├── reason_code.csv
    ├── status_history.csv
    └── transaction_history.csv
```

---

# Database Tables

The BANKDB schema contains six tables.

| Table | Description |
|---|---|
| `customer` | Customer master information |
| `account` | Customer account information |
| `transaction_history` | Financial and lifecycle transaction history |
| `status_history` | Customer and account status change history |
| `reason_code` | Valid reason codes used by status and transaction processing |
| `control` | Data generation and processing control records |

## Entity Relationships

```text
CUSTOMER
    │
    │ 1
    │
    ├──────────────< ACCOUNT
    │                   │
    │                   │ 1
    │                   │
    │                   ├──────< TRANSACTION_HISTORY
    │                   │
    │                   └──────< STATUS_HISTORY
    │
    └──────────────────────────< STATUS_HISTORY


REASON_CODE
    │
    ├──── Customer Status Reasons
    ├──── Account Status Reasons
    └──── Transaction Reasons
```

---

# Prerequisites

The following software must be installed.

## PostgreSQL

PostgreSQL must be installed and running locally.

Verify:

```bash
psql --version
```

## Python

Python is required for synthetic data generation.

Verify:

```bash
python --version
```

## Python Virtual Environment

Create and activate a virtual environment from the project root.

### Git Bash

```bash
python -m venv venv
source venv/Scripts/activate
```

### PowerShell

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Install required packages:

```bash
pip install -r database/requirements.txt
```

---

# Configuration

The main configuration file is:

```text
database/bankdb_config.yaml
```

This file controls:

- Random seed
- Bank sort code
- Customer generation volume
- Customer number ranges
- Customer status distribution
- Account generation rules
- Account type distribution
- Account status distribution
- Status reason mappings
- Transaction definitions
- Transaction type distribution
- Transaction volume
- Date ranges
- Control record generation

The generators should be configured through `bankdb_config.yaml` rather than modifying generator logic for data volume changes.

---

# Synthetic Data Generation

The main entry point is:

```text
database/generate_data.py
```

Run from the project root:

```bash
python database/generate_data.py
```

The script orchestrates:

```text
ReasonCodeGenerator
        │
        ▼
CustomerGenerator
        │
        ▼
AccountGenerator
        │
        ▼
StatusHistoryGenerator
        │
        ▼
TransactionHistoryGenerator
        │
        ▼
ControlGenerator
```

Generated CSV files are written to:

```text
database/output/
```

Expected output files:

```text
reason_code.csv
customer.csv
account.csv
status_history.csv
transaction_history.csv
control.csv
```

---

# Generator Components

## `reason_code_generator.py`

Generates reference reason codes categorized by applicability:

```text
ACCOUNT_STATUS
CUSTOMER_STATUS
TRANSACTION
```

Output:

```text
output/reason_code.csv
```

## `customer_generator.py`

Generates synthetic customer records including:

- Sort code
- Customer number
- Customer name
- Address
- Contact information
- Date of birth
- Credit score
- Customer status
- Status reason
- Lifecycle timestamps

Output:

```text
output/customer.csv
```

## `account_generator.py`

Generates customer accounts.

A customer may own multiple accounts.

Generation includes:

- Account number
- Account type
- Account status
- Balance
- Opening date
- Closing date
- Status reason

Output:

```text
output/account.csv
```

## `status_history_generator.py`

Generates historical status changes for:

```text
CUSTOMER
ACCOUNT
```

Output:

```text
output/status_history.csv
```

## `transaction_history_generator.py`

Generates synthetic transaction history linked to accounts.

Output:

```text
output/transaction_history.csv
```

## `control_generator.py`

Generates control and metadata records related to the generated dataset.

Output:

```text
output/control.csv
```

---

# Utility Components

## `date_utils.py`

Reusable date and timestamp functionality including:

- Random date generation
- Date arithmetic
- Age calculations
- Date range validation
- Timestamp generation

## `random_utils.py`

Deterministic random generation utilities including:

- Weighted selection
- Probability evaluation
- Random numeric values
- Random element selection

## `validation.py`

Shared validation logic including:

- Required values
- Date ordering
- Status and reason consistency
- Numeric ranges
- Referential integrity assumptions

---

# Database Schema Setup

The database schema is defined in:

```text
database/bankdb_schema.sql
```

The schema script creates:

- Tables
- Primary keys
- Foreign keys
- Check constraints
- Indexes
- Functions
- Triggers

Primary tables:

```text
customer
account
transaction_history
status_history
reason_code
control
```

---

# Complete Automated Setup

The recommended setup method is:

```text
database/setup_bankdb.ps1
```

The PowerShell script performs:

```text
Validate Files
      │
      ▼
Terminate Active Connections
      │
      ▼
Drop Existing Database
      │
      ▼
Create Database
      │
      ▼
Create Schema
      │
      ▼
Verify Tables
      │
      ▼
Verify Indexes
      │
      ▼
Generate CSV Data
      │
      ▼
Load CSV Data
      │
      ▼
Verify Data
```

---

# Running the Complete Setup

Run from the project root:

```text
C:\Users\Neeraj\Projects\inbox-agent
```

## Step 1: Activate the Python Virtual Environment

```powershell
.\venv\Scripts\Activate.ps1
```

## Step 2: Allow Script Execution for Current Session

If required:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

This setting applies only to the current PowerShell session.

## Step 3: Configure PostgreSQL Password

Edit:

```text
database/setup_bankdb.ps1
```

Update:

```powershell
$env:PGPASSWORD = "your_postgres_password"
```

## Step 4: Run Complete Setup

```powershell
.\database\setup_bankdb.ps1
```

---

# Manual Database Setup

## Configure PostgreSQL Environment

### Git Bash

```bash
export PGHOST=localhost
export PGPORT=5432
export PGUSER=postgres
export PGPASSWORD='your_postgres_password'
```

### PowerShell

```powershell
$env:PGHOST = "localhost"
$env:PGPORT = "5432"
$env:PGUSER = "postgres"
$env:PGPASSWORD = "your_postgres_password"
```

## Drop Existing Database

Terminate active connections:

```bash
psql -d postgres -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'bankdb'
  AND pid <> pg_backend_pid();
"
```

Drop the database:

```bash
psql -d postgres -c "DROP DATABASE IF EXISTS bankdb WITH (FORCE);"
```

## Create Database

```bash
psql -d postgres -c "CREATE DATABASE bankdb;"
```

## Create Schema

```bash
psql -d bankdb -f database/bankdb_schema.sql
```

## Verify Tables

```bash
psql -d bankdb -c "\dt"
```

Expected tables:

```text
account
control
customer
reason_code
status_history
transaction_history
```

## Verify Indexes

```bash
psql -d bankdb -c "\di"
```

---

# Data Generation

Generate synthetic CSV files:

```bash
python database/generate_data.py
```

Generated files:

```text
database/output/account.csv
database/output/control.csv
database/output/customer.csv
database/output/reason_code.csv
database/output/status_history.csv
database/output/transaction_history.csv
```

---

# Loading Data

The load script is:

```text
database/load_data.sql
```

Run:

```bash
psql -d bankdb -f database/load_data.sql
```

The data is loaded in dependency order:

```text
REASON_CODE
     │
     ▼
CUSTOMER
     │
     ▼
ACCOUNT
     │
     ├───────────────┐
     ▼               ▼
STATUS_HISTORY  TRANSACTION_HISTORY
     │
     ▼
CONTROL
```

---

# Truncating Data

The truncate script is:

```text
database/truncate_tables.sql
```

Run:

```bash
psql -d bankdb -f database/truncate_tables.sql
```

This removes table data while preserving:

- Database
- Tables
- Constraints
- Indexes
- Functions
- Triggers

Use this when regenerating and reloading synthetic data without recreating the schema.

---

# Data Verification

The verification script is:

```text
database/verify_data.sql
```

Run:

```bash
psql -d bankdb -f database/verify_data.sql
```

The verification process checks:

1. Row counts
2. Orphan account detection
3. Customer status and reason consistency
4. Account status and reason consistency
5. Closed account balance validation
6. Account closed date validation
7. Customer lifecycle event validation
8. Transaction amount rule validation

Expected result:

```text
invalid_rows
--------------
            0
```

All validation checks should return:

```text
invalid_rows = 0
```

---

# Typical Development Workflow

## Full Rebuild

Use when schema changes have been made:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\database\setup_bankdb.ps1
```

This performs:

```text
DROP DATABASE
CREATE DATABASE
CREATE SCHEMA
GENERATE DATA
LOAD DATA
VERIFY DATA
```

## Regenerate Data Only

Use when generator logic or configuration changes:

```bash
python database/generate_data.py
psql -d bankdb -f database/truncate_tables.sql
psql -d bankdb -f database/load_data.sql
psql -d bankdb -f database/verify_data.sql
```

## Verify Existing Data

```bash
psql -d bankdb -f database/verify_data.sql
```

---

# Data Dependency Order

```text
REASON_CODE
     │
     │ Reference Data
     ▼
CUSTOMER
     │
     │ Parent Entity
     ▼
ACCOUNT
     │
     ├──────────────────┐
     │                  │
     ▼                  ▼
STATUS_HISTORY    TRANSACTION_HISTORY
     │                  │
     └────────┬─────────┘
              │
              ▼
           CONTROL
```

---

# Important Files

| File | Purpose |
|---|---|
| `bankdb_config.yaml` | Central configuration for synthetic data generation |
| `bankdb_schema.sql` | Database schema, constraints, indexes, functions, and triggers |
| `generate_data.py` | Main synthetic data generation orchestrator |
| `load_data.sql` | Loads generated CSV files into PostgreSQL |
| `truncate_tables.sql` | Removes generated data from tables |
| `verify_data.sql` | Validates database integrity and business rules |
| `setup_bankdb.ps1` | Complete automated database setup |
| `generators/` | Individual table data generators |
| `utils/` | Shared generation and validation utilities |
| `output/` | Generated CSV files |

---

# Cleanup

Python bytecode cache directories can be safely removed.

### Git Bash

```bash
find database -type d -name "__pycache__" -exec rm -rf {} +
```

### PowerShell

```powershell
Get-ChildItem -Path database -Directory -Recurse -Filter "__pycache__" |
Remove-Item -Recurse -Force
```

---

# Recommended `.gitignore`

```gitignore
# Python
__pycache__/
*.py[cod]
venv/

# Generated database output
database/output/*.csv

# PostgreSQL credentials
.env
.env.*
```

Do not commit database passwords or credentials into source control.

---

# Quick Start

From the project root:

```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Allow local script execution for current session
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Run complete database setup
.\database\setup_bankdb.ps1
```

The workflow will:

```text
Create PostgreSQL database
Create tables
Create constraints
Create indexes
Create triggers
Generate synthetic data
Generate CSV files
Load CSV files
Validate data integrity
```

A successful setup ends with:

```text
############################################################
# BANKDB SETUP COMPLETED SUCCESSFULLY
############################################################
```

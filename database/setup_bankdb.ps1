# ============================================================================
# BANKDB - COMPLETE DATABASE SETUP
# ============================================================================
# Run from the project root:
#
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\database\setup_bankdb.ps1
#
# This script:
#   1. Validates required files
#   2. Drops existing bankdb
#   3. Creates a fresh bankdb
#   4. Creates schema, constraints, indexes, and triggers
#   5. Verifies tables and indexes
#   6. Generates synthetic data
#   7. Loads generated CSV files
#   8. Verifies loaded data
# ============================================================================

$ErrorActionPreference = "Stop"

# ============================================================================
# CONFIGURATION
# ============================================================================

$DatabaseName = "bankdb"

$env:PGHOST = "localhost"
$env:PGPORT = "5432"
$env:PGUSER = "postgres"

# CHANGE THIS VALUE
$env:PGPASSWORD = "neer2026"


# ============================================================================
# RESOLVE PROJECT PATHS
# ============================================================================

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DatabaseDir = $PSScriptRoot


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

function Write-Banner {
    param([string]$Message)

    Write-Host ""
    Write-Host "============================================================"
    Write-Host $Message
    Write-Host "============================================================"
}


function Invoke-ExternalCommand {
    param(
        [string]$StepName,
        [scriptblock]$Command
    )

    Write-Banner $StepName

    & $Command

    if ($LASTEXITCODE -ne 0) {
        throw "FAILED: $StepName (Exit Code: $LASTEXITCODE)"
    }
}


# ============================================================================
# START
# ============================================================================

Write-Host ""
Write-Host "############################################################"
Write-Host "# BANKDB COMPLETE SETUP"
Write-Host "############################################################"
Write-Host ""
Write-Host "Project Root : $ProjectRoot"
Write-Host "Database     : $DatabaseName"
Write-Host "PG Host      : $env:PGHOST"
Write-Host "PG Port      : $env:PGPORT"
Write-Host "PG User      : $env:PGUSER"


try {

    # ========================================================================
    # 1. VALIDATE REQUIRED FILES
    # ========================================================================

    Write-Banner "VALIDATING REQUIRED FILES"

    $RequiredFiles = @(
        "bankdb_schema.sql",
        "generate_data.py",
        "truncate_tables.sql",
        "load_data.sql",
        "verify_data.sql"
    )

    foreach ($File in $RequiredFiles) {

        $FilePath = Join-Path $DatabaseDir $File

        if (-not (Test-Path $FilePath)) {
            throw "Required file not found: $FilePath"
        }

        Write-Host "Found: $File"
    }


    # ========================================================================
    # 2. TERMINATE ACTIVE CONNECTIONS
    # ========================================================================

    Invoke-ExternalCommand "TERMINATING ACTIVE BANKDB CONNECTIONS" {

        psql -d postgres -c "
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '$DatabaseName'
              AND pid <> pg_backend_pid();
        "
    }


    # ========================================================================
    # 3. DROP DATABASE
    # ========================================================================

    Invoke-ExternalCommand "DROPPING EXISTING DATABASE" {

        psql -d postgres -c "DROP DATABASE IF EXISTS $DatabaseName WITH (FORCE);"
    }


    # ========================================================================
    # 4. CREATE DATABASE
    # ========================================================================

    Invoke-ExternalCommand "CREATING DATABASE" {

        psql -d postgres -c "CREATE DATABASE $DatabaseName;"
    }


    # ========================================================================
    # 5. CREATE SCHEMA
    # ========================================================================

    $SchemaFile = Join-Path $DatabaseDir "bankdb_schema.sql"

    Invoke-ExternalCommand "CREATING SCHEMA, CONSTRAINTS, INDEXES, AND TRIGGERS" {

        psql -d $DatabaseName -f $SchemaFile
    }


    # ========================================================================
    # 6. VERIFY TABLES
    # ========================================================================

    Invoke-ExternalCommand "VERIFYING TABLES" {

        psql -d $DatabaseName -c "\dt"
    }


    # ========================================================================
    # 7. VERIFY INDEXES
    # ========================================================================

    Invoke-ExternalCommand "VERIFYING INDEXES" {

        psql -d $DatabaseName -c "\di"
    }


    # ========================================================================
    # 8. GENERATE SYNTHETIC DATA
    # ========================================================================

    $GeneratorScript = Join-Path $DatabaseDir "generate_data.py"

    Invoke-ExternalCommand "GENERATING SYNTHETIC DATA" {

        python $GeneratorScript
    }


    # ========================================================================
    # 9. LOAD DATA
    # ========================================================================

    $LoadScript = Join-Path $DatabaseDir "load_data.sql"

    Invoke-ExternalCommand "LOADING CSV DATA" {

        psql -d $DatabaseName -f $LoadScript
    }


    # ========================================================================
    # 10. VERIFY DATA
    # ========================================================================

    $VerifyScript = Join-Path $DatabaseDir "verify_data.sql"

    Invoke-ExternalCommand "VERIFYING LOADED DATA" {

        psql -d $DatabaseName -f $VerifyScript
    }


    # ========================================================================
    # COMPLETION
    # ========================================================================

    Write-Host ""
    Write-Host "############################################################"
    Write-Host "# BANKDB SETUP COMPLETED SUCCESSFULLY"
    Write-Host "############################################################"
    Write-Host ""
    Write-Host "Database : $DatabaseName"
    Write-Host "Host     : $env:PGHOST"
    Write-Host "Port     : $env:PGPORT"
    Write-Host ""
}
catch {

    Write-Host ""
    Write-Host "############################################################"
    Write-Host "# BANKDB SETUP FAILED"
    Write-Host "############################################################"
    Write-Host ""
    Write-Host $_.Exception.Message -ForegroundColor Red

    exit 1
}

"""
BANKDB Synthetic Data Generator.

Main orchestration entry point for generating synthetic banking data.

Generation order:
1. Load and validate configuration.
2. Generate REASON_CODE reference data.
3. Generate CUSTOMER records.
4. Generate ACCOUNT records from CUSTOMER records.
5. Generate STATUS_HISTORY records from CUSTOMER and ACCOUNT states.
6. Generate Transaction_History financial and lifecycle events.
7. Generate CONTROL records after all primary datasets exist.

Expected directory structure:
database/
├── bankdb_config.yaml
├── generate_data.py
├── generators/
└── utils/
"""

import argparse
import sys
from pathlib import Path

import yaml

from generators.account_generator import AccountGenerator
from generators.control_generator import ControlGenerator
from generators.customer_generator import CustomerGenerator
from generators.transaction_history_generator import TranHistGenerator
from generators.reason_code_generator import ReasonCodeGenerator
from generators.status_history_generator import StatusHistoryGenerator


BASE_DIRECTORY = Path(__file__).resolve().parent
DEFAULT_CONFIG_FILE = BASE_DIRECTORY / "bankdb_config.yaml"


def load_configuration(config_file: Path) -> dict:
    """Load the BANKDB YAML configuration."""
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")

    with config_file.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    if not isinstance(config, dict):
        raise ValueError("Configuration file is empty or invalid.")

    return config


def validate_configuration(config: dict) -> None:
    """Validate configuration sections required by the generation pipeline."""
    required_sections = {
        "bank",
        "random",
        "customer",
        "account",
        "transactions",
        "reason_codes",
        "status_history",
        "output",
        "files",
        "generation",
    }

    missing = required_sections - set(config)
    if missing:
        raise ValueError(
            f"Configuration missing required sections: {', '.join(sorted(missing))}"
        )

    required_files = {
        "customer",
        "account",
        "control",
        "transaction_history",
        "reason_code",
        "status_history",
    }

    missing_files = required_files - set(config["files"])
    if missing_files:
        raise ValueError(
            f"Configuration missing output file definitions: "
            f"{', '.join(sorted(missing_files))}"
        )

    customer_count = config["generation"].get("customers")
    if not isinstance(customer_count, int) or customer_count <= 0:
        raise ValueError(
            "generation.customers must be a positive integer."
        )


def build_output_paths(config: dict) -> dict[str, Path]:
    """Build and create all configured output paths."""
    output_directory = Path(config["output"]["directory"])

    if not output_directory.is_absolute():
        output_directory = BASE_DIRECTORY / output_directory

    output_directory.mkdir(parents=True, exist_ok=True)

    return {
        name: output_directory / filename
        for name, filename in config["files"].items()
    }


def print_header(config_file: Path, output_paths: dict[str, Path]) -> None:
    """Print execution context."""
    print("=" * 60)
    print("BANKDB SYNTHETIC DATA GENERATOR")
    print("=" * 60)
    print(f"Configuration : {config_file}")
    print(f"Output        : {output_paths['customer'].parent}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate synthetic BANKDB datasets."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_FILE,
        help="Path to bankdb_config.yaml",
    )

    args = parser.parse_args()

    try:
        config_file = args.config.resolve()
        config = load_configuration(config_file)
        validate_configuration(config)
        output_paths = build_output_paths(config)

        print_header(config_file, output_paths)

        # ------------------------------------------------------------------
        # 1. REASON_CODE
        # Reference/master data generated directly from configuration.
        # ------------------------------------------------------------------
        reason_code_summary = ReasonCodeGenerator(config).generate_reason_codes(
            str(output_paths["reason_code"])
        )
        print(
            f"Reason Codes       : "
            f"{reason_code_summary['reason_codes_generated']}"
        )

        # ------------------------------------------------------------------
        # 2. CUSTOMER
        # Root entity for the customer/account relationship.
        # ------------------------------------------------------------------
        customer_summary = CustomerGenerator(config).generate_customers(
            config["generation"]["customers"],
            str(output_paths["customer"]),
        )
        print(
            f"Customers          : "
            f"{customer_summary['customers_generated']}"
        )

        # ------------------------------------------------------------------
        # 3. ACCOUNT
        # Generated from CUSTOMER records with lifecycle compatibility rules.
        # ------------------------------------------------------------------
        account_summary = AccountGenerator(config).generate_accounts(
            str(output_paths["customer"]),
            str(output_paths["account"]),
        )
        print(
            f"Accounts           : "
            f"{account_summary['accounts_generated']}"
        )

        # ------------------------------------------------------------------
        # 4. STATUS_HISTORY
        # Derived from final CUSTOMER and ACCOUNT states.
        # ------------------------------------------------------------------
        status_history_summary = (
            StatusHistoryGenerator(config).generate_status_history(
                str(output_paths["customer"]),
                str(output_paths["account"]),
                str(output_paths["status_history"]),
            )
        )
        print(
            f"Status History     : "
            f"{status_history_summary['history_entries_generated']}"
        )

        # ------------------------------------------------------------------
        # 5. Transaction_History
        # Includes financial transactions and customer/account lifecycle events.
        # CUSTOMER input is required for OCC/ODC generation.
        # ------------------------------------------------------------------
        transaction_history_summary = TranHistGenerator(config).generate_transactions(
            str(output_paths["account"]),
            str(output_paths["transaction_history"]),
            str(output_paths["customer"]),
        )
        print(
            f"Transactions       : "
            f"{transaction_history_summary['transactions_generated']}"
        )

        # ------------------------------------------------------------------
        # 6. CONTROL
        # Generated last so control totals reflect final CUSTOMER and ACCOUNT
        # datasets. CONTROL currently tracks entity and status counts.
        # ------------------------------------------------------------------
        control_summary = ControlGenerator(config).generate_control(
            str(output_paths["customer"]),
            str(output_paths["account"]),
            str(output_paths["control"]),
        )
        print(
            f"Control Records    : "
            f"{control_summary['control_records_generated']}"
        )

        print()
        print("=" * 60)
        print("DATA GENERATION COMPLETED SUCCESSFULLY")
        print("=" * 60)

        return 0

    except (FileNotFoundError, ValueError, KeyError, yaml.YAMLError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(
            f"UNEXPECTED ERROR: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())

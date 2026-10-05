"""
Generate ACCOUNT records aligned with BANKDB schema and lifecycle rules.
"""

import csv
from decimal import Decimal
from pathlib import Path

from utils.date_utils import DateUtils
from utils.random_utils import RandomUtils


class AccountGenerator:
    """Generate ACCOUNT records from CUSTOMER CSV data."""

    HEADER = [
        "sort_code",
        "account_number",
        "customer_number",
        "account_type",
        "interest_rate",
        "opened_date",
        "account_status",
        "status_reason",
        "status_changed_at",
        "closed_date",
        "overdraft_limit",
        "last_statement_date",
        "next_statement_date",
        "available_balance",
        "actual_balance",
        "created_at",
        "updated_at",
    ]

    REASON_OPTIONAL_STATUSES = {
        "ACTIVE",
        "DORMANT",
    }

    REQUIRED_CUSTOMER_COLUMNS = {
        "customer_number",
        "date_of_birth",
        "customer_status",
        "created_at",
    }

    def __init__(self, config: dict):
        self.config = config

        account_config = config["account"]

        self.random = RandomUtils(
            config["random"]["seed"] + 1
        )
        self.sort_code = config["bank"]["sort_code"]

        self.next_account_number = int(
            account_config["starting_account_number"]
        )
        self.minimum_accounts = int(
            account_config["minimum_per_customer"]
        )
        self.maximum_accounts = int(
            account_config["maximum_per_customer"]
        )

        self.account_types = list(
            account_config["account_types"]
        )
        self.interest_rates = account_config["interest_rates"]
        self.overdraft_limits = account_config["overdraft_limits"]
        self.balance_rules = account_config["balance_rules"]
        self.status_weights = account_config["status_weights"]
        self.reason_mapping = account_config.get(
            "status_reason_mapping",
            {},
        )

        self.lifecycle_constraints = config[
            "lifecycle_rules"
        ]["customer_status_account_constraints"]

        self._validate_configuration()

    def generate_accounts(
        self,
        customer_file: str,
        output_file: str,
    ) -> dict:
        """Generate ACCOUNT records from CUSTOMER CSV data."""

        input_path = Path(customer_file)
        output_path = Path(output_file)

        if not input_path.exists():
            raise FileNotFoundError(
                f"Customer input file not found: {input_path}"
            )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        accounts_generated = 0

        with (
            input_path.open(
                "r",
                newline="",
                encoding="utf-8",
            ) as source,
            output_path.open(
                "w",
                newline="",
                encoding="utf-8",
            ) as target,
        ):
            reader = csv.DictReader(source)
            self._validate_input_columns(reader.fieldnames)

            writer = csv.DictWriter(
                target,
                fieldnames=self.HEADER,
            )
            writer.writeheader()

            for customer in reader:
                # An empty list here is a deliberate configuration choice
                # (e.g. PENDING customers), not an error: it means this
                # customer gets zero accounts. _allowed_statuses_for_customer
                # only raises when a customer status has no lifecycle rule
                # configured at all.
                allowed_statuses = self._allowed_statuses_for_customer(
                    customer["customer_status"]
                )

                if not allowed_statuses:
                    continue

                account_count = self.random.randint(
                    self.minimum_accounts,
                    self.maximum_accounts,
                )

                for _ in range(account_count):
                    account = self._generate_account(
                        customer,
                        allowed_statuses,
                    )
                    writer.writerow(account)
                    accounts_generated += 1

        return {
            "accounts_generated": accounts_generated,
            "last_account_number": self.next_account_number - 1,
            "output_file": str(output_path),
        }

    def _generate_account(
        self,
        customer: dict,
        allowed_statuses: list[str],
    ) -> dict:
        """Generate one schema-valid ACCOUNT record."""

        account_number = str(self.next_account_number)
        self.next_account_number += 1

        account_type = self.random.choice(self.account_types)
        opened_date = self._generate_opened_date(
            customer["date_of_birth"],
            customer["created_at"],
        )

        account_status = self._choose_status(
            allowed_statuses
        )
        status_reason = self._reason_for_status(
            account_status
        )

        status_changed_at = DateUtils.random_datetime(
            opened_date,
            DateUtils.today(),
            self.random.probability,
        )

        # closed_date is derived directly from status_changed_at rather
        # than sampled independently, so a CLOSED account has exactly one
        # recorded closure moment shared with status_history and
        # transaction_history, instead of two dates that only coincide
        # by chance.
        closed_date = self._closed_date(
            account_status,
            status_changed_at,
        )

        available_balance, actual_balance = (
            self._generate_balances(
                account_type,
                account_status,
            )
        )

        last_statement_date = DateUtils.add_days(
            DateUtils.today(),
            -30,
        )
        next_statement_date = DateUtils.add_days(
            last_statement_date,
            30,
        )

        timestamp = DateUtils.now()

        return {
            "sort_code": self.sort_code,
            "account_number": account_number,
            "customer_number": customer["customer_number"],
            "account_type": account_type,
            "interest_rate": self.interest_rates[account_type],
            "opened_date": opened_date.isoformat(),
            "account_status": account_status,
            "status_reason": status_reason,
            "status_changed_at": status_changed_at.isoformat(
                sep=" "
            ),
            "closed_date": (
                closed_date.isoformat()
                if closed_date is not None
                else ""
            ),
            "overdraft_limit": self.overdraft_limits[account_type],
            "last_statement_date": last_statement_date.isoformat(),
            "next_statement_date": next_statement_date.isoformat(),
            "available_balance": available_balance,
            "actual_balance": actual_balance,
            "created_at": timestamp.isoformat(sep=" "),
            "updated_at": timestamp.isoformat(sep=" "),
        }

    def _allowed_statuses_for_customer(
        self,
        customer_status: str,
    ) -> list[str]:
        """
        Return account statuses permitted for a customer state.

        An empty list is a valid, intentional result (e.g. PENDING
        customers are allowed zero accounts) and is returned as-is.
        Only a missing lifecycle rule entirely is an error.
        """

        rule = self.lifecycle_constraints.get(
            customer_status
        )

        if rule is None:
            raise ValueError(
                f"No lifecycle rule configured for customer status "
                f"'{customer_status}'."
            )

        return list(
            rule.get(
                "allowed_account_statuses",
                [],
            )
        )

    def _choose_status(
        self,
        allowed_statuses: list[str],
    ) -> str:
        """Choose an allowed account status using configured weights."""

        weighted_statuses = {
            status: self.status_weights.get(status, 0)
            for status in allowed_statuses
        }

        if not any(weighted_statuses.values()):
            return self.random.choice(allowed_statuses)

        return self.random.weighted_choice(
            weighted_statuses
        )

    def _reason_for_status(
        self,
        account_status: str,
    ) -> str:
        """Return a mandatory reason for non-normal account statuses."""

        if account_status in self.REASON_OPTIONAL_STATUSES:
            return ""

        reasons = self.reason_mapping.get(
            account_status,
            [],
        )

        if not reasons:
            raise ValueError(
                f"Missing status_reason_mapping for account status "
                f"'{account_status}'."
            )

        return self.random.choice(reasons)

    def _generate_opened_date(
        self,
        date_of_birth: str,
        customer_created_at: str,
    ):
        """
        Generate an opening date after both the customer's 18th birthday
        and the date the customer relationship itself was created.

        Without the second floor, an account can be dated earlier than
        the customer record that owns it, since both dates were
        previously sampled independently over the same range.
        """

        date_of_birth = DateUtils.parse_date(date_of_birth)
        earliest_from_age = DateUtils.add_years(
            date_of_birth,
            18,
        )

        earliest_from_customer = DateUtils.parse_datetime(
            customer_created_at
        ).date()

        earliest_open_date = max(
            earliest_from_age,
            earliest_from_customer,
        )

        today = DateUtils.today()

        if earliest_open_date > today:
            earliest_open_date = today

        return DateUtils.random_date(
            earliest_open_date,
            today,
            self.random.probability,
        )

    def _closed_date(
        self,
        account_status: str,
        status_changed_at,
    ):
        """
        Return the closure date for CLOSED accounts.

        Derived directly from status_changed_at — the moment the account
        transitioned to CLOSED — rather than sampled independently, so
        there is exactly one recorded closure moment per account.
        """

        if account_status != "CLOSED":
            return None

        return status_changed_at.date()

    def _generate_balances(
        self,
        account_type: str,
        account_status: str,
    ) -> tuple[Decimal, Decimal]:
        """Generate balances consistent with account status and type."""

        if account_status == "CLOSED":
            zero = Decimal("0.00")
            return zero, zero

        rule = self.balance_rules[account_type]
        minimum = float(rule["minimum"])
        maximum = float(rule["maximum"])

        actual_balance = self.random.decimal(
            minimum,
            maximum,
        )

        if account_type == "CURRENT":
            hold_amount = self.random.decimal(
                0.00,
                min(1000.00, max(0.00, maximum)),
            )
            available_balance = max(
                Decimal("0.00"),
                actual_balance - hold_amount,
            )
        else:
            available_balance = actual_balance

        return available_balance, actual_balance

    def _validate_input_columns(
        self,
        fieldnames,
    ) -> None:
        """Validate required CUSTOMER CSV columns."""

        if not fieldnames:
            raise ValueError(
                "CUSTOMER CSV is empty or missing a header."
            )

        missing_columns = (
            self.REQUIRED_CUSTOMER_COLUMNS
            - set(fieldnames)
        )

        if missing_columns:
            missing = ", ".join(
                sorted(missing_columns)
            )
            raise ValueError(
                f"CUSTOMER CSV missing required columns: {missing}"
            )

    def _validate_configuration(self) -> None:
        """Validate account generation configuration."""

        if self.minimum_accounts < 1:
            raise ValueError(
                "minimum_per_customer must be at least 1."
            )

        if self.maximum_accounts < self.minimum_accounts:
            raise ValueError(
                "maximum_per_customer must be greater than or equal "
                "to minimum_per_customer."
            )

        if not self.account_types:
            raise ValueError(
                "At least one account type must be configured."
            )

        configured_statuses = set(self.status_weights)

        for account_type in self.account_types:
            if account_type not in self.interest_rates:
                raise ValueError(
                    f"Missing interest rate for account type "
                    f"'{account_type}'."
                )

            if account_type not in self.overdraft_limits:
                raise ValueError(
                    f"Missing overdraft limit for account type "
                    f"'{account_type}'."
                )

            if account_type not in self.balance_rules:
                raise ValueError(
                    f"Missing balance rule for account type "
                    f"'{account_type}'."
                )

        for customer_status, rule in (
            self.lifecycle_constraints.items()
        ):
            allowed_statuses = rule.get(
                "allowed_account_statuses",
                [],
            )

            # An empty list is a valid configuration (e.g. PENDING):
            # it means this customer status generates zero accounts.
            # There is nothing further to validate for it.
            if not allowed_statuses:
                continue

            for account_status in allowed_statuses:
                if account_status not in configured_statuses:
                    raise ValueError(
                        f"Account status '{account_status}' allowed for "
                        f"customer status '{customer_status}' is missing "
                        "from account.status_weights."
                    )

                if (
                    account_status
                    not in self.REASON_OPTIONAL_STATUSES
                    and not self.reason_mapping.get(account_status)
                ):
                    raise ValueError(
                        f"Missing status_reason_mapping for account "
                        f"status '{account_status}'."
                    )

    def reset(self) -> None:
        """Reset the account number sequence."""

        self.next_account_number = int(
            self.config["account"]["starting_account_number"]
        )

    def get_next_account_number(self) -> str:
        """Return the next account number without incrementing."""

        return str(self.next_account_number)

    def get_last_account_number(self) -> str:
        """Return the most recently generated account number."""

        return str(self.next_account_number - 1)

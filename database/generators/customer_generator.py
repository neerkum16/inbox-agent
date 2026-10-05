"""
Generate deterministic synthetic CUSTOMER records aligned with
bankdb_schema.sql and bankdb_config.yaml.
"""

import csv
from pathlib import Path

from faker import Faker

from utils.date_utils import DateUtils
from utils.random_utils import RandomUtils

class CustomerGenerator:
    """Generate deterministic synthetic CUSTOMER data."""
    
    HEADER = [
        "sort_code",
        "customer_number",
        "customer_name",
        "customer_address",
        "customer_city",
        "customer_state",
        "customer_postcode",
        "customer_email",
        "customer_phone",
        "date_of_birth",
        "credit_score",
        "credit_score_review_date",
        "customer_status",
        "status_reason",
        "status_changed_at",
        "created_at",
        "updated_at",
    ]

    # PENDING now requires a reason (KYC_INCOMPLETE): a customer cannot
    # be in an unresolved onboarding state with no explanation. Only
    # ACTIVE is a normal, self-explanatory state.
    REASON_REQUIRED_STATUSES = {
        "PENDING",
        "SUSPENDED",
        "PENDING_DELETE",
        "DELETED",
        "DECEASED",
    }
    
    REASON_OPTIONAL_STATUSES = {
        "ACTIVE",
    }

    def __init__(self, config: dict):
        self.config = config
    
        seed = config["random"]["seed"]
        customer_config = config["customer"]
    
        self.random = RandomUtils(seed)
    
        self.faker = Faker(customer_config.get("locale", "en_GB"))
        self.faker.seed_instance(seed)
    
        self.sort_code = config["bank"]["sort_code"]
        self.next_customer_number = int(
            customer_config["starting_customer_number"]
        )
    
        self.status_weights = customer_config["status_weights"]
        self.reason_mapping = customer_config.get(
            "status_reason_mapping",
            {},
        )
    
        self._validate_configuration()
    
    def generate_customers(
        self,
        customer_count: int,
        output_file: str,
    ) -> dict:
        """Generate CUSTOMER records and write them to CSV."""
    
        if customer_count <= 0:
            raise ValueError("customer_count must be greater than zero.")
    
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
    
        with output_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=self.HEADER,
            )
    
            writer.writeheader()
    
            for _ in range(customer_count):
                writer.writerow(self._generate_customer())
    
        return {
            "customers_generated": customer_count,
            "last_customer_number": self.next_customer_number - 1,
            "output_file": str(output_path),
        }
    
    def _generate_customer(self) -> dict:
        """Generate one CUSTOMER record."""
    
        customer_number = str(self.next_customer_number)
        self.next_customer_number += 1
    
        date_of_birth = DateUtils.random_date(
            DateUtils.years_ago(90),
            DateUtils.years_ago(18),
            self.random.probability,
        )
    
        minimum_created_date = DateUtils.add_years(
            date_of_birth,
            18,
        )
    
        created_date = DateUtils.random_date(
            minimum_created_date,
            DateUtils.today(),
            self.random.probability,
        )
    
        # This is the historical moment the customer relationship was
        # created. It is what gets written to created_at below, and it
        # is what downstream generators (ACCOUNT's opened_date floor,
        # Transaction_History's OCC event) key off of. It must not be
        # replaced with DateUtils.now() — doing so decouples created_at
        # from every other historically-dated field on this record and
        # lets an account appear to open before the customer relationship
        # that owns it exists.
        created_at = DateUtils.random_datetime(
            created_date,
            created_date,
            self.random.probability,
        )
    
        customer_status = self.random.weighted_choice(
            self.status_weights
        )
    
        status_reason = self._reason_for_status(
            customer_status
        )
    
        status_changed_at = DateUtils.random_datetime(
            created_date,
            DateUtils.today(),
            self.random.probability,
        )
    
        credit_score_review_date = DateUtils.random_date(
            created_date,
            DateUtils.today(),
            self.random.probability,
        )
    
        first_name = self.faker.first_name()
        last_name = self.faker.last_name()
    
        return {
            "sort_code": self.sort_code,
            "customer_number": customer_number,
            "customer_name": f"{first_name} {last_name}",
            "customer_address": self.faker.street_address(),
            "customer_city": self.faker.city(),
            "customer_state": self.faker.administrative_unit(),
            "customer_postcode": self.faker.postcode(),
            "customer_email": self._email(
                first_name,
                last_name,
                customer_number,
            ),
            "customer_phone": self.faker.phone_number(),
            "date_of_birth": date_of_birth.isoformat(),
            "credit_score": self.random.randint(300, 999),
            "credit_score_review_date": (
                credit_score_review_date.isoformat()
            ),
            "customer_status": customer_status,
            "status_reason": status_reason,
            "status_changed_at": status_changed_at.isoformat(
                sep=" "
            ),
            "created_at": created_at.isoformat(sep=" "),
            "updated_at": created_at.isoformat(sep=" "),
        }
    
    def _reason_for_status(self, status: str) -> str:
        """
        Return a valid reason for statuses requiring one.
    
        ACTIVE is the only status with no status reason. Every other
        configured status, including PENDING, must have at least one
        configured reason code.
        """
    
        if status in self.REASON_OPTIONAL_STATUSES:
            return ""
    
        reasons = self.reason_mapping.get(status, [])
    
        if status in self.REASON_REQUIRED_STATUSES:
            if not reasons:
                raise ValueError(
                    "Missing status reason mapping for "
                    f"customer status: {status}"
                )
    
            return self.random.choice(reasons)
    
        if reasons:
            return self.random.choice(reasons)
    
        return ""
    
    def _validate_configuration(self) -> None:
        """Validate customer status and reason configuration."""
    
        configured_statuses = set(self.status_weights)
    
        unknown_required_statuses = (
            self.REASON_REQUIRED_STATUSES - configured_statuses
        )
    
        if unknown_required_statuses:
            raise ValueError(
                "Required customer statuses are missing from "
                "customer.status_weights: "
                f"{', '.join(sorted(unknown_required_statuses))}"
            )
    
        for status in self.REASON_REQUIRED_STATUSES:
            reasons = self.reason_mapping.get(status, [])
    
            if not reasons:
                raise ValueError(
                    "Missing status_reason_mapping for "
                    f"customer status '{status}'"
                )
    
    @staticmethod
    def _email(
        first_name: str,
        last_name: str,
        customer_number: str,
    ) -> str:
        """Generate a deterministic synthetic email address."""
    
        local_part = (
            f"{first_name}.{last_name}.{customer_number}"
            .lower()
            .replace(" ", "")
            .replace("'", "")
        )
    
        return f"{local_part}@examplebank.com"
    
    def reset(self) -> None:
        """Reset the customer number sequence."""
    
        self.next_customer_number = int(
            self.config["customer"]["starting_customer_number"]
        )
    
    def get_next_customer_number(self) -> str:
        """Return the next customer number."""
    
        return str(self.next_customer_number)
    
    def get_last_customer_number(self) -> str:
        """Return the most recently generated customer number."""
    
        return str(self.next_customer_number - 1)

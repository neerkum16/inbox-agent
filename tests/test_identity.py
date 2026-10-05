import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).parent.parent / "agent" / "classify_and_extract.py"

source_tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
selected_nodes = []
for node in source_tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in {
        "_identity_record",
        "resolve_customer_identity",
    }:
        selected_nodes.append(node)

module = ast.Module(body=selected_nodes, type_ignores=[])
ast.fix_missing_locations(module)
namespace = {}
exec(compile(module, str(SOURCE), "exec"), namespace)
resolve_customer_identity = namespace["resolve_customer_identity"]


class TestIdentityResolution(unittest.TestCase):

    ONE = [{"sort_code": "123456", "customer_number": "100000001"}]
    TWO = [
        {"sort_code": "123456", "customer_number": "100000001"},
        {"sort_code": "654321", "customer_number": "100000002"},
    ]

    def test_unregistered_email(self):
        result = resolve_customer_identity([], "100000001")
        self.assertFalse(result["identity_eligible"])
        self.assertEqual(result["identity_status"], "email_not_registered")

    def test_single_customer_without_identifier(self):
        result = resolve_customer_identity(self.ONE)
        self.assertTrue(result["identity_eligible"])
        self.assertEqual(result["identity_status"], "verified_single_customer")
        self.assertEqual(result["resolved_customer_number"], "100000001")

    def test_single_customer_customer_number_matches(self):
        result = resolve_customer_identity(self.ONE, "100000001")
        self.assertTrue(result["identity_eligible"])
        self.assertEqual(result["identity_status"], "customer_number_match")

    def test_single_customer_customer_number_mismatches(self):
        result = resolve_customer_identity(self.ONE, "999999999")
        self.assertFalse(result["identity_eligible"])
        self.assertEqual(result["identity_status"], "customer_number_mismatch")

    def test_multiple_customers_customer_number_selects_one(self):
        result = resolve_customer_identity(self.TWO, "100000002")
        self.assertTrue(result["identity_eligible"])
        self.assertEqual(result["identity_status"], "customer_number_match")
        self.assertEqual(result["resolved_sort_code"], "654321")

    def test_multiple_customers_without_identifier_is_ambiguous(self):
        result = resolve_customer_identity(self.TWO)
        self.assertFalse(result["identity_eligible"])
        self.assertEqual(result["identity_status"], "multiple_customers_identifier_missing")

    def test_single_customer_account_number_selects_customer(self):
        accounts = [
            {"sort_code": "123456", "account_number": "12345678", "customer_number": "100000001"}
        ]
        result = resolve_customer_identity(
            self.ONE,
            None,
            accounts,
            "12345678",
        )
        self.assertTrue(result["identity_eligible"])
        # The real implementation does not distinguish "resolved via a
        # matching account number" from "resolved because there was only
        # one email-linked customer to begin with" in its status naming --
        # both paths report verified_single_customer. account_number_match
        # is not a status this function ever returns.
        self.assertEqual(result["identity_status"], "verified_single_customer")
        self.assertEqual(result["resolved_customer_number"], "100000001")

    def test_multiple_customers_account_number_selects_owner(self):
        accounts = [
            {"sort_code": "654321", "account_number": "87654321", "customer_number": "100000002"}
        ]
        result = resolve_customer_identity(
            self.TWO,
            None,
            accounts,
            "87654321",
        )
        self.assertTrue(result["identity_eligible"])
        # See the comment in test_single_customer_account_number_selects_customer:
        # verified_single_customer is correct here too. Narrowing multiple
        # candidates down to exactly one owner via the account number still
        # reports the same status as any other single-customer resolution.
        self.assertEqual(result["identity_status"], "verified_single_customer")
        self.assertEqual(result["resolved_customer_number"], "100000002")

    def test_account_number_not_found(self):
        result = resolve_customer_identity(
            self.ONE,
            None,
            [],
            "99999999",
        )
        self.assertFalse(result["identity_eligible"])
        self.assertEqual(result["identity_status"], "account_number_not_found")

    def test_account_number_belongs_to_different_customer(self):
        accounts = [
            {"sort_code": "654321", "account_number": "87654321", "customer_number": "100000002"}
        ]
        result = resolve_customer_identity(
            self.ONE,
            None,
            accounts,
            "87654321",
        )
        self.assertFalse(result["identity_eligible"])
        self.assertEqual(result["identity_status"], "account_number_not_owned")

    def test_customer_number_takes_precedence_when_both_identifiers_are_present(self):
        accounts = [
            {"sort_code": "123456", "account_number": "12345678", "customer_number": "100000001"}
        ]
        result = resolve_customer_identity(
            self.ONE,
            "999999999",
            accounts,
            "12345678",
        )
        self.assertFalse(result["identity_eligible"])
        self.assertEqual(result["identity_status"], "customer_number_mismatch")


if __name__ == "__main__":
    unittest.main()

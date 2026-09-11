import unittest
from decimal import Decimal

from pydantic import ValidationError

from app.models import InvoiceCreate


class InvoiceValidationTests(unittest.TestCase):
    def payload(self, amount="0.10"):
        return {"supplier_id": "SUP-001", "invoice_number": "TEST-1", "issue_date": "2025-01-01", "due_date": "2025-01-31",
                "lines": [{"description": "Item", "cost_center_id": "CC-100", "amount": amount}]}

    def test_decimal_is_exact(self):
        invoice = InvoiceCreate(**self.payload())
        self.assertEqual(invoice.lines[0].amount * 3, Decimal("0.30"))

    def test_invalid_amounts_are_rejected(self):
        for amount in ("0", "-1", "1.001", "NaN", "Infinity", "10000000000000000.00"):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                InvoiceCreate(**self.payload(amount))

    def test_due_before_issue_rejected(self):
        payload = self.payload()
        payload["due_date"] = "2024-12-31"
        with self.assertRaises(ValidationError):
            InvoiceCreate(**payload)

    def test_empty_invoice_rejected(self):
        payload = self.payload()
        payload["lines"] = []
        with self.assertRaises(ValidationError):
            InvoiceCreate(**payload)

    def test_cannot_inject_posted_status(self):
        payload = self.payload()
        payload["status"] = "posted"
        with self.assertRaises(ValidationError):
            InvoiceCreate(**payload)


if __name__ == "__main__":
    unittest.main()

"""Integration tests against an initialized disposable source database.

Set TEST_SOURCE_DSN to the app_writer connection for that database. Never target
an existing business database: these tests create/post/delete synthetic invoices.
"""
import os
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi import HTTPException
import psycopg
from psycopg.rows import dict_row

from app import main
from app.models import DueDateUpdate, InvoiceCreate


@unittest.skipUnless(os.getenv("TEST_SOURCE_DSN") or os.getenv("RUN_SOURCE_DB_TESTS") == "1", "Requires disposable source PostgreSQL")
class SourceDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.patch = patch.object(main, "source", self.connect)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.number = "TEST-" + uuid4().hex

    def connect(self):
        if os.getenv("TEST_SOURCE_DSN"):
            return psycopg.connect(os.environ["TEST_SOURCE_DSN"], row_factory=dict_row)
        return psycopg.connect(host="source", dbname="finance", user="app_writer",
                              password=os.environ["APP_PASSWORD"], row_factory=dict_row)

    def body(self, second_center="CC-200"):
        return InvoiceCreate(supplier_id="SUP-001", invoice_number=self.number,
            issue_date="2025-01-01", due_date="2025-01-31",
            lines=[{"description": "One", "cost_center_id": "CC-100", "amount": "60.10"},
                   {"description": "Two", "cost_center_id": second_center, "amount": "40.20"}])

    def test_failed_second_line_rolls_back_everything(self):
        with self.assertRaises(HTTPException) as error:
            main.create_invoice(self.body("MISSING"))
        self.assertEqual(error.exception.status_code, 422)
        with self.connect() as conn:
            self.assertEqual(conn.execute("SELECT count(*) AS n FROM invoice WHERE invoice_number=%s", (self.number,)).fetchone()["n"], 0)
        self.assertEqual(main.create_invoice(self.body())["status"], "draft")

    def test_posted_invoice_and_lines_protected_by_database(self):
        identity = UUID(main.create_invoice(self.body())["invoice_id"])
        main.post_invoice(identity)
        main.post_invoice(identity)
        for sql in ("UPDATE invoice SET due_date='2025-03-01' WHERE id=%s",
                    "DELETE FROM invoice WHERE id=%s",
                    "UPDATE invoice_line SET amount=1 WHERE invoice_id=%s",
                    "DELETE FROM invoice_line WHERE invoice_id=%s"):
            with self.subTest(sql=sql), self.assertRaises(psycopg.errors.CheckViolation):
                with self.connect() as conn:
                    conn.execute(sql, (identity,))

    def test_draft_update_delete_and_supplier_uniqueness(self):
        identity = UUID(main.create_invoice(self.body())["invoice_id"])
        with self.assertRaises(HTTPException) as error:
            main.create_invoice(self.body())
        self.assertEqual(error.exception.status_code, 409)
        main.update_invoice(identity, DueDateUpdate(due_date="2025-02-15"))
        with self.connect() as conn:
            row = conn.execute("SELECT due_date::text FROM invoice WHERE id=%s", (identity,)).fetchone()
            self.assertEqual(row["due_date"], "2025-02-15")
        main.delete_invoice(identity)
        with self.connect() as conn:
            self.assertEqual(conn.execute("SELECT count(*) AS n FROM invoice_line WHERE invoice_id=%s", (identity,)).fetchone()["n"], 0)

    def test_app_role_cannot_change_master_data(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.connect() as conn:
                conn.execute("UPDATE supplier SET name='Changed' WHERE id='SUP-001'")


if __name__ == "__main__":
    unittest.main()

"""End-to-end invoice assertions. Requires the running project; creates synthetic records."""
from decimal import Decimal
import json
import time
import urllib.error
from uuid import uuid4

from control import config, request, wait_for

BASE = "http://127.0.0.1:18780"


def main():
    key = config()["API_KEY"]

    def api(path, method="GET", body=None):
        return request(BASE + path, method, body, key)

    def rows():
        return api("/analytics/invoices")["invoices"]

    def find(identity):
        return next((r for r in rows() if r["invoice_id"] == identity), None)

    def expected_error(path, method, body, status):
        try:
            api(path, method, body)
        except urllib.error.HTTPError as exc:
            assert exc.code == status, (exc.code, status)
        else:
            raise AssertionError(f"Expected HTTP {status}")

    wait_for(lambda: api("/health"), "API")
    snapshot = wait_for(lambda: find("00000000-0000-0000-0000-000000000001"), "initial snapshot")
    assert Decimal(snapshot["amount"]) == Decimal("125.50")
    suffix = uuid4().hex[:12]
    body = {"supplier_id": "SUP-001", "invoice_number": f"SMOKE-{suffix}",
            "issue_date": "2025-02-01", "due_date": "2025-02-28",
            "lines": [{"description": "First line", "cost_center_id": "CC-100", "amount": "60.10"},
                      {"description": "Second line", "cost_center_id": "CC-200", "amount": "40.20"}]}
    started = time.monotonic()
    identity = api("/invoices", "POST", body)["invoice_id"]
    wait_for(lambda: (r := find(identity)) and r["line_count"] == 2 and Decimal(r["amount"]) == Decimal("100.30"), "both invoice lines")
    visibility = time.monotonic() - started
    expected_error("/invoices", "POST", body, 409)
    api(f"/invoices/{identity}", "PATCH", {"due_date": "2025-03-15"})
    wait_for(lambda: (r := find(identity)) and r["due_date"] == "2025-03-15", "due date update")
    api(f"/invoices/{identity}/post", "POST")
    wait_for(lambda: (r := find(identity)) and r["status"] == "posted" and r["line_count"] == 2, "posting")
    api(f"/invoices/{identity}/post", "POST")  # Idempotent business action.
    expected_error(f"/invoices/{identity}", "DELETE", None, 409)
    expected_error(f"/invoices/{identity}", "PATCH", {"due_date": "2025-04-01"}, 409)
    body["invoice_number"] = f"DELETE-{suffix}"
    draft = api("/invoices", "POST", body)["invoice_id"]
    wait_for(lambda: find(draft), "draft before delete")
    api(f"/invoices/{draft}", "DELETE")
    wait_for(lambda: find(draft) is None, "draft deletion")
    # A failure on the second line must roll back the header and first line.
    body["invoice_number"] = f"ATOMIC-{suffix}"
    body["lines"][1]["cost_center_id"] = "UNKNOWN"
    expected_error("/invoices", "POST", body, 422)
    body["lines"][1]["cost_center_id"] = "CC-200"
    repaired = api("/invoices", "POST", body)["invoice_id"]
    wait_for(lambda: (r := find(repaired)) and r["line_count"] == 2, "retry after rolled-back create")
    print(json.dumps({"result": "passed", "checked": ["initial snapshot", "create", "decimal total", "update", "post", "posted immutability", "delete", "atomic source rollback"],
                      "create_to_visible_seconds": round(visibility, 3), "invoice_id": identity,
                      "limits": "One smoke run; not a throughput, reconciliation, or failure-recovery guarantee."}, indent=2))


if __name__ == "__main__":
    main()

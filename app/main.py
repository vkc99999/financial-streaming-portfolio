import os
from uuid import UUID, uuid4

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from psycopg.rows import dict_row
from secrets import compare_digest

from app.models import DueDateUpdate, InvoiceCreate


def authorize(x_api_key: str = Header(default="")):
    if not compare_digest(x_api_key, os.environ["API_KEY"]):
        raise HTTPException(401, "Invalid API key")


app = FastAPI(title="Financial streaming — invoice slice", dependencies=[Depends(authorize)])


def source():
    return psycopg.connect(host="source", dbname="finance", user="app_writer",
                            password=os.environ["APP_PASSWORD"], row_factory=dict_row)


def analytics():
    return psycopg.connect(host="analytics", dbname="analytics", user="report_reader",
                            password=os.environ["READER_PASSWORD"], row_factory=dict_row)


@app.get("/health")
def health():
    with source() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok", "scope": "source API; does not certify pipeline health"}


@app.post("/invoices", status_code=201)
def create_invoice(body: InvoiceCreate):
    invoice_id = uuid4()
    try:
        with source() as conn:
            conn.execute("""INSERT INTO invoice(id,supplier_id,invoice_number,issue_date,due_date)
                         VALUES (%s,%s,%s,%s,%s)""",
                         (invoice_id, body.supplier_id, body.invoice_number, body.issue_date, body.due_date))
            for number, line in enumerate(body.lines, 1):
                conn.execute("""INSERT INTO invoice_line(id,invoice_id,line_number,description,cost_center_id,amount)
                             VALUES (%s,%s,%s,%s,%s,%s)""",
                             (uuid4(), invoice_id, number, line.description, line.cost_center_id, line.amount))
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "Supplier invoice number already exists")
    except psycopg.errors.ForeignKeyViolation:
        raise HTTPException(422, "Unknown supplier or cost center")
    return {"invoice_id": str(invoice_id), "status": "draft"}


def locked_invoice(conn, invoice_id):
    row = conn.execute("SELECT * FROM invoice WHERE id=%s FOR UPDATE", (invoice_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Invoice not found")
    return row


@app.patch("/invoices/{invoice_id}")
def update_invoice(invoice_id: UUID, body: DueDateUpdate):
    with source() as conn:
        row = locked_invoice(conn, invoice_id)
        if row["status"] != "draft":
            raise HTTPException(409, "Posted invoices cannot be edited")
        if body.due_date < row["issue_date"]:
            raise HTTPException(422, "due_date cannot precede issue_date")
        conn.execute("UPDATE invoice SET due_date=%s WHERE id=%s", (body.due_date, invoice_id))
    return {"invoice_id": str(invoice_id), "due_date": body.due_date}


@app.post("/invoices/{invoice_id}/post")
def post_invoice(invoice_id: UUID):
    with source() as conn:
        row = locked_invoice(conn, invoice_id)
        if row["status"] == "posted":
            return {"invoice_id": str(invoice_id), "status": "posted"}
        conn.execute("UPDATE invoice SET status='posted', posted_at=clock_timestamp() WHERE id=%s", (invoice_id,))
    return {"invoice_id": str(invoice_id), "status": "posted"}


@app.delete("/invoices/{invoice_id}", status_code=204)
def delete_invoice(invoice_id: UUID):
    with source() as conn:
        row = locked_invoice(conn, invoice_id)
        if row["status"] != "draft":
            raise HTTPException(409, "Posted invoices cannot be deleted")
        conn.execute("DELETE FROM invoice_line WHERE invoice_id=%s", (invoice_id,))
        conn.execute("DELETE FROM invoice WHERE id=%s", (invoice_id,))
    return Response(status_code=204)


@app.get("/analytics/invoices")
def reporting():
    with analytics() as conn:
        rows = conn.execute("""SELECT invoice_id,supplier_id,invoice_number,status,due_date,
                            count(*) AS line_count,sum(amount)::text AS amount
                            FROM invoice_line_current GROUP BY 1,2,3,4,5
                            ORDER BY invoice_number LIMIT 100""").fetchall()
    return {"consistency": "eventual; not reconciled", "invoices": rows}

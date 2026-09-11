#!/usr/bin/env bash
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=writer_pass="$WRITER_PASSWORD" --set=reader_pass="$READER_PASSWORD" <<'SQL'
CREATE ROLE analytics_writer LOGIN PASSWORD :'writer_pass';
CREATE ROLE report_reader LOGIN PASSWORD :'reader_pass';
CREATE TABLE invoice_line_current (
 line_id uuid PRIMARY KEY,
 invoice_id uuid NOT NULL,
 supplier_id text NOT NULL,
 invoice_number text NOT NULL,
 issue_date date NOT NULL,
 due_date date NOT NULL,
 status text NOT NULL,
 cost_center_id text NOT NULL,
 amount numeric(18,2) NOT NULL
);
CREATE INDEX ON invoice_line_current(invoice_id);
CREATE VIEW posted_invoice_lines AS SELECT * FROM invoice_line_current WHERE status='posted';
GRANT USAGE ON SCHEMA public TO analytics_writer,report_reader;
GRANT SELECT,INSERT,UPDATE,DELETE ON invoice_line_current TO analytics_writer;
GRANT SELECT ON invoice_line_current,posted_invoice_lines TO report_reader;
SQL

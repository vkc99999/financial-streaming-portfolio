#!/usr/bin/env bash
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=app_pass="$APP_PASSWORD" --set=cdc_pass="$CDC_PASSWORD" <<'SQL'
CREATE ROLE app_writer LOGIN PASSWORD :'app_pass';
CREATE ROLE cdc_reader LOGIN REPLICATION PASSWORD :'cdc_pass';
CREATE TABLE supplier(id text PRIMARY KEY, name text NOT NULL);
CREATE TABLE cost_center(id text PRIMARY KEY, name text NOT NULL);
INSERT INTO supplier VALUES ('SUP-001','Synthetic Office Supply'),('SUP-002','Synthetic Cloud Services');
INSERT INTO cost_center VALUES ('CC-100','Engineering'),('CC-200','Finance');
CREATE TABLE invoice (
 id uuid PRIMARY KEY,
 supplier_id text NOT NULL REFERENCES supplier(id),
 invoice_number text NOT NULL,
 issue_date date NOT NULL,
 due_date date NOT NULL CHECK (due_date >= issue_date),
 currency text NOT NULL DEFAULT 'USD' CHECK (currency='USD'),
 status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','posted')),
 posted_at timestamptz,
 UNIQUE(supplier_id,invoice_number),
 CHECK ((status='posted') = (posted_at IS NOT NULL))
);
CREATE TABLE invoice_line (
 id uuid PRIMARY KEY,
 invoice_id uuid NOT NULL REFERENCES invoice(id),
 line_number integer NOT NULL CHECK (line_number>0),
 description text NOT NULL,
 cost_center_id text NOT NULL REFERENCES cost_center(id),
 amount numeric(18,2) NOT NULL CHECK (amount>0),
 UNIQUE(invoice_id,line_number)
);
CREATE FUNCTION protect_invoice() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP <> 'INSERT' AND OLD.status='posted' THEN
  RAISE EXCEPTION 'Posted invoice is immutable' USING ERRCODE='23514';
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 IF NEW.status='posted' AND NOT EXISTS(SELECT 1 FROM invoice_line WHERE invoice_id=NEW.id) THEN
  RAISE EXCEPTION 'Cannot post an invoice without lines' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER protect_invoice BEFORE INSERT OR UPDATE OR DELETE ON invoice FOR EACH ROW EXECUTE FUNCTION protect_invoice();
CREATE FUNCTION protect_line() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE parent_id uuid; parent_status text;
BEGIN
 IF TG_OP='UPDATE' AND NEW.invoice_id IS DISTINCT FROM OLD.invoice_id THEN
  RAISE EXCEPTION 'Cannot move an invoice line' USING ERRCODE='23514';
 END IF;
 IF TG_OP='DELETE' THEN parent_id:=OLD.invoice_id; ELSE parent_id:=NEW.invoice_id; END IF;
 SELECT status INTO parent_status FROM invoice WHERE id=parent_id FOR UPDATE;
 IF parent_status='posted' THEN
  RAISE EXCEPTION 'Posted invoice lines are immutable' USING ERRCODE='23514';
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER protect_line BEFORE INSERT OR UPDATE OR DELETE ON invoice_line FOR EACH ROW EXECUTE FUNCTION protect_line();
ALTER TABLE invoice REPLICA IDENTITY FULL;
ALTER TABLE invoice_line REPLICA IDENTITY FULL;
CREATE PUBLICATION finance_publication FOR TABLE invoice,invoice_line;
GRANT USAGE ON SCHEMA public TO app_writer,cdc_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_writer,cdc_reader;
GRANT INSERT,UPDATE,DELETE ON invoice,invoice_line TO app_writer;
-- One preexisting draft provides a deterministic initial-snapshot fixture.
INSERT INTO invoice(id,supplier_id,invoice_number,issue_date,due_date)
 VALUES ('00000000-0000-0000-0000-000000000001','SUP-001','HISTORY-001','2025-01-01','2025-01-31');
INSERT INTO invoice_line VALUES ('00000000-0000-0000-0000-000000000002','00000000-0000-0000-0000-000000000001',1,'Historical fixture','CC-100',125.50);
SQL

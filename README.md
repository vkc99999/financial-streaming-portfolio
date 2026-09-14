# Financial streaming portfolio

Status: first invoice flow verified end to end on 2026-09-11; 12 validation/database tests and the streaming smoke test passed. This is a learning project, not a complete financial platform.

Goal: use a financial data pipeline to learn how to detect and investigate data problems. Keep building correct streaming analytics, and add batch quality checks, rule-versus-ML comparisons, and evidence-based AI investigation in separate steps.

New direction: [two-project roadmap](docs/portfolio-roadmap.md). Project 1 extends this repo; a healthcare referral assistant belongs in a later, separate repo. Batch checks, ML training, automatic monitoring, agent tools, and recovery approvals are planned, not implemented.

- [Requirements](requirements.md): scope, operating limits, success criteria, and test scenarios.
- [Data model](data-model.md): operational tables, analytical facts and dimensions, and financial rules.
- [Architecture options](architecture.md): three alternatives and why we chose Kafka + Flink.
- [Accepted topology](ADRs/001-local-streaming-topology.md) and [first invoice flow rules](ADRs/002-first-invoice-slice.md).
- [Runbook](RUNBOOK.md): local setup, tests, stop behavior, and limitations.
- [Streaming test evidence](evidence/2026-09-11-invoice-smoke.json), [fresh-database checks](evidence/2026-09-11-bootstrap.json), and [recorded incidents](evidence/incidents.json) for later AI investigation work.

## AI learning: stage 1

A separate [pipeline failure investigation API](docs/incident-api.md) accepts reports, calls an LLM, checks evidence quotes, and saves results in Postgres. It runs without Kafka/Flink. Local tests use mocked model responses; live model quality is not yet verified.

## What works now

Python API → source PostgreSQL → Debezium → Kafka → Flink SQL → analytics PostgreSQL.

Create invoices with lines, update draft due dates, delete drafts, and post invoices. A reporting endpoint lists current invoice totals. API validation, database transactions, and triggers protect the data. One sample invoice dated in the past tests the initial CDC snapshot.

Not implemented yet: payments/reversals, full facts and dimensions, a visual dashboard, independent reconciliation, past-data generator, performance benchmarks, full-cluster checkpoint restore, and AI tools that inspect or repair live systems. The data-model document describes planned tables, not just existing ones.

## Validation status

- All 12 tests passed in Python 3.12.10, including four real PostgreSQL tests; none skipped.
- Streaming smoke passed: initial sample data, create/update/post/delete, exact decimal totals, posted immutability, and source transaction rollback.
- One invoice reached analytics in 1.267 seconds. This is one observation, not a percentile or performance guarantee.
- Flink completed checkpoints. Crash recovery, full-cluster restore commands, independent reconciliation, replay correctness, and load tests remain unverified or unimplemented.
- Startup fixes: setup scripts are packaged in database images; SQL Client keeps Flink's startup configuration. Empty schemas were initialized without deleting volumes.
- Both database images passed fresh-storage checks in temporary containers, then those containers were removed.
- Project containers were stopped after testing; business data and checkpoint volumes remain.

Repository: [financial-streaming-portfolio](https://github.com/vkc99999/financial-streaming-portfolio) (private). Read the [runbook](RUNBOOK.md) before starting, especially its stop/resume limitation.

## How we will work

Requirements → architecture alternatives → agreed decisions and ADRs → implementation → failure tests → revisit decisions.

We use Python, SQL, and Docker Compose for the flow above, with a dashboard planned. The pinned dependency versions passed the smoke test. Stronger recovery guarantees and the dashboard tool are still to be decided; Kubernetes and a lakehouse are deferred.

Run this project only when needed. No scheduled jobs, background monitors, cloud resources, or recurring charges are configured. Start data generation, reconciliation, snapshots, and failure tests manually.

## Design choices still to review

Financial scope is agreed: one company, USD, supplier invoices, partial payments, and reversals. Tax, exchange rates, and a full general ledger are deferred.

Remaining modeling choices:
1. Historical reporting: preserve the organizational assignment effective when an invoice was posted, even if the organization changes later.
2. Snapshot facts: build these after transaction facts work. Each snapshot records a chosen observation time. Days when the project was stopped have no snapshot.

The remaining items are proposed defaults. Architecture selection and ADRs precede implementation.

## Short glossary

| Term | Meaning here |
|---|---|
| OLTP | The operational database handling individual business actions. |
| CDC | Capturing committed inserts, updates, and deletes from that database. |
| Grain | Exactly what one row represents. |
| Fact | A table containing measurable business activity or balances. |
| Dimension | Descriptive information used to group and explain facts. |
| Reconciliation | Independently checking reporting against expected source records and amounts. |
| Checkpoint | Saved processing progress used during recovery. |
| Idempotent | Repeating an operation has the same effect as applying it once. |
| SCD Type 2 | Keeping a new dated version when a tracked descriptive attribute changes. |
| Watermark | A processor's estimate of event-time progress; it is not proof that every source change reached the destination. |

## Portfolio evidence

Planned portfolio contents: setup instructions, sample data configuration, migrations, ADRs, manual tests, measured results, a short demo, and known limitations. Scale and recovery claims must link to actual runs. All data is generated for practice; this is not an SAP integration or an accounting-compliance product.

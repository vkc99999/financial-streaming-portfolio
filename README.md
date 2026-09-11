# Financial streaming portfolio

Status: first invoice flow verified end to end on 2026-09-11. Twelve validation/database tests passed, followed by the streaming smoke test. This is a learning project, not a completed financial platform.

Build a local supplier-invoice and payment system whose database changes continuously update analytics while it is running. Demonstrate correct reporting through late changes, duplicate delivery, crashes, and replay. Add AI only after the underlying results can be independently verified.

- [Requirements](requirements.md): scope, operating limits, success criteria, and test scenarios.
- [Data model](data-model.md): operational tables, analytical facts and dimensions, and financial rules.
- [Architecture options](architecture.md): three alternatives and the recommended direction for discussion.
- [Accepted topology](ADRs/001-local-streaming-topology.md) and [first-slice rules](ADRs/002-first-invoice-slice.md).
- [Runbook](RUNBOOK.md): local setup, tests, stop behavior, and limitations.
- [Streaming test evidence](evidence/2026-09-11-invoice-smoke.json), [fresh-database checks](evidence/2026-09-11-bootstrap.json), and [recorded incidents](evidence/incidents.json) for later AI investigation work.

## Current slice

Python API → source PostgreSQL → Debezium → Kafka → Flink SQL → analytics PostgreSQL.

Create an invoice with lines, update its draft due date, delete a draft, or post it. A reporting endpoint lists current analytical invoice totals. API input validation, database transaction boundaries, and database immutability triggers are included. One historical fixture exercises the initial CDC snapshot.

Not implemented yet: payments/reversals, full facts and dimensions, a visual dashboard, independent reconciliation, historical generator, performance benchmarks, full-cluster checkpoint restore, and AI. The logical data-model document describes the intended later scope, not existing tables.

## Validation status

- All 12 tests passed inside the Python 3.12.10 API image, including four real PostgreSQL integration tests; none skipped.
- Streaming smoke passed: initial history, create/update/post/delete, exact decimal totals, immutable posted invoices, and source transaction rollback.
- One new invoice appeared in analytics after 1.267 seconds. This single observation is not a performance guarantee or percentile measurement.
- Flink completed checkpoints, but crash recovery and full-cluster restart restoration are not yet tested or implemented as a lifecycle command.
- Earlier infrastructure issues are resolved sufficiently for the smoke test. Bootstrap scripts are now packaged in database images; SQL Client retains Flink's normal startup configuration. Existing empty schemas were initialized without deleting their volumes.
- Both database images also passed fresh-storage bootstrap checks in separate temporary containers; those test containers were removed afterward. Independent reconciliation, replay correctness, and load testing remain future work.
- All project containers were stopped after testing; business data and checkpoint volumes were retained.

Git is initialized locally. Nothing has been published to GitHub.

Read [the runbook](RUNBOOK.md) before starting services, especially the current stop/resume limitation.

## How we will work

Requirements → architecture alternatives → agreed decisions and ADRs → implementation → failure tests → revisit decisions.

The accepted technology direction is PostgreSQL → Debezium → Kafka → Flink → analytics PostgreSQL → dashboard. Python and SQL are the preferred implementation languages; Docker Compose is the local environment. The pinned first-slice dependency combination passed the smoke test. Stronger recovery guarantees and the dashboard tool remain future decisions. Kubernetes and a lakehouse are deferred.

This is an on-demand personal project. There are no scheduled jobs, background monitors, cloud resources, or recurring charges configured. Data generation, reconciliation, snapshots, and failure tests will be explicitly invoked.

## Design choices still to review

Financial scope is agreed: one company, USD, supplier invoices, partial payments, and reversals. Tax, exchange rates, and a full general ledger are deferred.

Remaining modeling choices:
1. Historical reporting: preserve the organizational assignment effective when an invoice was posted, even if the organization changes later.
2. Snapshot facts: build these after transaction facts work. A snapshot represents an explicit observation time; the project will not imply that daily snapshots exist for days it was stopped.

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

The eventual repository should contain runnable setup instructions, sample data configuration, migrations, ADRs, manual test commands, measured results, a short demo, and known limitations. Claims about scale and recovery must reference actual runs. Data is synthetic; this is not an SAP integration or an accounting-compliance product.

# Requirements — review draft

## Product and users

A fictional company receives supplier invoices, assigns expenses to cost centers/projects, records payments, and corrects mistakes through reversals. A finance analyst views outstanding amounts and spending assignments; a data engineer verifies delivery and recovery.

The purpose is learning streaming, data modeling, backend design, and reconciliation through a reproducible Git portfolio. Operate only when explicitly started. No scheduling, hosted deployment, or AI is included in the first implementation.

## Source and financial scope

- Generate synthetic suppliers, organizational master data, invoices, lines, payments, and allocations with a repeatable random seed.
- Bulk-load a valid historical dataset, then produce ongoing actions through application rules. Historical data and ongoing actions must obey the same financial invariants.
- Source PostgreSQL represents the business application's database; it is not simply a Kafka event generator. CDC must capture actual committed database changes.
- Agreed first scope: one company, USD, and supplier payables, including partial payments and reversals. Tax, foreign exchange, accounting-period close, credit notes, and a complete debit/credit ledger are deferred.
- Insert new business records, update drafts and permitted master-data fields, and delete eligible drafts. Posted financial activity is immutable; corrections use linked reversals and, where appropriate, replacement records.
- Synthetic history does not reconstruct a genuine corporate audit trail. Any generated historical lifecycle events must be explicitly identified as generated.

## Functional requirements

1. Capture the initial source contents and subsequent committed changes, including changes made while the initial copy runs.
2. Maintain analytics for posted invoices, payment allocations, reversals, and organizational dimensions.
3. Handle missing or late references explicitly: preserve the affected record, show its unresolved status, and resolve it when the necessary information arrives. Never silently discard it.
4. Preserve event identifiers and source ordering metadata needed to reject duplicates or stale updates.
5. Provide dashboards for outstanding/overdue invoices, invoiced amounts by cost center/project, payment activity, unresolved records, processing delay, and reconciliation results.
6. Expose manual commands for loading history, starting/stopping activity, invoking reconciliation, creating snapshot observations, injecting failures, and inspecting results.
7. Support reproducible recovery experiments, including interruption during writes and restarting after duplicate delivery.
8. Preserve rejected records with a reason and a controlled route for reprocessing after correction.

## Modeling requirements

Use normalized operational tables and a star-style analytical model. Teach transaction, periodic snapshot, and accumulating snapshot facts; shared dimensions; current-value and historical dimension updates; and a many-to-many allocation bridge. Introduce each only when its business question and row grain are clear. This is not a claim to cover every modeling technique.

## Reconciliation, on demand

Two manually selected modes: incremental checks of changed keys (including deletes) and full checks of the scoped dataset. Neither is scheduled.

For a full check:

1. Stop the generator and prevent new application writes; let in-flight transactions finish. All permitted writers must respect this pause.
2. Establish an identifiable committed source boundary and wait for all relevant analytics processing through that boundary, including dependent-table resolution.
3. Obtain an independent source view and compare expected results to analytics. The exact boundary and completion protocol is an architecture decision; an empty Kafka queue alone is insufficient.
4. Compare keys, critical field values, per-record amounts, and totals. Counts alone cannot prove correctness. Match scope, currency, reversal rules, and historical mapping semantics on both sides.
5. Record coverage, discrepancies, duration, and the compared boundary. Mark a timed-out or incomplete check as inconclusive, never passed.
6. Resume writes on ordinary success/failure; provide an explicit recovery command if the controller itself crashes. A cleanup handler alone cannot handle every process failure.

Source scans will be bounded and rate-limited. Pausing the controlled writers avoids holding broad database locks while waiting for the pipeline. A read-only repeatable-read transaction can stabilize a database view, but does not itself align two databases.

This intentionally trades write availability for understandable correctness on one machine. Production alternatives include consistent source snapshots aligned with CDC positions, partitioned checks, replica reads with lag accounted for, and source-generated control totals. They need a separate design; adding a replica alone does not solve consistency.

## Reliability and security

- Repeated delivery or replay must not multiply financial amounts. State the actual delivery and destination-write guarantees in ADRs; do not infer them solely from Flink checkpoints.
- Configure bounded retries and surface persistent failures. Missing references, rejected events, and stale updates must be measurable.
- Define restart behavior with and without retained checkpoints/events. When required history has expired, require an explicit rebuild or resnapshot plan rather than pretending replay is possible.
- Use fixed-precision decimal amounts; never floating-point financial arithmetic.
- Use separate credentials for application writes, CDC, analytics writes, reconciliation reads, and dashboard reads. Keep secrets outside Git and expose local interfaces only as needed.
- Reconciliation results should report synthetic keys and differences without logging credentials. AI later will require separate tool authorization and data-access decisions.

## Retention and local operation

Retain Kafka change events and detailed reconciliation evidence for a proposed seven calendar days for short-term investigation. No separate lakehouse or long-term event archive initially. Source and analytics business tables persist until an explicit reset; SCD history is separate from Kafka retention. Snapshot data growth will be measured.

Retention is not a regulatory audit guarantee. Disk limits must be monitored; silently shortening replay history is unacceptable. Seven-day expiry is not guaranteed to occur while services are stopped. Preserve selected anonymized/synthetic test summaries as portfolio evidence beyond the operational retention window.

Stopping containers releases compute resources while persistent data still occupies disk. Startup must not automatically generate load or run reconciliation. No recurring jobs are configured.

## Proposed workload and success targets

| Item | First target | Later local experiment |
|---|---|---|
| Historical invoice lines | 100,000, plus associated records | 1 million, plus associated records |
| Committed row changes | 20/second during an explicit run | 100/second, then bounded bursts |
| Freshness | 95% of relevant committed changes reflected in analytics within 5 seconds in steady state | Measure under load and during recovery |
| Correctness | No unexplained differences after completed full reconciliation | Same criterion after injected failures |
| Recovery | Measure detection, catch-up time, and correctness | Set a justified recovery target after baseline measurements |

These are proposed targets, not measured capabilities. One business action can change multiple rows. Measure commit-to-analytics delay separately from historical business timestamps and dashboard refresh delay. Record machine resources, versions, run duration, and data seed for every benchmark.

## Meaningful acceptance scenarios

| Scenario | Expected evidence |
|---|---|
| Initial load plus ongoing actions | Final reconciled records and amounts match the source. |
| Draft update/delete | Analytics eligibility and lifecycle results reflect the final source state. |
| Partial payment and reversal | Outstanding amount changes correctly and is not double-counted. |
| Duplicate delivery and restart | Financial results remain identical after catch-up. |
| Late dimension/reference | A visible unresolved record later resolves without loss. |
| Cost-center historical change | Historical facts retain the agreed effective assignment. |
| Destination unavailable | Failure is visible; bounded recovery catches up without incorrect totals. |
| Reconciliation mismatch | Missing records and equal-count-but-wrong-value cases are detected. |
| Reconciliation timeout | Check is inconclusive and normal writers can resume safely. |
| Project split across multiple rows | Allocated totals conserve the original invoice line amount. |

## Implementation sequence after design agreement

Operational model and generator → basic CDC with transaction facts → destination correctness and failure tests → manual reconciliation and dashboards → historical dimensions and additional fact patterns → load experiments → AI-assisted investigation/repair.

Architecture alternatives and ADRs precede implementation. No cloud deployment, Kubernetes, or code-generating repair agent is authorized by this draft.

# Requirements — review draft

This document covers the original financial workload. The [expanded project requirements](docs/portfolio-roadmap.md) add batch data-quality detection, ML comparisons, and investigation workflows. Earlier exclusions of AI/lakehouse work describe the initial streaming slice; later additions need separate decisions. Local, on-demand operation remains the default.

## Product and users

A fictional company records supplier invoices, cost center/project expenses, payments, and reversals. Finance analysts view outstanding amounts and spending assignments; data engineers verify delivery and recovery.

Learn streaming, data modeling, backend design, and reconciliation in a Git portfolio others can run. Start it manually; scheduling, hosting, and AI are outside the first implementation.

## Source and financial scope

- Generate realistic sample suppliers, organizational master data, invoices, lines, payments, and allocations. Use a fixed random seed: a number that makes the generator produce the same data when rerun with the same code and settings.
- Bulk-load sample records dated in the past, then generate new business actions. Both must follow the same financial rules.
- PostgreSQL is the business application's source database. CDC captures its committed changes.
- Scope: one company, USD, supplier payables, partial payments, and reversals. Defer tax, foreign exchange, accounting-period close, credit notes, and a full debit/credit ledger.
- Allow inserts, draft and permitted master-data updates, and eligible draft deletes. Posted activity is immutable; correct it through linked reversals and replacements where needed.
- Generated past records are not a real company audit trail. Clearly label any generated past events, such as invoice creation or posting.

## Functional requirements

1. Capture initial source rows and later committed changes, including changes during the initial copy.
2. Maintain analytics for posted invoices, payment allocations, reversals, and organizational dimensions.
3. Keep records with missing or late references, mark them unresolved, and resolve them when the missing information arrives. Never silently discard them.
4. Preserve event identifiers and source ordering metadata needed to reject duplicates or stale updates.
5. Provide dashboards for outstanding/overdue invoices, invoiced amounts by cost center/project, payment activity, unresolved records, processing delay, and reconciliation results.
6. Provide manual commands to load past data, start/stop activity, run reconciliation, create snapshots, inject failures, and inspect results.
7. Make recovery tests repeatable, including interrupted writes and restarts after duplicate delivery.
8. Preserve rejected records with a reason and a controlled route for reprocessing after correction.

## Modeling requirements

Use normalized operational tables and a star-style analytical model. Cover transaction, periodic snapshot, and accumulating snapshot facts; shared dimensions; current-value and historical dimension updates; and a many-to-many allocation bridge. Explain each business question and row grain first. This does not cover every modeling technique.

## Reconciliation, on demand

Run either incremental checks of changed keys (including deletes) or full checks of the selected dataset. Neither is scheduled.

For a full check:

1. Stop the generator and prevent new application writes; let in-flight transactions finish. All permitted writers must respect this pause.
2. Record a committed source boundary—a known point in the database change log. Wait until analytics has processed all changes through it and resolved dependent records.
3. Read the source independently to calculate expected analytics results. The exact boundary and catch-up checks still need a design; an empty Kafka queue is not enough.
4. Compare keys, critical field values, per-record amounts, and totals. Counts alone cannot prove correctness. Use the same records, currency, reversal rules, and historical organization mappings on both sides.
5. Record what was checked, differences, duration, and the compared boundary. Mark timed-out or incomplete checks as inconclusive, never passed.
6. Resume writes after normal success/failure. Provide a recovery command if the controller crashes; cleanup code cannot handle every process failure.

Bound and rate-limit source scans. Pause writers instead of holding broad locks while the pipeline catches up. A read-only repeatable-read transaction stabilizes one database view; it does not align two databases.

Pausing writes makes correctness easier to verify on one machine. Production alternatives include consistent source snapshots aligned with CDC positions, partitioned checks, replica reads with lag accounted for, and source-generated control totals. They need a separate design; adding a replica alone does not solve consistency.

## Reliability and security

- Repeated delivery or replay must not multiply financial amounts. State the actual delivery and destination-write guarantees in ADRs; do not infer them solely from Flink checkpoints.
- Limit retries and report failures that continue. Track missing references, rejected events, and stale updates.
- Define restart behavior with and without retained checkpoints/events. When required history has expired, require an explicit rebuild or resnapshot plan instead of attempting replay without the required data.
- Use fixed-precision decimal amounts; never floating-point financial arithmetic.
- Use separate credentials for application writes, CDC, analytics writes, reconciliation reads, and dashboard reads. Keep secrets outside Git and expose local interfaces only as needed.
- Reconciliation results should report sample record IDs and differences, never credentials. AI later will require separate tool authorization and data-access decisions.

## Retention and local operation

Proposed retention: seven calendar days of Kafka events and detailed reconciliation evidence for investigation. No lakehouse or long-term event archive initially. Business tables persist until an explicit reset; SCD history is independent of Kafka retention. Measure snapshot storage growth.

Retention is not a regulatory audit guarantee. Disk limits must be monitored; silently shortening replay history is unacceptable. Seven-day expiry is not guaranteed to occur while services are stopped. Keep selected anonymized or sample-data test summaries as portfolio evidence beyond this retention period.

Stopping containers releases compute resources while persistent data still occupies disk. Startup must not automatically generate load or run reconciliation. No recurring jobs are configured.

## Proposed workload and success targets

| Item | First target | Later local experiment |
|---|---|---|
| Past invoice lines | 100,000, plus associated records | 1 million, plus associated records |
| Committed row changes | 20/second during an explicit run | 100/second, then bounded bursts |
| Freshness | 95% of relevant committed changes reflected in analytics within 5 seconds in steady state | Measure under load and during recovery |
| Correctness | No unexplained differences after completed full reconciliation | Same criterion after injected failures |
| Recovery | Measure detection, catch-up time, and correctness | Set a justified recovery target after baseline measurements |

These are targets, not measured capabilities. One action can change multiple rows. Measure commit-to-analytics delay separately from business timestamps and dashboard refresh delay. Record machine resources, versions, run duration, and random seed per benchmark.

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
| Project split across multiple rows | Allocated amounts add up to the original invoice line amount. |

## Implementation sequence after design agreement

Operational model and generator → basic CDC with transaction facts → destination correctness and failure tests → manual reconciliation and dashboards → historical dimensions and additional fact patterns → load experiments → AI-assisted investigation/repair.

Architecture alternatives and ADRs precede implementation. Cloud deployment, Kubernetes, and agents that generate repair code are outside this draft’s scope.

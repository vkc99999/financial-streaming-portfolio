# Architecture options — review draft

Status: option A accepted; see [ADR 001](ADRs/001-local-streaming-topology.md). The comparison explains why. Financial scope: one company, USD, invoices, partial payments, and reversals. Python and SQL are preferred; run everything manually when needed.

## Decision 1: how to capture and process changes

All alternatives share a Python business application, operational PostgreSQL, separate analytics PostgreSQL, a dashboard, and an independent Python/SQL reconciliation tool.

| Option | Change-processing path | Benefit | Cost / limitation | Revisit when |
|---|---|---|---|---|
| A: Kafka and Flink | Source → Debezium in Kafka Connect → Kafka → Flink → analytics | Independent event retention/replay; hands-on streaming and recovery learning | More containers, memory, connector configuration, and places where failures can occur | Resource use prevents comfortable local work or retained replay is unnecessary |
| B: Direct Flink CDC | Source → Flink CDC → Flink transformations → analytics | Fewer services while retaining database CDC and stateful processing | No independent Kafka event archive; long recovery depends on source logs, checkpoints, or a resnapshot | Independent consumers or retained raw-event replay become requirements |
| C: Python consumer | Source → Debezium in Kafka Connect → Kafka → Python consumer → analytics | Python-focused processing with a retained event stream | We must implement more state management, joins, ordering, and recovery ourselves | Complex stateful calculations justify a streaming engine |

Why A: it supports our learning goals and seven-day event retention, if the machine can run it comfortably. B needs fewer services. C needs more custom code for correct processing; it is not automatically easier.

The direct PostgreSQL source is documented in [Flink CDC 3.5](https://nightlies.apache.org/flink/flink-cdc-docs-release-3.5/docs/connectors/flink-sources/postgres-cdc/). The separate capture path is documented in [Debezium's PostgreSQL connector](https://debezium.io/documentation/reference/stable/connectors/postgresql.html). These references describe capabilities, not a tested version combination. Check compatibility before pinning or changing images.

## How option A works (including planned features)

```text
Past-data generator / new-action generator
                         |
             Python business rules / API
                         |
              Source PostgreSQL
                         |
           Debezium in Kafka Connect
                         |
                       Kafka
                         |
               Flink SQL / PyFlink
                         |
              Analytics PostgreSQL
                         |
                     Dashboard

Manual reconciliation reads source and analytics
after pausing writers and proving catch-up.
```

Past sample data may be bulk-loaded using the same business rules; new actions use the API. SAP is not required.

| Connection | What crosses it | Purpose |
|---|---|---|
| Generator → API | Business requests over HTTP | Create invoices, record payments, update drafts, and reverse posted activity |
| API → source | SQL inside database transactions | Commit related rows together |
| Source → Debezium | Initial table contents, then committed changes decoded from PostgreSQL's write-ahead log | Capture committed data, not just API requests |
| Debezium → Kafka | Change records and identifiers | Retain data independently of the processor |
| Kafka → Flink | Change records read by topic/partition position | Validate, join, and transform into analytical records |
| Flink → analytics | Keyed inserts/updates/deletes through the database connector | Keep reporting tables updated |
| Dashboard → analytics | Read-only SQL | Display amounts, balances, freshness, and reconciliation status |

Kafka Connect runs Debezium. A Kafka partition is an ordered section of a topic; this does not guarantee order across tables. Flink SQL continuously processes changing tables.

## Correctness decisions still needed

1. **Business transactions versus streaming arrivals.** Related source rows can arrive at different times. A source transaction is atomic, but its analytics updates may appear separately. Mark incomplete results as provisional until related records arrive.
2. **Correct repeated writes.** Use stable fact identities and keyed replacement writes, instead of repeatedly adding amounts to a balance. Keyed writes alone do not prevent stale changes from overwriting newer state; ordering and recovery must also be specified. [Flink JDBC connector behavior](https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/connectors/table/jdbc/) documents upsert behavior when primary keys are supplied.
3. **Saved progress versus committed destination data.** A checkpoint saves processor state. Recovery guarantees also depend on destination writes. Document the guarantee and test crashes between these steps before claiming correctness.
4. **Reconciliation boundaries.** Pausing all controlled writers is agreed. We still need proof that every relevant destination has processed the source boundary; a marker observed on one partition is insufficient.
5. **Initial history and restart.** An initial snapshot copies existing rows, not all their past changes. Past business activity must be stored as source records to be available. Restarting with expired events or missing checkpoints requires a defined recovery procedure.

## Local cost and security

Use Docker Compose, persistent volumes, and manual commands. No Kubernetes, cloud resources, lakehouse, AI model calls, or scheduled operations initially. Start with one Kafka broker. There is no backup machine if this one fails. Parallel workers share its CPU and disk.

Keep internal services on the container network and credentials outside Git. Dashboard access is read-only; the application cannot write analytics. Give CDC only required capture permissions, which differ from ordinary SELECT access. Current authentication and exposed ports are documented in the [runbook](RUNBOOK.md); record future deployment changes in an ADR.

Choose a dashboard tool after defining reporting queries. Start with SQL views over validated facts; add materialized summaries only if measured query performance justifies maintaining them.

## Decisions and ADR sequence

Option A is selected. Review and record each decision before implementing it:

1. Capture/processing topology and local deployment.
2. Analytical identities, joins, dimension history, and destination-write guarantees.
3. Manual reconciliation boundary, recovery, and retained-history limits.
4. Dashboard access and reporting consistency.

ADRs will state the problem, alternatives, accepted decision, consequences, validation plan, and when to reconsider it. No architecture ADR is marked accepted merely because an option is recommended here.

# Architecture options — review draft

Status: option A accepted; see [ADR 001](ADRs/001-local-streaming-topology.md). The comparison is retained to explain the decision. Financial scope: one company, USD, invoices, partial payments, and reversals. Python and SQL are preferred; operation is entirely on demand.

## Decision 1: how to capture and process changes

All alternatives share a Python business application, operational PostgreSQL, separate analytics PostgreSQL, a dashboard, and an independent Python/SQL reconciliation tool.

| Option | Change-processing path | Benefit | Cost / limitation | Revisit when |
|---|---|---|---|---|
| A: Kafka and Flink | Source → Debezium in Kafka Connect → Kafka → Flink → analytics | Independent event retention/replay; substantial streaming and recovery learning | More containers, memory, connector configuration, and failure boundaries | Resource use prevents comfortable local work or retained replay is unnecessary |
| B: Direct Flink CDC | Source → Flink CDC → Flink transformations → analytics | Fewer services while retaining database CDC and stateful processing | No independent Kafka event archive; long recovery depends on source logs, checkpoints, or a resnapshot | Independent consumers or retained raw-event replay become requirements |
| C: Python consumer | Source → Debezium in Kafka Connect → Kafka → Python consumer → analytics | Python-focused processing with a retained event stream | We must implement more state management, joins, ordering, and recovery ourselves | Complex stateful calculations justify a streaming engine |

Recommendation: A fits the learning objective and the earlier seven-day event-retention proposal best, provided the local resource baseline is comfortable. B is the lower-service-count alternative. C trades infrastructure complexity for custom application correctness work; it is not automatically easier.

The direct PostgreSQL source is documented in [Flink CDC 3.5](https://nightlies.apache.org/flink/flink-cdc-docs-release-3.5/docs/connectors/flink-sources/postgres-cdc/). The separate capture path is documented in [Debezium's PostgreSQL connector](https://debezium.io/documentation/reference/stable/connectors/postgresql.html). These references establish capabilities, not a tested combination of versions for this project. Dependency compatibility must be checked before pinning images.

## What option A would do

```text
Historical generator / ongoing action generator
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

Historical loading may use a bulk path that enforces the same business rules; ongoing actions use the API. There is no external SAP dependency.

| Connection | What crosses it | Purpose |
|---|---|---|
| Generator → API | Business requests over HTTP | Create invoices, record payments, update drafts, and reverse posted activity |
| API → source | SQL inside database transactions | Commit related rows together |
| Source → Debezium | Initial table contents, then committed changes decoded from PostgreSQL's write-ahead log | Capture persisted facts, not just attempted API requests |
| Debezium → Kafka | Change records and identifiers | Retain data independently of the processor |
| Kafka → Flink | Change records read by topic/partition position | Validate, join, and transform into analytical records |
| Flink → analytics | Keyed inserts/updates/deletes through the database connector | Maintain queryable results |
| Dashboard → analytics | Read-only SQL | Display amounts, balances, freshness, and reconciliation status |

Kafka Connect is the service that runs the Debezium connector. A Kafka partition is an ordered section of a topic; order within a partition does not establish a global order across tables. Flink SQL queries can process changing tables continuously rather than executing only once.

## Important boundaries we must design next

1. **Business transactions versus streaming arrivals.** Related source rows can reach different processing paths at different times. Do not treat source commit atomicity as proof that analytical tables become visible atomically. Define unresolved states and expose provisional reporting until dependencies are complete.
2. **Correct repeated writes.** Use stable fact identities and keyed replacement writes, avoiding operations such as repeatedly adding an amount to an existing balance. Keyed writes alone do not prevent stale changes from overwriting newer state; ordering and recovery must also be specified. [Flink JDBC connector behavior](https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/connectors/table/jdbc/) documents upsert behavior when primary keys are supplied.
3. **Saved progress versus committed destination data.** A checkpoint saves processor state. Recovery guarantees also depend on destination writes. We will document the actual guarantee and test crashes at this boundary before claiming correctness.
4. **Reconciliation boundaries.** Pausing all controlled writers is agreed. We still need proof that every relevant destination has processed the source boundary; a marker observed on one partition is insufficient.
5. **Initial history and restart.** An initial snapshot describes existing rows, not every change that previously happened. Historical business activity must exist explicitly in source records. Restarting with expired events or missing checkpoints requires a defined recovery procedure.

## Local cost and security

Use Docker Compose, persistent volumes, and manual commands. No Kubernetes, cloud resources, lakehouse, AI model calls, or scheduled operations initially. Start with one Kafka broker and explicitly document that this provides no machine-failure redundancy. Local parallel workers share the same CPU and disk; they do not establish multi-machine availability.

Keep internal services on the container network. Give the dashboard read-only analytics credentials and the application no analytics-write credentials. Restrict the CDC account to required capture permissions, which differ from ordinary SELECT access. Store credentials outside version control. Authentication and exact exposed ports will be part of the deployment ADR.

Select the dashboard tool after the reporting queries are defined. Start with ordinary SQL views over validated fact tables; reconsider materialized summaries only after query measurements justify their maintenance cost.

## Decisions and ADR sequence

Option A is selected. Review and record these bounded decisions before the corresponding implementation:

1. Capture/processing topology and local deployment.
2. Analytical identities, joins, dimension history, and destination-write guarantees.
3. Manual reconciliation boundary, recovery, and retained-history limits.
4. Dashboard access and reporting consistency.

ADRs will state the problem, alternatives, accepted decision, consequences, validation plan, and conditions for revisiting it. No architecture ADR is marked accepted merely because an option is recommended here.

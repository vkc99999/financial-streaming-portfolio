# ADR 001: Kafka and Flink on demand

Status: accepted following the user's architecture confirmation. Implementation validation is separate from acceptance.

## Problem
Learn database CDC, stream processing, modeling, and recovery using sample financial data we can generate again on one machine, without running services continuously.

## Decision
Use a Python business application, source PostgreSQL, Debezium in Kafka Connect, Kafka, Flink SQL, and a separate analytics PostgreSQL database. Use Docker Compose with persistent local volumes and no automatic container restart policy. Dashboard and reconciliation tools read analytics through separate credentials. Source checks are manual. AI, Kubernetes, a lakehouse, and cloud deployment are deferred.

## Alternatives
Direct Flink CDC needs fewer services but removes the independent Kafka replay window. A Python Kafka consumer keeps application code familiar but requires custom state and join recovery logic. See [architecture.md](../architecture.md) for the full comparison.

## Consequences
Kafka and Flink add memory and dependency-management work. One broker on one machine cannot keep running if that machine fails. Seven-day Kafka retention is short-term replay history, not a financial audit guarantee. Containers start only through explicit commands and stop after tests.

## Validation and revisit
First demonstrate source snapshot, invoice create/update/delete/post, and analytics catching up to the source. Later test restart, replay, independent reconciliation, and sustained load. Revisit direct CDC if resource overhead prevents comfortable use. Revisit deployment if running across multiple machines becomes a learning goal.

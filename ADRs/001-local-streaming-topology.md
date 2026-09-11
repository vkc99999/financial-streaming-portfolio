# ADR 001: Kafka and Flink on demand

Status: accepted following the user's architecture confirmation. Implementation validation is separate from acceptance.

## Problem
Learn database CDC, stream processing, modeling, and recovery using reproducible financial data on one machine, without running services continuously.

## Decision
Use a Python business application, source PostgreSQL, Debezium in Kafka Connect, Kafka, Flink SQL, and a separate analytics PostgreSQL database. Use Docker Compose with persistent local volumes and no automatic container restart policy. Dashboard and reconciliation tools read analytics through separate credentials. Source checks are manual. AI, Kubernetes, a lakehouse, and cloud deployment are deferred.

## Alternatives
Direct Flink CDC needs fewer services but removes the independent Kafka replay window. A Python Kafka consumer keeps application code familiar but requires custom state and join recovery logic. See architecture.md for the full comparison.

## Consequences
Kafka and Flink add memory and dependency-management work. One broker and one machine provide no host-failure redundancy. Seven-day Kafka retention is short-term replay history, not a financial audit guarantee. Containers start only through explicit commands and stop after tests.

## Validation and revisit
First demonstrate source snapshot, invoice create/update/delete/post, and analytical convergence. Later test restart, replay, independent reconciliation, and sustained load. Revisit direct CDC if resource overhead prevents comfortable use. Revisit deployment only if multi-machine operations become a concrete learning goal.

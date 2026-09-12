# ADR 002: first invoice flow and financial write rules

Status: implementation decision within the accepted architecture; limited to invoices.

## Problem
Prove a small, understandable CDC flow before implementing the entire financial model. Avoid duplicated money and unclear table grain.

## Decision
Source invoice headers and lines are normalized. An API creates both in one database transaction. Draft due dates can change and drafts can be deleted. Posting is a separate operation; a database trigger blocks later updates/deletes of posted headers and lines. USD amounts are positive fixed-precision decimals. Payment/reversal APIs are planned for later.

Flink maintains one current reporting row per invoice line through a continuous join. The destination primary key is line_id. Each row contains invoice identity, supplier identity, draft/posted status, dates, cost center, and amount. Posted rows are exposed by a view. This table shows current values. It is not the final signed invoice-activity fact or a complete audit history.

Use parallelism of 1 and stable line keys initially. JDBC keyed upserts replace values rather than increment totals. Configure Flink CDC duplicate normalization for Debezium input, complete before-images (row values before a change) in PostgreSQL, and a checkpoint interval. These reduce duplicate-delivery risk, but do not provide atomic visibility across multiple destination rows. Readers may see intermediate states during a multi-line change; only a reconciled boundary may be called verified.

## Restart and replay boundary
This version submits one named job and refuses to start another when one is active. Checkpoints persist to a shared named volume. Automatic recovery of a running job can use its checkpoint. Full cluster stop/start does not yet support automatic recovery: startup refuses to resubmit over populated analytics until a checkpoint/rebuild procedure is implemented. Never silently use Kafka group offsets as a substitute for Flink join state.

## Alternatives and consequences
Flattening source invoices would simplify streaming but hide real cross-table behavior. Implementing all facts immediately would make early failures harder to understand. An append-only money sink would double-count replays. A transactional sink may provide stronger guarantees, but is a separate design choice needing verification.

## Tests and revisit
Test source header/line atomicity, decimal validation, posted immutability, snapshot capture, draft update/delete, and posted reporting. Do not claim crash/replay safety until dedicated fault tests pass. Introduce signed activity facts, dimensions, manual reconciliation, historical loading, and recoverable restart in later steps. Revisit single parallelism after correctness tests pass.

Validation on 2026-09-11: all 12 unit/database tests and the first streaming smoke passed. See [test evidence](../evidence/2026-09-11-invoice-smoke.json) for what was measured and its limits. The next priority is a tested stop/savepoint/resume procedure so the project can be used across repeated sessions without discarding data.

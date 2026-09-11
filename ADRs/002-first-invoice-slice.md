# ADR 002: first slice and financial write rules

Status: implementation decision within the accepted architecture; limited to invoices.

## Problem
Prove a small, understandable CDC flow before implementing the entire financial model. Avoid duplicated money and unclear table grain.

## Decision
Source invoice headers and lines are normalized. An API creates both in one database transaction. Draft due dates can change and drafts can be deleted. Posting is a separate operation; a database trigger blocks later updates/deletes of posted headers and lines. USD amounts are positive fixed-precision decimals. Payment/reversal APIs are not part of this slice.

Flink maintains one current reporting row per invoice line through a continuous join. The destination primary key is line_id. Each row contains invoice identity, supplier identity, draft/posted status, dates, cost center, and amount. Posted rows are exposed by a view. This current projection is NOT the final signed invoice-activity fact and contains no claim of a complete audit history.

Use a single processing parallelism and stable line keys initially. JDBC keyed upserts replace values rather than increment totals. Configure Flink CDC duplicate normalization for Debezium input, complete before-images in PostgreSQL, and a checkpoint interval. These reduce duplicate-delivery risk, but do not provide atomic visibility across multiple destination rows. Readers may see intermediate states during a multi-line change; only a reconciled boundary may be called verified.

## Restart and replay boundary
This slice submits one named job and refuses to start another when one is active. Checkpoints persist to a shared named volume. Automatic recovery of a running job can use its checkpoint. Full cluster stop/start is deliberately NOT advertised as transparent recovery: startup refuses to resubmit over populated analytics until a checkpoint/rebuild procedure is implemented. Never silently use Kafka group offsets as a substitute for Flink join state.

## Alternatives and consequences
Flattening source invoices would simplify streaming but hide real cross-table behavior. Implementing all facts immediately would obscure initial failures. An append-only money sink would double-count replays. A transactional sink may provide stronger guarantees, but is a separate design choice needing verification.

## Tests and revisit
Test source header/line atomicity, decimal validation, posted immutability, snapshot capture, draft update/delete, and posted reporting. Do not claim crash/replay safety until dedicated fault tests pass. Introduce signed activity facts, dimensions, manual reconciliation, historical loading, and recoverable restart in later slices. Revisit single parallelism after those correctness tests pass.

Validation on 2026-09-11: all 12 unit/database tests and the first streaming smoke passed. See ../evidence/2026-09-11-invoice-smoke.json for measured scope and limitations. The next lifecycle priority is a tested stop/savepoint/resume procedure so the project can be used across repeated sessions without discarding data.

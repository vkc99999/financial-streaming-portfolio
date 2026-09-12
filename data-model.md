# Data model — review draft

Grain means exactly what one row represents. These are planned logical models, not final SQL migrations. ADRs will define keys, change ordering, and stream joins.

## Operational model: preserve valid business transactions

| Table | Grain | Main relationships / rules |
|---|---|---|
| supplier | One supplier | Stable ID, name, active status. |
| cost_center | One cost center | Stable ID; descriptive fields and profit-center assignment. |
| profit_center | One profit center | Stable ID and description; groups cost centers for reporting. |
| project | One project/WBS element | Stable ID; optional parent project and active dates. |
| org_assignment_history | One cost-center assignment for a date range | Links a cost center to a profit center with non-overlapping effective dates. Needed for independent historical reconciliation. |
| invoice | One supplier invoice | Supplier, invoice number, status, issue/due/posting dates, currency. Unique supplier invoice identity. |
| invoice_line | One line of an invoice | Invoice, line number, description, amount, cost center. Unique invoice + line number. |
| line_project_allocation | One invoice-line allocation to a project | Stores allocated amount; allows multiple projects per line without duplicating the line's full amount. |
| payment | One outgoing supplier payment | Supplier, amount, currency, paid time, status. |
| payment_allocation | One assignment of payment amount to an invoice | Supports partial payments and one payment covering multiple invoices. |
| invoice_reversal | One full reversal of a posted invoice | Original invoice reference, reason, effective time; first scope allows at most one full reversal. |
| payment_reversal | One full reversal of a posted payment | Original payment reference, reason, effective time; first scope allows at most one full reversal. |

Proposed restrictions: no cross-supplier or cross-currency payment allocations; no overpayments in the first scope; no invoice reversal while active payments remain allocated to it. Reverse affected payments first. Once posted, a payment's allocations are fixed. Supporting partial reversals, unapplied cash, and reallocation later would require extending this model.

Application transactions and database constraints jointly enforce these rules. Deletion is limited to drafts and their eligible children, not referenced master data or posted financial activity.

## Analytical facts

| Table / pattern | Grain | Measures and business question |
|---|---|---|
| fact_invoice_line_activity — transaction fact | One original posting or reversal activity for one invoice line | Signed invoiced amount; what was invoiced by supplier/cost center/project? |
| fact_payment_activity — transaction fact | One payment posting or reversal activity | Signed payment amount; how much supplier cash-payment activity occurred? |
| fact_payment_allocation_activity — transaction fact | One posting or reversal activity for one payment allocation | Signed allocated amount; how much of an invoice has been paid? |
| fact_invoice_balance_snapshot — periodic snapshot | One posted invoice at one explicit daily observation cutoff | Outstanding amount and overdue amount; how did balances change across observed days? |
| fact_invoice_lifecycle — accumulating snapshot | One invoice | Creation, approval, posting, first-payment, and current full-settlement milestones; how long does processing take? |

These facts describe the same activity from different views; do not add their amounts together. Separate payment facts avoid counting a payment multiple times when it is split across invoices. Invoice IDs carried directly on facts are a degenerate dimension: a business identifier without a separate descriptive dimension table.

Each reversal has a stable ID and links to the original activity. Reprocessing must reuse that ID, never create another posting. Lifecycle facts can change again after a reversal; they do not replace the underlying activity history.

Create snapshots manually. A missed day has no snapshot unless enough business history exists to rebuild it. Never use today's balance for past dates. Backfilling snapshots and earlier lifecycle changes needs a later design.

## Dimensions and bridge

| Object | Pattern | Intended behavior |
|---|---|---|
| dim_supplier | Type 1 | Correct descriptive spelling in place; stable source supplier ID. |
| dim_cost_center | Type 2 | New dimension version for a tracked organizational assignment change. |
| dim_profit_center | Initially Type 1 | Current descriptive labels for the stable profit-center identity. |
| dim_project | Initially Type 1 | Project/WBS description and hierarchy; historical hierarchy changes deferred. |
| dim_date | Shared date dimension | Calendar fields reused for invoice, payment, due, and observation dates. |
| bridge_line_project | Allocation bridge | One project allocation per invoice-line activity, with signed allocated amount. |

Dimension version keys are distinct from stable source business IDs. Type 2 versions carry effective-from/effective-to dates; intervals must not overlap for a given business ID. Facts use the version effective at posting time, not whichever dimension row arrived most recently.

Late or retroactive changes need an explicit restatement policy. Proposed first behavior: resolve previously unknown mappings when the source provides the required history; flag retroactive changes affecting already-resolved facts for controlled reprocessing. Do not silently apply today's organization to all history.

## Example: why grain matters

Invoice I1 contains two lines: $60 and $40. Payment P1 allocates $30 to I1; P2 allocates another $20.

- Net invoiced amount: $100.
- Net allocated payments: $50.
- Outstanding amount: $50.

Joining two invoice lines directly to two allocations produces four rows and can double both totals. Aggregate each fact to invoice level before joining. Payment allocations do not identify individual lines; reporting paid amounts by project needs an explicit allocation policy and is deferred.

Project allocations, by contrast, are explicit on invoice lines. A $60 line split $45/$15 across two projects reports $45 and $15, never $60 to both.

## Core reconciliation rules

- Net invoiced amount = posted line amounts minus reversed posted line amounts.
- Net allocated amount = posted payment allocations minus allocations reversed with their payments.
- Invoice outstanding amount = net invoiced amount minus net allocated amount, under the first-scope restrictions.
- Invoice total must equal its line total; payment total must equal its allocation total in this scope.
- Project allocations must add up to each line's amount, including an explicit unassigned allocation if allowed.
- Sum only within the agreed currency and comparable scope. Never sum daily balance snapshots across dates to describe one current balance.
- Check identities and field values in addition to sums: two incorrect records can cancel in an aggregate.
- Independently derive expected analytical values from source business tables at the same agreed source boundary. Reusing the same transformation code for expected and actual values can reproduce the same bug.

## Decisions before implementation

Confirm financial restrictions, historical organization mappings, and when to add snapshots. Then use ADRs to define transaction boundaries, CDC snapshots, past source records, fact keys, cross-table arrival order, and recovery guarantees.

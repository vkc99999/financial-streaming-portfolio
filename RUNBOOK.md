# Run the first invoice flow

## Before starting

Open Docker Desktop and a terminal in this repo. The first build downloads images, Python packages, and three Flink connector/driver JARs. PostgreSQL and Kafka stay inside Docker; API and development interfaces use localhost only.

An open Docker window does not mean its engine is ready. Startup waits up to 15 seconds for a response and will not build/start the project if that check fails. Fix Docker startup before retrying.

Images and top-level Python packages are version-pinned and integration-tested, not security-audited for production. Scala in the Flink image tag refers to its distribution; we write no Scala application code. Full dependency locking and digest pinning are planned for repeatable builds.

## First run

```bash
python3 scripts/control.py init
python3 scripts/control.py up
python3 scripts/smoke.py
```

`init` creates random local credentials and SQL with local settings filled in in Git-ignored `.env` and `.runtime/`. Keep these local. `up` starts the project, registers the source connector, and submits one Flink job. It does not start an ongoing generator. The database starts with one sample invoice dated in the past, two suppliers, and two cost centers.

`smoke.py` creates sample invoices and checks their analytics rows. It checks initial sample data, two-line decimal totals, update, posting, duplicate invoice rejection, draft delete, that posted records cannot change, and retry after an invalid line causes source rollback. It does not prove reconciliation, exactly-once behavior, or sustained freshness.

Checks passed on 2026-09-11; see the evidence directory. Database images include setup scripts, and health checks require application tables—not just a running PostgreSQL process.

The minimal reporting API is `GET /analytics/invoices` on localhost port 18780. It requires the `X-API-Key` value from your local `.env`. The smoke script reads that value without printing it. A visual dashboard is planned.

Flink's local development interface is on port 18081 and Kafka Connect on port 18083. These interfaces are not authenticated; never expose them publicly. Connector configuration may contain credentials, so avoid sharing raw configuration/log dumps.

## Tests

Without Docker, validate input rules in a virtual environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

Database tests are skipped unless explicitly enabled. With the project’s test containers running:

```bash
docker compose exec -e RUN_SOURCE_DB_TESTS=1 api python -m unittest discover -s tests -v
```

These tests create sample records in the project source database. They test actual database rollback, immutability triggers, draft changes, and the limited application role. Do not point them at an existing business database. `TEST_SOURCE_DSN` is available for a separately initialized disposable test database.

## Stop and preserve data

```bash
python3 scripts/control.py stop
```

Stops this project's containers, preserving volumes and other projects. No restart policies or scheduled jobs are configured.

**Current limitation:** after a full cluster stop/start, automatic restoration of the Flink job's join state is not implemented. The controller refuses to submit a new job over populated analytics. Preserve the volumes for the planned restore feature. Do not delete checkpoints or change consumer offsets to bypass this guard. This version supports an initial session and smoke test; repeated resume/replay demos are not ready yet.

## Inspect a failure

```bash
python3 scripts/control.py status
docker compose logs --tail 80 source analytics
docker compose logs --tail 80 connect jobmanager taskmanager
```

Do not interpret a healthy API as a healthy pipeline. Check connector tasks, Flink job state, and the reporting output separately. On any failed startup or test, run the stop command when finished so the project does not keep consuming resources.

No destructive reset command is automated. The initial sample invoice and all later posted records remain stored until you explicitly choose to reset this project's volumes.

## Next learning step after the smoke test

Inspect one source invoice and its lines, the two CDC topics, the Flink join, and the analytics rows identified by their primary keys. Explain why two invoice lines must not be joined directly to two payment allocations. Then design payments and reconciliation before adding them.

# Run the first invoice slice

## Before starting

Open Docker Desktop and wait for its engine. Use a terminal in this repository directory. The initial build downloads container images, Python packages, and three Flink connector/driver JARs. PostgreSQL and Kafka are not published to the host; API and development control interfaces bind to localhost only.

The desktop window being open does not prove the engine is ready. Startup checks this with a 15-second timeout. If it fails, resolve Docker's startup problem before retrying; no project build/start is attempted by that command until the engine responds.

Images and top-level Python packages are version-pinned and passed the first integration run; they are not security-audited production recommendations. The Flink image tag mentions Scala because of its distribution; no application Scala code is required. Full dependency locking and digest pinning are follow-up reproducibility work.

## First run

```bash
python3 scripts/control.py init
python3 scripts/control.py up
python3 scripts/smoke.py
```

`init` creates random local credentials and rendered SQL in Git-ignored `.env` and `.runtime/`. Keep these local. `up` starts the project, registers the source connector, and submits one Flink job. It does not start an ongoing generator. The database starts with one synthetic historical invoice and two suppliers/cost centers.

`smoke.py` creates a few synthetic invoices and verifies their analytical projections. It checks initial history, two-line decimal totals, update, posting, duplicate invoice rejection, draft delete, posted immutability, and retry after an invalid line causes source rollback. It does not prove reconciliation, exactly-once behavior, or sustained freshness.

These checks passed on 2026-09-11; see the evidence directory. The database images now package initialization scripts directly, and health checks require application tables to exist. This avoids treating a running but uninitialized PostgreSQL process as application-ready.

The minimal reporting API is `GET /analytics/invoices` on localhost port 18780. It requires the `X-API-Key` value from your local `.env`. The smoke script reads that value without printing it. A visual dashboard is a later slice.

Flink's local development interface is on port 18081 and Kafka Connect on port 18083. These interfaces are not authenticated; never expose them publicly. Connector configuration may contain credentials, so avoid sharing raw configuration/log dumps.

## Tests

Without Docker, validate input rules in a virtual environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

Database tests are skipped unless explicitly enabled. With the disposable project stack running:

```bash
docker compose exec -e RUN_SOURCE_DB_TESTS=1 api python -m unittest discover -s tests -v
```

These tests create synthetic records in the project source database. They test actual database rollback, immutability triggers, draft changes, and the limited application role. Do not point them at an existing business database. `TEST_SOURCE_DSN` is available for a separately initialized disposable test database.

## Stop and preserve data

```bash
python3 scripts/control.py stop
```

This stops only this Compose project's containers; it does not stop unrelated projects or delete volumes. No restart policies or scheduled jobs are configured.

**Current limitation:** after a full cluster stop/start, automatic restoration of the Flink job's join state is not implemented. The controller refuses to submit a new job over populated analytics. Preserve the volumes for the forthcoming restore implementation. Do not delete checkpoints or change consumer offsets to bypass this guard. This first slice is intended for an initial session and smoke test, not yet repeated resume/replay demos.

## Inspect a failure

```bash
python3 scripts/control.py status
docker compose logs --tail 80 source analytics
docker compose logs --tail 80 connect jobmanager taskmanager
```

Do not interpret a healthy API as a healthy pipeline. Check connector tasks, Flink job state, and the reporting output separately. On any failed startup or test, run the stop command when finished so the project does not keep consuming resources.

No destructive reset command is automated. The source snapshot fixture and all subsequent posted records persist until you explicitly choose to reset this project's volumes.

## Next learning step after the smoke test

Inspect one source invoice and its lines, the two CDC topics, the Flink join, and the keyed analytical rows. Explain why two invoice lines must not be joined directly to two payment allocations. Then design payments and reconciliation before adding them.

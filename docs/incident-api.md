# Stage 1: pipeline failure investigation

Send a problem and observations → FastAPI → LLM → validate evidence → Postgres.

The LLM suggests causes and next checks. It cannot inspect services, run commands, or repair anything. A saved result is a suggestion, not a verified diagnosis. RAG, agents, and MCP come later in that order. See [ADR 003](../ADRs/003-incident-api.md).

## Run locally

From the repo directory, with Docker Desktop running:

```bash
python3 scripts/ai_setup.py
```

Edit the generated `.env.ai` locally. Fill in `OPENAI_API_KEY` and `OPENAI_MODEL` with a model available to your account that supports Responses API Structured Outputs. Never commit this file or paste keys into chat. No default model or paid call is selected automatically.

```bash
docker compose --env-file .env.ai -f compose.ai.yaml up -d --build
python3 scripts/investigate.py examples/incident.json
```

Only the incident API and its Postgres database start. The existing streaming stack stays separate. The example contains observations from a real failure in this project; it does not send the recorded answer to the model.

To fetch a saved result, use the request ID printed by the script:

```bash
python3 scripts/investigate.py --get YOUR_REQUEST_UUID
```

The script assigns a new ID each time unless the file contains `request_id`. Reuse that ID when retrying the same submission to avoid another model call. Using it for a different report returns 409. A completed model failure is saved with `status: failed` and a safe error code; inspect the JSON status, not only HTTP 200.

Stop when finished; data remains on disk:

```bash
docker compose --env-file .env.ai -f compose.ai.yaml stop
```

## API

- `POST /investigations`: JSON with `request_id` (UUID), `symptom`, and `observations` (each has a unique `id` and `text`).
- `GET /investigations/{request_id}`: saved report and result.
- `GET /health`: database check and whether model settings are present. It does not verify model credentials.

All three API routes require `X-API-Key` from `.env.ai`. The `/docs` and OpenAPI pages are public on localhost. Port: `18781`. Only this local user shares access; multi-user permissions are not implemented.

Each report allows 20 observations, up to 2,000 characters each, and a 2,000-character symptom. The output contains `summary`, `likely_causes` with evidence quotes, `missing_information`, and `next_checks`. With insufficient evidence, it must return no causes and state what is missing.

## What is checked

Pydantic validates JSON fields. Python verifies that each cited observation exists and its quote matches the submitted text after redaction. It does not prove the cause follows from that quote. The model is instructed to ignore instructions inside logs, but model behavior still needs testing against misleading reports.

Before storage or model calls, common password, token, API-key, bearer-token, and database-URL patterns are redacted. This cannot find every secret: use sample or already-sanitized logs. Raw provider errors and report text are not written to application logs. Model requests use `store: false`; this is not a claim of zero provider retention. [Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs).

## Tests and limits

```bash
docker compose --env-file .env.ai -f compose.ai.yaml exec -T -e RUN_INCIDENT_DB_TESTS=1 incident-api python -m unittest discover -s tests -p 'test_investigation.py' -v
```

Tests cover evidence matching, missing evidence, input limits, redaction, retries, refusal, invalid output, real Postgres storage, duplicate IDs, and database permissions. Model responses in these tests are mocked: they test our code, not model accuracy.

For an initial quality check, submit the sample and compare the answer with INIT-001 in [recorded incidents](../evidence/incidents.json). Check whether it identifies missing database initialization, cites the logs, and avoids claiming it fixed anything. Use FLINK-001 as a second case and an unclear report as a third. Keep the expected answers out of model input. Two known cases are a starting point, not a quality score or full evaluation framework.

Requests are synchronous. There are at most two model attempts, a 20-second socket timeout per attempt, and a short retry delay. Token usage is saved for successful calls; billing for failed or timed-out attempts may be unknown. No automatic price estimate is provided. Use provider budget controls for live experiments.

A process crash or database failure after the model call can leave a `pending` row. Fetch its ID before doing anything else; pending does not prove the model is still running. After checking that the old process ended, a new request ID can retry at the risk of another billed call. Automatic crash recovery, workers, rate limits, and full evaluation remain later work. Records persist until manually removed by the database administrator; no cleanup schedule runs.

Validation on 2026-09-13: 12 new tests passed using local PostgreSQL 14.18 and real HTTP requests with mocked model responses. The full run passed 20 tests and skipped four existing source-database tests. A later normal Docker Desktop restart fixed the engine. Both images built, Postgres 16.9 initialized, and the same tests passed inside Python 3.12.10 containers. The host HTTP health check also passed. Containers were stopped afterward, keeping their data. Live model calls remain unverified because model settings are still empty. See [test evidence](../evidence/2026-09-13-incident-api.json).

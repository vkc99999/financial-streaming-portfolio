# ADR 003: pipeline failure investigation API

Status: accepted for stage 1 after the user asked to implement this feature.

## Requirements
Submit a symptom and numbered observations (logs or service status). Return likely causes, exact evidence quotes, missing information, and suggested checks as JSON. Save the input, result, model, prompt version, token usage, duration, and safe failure code in Postgres. Require the local API key. Run only on demand.

## Decision
Use a separate FastAPI entry point and Postgres database within this repo. Call the OpenAI Responses API with a strict JSON schema. The model gets only the submitted report, no tools or database access. Validate every cited observation ID and quote before accepting the result. These checks prove a quote exists, not that the proposed cause is true.

Use synchronous requests for this small local version: at most two model attempts, 20-second HTTP timeouts, and a short retry delay for 429/5xx/network failures. Do not retry refusal or invalid output. Store a pending row before calling; repeated request IDs return the existing result without another call. A crash can leave a pending row; do not automatically repeat a possibly billed request.

Use a dedicated database role with SELECT/INSERT/UPDATE only on investigation records. Redact common credential patterns before storage and model calls. Redaction is best effort: submit only sample or already-sanitized logs. Logs contain IDs/status/timing, never report text or provider response bodies.

## Alternatives and tradeoffs
Rules are cheaper and predictable for known errors; an LLM can consider varied reports but can be wrong. An async worker would survive HTTP disconnects more cleanly but adds services and job management. A separate database costs some memory but avoids touching financial records or requiring Kafka/Flink.

## Limits and revisit
No RAG, agent loop, MCP, repairs, or claims of verified root cause. Single-user local API; no production rate limiting or multi-user access model yet. Add workers when long requests or crash recovery require them. Compare models using known incidents before trusting suggestions. Full evaluation framework remains stage 5; basic correctness tests start now.

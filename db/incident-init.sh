#!/usr/bin/env bash
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=app_pass="$INCIDENT_PASSWORD" <<'SQL'
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE ROLE incident_api LOGIN PASSWORD :'app_pass';
CREATE TABLE investigation (
 id uuid PRIMARY KEY,
 report jsonb NOT NULL,
 status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','completed','failed')),
 result jsonb,
 model text NOT NULL,
 prompt_version text NOT NULL,
 usage jsonb NOT NULL DEFAULT '{}',
 duration_ms integer,
 attempts integer,
 error_code text,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 finished_at timestamptz
);
GRANT USAGE ON SCHEMA public TO incident_api;
GRANT SELECT,INSERT,UPDATE ON investigation TO incident_api;
SQL

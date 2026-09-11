"""Manual local lifecycle; no scheduler and no implicit data reset."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
KEYS = ("SOURCE_PASSWORD", "ANALYTICS_PASSWORD", "APP_PASSWORD", "CDC_PASSWORD",
        "WRITER_PASSWORD", "READER_PASSWORD", "API_KEY")


def require_engine():
    """The desktop UI/socket can exist while the actual engine is unavailable."""
    try:
        result = subprocess.run(["docker", "info", "--format", "{{json .ServerVersion}}"],
                                cwd=ROOT, capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Docker engine did not respond within 15 seconds. Start or restart Docker Desktop, then retry.") from None
    except FileNotFoundError:
        raise RuntimeError("Docker CLI not found. Install Docker Desktop before starting this project.") from None
    try:
        version = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        version = None
    if result.returncode or not isinstance(version, str) or not version:
        raise RuntimeError("Docker engine is unavailable. Wait for Docker Desktop to report that the engine is running, then retry.")


def compose(*args, capture=False):
    return subprocess.run(["docker", "compose", *args], cwd=ROOT, check=True,
                          text=True, capture_output=capture)


def config():
    path = ROOT / ".env"
    if not path.exists():
        raise RuntimeError("Run: python3 scripts/control.py init")
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if line and not line.startswith("#"))


def request(url, method="GET", body=None, key=None):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-API-Key"] = key
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=headers), timeout=10) as r:
        raw = r.read()
        return json.loads(raw) if raw else None


def wait_for(fn, description, timeout=120):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            result = fn()
            if result:
                return result
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = type(exc).__name__
        time.sleep(1)
    raise RuntimeError(f"Timed out waiting for {description}; last error type: {last}")


def init():
    path = ROOT / ".env"
    if not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write("".join(f"{key}={secrets.token_hex(24)}\n" for key in KEYS))
    values = config()
    runtime = ROOT / ".runtime"
    runtime.mkdir(exist_ok=True)
    sql = (ROOT / "flink/invoice.sql").read_text().replace("__WRITER_PASSWORD__", values["WRITER_PASSWORD"])
    (runtime / "invoice.sql").write_text(sql)
    print("Local credentials and SQL prepared; .env and .runtime are Git-ignored. No services started.")


def start_pipeline():
    values = config()
    wait_for(lambda: request("http://127.0.0.1:18083/connectors") is not None, "Kafka Connect")
    endpoint = "http://127.0.0.1:18083/connectors/finance-source"
    connectors = request("http://127.0.0.1:18083/connectors")
    if "finance-source" not in connectors:
        request("http://127.0.0.1:18083/connectors", "POST", {
            "name": "finance-source", "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.hostname": "source", "database.port": "5432",
                "database.user": "cdc_reader", "database.password": values["CDC_PASSWORD"],
                "database.dbname": "finance", "topic.prefix": "finance",
                "plugin.name": "pgoutput", "slot.name": "finance_slot",
                "publication.name": "finance_publication", "publication.autocreate.mode": "disabled",
                "table.include.list": "public.invoice,public.invoice_line",
                "snapshot.mode": "initial", "decimal.handling.mode": "string",
                "time.precision.mode": "connect", "heartbeat.interval.ms": "1000",
                "key.converter": "org.apache.kafka.connect.json.JsonConverter",
                "value.converter": "org.apache.kafka.connect.json.JsonConverter",
                "key.converter.schemas.enable": "true", "value.converter.schemas.enable": "true"
            }})

    def healthy_connector():
        status = request(endpoint + "/status")
        return (status["connector"]["state"] == "RUNNING" and status.get("tasks")
                and all(t["state"] == "RUNNING" for t in status["tasks"]))

    wait_for(healthy_connector, "CDC connector tasks")
    wait_for(lambda: request("http://127.0.0.1:18081/overview").get("slots-total", 0) > 0, "Flink worker")
    jobs = request("http://127.0.0.1:18081/jobs/overview")["jobs"]
    active = [j for j in jobs if j["name"] == "invoice-current-v1" and j["state"] not in ("FAILED", "CANCELED", "FINISHED")]
    if active:
        print("Invoice job already active; no duplicate submitted.")
        return
    count = compose("exec", "-T", "analytics", "psql", "-U", "analytics_admin", "-d", "analytics",
                    "-Atc", "SELECT count(*) FROM invoice_line_current", capture=True).stdout.strip()
    if int(count):
        raise RuntimeError("Analytics already contains rows but no job is active. Refusing unsafe state-less resubmission. Preserve volumes; checkpoint restore/rebuild is a later slice.")
    result = compose("run", "--rm", "sql-client", capture=True)
    combined = result.stdout + result.stderr
    if "[ERROR]" in combined or "Job ID" not in combined:
        for value in values.values():
            combined = combined.replace(value, "<redacted>")
        raise RuntimeError("SQL submission did not confirm success:\n" + combined[-6000:])
    wait_for(lambda: any(j["name"] == "invoice-current-v1" and j["state"] == "RUNNING"
                         for j in request("http://127.0.0.1:18081/jobs/overview")["jobs"]), "invoice job")
    print("CDC and invoice processing running. No ongoing workload was started.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "up", "start-pipeline", "stop", "status"])
    command = parser.parse_args().command
    if command == "init":
        init()
    elif command == "up":
        require_engine()
        init()
        compose("up", "-d", "--build", "source", "analytics", "kafka", "connect", "jobmanager", "taskmanager", "api")
        start_pipeline()
    elif command == "start-pipeline":
        require_engine()
        start_pipeline()
    elif command == "stop":
        compose("stop")
        print("Project containers stopped; data volumes retained.")
    else:
        compose("ps")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Interrupted. If containers had started, run the stop command when finished.") from None
    except (RuntimeError, subprocess.CalledProcessError, urllib.error.URLError) as exc:
        # Do not print request objects or connector payloads containing credentials.
        raise SystemExit(str(exc))

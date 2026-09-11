SET 'pipeline.name' = 'invoice-current-v1';
SET 'parallelism.default' = '1';
SET 'execution.checkpointing.interval' = '5 s';
SET 'execution.checkpointing.externalized-checkpoint-retention' = 'RETAIN_ON_CANCELLATION';
SET 'table.exec.source.cdc-events-duplicate' = 'true';
SET 'table.dml-sync' = 'false';
SET 'table.local-time-zone' = 'UTC';

CREATE TABLE source_invoice (
 id STRING,
 supplier_id STRING,
 invoice_number STRING,
 issue_date INT,
 due_date INT,
 status STRING,
 PRIMARY KEY(id) NOT ENFORCED
) WITH (
 'connector'='kafka',
 'topic'='finance.public.invoice',
 'properties.bootstrap.servers'='kafka:9092',
 'properties.group.id'='invoice-current-v1-headers',
 'scan.startup.mode'='earliest-offset',
 'format'='debezium-json',
 'debezium-json.schema-include'='true',
 'debezium-json.ignore-parse-errors'='false'
);
CREATE TABLE source_line (
 id STRING,
 invoice_id STRING,
 cost_center_id STRING,
 amount DECIMAL(18,2),
 PRIMARY KEY(id) NOT ENFORCED
) WITH (
 'connector'='kafka',
 'topic'='finance.public.invoice_line',
 'properties.bootstrap.servers'='kafka:9092',
 'properties.group.id'='invoice-current-v1-lines',
 'scan.startup.mode'='earliest-offset',
 'format'='debezium-json',
 'debezium-json.schema-include'='true',
 'debezium-json.ignore-parse-errors'='false'
);
CREATE TABLE analytics_line (
 line_id STRING,
 invoice_id STRING,
 supplier_id STRING,
 invoice_number STRING,
 issue_date DATE,
 due_date DATE,
 status STRING,
 cost_center_id STRING,
 amount DECIMAL(18,2),
 PRIMARY KEY(line_id) NOT ENFORCED
) WITH (
 'connector'='jdbc',
 'url'='jdbc:postgresql://analytics:5432/analytics?stringtype=unspecified',
 'table-name'='invoice_line_current',
 'username'='analytics_writer',
 'password'='__WRITER_PASSWORD__',
 'sink.buffer-flush.max-rows'='1',
 'sink.buffer-flush.interval'='1s',
 'sink.max-retries'='3'
);
INSERT INTO analytics_line
 SELECT l.id,i.id,i.supplier_id,i.invoice_number,
        CAST(TIMESTAMPADD(DAY,i.issue_date,DATE '1970-01-01') AS DATE),
        CAST(TIMESTAMPADD(DAY,i.due_date,DATE '1970-01-01') AS DATE),
        i.status,l.cost_center_id,l.amount
 FROM source_line l JOIN source_invoice i ON l.invoice_id=i.id;

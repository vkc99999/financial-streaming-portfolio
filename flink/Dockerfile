FROM flink:1.20.1-scala_2.12-java17
USER root
RUN mkdir -p /opt/flink/checkpoints && chown flink:flink /opt/flink/checkpoints
RUN curl -fSL --retry 3 https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.4.0-1.20/flink-sql-connector-kafka-3.4.0-1.20.jar -o /opt/flink/lib/kafka.jar \
 && curl -fSL --retry 3 https://repo.maven.apache.org/maven2/org/apache/flink/flink-connector-jdbc/3.3.0-1.20/flink-connector-jdbc-3.3.0-1.20.jar -o /opt/flink/lib/jdbc.jar \
 && curl -fSL --retry 3 https://repo.maven.apache.org/maven2/org/postgresql/postgresql/42.7.5/postgresql-42.7.5.jar -o /opt/flink/lib/postgresql.jar
USER flink

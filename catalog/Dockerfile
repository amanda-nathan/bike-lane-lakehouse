# The REST catalog fixture only ships the SQLite driver, and SQLite allows one writer at a time.
# Add the Postgres driver so the catalog can keep its table pointers in Postgres.
FROM apache/iceberg-rest-fixture:1.9.1
ADD --chmod=644 \
    --checksum=sha256:73914527305a40cce504b0d3d90b23caf565136912d607ae8ae7c5895512332c \
    https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.14/postgresql-42.7.14.jar \
    /usr/lib/iceberg-rest/postgresql.jar
CMD ["java", "-cp", "iceberg-rest-adapter.jar:postgresql.jar", "org.apache.iceberg.rest.RESTCatalogServer"]

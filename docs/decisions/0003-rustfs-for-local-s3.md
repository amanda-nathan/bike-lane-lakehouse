# 0003 RustFS for local S3

Most Iceberg examples use MinIO for local S3, but the MinIO images can't be pulled from Docker Hub or quay.io anymore. I'm using [RustFS](https://github.com/rustfs/rustfs) instead, with the AWS CLI image to create the bucket.

The catalog, Trino, and PyIceberg only talk to storage through the S3 API, so the swap was one service in `docker-compose.yml` and one hostname. Moving to AWS works the same way: change the endpoint and credentials in `src/bikelake/config.py` and `trino/catalog/iceberg.properties`.

"""Catalog, S3, and Postgres settings.

Secrets come from the environment. Running from a laptop, they're read from .env.
"""

import os

from dotenv import load_dotenv

load_dotenv()

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_REGION = os.getenv("S3_REGION", "us-east-1")

LANDING_BUCKET = os.getenv("LANDING_BUCKET", "landing")

CATALOG_PROPS = {
    "type": "rest",
    "uri": os.getenv("ICEBERG_REST_URI", "http://localhost:8181"),
    "warehouse": os.getenv("ICEBERG_WAREHOUSE", "s3://warehouse/"),
    "s3.endpoint": S3_ENDPOINT,
    "s3.access-key-id": S3_ACCESS_KEY,
    "s3.secret-access-key": S3_SECRET_KEY,
    "s3.region": S3_REGION,
    "s3.path-style-access": "true",
}

POSTGRES_DSN = "postgresql://{user}:{password}@{host}:5432/{db}".format(
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
    host=os.getenv("POSTGRES_HOST", "localhost"),
    db=os.getenv("POSTGRES_DB"),
)

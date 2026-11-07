from urllib.parse import urlparse

from pyarrow import fs

from bikelake.config import S3_ACCESS_KEY, S3_ENDPOINT, S3_REGION, S3_SECRET_KEY


def s3() -> fs.S3FileSystem:
    endpoint = urlparse(S3_ENDPOINT)
    return fs.S3FileSystem(
        endpoint_override=endpoint.netloc,
        scheme=endpoint.scheme,
        access_key=S3_ACCESS_KEY,
        secret_key=S3_SECRET_KEY,
        region=S3_REGION,
    )


def exists(filesystem: fs.FileSystem, path: str) -> bool:
    return filesystem.get_file_info(path).type == fs.FileType.File

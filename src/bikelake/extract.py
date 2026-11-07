"""Download source files into the landing bucket, one CSV per source file."""

import shutil
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import os

import requests

from bikelake import storage
from bikelake.config import LANDING_BUCKET
from bikelake.sources import Source


def landing_paths(source: Source) -> list[tuple[str, str]]:
    """(url, landing path) for each file in a source."""
    urls = source.resolve_urls()
    if len(urls) == 1:
        return [(urls[0], f"{LANDING_BUCKET}/{source.name}/{source.name}.csv")]
    paths = []
    for url in urls:
        stem = PurePosixPath(urlparse(url).path).name.removesuffix(".zip").removesuffix(".csv")
        paths.append((url, f"{LANDING_BUCKET}/{source.name}/{stem}.csv"))
    return paths


def extract(source: Source, force: bool = False) -> None:
    s3 = storage.s3()
    for url, path in landing_paths(source):
        if storage.exists(s3, path) and not force:
            print(f"skip  s3://{path} (already landed; use --force to refresh)")
            continue

        print(f"get   {url}")
        headers = {}
        # NYC Open Data throttles anonymous requests from shared cloud machines; a free app token lifts that.
        if "data.cityofnewyork.us" in url and os.getenv("SOCRATA_APP_TOKEN"):
            headers["X-App-Token"] = os.environ["SOCRATA_APP_TOKEN"]
        with tempfile.TemporaryDirectory() as tmp:
            download = Path(tmp) / "download"
            with requests.get(url, stream=True, timeout=300, headers=headers) as resp:
                resp.raise_for_status()
                with open(download, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1 << 20):
                        f.write(chunk)

            with _open_csv(download) as src, s3.open_output_stream(path) as out:
                shutil.copyfileobj(src, out, length=1 << 20)

        print(f"put   s3://{path} ({s3.get_file_info(path).size / 1e6:.1f} MB)")


@contextmanager
def _open_csv(path: Path):
    if not zipfile.is_zipfile(path):
        with open(path, "rb") as f:
            yield f
        return
    with zipfile.ZipFile(path) as archive:
        members = [m for m in archive.namelist() if m.endswith(".csv") and not m.startswith("__MACOSX")]
        if len(members) != 1:
            raise ValueError(f"expected one CSV in {path}, found {members}")
        with archive.open(members[0]) as f:
            yield f
